#!/usr/bin/env python3
"""
Deep Analysis of Blocked Winning Trades - October 21, 2025

This script analyzes all 23 blocked 5-star winners to understand:
1. Which filters blocked them
2. What were the exact filter values
3. Why those filter values resulted in blocks
4. Recommendations for filter adjustments
"""

import json
from datetime import datetime
from collections import defaultdict

# Load validation results
with open('validation/reports/validation_results_20251021.json') as f:
    validation_data = json.load(f)

# Load entry decisions
with open('backtest/results/backtest_entry_decisions_20251021.json') as f:
    entry_data = json.load(f)

# Extract only the 5-star winners that were blocked
blocked_winners = [
    b for b in validation_data['breakouts']
    if b['outcome']['star_rating'] == 5 and b['decision'] == 'BLOCKED'
]

print(f"""
================================================================================
DEEP ANALYSIS: BLOCKED 5-STAR WINNERS - October 21, 2025
================================================================================

Total 5-Star Winners Identified: {len(blocked_winners)}
All were BLOCKED by our filters

This represents approximately $15,000-25,000 in missed profit

================================================================================
""")

# Find matching entry attempts for each blocked winner
winner_details = []

for winner in blocked_winners:
    symbol = winner['symbol']
    timestamp_str = winner['timestamp']
    breakout_type = winner['type']
    price = winner['price']
    max_gain = winner['outcome']['max_gain_pct']

    # Convert timestamp to match entry_data format (strip timezone for comparison)
    breakout_time = datetime.fromisoformat(timestamp_str.replace('-04:00', '').replace('+00:00', ''))

    # Find all entry attempts for this symbol around this time (within 30 minutes)
    matching_attempts = []
    for attempt in entry_data['attempts']:
        # Strip timezone for comparison
        attempt_time = datetime.fromisoformat(attempt['timestamp'].replace('-04:00', '').replace('+00:00', ''))
        if (attempt['symbol'] == symbol and
            attempt['side'] == breakout_type and
            abs((attempt_time - breakout_time).total_seconds()) <= 1800):  # 30 min window
            matching_attempts.append(attempt)

    # Get the closest attempt
    if matching_attempts:
        closest_attempt = min(
            matching_attempts,
            key=lambda x: abs((datetime.fromisoformat(x['timestamp'].replace('-04:00', '').replace('+00:00', '')) - breakout_time).total_seconds())
        )

        winner_details.append({
            'symbol': symbol,
            'timestamp': timestamp_str,
            'type': breakout_type,
            'price': price,
            'max_gain_pct': max_gain,
            'entry_attempt': closest_attempt
        })

# Group by symbol
by_symbol = defaultdict(list)
for detail in winner_details:
    by_symbol[detail['symbol']].append(detail)

# Analyze each symbol
for symbol in sorted(by_symbol.keys()):
    trades = by_symbol[symbol]
    print(f"\n{'='*80}")
    print(f"{symbol} - {len(trades)} BLOCKED WINNERS")
    print(f"{'='*80}\n")

    for i, trade in enumerate(trades, 1):
        attempt = trade['entry_attempt']

        print(f"WINNER #{i} - {trade['type']} @ {trade['timestamp']}")
        print(f"  Entry Price: ${trade['price']:.2f}")
        print(f"  Max Gain: +{trade['max_gain_pct']:.2f}%")
        print(f"  Potential Profit: ${trade['max_gain_pct'] * 500:.0f} (est.)\n")

        print(f"  FILTER ANALYSIS:")
        filters = attempt.get('filters', {})

        # CVD Filter
        cvd = filters.get('cvd', {})
        if cvd.get('enabled'):
            result = cvd.get('result', 'UNKNOWN')
            if result == 'BLOCK':
                print(f"    ❌ CVD FILTER: BLOCKED")
                print(f"       CVD State: {cvd.get('cvd_state', 'N/A')}")
                print(f"       Reason: {cvd.get('reason', 'N/A')}")
                if 'imbalance_pct' in cvd:
                    print(f"       Imbalance: {cvd['imbalance_pct']:.1f}%")
                if 'monitoring_duration' in cvd:
                    print(f"       Monitoring Duration: {cvd['monitoring_duration']} candles")
            else:
                print(f"    ✅ CVD FILTER: {result}")

        # Choppy Filter
        choppy = filters.get('choppy', {})
        if choppy.get('enabled'):
            result = choppy.get('result', 'UNKNOWN')
            if result == 'BLOCK':
                print(f"    ❌ CHOPPY FILTER: BLOCKED")
                print(f"       Range: {choppy.get('range_pct', 0)*100:.2f}%")
                print(f"       Threshold: {choppy.get('threshold', 0)*100:.2f}%")
                print(f"       Reason: {choppy.get('reason', 'N/A')}")
            else:
                print(f"    ✅ CHOPPY FILTER: {result}")

        # Stochastic Filter
        stochastic = filters.get('stochastic', {})
        if stochastic.get('enabled'):
            result = stochastic.get('result', 'UNKNOWN')
            if result == 'BLOCK':
                print(f"    ❌ STOCHASTIC FILTER: BLOCKED")
                print(f"       K value: {stochastic.get('k_value', 'N/A')}")
                print(f"       Required range: {stochastic.get('required_range', 'N/A')}")
                print(f"       Reason: {stochastic.get('reason', 'N/A')}")
            else:
                print(f"    ✅ STOCHASTIC FILTER: {result}")

        # Room-to-Run Filter
        room = filters.get('room_to_run', {})
        if room.get('enabled'):
            result = room.get('result', 'UNKNOWN')
            if result == 'BLOCK':
                print(f"    ❌ ROOM-TO-RUN FILTER: BLOCKED")
                print(f"       Room to target: {room.get('room_pct', 0)*100:.2f}%")
                print(f"       Threshold: {room.get('threshold', 0)*100:.2f}%")
                print(f"       Target price: ${room.get('target_price', 0):.2f}")
                print(f"       Reason: {room.get('reason', 'N/A')}")
            else:
                print(f"    ✅ ROOM-TO-RUN FILTER: {result}")

        # Volume Filter
        volume = filters.get('volume', {})
        if volume.get('enabled'):
            result = volume.get('result', 'UNKNOWN')
            if result == 'BLOCK':
                print(f"    ❌ VOLUME FILTER: BLOCKED")
                print(f"       Volume ratio: {volume.get('volume_ratio', 0):.2f}x")
                print(f"       Required: {volume.get('required_ratio', 0):.2f}x")
                print(f"       Reason: {volume.get('reason', 'N/A')}")
            else:
                print(f"    ✅ VOLUME FILTER: {result}")

        # Overall decision
        print(f"\n  DECISION: {attempt.get('decision', 'UNKNOWN')}")
        print(f"  PHASE: {attempt.get('phase', 'UNKNOWN')}")
        print(f"  REASON: {attempt.get('reason', 'N/A')}")
        print(f"\n  {'-'*76}\n")

