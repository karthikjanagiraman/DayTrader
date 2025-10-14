#!/usr/bin/env python3
"""
Analyze stop loss slippage for losing trades on October 7, 2025

Examines 5-second bar data to understand why actual losses far exceed
expected stop distances.
"""

import json
from datetime import datetime
from pathlib import Path

def load_bars(symbol, date_str='20251007'):
    """Load 5-second bars from cached data"""
    data_file = Path(f"data/{symbol}_{date_str}_5sec.json")

    if not data_file.exists():
        print(f"❌ Data file not found: {data_file}")
        return []

    with open(data_file) as f:
        bars = json.load(f)

    return bars

def analyze_stop_slippage(symbol, entry_price, stop_price, exit_price, entry_time, exit_time, side='SHORT'):
    """
    Analyze stop loss slippage using 5-second bar data

    Args:
        symbol: Stock symbol
        entry_price: Actual entry price
        stop_price: Stop loss price
        exit_price: Actual exit price
        entry_time_str: Entry time (HH:MM:SS format)
        exit_time_str: Exit time (HH:MM:SS format)
        side: 'LONG' or 'SHORT'
    """
    print(f"\n{'='*80}")
    print(f"STOP LOSS SLIPPAGE ANALYSIS: {symbol} {side}")
    print(f"{'='*80}")

    # Load bar data
    bars = load_bars(symbol)
    if not bars:
        return

    print(f"\n📊 Position Details:")
    print(f"  Entry Price: ${entry_price:.2f}")
    print(f"  Stop Price:  ${stop_price:.2f}")
    print(f"  Exit Price:  ${exit_price:.2f}")
    print(f"  Entry Time:  {entry_time}")
    print(f"  Exit Time:   {exit_time}")

    # Calculate expected vs actual loss
    if side == 'SHORT':
        expected_loss_per_share = stop_price - entry_price
        actual_loss_per_share = exit_price - entry_price
    else:
        expected_loss_per_share = entry_price - stop_price
        actual_loss_per_share = entry_price - exit_price

    slippage = actual_loss_per_share - expected_loss_per_share
    slippage_pct = (slippage / expected_loss_per_share * 100) if expected_loss_per_share > 0 else 0

    print(f"\n💰 Loss Analysis:")
    print(f"  Expected Loss: ${abs(expected_loss_per_share):.2f}/share")
    print(f"  Actual Loss:   ${abs(actual_loss_per_share):.2f}/share")
    print(f"  Slippage:      ${abs(slippage):.2f}/share ({slippage_pct:.1f}%)")

    # Find bars around entry and exit times
    print(f"\n🔍 Searching for entry/exit bars...")

    entry_bar_idx = None
    exit_bar_idx = None
    stop_hit_idx = None

    for idx, bar in enumerate(bars):
        bar_time = bar['date'].split('T')[1][:8]  # Extract HH:MM:SS

        # Find entry bar
        if entry_bar_idx is None and bar_time >= entry_time:
            entry_bar_idx = idx
            print(f"\n📍 Entry Bar (index {idx}):")
            print(f"   Time: {bar['date']}")
            print(f"   Open: ${bar['open']:.2f} | High: ${bar['high']:.2f} | Low: ${bar['low']:.2f} | Close: ${bar['close']:.2f}")

        # Find when stop was hit
        if stop_hit_idx is None:
            if side == 'SHORT':
                # Stop hit when price goes above stop price
                if bar['high'] >= stop_price:
                    stop_hit_idx = idx
                    print(f"\n⚠️  Stop Hit Bar (index {idx}):")
                    print(f"   Time: {bar['date']}")
                    print(f"   Open: ${bar['open']:.2f} | High: ${bar['high']:.2f} | Low: ${bar['low']:.2f} | Close: ${bar['close']:.2f}")
                    print(f"   🔺 High ${bar['high']:.2f} exceeded stop ${stop_price:.2f}")
            else:
                # Stop hit when price goes below stop price
                if bar['low'] <= stop_price:
                    stop_hit_idx = idx
                    print(f"\n⚠️  Stop Hit Bar (index {idx}):")
                    print(f"   Time: {bar['date']}")
                    print(f"   Open: ${bar['open']:.2f} | High: ${bar['high']:.2f} | Low: ${bar['low']:.2f} | Close: ${bar['close']:.2f}")
                    print(f"   🔻 Low ${bar['low']:.2f} went below stop ${stop_price:.2f}")

        # Find exit bar
        if exit_bar_idx is None and bar_time >= exit_time:
            exit_bar_idx = idx
            print(f"\n🚪 Exit Bar (index {idx}):")
            print(f"   Time: {bar['date']}")
            print(f"   Open: ${bar['open']:.2f} | High: ${bar['high']:.2f} | Low: ${bar['low']:.2f} | Close: ${bar['close']:.2f}")
            print(f"   Exit Price: ${exit_price:.2f}")

    # Analyze slippage cause
    print(f"\n🔬 Slippage Analysis:")

    if stop_hit_idx is not None and exit_bar_idx is not None:
        stop_bar = bars[stop_hit_idx]
        exit_bar = bars[exit_bar_idx]

        # Check if exit price is within the stop bar's range
        if side == 'SHORT':
            # For shorts, we exit at ask (higher price)
            if exit_price <= stop_bar['high']:
                print(f"  ✅ Exit price ${exit_price:.2f} is within stop bar's range (Low ${stop_bar['low']:.2f} - High ${stop_bar['high']:.2f})")
                print(f"  💡 Slippage likely due to:")
                print(f"     - Simulated stop slippage (0.2% in config)")
                print(f"     - Exiting at bar's high instead of stop price")
            else:
                print(f"  ❌ Exit price ${exit_price:.2f} EXCEEDS stop bar's high ${stop_bar['high']:.2f}")
                print(f"  💡 This indicates a price gap beyond the bar's range!")
        else:
            # For longs, we exit at bid (lower price)
            if exit_price >= stop_bar['low']:
                print(f"  ✅ Exit price ${exit_price:.2f} is within stop bar's range (Low ${stop_bar['low']:.2f} - High ${stop_bar['high']:.2f})")
                print(f"  💡 Slippage likely due to:")
                print(f"     - Simulated stop slippage (0.2% in config)")
                print(f"     - Exiting at bar's low instead of stop price")
            else:
                print(f"  ❌ Exit price ${exit_price:.2f} is BELOW stop bar's low ${stop_bar['low']:.2f}")
                print(f"  💡 This indicates a price gap beyond the bar's range!")

        # Show bars between stop hit and exit
        if stop_hit_idx != exit_bar_idx:
            print(f"\n📊 Bars between stop hit and exit:")
            for idx in range(stop_hit_idx, min(exit_bar_idx + 1, stop_hit_idx + 5)):
                bar = bars[idx]
                bar_time = bar['date'].split('T')[1][:8]
                print(f"   [{idx}] {bar_time}: ${bar['low']:.2f} - ${bar['high']:.2f} (Close: ${bar['close']:.2f})")
    else:
        print(f"  ⚠️  Could not locate stop hit or exit bar in data")

    print(f"\n{'='*80}\n")

