#!/usr/bin/env python3
"""
DEEP VERIFICATION: Volume Continuation Analysis Using IBKR 1-Minute Bars

This script:
1. Connects to IBKR API
2. Fetches clean 1-minute bars for each failed trade
3. Calculates volume ratios using 1-minute data (not aggregated 5-second bars)
4. Verifies the volume continuation findings from scratch
5. Cross-checks against log entries to understand delayed momentum

Author: Claude Code
Date: October 14, 2025
"""

import json
import sys
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util
import pytz

# Add parent directory to path
sys.path.append('/Users/karthik/projects/DayTrader/trader')

def parse_timestamp(timestamp_str):
    """Parse timestamp from trade JSON and convert to Eastern Time"""
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

def fetch_1min_bars(ib, symbol, entry_time_et, bars_before=5, bars_after=5):
    """
    Fetch 1-minute bars around entry time from IBKR

    Args:
        ib: IB connection
        symbol: Stock symbol
        entry_time_et: Entry time in Eastern timezone
        bars_before: Number of 1-min bars before entry
        bars_after: Number of 1-min bars after entry

    Returns:
        List of 1-minute bars
    """
    contract = Stock(symbol, 'SMART', 'USD')

    # Request bars ending at entry_time + bars_after minutes
    end_time = entry_time_et + timedelta(minutes=bars_after)

    # Total duration in seconds for IBKR API
    total_minutes = bars_before + bars_after
    duration_str = f"{total_minutes * 60} S"  # Convert to seconds

    # Format: YYYYMMDD HH:MM:SS (no timezone suffix, just use the datetime)
    # IBKR expects the time in the exchange timezone
    end_datetime_str = end_time.strftime('%Y%m%d %H:%M:%S')

    try:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime=end_datetime_str,
            durationStr=duration_str,
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1
        )

        return bars
    except Exception as e:
        print(f"    ❌ Error fetching {symbol}: {e}")
        return []

def calculate_volume_ratio(bars, bar_index, lookback_bars=20):
    """
    Calculate volume ratio for a specific bar

    Args:
        bars: List of 1-minute bars
        bar_index: Index of bar to calculate ratio for
        lookback_bars: Number of bars to use for average (default 20)

    Returns:
        Volume ratio (current volume / average volume)
    """
    if bar_index < lookback_bars:
        # Not enough history, use what we have
        lookback_bars = bar_index

    if lookback_bars == 0:
        return None

    # Calculate average volume from lookback period
    avg_volume = sum(bars[i].volume for i in range(bar_index - lookback_bars, bar_index)) / lookback_bars

    if avg_volume == 0:
        return None

    # Current bar volume
    current_volume = bars[bar_index].volume

    return current_volume / avg_volume

def find_entry_bar_index(bars, entry_time_et):
    """Find the index of the 1-minute bar that contains the entry time"""
    # Make entry_time timezone-naive for comparison
    entry_naive = entry_time_et.replace(tzinfo=None)

    for i, bar in enumerate(bars):
        # IBKR bar.date might be timezone-aware or naive
        bar_start = bar.date
        if hasattr(bar_start, 'tzinfo') and bar_start.tzinfo is not None:
            # Bar is timezone-aware, make it naive
            bar_start = bar_start.replace(tzinfo=None)

        bar_end = bar_start + timedelta(minutes=1)

        # Check if entry_time falls within this bar
        # Allow 5-second tolerance for entry times (since we use 5-second bars in backtest)
        if (bar_start <= entry_naive < bar_end) or \
           (abs((entry_naive - bar_start).total_seconds()) <= 5):
            return i

    return None

def format_time_et(dt):
    """Format datetime in Eastern Time"""
    if dt.tzinfo is None:
        return dt.strftime('%H:%M:%S')
    return dt.astimezone(pytz.timezone('US/Eastern')).strftime('%H:%M:%S ET')

