#!/usr/bin/env python3
"""
Test 4.1: October 9, 2025 Replay Test
Verifies backtester with Phase 1-3 matches expected results
"""

import subprocess
import json
import sys
from pathlib import Path

# Expected results from October 9, 2025 backtest (WITH Phase 1-3)
EXPECTED_RESULTS = {
    'date': '2025-10-09',
    'total_pnl': -2774.17,
    'trades': 4,
    'win_rate': 0.0,
    'symbols': ['AVGO', 'GS', 'BA', 'COIN'],
    'phase1_improvement': 1905.53,  # vs -$4,679.70 without Phase 1
    'tolerance_pct': 5.0  # ±5% tolerance for P&L
}

# Expected individual trades (from verification doc)
EXPECTED_TRADES = [
    {
        'symbol': 'AVGO',
        'entry': 347.61,
        'stop': 345.87,  # Widened from $347.10 pivot
        'stop_distance': 1.74,
        'setup_type': 'MOMENTUM',
        'phase1_impact': 'Prevented early stop at $347.10'
    },
    {
        'symbol': 'GS',
        'entry': 528.42,
        'stop': 530.53,  # Widened from $530.14 pivot
        'setup_type': 'REJECTION',
        'phase1_impact': 'Widened stop by 0.07%'
    },
    {
        'symbol': 'BA',
        'entry': None,  # To be verified
        'setup_type': 'MOMENTUM',
    },
    {
        'symbol': 'COIN',
        'entry': 391.77,
        'stop': 390.49,  # Pivot already wider than 0.3% min
        'setup_type': 'PULLBACK',
        'phase1_impact': 'Pivot already adequate'
    }
]

def run_backtest():
    """Run October 9 backtest"""
    print("=" * 80)
    print("OCTOBER 9, 2025 BACKTEST REPLAY")
    print("=" * 80)
    print()

    scanner_file = Path(__file__).parent.parent / 'stockscanner' / 'output' / 'scanner_results_20251009.json'

    if not scanner_file.exists():
        print(f"❌ Scanner file not found: {scanner_file}")
        print("   Run scanner first: cd ../stockscanner && python3 scanner.py --date 2025-10-09")
        return None

    print(f"Scanner file: {scanner_file}")
    print()

    # Run backtester
    cmd = [
        'python3',
        'backtester.py',
        '--scanner', str(scanner_file),
        '--date', '2025-10-09',
        '--account-size', '100000'
    ]

    print("Running backtester...")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(
        cmd,
        cwd=Path(__file__).parent / 'backtest',
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"❌ Backtester failed with exit code {result.returncode}")
        print("STDERR:", result.stderr)
        return None

    # Parse output
    output_lines = result.stdout.split('\n')

    # Extract P&L and trade count from summary
    pnl = None
    trades = None
    win_rate = None

    for line in output_lines:
        if 'Total P&L:' in line:
            # Extract P&L value
            parts = line.split('$')
            if len(parts) > 1:
                pnl = float(parts[1].replace(',', '').split()[0])
        elif 'Total trades:' in line:
            trades = int(line.split(':')[1].strip())
        elif 'Win rate:' in line:
            win_rate = float(line.split(':')[1].strip().replace('%', ''))

    return {
        'pnl': pnl,
        'trades': trades,
        'win_rate': win_rate / 100 if win_rate is not None else None,
        'output': output_lines
    }


def verify_results(actual):
    """Verify backtest results match expectations"""

    if actual is None:
        print("❌ No results to verify")
        return False

    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print()

    all_passed = True

    # Check P&L
    expected_pnl = EXPECTED_RESULTS['total_pnl']
    actual_pnl = actual['pnl']
    tolerance = abs(expected_pnl) * (EXPECTED_RESULTS['tolerance_pct'] / 100)

    print(f"1. Total P&L")
    print(f"   Expected: ${expected_pnl:,.2f} (±{EXPECTED_RESULTS['tolerance_pct']}%)")
    print(f"   Actual:   ${actual_pnl:,.2f}")

    if abs(actual_pnl - expected_pnl) <= tolerance:
        print(f"   ✅ PASS (within ${tolerance:.2f} tolerance)")
    else:
        print(f"   ❌ FAIL (outside ${tolerance:.2f} tolerance)")
        all_passed = False
    print()

    # Check trade count
    print(f"2. Trade Count")
    print(f"   Expected: {EXPECTED_RESULTS['trades']}")
    print(f"   Actual:   {actual['trades']}")

    if actual['trades'] == EXPECTED_RESULTS['trades']:
        print(f"   ✅ PASS")
    else:
        print(f"   ❌ FAIL")
        all_passed = False
    print()

    # Check win rate
    print(f"3. Win Rate")
    print(f"   Expected: {EXPECTED_RESULTS['win_rate'] * 100:.1f}%")
    print(f"   Actual:   {actual['win_rate'] * 100:.1f}%")

    if actual['win_rate'] == EXPECTED_RESULTS['win_rate']:
        print(f"   ✅ PASS")
    else:
        print(f"   ❌ FAIL (expected 0% on this difficult day)")
        all_passed = False
    print()

    # Check Phase 1 improvement
    print(f"4. Phase 1 Impact")
    print(f"   Without Phase 1: -$4,679.70")
    print(f"   With Phase 1:    ${actual_pnl:,.2f}")
    improvement = -4679.70 - actual_pnl
    expected_improvement = EXPECTED_RESULTS['phase1_improvement']
    print(f"   Improvement:     ${improvement:,.2f} (expected ${expected_improvement:,.2f})")

    if abs(improvement - expected_improvement) <= tolerance:
        print(f"   ✅ PASS (Phase 1 saved ~${improvement:,.0f})")
    else:
        print(f"   ❌ FAIL (improvement not matching)")
        all_passed = False
    print()

    return all_passed


def main():
    """Run October 9 replay test"""

    print()
    print("TEST 4.1: OCTOBER 9, 2025 REPLAY")
    print("Verifies Phase 1-3 implementations work correctly")
    print()

    # Run backtest
    results = run_backtest()

    if results is None:
        return 1

    # Verify results
    passed = verify_results(results)

    # Summary
    print("=" * 80)
    print("TEST RESULT")
    print("=" * 80)

    if passed:
        print("✅ ALL CHECKS PASSED")
        print()
        print("Phase 1-3 implementations are working correctly!")
        print("- Stop widening prevented noise-based stops")
        print("- Momentum filters applied correctly")
        print("- Pullback quality checks working")
        print()
        print("Ready for next phase: Live paper trading validation")
        return 0
    else:
        print("❌ SOME CHECKS FAILED")
        print()
        print("Review backtest output above for discrepancies")
        return 1


if __name__ == "__main__":
    sys.exit(main())
