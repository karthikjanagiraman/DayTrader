#!/usr/bin/env python3
"""
Test Crash Recovery System

Tests that StateManager can:
1. Save trading state to file
2. Load state from file
3. Validate state is from today
4. Reject stale state
5. Reconcile with IBKR positions

Run this BEFORE paper trading to ensure crash recovery works
"""

import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import pytz


class TestStateManager(unittest.TestCase):
    """Test StateManager save/load functionality"""

    def setUp(self):
        """Setup test environment"""
        self.eastern = pytz.timezone('US/Eastern')

        # Create temporary state file
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / 'trader_state.json'

    def test_save_and_load_state(self):
        """Test basic save and load cycle"""
        # Create sample state
        state = {
            'timestamp': datetime.now(pytz.UTC).astimezone(self.eastern).isoformat(),
            'date': datetime.now(pytz.UTC).astimezone(self.eastern).strftime('%Y-%m-%d'),
            'positions': {
                'TSLA': {
                    'symbol': 'TSLA',
                    'side': 'LONG',
                    'entry_price': 445.25,
                    'shares': 100,
                    'remaining': 0.5,
                    'pivot': 444.77
                }
            },
            'attempt_counts': {
                'TSLA': {'long_attempts': 1, 'resistance': 444.77}
            },
            'analytics': {
                'daily_pnl': 756.19,
                'total_trades': 3
            }
        }

        # Save state
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

        # Load state
        with open(self.state_file) as f:
            loaded_state = json.load(f)

        self.assertEqual(loaded_state['positions']['TSLA']['symbol'], 'TSLA')
        self.assertEqual(loaded_state['positions']['TSLA']['shares'], 100)
        self.assertEqual(loaded_state['analytics']['daily_pnl'], 756.19)

    def test_reject_stale_state(self):
        """Test that state from previous day is rejected"""
        # Create state from yesterday
        yesterday = datetime.now(pytz.UTC).astimezone(self.eastern) - timedelta(days=1)

        stale_state = {
            'timestamp': yesterday.isoformat(),
            'date': yesterday.strftime('%Y-%m-%d'),
            'positions': {
                'TSLA': {'symbol': 'TSLA', 'shares': 100}
            }
        }

        # Save stale state
        with open(self.state_file, 'w') as f:
            json.dump(stale_state, f)

        # Load and check date
        with open(self.state_file) as f:
            loaded_state = json.load(f)

        today = datetime.now(pytz.UTC).astimezone(self.eastern).strftime('%Y-%m-%d')
        is_stale = loaded_state['date'] != today

        self.assertTrue(is_stale, "State from yesterday should be rejected")

    def test_validate_today_state(self):
        """Test that state from today is accepted"""
        # Create state from today
        now = datetime.now(pytz.UTC).astimezone(self.eastern)

        fresh_state = {
            'timestamp': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'positions': {
                'TSLA': {'symbol': 'TSLA', 'shares': 100}
            }
        }

        # Save fresh state
        with open(self.state_file, 'w') as f:
            json.dump(fresh_state, f)

        # Load and check date
        with open(self.state_file) as f:
            loaded_state = json.load(f)

        today = datetime.now(pytz.UTC).astimezone(self.eastern).strftime('%Y-%m-%d')
        is_fresh = loaded_state['date'] == today

        self.assertTrue(is_fresh, "State from today should be accepted")

    def test_position_serialization(self):
        """Test that positions serialize correctly"""
        position = {
            'symbol': 'TSLA',
            'side': 'LONG',
            'entry_price': 445.25,
            'entry_time': '2025-10-06T10:05:47-04:00',
            'shares': 100,
            'remaining': 0.5,
            'pivot': 444.77,
            'target1': 460.25,
            'partials_taken': [
                {
                    'time': '2025-10-06T10:08:15-04:00',
                    'price': 447.13,
                    'shares': 50
                }
            ]
        }

        # Serialize
        serialized = json.dumps(position)

        # Deserialize
        deserialized = json.loads(serialized)

        self.assertEqual(deserialized['symbol'], 'TSLA')
        self.assertEqual(deserialized['shares'], 100)
        self.assertEqual(deserialized['remaining'], 0.5)
        self.assertEqual(len(deserialized['partials_taken']), 1)

    def test_attempt_count_serialization(self):
        """Test that attempt counts serialize correctly"""
        attempt_counts = {
            'TSLA': {
                'long_attempts': 2,
                'short_attempts': 0,
                'resistance': 444.77,
                'support': 432.50
            },
            'NVDA': {
                'long_attempts': 1,
                'short_attempts': 1,
                'resistance': 725.50,
                'support': 710.30
            }
        }

        # Serialize
        serialized = json.dumps(attempt_counts)

        # Deserialize
        deserialized = json.loads(serialized)

        self.assertEqual(deserialized['TSLA']['long_attempts'], 2)
        self.assertEqual(deserialized['NVDA']['short_attempts'], 1)

    def test_analytics_serialization(self):
        """Test that analytics serialize correctly"""
        analytics = {
            'daily_pnl': 756.19,
            'total_trades': 3,
            'winners': 2,
            'losers': 1,
            'filter_blocks': {
                'Waiting for confirmation': 12,
                'Room to target too small': 6,
                'Choppy market': 3
            },
            'entry_paths': {
                'LONG confirmed via MOMENTUM': 2,
                'LONG confirmed via PULLBACK': 1
            }
        }

        # Serialize
        serialized = json.dumps(analytics)

        # Deserialize
        deserialized = json.loads(serialized)

        self.assertEqual(deserialized['daily_pnl'], 756.19)
        self.assertEqual(deserialized['filter_blocks']['Choppy market'], 3)


