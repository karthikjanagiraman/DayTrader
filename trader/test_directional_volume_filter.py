#!/usr/bin/env python3
"""
Test Directional Volume Filter (Oct 14, 2025)

Tests the new directional volume filter that checks if volume spikes
confirm movement in the intended trade direction.

GS Trade Case Study:
- Entry: 9:45:06 AM, SHORT @ $744.21
- Support: $758.00 (price 1.82% below support)
- Volume: 2.0x average (HIGH)
- Candle: 0.2% size

Problem: Price was bouncing UP from earlier lows (~$742 to $744)
- High volume was confirming UPWARD movement (green candle)
- System entered SHORT into this UPWARD bounce
- This is a "dead cat bounce" entry - worst possible timing

Fix: Check candle direction before entering
- For SHORT: Require RED candle (close < open) = selling pressure
- For LONG: Require GREEN candle (close > open) = buying pressure
"""

import sys
from pathlib import Path
import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from strategy.ps60_strategy import PS60Strategy
from ib_insync import util
from datetime import datetime


def load_config():
    """Load actual trader config"""
    config_path = Path(__file__).parent / 'config' / 'trader_config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)
    # Disable some filters for focused testing
    if 'filters' not in config:
        config['filters'] = {}
    config['filters']['enable_entry_position_filter'] = False

    if 'trading' not in config:
        config['trading'] = {}
    config['trading']['enable_rsi_filter'] = False
    config['trading']['enable_macd_filter'] = False
    return config


class MockBar:
    """Mock IBKR bar for testing"""
    def __init__(self, date, open_price, high, low, close, volume):
        self.date = date
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.average = (high + low) / 2
        self.barCount = 1


def test_gs_short_scenario():
    """Test the actual GS scenario from Oct 14, 2025"""
    print("\n" + "="*80)
    print("TEST 1: GS SHORT Scenario (Oct 14, 2025 - 9:45 AM)")
    print("="*80)

    # Load actual trader config
    config = load_config()
    strategy = PS60Strategy(config)

    # Create bar sequence simulating GS movement on Oct 14
    # Price dropped from $758 (support) to $742, then bounced back to $744
    bars = []
    base_time = datetime(2025, 10, 14, 9, 44, 0)

    # Build up bars before the breakout (60 bars = 5 minutes at 5-sec bars)
    for i in range(60):
        # Simulate price dropping from $758 to $742
        price = 758.0 - (i * 0.27)  # Gradual decline
        bars.append(MockBar(
            date=base_time,
            open_price=price,
            high=price + 0.10,
            low=price - 0.10,
            close=price - 0.05,
            volume=1000  # Normal volume
        ))

    # Now simulate the BOUNCE at 9:45 AM (the problematic candle)
    # Price bouncing UP from $742 to $744 with HIGH volume
    # This is a GREEN candle (close > open) with 2.0x volume
    for i in range(12):  # 12 bars = 1 minute at 5-sec bars
        open_price = 742.0 + (i * 0.17)  # Rising from $742
        close_price = open_price + 0.15  # GREEN candle (close > open)

        bars.append(MockBar(
            date=base_time,
            open_price=open_price,
            high=close_price + 0.05,
            low=open_price - 0.05,
            close=close_price,
            volume=2000  # 2.0x volume (HIGH)
        ))

    # Test entry at the end of the bounce candle
    current_idx = len(bars) - 1
    support_price = 758.00
    current_price = bars[current_idx].close  # Should be ~$744

    print(f"\nScenario Setup:")
    print(f"  Support: ${support_price:.2f}")
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  Distance from Support: {((support_price - current_price) / support_price) * 100:.2f}%")
    print(f"  Candle Open: ${bars[current_idx - 11].open:.2f}")
    print(f"  Candle Close: ${bars[current_idx].close:.2f}")
    print(f"  Candle Direction: {'🟢 GREEN (UPWARD)' if bars[current_idx].close > bars[current_idx - 11].open else '🔴 RED (DOWNWARD)'}")
    print(f"  Volume Ratio: 2.0x (HIGH)")

    # Test SHORT entry
    confirmed, reason, state = strategy.check_hybrid_entry(
        bars, current_idx, support_price, side='SHORT',
        target_price=700.0,  # Dummy target
        symbol='GS'
    )

    print(f"\nResult:")
    print(f"  Entry Confirmed: {confirmed}")
    print(f"  Reason: {reason}")
    print(f"  State: {state.get('phase', 'N/A')}")

    if not confirmed and 'directional_volume_filter' in str(state.get('phase', '')):
        print(f"\n✅ SUCCESS: Directional volume filter BLOCKED the bad entry!")
        print(f"   Filter correctly detected upward bounce with volume")
        return True
    elif confirmed:
        print(f"\n❌ FAILURE: System would still enter this bad trade")
        print(f"   This is the GS loss scenario ($-23.58)")
        return False
    else:
        print(f"\n⚠️  BLOCKED but for different reason: {reason}")
        return False


