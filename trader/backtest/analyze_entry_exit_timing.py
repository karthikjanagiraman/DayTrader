#!/usr/bin/env python3
"""
Comprehensive analysis of entry/exit timing for Sept 23-30 trades
Examines price action before and after each trade entry
"""

import json
import sys
from datetime import datetime, timedelta
from ib_insync import IB, Stock
import pytz

# Load trades
with open('monthly_results/all_trades_202509.json') as f:
    trades = json.load(f)

print("=" * 100, flush=True)
print("COMPREHENSIVE ENTRY/EXIT TIMING ANALYSIS: Sept 23-30, 2025", flush=True)
print("=" * 100, flush=True)
print(f"\nAnalyzing {len(trades)} trades...\n", flush=True)
print("Loading historical bar data for each trade to analyze price action before/after entry...\n", flush=True)

# Connect to IBKR
ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=4000)
    print("✓ Connected to IBKR\n")
except:
    print("❌ Failed to connect to IBKR - cannot fetch historical data")
    sys.exit(1)

# Analysis results
analysis_results = []

for i, trade in enumerate(trades, 1):
    symbol = trade['symbol']
    entry_time_str = trade['entry_time']
    entry_price = trade['entry_price']
    exit_price = trade['exit_price']
    side = trade['side']
    pnl = trade['pnl']
    reason = trade['reason']

    # Parse entry time
    try:
        # Handle different timezone formats
        if 'Z' in entry_time_str:
            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
        else:
            entry_time = datetime.fromisoformat(entry_time_str)

        if entry_time.tzinfo is None:
            entry_time = pytz.UTC.localize(entry_time)
        else:
            entry_time = entry_time.astimezone(pytz.UTC)

    except Exception as e:
        print(f"⚠️  Trade {i}: {symbol} - Failed to parse entry time: {e}")
        continue

    # Convert to Eastern for display
    eastern = pytz.timezone('US/Eastern')
    entry_time_et = entry_time.astimezone(eastern)

    print(f"\n{'='*100}")
    print(f"Trade {i}/{len(trades)}: {symbol} {side}")
    print(f"Entry: ${entry_price:.2f} @ {entry_time_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Exit: ${exit_price:.2f} ({reason})")
    print(f"P&L: ${pnl:.2f}")
    print(f"{'='*100}")

    # Get 5-second bars for the day
    contract = Stock(symbol, 'SMART', 'USD')

    # Get bars from market open to close
    trade_date = entry_time_et.date()
    end_time = f"{trade_date.strftime('%Y%m%d')} 16:00:00 US/Eastern"

    try:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime=end_time,
            durationStr='1 D',
            barSizeSetting='5 secs',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        if not bars:
            print(f"⚠️  No bar data available for {symbol} on {trade_date}")
            continue

        print(f"✓ Loaded {len(bars)} bars (5-sec) for {symbol} on {trade_date}")

        # Find entry bar
        entry_bar_idx = None
        for idx, bar in enumerate(bars):
            bar_time = bar.date
            if bar_time >= entry_time:
                entry_bar_idx = idx
                break

        if entry_bar_idx is None:
            print(f"⚠️  Could not find entry bar for {symbol} @ {entry_time_et}")
            continue

        # Analyze price action
        # Look 5 minutes (60 bars) before and after entry
        lookback_bars = 60  # 5 minutes at 5-sec bars
        lookforward_bars = 60  # 5 minutes after

        start_idx = max(0, entry_bar_idx - lookback_bars)
        end_idx = min(len(bars), entry_bar_idx + lookforward_bars)

        # Price action before entry
        pre_entry_bars = bars[start_idx:entry_bar_idx]
        if pre_entry_bars:
            pre_high = max(b.high for b in pre_entry_bars)
            pre_low = min(b.low for b in pre_entry_bars)
            pre_open = pre_entry_bars[0].open
            pre_close = pre_entry_bars[-1].close
            pre_range_pct = ((pre_high - pre_low) / pre_low) * 100
            pre_move_pct = ((pre_close - pre_open) / pre_open) * 100

            print(f"\n📊 PRE-ENTRY (5 min before entry):")
            print(f"   Range: ${pre_low:.2f} - ${pre_high:.2f} ({pre_range_pct:.2f}% range)")
            print(f"   Move: ${pre_open:.2f} → ${pre_close:.2f} ({pre_move_pct:+.2f}%)")
            print(f"   Entry @ ${entry_price:.2f} was {((entry_price - pre_low) / (pre_high - pre_low) * 100):.1f}% of pre-entry range")

        # Price action after entry
        post_entry_bars = bars[entry_bar_idx:end_idx]
        if post_entry_bars:
            post_high = max(b.high for b in post_entry_bars)
            post_low = min(b.low for b in post_entry_bars)
            post_close = post_entry_bars[-1].close

            # Calculate max favorable and adverse excursion
            if side == 'LONG':
                max_favorable = ((post_high - entry_price) / entry_price) * 100
                max_adverse = ((post_low - entry_price) / entry_price) * 100
                final_move = ((post_close - entry_price) / entry_price) * 100
            else:  # SHORT
                max_favorable = ((entry_price - post_low) / entry_price) * 100
                max_adverse = ((entry_price - post_high) / entry_price) * 100
                final_move = ((entry_price - post_close) / entry_price) * 100

            print(f"\n📈 POST-ENTRY (5 min after entry):")
            print(f"   Range: ${post_low:.2f} - ${post_high:.2f}")
            print(f"   Max Favorable Excursion: {max_favorable:+.2f}%")
            print(f"   Max Adverse Excursion: {max_adverse:+.2f}%")
            print(f"   Final Position (5 min later): {final_move:+.2f}%")

        # Check if trade went favorable immediately or reversed
        immediate_bars = bars[entry_bar_idx:min(len(bars), entry_bar_idx + 12)]  # 1 minute
        if immediate_bars and len(immediate_bars) > 1:
            immediate_high = max(b.high for b in immediate_bars)
            immediate_low = min(b.low for b in immediate_bars)

            if side == 'LONG':
                immediate_move = ((immediate_high - entry_price) / entry_price) * 100
                immediate_adverse = ((immediate_low - entry_price) / entry_price) * 100
            else:
                immediate_move = ((entry_price - immediate_low) / entry_price) * 100
                immediate_adverse = ((entry_price - immediate_high) / entry_price) * 100

            print(f"\n⚡ IMMEDIATE (1 min after entry):")
            print(f"   Best move: {immediate_move:+.2f}%")
            print(f"   Worst move: {immediate_adverse:+.2f}%")

            # Categorize entry quality
            if immediate_adverse < -0.3:
                entry_quality = "❌ IMMEDIATE REVERSAL (went against us >0.3% in first minute)"
            elif immediate_move > 0.5:
                entry_quality = "✅ IMMEDIATE MOMENTUM (moved favorably >0.5% in first minute)"
            elif abs(immediate_move) < 0.2 and abs(immediate_adverse) < 0.2:
                entry_quality = "⚠️  CHOPPY (no clear direction in first minute)"
            else:
                entry_quality = "➡️  NEUTRAL (small movement)"

            print(f"   Quality: {entry_quality}")

        # Store analysis
        analysis_results.append({
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'reason': reason,
            'pre_range_pct': pre_range_pct if pre_entry_bars else 0,
            'pre_move_pct': pre_move_pct if pre_entry_bars else 0,
            'max_favorable': max_favorable if post_entry_bars else 0,
            'max_adverse': max_adverse if post_entry_bars else 0,
            'immediate_move': immediate_move if immediate_bars and len(immediate_bars) > 1 else 0,
            'immediate_adverse': immediate_adverse if immediate_bars and len(immediate_bars) > 1 else 0,
            'entry_quality': entry_quality if immediate_bars and len(immediate_bars) > 1 else 'UNKNOWN'
        })

        # Rate limiting
        import time
        if i % 10 == 0:
            print(f"\n⏸️  Processed {i}/{len(trades)} trades - pausing 10 seconds for rate limiting...")
            time.sleep(10)
        else:
            time.sleep(1)  # 1 second between requests

    except Exception as e:
        print(f"❌ Error fetching data for {symbol}: {e}")
        continue

