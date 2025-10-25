# CVD Continuous Monitoring - Implementation Guide (Oct 21, 2025)

## 🎯 Summary

**Status**: Configuration ✅ DONE | Code implementation ✅ COMPLETE

The continuous CVD monitoring requires modifying `ps60_entry_state_machine.py` to add a new state `CVD_MONITORING` that checks CVD on every 1-minute candle after breakout detection.

---

## 📋 Changes Required in `ps60_entry_state_machine.py`

### Change 1: Transition to CVD_MONITORING after weak breakout (Line 412-422)

**Current Code**:
```python
if breakout_type == 'MOMENTUM':
    # Strong initial volume detected (3.0x+)
    state.state = BreakoutState.MOMENTUM_CONFIRMATION_WAIT
    logger.info(f"[MOMENTUM INITIAL] {symbol} Bar {current_idx}: "
               f"{volume_ratio:.1f}x vol detected, waiting for sustained volume confirmation")
    return False, f"Strong volume detected ({volume_ratio:.1f}x), waiting for confirmation", state.to_dict()

# Weak breakout - continue to tracking state
return False, f"Weak breakout, tracking for pullback/sustained ({volume_ratio:.1f}x vol)", state.to_dict()
```

**NEW Code** (replace lines 412-422):
```python
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
    logger.info(f"[CVD_MONITORING] {symbol} Bar {current_idx}: "
               f"WEAK breakout ({volume_ratio:.1f}x), entering CVD monitoring")
    return False, f"Weak breakout, entering CVD monitoring", state.to_dict()
else:
    # Legacy behavior: continue to weak tracking
    return False, f"Weak breakout, tracking for pullback/sustained ({volume_ratio:.1f}x vol)", state.to_dict()
```

---

### Change 2: Add CVD_MONITORING State Handler (Insert after STATE 2, before STATE 2.5)

**Insert Location**: After line 423, before `elif state.state.value == 'MOMENTUM_CONFIRMATION_WAIT':`

