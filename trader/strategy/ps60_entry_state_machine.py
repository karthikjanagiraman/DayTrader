"""
State Machine-Based Entry Logic for PS60 Strategy

This module contains the new state machine approach for entry confirmation,
replacing the old lookback loop logic.

Created: October 9, 2025
Updated: October 19, 2025 - Added CVD filter integration
"""

from datetime import datetime
import logging

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


def _check_cvd_filter(strategy, symbol, bars, current_idx, side):
    """
    Check CVD (Cumulative Volume Delta) confirmation filter

    PHASE 8 (Oct 19, 2025): CVD integration for breakout validation

    Args:
        strategy: Strategy instance (contains config)
        symbol: Stock symbol
        bars: Historical bars
        current_idx: Current bar index
        side: 'LONG' or 'SHORT'

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
        # Initialize CVD calculator
        calculator = CVDCalculator(
            slope_lookback=cvd_config.get('slope_lookback', 5),
            bullish_threshold=cvd_config.get('bullish_slope_threshold', 1000),
            bearish_threshold=cvd_config.get('bearish_slope_threshold', -1000)
        )

        # Get tick data if available (live trading)
        ticks = None
        if hasattr(strategy, 'get_tick_data'):
            ticks = strategy.get_tick_data(symbol)

        # Calculate CVD using auto mode (prefers ticks, falls back to bars)
        cvd_result = calculator.calculate_auto(bars, current_idx, ticks=ticks)

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
        candle_start_array = (current_idx // bars_per_candle) * bars_per_candle
        candle_end_array = candle_start_array + bars_per_candle
        return bars[candle_start_array:candle_end_array]


def check_entry_state_machine(strategy, symbol, bars, current_idx, pivot_price, side='LONG',
                               target_price=None, cached_hourly_bars=None, absolute_idx=None, bar_buffer=None):
    """
    State machine-based entry confirmation

    CRITICAL FIX PART 2 (Oct 20, 2025):
    - current_idx = ARRAY index (for bars[] access)
    - absolute_idx = ABSOLUTE bar count (for state tracking)

    CRITICAL FIX PART 3 (Oct 20, 2025):
    - bar_buffer = BarBuffer instance for mapping absolute indices to array indices
    - Required for correct candle boundary calculations after buffer fills

    Instead of searching backwards through bars, we maintain state for each symbol
    and track progression through the decision tree.

    Args:
        current_idx: Array index for accessing bars[]
        absolute_idx: Absolute bar count for state tracking
        bar_buffer: BarBuffer instance (for candle mapping)

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
        bars_per_candle = strategy.candle_timeframe_seconds // 5  # 60 sec / 5 sec = 12 bars
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

        # Pass bars and current_idx for Phase 2 filters
        breakout_type = tracker.classify_breakout(symbol, is_strong_volume, is_large_candle,
                                                  bars=bars, current_idx=current_idx)

        logger.info(f"[BREAKOUT TYPE] {symbol} Bar {current_idx}: Classified as {breakout_type}")

        if breakout_type == 'MOMENTUM':
            # Strong breakout - ready to enter immediately
            # But first check filters
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
            fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side)
            if fails_cvd:
                tracker.reset_state(symbol)
                return False, cvd_reason, {'phase': 'cvd_filter'}

            return True, f"MOMENTUM_BREAKOUT ({volume_ratio:.1f}x vol, {candle_size_pct*100:.1f}% candle)", state.to_dict()

        # Weak breakout - continue to tracking state
        return False, f"Weak breakout, tracking for pullback/sustained ({volume_ratio:.1f}x vol)", state.to_dict()

    # STATE 3/4: WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST
    elif state.state.value in ['WEAK_BREAKOUT_TRACKING', 'PULLBACK_RETEST']:
        # Update price action tracking
        tracker.update_price_action(symbol, current_price, tracking_idx, timestamp)  # Use absolute index for state

        # PHASE 7 (Oct 13, 2025): Re-check for momentum on subsequent 1-minute candles
        # If a WEAK breakout later shows momentum-level volume, upgrade and enter
        # CRITICAL: Check this in BOTH WEAK_BREAKOUT_TRACKING AND PULLBACK_RETEST states!
        bars_per_candle = 12  # 12 five-second bars = 1 minute
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
                    # Momentum detected on subsequent candle - upgrade to MOMENTUM entry!
                    print(f"[MOMENTUM FOUND!] {symbol} Bar {current_idx} - Checking filters...")

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
                    fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side)
                    if fails_cvd:
                        print(f"[BLOCKED] {symbol} Bar {current_idx} - {cvd_reason}")
                        tracker.reset_state(symbol)
                        return False, cvd_reason, {'phase': 'cvd_filter'}

                    # MOMENTUM CONFIRMED on subsequent candle - ENTER!
                    print(f"[ENTERING!] {symbol} Bar {current_idx} - MOMENTUM_BREAKOUT (delayed)")
                    return True, f"MOMENTUM_BREAKOUT (delayed, {volume_ratio:.1f}x vol on candle {current_idx // bars_per_candle})", state.to_dict()

        # Check for pullback (only in WEAK_BREAKOUT_TRACKING state)
        if state.state.value == 'WEAK_BREAKOUT_TRACKING':
            if tracker.check_pullback(symbol, current_price, strategy.pullback_distance_pct):
                return False, "Pullback detected, waiting for bounce", state.to_dict()

        # Check for pullback bounce (entry signal)
        if state.state.value == 'PULLBACK_RETEST':
            # PHASE 8 (Oct 16, 2025): FIX CRITICAL BUG - Aggregate to 1-minute candles
            # ROOT CAUSE: Was using 5-second bar data, causing meaningless volume/candle ratios
            # FIX: Use same 1-minute aggregation logic as MOMENTUM path (lines 150-180)

            bars_per_candle = 12  # 12 five-second bars = 1 minute
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
                # Pullback bounce confirmed with MOMENTUM-LEVEL filters - check remaining filters

                # ENHANCED LOGGING (Oct 19, 2025): Log pullback bounce metrics
                logger.info(f"[PULLBACK BOUNCE] {symbol} Bar {current_idx}: "
                           f"Volume={candle_volume:,.0f}, Avg={avg_candle_volume:,.0f}, "
                           f"Ratio={candle_volume/avg_candle_volume:.2f}x (need {strategy.pullback_volume_threshold:.1f}x), "
                           f"Candle={current_candle_size_pct*100:.2f}% (need {strategy.pullback_candle_min_pct*100:.1f}%)")

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
                fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side)
                if fails_cvd:
                    tracker.reset_state(symbol)
                    return False, cvd_reason, {'phase': 'cvd_filter'}

                # PHASE 5: Include adjusted pivot and stop in return
                entry_state = state.to_dict()
                entry_state['adjusted_entry_pivot'] = adjusted_entry
                entry_state['adjusted_stop'] = adjusted_stop
                return True, "PULLBACK_RETEST entry (momentum confirmed)", entry_state

            return False, "Waiting for momentum on pullback bounce", state.to_dict()

        # Check for sustained break
        # PHASE 6 (Oct 12, 2025): Pass hourly SMA levels and momentum parameters
        required_bars = (strategy.sustained_break_minutes * 60) // 5  # e.g., 2 min = 24 bars

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
        current_bar = bars[current_idx]
        current_volume = current_bar.volume if hasattr(current_bar, 'volume') else None

        # Calculate average volume (last 20 bars of 5-second data)
        avg_volume = None
        if current_idx >= 20:
            avg_volume = sum(bars[i].volume for i in range(current_idx-19, current_idx+1)) / 20
        elif current_idx > 0:
            avg_volume = sum(bars[i].volume for i in range(current_idx+1)) / (current_idx + 1)

        # Calculate current candle size
        candle_size_pct = abs(current_bar.close - current_bar.open) / current_bar.open if current_bar.open != 0 else 0

        if tracker.check_sustained_hold(
            symbol=symbol,
            current_price=current_price,
            current_bar=current_idx,
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
            fails_cvd, cvd_reason = _check_cvd_filter(strategy, symbol, bars, current_idx, side)
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
