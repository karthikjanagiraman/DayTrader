"""
State Machine-Based Entry Logic for PS60 Strategy

This module contains the new state machine approach for entry confirmation,
replacing the old lookback loop logic.

Created: October 9, 2025
Updated: October 19, 2025 - Added CVD filter integration
"""

from datetime import datetime
import logging

# Import BreakoutState enum for state machine transitions (Oct 20, 2025)
from .breakout_state_tracker import BreakoutState

# Import CVD calculator for volume delta confirmation
CVD_AVAILABLE = False
CVDCalculator = None

try:
    # Try relative import first (when imported as package)
    from ..indicators.cvd_calculator import CVDCalculator
    CVD_AVAILABLE = True
except (ImportError, ValueError):
    try:
        # Fall back to absolute import (when run from backtest directory)
        from indicators.cvd_calculator import CVDCalculator
        CVD_AVAILABLE = True
    except ImportError:
        CVD_AVAILABLE = False
        logging.warning("CVD calculator not available - CVD filter disabled")

logger = logging.getLogger(__name__)


def _check_cvd_filter(strategy, symbol, bars, current_idx, side, bar_timestamp=None, backtester=None):
    """
    Check CVD (Cumulative Volume Delta) confirmation filter

    PHASE 8 (Oct 19, 2025): CVD integration for breakout validation
    Updated Oct 21, 2025: Support tick-based CVD for backtesting

    Args:
        strategy: Strategy instance (contains config)
        symbol: Stock symbol
        bars: Historical bars
        current_idx: Current bar index
        side: 'LONG' or 'SHORT'
        bar_timestamp: (Optional) Timestamp for backtest mode
        backtester: (Optional) Backtester instance for historical tick fetching

    Returns:
        tuple: (fails_filter, reason)
            - fails_filter: True if CVD blocks entry
            - reason: String explaining why it failed (or None if passed)
    """
    # Check if CVD filter is enabled
    if not CVD_AVAILABLE:
        return False, None

    cvd_config = strategy.config.get('confirmation', {}).get('cvd', {})
    if not cvd_config.get('enabled', False):
        return False, None

    try:
        # Initialize CVD calculator (Oct 27, 2025 - Cleaned up deprecated parameters)
        calculator = CVDCalculator(
            slope_lookback=cvd_config.get('slope_lookback', 5),
            imbalance_threshold=cvd_config.get('imbalance_threshold', 10.0)
        )

        # Get tick data if available
        # Live trading: get_tick_data(symbol) fetches last 10 seconds
        # Backtest mode: get_tick_data(symbol, bar_timestamp, backtester) fetches historical
        ticks = None
        if hasattr(strategy, 'get_tick_data'):
            if bar_timestamp is not None and backtester is not None:
                # Backtest mode - fetch historical ticks
                ticks = strategy.get_tick_data(symbol, bar_timestamp=bar_timestamp, backtester=backtester)
            else:
                # Live trading mode - fetch recent ticks
                ticks = strategy.get_tick_data(symbol)

        # Calculate CVD - MUST have tick data, no fallbacks allowed
        try:
            cvd_result = calculator.calculate_auto(bars, current_idx, ticks=ticks)
        except ValueError as e:
            # No tick data available - BLOCK ENTRY
            reason = f"CVD calculation failed: {str(e)}"
            logger.error(f"[CVD BLOCK] {symbol} Bar {current_idx}: {reason}")
            return True, reason

        # Check CVD trend matches entry direction
        # ENHANCED LOGGING (Oct 19, 2025): Detailed CVD analysis output
        cvd_details = {
            'cvd_value': cvd_result.cvd_value,
            'cvd_slope': cvd_result.cvd_slope,
            'cvd_trend': cvd_result.cvd_trend,
            'data_source': cvd_result.data_source,
            'divergence': cvd_result.divergence if hasattr(cvd_result, 'divergence') else None,
            'bar_idx': current_idx,
            'side': side
        }

        logger.info(f"[CVD ANALYSIS] {symbol} Bar {current_idx}: "
                   f"CVD={cvd_result.cvd_value:.0f}, Slope={cvd_result.cvd_slope:.0f}, "
                   f"Trend={cvd_result.cvd_trend}, Source={cvd_result.data_source}, "
                   f"Divergence={cvd_details['divergence']}")

        if side == 'LONG':
            # LONG entries need BULLISH CVD trend
            if cvd_result.cvd_trend == 'BEARISH':
                reason = f"CVD trend {cvd_result.cvd_trend} (expected BULLISH for LONG), slope {cvd_result.cvd_slope:.0f}"
                logger.info(f"[CVD BLOCK] {symbol}: {reason}")
                logger.info(f"[CVD BLOCK DETAIL] {symbol}: CVD={cvd_result.cvd_value:.0f}, "
                           f"Slope={cvd_result.cvd_slope:.0f}, Source={cvd_result.data_source}")
                return True, reason

            # Warn on bearish divergence (but don't block)
            if cvd_result.divergence == 'BEARISH_DIV':
                logger.warning(f"[CVD WARNING] {symbol}: Bearish divergence detected on LONG setup "
                             f"(CVD={cvd_result.cvd_value:.0f}, Slope={cvd_result.cvd_slope:.0f})")

        elif side == 'SHORT':
            # SHORT entries need BEARISH CVD trend
            if cvd_result.cvd_trend == 'BULLISH':
                reason = f"CVD trend {cvd_result.cvd_trend} (expected BEARISH for SHORT), slope {cvd_result.cvd_slope:.0f}"
                logger.info(f"[CVD BLOCK] {symbol}: {reason}")
                logger.info(f"[CVD BLOCK DETAIL] {symbol}: CVD={cvd_result.cvd_value:.0f}, "
                           f"Slope={cvd_result.cvd_slope:.0f}, Source={cvd_result.data_source}")
                return True, reason

            # Warn on bullish divergence (but don't block)
            if cvd_result.divergence == 'BULLISH_DIV':
                logger.warning(f"[CVD WARNING] {symbol}: Bullish divergence detected on SHORT setup "
                             f"(CVD={cvd_result.cvd_value:.0f}, Slope={cvd_result.cvd_slope:.0f})")

        # CVD confirmed
        logger.info(f"[CVD PASS] {symbol}: {cvd_result.cvd_trend} trend (slope {cvd_result.cvd_slope:.0f}), "
                   f"source {cvd_result.data_source}, CVD={cvd_result.cvd_value:.0f}")
        return False, None

    except Exception as e:
        logger.error(f"[CVD ERROR] {symbol}: Failed to calculate CVD: {e}")
        # If CVD calculation fails, don't block (fail open)
        return False, None


