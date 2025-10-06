#!/usr/bin/env python3
"""
False Breakout Analysis - First Attempt vs Second Attempt

Analyzes backtest data from Oct 1-3 to determine if second attempts
at pivots are more reliable than first attempts.
"""

import json
from datetime import datetime
from collections import defaultdict

def analyze_attempts():
    # Load trade data
    with open('/Users/karthik/projects/DayTrader/trader/backtest/monthly_results/all_trades_202510.json') as f:
        trades = json.load(f)

    # Filter to Oct 1-3 only
    oct_trades = []
    for trade in trades:
        entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
        if entry_time.day <= 3:
            oct_trades.append(trade)

    print(f"Total trades Oct 1-3: {len(oct_trades)}")

    # Group by symbol + date + side
    grouped = defaultdict(list)
    for trade in oct_trades:
        entry_time = datetime.fromisoformat(trade['entry_time'].replace('Z', '+00:00'))
        date = entry_time.date()
        key = (trade['symbol'], str(date), trade['side'])
        grouped[key].append(trade)

    # Analyze first vs second attempts
    first_attempt_stats = {'wins': 0, 'losses': 0, 'total_pnl': 0}
    second_attempt_stats = {'wins': 0, 'losses': 0, 'total_pnl': 0}

    examples = {
        'first_win': [],
        'first_loss': [],
        'second_win': [],
        'second_loss': [],
        'both_loss': [],
        'both_win': []
    }

    for key, trades_list in grouped.items():
        symbol, date, side = key

        # Sort by entry time
        trades_list.sort(key=lambda x: x['entry_time'])

        if len(trades_list) == 1:
            # Only one attempt
            trade = trades_list[0]
            is_winner = trade['pnl'] > 0
            first_attempt_stats['total_pnl'] += trade['pnl']
            if is_winner:
                first_attempt_stats['wins'] += 1
                examples['first_win'].append(trade)
            else:
                first_attempt_stats['losses'] += 1
                examples['first_loss'].append(trade)

        elif len(trades_list) == 2:
            # Two attempts
            first = trades_list[0]
            second = trades_list[1]

            first_win = first['pnl'] > 0
            second_win = second['pnl'] > 0

            first_attempt_stats['total_pnl'] += first['pnl']
            second_attempt_stats['total_pnl'] += second['pnl']

            if first_win:
                first_attempt_stats['wins'] += 1
            else:
                first_attempt_stats['losses'] += 1

            if second_win:
                second_attempt_stats['wins'] += 1
            else:
                second_attempt_stats['losses'] += 1

            # Track patterns
            if first_win and second_win:
                examples['both_win'].append((first, second))
            elif not first_win and not second_win:
                examples['both_loss'].append((first, second))
            elif not first_win and second_win:
                examples['second_win'].append((first, second))
            elif first_win and not second_win:
                examples['first_win'].append(first)
                examples['second_loss'].append(second)

    # Calculate stats
    first_total = first_attempt_stats['wins'] + first_attempt_stats['losses']
    second_total = second_attempt_stats['wins'] + second_attempt_stats['losses']

    first_win_rate = (first_attempt_stats['wins'] / first_total * 100) if first_total > 0 else 0
    second_win_rate = (second_attempt_stats['wins'] / second_total * 100) if second_total > 0 else 0

    first_avg_pnl = first_attempt_stats['total_pnl'] / first_total if first_total > 0 else 0
    second_avg_pnl = second_attempt_stats['total_pnl'] / second_total if second_total > 0 else 0

    print("\n" + "="*80)
    print("FALSE BREAKOUT ANALYSIS: FIRST VS SECOND ATTEMPT")
    print("="*80)

    print("\n📊 FIRST ATTEMPT STATISTICS:")
    print(f"  Total trades: {first_total}")
    print(f"  Winners: {first_attempt_stats['wins']} ({first_win_rate:.1f}%)")
    print(f"  Losers: {first_attempt_stats['losses']} ({100-first_win_rate:.1f}%)")
    print(f"  Total P&L: ${first_attempt_stats['total_pnl']:,.2f}")
    print(f"  Avg P&L: ${first_avg_pnl:,.2f}")

    print("\n📊 SECOND ATTEMPT STATISTICS:")
    print(f"  Total trades: {second_total}")
    print(f"  Winners: {second_attempt_stats['wins']} ({second_win_rate:.1f}%)")
    print(f"  Losers: {second_attempt_stats['losses']} ({100-second_win_rate:.1f}%)")
    print(f"  Total P&L: ${second_attempt_stats['total_pnl']:,.2f}")
    print(f"  Avg P&L: ${second_avg_pnl:,.2f}")

    print("\n🔍 PATTERN ANALYSIS:")
    print(f"  First LOSS → Second WIN: {len(examples['second_win'])} cases")
    print(f"  Both WIN: {len(examples['both_win'])} cases")
    print(f"  Both LOSS: {len(examples['both_loss'])} cases")

    # Show examples
    if examples['second_win']:
        print("\n✅ EXAMPLES: First attempt FAILED, Second attempt WON")
        print("-" * 80)
        for first, second in examples['second_win'][:5]:
            print(f"\n{first['symbol']} {first['side']} on {first['entry_time'][:10]}:")
            print(f"  Attempt #1: Entry ${first['entry_price']:.2f} → Exit ${first['exit_price']:.2f}")
            print(f"             P&L: ${first['pnl']:,.2f} ({first['reason']}) - LOSS")
            print(f"  Attempt #2: Entry ${second['entry_price']:.2f} → Exit ${second['exit_price']:.2f}")
            print(f"             P&L: ${second['pnl']:,.2f} ({second['reason']}) - WIN ✅")

    if examples['both_loss']:
        print("\n❌ EXAMPLES: Both attempts FAILED")
        print("-" * 80)
        for first, second in examples['both_loss'][:5]:
            print(f"\n{first['symbol']} {first['side']} on {first['entry_time'][:10]}:")
            print(f"  Attempt #1: Entry ${first['entry_price']:.2f} → Exit ${first['exit_price']:.2f}")
            print(f"             P&L: ${first['pnl']:,.2f} ({first['reason']}) - LOSS")
            print(f"  Attempt #2: Entry ${second['entry_price']:.2f} → Exit ${second['exit_price']:.2f}")
            print(f"             P&L: ${second['pnl']:,.2f} ({second['reason']}) - LOSS")

    # Conclusion
    print("\n" + "="*80)
    print("📈 CONCLUSION:")
    print("="*80)

    improvement = second_win_rate - first_win_rate
    if improvement > 5:
        print(f"✅ Second attempts are BETTER by {improvement:.1f}% win rate")
        print("   → Strategy should consider waiting for pullback/second attempt")
    elif improvement > 0:
        print(f"⚠️  Second attempts are SLIGHTLY better by {improvement:.1f}% win rate")
        print("   → Marginal improvement, not significant")
    else:
        print(f"❌ Second attempts are WORSE by {abs(improvement):.1f}% win rate")
        print("   → No benefit to waiting for second attempt")

    pnl_improvement = second_avg_pnl - first_avg_pnl
    print(f"\nAvg P&L improvement: ${pnl_improvement:,.2f} per trade")

    # Calculate expected value
    first_ev = (first_attempt_stats['wins'] / first_total * first_avg_pnl if first_total > 0 else 0)
    second_ev = (second_attempt_stats['wins'] / second_total * second_avg_pnl if second_total > 0 else 0)

    print(f"\nExpected Value (win rate × avg winner):")
    print(f"  First attempt: ${first_ev:,.2f}")
    print(f"  Second attempt: ${second_ev:,.2f}")

if __name__ == '__main__':
    analyze_attempts()
