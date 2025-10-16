#!/usr/bin/env python3
"""
Analyze which entry paths (MOMENTUM vs PULLBACK_RETEST vs SUSTAINED_BREAK)
were used for all losing trades in Sept 15, 2025 backtest.

Author: Claude Code
Date: October 14, 2025
"""

import json
import re
from collections import Counter
from datetime import datetime
import pytz

def parse_entry_reason(entry_reason):
    """
    Parse the entry reason to determine which path was taken.

    Returns: 'MOMENTUM', 'PULLBACK_RETEST', 'SUSTAINED_BREAK', or 'UNKNOWN'
    """
    if not entry_reason:
        return 'UNKNOWN'

    entry_reason_upper = entry_reason.upper()

    # Check for each path type
    if 'MOMENTUM_BREAKOUT' in entry_reason_upper:
        # Could be immediate or delayed momentum
        if 'DELAYED' in entry_reason_upper:
            return 'MOMENTUM_DELAYED'
        else:
            return 'MOMENTUM_IMMEDIATE'
    elif 'PULLBACK' in entry_reason_upper or 'RETEST' in entry_reason_upper:
        return 'PULLBACK_RETEST'
    elif 'SUSTAINED' in entry_reason_upper:
        return 'SUSTAINED_BREAK'
    else:
        return 'UNKNOWN'

def extract_candle_delay(entry_reason):
    """Extract the candle number from delayed momentum entries"""
    if 'candle' in entry_reason.lower():
        # Look for pattern like "on candle 30" or "candle 93"
        match = re.search(r'candle\s+(\d+)', entry_reason.lower())
        if match:
            return int(match.group(1))
    return None

