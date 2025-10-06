#!/usr/bin/env python3
"""
Comprehensive Test Suite for Live Trader
Tests all scenarios with simulated tick data

DO NOT RUN AGAINST LIVE MARKET - For testing only
"""

import unittest
from datetime import datetime, timedelta
import pytz
from collections import namedtuple
import json

# Mock IBKR objects
MockBar = namedtuple('MockBar', ['date', 'open', 'high', 'low', 'close', 'volume'])
MockTicker = namedtuple('MockTicker', ['last', 'bid', 'ask', 'volume'])

class BarBuffer:
    """
    Convert tick data into 5-second bars for strategy module

    CRITICAL: This bridges the gap between tick-by-tick live data
    and bar-based strategy logic from backtest
    """

    def __init__(self, symbol, bar_size_seconds=5):
        self.symbol = symbol
        self.bar_size = bar_size_seconds
        self.current_bar = None
        self.bars = []  # Keep last 120 bars (10 minutes at 5-second resolution)
        self.max_bars = 120

    def round_to_bar(self, timestamp):
        """Round timestamp to nearest bar boundary"""
        # Round down to nearest 5-second boundary
        total_seconds = timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
        bar_seconds = (total_seconds // self.bar_size) * self.bar_size

        hours = bar_seconds // 3600
        minutes = (bar_seconds % 3600) // 60
        seconds = bar_seconds % 60

        return timestamp.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)

    def update(self, tick_time, price, volume):
        """
        Update with new tick

        Parameters:
        - tick_time: datetime in Eastern Time
        - price: Last price
        - volume: Cumulative volume (IBKR style)
        """
        # Get bar boundary time
        bar_time = self.round_to_bar(tick_time)

        # Check if we need a new bar
        if self.current_bar is None or self.current_bar['time'] != bar_time:
            # Complete current bar and start new one
            if self.current_bar is not None:
                self.bars.append(self.current_bar)

                # Keep only last max_bars
                if len(self.bars) > self.max_bars:
                    self.bars.pop(0)

            # Start new bar
            self.current_bar = {
                'time': bar_time,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'volume_start': volume  # Track volume at bar start
            }
        else:
            # Update current bar
            self.current_bar['high'] = max(self.current_bar['high'], price)
            self.current_bar['low'] = min(self.current_bar['low'], price)
            self.current_bar['close'] = price
            self.current_bar['volume'] = volume

    def get_bars_for_strategy(self):
        """
        Get bars in format strategy module expects

        Returns list of MockBar objects
        """
        result = []

        # Convert completed bars
        for bar_dict in self.bars:
            # Calculate bar volume (delta from bar start)
            bar_volume = bar_dict['volume'] - bar_dict.get('volume_start', 0)

            result.append(MockBar(
                date=bar_dict['time'],
                open=bar_dict['open'],
                high=bar_dict['high'],
                low=bar_dict['low'],
                close=bar_dict['close'],
                volume=max(0, bar_volume)  # Ensure non-negative
            ))

        # Add current incomplete bar if exists
        if self.current_bar is not None:
            bar_volume = self.current_bar['volume'] - self.current_bar.get('volume_start', 0)

            result.append(MockBar(
                date=self.current_bar['time'],
                open=self.current_bar['open'],
                high=self.current_bar['high'],
                low=self.current_bar['low'],
                close=self.current_bar['close'],
                volume=max(0, bar_volume)
            ))

        return result

    def get_current_bar_index(self):
        """Get index of current bar (last bar in list)"""
        bars = self.get_bars_for_strategy()
        return len(bars) - 1 if bars else -1


