#!/usr/bin/env python3
"""
Fast analysis using cached 5-second bar data
"""

import json
from datetime import datetime, timedelta
import pytz

# Load all trades
with open('monthly_results/all_trades_202509.json') as f:
    trades = json.load(f)

print("=" * 100)
print("ENTRY/EXIT TIMING ANALYSIS - Using Cached Data")
print("=" * 100)
print(f"\nAnalyzing {len(trades)} trades from Sept 23-30\n")

results = []
skipped = 0

for i, trade in enumerate(trades, 1):
    symbol = trade['symbol']
    entry_time_str = trade['entry_time']
    entry_price = trade['entry_price']
    side = trade['side']
    pnl = trade['pnl']

    # Parse times
    try:
        if '-04:00' in entry_time_str or '-05:00' in entry_time_str:
            # Already has timezone
            entry_time = datetime.fromisoformat(entry_time_str)
        else:
            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
    except:
        skipped += 1
        continue

    eastern = pytz.timezone('US/Eastern')
    entry_time_et = entry_time.astimezone(eastern)
    trade_date = entry_time_et.strftime('%Y%m%d')

    # Load cached bar data
    cache_file = f"data/{symbol}_{trade_date}_5sec.json"

    try:
        with open(cache_file) as f:
            bars = json.load(f)

        if not bars:
            skipped += 1
            continue

        # Find entry bar
        entry_bar_idx = None
        for idx, bar in enumerate(bars):
            bar_time = datetime.fromisoformat(bar['date'].replace('Z', '+00:00'))
            if bar_time >= entry_time:
                entry_bar_idx = idx
                break

        if entry_bar_idx is None or entry_bar_idx < 60:
            skipped += 1
            continue

        # Analyze 5 min before entry (60 bars × 5 sec = 300 sec = 5 min)
        pre_bars = bars[max(0, entry_bar_idx - 60):entry_bar_idx]

        pre_high = max(b['high'] for b in pre_bars)
        pre_low = min(b['low'] for b in pre_bars)
        pre_open = pre_bars[0]['open']
        pre_close = pre_bars[-1]['close']

        pre_range_pct = ((pre_high - pre_low) / pre_low) * 100
        pre_trend_pct = ((pre_close - pre_open) / pre_open) * 100

        # Where in the 5-min range did we enter?
        if pre_high > pre_low:
            entry_position_pct = ((entry_price - pre_low) / (pre_high - pre_low)) * 100
        else:
            entry_position_pct = 50

        # Analyze first minute after entry (12 bars × 5 sec = 60 sec)
        post_bars = bars[entry_bar_idx:min(len(bars), entry_bar_idx + 12)]

        if len(post_bars) > 1:
            post_high = max(b['high'] for b in post_bars)
            post_low = min(b['low'] for b in post_bars)
            post_close = post_bars[-1]['close']

            if side == 'LONG':
                imm_best = ((post_high - entry_price) / entry_price) * 100
                imm_worst = ((post_low - entry_price) / entry_price) * 100
                imm_net = ((post_close - entry_price) / entry_price) * 100
            else:
                imm_best = ((entry_price - post_low) / entry_price) * 100
                imm_worst = ((entry_price - post_high) / entry_price) * 100
                imm_net = ((entry_price - post_close) / entry_price) * 100

            # Categorize entry quality
            if imm_worst < -0.3:
                verdict = "BAD_REVERSAL"
            elif imm_best > 0.5:
                verdict = "GOOD_MOMENTUM"
            elif abs(imm_net) < 0.15:
                verdict = "CHOPPY"
            else:
                verdict = "NEUTRAL"

            # Check if we're chasing
            if side == 'LONG' and entry_position_pct > 80:
                chasing = "CHASING_HIGH"
            elif side == 'SHORT' and entry_position_pct < 20:
                chasing = "CHASING_LOW"
            else:
                chasing = "OK"

            results.append({
                'symbol': symbol,
                'side': side,
                'pnl': pnl,
                'entry_price': entry_price,
                'entry_position_pct': entry_position_pct,
                'pre_trend': pre_trend_pct,
                'imm_best': imm_best,
                'imm_worst': imm_worst,
                'imm_net': imm_net,
                'verdict': verdict,
                'chasing': chasing
            })

            if i % 10 == 0:
                print(f"Processed {i}/{len(trades)} trades...")

    except FileNotFoundError:
        skipped += 1
        continue
    except Exception as e:
        skipped += 1
        continue

print(f"\n✓ Analyzed {len(results)} trades (skipped {skipped})\n")

# ANALYSIS
print("=" * 100)
print("SUMMARY ANALYSIS")
print("=" * 100)

winners = [r for r in results if r['pnl'] > 0]
losers = [r for r in results if r['pnl'] <= 0]

# Overall stats
print(f"\n📊 OVERALL (n={len(results)}):")
print(f"   Winners: {len(winners)} ({len(winners)/len(results)*100:.1f}%)")
print(f"   Losers: {len(losers)} ({len(losers)/len(results)*100:.1f}%)")

