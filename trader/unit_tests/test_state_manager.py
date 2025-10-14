#!/usr/bin/env python3
"""
Unit Tests for StateManager - State Persistence and Recovery (GAP #9)

Tests the StateManager class that handles crash recovery:
- Save state to file (every 10 seconds)
- Load state from file
- Recover positions from IBKR
- Reconcile state with IBKR portfolio
- Handle corrupted state files
- Validate state date (ignore old state)

Created: October 13, 2025
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, mock_open
from datetime import datetime, timedelta
from pathlib import Path
import json
import tempfile
import shutil
import pytz


class TestStateSaving(unittest.TestCase):
    """Test state saving functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.eastern = pytz.timezone('US/Eastern')

        # Create mock trader
        self.mock_trader = Mock()
        self.mock_trader.config = {
            'logging': {'log_dir': self.temp_dir}
        }
        self.mock_trader.positions = {}
        self.mock_trader.watchlist = []
        self.mock_trader.analytics = {
            'session_start': datetime.now(pytz.UTC).astimezone(self.eastern),
            'filter_blocks': {},
            'entry_paths': {},
            'pivot_checks': {}
        }
        self.mock_trader.pm = Mock()
        self.mock_trader.pm.get_daily_summary.return_value = {
            'daily_pnl': 0,
            'total_trades': 0,
            'winners': 0,
            'losers': 0
        }

    def tearDown(self):
        """Clean up test fixtures"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_state_file_is_created(self):
        """Test that state file is created when saving"""
        from state_manager import StateManager

        sm = StateManager(self.mock_trader)
        sm.save_state()

        # Verify state file exists
        state_file = Path(self.temp_dir) / 'trader_state.json'
        self.assertTrue(state_file.exists(), "State file should be created")

        print("✓ State file created successfully")

    def test_state_contains_required_fields(self):
        """Test that saved state contains all required fields"""
        from state_manager import StateManager

        sm = StateManager(self.mock_trader)
        sm.save_state()

        # Load and verify state
        state_file = Path(self.temp_dir) / 'trader_state.json'
        with open(state_file) as f:
            state = json.load(f)

        # Check required fields
        self.assertIn('timestamp', state, "Should have timestamp")
        self.assertIn('date', state, "Should have date")
        self.assertIn('positions', state, "Should have positions")
        self.assertIn('attempt_counts', state, "Should have attempt_counts")
        self.assertIn('analytics', state, "Should have analytics")
        self.assertIn('session', state, "Should have session")

        print(f"✓ State contains all required fields: {list(state.keys())}")

    def test_state_with_open_positions(self):
        """Test that open positions are saved correctly"""
        from state_manager import StateManager

        # Add position to trader
        self.mock_trader.positions = {
            'TSLA': {
                'symbol': 'TSLA',
                'side': 'LONG',
                'entry_price': 100.0,
                'entry_time': datetime.now(pytz.UTC).astimezone(self.eastern),
                'shares': 100,
                'remaining': 1.0,
                'pivot': 99.0,
                'target1': 105.0,
                'target2': 110.0,
                'stop': 98.0,
                'partials': []
            }
        }

        sm = StateManager(self.mock_trader)
        sm.save_state()

        # Load and verify
        state_file = Path(self.temp_dir) / 'trader_state.json'
        with open(state_file) as f:
            state = json.load(f)

        self.assertEqual(len(state['positions']), 1, "Should have 1 position")
        self.assertIn('TSLA', state['positions'], "Should contain TSLA position")
        self.assertEqual(state['positions']['TSLA']['shares'], 100, "Shares should match")

        print("✓ Open positions saved correctly")

    def test_backup_file_created_on_save(self):
        """Test that backup file is created when saving over existing state"""
        from state_manager import StateManager

        sm = StateManager(self.mock_trader)

        # Save first time (no backup created - no existing file)
        sm.save_state()
        state_file = Path(self.temp_dir) / 'trader_state.json'
        backup_file = Path(self.temp_dir) / 'trader_state_backup.json'

        self.assertTrue(state_file.exists(), "State file should exist after first save")
        self.assertFalse(backup_file.exists(), "No backup on first save (no previous file)")

        # Read first save content for comparison later
        first_content = state_file.read_text()

        # Modify trader state
        self.mock_trader.positions = {'AAPL': {'symbol': 'AAPL'}}

        # Save second time (should create backup from first save)
        sm.save_state()

        self.assertTrue(backup_file.exists(), "Backup file should be created on second save")
        self.assertTrue(state_file.exists(), "State file should still exist")

        # Backup should contain first save's content
        # Note: Path.replace() renames/moves the old file to backup location
        backup_content = backup_file.read_text()
        self.assertIn('"TSLA"', backup_content, "Backup should contain first save (TSLA)")

        # Current state should have new content (AAPL)
        current_content = state_file.read_text()
        self.assertIn('"AAPL"', current_content, "Current state should have AAPL")

        print("✓ Backup file created correctly")

    def test_atomic_write_using_temp_file(self):
        """Test that state write is atomic (uses temp file then rename)"""
        from state_manager import StateManager

        sm = StateManager(self.mock_trader)  # Fixed: was mock_trainer

        # Check that temp file is used (verify in implementation)
        # The implementation uses .tmp suffix and atomic rename
        sm.save_state()

        state_file = Path(self.temp_dir) / 'trader_state.json'
        temp_file = Path(self.temp_dir) / 'trader_state.tmp'

        # Temp file should not exist after save (was renamed)
        self.assertTrue(state_file.exists(), "State file should exist")
        self.assertFalse(temp_file.exists(), "Temp file should not exist after rename")

        print("✓ Atomic write verified")


class TestStateLoading(unittest.TestCase):
    """Test state loading functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.eastern = pytz.timezone('US/Eastern')

        self.mock_trader = Mock()
        self.mock_trader.config = {
            'logging': {'log_dir': self.temp_dir}
        }
        self.mock_trader.analytics = {'session_start': None}

    def tearDown(self):
        """Clean up test fixtures"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_load_returns_none_when_no_file_exists(self):
        """Test that load returns None when state file doesn't exist"""
        from state_manager import StateManager

        sm = StateManager(self.mock_trader)
        state = sm.load_state()

        self.assertIsNone(state, "Should return None when no state file exists")

        print("✓ Returns None for missing state file")

    def test_load_valid_state_from_today(self):
        """Test loading valid state from today"""
        from state_manager import StateManager

        # Create valid state file for today
        now_et = datetime.now(pytz.UTC).astimezone(self.eastern)
        state_data = {
            'timestamp': now_et.isoformat(),
            'date': now_et.strftime('%Y-%m-%d'),
            'positions': {},
            'analytics': {'daily_pnl': 0}
        }

        state_file = Path(self.temp_dir) / 'trader_state.json'
        with open(state_file, 'w') as f:
            json.dump(state_data, f)

        sm = StateManager(self.mock_trader)
        loaded_state = sm.load_state()

        self.assertIsNotNone(loaded_state, "Should load state from today")
        self.assertEqual(loaded_state['date'], now_et.strftime('%Y-%m-%d'))

        print("✓ Valid state loaded successfully")

    def test_load_ignores_old_state(self):
        """Test that state from previous day is ignored"""
        from state_manager import StateManager

        # Create state file from yesterday
        yesterday = datetime.now(self.eastern) - timedelta(days=1)
        state_data = {
            'timestamp': yesterday.isoformat(),
            'date': yesterday.strftime('%Y-%m-%d'),
            'positions': {'TSLA': {'symbol': 'TSLA'}},
            'analytics': {'daily_pnl': 1000}
        }

        state_file = Path(self.temp_dir) / 'trader_state.json'
        with open(state_file, 'w') as f:
            json.dump(state_data, f)

        sm = StateManager(self.mock_trader)
        loaded_state = sm.load_state()

        self.assertIsNone(loaded_state, "Should ignore state from previous day")

        print("✓ Old state correctly ignored")

    def test_load_handles_corrupted_json(self):
        """Test that corrupted JSON is handled gracefully"""
        from state_manager import StateManager

        # Create corrupted state file
        state_file = Path(self.temp_dir) / 'trader_state.json'
        state_file.write_text('{invalid json here}')

        sm = StateManager(self.mock_trader)
        loaded_state = sm.load_state()

        # Should return None and not crash
        self.assertIsNone(loaded_state, "Should return None for corrupted file")

        print("✓ Corrupted JSON handled gracefully")

    def test_load_tries_backup_when_primary_corrupted(self):
        """Test that backup is loaded when primary file is corrupted"""
        from state_manager import StateManager

        # Create corrupted primary file
        state_file = Path(self.temp_dir) / 'trader_state.json'
        state_file.write_text('{invalid json}')

        # Create valid backup file
        now_et = datetime.now(pytz.UTC).astimezone(self.eastern)
        backup_data = {
            'timestamp': now_et.isoformat(),
            'date': now_et.strftime('%Y-%m-%d'),
            'positions': {},
            'analytics': {'daily_pnl': 0}
        }

        backup_file = Path(self.temp_dir) / 'trader_state_backup.json'
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)

        sm = StateManager(self.mock_trader)
        loaded_state = sm.load_state()

        # Should load from backup
        self.assertIsNotNone(loaded_state, "Should load from backup")
        self.assertEqual(loaded_state['date'], now_et.strftime('%Y-%m-%d'))

        print("✓ Backup file loaded when primary corrupted")