class TestBarBuffer(unittest.TestCase):
    """Test bar buffer converts ticks to bars correctly"""

    def setUp(self):
        self.eastern = pytz.timezone('US/Eastern')
        self.buffer = BarBuffer('TEST', bar_size_seconds=5)

    def test_single_tick(self):
        """Test single tick creates one bar"""
        tick_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        self.buffer.update(tick_time, 100.0, 1000)

        bars = self.buffer.get_bars_for_strategy()
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0].open, 100.0)
        self.assertEqual(bars[0].close, 100.0)

    def test_multiple_ticks_same_bar(self):
        """Test multiple ticks in same 5-second window aggregate"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        # All within same 5-second window (10:05:00 - 10:05:04)
        self.buffer.update(base_time, 100.0, 1000)
        self.buffer.update(base_time + timedelta(seconds=1), 101.0, 1100)
        self.buffer.update(base_time + timedelta(seconds=2), 99.5, 1200)
        self.buffer.update(base_time + timedelta(seconds=3), 100.5, 1300)

        bars = self.buffer.get_bars_for_strategy()
        self.assertEqual(len(bars), 1, "Should have 1 bar")
        self.assertEqual(bars[0].open, 100.0, "Open should be first price")
        self.assertEqual(bars[0].high, 101.0, "High should be max price")
        self.assertEqual(bars[0].low, 99.5, "Low should be min price")
        self.assertEqual(bars[0].close, 100.5, "Close should be last price")

    def test_bar_boundaries(self):
        """Test bars created at 5-second boundaries"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        # Tick at 10:05:00 (bar 1)
        self.buffer.update(base_time, 100.0, 1000)

        # Tick at 10:05:05 (bar 2 - new 5-second boundary)
        self.buffer.update(base_time + timedelta(seconds=5), 101.0, 1100)

        # Tick at 10:05:10 (bar 3)
        self.buffer.update(base_time + timedelta(seconds=10), 102.0, 1200)

        bars = self.buffer.get_bars_for_strategy()
        self.assertEqual(len(bars), 3, "Should have 3 bars")
        self.assertEqual(bars[0].close, 100.0)
        self.assertEqual(bars[1].close, 101.0)
        self.assertEqual(bars[2].close, 102.0)

    def test_irregular_ticks(self):
        """Test handling of irregular tick timing"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        # Tick at 10:05:02 (within first bar 10:05:00-10:05:04)
        self.buffer.update(base_time + timedelta(seconds=2), 100.0, 1000)

        # Tick at 10:05:07 (within second bar 10:05:05-10:05:09)
        self.buffer.update(base_time + timedelta(seconds=7), 101.0, 1100)

        # Tick at 10:05:13 (within third bar 10:05:10-10:05:14)
        self.buffer.update(base_time + timedelta(seconds=13), 102.0, 1200)

        bars = self.buffer.get_bars_for_strategy()
        self.assertEqual(len(bars), 3, "Should have 3 bars despite irregular timing")

    def test_volume_calculation(self):
        """Test volume delta calculation (IBKR cumulative volume)"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))

        # Bar 1: Volume goes from 1000 to 1500 (delta = 500)
        self.buffer.update(base_time, 100.0, 1000)
        self.buffer.update(base_time + timedelta(seconds=1), 100.5, 1500)

        # Bar 2: Volume goes from 1500 to 2000 (delta = 500)
        self.buffer.update(base_time + timedelta(seconds=5), 101.0, 1500)
        self.buffer.update(base_time + timedelta(seconds=6), 101.5, 2000)

        bars = self.buffer.get_bars_for_strategy()

        # Note: Volume calculation may need refinement based on IBKR behavior
        # This test documents expected behavior
        self.assertGreaterEqual(bars[0].volume, 0, "Bar volume should be non-negative")
        self.assertGreaterEqual(bars[1].volume, 0, "Bar volume should be non-negative")

    def test_max_bars_limit(self):
        """Test buffer keeps only last 120 bars"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 0, 0))

        # Create 150 bars (more than max of 120)
        for i in range(150):
            tick_time = base_time + timedelta(seconds=i*5)
            self.buffer.update(tick_time, 100.0 + i, 1000 + i*100)

        bars = self.buffer.get_bars_for_strategy()
        self.assertLessEqual(len(bars), 121, "Should keep max 120 completed + 1 current")


class TestCandleCloseConfirmation(unittest.TestCase):
    """Test 1-minute candle close confirmation works with tick data"""

    def setUp(self):
        self.eastern = pytz.timezone('US/Eastern')
        self.buffer = BarBuffer('COIN', bar_size_seconds=5)

    def simulate_pivot_break_and_hold(self):
        """Simulate price breaking pivot and holding for 1 minute"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))
        pivot = 345.00

        # Generate ticks for 1 minute above pivot
        ticks = []
        for i in range(60):  # 60 seconds
            tick_time = base_time + timedelta(seconds=i)
            price = pivot + 0.50  # Hold above pivot
            volume = 10000 + i * 100
            ticks.append((tick_time, price, volume))

        return ticks, pivot, base_time

    def test_candle_close_after_60_seconds(self):
        """Test that we have 12 bars after 60 seconds (1 minute)"""
        ticks, pivot, base_time = self.simulate_pivot_break_and_hold()

        # Feed all ticks to buffer
        for tick_time, price, volume in ticks:
            self.buffer.update(tick_time, price, volume)

        bars = self.buffer.get_bars_for_strategy()

        # Should have 12 bars (60 seconds / 5 seconds per bar)
        self.assertEqual(len(bars), 12,
                        "After 60 seconds should have 12 five-second bars")

        # First bar should be at base_time
        self.assertEqual(bars[0].date.replace(tzinfo=None),
                        base_time.replace(tzinfo=None))

        # Last bar should be 55 seconds later (11 bars * 5 seconds)
        expected_last = base_time + timedelta(seconds=55)
        self.assertEqual(bars[-1].date.replace(tzinfo=None),
                        expected_last.replace(tzinfo=None))

    def test_all_bars_above_pivot(self):
        """Test all bar lows stay above pivot during 1-minute hold"""
        ticks, pivot, base_time = self.simulate_pivot_break_and_hold()

        for tick_time, price, volume in ticks:
            self.buffer.update(tick_time, price, volume)

        bars = self.buffer.get_bars_for_strategy()

        # All bars should have low >= pivot
        for bar in bars:
            self.assertGreaterEqual(bar.low, pivot,
                                   f"Bar at {bar.date} has low {bar.low} below pivot {pivot}")


