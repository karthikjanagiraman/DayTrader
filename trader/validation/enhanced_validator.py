#!/usr/bin/env python3
"""
Enhanced Validation Script - Comprehensive Analysis of Entry Decisions
Created: October 27, 2025
Purpose: Validate entry decisions, identify missed winners, analyze losing trades
"""

import json
import sys
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
import logging
from ib_insync import IB, Stock, util
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class EnhancedValidator:
    """Enhanced validator with comprehensive analysis capabilities"""

    def __init__(self, scanner_file: str, entry_log_file: str,
                 trade_log_file: Optional[str], date: str, account_size: int = 50000):
        """
        Initialize validator with all necessary data

        Args:
            scanner_file: Path to scanner results JSON
            entry_log_file: Path to entry decisions log JSON
            trade_log_file: Optional path to actual trades JSON
            date: Date to validate (YYYY-MM-DD)
            account_size: Account size for P&L calculations
        """
        self.scanner_file = scanner_file
        self.entry_log_file = entry_log_file
        self.trade_log_file = trade_log_file
        self.date = date
        self.account_size = account_size

        # Load data
        self.scanner_data = self._load_json(scanner_file)
        self.entry_log = self._load_json(entry_log_file)
        self.trades = self._load_json(trade_log_file) if trade_log_file else []

        # Connect to IBKR for market data
        self.ib = None
        self._connect_ibkr()

        # Analysis results
        self.missed_winners = []
        self.false_entries = []
        self.correct_blocks = []
        self.correct_entries = []
        self.filter_stats = defaultdict(lambda: {'blocks': 0, 'missed_winners': 0, 'saved_losses': 0})

    def _load_json(self, filepath: str) -> dict:
        """Load JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {filepath}: {e}")
            return {}

    def _connect_ibkr(self):
        """Connect to IBKR for fetching market data"""
        try:
            self.ib = IB()
            self.ib.connect('127.0.0.1', 7497, clientId=9002)
            logger.info("✓ Connected to IBKR for market data validation")
        except Exception as e:
            logger.warning(f"Could not connect to IBKR: {e}")
            logger.warning("Proceeding without market data validation")

    def analyze(self) -> Dict:
        """Run comprehensive analysis"""
        logger.info("=" * 80)
        logger.info("ENHANCED VALIDATION ANALYSIS")
        logger.info("=" * 80)

        # Step 1: Analyze missed winners
        self._analyze_missed_winners()

        # Step 2: Analyze losing trades
        self._analyze_losing_trades()

        # Step 3: Analyze filter effectiveness
        self._analyze_filter_effectiveness()

        # Step 4: Generate recommendations
        recommendations = self._generate_recommendations()

        # Step 5: Calculate financial impact
        financial_impact = self._calculate_financial_impact()

        # Compile results
        results = {
            'date': self.date,
            'summary': {
                'total_attempts': self.entry_log.get('total_attempts', 0),
                'entered': self.entry_log.get('entered', 0),
                'blocked': self.entry_log.get('blocked', 0),
                'missed_winners': len(self.missed_winners),
                'false_entries': len(self.false_entries),
                'correct_blocks': len(self.correct_blocks),
                'correct_entries': len(self.correct_entries)
            },
            'missed_winners': self.missed_winners,
            'false_entries': self.false_entries,
            'filter_stats': dict(self.filter_stats),
            'recommendations': recommendations,
            'financial_impact': financial_impact
        }

        # Generate report
        self._generate_report(results)

        return results

    def _analyze_missed_winners(self):
        """Identify and analyze missed winning trades"""
        logger.info("\n" + "=" * 80)
        logger.info("ANALYZING MISSED WINNERS")
        logger.info("=" * 80)

        # Get all blocked attempts
        blocked_attempts = [a for a in self.entry_log.get('attempts', [])
                           if a.get('decision') == 'BLOCKED']

        # Group by symbol and time window
        attempts_by_symbol = defaultdict(list)
        for attempt in blocked_attempts:
            symbol = attempt.get('symbol')
            attempts_by_symbol[symbol].append(attempt)

        # For each symbol, check if it was a winner
        for symbol, attempts in attempts_by_symbol.items():
            # Get scanner data for symbol
            stock_data = next((s for s in self.scanner_data if s['symbol'] == symbol), None)
            if not stock_data:
                continue

            # Fetch market data to check if targets were hit
            if self.ib:
                winner_data = self._check_if_winner(symbol, stock_data, attempts)
                if winner_data:
                    self.missed_winners.append(winner_data)
                    self._analyze_blocking_reason(winner_data)

    def _check_if_winner(self, symbol: str, stock_data: dict, attempts: List[dict]) -> Optional[dict]:
        """Check if blocked trade would have been a winner"""
        try:
            # Fetch 1-minute bars for the day
            contract = Stock(symbol, 'SMART', 'USD')
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=f"{self.date} 16:00:00",
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                return None

            # Convert to dataframe
            df = util.df(bars)

            # Check for breakouts and target hits
            resistance = stock_data.get('resistance')
            support = stock_data.get('support')
            target1 = stock_data.get('target1')

            # Find breakout points
            for idx, row in df.iterrows():
                # Long breakout
                if row['close'] > resistance:
                    # Check if target was hit
                    future_bars = df[idx:idx+30]  # Next 30 minutes
                    if not future_bars.empty:
                        max_price = future_bars['high'].max()
                        if max_price >= target1:
                            # This was a winner!
                            gain_pct = ((max_price - resistance) / resistance) * 100

                            # Find corresponding blocked attempt
                            timestamp = row['date']
                            blocked_attempt = self._find_blocked_attempt(attempts, timestamp, 'LONG')

                            if blocked_attempt:
                                return {
                                    'symbol': symbol,
                                    'type': 'LONG',
                                    'timestamp': timestamp,
                                    'breakout_price': row['close'],
                                    'max_price': max_price,
                                    'gain_pct': gain_pct,
                                    'target_hit': True,
                                    'blocked_reason': blocked_attempt.get('reason'),
                                    'filters': blocked_attempt.get('filters', {}),
                                    'confirmation_sequence': self._get_confirmation_sequence(
                                        attempts, timestamp
                                    )
                                }

                # Short breakout
                elif row['close'] < support:
                    # Similar logic for shorts
                    future_bars = df[idx:idx+30]
                    if not future_bars.empty:
                        min_price = future_bars['low'].min()
                        downside1 = stock_data.get('downside1')
                        if downside1 and min_price <= downside1:
                            gain_pct = ((support - min_price) / support) * 100

                            timestamp = row['date']
                            blocked_attempt = self._find_blocked_attempt(attempts, timestamp, 'SHORT')

                            if blocked_attempt:
                                return {
                                    'symbol': symbol,
                                    'type': 'SHORT',
                                    'timestamp': timestamp,
                                    'breakout_price': row['close'],
                                    'min_price': min_price,
                                    'gain_pct': gain_pct,
                                    'target_hit': True,
                                    'blocked_reason': blocked_attempt.get('reason'),
                                    'filters': blocked_attempt.get('filters', {}),
                                    'confirmation_sequence': self._get_confirmation_sequence(
                                        attempts, timestamp
                                    )
                                }

        except Exception as e:
            logger.error(f"Error checking winner for {symbol}: {e}")

        return None

    def _find_blocked_attempt(self, attempts: List[dict], timestamp, side: str) -> Optional[dict]:
        """Find blocked attempt near timestamp"""
        for attempt in attempts:
            if attempt.get('side') != side:
                continue

            # Check if within 5 minutes
            attempt_time = datetime.fromisoformat(attempt['timestamp'])
            if abs((timestamp - attempt_time).total_seconds()) < 300:
                return attempt

        return None

    def _get_confirmation_sequence(self, attempts: List[dict], breakout_time) -> List[dict]:
        """Get all retry attempts for a breakout"""
        sequence = []

        for attempt in attempts:
            attempt_time = datetime.fromisoformat(attempt['timestamp'])
            if abs((breakout_time - attempt_time).total_seconds()) < 300:
                sequence.append({
                    'timestamp': attempt['timestamp'],
                    'reason': attempt.get('reason'),
                    'phase': attempt.get('phase'),
                    'filters': attempt.get('filters', {})
                })

        return sorted(sequence, key=lambda x: x['timestamp'])

    def _analyze_blocking_reason(self, winner_data: dict):
        """Analyze why a winner was blocked"""
        filters = winner_data.get('filters', {})

        # Track which filters blocked winners
        for filter_name, filter_data in filters.items():
            if isinstance(filter_data, dict) and filter_data.get('result') == 'BLOCK':
                self.filter_stats[filter_name]['missed_winners'] += 1

                # Special handling for volume filter
                if filter_name == 'volume' and 'volume_ratio' in winner_data:
                    ratio = winner_data['volume_ratio']
                    logger.info(f"  Volume was {ratio:.2f}x (threshold 1.0x)")

    def _analyze_losing_trades(self):
        """Analyze actual losing trades taken"""
        logger.info("\n" + "=" * 80)
        logger.info("ANALYZING LOSING TRADES")
        logger.info("=" * 80)

        if not self.trades:
            logger.info("No trade log provided, skipping losing trade analysis")
            return

        for trade in self.trades:
            if trade.get('pnl', 0) < 0:
                # This is a losing trade
                symbol = trade['symbol']
                entry_time = trade['entry_time']
                exit_reason = trade['reason']
                loss = trade['pnl']

                # Find corresponding entry attempt
                entry_attempt = self._find_entry_attempt(symbol, entry_time)

                if entry_attempt:
                    # Analyze why this trade was entered
                    filters = entry_attempt.get('filters', {})

                    # Check if any filters should have blocked it
                    should_have_blocked = False
                    blocking_filters = []

                    for filter_name, filter_data in filters.items():
                        if isinstance(filter_data, dict):
                            if filter_data.get('result') == 'BLOCK':
                                should_have_blocked = True
                                blocking_filters.append(filter_name)

                    if should_have_blocked:
                        self.false_entries.append({
                            'symbol': symbol,
                            'entry_time': entry_time,
                            'loss': loss,
                            'exit_reason': exit_reason,
                            'should_have_blocked': blocking_filters,
                            'bug': 'Filters not enforced'
                        })

                    # Check if 7-minute rule saved us
                    if exit_reason == '7MIN_RULE':
                        logger.info(f"  {symbol}: 7-minute rule saved from larger loss (lost ${abs(loss):.2f})")

    def _find_entry_attempt(self, symbol: str, entry_time: str) -> Optional[dict]:
        """Find entry attempt for a trade"""
        for attempt in self.entry_log.get('attempts', []):
            if attempt.get('symbol') == symbol and attempt.get('decision') == 'ENTERED':
                # Check if times are close
                attempt_time = datetime.fromisoformat(attempt['timestamp'])
                trade_time = datetime.fromisoformat(entry_time)
                if abs((trade_time - attempt_time).total_seconds()) < 60:
                    return attempt
        return None

    def _analyze_filter_effectiveness(self):
        """Analyze effectiveness of each filter"""
        logger.info("\n" + "=" * 80)
        logger.info("FILTER EFFECTIVENESS ANALYSIS")
        logger.info("=" * 80)

        blocks_by_filter = self.entry_log.get('blocks_by_filter', {})

        for filter_name, block_count in blocks_by_filter.items():
            self.filter_stats[filter_name]['blocks'] = block_count

            # Estimate value saved (assume $150 per block on average)
            self.filter_stats[filter_name]['saved_losses'] = block_count * 150

        # Sort by effectiveness
        sorted_filters = sorted(
            self.filter_stats.items(),
            key=lambda x: x[1]['blocks'],
            reverse=True
        )

        logger.info("\nTOP BLOCKING FILTERS:")
        for idx, (filter_name, stats) in enumerate(sorted_filters[:5], 1):
            blocks = stats['blocks']
            missed = stats['missed_winners']
            saved = stats['saved_losses']
            net_value = saved - (missed * 500)  # Assume $500 lost per missed winner

            logger.info(f"{idx}. {filter_name}:")
            logger.info(f"   Blocks: {blocks}")
            logger.info(f"   Missed winners: {missed}")
            logger.info(f"   Est. net value: ${net_value:,.0f}")

    def _generate_recommendations(self) -> List[dict]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []

        # Check volume filter performance
        volume_stats = self.filter_stats.get('volume_filter', {})
        if volume_stats.get('missed_winners', 0) > 5:
            recommendations.append({
                'priority': 'HIGH',
                'filter': 'volume_filter',
                'action': 'LOOSEN',
                'current': '1.0x',
                'recommended': '0.75x',
                'reason': f"Blocked {volume_stats['missed_winners']} winners",
                'expected_impact': f"+${volume_stats['missed_winners'] * 500:,.0f}/day"
            })

        # Check CVD filter
        cvd_stats = self.filter_stats.get('cvd_monitoring', {})
        if cvd_stats.get('missed_winners', 0) > 3:
            recommendations.append({
                'priority': 'HIGH',
                'filter': 'cvd_monitoring',
                'action': 'ADJUST',
                'current': 'imbalance_threshold: 10.0%',
                'recommended': 'imbalance_threshold: 5.0%',
                'reason': f"Blocked {cvd_stats['missed_winners']} winners",
                'expected_impact': f"+${cvd_stats['missed_winners'] * 400:,.0f}/day"
            })

        # Check for excessive blocks
        total_blocks = self.entry_log.get('blocked', 0)
        total_attempts = self.entry_log.get('total_attempts', 1)
        block_rate = total_blocks / total_attempts if total_attempts > 0 else 0

        if block_rate > 0.95:
            recommendations.append({
                'priority': 'CRITICAL',
                'filter': 'overall',
                'action': 'REVIEW',
                'current': f'{block_rate:.1%} block rate',
                'recommended': '85-90% block rate',
                'reason': 'Filters too conservative overall',
                'expected_impact': 'More trading opportunities'
            })

        return recommendations

    def _calculate_financial_impact(self) -> dict:
        """Calculate financial impact of missed opportunities and false entries"""

        # Calculate missed winner impact
        missed_pnl = 0
        for winner in self.missed_winners:
            # Estimate P&L based on gain percentage
            position_size = min(1000, self.account_size * 0.01 / 0.50)  # 1% risk, $0.50 stop
            estimated_pnl = position_size * (winner['gain_pct'] / 100) * winner.get('breakout_price', 100)
            missed_pnl += estimated_pnl

        # Calculate false entry losses
        false_entry_losses = sum(entry['loss'] for entry in self.false_entries)

        # Calculate potential improvement
        potential_improvement = missed_pnl - false_entry_losses

        return {
            'missed_winner_value': missed_pnl,
            'false_entry_losses': false_entry_losses,
            'potential_improvement': potential_improvement,
            'potential_daily_return': (potential_improvement / self.account_size) * 100,
            'potential_monthly_return': (potential_improvement * 20 / self.account_size) * 100
        }

    def _generate_report(self, results: dict):
        """Generate comprehensive report"""
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION REPORT SUMMARY")
        logger.info("=" * 80)

        summary = results['summary']
        financial = results['financial_impact']

        # Summary stats
        logger.info(f"\nDECISION SUMMARY:")
        logger.info(f"  Total attempts: {summary['total_attempts']}")
        logger.info(f"  Entered: {summary['entered']} ({summary['entered']/summary['total_attempts']*100:.1f}%)")
        logger.info(f"  Blocked: {summary['blocked']} ({summary['blocked']/summary['total_attempts']*100:.1f}%)")

        # Quality metrics
        logger.info(f"\nQUALITY METRICS:")
        logger.info(f"  Missed winners: {summary['missed_winners']}")
        logger.info(f"  False entries: {summary['false_entries']}")
        logger.info(f"  Correct blocks: {summary['correct_blocks']}")
        logger.info(f"  Correct entries: {summary['correct_entries']}")

        # Financial impact
        logger.info(f"\nFINANCIAL IMPACT:")
        logger.info(f"  Missed winner value: ${financial['missed_winner_value']:,.2f}")
        logger.info(f"  False entry losses: ${abs(financial['false_entry_losses']):,.2f}")
        logger.info(f"  Potential improvement: ${financial['potential_improvement']:,.2f}")
        logger.info(f"  Potential daily return: {financial['potential_daily_return']:.2f}%")

        # Top recommendations
        logger.info(f"\nTOP RECOMMENDATIONS:")
        for idx, rec in enumerate(results['recommendations'][:3], 1):
            logger.info(f"\n{idx}. [{rec['priority']}] {rec['filter']}:")
            logger.info(f"   Action: {rec['action']}")
            logger.info(f"   Current: {rec['current']}")
            logger.info(f"   Recommended: {rec['recommended']}")
            logger.info(f"   Reason: {rec['reason']}")
            logger.info(f"   Expected impact: {rec['expected_impact']}")

        # Save to file
        output_file = f"validation/reports/enhanced_validation_{self.date.replace('-', '')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"\n✓ Full report saved to {output_file}")


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(description='Enhanced Entry Decision Validator')
    parser.add_argument('--scanner', required=True, help='Scanner results JSON file')
    parser.add_argument('--entry-log', required=True, help='Entry decisions log JSON file')
    parser.add_argument('--trade-log', help='Actual trades JSON file (optional)')
    parser.add_argument('--date', required=True, help='Date to validate (YYYY-MM-DD)')
    parser.add_argument('--account-size', type=int, default=50000, help='Account size')

    args = parser.parse_args()

    # Create validator
    validator = EnhancedValidator(
        scanner_file=args.scanner,
        entry_log_file=args.entry_log,
        trade_log_file=args.trade_log,
        date=args.date,
        account_size=args.account_size
    )

    # Run analysis
    results = validator.analyze()

    # Disconnect from IBKR
    if validator.ib:
        validator.ib.disconnect()

    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION COMPLETE")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()