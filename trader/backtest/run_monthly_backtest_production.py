#!/usr/bin/env python3
"""
Monthly Backtesting Script - Uses Production Scanner
Generates daily scanner results using the ACTUAL production scanner,
then runs backtests on those results.

CRITICAL: No look-ahead bias
- Scanner for Sept 1 trading uses Aug 31 EOD data
- Scanner for Sept 2 trading uses Sept 1 EOD data
- etc.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import subprocess
import time

# Add paths
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / 'stockscanner'))
sys.path.append(str(project_root / 'trader' / 'backtest'))

from scanner import PS60Scanner
from backtester import PS60Backtester


def get_trading_days(year, month):
    """Get all trading days for a given month (excluding weekends)"""
    from datetime import date
    import calendar

    # Get all days in the month
    num_days = calendar.monthrange(year, month)[1]
    days = []

    for day in range(1, num_days + 1):
        d = date(year, month, day)
        # Skip weekends (Saturday=5, Sunday=6)
        if d.weekday() < 5:
            days.append(d)

    return days


def run_scanner_for_date(scanner, trading_date):
    """
    Run production scanner for a specific trading date

    CRITICAL: Uses data from PREVIOUS trading day to avoid look-ahead bias

    Args:
        scanner: PS60Scanner instance
        trading_date: The date we're trading (market open date)

    Returns:
        Path to saved scanner results
    """
    # Scanner runs "night before" using previous day's close data
    # For Sept 1 trading, scanner uses Aug 31 data
    scan_date = trading_date - timedelta(days=1)

    print(f"\n{'='*80}")
    print(f"SCANNING FOR {trading_date.strftime('%Y-%m-%d')} TRADING SESSION")
    print(f"Using data through: {scan_date.strftime('%Y-%m-%d')} (previous close)")
    print(f"{'='*80}")

    # Run the production scanner with historical date
    success = scanner.run_scan(category='all', historical_date=scan_date)

    if not success or not scanner.results:
        print(f"⚠️  No results from scanner for {trading_date.strftime('%Y-%m-%d')}")
        return None

    # Save results with trading date in filename
    output_dir = Path(__file__).parent / 'monthly_results_production'
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"scanner_{trading_date.strftime('%Y%m%d')}.json"

    with open(output_file, 'w') as f:
        json.dump(scanner.results, f, indent=2)

    print(f"✓ Saved {len(scanner.results)} setups to {output_file}")

    # Clear results for next iteration
    scanner.results = []

    return output_file


def run_backtest_for_date(scanner_file, trading_date):
    """
    Run backtest for a specific trading date using scanner results

    Args:
        scanner_file: Path to scanner results JSON
        trading_date: The trading date to backtest

    Returns:
        Dictionary with backtest results
    """
    print(f"\n{'='*80}")
    print(f"BACKTESTING {trading_date.strftime('%Y-%m-%d')}")
    print(f"Scanner file: {scanner_file}")
    print(f"{'='*80}")

    # Run backtester
    bt = PS60Backtester(
        scanner_results_path=str(scanner_file),
        test_date=trading_date,
        account_size=100000
    )

    bt.run()

    # Return summary
    return {
        'date': trading_date.strftime('%Y-%m-%d'),
        'trades': len(bt.trades),
        'pnl': sum(t['pnl'] for t in bt.trades) if bt.trades else 0,
        'winners': len([t for t in bt.trades if t['pnl'] > 0]) if bt.trades else 0,
        'losers': len([t for t in bt.trades if t['pnl'] < 0]) if bt.trades else 0,
    }


def main():
    """Main execution"""
    # September 2025
    year = 2025
    month = 9

    print(f"\n{'='*80}")
    print(f"MONTHLY BACKTEST: {year}-{month:02d} (PRODUCTION SCANNER)")
    print(f"{'='*80}\n")

    # Get all trading days
    trading_days = get_trading_days(year, month)
    print(f"Found {len(trading_days)} trading days in {year}-{month:02d}\n")

    # Initialize scanner once
    scanner = PS60Scanner()

    # Results tracking
    all_results = []

    # Process each trading day
    for i, trading_date in enumerate(trading_days, 1):
        print(f"\n{'='*80}")
        print(f"Processing {trading_date.strftime('%Y-%m-%d')} ({i}/{len(trading_days)})")
        print(f"{'='*80}\n")

        try:
            # Step 1: Run scanner (using previous day's data)
            scanner_file = run_scanner_for_date(scanner, trading_date)

            if not scanner_file:
                print(f"⚠️  Skipping backtest - no scanner results")
                continue

            # Step 2: Run backtest on that day's trading
            result = run_backtest_for_date(scanner_file, trading_date)
            all_results.append(result)

            print(f"\n✓ {trading_date.strftime('%Y-%m-%d')}: {result['trades']} trades, ${result['pnl']:.2f} P&L")

        except Exception as e:
            print(f"\n❌ ERROR processing {trading_date.strftime('%Y-%m-%d')}: {e}")
            import traceback
            traceback.print_exc()
            continue

        # Small delay between days
        time.sleep(1)

    # Print monthly summary
    print(f"\n{'='*80}")
    print(f"MONTHLY SUMMARY: {year}-{month:02d}")
    print(f"{'='*80}")

    if all_results:
        total_trades = sum(r['trades'] for r in all_results)
        total_pnl = sum(r['pnl'] for r in all_results)
        total_winners = sum(r['winners'] for r in all_results)
        total_losers = sum(r['losers'] for r in all_results)

        win_rate = (total_winners / total_trades * 100) if total_trades > 0 else 0

        print(f"Total Trading Days: {len(all_results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Total P&L: ${total_pnl:,.2f}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"Winners: {total_winners}")
        print(f"Losers: {total_losers}")
        print(f"Avg P&L per Day: ${total_pnl / len(all_results):,.2f}")
        print(f"Avg Trades per Day: {total_trades / len(all_results):.1f}")

        # Save summary
        summary_file = Path(__file__).parent / 'monthly_results_production' / 'summary.json'
        with open(summary_file, 'w') as f:
            json.dump({
                'month': f"{year}-{month:02d}",
                'total_days': len(all_results),
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'winners': total_winners,
                'losers': total_losers,
                'daily_results': all_results
            }, f, indent=2)

        print(f"\n✓ Saved summary to {summary_file}")
    else:
        print("No results to summarize")

    print(f"\n{'='*80}\n")


if __name__ == '__main__':
    main()