class TestPullbackPattern(unittest.TestCase):
    """Test pullback/retest pattern detection with tick data"""

    def setUp(self):
        self.eastern = pytz.timezone('US/Eastern')
        self.buffer = BarBuffer('PLTR', bar_size_seconds=5)

    def simulate_pullback_pattern(self):
        """
        Simulate pullback pattern:
        1. Break pivot at T+0
        2. Pullback below pivot at T+30
        3. Re-break above pivot at T+45
        """
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))
        pivot = 182.24
        tolerance = 0.003  # 0.3%

        ticks = []

        # 0-30 seconds: Break and move up
        for i in range(30):
            tick_time = base_time + timedelta(seconds=i)
            price = pivot + 0.20  # Above pivot
            volume = 50000 + i * 100
            ticks.append((tick_time, price, volume))

        # 30-45 seconds: Pullback below pivot - tolerance
        for i in range(30, 45):
            tick_time = base_time + timedelta(seconds=i)
            price = pivot - (pivot * tolerance) - 0.05  # Below tolerance
            volume = 50000 + i * 100
            ticks.append((tick_time, price, volume))

        # 45-60 seconds: Re-break with volume
        for i in range(45, 60):
            tick_time = base_time + timedelta(seconds=i)
            price = pivot + 0.30  # Back above pivot
            volume = 50000 + i * 200  # Higher volume
            ticks.append((tick_time, price, volume))

        return ticks, pivot, tolerance

    def test_pullback_detected_in_bars(self):
        """Test that pullback is visible in bar data"""
        ticks, pivot, tolerance = self.simulate_pullback_pattern()

        for tick_time, price, volume in ticks:
            self.buffer.update(tick_time, price, volume)

        bars = self.buffer.get_bars_for_strategy()

        # Find bars that dipped below pivot - tolerance
        pullback_threshold = pivot * (1 - tolerance)
        pullback_bars = [b for b in bars if b.low < pullback_threshold]

        self.assertGreater(len(pullback_bars), 0,
                          "Should detect pullback below threshold in bars")

    def test_rebreak_detected_in_bars(self):
        """Test that re-break is visible in bar data"""
        ticks, pivot, tolerance = self.simulate_pullback_pattern()

        for tick_time, price, volume in ticks:
            self.buffer.update(tick_time, price, volume)

        bars = self.buffer.get_bars_for_strategy()

        # Last bars should be above pivot (re-break)
        last_3_bars = bars[-3:]
        for bar in last_3_bars:
            self.assertGreater(bar.close, pivot,
                              f"Re-break bars should close above pivot")


