#!/usr/bin/env python3
"""
Decision Tree Analysis - Map the actual path each trade took
and calculate win rates for each decision branch.

This focuses on WHAT HAPPENED in each trade, not comparing timeouts.
"""

import json
from pathlib import Path
from collections import defaultdict

def load_trades(date_str):
    """Load trades from results file"""
    file_path = Path(__file__).parent / 'results' / f'backtest_trades_{date_str}.json'
    if not file_path.exists():
        return []
    with open(file_path) as f:
        return json.load(f)

def analyze_decision_path(trade):
    """
    Map the decision path a trade took:

    Entry → Did it move favorably? → Did it take partials? → How did it exit?
    """

    path = {
        'symbol': trade['symbol'],
        'side': trade['side'],
        'pnl': trade['pnl'],
        'pnl_pct': trade['pnl_pct'],
        'duration': trade['duration_min'],
        'partials': trade['partials'],
        'exit_reason': trade['reason']
    }

    # Decision 1: Did price move favorably initially?
    if trade['pnl_pct'] > 0.5:
        path['initial_move'] = 'STRONG_FAVOR'  # >0.5% favorable
    elif trade['pnl_pct'] > 0:
        path['initial_move'] = 'SLIGHT_FAVOR'  # 0-0.5% favorable
    elif trade['pnl_pct'] > -0.5:
        path['initial_move'] = 'SLIGHT_AGAINST'  # 0 to -0.5%
    else:
        path['initial_move'] = 'STRONG_AGAINST'  # <-0.5%

    # Decision 2: Did it take partials?
    if trade['partials'] >= 2:
        path['partial_status'] = 'MULTIPLE_PARTIALS'  # Took 2+ partials
    elif trade['partials'] == 1:
        path['partial_status'] = 'ONE_PARTIAL'  # Took 1 partial
    else:
        path['partial_status'] = 'NO_PARTIALS'  # No partials

    # Decision 3: How long did it last?
    if trade['duration_min'] < 5:
        path['duration_category'] = 'INSTANT'  # <5 min
    elif trade['duration_min'] < 15:
        path['duration_category'] = 'SHORT'  # 5-15 min
    elif trade['duration_min'] < 60:
        path['duration_category'] = 'MEDIUM'  # 15-60 min
    else:
        path['duration_category'] = 'LONG'  # 60+ min

    # Decision 4: Exit mechanism
    path['exit_mechanism'] = trade['reason']

    # Decision 5: Final outcome
    if trade['pnl'] > 100:
        path['outcome'] = 'BIG_WIN'
    elif trade['pnl'] > 0:
        path['outcome'] = 'SMALL_WIN'
    elif trade['pnl'] > -100:
        path['outcome'] = 'SMALL_LOSS'
    else:
        path['outcome'] = 'BIG_LOSS'

    # Construct path string
    path['path_string'] = f"{path['initial_move']} → {path['partial_status']} → {path['duration_category']} → {path['exit_mechanism']} → {path['outcome']}"

    return path

