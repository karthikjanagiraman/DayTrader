#!/usr/bin/env python3
"""
Run backtest for one week (Sept 23-30, 2025)
Testing 5-minute rule fix with original config
"""

import sys
from datetime import date
sys.path.insert(0, '..')

from backtest.run_monthly_backtest import run_monthly_backtest

if __name__ == "__main__":
    print("="*80)
    print("WEEK BACKTEST: Sept 23-30, 2025")
    print("Testing: 5-minute rule fix (stuck-at-pivot detection)")
    print("Config: Original settings (score 70, R/R 1.0, 9:45 AM entry)")
    print("="*80)

    # Run backtest for last week of September
    # This was the best week in the original backtest
    run_monthly_backtest(
        year=2025,
        month=9,
        account_size=100000,
        start_day=23,  # Sept 23 (Monday)
        end_day=30     # Sept 30 (Tuesday, month-end)
    )
