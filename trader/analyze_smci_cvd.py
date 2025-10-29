#!/usr/bin/env python3
"""
Analyze SMCI tick data for bars 31-34 to investigate CVD bug
Why does CVD show BEARISH when price is moving UP?
"""

import json
from pathlib import Path
from datetime import datetime

def analyze_tick_file(tick_file_path, bar_label):
    """Analyze a single tick file and calculate buy/sell volumes."""

    with open(tick_file_path, 'r') as f:
        ticks = json.load(f)

    if not ticks:
        print(f"  {bar_label}: NO TICK DATA")
        return

    # Calculate buy/sell volumes using CVD logic
    buy_volume = 0.0
    sell_volume = 0.0
    neutral_volume = 0.0
    last_price = None

    first_price = ticks[0]['price']
    last_price_final = ticks[-1]['price']
    price_change = last_price_final - first_price
    price_change_pct = (price_change / first_price) * 100

    # Classify each tick
    last_price = None
    for tick in ticks:
        current_price = tick['price']
        size = tick['size']

        if last_price is not None:
            if current_price > last_price:
                # Uptick = buying pressure
                buy_volume += size
            elif current_price < last_price:
                # Downtick = selling pressure
                sell_volume += size
            else:
                # Equal price = neutral
                neutral_volume += size

        last_price = current_price

    # Calculate imbalance percentage (CVD formula)
    total_volume = buy_volume + sell_volume  # Excludes neutral
    if total_volume > 0:
        imbalance_pct = ((sell_volume - buy_volume) / total_volume) * 100.0
    else:
        imbalance_pct = 0.0

    # Determine CVD trend (from CVD calculator logic)
    threshold = 10.0  # imbalance_threshold from config
    if imbalance_pct < -threshold:
        cvd_trend = 'BULLISH'
    elif imbalance_pct > threshold:
        cvd_trend = 'BEARISH'
    else:
        cvd_trend = 'NEUTRAL'

    # Print analysis
    print(f"\n{bar_label}")
    print("=" * 80)
    print(f"  Price Movement: ${first_price:.2f} → ${last_price_final:.2f} = {price_change:+.2f} ({price_change_pct:+.2f}%)")
    if price_change > 0:
        print(f"  → UPWARD price movement (should be BULLISH CVD)")
    else:
        print(f"  → DOWNWARD price movement (should be BEARISH CVD)")

    print(f"\n  Tick Volumes:")
    print(f"    Buy Volume (upticks):    {buy_volume:>10,.0f}")
    print(f"    Sell Volume (downticks): {sell_volume:>10,.0f}")
    print(f"    Neutral Volume:          {neutral_volume:>10,.0f}")
    print(f"    Total Classified:        {total_volume:>10,.0f}")

    print(f"\n  CVD Calculation:")
    print(f"    Imbalance %: (sell - buy) / total * 100")
    print(f"    Imbalance %: ({sell_volume:.0f} - {buy_volume:.0f}) / {total_volume:.0f} * 100")
    print(f"    Imbalance %: {imbalance_pct:+.2f}%")

    print(f"\n  CVD Trend Determination:")
    print(f"    If imbalance < -10%: BULLISH")
    print(f"    If imbalance > +10%: BEARISH")
    print(f"    Otherwise: NEUTRAL")
    print(f"    → Calculated CVD Trend: {cvd_trend}")

    # Compare with expected
    expected_trend = 'BULLISH' if price_change > 0 else 'BEARISH'
    if cvd_trend == expected_trend:
        print(f"    ✅ CORRECT: Price {expected_trend}, CVD {cvd_trend}")
    else:
        print(f"    ❌ BUG: Price movement is {expected_trend} but CVD shows {cvd_trend}!")

    return {
        'bar': bar_label,
        'price_start': first_price,
        'price_end': last_price_final,
        'price_change': price_change,
        'price_change_pct': price_change_pct,
        'buy_volume': buy_volume,
        'sell_volume': sell_volume,
        'neutral_volume': neutral_volume,
        'total_volume': total_volume,
        'imbalance_pct': imbalance_pct,
        'cvd_trend': cvd_trend,
        'expected_trend': expected_trend,
        'matches': cvd_trend == expected_trend
    }


def main():
    """Analyze SMCI tick data for bars 31-34."""

    print("\n" + "=" * 80)
    print("SMCI CVD BUG INVESTIGATION - October 21, 2025")
    print("=" * 80)
    print("\nAnalyzing tick data for bars 31-34 to understand why CVD shows BEARISH")
    print("when price is moving UP.")
    print("\nFrom backtest log:")
    print("  Bar 32: Price $54.35 → $54.38 (UP $0.03), CVD: 21.0% BEARISH")
    print("  Bar 34: Price $54.16 → $54.28 (UP $0.12), CVD: 22.1% BEARISH")

    tick_dir = Path('/Users/karthik/projects/DayTrader/trader/backtest/data/ticks')

    results = []

    # Analyze each minute
    bars = [
        ('100000', 'Bar 31 (10:00 AM) - Momentum Detected'),
        ('100100', 'Bar 32 (10:01 AM) - CVD Monitoring, 21.0% imbalance'),
        ('100200', 'Bar 33 (10:02 AM) - CVD Monitoring, 32.3% imbalance'),
        ('100300', 'Bar 34 (10:03 AM) - Entry Confirmed, 22.1% imbalance')
    ]

    for time_str, label in bars:
        tick_file = tick_dir / f'SMCI_20251021_{time_str}_ticks.json'
        if tick_file.exists():
            result = analyze_tick_file(tick_file, label)
            if result:
                results.append(result)
        else:
            print(f"\n{label}")
            print(f"  ❌ TICK FILE NOT FOUND: {tick_file}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY OF FINDINGS")
    print("=" * 80)

    for result in results:
        match_symbol = "✅" if result['matches'] else "❌"
        print(f"\n{match_symbol} {result['bar']}")
        print(f"   Price: ${result['price_start']:.2f} → ${result['price_end']:.2f} ({result['price_change_pct']:+.2f}%)")
        print(f"   Buy: {result['buy_volume']:,.0f}, Sell: {result['sell_volume']:,.0f}")
        print(f"   Imbalance: {result['imbalance_pct']:+.1f}%")
        print(f"   CVD Trend: {result['cvd_trend']} (expected: {result['expected_trend']})")

    # Count mismatches
    mismatches = [r for r in results if not r['matches']]
    if mismatches:
        print(f"\n🚨 CRITICAL BUG CONFIRMED:")
        print(f"   {len(mismatches)}/{len(results)} bars show INCORRECT CVD trend!")
        print(f"\n   This explains why SHORT trades entered when price was moving UP!")
        print(f"   System entered SHORT because CVD showed BEARISH,")
        print(f"   but price was actually moving UP (should be BULLISH CVD).")
    else:
        print(f"\n✅ No CVD trend mismatches found")
        print(f"   All {len(results)} bars show CORRECT CVD trend matching price direction")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
