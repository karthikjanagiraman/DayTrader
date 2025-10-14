#!/usr/bin/env python3
"""
Unit Tests for PositionManager

Tests position tracking and management:
- Create positions
- Track partial exits
- Calculate P&L
- Track attempt counts
- Daily summary generation
- Position closing

Created: October 13, 2025
"""

import unittest
from unittest.mock import Mock
from datetime import datetime
import pytz
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategy.position_manager import PositionManager


class TestPositionCreation(unittest.TestCase):
    """Test position creation functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.pm = PositionManager()
        self.eastern = pytz.timezone('US/Eastern')

    def test_create_long_position(self):
        """Test creating a LONG position"""
        contract = Mock()
        contract.symbol = 'TSLA'

        position = self.pm.create_position(
            symbol='TSLA',
            side='LONG',
            entry_price=100.0,
            shares=100,
            pivot=99.0,
            contract=contract,
            target1=105.0,
            target2=110.0
        )

        # Verify position attributes
        self.assertEqual(position['symbol'], 'TSLA')
        self.assertEqual(position['side'], 'LONG')
        self.assertEqual(position['entry_price'], 100.0)
        self.assertEqual(position['shares'], 100)
        self.assertEqual(position['pivot'], 99.0)
        self.assertEqual(position['target1'], 105.0)
        self.assertEqual(position['remaining'], 1.0)  # 100%

        print("✓ LONG position created correctly")

    def test_create_short_position(self):
        """Test creating a SHORT position"""
        contract = Mock()
        contract.symbol = 'AAPL'

        position = self.pm.create_position(
            symbol='AAPL',
            side='SHORT',
            entry_price=150.0,
            shares=50,
            pivot=151.0,
            contract=contract,
            target1=145.0,
            target2=140.0
        )

        self.assertEqual(position['side'], 'SHORT')
        self.assertEqual(position['shares'], 50)

        print("✓ SHORT position created correctly")

    def test_position_has_entry_time(self):
        """Test that position has entry timestamp"""
        contract = Mock()

        position = self.pm.create_position(
            symbol='TSLA',
            side='LONG',
            entry_price=100.0,
            shares=100,
            pivot=99.0,
            contract=contract
        )

        self.assertIn('entry_time', position)
        self.assertIsInstance(position['entry_time'], datetime)

        print("✓ Position has entry timestamp")

    def test_position_tracking_extremes(self):
        """Test that position tracks price extremes"""
        contract = Mock()

        # LONG positions track highest_price (not lowest_price)
        long_position = self.pm.create_position(
            symbol='TSLA',
            side='LONG',
            entry_price=100.0,
            shares=100,
            pivot=99.0,
            contract=contract
        )

        # LONGs: highest_price initialized, lowest_price is None
        self.assertEqual(long_position['highest_price'], 100.0)
        self.assertIsNone(long_position['lowest_price'])

        # SHORT positions track lowest_price (not highest_price)
        short_position = self.pm.create_position(
            symbol='AAPL',
            side='SHORT',
            entry_price=150.0,
            shares=100,
            pivot=151.0,
            contract=contract
        )

        # SHORTs: lowest_price initialized, highest_price is None
        self.assertIsNone(short_position['highest_price'])
        self.assertEqual(short_position['lowest_price'], 150.0)

        print("✓ Position tracks price extremes correctly (LONG=highest, SHORT=lowest)")


class TestPartialExits(unittest.TestCase):
    """Test partial exit functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.pm = PositionManager()
        contract = Mock()

        # Create test position
        self.pm.create_position(
            symbol='TSLA',
            side='LONG',
            entry_price=100.0,
            shares=100,
            pivot=99.0,
            contract=contract,
            target1=105.0
        )

    def test_take_first_partial(self):
        """Test taking first partial (50%)"""
        partial_result = self.pm.take_partial(
            symbol='TSLA',
            price=102.0,      # Fixed: was exit_price
            pct=0.50,         # Fixed: was percentage
            reason='FIRST_PARTIAL'
        )

        position = self.pm.get_position('TSLA')

        # Verify partial
        self.assertIsNotNone(partial_result)
        self.assertEqual(partial_result['pct'], 0.50)  # Fixed: check pct, not shares
        self.assertEqual(position['remaining'], 0.50)  # 50% left
        self.assertEqual(len(position['partials']), 1)

        print("✓ First partial (50%) executed correctly")

    def test_take_second_partial(self):
        """Test taking second partial (25% of original)"""
        # First partial
        self.pm.take_partial('TSLA', 102.0, 0.50, 'FIRST_PARTIAL')

        # Second partial
        partial_result = self.pm.take_partial(
            symbol='TSLA',
            price=105.0,      # Fixed: was exit_price
            pct=0.25,         # Fixed: was percentage
            reason='TARGET1'
        )

        position = self.pm.get_position('TSLA')

        # Verify second partial
        self.assertEqual(partial_result['pct'], 0.25)  # Fixed: check pct, not shares
        self.assertEqual(position['remaining'], 0.25)  # 25% left (runner)
        self.assertEqual(len(position['partials']), 2)

        print("✓ Second partial (25%) executed correctly")

    def test_partial_pnl_calculation(self):
        """Test P&L calculation for partial exits"""
        partial_result = self.pm.take_partial(
            symbol='TSLA',
            price=102.0,      # Fixed: was exit_price (Entry was 100.0)
            pct=0.50,         # Fixed: was percentage
            reason='FIRST_PARTIAL'
        )

        # Partial returns 'gain' per share, not total 'pnl'
        # Gain = $2.0 per share (102 - 100)
        expected_gain = 2.0
        self.assertAlmostEqual(partial_result['gain'], expected_gain, places=2)

        print(f"✓ Partial gain calculated correctly: ${partial_result['gain']:.2f}/share")

    def test_can_take_more_than_remaining(self):
        """Test that API allows taking more than remaining (caller must validate)"""
        # Take 50%
        self.pm.take_partial('TSLA', 102.0, 0.50, 'FIRST')

        # API allows taking 60% even though only 50% left
        # This puts remaining into negative territory
        # (In production, caller should validate before calling take_partial)
        partial_result = self.pm.take_partial('TSLA', 103.0, 0.60, 'SECOND')

        # Verify the partial was recorded
        self.assertIsNotNone(partial_result)
        self.assertEqual(partial_result['pct'], 0.60)

        # Position goes negative (0.50 - 0.60 = -0.10)
        position = self.pm.get_position('TSLA')
        self.assertAlmostEqual(position['remaining'], -0.10, places=2)

        # Position still exists in positions dict
        self.assertTrue(self.pm.has_position('TSLA'))

        print("✓ API allows oversized partials (caller must validate)")


