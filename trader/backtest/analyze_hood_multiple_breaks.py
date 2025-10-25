#!/usr/bin/env python3
"""
Analyze HOOD tick data at MULTIPLE support breaks on Oct 21
Check 9:43, 9:55, and 10:27 AM breakdowns
Using CORRECT uptick/downtick rule
"""
import json
from pathlib import Path

def analyze_tick_window(tick_file):
    """Analyze CVD for a single 1-minute window using proper uptick/downtick rule"""
    if not tick_file.exists():
        return None

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

def print_candle_analysis(time_label, result):
    """Print CVD analysis for a single candle"""
    if result is None:
        print(f"{time_label}: ❌ No data available")
        return

    print(f"{time_label}:")
    print(f"  Total ticks:     {result['total_ticks']:,}")
    print(f"  Total volume:    {result['total_volume']:,.0f} shares")
    print(f"  Buy volume:      {result['buy_volume']:,.0f} shares ({result['buy_volume']/result['total_volume']*100:.1f}%)")
    print(f"  Sell volume:     {result['sell_volume']:,.0f} shares ({result['sell_volume']/result['total_volume']*100:.1f}%)")
    print(f"  Neutral volume:  {result['neutral_volume']:,.0f} shares ({result['neutral_volume']/result['total_volume']*100:.1f}%)")
    print(f"  Imbalance:       {result['imbalance_pct']:+.1f}%")
    print(f"  Price range:     ${result['price_range'][0]:.2f} - ${result['price_range'][1]:.2f}")
    print(f"  Candle:          ${result['first_price']:.2f} → ${result['last_price']:.2f}")
    print()

    # Check thresholds
    print(f"  AGGRESSIVE (40%): {'✅ PASS' if result['imbalance_pct'] >= 40 else '❌ FAIL'} ({abs(result['imbalance_pct']):.1f}% vs 40%)")
    print(f"  SUSTAINED (20%):  {'✅ PASS' if result['imbalance_pct'] >= 20 else '❌ FAIL'} ({abs(result['imbalance_pct']):.1f}% vs 20%)")

    if result['imbalance_pct'] > 0:
        print(f"  📊 BEARISH bias (more selling) ✅")
    elif result['imbalance_pct'] < 0:
        print(f"  📈 BULLISH bias (more buying) ❌")
    else:
        print(f"  ⚖️  NEUTRAL")
    print()

# Header
print("="*80)
print("CVD ANALYSIS - HOOD MULTIPLE SUPPORT BREAKS (Oct 21, 2025)")
print("Using CORRECT uptick/downtick rule from CVDCalculator")
print("="*80)
print()

# Scanner setup
support = 132.90
downside1 = 125.26

print(f"Scanner Setup:")
print(f"  Support: ${support:.2f} (SHORT entry trigger)")
print(f"  Downside1 target: ${downside1:.2f}")
print()

# Analyze all three breakdown times
print("="*80)
print("BREAKDOWN #1: 9:43 AM")
print("="*80)
result_0943 = analyze_tick_window(Path("data/ticks/HOOD_20251021_094300_ticks.json"))
print_candle_analysis("9:43 AM", result_0943)

print("="*80)
print("BREAKDOWN #2: 9:55 AM")
print("="*80)
result_0955 = analyze_tick_window(Path("data/ticks/HOOD_20251021_095500_ticks.json"))
print_candle_analysis("9:55 AM", result_0955)

print("="*80)
print("BREAKDOWN #3: 10:27 AM")
print("="*80)
result_1027 = analyze_tick_window(Path("data/ticks/HOOD_20251021_102700_ticks.json"))
print_candle_analysis("10:27 AM", result_1027)

# Check for SUSTAINED path at each breakdown
print("="*80)
print("SUSTAINED PATH ANALYSIS (3 consecutive candles ≥20% BEARISH)")
print("="*80)
print()

def check_sustained_path(start_time, start_result):
    """Check if 3 consecutive candles meet 20% threshold"""
    print(f"Starting at {start_time}:")

    # Parse time
    hour = int(start_time[:2])
    minute = int(start_time[2:4])

    results = [start_result]

    # Get next 2 candles
    for i in range(1, 3):
        next_minute = minute + i
        next_hour = hour
        if next_minute >= 60:
            next_minute -= 60
            next_hour += 1

        next_time = f"{next_hour:02d}{next_minute:02d}00"
        tick_file = Path(f"data/ticks/HOOD_20251021_{next_time}_ticks.json")
        result = analyze_tick_window(tick_file)
        results.append(result)

    # Check all 3 candles
    times = [start_time, f"{hour:02d}{(minute+1)%60:02d}", f"{hour:02d}{(minute+2)%60:02d}"]
    all_pass = True

    for i, (time, result) in enumerate(zip(times, results)):
        if result is None:
            print(f"  {time[:2]}:{time[2:4]} AM: ❌ No data")
            all_pass = False
        else:
            status = '✅' if result['imbalance_pct'] >= 20 else '❌'
            print(f"  {time[:2]}:{time[2:4]} AM: {result['imbalance_pct']:+.1f}% {status}")
            if result['imbalance_pct'] < 20:
                all_pass = False

    if all_pass:
        print(f"  ✅ SUSTAINED PATH TRIGGERED!")
    else:
        print(f"  ❌ SUSTAINED PATH NOT MET")
    print()

# Check sustained path from each breakdown
if result_0943:
    check_sustained_path("094300", result_0943)

if result_0955:
    check_sustained_path("095500", result_0955)

if result_1027:
    check_sustained_path("102700", result_1027)

print("="*80)
print("SUMMARY")
print("="*80)
print()

breakdown_times = [
    ("9:43 AM", result_0943),
    ("9:55 AM", result_0955),
    ("10:27 AM", result_1027)
]

print("Breakdown Imbalances:")
for time_label, result in breakdown_times:
    if result:
        aggressive = '✅' if result['imbalance_pct'] >= 40 else '❌'
        sustained = '✅' if result['imbalance_pct'] >= 20 else '❌'
        print(f"  {time_label}: {result['imbalance_pct']:+.1f}% | AGG(40%): {aggressive} | SUS(20%): {sustained}")
    else:
        print(f"  {time_label}: ❌ No data")

print()
print("="*80)
