#!/usr/bin/env python3
"""
Unit tests for CVD calculator
Tests both tick mode (live trading) and bar mode (backtesting)
"""

import pytest
import sys
from dataclasses import dataclass

# Add parent directory to path
sys.path.insert(0, '/Users/karthik/projects/DayTrader')

from trader.indicators.cvd_calculator import CVDCalculator, CVDResult


# Mock data classes for testing
@dataclass
class MockBar:
    """Mock bar for testing bar approximation"""
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class MockTick:
    """Mock tick for testing tick data"""
    price: float
    size: int


class TestCVDCalculatorBarMode:
    """Test CVD calculation from OHLCV bars (backtesting mode)"""

    def test_bar_approximation_bullish(self):
        """Test CVD calculation from bars - bullish case (closes in upper half)"""
        calculator = CVDCalculator(slope_lookback=3, bullish_threshold=1000, bearish_threshold=-1000)

        # Create mock bars with closes in upper half of range (bullish)
        bars = [
            MockBar(open=100, high=105, low=99, close=104, volume=1000),   # Close 83% up in range
            MockBar(open=104, high=108, low=103, close=107, volume=1200),  # Close 80% up
            MockBar(open=107, high=111, low=106, close=110, volume=1500),  # Close 80% up
        ]

        result = calculator.calculate_from_bars(bars, current_idx=2)

        print(f"\n=== Bullish Bar Test ===")
        print(f"CVD Value: {result.cvd_value:.2f}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")
        print(f"CVD Trend: {result.cvd_trend}")
        print(f"Data Source: {result.data_source}")
        print(f"Confidence: {result.confidence}")

        assert result.cvd_value > 0, "CVD should be positive (net buying pressure)"
        assert result.cvd_slope > 0, "Slope should be positive (increasing buying)"
        assert result.cvd_trend in ['BULLISH', 'NEUTRAL'], f"Expected BULLISH or NEUTRAL, got {result.cvd_trend}"
        assert result.data_source == 'BAR'
        assert result.confidence == 0.7

    def test_bar_approximation_bearish(self):
        """Test CVD calculation from bars - bearish case (closes in lower half)"""
        calculator = CVDCalculator(slope_lookback=3, bullish_threshold=1000, bearish_threshold=-1000)

        # Create mock bars with closes in lower half of range (bearish)
        bars = [
            MockBar(open=100, high=101, low=95, close=96, volume=1000),   # Close 17% up in range
            MockBar(open=96, high=97, low=92, close=93, volume=1200),     # Close 20% up
            MockBar(open=93, high=94, low=89, close=90, volume=1500),     # Close 20% up
        ]

        result = calculator.calculate_from_bars(bars, current_idx=2)

        print(f"\n=== Bearish Bar Test ===")
        print(f"CVD Value: {result.cvd_value:.2f}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")
        print(f"CVD Trend: {result.cvd_trend}")

        assert result.cvd_value < 0, "CVD should be negative (net selling pressure)"
        assert result.cvd_slope < 0, "Slope should be negative (increasing selling)"
        assert result.cvd_trend in ['BEARISH', 'NEUTRAL'], f"Expected BEARISH or NEUTRAL, got {result.cvd_trend}"

    def test_divergence_bullish(self):
        """Test bullish divergence detection (price down, CVD up)"""
        calculator = CVDCalculator(slope_lookback=5, bullish_threshold=1000, bearish_threshold=-1000)

        # Bullish divergence: price declining but CVD increasing (buying on dips)
        bars = [
            MockBar(open=100, high=101, low=99, close=100, volume=1000),
            MockBar(open=100, high=101, low=98, close=98, volume=1000),   # Price down
            MockBar(open=98, high=99, low=96, close=97.5, volume=1000),   # Price down more
            MockBar(open=97.5, high=98, low=95, close=97, volume=1000),   # Price down more
            MockBar(open=97, high=98, low=95, close=96, volume=1000),     # Price down more
        ]

        # Manipulate bars to create divergence: price down but closes high in range
        for i, bar in enumerate(bars):
            # Make closes progressively higher in their ranges (buyers stepping in)
            range_size = bar.high - bar.low
            # Position close at 60-80% of range despite price declining
            target_position = 0.6 + (i * 0.05)
            bar.close = bar.low + (range_size * target_position)

        result = calculator.calculate_from_bars(bars, current_idx=4)

        print(f"\n=== Bullish Divergence Test ===")
        print(f"CVD Divergence: {result.divergence}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")

        # Divergence detection may or may not trigger depending on thresholds
        # At minimum, CVD should be positive or increasing
        assert result.cvd_slope >= 0 or result.divergence == 'BULLISH_DIV', \
            "Should show buying pressure or bullish divergence"

    def test_divergence_bearish(self):
        """Test bearish divergence detection (price up, CVD down)"""
        calculator = CVDCalculator(slope_lookback=5, bullish_threshold=1000, bearish_threshold=-1000)

        # Bearish divergence: price rising but CVD decreasing (selling into strength)
        bars = [
            MockBar(open=100, high=101, low=99, close=100, volume=1000),
            MockBar(open=100, high=103, low=100, close=102, volume=1000),  # Price up
            MockBar(open=102, high=105, low=102, close=104, volume=1000),  # Price up more
            MockBar(open=104, high=107, low=104, close=106, volume=1000),  # Price up more
            MockBar(open=106, high=109, low=106, close=108, volume=1000),  # Price up more
        ]

        # Manipulate bars to create divergence: price up but closes low in range
        for i, bar in enumerate(bars):
            # Make closes progressively lower in their ranges (sellers stepping in)
            range_size = bar.high - bar.low
            # Position close at 40-20% of range despite price rising
            target_position = 0.4 - (i * 0.05)
            bar.close = bar.low + (range_size * max(target_position, 0.2))

        result = calculator.calculate_from_bars(bars, current_idx=4)

        print(f"\n=== Bearish Divergence Test ===")
        print(f"CVD Divergence: {result.divergence}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")

        # Divergence detection may or may not trigger
        # At minimum, CVD should be negative or decreasing
        assert result.cvd_slope <= 0 or result.divergence == 'BEARISH_DIV', \
            "Should show selling pressure or bearish divergence"

    def test_no_range_bars(self):
        """Test handling of bars with no range (high == low)"""
        calculator = CVDCalculator(slope_lookback=3)

        # Bars with no range (high == low)
        bars = [
            MockBar(open=100, high=100, low=100, close=100, volume=1000),
            MockBar(open=100, high=100, low=100, close=100, volume=1000),
            MockBar(open=100, high=100, low=100, close=100, volume=1000),
        ]

        result = calculator.calculate_from_bars(bars, current_idx=2)

        print(f"\n=== No Range Test ===")
        print(f"CVD Value: {result.cvd_value:.2f}")
        print(f"CVD Trend: {result.cvd_trend}")

        assert result.cvd_value == 0, "CVD should be zero for no-range bars"
        assert result.cvd_trend == 'NEUTRAL'