class TestPnLCalculation(unittest.TestCase):
    """Test P&L calculation logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.pm = PositionManager()

    def test_pnl_for_long_winner(self):
        """Test P&L for winning LONG trade"""
        position = {
            'side': 'LONG',
            'entry_price': 100.0,
            'shares': 100,
            'remaining': 1.0,
            'partials': []  # Fixed: Added required key
        }

        pnl = self.pm.calculate_pnl(position, exit_price=105.0)

        # P&L = (105 - 100) * 100 = $500
        self.assertEqual(pnl, 500.0)

        print(f"✓ LONG winner P&L: ${pnl:.2f}")

    def test_pnl_for_long_loser(self):
        """Test P&L for losing LONG trade"""
        position = {
            'side': 'LONG',
            'entry_price': 100.0,
            'shares': 100,
            'remaining': 1.0,
            'partials': []  # Fixed: Added required key
        }

        pnl = self.pm.calculate_pnl(position, exit_price=98.0)

        # P&L = (98 - 100) * 100 = -$200
        self.assertEqual(pnl, -200.0)

        print(f"✓ LONG loser P&L: ${pnl:.2f}")

    def test_pnl_for_short_winner(self):
        """Test P&L for winning SHORT trade"""
        position = {
            'side': 'SHORT',
            'entry_price': 100.0,
            'shares': 100,
            'remaining': 1.0,
            'partials': []  # Fixed: Added required key
        }

        pnl = self.pm.calculate_pnl(position, exit_price=95.0)

        # P&L = (100 - 95) * 100 = $500 (profit when price goes down)
        self.assertEqual(pnl, 500.0)

        print(f"✓ SHORT winner P&L: ${pnl:.2f}")

    def test_pnl_for_short_loser(self):
        """Test P&L for losing SHORT trade"""
        position = {
            'side': 'SHORT',
            'entry_price': 100.0,
            'shares': 100,
            'remaining': 1.0,
            'partials': []  # Fixed: Added required key
        }

        pnl = self.pm.calculate_pnl(position, exit_price=102.0)

        # P&L = (100 - 102) * 100 = -$200 (loss when price goes up)
        self.assertEqual(pnl, -200.0)

        print(f"✓ SHORT loser P&L: ${pnl:.2f}")

    def test_pnl_for_partial_remaining(self):
        """Test P&L for position with partials taken"""
        position = {
            'side': 'LONG',
            'entry_price': 100.0,
            'shares': 100,
            'remaining': 0.25,  # Only 25% left (75% already exited)
            'partials': []  # Fixed: Added required key (empty since we're only testing remaining)
        }

        pnl = self.pm.calculate_pnl(position, exit_price=105.0)

        # P&L = (105 - 100) * 100 * 0.25 = $125 (only for remaining 25%)
        self.assertEqual(pnl, 125.0)

        print(f"✓ Partial remaining P&L: ${pnl:.2f}")


class TestPositionClosing(unittest.TestCase):
    """Test position closing functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.pm = PositionManager()
        contract = Mock()

        self.pm.create_position(
            symbol='TSLA',
            side='LONG',
            entry_price=100.0,
            shares=100,
            pivot=99.0,
            contract=contract
        )

    def test_close_full_position(self):
        """Test closing entire position"""
        closed_trade = self.pm.close_position(
            symbol='TSLA',
            exit_price=105.0,
            reason='TARGET'
        )

        # Verify closure
        self.assertIsNotNone(closed_trade)
        self.assertEqual(closed_trade['pnl'], 500.0)  # $5 * 100 shares
        self.assertFalse(self.pm.has_position('TSLA'))

        print(f"✓ Full position closed: ${closed_trade['pnl']:.2f} P&L")

    def test_close_runner_after_partials(self):
        """Test closing runner position after partials"""
        # Take partials first
        self.pm.take_partial('TSLA', 102.0, 0.50, 'FIRST')  # 50% at $2 gain = +$100
        self.pm.take_partial('TSLA', 105.0, 0.25, 'SECOND')  # 25% at $5 gain = +$125

        # Close runner (25% remaining at $103)
        closed_trade = self.pm.close_position(
            symbol='TSLA',
            exit_price=103.0,
            reason='TRAIL_STOP'
        )

        # Total P&L calculation:
        # Partial 1: $2 * 100 * 0.50 = $100
        # Partial 2: $5 * 100 * 0.25 = $125
        # Runner:    $3 * 100 * 0.25 = $75
        # TOTAL:                      $300
        expected_total_pnl = 300.0
        self.assertAlmostEqual(closed_trade['pnl'], expected_total_pnl, places=2)

        print(f"✓ Runner closed: ${closed_trade['pnl']:.2f} total P&L")

    def test_close_records_exit_time(self):
        """Test that closing records exit timestamp"""
        closed_trade = self.pm.close_position('TSLA', 105.0, 'EOD')

        self.assertIn('exit_time', closed_trade)
        self.assertIsInstance(closed_trade['exit_time'], datetime)

        print("✓ Exit time recorded")

    def test_close_calculates_duration(self):
        """Test that closing calculates trade duration"""
        closed_trade = self.pm.close_position('TSLA', 105.0, 'TARGET')

        self.assertIn('duration_min', closed_trade)
        self.assertGreater(closed_trade['duration_min'], 0)

        print(f"✓ Duration calculated: {closed_trade['duration_min']:.2f} minutes")


