#!/usr/bin/env python3
"""
Comprehensive analysis of all Oct 9 trades
"""

# All 30 trades from backtest output
trades = [
    {"symbol": "BB", "side": "LONG", "pnl": -44.39, "duration": 14, "reason": "STOP"},
    {"symbol": "COIN", "side": "LONG", "pnl": -1339.26, "duration": 0, "reason": "STOP"},
    {"symbol": "COIN", "side": "LONG", "pnl": -2944.55, "duration": 4, "reason": "STOP"},
    {"symbol": "OXY", "side": "SHORT", "pnl": -19.26, "duration": 107, "reason": "TRAIL_STOP"},
    {"symbol": "PYPL", "side": "SHORT", "pnl": -285.79, "duration": 0, "reason": "STOP"},
    {"symbol": "PYPL", "side": "SHORT", "pnl": -255.79, "duration": 0, "reason": "STOP"},
    {"symbol": "ROKU", "side": "SHORT", "pnl": -598.99, "duration": 4, "reason": "STOP"},
    {"symbol": "ROKU", "side": "SHORT", "pnl": -409.36, "duration": 12, "reason": "STOP"},
    {"symbol": "AVGO", "side": "LONG", "pnl": -1111.36, "duration": 0, "reason": "STOP"},
    {"symbol": "AVGO", "side": "LONG", "pnl": -1231.36, "duration": 0, "reason": "STOP"},
    {"symbol": "TSLA", "side": "SHORT", "pnl": -1781.43, "duration": 9, "reason": "STOP"},
    {"symbol": "TSLA", "side": "SHORT", "pnl": -12.90, "duration": 4, "reason": "TRAIL_STOP"},
    {"symbol": "QCOM", "side": "SHORT", "pnl": -621.58, "duration": 1, "reason": "STOP"},
    {"symbol": "QCOM", "side": "SHORT", "pnl": -541.66, "duration": 5, "reason": "STOP"},
    {"symbol": "BA", "side": "SHORT", "pnl": 1544.86, "duration": 338, "reason": "EOD"},
    {"symbol": "PLTR", "side": "LONG", "pnl": 84.82, "duration": 15, "reason": "15MIN_RULE"},
    {"symbol": "META", "side": "LONG", "pnl": 392.35, "duration": 15, "reason": "15MIN_RULE"},
    {"symbol": "C", "side": "SHORT", "pnl": 83.71, "duration": 16, "reason": "15MIN_RULE"},
    {"symbol": "GS", "side": "SHORT", "pnl": -2442.56, "duration": 15, "reason": "15MIN_RULE"},
    {"symbol": "SOFI", "side": "LONG", "pnl": -184.81, "duration": 2, "reason": "STOP"},
    {"symbol": "SOFI", "side": "LONG", "pnl": -114.71, "duration": 0, "reason": "STOP"},
    {"symbol": "LYFT", "side": "SHORT", "pnl": -6.53, "duration": 3, "reason": "TRAIL_STOP"},
    {"symbol": "LYFT", "side": "SHORT", "pnl": -162.31, "duration": 3, "reason": "STOP"},
    {"symbol": "CVX", "side": "SHORT", "pnl": -55.44, "duration": 20, "reason": "TRAIL_STOP"},
    {"symbol": "CVX", "side": "SHORT", "pnl": -488.50, "duration": 0, "reason": "STOP"},
    {"symbol": "BAC", "side": "SHORT", "pnl": -179.32, "duration": 2, "reason": "STOP"},
    {"symbol": "BAC", "side": "SHORT", "pnl": -179.32, "duration": 0, "reason": "STOP"},
    {"symbol": "MS", "side": "SHORT", "pnl": -632.20, "duration": 1, "reason": "STOP"},
    {"symbol": "JD", "side": "SHORT", "pnl": -132.70, "duration": 0, "reason": "STOP"},
    {"symbol": "JD", "side": "SHORT", "pnl": -122.71, "duration": 0, "reason": "STOP"},
]

print("=" * 100)
print("COMPREHENSIVE OCTOBER 9 ANALYSIS")
print("=" * 100)

# Categorize
false_breakouts = [t for t in trades if t['duration'] <= 5 and t['reason'] == 'STOP']
instant_stops = [t for t in trades if t['duration'] <= 1 and t['reason'] == 'STOP']
fifteen_min_exits = [t for t in trades if t['reason'] == '15MIN_RULE']
trail_stops = [t for t in trades if t['reason'] == 'TRAIL_STOP']
winners = [t for t in trades if t['pnl'] > 0]
losers = [t for t in trades if t['pnl'] < 0]

