#!/usr/bin/env python3
"""
Enhanced Scanner Scoring System

Based on validation data analysis, this module provides improved scoring
that predicts winners vs false breakouts with higher accuracy.

Key Learnings from Oct 6, 2025 validation:
1. Pivot Width: Tight pivots (2-3%) = SUCCESS, Wide pivots (>5%) = FALSE
2. LONG vs SHORT: LONG 40% success, SHORT 25% success
3. Index ETFs: 100% false breakout rate
4. High-Vol Stocks: 75% false breakout rate

Usage:
    from enhanced_scoring import EnhancedScorer
    scorer = EnhancedScorer()
    score = scorer.score_setup(stock_data)
"""

import json
from pathlib import Path

class EnhancedScorer:
    """Enhanced scoring based on validation data"""

    def __init__(self, validation_metrics_file='validation_metrics.json'):
        """
        Initialize with validation metrics

        Args:
            validation_metrics_file: Path to validation metrics JSON
        """
        self.metrics = {}
        self.load_metrics(validation_metrics_file)

        # Default thresholds (from Oct 6 validation)
        self.optimal_pivot_width_pct = 2.51  # Median for successes
        self.max_good_pivot_width_pct = 3.5   # Upper bound for good setups
        self.max_pivot_width_pct = 4.92       # Beyond this = likely false breakout

        # Blacklist (based on validation)
        self.index_etfs = ['SPY', 'QQQ', 'DIA', 'IWM']
        self.high_vol_stocks = ['TSLA', 'NVDA', 'COIN', 'AMC', 'GME', 'HOOD', 'LCID', 'RIVN']

    def load_metrics(self, metrics_file):
        """Load validation metrics if available"""
        if Path(metrics_file).exists():
            with open(metrics_file) as f:
                data = json.load(f)
                self.metrics = data.get('metrics', {})
                print(f"✓ Loaded validation metrics from {metrics_file}")
                print(f"  Success Rate: {self.metrics.get('success_rate', 0)*100:.1f}%")
                print(f"  LONG Success: {self.metrics.get('long_success_rate', 0)*100:.1f}%")
                print(f"  SHORT Success: {self.metrics.get('short_success_rate', 0)*100:.1f}%")
        else:
            print(f"⚠️  No validation metrics found, using defaults")

    def calculate_base_score(self, stock):
        """
        Calculate base score using original scanner logic

        Args:
            stock: Dict with stock data

        Returns:
            int: Base score (0-100)
        """
        score = 50  # Start at 50

        # Distance to resistance/support
        dist_to_r = stock.get('dist_to_R%', 0)
        dist_to_s = stock.get('dist_to_S%', 0)

        if dist_to_r < 1:
            score += 25
        elif dist_to_r < 2:
            score += 15
        elif dist_to_r < 3:
            score += 10

        if dist_to_s < 1:
            score += 25
        elif dist_to_s < 2:
            score += 15
        elif dist_to_s < 3:
            score += 10

        # Risk/reward
        risk_reward = stock.get('risk_reward', 0)
        if risk_reward > 3:
            score += 20
        elif risk_reward > 2:
            score += 15
        elif risk_reward > 1.5:
            score += 10

        # Volume
        rvol = stock.get('rvol', 1.0)
        if rvol > 2.0:
            score += 15
        elif rvol > 1.5:
            score += 10

        # Volatility (ATR)
        atr_pct = stock.get('atr%', 0)
        if 2.0 <= atr_pct <= 5.0:
            score += 10  # Moderate volatility is good
        elif atr_pct > 8.0:
            score -= 10  # Too volatile

        return min(100, max(0, score))

    def calculate_pivot_width_score(self, stock):
        """
        Score based on pivot width

        KEY INSIGHT: Tight pivots (2-3%) = SUCCESS, Wide pivots (>5%) = FALSE

        Args:
            stock: Dict with resistance, support

        Returns:
            int: Adjustment (-30 to +20)
        """
        resistance = stock.get('resistance')
        support = stock.get('support')

        if not resistance or not support:
            return 0

        pivot_width = resistance - support
        pivot_width_pct = (pivot_width / support) * 100

        # Store for reference
        stock['pivot_width_pct'] = pivot_width_pct

        # Scoring based on validation data
        if pivot_width_pct <= self.optimal_pivot_width_pct:
            # Very tight pivot (2-2.5%) - EXCELLENT
            return +20
        elif pivot_width_pct <= self.max_good_pivot_width_pct:
            # Good pivot width (2.5-3.5%) - GOOD
            return +10
        elif pivot_width_pct <= self.max_pivot_width_pct:
            # Acceptable but risky (3.5-5%) - NEUTRAL
            return 0
        elif pivot_width_pct <= 7.0:
            # Wide pivot (5-7%) - PENALIZE
            return -15
        else:
            # Very wide pivot (>7%) - STRONGLY PENALIZE
            return -30

    def calculate_direction_score(self, stock, side):
        """
        Score based on LONG vs SHORT direction

        KEY INSIGHT: LONG 40% success, SHORT 25% success

        Args:
            stock: Dict with stock data
            side: 'LONG' or 'SHORT'

        Returns:
            int: Adjustment (-20 to +10)
        """
        if side == 'LONG':
            # LONG has better success rate (40%)
            return +10
        elif side == 'SHORT':
            # SHORT has worse success rate (25%)
            return -20
        return 0

    def calculate_symbol_penalty(self, symbol):
        """
        Penalty for problematic symbols

        KEY INSIGHT: Index ETFs and high-vol stocks have high false breakout rates

        Args:
            symbol: Stock symbol

        Returns:
            int: Penalty (0 to -40)
        """
        penalty = 0

        # Index ETFs (100% false breakout rate)
        if symbol in self.index_etfs:
            penalty -= 40

        # High-volatility stocks (75% false breakout rate)
        if symbol in self.high_vol_stocks:
            penalty -= 25

        return penalty

    def calculate_move_quality_score(self, stock):
        """
        Score based on expected move quality

        Args:
            stock: Dict with target, resistance, etc.

        Returns:
            int: Adjustment (-10 to +15)
        """
        score = 0

        # Check if we have enough room to target
        resistance = stock.get('resistance')
        target1 = stock.get('target1')

        if resistance and target1:
            move_to_target_pct = ((target1 - resistance) / resistance) * 100

            # Validation showed successful moves averaged 1.98%
            # Best moves were 2-4.5%
            if move_to_target_pct >= 3.0:
                score += 15  # Excellent move potential
            elif move_to_target_pct >= 2.0:
                score += 10  # Good move potential
            elif move_to_target_pct < 1.0:
                score -= 10  # Too tight target

        return score

    def score_setup(self, stock, side='LONG'):
        """
        Calculate enhanced score for a setup

        Args:
            stock: Dict with stock data (resistance, support, etc.)
            side: 'LONG' or 'SHORT'

        Returns:
            dict with score and breakdown
        """
        symbol = stock.get('symbol', stock.get('Symbol', ''))

        # Calculate components
        base_score = self.calculate_base_score(stock)
        pivot_adj = self.calculate_pivot_width_score(stock)
        direction_adj = self.calculate_direction_score(stock, side)
        symbol_penalty = self.calculate_symbol_penalty(symbol)
        move_quality_adj = self.calculate_move_quality_score(stock)

        # Total enhanced score
        total_score = base_score + pivot_adj + direction_adj + symbol_penalty + move_quality_adj
        total_score = min(100, max(0, total_score))

        return {
            'total_score': total_score,
            'base_score': base_score,
            'adjustments': {
                'pivot_width': pivot_adj,
                'direction': direction_adj,
                'symbol_penalty': symbol_penalty,
                'move_quality': move_quality_adj
            },
            'pivot_width_pct': stock.get('pivot_width_pct', 0),
            'recommendation': self._get_recommendation(total_score)
        }

    def _get_recommendation(self, score):
        """Get trading recommendation based on score"""
        if score >= 80:
            return 'STRONG BUY'
        elif score >= 70:
            return 'BUY'
        elif score >= 60:
            return 'CONSIDER'
        elif score >= 50:
            return 'NEUTRAL'
        else:
            return 'AVOID'

    def rescore_scanner_output(self, scanner_file, output_file=None):
        """
        Rescore existing scanner output with enhanced scoring

        Args:
            scanner_file: Path to scanner CSV or JSON
            output_file: Optional output file path

        Returns:
            list of rescored stocks
        """
        import csv

        # Load scanner data
        stocks = []
        with open(scanner_file) as f:
            if scanner_file.endswith('.json'):
                stocks = json.load(f)
            else:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    for key in ['close', 'resistance', 'support', 'target1', 'risk_reward',
                                'dist_to_R%', 'dist_to_S%', 'rvol', 'atr%']:
                        if key in row and row[key]:
                            try:
                                row[key] = float(row[key])
                            except:
                                pass
                    stocks.append(row)

        print(f"✓ Loaded {len(stocks)} stocks from scanner")

        # Rescore each
        rescored = []
        for stock in stocks:
            # Score for both LONG and SHORT
            long_score_data = self.score_setup(stock, 'LONG')
            short_score_data = self.score_setup(stock, 'SHORT')

            stock['enhanced_long_score'] = long_score_data['total_score']
            stock['enhanced_short_score'] = short_score_data['total_score']
            stock['long_recommendation'] = long_score_data['recommendation']
            stock['short_recommendation'] = short_score_data['recommendation']
            stock['pivot_width_pct'] = long_score_data['pivot_width_pct']

            # Best overall score
            stock['best_enhanced_score'] = max(long_score_data['total_score'],
                                               short_score_data['total_score'])

            rescored.append(stock)

        # Sort by best score
        rescored.sort(key=lambda x: x['best_enhanced_score'], reverse=True)

        # Print top 10
        print("\n" + "="*80)
        print("TOP 10 SETUPS (Enhanced Scoring)")
        print("="*80)
        for i, stock in enumerate(rescored[:10], 1):
            symbol = stock.get('symbol', stock.get('Symbol', ''))
            long_score = stock['enhanced_long_score']
            short_score = stock['enhanced_short_score']
            pivot_width = stock.get('pivot_width_pct', 0)

            print(f"{i:2}. {symbol:6} - LONG:{long_score:3.0f} SHORT:{short_score:3.0f} "
                  f"(pivot {pivot_width:.2f}%) - {stock['long_recommendation']}")

        # Save if requested
        if output_file:
            with open(output_file, 'w') as f:
                if output_file.endswith('.json'):
                    json.dump(rescored, f, indent=2, default=str)
                else:
                    writer = csv.DictWriter(f, fieldnames=rescored[0].keys())
                    writer.writeheader()
                    writer.writerows(rescored)
            print(f"\n✓ Rescored data saved to: {output_file}")

        return rescored

def main():
    """Demo usage"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python enhanced_scoring.py <scanner_file> [output_file]")
        print("Example: python enhanced_scoring.py scanner_results.csv rescored_output.csv")
        sys.exit(1)

    scanner_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    scorer = EnhancedScorer()
    scorer.rescore_scanner_output(scanner_file, output_file)

if __name__ == '__main__':
    main()
