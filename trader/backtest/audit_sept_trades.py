#!/usr/bin/env python3
"""
Comprehensive audit of Sept 23-30 trades
Analyzes entry logic, exit logic, and identifies patterns in losses
"""

import json
from datetime import datetime
from collections import defaultdict

# Load trades
with open('monthly_results/all_trades_202509.json') as f:
    trades = json.load(f)

print("=" * 80)
print("COMPREHENSIVE TRADE AUDIT: Sept 23-30, 2025")
print("=" * 80)
print(f"\nTotal Trades: {len(trades)}")
print()

# Categorize trades
winners = [t for t in trades if t['pnl'] > 0]
losers = [t for t in trades if t['pnl'] <= 0]

print(f"Winners: {len(winners)} ({len(winners)/len(trades)*100:.1f}%)")
print(f"Losers: {len(losers)} ({len(losers)/len(trades)*100:.1f}%)")
print()

# Exit reason breakdown
exit_reasons = defaultdict(list)
for t in trades:
    exit_reasons[t['reason']].append(t)

print("=" * 80)
print("EXIT REASON BREAKDOWN")
print("=" * 80)
for reason, trades_list in sorted(exit_reasons.items(), key=lambda x: len(x[1]), reverse=True):
    total_pnl = sum(t['pnl'] for t in trades_list)
    win_rate = len([t for t in trades_list if t['pnl'] > 0]) / len(trades_list) * 100
    print(f"\n{reason}: {len(trades_list)} trades")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Total P&L: ${total_pnl:,.2f}")
    print(f"  Avg P&L: ${total_pnl/len(trades_list):.2f}")

# Duration analysis
print("\n" + "=" * 80)
print("DURATION ANALYSIS")
print("=" * 80)

durations = [t['duration_min'] for t in trades if 'duration_min' in t]
if durations:
    print(f"Avg Duration: {sum(durations)/len(durations):.1f} minutes")
    print(f"Max Duration: {max(durations):.1f} minutes")
    print(f"Min Duration: {min(durations):.1f} minutes")

    # Quick exits (<5 min)
    quick_exits = [t for t in trades if t.get('duration_min', 0) < 5]
    print(f"\nQuick Exits (<5 min): {len(quick_exits)} trades")
    quick_exit_pnl = sum(t['pnl'] for t in quick_exits)
    print(f"  Total P&L: ${quick_exit_pnl:,.2f}")
    print(f"  Avg P&L: ${quick_exit_pnl/len(quick_exits):.2f}")

# 8-minute rule analysis
eight_min_exits = exit_reasons.get('8MIN_RULE', [])
if eight_min_exits:
    print("\n" + "=" * 80)
    print("8-MINUTE RULE ANALYSIS")
    print("=" * 80)
    print(f"Total 8-min exits: {len(eight_min_exits)}")

    saved_losses = [t for t in eight_min_exits if t['pnl'] > -500]
    big_losses = [t for t in eight_min_exits if t['pnl'] <= -500]

    print(f"Small losses saved: {len(saved_losses)} (P&L: ${sum(t['pnl'] for t in saved_losses):,.2f})")
    print(f"Big losses: {len(big_losses)} (P&L: ${sum(t['pnl'] for t in big_losses):,.2f})")

    # Show worst 8-min exits
    if big_losses:
        print("\nWorst 8-min rule exits:")
        for t in sorted(big_losses, key=lambda x: x['pnl'])[:5]:
            print(f"  {t['symbol']} {t['side']}: ${t['pnl']:.2f} (entry: ${t['entry_price']:.2f}, exit: ${t['exit_price']:.2f})")

# Symbol analysis
print("\n" + "=" * 80)
print("SYMBOL PERFORMANCE")
print("=" * 80)

symbol_stats = defaultdict(lambda: {'trades': 0, 'pnl': 0, 'winners': 0})
for t in trades:
    symbol_stats[t['symbol']]['trades'] += 1
    symbol_stats[t['symbol']]['pnl'] += t['pnl']
    if t['pnl'] > 0:
        symbol_stats[t['symbol']]['winners'] += 1

# Show worst performing symbols
print("\nWorst Performing Symbols:")
worst_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'])[:10]
for symbol, stats in worst_symbols:
    win_rate = stats['winners'] / stats['trades'] * 100
    print(f"  {symbol}: {stats['trades']} trades, ${stats['pnl']:.2f} P&L, {win_rate:.0f}% win rate")

# Show best performing symbols (if any)
print("\nBest Performing Symbols:")
best_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)[:10]
for symbol, stats in best_symbols:
    win_rate = stats['winners'] / stats['trades'] * 100
    print(f"  {symbol}: {stats['trades']} trades, ${stats['pnl']:.2f} P&L, {win_rate:.0f}% win rate")

# LONG vs SHORT analysis
print("\n" + "=" * 80)
print("LONG vs SHORT PERFORMANCE")
print("=" * 80)

longs = [t for t in trades if t['side'] == 'LONG']
shorts = [t for t in trades if t['side'] == 'SHORT']

print(f"\nLONGS: {len(longs)} trades")
long_pnl = sum(t['pnl'] for t in longs)
long_winners = len([t for t in longs if t['pnl'] > 0])
print(f"  Total P&L: ${long_pnl:,.2f}")
print(f"  Win Rate: {long_winners/len(longs)*100:.1f}%")
print(f"  Avg P&L: ${long_pnl/len(longs):.2f}")