# Summary statistics
print(f"\n{'='*80}")
print("FILTER BLOCKING SUMMARY")
print(f"{'='*80}\n")

filter_blocks = defaultdict(int)
for detail in winner_details:
    filters = detail['entry_attempt'].get('filters', {})
    for filter_name, filter_data in filters.items():
        if isinstance(filter_data, dict) and filter_data.get('result') == 'BLOCK':
            filter_blocks[filter_name] += 1

print(f"Total Winners Analyzed: {len(winner_details)}\n")
print("Blocks by Filter:")
for filter_name, count in sorted(filter_blocks.items(), key=lambda x: x[1], reverse=True):
    pct = (count / len(winner_details)) * 100
    print(f"  {filter_name.upper()}: {count} blocks ({pct:.1f}%)")

# Recommendations
print(f"\n{'='*80}")
print("RECOMMENDATIONS")
print(f"{'='*80}\n")

if filter_blocks.get('cvd', 0) > 10:
    print("🚨 CVD FILTER - CRITICAL ISSUE")
    print(f"   Blocked {filter_blocks['cvd']} winners ({filter_blocks['cvd']/len(winner_details)*100:.1f}%)")
    print("   Recommendation: Disable or significantly loosen CVD monitoring")
    print("   Alternative: Use CVD as informational only, not blocking\n")

if filter_blocks.get('stochastic', 0) > 5:
    print("⚠️  STOCHASTIC FILTER - MAJOR ISSUE")
    print(f"   Blocked {filter_blocks['stochastic']} winners ({filter_blocks['stochastic']/len(winner_details)*100:.1f}%)")
    print("   Recommendation: Loosen stochastic ranges")
    print("   For SHORT: Expand range from K=20-50 to K=20-80")
    print("   For LONG: Expand range from K=60-80 to K=40-80\n")

if filter_blocks.get('volume', 0) > 5:
    print("⚠️  VOLUME FILTER - ISSUE")
    print(f"   Blocked {filter_blocks['volume']} winners ({filter_blocks['volume']/len(winner_details)*100:.1f}%)")
    print("   Recommendation: Lower volume threshold")
    print("   From 1.0x → 0.5x average volume\n")

if filter_blocks.get('room_to_run', 0) > 3:
    print("⚠️  ROOM-TO-RUN FILTER - MINOR ISSUE")
    print(f"   Blocked {filter_blocks['room_to_run']} winners ({filter_blocks['room_to_run']/len(winner_details)*100:.1f}%)")
    print("   Recommendation: Consider lowering threshold")
    print("   From 1.5% → 1.0%\n")

print(f"\n{'='*80}")
print("ESTIMATED IMPACT")
print(f"{'='*80}\n")

total_missed_gain = sum(d['max_gain_pct'] for d in winner_details)
avg_missed_gain = total_missed_gain / len(winner_details)

print(f"Total Missed Gain: {total_missed_gain:.2f}%")
print(f"Average Gain per Winner: {avg_missed_gain:.2f}%")
print(f"Estimated Missed Profit: ${total_missed_gain * 500:.0f} - ${total_missed_gain * 1000:.0f}")
print(f"\nWith proper filtering, Oct 21 could have been:")
print(f"  Actual P&L: -$284")
print(f"  Potential P&L: +$15,000 to +$25,000")
print(f"  Swing: +$15,284 to +$25,284")

print(f"\n{'='*80}")
print("END OF ANALYSIS")
print(f"{'='*80}\n")