def _get_candle_bars(bars, tracking_idx, bars_per_candle, bar_buffer=None, current_idx=None):
    """
    Helper function to get candle bars using correct indexing

    CRITICAL FIX PART 3 (Oct 20, 2025): Calculate candle boundaries using absolute indices,
    then map to array indices for data access.

    Args:
        bars: Array of bars
        tracking_idx: Absolute bar index
        bars_per_candle: Number of bars per candle (12 for 1-min candle)
        bar_buffer: BarBuffer instance (for live trading with buffer)
        current_idx: Current array index (fallback for backtester)

    Returns:
        list: Candle bars, or empty list if unavailable
    """
    # Calculate candle boundaries using ABSOLUTE indices
    candle_start_abs = (tracking_idx // bars_per_candle) * bars_per_candle
    candle_end_abs = candle_start_abs + bars_per_candle

    # If bar_buffer available (live trading), map absolute to array indices
    if bar_buffer is not None:
        candle_start_array = bar_buffer.map_absolute_to_array_index(candle_start_abs)
        candle_end_array = bar_buffer.map_absolute_to_array_index(candle_end_abs - 1)

        if candle_start_array is None or candle_end_array is None:
            # Candle bars dropped from buffer (shouldn't happen with 20-min buffer)
            return []

        # Get candle bars (end_array + 1 for inclusive slicing)
        return bars[candle_start_array:candle_end_array + 1]
    else:
        # Fallback for backtester (no buffer, indices align)
        # CRITICAL: Use tracking_idx, not current_idx! (Oct 20, 2025 sustained volume fix)
        candle_start_array = (tracking_idx // bars_per_candle) * bars_per_candle
        candle_end_array = candle_start_array + bars_per_candle
        return bars[candle_start_array:candle_end_array]


def _check_sustained_volume(bars, tracking_idx, bars_per_candle, bar_buffer, current_idx, strategy, num_candles=1):
    """
    Helper function to check if volume is sustained over N subsequent candles.

    Oct 20, 2025: Configurable sustained volume requirement for all entry paths.

    Args:
        bars: Array of bars
        tracking_idx: Absolute bar index
        bars_per_candle: Number of bars per candle (12 for 1-min)
        bar_buffer: BarBuffer instance (for live trading)
        current_idx: Current array index (for backtester)
        strategy: Strategy instance (for accessing config)
        num_candles: Number of subsequent candles to check (default 1)

    Returns:
        tuple: (all_sustained: bool, volume_ratios: list)
            all_sustained: True if ALL checked candles meet threshold
            volume_ratios: List of volume ratios for each checked candle
    """
    sustained_threshold = getattr(strategy, 'sustained_volume_threshold', 1.5)
    volume_ratios = []

    for candle_offset in range(1, num_candles + 1):
        # Calculate tracking index for this subsequent candle
        subsequent_tracking_idx = tracking_idx + (candle_offset * bars_per_candle)

        # Get candle bars
        candle_bars = _get_candle_bars(bars, subsequent_tracking_idx, bars_per_candle, bar_buffer, current_idx)

        if not candle_bars or len(candle_bars) < bars_per_candle:
            # Can't check this candle yet (not enough data)
            return False, volume_ratios

        # Calculate this candle's volume
        candle_volume = sum(b.volume for b in candle_bars)

        # Calculate average volume using ABSOLUTE indices
        candle_start_abs = (subsequent_tracking_idx // bars_per_candle) * bars_per_candle
        avg_volume_lookback_abs = max(0, candle_start_abs - (20 * bars_per_candle))

        # Map to array indices
        if bar_buffer is not None:
            lookback_start_array = bar_buffer.map_absolute_to_array_index(avg_volume_lookback_abs)
            candle_start_array = bar_buffer.map_absolute_to_array_index(candle_start_abs)
            if lookback_start_array is not None and candle_start_array is not None:
                past_bars = bars[lookback_start_array:candle_start_array]
            else:
                past_bars = []
        else:
            # Fallback for backtester (indices align, use absolute indices directly)
            # CRITICAL: Use subsequent_tracking_idx, not current_idx! (Oct 20, 2025 sustained volume fix)
            candle_start_array = (subsequent_tracking_idx // bars_per_candle) * bars_per_candle
            avg_volume_lookback_array = max(0, candle_start_array - (20 * bars_per_candle))
            past_bars = bars[avg_volume_lookback_array:candle_start_array]

        if past_bars:
            avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
            avg_candle_volume = avg_volume_per_bar * bars_per_candle
        else:
            avg_candle_volume = candle_volume

        # Calculate volume ratio
        volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 1.0
        volume_ratios.append(volume_ratio)

        # Check if this candle meets threshold
        if volume_ratio < sustained_threshold:
            # This candle failed - return False immediately
            return False, volume_ratios

    # All candles met threshold
    return True, volume_ratios


def check_entry_state_machine(strategy, symbol, bars, current_idx, pivot_price, side='LONG',
                               target_price=None, cached_hourly_bars=None, absolute_idx=None, bar_buffer=None, backtester=None):
    """
    State machine-based entry confirmation

    CRITICAL FIX PART 2 (Oct 20, 2025):
    - current_idx = ARRAY index (for bars[] access)
    - absolute_idx = ABSOLUTE bar count (for state tracking)

    CRITICAL FIX PART 3 (Oct 20, 2025):
    - bar_buffer = BarBuffer instance for mapping absolute indices to array indices
    - Required for correct candle boundary calculations after buffer fills

    Updated Oct 21, 2025:
    - backtester = Backtester instance for historical tick fetching (CVD improvement)

    Instead of searching backwards through bars, we maintain state for each symbol
    and track progression through the decision tree.

    Args:
        current_idx: Array index for accessing bars[]
        absolute_idx: Absolute bar count for state tracking
        bar_buffer: BarBuffer instance (for candle mapping)
        backtester: Backtester instance for historical tick fetching (optional, backtest only)

    Returns:
        tuple: (should_enter, reason, entry_state)
    """
    tracker = strategy.state_tracker
    state = tracker.get_state(symbol)

    # Use current_idx (array index) for bars[] access
    current_price = bars[current_idx].close
    timestamp = bars[current_idx].date if hasattr(bars[current_idx], 'date') else datetime.now()

    # Use absolute_idx for state tracking (fallback to current_idx for backwards compatibility)
    tracking_idx = absolute_idx if absolute_idx is not None else current_idx

    # Check if breakout is too old (freshness check)
    if not tracker.check_freshness(symbol, tracking_idx, strategy.max_breakout_age_bars):
        tracker.reset_state(symbol)
        state = tracker.get_state(symbol)  # Get fresh state

    # STATE 1: MONITORING - Looking for breakout
    if state.state.value == 'MONITORING':
        # Check if price is through pivot
        is_through = (current_price > pivot_price) if side == 'LONG' else (current_price < pivot_price)

        if is_through:
            # Breakout detected! Store it in memory
            tracker.update_breakout(
                symbol=symbol,
                bar_idx=tracking_idx,  # Use absolute index for state
                price=current_price,
                timestamp=timestamp,
                pivot=pivot_price,
                side=side
            )
            return False, "Breakout detected, waiting for candle close", state.to_dict()

        return False, "Price not through pivot", state.to_dict()

    # STATE 2: BREAKOUT_DETECTED - Waiting for candle close
    elif state.state.value == 'BREAKOUT_DETECTED':
        # Check if we're at candle boundary
        bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # Dynamic based on bar resolution
        bars_into_candle = tracking_idx % bars_per_candle  # Use absolute index

        if bars_into_candle < (bars_per_candle - 1):
            # Not at candle close yet
            return False, "Waiting for 1-min candle close", {
                'phase': 'waiting_candle_close',
                'bars_remaining': (bars_per_candle - 1) - bars_into_candle
            }

        # We're at candle close - analyze it
        # CRITICAL FIX PART 3 (Oct 20, 2025): Use helper to get candle bars with correct indexing
        candle_bars = _get_candle_bars(bars, tracking_idx, bars_per_candle, bar_buffer, current_idx)

        if not candle_bars or len(candle_bars) < bars_per_candle:
            # Candle bars unavailable (dropped from buffer or incomplete)
            tracker.reset_state(symbol)
            return False, "Candle bars unavailable", state.to_dict()

        # Calculate candle characteristics
        candle_close = candle_bars[-1].close
        candle_open = candle_bars[0].open
        candle_size_pct = abs(candle_close - candle_open) / candle_open
        candle_volume = sum(b.volume for b in candle_bars)

        # Calculate volume ratio using ABSOLUTE indices for lookback
        # CRITICAL FIX PART 3 (Oct 20, 2025): Calculate lookback using absolute indices
        candle_start_abs = (tracking_idx // bars_per_candle) * bars_per_candle
        avg_volume_lookback_abs = max(0, candle_start_abs - (20 * bars_per_candle))

        # Map lookback absolute indices to array indices
        if bar_buffer is not None:
            lookback_start_array = bar_buffer.map_absolute_to_array_index(avg_volume_lookback_abs)
            candle_start_array = bar_buffer.map_absolute_to_array_index(candle_start_abs)

            if lookback_start_array is not None and candle_start_array is not None:
                past_bars = bars[lookback_start_array:candle_start_array]
            else:
                past_bars = []
        else:
            # Fallback for backtester
            candle_start_array = (current_idx // bars_per_candle) * bars_per_candle
            avg_volume_lookback_array = max(0, candle_start_array - (20 * bars_per_candle))
            past_bars = bars[avg_volume_lookback_array:candle_start_array]

        if past_bars:
            avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
            avg_candle_volume = avg_volume_per_bar * bars_per_candle
        else:
            avg_candle_volume = candle_volume

        volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 1.0

        # Check if candle closed correctly through pivot
        if side == 'LONG' and candle_close <= pivot_price:
            tracker.reset_state(symbol)
            return False, "Candle closed below resistance", state.to_dict()
        elif side == 'SHORT' and candle_close >= pivot_price:
            tracker.reset_state(symbol)
            return False, "Candle closed above support", state.to_dict()

        # Candle closed correctly - record it
        tracker.update_candle_close(
            symbol=symbol,
            bar_idx=tracking_idx,  # Use absolute index for state
            price=candle_close,
            timestamp=timestamp,
            volume_ratio=volume_ratio,
            candle_size_pct=candle_size_pct
        )

        # Classify breakout strength
        is_strong_volume = volume_ratio >= strategy.momentum_volume_threshold
        is_large_candle = candle_size_pct >= strategy.momentum_candle_min_pct

        # ENHANCED LOGGING (Oct 19, 2025): Log volume metrics at candle close
        logger.info(f"[VOLUME ANALYSIS] {symbol} Bar {current_idx} (Candle Close): "
                   f"Volume={candle_volume:,.0f}, Avg={avg_candle_volume:,.0f}, "
                   f"Ratio={volume_ratio:.2f}x (need {strategy.momentum_volume_threshold:.1f}x), "
                   f"Candle={candle_size_pct*100:.2f}% (need {strategy.momentum_candle_min_pct*100:.1f}%), "
                   f"Strong={is_strong_volume}, Large={is_large_candle}")

        # Pass bars, current_idx, volume_ratio, and min threshold for all filters
        # CRITICAL FIX (Oct 20, 2025): Pass volume_ratio and min_threshold to enable minimum volume filter
        # CRITICAL FIX (Oct 24, 2025): Adaptive threshold for insufficient history
        # Problem: Market open bar (bar 0) has 2x volume spike, inflates early averages
        # Solution: Use 1.0x threshold (neutral) until we have 20 bars of history
        bars_of_history = min(current_idx, 20)  # Can't have more than current_idx bars

        if bars_of_history < 20:
            # Insufficient history - use neutral threshold (1.0x = match average)
            min_vol_threshold = 1.0
            logger.debug(f"[ADAPTIVE THRESHOLD] {symbol} Bar {current_idx}: "
                        f"Only {bars_of_history} bars history, using 1.0x threshold")
        else:
            # Full 20-bar history - use normal threshold (1.5x)
            min_vol_threshold = getattr(strategy, 'min_initial_volume_threshold', 1.0)

        breakout_type = tracker.classify_breakout(symbol, is_strong_volume, is_large_candle,
                                                  bars=bars, current_idx=current_idx,
                                                  volume_ratio=volume_ratio,
                                                  min_volume_threshold=min_vol_threshold)

        logger.info(f"[BREAKOUT TYPE] {symbol} Bar {current_idx}: Classified as {breakout_type}")

        # CRITICAL FIX (Oct 20, 2025): Handle FAILED breakouts (sub-average volume)
        if breakout_type == 'FAILED':
            # Sub-average volume - reject this breakout entirely
            # This prevents Oct 15-style disasters (0.44x-0.79x volume entries)
            tracker.reset_state(symbol)
            logger.info(f"[BREAKOUT FAILED] {symbol} Bar {current_idx}: "
                       f"Sub-average volume ({volume_ratio:.2f}x < {min_vol_threshold:.1f}x threshold) - REJECTED "
                       f"(history: {bars_of_history} bars)")
            return False, f"Breakout rejected: Sub-average volume ({volume_ratio:.2f}x)", {'phase': 'volume_filter'}

        # PHASE 10 (Oct 21, 2025): CVD Continuous Monitoring - Check config
        cvd_config = strategy.config.get('confirmation', {}).get('cvd', {})
        cvd_enabled = cvd_config.get('enabled', False)
        continuous_monitoring = cvd_config.get('continuous_monitoring', False)

        if breakout_type == 'MOMENTUM':
            # Strong initial volume detected (1.0x+ with large candle)
            if cvd_enabled and continuous_monitoring:
                # With CVD monitoring, transition to CVD_MONITORING even for momentum
                # Will check for strong CVD spike (≥2000) or sustained CVD
                state.state = BreakoutState.CVD_MONITORING
                state.cvd_monitoring_active = True
                state.cvd_monitoring_start_time = timestamp
                state.cvd_consecutive_bullish_count = 0
                state.cvd_consecutive_bearish_count = 0
                state.backtester = backtester  # Store for tick data fetching (Oct 21, 2025)
                logger.info(f"[CVD_MONITORING] {symbol} Bar {current_idx}: "
                           f"MOMENTUM breakout ({volume_ratio:.1f}x), entering CVD monitoring")
                return False, f"Momentum detected, entering CVD monitoring", state.to_dict()
            else:
                # Legacy behavior: go to momentum confirmation wait
                state.state = BreakoutState.MOMENTUM_CONFIRMATION_WAIT
                logger.info(f"[MOMENTUM INITIAL] {symbol} Bar {current_idx}: "
                           f"{volume_ratio:.1f}x vol detected, waiting for sustained volume confirmation")
                return False, f"Strong volume detected ({volume_ratio:.1f}x), waiting for confirmation", state.to_dict()

        # Weak breakout
        if cvd_enabled and continuous_monitoring:
            # Transition to CVD monitoring for weak breakouts
            state.state = BreakoutState.CVD_MONITORING
            state.cvd_monitoring_active = True
            state.cvd_monitoring_start_time = timestamp
            state.cvd_consecutive_bullish_count = 0
            state.cvd_consecutive_bearish_count = 0
            state.backtester = backtester  # Store for tick data fetching (Oct 21, 2025)
            logger.info(f"[CVD_MONITORING] {symbol} Bar {current_idx}: "
                       f"WEAK breakout ({volume_ratio:.1f}x), entering CVD monitoring")
            return False, f"Weak breakout, entering CVD monitoring", state.to_dict()
        else:
            # Legacy behavior: continue to weak tracking
            return False, f"Weak breakout, tracking for pullback/sustained ({volume_ratio:.1f}x vol)", state.to_dict()

    # STATE 2.1: CVD_MONITORING - Continuous CVD checks (Oct 21, 2025) ⭐ NEW
    elif state.state.value == 'CVD_MONITORING':
        """
        Continuously monitor CVD on every 1-minute candle close

        TWO ENTRY PATHS:
        1. AGGRESSIVE: CVD slope ≥ 2000 → enter immediately
        2. PATIENT: CVD slope ≥ 1000 for 2+ consecutive candles → enter

        TIMEOUT: 10 minutes without confirmation → abandon
        """

        cvd_config = strategy.config['confirmation']['cvd']
        bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # Dynamic based on bar resolution

        # Check timeout (10 minutes)
        time_elapsed = (timestamp - state.cvd_monitoring_start_time).total_seconds() / 60
        max_time = cvd_config.get('max_monitoring_time_minutes', 10)

        if time_elapsed > max_time:
            logger.info(f"[CVD_MONITORING] {symbol}: TIMEOUT after {time_elapsed:.1f} minutes")
            tracker.reset_state(symbol)
            return False, f"CVD monitoring timeout ({time_elapsed:.1f} min)", {}

        # Wait for 1-minute candle close
        # bars_per_candle dynamically calculated:
        #   - 1-min bars: bars_per_candle=1 (check every bar since each bar IS a candle)
        #   - 5-sec bars: bars_per_candle=12 (check only on bar 11 = candle close)
        bars_into_candle = tracking_idx % bars_per_candle
        if bars_into_candle < (bars_per_candle - 1):
            return False, f"CVD monitoring: waiting for candle close ({bars_into_candle}/{bars_per_candle})", {
                'phase': 'cvd_monitoring',
                'time_elapsed_min': time_elapsed,
                'cvd_consecutive_count': state.cvd_consecutive_bullish_count if side == 'LONG' else state.cvd_consecutive_bearish_count
            }

        # At candle close - get CVD data
        try:
            # Use stored backtester from state OR passed backtester
            effective_backtester = state.backtester or backtester

            # PHASE 1: Check if we have pre-built CVD-enriched bars (Oct 21, 2025)
            cvd_value = None
            cvd_slope = None  # DEPRECATED
            cvd_trend = None
            cvd_source = None
            imbalance_pct = None  # NEW (Oct 22, 2025 - Phase 1 Fix)

            if effective_backtester and hasattr(effective_backtester, 'cvd_enriched_bars'):
                cvd_data = effective_backtester.cvd_enriched_bars.get(symbol)
                if cvd_data and 'bars' in cvd_data:
                    # Look up CVD for this specific bar
                    # Find the bar matching current_idx
                    # Note: cvd_data['bars'] is a list indexed from 0, matching current_idx
                    if current_idx < len(cvd_data['bars']):
                        bar_cvd = cvd_data['bars'][current_idx].get('cvd')
                        if bar_cvd:
                            cvd_value = bar_cvd.get('value', 0.0)
                            cvd_slope = bar_cvd.get('slope', 0.0)  # DEPRECATED
                            cvd_trend = bar_cvd.get('trend', 'NEUTRAL')
                            imbalance_pct = bar_cvd.get('imbalance_pct', 0.0)  # NEW: Percentage imbalance
                            cvd_source = 'CACHED'
                            logger.info(f"[CVD_MONITORING] {symbol} Bar {current_idx}: "
                                       f"✅ CVD from CACHE: imbalance={imbalance_pct:.1f}%, trend={cvd_trend}")

                            # CVD PRICE VALIDATION (Phase 2 - Oct 26, 2025)
                            # Check if CVD signal aligns with candle color
                            signals_aligned = bar_cvd.get('signals_aligned', True)
                            validation_reason = bar_cvd.get('validation_reason', '')

                            if not signals_aligned:
                                logger.info(f"[CVD_MONITORING] {symbol}: ❌ CVD PRICE VALIDATION FAILED - {validation_reason}")
                                tracker.reset_state(symbol)
                                return False, f"CVD price validation: {validation_reason}", {
                                    'phase': 'cvd_price_validation_failed'
                                }

                            logger.debug(f"[CVD_MONITORING] {symbol}: ✅ CVD PRICE VALIDATION PASSED")

            # PHASE 2: If no cached data, calculate CVD from ticks (fallback for live trading)
            if imbalance_pct is None:
                # Get tick data - REQUIRED, no fallbacks allowed
                ticks = None
                if hasattr(strategy, 'get_tick_data'):
                    if effective_backtester is not None:
                        # Backtest mode - fetch historical ticks for CURRENT bar
                        ticks = strategy.get_tick_data(symbol, bar_timestamp=timestamp, backtester=effective_backtester)
                        if not ticks:
                            logger.error(f"❌ NO TICK DATA returned for {symbol} at {timestamp}")
                    else:
                        # Live trading mode - fetch recent ticks
                        ticks = strategy.get_tick_data(symbol)
                        if not ticks:
                            logger.warning(f"⚠️ No tick data available for {symbol} in live mode")

                # Calculate CVD using auto mode
                import sys
                import os
                # Add parent directory to path if needed
                parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                if parent_dir not in sys.path:
                    sys.path.insert(0, parent_dir)

                from indicators.cvd_calculator import CVDCalculator
                calculator = CVDCalculator(
                    slope_lookback=cvd_config.get('slope_lookback', 5),
                    imbalance_threshold=cvd_config.get('imbalance_threshold', 10.0)
                )

                # CVD calculation WILL FAIL if no tick data - this is intentional
                try:
                    cvd_result = calculator.calculate_auto(bars, current_idx, ticks=ticks)
                    cvd_slope = cvd_result.cvd_slope  # DEPRECATED - kept for logging
                    cvd_trend = cvd_result.cvd_trend
                    imbalance_pct = cvd_result.imbalance_pct  # NEW: Use percentage imbalance
                    cvd_source = 'LIVE'
                    logger.info(f"[CVD_MONITORING] {symbol} Bar {current_idx}: "
                               f"✅ CVD from TICKS: imbalance={imbalance_pct:.1f}%, trend={cvd_trend}, "
                               f"buy={cvd_result.buy_volume:.0f}, sell={cvd_result.sell_volume:.0f}")

                    # CANDLE COLOR VALIDATION (Oct 27, 2025 - Phase 11)
                    # Check if CVD signal aligns with candle color (same as cached path)
                    signals_aligned = cvd_result.signals_aligned
                    validation_reason = cvd_result.validation_reason

                    if not signals_aligned:
                        logger.info(f"[CVD_MONITORING] {symbol}: ❌ CANDLE COLOR CONFLICT - {validation_reason}")
                        tracker.reset_state(symbol)
                        return False, f"Candle color conflict: {validation_reason}", {
                            'phase': 'cvd_candle_color_conflict'
                        }

                    logger.debug(f"[CVD_MONITORING] {symbol}: ✅ CANDLE COLOR VALIDATION PASSED")

                except ValueError as e:
                    # No tick data available - FAIL EXPLICITLY
                    logger.error(f"[CVD_MONITORING] {symbol} Bar {current_idx}: CVD FAILURE - {str(e)}")
                    tracker.reset_state(symbol)
                    return False, f"CVD calculation failed: {str(e)}", {
                        'phase': 'cvd_failure',
                        'error': str(e)
                    }

            # Store CVD state (works for both CACHED and LIVE sources)
            state.cvd_last_slope = cvd_slope  # DEPRECATED
            state.cvd_last_trend = cvd_trend
            state.cvd_last_imbalance_pct = imbalance_pct  # NEW (Oct 22, 2025 - Phase 1 Fix)

            # PATH 1: Strong CVD spike with confirmation (Oct 23, 2025 - Phase 10 tuning)
            # NEW: Initial candle ≥30% + next candle ≥10% confirmation
            strong_imbalance = cvd_config.get('strong_imbalance_threshold', 30.0)
            confirmation_imbalance = cvd_config.get('strong_confirmation_threshold', 10.0)

            # Check if we have a pending strong spike awaiting confirmation
            if hasattr(state, 'pending_strong_spike') and state.pending_strong_spike:
                # We're on the confirmation candle
                logger.info(f"[CVD_MONITORING] {symbol}: Checking STRONG SPIKE CONFIRMATION (initial: {state.pending_strong_imbalance:.1f}%, current: {imbalance_pct:.1f}%)")

                if side == 'LONG':
                    # Need confirmation candle to also be buying (negative) and ≥10%
                    if imbalance_pct <= -confirmation_imbalance:
                        logger.info(f"[CVD_MONITORING] {symbol}: ✅ STRONG SPIKE CONFIRMED! (initial {state.pending_strong_imbalance:.1f}% + confirm {imbalance_pct:.1f}%)")

                        # Validate price still above pivot
                        pivot = state.pivot_price
                        if current_price <= pivot:
                            logger.info(f"[CVD_MONITORING] {symbol}: ❌ BLOCKED - Price ${current_price:.2f} fell below pivot ${pivot:.2f}")
                            state.pending_strong_spike = False
                            tracker.reset_state(symbol)
                            return False, f"Price fell below pivot", {'phase': 'cvd_price_reversal'}

                        # VOLUME FILTER (Oct 26, 2025 - Phase 11): ALL entry paths must check volume
                        # Calculate 1-minute candle volume
                        candle_bars = _get_candle_bars(bars, tracking_idx, bars_per_candle, bar_buffer, current_idx)
                        if candle_bars and len(candle_bars) == bars_per_candle:
                            candle_volume = sum(b.volume for b in candle_bars)

                            # Calculate average volume (previous 20 1-minute candles)
                            candle_start_abs = (tracking_idx // bars_per_candle) * bars_per_candle
                            avg_volume_lookback_abs = max(0, candle_start_abs - (20 * bars_per_candle))

                            if bar_buffer is not None:
                                lookback_start_array = bar_buffer.map_absolute_to_array_index(avg_volume_lookback_abs)
                                candle_start_array = bar_buffer.map_absolute_to_array_index(candle_start_abs)
                                if lookback_start_array is not None and candle_start_array is not None:
                                    past_bars = bars[lookback_start_array:candle_start_array]
                                else:
                                    past_bars = []
                            else:
                                # Backtester mode
                                candle_start_array = (tracking_idx // bars_per_candle) * bars_per_candle
                                avg_volume_lookback_array = max(0, candle_start_array - (20 * bars_per_candle))
                                past_bars = bars[avg_volume_lookback_array:candle_start_array]

                            if past_bars:
                                avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
                                avg_candle_volume = avg_volume_per_bar * bars_per_candle
                                volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 1.0

                                # Use CVD volume threshold (default 1.5x for CVD confirmations)
                                cvd_volume_threshold = cvd_config.get('cvd_volume_threshold', 1.5)

                                if volume_ratio < cvd_volume_threshold:
                                    logger.info(f"[CVD_MONITORING] {symbol}: ❌ VOLUME FILTER - "
                                               f"{candle_volume:,.0f} shares ({volume_ratio:.2f}x) < {cvd_volume_threshold:.1f}x threshold")
                                    state.pending_strong_spike = False
                                    tracker.reset_state(symbol)
                                    return False, f"Volume filter: {volume_ratio:.2f}x < {cvd_volume_threshold:.1f}x", {'phase': 'volume_filter'}

                                logger.info(f"[CVD_MONITORING] {symbol}: ✅ VOLUME PASSED - "
                                           f"{candle_volume:,.0f} shares ({volume_ratio:.2f}x) >= {cvd_volume_threshold:.1f}x")

                        # Run other filters
                        fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                        if fails_stochastic:
                            state.pending_strong_spike = False
                            tracker.reset_state(symbol)
                            return False, stochastic_reason, {'phase': 'stochastic_filter'}

                        fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                        if fails_room:
                            state.pending_strong_spike = False
                            tracker.reset_state(symbol)
                            return False, room_reason, {'phase': 'room_to_run_filter'}

                        # ENTER!
                        state.pending_strong_spike = False
                        tracker.reset_state(symbol)
                        return True, f"Strong spike confirmed ({state.pending_strong_imbalance:.1f}% + {imbalance_pct:.1f}%)", {
                            'phase': 'cvd_aggressive_confirmed',
                            'initial_imbalance': state.pending_strong_imbalance,
                            'confirm_imbalance': imbalance_pct
                        }
                    else:
                        logger.info(f"[CVD_MONITORING] {symbol}: ❌ Confirmation failed ({imbalance_pct:.1f}% < -{confirmation_imbalance}%), clearing pending spike")
                        state.pending_strong_spike = False

                elif side == 'SHORT':
                    # Need confirmation candle to also be selling (positive) and ≥10%
                    if imbalance_pct >= confirmation_imbalance:
                        logger.info(f"[CVD_MONITORING] {symbol}: ✅ STRONG SPIKE CONFIRMED! (initial {state.pending_strong_imbalance:.1f}% + confirm {imbalance_pct:.1f}%)")

                        # Validate price still below pivot
                        pivot = state.pivot_price
                        if current_price >= pivot:
                            logger.info(f"[CVD_MONITORING] {symbol}: ❌ BLOCKED - Price ${current_price:.2f} rose above pivot ${pivot:.2f}")
                            state.pending_strong_spike = False
                            tracker.reset_state(symbol)
                            return False, f"Price rose above pivot", {'phase': 'cvd_price_reversal'}

                        # VOLUME FILTER (Oct 26, 2025 - Phase 11): ALL entry paths must check volume
                        # Calculate 1-minute candle volume
                        candle_bars = _get_candle_bars(bars, tracking_idx, bars_per_candle, bar_buffer, current_idx)
                        if candle_bars and len(candle_bars) == bars_per_candle:
                            candle_volume = sum(b.volume for b in candle_bars)

                            # Calculate average volume (previous 20 1-minute candles)
                            candle_start_abs = (tracking_idx // bars_per_candle) * bars_per_candle
                            avg_volume_lookback_abs = max(0, candle_start_abs - (20 * bars_per_candle))

                            if bar_buffer is not None:
                                lookback_start_array = bar_buffer.map_absolute_to_array_index(avg_volume_lookback_abs)
                                candle_start_array = bar_buffer.map_absolute_to_array_index(candle_start_abs)
                                if lookback_start_array is not None and candle_start_array is not None:
                                    past_bars = bars[lookback_start_array:candle_start_array]
                                else:
                                    past_bars = []
                            else:
                                # Backtester mode
                                candle_start_array = (tracking_idx // bars_per_candle) * bars_per_candle
                                avg_volume_lookback_array = max(0, candle_start_array - (20 * bars_per_candle))
                                past_bars = bars[avg_volume_lookback_array:candle_start_array]

                            if past_bars:
                                avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
                                avg_candle_volume = avg_volume_per_bar * bars_per_candle
                                volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 1.0

                                # Use CVD volume threshold (default 1.5x for CVD confirmations)
                                cvd_volume_threshold = cvd_config.get('cvd_volume_threshold', 1.5)

                                if volume_ratio < cvd_volume_threshold:
                                    logger.info(f"[CVD_MONITORING] {symbol}: ❌ VOLUME FILTER - "
                                               f"{candle_volume:,.0f} shares ({volume_ratio:.2f}x) < {cvd_volume_threshold:.1f}x threshold")
                                    state.pending_strong_spike = False
                                    tracker.reset_state(symbol)
                                    return False, f"Volume filter: {volume_ratio:.2f}x < {cvd_volume_threshold:.1f}x", {'phase': 'volume_filter'}

                                logger.info(f"[CVD_MONITORING] {symbol}: ✅ VOLUME PASSED - "
                                           f"{candle_volume:,.0f} shares ({volume_ratio:.2f}x) >= {cvd_volume_threshold:.1f}x")

                        # Run other filters
                        fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                        if fails_stochastic:
                            state.pending_strong_spike = False
                            tracker.reset_state(symbol)
                            return False, stochastic_reason, {'phase': 'stochastic_filter'}

                        fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                        if fails_room:
                            state.pending_strong_spike = False
                            tracker.reset_state(symbol)
                            return False, room_reason, {'phase': 'room_to_run_filter'}

                        # ENTER!
                        state.pending_strong_spike = False
                        tracker.reset_state(symbol)
                        return True, f"Strong spike confirmed ({state.pending_strong_imbalance:.1f}% + {imbalance_pct:.1f}%)", {
                            'phase': 'cvd_aggressive_confirmed',
                            'initial_imbalance': state.pending_strong_imbalance,
                            'confirm_imbalance': imbalance_pct
                        }
                    else:
                        logger.info(f"[CVD_MONITORING] {symbol}: ❌ Confirmation failed ({imbalance_pct:.1f}% < {confirmation_imbalance}%), clearing pending spike")
                        state.pending_strong_spike = False

            # Check for new strong spike (initial candle ≥30%)
            if side == 'LONG':
                if imbalance_pct <= -strong_imbalance:
                    logger.info(f"[CVD_MONITORING] {symbol}: 🔔 STRONG SPIKE detected ({imbalance_pct:.1f}% ≤ -{strong_imbalance}%), awaiting confirmation next candle")
                    state.pending_strong_spike = True
                    state.pending_strong_imbalance = imbalance_pct
            elif side == 'SHORT':
                if imbalance_pct >= strong_imbalance:
                    logger.info(f"[CVD_MONITORING] {symbol}: 🔔 STRONG SPIKE detected ({imbalance_pct:.1f}% ≥ {strong_imbalance}%), awaiting confirmation next candle")
                    state.pending_strong_spike = True
                    state.pending_strong_imbalance = imbalance_pct

            # PATH 2: Sustained CVD with Sliding Window (Oct 23, 2025 - Phase 10 tuning)
            # NEW: Continuously search for 3 consecutive candles ≥10% (no reset!)
            sustained_imbalance = cvd_config.get('imbalance_threshold', 10.0)
            min_consecutive = cvd_config.get('min_consecutive_bullish', 3) if side == 'LONG' else cvd_config.get('min_consecutive_bearish', 3)

            # Initialize imbalance history if not exists
            if not hasattr(state, 'cvd_imbalance_history'):
                state.cvd_imbalance_history = []

            # Add current imbalance to history
            state.cvd_imbalance_history.append(imbalance_pct)

            # Keep history manageable (last 20 candles is plenty)
            if len(state.cvd_imbalance_history) > 20:
                state.cvd_imbalance_history = state.cvd_imbalance_history[-20:]

            logger.debug(f"[CVD_MONITORING] {symbol}: Imbalance history: {[f'{x:.1f}' for x in state.cvd_imbalance_history[-5:]]}")

            # Sliding window: Check if ANY 3 consecutive values meet threshold
            if len(state.cvd_imbalance_history) >= min_consecutive:
                for i in range(len(state.cvd_imbalance_history) - min_consecutive + 1):
                    window = state.cvd_imbalance_history[i:i + min_consecutive]

                    if side == 'LONG':
                        # LONG: Need 3 consecutive BUYING (negative) candles ≥10%
                        if all(x <= -sustained_imbalance for x in window):
                            logger.info(f"[CVD_MONITORING] {symbol}: 🎯 SUSTAINED BUYING found! 3 consecutive candles: {[f'{x:.1f}%' for x in window]}")

                            # Validate price still above pivot
                            pivot = state.pivot_price
                            if current_price <= pivot:
                                logger.info(f"[CVD_MONITORING] {symbol}: ❌ BLOCKED - Price ${current_price:.2f} fell below pivot ${pivot:.2f}")
                                # Don't reset history - keep searching
                                continue

                            logger.info(f"[CVD_MONITORING] {symbol}: ✅ Price ${current_price:.2f} > pivot ${pivot:.2f} → Checking filters...")

                            # Run entry filters
                            fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                            if fails_stochastic:
                                # Don't reset history - filter may pass later
                                continue

                            fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                            if fails_room:
                                # Don't reset history - room may improve
                                continue

                            # ENTER!
                            tracker.reset_state(symbol)
                            return True, f"Sustained buying (3 consecutive: {[f'{x:.1f}%' for x in window]})", {
                                'phase': 'cvd_sustained',
                                'consecutive_imbalances': window,
                                'time_to_entry_min': time_elapsed
                            }

                    elif side == 'SHORT':
                        # SHORT: Need 3 consecutive SELLING (positive) candles ≥10%
                        if all(x >= sustained_imbalance for x in window):
                            logger.info(f"[CVD_MONITORING] {symbol}: 🎯 SUSTAINED SELLING found! 3 consecutive candles: {[f'{x:.1f}%' for x in window]}")

                            # Validate price still below pivot
                            pivot = state.pivot_price
                            if current_price >= pivot:
                                logger.info(f"[CVD_MONITORING] {symbol}: ❌ BLOCKED - Price ${current_price:.2f} rose above pivot ${pivot:.2f}")
                                # Don't reset history - keep searching
                                continue

                            logger.info(f"[CVD_MONITORING] {symbol}: ✅ Price ${current_price:.2f} < pivot ${pivot:.2f} → Checking filters...")

                            # Run entry filters
                            fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                            if fails_stochastic:
                                # Don't reset history - filter may pass later
                                continue

                            fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                            if fails_room:
                                # Don't reset history - room may improve
                                continue

                            # ENTER!
                            tracker.reset_state(symbol)
                            return True, f"Sustained selling (3 consecutive: {[f'{x:.1f}%' for x in window]})", {
                                'phase': 'cvd_sustained',
                                'consecutive_imbalances': window,
                                'time_to_entry_min': time_elapsed
                            }

            # Continue monitoring
            history_len = len(state.cvd_imbalance_history) if hasattr(state, 'cvd_imbalance_history') else 0
            return False, f"CVD monitoring (imbalance {imbalance_pct:.1f}%, history: {history_len} candles)", {
                'phase': 'cvd_monitoring',
                'imbalance_pct': imbalance_pct,
                'cvd_trend': cvd_trend,
                'time_elapsed_min': time_elapsed
            }

        except Exception as e:
            logger.error(f"[CVD_MONITORING] {symbol}: CVD calculation failed: {e}")
            # On error, fall back to old behavior (transition to weak tracking)
            state.state = BreakoutState.WEAK_BREAKOUT_TRACKING
            return False, f"CVD calculation error, falling back to weak tracking", state.to_dict()

    # STATE 2.5: MOMENTUM_CONFIRMATION_WAIT - Check sustained volume (Oct 20, 2025)
    elif state.state.value == 'MOMENTUM_CONFIRMATION_WAIT':
        # Check sustained volume using helper function
        bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # Dynamic based on bar resolution
        num_candles_to_check = getattr(strategy, 'sustained_volume_candles', 1)

        # Check if enough time has passed to check sustained volume
        candles_since_detection = (tracking_idx - state.candle_close_bar) // bars_per_candle

        if candles_since_detection < num_candles_to_check:
            # Not enough candles yet
            bars_remaining = (num_candles_to_check * bars_per_candle) - (tracking_idx - state.candle_close_bar)
            return False, f"Waiting for {num_candles_to_check} confirmation candle(s)", {
                'phase': 'momentum_confirmation_wait',
                'bars_remaining': bars_remaining
            }

        # Check if we're at a candle boundary
        bars_into_candle = tracking_idx % bars_per_candle
        if bars_into_candle < (bars_per_candle - 1):
            # Not at candle close yet, keep waiting
            return False, "Waiting for confirmation candle close", {
                'phase': 'momentum_confirmation_wait',
                'bars_remaining': (bars_per_candle - 1) - bars_into_candle
            }

        # We're at candle close - check sustained volume using helper
        all_sustained, volume_ratios = _check_sustained_volume(
            bars, state.candle_close_bar, bars_per_candle,
            bar_buffer, current_idx, strategy, num_candles_to_check
        )

        if not all_sustained:
            # Sustained volume failed - downgrade to WEAK
            state.state = BreakoutState.WEAK_BREAKOUT_TRACKING
            ratios_str = ", ".join([f"{r:.1f}x" for r in volume_ratios])
            logger.info(f"[MOMENTUM DOWNGRADED] {symbol} Bar {current_idx}: "
                       f"Sustained volume failed ({ratios_str}), downgrading to WEAK_BREAKOUT_TRACKING")
            return False, f"Momentum not sustained ({ratios_str}), tracking", state.to_dict()

        # All sustained volume checks passed!
        ratios_str = ", ".join([f"{r:.1f}x" for r in volume_ratios])
        logger.info(f"[SUSTAINED VOLUME CONFIRMED] {symbol} Bar {current_idx}: {ratios_str}")

        # Sustained volume confirmed - check remaining filters before entry
        is_choppy, choppy_reason = strategy._check_choppy_market(bars, current_idx)
        if is_choppy:
            tracker.reset_state(symbol)
            return False, choppy_reason, {'phase': 'choppy_filter'}

        if target_price:
            insufficient_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
            if insufficient_room:
                tracker.reset_state(symbol)
                return False, room_reason, {'phase': 'room_to_run_filter'}

        # STOCHASTIC FILTER (Oct 15, 2025): Check momentum confirmation
        fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
        if fails_stochastic:
            tracker.reset_state(symbol)
            return False, stochastic_reason, {'phase': 'stochastic_filter'}

        # CVD FILTER (Oct 19, 2025): Check volume delta confirmation
        # Updated Oct 21, 2025: Pass timestamp and backtester for tick-based CVD
        fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side,
                                                    bar_timestamp=timestamp, backtester=backtester)
        if fails_cvd:
            tracker.reset_state(symbol)
            return False, cvd_reason, {'phase': 'cvd_filter'}

        # ALL FILTERS PASSED - MOMENTUM ENTRY CONFIRMED!
        return True, f"MOMENTUM_BREAKOUT (sustained {ratios_str})", state.to_dict()

    # STATE 3/4: WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST
    elif state.state.value in ['WEAK_BREAKOUT_TRACKING', 'PULLBACK_RETEST']:
        # Update price action tracking
        tracker.update_price_action(symbol, current_price, tracking_idx, timestamp)  # Use absolute index for state

        # PHASE 7 (Oct 13, 2025): Re-check for momentum on subsequent 1-minute candles
        # If a WEAK breakout later shows momentum-level volume, upgrade and enter
        # CRITICAL: Check this in BOTH WEAK_BREAKOUT_TRACKING AND PULLBACK_RETEST states!
        bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # Dynamic based on bar resolution
        bars_into_candle = tracking_idx % bars_per_candle  # Use absolute index for candle boundary check

        # Check if we're at a new 1-minute candle close (and not the original breakout candle)
        if bars_into_candle == (bars_per_candle - 1) and tracking_idx > state.candle_close_bar:  # Compare absolute indices
            # We're at a new 1-minute candle close - re-check for momentum
            # CRITICAL FIX PART 3 (Oct 20, 2025): Use helper to get candle bars with correct indexing
            candle_bars = _get_candle_bars(bars, tracking_idx, bars_per_candle, bar_buffer, current_idx)

            if not candle_bars or len(candle_bars) < bars_per_candle:
                # Skip this candle if bars unavailable
                pass
            else:
                # Calculate this candle's volume
                candle_volume = sum(b.volume for b in candle_bars)

                # Calculate average candle volume using ABSOLUTE indices
                # CRITICAL FIX PART 3 (Oct 20, 2025): Calculate lookback using absolute indices
                candle_start_abs = (tracking_idx // bars_per_candle) * bars_per_candle
                avg_volume_lookback_abs = max(0, candle_start_abs - (20 * bars_per_candle))

                # Map lookback absolute indices to array indices
                if bar_buffer is not None:
                    lookback_start_array = bar_buffer.map_absolute_to_array_index(avg_volume_lookback_abs)
                    candle_start_array = bar_buffer.map_absolute_to_array_index(candle_start_abs)

                    if lookback_start_array is not None and candle_start_array is not None:
                        past_bars = bars[lookback_start_array:candle_start_array]
                    else:
                        past_bars = []
                else:
                    # Fallback for backtester
                    candle_start_array = (current_idx // bars_per_candle) * bars_per_candle
                    avg_volume_lookback_array = max(0, candle_start_array - (20 * bars_per_candle))
                    past_bars = bars[avg_volume_lookback_array:candle_start_array]

                if past_bars:
                    avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
                    avg_candle_volume = avg_volume_per_bar * bars_per_candle
                else:
                    avg_candle_volume = candle_volume

                volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 1.0

                # Calculate candle size
                candle_close = candle_bars[-1].close
                candle_open = candle_bars[0].open
                candle_size_pct = abs(candle_close - candle_open) / candle_open

                # Check if this candle meets MOMENTUM criteria
                is_strong_volume = volume_ratio >= strategy.momentum_volume_threshold
                is_large_candle = candle_size_pct >= strategy.momentum_candle_min_pct

                # DEBUG: Always print to see if this code runs
                print(f"[DELAYED MOMENTUM] {symbol} Bar {current_idx} (candle #{current_idx // bars_per_candle}) - "
                      f"{volume_ratio:.2f}x vol (need {strategy.momentum_volume_threshold:.1f}x), "
                      f"{candle_size_pct*100:.2f}% candle (need {strategy.momentum_candle_min_pct*100:.1f}%)")

                if is_strong_volume and is_large_candle:
                    # Strong volume detected on subsequent candle - NOW check SUSTAINED volume (Oct 20, 2025)
                    print(f"[MOMENTUM FOUND!] {symbol} Bar {current_idx} - Checking sustained volume on NEXT candle...")

                    # Store this candle's detection, wait for NEXT candle to confirm sustained volume
                    state.delayed_momentum_detected_bar = tracking_idx
                    state.delayed_momentum_volume_ratio = volume_ratio
                    return False, f"Delayed momentum detected ({volume_ratio:.1f}x), waiting for sustained volume", state.to_dict()

        # Check if we previously detected delayed momentum and need to check sustained volume
        if hasattr(state, 'delayed_momentum_detected_bar') and state.delayed_momentum_detected_bar is not None:
            num_candles_to_check = getattr(strategy, 'sustained_volume_candles', 1)
            candles_since_detection = (tracking_idx - state.delayed_momentum_detected_bar) // bars_per_candle

            if candles_since_detection >= num_candles_to_check and bars_into_candle == (bars_per_candle - 1):
                # We're at candle close - check sustained volume using helper
                all_sustained, volume_ratios = _check_sustained_volume(
                    bars, state.delayed_momentum_detected_bar, bars_per_candle,
                    bar_buffer, current_idx, strategy, num_candles_to_check
                )

                ratios_str = ", ".join([f"{r:.1f}x" for r in volume_ratios])

                if all_sustained:
                    # Sustained volume confirmed - proceed with entry checks!
                    print(f"[DELAYED SUSTAINED CONFIRMED!] {symbol} Bar {current_idx}: {ratios_str}")

                    # Check remaining filters
                    is_choppy, choppy_reason = strategy._check_choppy_market(bars, current_idx)
                    if is_choppy:
                        print(f"[BLOCKED] {symbol} Bar {current_idx} - {choppy_reason}")
                        tracker.reset_state(symbol)
                        return False, choppy_reason, {'phase': 'choppy_filter'}

                    if target_price:
                        insufficient_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                        if insufficient_room:
                            print(f"[BLOCKED] {symbol} Bar {current_idx} - {room_reason}")
                            tracker.reset_state(symbol)
                            return False, room_reason, {'phase': 'room_to_run_filter'}

                    # STOCHASTIC FILTER (Oct 15, 2025): Check momentum confirmation
                    fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                    if fails_stochastic:
                        print(f"[BLOCKED] {symbol} Bar {current_idx} - {stochastic_reason}")
                        tracker.reset_state(symbol)
                        return False, stochastic_reason, {'phase': 'stochastic_filter'}

                    # CVD FILTER (Oct 19, 2025): Check volume delta confirmation
                    # Updated Oct 21, 2025: Pass timestamp and backtester for tick-based CVD
                    fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side,
                                                                bar_timestamp=timestamp, backtester=backtester)
                    if fails_cvd:
                        print(f"[BLOCKED] {symbol} Bar {current_idx} - {cvd_reason}")
                        tracker.reset_state(symbol)
                        return False, cvd_reason, {'phase': 'cvd_filter'}

                    # DELAYED MOMENTUM CONFIRMED with SUSTAINED VOLUME - ENTER!
                    print(f"[ENTERING!] {symbol} Bar {current_idx} - MOMENTUM_BREAKOUT (delayed, sustained)")
                    return True, f"MOMENTUM_BREAKOUT (delayed {state.delayed_momentum_volume_ratio:.1f}x, sustained {ratios_str})", state.to_dict()
                else:
                    # Sustained volume NOT confirmed - reset delayed momentum detection
                    print(f"[DELAYED SUSTAINED FAILED] {symbol} Bar {current_idx}: {ratios_str}")
                    state.delayed_momentum_detected_bar = None
                    state.delayed_momentum_volume_ratio = None

        # Check for pullback (only in WEAK_BREAKOUT_TRACKING state)
        if state.state.value == 'WEAK_BREAKOUT_TRACKING':
            if tracker.check_pullback(symbol, current_price, strategy.pullback_distance_pct):
                return False, "Pullback detected, waiting for bounce", state.to_dict()

        # Check for pullback bounce (entry signal)
        if state.state.value == 'PULLBACK_RETEST':
            # PHASE 8 (Oct 16, 2025): FIX CRITICAL BUG - Aggregate to 1-minute candles
            # ROOT CAUSE: Was using 5-second bar data, causing meaningless volume/candle ratios
            # FIX: Use same 1-minute aggregation logic as MOMENTUM path (lines 150-180)

            bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # Dynamic based on bar resolution
            bars_into_candle = current_idx % bars_per_candle

            # Only check at 1-minute candle close (like MOMENTUM path does)
            if bars_into_candle == (bars_per_candle - 1):
                # We're at a 1-minute candle close - aggregate and check bounce
                candle_start = (current_idx // bars_per_candle) * bars_per_candle
                candle_end = candle_start + bars_per_candle
                candle_bars = bars[candle_start:candle_end]

                # ✅ Calculate 1-minute aggregated volume
                candle_volume = sum(b.volume for b in candle_bars)

                # ✅ Calculate average of past 20 1-minute candles
                avg_volume_lookback = max(0, candle_start - (20 * bars_per_candle))
                if avg_volume_lookback < candle_start:
                    past_bars = bars[avg_volume_lookback:candle_start]
                    if past_bars:
                        avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
                        avg_candle_volume = avg_volume_per_bar * bars_per_candle
                    else:
                        avg_candle_volume = candle_volume
                else:
                    avg_candle_volume = candle_volume

                # ✅ Calculate 1-minute candle size
                candle_open = candle_bars[0].open
                candle_close = candle_bars[-1].close
                current_candle_size_pct = abs(candle_close - candle_open) / candle_open

                # ✅ Calculate previous price (for bounce direction check)
                if candle_start > 0:
                    previous_price = bars[candle_start - 1].close
                else:
                    previous_price = None

                # ✅ NOW check bounce with 1-minute aggregated data
                bounce_confirmed, adjusted_entry, adjusted_stop = tracker.check_pullback_bounce(
                        symbol,
                        current_price,
                        bounce_threshold_pct=0.0015,  # Increased from 0.001 to 0.0015
                        previous_price=previous_price,
                        current_volume=candle_volume,  # ✅ 1-minute volume
                        avg_volume=avg_candle_volume,  # ✅ Average of 20 1-minute candles
                        candle_size_pct=current_candle_size_pct,  # ✅ 1-minute candle size
                        momentum_volume_threshold=strategy.pullback_volume_threshold,  # FIX: Use pullback threshold (2.0x)
                        momentum_candle_threshold=strategy.pullback_candle_min_pct)  # FIX: Use pullback threshold (0.5%)
            else:
                # Not at 1-minute candle close yet, continue waiting
                bounce_confirmed = False
                adjusted_entry = None
                adjusted_stop = None

            if bounce_confirmed:
                # Pullback bounce confirmed with strong volume - NOW check SUSTAINED volume (Oct 20, 2025)

                # ENHANCED LOGGING (Oct 19, 2025): Log pullback bounce metrics
                logger.info(f"[PULLBACK BOUNCE] {symbol} Bar {current_idx}: "
                           f"Volume={candle_volume:,.0f}, Avg={avg_candle_volume:,.0f}, "
                           f"Ratio={candle_volume/avg_candle_volume:.2f}x (need {strategy.pullback_volume_threshold:.1f}x), "
                           f"Candle={current_candle_size_pct*100:.2f}% (need {strategy.pullback_candle_min_pct*100:.1f}%)")

                # Store bounce detection, wait for NEXT candle to confirm sustained volume
                state.pullback_bounce_detected_bar = tracking_idx
                state.pullback_bounce_volume_ratio = candle_volume / avg_candle_volume
                state.pullback_adjusted_entry = adjusted_entry
                state.pullback_adjusted_stop = adjusted_stop
                return False, f"Pullback bounce detected ({state.pullback_bounce_volume_ratio:.1f}x), waiting for sustained volume", state.to_dict()

            # Check if we previously detected pullback bounce and need to check sustained volume
            if hasattr(state, 'pullback_bounce_detected_bar') and state.pullback_bounce_detected_bar is not None:
                bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # Dynamic based on bar resolution
                num_candles_to_check = getattr(strategy, 'sustained_volume_candles', 1)
                candles_since_detection = (tracking_idx - state.pullback_bounce_detected_bar) // bars_per_candle
                bars_into_candle = tracking_idx % bars_per_candle

                if candles_since_detection >= num_candles_to_check and bars_into_candle == (bars_per_candle - 1):
                    # We're at candle close - check sustained volume using helper
                    all_sustained, volume_ratios = _check_sustained_volume(
                        bars, state.pullback_bounce_detected_bar, bars_per_candle,
                        bar_buffer, current_idx, strategy, num_candles_to_check
                    )

                    ratios_str = ", ".join([f"{r:.1f}x" for r in volume_ratios])
                    logger.info(f"[PULLBACK SUSTAINED CHECK] {symbol} Bar {current_idx}: {ratios_str}")

                    if all_sustained:
                        # Sustained volume confirmed - proceed with entry checks!

                        # FIX #1 (Oct 15, 2025): Check time since initial break (staleness check)
                        if hasattr(strategy, 'max_retest_time_minutes'):
                            time_since_breakout = (timestamp - state.breakout_detected_at).total_seconds() / 60
                            if time_since_breakout > strategy.max_retest_time_minutes:
                                tracker.reset_state(symbol)
                                return False, f"Stale retest: {time_since_breakout:.1f} min since initial break (max {strategy.max_retest_time_minutes} min)", {'phase': 'staleness_filter'}

                        # FIX #2 (Oct 15, 2025): Check entry position relative to pivot
                        if side == 'LONG':
                            pct_above_pivot = (current_price - pivot_price) / pivot_price
                            if pct_above_pivot > strategy.max_entry_above_resistance:
                                tracker.reset_state(symbol)
                                return False, f"Entry too far above resistance: {pct_above_pivot*100:.2f}% (max {strategy.max_entry_above_resistance*100:.1f}%)", {'phase': 'entry_position_filter'}
                        elif side == 'SHORT':
                            pct_below_pivot = (pivot_price - current_price) / pivot_price
                            if pct_below_pivot > strategy.max_entry_below_support:
                                tracker.reset_state(symbol)
                                return False, f"Entry too far below support: {pct_below_pivot*100:.2f}% (max {strategy.max_entry_below_support*100:.1f}%)", {'phase': 'entry_position_filter'}

                        if target_price:
                            insufficient_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                            if insufficient_room:
                                tracker.reset_state(symbol)
                                return False, room_reason, {'phase': 'room_to_run_filter'}

                        # STOCHASTIC FILTER (Oct 15, 2025): Check momentum confirmation
                        fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                        if fails_stochastic:
                            tracker.reset_state(symbol)
                            return False, stochastic_reason, {'phase': 'stochastic_filter'}

                        # CVD FILTER (Oct 19, 2025): Check volume delta confirmation
                        # Updated Oct 21, 2025: Pass timestamp and backtester for tick-based CVD
                        fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side,
                                                                    bar_timestamp=timestamp, backtester=backtester)
                        if fails_cvd:
                            tracker.reset_state(symbol)
                            return False, cvd_reason, {'phase': 'cvd_filter'}

                        # PULLBACK BOUNCE CONFIRMED with SUSTAINED VOLUME - ENTER!
                        entry_state = state.to_dict()
                        entry_state['adjusted_entry_pivot'] = state.pullback_adjusted_entry
                        entry_state['adjusted_stop'] = state.pullback_adjusted_stop
                        return True, f"PULLBACK_RETEST (bounce {state.pullback_bounce_volume_ratio:.1f}x, sustained {ratios_str})", entry_state
                    else:
                        # Sustained volume NOT confirmed - reset pullback detection
                        logger.info(f"[PULLBACK SUSTAINED FAILED] {symbol} Bar {current_idx}: {ratios_str}")
                        state.pullback_bounce_detected_bar = None
                        state.pullback_bounce_volume_ratio = None
                        state.pullback_adjusted_entry = None
                        state.pullback_adjusted_stop = None

            return False, "Waiting for momentum on pullback bounce", state.to_dict()

        # Check for sustained break
        # PHASE 6 (Oct 12, 2025): Pass hourly SMA levels and momentum parameters
        required_bars = (strategy.sustained_break_minutes * 60) // strategy.bar_size_seconds  # e.g., 2 min = 2 bars @ 1-min or 24 bars @ 5-sec

        # Calculate hourly SMA levels for next level detection
        from .sma_calculator import calculate_sma_from_bars
        hourly_sma_levels = None
        if cached_hourly_bars and len(cached_hourly_bars) >= 20:
            hourly_sma_levels = {}
            for period in [5, 10, 20]:
                sma_value = calculate_sma_from_bars(cached_hourly_bars, period)
                if sma_value:
                    hourly_sma_levels[f'sma{period}'] = sma_value

        # Calculate momentum parameters (volume, candle size)
        # Oct 28, 2025 - Issue #2 & #3 Fix: Use helper functions for proper candle aggregation
        # Live: Aggregates 5-second bars to 1-minute candles
        # Backtest: Uses 1-minute bars directly
        candle_metrics = strategy.get_current_candle_metrics(bars, current_idx)

        if candle_metrics is None:
            # Can't calculate metrics, insufficient bars
            return False, "Insufficient bars for candle metrics", state.to_dict()

        current_volume = candle_metrics['volume']
        candle_size_pct = candle_metrics['size_pct']

        # Calculate average volume over last 20 1-minute candles (not 20 bars!)
        # Live: 20 candles = 240 bars (20 minutes)
        # Backtest: 20 candles = 20 bars (20 minutes)
        avg_volume = strategy.get_average_candle_volume(bars, current_idx, lookback_candles=20)

        if tracker.check_sustained_hold(
            symbol=symbol,
            current_price=current_price,
            current_bar=tracking_idx,  # CRITICAL FIX (Oct 21, 2025): Use absolute index for state tracking
            required_bars=required_bars,
            max_pullback_pct=strategy.sustained_break_max_pullback_pct,
            hourly_sma_levels=hourly_sma_levels,
            target_price=target_price,
            current_volume=current_volume,
            avg_volume=avg_volume,
            candle_size_pct=candle_size_pct,
            momentum_volume_threshold=strategy.momentum_volume_threshold,
            momentum_candle_threshold=strategy.momentum_candle_min_pct
        ):
            # Sustained break confirmed WITH momentum - check filters (room already checked in method)

            # STOCHASTIC FILTER (Oct 15, 2025): Check momentum confirmation
            fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
            if fails_stochastic:
                tracker.reset_state(symbol)
                return False, stochastic_reason, {'phase': 'stochastic_filter'}

            # CVD FILTER (Oct 19, 2025): Check volume delta confirmation
            # Updated Oct 21, 2025: Pass timestamp and backtester for tick-based CVD
            fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side,
                                                        bar_timestamp=timestamp, backtester=backtester)
            if fails_cvd:
                tracker.reset_state(symbol)
                return False, cvd_reason, {'phase': 'cvd_filter'}

            return True, f"SUSTAINED_BREAK ({state.bars_held_above_pivot} bars)", state.to_dict()

        # Still tracking
        bars_held = state.bars_held_above_pivot
        return False, f"Tracking weak breakout (held {bars_held}/{required_bars} bars)", state.to_dict()

    # STATE 5: READY_TO_ENTER
    elif state.state.value == 'READY_TO_ENTER':
        # Entry conditions met
        ready, reason, state_dict = tracker.is_ready_to_enter(symbol)
        if ready:
            # Reset state after entry
            tracker.reset_state(symbol)
            return True, reason, state_dict

    # STATE 6: FAILED
    elif state.state.value == 'FAILED':
        # Setup failed, reset
        tracker.reset_state(symbol)
        return False, "Setup failed, resetting to monitoring", {}

    # Unknown state
    return False, f"Unknown state: {state.state.value}", state.to_dict()
