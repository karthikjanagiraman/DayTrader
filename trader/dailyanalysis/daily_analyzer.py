#!/usr/bin/env python3
"""
Daily Session Analyzer

Analyzes a single trading session's performance, generating:
- P&L breakdown
- Win rate and statistics
- Entry path effectiveness
- Filter blocking analysis
- Time-based performance
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import pytz


class DailySessionAnalyzer:
    """
    Analyzes a complete trading session

    Input Sources:
    - trades_YYYYMMDD.json: Closed trades with P&L
    - trader_YYYYMMDD.log: Complete session log
    - trader_state.json: Final session state

    Output:
    - Console report
    - HTML report (optional)
    - JSON metrics (optional)
    """

    def __init__(self, date_str, log_dir='./logs'):
        """
        Initialize analyzer for specific date

        Args:
            date_str: Date in YYYYMMDD format (e.g., "20251007")
            log_dir: Directory containing log files
        """
        self.date_str = date_str
        self.log_dir = Path(log_dir)

        # Load data sources
        self.trades = self._load_trades()
        self.log_lines = self._load_log()

        # Parsed analytics
        self.metrics = {}
        self.filter_blocks = defaultdict(int)
        self.entry_paths = defaultdict(int)

    def _load_trades(self):
        """Load trades JSON file"""
        trades_file = self.log_dir / f"trades_{self.date_str}.json"

        if not trades_file.exists():
            print(f"⚠️  No trades file found: {trades_file}")
            return []

        with open(trades_file, 'r') as f:
            return json.load(f)

    def _load_log(self):
        """Load log file"""
        log_file = self.log_dir / f"trader_{self.date_str}.log"

        if not log_file.exists():
            print(f"⚠️  No log file found: {log_file}")
            return []

        with open(log_file, 'r') as f:
            return f.readlines()

    def analyze(self):
        """Run complete analysis"""
        print(f"\n{'='*80}")
        print(f"DAILY SESSION ANALYSIS - {self.date_str}")
        print(f"{'='*80}")

        self._analyze_pnl()
        self._analyze_entry_paths()
        self._analyze_filters()
        self._analyze_timing()
        self._analyze_risk_management()

        return self.metrics

    def _analyze_pnl(self):
        """Analyze P&L performance"""
        print(f"\n📊 P&L ANALYSIS")
        print(f"{'-'*80}")

        if not self.trades:
            print("No trades executed")
            self.metrics['total_trades'] = 0
            self.metrics['daily_pnl'] = 0
            return

        # Calculate metrics
        df = pd.DataFrame(self.trades)

        total_pnl = df['pnl'].sum()
        total_trades = len(df)
        winners = len(df[df['pnl'] > 0])
        losers = len(df[df['pnl'] < 0])
        scratches = len(df[df['pnl'] == 0])

        win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

        avg_winner = df[df['pnl'] > 0]['pnl'].mean() if winners > 0 else 0
        avg_loser = df[df['pnl'] < 0]['pnl'].mean() if losers > 0 else 0
        avg_trade = df['pnl'].mean()

        # Calculate profit factor
        gross_profit = df[df['pnl'] > 0]['pnl'].sum() if winners > 0 else 0
        gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum()) if losers > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Store metrics
        self.metrics.update({
            'total_trades': total_trades,
            'daily_pnl': total_pnl,
            'winners': winners,
            'losers': losers,
            'scratches': scratches,
            'win_rate': win_rate,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'avg_trade': avg_trade,
            'profit_factor': profit_factor,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
        })

        # Print results
        print(f"Total P&L: ${total_pnl:,.2f}")
        print(f"Total Trades: {total_trades}")
        print(f"  Winners: {winners} ({win_rate:.1f}%)")
        print(f"  Losers: {losers} ({(losers/total_trades*100):.1f}%)")
        if scratches > 0:
            print(f"  Scratches: {scratches}")

        print(f"\nAverage Trade: ${avg_trade:.2f}")
        print(f"Average Winner: ${avg_winner:.2f}")
        print(f"Average Loser: ${avg_loser:.2f}")

        if profit_factor != float('inf'):
            print(f"\nProfit Factor: {profit_factor:.2f}")

        print(f"\nGross Profit: ${gross_profit:,.2f}")
        print(f"Gross Loss: ${gross_loss:,.2f}")

        # Best and worst trades
        best_trade = df.loc[df['pnl'].idxmax()]
        worst_trade = df.loc[df['pnl'].idxmin()]

        print(f"\n💰 Best Trade:")
        print(f"  {best_trade['symbol']} {best_trade['side']}: ${best_trade['pnl']:.2f}")
        print(f"  Entry: ${best_trade['entry_price']:.2f} → Exit: ${best_trade['exit_price']:.2f}")
        print(f"  Reason: {best_trade['reason']}")

        print(f"\n❌ Worst Trade:")
        print(f"  {worst_trade['symbol']} {worst_trade['side']}: ${worst_trade['pnl']:.2f}")
        print(f"  Entry: ${worst_trade['entry_price']:.2f} → Exit: ${worst_trade['exit_price']:.2f}")
        print(f"  Reason: {worst_trade['reason']}")

    def _analyze_entry_paths(self):
        """Analyze which entry confirmation methods were used"""
        print(f"\n📈 ENTRY PATH ANALYSIS")
        print(f"{'-'*80}")

        # Parse log for ACTUAL trade entries (not just signals)
        # Look for the entry confirmation lines that come with executed trades
        trade_entries = []
        for i, line in enumerate(self.log_lines):
            # Look for actual trade execution lines (with emoji indicators)
            if ('🟢 LONG' in line or '🔴 SHORT' in line) and '@' in line:
                # Now find the Entry Path line that follows within next 5 lines
                for j in range(i+1, min(i+6, len(self.log_lines))):
                    if 'Entry Path:' in self.log_lines[j]:
                        # Extract entry type (MOMENTUM_BREAKOUT, PULLBACK/RETEST, SUSTAINED_BREAK)
                        parts = self.log_lines[j].split('Entry Path:')[1].strip()
                        entry_type = parts.split('(')[0].strip()
                        self.entry_paths[entry_type] += 1
                        trade_entries.append(entry_type)
                        break

        if not self.entry_paths:
            print("No entry paths detected")
            return

        # Use actual trade count instead of entry path count
        total_entries = len(trade_entries)

        print(f"Actual Trades Executed: {total_entries}\n")

        for path, count in sorted(self.entry_paths.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_entries * 100) if total_entries > 0 else 0
            print(f"  {path}: {count} ({pct:.1f}%)")

            # Provide context
            if 'MOMENTUM' in path:
                print(f"    → Immediate entry (volume ≥1.3x, candle ≥0.8%)")
            elif 'PULLBACK' in path or 'RETEST' in path:
                print(f"    → Patient entry (waited for pullback/retest)")
            elif 'SUSTAINED' in path:
                print(f"    → Grinding entry (held 2+ minutes above pivot)")

        self.metrics['entry_paths'] = dict(self.entry_paths)

    def _analyze_filters(self):
        """Analyze why trades were blocked"""
        print(f"\n🎯 FILTER EFFECTIVENESS ANALYSIS")
        print(f"{'-'*80}")

        # Parse log for filter blocks
        for line in self.log_lines:
            if 'blocked' in line.lower() and '❌' in line:
                # Extract reason
                if ' - ' in line:
                    reason = line.split(' - ')[1].strip()
                    self.filter_blocks[reason] += 1

        if not self.filter_blocks:
            print("⚠️  No filter blocks detected (unusual - verify filters are working)")
            return

        total_blocks = sum(self.filter_blocks.values())

        print(f"Total Blocks: {total_blocks}\n")
        print(f"Top Blocking Filters:\n")

        for filter_reason, count in sorted(self.filter_blocks.items(), key=lambda x: x[1], reverse=True)[:10]:
            pct = (count / total_blocks * 100) if total_blocks > 0 else 0
            print(f"  {filter_reason}: {count} ({pct:.1f}%)")

            # Provide actionable insights
            if 'Max attempts' in filter_reason:
                print(f"    → Good - prevents whipsaw losses")
            elif 'choppy' in filter_reason.lower():
                print(f"    → Saved ~${count * 100:.0f} (estimated)")
            elif 'room' in filter_reason.lower() or 'Room' in filter_reason:
                print(f"    → Good risk management - insufficient profit potential")
            elif 'Position too large' in filter_reason:
                print(f"    → Check position sizing - may need adaptive sizing")
            elif 'Gap' in filter_reason:
                print(f"    → Protected capital from gapped-away setups")
            elif 'Waiting' in filter_reason:
                print(f"    → Confirmation logic working - patience required")

        self.metrics['filter_blocks'] = dict(self.filter_blocks)

    def _analyze_timing(self):
        """Analyze timing-based performance"""
        print(f"\n⏰ TIMING ANALYSIS")
        print(f"{'-'*80}")

        if not self.trades:
            print("No trades to analyze")
            return

        df = pd.DataFrame(self.trades)

        # Parse entry times and extract hour
        df['entry_hour'] = df['entry_time'].apply(lambda x:
            datetime.fromisoformat(x.replace('Z', '+00:00')).astimezone(pytz.timezone('US/Eastern')).hour
        )

        # Group by hour
        hourly_pnl = df.groupby('entry_hour')['pnl'].agg(['sum', 'count', 'mean'])

        print(f"Performance by Entry Hour (ET):\n")

        for hour in sorted(hourly_pnl.index):
            count = int(hourly_pnl.loc[hour, 'count'])
            total_pnl = hourly_pnl.loc[hour, 'sum']
            avg_pnl = hourly_pnl.loc[hour, 'mean']

            # Convert 24-hour to 12-hour format
            hour_12 = hour if hour <= 12 else hour - 12
            am_pm = 'AM' if hour < 12 else 'PM'

            print(f"  {hour_12:2d}:00 {am_pm}: {count:2d} trades, ${total_pnl:+7.2f} total, ${avg_pnl:+6.2f} avg")

        # Best and worst hours
        best_hour = hourly_pnl['sum'].idxmax()
        worst_hour = hourly_pnl['sum'].idxmin()

        best_hour_12 = best_hour if best_hour <= 12 else best_hour - 12
        worst_hour_12 = worst_hour if worst_hour <= 12 else worst_hour - 12
        best_am_pm = 'AM' if best_hour < 12 else 'PM'
        worst_am_pm = 'AM' if worst_hour < 12 else 'PM'

        print(f"\n💰 Best Hour: {best_hour_12}:00 {best_am_pm} (${hourly_pnl.loc[best_hour, 'sum']:.2f})")
        print(f"❌ Worst Hour: {worst_hour_12}:00 {worst_am_pm} (${hourly_pnl.loc[worst_hour, 'sum']:.2f})")

        self.metrics['hourly_performance'] = hourly_pnl.to_dict()

    def _analyze_risk_management(self):
        """Analyze risk management effectiveness"""
        print(f"\n🛡️  RISK MANAGEMENT ANALYSIS")
        print(f"{'-'*80}")

        if not self.trades:
            print("No trades to analyze")
            return

        df = pd.DataFrame(self.trades)

        # Exit reason breakdown
        print(f"Exit Reason Breakdown:\n")

        exit_reasons = df.groupby('reason')['pnl'].agg(['count', 'sum', 'mean'])

        for reason in exit_reasons.index:
            count = int(exit_reasons.loc[reason, 'count'])
            total_pnl = exit_reasons.loc[reason, 'sum']
            avg_pnl = exit_reasons.loc[reason, 'mean']

            print(f"  {reason:15s}: {count:2d} trades, ${total_pnl:+8.2f} total, ${avg_pnl:+6.2f} avg")

        # Partials analysis
        print(f"\nPartials Effectiveness:\n")

        partials_df = df[df['partials'] > 0]
        no_partials_df = df[df['partials'] == 0]

        if len(partials_df) > 0:
            avg_with_partials = partials_df['pnl'].mean()
            print(f"  Trades with partials: {len(partials_df)} (avg: ${avg_with_partials:.2f})")

        if len(no_partials_df) > 0:
            avg_no_partials = no_partials_df['pnl'].mean()
            print(f"  Trades without partials: {len(no_partials_df)} (avg: ${avg_no_partials:.2f})")

        # Largest loss (risk management test)
        max_loss = df['pnl'].min()
        max_loss_trade = df.loc[df['pnl'].idxmin()]

        print(f"\n❌ Largest Single Loss: ${max_loss:.2f}")
        print(f"  {max_loss_trade['symbol']} {max_loss_trade['side']} - {max_loss_trade['reason']}")

        # Risk of ruin check (should never exceed max daily loss)
        max_daily_loss_pct = 3.0  # 3% from config
        account_size = 100000  # From config
        max_daily_loss_dollars = account_size * (max_daily_loss_pct / 100)

        if max_loss < -max_daily_loss_dollars:
            print(f"\n⚠️  WARNING: Single loss (${abs(max_loss):.2f}) exceeded max daily loss limit (${max_daily_loss_dollars:.2f})")
            print(f"  → Risk management failed - review position sizing")
        else:
            print(f"\n✓ Largest loss within risk limits (max: ${max_daily_loss_dollars:.2f})")

        self.metrics['exit_reasons'] = exit_reasons.to_dict()

    def save_report(self, output_file=None):
        """Save analysis to JSON file"""
        if output_file is None:
            output_file = self.log_dir / f"analysis_{self.date_str}.json"

        with open(output_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, default=str)

        print(f"\n📄 Analysis saved to: {output_file}")
        return output_file


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python daily_analyzer.py YYYYMMDD")
        print("Example: python daily_analyzer.py 20251007")
        sys.exit(1)

    date_str = sys.argv[1]

    analyzer = DailySessionAnalyzer(date_str)
    analyzer.analyze()
    analyzer.save_report()
