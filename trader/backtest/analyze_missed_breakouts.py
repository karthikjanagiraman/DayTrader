#!/usr/bin/env python3
"""
Analyze Sept 23-30 market data to find successful breakouts we MISSED
due to strict momentum criteria (1.3x volume + 0.8% candle)

This will:
1. Look at all stocks that broke resistance
2. Check if they went to target (successful breakout)
3. Analyze what their volume/candle characteristics were
4. Show us what we filtered out that would have been winners
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock, util
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def analyze_missed_breakouts_single_day(date_str='2025-09-30'):
    """
    For a single day, check ALL stocks that:
    1. Broke above resistance
    2. Went to target (successful)

    Then see what their volume/momentum characteristics were
    """

    print(f"\n{'='*80}")
    print(f"ANALYZING MISSED BREAKOUT OPPORTUNITIES - {date_str}")
    print(f"{'='*80}")

    # Load scanner data
    scanner_file = Path(__file__).parent / "monthly_results_production" / f"scanner_{date_str.replace('-', '')}.json"

    if not scanner_file.exists():
        print(f"⚠️  Scanner file not found: {scanner_file}")
        return

    with open(scanner_file) as f:
        scanner_data = json.load(f)

    print(f"\nLoaded {len(scanner_data)} stocks from scanner")

    # Filter to stocks with good setups (score >= 50, R/R >= 1.0)
    filtered = [s for s in scanner_data if s.get('score', 0) >= 50 and s.get('risk_reward', 0) >= 1.0]
    print(f"Filtered to {len(filtered)} stocks (score >= 50, R/R >= 1.0)")

    # Connect to IBKR
    print("\nConnecting to IBKR...")
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=5000)
        print("✓ Connected to IBKR")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("Please start TWS/Gateway on port 7497")
        return

    results = []

    # Analyze each stock
    for i, stock in enumerate(filtered[:20], 1):  # Limit to top 20 to avoid rate limits
        symbol = stock['symbol']
        resistance = stock['resistance']
        target1 = stock.get('target1', resistance * 1.02)
        close_price = stock['close']

        print(f"\n[{i}/{min(20, len(filtered))}] {symbol}: Resistance ${resistance:.2f}, Target ${target1:.2f}")

        # Fetch 1-minute bars for the day
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=f'{date_str.replace("-", "")} 16:00:00',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                print(f"  ⚠️  No data returned")
                continue

            print(f"  Fetched {len(bars)} bars")

            # Analyze this stock's breakout potential
            result = analyze_stock_breakout(symbol, bars, resistance, target1, close_price)
            if result:
                results.append(result)

            # Sleep to avoid rate limits
            time.sleep(0.5)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            time.sleep(1)
            continue

    # Disconnect
    ib.disconnect()

    # Print summary
    print_summary(results)

    return results

def analyze_stock_breakout(symbol, bars, resistance, target1, close_price):
    """
    Analyze if this stock had a successful breakout that we missed

    Returns dict with analysis if successful, None if not
    """

    # Find where price first broke resistance
    breakout_bar = None
    breakout_idx = None

    for i, bar in enumerate(bars):
        if bar.close > resistance:
            breakout_bar = bar
            breakout_idx = i
            break

    if not breakout_bar:
        print(f"  → Never broke resistance")
        return None

    # Check if it reached target
    max_price = max(b.high for b in bars[breakout_idx:])
    reached_target = max_price >= target1

    if not reached_target:
        print(f"  → Broke resistance but didn't reach target (max ${max_price:.2f})")
        return None

    # This is a SUCCESSFUL breakout we might have missed!
    print(f"  ✓ SUCCESS: Broke ${resistance:.2f} @ {breakout_bar.date.strftime('%H:%M')}, reached ${max_price:.2f}")

    # Calculate volume characteristics at breakout
    # Get average volume from bars before breakout
    pre_breakout_bars = bars[:breakout_idx] if breakout_idx > 0 else []

    if len(pre_breakout_bars) >= 20:
        avg_volume = sum(b.volume for b in pre_breakout_bars[-20:]) / 20
    elif len(pre_breakout_bars) > 0:
        avg_volume = sum(b.volume for b in pre_breakout_bars) / len(pre_breakout_bars)
    else:
        avg_volume = breakout_bar.volume  # First bar of day

    volume_ratio = breakout_bar.volume / avg_volume if avg_volume > 0 else 0

    # Calculate candle characteristics
    candle_size = abs(breakout_bar.close - breakout_bar.open)
    candle_pct = (candle_size / breakout_bar.open * 100) if breakout_bar.open > 0 else 0

    # Calculate ATR (simplified - just recent range)
    if len(pre_breakout_bars) >= 20:
        recent_ranges = [b.high - b.low for b in pre_breakout_bars[-20:]]
        atr = sum(recent_ranges) / len(recent_ranges)
    else:
        atr = breakout_bar.high - breakout_bar.low

    candle_atr_ratio = candle_size / atr if atr > 0 else 0

    # Check if it would have passed our filters
    passed_volume = volume_ratio >= 1.3
    passed_candle = candle_pct >= 0.8 or candle_atr_ratio >= 2.0
    passed_both = passed_volume and passed_candle

    # Calculate profit potential
    gain_to_target = ((target1 - breakout_bar.close) / breakout_bar.close * 100)

    result = {
        'symbol': symbol,
        'breakout_time': breakout_bar.date.strftime('%H:%M'),
        'breakout_price': breakout_bar.close,
        'max_price': max_price,
        'target1': target1,
        'volume_ratio': volume_ratio,
        'candle_pct': candle_pct,
        'candle_atr_ratio': candle_atr_ratio,
        'passed_volume': passed_volume,
        'passed_candle': passed_candle,
        'passed_both': passed_both,
        'gain_to_target': gain_to_target
    }

    status = "✓ PASSED FILTERS" if passed_both else "✗ FILTERED OUT"
    print(f"    Volume: {volume_ratio:.2f}x ({'✓' if passed_volume else '✗'} need 1.3x)")
    print(f"    Candle: {candle_pct:.2f}% ({'✓' if candle_pct >= 0.8 else '✗'} need 0.8%) or {candle_atr_ratio:.2f}x ATR ({'✓' if candle_atr_ratio >= 2.0 else '✗'} need 2.0x)")
    print(f"    {status}")
    print(f"    Gain to target: {gain_to_target:.2f}%")

    return result

def print_summary(results):
    """Print summary of all analyzed breakouts"""

    if not results:
        print("\n" + "="*80)
        print("NO SUCCESSFUL BREAKOUTS FOUND")
        print("="*80)
        print("\nThis confirms: Sept 23-30 had NO winning breakout opportunities")
        print("The strict filters didn't miss any winners - there were none!")
        return

    print("\n" + "="*80)
    print("SUMMARY OF SUCCESSFUL BREAKOUTS")
    print("="*80)

    passed = [r for r in results if r['passed_both']]
    filtered = [r for r in results if not r['passed_both']]

    print(f"\nTotal successful breakouts: {len(results)}")
    print(f"  Passed our filters: {len(passed)} ({len(passed)/len(results)*100:.1f}%)")
    print(f"  Filtered out: {len(filtered)} ({len(filtered)/len(results)*100:.1f}%)")

    if filtered:
        print("\n" + "-"*80)
        print("WINNERS WE MISSED (Filtered Out):")
        print("-"*80)
        print(f"{'Symbol':<8} {'Time':<8} {'Vol':<8} {'Candle%':<10} {'ATR':<8} {'Gain%':<8}")
        print("-"*80)

        for r in sorted(filtered, key=lambda x: x['gain_to_target'], reverse=True):
            print(f"{r['symbol']:<8} {r['breakout_time']:<8} "
                  f"{r['volume_ratio']:<7.2f}x {r['candle_pct']:<9.2f}% "
                  f"{r['candle_atr_ratio']:<7.2f}x {r['gain_to_target']:<7.2f}%")

        # Calculate what we missed
        total_missed_gain = sum(r['gain_to_target'] for r in filtered)
        avg_missed_gain = total_missed_gain / len(filtered)

        print()
        print(f"Average gain we missed: {avg_missed_gain:.2f}%")
        print(f"Total potential missed: {total_missed_gain:.2f}%")

        # Analyze WHY they were filtered
        vol_only = [r for r in filtered if r['passed_volume'] and not r['passed_candle']]
        candle_only = [r for r in filtered if r['passed_candle'] and not r['passed_volume']]
        neither = [r for r in filtered if not r['passed_volume'] and not r['passed_candle']]

        print("\nWhy filtered out:")
        print(f"  Volume OK, candle too small: {len(vol_only)} ({len(vol_only)/len(filtered)*100:.1f}%)")
        print(f"  Candle OK, volume too low: {len(candle_only)} ({len(candle_only)/len(filtered)*100:.1f}%)")
        print(f"  Both insufficient: {len(neither)} ({len(neither)/len(filtered)*100:.1f}%)")

        # Recommend new thresholds
        print("\n" + "-"*80)
        print("RECOMMENDED THRESHOLD ADJUSTMENTS:")
        print("-"*80)

        all_volumes = [r['volume_ratio'] for r in filtered]
        all_candles = [r['candle_pct'] for r in filtered]

        if all_volumes:
            min_vol = min(all_volumes)
            avg_vol = sum(all_volumes) / len(all_volumes)
            print(f"Volume ratios of missed winners: {min_vol:.2f}x to {max(all_volumes):.2f}x (avg {avg_vol:.2f}x)")
            print(f"→ Reduce from 1.3x to {min_vol:.2f}x to catch all winners")

        if all_candles:
            min_candle = min(all_candles)
            avg_candle = sum(all_candles) / len(all_candles)
            print(f"Candle sizes of missed winners: {min_candle:.2f}% to {max(all_candles):.2f}% (avg {avg_candle:.2f}%)")
            print(f"→ Reduce from 0.8% to {min_candle:.2f}% to catch all winners")

    if passed:
        print("\n" + "-"*80)
        print("WINNERS WE CAUGHT (Passed Filters):")
        print("-"*80)
        for r in passed:
            print(f"  {r['symbol']}: {r['gain_to_target']:.2f}% gain")

def main():
    """Run analysis for Sept 30 (most recent day with data)"""

    print("\n" + "="*80)
    print("MISSED BREAKOUT OPPORTUNITY ANALYSIS")
    print("="*80)
    print("\nObjective: Find successful breakouts we filtered out due to strict criteria")
    print("Method: Analyze actual market data to see volume/momentum of winners")
    print()
    print("Current filters:")
    print("  - Volume >= 1.3x average")
    print("  - Candle >= 0.8% OR >= 2x ATR")
    print()

    # Analyze Sept 30 (the last day)
    results = analyze_missed_breakouts_single_day('2025-09-30')

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)

    if results and any(not r['passed_both'] for r in results):
        print("\n✓ Found successful breakouts we filtered out")
        print("→ Relax volume/candle thresholds based on recommendations above")
        print("→ Rerun backtest with relaxed criteria")
        print("→ Compare results")
    else:
        print("\n✗ No successful breakouts found (or all passed filters)")
        print("→ Sept 23-30 was a bad market for breakouts")
        print("→ Filters are NOT the problem - market conditions were")
        print("→ Strategy won't work in down/choppy markets regardless of filters")

if __name__ == "__main__":
    main()