def main():
    """Main analysis function"""

    print("="*100)
    print("📊 ENTRY PATH ANALYSIS - ALL LOSING TRADES")
    print("="*100)
    print()

    # Load trades
    trades_file = '/Users/karthik/projects/DayTrader/trader/backtest/results/backtest_trades_20250915.json'

    print(f"Loading trades from: {trades_file}")
    with open(trades_file) as f:
        trades = json.load(f)

    # Separate winners and losers
    losers = [t for t in trades if t['pnl'] < 0]
    winners = [t for t in trades if t['pnl'] > 0]

    print(f"Total trades: {len(trades)}")
    print(f"Winners: {len(winners)} ({len(winners)/len(trades)*100:.1f}%)")
    print(f"Losers: {len(losers)} ({len(losers)/len(trades)*100:.1f}%)")
    print()

    # Analyze entry paths for losers
    loser_paths = Counter()
    loser_path_details = {
        'MOMENTUM_IMMEDIATE': [],
        'MOMENTUM_DELAYED': [],
        'PULLBACK_RETEST': [],
        'SUSTAINED_BREAK': [],
        'UNKNOWN': []
    }

    for trade in losers:
        path = parse_entry_reason(trade.get('entry_reason', ''))
        loser_paths[path] += 1

        # Store trade details
        trade_info = {
            'symbol': trade['symbol'],
            'pnl': trade['pnl'],
            'entry_reason': trade.get('entry_reason', 'Unknown'),
            'duration_min': trade.get('duration_min', 0)
        }

        # Extract candle delay for delayed momentum
        if path == 'MOMENTUM_DELAYED':
            trade_info['candle_delay'] = extract_candle_delay(trade.get('entry_reason', ''))

        loser_path_details[path].append(trade_info)

    # Analyze entry paths for winners (for comparison)
    winner_paths = Counter()
    winner_path_details = {
        'MOMENTUM_IMMEDIATE': [],
        'MOMENTUM_DELAYED': [],
        'PULLBACK_RETEST': [],
        'SUSTAINED_BREAK': [],
        'UNKNOWN': []
    }

    for trade in winners:
        path = parse_entry_reason(trade.get('entry_reason', ''))
        winner_paths[path] += 1

        trade_info = {
            'symbol': trade['symbol'],
            'pnl': trade['pnl'],
            'entry_reason': trade.get('entry_reason', 'Unknown')
        }

        if path == 'MOMENTUM_DELAYED':
            trade_info['candle_delay'] = extract_candle_delay(trade.get('entry_reason', ''))

        winner_path_details[path].append(trade_info)

    # Print summary statistics
    print("="*100)
    print("📊 ENTRY PATH DISTRIBUTION - LOSING TRADES")
    print("="*100)

    total_losers = len(losers)
    for path in ['MOMENTUM_IMMEDIATE', 'MOMENTUM_DELAYED', 'PULLBACK_RETEST', 'SUSTAINED_BREAK', 'UNKNOWN']:
        count = loser_paths[path]
        if count > 0:
            pct = count / total_losers * 100
            avg_loss = sum(t['pnl'] for t in loser_path_details[path]) / count if count > 0 else 0

            print(f"\n{path}:")
            print(f"  Count: {count} ({pct:.1f}%)")
            print(f"  Average loss: ${avg_loss:.2f}")

            # For delayed momentum, show delay statistics
            if path == 'MOMENTUM_DELAYED':
                delays = [t['candle_delay'] for t in loser_path_details[path] if t.get('candle_delay')]
                if delays:
                    avg_delay = sum(delays) / len(delays)
                    max_delay = max(delays)
                    min_delay = min(delays)
                    print(f"  Candle delays: avg={avg_delay:.1f}, min={min_delay}, max={max_delay}")

            # Show worst 3 trades
            worst_trades = sorted(loser_path_details[path], key=lambda x: x['pnl'])[:3]
            print(f"  Worst trades:")
            for t in worst_trades:
                print(f"    {t['symbol']}: ${t['pnl']:.2f} ({t['duration_min']:.1f} min)")

    # Print comparison with winners
    print()
    print("="*100)
    print("📊 ENTRY PATH COMPARISON: WINNERS vs LOSERS")
    print("="*100)

    print(f"\n{'Path':<20} {'Winners':<20} {'Losers':<20} {'Win Rate':<15}")
    print("-"*75)

    for path in ['MOMENTUM_IMMEDIATE', 'MOMENTUM_DELAYED', 'PULLBACK_RETEST', 'SUSTAINED_BREAK', 'UNKNOWN']:
        w_count = winner_paths[path]
        l_count = loser_paths[path]
        total = w_count + l_count

        if total > 0:
            win_rate = w_count / total * 100
            w_str = f"{w_count} ({w_count/len(winners)*100:.1f}%)"
            l_str = f"{l_count} ({l_count/len(losers)*100:.1f}%)"
            wr_str = f"{win_rate:.1f}%"

            print(f"{path:<20} {w_str:<20} {l_str:<20} {wr_str:<15}")

    # Check if delayed momentum exists
    print()
    print("="*100)
    print("🔍 DETAILED ANALYSIS")
    print("="*100)

    # Analyze momentum entries
    momentum_total = loser_paths['MOMENTUM_IMMEDIATE'] + loser_paths['MOMENTUM_DELAYED']
    non_momentum = total_losers - momentum_total

    print(f"\n📈 Momentum vs Non-Momentum Losers:")
    print(f"  Momentum entries (immediate + delayed): {momentum_total} ({momentum_total/total_losers*100:.1f}%)")
    print(f"  Non-momentum entries: {non_momentum} ({non_momentum/total_losers*100:.1f}%)")

    if momentum_total > 0:
        momentum_losses = (
            sum(t['pnl'] for t in loser_path_details['MOMENTUM_IMMEDIATE']) +
            sum(t['pnl'] for t in loser_path_details['MOMENTUM_DELAYED'])
        )
        avg_momentum_loss = momentum_losses / momentum_total
        print(f"  Average momentum loss: ${avg_momentum_loss:.2f}")

    if non_momentum > 0:
        non_momentum_losses = sum(t['pnl'] for path in ['PULLBACK_RETEST', 'SUSTAINED_BREAK', 'UNKNOWN']
                                  for t in loser_path_details[path])
        avg_non_momentum_loss = non_momentum_losses / non_momentum if non_momentum > 0 else 0
        print(f"  Average non-momentum loss: ${avg_non_momentum_loss:.2f}")

    # Check if PULLBACK_RETEST dominates
    pullback_pct = loser_paths['PULLBACK_RETEST'] / total_losers * 100 if total_losers > 0 else 0

    print(f"\n⚠️  Key Findings:")

    if pullback_pct > 50:
        print(f"  ❌ PULLBACK_RETEST path accounts for {pullback_pct:.1f}% of all losers!")
        print(f"     This suggests the pullback/retest logic may be flawed")

    if loser_paths['MOMENTUM_DELAYED'] > loser_paths['MOMENTUM_IMMEDIATE']:
        print(f"  ❌ More delayed momentum losers ({loser_paths['MOMENTUM_DELAYED']}) than immediate ({loser_paths['MOMENTUM_IMMEDIATE']})")
        print(f"     Delayed momentum entries appear problematic")

    if momentum_total < non_momentum:
        print(f"  ❌ Most losers ({non_momentum_losses/total_losers*100:.1f}%) are NOT momentum entries")
        print(f"     Non-momentum entry paths need review")

    # Sample of each path type
    print()
    print("="*100)
    print("📝 SAMPLE TRADES BY PATH")
    print("="*100)

    for path in ['MOMENTUM_IMMEDIATE', 'MOMENTUM_DELAYED', 'PULLBACK_RETEST', 'SUSTAINED_BREAK']:
        if loser_path_details[path]:
            print(f"\n{path} Examples:")
            # Show first 3 trades
            for t in loser_path_details[path][:3]:
                reason = t['entry_reason']
                if len(reason) > 60:
                    reason = reason[:57] + "..."
                print(f"  {t['symbol']}: ${t['pnl']:.2f} - \"{reason}\"")

    # Save detailed results
    output = {
        'summary': {
            'total_losers': total_losers,
            'path_distribution': dict(loser_paths),
            'momentum_total': momentum_total,
            'non_momentum_total': non_momentum
        },
        'loser_details': loser_path_details,
        'winner_details': winner_path_details
    }

    output_file = '/Users/karthik/projects/DayTrader/trader/backtest/entry_path_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n💾 Detailed results saved to: {output_file}")

if __name__ == '__main__':
    main()