#!/usr/bin/env python3
"""
Validate tick data completeness for October 15-22, 2025
Checks file counts, time coverage, and data integrity
"""

import os
import json
from collections import defaultdict
from datetime import datetime, time

# Expected symbols and dates
SYMBOLS = ['AMD', 'COIN', 'GME', 'HOOD', 'NVDA', 'PATH', 'PLTR', 'SMCI', 'SOFI', 'TSLA']
DATES = ['20251015', '20251016', '20251020', '20251021', '20251022']

# Trading hours (ET): 9:30 AM - 4:00 PM = 390 minutes
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
EXPECTED_FILES = 390  # 6.5 hours * 60 minutes

def parse_filename(filename):
    """Extract symbol, date, time from tick filename"""
    # Format: SYMBOL_YYYYMMDD_HHMMSS_ticks.json
    parts = filename.replace('_ticks.json', '').split('_')
    if len(parts) != 3:
        return None, None, None

    symbol = parts[0]
    date = parts[1]
    time_str = parts[2]

    return symbol, date, time_str

def validate_tick_data():
    """Validate tick data completeness"""

    # Get all tick files
    tick_files = [f for f in os.listdir('.') if f.endswith('_ticks.json')]

    # Group by symbol and date
    data = defaultdict(lambda: defaultdict(list))

    for filename in tick_files:
        symbol, date, time_str = parse_filename(filename)
        if symbol and date:
            data[symbol][date].append({
                'filename': filename,
                'time': time_str,
                'size': os.path.getsize(filename)
            })

    # Validation report
    print("=" * 80)
    print("TICK DATA COMPLETENESS VALIDATION")
    print("=" * 80)
    print()

    summary = {
        'total_symbols': 0,
        'total_dates': 0,
        'complete_days': 0,
        'incomplete_days': 0,
        'missing_days': 0
    }

    for symbol in SYMBOLS:
        print(f"{'='*80}")
        print(f"SYMBOL: {symbol}")
        print(f"{'='*80}")

        if symbol not in data:
            print(f"  ❌ NO TICK DATA FOUND")
            print()
            continue

        summary['total_symbols'] += 1

        for date in DATES:
            if date not in data[symbol]:
                print(f"  {date}: ❌ MISSING (0 files)")
                summary['missing_days'] += 1
                continue

            files = data[symbol][date]
            file_count = len(files)

            # Sort by time
            files.sort(key=lambda x: x['time'])

            # Get time range
            first_time = files[0]['time']
            last_time = files[-1]['time']

            # Calculate total size
            total_size = sum(f['size'] for f in files)
            size_mb = total_size / (1024 * 1024)

            # Check completeness
            completeness = (file_count / EXPECTED_FILES) * 100

            # Status
            if file_count >= EXPECTED_FILES - 10:  # Allow 10 minute tolerance
                status = "✅ COMPLETE"
                summary['complete_days'] += 1
            elif file_count >= EXPECTED_FILES * 0.9:  # 90% threshold
                status = "⚠️  MOSTLY COMPLETE"
                summary['incomplete_days'] += 1
            else:
                status = "❌ INCOMPLETE"
                summary['incomplete_days'] += 1

            summary['total_dates'] += 1

            # Check for zero-byte files
            zero_files = [f for f in files if f['size'] == 0]

            # Print status
            print(f"  {date}: {status}")
            print(f"    Files: {file_count}/{EXPECTED_FILES} ({completeness:.1f}%)")
            print(f"    Time Range: {first_time[:2]}:{first_time[2:4]} - {last_time[:2]}:{last_time[2:4]}")
            print(f"    Total Size: {size_mb:.2f} MB")

            if zero_files:
                print(f"    ⚠️  WARNING: {len(zero_files)} zero-byte files")

            # Check for large time gaps
            gaps = []
            for i in range(1, len(files)):
                prev_time = int(files[i-1]['time'])
                curr_time = int(files[i]['time'])

                # Calculate time difference in minutes
                prev_hour = prev_time // 10000
                prev_min = (prev_time % 10000) // 100
                curr_hour = curr_time // 10000
                curr_min = (curr_time % 10000) // 100

                time_diff = (curr_hour - prev_hour) * 60 + (curr_min - prev_min)

                if time_diff > 5:  # Gap > 5 minutes
                    gaps.append((files[i-1]['time'], files[i]['time'], time_diff))

            if gaps:
                print(f"    ⚠️  WARNING: {len(gaps)} time gaps > 5 minutes:")
                for prev_t, curr_t, diff in gaps[:3]:  # Show first 3
                    print(f"       {prev_t[:2]}:{prev_t[2:4]} → {curr_t[:2]}:{curr_t[2:4]} ({diff} min gap)")
                if len(gaps) > 3:
                    print(f"       ... and {len(gaps) - 3} more gaps")

            print()

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Symbols with Data: {summary['total_symbols']}/{len(SYMBOLS)}")
    print(f"Total Date-Symbol Combinations: {summary['total_dates']}")
    print(f"  ✅ Complete Days: {summary['complete_days']} ({summary['complete_days']/summary['total_dates']*100 if summary['total_dates'] > 0 else 0:.1f}%)")
    print(f"  ⚠️  Incomplete Days: {summary['incomplete_days']} ({summary['incomplete_days']/summary['total_dates']*100 if summary['total_dates'] > 0 else 0:.1f}%)")
    print(f"  ❌ Missing Days: {summary['missing_days']}")
    print()

    # Overall assessment
    if summary['complete_days'] >= summary['total_dates'] * 0.9:
        print("✅ OVERALL: EXCELLENT DATA QUALITY (90%+ complete)")
    elif summary['complete_days'] >= summary['total_dates'] * 0.7:
        print("⚠️  OVERALL: GOOD DATA QUALITY (70%+ complete)")
    else:
        print("❌ OVERALL: POOR DATA QUALITY (<70% complete)")

    print("=" * 80)

if __name__ == "__main__":
    validate_tick_data()