def test_valid_short_scenario():
    """Test a valid SHORT scenario - downward breakdown with volume"""
    print("\n" + "="*80)
    print("TEST 2: Valid SHORT Scenario (Downward Breakdown)")
    print("="*80)

    config = {
        'confirmation': {
            'momentum_volume_threshold': 2.0,
            'momentum_candle_min_pct': 0.002,
            'momentum_candle_min_atr': 0.0,
            'enable_choppy_filter': False,
        },
        'filters': {
            'enable_entry_position_filter': False,
        },
        'trading': {
            'enable_rsi_filter': False,
            'enable_macd_filter': False,
            'entry': {
                'min_entry_time': '09:30',
                'max_entry_time': '15:00'
            }
        }
    }
    strategy = PS60Strategy(config)

    bars = []
    base_time = datetime(2025, 10, 14, 10, 0, 0)

    # Build up bars at support
    for i in range(60):
        bars.append(MockBar(
            date=base_time,
            open_price=758.0,
            high=759.0,
            low=757.0,
            close=758.0,
            volume=1000
        ))

    # Simulate DOWNWARD breakdown with volume (RED candle)
    for i in range(12):
        open_price = 758.0 - (i * 0.20)  # Falling from $758
        close_price = open_price - 0.18  # RED candle (close < open)

        bars.append(MockBar(
            date=base_time,
            open_price=open_price,
            high=open_price + 0.05,
            low=close_price - 0.05,
            close=close_price,
            volume=2000  # 2.0x volume
        ))

    current_idx = len(bars) - 1
    support_price = 758.00
    current_price = bars[current_idx].close

    print(f"\nScenario Setup:")
    print(f"  Support: ${support_price:.2f}")
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  Candle Open: ${bars[current_idx - 11].open:.2f}")
    print(f"  Candle Close: ${bars[current_idx].close:.2f}")
    print(f"  Candle Direction: {'🟢 GREEN (UPWARD)' if bars[current_idx].close > bars[current_idx - 11].open else '🔴 RED (DOWNWARD)'}")
    print(f"  Volume Ratio: 2.0x (HIGH)")

    confirmed, reason, state = strategy.check_hybrid_entry(
        bars, current_idx, support_price, side='SHORT',
        target_price=700.0,
        symbol='TEST'
    )

    print(f"\nResult:")
    print(f"  Entry Confirmed: {confirmed}")
    print(f"  Reason: {reason}")

    if confirmed:
        print(f"\n✅ SUCCESS: Valid SHORT entry was ALLOWED")
        print(f"   Downward breakdown with volume confirmed")
        return True
    else:
        print(f"\n❌ FAILURE: Valid entry was blocked: {reason}")
        return False


def test_valid_long_scenario():
    """Test a valid LONG scenario - upward breakout with volume"""
    print("\n" + "="*80)
    print("TEST 3: Valid LONG Scenario (Upward Breakout)")
    print("="*80)

    config = {
        'confirmation': {
            'momentum_volume_threshold': 2.0,
            'momentum_candle_min_pct': 0.002,
            'momentum_candle_min_atr': 0.0,
            'enable_choppy_filter': False,
        },
        'filters': {
            'enable_entry_position_filter': False,
        },
        'trading': {
            'enable_rsi_filter': False,
            'enable_macd_filter': False,
            'entry': {
                'min_entry_time': '09:30',
                'max_entry_time': '15:00'
            }
        }
    }
    strategy = PS60Strategy(config)

    bars = []
    base_time = datetime(2025, 10, 14, 10, 30, 0)

    # Build up bars at resistance
    for i in range(60):
        bars.append(MockBar(
            date=base_time,
            open_price=445.0,
            high=446.0,
            low=444.0,
            close=445.0,
            volume=1000
        ))

    # Simulate UPWARD breakout with volume (GREEN candle)
    for i in range(12):
        open_price = 445.0 + (i * 0.20)  # Rising from $445
        close_price = open_price + 0.18  # GREEN candle (close > open)

        bars.append(MockBar(
            date=base_time,
            open_price=open_price,
            high=close_price + 0.05,
            low=open_price - 0.05,
            close=close_price,
            volume=2000  # 2.0x volume
        ))

    current_idx = len(bars) - 1
    resistance_price = 445.00
    current_price = bars[current_idx].close

    print(f"\nScenario Setup:")
    print(f"  Resistance: ${resistance_price:.2f}")
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  Candle Open: ${bars[current_idx - 11].open:.2f}")
    print(f"  Candle Close: ${bars[current_idx].close:.2f}")
    print(f"  Candle Direction: {'🟢 GREEN (UPWARD)' if bars[current_idx].close > bars[current_idx - 11].open else '🔴 RED (DOWNWARD)'}")
    print(f"  Volume Ratio: 2.0x (HIGH)")

    confirmed, reason, state = strategy.check_hybrid_entry(
        bars, current_idx, resistance_price, side='LONG',
        target_price=450.0,
        symbol='TEST'
    )

    print(f"\nResult:")
    print(f"  Entry Confirmed: {confirmed}")
    print(f"  Reason: {reason}")

    if confirmed:
        print(f"\n✅ SUCCESS: Valid LONG entry was ALLOWED")
        print(f"   Upward breakout with volume confirmed")
        return True
    else:
        print(f"\n❌ FAILURE: Valid entry was blocked: {reason}")
        return False