print(f"\n📊 TRADE BREAKDOWN:")
print(f"  Total trades: {len(trades)}")
print(f"  Winners: {len(winners)} ({len(winners)/len(trades)*100:.1f}%)")
print(f"  Losers: {len(losers)} ({len(losers)/len(trades)*100:.1f}%)")

print(f"\n❌ FALSE BREAKOUTS (Stopped out ≤5 min):")
print(f"  Count: {len(false_breakouts)} ({len(false_breakouts)/len(trades)*100:.1f}%)")
print(f"  Total loss: ${sum(t['pnl'] for t in false_breakouts):.2f}")
print(f"  Avg loss: ${sum(t['pnl'] for t in false_breakouts)/len(false_breakouts):.2f}")

print(f"\n⚡ INSTANT STOPS (≤1 min):")
print(f"  Count: {len(instant_stops)}")
print(f"  Total loss: ${sum(t['pnl'] for t in instant_stops):.2f}")

print(f"\n⏱️  15-MINUTE RULE EXITS:")
print(f"  Count: {len(fifteen_min_exits)}")
print(f"  Winners: {len([t for t in fifteen_min_exits if t['pnl'] > 0])}")
print(f"  Losers: {len([t for t in fifteen_min_exits if t['pnl'] < 0])}")
print(f"  Total P&L: ${sum(t['pnl'] for t in fifteen_min_exits):.2f}")

print(f"\n🎯 TRAIL STOPS:")
print(f"  Count: {len(trail_stops)}")
print(f"  Total P&L: ${sum(t['pnl'] for t in trail_stops):.2f}")

# Direction analysis
long_trades = [t for t in trades if t['side'] == 'LONG']
short_trades = [t for t in trades if t['side'] == 'SHORT']

long_winners = [t for t in long_trades if t['pnl'] > 0]
short_winners = [t for t in short_trades if t['pnl'] > 0]

print(f"\n📈 DIRECTION ANALYSIS:")
print(f"  LONGS: {len(long_trades)} total | {len(long_winners)} winners ({len(long_winners)/len(long_trades)*100:.1f}%)")
print(f"    Total P&L: ${sum(t['pnl'] for t in long_trades):.2f}")
print(f"  SHORTS: {len(short_trades)} total | {len(short_winners)} winners ({len(short_winners)/len(short_trades)*100:.1f}%)")
print(f"    Total P&L: ${sum(t['pnl'] for t in short_trades):.2f}")

# Key insights
print(f"\n💡 KEY INSIGHTS:")
print(f"  1. False breakouts caused ${sum(t['pnl'] for t in false_breakouts):.2f} loss ({abs(sum(t['pnl'] for t in false_breakouts))/abs(sum(t['pnl'] for t in losers))*100:.1f}% of total losses)")
print(f"  2. Instant stops (≤1 min) suggest entries are too aggressive")
print(f"  3. Only 1 trade (BA) held until EOD - this was the biggest winner")
print(f"  4. 15-minute rule fired {len(fifteen_min_exits)} times (mixed results)")

# List all false breakouts
print(f"\n❌ DETAILED FALSE BREAKOUTS (≤5 min stops):")
for t in sorted(false_breakouts, key=lambda x: x['pnl']):
    print(f"  {t['symbol']:6} {t['side']:5} | Loss: ${t['pnl']:8.2f} | {t['duration']:2} min")

# Top winners
print(f"\n✅ TOP WINNERS:")
for t in sorted(winners, key=lambda x: -x['pnl'])[:5]:
    print(f"  {t['symbol']:6} {t['side']:5} | Profit: ${t['pnl']:8.2f} | {t['duration']:3} min | {t['reason']}")

# Critical problem summary
print(f"\n🚨 CRITICAL PROBLEM:")
print(f"  {len(false_breakouts)} trades ({len(false_breakouts)/len(trades)*100:.1f}%) were FALSE BREAKOUTS")
print(f"  These trades lost ${sum(t['pnl'] for t in false_breakouts):.2f}")
print(f"  Entry logic is entering TOO LATE or on WEAK breakouts")
print(f"  Need better confirmation BEFORE entering")