def main():
    print("="*100)
    print("DECISION TREE ANALYSIS - October 7-9, 2025")
    print("="*100)
    print()

    # Load all trades
    dates = ['20251007', '20251008', '20251009']
    all_trades = []
    for date in dates:
        all_trades.extend(load_trades(date))

    print(f"Total trades analyzed: {len(all_trades)}")
    print()

    # Analyze each trade
    paths = []
    for trade in all_trades:
        path = analyze_decision_path(trade)
        paths.append(path)

    # Decision 1 Analysis: Initial Move Direction
    print("="*100)
    print("DECISION 1: INITIAL PRICE MOVEMENT (First Move After Entry)")
    print("="*100)
    print()

    initial_move_stats = defaultdict(lambda: {'count': 0, 'winners': 0, 'total_pnl': 0, 'trades': []})
    for path in paths:
        move = path['initial_move']
        initial_move_stats[move]['count'] += 1
        initial_move_stats[move]['total_pnl'] += path['pnl']
        initial_move_stats[move]['trades'].append(path)
        if path['pnl'] > 0:
            initial_move_stats[move]['winners'] += 1

    for move in ['STRONG_FAVOR', 'SLIGHT_FAVOR', 'SLIGHT_AGAINST', 'STRONG_AGAINST']:
        if move not in initial_move_stats:
            continue
        stats = initial_move_stats[move]
        win_rate = (stats['winners'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0

        print(f"{move}:")
        print(f"  Count: {stats['count']} ({stats['count']/len(all_trades)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg P&L: ${avg_pnl:.2f}")
        print(f"  Total P&L: ${stats['total_pnl']:.2f}")

        # Show examples
        print(f"  Examples:")
        for trade in stats['trades'][:3]:
            print(f"    - {trade['symbol']} {trade['side']}: ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%) [{trade['exit_reason']}]")
        print()

    # Decision 2 Analysis: Partial Status
    print("="*100)
    print("DECISION 2: PARTIAL PROFIT TAKING")
    print("="*100)
    print()

    partial_stats = defaultdict(lambda: {'count': 0, 'winners': 0, 'total_pnl': 0, 'trades': []})
    for path in paths:
        status = path['partial_status']
        partial_stats[status]['count'] += 1
        partial_stats[status]['total_pnl'] += path['pnl']
        partial_stats[status]['trades'].append(path)
        if path['pnl'] > 0:
            partial_stats[status]['winners'] += 1

    for status in ['MULTIPLE_PARTIALS', 'ONE_PARTIAL', 'NO_PARTIALS']:
        if status not in partial_stats:
            continue
        stats = partial_stats[status]
        win_rate = (stats['winners'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0

        print(f"{status}:")
        print(f"  Count: {stats['count']} ({stats['count']/len(all_trades)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg P&L: ${avg_pnl:.2f}")
        print(f"  Total P&L: ${stats['total_pnl']:.2f}")
        print(f"  Examples:")
        for trade in stats['trades'][:3]:
            print(f"    - {trade['symbol']} {trade['side']}: ${trade['pnl']:.2f} ({trade['duration']:.0f} min) [{trade['exit_reason']}]")
        print()

    # Decision 3 Analysis: Duration Category
    print("="*100)
    print("DECISION 3: TRADE DURATION (How Long It Lasted)")
    print("="*100)
    print()

    duration_stats = defaultdict(lambda: {'count': 0, 'winners': 0, 'total_pnl': 0, 'trades': []})
    for path in paths:
        cat = path['duration_category']
        duration_stats[cat]['count'] += 1
        duration_stats[cat]['total_pnl'] += path['pnl']
        duration_stats[cat]['trades'].append(path)
        if path['pnl'] > 0:
            duration_stats[cat]['winners'] += 1

    for cat in ['INSTANT', 'SHORT', 'MEDIUM', 'LONG']:
        if cat not in duration_stats:
            continue
        stats = duration_stats[cat]
        win_rate = (stats['winners'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0

        print(f"{cat}:")
        print(f"  Count: {stats['count']} ({stats['count']/len(all_trades)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg P&L: ${avg_pnl:.2f}")
        print(f"  Total P&L: ${stats['total_pnl']:.2f}")
        print(f"  Examples:")
        for trade in stats['trades'][:3]:
            print(f"    - {trade['symbol']} {trade['side']}: ${trade['pnl']:.2f} ({trade['duration']:.0f} min) [{trade['exit_reason']}]")
        print()

    # Decision 4 Analysis: Exit Mechanism
    print("="*100)
    print("DECISION 4: EXIT MECHANISM (How Trade Closed)")
    print("="*100)
    print()

    exit_stats = defaultdict(lambda: {'count': 0, 'winners': 0, 'total_pnl': 0, 'trades': []})
    for path in paths:
        mechanism = path['exit_mechanism']
        exit_stats[mechanism]['count'] += 1
        exit_stats[mechanism]['total_pnl'] += path['pnl']
        exit_stats[mechanism]['trades'].append(path)
        if path['pnl'] > 0:
            exit_stats[mechanism]['winners'] += 1

    for mechanism in sorted(exit_stats.keys(), key=lambda x: exit_stats[x]['count'], reverse=True):
        stats = exit_stats[mechanism]
        win_rate = (stats['winners'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0

        print(f"{mechanism}:")
        print(f"  Count: {stats['count']} ({stats['count']/len(all_trades)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg P&L: ${avg_pnl:.2f}")
        print(f"  Total P&L: ${stats['total_pnl']:.2f}")
        print()

    # Full Path Analysis
    print("="*100)
    print("COMPLETE DECISION PATHS (Full Journey)")
    print("="*100)
    print()

    path_stats = defaultdict(lambda: {'count': 0, 'winners': 0, 'total_pnl': 0, 'trades': []})
    for path in paths:
        path_str = path['path_string']
        path_stats[path_str]['count'] += 1
        path_stats[path_str]['total_pnl'] += path['pnl']
        path_stats[path_str]['trades'].append(path)
        if path['pnl'] > 0:
            path_stats[path_str]['winners'] += 1

    # Sort by count
    sorted_paths = sorted(path_stats.items(), key=lambda x: x[1]['count'], reverse=True)

    for path_str, stats in sorted_paths[:10]:  # Top 10 most common paths
        win_rate = (stats['winners'] / stats['count'] * 100) if stats['count'] > 0 else 0
        avg_pnl = stats['total_pnl'] / stats['count'] if stats['count'] > 0 else 0

        print(f"\nPath {sorted_paths.index((path_str, stats)) + 1}:")
        print(f"  {path_str}")
        print(f"  Count: {stats['count']} ({stats['count']/len(all_trades)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg P&L: ${avg_pnl:.2f}")
        print(f"  Trades: {', '.join([t['symbol'] for t in stats['trades']])}")

    # Key Insights
    print("\n" + "="*100)
    print("KEY INSIGHTS FROM DECISION TREE")
    print("="*100)
    print()

    # Insight 1: Correlation between initial move and outcome
    strong_favor_trades = [p for p in paths if p['initial_move'] == 'STRONG_FAVOR']
    strong_against_trades = [p for p in paths if p['initial_move'] == 'STRONG_AGAINST']

    sf_win_rate = sum(1 for t in strong_favor_trades if t['pnl'] > 0) / len(strong_favor_trades) * 100 if strong_favor_trades else 0
    sa_win_rate = sum(1 for t in strong_against_trades if t['pnl'] > 0) / len(strong_against_trades) * 100 if strong_against_trades else 0

    print("INSIGHT 1: Initial Move Predicts Outcome")
    print(f"  - If price moves STRONGLY IN FAVOR initially: {sf_win_rate:.1f}% win rate")
    print(f"  - If price moves STRONGLY AGAINST initially: {sa_win_rate:.1f}% win rate")
    print(f"  - Difference: {sf_win_rate - sa_win_rate:.1f} percentage points")
    print()

    # Insight 2: Partial taking correlation
    partial_trades = [p for p in paths if p['partials'] > 0]
    no_partial_trades = [p for p in paths if p['partials'] == 0]

    partial_win_rate = sum(1 for t in partial_trades if t['pnl'] > 0) / len(partial_trades) * 100 if partial_trades else 0
    no_partial_win_rate = sum(1 for t in no_partial_trades if t['pnl'] > 0) / len(no_partial_trades) * 100 if no_partial_trades else 0

    print("INSIGHT 2: Partial Profit Taking")
    print(f"  - Trades that took partials: {partial_win_rate:.1f}% win rate")
    print(f"  - Trades with NO partials: {no_partial_win_rate:.1f}% win rate")
    print(f"  - Partials indicate: Trade moved favorably enough to trigger threshold")
    print()

    # Insight 3: Duration correlation
    long_duration_trades = [p for p in paths if p['duration'] > 60]
    short_duration_trades = [p for p in paths if p['duration'] < 15]

    long_win_rate = sum(1 for t in long_duration_trades if t['pnl'] > 0) / len(long_duration_trades) * 100 if long_duration_trades else 0
    short_win_rate = sum(1 for t in short_duration_trades if t['pnl'] > 0) / len(short_duration_trades) * 100 if short_duration_trades else 0

    print("INSIGHT 3: Duration Pattern")
    print(f"  - Trades lasting >60 minutes: {long_win_rate:.1f}% win rate")
    print(f"  - Trades lasting <15 minutes: {short_win_rate:.1f}% win rate")
    print(f"  - Pattern: {'Winners run longer' if long_win_rate > short_win_rate else 'No clear pattern'}")
    print()

if __name__ == '__main__':
    main()