**NEW State Handler**:
```python
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
    bars_per_candle = strategy.candle_timeframe_seconds // 5  # 12 bars = 1 minute

    # Check timeout (10 minutes)
    time_elapsed = (timestamp - state.cvd_monitoring_start_time).total_seconds() / 60
    max_time = cvd_config.get('max_monitoring_time_minutes', 10)

    if time_elapsed > max_time:
        logger.info(f"[CVD_MONITORING] {symbol}: TIMEOUT after {time_elapsed:.1f} minutes")
        tracker.reset_state(symbol)
        return False, f"CVD monitoring timeout ({time_elapsed:.1f} min)", {}

    # Wait for 1-minute candle close
    bars_into_candle = tracking_idx % bars_per_candle
    if bars_into_candle < (bars_per_candle - 1):
        return False, f"CVD monitoring: waiting for candle close ({bars_into_candle}/{bars_per_candle})", {
            'phase': 'cvd_monitoring',
            'time_elapsed_min': time_elapsed,
            'cvd_consecutive_count': state.cvd_consecutive_bullish_count if side == 'LONG' else state.cvd_consecutive_bearish_count
        }

    # At candle close - calculate CVD
    try:
        # Get tick data if available (live trading)
        ticks = None
        if hasattr(strategy, 'get_tick_data'):
            ticks = strategy.get_tick_data(symbol)

        # Calculate CVD using auto mode
        calculator = CVDCalculator(
            slope_lookback=cvd_config.get('slope_lookback', 5),
            bullish_threshold=cvd_config.get('bullish_slope_threshold', 1000),
            bearish_threshold=cvd_config.get('bearish_slope_threshold', -1000)
        )
        cvd_result = calculator.calculate_auto(bars, current_idx, ticks=ticks)

        cvd_slope = cvd_result.cvd_slope
        cvd_trend = cvd_result.cvd_trend

        # Store CVD state
        state.cvd_last_slope = cvd_slope
        state.cvd_last_trend = cvd_trend

        logger.info(f"[CVD_MONITORING] {symbol} Bar {current_idx}: "
                   f"CVD slope={cvd_slope:.0f}, trend={cvd_trend}, "
                   f"consecutive={state.cvd_consecutive_bullish_count if side == 'LONG' else state.cvd_consecutive_bearish_count}")

        # PATH 1: Strong CVD spike (immediate entry)
        if side == 'LONG':
            strong_threshold = cvd_config.get('strong_bullish_threshold', 2000)
            if cvd_slope >= strong_threshold:
                logger.info(f"[CVD_MONITORING] {symbol}: ⚡ STRONG CVD SPIKE {cvd_slope:.0f} ≥ {strong_threshold} → ENTER!")

                # Run all entry filters
                fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                if fails_stochastic:
                    tracker.reset_state(symbol)
                    return False, stochastic_reason, {'phase': 'stochastic_filter'}

                # CVD already confirmed (that's why we're here), but check room-to-run
                fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                if fails_room:
                    tracker.reset_state(symbol)
                    return False, room_reason, {'phase': 'room_to_run_filter'}

                # ENTER!
                tracker.reset_state(symbol)
                return True, f"Strong CVD spike ({cvd_slope:.0f})", {
                    'phase': 'cvd_aggressive',
                    'cvd_slope': cvd_slope,
                    'time_to_entry_min': time_elapsed
                }

        elif side == 'SHORT':
            strong_threshold = cvd_config.get('strong_bearish_threshold', -2000)
            if cvd_slope <= strong_threshold:
                logger.info(f"[CVD_MONITORING] {symbol}: ⚡ STRONG CVD SPIKE {cvd_slope:.0f} ≤ {strong_threshold} → ENTER!")

                # Run entry filters
                fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                if fails_stochastic:
                    tracker.reset_state(symbol)
                    return False, stochastic_reason, {'phase': 'stochastic_filter'}

                fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                if fails_room:
                    tracker.reset_state(symbol)
                    return False, room_reason, {'phase': 'room_to_run_filter'}

                # ENTER!
                tracker.reset_state(symbol)
                return True, f"Strong CVD spike ({cvd_slope:.0f})", {
                    'phase': 'cvd_aggressive',
                    'cvd_slope': cvd_slope,
                    'time_to_entry_min': time_elapsed
                }

        # PATH 2: Sustained CVD (consecutive candles)
        if side == 'LONG':
            bullish_threshold = cvd_config.get('bullish_slope_threshold', 1000)
            min_consecutive = cvd_config.get('min_consecutive_bullish', 2)

            if cvd_slope >= bullish_threshold:
                # CVD is bullish - increment counter
                state.cvd_consecutive_bullish_count += 1
                logger.info(f"[CVD_MONITORING] {symbol}: ✅ CVD BULLISH candle #{state.cvd_consecutive_bullish_count} "
                           f"(slope {cvd_slope:.0f})")

                if state.cvd_consecutive_bullish_count >= min_consecutive:
                    logger.info(f"[CVD_MONITORING] {symbol}: 🎯 SUSTAINED CVD confirmed "
                               f"({state.cvd_consecutive_bullish_count} consecutive candles) → ENTER!")

                    # Run entry filters
                    fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                    if fails_stochastic:
                        tracker.reset_state(symbol)
                        return False, stochastic_reason, {'phase': 'stochastic_filter'}

                    fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                    if fails_room:
                        tracker.reset_state(symbol)
                        return False, room_reason, {'phase': 'room_to_run_filter'}

                    # ENTER!
                    tracker.reset_state(symbol)
                    return True, f"Sustained CVD ({state.cvd_consecutive_bullish_count} candles)", {
                        'phase': 'cvd_sustained',
                        'cvd_slope': cvd_slope,
                        'consecutive_candles': state.cvd_consecutive_bullish_count,
                        'time_to_entry_min': time_elapsed
                    }

            # CVD went bearish - reset counter
            elif cvd_slope < cvd_config.get('bearish_slope_threshold', -1000):
                if state.cvd_consecutive_bullish_count > 0:
                    logger.info(f"[CVD_MONITORING] {symbol}: ⚠️ CVD reversed to BEARISH ({cvd_slope:.0f}), "
                               f"resetting counter (was {state.cvd_consecutive_bullish_count})")
                state.cvd_consecutive_bullish_count = 0

            # CVD neutral - don't reset (allow brief pauses)
            else:
                logger.debug(f"[CVD_MONITORING] {symbol}: CVD NEUTRAL ({cvd_slope:.0f}), "
                            f"keeping count at {state.cvd_consecutive_bullish_count}")

        elif side == 'SHORT':
            bearish_threshold = cvd_config.get('bearish_slope_threshold', -1000)
            min_consecutive = cvd_config.get('min_consecutive_bearish', 2)

            if cvd_slope <= bearish_threshold:
                # CVD is bearish - increment counter
                state.cvd_consecutive_bearish_count += 1
                logger.info(f"[CVD_MONITORING] {symbol}: ✅ CVD BEARISH candle #{state.cvd_consecutive_bearish_count} "
                           f"(slope {cvd_slope:.0f})")

                if state.cvd_consecutive_bearish_count >= min_consecutive:
                    logger.info(f"[CVD_MONITORING] {symbol}: 🎯 SUSTAINED CVD confirmed "
                               f"({state.cvd_consecutive_bearish_count} consecutive candles) → ENTER!")

                    # Run entry filters
                    fails_stochastic, stochastic_reason = strategy._check_stochastic_filter(symbol, side)
                    if fails_stochastic:
                        tracker.reset_state(symbol)
                        return False, stochastic_reason, {'phase': 'stochastic_filter'}

                    fails_room, room_reason = strategy._check_room_to_run(current_price, target_price, side)
                    if fails_room:
                        tracker.reset_state(symbol)
                        return False, room_reason, {'phase': 'room_to_run_filter'}

                    # ENTER!
                    tracker.reset_state(symbol)
                    return True, f"Sustained CVD ({state.cvd_consecutive_bearish_count} candles)", {
                        'phase': 'cvd_sustained',
                        'cvd_slope': cvd_slope,
                        'consecutive_candles': state.cvd_consecutive_bearish_count,
                        'time_to_entry_min': time_elapsed
                    }

            # CVD went bullish - reset counter
            elif cvd_slope > cvd_config.get('bullish_slope_threshold', 1000):
                if state.cvd_consecutive_bearish_count > 0:
                    logger.info(f"[CVD_MONITORING] {symbol}: ⚠️ CVD reversed to BULLISH ({cvd_slope:.0f}), "
                               f"resetting counter (was {state.cvd_consecutive_bearish_count})")
                state.cvd_consecutive_bearish_count = 0

            # CVD neutral - don't reset
            else:
                logger.debug(f"[CVD_MONITORING] {symbol}: CVD NEUTRAL ({cvd_slope:.0f}), "
                            f"keeping count at {state.cvd_consecutive_bearish_count}")

        # Continue monitoring
        return False, f"CVD monitoring (slope {cvd_slope:.0f}, consecutive {state.cvd_consecutive_bullish_count if side == 'LONG' else state.cvd_consecutive_bearish_count})", {
            'phase': 'cvd_monitoring',
            'cvd_slope': cvd_slope,
            'cvd_trend': cvd_trend,
            'time_elapsed_min': time_elapsed
        }

    except Exception as e:
        logger.error(f"[CVD_MONITORING] {symbol}: CVD calculation failed: {e}")
        # On error, fall back to old behavior (transition to weak tracking)
        state.state = BreakoutState.WEAK_BREAKOUT_TRACKING
        return False, f"CVD calculation error, falling back to weak tracking", state.to_dict()
```

