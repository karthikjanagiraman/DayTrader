#!/usr/bin/env python3
"""Test script to run backtest for just a few days"""

from run_monthly_backtest import HistoricalScanner
from backtester import PS60Backtester
from datetime import datetime
from pathlib import Path
import json

# Test with just Sept 27-30 first
test_dates = [
    datetime(2025, 9, 27),  # Friday
    datetime(2025, 9, 30),  # Monday
]

scanner = HistoricalScanner()
output_dir = Path('monthly_results')
output_dir.mkdir(exist_ok=True)

for test_date in test_dates:
    print(f"\n{'='*80}")
    print(f"Testing {test_date.strftime('%Y-%m-%d')}")
    print(f"{'='*80}")

    # Run scanner
    results = scanner.scan_for_date(test_date)

    if results and len(results) > 0:
        # Save scanner results
        scanner_file = output_dir / f'scanner_{test_date.strftime("%Y%m%d")}.json'
        with open(scanner_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"✓ Scanner: {len(results)} setups saved to {scanner_file}")

        # Run backtest
        backtester = PS60Backtester(
            scanner_results_path=str(scanner_file),
            test_date=test_date,
            account_size=100000
        )
        backtester.run()

        if backtester.trades:
            total_pnl = sum(t['pnl'] for t in backtester.trades)
            print(f"✓ Backtest: {len(backtester.trades)} trades, ${total_pnl:,.2f} P&L")
        else:
            print(f"✓ Backtest: No trades")
    else:
        print(f"✗ No scanner results")

print(f"\n{'='*80}")
print("Test complete!")
print(f"{'='*80}")
