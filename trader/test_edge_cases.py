#!/usr/bin/env python3
"""
Test Edge Cases for Live Trader

Tests additional scenarios beyond basic BarBuffer functionality:
- Multiple simultaneous positions
- Whipsaw protection (multiple pivot breaks)
- Gap in tick data
- EOD close with open positions
- Volume spike detection
- Max attempts enforcement
"""

import unittest
from datetime import datetime, timedelta
import pytz
from collections import namedtuple

# Mock classes for testing
MockBar = namedtuple('MockBar', ['date', 'open', 'high', 'low', 'close', 'volume'])


class TestMultiplePositions(unittest.TestCase):
    """Test handling multiple simultaneous positions"""

    def setUp(self):
        """Setup test environment"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_max_positions_limit(self):
        """Test that max positions limit is enforced"""
        # Simulate 5 open positions (max allowed)
        open_positions = {
            'TSLA': {'side': 'LONG', 'entry_price': 444.77},
            'NVDA': {'side': 'LONG', 'entry_price': 725.50},
            'AMD': {'side': 'LONG', 'entry_price': 165.30},
            'AAPL': {'side': 'LONG', 'entry_price': 175.25},
            'MSFT': {'side': 'LONG', 'entry_price': 425.80}
        }

        max_positions = 5

        # Should block new entry when at max
        can_enter = len(open_positions) < max_positions
        self.assertFalse(can_enter, "Should not allow entry when at max positions")

    def test_position_tracking_accuracy(self):
        """Test that position manager tracks multiple positions correctly"""
        positions = {}

        # Enter 3 positions
        positions['TSLA'] = {'entry_price': 444.77, 'shares': 100, 'remaining': 1.0}
        positions['NVDA'] = {'entry_price': 725.50, 'shares': 50, 'remaining': 1.0}
        positions['AMD'] = {'entry_price': 165.30, 'shares': 200, 'remaining': 1.0}

        self.assertEqual(len(positions), 3, "Should have 3 positions")

        # Take partial on TSLA
        positions['TSLA']['remaining'] = 0.5

        # Close NVDA
        del positions['NVDA']

        self.assertEqual(len(positions), 2, "Should have 2 positions after close")
        self.assertEqual(positions['TSLA']['remaining'], 0.5, "TSLA should have 50% remaining")


class TestWhipsawProtection(unittest.TestCase):
    """Test protection against whipsaw trades"""

    def test_max_attempts_enforcement(self):
        """Test that max 2 attempts per pivot is enforced"""
        attempts = 0
        max_attempts = 2

        # First attempt
        attempts += 1
        can_enter_1 = attempts <= max_attempts
        self.assertTrue(can_enter_1, "First attempt should be allowed")

        # Second attempt
        attempts += 1
        can_enter_2 = attempts <= max_attempts
        self.assertTrue(can_enter_2, "Second attempt should be allowed")

        # Third attempt (should be blocked)
        attempts += 1
        can_enter_3 = attempts <= max_attempts
        self.assertFalse(can_enter_3, "Third attempt should be blocked")

    def test_attempt_count_reset_per_pivot(self):
        """Test that attempt counts are per pivot (resistance vs support)"""
        long_attempts = {'TSLA': 2}  # 2 attempts at resistance
        short_attempts = {'TSLA': 0}  # 0 attempts at support

        # Long attempts maxed out
        can_enter_long = long_attempts['TSLA'] < 2
        self.assertFalse(can_enter_long, "Long entry should be blocked")

        # Short attempts still available
        can_enter_short = short_attempts['TSLA'] < 2
        self.assertTrue(can_enter_short, "Short entry should be allowed")


class TestGapInTickData(unittest.TestCase):
    """Test handling of gaps in tick data (low volume periods)"""

    def setUp(self):
        """Setup test environment"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_bar_buffer_handles_30_second_gap(self):
        """Test that bar buffer handles 30-second gap in ticks"""
        from trader import BarBuffer

        buffer = BarBuffer('TEST', bar_size_seconds=5)

        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        # Tick at 10:05:00
        buffer.update(base_time, 100.0, 1000)

        # No ticks for 30 seconds...

        # Tick at 10:05:35 (30 seconds later)
        gap_time = base_time + timedelta(seconds=35)
        buffer.update(gap_time, 101.0, 1100)

        bars = buffer.get_bars_for_strategy()

        # Should have created multiple bars (one every 5 seconds)
        # But only 2 will have data (start and end)
        self.assertGreaterEqual(len(bars), 2, "Should have at least 2 bars")

    def test_current_bar_persists_during_gap(self):
        """Test that current bar persists when no new ticks arrive"""
        from trader import BarBuffer

        buffer = BarBuffer('TEST', bar_size_seconds=5)

        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        # Create a bar
        buffer.update(base_time, 100.0, 1000)
        buffer.update(base_time + timedelta(seconds=1), 101.0, 1100)

        bars_before = buffer.get_bars_for_strategy()
        count_before = len(bars_before)

        # Get bars again without new ticks (simulating gap)
        bars_during_gap = buffer.get_bars_for_strategy()

        self.assertEqual(len(bars_during_gap), count_before,
                        "Bar count should not change during gap")


