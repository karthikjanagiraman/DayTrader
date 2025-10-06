#!/usr/bin/env python3
"""
Sample analysis of key trades from Sept 23-30
Focuses on worst losers and all winners to understand patterns
"""

import json
import sys
from datetime import datetime
from ib_insync import IB, Stock
import pytz

# Load trades
with open('monthly_results/all_trades_202509.json') as f:
    trades = json.load(f)

# Select trades to analyze:
# - All winners (13 trades)
# - Top 15 worst losers
# Total: ~28 trades (much faster)

winners = [t for t in trades if t['pnl'] > 0]
losers = sorted([t for t in trades if t['pnl'] <= 0], key=lambda x: x['pnl'])[:15]

sample_trades = winners + losers

print("=" * 100)
print("SAMPLE ENTRY/EXIT TIMING ANALYSIS: Sept 23-30, 2025")
print("=" * 100)
print(f"\nAnalyzing {len(sample_trades)} key trades:")
print(f"  - {len(winners)} winners")
print(f"  - {len(losers)} worst losers\n")

# Connect to IBKR
ib = IB()
try:
    ib.connect('127.0.0.1', 7497, clientId=4001)
    print("✓ Connected to IBKR\n")
except Exception as e:
    print(f"❌ Failed to connect to IBKR: {e}")
    sys.exit(1)

# Analysis results
analysis_results = []