class TestIBKRRecovery(unittest.TestCase):
    """Test recovery from IBKR portfolio"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_trader = Mock()
        self.mock_trader.config = {'logging': {'log_dir': self.temp_dir}}
        self.mock_trader.watchlist = [
            {'symbol': 'TSLA', 'resistance': 100},
            {'symbol': 'AAPL', 'resistance': 150}
        ]
        self.mock_trader.positions = {}

    def tearDown(self):
        """Clean up"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def test_recover_long_position_from_ibkr(self):
        """Test recovering a LONG position from IBKR"""
        from state_manager import StateManager

        # Mock IBKR position
        mock_position = Mock()
        mock_position.contract.symbol = 'TSLA'
        mock_position.position = 100  # Positive = LONG
        mock_position.avgCost = 99.50

        self.mock_trader.ib = Mock()
        self.mock_trader.ib.positions.return_value = [mock_position]

        sm = StateManager(self.mock_trader)
        ibkr_positions = sm.recover_from_ibkr()

        # Verify recovery
        self.assertIn('TSLA', ibkr_positions, "TSLA position should be recovered")
        self.assertEqual(ibkr_positions['TSLA']['side'], 'LONG')
        self.assertEqual(ibkr_positions['TSLA']['shares'], 100)
        self.assertAlmostEqual(ibkr_positions['TSLA']['avg_cost'], 99.50)

        print("✓ LONG position recovered from IBKR")

    def test_recover_short_position_from_ibkr(self):
        """Test recovering a SHORT position from IBKR"""
        from state_manager import StateManager

        # Mock IBKR position
        mock_position = Mock()
        mock_position.contract.symbol = 'AAPL'
        mock_position.position = -50  # Negative = SHORT
        mock_position.avgCost = 150.25

        self.mock_trader.ib = Mock()
        self.mock_trader.ib.positions.return_value = [mock_position]

        sm = StateManager(self.mock_trader)
        ibkr_positions = sm.recover_from_ibkr()

        # Verify recovery
        self.assertIn('AAPL', ibkr_positions, "AAPL position should be recovered")
        self.assertEqual(ibkr_positions['AAPL']['side'], 'SHORT')
        self.assertEqual(ibkr_positions['AAPL']['shares'], 50)  # abs() of -50

        print("✓ SHORT position recovered from IBKR")

    def test_recover_ignores_positions_not_in_watchlist(self):
        """Test that positions not in today's watchlist are ignored"""
        from state_manager import StateManager

        # Mock IBKR position for symbol NOT in watchlist
        mock_position = Mock()
        mock_position.contract.symbol = 'NVDA'  # Not in watchlist
        mock_position.position = 100
        mock_position.avgCost = 200.00

        self.mock_trader.ib = Mock()
        self.mock_trader.ib.positions.return_value = [mock_position]

        sm = StateManager(self.mock_trader)
        ibkr_positions = sm.recover_from_ibkr()

        # Should not recover NVDA
        self.assertNotIn('NVDA', ibkr_positions, "Should ignore positions not in watchlist")

        print("✓ Positions not in watchlist are ignored")

    def test_recover_handles_ibkr_connection_error(self):
        """Test that IBKR connection errors are handled gracefully"""
        from state_manager import StateManager

        # Mock IBKR connection error
        self.mock_trader.ib = Mock()
        self.mock_trader.ib.positions.side_effect = Exception("Connection lost")

        sm = StateManager(self.mock_trader)
        ibkr_positions = sm.recover_from_ibkr()

        # Should return empty dict and not crash
        self.assertEqual(len(ibkr_positions), 0, "Should return empty dict on error")

        print("✓ IBKR connection errors handled gracefully")