def test_invalid_long_scenario():
    """Test an invalid LONG scenario - pullback down with volume"""
    print("\n" + "="*80)
    print("TEST 4: Invalid LONG Scenario (Downward Pullback)")
    print("="*80)

    config = {
        'confirmation': {
            'momentum_volume_threshold': 2.0,
            'momentum_candle_min_pct': 0.002,
            'momentum_candle_min_atr': 0.0,
            'enable_choppy_filter': False,
        },
        'filters': {
            'enable_entry_position_filter': False,
        },
        'trading': {
            'enable_rsi_filter': False,
            'enable_macd_filter': False,
            'entry': {
                'min_entry_time': '09:30',
                'max_entry_time': '15:00'
            }
        }
    }
    strategy = PS60Strategy(config)

    bars = []
    base_time = datetime(2025, 10, 14, 11, 0, 0)

    # Build up bars
    for i in range(60):
        bars.append(MockBar(
            date=base_time,
            open_price=445.0,
            high=446.0,
            low=444.0,
            close=445.0,
            volume=1000
        ))

    # Simulate price above resistance but PULLING BACK down (RED candle)
    # This is like a failed breakout - price went above resistance then reversed
    for i in range(12):
        open_price = 447.0 - (i * 0.15)  # Falling from $447
        close_price = open_price - 0.12  # RED candle (close < open)

        bars.append(MockBar(
            date=base_time,
            open_price=open_price,
            high=open_price + 0.05,
            low=close_price - 0.05,
            close=close_price,
            volume=2000  # 2.0x volume
        ))

    current_idx = len(bars) - 1
    resistance_price = 445.00
    current_price = bars[current_idx].close

    print(f"\nScenario Setup:")
    print(f"  Resistance: ${resistance_price:.2f}")
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  Candle Open: ${bars[current_idx - 11].open:.2f}")
    print(f"  Candle Close: ${bars[current_idx].close:.2f}")
    print(f"  Candle Direction: {'🟢 GREEN (UPWARD)' if bars[current_idx].close > bars[current_idx - 11].open else '🔴 RED (DOWNWARD)'}")
    print(f"  Volume Ratio: 2.0x (HIGH)")

    confirmed, reason, state = strategy.check_hybrid_entry(
        bars, current_idx, resistance_price, side='LONG',
        target_price=450.0,
        symbol='TEST'
    )

    print(f"\nResult:")
    print(f"  Entry Confirmed: {confirmed}")
    print(f"  Reason: {reason}")

    if not confirmed and 'directional_volume_filter' in str(state.get('phase', '')):
        print(f"\n✅ SUCCESS: Directional volume filter BLOCKED the bad entry!")
        print(f"   Filter correctly detected downward pullback with volume")
        return True
    elif confirmed:
        print(f"\n❌ FAILURE: System would enter this bad trade")
        return False
    else:
        print(f"\n⚠️  BLOCKED but for different reason: {reason}")
        return False


if __name__ == '__main__':
    print("\n" + "="*80)
    print("DIRECTIONAL VOLUME FILTER TEST SUITE")
    print("="*80)
    print("Testing filter that prevents entering on pullbacks/bounces")
    print("with volume in the opposite direction of intended trade")

    # Run all tests
    test1 = test_gs_short_scenario()
    test2 = test_valid_short_scenario()
    test3 = test_valid_long_scenario()
    test4 = test_invalid_long_scenario()

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Test 1 (GS Bad SHORT):     {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"Test 2 (Valid SHORT):      {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"Test 3 (Valid LONG):       {'✅ PASS' if test3 else '❌ FAIL'}")
    print(f"Test 4 (Bad LONG):         {'✅ PASS' if test4 else '❌ FAIL'}")
    print(f"\nOverall: {'✅ ALL TESTS PASSED' if all([test1, test2, test3, test4]) else '❌ SOME TESTS FAILED'}")
    print("="*80)
