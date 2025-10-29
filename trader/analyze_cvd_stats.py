#!/usr/bin/env python3
"""
Analyze CVD Statistics for SMCI Bars 10:00-10:03 (Oct 21, 2025)

Calculate buy/sell volumes and CVD imbalances for the requested bars.
"""

import json
import sys
from pathlib import Path

def classify_tick(current_price, previous_price):
    """
    Classify tick as buy (uptick) or sell (downtick)

    Returns:
        str: 'BUY' if uptick, 'SELL' if downtick, 'NEUTRAL' if unchanged
    """
    if current_price > previous_price:
        return 'BUY'
    elif current_price < previous_price:
        return 'SELL'
    else:
        return 'NEUTRAL'

def calculate_cvd_for_bar(tick_file):
    """Calculate CVD statistics for a single bar"""

    with open(tick_file) as f:
        ticks = json.load(f)

    if not ticks:
        return None

    buy_volume = 0
    sell_volume = 0
    total_volume = 0
    previous_price = ticks[0]['price']

    for tick in ticks:
        price = tick['price']
        volume = tick['size']

        classification = classify_tick(price, previous_price)

        if classification == 'BUY':
            buy_volume += volume
        elif classification == 'SELL':
            sell_volume += volume
        # Neutral ticks don't add to buy/sell

        total_volume += volume
        previous_price = price

    # Calculate CVD imbalance
    if total_volume > 0:
        cvd_imbalance = ((sell_volume - buy_volume) / total_volume) * 100
    else:
        cvd_imbalance = 0.0

    return {
        'buy_volume': buy_volume,
        'sell_volume': sell_volume,
        'total_volume': total_volume,
        'cvd_imbalance': cvd_imbalance,
        'tick_count': len(ticks),
        'first_price': ticks[0]['price'],
        'last_price': ticks[-1]['price']
    }

def main():
    """Analyze CVD for SMCI bars 10:00-10:03"""

    base_path = Path('/Users/karthik/projects/DayTrader/trader/backtest/data/ticks')

    bars = [
        ('10:00:00', 'SMCI_20251021_100000_ticks.json'),
        ('10:01:00', 'SMCI_20251021_100100_ticks.json'),
        ('10:02:00', 'SMCI_20251021_100200_ticks.json'),
        ('10:03:00', 'SMCI_20251021_100300_ticks.json')
    ]

    print("=" * 80)
    print("SMCI CVD STATISTICS - October 21, 2025 (10:00-10:03)")
    print("=" * 80)
    print()

    for time, filename in bars:
        tick_file = base_path / filename

        if not tick_file.exists():
            print(f"❌ {time}: File not found - {filename}")
            continue

        stats = calculate_cvd_for_bar(tick_file)

        if not stats:
            print(f"❌ {time}: No tick data")
            continue

        print(f"📊 {time}")
        print(f"   Ticks: {stats['tick_count']}")
        print(f"   Price: ${stats['first_price']:.2f} → ${stats['last_price']:.2f}")
        print(f"   Price Change: ${stats['last_price'] - stats['first_price']:+.2f}")
        print()
        print(f"   Buy Volume:  {stats['buy_volume']:>10,}")
        print(f"   Sell Volume: {stats['sell_volume']:>10,}")
        print(f"   Total Volume: {stats['total_volume']:>10,}")
        print()
        print(f"   CVD Imbalance: {stats['cvd_imbalance']:+.2f}%")

        if stats['cvd_imbalance'] > 0:
            print(f"   → BEARISH (more sell pressure)")
        elif stats['cvd_imbalance'] < 0:
            print(f"   → BULLISH (more buy pressure)")
        else:
            print(f"   → NEUTRAL")

        print()
        print("-" * 80)
        print()

    # Load 1-minute bar data for volume thresholds
    bars_file = Path('/Users/karthik/projects/DayTrader/trader/backtest/data/SMCI_20251021_1min.json')
    with open(bars_file) as f:
        bars_data = json.load(f)

    # Find the 10:00-10:03 bars
    print()
    print("=" * 80)
    print("VOLUME THRESHOLD INFORMATION")
    print("=" * 80)
    print()

    for bar in bars_data:
        time_str = bar['date'].split('T')[1].split('-')[0][:5]
        if time_str in ['10:00', '10:01', '10:02', '10:03']:
            volume = bar['volume']
            avg_volume = bar.get('average', 0)  # Average price, not average volume

            print(f"{time_str}: Volume = {volume:,.0f}")

    print()
    print("Note: Volume threshold typically calculated from 20-period average")
    print("      For CVD entry: Usually requires 1.3-2.0x average volume")
    print()

if __name__ == '__main__':
    main()
