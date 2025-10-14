#!/usr/bin/env python3
"""
Batch scanner for generating historical scanner results
Runs scanner for multiple trading days
"""

from datetime import date, timedelta
from scanner import PS60Scanner
import time
import sys

def get_trading_days(start_date, end_date):
    """Generate list of trading days (excluding weekends)"""
    current_date = start_date
    trading_days = []

    while current_date <= end_date:
        # Skip weekends (Saturday=5, Sunday=6)
        if current_date.weekday() < 5:
            trading_days.append(current_date)
        current_date += timedelta(days=1)

    return trading_days

def main():
    # Configuration
    start_date = date(2025, 9, 15)
    end_date = date(2025, 10, 7)

    trading_days = get_trading_days(start_date, end_date)

    print(f"\n{'='*80}")
    print(f"BATCH HISTORICAL SCANNER")
    print(f"{'='*80}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Trading Days: {len(trading_days)}")
    print(f"{'='*80}\n")

    # Run scanner for each trading day
    successful = []
    failed = []

    for i, trading_day in enumerate(trading_days, 1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(trading_days)}] Scanning for {trading_day.strftime('%Y-%m-%d')} ({trading_day.strftime('%A')})")
        print(f"{'='*80}")

        try:
            # Create new scanner instance for each day
            # Use unique client ID (2000 + day index) to avoid conflicts
            scanner = PS60Scanner()
            scanner.connect(client_id=2000 + i)
            success = scanner.run_scan(category='all', historical_date=trading_day)

            if success:
                successful.append(trading_day)
                print(f"\n✅ Completed: {trading_day.strftime('%Y-%m-%d')}")
            else:
                failed.append(trading_day)
                print(f"\n❌ Failed: {trading_day.strftime('%Y-%m-%d')}")

            # Small delay between scans to avoid overwhelming IBKR
            if i < len(trading_days):
                print("\nWaiting 3 seconds before next scan...")
                time.sleep(3)

        except KeyboardInterrupt:
            print("\n\n⚠️  Scan interrupted by user")
            break
        except Exception as e:
            failed.append(trading_day)
            print(f"\n❌ Error: {trading_day.strftime('%Y-%m-%d')}: {e}")
            import traceback
            traceback.print_exc()

    # Final summary
    print(f"\n{'='*80}")
    print("BATCH SCAN SUMMARY")
    print(f"{'='*80}")
    print(f"Total Days: {len(trading_days)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        print("\n✅ Successfully scanned:")
        for day in successful:
            print(f"   - {day.strftime('%Y-%m-%d')}")

    if failed:
        print("\n❌ Failed to scan:")
        for day in failed:
            print(f"   - {day.strftime('%Y-%m-%d')}")

    print(f"\n📁 Output files: stockscanner/output/scanner_results_YYYYMMDD.csv")
    print(f"{'='*80}\n")

    return 0 if len(failed) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
