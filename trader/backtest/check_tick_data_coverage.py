#!/usr/bin/env python3
"""
Check which dates have complete tick/CVD data for all scanner stocks
"""
import json
import glob
from pathlib import Path
from collections import defaultdict

# Find all scanner files
scanner_dir = "/Users/karthik/projects/DayTrader/stockscanner/output"
scanner_files = sorted(glob.glob(f"{scanner_dir}/scanner_results_*.json"))

print("=" * 80)
print("TICK/CVD DATA COVERAGE ANALYSIS")
print("=" * 80)
print()

results = []

for scanner_file in scanner_files:
    # Extract date from filename (e.g., scanner_results_20251021.json -> 20251021)
    filename = Path(scanner_file).stem
    date_str = filename.split('_')[-1]

    # Load scanner results
    try:
        with open(scanner_file) as f:
            scanner = json.load(f)
    except:
        continue

    symbols = [s['symbol'] for s in scanner]
    total_stocks = len(symbols)

    # Check CVD data for each stock
    stocks_with_cvd = 0
    stocks_with_volume = 0
    missing_stocks = []
    empty_stocks = []

    for symbol in symbols:
        cvd_file = f"data/cvd_bars/{symbol}_{date_str}_cvd.json"

        # Check if CVD file exists
        if not Path(cvd_file).exists():
            missing_stocks.append(symbol)
            continue

        stocks_with_cvd += 1

        # Check if CVD file has actual volume data
        try:
            with open(cvd_file) as f:
                data = json.load(f)

            bars = data.get('bars', [])
            nonzero_vol_bars = sum(1 for b in bars if b.get('total_volume', 0) > 0)

            if nonzero_vol_bars > 0:
                stocks_with_volume += 1
            else:
                empty_stocks.append(symbol)
        except:
            empty_stocks.append(symbol)

    # Calculate coverage
    cvd_coverage = (stocks_with_cvd / total_stocks * 100) if total_stocks > 0 else 0
    volume_coverage = (stocks_with_volume / total_stocks * 100) if total_stocks > 0 else 0

    # Status
    if volume_coverage == 100:
        status = "✅ COMPLETE"
    elif volume_coverage > 0:
        status = "⚠️  PARTIAL"
    else:
        status = "❌ EMPTY"

    results.append({
        'date': date_str,
        'status': status,
        'total': total_stocks,
        'with_volume': stocks_with_volume,
        'volume_pct': volume_coverage,
        'missing': missing_stocks,
        'empty': empty_stocks
    })

    print(f"{status} {date_str}: {stocks_with_volume}/{total_stocks} stocks ({volume_coverage:.0f}%) have CVD data")

    if missing_stocks:
        print(f"   Missing files: {', '.join(missing_stocks[:5])}{' ...' if len(missing_stocks) > 5 else ''}")

    if empty_stocks:
        print(f"   Empty files: {', '.join(empty_stocks[:5])}{' ...' if len(empty_stocks) > 5 else ''}")

    print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

complete_dates = [r for r in results if r['volume_pct'] == 100]
partial_dates = [r for r in results if 0 < r['volume_pct'] < 100]
empty_dates = [r for r in results if r['volume_pct'] == 0]

print(f"✅ COMPLETE ({len(complete_dates)} dates): All stocks have CVD data with volume")
for r in complete_dates:
    print(f"   {r['date']}: {r['with_volume']}/{r['total']} stocks")

if partial_dates:
    print(f"\n⚠️  PARTIAL ({len(partial_dates)} dates): Some stocks missing CVD data")
    for r in partial_dates:
        print(f"   {r['date']}: {r['with_volume']}/{r['total']} stocks ({r['volume_pct']:.0f}%)")

if empty_dates:
    print(f"\n❌ EMPTY ({len(empty_dates)} dates): No stocks have CVD volume data")
    for r in empty_dates:
        print(f"   {r['date']}: {r['with_volume']}/{r['total']} stocks")

print()
print("=" * 80)
print(f"READY FOR BACKTEST: {len(complete_dates)} dates")
print("=" * 80)

if complete_dates:
    print("\nDates ready for CVD backtest:")
    for r in complete_dates:
        print(f"  python3 backtester.py --date {r['date'][:4]}-{r['date'][4:6]}-{r['date'][6:8]} "
              f"--scanner ../stockscanner/output/scanner_results_{r['date']}.json "
              f"--account-size 50000")
