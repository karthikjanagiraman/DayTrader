#!/usr/bin/env python3
"""
Quick one-day test with new requirements implementation
Testing: Sept 23, 2025 (was best day originally)
"""

import sys
from pathlib import Path
from datetime import date

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'stockscanner'))

from backtest.backtester import PS60Backtester

# Test date
test_date = date(2025, 9, 23)
scanner_file = f"backtest/monthly_results_production/scanner_{test_date.strftime('%Y%m%d')}.json"

print("="*80)
print("ONE-DAY BACKTEST: September 23, 2025")
print("Testing new requirements implementation:")
print("  - Min R/R 2.0 (was 1.0)")
print("  - 1R-based partial profits (was $0.25)")
print("  - Volume + momentum + sustained break confirmation")
print("  - NO 5-minute rule")
print("  - Slippage 0.1% + commissions $0.005/share")
print("="*80)

try:
    backtester = PS60Backtester(
        scanner_file=scanner_file,
        test_date=test_date,
        account_size=100000
    )

    backtester.run()

    if backtester.trades:
        day_pnl = sum(t['pnl'] for t in backtester.trades)
        print(f"\n{'='*80}")
        print(f"Day Summary: {len(backtester.trades)} trades, ${day_pnl:,.2f} P&L")
        print(f"{'='*80}")
    else:
        print("\n❌ No trades executed")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
