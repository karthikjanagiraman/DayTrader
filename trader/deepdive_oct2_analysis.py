#!/usr/bin/env python3
"""
Deep-dive analysis of October 2nd trades
Examine what happened after stops, premature exits, and market conditions
"""

import json
import pandas as pd
from datetime import datetime

def load_market_data(symbol):
    """Load 5-second bar data"""
    with open(f'backtest/data/{symbol}_20251002_5sec.json', 'r') as f:
        return json.load(f)

def load_scanner_data():
    """Load scanner predictions"""
    with open('../stockscanner/output/scanner_results_20251002.json', 'r') as f:
        return json.load(f)

def analyze_post_stop_action(bars, entry_idx, stop_price, side='LONG'):
    """Analyze what happened after stop was hit"""
    # Find when stop was hit
    stop_idx = None
    for i in range(entry_idx, len(bars)):
        if side == 'LONG' and bars[i]['low'] <= stop_price:
            stop_idx = i
            break

    if stop_idx is None:
        return None

    # Look at next 30 minutes (360 bars @ 5sec) after stop
    lookback_end = min(stop_idx + 360, len(bars))
    post_stop_bars = bars[stop_idx:lookback_end]

    # Find high and low after stop
    post_highs = [b['high'] for b in post_stop_bars]
    post_lows = [b['low'] for b in post_stop_bars]

    max_after_stop = max(post_highs) if post_highs else stop_price
    min_after_stop = min(post_lows) if post_lows else stop_price

    # Calculate what we missed
    if side == 'LONG':
        potential_gain = max_after_stop - stop_price
        potential_gain_pct = (potential_gain / stop_price) * 100
    else:
        potential_gain = stop_price - min_after_stop
        potential_gain_pct = (potential_gain / stop_price) * 100

    return {
        'stop_time': bars[stop_idx]['date'],
        'stop_price': stop_price,
        'max_after_stop': max_after_stop,
        'min_after_stop': min_after_stop,
        'potential_gain': potential_gain,
        'potential_gain_pct': potential_gain_pct,
        'would_have_hit_target': potential_gain_pct > 1.0  # >1% gain
    }

def find_entry_bar(bars, entry_time, entry_price):
    """Find the bar where entry occurred"""
    for i, bar in enumerate(bars):
        time_str = bar['date'].split('T')[1][:5]  # Get HH:MM
        entry_time_str = entry_time.split(':')[0] + ':' + entry_time.split(':')[1]
        if time_str == entry_time_str and abs(bar['close'] - entry_price) < 0.5:
            return i
    return None

def get_market_context(bars, idx):
    """Get market conditions at entry time"""
    if idx < 12:  # Not enough data
        return "Market open (insufficient data)"

    # Look at previous 1 minute (12 bars @ 5sec)
    prev_bars = bars[max(0, idx-12):idx]

    # Calculate trend
    closes = [b['close'] for b in prev_bars]
    trend = "UP" if closes[-1] > closes[0] else "DOWN" if closes[-1] < closes[0] else "FLAT"

    # Calculate volatility
    ranges = [(b['high'] - b['low']) / b['close'] * 100 for b in prev_bars]
    avg_range = sum(ranges) / len(ranges)
    volatility = "HIGH" if avg_range > 0.05 else "MODERATE" if avg_range > 0.02 else "LOW"

    # Volume trend
    volumes = [b['volume'] for b in prev_bars]
    avg_volume = sum(volumes) / len(volumes)
    current_volume = bars[idx]['volume']
    volume_status = "SURGING" if current_volume > avg_volume * 1.5 else "NORMAL" if current_volume > avg_volume * 0.8 else "DECLINING"

    return f"{trend} trend, {volatility} volatility, {volume_status} volume"

