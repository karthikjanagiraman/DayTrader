#!/usr/bin/env python3
"""
Analyze volume continuation for all failed trades from Sept 15, 2025 backtest.
Calculates volume ratios for entry candle + next 2 1-minute candles.

Author: Claude Code
Date: October 14, 2025
"""

import json
import os
from datetime import datetime, timedelta
import pytz

def parse_timestamp(timestamp_str):
    """Parse timestamp and convert to Eastern Time"""
    eastern = pytz.timezone('US/Eastern')

    # Handle both formats: with 'Z' and with timezone offset
    if timestamp_str.endswith('Z'):
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    else:
        dt = datetime.fromisoformat(timestamp_str)

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)

    # Convert to Eastern
    return dt.astimezone(eastern)

def load_5sec_bars(symbol, date="20250915"):
    """Load cached 5-second bars for a symbol"""
    file_path = f'/Users/karthik/projects/DayTrader/trader/backtest/data/{symbol}_{date}_5sec.json'

    if not os.path.exists(file_path):
        print(f"  ⚠️  No cached data for {symbol}")
        return None

    with open(file_path) as f:
        bars = json.load(f)

    return bars

def find_entry_bar_index(bars, entry_time):
    """Find the index of the bar containing the entry time"""
    for i, bar in enumerate(bars):
        # The cached data uses 'date' not 'timestamp'
        bar_time_str = bar['date']
        bar_time = datetime.fromisoformat(bar_time_str.replace('Z', '+00:00'))

        # The date field already includes timezone (-04:00)
        eastern = pytz.timezone('US/Eastern')
        bar_time_et = bar_time

        # Check if within same second (5-second bars)
        if abs((entry_time - bar_time_et).total_seconds()) < 5:
            return i

    return None

def calculate_candle_volume_ratio(bars, candle_start_idx, lookback_candles=20):
    """Calculate volume ratio for a 1-minute candle (12 five-second bars)"""

    # Get 12 bars for this candle (1 minute = 12 × 5 seconds)
    candle_end_idx = min(candle_start_idx + 12, len(bars))
    candle_bars = bars[candle_start_idx:candle_end_idx]

    if not candle_bars:
        return None, 0

    # Sum volume for this candle
    candle_volume = sum(bar['volume'] for bar in candle_bars)

    # Calculate average volume from previous candles
    # Look back 20 1-minute candles (240 five-second bars)
    lookback_start = max(0, candle_start_idx - (lookback_candles * 12))
    lookback_end = candle_start_idx

    if lookback_start >= lookback_end:
        return None, candle_volume

    lookback_bars = bars[lookback_start:lookback_end]

    if not lookback_bars:
        return None, candle_volume

    # Calculate average per 5-second bar
    avg_volume_per_bar = sum(bar['volume'] for bar in lookback_bars) / len(lookback_bars)

    # Scale to 1-minute candle (12 bars)
    avg_candle_volume = avg_volume_per_bar * 12

    if avg_candle_volume == 0:
        return None, candle_volume

    volume_ratio = candle_volume / avg_candle_volume

    return volume_ratio, candle_volume