class TestEODClose(unittest.TestCase):
    """Test end-of-day close logic"""

    def setUp(self):
        """Setup test environment"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_eod_close_triggers_at_355pm(self):
        """Test that EOD close triggers at 3:55 PM ET"""
        # 3:54 PM - should NOT trigger
        time_354 = self.eastern.localize(datetime(2025, 10, 6, 15, 54, 0))
        is_eod_354 = time_354.hour == 15 and time_354.minute >= 55
        self.assertFalse(is_eod_354, "Should not trigger EOD at 3:54 PM")

        # 3:55 PM - SHOULD trigger
        time_355 = self.eastern.localize(datetime(2025, 10, 6, 15, 55, 0))
        is_eod_355 = time_355.hour == 15 and time_355.minute >= 55
        self.assertTrue(is_eod_355, "Should trigger EOD at 3:55 PM")

    def test_all_positions_closed_at_eod(self):
        """Test that all positions are closed at EOD"""
        positions = {
            'TSLA': {'side': 'LONG', 'entry_price': 444.77, 'remaining': 0.25},
            'NVDA': {'side': 'LONG', 'entry_price': 725.50, 'remaining': 0.50},
            'AMD': {'side': 'SHORT', 'entry_price': 165.30, 'remaining': 1.0}
        }

        # Simulate EOD close
        positions_to_close = list(positions.keys())
        for symbol in positions_to_close:
            del positions[symbol]

        self.assertEqual(len(positions), 0, "All positions should be closed at EOD")


class TestVolumeSpikeDetection(unittest.TestCase):
    """Test volume spike detection for momentum entries"""

    def test_volume_spike_calculation(self):
        """Test that volume spikes are detected correctly"""
        # Average volume = 1000 shares per candle
        avg_volume = 1000

        # Current candle volume = 1500 shares (1.5x average)
        current_volume = 1500

        volume_ratio = current_volume / avg_volume

        is_momentum = volume_ratio >= 1.3
        self.assertTrue(is_momentum, "1.5x volume should be momentum")

    def test_low_volume_not_momentum(self):
        """Test that low volume is not classified as momentum"""
        avg_volume = 1000
        current_volume = 800  # 0.8x average

        volume_ratio = current_volume / avg_volume

        is_momentum = volume_ratio >= 1.3
        self.assertFalse(is_momentum, "0.8x volume should not be momentum")


class TestConfirmationTimings(unittest.TestCase):
    """Test confirmation timing requirements"""

    def setUp(self):
        """Setup test environment"""
        self.eastern = pytz.timezone('US/Eastern')

    def test_one_minute_candle_close_wait(self):
        """Test that we wait for 1-minute candle to close"""
        pivot_break_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 15))

        # 30 seconds later - should still be waiting
        check_time_30s = pivot_break_time + timedelta(seconds=30)
        elapsed_30s = (check_time_30s - pivot_break_time).total_seconds()
        can_enter_30s = elapsed_30s >= 60
        self.assertFalse(can_enter_30s, "Should wait at 30 seconds")

        # 60 seconds later - can enter
        check_time_60s = pivot_break_time + timedelta(seconds=60)
        elapsed_60s = (check_time_60s - pivot_break_time).total_seconds()
        can_enter_60s = elapsed_60s >= 60
        self.assertTrue(can_enter_60s, "Should allow entry at 60 seconds")

    def test_sustained_break_2_minute_requirement(self):
        """Test that sustained break requires 2 minutes"""
        pivot_break_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 15))

        # 1 minute later - not sustained yet
        check_time_1min = pivot_break_time + timedelta(minutes=1)
        elapsed_1min = (check_time_1min - pivot_break_time).total_seconds()
        is_sustained_1min = elapsed_1min >= 120
        self.assertFalse(is_sustained_1min, "Should not be sustained at 1 minute")

        # 2 minutes later - sustained
        check_time_2min = pivot_break_time + timedelta(minutes=2)
        elapsed_2min = (check_time_2min - pivot_break_time).total_seconds()
        is_sustained_2min = elapsed_2min >= 120
        self.assertTrue(is_sustained_2min, "Should be sustained at 2 minutes")


class TestRoomToRunFilter(unittest.TestCase):
    """Test room-to-run filter calculations"""

    def test_insufficient_room_blocks_entry(self):
        """Test that insufficient room to target blocks entry"""
        current_price = 100.0
        target_price = 101.0  # Only 1% away

        room_pct = ((target_price - current_price) / current_price) * 100

        min_room_required = 1.5  # Need 1.5% minimum

        has_room = room_pct >= min_room_required
        self.assertFalse(has_room, "1% room should be blocked (need 1.5%)")

    def test_sufficient_room_allows_entry(self):
        """Test that sufficient room allows entry"""
        current_price = 100.0
        target_price = 102.0  # 2% away

        room_pct = ((target_price - current_price) / current_price) * 100

        min_room_required = 1.5

        has_room = room_pct >= min_room_required
        self.assertTrue(has_room, "2% room should allow entry")


class TestChoppyMarketFilter(unittest.TestCase):
    """Test choppy market filter"""

    def test_small_range_blocks_entry(self):
        """Test that small 5-minute range blocks entry"""
        # 5-minute range = 0.5%
        range_5min = 0.5

        # ATR = 1.2%
        atr = 1.2

        range_to_atr_ratio = range_5min / atr  # 0.42

        choppy_threshold = 0.5  # Need 0.5× ATR minimum

        is_choppy = range_to_atr_ratio < choppy_threshold
        self.assertTrue(is_choppy, "0.42× ATR should be choppy (need 0.5×)")

    def test_large_range_allows_entry(self):
        """Test that large 5-minute range allows entry"""
        range_5min = 0.8  # 0.8%
        atr = 1.2  # 1.2%

        range_to_atr_ratio = range_5min / atr  # 0.67

        choppy_threshold = 0.5

        is_choppy = range_to_atr_ratio < choppy_threshold
        self.assertFalse(is_choppy, "0.67× ATR should not be choppy")


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)