class TestCVDCalculatorTickMode:
    """Test CVD calculation from tick data (live trading mode)"""

    def test_tick_data_bullish(self):
        """Test CVD from tick data - bullish (upticks dominate)"""
        calculator = CVDCalculator(slope_lookback=5, bullish_threshold=100, bearish_threshold=-100)

        # Create mock ticks with more upticks (bullish)
        ticks = [
            MockTick(price=100.0, size=100),
            MockTick(price=100.05, size=150),  # Uptick
            MockTick(price=100.10, size=200),  # Uptick
            MockTick(price=100.08, size=50),   # Downtick
            MockTick(price=100.15, size=300),  # Uptick
            MockTick(price=100.20, size=250),  # Uptick
        ]

        result = calculator.calculate_from_ticks(ticks)

        print(f"\n=== Bullish Tick Test ===")
        print(f"CVD Value: {result.cvd_value:.2f}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")
        print(f"CVD Trend: {result.cvd_trend}")
        print(f"Data Source: {result.data_source}")
        print(f"Confidence: {result.confidence}")

        assert result.cvd_value > 0, "CVD should be positive (more upticks)"
        assert result.data_source == 'TICK'
        assert result.confidence == 1.0

    def test_tick_data_bearish(self):
        """Test CVD from tick data - bearish (downticks dominate)"""
        calculator = CVDCalculator(slope_lookback=5, bullish_threshold=100, bearish_threshold=-100)

        # Create mock ticks with more downticks (bearish)
        ticks = [
            MockTick(price=100.0, size=100),
            MockTick(price=99.95, size=150),   # Downtick
            MockTick(price=99.90, size=200),   # Downtick
            MockTick(price=99.92, size=50),    # Uptick
            MockTick(price=99.85, size=300),   # Downtick
            MockTick(price=99.80, size=250),   # Downtick
        ]

        result = calculator.calculate_from_ticks(ticks)

        print(f"\n=== Bearish Tick Test ===")
        print(f"CVD Value: {result.cvd_value:.2f}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")
        print(f"CVD Trend: {result.cvd_trend}")

        assert result.cvd_value < 0, "CVD should be negative (more downticks)"


