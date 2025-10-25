#!/usr/bin/env python3
"""
Check CVD data quality for all stocks on Oct 21, 2025
"""
import json
import glob
from pathlib import Path

cvd_files = glob.glob("data/cvd_bars/*_20251021_cvd.json")

print("=" * 80)
print("CVD DATA QUALITY CHECK - Oct 21, 2025")
print("=" * 80)
print()

total_files = len(cvd_files)
empty_files = 0

for file_path in sorted(cvd_files):
    symbol = Path(file_path).stem.split('_')[0]

    with open(file_path) as f:
        data = json.load(f)

    bars = data.get('bars', [])
    zero_vol_bars = sum(1 for b in bars if b.get('total_volume', 0) == 0)
    nonzero_vol_bars = len(bars) - zero_vol_bars

    pct_zero = (zero_vol_bars / len(bars) * 100) if bars else 0

    if pct_zero > 50:
        status = "❌ EMPTY"
        empty_files += 1
    elif pct_zero > 10:
        status = "⚠️  SPARSE"
    else:
        status = "✅ GOOD"

    print(f"{status} {symbol:6s}: {nonzero_vol_bars:3d}/{len(bars):3d} bars have volume ({100-pct_zero:.1f}%)")

print()
print("=" * 80)
print(f"SUMMARY: {empty_files}/{total_files} files have >50% empty bars")
print("=" * 80)