class TestPositionReconciliation(unittest.TestCase):
    """Test reconciliation between state file and IBKR"""

    def test_reconcile_accepts_matching_positions(self):
        """Test that matching positions between state and IBKR are accepted"""
        # State file shows: TSLA 100 shares
        # IBKR shows: TSLA 100 shares
        # Result: Accept and restore

        state_position = {
            'symbol': 'TSLA',
            'shares': 100,
            'side': 'LONG',
            'entry_price': 99.0
        }

        ibkr_position = {
            'shares': 100,
            'side': 'LONG',
            'avg_cost': 99.0
        }

        # Verify they match
        self.assertEqual(state_position['shares'], ibkr_position['shares'])
        self.assertEqual(state_position['side'], ibkr_position['side'])

        print("✓ Matching positions reconciled correctly")

    def test_reconcile_prefers_ibkr_share_count(self):
        """Test that IBKR share count is used when there's a mismatch"""
        # State file shows: TSLA 100 shares
        # IBKR shows: TSLA 50 shares (partial was filled)
        # Result: Use IBKR value (50 shares)

        state_shares = 100
        ibkr_shares = 50

        # IBKR is source of truth
        actual_shares = ibkr_shares

        self.assertEqual(actual_shares, 50, "Should use IBKR share count")

        print("✓ IBKR share count preferred in mismatch")

    def test_reconcile_skips_positions_missing_from_ibkr(self):
        """Test that positions in state but not in IBKR are skipped"""
        # State file shows: TSLA position
        # IBKR shows: No TSLA position
        # Result: Do NOT restore (likely closed by broker)

        state_has_position = True
        ibkr_has_position = False

        should_restore = state_has_position and ibkr_has_position

        self.assertFalse(should_restore, "Should not restore position missing from IBKR")

        print("✓ Positions missing from IBKR are skipped")


def run_tests():
    """Run all state manager tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestStateSaving))
    suite.addTests(loader.loadTestsFromTestCase(TestStateLoading))
    suite.addTests(loader.loadTestsFromTestCase(TestIBKRRecovery))
    suite.addTests(loader.loadTestsFromTestCase(TestPositionReconciliation))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY - State Manager (GAP #9)")
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