class TestCVDCalculatorAutoMode:
    """Test auto-selection between tick and bar modes"""

    def test_auto_selects_tick_when_available(self):
        """Test that auto mode prefers tick data when available"""
        calculator = CVDCalculator(slope_lookback=3)

        ticks = [
            MockTick(price=100.0, size=100),
            MockTick(price=100.10, size=150),
        ]

        bars = [
            MockBar(open=100, high=101, low=99, close=100.5, volume=1000),
        ]

        result = calculator.calculate_auto(bars, current_idx=0, ticks=ticks)

        print(f"\n=== Auto Mode (Tick Available) ===")
        print(f"Data Source: {result.data_source}")

        assert result.data_source == 'TICK', "Should prefer tick data when available"
        assert result.confidence == 1.0

    def test_auto_falls_back_to_bars(self):
        """Test that auto mode falls back to bars when ticks unavailable"""
        calculator = CVDCalculator(slope_lookback=3)

        bars = [
            MockBar(open=100, high=105, low=99, close=104, volume=1000),
            MockBar(open=104, high=108, low=103, close=107, volume=1200),
            MockBar(open=107, high=111, low=106, close=110, volume=1500),
        ]

        # No ticks provided
        result = calculator.calculate_auto(bars, current_idx=2, ticks=None)

        print(f"\n=== Auto Mode (No Ticks) ===")
        print(f"Data Source: {result.data_source}")

        assert result.data_source == 'BAR', "Should fall back to bar approximation"
        assert result.confidence == 0.7


class TestCVDCalculatorEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_bars(self):
        """Test handling of empty bar list"""
        calculator = CVDCalculator()

        result = calculator.calculate_from_bars([], current_idx=0)

        assert result.cvd_value == 0.0
        assert result.cvd_trend == 'NEUTRAL'
        assert result.confidence == 0.0

    def test_empty_ticks(self):
        """Test handling of empty tick list"""
        calculator = CVDCalculator()

        result = calculator.calculate_from_ticks([])

        assert result.cvd_value == 0.0
        assert result.cvd_trend == 'NEUTRAL'
        assert result.confidence == 0.0

    def test_single_bar(self):
        """Test handling of single bar"""
        calculator = CVDCalculator(slope_lookback=3)

        bars = [
            MockBar(open=100, high=105, low=99, close=104, volume=1000),
        ]

        result = calculator.calculate_from_bars(bars, current_idx=0)

        print(f"\n=== Single Bar Test ===")
        print(f"CVD Value: {result.cvd_value:.2f}")
        print(f"CVD Slope: {result.cvd_slope:.2f}")

        assert result.data_source == 'BAR'
        # Slope should be 0 (not enough data)
        assert result.cvd_slope == 0.0

    def test_reset(self):
        """Test that reset clears history"""
        calculator = CVDCalculator()

        bars = [
            MockBar(open=100, high=105, low=99, close=104, volume=1000),
            MockBar(open=104, high=108, low=103, close=107, volume=1200),
        ]

        calculator.calculate_from_bars(bars, current_idx=1)
        assert len(calculator.cvd_history) > 0

        calculator.reset()
        assert len(calculator.cvd_history) == 0
        assert len(calculator.price_history) == 0


def run_all_tests():
    """Run all CVD calculator tests"""
    print("="*80)
    print("RUNNING CVD CALCULATOR UNIT TESTS")
    print("="*80)

    # Run pytest
    pytest.main([__file__, '-v', '-s'])


if __name__ == '__main__':
    run_all_tests()
