#!/usr/bin/env python3
"""
Analyze October 9 backtest failures
Determine false breakouts vs real breakouts
"""

import json
from datetime import datetime

# Load all trades from monthly results
with open('monthly_results/all_trades_202510.json', 'r') as f:
    all_trades = json.load(f)

# Filter to Oct 9 only
oct9_trades = [t for t in all_trades if t['date'] == '2025-10-09']

print("=" * 80)
print("OCTOBER 9, 2025 - FAILURE ANALYSIS")
print("=" * 80)
print(f"Total trades: {len(oct9_trades)}")

# Categorize by outcome
losers = [t for t in oct9_trades if t['pnl'] < 0]
winners = [t for t in oct9_trades if t['pnl'] > 0]

print(f"Winners: {len(winners)} ({len(winners)/len(oct9_trades)*100:.1f}%)")
print(f"Losers: {len(losers)} ({len(losers)/len(oct9_trades)*100:.1f}%)")

# Analyze loser characteristics
print("\n" + "=" * 80)
print("LOSER ANALYSIS")
print("=" * 80)

quick_stops = [t for t in losers if t['duration_minutes'] < 5]
slow_bleeds = [t for t in losers if t['duration_minutes'] >= 5]

print(f"\nQuick stops (<5 min): {len(quick_stops)} ({len(quick_stops)/len(losers)*100:.1f}%)")
print(f"Slow bleeds (>=5 min): {len(slow_bleeds)} ({len(slow_bleeds)/len(losers)*100:.1f}%)")

# Quick stops are likely false breakouts
print(f"\nQUICK STOPS (False Breakouts):")
for t in quick_stops[:10]:  # Top 10
    print(f"  {t['symbol']:6} {t['side']:5} | Entry: ${t['entry_price']:.2f} | "
          f"Stop: ${t['exit_price']:.2f} | Loss: ${t['pnl']:.0f} | "
          f"Duration: {t['duration_minutes']} min")

# Analyze by direction
long_losers = [t for t in losers if t['side'] == 'LONG']
short_losers = [t for t in losers if t['side'] == 'SHORT']

print(f"\n" + "=" * 80)
print("DIRECTION ANALYSIS")
print("=" * 80)
print(f"LONG losers: {len(long_losers)} | Avg loss: ${sum(t['pnl'] for t in long_losers)/len(long_losers):.2f}")
print(f"SHORT losers: {len(short_losers)} | Avg loss: ${sum(t['pnl'] for t in short_losers)/len(short_losers):.2f}")

# Biggest losers
print(f"\n" + "=" * 80)
print("TOP 10 BIGGEST LOSSES")
print("=" * 80)
sorted_losers = sorted(losers, key=lambda x: x['pnl'])
for i, t in enumerate(sorted_losers[:10], 1):
    print(f"{i:2}. {t['symbol']:6} {t['side']:5} | "
          f"Entry: ${t['entry_price']:.2f} → ${t['exit_price']:.2f} | "
          f"Loss: ${t['pnl']:.0f} | {t['duration_minutes']} min | {t['exit_reason']}")

# Analyze winners for comparison
print(f"\n" + "=" * 80)
print("WINNERS (For Comparison)")
print("=" * 80)
for t in winners:
    print(f"  {t['symbol']:6} {t['side']:5} | Entry: ${t['entry_price']:.2f} | "
          f"Exit: ${t['exit_price']:.2f} | Profit: +${t['pnl']:.0f} | "
          f"Duration: {t['duration_minutes']} min | {t['exit_reason']}")

# Summary statistics
print(f"\n" + "=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)
print(f"Avg loser duration: {sum(t['duration_minutes'] for t in losers)/len(losers):.1f} min")
print(f"Avg winner duration: {sum(t['duration_minutes'] for t in winners)/len(winners):.1f} min" if winners else "No winners")
print(f"\nLosses from quick stops (<5 min): ${sum(t['pnl'] for t in quick_stops):.0f}")
print(f"Losses from slow bleeds (>=5 min): ${sum(t['pnl'] for t in slow_bleeds):.0f}")

# Count false breakouts (stopped out in <2 min)
false_breakouts = [t for t in losers if t['duration_minutes'] <= 2 and t['exit_reason'] == 'STOP']
print(f"\nProbable FALSE BREAKOUTS (<= 2 min, STOP): {len(false_breakouts)} trades")
print(f"Total loss from false breakouts: ${sum(t['pnl'] for t in false_breakouts):.0f}")

