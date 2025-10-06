#!/usr/bin/env python3
"""
Monthly Backtesting Script
Runs scanner + backtest for each trading day in a given month

✅ FIXED - Now uses production scanner files (Oct 3, 2025)

The embedded HistoricalScanner class has been REMOVED because it produced
catastrophically wrong backtest results.

**What Changed**:
- REMOVED: Embedded scanner (produced -$56k P&L) ❌
- NOW USES: Production scanner files from monthly_results_production/ ✅
- Result: Accurate backtest results (+$8.9k P&L for Sept 2025)

**This script now**:
1. Loads pre-generated production scanner files
2. Runs backtest with correct pivot data
3. Produces accurate results matching production scanner quality

See SCANNER_WARNING.md and CLAUDE.md for details on why the embedded scanner was removed.
"""

from ib_insync import *
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import pandas as pd
import time
import argparse

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent / 'stockscanner'))

# Create logs directory
LOGS_DIR = Path(__file__).parent / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# ============================================================================
# ⚠️  EMBEDDED SCANNER REMOVED - USE PRODUCTION SCANNER INSTEAD ⚠️
# ============================================================================
#
# The HistoricalScanner class (220 lines) has been REMOVED because it produced
# CATASTROPHICALLY WRONG backtest results.
#
# **What was here**: Embedded scanner with simplified scoring logic
# **Why removed**:
#   - Embedded scanner: -$56,362 P&L, 26.8% win rate ❌ WRONG
#   - Production scanner: +$8,895 P&L, 39.9% win rate ✅ CORRECT
#   - **$65,257 difference** - completely false results!
#
# **TODO - How to fix this script**:
#
# Option 1: Use pre-generated scanner files (RECOMMENDED):
#    scanner_file = f"monthly_results_production/scanner_{date_str}.json"
#    with open(scanner_file) as f:
#        scanner_results = json.load(f)
#
# Option 2: Import and use production scanner:
#    from scanner import Scanner
#    scanner = Scanner()
#    results = scanner.scan(date=historical_date)  # Need to add date param
#
# See SCANNER_WARNING.md and CLAUDE.md for full details.
#
# ============================================================================