for i, trade in enumerate(sample_trades, 1):
    symbol = trade['symbol']
    entry_time_str = trade['entry_time']
    entry_price = trade['entry_price']
    exit_price = trade['exit_price']
    side = trade['side']
    pnl = trade['pnl']
    reason = trade['reason']

    # Parse entry time
    try:
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

    # Convert to Eastern
    eastern = pytz.timezone('US/Eastern')
    entry_time_et = entry_time.astimezone(eastern)

    trade_type = "✅ WINNER" if pnl > 0 else "❌ LOSER"
    print(f"\n{'='*100}")
    print(f"Trade {i}/{len(sample_trades)}: {symbol} {side} - {trade_type}")
    print(f"Entry: ${entry_price:.2f} @ {entry_time_et.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Exit: ${exit_price:.2f} ({reason})")
    print(f"P&L: ${pnl:.2f}")
    print(f"{'='*100}")

    # Get 5-second bars
    contract = Stock(symbol, 'SMART', 'USD')
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

        if not bars or len(bars) < 10:
            print(f"⚠️  Insufficient bar data for {symbol}")
            import time
            time.sleep(1)
            continue

        print(f"✓ Loaded {len(bars)} bars")

        # Find entry bar
        entry_bar_idx = None
        for idx, bar in enumerate(bars):
            if bar.date >= entry_time:
                entry_bar_idx = idx
                break

        if entry_bar_idx is None:
            print(f"⚠️  Entry bar not found")
            import time
            time.sleep(1)
            continue

        # Analyze price action
        lookback = 60  # 5 min before
        lookforward = 60  # 5 min after

        # PRE-ENTRY ANALYSIS
        pre_start = max(0, entry_bar_idx - lookback)
        pre_bars = bars[pre_start:entry_bar_idx]

        if pre_bars:
            pre_high = max(b.high for b in pre_bars)
            pre_low = min(b.low for b in pre_bars)
            pre_open = pre_bars[0].open
            pre_close = pre_bars[-1].close
            pre_range_pct = ((pre_high - pre_low) / pre_low) * 100
            pre_move_pct = ((pre_close - pre_open) / pre_open) * 100
            entry_position_in_range = ((entry_price - pre_low) / (pre_high - pre_low)) * 100 if pre_high > pre_low else 50

            print(f"\n📊 PRE-ENTRY (5 min before):")
            print(f"   Range: ${pre_low:.2f} - ${pre_high:.2f} ({pre_range_pct:.2f}%)")
            print(f"   Trend: ${pre_open:.2f} → ${pre_close:.2f} ({pre_move_pct:+.2f}%)")
            print(f"   Entry was at {entry_position_in_range:.0f}% of 5-min range")

            # Interpret entry position
            if side == 'LONG':
                if entry_position_in_range > 80:
                    print(f"   ⚠️  CHASING: Entered near 5-min high (top 20%)")
                elif entry_position_in_range < 50:
                    print(f"   ✅ GOOD: Entered in lower half of range")
            else:  # SHORT
                if entry_position_in_range < 20:
                    print(f"   ⚠️  CHASING: Entered near 5-min low (bottom 20%)")
                elif entry_position_in_range > 50:
                    print(f"   ✅ GOOD: Entered in upper half of range")

        # POST-ENTRY ANALYSIS
        post_end = min(len(bars), entry_bar_idx + lookforward)
        post_bars = bars[entry_bar_idx:post_end]

        if post_bars:
            post_high = max(b.high for b in post_bars)
            post_low = min(b.low for b in post_bars)

            if side == 'LONG':
                max_favorable = ((post_high - entry_price) / entry_price) * 100
                max_adverse = ((post_low - entry_price) / entry_price) * 100
            else:
                max_favorable = ((entry_price - post_low) / entry_price) * 100
                max_adverse = ((entry_price - post_high) / entry_price) * 100

            print(f"\n📈 POST-ENTRY (5 min after):")
            print(f"   Max Favorable: {max_favorable:+.2f}%")
            print(f"   Max Adverse: {max_adverse:+.2f}%")

            # Interpret
            if max_adverse < -0.5:
                print(f"   ❌ Went against us badly (>{0.5:.1f}%)")
            if max_favorable > 0.5:
                print(f"   ✅ Had profit potential (>{0.5:.1f}%)")

        # IMMEDIATE REACTION (first minute)
        immediate_end = min(len(bars), entry_bar_idx + 12)
        immediate_bars = bars[entry_bar_idx:immediate_end]

        if immediate_bars and len(immediate_bars) > 1:
            imm_high = max(b.high for b in immediate_bars)
            imm_low = min(b.low for b in immediate_bars)
            imm_close = immediate_bars[-1].close

            if side == 'LONG':
                imm_move = ((imm_high - entry_price) / entry_price) * 100
                imm_adverse = ((imm_low - entry_price) / entry_price) * 100
                imm_net = ((imm_close - entry_price) / entry_price) * 100
            else:
                imm_move = ((entry_price - imm_low) / entry_price) * 100
                imm_adverse = ((entry_price - imm_high) / entry_price) * 100
                imm_net = ((entry_price - imm_close) / entry_price) * 100

            print(f"\n⚡ FIRST MINUTE:")
            print(f"   Best: {imm_move:+.2f}%")
            print(f"   Worst: {imm_adverse:+.2f}%")
            print(f"   Close: {imm_net:+.2f}%")

            # Categorize
            if imm_adverse < -0.3:
                verdict = "❌ IMMEDIATE REVERSAL (bad entry)"
            elif imm_move > 0.5:
                verdict = "✅ IMMEDIATE MOMENTUM (good entry)"
            elif abs(imm_net) < 0.15:
                verdict = "⚠️  CHOPPY (no clear direction)"
            else:
                verdict = "➡️  NEUTRAL"

            print(f"   Verdict: {verdict}")

            # Store
            analysis_results.append({
                'symbol': symbol,
                'side': side,
                'pnl': pnl,
                'reason': reason,
                'entry_position_pct': entry_position_in_range if pre_bars else 50,
                'pre_trend': pre_move_pct if pre_bars else 0,
                'max_favorable': max_favorable if post_bars else 0,
                'max_adverse': max_adverse if post_bars else 0,
                'immediate_best': imm_move,
                'immediate_worst': imm_adverse,
                'verdict': verdict
            })

        import time
        time.sleep(1)  # Rate limiting

    except Exception as e:
        print(f"❌ Error: {e}")
        import time
        time.sleep(1)
        continue

# Disconnect
ib.disconnect()
print("\n✓ Disconnected\n")

# SUMMARY
print("\n" + "=" * 100)
print("SUMMARY ANALYSIS")
print("n" + "=" * 100)

