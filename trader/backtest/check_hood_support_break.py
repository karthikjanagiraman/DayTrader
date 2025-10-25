#!/usr/bin/env python3
"""
Check if HOOD broke support ($132.90) on Oct 21, 2025
"""
import json
from pathlib import Path
import glob

# HOOD scanner setup
support_level = 132.90
resistance_level = 140.20
previous_close = 137.24

print("="*80)
print("HOOD SUPPORT BREAK ANALYSIS - Oct 21, 2025")
print("="*80)
print(f"Support level: ${support_level:.2f}")
print(f"Resistance level: ${resistance_level:.2f}")
print(f"Previous close: ${previous_close:.2f}")
print()

# Find all HOOD tick files
tick_files = sorted(glob.glob("data/ticks/HOOD_20251021_*.json"))
print(f"Total tick files: {len(tick_files)}")
print()

# Track price extremes
day_high = 0.0
day_low = 999999.0
support_breaks = []
resistance_breaks = []

for tick_file in tick_files:
    with open(tick_file) as f:
        ticks = json.load(f)

    if not ticks:
        continue

    for tick in ticks:
        price = tick['price']

        # Track day high/low
        day_high = max(day_high, price)
        day_low = min(day_low, price)

        # Check support break
        if price < support_level:
            time_str = Path(tick_file).stem.split('_')[-2]  # Extract time
            support_breaks.append({
                'time': time_str,
                'price': price,
                'file': Path(tick_file).name
            })

        # Check resistance break
        if price > resistance_level:
            time_str = Path(tick_file).stem.split('_')[-2]
            resistance_breaks.append({
                'time': time_str,
                'price': price,
                'file': Path(tick_file).name
            })

print(f"Day's Range: ${day_low:.2f} - ${day_high:.2f}")
print(f"Day's Move: {((day_high - day_low) / day_low * 100):.2f}%")
print()

# Support analysis
print("="*80)
print("SUPPORT BREAK ($132.90) ANALYSIS")
print("="*80)

if support_breaks:
    print(f"✅ SUPPORT WAS BROKEN!")
    print(f"Total support breaks: {len(support_breaks)}")
    print()

    # Find first break
    first_break = support_breaks[0]
    print(f"First break:")
    print(f"  Time: {first_break['time'][:2]}:{first_break['time'][2:4]} ET")
    print(f"  Price: ${first_break['price']:.2f}")
    print(f"  File: {first_break['file']}")
    print()

    # Find lowest price during support break
    lowest_break = min(support_breaks, key=lambda x: x['price'])
    print(f"Lowest price below support:")
    print(f"  Time: {lowest_break['time'][:2]}:{lowest_break['time'][2:4]} ET")
    print(f"  Price: ${lowest_break['price']:.2f}")
    print(f"  Distance below support: ${support_level - lowest_break['price']:.2f} ({((support_level - lowest_break['price']) / support_level * 100):.2f}%)")
    print()
else:
    print(f"❌ SUPPORT WAS NOT BROKEN")
    print(f"Lowest price: ${day_low:.2f}")
    print(f"Distance to support: ${day_low - support_level:.2f} ({((day_low - support_level) / support_level * 100):.2f}% above)")
    print()

# Resistance analysis
print("="*80)
print("RESISTANCE BREAK ($140.20) ANALYSIS")
print("="*80)

if resistance_breaks:
    print(f"✅ RESISTANCE WAS BROKEN!")
    print(f"Total resistance breaks: {len(resistance_breaks)}")
    print()

    # Find first break
    first_break = resistance_breaks[0]
    print(f"First break:")
    print(f"  Time: {first_break['time'][:2]}:{first_break['time'][2:4]} ET")
    print(f"  Price: ${first_break['price']:.2f}")
    print(f"  File: {first_break['file']}")
    print()
else:
    print(f"❌ RESISTANCE WAS NOT BROKEN")
    print(f"Highest price: ${day_high:.2f}")
    print(f"Distance to resistance: ${resistance_level - day_high:.2f} ({((resistance_level - day_high) / resistance_level * 100):.2f}% below)")
    print()

print("="*80)