def run_monthly_backtest(year, month, account_size=100000, start_day=None, end_day=None, run_name=None):
    """Run scanner + backtest for each trading day in the month or date range

    Args:
        year: Year to backtest
        month: Month to backtest
        account_size: Account size for position sizing
        start_day: Optional start day (1-31) to limit range
        end_day: Optional end day (1-31) to limit range
        run_name: Optional run name for logging (e.g., 'longs_only', 'shorts_disabled')
    """

    # Generate run name and timestamp for logging
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if run_name:
        log_name = f"{run_name}_{year}{month:02d}_{timestamp}"
    else:
        log_name = f"backtest_{year}{month:02d}_{timestamp}"

    log_file = LOGS_DIR / f"{log_name}.log"

    # Tee output to both console and log file
    class TeeOutput:
        def __init__(self, *files):
            self.files = files
        def write(self, text):
            for f in self.files:
                f.write(text)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()

    log_fh = open(log_file, 'w')
    original_stdout = sys.stdout
    sys.stdout = TeeOutput(sys.stdout, log_fh)

    try:
        print(f"\n{'='*80}")
        print(f"MONTHLY BACKTEST: {year}-{month:02d}")
        if start_day or end_day:
            print(f"Date Range: Day {start_day or 1} to Day {end_day or 'end of month'}")
        if run_name:
            print(f"Run Name: {run_name}")
        print(f"Log File: {log_file}")
        print(f"Timestamp: {timestamp}")
        print(f"{'='*80}\n")

        # Create output directory
        output_dir = Path(__file__).parent / 'monthly_results'
        output_dir.mkdir(exist_ok=True)

        # Import backtester
        sys.path.append(str(Path(__file__).parent))
        from backtester import PS60Backtester

        # Use production scanner files (NOT embedded scanner - see warning above)
        production_dir = Path(__file__).parent / 'monthly_results_production'
        if not production_dir.exists():
            raise FileNotFoundError(
                f"Production scanner directory not found: {production_dir}\n"
                f"Cannot run backtest without production scanner files."
            )

        # Get all days in the month
        if start_day:
            start_date = datetime(year, month, start_day)
        else:
            start_date = datetime(year, month, 1)

        if end_day:
            end_date = datetime(year, month, end_day)
        elif month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        current_date = start_date
        all_results = []
        daily_results = []

        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:  # Saturday=5, Sunday=6
                current_date += timedelta(days=1)
                continue

            date_str = current_date.strftime('%Y%m%d')
            print(f"\n{'='*80}")
            print(f"Processing {current_date.strftime('%Y-%m-%d')} ({current_date.strftime('%A')})")
            print(f"{'='*80}")

            try:
                # Step 1: Load production scanner results
                print(f"\n[1/2] Loading production scanner file...")
                scanner_file = production_dir / f'scanner_{date_str}.json'

                if not scanner_file.exists():
                    print(f"✗ No production scanner file for {date_str}, skipping...")
                    current_date += timedelta(days=1)
                    continue

                with open(scanner_file) as f:
                    scanner_results = json.load(f)

                if not scanner_results or len(scanner_results) == 0:
                    print(f"✗ Empty scanner results for {date_str}, skipping...")
                    current_date += timedelta(days=1)
                    continue

                print(f"✓ Loaded {len(scanner_results)} setups from production scanner")
                print(f"✓ File: {scanner_file}")

                # Step 2: Run backtest using scanner results
                print(f"\n[2/2] Running backtest...")
                backtester = PS60Backtester(
                    scanner_results_path=str(scanner_file),
                    test_date=current_date,
                    account_size=account_size
                )

                # Run backtest (it modifies backtester.trades internally)
                backtester.run()
                trades = backtester.trades

                if trades:
                    # Calculate daily P&L
                    total_pnl = sum(t['pnl'] for t in trades)
                    winners = [t for t in trades if t['pnl'] > 0]
                    losers = [t for t in trades if t['pnl'] < 0]
                    win_rate = (len(winners) / len(trades) * 100) if trades else 0

                    daily_summary = {
                        'date': current_date.strftime('%Y-%m-%d'),
                        'trades': len(trades),
                        'winners': len(winners),
                        'losers': len(losers),
                        'win_rate': round(win_rate, 1),
                        'total_pnl': round(total_pnl, 2),
                        'avg_pnl': round(total_pnl / len(trades), 2) if trades else 0
                    }

                    daily_results.append(daily_summary)
                    all_results.extend(trades)

                    print(f"\n✓ Backtest complete: {len(trades)} trades, ${total_pnl:,.2f} P&L")
                else:
                    print(f"✓ Backtest complete: No trades")

            except Exception as e:
                print(f"✗ Error processing {date_str}: {e}")
                import traceback
                traceback.print_exc()

            current_date += timedelta(days=1)
            time.sleep(1)  # Small delay between days

        # Generate monthly summary
        if daily_results:
            print(f"\n{'='*80}")
        print(f"MONTHLY SUMMARY: {year}-{month:02d}")
        print(f"{'='*80}\n")

        df = pd.DataFrame(daily_results)
        print(df.to_string(index=False))

        total_trades = df['trades'].sum()
        total_pnl = df['total_pnl'].sum()
        avg_daily_pnl = df['total_pnl'].mean()
        winning_days = len(df[df['total_pnl'] > 0])
        losing_days = len(df[df['total_pnl'] < 0])
        overall_win_rate = (df['winners'].sum() / df['trades'].sum() * 100) if total_trades > 0 else 0

        print(f"\n{'='*80}")
        print(f"OVERALL STATISTICS")
        print(f"{'='*80}")
        print(f"Trading Days: {len(daily_results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Total P&L: ${total_pnl:,.2f}")
        print(f"Avg Daily P&L: ${avg_daily_pnl:,.2f}")
        print(f"Win Rate: {overall_win_rate:.1f}%")
        print(f"Winning Days: {winning_days}/{len(daily_results)} ({winning_days/len(daily_results)*100:.1f}%)")
        print(f"Losing Days: {losing_days}/{len(daily_results)}")
        print(f"Monthly Return: {(total_pnl/account_size)*100:.2f}%")

        # Save results
        summary_file = output_dir / f'monthly_summary_{year}{month:02d}.json'
        with open(summary_file, 'w') as f:
            json.dump({
                'month': f'{year}-{month:02d}',
                'daily_results': daily_results,
                'summary': {
                    'trading_days': len(daily_results),
                    'total_trades': int(total_trades),
                    'total_pnl': round(total_pnl, 2),
                    'avg_daily_pnl': round(avg_daily_pnl, 2),
                    'win_rate': round(overall_win_rate, 1),
                    'winning_days': winning_days,
                    'losing_days': losing_days,
                    'monthly_return_pct': round((total_pnl/account_size)*100, 2)
                }
            }, f, indent=2)
        print(f"\n✓ Results saved to {summary_file}")

        # Save all trades
        trades_file = output_dir / f'all_trades_{year}{month:02d}.json'
        with open(trades_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"✓ All trades saved to {trades_file}")

    finally:
        # Restore stdout and close log file
        sys.stdout = original_stdout
        log_fh.close()
        print(f"\n✓ Full backtest log saved to: {log_file}")

    if not daily_results:
        print(f"\nNo trading days processed for {year}-{month:02d}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run monthly backtest')
    parser.add_argument('--year', type=int, default=2025, help='Year')
    parser.add_argument('--month', type=int, default=9, help='Month (1-12)')
    parser.add_argument('--account-size', type=int, default=100000, help='Account size')
    parser.add_argument('--start-day', type=int, help='Start day (1-31) - optional')
    parser.add_argument('--end-day', type=int, help='End day (1-31) - optional')
    parser.add_argument('--run-name', type=str, help='Run name for logging (e.g., longs_only)')

    args = parser.parse_args()

    run_monthly_backtest(
        args.year,
        args.month,
        args.account_size,
        args.start_day,
        args.end_day,
        args.run_name
    )