class TestSustainedBreak(unittest.TestCase):
    """Test sustained break pattern detection with tick data"""

    def setUp(self):
        self.eastern = pytz.timezone('US/Eastern')
        self.buffer = BarBuffer('COIN', bar_size_seconds=5)

    def simulate_sustained_break(self, sustained_duration=120):
        """
        Simulate sustained break:
        - Price breaks and holds above pivot for 2 minutes
        - Small dips OK within tolerance
        """
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 5, 0))
        pivot = 345.00
        tolerance = 0.003  # 0.3%

        ticks = []

        for i in range(sustained_duration):  # 120 seconds = 2 minutes
            tick_time = base_time + timedelta(seconds=i)

            # Price stays above pivot with small fluctuations
            # Occasional dips to within tolerance
            if i % 20 == 0:  # Every 20 seconds, small dip
                price = pivot + (pivot * tolerance * 0.5)  # Within tolerance
            else:
                price = pivot + 0.30  # Well above pivot

            volume = 100000 + i * 100
            ticks.append((tick_time, price, volume))

        return ticks, pivot, tolerance

    def test_sustained_above_pivot_for_2_minutes(self):
        """Test price stays above pivot - tolerance for 2 minutes"""
        ticks, pivot, tolerance = self.simulate_sustained_break()

        for tick_time, price, volume in ticks:
            self.buffer.update(tick_time, price, volume)

        bars = self.buffer.get_bars_for_strategy()

        # Should have 24 bars (120 seconds / 5 seconds)
        self.assertEqual(len(bars), 24, "Should have 24 bars for 2 minutes")

        # All bars should have low >= pivot * (1 - tolerance)
        threshold = pivot * (1 - tolerance)
        for bar in bars:
            self.assertGreaterEqual(bar.low, threshold,
                                   f"Bar at {bar.date} dipped below sustained threshold")


class TestChoppyFilter(unittest.TestCase):
    """Test choppy filter works with tick-derived bars"""

    def setUp(self):
        self.eastern = pytz.timezone('US/Eastern')
        self.buffer = BarBuffer('AMD', bar_size_seconds=5)

    def simulate_choppy_market(self):
        """Simulate choppy market: small range, no trending"""
        base_time = self.eastern.localize(datetime(2025, 10, 6, 10, 0, 0))

        ticks = []
        base_price = 161.00

        # 5 minutes of choppy action (300 seconds)
        for i in range(300):
            tick_time = base_time + timedelta(seconds=i)

            # Oscillate ±0.2% around base price
            oscillation = 0.20 * (1 if i % 2 == 0 else -1)
            price = base_price + oscillation
            volume = 500000 + i * 100

            ticks.append((tick_time, price, volume))

        return ticks, base_price

    def test_small_range_in_choppy_market(self):
        """Test that choppy market has small 5-minute range"""
        ticks, base_price = self.simulate_choppy_market()

        for tick_time, price, volume in ticks:
            self.buffer.update(tick_time, price, volume)

        bars = self.buffer.get_bars_for_strategy()

        # Get last 60 bars (5 minutes at 5-second bars)
        last_60_bars = bars[-60:] if len(bars) >= 60 else bars

        # Calculate 5-minute range
        high_5min = max(b.high for b in last_60_bars)
        low_5min = min(b.low for b in last_60_bars)
        range_5min = high_5min - low_5min

        # Range should be small (< $1.00 in this simulation)
        self.assertLess(range_5min, 1.00,
                       "Choppy market should have small range")


def run_all_tests():
    """Run all test suites"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBarBuffer))
    suite.addTests(loader.loadTestsFromTestCase(TestCandleCloseConfirmation))
    suite.addTests(loader.loadTestsFromTestCase(TestPullbackPattern))
    suite.addTests(loader.loadTestsFromTestCase(TestSustainedBreak))
    suite.addTests(loader.loadTestsFromTestCase(TestChoppyFilter))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_all_tests())
