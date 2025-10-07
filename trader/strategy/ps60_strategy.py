"""
PS60 Strategy - Core Trading Logic

This module contains the core PS60 trading strategy logic shared by:
- Live trader (trader.py)
- Backtester (backtest/backtester.py)

All trading decisions, entry/exit rules, and risk management are centralized here.
"""

from datetime import datetime, time as time_obj
import pytz


class PS60Strategy:
    """
    PS60 Trading Strategy Implementation

    Based on Dan Shapiro's PS60 Process:
    - Entry: Pivot breaks (scanner-identified resistance/support)
    - Exits: Partial profits, trailing stops, EOD close
    - Risk: 5-7 min rule for reload sellers, stops at pivot
    """

    def __init__(self, config):
        """
        Initialize PS60 strategy with configuration

        Args:
            config: Trading configuration dict from trader_config.yaml
        """
        self.config = config
        self.trading_config = config['trading']
        self.filters = config['filters']

        # Entry timing
        self.min_entry_time = self._parse_time(
            self.trading_config['entry']['min_entry_time']
        )
        self.max_entry_time = self._parse_time(
            self.trading_config['entry']['max_entry_time']
        )

        # Exit rules (now 1R-based, not fixed dollar amount)
        self.partial_1_pct = self.trading_config['exits']['partial_1_pct']
        self.partial_2_pct = self.trading_config['exits'].get('partial_2_pct', 0.25)
        self.runner_pct = self.trading_config['exits'].get('runner_pct', 0.25)

        self.eod_close_time = self._parse_time(
            self.trading_config['exits']['eod_close_time']
        )

        # Risk management
        self.breakeven_after_partial = self.trading_config['risk']['breakeven_after_partial']
        self.stop_at_pivot = self.trading_config['risk'].get('stop_at_pivot', False)
        self.use_atr_stops = self.trading_config['risk'].get('use_atr_stops', True)
        self.atr_stop_multiplier = self.trading_config['risk'].get('atr_stop_multiplier', 2.0)
        self.atr_stop_period = self.trading_config['risk'].get('atr_stop_period', 20)
        self.account_size = self.trading_config.get('account_size', 100000)
        self.risk_per_trade = self.trading_config.get('risk_per_trade', 0.01)

        # Position sizing
        position_sizing = self.trading_config.get('position_sizing', {})
        self.max_position_pct = position_sizing.get('max_position_pct', 10.0)

        # Attempts
        self.max_attempts_per_pivot = self.trading_config['attempts']['max_attempts_per_pivot']

        # Filters
        self.min_score = self.filters['min_score']
        self.min_risk_reward = self.filters['min_risk_reward']
        self.max_dist_to_pivot = self.filters['max_dist_to_pivot']
        self.avoid_index_shorts = self.filters.get('avoid_index_shorts', True)
        self.avoid_symbols = self.filters.get('avoid_symbols', [])

        # Gap filter
        self.enable_gap_filter = self.filters.get('enable_gap_filter', True)
        self.max_gap_through_pivot = self.filters.get('max_gap_through_pivot', 1.0)
        self.min_room_to_target = self.filters.get('min_room_to_target', 3.0)

        # Room-to-run filter (Oct 5, 2025)
        # Smarter chasing filter for pullback/retest: checks if enough room to target
        self.enable_room_to_run_filter = self.filters.get('enable_room_to_run_filter', True)
        self.min_room_to_target_pct = self.filters.get('min_room_to_target_pct', 1.5)

        # Confirmation logic (per requirements spec)
        confirmation_config = self.trading_config.get('confirmation', {})
        self.confirmation_enabled = confirmation_config.get('enabled', True)
        self.volume_surge_required = confirmation_config.get('volume_surge_required', True)
        self.volume_surge_multiplier = confirmation_config.get('volume_surge_multiplier', 1.5)
        self.momentum_candle_required = confirmation_config.get('momentum_candle_required', True)
        self.momentum_candle_size = confirmation_config.get('momentum_candle_size', 1.5)
        self.sustained_break_minutes = confirmation_config.get('sustained_break_minutes', 2)

        # HYBRID STRATEGY: Momentum + Pullback/Retest (Oct 4, 2025)
        # Two entry types: strong momentum (immediate) vs weak break (wait for pullback)
        self.require_candle_close = confirmation_config.get('require_candle_close', True)
        self.candle_timeframe_seconds = confirmation_config.get('candle_timeframe_seconds', 60)

        # Momentum breakout thresholds (immediate entry)
        self.momentum_volume_threshold = confirmation_config.get('momentum_volume_threshold', 2.0)
        self.momentum_candle_min_pct = confirmation_config.get('momentum_candle_min_pct', 0.015)
        self.momentum_candle_min_atr = confirmation_config.get('momentum_candle_min_atr', 2.0)

        # Pullback/retest thresholds (patient entry)
        self.require_pullback_retest = confirmation_config.get('require_pullback_retest', True)
        self.pullback_distance_pct = confirmation_config.get('pullback_distance_pct', 0.003)
        self.max_pullback_bars = confirmation_config.get('max_pullback_bars', 24)
        self.pullback_volume_threshold = confirmation_config.get('pullback_volume_threshold', 1.2)

        # Sustained break logic (Oct 5, 2025) - Alternative to momentum candle
        # Catches "slow grind" breakouts that hold above resistance with volume
        self.sustained_break_enabled = confirmation_config.get('sustained_break_enabled', True)
        self.sustained_break_minutes = confirmation_config.get('sustained_break_minutes', 2)
        self.sustained_break_max_pullback_pct = confirmation_config.get('sustained_break_max_pullback_pct', 0.001)

        # FIX #2 (Oct 4, 2025): Entry position filter to prevent chasing
        self.enable_entry_position_filter = confirmation_config.get('enable_entry_position_filter', False)
        self.max_entry_position_pct = confirmation_config.get('max_entry_position_pct', 70)
        self.entry_position_lookback_bars = confirmation_config.get('entry_position_lookback_bars', 60)

        # FIX #4 (Oct 4, 2025): Choppy filter to avoid consolidation entries
        self.enable_choppy_filter = confirmation_config.get('enable_choppy_filter', False)
        self.choppy_atr_multiplier = confirmation_config.get('choppy_atr_multiplier', 0.5)
        self.choppy_lookback_bars = confirmation_config.get('choppy_lookback_bars', 60)

        # ATR period for stop calculation (needed by _calculate_atr)
        self.atr_period = self.atr_stop_period

        # Setup types
        setup_types = self.trading_config.get('setup_types', {})
        self.enable_breakout = setup_types.get('breakout', True)
        self.enable_bounce = setup_types.get('bounce', True)
        self.enable_rejection = setup_types.get('rejection', False)

        # Slippage and commissions
        slippage_config = self.trading_config.get('slippage', {})
        self.slippage_enabled = slippage_config.get('enabled', True)
        self.slippage_pct = slippage_config.get('percentage', 0.001)

        commission_config = self.trading_config.get('commissions', {})
        self.commission_enabled = commission_config.get('enabled', True)
        self.commission_per_share = commission_config.get('per_share', 0.005)

        # Trailing stop (per requirements)
        trailing_stop_config = self.trading_config.get('trailing_stop', {})
        self.trailing_stop_enabled = trailing_stop_config.get('enabled', True)
        self.trailing_stop_type = trailing_stop_config.get('type', 'percentage')
        self.trailing_stop_pct = trailing_stop_config.get('percentage', 0.005)  # 0.5%
        self.trailing_stop_atr_mult = trailing_stop_config.get('atr_multiplier', 2.0)
        self.trailing_stop_min_profit = trailing_stop_config.get('min_profit_to_activate', 0.01)  # 1%

    def _parse_time(self, time_str):
        """Parse time string to time object"""
        return datetime.strptime(time_str, '%H:%M').time()

    def check_breakout_confirmation(self, bars, breakout_idx, pivot_price, side='LONG'):
        """
        Check if breakout is confirmed per requirements:
        1. Volume surge (>1.5x average)
        2. Momentum candle (>1.5x average range)
        3. Sustained break (hold above/below for N minutes)

        Args:
            bars: List of 1-min bars (OHLCV data)
            breakout_idx: Index where breakout occurred
            pivot_price: The pivot level being broken
            side: 'LONG' or 'SHORT'

        Returns:
            (bool, reason) - Is confirmed, and reason if not
        """
        if not self.confirmation_enabled:
            return True, "Confirmation disabled"

        if breakout_idx >= len(bars):
            return False, "Invalid breakout index"

        breakout_bar = bars[breakout_idx]

        # 1. Volume confirmation (if enabled)
        if self.volume_surge_required:
            # Calculate average volume from recent bars (last 20 bars before breakout)
            start_idx = max(0, breakout_idx - 20)
            recent_bars = bars[start_idx:breakout_idx]

            if len(recent_bars) < 5:  # Need minimum history
                return False, "Insufficient volume history"

            avg_volume = sum(bar.volume for bar in recent_bars) / len(recent_bars)

            if breakout_bar.volume < avg_volume * self.volume_surge_multiplier:
                return False, f"Volume too low ({breakout_bar.volume:.0f} vs {avg_volume * self.volume_surge_multiplier:.0f} required)"

        # 2. Momentum candle confirmation (if enabled)
        if self.momentum_candle_required:
            # Calculate average candle range
            start_idx = max(0, breakout_idx - 20)
            recent_bars = bars[start_idx:breakout_idx]

            if len(recent_bars) < 5:
                return False, "Insufficient price history"

            avg_range = sum(bar.high - bar.low for bar in recent_bars) / len(recent_bars)
            breakout_range = breakout_bar.high - breakout_bar.low

            if breakout_range < avg_range * self.momentum_candle_size:
                return False, f"Momentum candle too small ({breakout_range:.2f} vs {avg_range * self.momentum_candle_size:.2f} required)"

        # 3. Sustained break confirmation (if required)
        if self.sustained_break_minutes > 0:
            # Check if price stays above/below pivot for N minutes
            end_idx = min(len(bars), breakout_idx + self.sustained_break_minutes)
            bars_after_break = bars[breakout_idx:end_idx]

            if len(bars_after_break) < self.sustained_break_minutes:
                return False, f"Insufficient bars for sustained check (need {self.sustained_break_minutes} min)"

            for bar in bars_after_break:
                if side == 'LONG':
                    if bar.low < pivot_price:  # Dropped back below pivot
                        return False, f"Failed to sustain above {pivot_price:.2f}"
                else:  # SHORT
                    if bar.high > pivot_price:  # Bounced back above pivot
                        return False, f"Failed to sustain below {pivot_price:.2f}"

        return True, "Confirmed"

    def check_retest_confirmation(self, bars, current_idx, pivot_price, side='LONG'):
        """
        Confirmation Strategy (CORRECTED - Oct 4, 2025)

        Strategy: Monitor after breakout, enter when price confirms with % move
        Default: 0.5% (configurable via strong_breakout_threshold)

        How it works:
        1. Breakout occurs (price crosses resistance/support by ANY amount)
        2. Continue monitoring price action
        3. Enter when price reaches confirmation threshold above resistance
        4. Volume confirmation required at entry

        Example (LONG) with 0.5% threshold:
          Resistance: $444.77
          Breakout at: $445.04 (0.06% - too small to enter)
          Monitor and wait...
          Price hits: $446.99 (0.5% above $444.77) ✅ ENTER HERE
          Stop: $444.77 (at original resistance)

        This approach:
          ✅ Confirms strong follow-through (not just noise)
          ✅ Avoids tiny false breakouts
          ✅ Doesn't miss the move (monitors instead of filtering)
          ✅ Gets good entry with conviction
          ✅ Faster than 1% threshold

        Args:
            bars: List of price bars (OHLCV)
            current_idx: Current bar index
            pivot_price: Resistance (LONG) or Support (SHORT) level
            side: 'LONG' or 'SHORT'

        Returns:
            (should_enter, reason, stop_price)
        """
        if not self.retest_strategy_enabled:
            return False, "Retest strategy disabled", None

        if current_idx >= len(bars):
            return False, "Invalid bar index", None

        current_bar = bars[current_idx]
        current_price = current_bar.close

        # Calculate confirmation threshold (adaptive based on type)
        if self.confirmation_type == 'atr':
            # ATR-based: Calculate ATR from recent bars
            atr = self._calculate_atr(bars, current_idx)
            confirmation_threshold_dollars = atr * self.atr_multiplier
            confirmation_threshold_pct = (confirmation_threshold_dollars / pivot_price)
        else:
            # Fixed percentage
            confirmation_threshold_pct = self.strong_breakout_threshold
            confirmation_threshold_dollars = pivot_price * confirmation_threshold_pct

        # Calculate the confirmation price
        if side == 'LONG':
            confirmation_price = pivot_price + confirmation_threshold_dollars
            move_pct = ((current_price - pivot_price) / pivot_price) * 100
        else:  # SHORT
            confirmation_price = pivot_price - confirmation_threshold_dollars
            move_pct = ((pivot_price - current_price) / pivot_price) * 100

        # Check if we're above pivot (breakout occurred)
        if side == 'LONG':
            if current_price <= pivot_price:
                return False, f"Below resistance ${pivot_price:.2f}", None
        else:  # SHORT
            if current_price >= pivot_price:
                return False, f"Above support ${pivot_price:.2f}", None

        # Check if we've reached 1% confirmation level
        if side == 'LONG':
            confirmed = current_price >= confirmation_price
        else:  # SHORT
            confirmed = current_price <= confirmation_price

        if not confirmed:
            # Breakout occurred but haven't hit confirmation threshold yet - keep monitoring
            threshold_desc = f"{confirmation_threshold_pct*100:.1f}%" if self.confirmation_type == 'fixed' else f"${confirmation_threshold_dollars:.2f} (ATR)"
            return False, f"MONITORING (broke {move_pct:.2f}%, waiting for {threshold_desc} confirmation at ${confirmation_price:.2f})", None

        # We've hit 1% confirmation! Now check volume
        if self.volume_surge_required:
            # Check if ANY bar since breakout had volume surge
            # Find where breakout started (first bar above/below pivot)
            breakout_bar_idx = None
            for i in range(max(0, current_idx - 60), current_idx + 1):  # Look back max 5 min
                if i >= len(bars):
                    break
                bar = bars[i]
                if side == 'LONG':
                    if bar.close > pivot_price:
                        breakout_bar_idx = i
                        break
                else:  # SHORT
                    if bar.close < pivot_price:
                        breakout_bar_idx = i
                        break

            if breakout_bar_idx is None:
                breakout_bar_idx = max(0, current_idx - 5)  # Default to 5 bars back

            # Check volume surge in the breakout move
            has_volume = self._check_volume_surge_in_range(bars, breakout_bar_idx, current_idx + 1)

            if not has_volume:
                return False, f"1% CONFIRMATION but NO VOLUME (move {move_pct:.2f}%)", None

        # ✅ ENTRY CONFIRMED: Hit 1% threshold with volume
        # Calculate stop price (ATR-based or pivot-based)
        if self.use_atr_stops:
            # ATR-based stop: Entry - (ATR × multiplier)
            atr = self._calculate_atr(bars, current_idx)
            if side == 'LONG':
                stop_price = current_price - (atr * self.atr_stop_multiplier)
            else:  # SHORT
                stop_price = current_price + (atr * self.atr_stop_multiplier)
        else:
            # Pivot-based stop: Original pivot (resistance becomes support)
            stop_price = pivot_price

        return True, f"1%_CONFIRMATION (entry ${current_price:.2f}, {move_pct:.2f}% from pivot with volume)", stop_price

    def _has_fallen_below_pivot(self, bars, current_idx, pivot_price, side='LONG'):
        """
        Check if price fell back below/above pivot in recent bars

        Args:
            bars: List of price bars
            current_idx: Current bar index
            pivot_price: The pivot level
            side: 'LONG' or 'SHORT'

        Returns:
            bool - True if price fell back (whipsawed)
        """
        # Check last N bars (e.g., 5 bars = 25 seconds @ 5-sec bars)
        lookback = min(self.sustained_check_bars, current_idx)
        start_idx = max(0, current_idx - lookback)
        recent_bars = bars[start_idx:current_idx]

        for bar in recent_bars:
            if side == 'LONG':
                if bar.low < pivot_price:
                    return True  # Fell back below resistance
            else:  # SHORT
                if bar.high > pivot_price:
                    return True  # Bounced back above support

        return False

    def _had_initial_break_and_pullback(self, bars, current_idx, pivot_price, side='LONG'):
        """
        Check if there was a previous breakout that failed (pulled back)
        within the retest window

        Args:
            bars: List of price bars
            current_idx: Current bar index
            pivot_price: The pivot level
            side: 'LONG' or 'SHORT'

        Returns:
            bool - True if this looks like a retest setup
        """
        # Look back in retest window (e.g., 5 minutes = 60 bars @ 5-sec bars)
        window_bars = self.retest_window_minutes * 12  # 12 bars per minute @ 5-sec
        lookback_start = max(0, current_idx - window_bars)
        lookback_bars = bars[lookback_start:current_idx]

        broke_pivot = False
        pulled_back = False

        for bar in lookback_bars:
            if side == 'LONG':
                # Check if broke above resistance (close above, not just wick)
                if bar.close > pivot_price and not broke_pivot:
                    broke_pivot = True
                # Check if then fell back below (close below, not just wick)
                # This prevents false signals from intra-bar volatility
                elif broke_pivot and bar.close < pivot_price:
                    pulled_back = True
                    break
            else:  # SHORT
                # Check if broke below support (close below, not just wick)
                if bar.close < pivot_price and not broke_pivot:
                    broke_pivot = True
                # Check if then bounced back above (close above, not just wick)
                elif broke_pivot and bar.close > pivot_price:
                    pulled_back = True
                    break

        return broke_pivot and pulled_back

    def _calculate_stop_with_buffer(self, pivot_price, side='LONG'):
        """
        Calculate stop price with buffer below/above pivot

        Args:
            pivot_price: The pivot level (resistance or support)
            side: 'LONG' or 'SHORT'

        Returns:
            float - Stop price with buffer
        """
        if side == 'LONG':
            # Stop below resistance
            return pivot_price * (1 - self.stop_buffer_pct)
        else:  # SHORT
            # Stop above support
            return pivot_price * (1 + self.stop_buffer_pct)

    def _check_volume_surge_single_bar(self, bars, bar_idx):
        """
        Check if a single bar has volume surge (≥1.5x average)

        Used for retest entries - checking volume at the retest bar

        Args:
            bars: List of price bars
            bar_idx: Index of bar to check

        Returns:
            bool - True if bar has volume surge
        """
        if bar_idx >= len(bars) or bar_idx < 5:
            return False

        bar = bars[bar_idx]

        # Calculate average volume from 20 bars before this bar
        start_idx = max(0, bar_idx - 20)
        recent_bars = bars[start_idx:bar_idx]

        if len(recent_bars) < 5:
            return False  # Not enough history

        avg_volume = sum(b.volume for b in recent_bars) / len(recent_bars)
        required_volume = avg_volume * self.volume_surge_multiplier

        return bar.volume >= required_volume

    def _check_volume_surge_in_range(self, bars, start_idx, end_idx):
        """
        Check if ANY bar in range has volume surge (≥1.5x average)

        Used for strong breakouts - checking if the move had volume backing

        Args:
            bars: List of price bars
            start_idx: Start of range (inclusive)
            end_idx: End of range (exclusive)

        Returns:
            bool - True if at least one bar has volume surge
        """
        if start_idx < 5 or end_idx > len(bars):
            return False

        # Calculate average volume from bars before the range
        avg_start = max(0, start_idx - 20)
        avg_bars = bars[avg_start:start_idx]

        if len(avg_bars) < 5:
            return False  # Not enough history

        avg_volume = sum(b.volume for b in avg_bars) / len(avg_bars)
        required_volume = avg_volume * self.volume_surge_multiplier

        # Check if ANY bar in the range has volume surge
        range_bars = bars[start_idx:end_idx]
        return any(bar.volume >= required_volume for bar in range_bars)

    def _calculate_atr(self, bars, current_idx):
        """
        Calculate Average True Range (ATR) from recent bars

        ATR measures volatility by averaging the true range over N periods.
        True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))

        Args:
            bars: List of price bars (OHLCV)
            current_idx: Current bar index

        Returns:
            float - ATR value in dollars
        """
        # Get bars for ATR calculation
        start_idx = max(0, current_idx - self.atr_period)
        atr_bars = bars[start_idx:current_idx + 1]

        if len(atr_bars) < 2:
            # Not enough bars, use simple high-low range
            return atr_bars[0].high - atr_bars[0].low if atr_bars else 1.0

        true_ranges = []
        for i in range(1, len(atr_bars)):
            current = atr_bars[i]
            previous = atr_bars[i - 1]

            # True Range = max of:
            # 1. Current high - current low
            # 2. abs(current high - previous close)
            # 3. abs(current low - previous close)
            tr = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close)
            )
            true_ranges.append(tr)

        # ATR is the average of true ranges
        atr = sum(true_ranges) / len(true_ranges) if true_ranges else 1.0

        return atr

    def check_pullback_retest(self, bars, current_idx, pivot_price, side='LONG'):
        """
        Check for pullback/retest entry pattern (Oct 4, 2025)

        Strategy based on false breakout analysis:
        - First attempts fail 77.5% of the time
        - Second attempts succeed 8.8% more often (31.2% vs 22.5%)
        - "Second attempt" = pullback to pivot + re-break

        Entry Logic:
        1. Price breaks resistance (initial breakout)
        2. Wait for 1-minute candle to close above resistance
        3. Wait for pullback within 0.3% of resistance (retest)
        4. Enter when price re-breaks resistance with volume

        Args:
            bars: List of 5-second bars
            current_idx: Current bar index
            pivot_price: Resistance (long) or support (short)
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (should_enter, reason, entry_state)
                entry_state = {
                    'phase': 'waiting_candle_close' | 'waiting_pullback' | 'ready'
                    'breakout_bar': index of initial breakout
                    'candle_close_bar': index where 1-min candle closed
                    'pullback_detected': bool
                }
        """
        if not self.require_candle_close and not self.require_pullback_retest:
            # Both disabled, allow immediate entry
            current_price = bars[current_idx].close
            if side == 'LONG':
                return (current_price > pivot_price), "Immediate entry", None
            else:
                return (current_price < pivot_price), "Immediate entry", None

        # Look back to find the sequence: breakout → 1-min candle close → pullback → re-break
        bars_per_candle = self.candle_timeframe_seconds // 5  # 60 sec / 5 sec = 12 bars

        # Find where price first broke the pivot (look back up to max_pullback_bars)
        lookback_start = max(0, current_idx - self.max_pullback_bars - bars_per_candle)

        breakout_bar = None
        for i in range(lookback_start, current_idx):
            bar_price = bars[i].close
            if side == 'LONG' and bar_price > pivot_price and (i == 0 or bars[i-1].close <= pivot_price):
                breakout_bar = i
                break
            elif side == 'SHORT' and bar_price < pivot_price and (i == 0 or bars[i-1].close >= pivot_price):
                breakout_bar = i
                break

        if breakout_bar is None:
            return False, "No breakout detected", {'phase': 'no_breakout'}

        # Check if we're still within the allowed window
        bars_since_breakout = current_idx - breakout_bar
        if bars_since_breakout > self.max_pullback_bars + bars_per_candle:
            return False, "Breakout too old", {'phase': 'expired'}

        # PHASE 1: Wait for 1-minute candle close
        if self.require_candle_close:
            # Find the 1-min candle that contains the breakout
            candle_start = (breakout_bar // bars_per_candle) * bars_per_candle
            candle_end = candle_start + bars_per_candle

            if current_idx < candle_end:
                # Still inside the breakout candle, wait for close
                return False, "Waiting for 1-min candle close", {
                    'phase': 'waiting_candle_close',
                    'breakout_bar': breakout_bar,
                    'candle_closes_at': candle_end
                }

            # Candle has closed, check if it closed above/below pivot
            if candle_end <= len(bars):
                candle_close_price = bars[candle_end - 1].close

                if side == 'LONG' and candle_close_price <= pivot_price:
                    return False, "1-min candle closed below resistance (failed)", {'phase': 'failed_close'}
                elif side == 'SHORT' and candle_close_price >= pivot_price:
                    return False, "1-min candle closed above support (failed)", {'phase': 'failed_close'}

        # PHASE 2: Wait for pullback to pivot
        if self.require_pullback_retest:
            # Look for pullback after candle close
            candle_close_bar = ((breakout_bar // bars_per_candle) * bars_per_candle) + bars_per_candle

            # Check if price has pulled back close to pivot
            pullback_zone = pivot_price * (1 + self.pullback_distance_pct) if side == 'LONG' else pivot_price * (1 - self.pullback_distance_pct)

            pullback_detected = False
            pullback_bar = None

            for i in range(candle_close_bar, current_idx + 1):
                bar_low = bars[i].low
                bar_high = bars[i].high

                if side == 'LONG':
                    # For longs: check if low came within 0.3% above pivot
                    if bar_low <= pullback_zone:
                        pullback_detected = True
                        pullback_bar = i
                        break
                else:
                    # For shorts: check if high came within 0.3% below pivot
                    if bar_high >= pullback_zone:
                        pullback_detected = True
                        pullback_bar = i
                        break

            if not pullback_detected:
                return False, "Waiting for pullback to pivot", {
                    'phase': 'waiting_pullback',
                    'breakout_bar': breakout_bar,
                    'candle_close_bar': candle_close_bar,
                    'pullback_zone': pullback_zone
                }

            # PHASE 3: Pullback detected, check if re-breaking with volume
            current_price = bars[current_idx].close

            if side == 'LONG':
                if current_price > pivot_price:
                    # Re-breaking resistance after pullback!
                    # Check volume
                    if self.volume_surge_required:
                        has_volume = self._check_volume_surge_in_range(bars, pullback_bar, current_idx + 1)
                        if not has_volume:
                            return False, "Re-breaking but no volume surge", {'phase': 'no_volume'}

                    return True, "PULLBACK/RETEST entry (1-min close + pullback + re-break with volume)", {
                        'phase': 'ready',
                        'breakout_bar': breakout_bar,
                        'pullback_bar': pullback_bar,
                        'entry_bar': current_idx
                    }
                else:
                    return False, "Pullback detected, waiting for re-break", {
                        'phase': 'pullback_complete',
                        'pullback_bar': pullback_bar
                    }
            else:  # SHORT
                if current_price < pivot_price:
                    # Re-breaking support after pullback!
                    if self.volume_surge_required:
                        has_volume = self._check_volume_surge_in_range(bars, pullback_bar, current_idx + 1)
                        if not has_volume:
                            return False, "Re-breaking but no volume surge", {'phase': 'no_volume'}

                    return True, "PULLBACK/RETEST entry (1-min close + pullback + re-break with volume)", {
                        'phase': 'ready',
                        'breakout_bar': breakout_bar,
                        'pullback_bar': pullback_bar,
                        'entry_bar': current_idx
                    }
                else:
                    return False, "Pullback detected, waiting for re-break", {
                        'phase': 'pullback_complete',
                        'pullback_bar': pullback_bar
                    }

        # If we got here, candle close confirmed but no pullback required
        current_price = bars[current_idx].close
        if side == 'LONG':
            return (current_price > pivot_price), "1-min candle close entry (no pullback required)", None
        else:
            return (current_price < pivot_price), "1-min candle close entry (no pullback required)", None

    def check_sustained_break(self, bars, current_idx, pivot_price, side='LONG'):
        """
        Check for sustained break pattern (Oct 5, 2025)

        Alternative to momentum breakout - catches "slow grind" breakouts.
        Criteria:
        - Price broke pivot
        - Has HELD above/below pivot for N minutes (with minimal pullback)
        - Volume shows buying/selling pressure

        This catches PLTR-type breakouts:
        - Weak initial candle (0.04% vs 0.8% required)
        - But sustained hold above resistance for 2+ minutes
        - Good volume (1.44x average)

        Args:
            bars: List of 5-second bars
            current_idx: Current bar index
            pivot_price: Resistance (long) or support (short)
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (is_sustained, reason, state)
        """
        if not self.sustained_break_enabled:
            return False, "Sustained break disabled", None

        # Calculate how many 5-second bars = sustained_break_minutes
        bars_required = (self.sustained_break_minutes * 60) // 5  # e.g., 2 min = 24 bars

        # Look back to find when price first broke pivot
        lookback = min(current_idx, bars_required + 60)  # Extra lookback to find break
        breakout_bar = None

        for i in range(current_idx - lookback, current_idx):
            if i < 0:
                continue

            bar_price = bars[i].close

            # Find first break
            if side == 'LONG':
                if bar_price > pivot_price and (i == 0 or bars[i-1].close <= pivot_price):
                    breakout_bar = i
                    break
            else:  # SHORT
                if bar_price < pivot_price and (i == 0 or bars[i-1].close >= pivot_price):
                    breakout_bar = i
                    break

        if breakout_bar is None:
            return False, "No breakout detected", {'phase': 'no_breakout'}

        # Check if we have enough bars since breakout
        bars_since_breakout = current_idx - breakout_bar
        if bars_since_breakout < bars_required:
            return False, f"Waiting for sustained hold ({bars_since_breakout}/{bars_required} bars)", {
                'phase': 'accumulating',
                'breakout_bar': breakout_bar,
                'bars_held': bars_since_breakout,
                'bars_needed': bars_required
            }

        # Check if price has HELD above/below pivot (with max pullback tolerance)
        sustained_window = bars[breakout_bar:current_idx+1]

        if side == 'LONG':
            # Check all bars stayed above pivot (with small pullback tolerance)
            min_pullback_level = pivot_price * (1 - self.sustained_break_max_pullback_pct)

            for bar in sustained_window:
                if bar.low < min_pullback_level:
                    # Pulled back too far below pivot
                    return False, f"Broke below pivot (low ${bar.low:.2f} < ${min_pullback_level:.2f})", {
                        'phase': 'failed_sustained'
                    }
        else:  # SHORT
            # Check all bars stayed below pivot (with small pullback tolerance)
            max_pullback_level = pivot_price * (1 + self.sustained_break_max_pullback_pct)

            for bar in sustained_window:
                if bar.high > max_pullback_level:
                    # Rallied too far above pivot
                    return False, f"Broke above pivot (high ${bar.high:.2f} > ${max_pullback_level:.2f})", {
                        'phase': 'failed_sustained'
                    }

        # Calculate volume during sustained window
        window_volume = sum(b.volume for b in sustained_window)

        # Get average volume from bars before breakout
        if breakout_bar >= 120:  # Need 10 min history (120 five-sec bars)
            pre_break_bars = bars[breakout_bar-120:breakout_bar]
            avg_volume_per_bar = sum(b.volume for b in pre_break_bars) / len(pre_break_bars)
            avg_window_volume = avg_volume_per_bar * len(sustained_window)

            volume_ratio = window_volume / avg_window_volume if avg_window_volume > 0 else 1.0
        else:
            # Not enough history, assume current is average
            volume_ratio = 1.0

        # Require volume during sustained period (shows buying/selling pressure)
        if volume_ratio < self.volume_surge_multiplier:  # Use same threshold as momentum
            return False, f"Insufficient sustained volume ({volume_ratio:.2f}x < {self.volume_surge_multiplier:.2f}x)", {
                'phase': 'low_volume',
                'volume_ratio': volume_ratio
            }

        # Success - sustained break confirmed!
        return True, f"SUSTAINED_BREAK ({bars_since_breakout} bars/{self.sustained_break_minutes} min, {volume_ratio:.2f}x vol)", {
            'phase': 'sustained_entry',
            'breakout_bar': breakout_bar,
            'bars_held': bars_since_breakout,
            'volume_ratio': volume_ratio,
            'entry_bar': current_idx
        }

    def check_hybrid_entry(self, bars, current_idx, pivot_price, side='LONG', target_price=None):
        """
        HYBRID Entry Strategy (Oct 4, 2025)

        Two entry types based on breakout strength:
        1. MOMENTUM BREAKOUT: Strong volume + large candle = immediate entry
        2. PULLBACK/RETEST: Weak initial break = wait for pullback

        Strategy:
        - Always require 1-min candle close above pivot (filters whipsaws)
        - If breakout candle has strong volume AND large size → MOMENTUM entry
        - If breakout candle is weak → wait for PULLBACK/RETEST

        Args:
            bars: List of 5-second bars
            current_idx: Current bar index
            pivot_price: Resistance (long) or support (short)
            side: 'LONG' or 'SHORT'
            target_price: Target price (optional, for room-to-run filter)

        Returns:
            tuple: (should_enter, reason, entry_state)
        """
        if not self.require_candle_close:
            # Candle close disabled, allow immediate entry
            current_price = bars[current_idx].close
            if side == 'LONG':
                return (current_price > pivot_price), "Immediate entry", None
            else:
                return (current_price < pivot_price), "Immediate entry", None

        bars_per_candle = self.candle_timeframe_seconds // 5  # 60 sec / 5 sec = 12 bars

        # Find where price first broke the pivot
        lookback_start = max(0, current_idx - self.max_pullback_bars - bars_per_candle)

        breakout_bar = None
        for i in range(lookback_start, current_idx):
            bar_price = bars[i].close
            if side == 'LONG' and bar_price > pivot_price and (i == 0 or bars[i-1].close <= pivot_price):
                breakout_bar = i
                break
            elif side == 'SHORT' and bar_price < pivot_price and (i == 0 or bars[i-1].close >= pivot_price):
                breakout_bar = i
                break

        if breakout_bar is None:
            return False, "No breakout detected", {'phase': 'no_breakout'}

        # Check if breakout is expired
        bars_since_breakout = current_idx - breakout_bar
        if bars_since_breakout > self.max_pullback_bars + bars_per_candle:
            return False, "Breakout too old", {'phase': 'expired'}

        # STEP 1: Wait for 1-minute candle close
        candle_start = (breakout_bar // bars_per_candle) * bars_per_candle
        candle_end = candle_start + bars_per_candle

        # BOUNDS CHECK: Ensure candle_end doesn't exceed array length
        if candle_end > len(bars):
            candle_end = len(bars)

        # Additional safety: Ensure we have enough bars for the candle
        if candle_end - candle_start < bars_per_candle:
            return False, "Insufficient bars for candle close", {'phase': 'insufficient_data'}

        if current_idx < candle_end:
            # Still inside the breakout candle, wait for close
            return False, "Waiting for 1-min candle close", {
                'phase': 'waiting_candle_close',
                'breakout_bar': breakout_bar,
                'candle_closes_at': candle_end
            }

        # Candle has closed - get close price with bounds check
        candle_close_price = bars[candle_end - 1].close

        if side == 'LONG' and candle_close_price <= pivot_price:
            return False, "1-min candle closed below resistance (failed)", {'phase': 'failed_close'}
        elif side == 'SHORT' and candle_close_price >= pivot_price:
            return False, "1-min candle closed above support (failed)", {'phase': 'failed_close'}

        # STEP 2: Analyze breakout candle strength
        candle_bars = bars[candle_start:candle_end]

        # Calculate candle size
        candle_open = candle_bars[0].open
        candle_close = candle_bars[-1].close
        candle_high = max(b.high for b in candle_bars)
        candle_low = min(b.low for b in candle_bars)

        candle_size_pct = abs(candle_close - candle_open) / candle_open
        candle_range_pct = (candle_high - candle_low) / candle_open

        # Calculate volume ratio
        candle_volume = sum(b.volume for b in candle_bars)

        # Get average volume (look back 20 candles)
        avg_volume_lookback = max(0, candle_start - (20 * bars_per_candle))
        if avg_volume_lookback < candle_start:
            past_bars = bars[avg_volume_lookback:candle_start]
            if past_bars:
                avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
                avg_candle_volume = avg_volume_per_bar * bars_per_candle
            else:
                avg_candle_volume = candle_volume  # No history, assume current is average
        else:
            avg_candle_volume = candle_volume

        # BOUNDS CHECK: Prevent division by zero
        volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 1.0

        # Calculate ATR ratio with bounds checking
        # Ensure we have enough bars for ATR calculation
        if candle_end - 1 >= self.atr_period:
            atr = self._calculate_atr(bars, candle_end - 1)
            candle_atr_ratio = (candle_high - candle_low) / atr if atr > 0 else 1.0
        else:
            # Not enough data for ATR - use simplified ratio
            candle_atr_ratio = 1.0

        # STEP 3: Determine entry type
        is_strong_volume = volume_ratio >= self.momentum_volume_threshold
        is_large_candle = (candle_size_pct >= self.momentum_candle_min_pct or
                          candle_atr_ratio >= self.momentum_candle_min_atr)

        if is_strong_volume and is_large_candle:
            # ✅ MOMENTUM BREAKOUT - Enter immediately!
            current_price = bars[current_idx].close

            # FIX #4: Check if market is choppy (anti-consolidation filter)
            is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
            if is_choppy:
                return False, choppy_reason, {'phase': 'choppy_filter'}

            # FIX #2: Check entry position before entering (anti-chasing filter)
            is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
            if is_chasing:
                return False, chasing_reason, {'phase': 'chasing_filter'}

            if side == 'LONG':
                if current_price > pivot_price:
                    return True, f"MOMENTUM_BREAKOUT ({volume_ratio:.1f}x vol, {candle_size_pct*100:.1f}% candle)", {
                        'phase': 'momentum_entry',
                        'breakout_bar': breakout_bar,
                        'candle_start': candle_start,
                        'candle_end': candle_end,
                        'volume_ratio': volume_ratio,
                        'candle_size_pct': candle_size_pct,
                        'entry_bar': current_idx
                    }
            else:  # SHORT
                if current_price < pivot_price:
                    return True, f"MOMENTUM_BREAKOUT ({volume_ratio:.1f}x vol, {candle_size_pct*100:.1f}% candle)", {
                        'phase': 'momentum_entry',
                        'breakout_bar': breakout_bar,
                        'candle_start': candle_start,
                        'candle_end': candle_end,
                        'volume_ratio': volume_ratio,
                        'candle_size_pct': candle_size_pct,
                        'entry_bar': current_idx
                    }

        # STEP 4: Weak breakout - try pullback/retest logic OR sustained break
        if self.require_pullback_retest:
            pullback_confirmed, pullback_reason, pullback_state = self.check_pullback_retest(
                bars, current_idx, pivot_price, side
            )

            if pullback_confirmed:
                # FIX #4: Check if market is choppy (anti-consolidation filter)
                is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
                if is_choppy:
                    return False, choppy_reason, {'phase': 'choppy_filter'}

                # Room-to-run filter (Oct 5, 2025)
                # Smarter chasing filter: Check if enough room to target
                # Replaces range-based chasing filter with target-based logic
                current_price = bars[current_idx].close
                insufficient_room, room_reason = self._check_room_to_run(
                    current_price, target_price, side
                )
                if insufficient_room:
                    return False, room_reason, {'phase': 'room_to_run_filter'}

                # Enhance reason to show it's part of hybrid strategy
                return True, f"PULLBACK/RETEST (weak initial: {volume_ratio:.1f}x vol, {candle_size_pct*100:.1f}% candle)", pullback_state
            else:
                # Pullback not confirmed yet - check sustained break as alternative
                # This catches PLTR-type slow grinds that don't pull back
                sustained_confirmed, sustained_reason, sustained_state = self.check_sustained_break(
                    bars, current_idx, pivot_price, side
                )

                if sustained_confirmed:
                    print(f"🔍 DEBUG: Sustained break confirmed! About to return TRUE...")
                    # FIX #4: Check if market is choppy (anti-consolidation filter)
                    is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
                    if is_choppy:
                        print(f"🔍 DEBUG: Blocked by choppy filter")
                        return False, choppy_reason, {'phase': 'choppy_filter'}

                    # Room-to-run filter (Oct 5, 2025)
                    # Smarter chasing filter: Check if enough room to target
                    current_price = bars[current_idx].close
                    insufficient_room, room_reason = self._check_room_to_run(
                        current_price, target_price, side
                    )
                    if insufficient_room:
                        print(f"🔍 DEBUG: Blocked by room-to-run filter")
                        return False, room_reason, {'phase': 'room_to_run_filter'}

                    print(f"🔍 DEBUG: Returning TRUE for sustained break (passed room-to-run filter)")
                    return True, sustained_reason, sustained_state
                else:
                    # Still waiting for pullback or sustained break
                    return False, f"Waiting for pullback or sustained break (weak: {volume_ratio:.1f}x vol, {candle_size_pct*100:.1f}% candle)", pullback_state
        else:
            # Pullback disabled - check sustained break OR enter on candle close
            sustained_confirmed, sustained_reason, sustained_state = self.check_sustained_break(
                bars, current_idx, pivot_price, side
            )

            if sustained_confirmed:
                # Skip chasing filter for sustained breaks (same reason as above)
                return True, sustained_reason, sustained_state
            else:
                # Sustained break not ready, enter on candle close even if weak
                current_price = bars[current_idx].close
                if side == 'LONG':
                    return (current_price > pivot_price), f"Weak breakout entry ({volume_ratio:.1f}x vol)", None
                else:
                    return (current_price < pivot_price), f"Weak breakout entry ({volume_ratio:.1f}x vol)", None

    def _check_gap_filter(self, stock_data, current_price, side='LONG'):
        """
        Check if trade should be skipped due to gap through pivot

        Smart Gap Filter:
        - Allow if gap is small (<1% through pivot)
        - Allow if gap is large BUT plenty of room to target (>3%)
        - Skip if gap is large AND little room left to target

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            side: 'LONG' or 'SHORT'

        Returns:
            (bool, reason) - Should skip, and reason
        """
        if not self.enable_gap_filter:
            return False, None

        previous_close = stock_data.get('close')
        if previous_close is None:
            return False, None  # No previous close data, can't check gap

        if side == 'LONG':
            pivot = stock_data['resistance']
            target = stock_data.get('target1')

            # Check if gapped through pivot
            if previous_close < pivot and current_price > pivot:
                gap_pct = ((current_price - pivot) / pivot) * 100

                # Small gap (<1%) - OK to enter
                if gap_pct <= self.max_gap_through_pivot:
                    return False, None

                # Large gap - check room to target
                if target:
                    room_to_target = ((target - current_price) / current_price) * 100

                    # Plenty of room (>3%) - OK to enter despite gap
                    if room_to_target >= self.min_room_to_target:
                        return False, None

                    # Gap ate up the move - SKIP
                    return True, f"Gap {gap_pct:.1f}% through pivot, only {room_to_target:.1f}% to target"

        else:  # SHORT
            pivot = stock_data['support']
            target = stock_data.get('downside1', stock_data.get('target1'))

            # Check if gapped down through pivot
            if previous_close > pivot and current_price < pivot:
                gap_pct = ((pivot - current_price) / pivot) * 100

                # Small gap (<1%) - OK to enter
                if gap_pct <= self.max_gap_through_pivot:
                    return False, None

                # Large gap - check room to target
                if target:
                    room_to_target = ((current_price - target) / current_price) * 100

                    # Plenty of room (>3%) - OK to enter despite gap
                    if room_to_target >= self.min_room_to_target:
                        return False, None

                    # Gap ate up the move - SKIP
                    return True, f"Gap {gap_pct:.1f}% through pivot, only {room_to_target:.1f}% to target"

        return False, None

    def _check_entry_position(self, bars, current_idx, entry_price, side='LONG'):
        """
        FIX #2 (Oct 4, 2025): Check if entry position is too high in recent range

        Prevents chasing entries by ensuring we're not buying near local highs
        or selling near local lows.

        Analysis from Sept 23-30:
        - Winners entered at 36% of 5-min range
        - Losers entered at 81% of 5-min range
        - Chasing trades (>70%) had 15.3% win rate and lost $13,099

        Args:
            bars: List of 5-second bars
            current_idx: Current bar index
            entry_price: Proposed entry price
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (should_skip, reason)
                - should_skip: True if entry position is too high (chasing)
                - reason: Explanation string
        """
        if not self.enable_entry_position_filter:
            return False, None

        # Get recent price range (5 minutes of 5-sec bars = 60 bars)
        lookback_start = max(0, current_idx - self.entry_position_lookback_bars)
        recent_bars = bars[lookback_start:current_idx + 1]

        if len(recent_bars) < 10:  # Need at least 10 bars for valid range
            return False, None

        # Calculate range
        recent_high = max(b.high for b in recent_bars)
        recent_low = min(b.low for b in recent_bars)

        if recent_high <= recent_low:  # No range
            return False, None

        # Calculate entry position in range (0-100%)
        entry_position_pct = ((entry_price - recent_low) / (recent_high - recent_low)) * 100

        # Check if chasing
        if side == 'LONG':
            # For longs, don't buy near the high of recent range
            if entry_position_pct > self.max_entry_position_pct:
                return True, f"Chasing: Entry at {entry_position_pct:.0f}% of 5-min range (max {self.max_entry_position_pct}%)"
        else:  # SHORT
            # For shorts, don't sell near the low of recent range
            if entry_position_pct < (100 - self.max_entry_position_pct):
                return True, f"Chasing: Entry at {entry_position_pct:.0f}% of 5-min range (min {100-self.max_entry_position_pct}%)"

        return False, None

    def _check_room_to_run(self, current_price, target_price, side='LONG'):
        """
        Room-to-run filter (Oct 5, 2025)

        Smarter chasing filter for pullback/retest entries.
        Instead of checking position in recent range, check if there's
        enough room remaining to reach the target.

        This prevents entering trades where:
        - Overnight gaps ate up most of the move
        - Delayed entry means target is too close
        - Risk/reward no longer favorable

        Args:
            current_price: Current/entry price
            target_price: Target price (target1 from scanner)
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (insufficient_room, reason)
                - insufficient_room: True if not enough room to target
                - reason: Explanation string

        Example:
            Entry $183.03, Target $184.14 = 0.61% room → BLOCK
            Entry $100, Target $103 = 3.0% room → ALLOW
        """
        if not self.enable_room_to_run_filter:
            return False, None

        if target_price is None:
            return False, None  # Can't check without target

        if side == 'LONG':
            room_pct = ((target_price - current_price) / current_price) * 100
        else:  # SHORT
            room_pct = ((current_price - target_price) / current_price) * 100

        if room_pct < self.min_room_to_target_pct:
            return True, f"Insufficient room to target: {room_pct:.2f}% < {self.min_room_to_target_pct:.1f}% minimum"

        return False, None

    def _check_choppy_market(self, bars, current_idx):
        """
        FIX #4 (Oct 4, 2025): Check if market is choppy/consolidating

        Prevents entering during sideways price action that leads to whipsaws.

        Analysis from Sept 23-30:
        - 75 trades (61%) had choppy price action (first min move <0.15%)
        - These choppy trades had 6.7% win rate and lost $15,425
        - Need to detect consolidation and skip entry

        Args:
            bars: List of 5-second bars
            current_idx: Current bar index

        Returns:
            tuple: (is_choppy, reason)
                - is_choppy: True if market is consolidating (low volatility)
                - reason: Explanation string
        """
        if not self.enable_choppy_filter:
            return False, None

        # Get recent bars (5 minutes)
        lookback_start = max(0, current_idx - self.choppy_lookback_bars)
        recent_bars = bars[lookback_start:current_idx + 1]

        if len(recent_bars) < self.atr_period:  # Need enough bars for ATR
            return False, None

        # Calculate recent range
        recent_high = max(b.high for b in recent_bars)
        recent_low = min(b.low for b in recent_bars)
        recent_range = recent_high - recent_low

        if recent_range == 0:
            return True, "No price movement (zero range)"

        # Calculate ATR
        atr = self._calculate_atr(bars, current_idx)

        if atr == 0:
            return False, None

        # Check if recent range is too tight compared to ATR
        range_to_atr_ratio = recent_range / atr

        if range_to_atr_ratio < self.choppy_atr_multiplier:
            return True, f"Choppy market: 5-min range is only {range_to_atr_ratio:.2f}× ATR (min {self.choppy_atr_multiplier}×)"

        return False, None

    def should_enter_long(self, stock_data, current_price, attempt_count=0, bars=None, current_idx=None):
        """
        Check if should enter long position

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            attempt_count: Number of previous attempts on this pivot
            bars: Optional - List of bars for hybrid entry confirmation (live trader)
            current_idx: Optional - Current bar index (live trader)

        Returns:
            (bool, reason) - Should enter, and reason why/why not
        """
        symbol = stock_data['symbol']
        resistance = stock_data['resistance']

        # Check if pivot broken
        if current_price <= resistance:
            return False, "Price below resistance"

        # Check attempt count
        if attempt_count >= self.max_attempts_per_pivot:
            return False, f"Max attempts ({self.max_attempts_per_pivot}) reached"

        # Check if in avoid list
        if symbol in self.avoid_symbols:
            return False, f"Symbol in avoid list"

        # Check position size (prevents over-concentration in high-priced stocks)
        stop_distance = abs(current_price - resistance)
        max_risk_dollars = self.account_size * self.risk_per_trade
        shares = max_risk_dollars / stop_distance if stop_distance > 0 else 0
        position_value = shares * current_price
        position_pct = (position_value / self.account_size) * 100

        if position_pct > self.max_position_pct:
            return False, f"Position too large ({position_pct:.1f}% > {self.max_position_pct}% max)"

        # NOTE: Gap filter is NOT checked here - it's applied at market open
        # by filter_scanner_for_gaps() in the backtester/live trader before
        # the stock is even added to the watchlist. Checking it here with
        # current_price would incorrectly use intraday price movement instead
        # of the actual overnight gap.

        # CRITICAL: If bars provided (live trader), check hybrid entry confirmation
        if bars is not None and current_idx is not None:
            target1 = stock_data.get('target1')
            confirmed, path, reason = self.check_hybrid_entry(
                bars, current_idx, resistance, side='LONG', target_price=target1
            )

            if not confirmed:
                return False, reason

            return True, f"LONG confirmed via {path}"

        # Backtest path: Pivot broken (hybrid entry checked in backtester loop)
        return True, "Resistance broken"

    def should_enter_short(self, stock_data, current_price, attempt_count=0, bars=None, current_idx=None):
        """
        Check if should enter short position

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            attempt_count: Number of previous attempts on this pivot
            bars: Optional - List of bars for hybrid entry confirmation (live trader)
            current_idx: Optional - Current bar index (live trader)

        Returns:
            (bool, reason) - Should enter, and reason why/why not
        """
        symbol = stock_data['symbol']
        support = stock_data['support']

        # Check if pivot broken
        if current_price >= support:
            return False, "Price above support"

        # Check attempt count
        if attempt_count >= self.max_attempts_per_pivot:
            return False, f"Max attempts ({self.max_attempts_per_pivot}) reached"

        # Avoid index shorts if configured
        if self.avoid_index_shorts:
            index_symbols = ['SPY', 'QQQ', 'DIA', 'IWM']
            if symbol in index_symbols:
                return False, "Avoiding index short"

        # Check if in avoid list
        if symbol in self.avoid_symbols:
            return False, f"Symbol in avoid list"

        # NOTE: Gap filter is NOT checked here - it's applied at market open
        # by filter_scanner_for_gaps() in the backtester/live trader before
        # the stock is even added to the watchlist. Checking it here with
        # current_price would incorrectly use intraday price movement instead
        # of the actual overnight gap.

        # Check position size (prevents over-concentration in high-priced stocks)
        stop_distance = abs(current_price - support)
        max_risk_dollars = self.account_size * self.risk_per_trade
        shares = max_risk_dollars / stop_distance if stop_distance > 0 else 0
        position_value = shares * current_price
        position_pct = (position_value / self.account_size) * 100

        if position_pct > self.max_position_pct:
            return False, f"Position too large ({position_pct:.1f}% > {self.max_position_pct}% max)"

        # CRITICAL: If bars provided (live trader), check hybrid entry confirmation
        if bars is not None and current_idx is not None:
            downside1 = stock_data.get('downside1')
            confirmed, path, reason = self.check_hybrid_entry(
                bars, current_idx, support, side='SHORT', target_price=downside1
            )

            if not confirmed:
                return False, reason

            return True, f"SHORT confirmed via {path}"

        # Backtest path: Pivot broken (hybrid entry checked in backtester loop)
        return True, "Support broken"

    def should_take_partial(self, position, current_price):
        """
        Check if should take partial profit

        Per requirements: Take partial at 1R (when profit equals initial risk)

        Returns:
            (bool, pct, reason) - Should take partial, what %, and reason
        """
        entry_price = position['entry_price']
        stop_price = position['stop']
        side = position['side']
        remaining = position['remaining']
        partials_taken = len(position['partials'])

        # Calculate current gain and initial risk (1R)
        if side == 'LONG':
            gain = current_price - entry_price
            risk = entry_price - stop_price  # Initial risk (1R)
        else:
            gain = entry_price - current_price
            risk = stop_price - entry_price  # Initial risk (1R)

        # First partial (50%) at 1R - per requirements
        # This means: profit >= risk (1:1 ratio achieved)
        if remaining == 1.0 and gain >= risk:
            return True, self.partial_1_pct, '1R (Profit = Risk)'

        # Second partial (25% at target1) - only if we took first partial
        if remaining == 0.5 and partials_taken == 1:
            # Check if at target1 (from scanner)
            if side == 'LONG':
                target1 = position.get('target1', entry_price + (risk * 2))  # Default to 2R if no target
                if current_price >= target1:
                    # Calculate pct relative to remaining (25% of original = 50% of remaining)
                    return True, 0.50, 'TARGET1 (2R)'
            else:
                target1 = position.get('target1', entry_price - (risk * 2))
                if current_price <= target1:
                    return True, 0.50, 'TARGET1 (2R)'

        return False, 0, None

    def should_move_stop_to_breakeven(self, position):
        """Check if should move stop to breakeven"""
        if not self.breakeven_after_partial:
            return False

        # Move to breakeven after first partial
        if position['partials'] and position['stop'] != position['entry_price']:
            return True

        return False

    def calculate_stop_price(self, position, current_price=None):
        """
        Calculate stop price for position

        Returns:
            float - Stop price
        """
        # After partial: breakeven
        if position['partials'] and self.breakeven_after_partial:
            return position['entry_price']

        # Initial stop: at pivot
        if self.stop_at_pivot:
            if position['side'] == 'LONG':
                return position['pivot']  # Resistance (entry trigger)
            else:
                return position['pivot']  # Support (entry trigger)

        # Default: entry price
        return position['entry_price']

    def update_trailing_stop(self, position, current_price):
        """
        Update trailing stop for runner position

        Per requirements: Trail by percentage or ATR-based
        Only activate after minimum profit achieved

        Args:
            position: Position dict
            current_price: Current market price

        Returns:
            (bool, float, str) - (Stop updated, new stop price, reason)
        """
        if not self.trailing_stop_enabled:
            return False, position['stop'], "Trailing stop disabled"

        # Only apply trailing stop to runners (after partials taken)
        if position.get('remaining', 1.0) >= 1.0:
            return False, position['stop'], "Not a runner yet (no partials taken)"

        entry_price = position['entry_price']
        side = position['side']
        current_stop = position['stop']

        # Calculate current profit %
        if side == 'LONG':
            profit_pct = ((current_price - entry_price) / entry_price)
        else:
            profit_pct = ((entry_price - current_price) / entry_price)

        # Only activate trailing stop after minimum profit
        if profit_pct < self.trailing_stop_min_profit:
            return False, current_stop, f"Profit {profit_pct:.2%} below min {self.trailing_stop_min_profit:.2%}"

        # Track highest/lowest price for trailing
        if 'high_water_mark' not in position:
            position['high_water_mark'] = current_price
        if 'low_water_mark' not in position:
            position['low_water_mark'] = current_price

        # Calculate new trailing stop
        if self.trailing_stop_type == 'percentage':
            if side == 'LONG':
                # Update high water mark
                if current_price > position['high_water_mark']:
                    position['high_water_mark'] = current_price

                # Trail by percentage below high
                new_stop = position['high_water_mark'] * (1 - self.trailing_stop_pct)

                # Only move stop up (never down for longs)
                if new_stop > current_stop:
                    return True, new_stop, f"Trailing {self.trailing_stop_pct:.1%} below high ${position['high_water_mark']:.2f}"

            else:  # SHORT
                # Update low water mark
                if current_price < position['low_water_mark']:
                    position['low_water_mark'] = current_price

                # Trail by percentage above low
                new_stop = position['low_water_mark'] * (1 + self.trailing_stop_pct)

                # Only move stop down (never up for shorts)
                if new_stop < current_stop:
                    return True, new_stop, f"Trailing {self.trailing_stop_pct:.1%} above low ${position['low_water_mark']:.2f}"

        elif self.trailing_stop_type == 'atr':
            # ATR-based trailing (would need ATR calculation)
            # For now, fall back to percentage
            return self.update_trailing_stop_percentage(position, current_price)

        return False, current_stop, "No update needed"

    def check_trailing_stop_hit(self, position, current_price):
        """
        Check if trailing stop has been hit

        Args:
            position: Position dict
            current_price: Current market price

        Returns:
            (bool, str) - (Stop hit, reason)
        """
        if not self.trailing_stop_enabled:
            return False, None

        # Only check for runners
        if position.get('remaining', 1.0) >= 1.0:
            return False, None

        stop_price = position['stop']
        side = position['side']

        if side == 'LONG':
            if current_price <= stop_price:
                return True, f"TRAIL_STOP (${stop_price:.2f})"
        else:  # SHORT
            if current_price >= stop_price:
                return True, f"TRAIL_STOP (${stop_price:.2f})"

        return False, None

    def is_within_entry_window(self, current_time):
        """
        Check if current time is within entry window

        Args:
            current_time: datetime object (should be Eastern Time)

        Returns:
            bool - Can enter new trades
        """
        # Ensure we're working with Eastern Time
        if current_time.tzinfo is None:
            eastern = pytz.timezone('US/Eastern')
            current_time = eastern.localize(current_time)
        elif current_time.tzinfo != pytz.timezone('US/Eastern'):
            eastern = pytz.timezone('US/Eastern')
            current_time = current_time.astimezone(eastern)

        current = current_time.time()

        return self.min_entry_time <= current <= self.max_entry_time

    def is_near_eod(self, current_time):
        """
        Check if near end of day (should close positions)

        Args:
            current_time: datetime object (should be Eastern Time)

        Returns:
            bool - Should close all positions
        """
        # Ensure we're working with Eastern Time
        if current_time.tzinfo is None:
            eastern = pytz.timezone('US/Eastern')
            current_time = eastern.localize(current_time)
        elif current_time.tzinfo != pytz.timezone('US/Eastern'):
            eastern = pytz.timezone('US/Eastern')
            current_time = current_time.astimezone(eastern)

        current = current_time.time()

        return current >= self.eod_close_time

    def calculate_position_size(self, account_size, entry_price, stop_price, risk_per_trade=None):
        """
        Calculate position size based on risk

        Args:
            account_size: Total account value
            entry_price: Entry price
            stop_price: Stop loss price
            risk_per_trade: Risk per trade (default from config)

        Returns:
            int - Number of shares
        """
        if risk_per_trade is None:
            risk_per_trade = self.trading_config['risk_per_trade']

        risk_amount = account_size * risk_per_trade
        stop_distance = abs(entry_price - stop_price)

        if stop_distance == 0:
            return 0

        shares = int(risk_amount / stop_distance)

        # Apply min/max constraints
        min_shares = self.trading_config['position_sizing']['min_shares']
        max_shares = self.trading_config['position_sizing']['max_shares']

        shares = max(min_shares, min(shares, max_shares))

        return shares

    def filter_scanner_results(self, scanner_results):
        """
        Filter scanner results based on strategy criteria

        Args:
            scanner_results: List of scanner result dicts

        Returns:
            List of filtered results
        """
        filtered = []

        for stock in scanner_results:
            # Score filter
            if stock.get('score', 0) < self.min_score:
                continue

            # Risk/Reward filter
            if stock.get('risk_reward', 0) < self.min_risk_reward:
                continue

            # Distance to pivot filter (optional)
            dist_to_r = abs(stock.get('dist_to_R%', 100))
            dist_to_s = abs(stock.get('dist_to_S%', 100))
            min_dist = min(dist_to_r, dist_to_s)

            if min_dist > self.max_dist_to_pivot:
                continue

            # Symbol avoid list
            if stock['symbol'] in self.avoid_symbols:
                continue

            filtered.append(stock)

        return filtered

    def filter_scanner_for_gaps(self, scanner_results, opening_prices):
        """
        Filter scanner results at market open based on overnight gaps

        This is called ONCE at 9:30 AM to remove stocks where the gap
        invalidated the setup (gap ate up the move to target).

        Args:
            scanner_results: List of scanner setups from previous night
            opening_prices: Dict of {symbol: opening_price} from market open

        Returns:
            (filtered_list, gap_report) - Filtered stocks and gap analysis report
        """
        if not self.enable_gap_filter:
            return scanner_results, {'skipped': [], 'adjusted': [], 'noted': []}

        filtered = []
        gap_report = {'skipped': [], 'adjusted': [], 'noted': []}

        for stock in scanner_results:
            symbol = stock['symbol']
            opening_price = opening_prices.get(symbol)

            if opening_price is None:
                # No opening price data, keep the stock
                filtered.append(stock)
                continue

            prev_close = stock.get('close')
            if prev_close is None:
                filtered.append(stock)
                continue

            resistance = stock.get('resistance')
            support = stock.get('support')
            target1 = stock.get('target1')

            # Calculate gap
            gap_pct = ((opening_price - prev_close) / prev_close) * 100

            skip_long = False
            skip_short = False
            reason = None

            # Check LONG setup (gap up through resistance)
            if resistance and target1:
                # Did it gap through resistance?
                if opening_price > resistance and prev_close < resistance:
                    gap_through_pct = ((opening_price - resistance) / resistance) * 100
                    room_to_target = ((target1 - opening_price) / opening_price) * 100

                    # Large gap with no room left?
                    if gap_through_pct > self.max_gap_through_pivot and room_to_target < self.min_room_to_target:
                        skip_long = True
                        reason = f"Gap up {gap_through_pct:.1f}% through resistance, only {room_to_target:.1f}% to target"
                        gap_report['skipped'].append({
                            'symbol': symbol,
                            'direction': 'LONG',
                            'gap_pct': gap_pct,
                            'gap_through': gap_through_pct,
                            'room_to_target': room_to_target,
                            'reason': reason
                        })
                    elif gap_through_pct > self.max_gap_through_pivot:
                        # Large gap but still has room
                        gap_report['adjusted'].append({
                            'symbol': symbol,
                            'direction': 'LONG',
                            'gap_pct': gap_pct,
                            'gap_through': gap_through_pct,
                            'room_to_target': room_to_target,
                            'reason': f"Gap up {gap_through_pct:.1f}%, but {room_to_target:.1f}% to target remains"
                        })

            # Check SHORT setup (gap down through support)
            if support and self.trading_config.get('enable_shorts', False):
                downside_target = stock.get('downside1', support * 0.98)

                # Did it gap through support?
                if opening_price < support and prev_close > support:
                    gap_through_pct = ((support - opening_price) / support) * 100
                    room_to_downside = ((opening_price - downside_target) / opening_price) * 100

                    # Large gap with no room left?
                    if gap_through_pct > self.max_gap_through_pivot and room_to_downside < self.min_room_to_target:
                        skip_short = True
                        reason = f"Gap down {gap_through_pct:.1f}% through support, only {room_to_downside:.1f}% to downside"
                        gap_report['skipped'].append({
                            'symbol': symbol,
                            'direction': 'SHORT',
                            'gap_pct': gap_pct,
                            'gap_through': gap_through_pct,
                            'room_to_target': room_to_downside,
                            'reason': reason
                        })
                    elif gap_through_pct > self.max_gap_through_pivot:
                        gap_report['adjusted'].append({
                            'symbol': symbol,
                            'direction': 'SHORT',
                            'gap_pct': gap_pct,
                            'gap_through': gap_through_pct,
                            'room_to_target': room_to_downside,
                            'reason': f"Gap down {gap_through_pct:.1f}%, but {room_to_downside:.1f}% to downside remains"
                        })

            # Report significant gaps (>2%) even if not skipping
            if abs(gap_pct) > 2.0 and not skip_long and not skip_short:
                dist_to_r = abs(((opening_price - resistance) / opening_price) * 100) if resistance else 100
                dist_to_s = abs(((opening_price - support) / opening_price) * 100) if support else 100
                gap_report['noted'].append({
                    'symbol': symbol,
                    'direction': 'BOTH',
                    'gap_pct': gap_pct,
                    'dist_to_pivot': min(dist_to_r, dist_to_s),
                    'reason': f"Gap {gap_pct:+.1f}%, now {min(dist_to_r, dist_to_s):.1f}% from pivot"
                })

            # Keep stock if not skipped
            if not skip_long and not skip_short:
                filtered.append(stock)

        return filtered, gap_report

    def check_bounce_setup(self, bars, current_idx, support_price, side='LONG'):
        """
        Check for bounce play setup per requirements:
        - Stock pulls back to known support
        - Bounces upward with reversal pattern
        - Confirmed with volume

        Args:
            bars: List of 1-minute bars
            current_idx: Current bar index
            support_price: Support level to bounce from
            side: 'LONG' for bounce off support

        Returns:
            (bool, str) - (Is bounce confirmed, reason)
        """
        if not self.enable_bounce:
            return False, "Bounce setups disabled"

        if current_idx < 5:
            return False, "Insufficient bars for bounce detection"

        current_bar = bars[current_idx]

        # Check if price touched support in recent bars
        lookback = min(10, current_idx)
        recent_bars = bars[current_idx - lookback:current_idx + 1]

        touched_support = False
        bounce_bar_idx = None

        for i, bar in enumerate(recent_bars):
            # Check if low touched or pierced support
            if bar.low <= support_price * 1.002:  # Within 0.2% of support
                touched_support = True
                bounce_bar_idx = current_idx - lookback + i

        if not touched_support:
            return False, "Support not touched recently"

        # Check for reversal pattern (bullish engulfing or hammer)
        if current_idx > bounce_bar_idx:
            bounce_bar = bars[bounce_bar_idx]
            next_bar = bars[bounce_bar_idx + 1] if bounce_bar_idx + 1 < len(bars) else None

            if next_bar:
                # Bullish engulfing: Next bar closes above previous high
                if next_bar.close > bounce_bar.high:
                    # FIX #2 & #4 (Oct 4, 2025): Apply filters before confirming bounce
                    current_price = next_bar.close
                    is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
                    if is_chasing:
                        return False, f"Bounce rejected: {chasing_reason}"

                    is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
                    if is_choppy:
                        return False, f"Bounce rejected: {choppy_reason}"

                    # Check volume confirmation
                    if self.confirmation_enabled and self.volume_surge_required:
                        recent_vol = [b.volume for b in recent_bars[:-1]]
                        avg_vol = sum(recent_vol) / len(recent_vol) if recent_vol else 1

                        if next_bar.volume >= avg_vol * self.volume_surge_multiplier:
                            return True, f"Bounce confirmed: Bullish engulfing with volume surge"
                    else:
                        return True, "Bounce confirmed: Bullish engulfing"

                # Hammer pattern: Long lower wick, close near high
                body = abs(bounce_bar.close - bounce_bar.open)
                lower_wick = bounce_bar.open - bounce_bar.low if bounce_bar.close > bounce_bar.open else bounce_bar.close - bounce_bar.low
                candle_range = bounce_bar.high - bounce_bar.low

                if candle_range > 0:
                    if lower_wick / candle_range > 0.6 and body / candle_range < 0.3:
                        # FIX #2 & #4 (Oct 4, 2025): Apply filters before confirming bounce
                        current_price = bounce_bar.close
                        is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
                        if is_chasing:
                            return False, f"Bounce rejected: {chasing_reason}"

                        is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
                        if is_choppy:
                            return False, f"Bounce rejected: {choppy_reason}"

                        return True, "Bounce confirmed: Hammer pattern"

        # Check if price is now above support (bouncing)
        if current_bar.close > support_price * 1.005:  # 0.5% above support
            # FIX #2 (Oct 4, 2025): Apply entry position filter to bounce entries
            current_price = current_bar.close
            is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
            if is_chasing:
                return False, f"Bounce rejected: {chasing_reason}"

            # FIX #4 (Oct 4, 2025): Apply choppy filter to bounce entries
            is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
            if is_choppy:
                return False, f"Bounce rejected: {choppy_reason}"

            return True, "Bounce confirmed: Price above support"

        return False, "No clear bounce pattern"

    def check_rejection_setup(self, bars, current_idx, resistance_price, side='SHORT'):
        """
        Check for rejection/fade setup per requirements:
        - Price hits resistance but fails to break out
        - Shows rejection (long upper wick, bearish reversal)
        - Confirmed with volume

        Args:
            bars: List of 1-minute bars
            current_idx: Current bar index
            resistance_price: Resistance level to reject from
            side: 'SHORT' for fade/rejection

        Returns:
            (bool, str) - (Is rejection confirmed, reason)
        """
        if not self.enable_rejection:
            return False, "Rejection setups disabled"

        if current_idx < 5:
            return False, "Insufficient bars for rejection detection"

        current_bar = bars[current_idx]

        # Check if price touched resistance in recent bars
        lookback = min(10, current_idx)
        recent_bars = bars[current_idx - lookback:current_idx + 1]

        touched_resistance = False
        rejection_bar_idx = None

        for i, bar in enumerate(recent_bars):
            # Check if high touched or pierced resistance
            if bar.high >= resistance_price * 0.998:  # Within 0.2% of resistance
                touched_resistance = True
                rejection_bar_idx = current_idx - lookback + i

        if not touched_resistance:
            return False, "Resistance not touched recently"

        # Check for rejection pattern (long upper wick)
        if rejection_bar_idx is not None:
            reject_bar = bars[rejection_bar_idx]

            # Long upper wick rejection
            body = abs(reject_bar.close - reject_bar.open)
            upper_wick = reject_bar.high - max(reject_bar.close, reject_bar.open)
            candle_range = reject_bar.high - reject_bar.low

            if candle_range > 0:
                # Upper wick > 60% of candle, body < 30%
                if upper_wick / candle_range > 0.6 and body / candle_range < 0.3:
                    # FIX #2 & #4 (Oct 4, 2025): Apply filters before confirming rejection
                    current_price = reject_bar.close
                    is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
                    if is_chasing:
                        return False, f"Rejection rejected: {chasing_reason}"

                    is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
                    if is_choppy:
                        return False, f"Rejection rejected: {choppy_reason}"

                    # Check volume confirmation
                    if self.confirmation_enabled and self.volume_surge_required:
                        recent_vol = [b.volume for b in recent_bars[:-1]]
                        avg_vol = sum(recent_vol) / len(recent_vol) if recent_vol else 1

                        if reject_bar.volume >= avg_vol * self.volume_surge_multiplier:
                            return True, "Rejection confirmed: Long upper wick with volume"
                    else:
                        return True, "Rejection confirmed: Long upper wick"

            # Check for bearish engulfing after touching resistance
            if rejection_bar_idx + 1 < len(bars):
                next_bar = bars[rejection_bar_idx + 1]

                # Bearish engulfing: Next bar closes below previous low
                if next_bar.close < reject_bar.low:
                    # FIX #2 & #4 (Oct 4, 2025): Apply filters before confirming rejection
                    current_price = next_bar.close
                    is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
                    if is_chasing:
                        return False, f"Rejection rejected: {chasing_reason}"

                    is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
                    if is_choppy:
                        return False, f"Rejection rejected: {choppy_reason}"

                    return True, "Rejection confirmed: Bearish engulfing"

        # Check if price is now below resistance (rejecting)
        if current_bar.close < resistance_price * 0.995:  # 0.5% below resistance
            # FIX #2 & #4 (Oct 4, 2025): Apply filters before confirming rejection
            current_price = current_bar.close
            is_chasing, chasing_reason = self._check_entry_position(bars, current_idx, current_price, side)
            if is_chasing:
                return False, f"Rejection rejected: {chasing_reason}"

            is_choppy, choppy_reason = self._check_choppy_market(bars, current_idx)
            if is_choppy:
                return False, f"Rejection rejected: {choppy_reason}"

            return True, "Rejection confirmed: Price below resistance"

        return False, "No clear rejection pattern"
