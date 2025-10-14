#!/usr/bin/env python3
"""
Test Runner - Execute All Unit Tests

Runs all unit tests in the unit_tests/ directory and provides
comprehensive summary of results.

Usage:
    python3 run_all_tests.py              # Run all tests
    python3 run_all_tests.py -v           # Verbose output
    python3 run_all_tests.py --failfast   # Stop on first failure

Created: October 13, 2025
"""

import unittest
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def discover_and_run_tests(verbosity=2, failfast=False):
    """
    Discover and run all tests in the unit_tests directory

    Args:
        verbosity: 0=quiet, 1=normal, 2=verbose
        failfast: Stop on first failure

    Returns:
        bool: True if all tests passed, False otherwise
    """
    # Discover all test files
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern='test_*.py')

    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity, failfast=failfast)
    result = runner.run(suite)

    # Print comprehensive summary
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUMMARY - PS60 Trading System")
    print("="*80)

    print(f"\nTotal Tests Run: {result.testsRun}")
    print(f"✅ Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Failures: {len(result.failures)}")
    print(f"⚠️  Errors: {len(result.errors)}")
    print(f"⏭️  Skipped: {len(result.skipped)}")

    # Calculate success rate
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) /
                       result.testsRun * 100)
        print(f"\n📊 Success Rate: {success_rate:.1f}%")

    # Show failures if any
    if result.failures:
        print("\n" + "="*80)
        print("FAILURES:")
        print("="*80)
        for test, traceback in result.failures:
            print(f"\n❌ {test}")
            print(traceback)

    # Show errors if any
    if result.errors:
        print("\n" + "="*80)
        print("ERRORS:")
        print("="*80)
        for test, traceback in result.errors:
            print(f"\n⚠️  {test}")
            print(traceback)

    # Final verdict
    print("\n" + "="*80)
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        return True
    else:
        print("❌ SOME TESTS FAILED - Review above for details")
        print("="*80)
        return False


def list_test_files():
    """List all available test files"""
    test_dir = Path(__file__).parent
    test_files = sorted(test_dir.glob('test_*.py'))

    print("\n" + "="*80)
    print("AVAILABLE TEST FILES")
    print("="*80)

    for i, test_file in enumerate(test_files, 1):
        print(f"{i}. {test_file.name}")

    print(f"\nTotal: {len(test_files)} test files")
    print("="*80)


def run_specific_test(test_name):
    """
    Run a specific test file or test case

    Args:
        test_name: Name of test file (e.g., 'test_state_manager')
                  or test case (e.g., 'test_state_manager.TestStateSaving')
    """
    loader = unittest.TestLoader()

    try:
        # Try to load as module.TestCase
        if '.' in test_name:
            suite = loader.loadTestsFromName(test_name)
        else:
            # Load entire test file
            suite = loader.loadTestsFromName(test_name)

        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        return result.wasSuccessful()

    except Exception as e:
        print(f"❌ Error loading test '{test_name}': {e}")
        return False


if __name__ == '__main__':
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list' or sys.argv[1] == '-l':
            list_test_files()
            sys.exit(0)

        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print(__doc__)
            sys.exit(0)

        elif sys.argv[1].startswith('test_'):
            # Run specific test
            success = run_specific_test(sys.argv[1])
            sys.exit(0 if success else 1)

    # Parse flags
    verbosity = 2
    failfast = False

    if '-v' in sys.argv:
        verbosity = 2
    elif '-q' in sys.argv or '--quiet' in sys.argv:
        verbosity = 0

    if '--failfast' in sys.argv or '-f' in sys.argv:
        failfast = True

    # Run all tests
    success = discover_and_run_tests(verbosity=verbosity, failfast=failfast)
    sys.exit(0 if success else 1)
