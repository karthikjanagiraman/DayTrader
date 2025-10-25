#!/usr/bin/env python3
"""
Analyze SOFI tick data at 12:43 PM on Oct 21 to calculate CVD metrics
"""
import json
from pathlib import Path

# Load tick data
tick_file = Path("data/ticks/SOFI_20251021_124300_ticks.json")
with open(tick_file) as f:
    ticks = json.load(f)

print(f"Total ticks: {len(ticks)}")
print()

# Calculate CVD metrics
if not ticks:
    print("No ticks found!")
    exit(1)

# Determine bid/ask spread and classify ticks
total_volume = 0
buy_volume = 0
sell_volume = 0

# Get price range for bid/ask estimation
prices = [tick['price'] for tick in ticks]
min_price = min(prices)
max_price = max(prices)
mid_price = (min_price + max_price) / 2

print(f"Price range: ${min_price:.2f} - ${max_price:.2f}")
print(f"Mid price: ${mid_price:.2f}")
print()

# Classify each tick as buy or sell based on price relative to mid
for tick in ticks:
    volume = tick['size']
    price = tick['price']
    total_volume += volume

    # Simple classification: above mid = buy, below mid = sell
    if price >= mid_price:
        buy_volume += volume
    else:
        sell_volume += volume

# Calculate imbalance
if total_volume > 0:
    buy_pct = (buy_volume / total_volume) * 100
    sell_pct = (sell_volume / total_volume) * 100
    imbalance_pct = ((sell_volume - buy_volume) / total_volume) * 100
else:
    buy_pct = 0
    sell_pct = 0
    imbalance_pct = 0

print("="*60)
print("CVD METRICS - SOFI @ 12:43 PM (Oct 21, 2025)")
print("="*60)
print(f"Total Volume:    {total_volume:,} shares")
print(f"Buy Volume:      {buy_volume:,} shares ({buy_pct:.1f}%)")
print(f"Sell Volume:     {sell_volume:,} shares ({sell_pct:.1f}%)")
print(f"Imbalance:       {imbalance_pct:+.1f}%")
print()

# Check against thresholds
print("THRESHOLD CHECKS:")
print(f"  AGGRESSIVE (40% imbalance): {'✅ PASS' if abs(imbalance_pct) >= 40 else '❌ FAIL'} ({abs(imbalance_pct):.1f}% >= 40%)")
print(f"  SUSTAINED (20% imbalance):  {'✅ PASS' if abs(imbalance_pct) >= 20 else '❌ FAIL'} ({abs(imbalance_pct):.1f}% >= 20%)")
print()

if imbalance_pct > 0:
    print("📊 BEARISH bias (more selling than buying)")
elif imbalance_pct < 0:
    print("📈 BULLISH bias (more buying than selling)")
else:
    print("⚖️  NEUTRAL (equal buy/sell)")

# Show sample ticks
print()
print("Sample ticks (first 10):")
for i, tick in enumerate(ticks[:10]):
    classification = "BUY" if tick['price'] >= mid_price else "SELL"
    print(f"  {i+1}. ${tick['price']:.2f} x {tick['size']:,} shares ({classification})")