if not analysis_results:
    print("No results")
    sys.exit(0)

# Split by outcome
winners_analyzed = [r for r in analysis_results if r['pnl'] > 0]
losers_analyzed = [r for r in analysis_results if r['pnl'] <= 0]

print(f"\n✅ WINNERS ({len(winners_analyzed)} trades):\n")
if winners_analyzed:
    avg_entry_pos = sum(r['entry_position_pct'] for r in winners_analyzed) / len(winners_analyzed)
    avg_imm_best = sum(r['immediate_best'] for r in winners_analyzed) / len(winners_analyzed)
    avg_imm_worst = sum(r['immediate_worst'] for r in winners_analyzed) / len(winners_analyzed)

    print(f"  Avg entry position in 5-min range: {avg_entry_pos:.0f}%")
    print(f"  Avg immediate best move: {avg_imm_best:+.2f}%")
    print(f"  Avg immediate worst move: {avg_imm_worst:+.2f}%")

    # Verdict breakdown
    verdicts = {}
    for r in winners_analyzed:
        v = r['verdict']
        verdicts[v] = verdicts.get(v, 0) + 1
    print(f"\n  Entry Quality:")
    for v, count in sorted(verdicts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {v}: {count}")

print(f"\n❌ LOSERS ({len(losers_analyzed)} trades):\n")
if losers_analyzed:
    avg_entry_pos = sum(r['entry_position_pct'] for r in losers_analyzed) / len(losers_analyzed)
    avg_imm_best = sum(r['immediate_best'] for r in losers_analyzed) / len(losers_analyzed)
    avg_imm_worst = sum(r['immediate_worst'] for r in losers_analyzed) / len(losers_analyzed)

    print(f"  Avg entry position in 5-min range: {avg_entry_pos:.0f}%")
    print(f"  Avg immediate best move: {avg_imm_best:+.2f}%")
    print(f"  Avg immediate worst move: {avg_imm_worst:+.2f}%")

    # Verdict breakdown
    verdicts = {}
    for r in losers_analyzed:
        v = r['verdict']
        verdicts[v] = verdicts.get(v, 0) + 1
    print(f"\n  Entry Quality:")
    for v, count in sorted(verdicts.items(), key=lambda x: x[1], reverse=True):
        print(f"    {v}: {count}")

    # Missed opportunities
    had_profit = [r for r in losers_analyzed if r['max_favorable'] > 0.5]
    print(f"\n  Losers that had >0.5% profit opportunity: {len(had_profit)}")
    if had_profit:
        avg_favorable = sum(r['max_favorable'] for r in had_profit) / len(had_profit)
        print(f"  Average profit potential: {avg_favorable:.2f}%")
        print(f"  → These losses were exits/stops, not bad entries")

# KEY INSIGHTS
print(f"\n" + "=" * 100)
print("KEY INSIGHTS")
print("=" * 100)

bad_entries = [r for r in analysis_results if "REVERSAL" in r['verdict']]
good_entries = [r for r in analysis_results if "MOMENTUM" in r['verdict']]

print(f"\n1. BAD ENTRIES (immediate reversal): {len(bad_entries)}/{len(analysis_results)}")
if bad_entries:
    bad_pnl = sum(r['pnl'] for r in bad_entries)
    print(f"   Total P&L: ${bad_pnl:.2f}")
    print(f"   → Entry timing is the problem for these trades")

print(f"\n2. GOOD ENTRIES (immediate momentum): {len(good_entries)}/{len(analysis_results)}")
if good_entries:
    good_pnl = sum(r['pnl'] for r in good_entries)
    good_won = len([r for r in good_entries if r['pnl'] > 0])
    print(f"   Total P&L: ${good_pnl:.2f}")
    print(f"   Win Rate: {good_won}/{len(good_entries)} ({good_won/len(good_entries)*100:.0f}%)")

# Save results
with open('/tmp/sept_sample_analysis.json', 'w') as f:
    json.dump(analysis_results, f, indent=2)

print(f"\n✓ Results saved to /tmp/sept_sample_analysis.json\n")
print("=" * 100)
