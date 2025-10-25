#!/usr/bin/env python3
"""
Test Candle-Based Stop Loss Logic (Oct 23, 2025)

Validates that candle-based stops work correctly for both LONG and SHORT entries
with various candle patterns.
"""
import sys
sys.path.insert(0, '/Users/karthik/projects/DayTrader/trader')

from strategy.ps60_strategy import PS60Strategy
import yaml
from datetime import datetime

class MockBar:
    """Mock bar object for testing"""
    def __init__(self, open_price, high, low, close):
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.date = datetime.now()
        self.volume = 1000

def create_test_config(stop_loss_method='candle'):
    """Create test configuration"""
    # Load the real config and modify just the stop loss method
    config_path = '/Users/karthik/projects/DayTrader/trader/config/trader_config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Override the stop loss method for testing
    config['trading']['risk']['stop_loss_method'] = stop_loss_method

    return config

def print_test_header(test_name):
    """Print test header"""
    print("\n" + "="*80)
    print(f"TEST: {test_name}")
    print("="*80)

def test_long_with_red_candle_before():
    """Test LONG entry with red candle before (should use red's LOW)"""
    print_test_header("LONG Entry: Red candle before entry")

    # Create bars: 2 green, 1 red, 2 green (entry on last green)
    bars = [
        MockBar(open_price=28.00, high=28.10, low=27.95, close=28.08),  # Green
        MockBar(open_price=28.08, high=28.20, low=28.05, close=28.18),  # Green
        MockBar(open_price=28.18, high=28.20, low=28.10, close=28.12),  # RED (close < open)
        MockBar(open_price=28.12, high=28.25, low=28.10, close=28.22),  # Green
        MockBar(open_price=28.22, high=28.35, low=28.20, close=28.30),  # Green - ENTRY
    ]

    config = create_test_config('candle')
    strategy = PS60Strategy(config)

    position = {
        'entry_price': 28.30,
        'side': 'LONG',
        'partials': 0,
        'pivot': 28.00  # Fallback pivot
    }

    stop = strategy.calculate_stop_price(
        position=position,
        stock_data=None,
        bars=bars,
        entry_bar_idx=4  # Last bar is entry
    )

    expected_stop = 28.10  # LOW of red candle at index 2
    print(f"\nCandles before entry:")
    for i, bar in enumerate(bars):
        color = "🟢 GREEN" if bar.close > bar.open else "🔴 RED"
        entry_marker = " ← ENTRY" if i == 4 else ""
        red_marker = " ← LAST RED (stop = LOW $28.10)" if i == 2 else ""
        print(f"  Bar {i}: O=${bar.open:.2f} H=${bar.high:.2f} L=${bar.low:.2f} C=${bar.close:.2f} {color}{red_marker}{entry_marker}")

    print(f"\nExpected stop: ${expected_stop:.2f} (LOW of last red candle)")
    print(f"Actual stop:   ${stop:.2f}")

    if abs(stop - expected_stop) < 0.01:
        print("✅ TEST PASSED")
        return True
    else:
        print("❌ TEST FAILED")
        return False

