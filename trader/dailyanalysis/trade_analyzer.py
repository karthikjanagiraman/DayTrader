#!/usr/bin/env python3
"""
Trade Performance Analyzer

Deep analysis of individual trade characteristics:
- Win/loss pattern analysis
- Hold time distribution
- Entry type vs outcome
- Symbol performance
- Setup quality correlation
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import pytz


class TradePerformanceAnalyzer:
    """
    Analyzes trade-level performance patterns

    Goals:
    - Identify which setups work best
    - Find optimal hold times
    - Detect symbol-specific patterns
    - Compare entry methods
    """

    def __init__(self, trades_file=None, date_str=None, log_dir='./logs'):
        """
        Initialize analyzer

        Args:
            trades_file: Path to trades JSON (or None to auto-detect from date_str)
            date_str: Date in YYYYMMDD format
            log_dir: Directory containing trade files
        """
        self.log_dir = Path(log_dir)

        if trades_file:
            self.trades_file = Path(trades_file)
        elif date_str:
            self.trades_file = self.log_dir / f"trades_{date_str}.json"
        else:
            raise ValueError("Must provide either trades_file or date_str")

        self.trades = self._load_trades()
        self.df = pd.DataFrame(self.trades) if self.trades else pd.DataFrame()

    def _load_trades(self):
        """Load trades from JSON"""
        if not self.trades_file.exists():
            print(f"⚠️  Trades file not found: {self.trades_file}")
            return []

        with open(self.trades_file, 'r') as f:
            return json.load(f)

    def analyze(self):
        """Run complete trade analysis"""
        print(f"\n{'='*80}")
        print(f"TRADE PERFORMANCE ANALYSIS")
        print(f"{'='*80}")

        if self.df.empty:
            print("\n⚠️  No trades to analyze")
            return

        self._analyze_by_symbol()
        self._analyze_by_direction()
        self._analyze_hold_time()
        self._analyze_exit_reasons()
        self._analyze_partials_impact()

    def _analyze_by_symbol(self):
        """Analyze performance by symbol"""
        print(f"\n📊 PERFORMANCE BY SYMBOL")
        print(f"{'-'*80}")

        symbol_stats = self.df.groupby('symbol').agg({
            'pnl': ['count', 'sum', 'mean'],
            'shares': 'mean',
        })

        # Add win rate
        def win_rate(group):
            return (group['pnl'] > 0).sum() / len(group) * 100

        symbol_stats['win_rate'] = self.df.groupby('symbol').apply(win_rate)

        # Sort by total P&L
        symbol_stats = symbol_stats.sort_values(('pnl', 'sum'), ascending=False)

        print(f"\n{'Symbol':<8} {'Trades':>7} {'Total P&L':>12} {'Avg P&L':>10} {'Win%':>6} {'Avg Shares':>12}")
        print(f"{'-'*70}")

        for symbol in symbol_stats.index:
            count = int(symbol_stats.loc[symbol, ('pnl', 'count')])
            total_pnl = symbol_stats.loc[symbol, ('pnl', 'sum')]
            avg_pnl = symbol_stats.loc[symbol, ('pnl', 'mean')]
            win_pct = symbol_stats.loc[symbol, 'win_rate']
            avg_shares = int(symbol_stats.loc[symbol, ('shares', 'mean')])

            print(f"{symbol:<8} {count:>7} ${total_pnl:>10.2f} ${avg_pnl:>8.2f} {win_pct:>5.1f}% {avg_shares:>12,}")

        # Best and worst symbols
        best_symbol = symbol_stats[('pnl', 'sum')].idxmax()
        worst_symbol = symbol_stats[('pnl', 'sum')].idxmin()

        print(f"\n💰 Best Symbol: {best_symbol} (${symbol_stats.loc[best_symbol, ('pnl', 'sum')]:.2f})")
        print(f"❌ Worst Symbol: {worst_symbol} (${symbol_stats.loc[worst_symbol, ('pnl', 'sum')]:.2f})")

    def _analyze_by_direction(self):
        """Analyze LONG vs SHORT performance"""
        print(f"\n📈 PERFORMANCE BY DIRECTION")
        print(f"{'-'*80}")

        direction_stats = self.df.groupby('side').agg({
            'pnl': ['count', 'sum', 'mean'],
        })

        # Add win rate
        def win_rate(group):
            return (group['pnl'] > 0).sum() / len(group) * 100

        direction_stats['win_rate'] = self.df.groupby('side').apply(win_rate)

        print(f"\n{'Direction':<10} {'Trades':>7} {'Total P&L':>12} {'Avg P&L':>10} {'Win%':>6}")
        print(f"{'-'*50}")

        for direction in direction_stats.index:
            count = int(direction_stats.loc[direction, ('pnl', 'count')])
            total_pnl = direction_stats.loc[direction, ('pnl', 'sum')]
            avg_pnl = direction_stats.loc[direction, ('pnl', 'mean')]
            win_pct = direction_stats.loc[direction, 'win_rate']

            print(f"{direction:<10} {count:>7} ${total_pnl:>10.2f} ${avg_pnl:>8.2f} {win_pct:>5.1f}%")

        # Statistical comparison
        if 'LONG' in direction_stats.index and 'SHORT' in direction_stats.index:
            long_avg = direction_stats.loc['LONG', ('pnl', 'mean')]
            short_avg = direction_stats.loc['SHORT', ('pnl', 'mean')]

            if long_avg > short_avg:
                diff_pct = ((long_avg - short_avg) / abs(short_avg)) * 100
                print(f"\n→ LONGS outperform SHORTS by {diff_pct:.1f}%")
            else:
                diff_pct = ((short_avg - long_avg) / abs(long_avg)) * 100
                print(f"\n→ SHORTS outperform LONGS by {diff_pct:.1f}%")

    def _analyze_hold_time(self):
        """Analyze hold time patterns"""
        print(f"\n⏱️  HOLD TIME ANALYSIS")
        print(f"{'-'*80}")

        # Calculate hold time in minutes
        def calc_hold_time(row):
            entry = datetime.fromisoformat(row['entry_time'].replace('Z', '+00:00'))
            exit_time = datetime.fromisoformat(row['exit_time'].replace('Z', '+00:00'))
            return (exit_time - entry).total_seconds() / 60

        self.df['hold_time_min'] = self.df.apply(calc_hold_time, axis=1)

        # Bucket into time ranges
        bins = [0, 5, 10, 30, 60, 120, 240, 480]
        labels = ['0-5min', '5-10min', '10-30min', '30-60min', '1-2hr', '2-4hr', '4-8hr']

        self.df['hold_bucket'] = pd.cut(self.df['hold_time_min'], bins=bins, labels=labels, include_lowest=True)

        # Analyze by bucket
        bucket_stats = self.df.groupby('hold_bucket', observed=True).agg({
            'pnl': ['count', 'sum', 'mean'],
        })

        # Add win rate
        def win_rate(group):
            return (group['pnl'] > 0).sum() / len(group) * 100 if len(group) > 0 else 0

        bucket_stats['win_rate'] = self.df.groupby('hold_bucket', observed=True).apply(win_rate)

        print(f"\n{'Hold Time':<12} {'Trades':>7} {'Total P&L':>12} {'Avg P&L':>10} {'Win%':>6}")
        print(f"{'-'*50}")

        for bucket in bucket_stats.index:
            count = int(bucket_stats.loc[bucket, ('pnl', 'count')])
            total_pnl = bucket_stats.loc[bucket, ('pnl', 'sum')]
            avg_pnl = bucket_stats.loc[bucket, ('pnl', 'mean')]
            win_pct = bucket_stats.loc[bucket, 'win_rate']

            print(f"{bucket:<12} {count:>7} ${total_pnl:>10.2f} ${avg_pnl:>8.2f} {win_pct:>5.1f}%")

        # Best performing hold time
        best_bucket = bucket_stats[('pnl', 'mean')].idxmax()
        print(f"\n💰 Most Profitable Hold Time: {best_bucket} (${bucket_stats.loc[best_bucket, ('pnl', 'mean')]:.2f} avg)")

        # Quick exits analysis (5-min rule)
        quick_exits = self.df[self.df['hold_time_min'] <= 7]
        if len(quick_exits) > 0:
            quick_avg = quick_exits['pnl'].mean()
            quick_total = quick_exits['pnl'].sum()
            print(f"\n⚡ Quick Exits (≤7 min): {len(quick_exits)} trades, ${quick_total:.2f} total, ${quick_avg:.2f} avg")
            print(f"   → 5-minute rule {'working well' if quick_avg > -50 else 'needs review'}")

    def _analyze_exit_reasons(self):
        """Analyze performance by exit reason"""
        print(f"\n🚪 EXIT REASON ANALYSIS")
        print(f"{'-'*80}")

        exit_stats = self.df.groupby('reason').agg({
            'pnl': ['count', 'sum', 'mean'],
        })

        # Add win rate
        def win_rate(group):
            return (group['pnl'] > 0).sum() / len(group) * 100

        exit_stats['win_rate'] = self.df.groupby('reason').apply(win_rate)

        # Sort by count
        exit_stats = exit_stats.sort_values(('pnl', 'count'), ascending=False)

        print(f"\n{'Exit Reason':<20} {'Trades':>7} {'Total P&L':>12} {'Avg P&L':>10} {'Win%':>6}")
        print(f"{'-'*60}")

        for reason in exit_stats.index:
            count = int(exit_stats.loc[reason, ('pnl', 'count')])
            total_pnl = exit_stats.loc[reason, ('pnl', 'sum')]
            avg_pnl = exit_stats.loc[reason, ('pnl', 'mean')]
            win_pct = exit_stats.loc[reason, 'win_rate']

            print(f"{reason:<20} {count:>7} ${total_pnl:>10.2f} ${avg_pnl:>8.2f} {win_pct:>5.1f}%")

        # Analyze specific exit reasons
        print(f"\n📋 Exit Reason Insights:")

        if '5MIN_RULE' in exit_stats.index:
            count_5min = int(exit_stats.loc['5MIN_RULE', ('pnl', 'count')])
            avg_5min = exit_stats.loc['5MIN_RULE', ('pnl', 'mean')]
            print(f"\n  5-Minute Rule: {count_5min} trades, ${avg_5min:.2f} avg")
            if avg_5min < -100:
                print(f"    ⚠️  Losing money on quick exits - consider relaxing criteria")
            else:
                print(f"    ✓ Preventing larger losses - rule working correctly")

        if 'EOD' in exit_stats.index:
            count_eod = int(exit_stats.loc['EOD', ('pnl', 'count')])
            avg_eod = exit_stats.loc['EOD', ('pnl', 'mean')]
            total_eod = exit_stats.loc['EOD', ('pnl', 'sum')]
            print(f"\n  End-of-Day Closes: {count_eod} trades, ${total_eod:.2f} total, ${avg_eod:.2f} avg")
            if avg_eod > 100:
                print(f"    💰 Runners performing well - let winners run strategy working")
            else:
                print(f"    ⚠️  Consider tighter trailing stops or earlier profit-taking")

        if 'STOP' in exit_stats.index:
            count_stop = int(exit_stats.loc['STOP', ('pnl', 'count')])
            avg_stop = exit_stats.loc['STOP', ('pnl', 'mean')]
            print(f"\n  Stop Losses: {count_stop} trades, ${avg_stop:.2f} avg")
            if avg_stop < -200:
                print(f"    ⚠️  Large stop losses - consider tighter stops or smaller position sizes")
            else:
                print(f"    ✓ Stop losses within acceptable range")

    def _analyze_partials_impact(self):
        """Analyze impact of partial profit-taking"""
        print(f"\n✂️  PARTIAL PROFIT ANALYSIS")
        print(f"{'-'*80}")

        # Split by whether partials were taken
        with_partials = self.df[self.df['partials'] > 0]
        without_partials = self.df[self.df['partials'] == 0]

        print(f"\n{'Strategy':<20} {'Trades':>7} {'Total P&L':>12} {'Avg P&L':>10} {'Win%':>6}")
        print(f"{'-'*60}")

        if len(with_partials) > 0:
            count = len(with_partials)
            total_pnl = with_partials['pnl'].sum()
            avg_pnl = with_partials['pnl'].mean()
            win_rate = (with_partials['pnl'] > 0).sum() / len(with_partials) * 100

            print(f"{'With Partials':<20} {count:>7} ${total_pnl:>10.2f} ${avg_pnl:>8.2f} {win_rate:>5.1f}%")

        if len(without_partials) > 0:
            count = len(without_partials)
            total_pnl = without_partials['pnl'].sum()
            avg_pnl = without_partials['pnl'].mean()
            win_rate = (without_partials['pnl'] > 0).sum() / len(without_partials) * 100

            print(f"{'Without Partials':<20} {count:>7} ${total_pnl:>10.2f} ${avg_pnl:>8.2f} {win_rate:>5.1f}%")

        # Statistical comparison
        if len(with_partials) > 0 and len(without_partials) > 0:
            avg_with = with_partials['pnl'].mean()
            avg_without = without_partials['pnl'].mean()

            print(f"\n📊 Comparison:")
            if avg_with > avg_without:
                diff = avg_with - avg_without
                print(f"  Taking partials improves avg P&L by ${diff:.2f}")
                print(f"  → Partial profit-taking strategy is WORKING")
            else:
                diff = avg_without - avg_with
                print(f"  Trades without partials outperform by ${diff:.2f}")
                print(f"  ⚠️  May be exiting winners too early - consider letting more run")

        # Analyze number of partials
        if len(with_partials) > 0:
            print(f"\n  Partial Distribution:")
            partial_counts = with_partials['partials'].value_counts().sort_index()
            for num_partials, count in partial_counts.items():
                avg_pnl = with_partials[with_partials['partials'] == num_partials]['pnl'].mean()
                print(f"    {int(num_partials)} partial(s): {count} trades, ${avg_pnl:.2f} avg")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python trade_analyzer.py YYYYMMDD")
        print("Example: python trade_analyzer.py 20251007")
        sys.exit(1)

    date_str = sys.argv[1]

    analyzer = TradePerformanceAnalyzer(date_str=date_str)
    analyzer.analyze()