class TestDailySummary(unittest.TestCase):
    """Test daily summary generation"""

    def setUp(self):
        """Set up test fixtures"""
        self.pm = PositionManager()

    def test_summary_with_no_trades(self):
        """Test summary with no trades"""
        summary = self.pm.get_daily_summary()

        self.assertEqual(summary['total_trades'], 0)
        self.assertEqual(summary['daily_pnl'], 0)
        self.assertEqual(summary['winners'], 0)
        self.assertEqual(summary['losers'], 0)

        print("✓ Empty summary generated correctly")

    def test_summary_with_winning_trades(self):
        """Test summary with winning trades"""
        # Create and close winning trades
        for i in range(3):
            contract = Mock()
            self.pm.create_position(
                symbol=f'STOCK{i}',
                side='LONG',
                entry_price=100.0,
                shares=100,
                pivot=99.0,
                contract=contract
            )
            self.pm.close_position(f'STOCK{i}', 105.0, 'TARGET')

        summary = self.pm.get_daily_summary()

        self.assertEqual(summary['total_trades'], 3)
        self.assertEqual(summary['winners'], 3)
        self.assertEqual(summary['losers'], 0)
        self.assertEqual(summary['win_rate'], 100.0)
        self.assertEqual(summary['daily_pnl'], 1500.0)  # $500 * 3

        print(f"✓ Summary with winners: ${summary['daily_pnl']:.2f}, {summary['win_rate']:.1f}% win rate")

    def test_summary_with_mixed_results(self):
        """Test summary with winners and losers"""
        # Create winners and losers
        contract = Mock()

        # 2 winners
        for i in range(2):
            self.pm.create_position(f'WIN{i}', 'LONG', 100.0, 100, 99.0, contract)
            self.pm.close_position(f'WIN{i}', 105.0, 'TARGET')  # +$500 each

        # 1 loser
        self.pm.create_position('LOSS', 'LONG', 100.0, 100, 99.0, contract)
        self.pm.close_position('LOSS', 98.0, 'STOP')  # -$200

        summary = self.pm.get_daily_summary()

        self.assertEqual(summary['total_trades'], 3)
        self.assertEqual(summary['winners'], 2)
        self.assertEqual(summary['losers'], 1)
        self.assertAlmostEqual(summary['win_rate'], 66.67, places=1)
        self.assertEqual(summary['daily_pnl'], 800.0)  # $1000 - $200

        print(f"✓ Mixed summary: ${summary['daily_pnl']:.2f}, {summary['win_rate']:.1f}% win rate")


