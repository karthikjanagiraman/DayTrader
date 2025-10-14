#!/usr/bin/env python3
"""
Comprehensive Entry/Exit Analysis for Sept 23-30 With Fixes
Analyzes all 88 trades to understand price action before/after entry
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

# Load all trades from the backtest
trades_file = '/Users/karthik/projects/DayTrader/trader/backtest/monthly_results/all_trades_202509.json'

with open(trades_file) as f:
    all_trades_data = json.load(f)

# Filter to Sept 23-30 trades only
# Extract date from entry_time field
trades = []
for t in all_trades_data:
    entry_time_str = t['entry_time']
    entry_date = entry_time_str.split()[0]  # Extract YYYY-MM-DD
    if '2025-09-23' <= entry_date <= '2025-09-30':
        trades.append(t)

print(f"Analyzing {len(trades)} trades from Sept 23-30 with fixes applied...")
print("=" * 80)

# Cache directory for 5-second bars
cache_dir = '/Users/karthik/projects/DayTrader/trader/backtest/data'

results = []
categories = defaultdict(int)

for idx, trade in enumerate(trades, 1):
    symbol = trade['symbol']
    entry_time_full = trade['entry_time']
    entry_price = trade['entry_price']
    exit_price = trade['exit_price']
    side = trade['side']
    pnl = trade['pnl']

    # Extract date and time
    date = entry_time_full.split()[0]  # YYYY-MM-DD
    time_with_tz = entry_time_full.split()[1]  # HH:MM:SS-04:00
    entry_time_str = time_with_tz.split('-')[0][:5]  # HH:MM

    # Load cached 5-second bars for this symbol/date
    cache_file = os.path.join(cache_dir, f"{symbol}_{date.replace('-', '')}_5sec.json")

    if not os.path.exists(cache_file):
        print(f"\n{idx}. {symbol} {side} - NO CACHE FILE")
        continue

    with open(cache_file) as f:
        bars = json.load(f)

    # Find entry bar
    entry_time = datetime.strptime(f"{date} {entry_time_str}", "%Y-%m-%d %H:%M")

    # Find the bar closest to entry time
    entry_bar_idx = None
    min_time_diff = float('inf')

    for i, bar in enumerate(bars):
        bar_time = datetime.fromisoformat(bar['date'].replace('Z', '+00:00'))
        bar_time = bar_time.replace(tzinfo=None)  # Remove timezone for comparison
        time_diff = abs((bar_time - entry_time).total_seconds())

        if time_diff < min_time_diff:
            min_time_diff = time_diff
            entry_bar_idx = i

    if entry_bar_idx is None or entry_bar_idx < 60:
        print(f"\n{idx}. {symbol} {side} - Entry bar not found or too early")
        continue

    # Analyze price action BEFORE entry (5 minutes = 60 bars)
    pre_entry_bars = bars[max(0, entry_bar_idx - 60):entry_bar_idx]

    if len(pre_entry_bars) < 10:
        continue

    pre_high = max(b['high'] for b in pre_entry_bars)
    pre_low = min(b['low'] for b in pre_entry_bars)
    pre_range = pre_high - pre_low

    # Entry position in recent range
    if pre_range > 0:
        entry_position_pct = ((entry_price - pre_low) / pre_range) * 100
    else:
        entry_position_pct = 50.0

    # Analyze price action AFTER entry (first minute = 12 bars)
    post_entry_bars = bars[entry_bar_idx:min(entry_bar_idx + 12, len(bars))]

    if len(post_entry_bars) < 5:
        continue

    # Immediate reaction (first minute after entry)
    imm_high = max(b['high'] for b in post_entry_bars)
    imm_low = min(b['low'] for b in post_entry_bars)
    imm_close = post_entry_bars[-1]['close']

    # Calculate immediate move from entry
    if side == 'LONG':
        imm_best = ((imm_high - entry_price) / entry_price) * 100
        imm_worst = ((imm_low - entry_price) / entry_price) * 100
        imm_net = ((imm_close - entry_price) / entry_price) * 100
    else:  # SHORT
        imm_best = ((entry_price - imm_low) / entry_price) * 100
        imm_worst = ((entry_price - imm_high) / entry_price) * 100
        imm_net = ((entry_price - imm_close) / entry_price) * 100

    # Calculate 5-minute range as % of ATR (estimate ATR from pre-entry bars)
    atr_estimate = sum(b['high'] - b['low'] for b in pre_entry_bars) / len(pre_entry_bars)
    range_to_atr_ratio = pre_range / atr_estimate if atr_estimate > 0 else 0

    # Categorize entry quality
    is_chasing = (side == 'LONG' and entry_position_pct > 70) or \
                 (side == 'SHORT' and entry_position_pct < 30)

    is_choppy = range_to_atr_ratio < 0.5

    is_bad_reversal = imm_worst < -0.3  # Immediate move against position

    is_good_momentum = imm_best > 0.5  # Immediate favorable move

    # Determine verdict
    if is_bad_reversal:
        verdict = "BAD_REVERSAL"
    elif is_good_momentum:
        verdict = "GOOD_MOMENTUM"
    elif is_choppy:
        verdict = "CHOPPY"
    elif is_chasing:
        verdict = "CHASING"
    else:
        verdict = "NEUTRAL"

    categories[verdict] += 1

    # Store result
    result = {
        'trade_num': idx,
        'symbol': symbol,
        'side': side,
        'date': date,
        'entry_price': entry_price,
        'exit_price': exit_price,
        'pnl': pnl,
        'entry_position_pct': entry_position_pct,
        'pre_range_pct': (pre_range / entry_price) * 100,
        'range_to_atr_ratio': range_to_atr_ratio,
        'imm_best': imm_best,
        'imm_worst': imm_worst,
        'imm_net': imm_net,
        'verdict': verdict,
        'is_chasing': is_chasing,
        'is_choppy': is_choppy,
    }

    results.append(result)

    # Print detailed analysis for each trade
    winner = "✅" if pnl > 0 else "❌"
    print(f"\n{idx}. {winner} {symbol} {side} (${entry_price:.2f} → ${exit_price:.2f}, P&L: ${pnl:.2f})")
    print(f"   Entry Position: {entry_position_pct:.0f}% of 5-min range {'🔴 CHASING' if is_chasing else '🟢 GOOD'}")
    print(f"   Pre-Entry Range: ${pre_range:.2f} ({(pre_range/entry_price)*100:.2f}% of price)")
    print(f"   Range/ATR Ratio: {range_to_atr_ratio:.2f}× {'🔴 CHOPPY' if is_choppy else '🟢 TRENDING'}")
    print(f"   First Minute: Best {imm_best:+.2f}%, Worst {imm_worst:+.2f}%, Net {imm_net:+.2f}%")
    print(f"   Verdict: {verdict}")

# Summary statistics
print("\n" + "=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)

print(f"\nTotal trades analyzed: {len(results)}")

print(f"\nEntry Quality Breakdown:")
for verdict, count in sorted(categories.items(), key=lambda x: -x[1]):
    pct = (count / len(results)) * 100
    print(f"  {verdict}: {count} trades ({pct:.1f}%)")

# Winners vs Losers analysis
winners = [r for r in results if r['pnl'] > 0]
losers = [r for r in results if r['pnl'] <= 0]

print(f"\nWinners ({len(winners)}) vs Losers ({len(losers)}):")
if winners:
    avg_winner_entry_pos = sum(r['entry_position_pct'] for r in winners) / len(winners)
    print(f"  Winners avg entry position: {avg_winner_entry_pos:.0f}% of range")
else:
    print(f"  Winners avg entry position: N/A (no winners)")

if losers:
    avg_loser_entry_pos = sum(r['entry_position_pct'] for r in losers) / len(losers)
    print(f"  Losers avg entry position: {avg_loser_entry_pos:.0f}% of range")

# Chasing analysis
chasing_trades = [r for r in results if r['is_chasing']]
print(f"\nChasing Trades: {len(chasing_trades)}")
if chasing_trades:
    chasing_winners = len([r for r in chasing_trades if r['pnl'] > 0])
    chasing_losers = len([r for r in chasing_trades if r['pnl'] <= 0])
    chasing_total_pnl = sum(r['pnl'] for r in chasing_trades)
    print(f"  Winners: {chasing_winners}, Losers: {chasing_losers}")
    print(f"  Win Rate: {(chasing_winners / len(chasing_trades)) * 100:.1f}%")
    print(f"  Total P&L: ${chasing_total_pnl:.2f}")

# Choppy analysis
choppy_trades = [r for r in results if r['is_choppy']]
print(f"\nChoppy Trades (range < 0.5× ATR): {len(choppy_trades)}")
if choppy_trades:
    choppy_winners = len([r for r in choppy_trades if r['pnl'] > 0])
    choppy_losers = len([r for r in choppy_trades if r['pnl'] <= 0])
    choppy_total_pnl = sum(r['pnl'] for r in choppy_trades)
    print(f"  Winners: {choppy_winners}, Losers: {choppy_losers}")
    print(f"  Win Rate: {(choppy_winners / len(choppy_trades)) * 100:.1f}%")
    print(f"  Total P&L: ${choppy_total_pnl:.2f}")

# Bad reversal analysis
bad_reversals = [r for r in results if r['verdict'] == 'BAD_REVERSAL']
print(f"\nBad Reversals (immediate move against position >0.3%): {len(bad_reversals)}")
if bad_reversals:
    bad_rev_winners = len([r for r in bad_reversals if r['pnl'] > 0])
    bad_rev_total_pnl = sum(r['pnl'] for r in bad_reversals)
    print(f"  Winners: {bad_rev_winners}, Losers: {len(bad_reversals) - bad_rev_winners}")
    print(f"  Total P&L: ${bad_rev_total_pnl:.2f}")

# Save detailed results
output_file = '/Users/karthik/projects/DayTrader/trader/with_fixes_entry_analysis.json'
with open(output_file, 'w') as f:
    json.dump({
        'summary': {
            'total_trades': len(results),
            'categories': dict(categories),
            'winners': len(winners),
            'losers': len(losers),
            'chasing_trades': len(chasing_trades),
            'choppy_trades': len(choppy_trades),
            'bad_reversals': len(bad_reversals),
        },
        'trades': results
    }, f, indent=2)

print(f"\n✓ Detailed results saved to: {output_file}")