def analyze_trade_volume(trade):
    """Analyze volume continuation for a single trade"""

    symbol = trade['symbol']
    entry_time = parse_timestamp(trade['entry_time'])

    # Load 5-second bars
    bars = load_5sec_bars(symbol)

    if not bars:
        return None

    # Find entry bar
    entry_bar_idx = find_entry_bar_index(bars, entry_time)

    if entry_bar_idx is None:
        print(f"  ⚠️  Could not find entry bar for {symbol} at {entry_time.strftime('%H:%M:%S ET')}")
        return None

    # Calculate candle boundaries
    # Entry candle starts at the beginning of the minute
    entry_candle_start = (entry_bar_idx // 12) * 12

    results = {
        'symbol': symbol,
        'entry_time': entry_time.strftime('%H:%M:%S ET'),
        'entry_price': trade['entry_price'],
        'exit_price': trade['exit_price'],
        'pnl': trade['pnl'],
        'reason': trade['reason'],
        'entry_reason': trade.get('entry_reason', 'Unknown'),
        'candles': []
    }

    # Analyze entry candle + next 2 candles
    for offset in range(3):
        candle_start = entry_candle_start + (offset * 12)

        if candle_start >= len(bars):
            results['candles'].append({
                'offset': offset,
                'volume_ratio': None,
                'volume': 0,
                'status': 'No data'
            })
            continue

        volume_ratio, volume = calculate_candle_volume_ratio(bars, candle_start)

        # Determine status
        if volume_ratio is None:
            status = 'Insufficient history'
        elif volume_ratio >= 2.0:
            status = '🟢 STRONG'
        elif volume_ratio >= 1.3:
            status = '🟡 MODERATE'
        else:
            status = '🔴 WEAK'

        results['candles'].append({
            'offset': offset,
            'volume_ratio': volume_ratio,
            'volume': volume,
            'status': status
        })

    return results

def check_delayed_momentum(entry_reason):
    """Check if entry was a delayed momentum entry"""
    if not entry_reason:
        return False

    entry_reason_lower = entry_reason.lower()

    # Check for delayed momentum indicators
    if 'delayed' in entry_reason_lower:
        return True

    # Check for candle number in reason (e.g., "on candle 30")
    if 'candle' in entry_reason_lower and any(str(i) in entry_reason for i in range(10, 200)):
        return True

    return False

def main():
    """Main analysis function"""

    print("="*100)
    print("📊 VOLUME CONTINUATION ANALYSIS - ALL FAILED TRADES")
    print("="*100)
    print()

    # Load trades
    trades_file = '/Users/karthik/projects/DayTrader/trader/backtest/results/backtest_trades_20250915.json'

    print(f"Loading trades from: {trades_file}")
    with open(trades_file) as f:
        trades = json.load(f)

    # Filter for failed trades (negative P&L)
    failed_trades = [t for t in trades if t['pnl'] < 0]

    print(f"Found {len(failed_trades)} failed trades")
    print()

    # Analyze each trade
    all_results = []

    for i, trade in enumerate(failed_trades, 1):
        print(f"Analyzing trade {i}/{len(failed_trades)}: {trade['symbol']}...")
        result = analyze_trade_volume(trade)

        if result:
            all_results.append(result)

    print()
    print("="*100)
    print("📊 DETAILED RESULTS - VOLUME CONTINUATION AFTER ENTRY")
    print("="*100)

    # Sort by P&L (worst first)
    all_results.sort(key=lambda x: x['pnl'])

    # Detailed table
    print()
    print(f"{'#':<4} {'Symbol':<8} {'Entry':<12} {'P&L':<10} {'Entry Vol':<15} {'+1min Vol':<15} {'+2min Vol':<15} {'Cont?':<8} {'Type':<10}")
    print("-"*130)

    volume_continued_count = 0
    no_continuation_count = 0
    delayed_momentum_count = 0
    delayed_with_continuation = 0
    delayed_without_continuation = 0

    for i, r in enumerate(all_results, 1):
        symbol = r['symbol']
        entry_time = r['entry_time']
        pnl = r['pnl']

        # Get volume ratios
        entry_vol = r['candles'][0]['volume_ratio'] if len(r['candles']) > 0 else None
        vol_1min = r['candles'][1]['volume_ratio'] if len(r['candles']) > 1 else None
        vol_2min = r['candles'][2]['volume_ratio'] if len(r['candles']) > 2 else None

        # Check continuation (at least one candle ≥1.3x)
        continuation = False
        if vol_1min and vol_1min >= 1.3:
            continuation = True
        elif vol_2min and vol_2min >= 1.3:
            continuation = True

        if continuation:
            volume_continued_count += 1
            cont_str = "✅ YES"
        else:
            no_continuation_count += 1
            cont_str = "❌ NO"

        # Check if delayed momentum
        is_delayed = check_delayed_momentum(r['entry_reason'])
        entry_type = "DELAYED" if is_delayed else "NORMAL"

        if is_delayed:
            delayed_momentum_count += 1
            if continuation:
                delayed_with_continuation += 1
            else:
                delayed_without_continuation += 1

        # Format values
        entry_str = f"{entry_vol:.2f}x" if entry_vol else "N/A"
        vol1_str = f"{vol_1min:.2f}x" if vol_1min else "N/A"
        vol2_str = f"{vol_2min:.2f}x" if vol_2min else "N/A"

        # Color code based on thresholds
        if entry_vol and entry_vol < 1.3:
            entry_str = f"🔴 {entry_str}"
        elif entry_vol and entry_vol >= 2.0:
            entry_str = f"🟢 {entry_str}"

        print(f"{i:<4} {symbol:<8} {entry_time:<12} ${pnl:<9.2f} {entry_str:<15} {vol1_str:<15} {vol2_str:<15} {cont_str:<8} {entry_type:<10}")

    # Summary statistics
    print()
    print("="*100)
    print("📊 SUMMARY STATISTICS")
    print("="*100)

    total_analyzed = len(all_results)

    print(f"\nTotal Failed Trades Analyzed: {total_analyzed}")
    print(f"Volume CONTINUED (≥1.3x in next 2 candles): {volume_continued_count} ({volume_continued_count/total_analyzed*100:.1f}%)")
    print(f"Volume did NOT continue: {no_continuation_count} ({no_continuation_count/total_analyzed*100:.1f}%)")

    # Entry volume analysis
    entry_volumes = [r['candles'][0]['volume_ratio'] for r in all_results if r['candles'][0]['volume_ratio'] is not None]

    if entry_volumes:
        avg_entry_volume = sum(entry_volumes) / len(entry_volumes)
        below_2x = sum(1 for v in entry_volumes if v < 2.0)
        below_13x = sum(1 for v in entry_volumes if v < 1.3)

        print(f"\n📈 Entry Bar Volume Analysis:")
        print(f"Average entry volume: {avg_entry_volume:.2f}x")
        print(f"Below 2.0x threshold: {below_2x}/{len(entry_volumes)} ({below_2x/len(entry_volumes)*100:.1f}%)")
        print(f"Below 1.3x threshold: {below_13x}/{len(entry_volumes)} ({below_13x/len(entry_volumes)*100:.1f}%)")

    # Volume decay analysis
    candle_1_volumes = [r['candles'][1]['volume_ratio'] for r in all_results if len(r['candles']) > 1 and r['candles'][1]['volume_ratio'] is not None]
    candle_2_volumes = [r['candles'][2]['volume_ratio'] for r in all_results if len(r['candles']) > 2 and r['candles'][2]['volume_ratio'] is not None]

    if candle_1_volumes:
        avg_1min_volume = sum(candle_1_volumes) / len(candle_1_volumes)
        print(f"\n📉 Volume Decay Pattern:")
        print(f"Entry candle: {avg_entry_volume:.2f}x")
        print(f"+1 minute: {avg_1min_volume:.2f}x ({(avg_1min_volume/avg_entry_volume-1)*100:+.1f}%)")

        if candle_2_volumes:
            avg_2min_volume = sum(candle_2_volumes) / len(candle_2_volumes)
            print(f"+2 minutes: {avg_2min_volume:.2f}x ({(avg_2min_volume/avg_entry_volume-1)*100:+.1f}%)")

    # Delayed momentum analysis
    print(f"\n⏰ Delayed Momentum Analysis:")
    print(f"Total delayed momentum entries: {delayed_momentum_count} ({delayed_momentum_count/total_analyzed*100:.1f}%)")

    if delayed_momentum_count > 0:
        print(f"Delayed WITH continuation: {delayed_with_continuation} ({delayed_with_continuation/delayed_momentum_count*100:.1f}%)")
        print(f"Delayed WITHOUT continuation: {delayed_without_continuation} ({delayed_without_continuation/delayed_momentum_count*100:.1f}%)")

    # Calculate delayed vs normal continuation rates
    normal_entries = total_analyzed - delayed_momentum_count
    normal_with_continuation = volume_continued_count - delayed_with_continuation

    if normal_entries > 0:
        print(f"\n📊 Continuation Rate Comparison:")
        print(f"Normal entries: {normal_with_continuation}/{normal_entries} = {normal_with_continuation/normal_entries*100:.1f}% continuation")

        if delayed_momentum_count > 0:
            print(f"Delayed entries: {delayed_with_continuation}/{delayed_momentum_count} = {delayed_with_continuation/delayed_momentum_count*100:.1f}% continuation")

    # Key findings
    print()
    print("="*100)
    print("🔍 KEY FINDINGS")
    print("="*100)

    continuation_rate = volume_continued_count / total_analyzed * 100

    if continuation_rate < 40:
        print(f"❌ CRITICAL: Only {continuation_rate:.1f}% of failed trades had volume continuation")
        print("   This suggests volume spikes are too brief to sustain momentum")

    if avg_entry_volume < 2.0:
        print(f"⚠️  WARNING: Average entry volume {avg_entry_volume:.2f}x is below 2.0x threshold")
        print("   Many entries happen with insufficient volume confirmation")

    if delayed_momentum_count > total_analyzed * 0.3:
        print(f"⚠️  ISSUE: {delayed_momentum_count/total_analyzed*100:.1f}% of trades are delayed momentum")
        print("   These entries miss the initial volume spike")

    # Save results
    output_file = '/Users/karthik/projects/DayTrader/trader/backtest/failed_trades_volume_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n💾 Detailed results saved to: {output_file}")

if __name__ == '__main__':
    main()