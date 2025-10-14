#!/usr/bin/env python3
"""
Backtest Comparator

Runs a same-day backtest with current filters and compares:
- Which trades the backtest would have taken
- How it compares to actual live trading
- Which breakouts were caught/missed
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'stockscanner'))

# Import backtest module
sys.path.insert(0, str(Path(__file__).parent.parent / 'backtest'))
try:
    from backtester import Backtester
except ImportError:
    # If backtester doesn't exist, create a placeholder
    class Backtester:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Backtester not implemented yet")

from strategy import PS60Strategy
import yaml


class BacktestComparator:
    """
    Runs same-day backtest and compares with live results

    Step 2 of EOD Analysis: Validate strategy logic against market reality
    """

    def __init__(self, date_str):
        """
        Initialize comparator

        Args:
            date_str: Date in YYYYMMDD format
        """
        self.date_str = date_str
        self.date = datetime.strptime(date_str, '%Y%m%d')

        # Load config
        config_path = Path(__file__).parent.parent / 'config' / 'trader_config.yaml'
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Load live trades if available
        self.live_trades = self._load_live_trades()

        # Load market validation if available
        self.market_validation = self._load_market_validation()

        # Backtest results
        self.backtest_trades = []
        self.comparison_results = {}

    def _load_live_trades(self):
        """Load live trading results"""
        trades_file = Path(f'logs/trades_{self.date_str}.json')
        if trades_file.exists():
            with open(trades_file, 'r') as f:
                return json.load(f)
        return []

    def _load_market_validation(self):
        """Load market validation results"""
        validation_file = Path(f'logs/market_validation_{self.date_str}.json')
        if validation_file.exists():
            with open(validation_file, 'r') as f:
                return json.load(f)
        return {}

    def run_backtest(self):
        """Run backtest for the specific day"""
        print(f"\n{'='*80}")
        print(f"SAME-DAY BACKTEST - {self.date_str}")
        print(f"{'='*80}")

        # Find scanner file
        scanner_file = self._find_scanner_file()
        if not scanner_file:
            print("\n⚠️  No scanner file found for this date")
            return

        print(f"\n📄 Using scanner: {scanner_file}")
        print(f"📊 Using config: trader_config.yaml")

        # Initialize backtester
        backtester = Backtester(
            scanner_file=str(scanner_file),
            config=self.config,
            start_date=self.date,
            end_date=self.date
        )

        # Run backtest
        print(f"\n⏳ Running backtest...")
        results = backtester.run()

        # Store results
        self.backtest_trades = results.get('trades', [])

        # Print backtest summary
        self._print_backtest_summary()

        return self.backtest_trades

    def _find_scanner_file(self):
        """Find appropriate scanner file"""
        # Try enhanced scoring first
        enhanced = Path(f'../scanner_validation/rescored_{self.date_str}.csv')
        if enhanced.exists():
            return enhanced

        # Try standard scanner
        standard = Path(f'../stockscanner/output/scanner_results_{self.date_str}.json')
        if standard.exists():
            return standard

        return None

    def _print_backtest_summary(self):
        """Print backtest results summary"""
        if not self.backtest_trades:
            print("\n📊 Backtest Results: No trades executed")
            return

        # Calculate metrics
        df = pd.DataFrame(self.backtest_trades)
        total_pnl = df['pnl'].sum()
        win_rate = (df['pnl'] > 0).mean() * 100
        total_trades = len(df)

        print(f"\n📊 Backtest Results:")
        print(f"  Total Trades: {total_trades}")
        print(f"  Total P&L: ${total_pnl:.2f}")
        print(f"  Win Rate: {win_rate:.1f}%")

        # Top trades
        if total_trades > 0:
            best = df.loc[df['pnl'].idxmax()]
            worst = df.loc[df['pnl'].idxmin()]

            print(f"\n  Best Trade: {best['symbol']} {best['side']} (${best['pnl']:.2f})")
            print(f"  Worst Trade: {worst['symbol']} {worst['side']} (${worst['pnl']:.2f})")

    def compare_with_live(self):
        """Compare backtest results with live trading"""
        print(f"\n{'='*80}")
        print(f"BACKTEST vs LIVE COMPARISON")
        print(f"{'='*80}")

        # Convert to DataFrames for easier comparison
        if self.backtest_trades:
            bt_df = pd.DataFrame(self.backtest_trades)
            bt_df['source'] = 'backtest'
        else:
            bt_df = pd.DataFrame()

        if self.live_trades:
            live_df = pd.DataFrame(self.live_trades)
            live_df['source'] = 'live'
        else:
            live_df = pd.DataFrame()

        # Overall comparison
        self._compare_overall_metrics(bt_df, live_df)

        # Symbol-by-symbol comparison
        self._compare_by_symbol(bt_df, live_df)

        # Trade timing comparison
        self._compare_trade_timing(bt_df, live_df)

        # Filter effectiveness comparison
        self._compare_filter_effectiveness(bt_df, live_df)

    def _compare_overall_metrics(self, bt_df, live_df):
        """Compare overall metrics"""
        print(f"\n📊 OVERALL METRICS COMPARISON")
        print(f"{'-'*60}")

        # Calculate metrics for both
        bt_trades = len(bt_df) if not bt_df.empty else 0
        bt_pnl = bt_df['pnl'].sum() if not bt_df.empty else 0
        bt_win_rate = (bt_df['pnl'] > 0).mean() * 100 if not bt_df.empty else 0

        live_trades = len(live_df) if not live_df.empty else 0
        live_pnl = live_df['pnl'].sum() if not live_df.empty else 0
        live_win_rate = (live_df['pnl'] > 0).mean() * 100 if not live_df.empty else 0

        print(f"\n{'Metric':<20} {'Backtest':>15} {'Live':>15} {'Difference':>15}")
        print(f"{'-'*65}")
        print(f"{'Total Trades':<20} {bt_trades:>15} {live_trades:>15} {bt_trades - live_trades:>15}")
        print(f"{'Total P&L':<20} ${bt_pnl:>14.2f} ${live_pnl:>14.2f} ${bt_pnl - live_pnl:>14.2f}")
        print(f"{'Win Rate %':<20} {bt_win_rate:>14.1f}% {live_win_rate:>14.1f}% {bt_win_rate - live_win_rate:>14.1f}%")

        if bt_trades > 0 and live_trades > 0:
            print(f"{'Avg Trade P&L':<20} ${bt_pnl/bt_trades:>14.2f} ${live_pnl/live_trades:>14.2f} ${(bt_pnl/bt_trades) - (live_pnl/live_trades):>14.2f}")

        # Analysis
        print(f"\n📋 Analysis:")
        if bt_trades > live_trades:
            print(f"  • Backtest took {bt_trades - live_trades} MORE trades")
            print(f"    → Live system may be over-filtering or had connection issues")
        elif live_trades > bt_trades:
            print(f"  • Live took {live_trades - bt_trades} MORE trades")
            print(f"    → Backtest may be missing some entry conditions")

        if abs(bt_pnl - live_pnl) > 1000:
            print(f"  • P&L difference of ${abs(bt_pnl - live_pnl):.2f}")
            if bt_pnl > live_pnl:
                print(f"    → Backtest overestimating (slippage? execution delays?)")
            else:
                print(f"    → Live outperformed (better execution? manual overrides?)")

    def _compare_by_symbol(self, bt_df, live_df):
        """Compare trades by symbol"""
        print(f"\n📊 SYMBOL-BY-SYMBOL COMPARISON")
        print(f"{'-'*60}")

        # Get all symbols traded
        all_symbols = set()
        if not bt_df.empty:
            all_symbols.update(bt_df['symbol'].unique())
        if not live_df.empty:
            all_symbols.update(live_df['symbol'].unique())

        if not all_symbols:
            print("  No symbols to compare")
            return

        comparison = []
        for symbol in sorted(all_symbols):
            bt_trades = bt_df[bt_df['symbol'] == symbol] if not bt_df.empty else pd.DataFrame()
            live_trades = live_df[live_df['symbol'] == symbol] if not live_df.empty else pd.DataFrame()

            comparison.append({
                'symbol': symbol,
                'bt_count': len(bt_trades),
                'bt_pnl': bt_trades['pnl'].sum() if len(bt_trades) > 0 else 0,
                'live_count': len(live_trades),
                'live_pnl': live_trades['pnl'].sum() if len(live_trades) > 0 else 0
            })

        # Print comparison table
        print(f"\n{'Symbol':<8} {'BT Trades':>10} {'BT P&L':>12} {'Live Trades':>12} {'Live P&L':>12}")
        print(f"{'-'*60}")

        for comp in comparison:
            print(f"{comp['symbol']:<8} {comp['bt_count']:>10} ${comp['bt_pnl']:>10.2f} "
                  f"{comp['live_count']:>12} ${comp['live_pnl']:>10.2f}")

        # Identify discrepancies
        print(f"\n⚠️  Notable Discrepancies:")
        for comp in comparison:
            if comp['bt_count'] > 0 and comp['live_count'] == 0:
                print(f"  • {comp['symbol']}: Backtest traded, Live didn't")
                print(f"    → Check live logs for filter blocks")
            elif comp['live_count'] > 0 and comp['bt_count'] == 0:
                print(f"  • {comp['symbol']}: Live traded, Backtest didn't")
                print(f"    → Check for manual overrides or logic differences")

    def _compare_trade_timing(self, bt_df, live_df):
        """Compare entry timing"""
        print(f"\n⏰ TRADE TIMING COMPARISON")
        print(f"{'-'*60}")

        # Parse entry times
        if not bt_df.empty and 'entry_time' in bt_df.columns:
            bt_df['entry_hour'] = pd.to_datetime(bt_df['entry_time']).dt.hour

        if not live_df.empty and 'entry_time' in live_df.columns:
            live_df['entry_hour'] = pd.to_datetime(live_df['entry_time']).dt.hour

        # Compare hourly distribution
        bt_hourly = bt_df.groupby('entry_hour').size() if not bt_df.empty and 'entry_hour' in bt_df else pd.Series()
        live_hourly = live_df.groupby('entry_hour').size() if not live_df.empty and 'entry_hour' in live_df else pd.Series()

        print(f"\n{'Hour':<6} {'Backtest':>10} {'Live':>10}")
        print(f"{'-'*26}")

        all_hours = set(bt_hourly.index) | set(live_hourly.index)
        for hour in sorted(all_hours):
            bt_count = bt_hourly.get(hour, 0)
            live_count = live_hourly.get(hour, 0)
            print(f"{hour:02d}:00  {bt_count:>10} {live_count:>10}")

        # Analysis
        if not bt_hourly.empty and not live_hourly.empty:
            bt_peak = bt_hourly.idxmax()
            live_peak = live_hourly.idxmax()

            if bt_peak != live_peak:
                print(f"\n  • Peak hours differ: Backtest {bt_peak}:00, Live {live_peak}:00")

    def _compare_filter_effectiveness(self, bt_df, live_df):
        """Compare which filters affected trades"""
        print(f"\n🎯 FILTER EFFECTIVENESS")
        print(f"{'-'*60}")

        # This would require parsing logs for filter blocks
        # For now, just compare trade counts as proxy

        bt_count = len(bt_df) if not bt_df.empty else 0
        live_count = len(live_df) if not live_df.empty else 0

        if bt_count > live_count * 1.5:
            print(f"\n  ⚠️  Backtest took {bt_count - live_count} more trades")
            print(f"      Possible causes:")
            print(f"      • Live filters too strict")
            print(f"      • Connection issues in live")
            print(f"      • Manual intervention in live")
        elif live_count > bt_count * 1.5:
            print(f"\n  ⚠️  Live took {live_count - bt_count} more trades")
            print(f"      Possible causes:")
            print(f"      • Backtest filters too strict")
            print(f"      • Manual overrides in live")
            print(f"      • Logic differences")
        else:
            print(f"\n  ✓ Trade counts relatively similar ({bt_count} vs {live_count})")

    def compare_with_market(self):
        """Compare backtest with market validation"""
        if not self.market_validation:
            print(f"\n⚠️  No market validation data available")
            return

        print(f"\n{'='*80}")
        print(f"BACKTEST vs MARKET REALITY")
        print(f"{'='*80}")

        # Check which validated breakouts were caught by backtest
        bt_symbols = set(t['symbol'] for t in self.backtest_trades)

        print(f"\n📊 Breakout Coverage:")
        caught_breakouts = 0
        missed_breakouts = 0

        for symbol, validation in self.market_validation.items():
            if validation.get('breakouts'):
                if symbol in bt_symbols:
                    caught_breakouts += len(validation['breakouts'])
                    print(f"  ✓ {symbol}: Caught {len(validation['breakouts'])} breakout(s)")
                else:
                    missed_breakouts += len(validation['breakouts'])
                    print(f"  ❌ {symbol}: Missed {len(validation['breakouts'])} breakout(s)")

        if caught_breakouts + missed_breakouts > 0:
            catch_rate = (caught_breakouts / (caught_breakouts + missed_breakouts)) * 100
            print(f"\n  Breakout Catch Rate: {catch_rate:.1f}%")
            print(f"  Caught: {caught_breakouts}")
            print(f"  Missed: {missed_breakouts}")

    def save_comparison(self):
        """Save comparison results"""
        output = {
            'date': self.date_str,
            'backtest_trades': self.backtest_trades,
            'live_trades': self.live_trades,
            'comparison': self.comparison_results
        }

        output_file = Path(f'logs/backtest_comparison_{self.date_str}.json')
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n📄 Comparison saved to: {output_file}")
        return output_file


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python backtest_comparator.py YYYYMMDD")
        print("Example: python backtest_comparator.py 20251007")
        sys.exit(1)

    date_str = sys.argv[1]

    comparator = BacktestComparator(date_str)

    # Run backtest
    comparator.run_backtest()

    # Compare with live
    comparator.compare_with_live()

    # Compare with market
    comparator.compare_with_market()

    # Save results
    comparator.save_comparison()