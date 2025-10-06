#!/usr/bin/env python3
"""
Test gap filter logic to ensure it correctly identifies gaps through pivots
"""

import sys
sys.path.insert(0, '/Users/karthik/projects/DayTrader/trader')

from strategy.ps60_strategy import PS60Strategy
import yaml

# Load config
with open('/Users/karthik/projects/DayTrader/trader/config/trader_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

strategy = PS60Strategy(config)

# Test cases
print("=" * 80)
print("GAP FILTER TEST CASES")
print("=" * 80)

# Test 1: Small gap through resistance (should allow)
print("\nTest 1: Small gap through resistance (0.8%)")
stock1 = {
    'symbol': 'TEST1',
    'close': 100.0,
    'resistance': 102.0,
    'support': 98.0,
    'target1': 110.0
}
current_price = 102.8  # 0.78% above resistance
should_enter, reason = strategy.should_enter_long(stock1, current_price, 0)
print(f"  Close: ${stock1['close']}, Resistance: ${stock1['resistance']}")
print(f"  Current: ${current_price} (gap through: {((current_price - stock1['resistance']) / stock1['resistance'] * 100):.1f}%)")
print(f"  Room to target: {((stock1['target1'] - current_price) / current_price * 100):.1f}%")
print(f"  Result: {'✅ ENTER' if should_enter else '❌ SKIP'} - {reason or 'OK'}")

# Test 2: Large gap with room (should allow)
print("\nTest 2: Large gap through resistance (2.0%) but room to target (5%)")
stock2 = {
    'symbol': 'TEST2',
    'close': 100.0,
    'resistance': 102.0,
    'support': 98.0,
    'target1': 109.0
}
current_price = 104.0  # 1.96% above resistance
should_enter, reason = strategy.should_enter_long(stock2, current_price, 0)
print(f"  Close: ${stock2['close']}, Resistance: ${stock2['resistance']}")
print(f"  Current: ${current_price} (gap through: {((current_price - stock2['resistance']) / stock2['resistance'] * 100):.1f}%)")
print(f"  Room to target: {((stock2['target1'] - current_price) / current_price * 100):.1f}%")
print(f"  Result: {'✅ ENTER' if should_enter else '❌ SKIP'} - {reason or 'OK'}")

# Test 3: Large gap without room (should skip)
print("\nTest 3: Large gap through resistance (2.0%) with no room to target (1.5%)")
stock3 = {
    'symbol': 'TEST3',
    'close': 100.0,
    'resistance': 102.0,
    'support': 98.0,
    'target1': 105.5
}
current_price = 104.0  # 1.96% above resistance
should_enter, reason = strategy.should_enter_long(stock3, current_price, 0)
print(f"  Close: ${stock3['close']}, Resistance: ${stock3['resistance']}")
print(f"  Current: ${current_price} (gap through: {((current_price - stock3['resistance']) / stock3['resistance'] * 100):.1f}%)")
print(f"  Room to target: {((stock3['target1'] - current_price) / current_price * 100):.1f}%")
print(f"  Result: {'✅ ENTER' if should_enter else '❌ SKIP'} - {reason or 'OK'}")

# Test 4: CLOV-like scenario (gap ate up move)
print("\nTest 4: CLOV-like scenario (gap through resistance, minimal room left)")
stock4 = {
    'symbol': 'CLOV',
    'close': 2.70,
    'resistance': 3.24,
    'support': 2.62,
    'target1': 3.40
}
current_price = 3.30  # Gapped through resistance, opened at $3.30
should_enter, reason = strategy.should_enter_long(stock4, current_price, 0)
print(f"  Close: ${stock4['close']}, Resistance: ${stock4['resistance']}")
print(f"  Current: ${current_price} (gap through: {((current_price - stock4['resistance']) / stock4['resistance'] * 100):.1f}%)")
print(f"  Room to target: {((stock4['target1'] - current_price) / current_price * 100):.1f}%")
print(f"  Result: {'✅ ENTER' if should_enter else '❌ SKIP'} - {reason or 'OK'}")

# Test 5: No gap (normal entry)
print("\nTest 5: No gap, normal pivot break")
stock5 = {
    'symbol': 'NORMAL',
    'close': 100.0,
    'resistance': 102.0,
    'support': 98.0,
    'target1': 110.0
}
current_price = 102.1  # Just above resistance
should_enter, reason = strategy.should_enter_long(stock5, current_price, 0)
print(f"  Close: ${stock5['close']}, Resistance: ${stock5['resistance']}")
print(f"  Current: ${current_price} (no gap, price was below before)")
print(f"  Room to target: {((stock5['target1'] - current_price) / current_price * 100):.1f}%")
print(f"  Result: {'✅ ENTER' if should_enter else '❌ SKIP'} - {reason or 'OK'}")

print("\n" + "=" * 80)
print("Gap filter configuration:")
print(f"  enable_gap_filter: {config['filters'].get('enable_gap_filter', True)}")
print(f"  max_gap_through_pivot: {config['filters'].get('max_gap_through_pivot', 1.0)}%")
print(f"  min_room_to_target: {config['filters'].get('min_room_to_target', 3.0)}%")
print("=" * 80)
