"""
State Machine-Based Entry Logic for PS60 Strategy

This module contains the new state machine approach for entry confirmation,
replacing the old lookback loop logic.

Created: October 9, 2025
"""

from datetime import datetime


def check_entry_state_machine(strategy, symbol, bars, current_idx, pivot_price, side='LONG',
                               target_price=None, cached_hourly_bars=None):
    """
    State machine-based entry confirmation

    Instead of searching backwards through bars, we maintain state for each symbol
    and track progression through the decision tree.

    Returns:
        tuple: (should_enter, reason, entry_state)
    """
    tracker = strategy.state_tracker
    state = tracker.get_state(symbol)
    current_price = bars[current_idx].close
    timestamp = bars[current_idx].date if hasattr(bars[current_idx], 'date') else datetime.now()

    # Check if breakout is too old (freshness check)
    if not tracker.check_freshness(symbol, current_idx, strategy.max_breakout_age_bars):
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
                bar_idx=current_idx,
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
        bars_into_candle = current_idx % bars_per_candle

        if bars_into_candle < (bars_per_candle - 1):
            # Not at candle close yet
            return False, "Waiting for 1-min candle close", {
                'phase': 'waiting_candle_close',
                'bars_remaining': (bars_per_candle - 1) - bars_into_candle
            }

        # We're at candle close - analyze it
        candle_start = (current_idx // bars_per_candle) * bars_per_candle
        candle_end = candle_start + bars_per_candle
        candle_bars = bars[candle_start:candle_end]

        # Calculate candle characteristics
        candle_close = candle_bars[-1].close
        candle_open = candle_bars[0].open
        candle_size_pct = abs(candle_close - candle_open) / candle_open
        candle_volume = sum(b.volume for b in candle_bars)

        # Calculate volume ratio
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
            bar_idx=current_idx,
            price=candle_close,
            timestamp=timestamp,
            volume_ratio=volume_ratio,
            candle_size_pct=candle_size_pct
        )

        # Classify breakout strength
        is_strong_volume = volume_ratio >= strategy.momentum_volume_threshold
        is_large_candle = candle_size_pct >= strategy.momentum_candle_min_pct

        # Pass bars and current_idx for Phase 2 filters
        breakout_type = tracker.classify_breakout(symbol, is_strong_volume, is_large_candle,
                                                  bars=bars, current_idx=current_idx)

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

            return True, f"MOMENTUM_BREAKOUT ({volume_ratio:.1f}x vol, {candle_size_pct*100:.1f}% candle)", state.to_dict()

        # Weak breakout - continue to tracking state
        return False, f"Weak breakout, tracking for pullback/sustained ({volume_ratio:.1f}x vol)", state.to_dict()

    # STATE 3/4: WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST
    elif state.state.value in ['WEAK_BREAKOUT_TRACKING', 'PULLBACK_RETEST']:
        # Update price action tracking
        tracker.update_price_action(symbol, current_price, current_idx, timestamp)

        # PHASE 7 (Oct 13, 2025): Re-check for momentum on subsequent 1-minute candles
        # If a WEAK breakout later shows momentum-level volume, upgrade and enter
        # CRITICAL: Check this in BOTH WEAK_BREAKOUT_TRACKING AND PULLBACK_RETEST states!
        bars_per_candle = 12  # 12 five-second bars = 1 minute
        bars_into_candle = current_idx % bars_per_candle

        # Check if we're at a new 1-minute candle close (and not the original breakout candle)
        if bars_into_candle == (bars_per_candle - 1) and current_idx > state.candle_close_bar:
            # We're at a new 1-minute candle close - re-check for momentum
            candle_start = (current_idx // bars_per_candle) * bars_per_candle
            candle_end = candle_start + bars_per_candle
            candle_bars = bars[candle_start:candle_end]

            # Calculate this candle's volume
            candle_volume = sum(b.volume for b in candle_bars)

            # Calculate average candle volume
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

                # MOMENTUM CONFIRMED on subsequent candle - ENTER!
                print(f"[ENTERING!] {symbol} Bar {current_idx} - MOMENTUM_BREAKOUT (delayed)")
                return True, f"MOMENTUM_BREAKOUT (delayed, {volume_ratio:.1f}x vol on candle {current_idx // bars_per_candle})", state.to_dict()

        # Check for pullback (only in WEAK_BREAKOUT_TRACKING state)
        if state.state.value == 'WEAK_BREAKOUT_TRACKING':
            if tracker.check_pullback(symbol, current_price, strategy.pullback_distance_pct):
                return False, "Pullback detected, waiting for bounce", state.to_dict()

        # Check for pullback bounce (entry signal)
        if state.state.value == 'PULLBACK_RETEST':
            # PHASE 4 (Oct 12, 2025): Calculate MOMENTUM-LEVEL parameters for bounce
            # CRITICAL FIX: Require same filters as MOMENTUM entry
            previous_price = bars[current_idx - 1].close if current_idx > 0 else None
            current_bar = bars[current_idx]
            current_volume = current_bar.volume

            # Calculate average volume (last 20 bars)
            if current_idx >= 20:
                avg_volume = sum(bars[i].volume for i in range(current_idx-19, current_idx+1)) / 20
            else:
                avg_volume = current_volume  # Fallback if not enough bars

            # Calculate current candle size (for momentum candle check)
            current_candle_size_pct = abs(current_bar.close - current_bar.open) / current_bar.open

            # Check bounce with Phase 4 MOMENTUM-LEVEL filters
            # PHASE 5: Now returns adjusted entry pivot and stop
            bounce_confirmed, adjusted_entry, adjusted_stop = tracker.check_pullback_bounce(
                    symbol,
                    current_price,
                    bounce_threshold_pct=0.0015,  # Increased from 0.001 to 0.0015
                    previous_price=previous_price,
                    current_volume=current_volume,
                    avg_volume=avg_volume,
                    candle_size_pct=current_candle_size_pct,  # NEW: Match MOMENTUM
                    momentum_volume_threshold=strategy.momentum_volume_threshold,  # NEW: Use same threshold (2.0x)
                    momentum_candle_threshold=strategy.momentum_candle_min_pct)  # NEW: Use same threshold (0.3%)

            if bounce_confirmed:
                # Pullback bounce confirmed with MOMENTUM-LEVEL filters - check remaining filters
                if target_price:
                    insufficient_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                    if insufficient_room:
                        tracker.reset_state(symbol)
                        return False, room_reason, {'phase': 'room_to_run_filter'}

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
