#!/usr/bin/env python3
"""
Analyze a SINGLE day comprehensively
Much faster - avoids rate limits
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock
import time
import pandas as pd

def analyze_single_day(date_str='2025-09-30'):
    """Analyze all stocks for a single day"""

    print("\n" + "="*80)
    print(f"COMPREHENSIVE ANALYSIS - {date_str}")
    print("="*80)

    # Load scanner
    scanner_file = Path(__file__).parent / "monthly_results_production" / f"scanner_{date_str.replace('-', '')}.json"

    if not scanner_file.exists():
        print(f"⚠️  Scanner file not found")
        return []

    with open(scanner_file) as f:
        scanner_data = json.load(f)

    # Filter to tradeable stocks
    filtered = [s for s in scanner_data
                if s.get('score', 0) >= 50 and s.get('risk_reward', 0) >= 1.0]

    print(f"\nScanner stocks (score >= 50, R/R >= 1.0): {len(filtered)}")

    # Connect to IBKR
    print("Connecting to IBKR...")
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=5010)
        print("✓ Connected\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return []

    results = []

    # Analyze each stock
    for i, stock in enumerate(filtered, 1):
        symbol = stock['symbol']
        resistance = stock['resistance']
        support = stock['support']
        target1 = stock.get('target1', resistance * 1.02)
        downside1 = stock.get('downside1', support * 0.98)

        print(f"[{i}/{len(filtered)}] {symbol}")

        # Fetch data
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

            if not bars or len(bars) < 10:
                print(f"  ⚠️  Insufficient data")
                time.sleep(0.5)
                continue

            # Check LONG breakout
            long_result = analyze_direction(
                symbol, bars, resistance, target1,
                side='LONG', date=date_str
            )
            if long_result:
                results.append(long_result)

            # Check SHORT breakdown
            short_result = analyze_direction(
                symbol, bars, support, downside1,
                side='SHORT', date=date_str
            )
            if short_result:
                results.append(short_result)

            # Rate limit - small delay
            time.sleep(0.5)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            time.sleep(1)
            continue

    ib.disconnect()

    # Generate report
    generate_report(results, date_str)

    return results

def analyze_direction(symbol, bars, pivot, target, side='LONG', date=''):
    """Analyze a single direction (long or short)"""

    # Find breakout
    breakout_idx = None
    breakout_bar = None

    for i, bar in enumerate(bars):
        if side == 'LONG' and bar.close > pivot:
            breakout_idx = i
            breakout_bar = bar
            break
        elif side == 'SHORT' and bar.close < pivot:
            breakout_idx = i
            breakout_bar = bar
            break

    if not breakout_bar:
        return None

    # Calculate characteristics
    pre_bars = bars[:breakout_idx] if breakout_idx > 0 else []

    # Volume ratio
    if len(pre_bars) >= 20:
        avg_vol = sum(b.volume for b in pre_bars[-20:]) / 20
    elif len(pre_bars) > 0:
        avg_vol = sum(b.volume for b in pre_bars) / len(pre_bars)
    else:
        avg_vol = breakout_bar.volume

    vol_ratio = breakout_bar.volume / avg_vol if avg_vol > 0 else 0

    # Candle characteristics
    candle_size = abs(breakout_bar.close - breakout_bar.open)
    candle_pct = (candle_size / breakout_bar.open * 100) if breakout_bar.open > 0 else 0

    # ATR
    if len(pre_bars) >= 20:
        atr = sum(b.high - b.low for b in pre_bars[-20:]) / 20
    else:
        atr = breakout_bar.high - breakout_bar.low if breakout_bar else 0.01

    candle_atr_ratio = candle_size / atr if atr > 0 else 0

    # Check filters
    passed_vol = vol_ratio >= 1.3
    passed_candle = candle_pct >= 0.8 or candle_atr_ratio >= 2.0
    passed_filters = passed_vol and passed_candle

    # Check if reached target
    future_bars = bars[breakout_idx:]

    if side == 'LONG':
        max_price = max(b.high for b in future_bars)
        reached_target = max_price >= target
        best_gain = ((max_price - breakout_bar.close) / breakout_bar.close * 100)
    else:
        min_price = min(b.low for b in future_bars)
        reached_target = min_price <= target
        best_gain = ((breakout_bar.close - min_price) / breakout_bar.close * 100)

    # Determine outcome
    if reached_target and passed_filters:
        outcome = "CAUGHT_WINNER"
        symbol_out = "✓"
    elif reached_target and not passed_filters:
        outcome = "MISSED_WINNER"
        symbol_out = "⚠️"
    elif not reached_target and passed_filters:
        outcome = "FALSE_POSITIVE"
        symbol_out = "✗"
    else:
        outcome = "CORRECTLY_FILTERED"
        symbol_out = "-"

    print(f"  {side}: {symbol_out} {outcome[:15]:<15} Vol:{vol_ratio:>5.2f}x Candle:{candle_pct:>5.2f}% Gain:{best_gain:>5.2f}%")

    return {
        'date': date,
        'symbol': symbol,
        'side': side,
        'pivot': pivot,
        'target': target,
        'breakout_price': breakout_bar.close,
        'breakout_time': breakout_bar.date.strftime('%H:%M'),
        'vol_ratio': vol_ratio,
        'candle_pct': candle_pct,
        'candle_atr_ratio': candle_atr_ratio,
        'passed_vol': passed_vol,
        'passed_candle': passed_candle,
        'passed_filters': passed_filters,
        'reached_target': reached_target,
        'best_gain': best_gain,
        'outcome': outcome
    }

def generate_report(results, date_str):
    """Generate report for single day"""

    print("\n" + "="*80)
    print(f"REPORT - {date_str}")
    print("="*80)

    if not results:
        print("\n✓ NO BREAKOUTS - All stocks stayed within range")
        return

    df = pd.DataFrame(results)

    # Overall stats
    total = len(results)
    successful = len(df[df['reached_target']])

    print(f"\nTotal breakouts: {total}")
    print(f"  Reached target: {successful} ({successful/total*100:.1f}%)")
    print(f"  Failed: {total - successful} ({(total - successful)/total*100:.1f}%)")

    # By side
    longs = df[df['side'] == 'LONG']
    shorts = df[df['side'] == 'SHORT']

    print(f"\nBy direction:")
    print(f"  LONG: {len(longs)} breakouts, {len(longs[longs['reached_target']])} successful ({len(longs[longs['reached_target']])/len(longs)*100:.1f}%)")
    print(f"  SHORT: {len(shorts)} breakouts, {len(shorts[shorts['reached_target']])} successful ({len(shorts[shorts['reached_target']])/len(shorts)*100:.1f}%)")

    # Outcome breakdown
    print("\n" + "-"*80)
    print("OUTCOMES:")
    print("-"*80)

    for outcome in ['CAUGHT_WINNER', 'MISSED_WINNER', 'FALSE_POSITIVE', 'CORRECTLY_FILTERED']:
        count = len(df[df['outcome'] == outcome])

        if outcome == 'CAUGHT_WINNER':
            desc = "✓ Winners CAUGHT (passed & reached target)"
        elif outcome == 'MISSED_WINNER':
            desc = "⚠️  Winners MISSED (filtered but reached target)"
        elif outcome == 'FALSE_POSITIVE':
            desc = "✗ False positives (passed but failed)"
        else:
            desc = "✓ Correctly filtered (rejected & failed)"

        print(f"{desc:<50} {count:>3} ({count/total*100:>5.1f}%)")

    # MISSED WINNERS
    missed = df[df['outcome'] == 'MISSED_WINNER']

    if len(missed) > 0:
        print("\n" + "="*80)
        print(f"⚠️  MISSED {len(missed)} WINNERS!")
        print("="*80)

        total_gain = missed['best_gain'].sum()
        avg_gain = missed['best_gain'].mean()

        print(f"\nTotal missed gains: {total_gain:.2f}%")
        print(f"Average gain: {avg_gain:.2f}%")

        print("\n" + "-"*80)
        print("ALL MISSED WINNERS:")
        print("-"*80)
        print(f"{'Symbol':<8} {'Side':<6} {'Vol':<8} {'Candle%':<10} {'ATR':<8} {'Gain%':<8}")
        print("-"*80)

        for _, row in missed.sort_values('best_gain', ascending=False).iterrows():
            vol_mark = '✓' if row['passed_vol'] else '✗'
            candle_mark = '✓' if row['passed_candle'] else '✗'
            print(f"{row['symbol']:<8} {row['side']:<6} {vol_mark} {row['vol_ratio']:<6.2f}x "
                  f"{candle_mark} {row['candle_pct']:<8.2f}% {row['candle_atr_ratio']:<6.2f}x "
                  f"{row['best_gain']:<7.2f}%")

        # Recommendations
        print("\n" + "-"*80)
        print("THRESHOLD RECOMMENDATIONS:")
        print("-"*80)

        min_vol = missed['vol_ratio'].min()
        min_candle = missed['candle_pct'].min()

        print(f"To catch ALL missed winners:")
        print(f"  Volume: 1.3x → {min_vol:.2f}x")
        print(f"  Candle: 0.8% → {min_candle:.2f}%")

    else:
        print("\n" + "="*80)
        print("✓ NO MISSED WINNERS!")
        print("="*80)
        print("\nFilters are working perfectly - didn't miss any successful breakouts")

    # Save
    output_file = Path(__file__).parent / f"analysis_{date_str.replace('-', '')}.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Data saved: {output_file}")

if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else '2025-09-30'
    analyze_single_day(date)
