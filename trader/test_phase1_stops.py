#!/usr/bin/env python3
"""
Test Phase 1: Minimum Stop Distance Logic
Verifies stop widening is working correctly for momentum, pullback, and bounce setups
"""

import sys
from typing import Tuple

# Test cases from October 9, 2025 backtest
TEST_CASES = [
    {
        'name': 'AVGO Momentum Long',
        'setup_type': 'MOMENTUM',
        'side': 'LONG',
        'entry': 347.61,
        'pivot': 347.10,
        'expected_stop': 345.87,  # 0.5% below entry
        'expected_distance_pct': 0.5,
        'description': 'Tight pivot (0.15% away) should widen to 0.5% minimum'
    },
    {
        'name': 'COIN Pullback Long',
        'setup_type': 'PULLBACK',
        'side': 'LONG',
        'entry': 391.77,
        'pivot': 390.49,
        'expected_stop': 390.49,  # Pivot wider than 0.3% min
        'expected_distance_pct': 0.33,
        'description': 'Pivot already 0.33% away, use pivot (wider than 0.3% min)'
    },
    {
        'name': 'GS Rejection Short',
        'setup_type': 'REJECTION',
        'side': 'SHORT',
        'entry': 528.42,
        'pivot': 530.14,
        'expected_stop': 530.53,  # 0.4% above entry
        'expected_distance_pct': 0.4,
        'description': 'Tight pivot (0.33% away) should widen to 0.4% minimum'
    },
    {
        'name': 'Very Tight Pivot Test',
        'setup_type': 'MOMENTUM',
        'side': 'LONG',
        'entry': 100.10,
        'pivot': 100.05,  # Only 0.05% away!
        'expected_stop': 99.60,  # 0.5% minimum
        'expected_distance_pct': 0.5,
        'description': 'Extremely tight pivot (0.05%) must widen to 0.5%'
    },
    {
        'name': 'Bounce Setup',
        'setup_type': 'BOUNCE',
        'side': 'LONG',
        'entry': 250.00,
        'pivot': 248.00,  # 0.8% away
        'expected_stop': 248.00,  # Pivot wider than 0.4% min, use pivot
        'expected_distance_pct': 0.8,
        'description': 'Bounce pivot 0.8% away, already wider than 0.4% min - use pivot'
    }
]

def calculate_stop(setup_type: str, side: str, entry: float, pivot: float) -> Tuple[float, float]:
    """
    Calculate stop price using Phase 1 minimum stop distance logic

    Returns: (stop_price, distance_pct)
    """

    # PHASE 1 FIX (Oct 9, 2025): Enforce minimum stop distances
    MOMENTUM_MIN_STOP_PCT = 0.005  # 0.5% for momentum breakouts
    PULLBACK_MIN_STOP_PCT = 0.003  # 0.3% for pullback/retest
    BOUNCE_MIN_STOP_PCT = 0.004    # 0.4% for bounce setups
    REJECTION_MIN_STOP_PCT = 0.004 # 0.4% for rejection setups

    # Determine minimum stop distance based on setup type
    if setup_type == 'MOMENTUM' or setup_type == 'BREAKOUT':
        min_stop_pct = MOMENTUM_MIN_STOP_PCT
    elif setup_type == 'BOUNCE':
        min_stop_pct = BOUNCE_MIN_STOP_PCT
    elif setup_type == 'REJECTION':
        min_stop_pct = REJECTION_MIN_STOP_PCT
    else:  # PULLBACK or other
        min_stop_pct = PULLBACK_MIN_STOP_PCT

    if side == 'LONG':
        # Calculate minimum stop price (BELOW entry for longs)
        min_stop_price = entry * (1 - min_stop_pct)

        # Use the LOWER of base_stop or min_stop (provides more protection)
        stop_price = min(pivot, min_stop_price)

        # Calculate distance
        distance_pct = ((entry - stop_price) / entry) * 100

    else:  # SHORT
        # Calculate minimum stop price (ABOVE entry for shorts)
        min_stop_price = entry * (1 + min_stop_pct)

        # Use the HIGHER of base_stop or min_stop (provides more protection for shorts)
        stop_price = max(pivot, min_stop_price)

        # Calculate distance
        distance_pct = ((stop_price - entry) / entry) * 100

    return stop_price, distance_pct


def run_tests():
    """Run all Phase 1 stop calculation tests"""

    print("=" * 80)
    print("PHASE 1 STOP WIDENING TESTS")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for test in TEST_CASES:
        print(f"Test: {test['name']}")
        print(f"Description: {test['description']}")
        print(f"Setup: {test['setup_type']} {test['side']} @ ${test['entry']:.2f}, pivot ${test['pivot']:.2f}")
        print()

        # Calculate stop using Phase 1 logic
        actual_stop, actual_distance_pct = calculate_stop(
            test['setup_type'],
            test['side'],
            test['entry'],
            test['pivot']
        )

        # Check if stop price matches expected
        stop_match = abs(actual_stop - test['expected_stop']) < 0.01

        # Check if distance matches expected (within 0.01%)
        distance_match = abs(actual_distance_pct - test['expected_distance_pct']) < 0.01

        # Results
        print(f"Expected Stop: ${test['expected_stop']:.2f} ({test['expected_distance_pct']:.2f}% away)")
        print(f"Actual Stop:   ${actual_stop:.2f} ({actual_distance_pct:.2f}% away)")

        if stop_match and distance_match:
            print("✅ PASS")
            passed += 1
        else:
            print("❌ FAIL")
            failed += 1
            if not stop_match:
                print(f"   Stop price mismatch: expected ${test['expected_stop']:.2f}, got ${actual_stop:.2f}")
            if not distance_match:
                print(f"   Distance mismatch: expected {test['expected_distance_pct']:.2f}%, got {actual_distance_pct:.2f}%")

        print()
        print("-" * 80)
        print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total Tests: {len(TEST_CASES)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print()

    if failed == 0:
        print("🎉 ALL TESTS PASSED - Phase 1 stop widening logic is correct!")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Phase 1 logic needs review")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