def analyze_trade_volume(ib, trade):
    """
    Analyze volume continuation for a single trade

    Returns:
        Dictionary with analysis results
    """
    symbol = trade['symbol']
    entry_time_et = parse_timestamp(trade['entry_time'])
    exit_time_et = parse_timestamp(trade['exit_time'])

    print(f"\n{'='*100}")
    print(f"📊 {symbol} {trade['side']} - P&L: ${trade['pnl']:.2f}")
    print(f"{'='*100}")
    print(f"Entry: {format_time_et(entry_time_et)} @ ${trade['entry_price']:.2f}")
    print(f"Exit:  {format_time_et(exit_time_et)} @ ${trade['exit_price']:.2f}")
    print(f"Duration: {trade['duration_min']:.1f} minutes")
    print(f"Reason: {trade['reason']}")

    # Fetch 1-minute bars (5 before entry, 5 after)
    print(f"\n🔍 Fetching 1-minute bars from IBKR...")
    bars = fetch_1min_bars(ib, symbol, entry_time_et, bars_before=25, bars_after=10)

    if not bars:
        print(f"❌ No bars fetched for {symbol}")
        return None

    print(f"✅ Fetched {len(bars)} bars from IBKR")

    # Find entry bar
    entry_bar_idx = find_entry_bar_index(bars, entry_time_et)

    if entry_bar_idx is None:
        print(f"❌ Could not find entry bar for {format_time_et(entry_time_et)}")
        # Show available bars
        print(f"\nAvailable bars:")
        for i, bar in enumerate(bars[-10:]):
            print(f"  [{len(bars)-10+i}] {bar.date} - Vol: {bar.volume:,}")
        return None

    print(f"\n✅ Entry bar found at index {entry_bar_idx}")
    print(f"   Bar time: {bars[entry_bar_idx].date}")
    print(f"   Entry time: {entry_time_et.replace(tzinfo=None)}")

    # Calculate volume ratios
    print(f"\n📈 VOLUME ANALYSIS:")
    print(f"{'='*100}")

    results = {
        'symbol': symbol,
        'entry_time': format_time_et(entry_time_et),
        'pnl': trade['pnl'],
        'bars': []
    }

    # Analyze entry bar and next 2 bars
    for offset in [0, 1, 2]:
        bar_idx = entry_bar_idx + offset

        if bar_idx >= len(bars):
            print(f"   [{offset:+2d} min] ⚠️  No data available")
            continue

        bar = bars[bar_idx]
        volume_ratio = calculate_volume_ratio(bars, bar_idx, lookback_bars=20)

        # Bar details
        bar_label = "ENTRY" if offset == 0 else f"+{offset}min"

        print(f"\n   [{bar_label:>6}] {bar.date.strftime('%H:%M:%S')}")
        print(f"            Volume: {bar.volume:>10,} shares")

        if volume_ratio is not None:
            print(f"            Ratio:  {volume_ratio:>10.2f}x")

            # Color code based on thresholds
            if volume_ratio >= 2.0:
                verdict = "🟢 STRONG (≥2.0x)"
            elif volume_ratio >= 1.3:
                verdict = "🟡 MODERATE (≥1.3x)"
            else:
                verdict = "🔴 WEAK (<1.3x)"

            print(f"            {verdict}")
        else:
            print(f"            Ratio:  ⚠️  Insufficient history")

        results['bars'].append({
            'offset': offset,
            'time': bar.date.strftime('%H:%M:%S'),
            'volume': bar.volume,
            'ratio': volume_ratio
        })

    # Calculate volume continuation verdict
    entry_ratio = results['bars'][0]['ratio'] if results['bars'] else None
    next_ratios = [b['ratio'] for b in results['bars'][1:3] if b['ratio'] is not None]

    print(f"\n{'='*100}")
    print(f"📊 VOLUME CONTINUATION ANALYSIS:")
    print(f"{'='*100}")

    if entry_ratio is not None:
        print(f"Entry bar volume: {entry_ratio:.2f}x")

        if entry_ratio >= 2.0:
            print(f"✅ Entry bar meets MOMENTUM threshold (≥2.0x)")
        else:
            print(f"❌ Entry bar BELOW momentum threshold ({entry_ratio:.2f}x < 2.0x)")
            print(f"   ⚠️  This suggests a DELAYED MOMENTUM entry")

    if next_ratios:
        avg_next = sum(next_ratios) / len(next_ratios)
        print(f"\nNext 2 bars average: {avg_next:.2f}x")

        continuation = any(r >= 1.3 for r in next_ratios)
        if continuation:
            print(f"✅ Volume CONTINUED (at least one bar ≥1.3x)")
            results['continuation'] = True
        else:
            print(f"❌ Volume did NOT continue (all bars <1.3x)")
            results['continuation'] = False
    else:
        print(f"⚠️  Insufficient data to assess continuation")
        results['continuation'] = None

    # Show 20-bar lookback for context
    print(f"\n📊 20-BAR LOOKBACK CONTEXT (for entry bar calculation):")
    print(f"{'='*100}")
    if entry_bar_idx >= 20:
        lookback_start = entry_bar_idx - 20
        lookback_end = entry_bar_idx

        lookback_volumes = [bars[i].volume for i in range(lookback_start, lookback_end)]
        avg_lookback = sum(lookback_volumes) / len(lookback_volumes)

        print(f"Average volume (20 bars before entry): {avg_lookback:,.0f} shares")
        print(f"Entry bar volume: {bars[entry_bar_idx].volume:,} shares")

        if entry_ratio is not None:
            print(f"Calculated ratio: {bars[entry_bar_idx].volume:,} / {avg_lookback:,.0f} = {entry_ratio:.2f}x ✅")

    return results

