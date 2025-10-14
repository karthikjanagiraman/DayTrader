#!/usr/bin/env python3
"""
Analyze trade paths - categorize all trades by their behavior patterns
and calculate statistics for each path type.
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Define trade path categories
PATHS = {
    'IMMEDIATE_STOP': {
        'description': 'Hit stop within 5 minutes (instant failure)',
        'criteria': lambda t: t['reason'] == 'STOP' and t['duration_min'] <= 5
    },
    'QUICK_TIMEOUT': {
        'description': 'Hit 7-15 min timeout with small loss (<$100)',
        'criteria': lambda t: '15MIN_RULE' in t['reason'] and t['duration_min'] <= 15 and t['pnl'] < 0 and t['pnl'] > -100
    },
    'SLOW_BLEED': {
        'description': 'Hit timeout with large loss (>$100)',
        'criteria': lambda t: '15MIN_RULE' in t['reason'] and t['pnl'] <= -100
    },
    'TIMEOUT_SCRATCH': {
        'description': 'Hit timeout near breakeven (±$50)',
        'criteria': lambda t: '15MIN_RULE' in t['reason'] and abs(t['pnl']) <= 50
    },
    'TIMEOUT_WINNER': {
        'description': 'Hit timeout with profit',
        'criteria': lambda t: '15MIN_RULE' in t['reason'] and t['pnl'] > 50
    },
    'PARTIAL_WINNER': {
        'description': 'Took partials, exited via trailing stop',
        'criteria': lambda t: t['partials'] >= 1 and t['reason'] == 'TRAIL_STOP'
    },
    'LATE_STOP': {
        'description': 'Hit stop after 5+ minutes (slow reversal)',
        'criteria': lambda t: t['reason'] == 'STOP' and t['duration_min'] > 5
    },
    'EOD_EXIT': {
        'description': 'Held until end of day',
        'criteria': lambda t: t['reason'] == 'EOD'
    }
}

def load_trades(date_str):
    """Load trades from results file"""
    file_path = Path(__file__).parent / 'results' / f'backtest_trades_{date_str}.json'
    if not file_path.exists():
        return []
    with open(file_path) as f:
        return json.load(f)

def categorize_trade(trade):
    """Categorize a trade into one of the path types"""
    for path_name, path_def in PATHS.items():
        if path_def['criteria'](trade):
            return path_name
    return 'UNKNOWN'

def analyze_all_trades():
    """Analyze all trades from Oct 7-9 with both 7-min and 15-min rules"""

    print("="*80)
    print("TRADE PATH ANALYSIS - 7-MIN VS 15-MIN TIMEOUT RULE")
    print("="*80)
    print()

    dates = ['20251007', '20251008', '20251009']

    # Collect all trades
    all_trades_7min = []
    all_trades_15min = []

    for date in dates:
        trades = load_trades(date)
        all_trades_7min.extend(trades)
        all_trades_15min.extend(trades)  # Same data for now, will compare both

    print(f"Total trades loaded: {len(all_trades_7min)}")
    print()

    # Categorize trades by path
    path_stats = defaultdict(lambda: {
        'count': 0,
        'trades': [],
        'total_pnl': 0,
        'winners': 0,
        'losers': 0,
        'avg_duration': 0,
        'avg_pnl_pct': 0
    })

    for trade in all_trades_7min:
        path = categorize_trade(trade)
        stats = path_stats[path]
        stats['count'] += 1
        stats['trades'].append(trade)
        stats['total_pnl'] += trade['pnl']
        stats['avg_duration'] += trade['duration_min']
        stats['avg_pnl_pct'] += trade['pnl_pct']

        if trade['pnl'] > 0:
            stats['winners'] += 1
        else:
            stats['losers'] += 1

    # Calculate averages
    for path_name, stats in path_stats.items():
        if stats['count'] > 0:
            stats['avg_duration'] /= stats['count']
            stats['avg_pnl_pct'] /= stats['count']
            stats['avg_pnl'] = stats['total_pnl'] / stats['count']
            stats['win_rate'] = (stats['winners'] / stats['count']) * 100

    # Print results
    print("\n" + "="*80)
    print("PATH ANALYSIS - ALL TRADES")
    print("="*80)

    # Sort by count descending
    sorted_paths = sorted(path_stats.items(), key=lambda x: x[1]['count'], reverse=True)

    for path_name, stats in sorted_paths:
        if stats['count'] == 0:
            continue

        print(f"\n{'='*80}")
        print(f"PATH: {path_name}")
        print(f"Description: {PATHS.get(path_name, {}).get('description', 'Unknown')}")
        print(f"{'='*80}")
        print(f"Count:          {stats['count']} trades ({stats['count']/len(all_trades_7min)*100:.1f}% of all trades)")
        print(f"Win Rate:       {stats['win_rate']:.1f}% ({stats['winners']} winners, {stats['losers']} losers)")
        print(f"Total P&L:      ${stats['total_pnl']:,.2f}")
        print(f"Avg P&L:        ${stats['avg_pnl']:.2f}")
        print(f"Avg P&L %:      {stats['avg_pnl_pct']:.2f}%")
        print(f"Avg Duration:   {stats['avg_duration']:.1f} minutes")

        # Show example trades (first 3)
        print(f"\nExample Trades:")
        for i, trade in enumerate(stats['trades'][:3], 1):
            print(f"  {i}. {trade['symbol']} {trade['side']}: "
                  f"Entry ${trade['entry_price']:.2f} → Exit ${trade['exit_price']:.2f} "
                  f"({trade['duration_min']:.0f}min) = ${trade['pnl']:.2f} ({trade['pnl_pct']:.2f}%)")

    # Summary statistics
    print("\n" + "="*80)
    print("SUMMARY BY EXIT REASON")
    print("="*80)

    exit_reasons = defaultdict(lambda: {'count': 0, 'pnl': 0, 'winners': 0})
    for trade in all_trades_7min:
        reason = trade['reason']
        exit_reasons[reason]['count'] += 1
        exit_reasons[reason]['pnl'] += trade['pnl']
        if trade['pnl'] > 0:
            exit_reasons[reason]['winners'] += 1

    for reason, stats in sorted(exit_reasons.items(), key=lambda x: x[1]['count'], reverse=True):
        win_rate = (stats['winners'] / stats['count']) * 100 if stats['count'] > 0 else 0
        avg_pnl = stats['pnl'] / stats['count'] if stats['count'] > 0 else 0
        print(f"\n{reason}:")
        print(f"  Count:    {stats['count']} ({stats['count']/len(all_trades_7min)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Total P&L: ${stats['pnl']:,.2f}")
        print(f"  Avg P&L:   ${avg_pnl:.2f}")

    # Duration analysis
    print("\n" + "="*80)
    print("DURATION ANALYSIS")
    print("="*80)

    duration_buckets = {
        '0-5 min': [],
        '5-10 min': [],
        '10-15 min': [],
        '15-30 min': [],
        '30-60 min': [],
        '60+ min': []
    }

    for trade in all_trades_7min:
        dur = trade['duration_min']
        if dur <= 5:
            duration_buckets['0-5 min'].append(trade)
        elif dur <= 10:
            duration_buckets['5-10 min'].append(trade)
        elif dur <= 15:
            duration_buckets['10-15 min'].append(trade)
        elif dur <= 30:
            duration_buckets['15-30 min'].append(trade)
        elif dur <= 60:
            duration_buckets['30-60 min'].append(trade)
        else:
            duration_buckets['60+ min'].append(trade)

    for bucket_name, trades in duration_buckets.items():
        if not trades:
            continue

        total_pnl = sum(t['pnl'] for t in trades)
        winners = sum(1 for t in trades if t['pnl'] > 0)
        win_rate = (winners / len(trades)) * 100
        avg_pnl = total_pnl / len(trades)

        print(f"\n{bucket_name}:")
        print(f"  Count:    {len(trades)} ({len(trades)/len(all_trades_7min)*100:.1f}%)")
        print(f"  Win Rate: {win_rate:.1f}%")
        print(f"  Avg P&L:  ${avg_pnl:.2f}")
        print(f"  Total P&L: ${total_pnl:,.2f}")

    # Symbol analysis
    print("\n" + "="*80)
    print("TOP 5 BEST PERFORMING SYMBOLS")
    print("="*80)

    symbol_stats = defaultdict(lambda: {'pnl': 0, 'count': 0, 'winners': 0})
    for trade in all_trades_7min:
        symbol_stats[trade['symbol']]['pnl'] += trade['pnl']
        symbol_stats[trade['symbol']]['count'] += 1
        if trade['pnl'] > 0:
            symbol_stats[trade['symbol']]['winners'] += 1

    top_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)[:5]
    for symbol, stats in top_symbols:
        win_rate = (stats['winners'] / stats['count']) * 100
        print(f"\n{symbol}:")
        print(f"  Trades:    {stats['count']}")
        print(f"  Win Rate:  {win_rate:.1f}%")
        print(f"  Total P&L: ${stats['pnl']:.2f}")
        print(f"  Avg P&L:   ${stats['pnl']/stats['count']:.2f}")

    print("\n" + "="*80)
    print("TOP 5 WORST PERFORMING SYMBOLS")
    print("="*80)

    worst_symbols = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'])[:5]
    for symbol, stats in worst_symbols:
        win_rate = (stats['winners'] / stats['count']) * 100
        print(f"\n{symbol}:")
        print(f"  Trades:    {stats['count']}")
        print(f"  Win Rate:  {win_rate:.1f}%")
        print(f"  Total P&L: ${stats['pnl']:.2f}")
        print(f"  Avg P&L:   ${stats['pnl']/stats['count']:.2f}")

    # Side analysis (LONG vs SHORT)
    print("\n" + "="*80)
    print("LONG VS SHORT ANALYSIS")
    print("="*80)

    side_stats = defaultdict(lambda: {'count': 0, 'pnl': 0, 'winners': 0})
    for trade in all_trades_7min:
        side = trade['side']
        side_stats[side]['count'] += 1
        side_stats[side]['pnl'] += trade['pnl']
        if trade['pnl'] > 0:
            side_stats[side]['winners'] += 1

    for side in ['LONG', 'SHORT']:
        if side not in side_stats:
            continue
        stats = side_stats[side]
        win_rate = (stats['winners'] / stats['count']) * 100
        avg_pnl = stats['pnl'] / stats['count']
        print(f"\n{side}:")
        print(f"  Trades:    {stats['count']} ({stats['count']/len(all_trades_7min)*100:.1f}%)")
        print(f"  Win Rate:  {win_rate:.1f}%")
        print(f"  Total P&L: ${stats['pnl']:,.2f}")
        print(f"  Avg P&L:   ${avg_pnl:.2f}")

if __name__ == '__main__':
    analyze_all_trades()
