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
    """CVD calculation result (Oct 22, 2025 - Phase 1 Fix)"""
    cvd_value: float           # Current CVD value (cumulative delta)
    cvd_slope: float           # DEPRECATED: Slope over last N bars (kept for compatibility)
    cvd_trend: str             # 'BULLISH', 'BEARISH', 'NEUTRAL'
    divergence: Optional[str]  # 'BULLISH_DIV', 'BEARISH_DIV', None
    data_source: str           # 'TICK' or 'BAR'
    confidence: float          # 0.0-1.0 confidence in the signal

    # NEW METRICS (Oct 22, 2025 - Phase 1 Fix)
    buy_volume: float = 0.0    # Total buying volume
    sell_volume: float = 0.0   # Total selling volume
    imbalance_pct: float = 0.0 # (sell - buy) / total * 100 (positive = selling, negative = buying)

    # PRICE VALIDATION (Oct 26, 2025 - Phase 2 Fix)
    price_direction: str = 'NEUTRAL'  # 'UP', 'DOWN', 'NEUTRAL' (bar-to-bar movement)
    price_change_pct: float = 0.0     # Percentage price change
    signals_aligned: bool = True      # Do CVD and price agree?
    validation_reason: str = ''       # Why signals don't align (if applicable)


class CVDCalculator:
    """
    Hybrid CVD calculator
    Auto-selects tick or bar mode based on data availability
    """

    def __init__(self, slope_lookback: int = 5, imbalance_threshold: float = 10.0):
        """
        Oct 27, 2025 - Cleaned up deprecated slope-based parameters
        Oct 22, 2025 - Phase 1 Fix: Added percentage-based imbalance threshold

        Args:
            slope_lookback: Number of bars for divergence detection (still used)
            imbalance_threshold: Percentage imbalance for trend classification
                                10.0 = 10% more selling (BEARISH) or 10% more buying (BULLISH)
                                Formula: (sell_volume - buy_volume) / total_volume * 100
        """
        self.slope_lookback = slope_lookback
        self.imbalance_threshold = imbalance_threshold
        self.cvd_history = []  # Running CVD values
        self.price_history = []  # Price history for divergence detection

    def calculate_from_ticks(self, ticks: List, bar=None) -> CVDResult:
        """
        Calculate CVD from tick data (live trading)

        Oct 22, 2025 - Phase 1 Fix: Now uses percentage-based imbalance
        Oct 28, 2025 - CRITICAL BUG FIX: Use tick prices directly for candle color validation

        Uses tick classification:
        - Uptick (price > last): Buying pressure
        - Downtick (price < last): Selling pressure

        NEW: Tracks buy_volume and sell_volume separately
        NEW: Calculates imbalance_pct = (sell - buy) / total * 100
        NEW: Trend based on percentage imbalance (not slope)

        Args:
            ticks: List of tick objects with .price, .size attributes
            bar: DEPRECATED - no longer used (Oct 28, 2025 fix)

        Returns:
            CVDResult with data_source='TICK'
        """
        if not ticks or len(ticks) == 0:
            return CVDResult(
                cvd_value=0.0,
                cvd_slope=0.0,  # DEPRECATED
                cvd_trend='NEUTRAL',
                divergence=None,
                data_source='TICK',
                confidence=0.0,
                buy_volume=0.0,
                sell_volume=0.0,
                imbalance_pct=0.0
            )

        # Phase 1 Fix: Track buy/sell volume separately
        cvd = 0.0
        buy_volume = 0.0
        sell_volume = 0.0
        neutral_volume = 0.0
        last_price = None

        # Oct 28, 2025 FIX: Track first and last tick prices for candle color
        first_tick_price = ticks[0].price  # "Open" of the tick window
        last_tick_price = None

        for tick in ticks:
            if last_price is not None:
                # Classify tick as buy or sell based on price movement
                if tick.price > last_price:
                    # Uptick = buying pressure
                    buy_volume += tick.size
                    cvd += tick.size
                elif tick.price < last_price:
                    # Downtick = selling pressure
                    sell_volume += tick.size
                    cvd -= tick.size
                else:
                    # Equal price = neutral (don't count towards imbalance)
                    neutral_volume += tick.size

            last_price = tick.price
            last_tick_price = tick.price  # Update last tick price
            self.price_history.append(tick.price)

        # Store in history (for divergence detection)
        self.cvd_history.append(cvd)

        # Phase 1 Fix: Calculate percentage imbalance
        total_volume = buy_volume + sell_volume  # Excludes neutral ticks
        if total_volume > 0:
            # Positive imbalance_pct = more selling (BEARISH)
            # Negative imbalance_pct = more buying (BULLISH)
            imbalance_pct = ((sell_volume - buy_volume) / total_volume) * 100.0
        else:
            imbalance_pct = 0.0

        # Phase 1 Fix: Determine trend based on PERCENTAGE IMBALANCE (not slope)
        trend = self._determine_trend_from_imbalance(imbalance_pct)

        # Calculate slope for backward compatibility (DEPRECATED)
        slope = self._calculate_slope()

        # Detect divergence (need price history)
        divergence = None
        if len(self.price_history) >= self.slope_lookback:
            recent_prices = self.price_history[-self.slope_lookback:]
            recent_cvd = self.cvd_history[-self.slope_lookback:]
            divergence = self._detect_divergence(recent_prices, recent_cvd)

        # Confidence: 1.0 for tick data (most accurate)
        confidence = 1.0

        # PRICE VALIDATION (Oct 28, 2025 - CRITICAL FIX)
        # Use TICK DATA directly for candle color (not 5-second bars!)
        # Compare first tick price (open) vs last tick price (close)
        price_direction = 'NEUTRAL'
        price_change_pct = 0.0
        signals_aligned = True
        validation_reason = ''

        if last_tick_price is not None and first_tick_price > 0:
            # Calculate price change from first to last tick
            price_change = last_tick_price - first_tick_price
            price_change_pct = (price_change / first_tick_price) * 100

            # DOJI threshold: 0.02% (traditional definition)
            DOJI_THRESHOLD = 0.02  # 0.02% = essentially no movement

            # Determine candle color from TICKS
            if abs(price_change_pct) < DOJI_THRESHOLD:
                price_direction = 'NEUTRAL'  # DOJI - no clear winner
            elif price_change > 0:
                price_direction = 'UP'  # Green candle - buyers won
            else:
                price_direction = 'DOWN'  # Red candle - sellers won

            # Check alignment with CVD trend
            # BEARISH CVD (more selling) should produce RED candle (sellers won)
            # BULLISH CVD (more buying) should produce GREEN candle (buyers won)
            # DOJI (neutral) = misalignment (CVD showed pressure but no winner)
            if trend == 'BEARISH' and price_direction == 'UP':
                signals_aligned = False
                validation_reason = f"CVD BEARISH ({imbalance_pct:+.2f}% selling) but GREEN candle ({price_change_pct:+.2f}%)"
            elif trend == 'BULLISH' and price_direction == 'DOWN':
                signals_aligned = False
                validation_reason = f"CVD BULLISH ({imbalance_pct:+.2f}% buying) but RED candle ({price_change_pct:+.2f}%)"
            elif trend == 'BEARISH' and price_direction == 'NEUTRAL':
                signals_aligned = False
                validation_reason = f"CVD BEARISH ({imbalance_pct:+.2f}% selling) but DOJI (no winner)"
            elif trend == 'BULLISH' and price_direction == 'NEUTRAL':
                signals_aligned = False
                validation_reason = f"CVD BULLISH ({imbalance_pct:+.2f}% buying) but DOJI (no winner)"

        # Log detailed CVD breakdown (for debugging)
        logger.debug(f"CVD from ticks: buy={buy_volume:.0f}, sell={sell_volume:.0f}, "
                    f"neutral={neutral_volume:.0f}, imbalance={imbalance_pct:.1f}%, trend={trend}")
        logger.debug(f"Price validation (from ticks): first_tick=${first_tick_price:.2f}, "
                    f"last_tick=${last_tick_price:.2f}, change={price_change_pct:+.3f}%, "
                    f"direction={price_direction}, aligned={signals_aligned}")
        if not signals_aligned:
            logger.info(f"⚠️  CVD/PRICE MISMATCH: {validation_reason}")

        return CVDResult(
            cvd_value=cvd,
            cvd_slope=slope,  # DEPRECATED, kept for compatibility
            cvd_trend=trend,
            divergence=divergence,
            data_source='TICK',
            confidence=confidence,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            imbalance_pct=imbalance_pct,
            price_direction=price_direction,
            price_change_pct=price_change_pct,
            signals_aligned=signals_aligned,
            validation_reason=validation_reason
        )

    def calculate_from_bars(self, bars: List, current_idx: int) -> CVDResult:
        """
        Calculate CVD from OHLCV bars (backtesting)

        Oct 22, 2025 - Phase 1 Fix: Now uses percentage-based imbalance

        Uses close position heuristic:
        - Close in upper 50% of range = buying pressure dominates
        - Close in lower 50% of range = selling pressure dominates

        Formula:
            buying_volume = volume * ((close - low) / (high - low))
            selling_volume = volume * ((high - close) / (high - low))
            delta = buying_volume - selling_volume

        NEW: Tracks buy_volume and sell_volume separately
        NEW: Calculates imbalance_pct = (sell - buy) / total * 100

        Args:
            bars: List of bar objects with .open, .high, .low, .close, .volume
            current_idx: Index of current bar

        Returns:
            CVDResult with data_source='BAR'
        """
        if not bars or current_idx < 0:
            return CVDResult(
                cvd_value=0.0,
                cvd_slope=0.0,  # DEPRECATED
                cvd_trend='NEUTRAL',
                divergence=None,
                data_source='BAR',
                confidence=0.0,
                buy_volume=0.0,
                sell_volume=0.0,
                imbalance_pct=0.0
            )

        # Reset history for new calculation
        self.cvd_history = []
        self.price_history = []

        # Calculate CVD for each bar in lookback window
        # Use at least 20 bars for context, or all available
        lookback_start = max(0, current_idx - 20)

        cvd = 0.0
        total_buy_volume = 0.0
        total_sell_volume = 0.0

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

                # Phase 1 Fix: Accumulate buy/sell volumes
                total_buy_volume += buying_volume
                total_sell_volume += selling_volume
            else:
                # No range (high == low) = neutral, no volume delta
                delta = 0

            cvd += delta

            # Store CVD and price for divergence detection
            self.cvd_history.append(cvd)
            self.price_history.append(bar.close)

        # Phase 1 Fix: Calculate percentage imbalance
        total_volume = total_buy_volume + total_sell_volume
        if total_volume > 0:
            imbalance_pct = ((total_sell_volume - total_buy_volume) / total_volume) * 100.0
        else:
            imbalance_pct = 0.0

        # Phase 1 Fix: Determine trend based on PERCENTAGE IMBALANCE (not slope)
        trend = self._determine_trend_from_imbalance(imbalance_pct)

        # Calculate slope for backward compatibility (DEPRECATED)
        slope = self._calculate_slope()

        # Detect divergence
        divergence = None
        if len(self.price_history) >= self.slope_lookback:
            recent_prices = self.price_history[-self.slope_lookback:]
            recent_cvd = self.cvd_history[-self.slope_lookback:]
            divergence = self._detect_divergence(recent_prices, recent_cvd)

        # Confidence: 0.7 for bar approximation (less accurate than ticks)
        confidence = 0.7

        # Log detailed CVD breakdown (for debugging)
        logger.debug(f"CVD from bars: buy={total_buy_volume:.0f}, sell={total_sell_volume:.0f}, "
                    f"imbalance={imbalance_pct:.1f}%, trend={trend}")

        return CVDResult(
            cvd_value=cvd,
            cvd_slope=slope,  # DEPRECATED, kept for compatibility
            cvd_trend=trend,
            divergence=divergence,
            data_source='BAR',
            confidence=confidence,
            buy_volume=total_buy_volume,
            sell_volume=total_sell_volume,
            imbalance_pct=imbalance_pct
        )

    def calculate_auto(self, bars: List, current_idx: int, ticks: Optional[List] = None) -> CVDResult:
        """
        Calculate CVD from tick data ONLY - NO APPROXIMATIONS

        Oct 21, 2025: Removed bar approximation fallback. System must provide tick data
        or explicitly handle the failure. No silent fallbacks to inaccurate methods.

        Oct 28, 2025: CRITICAL BUG FIX - Use tick data directly for candle color
                      Removed bar parameter (was using 5-second bars incorrectly)

        Args:
            bars: Bar data (kept for backward compatibility, not used)
            current_idx: Current bar index (kept for backward compatibility, not used)
            ticks: REQUIRED tick data for accurate CVD

        Returns:
            CVDResult from tick data with candle color validation using ticks

        Raises:
            ValueError: If no tick data is available
        """
        if ticks and len(ticks) > 0:
            # Use tick data - the ONLY acceptable source
            logger.info(f"✅ CVD: Using TICK data ({len(ticks)} ticks)")

            # Oct 28, 2025 FIX: No longer pass bar to calculate_from_ticks
            # Candle color is now determined from tick prices (first vs last)
            return self.calculate_from_ticks(ticks, bar=None)
        else:
            # FAIL EXPLICITLY - no approximations allowed
            error_msg = f"❌ CVD FAILURE: No tick data available at bar {current_idx}. Cannot calculate accurate CVD."
            logger.error(error_msg)
            raise ValueError(error_msg)

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

    def _determine_trend_from_imbalance(self, imbalance_pct: float) -> str:
        """
        Classify CVD trend based on PERCENTAGE IMBALANCE (Oct 22, 2025 - Phase 1 Fix)

        This is the NEW method that replaces slope-based classification.
        Uses percentage of buy/sell volume to determine trend direction.

        Args:
            imbalance_pct: (sell_volume - buy_volume) / total_volume * 100
                          Positive = more selling (BEARISH)
                          Negative = more buying (BULLISH)

        Returns:
            'BULLISH' if imbalance < -threshold (more buying)
            'BEARISH' if imbalance > +threshold (more selling)
            'NEUTRAL' otherwise

        Example:
            Buy: 10,000, Sell: 15,000, Total: 25,000
            imbalance_pct = (15000 - 10000) / 25000 * 100 = 20.0% (BEARISH)

            Buy: 18,000, Sell: 12,000, Total: 30,000
            imbalance_pct = (12000 - 18000) / 30000 * 100 = -20.0% (BULLISH)
        """
        if imbalance_pct < -self.imbalance_threshold:
            # Negative imbalance = more buying than selling
            return 'BULLISH'
        elif imbalance_pct > self.imbalance_threshold:
            # Positive imbalance = more selling than buying
            return 'BEARISH'
        else:
            # Within threshold = balanced trading
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
            'imbalance_threshold': self.imbalance_threshold
        }