# Entry quality breakdown
print(f"\n📈 ENTRY QUALITY:")
for verdict in ["GOOD_MOMENTUM", "NEUTRAL", "CHOPPY", "BAD_REVERSAL"]:
    trades_with_verdict = [r for r in results if r['verdict'] == verdict]
    if trades_with_verdict:
        count = len(trades_with_verdict)
        pct = (count / len(results)) * 100
        avg_pnl = sum(r['pnl'] for r in trades_with_verdict) / count
        win_rate = len([r for r in trades_with_verdict if r['pnl'] > 0]) / count * 100

        print(f"\n   {verdict}: {count} trades ({pct:.1f}%)")
        print(f"      Avg P&L: ${avg_pnl:.2f}")
        print(f"      Win Rate: {win_rate:.1f}%")

# Chasing analysis
print(f"\n🏃 CHASING ANALYSIS:")
chasing_trades = [r for r in results if r['chasing'] != 'OK']
if chasing_trades:
    print(f"   Chasing trades: {len(chasing_trades)} ({len(chasing_trades)/len(results)*100:.1f}%)")
    chasing_pnl = sum(r['pnl'] for r in chasing_trades)
    chasing_win_rate = len([r for r in chasing_trades if r['pnl'] > 0]) / len(chasing_trades) * 100
    print(f"   Total P&L: ${chasing_pnl:.2f}")
    print(f"   Win Rate: {chasing_win_rate:.1f}%")

# Winners vs Losers characteristics
print(f"\n✅ WINNERS ({len(winners)} trades):")
if winners:
    avg_entry_pos = sum(r['entry_position_pct'] for r in winners) / len(winners)
    avg_imm_best = sum(r['imm_best'] for r in winners) / len(winners)
    avg_imm_worst = sum(r['imm_worst'] for r in winners) / len(winners)

    print(f"   Avg entry position in range: {avg_entry_pos:.0f}%")
    print(f"   Avg immediate best: {avg_imm_best:+.2f}%")
    print(f"   Avg immediate worst: {avg_imm_worst:+.2f}%")

    # Verdict counts
    for v in ["GOOD_MOMENTUM", "NEUTRAL", "CHOPPY", "BAD_REVERSAL"]:
        count = len([r for r in winners if r['verdict'] == v])
        if count > 0:
            print(f"   {v}: {count}")

print(f"\n❌ LOSERS ({len(losers)} trades):")
if losers:
    avg_entry_pos = sum(r['entry_position_pct'] for r in losers) / len(losers)
    avg_imm_best = sum(r['imm_best'] for r in losers) / len(losers)
    avg_imm_worst = sum(r['imm_worst'] for r in losers) / len(losers)

    print(f"   Avg entry position in range: {avg_entry_pos:.0f}%")
    print(f"   Avg immediate best: {avg_imm_best:+.2f}%")
    print(f"   Avg immediate worst: {avg_imm_worst:+.2f}%")

    # Verdict counts
    for v in ["GOOD_MOMENTUM", "NEUTRAL", "CHOPPY", "BAD_REVERSAL"]:
        count = len([r for r in losers if r['verdict'] == v])
        if count > 0:
            print(f"   {v}: {count}")

# Key insights
print(f"\n" + "=" * 100)
print("KEY INSIGHTS")
print("=" * 100)

bad_entries = [r for r in results if r['verdict'] == 'BAD_REVERSAL']
print(f"\n1. BAD ENTRIES (immediate reversal <-0.3%): {len(bad_entries)}/{len(results)} ({len(bad_entries)/len(results)*100:.1f}%)")
if bad_entries:
    bad_pnl = sum(r['pnl'] for r in bad_entries)
    bad_won = len([r for r in bad_entries if r['pnl'] > 0])
    print(f"   Total P&L: ${bad_pnl:.2f}")
    print(f"   Win Rate: {bad_won}/{len(bad_entries)} ({bad_won/len(bad_entries)*100:.0f}%)")
    print(f"   → These entries happened at local tops/bottoms - TIMING ISSUE")

good_entries = [r for r in results if r['verdict'] == 'GOOD_MOMENTUM']
print(f"\n2. GOOD ENTRIES (immediate momentum >+0.5%): {len(good_entries)}/{len(results)} ({len(good_entries)/len(results)*100:.1f}%)")
if good_entries:
    good_pnl = sum(r['pnl'] for r in good_entries)
    good_won = len([r for r in good_entries if r['pnl'] > 0])
    print(f"   Total P&L: ${good_pnl:.2f}")
    print(f"   Win Rate: {good_won}/{len(good_entries)} ({good_won/len(good_entries)*100:.0f}%)")

    # Good entries that lost
    good_lost = [r for r in good_entries if r['pnl'] < 0]
    if good_lost:
        print(f"\n   Good entries that LOST: {len(good_lost)}")
        print(f"   → These had good timing but stops/exits were the problem")

# Save detailed results
with open('/tmp/sept_cached_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n✓ Detailed results saved to /tmp/sept_cached_analysis.json")
print("\n" + "=" * 100)
