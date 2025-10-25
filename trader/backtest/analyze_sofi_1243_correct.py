#!/usr/bin/env python3
"""
Analyze SOFI tick data at 12:43 PM on Oct 21 using CORRECT CVD methodology
Uses uptick/downtick rule (not simple midpoint classification)
"""
import json
from pathlib import Path

def analyze_tick_window(tick_file):
    """Analyze CVD for a single 1-minute window using proper uptick/downtick rule"""
    with open(tick_file) as f:
        ticks = json.load(f)

    if not ticks:
        return None

    # CORRECT METHOD: Uptick/Downtick rule (from CVDCalculator)
    buy_volume = 0.0
    sell_volume = 0.0
    neutral_volume = 0.0
    last_price = None

    for tick in ticks:
        price = tick['price']
        size = tick['size']

        if last_price is not None:
            # Classify tick as buy or sell based on price movement
            if price > last_price:
                # Uptick = buying pressure
                buy_volume += size
            elif price < last_price:
                # Downtick = selling pressure
                sell_volume += size
            else:
                # Equal price = neutral (don't count towards imbalance)
                neutral_volume += size

        last_price = price

    # Calculate imbalance
    total_volume = buy_volume + sell_volume  # Excludes neutral ticks
    if total_volume > 0:
        # Positive imbalance = more selling (BEARISH)
        # Negative imbalance = more buying (BULLISH)
        imbalance_pct = ((sell_volume - buy_volume) / total_volume) * 100.0
    else:
        imbalance_pct = 0.0

    # Get price info
    prices = [tick['price'] for tick in ticks]

    return {
        'total_ticks': len(ticks),
        'total_volume': buy_volume + sell_volume + neutral_volume,
        'buy_volume': buy_volume,
        'sell_volume': sell_volume,
        'neutral_volume': neutral_volume,
        'imbalance_pct': imbalance_pct,
        'price_range': (min(prices), max(prices)),
        'first_price': ticks[0]['price'],
        'last_price': ticks[-1]['price']
    }

# Analyze 12:43 PM
print("="*80)
print("CVD ANALYSIS - SOFI (Oct 21, 2025)")
print("Using CORRECT uptick/downtick rule from CVDCalculator")
print("="*80)
print()

tick_file_1243 = Path("data/ticks/SOFI_20251021_124300_ticks.json")
result_1243 = analyze_tick_window(tick_file_1243)

print("12:43 PM Candle:")
print(f"  Total ticks:     {result_1243['total_ticks']:,}")
print(f"  Total volume:    {result_1243['total_volume']:,.0f} shares")
print(f"  Buy volume:      {result_1243['buy_volume']:,.0f} shares ({result_1243['buy_volume']/result_1243['total_volume']*100:.1f}%)")
print(f"  Sell volume:     {result_1243['sell_volume']:,.0f} shares ({result_1243['sell_volume']/result_1243['total_volume']*100:.1f}%)")
print(f"  Neutral volume:  {result_1243['neutral_volume']:,.0f} shares")
print(f"  Imbalance:       {result_1243['imbalance_pct']:+.1f}%")
print(f"  Price range:     ${result_1243['price_range'][0]:.2f} - ${result_1243['price_range'][1]:.2f}")
print(f"  Candle:          ${result_1243['first_price']:.2f} → ${result_1243['last_price']:.2f}")
print()

# Check against thresholds
print("THRESHOLD CHECKS:")
print(f"  AGGRESSIVE (40%): {'✅ PASS' if abs(result_1243['imbalance_pct']) >= 40 else '❌ FAIL'} ({abs(result_1243['imbalance_pct']):.1f}% >= 40%)")
print(f"  SUSTAINED (20%):  {'✅ PASS' if abs(result_1243['imbalance_pct']) >= 20 else '❌ FAIL'} ({abs(result_1243['imbalance_pct']):.1f}% >= 20%)")
print()

if result_1243['imbalance_pct'] > 0:
    print("📊 BEARISH bias (more selling than buying)")
elif result_1243['imbalance_pct'] < 0:
    print("📈 BULLISH bias (more buying than selling)")
else:
    print("⚖️  NEUTRAL (equal buy/sell)")

print()
print("="*80)

# Also analyze 12:44 PM to check sustained condition
tick_file_1244 = Path("data/ticks/SOFI_20251021_124400_ticks.json")
if tick_file_1244.exists():
    result_1244 = analyze_tick_window(tick_file_1244)

    print()
    print("12:44 PM Candle (next minute):")
    print(f"  Total ticks:     {result_1244['total_ticks']:,}")
    print(f"  Total volume:    {result_1244['total_volume']:,.0f} shares")
    print(f"  Buy volume:      {result_1244['buy_volume']:,.0f} shares ({result_1244['buy_volume']/result_1244['total_volume']*100:.1f}%)")
    print(f"  Sell volume:     {result_1244['sell_volume']:,.0f} shares ({result_1244['sell_volume']/result_1244['total_volume']*100:.1f}%)")
    print(f"  Neutral volume:  {result_1244['neutral_volume']:,.0f} shares")
    print(f"  Imbalance:       {result_1244['imbalance_pct']:+.1f}%")
    print(f"  Price range:     ${result_1244['price_range'][0]:.2f} - ${result_1244['price_range'][1]:.2f}")
    print(f"  Candle:          ${result_1244['first_price']:.2f} → ${result_1244['last_price']:.2f}")
    print()

    # Check sustained condition
    print("SUSTAINED PATH (2 consecutive candles ≥20%):")
    both_pass_sustained = (abs(result_1243['imbalance_pct']) >= 20 and
                          abs(result_1244['imbalance_pct']) >= 20)
    print(f"  12:43 PM: {abs(result_1243['imbalance_pct']):.1f}% {'✅' if abs(result_1243['imbalance_pct']) >= 20 else '❌'}")
    print(f"  12:44 PM: {abs(result_1244['imbalance_pct']):.1f}% {'✅' if abs(result_1244['imbalance_pct']) >= 20 else '❌'}")
    print(f"  {'✅ SUSTAINED PATH TRIGGERED!' if both_pass_sustained else '❌ SUSTAINED PATH NOT MET'}")
    print()
    print("="*80)
