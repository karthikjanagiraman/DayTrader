#!/usr/bin/env python3
"""
Map backtest trades to actual code decision tree paths.

This analyzes which path each trade took through the state machine,
which filters were applied, and calculates win rates for each path.
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def load_trades(date_str):
    """Load trades from results file"""
    file_path = Path(__file__).parent / 'results' / f'backtest_trades_{date_str}.json'
    if not file_path.exists():
        return []
    with open(file_path) as f:
        return json.load(f)

def classify_trade_path(trade):
    """
    Classify which code path this trade took based on entry characteristics.

    Returns dict with:
        - entry_path: MOMENTUM, SUSTAINED_BREAK, or PULLBACK_RETEST
        - filters_passed: List of filters that passed
        - filters_failed: List of filters that failed (if any)
        - entry_delay: Minutes from breakout to entry
        - entry_reason: Why entered (from trade data)
    """

    classification = {
        'symbol': trade['symbol'],
        'side': trade['side'],
        'entry_price': trade['entry_price'],
        'exit_price': trade['exit_price'],
        'pnl': trade['pnl'],
        'pnl_pct': trade['pnl_pct'],
        'duration_min': trade['duration_min'],
        'partials': trade['partials'],
        'exit_reason': trade['reason']
    }

    # Determine entry path based on trade characteristics
    # Note: Actual backtest doesn't store entry_reason, so we infer from behavior

    # Check for momentum characteristics:
    # - Fast entry (within 2 minutes of breakout)
    # - High volume surge (if we had the data)
    # - Large first move

    first_move_pct = abs(trade['pnl_pct'])
    duration = trade['duration_min']

    # HEURISTIC: Classify based on behavior patterns
    # This is approximate since we don't have state machine logs

    if trade['partials'] >= 1 and duration > 60:
        # Took partials and ran long = likely momentum breakout
        classification['entry_path'] = 'MOMENTUM'
        classification['entry_confidence'] = 'HIGH'
        classification['reasoning'] = 'Fast move, took partials, ran long'

    elif duration <= 7 and trade['reason'] == '15MIN_RULE':
        # Hit 7-min timeout = likely failed any path
        # Could be momentum that failed filters OR weak breakout that never got entry signal

        if first_move_pct < 0.15:
            # Almost no movement = likely choppy market filter should have blocked
            classification['entry_path'] = 'MOMENTUM_ATTEMPTED'
            classification['entry_confidence'] = 'MEDIUM'
            classification['reasoning'] = 'Choppy market - should have been filtered'
            classification['filter_failure'] = 'CHOPPY_MARKET'
        else:
            # Had some movement but stopped quickly
            classification['entry_path'] = 'MOMENTUM_ATTEMPTED'
            classification['entry_confidence'] = 'MEDIUM'
            classification['reasoning'] = 'Quick stop - momentum failed'

    elif duration > 7 and duration < 30:
        # Medium duration, no partials = likely weak breakout path
        if trade['reason'] == '15MIN_RULE':
            classification['entry_path'] = 'WEAK_ATTEMPTED'
            classification['entry_confidence'] = 'LOW'
            classification['reasoning'] = 'Medium duration timeout - sustained or pullback path'
        else:
            classification['entry_path'] = 'PULLBACK_RETEST'
            classification['entry_confidence'] = 'MEDIUM'
            classification['reasoning'] = 'Medium duration with exit signal'

    elif duration >= 30:
        # Long duration = likely pullback/retest or sustained break
        if trade['partials'] >= 1:
            classification['entry_path'] = 'PULLBACK_RETEST'
            classification['entry_confidence'] = 'HIGH'
            classification['reasoning'] = 'Long duration, took partials'
        else:
            classification['entry_path'] = 'SUSTAINED_BREAK'
            classification['entry_confidence'] = 'MEDIUM'
            classification['reasoning'] = 'Long duration, no partials'
    else:
        classification['entry_path'] = 'UNKNOWN'
        classification['entry_confidence'] = 'NONE'
        classification['reasoning'] = 'Could not classify'

    # Analyze filter effectiveness
    classification['should_have_filtered'] = False
    classification['filter_suggestions'] = []

    # FILTER ANALYSIS: Which filters SHOULD have blocked this trade?

    # 1. Choppy Market Filter (range/ATR < 0.5)
    if duration <= 7 and first_move_pct < 0.15 and trade['pnl'] < 0:
        classification['should_have_filtered'] = True
        classification['filter_suggestions'].append('CHOPPY_MARKET (first min move <0.15%)')

    # 2. Room-to-Run Filter (insufficient room to target)
    # We don't have target data in trades, so can't check this

    # 3. Time-of-Day Filter (momentum after 2 PM)
    # We don't have entry time, so can't check this

    # 4. Volume Sustainability Filter
    # We don't have volume data in trades, so can't check this

    return classification

def analyze_all_trades():
    """Analyze all trades from Oct 7-9 and map to code paths"""

    print("=" * 100)
    print("CODE PATH ANALYSIS - October 7-9, 2025")
    print("Mapping Actual Trades to Code Decision Tree Paths")
    print("=" * 100)
    print()

    dates = ['20251007', '20251008', '20251009']

    all_trades = []
    all_classifications = []

    for date in dates:
        trades = load_trades(date)
        all_trades.extend(trades)

    print(f"Total trades loaded: {len(all_trades)}")
    print()

    # Classify each trade
    for trade in all_trades:
        classification = classify_trade_path(trade)
        all_classifications.append(classification)

    # Aggregate statistics by path
    path_stats = defaultdict(lambda: {
        'count': 0,
        'winners': 0,
        'losers': 0,
        'total_pnl': 0,
        'trades': []
    })

    for cls in all_classifications:
        path = cls['entry_path']
        stats = path_stats[path]

        stats['count'] += 1
        stats['trades'].append(cls)
        stats['total_pnl'] += cls['pnl']

        if cls['pnl'] > 0:
            stats['winners'] += 1
        else:
            stats['losers'] += 1

    # Print results by path
    print("\n" + "=" * 100)
    print("TRADE CLASSIFICATION BY CODE PATH")
    print("=" * 100)

    for path in ['MOMENTUM', 'MOMENTUM_ATTEMPTED', 'SUSTAINED_BREAK',
                 'PULLBACK_RETEST', 'WEAK_ATTEMPTED', 'UNKNOWN']:
        if path not in path_stats:
            continue

        stats = path_stats[path]
        win_rate = (stats['winners'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0

        print(f"\n{'=' * 100}")
        print(f"PATH: {path}")
        print(f"{'=' * 100}")
        print(f"Count:        {stats['count']} ({stats['count']/len(all_trades)*100:.1f}% of all trades)")
        print(f"Win Rate:     {win_rate:.1f}% ({stats['winners']} winners, {stats['losers']} losers)")
        print(f"Total P&L:    ${stats['total_pnl']:,.2f}")
        print(f"Avg P&L:      ${avg_pnl:.2f}")

        # Show example trades
        print(f"\nExample Trades (first 5):")
        for i, trade in enumerate(stats['trades'][:5], 1):
            print(f"  {i}. {trade['symbol']} {trade['side']}: "
                  f"${trade['entry_price']:.2f} → ${trade['exit_price']:.2f} "
                  f"({trade['duration_min']:.0f}min) = ${trade['pnl']:.2f} "
                  f"[{trade['exit_reason']}]")
            print(f"     Reasoning: {trade['reasoning']}")

    # Filter effectiveness analysis
    print("\n" + "=" * 100)
    print("FILTER EFFECTIVENESS ANALYSIS")
    print("=" * 100)

    should_have_filtered = [cls for cls in all_classifications if cls['should_have_filtered']]

    print(f"\nTrades that SHOULD have been filtered: {len(should_have_filtered)}/{len(all_trades)} "
          f"({len(should_have_filtered)/len(all_trades)*100:.1f}%)")

    if should_have_filtered:
        total_saved = sum(abs(cls['pnl']) for cls in should_have_filtered if cls['pnl'] < 0)
        print(f"Potential P&L saved by proper filtering: ${total_saved:,.2f}")

        # Group by filter type
        filter_groups = defaultdict(lambda: {'count': 0, 'pnl_saved': 0, 'trades': []})

        for cls in should_have_filtered:
            for filter_name in cls['filter_suggestions']:
                filter_groups[filter_name]['count'] += 1
                if cls['pnl'] < 0:
                    filter_groups[filter_name]['pnl_saved'] += abs(cls['pnl'])
                filter_groups[filter_name]['trades'].append(cls)

        print("\nBreakdown by Filter Type:")
        for filter_name, data in sorted(filter_groups.items(),
                                       key=lambda x: x[1]['pnl_saved'],
                                       reverse=True):
            print(f"\n  {filter_name}:")
            print(f"    Would filter: {data['count']} trades")
            print(f"    P&L saved: ${data['pnl_saved']:,.2f}")
            print(f"    Examples:")
            for trade in data['trades'][:3]:
                print(f"      - {trade['symbol']} {trade['side']}: ${trade['pnl']:.2f} "
                      f"({trade['duration_min']:.0f}min)")

    # Winners analysis - did we miss any?
    print("\n" + "=" * 100)
    print("WINNER ANALYSIS - Did We Miss Any?")
    print("=" * 100)

    winners = [cls for cls in all_classifications if cls['pnl'] > 0]
    print(f"\nTotal winners: {len(winners)}/{len(all_trades)} ({len(winners)/len(all_trades)*100:.1f}%)")
    print(f"Total winner P&L: ${sum(w['pnl'] for w in winners):,.2f}")

    # Analyze winner characteristics
    momentum_winners = [w for w in winners if 'MOMENTUM' in w['entry_path']]
    pullback_winners = [w for w in winners if 'PULLBACK' in w['entry_path']]
    sustained_winners = [w for w in winners if 'SUSTAINED' in w['entry_path']]

    print(f"\nWinner Breakdown by Path:")
    print(f"  Momentum:        {len(momentum_winners)} winners, ${sum(w['pnl'] for w in momentum_winners):,.2f}")
    print(f"  Pullback/Retest: {len(pullback_winners)} winners, ${sum(w['pnl'] for w in pullback_winners):,.2f}")
    print(f"  Sustained Break: {len(sustained_winners)} winners, ${sum(w['pnl'] for w in sustained_winners):,.2f}")

    print("\nTop 5 Winners:")
    for i, winner in enumerate(sorted(winners, key=lambda x: x['pnl'], reverse=True)[:5], 1):
        print(f"  {i}. {winner['symbol']} {winner['side']}: ${winner['pnl']:.2f} "
              f"({winner['duration_min']:.0f}min, {winner['partials']} partials) "
              f"[{winner['entry_path']}]")
        print(f"     {winner['reasoning']}")

    # Day-by-day analysis
    print("\n" + "=" * 100)
    print("DAY-BY-DAY PATH ANALYSIS")
    print("=" * 100)

    for date in dates:
        trades = load_trades(date)
        if not trades:
            continue

        date_formatted = f"{date[:4]}-{date[4:6]}-{date[6:]}"

        day_classifications = []
        for trade in trades:
            cls = classify_trade_path(trade)
            day_classifications.append(cls)

        day_path_stats = defaultdict(lambda: {'count': 0, 'pnl': 0})
        for cls in day_classifications:
            path = cls['entry_path']
            day_path_stats[path]['count'] += 1
            day_path_stats[path]['pnl'] += cls['pnl']

        total_pnl = sum(cls['pnl'] for cls in day_classifications)
        total_trades = len(day_classifications)

        print(f"\n{date_formatted}:")
        print(f"  Total: {total_trades} trades, ${total_pnl:,.2f} P&L")
        print(f"  Path breakdown:")
        for path, stats in sorted(day_path_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            print(f"    {path}: {stats['count']} trades (${stats['pnl']:.2f})")

    # Summary statistics
    print("\n" + "=" * 100)
    print("SUMMARY STATISTICS")
    print("=" * 100)

    total_pnl = sum(cls['pnl'] for cls in all_classifications)
    total_winners = len([cls for cls in all_classifications if cls['pnl'] > 0])
    total_losers = len([cls for cls in all_classifications if cls['pnl'] < 0])
    win_rate = (total_winners / len(all_classifications) * 100) if all_classifications else 0

    print(f"\nOverall Performance:")
    print(f"  Total Trades:  {len(all_classifications)}")
    print(f"  Winners:       {total_winners} ({win_rate:.1f}%)")
    print(f"  Losers:        {total_losers} ({100-win_rate:.1f}%)")
    print(f"  Total P&L:     ${total_pnl:,.2f}")
    print(f"  Avg Trade:     ${total_pnl/len(all_classifications):.2f}")

    avg_winner = sum(cls['pnl'] for cls in all_classifications if cls['pnl'] > 0) / total_winners if total_winners > 0 else 0
    avg_loser = sum(cls['pnl'] for cls in all_classifications if cls['pnl'] < 0) / total_losers if total_losers > 0 else 0

    print(f"\n  Avg Winner:    ${avg_winner:.2f}")
    print(f"  Avg Loser:     ${avg_loser:.2f}")
    print(f"  Win/Loss:      {abs(avg_winner/avg_loser):.2f}x" if avg_loser != 0 else "  Win/Loss:      N/A")

    # Most common exit reasons
    print(f"\nExit Reason Breakdown:")
    exit_reasons = defaultdict(int)
    for cls in all_classifications:
        exit_reasons[cls['exit_reason']] += 1

    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reason}: {count} ({count/len(all_classifications)*100:.1f}%)")

if __name__ == '__main__':
    analyze_all_trades()