# Disconnect
ib.disconnect()
print("\n✓ Disconnected from IBKR\n")

# SUMMARY ANALYSIS
print("\n" + "=" * 100)
print("SUMMARY ANALYSIS")
print("=" * 100)

if not analysis_results:
    print("No analysis results available")
    sys.exit(0)

# Entry quality breakdown
entry_quality_counts = {}
for result in analysis_results:
    quality = result.get('entry_quality', 'UNKNOWN')
    if quality not in entry_quality_counts:
        entry_quality_counts[quality] = []
    entry_quality_counts[quality].append(result)

print(f"\n📊 ENTRY QUALITY BREAKDOWN (n={len(analysis_results)}):\n")
for quality, results_list in sorted(entry_quality_counts.items(), key=lambda x: len(x[1]), reverse=True):
    count = len(results_list)
    pct = (count / len(analysis_results)) * 100
    avg_pnl = sum(r['pnl'] for r in results_list) / count
    win_rate = len([r for r in results_list if r['pnl'] > 0]) / count * 100

    print(f"{quality}: {count} trades ({pct:.1f}%)")
    print(f"  Avg P&L: ${avg_pnl:.2f}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print()

# Immediate reversal analysis
immediate_reversals = [r for r in analysis_results if r.get('immediate_adverse', 0) < -0.3]
print(f"\n⚠️  IMMEDIATE REVERSALS (went against us >0.3% in first minute): {len(immediate_reversals)} trades")
if immediate_reversals:
    total_loss = sum(r['pnl'] for r in immediate_reversals)
    print(f"   Total P&L from immediate reversals: ${total_loss:.2f}")
    print(f"   These were bad entries - entered at local top/bottom")

# Good entries that still lost
good_entries_lost = [r for r in analysis_results if r.get('immediate_move', 0) > 0.3 and r['pnl'] < 0]
print(f"\n🤔 GOOD ENTRIES THAT LOST (moved favorably >0.3% then reversed): {len(good_entries_lost)} trades")
if good_entries_lost:
    total_loss = sum(r['pnl'] for r in good_entries_lost)
    print(f"   Total P&L: ${total_loss:.2f}")
    print(f"   These entries were good, but exits were too early or stops too tight")

# Bad entries that won
bad_entries_won = [r for r in analysis_results if r.get('immediate_adverse', 0) < -0.2 and r['pnl'] > 0]
print(f"\n😮 BAD ENTRIES THAT WON (went against us initially but recovered): {len(bad_entries_won)} trades")
if bad_entries_won:
    total_profit = sum(r['pnl'] for r in bad_entries_won)
    print(f"   Total P&L: ${total_profit:.2f}")
    print(f"   Lucky recoveries - these should have been losses")

# Max favorable excursion analysis
print(f"\n📈 MAX FAVORABLE EXCURSION ANALYSIS:")
losers_with_profit_potential = [r for r in analysis_results if r['pnl'] < 0 and r.get('max_favorable', 0) > 0.5]
print(f"   Losing trades that had >0.5% favorable excursion: {len(losers_with_profit_potential)}")
if losers_with_profit_potential:
    missed_profit = sum(abs(r['pnl']) for r in losers_with_profit_potential)
    avg_favorable = sum(r['max_favorable'] for r in losers_with_profit_potential) / len(losers_with_profit_potential)
    print(f"   These trades moved favorably (avg {avg_favorable:.2f}%) but we didn't capture it")
    print(f"   Total losses that could have been avoided: ${missed_profit:.2f}")

# Winners analysis
winners = [r for r in analysis_results if r['pnl'] > 0]
losers = [r for r in analysis_results if r['pnl'] <= 0]

print(f"\n✅ WINNERS ({len(winners)} trades):")
if winners:
    avg_immediate = sum(r.get('immediate_move', 0) for r in winners) / len(winners)
    avg_favorable = sum(r.get('max_favorable', 0) for r in winners) / len(winners)
    print(f"   Avg immediate move (1 min): {avg_immediate:+.2f}%")
    print(f"   Avg max favorable: {avg_favorable:+.2f}%")

print(f"\n❌ LOSERS ({len(losers)} trades):")
if losers:
    avg_immediate = sum(r.get('immediate_move', 0) for r in losers) / len(losers)
    avg_adverse = sum(r.get('immediate_adverse', 0) for r in losers) / len(losers)
    print(f"   Avg immediate move (1 min): {avg_immediate:+.2f}%")
    print(f"   Avg immediate adverse: {avg_adverse:+.2f}%")

# Save detailed results
with open('/tmp/sept_entry_exit_analysis.json', 'w') as f:
    json.dump(analysis_results, f, indent=2)

print(f"\n✓ Detailed results saved to /tmp/sept_entry_exit_analysis.json")

print("\n" + "=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