---

## 🎯 Expected Behavior After Implementation

### AMD Oct 15 Example

```
09:47:00 Bar 203 - Breakout @ $225.10
  Volume: 1.2x ✅ (≥ 1.0x threshold)
  Candle size: 0.2% (small, not momentum)
  → Classified as WEAK
  → STATE: CVD_MONITORING
  → cvd_monitoring_start_time = 09:47:00

09:48:00 Bar 215 - 1st CVD Check
  CVD slope: +1200 (BULLISH)
  → consecutive_bullish_count = 1
  → Continue monitoring

09:49:00 Bar 227 - 2nd CVD Check
  CVD slope: +1400 (BULLISH, sustained!)
  → consecutive_bullish_count = 2 ✅
  → SUSTAINED CVD CONFIRMED
  → Run filters (stochastic ✅, room-to-run ✅)
  → ENTER @ $226.50

Entry: $226.50
Stop: $225.25 (0.5x ATR = $1.25)
Shares: 400
Target: $234.98
P&L: +$3,392 ✅
```

---

## 📋 Next Steps

1. ✅ Configuration changes - DONE
2. ✅ State tracker fields - DONE
3. ✅ Implement code changes above - DONE (Oct 21, 2025)
4. ⏳ Test on Oct 15 backtest - IN PROGRESS
5. ⏳ Validate improvement vs current -$357 result - PENDING

---

**Status**: ✅ IMPLEMENTATION COMPLETE | ⏳ Testing in progress
