#!/usr/bin/env python3
"""
COMPREHENSIVE BREAKOUT ANALYSIS - Sept 23-30, 2025
Analyzes ALL stocks (both longs and shorts) to find:
1. Stocks that broke resistance/support
2. Which ones reached targets (successful)
3. Their volume/momentum characteristics
4. What we missed vs what we correctly filtered
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock
import time
import pandas as pd

def analyze_comprehensive(start_day=23, end_day=30):
    """Analyze all days comprehensively"""

    print("\n" + "="*80)
    print("COMPREHENSIVE BREAKOUT ANALYSIS - Sept 23-30, 2025")
    print("="*80)
    print("\nObjective: Check EVERY stock that broke resistance/support")
    print("For each, determine:")
    print("  1. Did it reach target? (SUCCESS)")
    print("  2. What were volume/candle characteristics?")
    print("  3. Would our filters have caught it?")
    print("  4. Did we miss any winners?")

    # Connect to IBKR
    print("\nConnecting to IBKR...")
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=5003)
        print("✓ Connected\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    all_results = []

    # Analyze each day
    for day in range(start_day, end_day + 1):
        if day == 27 or day == 28:  # Weekend
            continue

        date_str = f"2025-09-{day:02d}"

        print("\n" + "="*80)
        print(f"ANALYZING {date_str}")
        print("="*80)

        results = analyze_single_day(ib, date_str)
        all_results.extend(results)

        # Summary for this day
        if results:
            successful = [r for r in results if r['reached_target']]
            filtered_out = [r for r in results if not r['passed_filters'] and r['reached_target']]

            print(f"\n{date_str} Summary:")
            print(f"  Total breakouts: {len(results)}")
            print(f"  Successful (reached target): {len(successful)}")
            print(f"  Missed winners (filtered out): {len(filtered_out)}")

    ib.disconnect()

    # Generate comprehensive report
    generate_report(all_results)

    return all_results

def analyze_single_day(ib, date_str):
    """Analyze all stocks for a single day"""

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

    print(f"Scanner stocks (score >= 50, R/R >= 1.0): {len(filtered)}")

    results = []

    # Analyze each stock
    for i, stock in enumerate(filtered, 1):
        symbol = stock['symbol']
        resistance = stock['resistance']
        support = stock['support']
        target1 = stock.get('target1', resistance * 1.02)
        downside1 = stock.get('downside1', support * 0.98)

        print(f"\n[{i}/{len(filtered)}] {symbol}:")
        print(f"  Long: R=${resistance:.2f} → T=${target1:.2f}")
        print(f"  Short: S=${support:.2f} → T=${downside1:.2f}")

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

            # Rate limit
            time.sleep(0.6)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            time.sleep(1)
            continue

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

    # Print result
    status = "✓ SUCCESS" if reached_target else "✗ FAILED"
    filter_status = "✓ PASSED" if passed_filters else "✗ FILTERED"

    print(f"  {side}: {status} ({filter_status})")
    print(f"    Volume: {vol_ratio:.2f}x, Candle: {candle_pct:.2f}%, ATR: {candle_atr_ratio:.2f}x")
    print(f"    Best gain: {best_gain:.2f}%")

    # Determine outcome
    if reached_target and passed_filters:
        outcome = "CAUGHT_WINNER"
    elif reached_target and not passed_filters:
        outcome = "MISSED_WINNER"
    elif not reached_target and passed_filters:
        outcome = "FALSE_POSITIVE"
    else:
        outcome = "CORRECTLY_FILTERED"

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

def generate_report(results):
    """Generate comprehensive report"""

    if not results:
        print("\n" + "="*80)
        print("NO BREAKOUTS FOUND")
        print("="*80)
        return

    print("\n" + "="*80)
    print("COMPREHENSIVE ANALYSIS REPORT")
    print("="*80)

    df = pd.DataFrame(results)

    # Overall stats
    total = len(results)
    successful = len(df[df['reached_target']])
    failed = total - successful

    print(f"\nTotal breakouts analyzed: {total}")
    print(f"  Reached target (successful): {successful} ({successful/total*100:.1f}%)")
    print(f"  Failed to reach target: {failed} ({failed/total*100:.1f}%)")

    # By side
    longs = df[df['side'] == 'LONG']
    shorts = df[df['side'] == 'SHORT']

    print(f"\nBy direction:")
    print(f"  LONG breakouts: {len(longs)}")
    print(f"    Successful: {len(longs[longs['reached_target']])} ({len(longs[longs['reached_target']])/len(longs)*100:.1f}%)")
    print(f"  SHORT breakdowns: {len(shorts)}")
    print(f"    Successful: {len(shorts[shorts['reached_target']])} ({len(shorts[shorts['reached_target']])/len(shorts)*100:.1f}%)")

    # Outcome breakdown
    print("\n" + "-"*80)
    print("OUTCOME BREAKDOWN:")
    print("-"*80)

    for outcome in ['CAUGHT_WINNER', 'MISSED_WINNER', 'FALSE_POSITIVE', 'CORRECTLY_FILTERED']:
        count = len(df[df['outcome'] == outcome])
        pct = count / total * 100

        if outcome == 'CAUGHT_WINNER':
            desc = "✓ Winners we CAUGHT (passed filters & reached target)"
        elif outcome == 'MISSED_WINNER':
            desc = "⚠️  Winners we MISSED (filtered out but reached target)"
        elif outcome == 'FALSE_POSITIVE':
            desc = "✗ False positives (passed filters but failed)"
        else:
            desc = "✓ Correctly filtered (failed to reach target)"

        print(f"\n{desc}")
        print(f"  Count: {count} ({pct:.1f}%)")

        if count > 0 and outcome in ['CAUGHT_WINNER', 'MISSED_WINNER']:
            subset = df[df['outcome'] == outcome]
            avg_gain = subset['best_gain'].mean()
            total_gain = subset['best_gain'].sum()
            print(f"  Average gain: {avg_gain:.2f}%")
            print(f"  Total potential: {total_gain:.2f}%")

            # Show top 5
            if len(subset) > 0:
                print(f"\n  Top trades:")
                top = subset.nlargest(5, 'best_gain')
                for _, row in top.iterrows():
                    print(f"    {row['symbol']} ({row['side']}): {row['best_gain']:.2f}% gain "
                          f"(Vol: {row['vol_ratio']:.2f}x, Candle: {row['candle_pct']:.2f}%)")

    # MISSED WINNERS analysis
    missed = df[df['outcome'] == 'MISSED_WINNER']

    if len(missed) > 0:
        print("\n" + "="*80)
        print("DETAILED ANALYSIS: MISSED WINNERS")
        print("="*80)

        print(f"\nWe missed {len(missed)} winning trades worth {missed['best_gain'].sum():.2f}% potential")

        # Why were they filtered?
        vol_fail = len(missed[~missed['passed_vol']])
        candle_fail = len(missed[~missed['passed_candle']])

        print(f"\nWhy filtered out:")
        print(f"  Volume too low: {vol_fail} ({vol_fail/len(missed)*100:.1f}%)")
        print(f"  Candle too small: {candle_fail} ({candle_fail/len(missed)*100:.1f}%)")

        # Threshold recommendations
        print("\n" + "-"*80)
        print("RECOMMENDED THRESHOLD ADJUSTMENTS:")
        print("-"*80)

        min_vol = missed['vol_ratio'].min()
        avg_vol = missed['vol_ratio'].mean()
        print(f"Volume of missed winners: {min_vol:.2f}x to {missed['vol_ratio'].max():.2f}x (avg {avg_vol:.2f}x)")
        print(f"→ Current threshold: 1.3x")
        print(f"→ To catch all: reduce to {min_vol:.2f}x")
        print(f"→ To catch 80%: reduce to {missed['vol_ratio'].quantile(0.2):.2f}x")

        min_candle = missed['candle_pct'].min()
        avg_candle = missed['candle_pct'].mean()
        print(f"\nCandle size of missed winners: {min_candle:.2f}% to {missed['candle_pct'].max():.2f}% (avg {avg_candle:.2f}%)")
        print(f"→ Current threshold: 0.8%")
        print(f"→ To catch all: reduce to {min_candle:.2f}%")
        print(f"→ To catch 80%: reduce to {missed['candle_pct'].quantile(0.2):.2f}%")

        # Show all missed winners
        print("\n" + "-"*80)
        print("ALL MISSED WINNERS:")
        print("-"*80)
        print(f"{'Date':<12} {'Symbol':<8} {'Side':<6} {'Vol':<8} {'Candle%':<10} {'ATR':<8} {'Gain%':<8}")
        print("-"*80)

        for _, row in missed.sort_values('best_gain', ascending=False).iterrows():
            vol_mark = '✓' if row['passed_vol'] else '✗'
            candle_mark = '✓' if row['passed_candle'] else '✗'
            print(f"{row['date']:<12} {row['symbol']:<8} {row['side']:<6} "
                  f"{vol_mark} {row['vol_ratio']:<6.2f}x {candle_mark} {row['candle_pct']:<8.2f}% "
                  f"{row['candle_atr_ratio']:<6.2f}x {row['best_gain']:<7.2f}%")

    # Save to CSV
    output_file = Path(__file__).parent / "comprehensive_breakout_analysis.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Full data saved to: {output_file}")

    # Final recommendation
    print("\n" + "="*80)
    print("FINAL RECOMMENDATION")
    print("="*80)

    if len(missed) == 0:
        print("\n✓ NO MISSED WINNERS")
        print("  → Current filters are PERFECT for this market")
        print("  → We didn't miss any successful breakouts")
        print("  → Keep current thresholds (1.3x vol, 0.8% candle)")
    else:
        total_missed_gain = missed['best_gain'].sum()
        avg_missed_gain = missed['best_gain'].mean()

        print(f"\n⚠️  MISSED {len(missed)} WINNERS (Total: {total_missed_gain:.2f}%, Avg: {avg_missed_gain:.2f}%)")

        if avg_missed_gain < 1.0:
            print("  → But average gain is very small (<1%)")
            print("  → Not worth relaxing filters for such small wins")
            print("  → Keep current thresholds")
        elif len(missed) < 5:
            print("  → Only a few winners missed")
            print("  → Consider slight relaxation if profitable")
        else:
            print("  → Significant number of winners missed")
            print("  → Consider relaxing thresholds based on recommendations above")

if __name__ == "__main__":
    analyze_comprehensive(start_day=23, end_day=30)