def test_short_with_green_candle_before():
    """Test SHORT entry with green candle before (should use green's HIGH)"""
    print_test_header("SHORT Entry: Green candle before entry")

    # Create bars: 2 red, 1 green, 2 red (entry on last red)
    bars = [
        MockBar(open_price=234.80, high=234.85, low=234.60, close=234.65),  # Red
        MockBar(open_price=234.65, high=234.70, low=234.50, close=234.55),  # Red
        MockBar(open_price=234.55, high=234.75, low=234.50, close=234.70),  # GREEN (close > open)
        MockBar(open_price=234.70, high=234.75, low=234.55, close=234.60),  # Red
        MockBar(open_price=234.60, high=234.65, low=234.45, close=234.50),  # Red - ENTRY
    ]

    config = create_test_config('candle')
    strategy = PS60Strategy(config)

    position = {
        'entry_price': 234.50,
        'side': 'SHORT',
        'partials': 0,
        'pivot': 235.00  # Fallback pivot
    }

    stop = strategy.calculate_stop_price(
        position=position,
        stock_data=None,
        bars=bars,
        entry_bar_idx=4  # Last bar is entry
    )

    expected_stop = 234.75  # HIGH of green candle at index 2
    print(f"\nCandles before entry:")
    for i, bar in enumerate(bars):
        color = "🟢 GREEN" if bar.close > bar.open else "🔴 RED"
        entry_marker = " ← ENTRY" if i == 4 else ""
        green_marker = " ← LAST GREEN (stop = HIGH $234.75)" if i == 2 else ""
        print(f"  Bar {i}: O=${bar.open:.2f} H=${bar.high:.2f} L=${bar.low:.2f} C=${bar.close:.2f} {color}{green_marker}{entry_marker}")

    print(f"\nExpected stop: ${expected_stop:.2f} (HIGH of last green candle)")
    print(f"Actual stop:   ${stop:.2f}")

    if abs(stop - expected_stop) < 0.01:
        print("✅ TEST PASSED")
        return True
    else:
        print("❌ TEST FAILED")
        return False

def test_long_all_green_fallback_to_pivot():
    """Test LONG entry with all green candles (should fallback to pivot)"""
    print_test_header("LONG Entry: All green candles (fallback to pivot)")

    # Create bars: All green leading to entry
    bars = [
        MockBar(open_price=28.00, high=28.10, low=27.95, close=28.08),  # Green
        MockBar(open_price=28.08, high=28.20, low=28.05, close=28.18),  # Green
        MockBar(open_price=28.18, high=28.30, low=28.15, close=28.28),  # Green
        MockBar(open_price=28.28, high=28.40, low=28.25, close=28.38),  # Green
        MockBar(open_price=28.38, high=28.50, low=28.35, close=28.48),  # Green - ENTRY
    ]

    config = create_test_config('candle')
    strategy = PS60Strategy(config)

    pivot = 28.00
    position = {
        'entry_price': 28.48,
        'side': 'LONG',
        'partials': 0,
        'pivot': pivot
    }

    stop = strategy.calculate_stop_price(
        position=position,
        stock_data=None,
        bars=bars,
        entry_bar_idx=4
    )

    print(f"\nCandles before entry:")
    for i, bar in enumerate(bars):
        color = "🟢 GREEN" if bar.close > bar.open else "🔴 RED"
        entry_marker = " ← ENTRY" if i == 4 else ""
        print(f"  Bar {i}: O=${bar.open:.2f} H=${bar.high:.2f} L=${bar.low:.2f} C=${bar.close:.2f} {color}{entry_marker}")

    print(f"\nNo red candles found → Falling back to pivot")
    print(f"Expected stop: ${pivot:.2f} (pivot/resistance)")
    print(f"Actual stop:   ${stop:.2f}")

    if abs(stop - pivot) < 0.01:
        print("✅ TEST PASSED")
        return True
    else:
        print("❌ TEST FAILED")
        return False

def test_short_all_red_fallback_to_pivot():
    """Test SHORT entry with all red candles (should fallback to pivot)"""
    print_test_header("SHORT Entry: All red candles (fallback to pivot)")

    # Create bars: All red leading to entry
    bars = [
        MockBar(open_price=234.80, high=234.85, low=234.70, close=234.75),  # Red
        MockBar(open_price=234.75, high=234.80, low=234.60, close=234.65),  # Red
        MockBar(open_price=234.65, high=234.70, low=234.50, close=234.55),  # Red
        MockBar(open_price=234.55, high=234.60, low=234.40, close=234.45),  # Red
        MockBar(open_price=234.45, high=234.50, low=234.30, close=234.35),  # Red - ENTRY
    ]

    config = create_test_config('candle')
    strategy = PS60Strategy(config)

    pivot = 235.00
    position = {
        'entry_price': 234.35,
        'side': 'SHORT',
        'partials': 0,
        'pivot': pivot
    }

    stop = strategy.calculate_stop_price(
        position=position,
        stock_data=None,
        bars=bars,
        entry_bar_idx=4
    )

    print(f"\nCandles before entry:")
    for i, bar in enumerate(bars):
        color = "🟢 GREEN" if bar.close > bar.open else "🔴 RED"
        entry_marker = " ← ENTRY" if i == 4 else ""
        print(f"  Bar {i}: O=${bar.open:.2f} H=${bar.high:.2f} L=${bar.low:.2f} C=${bar.close:.2f} {color}{entry_marker}")

    print(f"\nNo green candles found → Falling back to pivot")
    print(f"Expected stop: ${pivot:.2f} (pivot/support)")
    print(f"Actual stop:   ${stop:.2f}")

    if abs(stop - pivot) < 0.01:
        print("✅ TEST PASSED")
        return True
    else:
        print("❌ TEST FAILED")
        return False