def main():
    """Main verification script"""

    print("="*100)
    print("🔬 DEEP VERIFICATION: Volume Continuation Analysis Using IBKR 1-Minute Bars")
    print("="*100)
    print()
    print("This script will:")
    print("1. Load failed trades from Sept 15, 2025 backtest")
    print("2. Connect to IBKR API")
    print("3. Fetch clean 1-minute bars for each trade")
    print("4. Calculate volume ratios from scratch")
    print("5. Verify volume continuation findings")
    print()

    # Load trades
    trades_file = '/Users/karthik/projects/DayTrader/trader/backtest/results/backtest_trades_20250915.json'

    print(f"📂 Loading trades from: {trades_file}")
    with open(trades_file) as f:
        trades = json.load(f)

    # Filter for 7MIN_RULE losers
    failed_trades = [t for t in trades if t['reason'] == '7MIN_RULE' and t['pnl'] < 0]

    # Sort by worst losses and take top 10
    failed_trades_sorted = sorted(failed_trades, key=lambda x: x['pnl'])[:10]

    print(f"✅ Found {len(failed_trades)} total 7MIN_RULE losers")
    print(f"📊 Analyzing top 10 worst losses")
    print()

    # Connect to IBKR
    print("🔌 Connecting to IBKR...")
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=9999)
        print("✅ Connected to IBKR")
    except Exception as e:
        print(f"❌ Failed to connect to IBKR: {e}")
        print("⚠️  Make sure TWS/Gateway is running on port 7497")
        return

    print()

    # Analyze each trade
    all_results = []

    for i, trade in enumerate(failed_trades_sorted, 1):
        print(f"\n{'#'*100}")
        print(f"# TRADE {i}/10")
        print(f"{'#'*100}")

        result = analyze_trade_volume(ib, trade)

        if result:
            all_results.append(result)

        # Pace requests to avoid IBKR rate limits
        if i < len(failed_trades_sorted):
            print(f"\n⏳ Waiting 2 seconds before next request (IBKR rate limit)...")
            ib.sleep(2)

    # Disconnect
    print(f"\n{'='*100}")
    print("🔌 Disconnecting from IBKR...")
    ib.disconnect()
    print("✅ Disconnected")

    # Summary analysis
    print(f"\n{'='*100}")
    print("📊 SUMMARY ANALYSIS - TOP 10 WORST 7MIN_RULE LOSERS")
    print(f"{'='*100}")

    if all_results:
        # Count continuation
        continued_count = sum(1 for r in all_results if r.get('continuation') == True)
        not_continued_count = sum(1 for r in all_results if r.get('continuation') == False)

        print(f"\nTotal trades analyzed: {len(all_results)}")
        print(f"Volume CONTINUED: {continued_count} ({continued_count/len(all_results)*100:.1f}%)")
        print(f"Volume did NOT continue: {not_continued_count} ({not_continued_count/len(all_results)*100:.1f}%)")

        # Check entry bar volume ratios
        entry_ratios = [r['bars'][0]['ratio'] for r in all_results if r['bars'] and r['bars'][0]['ratio'] is not None]

        if entry_ratios:
            avg_entry_ratio = sum(entry_ratios) / len(entry_ratios)
            below_threshold = sum(1 for r in entry_ratios if r < 2.0)

            print(f"\n📈 Entry Bar Volume Analysis:")
            print(f"Average entry bar volume: {avg_entry_ratio:.2f}x")
            print(f"Below 2.0x threshold: {below_threshold}/{len(entry_ratios)} ({below_threshold/len(entry_ratios)*100:.1f}%)")

        # Detailed table
        print(f"\n{'='*100}")
        print(f"DETAILED RESULTS TABLE:")
        print(f"{'='*100}")
        print(f"{'Rank':<6} {'Symbol':<8} {'P&L':<12} {'Entry Vol':<12} {'+1min Vol':<12} {'+2min Vol':<12} {'Cont?':<8}")
        print(f"{'-'*100}")

        for i, r in enumerate(all_results, 1):
            symbol = r['symbol']
            pnl = r['pnl']

            entry_vol = r['bars'][0]['ratio'] if r['bars'] and r['bars'][0]['ratio'] else None
            vol_1min = r['bars'][1]['ratio'] if len(r['bars']) > 1 and r['bars'][1]['ratio'] else None
            vol_2min = r['bars'][2]['ratio'] if len(r['bars']) > 2 and r['bars'][2]['ratio'] else None

            cont = r.get('continuation')
            cont_str = "✅ YES" if cont else "❌ NO" if cont is False else "⚠️  N/A"

            entry_str = f"{entry_vol:.2f}x" if entry_vol else "N/A"
            vol1_str = f"{vol_1min:.2f}x" if vol_1min else "N/A"
            vol2_str = f"{vol_2min:.2f}x" if vol_2min else "N/A"

            print(f"{i:<6} {symbol:<8} ${pnl:<11.2f} {entry_str:<12} {vol1_str:<12} {vol2_str:<12} {cont_str:<8}")

    print(f"\n{'='*100}")
    print("✅ VERIFICATION COMPLETE")
    print(f"{'='*100}")

    # Save results
    output_file = '/Users/karthik/projects/DayTrader/trader/backtest/volume_verification_ibkr.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")

if __name__ == '__main__':
    main()