class TestAttemptTracking(unittest.TestCase):
    """Test attempt count tracking"""

    def setUp(self):
        """Set up test fixtures"""
        self.pm = PositionManager()

    def test_initial_attempt_count_is_zero(self):
        """Test that initial attempt count is 0"""
        attempts = self.pm.get_attempt_count('TSLA', 100.0)

        self.assertEqual(attempts, 0)

        print("✓ Initial attempt count is 0")

    def test_attempt_count_increments(self):
        """Test that attempt count increments after position close"""
        contract = Mock()

        # First attempt
        self.pm.create_position('TSLA', 'LONG', 100.0, 100, 99.0, contract)
        self.pm.close_position('TSLA', 98.0, 'STOP')

        attempts_after_first = self.pm.get_attempt_count('TSLA', 99.0)
        self.assertEqual(attempts_after_first, 1)

        # Second attempt
        self.pm.create_position('TSLA', 'LONG', 100.5, 100, 99.0, contract)
        self.pm.close_position('TSLA', 102.0, 'PARTIAL')

        attempts_after_second = self.pm.get_attempt_count('TSLA', 99.0)
        self.assertEqual(attempts_after_second, 2)

        print("✓ Attempt count increments correctly")

    def test_different_pivots_tracked_separately(self):
        """Test that different pivots have separate attempt counts"""
        contract = Mock()

        # Attempt at pivot $99
        self.pm.create_position('TSLA', 'LONG', 100.0, 100, 99.0, contract)
        self.pm.close_position('TSLA', 98.0, 'STOP')

        # Attempt at pivot $105
        self.pm.create_position('TSLA', 'LONG', 106.0, 100, 105.0, contract)
        self.pm.close_position('TSLA', 104.0, 'STOP')

        attempts_at_99 = self.pm.get_attempt_count('TSLA', 99.0)
        attempts_at_105 = self.pm.get_attempt_count('TSLA', 105.0)

        self.assertEqual(attempts_at_99, 1)
        self.assertEqual(attempts_at_105, 1)

        print("✓ Different pivots tracked separately")


def run_tests():
    """Run all position manager tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPositionCreation))
    suite.addTests(loader.loadTestsFromTestCase(TestPartialExits))
    suite.addTests(loader.loadTestsFromTestCase(TestPnLCalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestPositionClosing))
    suite.addTests(loader.loadTestsFromTestCase(TestDailySummary))
    suite.addTests(loader.loadTestsFromTestCase(TestAttemptTracking))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY - Position Manager")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
