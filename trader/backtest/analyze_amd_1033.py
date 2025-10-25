#!/usr/bin/env python3
"""
Analyze AMD tick data at 10:33 AM on Oct 21 (support break)
Using CORRECT uptick/downtick rule
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

# Analyze 10:33 AM (support break candle)
print("="*80)
print("CVD ANALYSIS - AMD (Oct 21, 2025)")
print("Support break at 10:33 AM ET")
print("Using CORRECT uptick/downtick rule from CVDCalculator")
print("="*80)
print()

# Scanner setup
support = 234.40
downside1 = 230.16

print(f"Scanner Setup:")
print(f"  Support: ${support:.2f} (SHORT entry trigger)")
print(f"  Downside1 target: ${downside1:.2f}")
print()

# Analyze 10:33 AM
tick_file_1033 = Path("data/ticks/AMD_20251021_103300_ticks.json")
result_1033 = analyze_tick_window(tick_file_1033)

print("10:33 AM Candle (support breakdowncandle):")
print(f"  Total ticks:     {result_1033['total_ticks']:,}")
print(f"  Total volume:    {result_1033['total_volume']:,.0f} shares")
print(f"  Buy volume:      {result_1033['buy_volume']:,.0f} shares ({result_1033['buy_volume']/result_1033['total_volume']*100:.1f}%)")
print(f"  Sell volume:     {result_1033['sell_volume']:,.0f} shares ({result_1033['sell_volume']/result_1033['total_volume']*100:.1f}%)")
print(f"  Neutral volume:  {result_1033['neutral_volume']:,.0f} shares")
print(f"  Imbalance:       {result_1033['imbalance_pct']:+.1f}%")
print(f"  Price range:     ${result_1033['price_range'][0]:.2f} - ${result_1033['price_range'][1]:.2f}")
print(f"  Candle:          ${result_1033['first_price']:.2f} → ${result_1033['last_price']:.2f}")
print()

# Check against thresholds
print("THRESHOLD CHECKS (for SHORT entry):")
print(f"  AGGRESSIVE (40%): {'✅ PASS' if result_1033['imbalance_pct'] >= 40 else '❌ FAIL'} ({abs(result_1033['imbalance_pct']):.1f}% >= 40%)")
print(f"  SUSTAINED (20%):  {'✅ PASS' if result_1033['imbalance_pct'] >= 20 else '❌ FAIL'} ({abs(result_1033['imbalance_pct']):.1f}% >= 20%)")
print()

if result_1033['imbalance_pct'] > 0:
    print("📊 BEARISH bias (more selling than buying) ✅ Correct for SHORT")
elif result_1033['imbalance_pct'] < 0:
    print("📈 BULLISH bias (more buying than selling) ❌ Wrong for SHORT")
else:
    print("⚖️  NEUTRAL (equal buy/sell)")

print()
print("="*80)

# Also analyze next 2 candles for SUSTAINED path
for i, minute in enumerate(["10:34", "10:35"], start=1):
    tick_file = Path(f"data/ticks/AMD_20251021_{minute.replace(':', '')}00_ticks.json")

    if tick_file.exists():
        result = analyze_tick_window(tick_file)

        print()
        print(f"{minute} AM Candle (+{i} minute after break):")
        print(f"  Imbalance:       {result['imbalance_pct']:+.1f}%")
        print(f"  Candle:          ${result['first_price']:.2f} → ${result['last_price']:.2f}")
        print(f"  Meets 20%:       {'✅' if result['imbalance_pct'] >= 20 else '❌'} ({abs(result['imbalance_pct']):.1f}% >= 20%)")

# Check sustained condition
print()
print("="*80)
print("SUSTAINED PATH (3 consecutive candles ≥20% BEARISH):")
print(f"  10:33 AM: {result_1033['imbalance_pct']:.1f}% {'✅' if result_1033['imbalance_pct'] >= 20 else '❌'}")

# Load next two candles
tick_file_1034 = Path("data/ticks/AMD_20251021_103400_ticks.json")
tick_file_1035 = Path("data/ticks/AMD_20251021_103500_ticks.json")

if tick_file_1034.exists():
    result_1034 = analyze_tick_window(tick_file_1034)
    print(f"  10:34 AM: {result_1034['imbalance_pct']:.1f}% {'✅' if result_1034['imbalance_pct'] >= 20 else '❌'}")

if tick_file_1035.exists():
    result_1035 = analyze_tick_window(tick_file_1035)
    print(f"  10:35 AM: {result_1035['imbalance_pct']:.1f}% {'✅' if result_1035['imbalance_pct'] >= 20 else '❌'}")

# Final decision
all_pass_sustained = (result_1033['imbalance_pct'] >= 20 and
                     result_1034['imbalance_pct'] >= 20 and
                     result_1035['imbalance_pct'] >= 20)

print()
if all_pass_sustained:
    print("✅ SUSTAINED PATH TRIGGERED! (3 consecutive bearish candles)")
else:
    print("❌ SUSTAINED PATH NOT MET (need 3 consecutive ≥20%)")

print()
print("="*80)
