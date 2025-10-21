#!/usr/bin/env python3
"""
Cumulative Volume Delta (CVD) Calculator
Hybrid approach: tick data (live) or bar approximation (backtest)

CVD measures buying vs selling pressure by tracking the cumulative difference
between buying volume and selling volume.

Usage:
    # Backtesting (bar approximation)
    calculator = CVDCalculator(slope_lookback=5)
    result = calculator.calculate_from_bars(bars, current_idx)

    # Live trading (tick data)
    result = calculator.calculate_from_ticks(ticks)

    # Auto-select based on availability
    result = calculator.calculate_auto(bars, current_idx, ticks=ticks)
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class CVDResult:
    """CVD calculation result"""
    cvd_value: float           # Current CVD value
    cvd_slope: float           # Slope over last N bars (positive = buying, negative = selling)
    cvd_trend: str             # 'BULLISH', 'BEARISH', 'NEUTRAL'
    divergence: Optional[str]  # 'BULLISH_DIV', 'BEARISH_DIV', None
    data_source: str           # 'TICK' or 'BAR'
    confidence: float          # 0.0-1.0 confidence in the signal


class CVDCalculator:
    """
    Hybrid CVD calculator
    Auto-selects tick or bar mode based on data availability
    """

    def __init__(self, slope_lookback: int = 5, bullish_threshold: float = 1000,
                 bearish_threshold: float = -1000):
        """
        Args:
            slope_lookback: Number of bars to calculate CVD slope
            bullish_threshold: Minimum slope for BULLISH trend
            bearish_threshold: Maximum slope for BEARISH trend
        """
        self.slope_lookback = slope_lookback
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self.cvd_history = []  # Running CVD values
        self.price_history = []  # Price history for divergence detection

    def calculate_from_ticks(self, ticks: List) -> CVDResult:
        """
        Calculate CVD from tick data (live trading)

        Uses tick classification:
        - Uptick (price > last): Buying pressure
        - Downtick (price < last): Selling pressure

        Args:
            ticks: List of tick objects with .price, .size attributes

        Returns:
            CVDResult with data_source='TICK'
        """
        if not ticks or len(ticks) == 0:
            return CVDResult(
                cvd_value=0.0,
                cvd_slope=0.0,
                cvd_trend='NEUTRAL',
                divergence=None,
                data_source='TICK',
                confidence=0.0
            )

        cvd = 0.0
        last_price = None

        for tick in ticks:
            if last_price is not None:
                # Classify tick as buy or sell based on price movement
                if tick.price > last_price:
                    # Uptick = buying pressure
                    cvd += tick.size
                elif tick.price < last_price:
                    # Downtick = selling pressure
                    cvd -= tick.size
                # Equal price = no change

            last_price = tick.price
            self.price_history.append(tick.price)

        # Store in history
        self.cvd_history.append(cvd)

        # Calculate slope
        slope = self._calculate_slope()
        trend = self._determine_trend(slope)

        # Detect divergence (need price history)
        divergence = None
        if len(self.price_history) >= self.slope_lookback:
            recent_prices = self.price_history[-self.slope_lookback:]
            recent_cvd = self.cvd_history[-self.slope_lookback:]
            divergence = self._detect_divergence(recent_prices, recent_cvd)

        # Confidence: 1.0 for tick data (most accurate)
        confidence = 1.0

        return CVDResult(
            cvd_value=cvd,
            cvd_slope=slope,
            cvd_trend=trend,
            divergence=divergence,
            data_source='TICK',
            confidence=confidence
        )

    def calculate_from_bars(self, bars: List, current_idx: int) -> CVDResult:
        """
        Calculate CVD from OHLCV bars (backtesting)

        Uses close position heuristic:
        - Close in upper 50% of range = buying pressure dominates
        - Close in lower 50% of range = selling pressure dominates

        Formula:
            buying_volume = volume * ((close - low) / (high - low))
            selling_volume = volume * ((high - close) / (high - low))
            delta = buying_volume - selling_volume

        Args:
            bars: List of bar objects with .open, .high, .low, .close, .volume
            current_idx: Index of current bar

        Returns:
            CVDResult with data_source='BAR'
        """
        if not bars or current_idx < 0:
            return CVDResult(
                cvd_value=0.0,
                cvd_slope=0.0,
                cvd_trend='NEUTRAL',
                divergence=None,
                data_source='BAR',
                confidence=0.0
            )

        # Reset history for new calculation
        self.cvd_history = []
        self.price_history = []

        # Calculate CVD for each bar in lookback window
        # Use at least 20 bars for context, or all available
        lookback_start = max(0, current_idx - 20)

        cvd = 0.0

        for i in range(lookback_start, current_idx + 1):
            bar = bars[i]

            # Calculate where close is in the range
            range_size = bar.high - bar.low

            if range_size > 0:
                # Position of close in range (0.0 = low, 1.0 = high)
                close_position = (bar.close - bar.low) / range_size

                # Buying pressure: proportion of volume attributed to buyers
                # Selling pressure: remaining volume attributed to sellers
                buying_volume = bar.volume * close_position
                selling_volume = bar.volume * (1 - close_position)

                delta = buying_volume - selling_volume
            else:
                # No range (high == low) = neutral, no volume delta
                delta = 0

            cvd += delta

            # Store CVD and price for divergence detection
            self.cvd_history.append(cvd)
            self.price_history.append(bar.close)

        # Calculate slope over last N bars
        slope = self._calculate_slope()
        trend = self._determine_trend(slope)

        # Detect divergence
        divergence = None
        if len(self.price_history) >= self.slope_lookback:
            recent_prices = self.price_history[-self.slope_lookback:]
            recent_cvd = self.cvd_history[-self.slope_lookback:]
            divergence = self._detect_divergence(recent_prices, recent_cvd)

        # Confidence: 0.7 for bar approximation (less accurate than ticks)
        confidence = 0.7

        return CVDResult(
            cvd_value=cvd,
            cvd_slope=slope,
            cvd_trend=trend,
            divergence=divergence,
            data_source='BAR',
            confidence=confidence
        )

    def calculate_auto(self, bars: List, current_idx: int, ticks: Optional[List] = None) -> CVDResult:
        """
        Auto-select calculation method based on data availability

        Priority:
        1. Tick data (if available and non-empty) - most accurate
        2. Bar approximation (fallback) - good enough for backtesting

        Args:
            bars: Bar data (always available)
            current_idx: Current bar index
            ticks: Optional tick data (only available in live trading)

        Returns:
            CVDResult from best available data source
        """
        if ticks and len(ticks) > 0:
            # Live trading - use tick data
            logger.debug(f"Using TICK data for CVD calculation ({len(ticks)} ticks)")
            return self.calculate_from_ticks(ticks)
        else:
            # Backtesting - use bar approximation
            logger.debug(f"Using BAR approximation for CVD calculation (idx={current_idx})")
            return self.calculate_from_bars(bars, current_idx)

    def _calculate_slope(self) -> float:
        """
        Calculate CVD slope over last N bars using linear regression

        Returns:
            Slope value (positive = increasing buying, negative = increasing selling)
        """
        if len(self.cvd_history) < 2:
            return 0.0

        # Use min(slope_lookback, available history)
        lookback = min(self.slope_lookback, len(self.cvd_history))
        recent_cvd = self.cvd_history[-lookback:]

        if lookback < 2:
            return 0.0

        # Linear regression slope
        x = np.arange(len(recent_cvd))
        y = np.array(recent_cvd)

        # Calculate slope: Δy/Δx
        try:
            slope = np.polyfit(x, y, 1)[0]
            return slope
        except Exception as e:
            logger.warning(f"Failed to calculate CVD slope: {e}")
            return 0.0

    def _determine_trend(self, slope: float) -> str:
        """
        Classify CVD trend based on slope

        Args:
            slope: CVD slope from linear regression

        Returns:
            'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        if slope > self.bullish_threshold:
            return 'BULLISH'
        elif slope < self.bearish_threshold:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    def _detect_divergence(self, price_history: List[float], cvd_history: List[float]) -> Optional[str]:
        """
        Detect price/CVD divergence

        Divergence occurs when price and CVD move in opposite directions:
        - Bullish divergence: Price making lower lows, CVD making higher lows (reversal signal)
        - Bearish divergence: Price making higher highs, CVD making lower highs (reversal signal)

        Args:
            price_history: Recent price values
            cvd_history: Recent CVD values

        Returns:
            'BULLISH_DIV', 'BEARISH_DIV', or None
        """
        if len(price_history) < 3 or len(cvd_history) < 3:
            return None

        # Compare first and last values (simple divergence detection)
        # More sophisticated: could use swing highs/lows
        price_direction = price_history[-1] - price_history[0]
        cvd_direction = cvd_history[-1] - cvd_history[0]

        # Require significant divergence (>10% threshold)
        price_change_pct = abs(price_direction) / price_history[0] if price_history[0] != 0 else 0
        cvd_change_pct = abs(cvd_direction) / abs(cvd_history[0]) if cvd_history[0] != 0 else 0

        # Need at least 1% price move and opposite CVD move
        if price_change_pct < 0.01:
            return None

        # Bullish divergence: price down, CVD up
        if price_direction < 0 and cvd_direction > 0:
            return 'BULLISH_DIV'

        # Bearish divergence: price up, CVD down
        if price_direction > 0 and cvd_direction < 0:
            return 'BEARISH_DIV'

        return None

    def reset(self):
        """Reset CVD history (call at start of each new symbol)"""
        self.cvd_history = []
        self.price_history = []

    def get_debug_info(self) -> dict:
        """Get debug information about current CVD state"""
        return {
            'cvd_history_length': len(self.cvd_history),
            'price_history_length': len(self.price_history),
            'current_cvd': self.cvd_history[-1] if self.cvd_history else None,
            'current_slope': self._calculate_slope(),
            'lookback': self.slope_lookback,
            'bullish_threshold': self.bullish_threshold,
            'bearish_threshold': self.bearish_threshold
        }
