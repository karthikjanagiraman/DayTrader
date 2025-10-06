#!/usr/bin/env python3
"""
Detailed Trade-by-Trade Analysis for October 2nd Retest Strategy Backtest

Analyzes each of the 17 trades to understand:
1. Why the setup triggered (retest confirmation logic)
2. Market context at entry
3. What happened after entry
4. Why the stop was hit
5. What happened after the stop
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import namedtuple

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def load_bars(symbol, date_str='20251002'):
    """Load 5-second bars for a symbol"""
    cache_file = Path(f'backtest/data/{symbol}_{date_str}_5sec.json')
    if not cache_file.exists():
        return None

    with open(cache_file) as f:
        bars_data = json.load(f)

    Bar = namedtuple('Bar', ['date', 'open', 'high', 'low', 'close', 'volume', 'average', 'barCount'])
    bars = [Bar(**b) for b in bars_data]
    return bars

def find_bar_by_time(bars, target_time_str):
    """Find bar closest to target time"""
    target_time = datetime.fromisoformat(target_time_str.replace(' ', 'T'))

    best_idx = 0
    min_diff = float('inf')

    for i, bar in enumerate(bars):
        bar_time = datetime.fromisoformat(bar.date)
        diff = abs((bar_time - target_time).total_seconds())
        if diff < min_diff:
            min_diff = diff
            best_idx = i

    return best_idx, bars[best_idx]

def analyze_price_action(bars, entry_idx, resistance, stop_price):
    """Analyze price action around entry"""
    # Pre-entry context (100 bars = ~8 minutes before)
    pre_entry_start = max(0, entry_idx - 100)
    pre_entry_bars = bars[pre_entry_start:entry_idx]

    # Post-entry (next 300 bars = ~25 minutes)
    post_entry_bars = bars[entry_idx:min(entry_idx + 300, len(bars))]

    # Find highest high and lowest low pre-entry
    if pre_entry_bars:
        pre_high = max(b.high for b in pre_entry_bars)
        pre_low = min(b.low for b in pre_entry_bars)
    else:
        pre_high = pre_low = bars[entry_idx].close

    # Check if price went above entry before hitting stop
    went_profitable = False
    max_gain = 0
    max_gain_price = 0
    bars_before_stop = 0

    entry_price = bars[entry_idx].close

    for i, bar in enumerate(post_entry_bars):
        if bar.high > entry_price:
            went_profitable = True
            gain = ((bar.high - entry_price) / entry_price) * 100
            if gain > max_gain:
                max_gain = gain
                max_gain_price = bar.high

        # Check if stop hit
        if bar.low <= stop_price:
            bars_before_stop = i
            break

    # Check what happened after stop
    if bars_before_stop < len(post_entry_bars):
        after_stop_bars = post_entry_bars[bars_before_stop:]
        if after_stop_bars:
            # Find highest price reached after stop
            max_after_stop = max(b.high for b in after_stop_bars)
            recovery_pct = ((max_after_stop - stop_price) / stop_price) * 100
        else:
            max_after_stop = stop_price
            recovery_pct = 0
    else:
        max_after_stop = 0
        recovery_pct = 0

    # Count retests of resistance before entry
    retest_count = 0
    for bar in pre_entry_bars:
        if abs(bar.high - resistance) / resistance < 0.002:  # Within 0.2%
            retest_count += 1

    return {
        'pre_high': pre_high,
        'pre_low': pre_low,
        'resistance_tests': retest_count,
        'went_profitable': went_profitable,
        'max_gain_pct': max_gain,
        'max_gain_price': max_gain_price,
        'bars_to_stop': bars_before_stop,
        'time_to_stop_sec': bars_before_stop * 5,
        'max_after_stop': max_after_stop,
        'recovery_pct': recovery_pct
    }

def check_retest_pattern(bars, entry_idx, resistance):
    """Check if this was a valid retest pattern"""
    # Look back 60 bars (5 minutes)
    lookback = min(60, entry_idx)
    lookback_bars = bars[entry_idx - lookback:entry_idx]

    broke_above = False
    pulled_back = False
    break_idx = None
    pullback_idx = None

    for i, bar in enumerate(lookback_bars):
        if bar.close > resistance and not broke_above:
            broke_above = True
            break_idx = i
        elif broke_above and bar.close < resistance:
            pulled_back = True
            pullback_idx = i
            break

    return {
        'was_retest': broke_above and pulled_back,
        'break_idx': break_idx,
        'pullback_idx': pullback_idx
    }

def analyze_trade(trade_num, symbol, entry_time, entry_price, stop_price, exit_price, resistance, support):
    """Detailed analysis of a single trade"""
    print(f"\n{'='*100}")
    print(f"TRADE #{trade_num}: {symbol} LONG")
    print(f"{'='*100}")

    # Load bars
    bars = load_bars(symbol)
    if not bars:
        print(f"❌ No data available for {symbol}")
        return

    # Find entry bar
    entry_idx, entry_bar = find_bar_by_time(bars, entry_time)

    print(f"\n📍 ENTRY CONTEXT:")
    print(f"   Time: {entry_time}")
    print(f"   Entry Price: ${entry_price:.2f}")
    print(f"   Resistance: ${resistance:.2f}")
    print(f"   Move Above Resistance: {((entry_price - resistance) / resistance) * 100:.2f}%")
    print(f"   Stop: ${stop_price:.2f} (buffer: {((resistance - stop_price) / resistance) * 100:.2f}%)")
    print(f"   Risk per share: ${entry_price - stop_price:.2f}")

    # Check retest pattern
    retest_info = check_retest_pattern(bars, entry_idx, resistance)
    if retest_info['was_retest']:
        print(f"\n✅ RETEST PATTERN CONFIRMED:")
        print(f"   Initial break: ~{retest_info['break_idx']} bars before entry")
        print(f"   Pullback: ~{retest_info['pullback_idx']} bars before entry")
    else:
        print(f"\n⚠️  NO CLEAR RETEST PATTERN")
        print(f"   Entry appears to be on initial break or weak setup")

    # Analyze price action
    action = analyze_price_action(bars, entry_idx, resistance, stop_price)

    print(f"\n📊 PRE-ENTRY CONTEXT (8 min before):")
    print(f"   High: ${action['pre_high']:.2f}")
    print(f"   Low: ${action['pre_low']:.2f}")
    print(f"   Range: {((action['pre_high'] - action['pre_low']) / action['pre_low']) * 100:.2f}%")
    print(f"   Resistance Tests: {action['resistance_tests']} times")

    print(f"\n📈 POST-ENTRY PERFORMANCE:")
    if action['went_profitable']:
        print(f"   ✅ Went profitable: YES")
        print(f"   Max gain: +{action['max_gain_pct']:.2f}% (${action['max_gain_price']:.2f})")
        print(f"   Could have taken: ${(action['max_gain_price'] - entry_price) * 1000:.2f} profit on 1000 shares")
    else:
        print(f"   ❌ Went profitable: NO (never above entry)")

    print(f"\n🛑 STOP HIT:")
    print(f"   Time to stop: {action['bars_to_stop']} bars ({action['time_to_stop_sec']} seconds = {action['time_to_stop_sec']/60:.1f} min)")
    print(f"   Exit Price: ${exit_price:.2f}")
    print(f"   Loss: ${(exit_price - entry_price) * 1000:.2f} on 1000 shares")

    print(f"\n🔄 AFTER STOP:")
    if action['recovery_pct'] > 0.5:
        print(f"   ⚠️  PREMATURE STOP - Stock recovered!")
        print(f"   Max price after stop: ${action['max_after_stop']:.2f}")
        print(f"   Recovery: +{action['recovery_pct']:.2f}% from stop")
        print(f"   Missed gain: ${(action['max_after_stop'] - entry_price) * 1000:.2f} on 1000 shares")
    else:
        print(f"   ✅ Stop was correct - no significant recovery")
        print(f"   Max price after stop: ${action['max_after_stop']:.2f} (+{action['recovery_pct']:.2f}%)")

    # Market context
    print(f"\n🌐 MARKET CONTEXT:")
    # Check overall trend
    first_50_bars = bars[max(0, entry_idx-50):entry_idx]
    if first_50_bars:
        trend_start = first_50_bars[0].close
        trend_end = first_50_bars[-1].close
        trend_pct = ((trend_end - trend_start) / trend_start) * 100

        if trend_pct > 0.5:
            print(f"   Trend: UPTREND (+{trend_pct:.2f}% in 5 min before entry)")
        elif trend_pct < -0.5:
            print(f"   Trend: DOWNTREND ({trend_pct:.2f}% in 5 min before entry)")
        else:
            print(f"   Trend: SIDEWAYS ({trend_pct:+.2f}% in 5 min before entry)")

    # Volume analysis
    if entry_idx > 10:
        recent_volume = sum(b.volume for b in bars[entry_idx-10:entry_idx]) / 10
        entry_volume = entry_bar.volume
        vol_ratio = entry_volume / recent_volume if recent_volume > 0 else 0
        print(f"   Volume: {vol_ratio:.2f}x recent average")

    print(f"\n💡 VERDICT:")

    # Determine failure reason
    if not retest_info['was_retest']:
        print(f"   ❌ WEAK SETUP - Not a clean retest pattern")

    if action['bars_to_stop'] < 12:  # Less than 1 minute
        print(f"   ❌ IMMEDIATE WHIPSAW - Stopped in {action['time_to_stop_sec']} seconds")

    if action['went_profitable'] and action['max_gain_pct'] > 0.3:
        print(f"   ⚠️  PARTIAL PROFIT OPPORTUNITY MISSED - Went +{action['max_gain_pct']:.2f}%")

    if action['recovery_pct'] > 2:
        print(f"   ❌ PREMATURE EXIT - Recovered {action['recovery_pct']:.2f}% after stop")
        print(f"   💡 LESSON: Stop too tight or entry too early")

    if action['resistance_tests'] < 3:
        print(f"   ⚠️  WEAK RESISTANCE - Only tested {action['resistance_tests']} times")

    return action

def main():
    """Analyze all trades from October 2nd backtest"""

    # Load trade results
    trades_file = Path('backtest/monthly_results/all_trades_202510.json')
    if not trades_file.exists():
        print("❌ Trade results file not found")
        return

    with open(trades_file) as f:
        all_trades = json.load(f)

    # Load scanner data for resistance/support
    scanner_file = Path('backtest/monthly_results_production/scanner_20251002.json')
    with open(scanner_file) as f:
        scanner_data = json.load(f)

    # Create lookup
    scanner_lookup = {s['symbol']: s for s in scanner_data}

    print("="*100)
    print("OCTOBER 2ND RETEST STRATEGY - DETAILED TRADE ANALYSIS")
    print("="*100)
    print(f"\nAnalyzing {len(all_trades)} trades...")

    # Track statistics
    premature_stops = []
    weak_setups = []
    immediate_whipsaws = []

    for i, trade in enumerate(all_trades, 1):
        symbol = trade['symbol']

        if symbol not in scanner_lookup:
            print(f"\n❌ {symbol} not found in scanner data")
            continue

        scanner = scanner_lookup[symbol]

        # Entry time already includes full timestamp
        entry_time = trade['entry_time']

        action = analyze_trade(
            i,
            symbol,
            entry_time,
            trade['entry_price'],
            trade.get('stop_price', scanner['resistance']),
            trade['exit_price'],
            scanner['resistance'],
            scanner['support']
        )

        if action:
            # Categorize failures
            if action['recovery_pct'] > 2:
                premature_stops.append((symbol, action['recovery_pct']))

            if action['bars_to_stop'] < 12:
                immediate_whipsaws.append((symbol, action['time_to_stop_sec']))

    # Summary
    print(f"\n\n{'='*100}")
    print("SUMMARY OF FAILURES")
    print(f"{'='*100}")

    print(f"\n❌ PREMATURE STOPS ({len(premature_stops)} trades):")
    print("   These stops were hit but stock recovered significantly after")
    for symbol, recovery in sorted(premature_stops, key=lambda x: x[1], reverse=True):
        print(f"   {symbol}: Recovered +{recovery:.2f}% after stop")

    print(f"\n⚡ IMMEDIATE WHIPSAWS ({len(immediate_whipsaws)} trades):")
    print("   Stopped out within 1 minute of entry")
    for symbol, time_sec in sorted(immediate_whipsaws, key=lambda x: x[1]):
        print(f"   {symbol}: Stopped in {time_sec} seconds")

    print(f"\n💡 KEY LESSONS:")
    print(f"   1. {len(premature_stops)}/{len(all_trades)} stops were premature ({len(premature_stops)/len(all_trades)*100:.1f}%)")
    print(f"   2. {len(immediate_whipsaws)}/{len(all_trades)} were immediate whipsaws ({len(immediate_whipsaws)/len(all_trades)*100:.1f}%)")
    print(f"   3. Retest strategy is working but stops may be too tight")
    print(f"   4. Consider requiring stronger confirmation or wider stops")

if __name__ == '__main__':
    main()