def test_config_switch_atr_vs_candle():
    """Test switching between ATR and candle-based stops via config"""
    print_test_header("Config Switch: ATR vs Candle-based stops")

    bars = [
        MockBar(open_price=28.00, high=28.10, low=27.95, close=28.08),
        MockBar(open_price=28.08, high=28.20, low=28.05, close=28.12),  # RED
        MockBar(open_price=28.12, high=28.30, low=28.10, close=28.25),  # Green - ENTRY
    ]

    stock_data = {'atr%': 4.5}  # Medium volatility → 1.2% ATR stop

    position = {
        'entry_price': 28.25,
        'side': 'LONG',
        'partials': 0,
        'pivot': 28.00
    }

    # Test 1: Candle-based method
    print("\n--- Method: CANDLE ---")
    config_candle = create_test_config('candle')
    strategy_candle = PS60Strategy(config_candle)

    stop_candle = strategy_candle.calculate_stop_price(
        position=position,
        stock_data=stock_data,
        bars=bars,
        entry_bar_idx=2
    )

    expected_candle_stop = 28.05  # LOW of red candle
    print(f"Expected stop: ${expected_candle_stop:.2f} (LOW of red candle)")
    print(f"Actual stop:   ${stop_candle:.2f}")

    # Test 2: ATR-based method
    print("\n--- Method: ATR ---")
    config_atr = create_test_config('atr')
    strategy_atr = PS60Strategy(config_atr)

    stop_atr = strategy_atr.calculate_stop_price(
        position=position,
        stock_data=stock_data,
        bars=bars,
        entry_bar_idx=2
    )

    # ATR: 4.5% → 1.2% stop width → 28.25 * (1 - 0.012) = 27.911
    expected_atr_stop = 28.25 * (1 - 0.012)
    print(f"Expected stop: ${expected_atr_stop:.2f} (ATR-based 1.2%)")
    print(f"Actual stop:   ${stop_atr:.2f}")

    # Validate both methods work correctly
    candle_ok = abs(stop_candle - expected_candle_stop) < 0.01
    atr_ok = abs(stop_atr - expected_atr_stop) < 0.01
    different_methods = abs(stop_candle - stop_atr) > 0.10  # Should be different

    if candle_ok and atr_ok and different_methods:
        print("\n✅ TEST PASSED - Both methods work and produce different results")
        return True
    else:
        print("\n❌ TEST FAILED")
        print(f"  Candle OK: {candle_ok}")
        print(f"  ATR OK: {atr_ok}")
        print(f"  Different: {different_methods}")
        return False

def run_all_tests():
    """Run all candle-based stop loss tests"""
    print("\n" + "="*80)
    print("CANDLE-BASED STOP LOSS TEST SUITE")
    print("October 23, 2025")
    print("="*80)

    tests = [
        ("LONG with red candle", test_long_with_red_candle_before),
        ("SHORT with green candle", test_short_with_green_candle_before),
        ("LONG all green (fallback)", test_long_all_green_fallback_to_pivot),
        ("SHORT all red (fallback)", test_short_all_red_fallback_to_pivot),
        ("Config switch (ATR vs Candle)", test_config_switch_atr_vs_candle),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ TEST CRASHED: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\nResults: {passed}/{total} tests passed ({passed/total*100:.1f}%)")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