print(f"\nSHORTS: {len(shorts)} trades")
short_pnl = sum(t['pnl'] for t in shorts)
short_winners = len([t for t in shorts if t['pnl'] > 0])
print(f"  Total P&L: ${short_pnl:,.2f}")
print(f"  Win Rate: {short_winners/len(shorts)*100:.1f}%")
print(f"  Avg P&L: ${short_pnl/len(shorts):.2f}")

# Daily analysis
print("\n" + "=" * 80)
print("DAILY BREAKDOWN")
print("=" * 80)

daily_stats = defaultdict(lambda: {'trades': [], 'pnl': 0})
for t in trades:
    date = t['entry_time'].split('T')[0]
    daily_stats[date]['trades'].append(t)
    daily_stats[date]['pnl'] += t['pnl']

for date in sorted(daily_stats.keys()):
    stats = daily_stats[date]
    day_trades = stats['trades']
    winners_count = len([t for t in day_trades if t['pnl'] > 0])

    print(f"\n{date}:")
    print(f"  Trades: {len(day_trades)}")
    print(f"  P&L: ${stats['pnl']:,.2f}")
    print(f"  Win Rate: {winners_count/len(day_trades)*100:.1f}%")

    # Show worst trade of the day
    worst = min(day_trades, key=lambda x: x['pnl'])
    print(f"  Worst: {worst['symbol']} {worst['side']} ${worst['pnl']:.2f} ({worst['reason']})")

    # Show best trade of the day (if positive)
    best = max(day_trades, key=lambda x: x['pnl'])
    if best['pnl'] > 0:
        print(f"  Best: {best['symbol']} {best['side']} +${best['pnl']:.2f} ({best['reason']})")

# Partial profit analysis
print("\n" + "=" * 80)
print("PARTIAL PROFIT ANALYSIS")
print("=" * 80)

with_partials = [t for t in trades if t.get('partials', 0) > 0]
without_partials = [t for t in trades if t.get('partials', 0) == 0]

print(f"\nTrades with partials: {len(with_partials)}")
print(f"  Total P&L: ${sum(t['pnl'] for t in with_partials):,.2f}")
print(f"  Avg P&L: ${sum(t['pnl'] for t in with_partials)/len(with_partials):.2f}")

print(f"\nTrades without partials: {len(without_partials)}")
print(f"  Total P&L: ${sum(t['pnl'] for t in without_partials):,.2f}")
print(f"  Avg P&L: ${sum(t['pnl'] for t in without_partials)/len(without_partials):.2f}")

# Entry time analysis
print("\n" + "=" * 80)
print("ENTRY TIME ANALYSIS")
print("=" * 80)

early_entries = []  # Before 10:00
mid_entries = []    # 10:00-14:00
late_entries = []   # After 14:00

for t in trades:
    entry_time = datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00'))
    hour = entry_time.hour

    if hour < 10:
        early_entries.append(t)
    elif hour < 14:
        mid_entries.append(t)
    else:
        late_entries.append(t)

print(f"\nEarly (before 10 AM): {len(early_entries)} trades")
if early_entries:
    print(f"  Total P&L: ${sum(t['pnl'] for t in early_entries):,.2f}")
    print(f"  Win Rate: {len([t for t in early_entries if t['pnl'] > 0])/len(early_entries)*100:.1f}%")

print(f"\nMid-day (10 AM - 2 PM): {len(mid_entries)} trades")
if mid_entries:
    print(f"  Total P&L: ${sum(t['pnl'] for t in mid_entries):,.2f}")
    print(f"  Win Rate: {len([t for t in mid_entries if t['pnl'] > 0])/len(mid_entries)*100:.1f}%")

print(f"\nLate (after 2 PM): {len(late_entries)} trades")
if late_entries:
    print(f"  Total P&L: ${sum(t['pnl'] for t in late_entries):,.2f}")
    print(f"  Win Rate: {len([t for t in late_entries if t['pnl'] > 0])/len(late_entries)*100:.1f}%")

# Top 10 worst trades
print("\n" + "=" * 80)
print("TOP 10 WORST TRADES")
print("=" * 80)

worst_trades = sorted(trades, key=lambda x: x['pnl'])[:10]
for i, t in enumerate(worst_trades, 1):
    entry_time = datetime.fromisoformat(t['entry_time'].replace('Z', '+00:00'))
    print(f"\n{i}. {t['symbol']} {t['side']}")
    print(f"   Entry: ${t['entry_price']:.2f} @ {entry_time.strftime('%m/%d %H:%M')}")
    print(f"   Exit: ${t['exit_price']:.2f} ({t['reason']})")
    print(f"   P&L: ${t['pnl']:.2f} ({t['pnl_pct']:.2f}%)")
    print(f"   Duration: {t.get('duration_min', 0):.0f} min")
    print(f"   Partials: {t.get('partials', 0)}")

# Summary and recommendations
print("\n" + "=" * 80)
print("SUMMARY & KEY FINDINGS")
print("=" * 80)

print(f"\n1. Overall Performance: -${sum(t['pnl'] for t in trades):,.2f} ({len(winners)} winners, {len(losers)} losers)")
print(f"2. Win Rate: {len(winners)/len(trades)*100:.1f}% (target: >35%)")
print(f"3. Average Loss: ${sum(t['pnl'] for t in losers)/len(losers):.2f}")
print(f"4. Average Winner: ${sum(t['pnl'] for t in winners)/len(winners):.2f}" if winners else "4. No winners")
print(f"5. Most Common Exit: {max(exit_reasons.items(), key=lambda x: len(x[1]))[0]}")

print("\n" + "=" * 80)
