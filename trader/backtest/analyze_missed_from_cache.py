#!/usr/bin/env python3
"""
Analyze cached 5-second bar data to find missed breakout opportunities
Uses data already downloaded during Sept 23-30 backtest
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def analyze_day_from_cache(date_str='2025-09-30'):
    """Analyze a single day using cached bar data"""

    print(f"\n{'='*80}")
    print(f"ANALYZING MISSED BREAKOUTS - {date_str} (from cache)")
    print(f"{'='*80}")

    # Load scanner data
    scanner_file = Path(__file__).parent / "monthly_results_production" / f"scanner_{date_str.replace('-', '')}.json"

    if not scanner_file.exists():
        print(f"⚠️  Scanner file not found")
        return []

    with open(scanner_file) as f:
        scanner_data = json.load(f)

    # Filter stocks
    filtered = [s for s in scanner_data
                if s.get('score', 0) >= 50 and s.get('risk_reward', 0) >= 1.0]

    print(f"Scanner stocks (score >= 50, R/R >= 1.0): {len(filtered)}")

    # Look for cached bar files
    cache_pattern = f"*_{date_str.replace('-', '')}_5sec.json"
    cache_dir = Path(__file__).parent.parent / "backtest"

    # Find all cache files
    cache_files = list(cache_dir.glob(cache_pattern))
    print(f"Found {len(cache_files)} cached bar files")

    if not cache_files:
        print("⚠️  No cached bar data found. Run backtest first to generate cache.")
        return []

    results = []

    for cache_file in cache_files:
        # Extract symbol from filename (e.g., "TSLA_20250930_5sec.json")
        symbol = cache_file.stem.split('_')[0]

        # Find this symbol in scanner data
        stock = next((s for s in filtered if s['symbol'] == symbol), None)
        if not stock:
            continue

        resistance = stock['resistance']
        target1 = stock.get('target1', resistance * 1.02)

        # Load bars
        with open(cache_file) as f:
            bars_data = json.load(f)

        if not bars_data:
            continue

        # Convert to simple bar objects
        class Bar:
            def __init__(self, d):
                self.open = d['open']
                self.high = d['high']
                self.low = d['low']
                self.close = d['close']
                self.volume = d['volume']
                self.date = d['date']

        bars = [Bar(b) for b in bars_data]

        # Analyze breakout
        result = analyze_breakout(symbol, bars, resistance, target1)
        if result:
            results.append(result)

    return results

def analyze_breakout(symbol, bars, resistance, target1):
    """Check if stock had successful breakout and analyze characteristics"""

    # Find breakout
    breakout_idx = None
    for i, bar in enumerate(bars):
        if bar.close > resistance:
            breakout_idx = i
            break

    if breakout_idx is None:
        return None

    breakout_bar = bars[breakout_idx]

    # Check if reached target
    max_price = max(b.high for b in bars[breakout_idx:])
    if max_price < target1:
        return None  # Didn't reach target

    # Calculate volume ratio
    pre_bars = bars[:breakout_idx] if breakout_idx > 0 else []
    if len(pre_bars) >= 20:
        avg_vol = sum(b.volume for b in pre_bars[-20:]) / 20
    elif len(pre_bars) > 0:
        avg_vol = sum(b.volume for b in pre_bars) / len(pre_bars)
    else:
        avg_vol = breakout_bar.volume

    vol_ratio = breakout_bar.volume / avg_vol if avg_vol > 0 else 0

    # Calculate candle size
    candle_size = abs(breakout_bar.close - breakout_bar.open)
    candle_pct = (candle_size / breakout_bar.open * 100) if breakout_bar.open > 0 else 0

    # Calculate ATR
    if len(pre_bars) >= 20:
        atr = sum(b.high - b.low for b in pre_bars[-20:]) / 20
    else:
        atr = breakout_bar.high - breakout_bar.low

    candle_atr = candle_size / atr if atr > 0 else 0

    # Check filters
    passed_vol = vol_ratio >= 1.3
    passed_candle = candle_pct >= 0.8 or candle_atr >= 2.0
    passed_both = passed_vol and passed_candle

    gain_pct = ((target1 - breakout_bar.close) / breakout_bar.close * 100)

    return {
        'symbol': symbol,
        'breakout_price': breakout_bar.close,
        'max_price': max_price,
        'target': target1,
        'vol_ratio': vol_ratio,
        'candle_pct': candle_pct,
        'candle_atr': candle_atr,
        'passed_vol': passed_vol,
        'passed_candle': passed_candle,
        'passed_both': passed_both,
        'gain_pct': gain_pct
    }

def print_results(results):
    """Print analysis results"""

    if not results:
        print("\n" + "="*80)
        print("NO SUCCESSFUL BREAKOUTS FOUND")
        print("="*80)
        print("\nConclusion: Sept 23-30 had NO winning breakout opportunities")
        print("The strict filters didn't cause us to miss winners - there were NONE!")
        print("\nThis confirms the market was DOWN/CHOPPY with no momentum moves.")
        return

    print("\n" + "="*80)
    print(f"FOUND {len(results)} SUCCESSFUL BREAKOUTS")
    print("="*80)

    passed = [r for r in results if r['passed_both']]
    filtered = [r for r in results if not r['passed_both']]

    print(f"\nPassed our filters: {len(passed)}")
    print(f"Filtered out: {len(filtered)} ⚠️  MISSED WINNERS")

    if filtered:
        print("\n" + "-"*80)
        print("WINNERS WE MISSED:")
        print("-"*80)
        print(f"{'Symbol':<8} {'Price':<10} {'Target':<10} {'Vol':<8} {'Candle%':<10} {'ATR':<8} {'Gain%':<8}")
        print("-"*80)

        for r in sorted(filtered, key=lambda x: x['gain_pct'], reverse=True):
            vol_mark = '✓' if r['passed_vol'] else '✗'
            candle_mark = '✓' if r['passed_candle'] else '✗'

            print(f"{r['symbol']:<8} ${r['breakout_price']:<9.2f} ${r['target']:<9.2f} "
                  f"{vol_mark} {r['vol_ratio']:<6.2f}x {candle_mark} {r['candle_pct']:<8.2f}% "
                  f"{r['candle_atr']:<6.2f}x {r['gain_pct']:<7.2f}%")

        # Stats
        avg_gain = sum(r['gain_pct'] for r in filtered) / len(filtered)
        total_gain = sum(r['gain_pct'] for r in filtered)

        print()
        print(f"Average missed gain: {avg_gain:.2f}%")
        print(f"Total missed gains: {total_gain:.2f}%")

        # Why filtered
        vol_fail = sum(1 for r in filtered if not r['passed_vol'])
        candle_fail = sum(1 for r in filtered if not r['passed_candle'])

        print(f"\nReasons filtered:")
        print(f"  Volume too low (<1.3x): {vol_fail}/{len(filtered)}")
        print(f"  Candle too small (<0.8% or <2xATR): {candle_fail}/{len(filtered)}")

        # Recommendations
        min_vol = min(r['vol_ratio'] for r in filtered)
        min_candle = min(r['candle_pct'] for r in filtered)

        print("\n" + "-"*80)
        print("RECOMMENDED ADJUSTMENTS:")
        print("-"*80)
        print(f"Volume threshold: 1.3x → {min_vol:.2f}x (to catch smallest winner)")
        print(f"Candle threshold: 0.8% → {min_candle:.2f}% (to catch smallest winner)")

    if passed:
        print("\n" + "-"*80)
        print("WINNERS WE CAUGHT:")
        print("-"*80)
        for r in passed:
            print(f"  {r['symbol']}: {r['gain_pct']:.2f}% gain ✓")

def analyze_all_days():
    """Analyze all cached days"""

    print("\n" + "="*80)
    print("MISSED BREAKOUT ANALYSIS - Sept 23-30")
    print("="*80)
    print("\nAnalyzing cached bar data from backtest runs...")

    all_results = []

    for day in [23, 24, 25, 26, 29, 30]:
        date_str = f"2025-09-{day:02d}"
        results = analyze_day_from_cache(date_str)
        all_results.extend(results)

    print("\n" + "="*80)
    print("COMBINED RESULTS (Sept 23-30)")
    print("="*80)

    print_results(all_results)

if __name__ == "__main__":
    analyze_all_days()