def main():
    """Analyze top losing trades from October 7, 2025"""

    print("\n🔍 STOP LOSS SLIPPAGE ANALYSIS - October 7, 2025")
    print("="*80)

    # Top losing trades with detailed information
    trades = [
        {
            'symbol': 'JPM',
            'side': 'SHORT',
            'entry_price': 304.67,
            'stop_price': 305.10,
            'exit_price': 305.88,
            'entry_time': '09:59:30',
            'exit_time': '10:04:00'
        },
        {
            'symbol': 'ARM',
            'side': 'LONG',
            'entry_price': 136.95,
            'stop_price': 136.64,
            'exit_price': 136.36,
            'entry_time': '12:24:55',
            'exit_time': '12:28:20'
        },
        {
            'symbol': 'AMZN',
            'side': 'SHORT',
            'entry_price': 219.22,
            'stop_price': 219.54,
            'exit_price': 219.94,
            'entry_time': '10:27:15',
            'exit_time': '10:28:30'
        },
        {
            'symbol': 'ROKU',
            'side': 'LONG',
            'entry_price': 69.56,
            'stop_price': 69.34,
            'exit_price': 69.04,
            'entry_time': '14:40:40',
            'exit_time': '14:44:05'
        }
    ]

    for trade in trades:
        analyze_stop_slippage(**trade)

    print("\n✅ Analysis complete\n")

if __name__ == '__main__':
    main()