def analyze_stock(symbol, scanner_data):
    """Deep-dive analysis of a stock's trades"""

    bars = load_market_data(symbol)
    stock = next((s for s in scanner_data if s['symbol'] == symbol), None)

    if not stock:
        return None

    resistance = stock['resistance']
    support = stock['support']
    target1 = stock['target1']

    print(f"\n{'='*80}")
    print(f"{symbol} DEEP-DIVE ANALYSIS")
    print(f"{'='*80}")
    print(f"Scanner: Resistance ${resistance:.2f}, Target1 ${target1:.2f}, Score {stock['score']}, R/R {stock['risk_reward']:.2f}")
    print(f"Previous Close: ${stock['close']:.2f}")
    print(f"Opening Price: ${bars[0]['open']:.2f} (Gap: {((bars[0]['open'] - stock['close'])/stock['close']*100):.2f}%)")
    print()

    # Find all breakout attempts
    trade_num = 0
    prev_attempt_idx = -100

    for i, bar in enumerate(bars):
        # Check if this is a breakout (max 2 attempts)
        if bar['high'] > resistance and i > prev_attempt_idx + 12:  # 1 min gap between attempts
            trade_num += 1
            if trade_num > 2:
                break

            prev_attempt_idx = i

            entry_price = max(bar['open'], resistance + 0.01)
            if bar['close'] > resistance:
                entry_price = bar['close']

            entry_time = bar['date']
            stop_price = resistance

            # Find exit
            exit_bar = None
            exit_reason = None
            partial_taken = False
            partial_price = None

            # Check for partial (1R gain = entry - stop)
            risk = entry_price - stop_price
            partial_target = entry_price + risk

            for j in range(i, len(bars)):
                # Check partial
                if not partial_taken and bars[j]['high'] >= partial_target:
                    partial_taken = True
                    partial_price = partial_target
                    # Update stop to breakeven
                    stop_price = entry_price

                # Check stop
                if bars[j]['low'] <= stop_price:
                    exit_bar = j
                    exit_reason = "STOP" if not partial_taken else "TRAIL_STOP"
                    break

            if exit_bar is None:
                exit_bar = len(bars) - 1
                exit_reason = "EOD"

            exit_price = stop_price if exit_reason in ["STOP", "TRAIL_STOP"] else bars[exit_bar]['close']
            exit_time = bars[exit_bar]['date']

            # Calculate P&L
            if partial_taken:
                pnl = (partial_price - entry_price) * 500 + (exit_price - entry_price) * 500
            else:
                pnl = (exit_price - entry_price) * 1000

            duration_bars = exit_bar - i
            duration_min = duration_bars * 5 / 60

            # Market context at entry
            context = get_market_context(bars, i)

            # Post-stop analysis
            post_stop = analyze_post_stop_action(bars, i, stop_price, 'LONG')

            print(f"TRADE #{trade_num}:")
            print(f"  Entry: ${entry_price:.2f} @ {entry_time.split('T')[1][:8]}")
            print(f"  Market Context: {context}")
            print(f"  Initial Stop: ${stop_price:.2f} ({((entry_price - stop_price)/entry_price*100):.2f}% risk)")

            if partial_taken:
                print(f"  Partial: 50% @ ${partial_price:.2f} (+${partial_price - entry_price:.2f})")
                print(f"  Stop moved to breakeven: ${entry_price:.2f}")

            print(f"  Exit: ${exit_price:.2f} @ {exit_time.split('T')[1][:8]} ({exit_reason})")
            print(f"  Duration: {duration_min:.1f} minutes")
            print(f"  P&L: ${pnl:+.2f} ({((exit_price - entry_price)/entry_price*100):+.2f}%)")

            if post_stop:
                print(f"\n  POST-STOP ANALYSIS (next 30 min):")
                print(f"    Stop hit: ${post_stop['stop_price']:.2f} @ {post_stop['stop_time'].split('T')[1][:8]}")
                print(f"    High after stop: ${post_stop['max_after_stop']:.2f}")
                print(f"    Potential gain if held: ${post_stop['potential_gain']:+.2f} ({post_stop['potential_gain_pct']:+.2f}%)")

                if post_stop['would_have_hit_target']:
                    print(f"    ⚠️  PREMATURE EXIT: Stock gained {post_stop['potential_gain_pct']:.1f}% after stop!")
                else:
                    print(f"    ✓ Stop was correct: Stock didn't recover meaningfully")

            print()

    # Overall stock performance
    day_high = max(b['high'] for b in bars)
    day_low = min(b['low'] for b in bars)
    eod_close = bars[-1]['close']

    print(f"DAY SUMMARY:")
    print(f"  High: ${day_high:.2f} ({((day_high - resistance)/resistance*100):.2f}% above resistance)")
    print(f"  Low: ${day_low:.2f}")
    print(f"  Close: ${eod_close:.2f}")

    # Did it hit target1?
    if day_high >= target1:
        print(f"  ✓ Target1 ${target1:.2f} WAS HIT (+{((target1 - resistance)/resistance*100):.1f}%)")
        # When did it hit?
        for i, bar in enumerate(bars):
            if bar['high'] >= target1:
                print(f"    Hit at {bar['date'].split('T')[1][:8]}")
                break
    else:
        print(f"  ✗ Target1 ${target1:.2f} NOT HIT (max {((day_high - resistance)/resistance*100):.1f}% above resistance)")

    print()

def main():
    traded_symbols = ['MU', 'ROKU', 'ARM', 'JD', 'F', 'LCID', 'PLTR', 'INTC']
    scanner_data = load_scanner_data()

    print("="*80)
    print("OCTOBER 2ND DEEP-DIVE TRADE ANALYSIS")
    print("Examining: Entry timing, market conditions, post-stop action, premature exits")
    print("="*80)

    premature_exits = []
    correct_stops = []

    for symbol in traded_symbols:
        analyze_stock(symbol, scanner_data)

    print("\n" + "="*80)
    print("KEY FINDINGS SUMMARY")
    print("="*80)

if __name__ == "__main__":
    main()