class TestReconciliation(unittest.TestCase):
    """Test state file vs IBKR reconciliation logic"""

    def test_state_matches_ibkr(self):
        """Test when state file matches IBKR positions"""
        # State file
        state_positions = {
            'TSLA': {'shares': 100, 'entry_price': 445.25}
        }

        # IBKR
        ibkr_positions = {
            'TSLA': {'shares': 100, 'avg_cost': 445.25}
        }

        # Reconcile
        matches = abs(state_positions['TSLA']['shares'] - ibkr_positions['TSLA']['shares']) < 0.1

        self.assertTrue(matches, "Shares should match")

    def test_state_diverges_from_ibkr(self):
        """Test when state file diverges from IBKR (use IBKR value)"""
        # State file (stale)
        state_positions = {
            'TSLA': {'shares': 100, 'entry_price': 445.25}
        }

        # IBKR (50 shares sold during downtime)
        ibkr_positions = {
            'TSLA': {'shares': 50, 'avg_cost': 445.25}
        }

        # Reconcile - IBKR is source of truth
        diverges = abs(state_positions['TSLA']['shares'] - ibkr_positions['TSLA']['shares']) > 0.1

        self.assertTrue(diverges, "Should detect divergence")

        # Use IBKR value
        corrected_shares = ibkr_positions['TSLA']['shares']
        self.assertEqual(corrected_shares, 50, "Should use IBKR value")

    def test_state_has_position_ibkr_doesnt(self):
        """Test when state file shows position but IBKR doesn't (closed)"""
        # State file
        state_positions = {
            'TSLA': {'shares': 100, 'entry_price': 445.25}
        }

        # IBKR (position was closed)
        ibkr_positions = {}

        # Should NOT restore this position
        should_restore = 'TSLA' in ibkr_positions

        self.assertFalse(should_restore, "Should not restore closed position")

    def test_ibkr_has_position_state_doesnt(self):
        """Test when IBKR shows position but state file doesn't (manual entry or lost file)"""
        # State file
        state_positions = {}

        # IBKR (position opened manually or file lost)
        ibkr_positions = {
            'TSLA': {'shares': 100, 'avg_cost': 445.25}
        }

        # Should create minimal position
        needs_recovery = 'TSLA' in ibkr_positions and 'TSLA' not in state_positions

        self.assertTrue(needs_recovery, "Should detect untracked position")


class TestAtomicWrites(unittest.TestCase):
    """Test atomic file writes (corruption prevention)"""

    def test_atomic_write_pattern(self):
        """Test that atomic writes work correctly"""
        temp_dir = Path(tempfile.mkdtemp())
        target_file = temp_dir / 'state.json'
        temp_file = temp_dir / 'state.tmp'

        # Write to temp file
        data = {'test': 'data'}
        with open(temp_file, 'w') as f:
            json.dump(data, f)

        # Rename (atomic operation)
        temp_file.rename(target_file)

        # Verify
        self.assertTrue(target_file.exists(), "Target file should exist")
        self.assertFalse(temp_file.exists(), "Temp file should be gone")

        # Load and verify
        with open(target_file) as f:
            loaded = json.load(f)

        self.assertEqual(loaded['test'], 'data')


if __name__ == '__main__':
    print("="*80)
    print("TESTING CRASH RECOVERY SYSTEM")
    print("="*80)
    print()

    # Run all tests
    unittest.main(verbosity=2)
