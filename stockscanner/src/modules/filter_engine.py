"""
PS60 Filter Engine Module
Applies PS60 trading strategy filters to identify candidates
Following exact requirements from the specification
"""

from typing import Dict, Any, List, Tuple
from datetime import datetime
from loguru import logger


class PS60FilterEngine:
    """Apply PS60 filters to identify trading candidates"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize filter engine with PS60 criteria

        Args:
            config: Configuration dictionary with filter settings
        """
        self.config = config
        self.filters = config.get('filters', {})
        self.risk = config.get('risk', {})

    def apply_gap_filter(self, stock_data: Dict[str, Any]) -> bool:
        """
        Apply gap percentage filter

        Args:
            stock_data: Processed stock data

        Returns:
            True if passes gap filter
        """
        gap_threshold = self.filters.get('gap_threshold', 2.0)
        gap_pct = abs(stock_data.get('gap_pct', 0))

        passed = gap_pct >= gap_threshold

        if not passed:
            logger.debug(f"{stock_data['symbol']}: Gap {gap_pct}% < threshold {gap_threshold}%")

        return passed

    def apply_volume_filter(self, stock_data: Dict[str, Any]) -> bool:
        """
        Apply relative volume (RVOL) filter

        Args:
            stock_data: Processed stock data

        Returns:
            True if passes volume filter
        """
        rvol_threshold = self.filters.get('rvol_threshold', 2.0)
        rvol = stock_data.get('rvol', 0)

        passed = rvol >= rvol_threshold

        if not passed:
            logger.debug(f"{stock_data['symbol']}: RVOL {rvol} < threshold {rvol_threshold}")

        return passed

    def apply_pattern_filter(self, stock_data: Dict[str, Any]) -> bool:
        """
        Apply chart pattern filter

        Args:
            stock_data: Processed stock data

        Returns:
            True if has relevant patterns
        """
        if not self.filters.get('enable_pattern_detection', True):
            return True

        patterns = stock_data.get('patterns', {})

        # Check for any significant pattern
        has_pattern = (
            patterns.get('base_detected', False) or
            patterns.get('consolidation', False) or
            patterns.get('breakout_pending', False)
        )

        if not has_pattern and patterns.get('pattern_description', ''):
            # Consider any described pattern as valid
            has_pattern = True

        return has_pattern

    def apply_room_to_run_filter(self, stock_data: Dict[str, Any]) -> bool:
        """
        Apply room to run filter (check for obstacles)

        Args:
            stock_data: Processed stock data

        Returns:
            True if has room to run
        """
        room_analysis = stock_data.get('room_analysis', {})

        # If no room analysis, pass by default
        if not room_analysis:
            return True

        has_room = room_analysis.get('has_room', True)

        if not has_room:
            obstacle = room_analysis.get('obstacle', 'resistance')
            distance = room_analysis.get('distance_pct', 0)
            logger.debug(f"{stock_data['symbol']}: No room to run - {obstacle} at {distance}% away")

        return has_room

    def check_news_catalyst(self, stock_data: Dict[str, Any]) -> float:
        """
        Check for news catalyst and apply weighting

        Args:
            stock_data: Processed stock data

        Returns:
            News weight multiplier
        """
        news = stock_data.get('news', [])
        news_weight = self.filters.get('news_weight', 1.5)

        if news and len(news) > 0:
            return news_weight

        return 1.0

    def calculate_risk_reward(
        self,
        stock_data: Dict[str, Any],
        direction: str
    ) -> Dict[str, float]:
        """
        Calculate risk/reward ratio for the setup

        Args:
            stock_data: Processed stock data
            direction: 'long' or 'short'

        Returns:
            Dictionary with risk/reward metrics
        """
        current_price = stock_data.get('current_price', 0)
        min_rr = self.risk.get('min_reward_risk_ratio', 1.0)

        if direction == 'long':
            entry = stock_data.get('pivot_high', current_price)
            stop = stock_data.get('daily_low', entry * 0.98)  # Default 2% stop
            room_analysis = stock_data.get('room_analysis', {})
            target = room_analysis.get('next_level')
            if target is None or target <= entry:
                target = entry * 1.02  # Default 2% target

        else:  # short
            entry = stock_data.get('pivot_low', current_price)
            stop = stock_data.get('daily_high', entry * 1.02)
            room_analysis = stock_data.get('room_analysis', {})
            target = room_analysis.get('next_level')
            if target is None or target >= entry:
                target = entry * 0.98  # Default 2% target

        # Calculate risk and reward
        risk = abs(entry - stop)
        reward = abs(target - entry)

        if risk > 0:
            rr_ratio = reward / risk
        else:
            rr_ratio = 0

        return {
            'entry': entry,
            'stop': stop,
            'target': target,
            'risk': risk,
            'reward': reward,
            'rr_ratio': round(rr_ratio, 2),
            'meets_minimum': rr_ratio >= min_rr
        }

    def score_candidate(self, stock_data: Dict[str, Any]) -> float:
        """
        Score a candidate based on multiple factors

        Args:
            stock_data: Processed stock data

        Returns:
            Composite score (0-100)
        """
        score = 0

        # Gap score (up to 30 points)
        gap_pct = abs(stock_data.get('gap_pct', 0))
        gap_score = min(gap_pct * 5, 30)  # 6% gap = max 30 points
        score += gap_score

        # Volume score (up to 30 points)
        rvol = stock_data.get('rvol', 0)
        rvol_score = min(rvol * 10, 30)  # RVOL 3.0 = max 30 points
        score += rvol_score

        # Pattern score (up to 20 points)
        patterns = stock_data.get('patterns', {})
        if patterns.get('base_detected'):
            score += 10
        if patterns.get('breakout_pending'):
            score += 10

        # Room to run score (up to 20 points)
        room_analysis = stock_data.get('room_analysis', {})
        if room_analysis.get('has_room', False):
            distance = room_analysis.get('distance_pct', 0)
            room_score = min(distance * 2, 20)  # 10% room = max 20 points
            score += room_score

        # Apply news multiplier
        news_weight = self.check_news_catalyst(stock_data)
        score *= news_weight

        return min(score, 100)  # Cap at 100

    def generate_rationale(self, stock_data: Dict[str, Any], direction: str) -> str:
        """
        Generate human-readable rationale for the candidate

        Args:
            stock_data: Processed stock data
            direction: 'long' or 'short'

        Returns:
            Rationale string
        """
        rationale_parts = []

        # Gap information
        gap_pct = stock_data.get('gap_pct', 0)
        if abs(gap_pct) > 0:
            gap_dir = "up" if gap_pct > 0 else "down"
            rationale_parts.append(f"Stock is {gap_dir} {abs(gap_pct)}% from yesterday's close in pre-market")

        # Volume information
        rvol = stock_data.get('rvol', 0)
        if rvol > 1:
            rationale_parts.append(f"Trading at {rvol}x normal volume")

        # Pattern information
        patterns = stock_data.get('patterns', {})
        if patterns.get('pattern_description'):
            rationale_parts.append(patterns['pattern_description'])

        # Room to run information
        room_analysis = stock_data.get('room_analysis', {})
        if room_analysis.get('next_level'):
            level = room_analysis['next_level']
            obstacle = room_analysis.get('obstacle', 'resistance')
            distance = room_analysis.get('distance_pct', 0)

            if direction == 'long':
                rationale_parts.append(f"Next resistance at ${level:.2f} ({obstacle}), {distance}% away")
            else:
                rationale_parts.append(f"Next support at ${level:.2f} ({obstacle}), {distance}% away")

        # News catalyst
        news = stock_data.get('news', [])
        if news:
            rationale_parts.append("News catalyst present")

        # Risk/reward
        rr_metrics = self.calculate_risk_reward(stock_data, direction)
        if rr_metrics['meets_minimum']:
            rationale_parts.append(f"Risk/Reward ratio: {rr_metrics['rr_ratio']}:1")

        return ". ".join(rationale_parts)

    def filter_candidates(
        self,
        stocks_data: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter and categorize stocks into long and short candidates

        Args:
            stocks_data: List of processed stock data

        Returns:
            Tuple of (long_candidates, short_candidates)
        """
        long_candidates = []
        short_candidates = []

        for stock_data in stocks_data:
            # Skip invalid data
            if not stock_data.get('valid', False):
                continue

            # Apply filters
            passes_gap = self.apply_gap_filter(stock_data)
            passes_volume = self.apply_volume_filter(stock_data)
            passes_pattern = self.apply_pattern_filter(stock_data)
            passes_room = self.apply_room_to_run_filter(stock_data)

            # Must pass gap and volume filters at minimum
            if not (passes_gap and passes_volume):
                continue

            # Score the candidate
            score = self.score_candidate(stock_data)

            # Determine direction based on gap
            gap_pct = stock_data.get('gap_pct', 0)
            direction = 'long' if gap_pct > 0 else 'short'

            # Calculate risk/reward
            rr_metrics = self.calculate_risk_reward(stock_data, direction)

            # Generate rationale
            rationale = self.generate_rationale(stock_data, direction)

            # Create candidate entry
            candidate = {
                'symbol': stock_data['symbol'],
                'direction': direction,
                'score': score,
                'gap_pct': gap_pct,
                'rvol': stock_data.get('rvol', 0),
                'current_price': stock_data.get('current_price', 0),
                'pivot_high': stock_data.get('pivot_high', 0),
                'pivot_low': stock_data.get('pivot_low', 0),
                'entry': rr_metrics['entry'],
                'stop': rr_metrics['stop'],
                'target': rr_metrics['target'],
                'rr_ratio': rr_metrics['rr_ratio'],
                'rationale': rationale,
                'patterns': stock_data.get('patterns', {}),
                'room_analysis': stock_data.get('room_analysis', {}),
                'passes_all_filters': passes_pattern and passes_room
            }

            # Categorize by direction
            if direction == 'long':
                long_candidates.append(candidate)
            else:
                short_candidates.append(candidate)

        # Sort by score (highest first)
        long_candidates.sort(key=lambda x: x['score'], reverse=True)
        short_candidates.sort(key=lambda x: x['score'], reverse=True)

        # Apply max candidate limits
        max_long = self.config.get('output', {}).get('max_long_candidates', 10)
        max_short = self.config.get('output', {}).get('max_short_candidates', 10)

        long_candidates = long_candidates[:max_long]
        short_candidates = short_candidates[:max_short]

        logger.info(f"Filtered to {len(long_candidates)} long and {len(short_candidates)} short candidates")

        return long_candidates, short_candidates

    def assess_market_context(
        self,
        index_data: Dict[str, Any],
        candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Assess overall market context

        Args:
            index_data: Market index data (futures, etc.)
            candidates: All filtered candidates

        Returns:
            Market context assessment
        """
        context = {
            'timestamp': datetime.now(),
            'bias': 'neutral',
            'volatility': 'normal',
            'summary': ''
        }

        # Analyze index futures
        if index_data:
            nasdaq_change = index_data.get('nasdaq_futures_pct', 0)
            sp_change = index_data.get('sp_futures_pct', 0)

            # Determine bias
            if nasdaq_change > 1 and sp_change > 0.5:
                context['bias'] = 'bullish'
            elif nasdaq_change < -1 and sp_change < -0.5:
                context['bias'] = 'bearish'

            context['summary'] = f"Nasdaq futures {nasdaq_change:+.2f}%, S&P futures {sp_change:+.2f}%"

        # Analyze candidate distribution
        long_count = sum(1 for c in candidates if c.get('direction') == 'long')
        short_count = sum(1 for c in candidates if c.get('direction') == 'short')

        if long_count > short_count * 2:
            context['summary'] += f". Strong bullish sentiment ({long_count} longs vs {short_count} shorts)"
            if context['bias'] == 'neutral':
                context['bias'] = 'bullish'
        elif short_count > long_count * 2:
            context['summary'] += f". Strong bearish sentiment ({short_count} shorts vs {long_count} longs)"
            if context['bias'] == 'neutral':
                context['bias'] = 'bearish'
        else:
            context['summary'] += f". Mixed sentiment ({long_count} longs, {short_count} shorts)"

        # Check average gap percentages
        avg_gap = sum(abs(c.get('gap_pct', 0)) for c in candidates) / len(candidates) if candidates else 0
        if avg_gap > 3:
            context['volatility'] = 'elevated'
            context['summary'] += f". Elevated volatility (avg gap {avg_gap:.1f}%)"

        return context