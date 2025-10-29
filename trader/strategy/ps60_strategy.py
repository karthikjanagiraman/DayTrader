"""
PS60 Strategy - Core Trading Logic

This module contains the core PS60 trading strategy logic shared by:
- Live trader (trader.py)
- Backtester (backtest/backtester.py)

All trading decisions, entry/exit rules, and risk management are centralized here.
"""

from datetime import datetime, time as time_obj
import pytz
import logging
from typing import Dict, List, Optional
from .breakout_state_tracker import BreakoutStateTracker, BreakoutState
from .ps60_entry_state_machine import check_entry_state_machine
from .sma_calculator import SMACalculator, calculate_sma_from_bars
from .stochastic_calculator import StochasticCalculator

# Setup module logger
logger = logging.getLogger(__name__)


class PS60Strategy:
    """
    PS60 Trading Strategy Implementation

    Based on Dan Shapiro's PS60 Process:
    - Entry: Pivot breaks (scanner-identified resistance/support)
    - Exits: Partial profits, trailing stops, EOD close
    - Risk: 5-7 min rule for reload sellers, stops at pivot
    """

    def __init__(self, config, ib_connection=None, bar_size_seconds=5):
        """
        Initialize PS60 strategy with configuration

        Args:
            config: Trading configuration dict from trader_config.yaml
            ib_connection: Optional IB connection for fetching hourly bars (RSI/MACD)
            bar_size_seconds: Size of each bar in seconds (5 for live trading, 60 for 1-min backtest)
        """
        self.config = config
        self.trading_config = config['trading']
        self.filters = config['filters']
        self.ib = ib_connection  # For fetching hourly bars for momentum indicators
        self.bar_size_seconds = bar_size_seconds  # Store bar resolution (Oct 22, 2025)

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

        # Progressive Partial System (Oct 12, 2025)
        # New: 25% at each technical level (SMA + targets) instead of fixed 1R/2R
        self.use_sma_target_partials = self.trading_config['exits'].get('use_sma_target_partials', False)
        self.partial_size = self.trading_config['exits'].get('partial_size', 0.25)
        self.max_partial_levels = self.trading_config['exits'].get('max_partial_levels', 4)

        # SMA configuration
        sma_config = self.trading_config['exits'].get('sma', {})
        self.sma_enabled = sma_config.get('enabled', True)
        self.sma_periods = sma_config.get('periods', [5, 10, 20])
        self.sma_timeframe = sma_config.get('timeframe', '1 hour')
        self.sma_cache_duration = sma_config.get('cache_duration_sec', 300)

        # Scanner targets configuration
        scanner_targets_config = self.trading_config['exits'].get('scanner_targets', {})
        self.scanner_targets_enabled = scanner_targets_config.get('enabled', True)
        self.use_target1 = scanner_targets_config.get('use_target1', True)
        self.use_target2 = scanner_targets_config.get('use_target2', True)
        self.use_target3 = scanner_targets_config.get('use_target3', False)

        # Progressive stop management
        progressive_stops_config = self.trading_config['exits'].get('progressive_stops', {})
        self.progressive_stops_enabled = progressive_stops_config.get('enabled', True)
        self.move_stop_to_previous_level = progressive_stops_config.get('move_to_previous_level', True)
        self.min_stop_distance_pct = progressive_stops_config.get('min_stop_distance_pct', 0.005)

        # Fallback settings
        self.fallback_to_1r = self.trading_config['exits'].get('fallback_to_1r', True)
        self.min_levels_required = self.trading_config['exits'].get('min_levels_required', 2)

        # Initialize SMA calculator if enabled and IB connection available
        self.sma_calculator = None
        if self.use_sma_target_partials and self.sma_enabled and ib_connection:
            try:
                self.sma_calculator = SMACalculator(ib_connection, cache_duration_sec=self.sma_cache_duration)
                logger.info(f"SMA calculator initialized (timeframe: {self.sma_timeframe}, periods: {self.sma_periods})")
            except Exception as e:
                logger.warning(f"Failed to initialize SMA calculator: {e}")
                self.sma_calculator = None

        # Stochastic Oscillator Filter (Oct 15, 2025)
        # Used to confirm momentum and avoid overbought/oversold entries
        stochastic_config = config.get('stochastic', {})
        self.stochastic_enabled = stochastic_config.get('enabled', False)
        self.stochastic_k_period = stochastic_config.get('k_period', 21)
        self.stochastic_k_smooth = stochastic_config.get('k_smooth', 1)
        self.stochastic_d_smooth = stochastic_config.get('d_smooth', 3)
        self.stochastic_long_min_k = stochastic_config.get('long_min_k', 60)
        self.stochastic_long_max_k = stochastic_config.get('long_max_k', 80)
        self.stochastic_short_min_k = stochastic_config.get('short_min_k', 20)
        self.stochastic_short_max_k = stochastic_config.get('short_max_k', 50)
        self.stochastic_cache_duration = stochastic_config.get('cache_duration_sec', 3600)
        self.stochastic_allow_if_unavailable = stochastic_config.get('allow_entry_if_unavailable', True)

        # Initialize stochastic calculator if enabled and IB connection available
        self.stochastic_calculator = None
        if self.stochastic_enabled and ib_connection:
            try:
                self.stochastic_calculator = StochasticCalculator(
                    ib_connection,
                    k_period=self.stochastic_k_period,
                    k_smooth=self.stochastic_k_smooth,
                    d_smooth=self.stochastic_d_smooth,
                    cache_duration_sec=self.stochastic_cache_duration
                )
                logger.info(f"Stochastic calculator initialized ({self.stochastic_k_period}, {self.stochastic_k_smooth}, {self.stochastic_d_smooth})")
                logger.info(f"  LONG entries: %K between {self.stochastic_long_min_k}-{self.stochastic_long_max_k}")
                logger.info(f"  SHORT entries: %K between {self.stochastic_short_min_k}-{self.stochastic_short_max_k}")
            except Exception as e:
                logger.warning(f"Failed to initialize stochastic calculator: {e}")
                self.stochastic_calculator = None

        # Risk management
        self.breakeven_after_partial = self.trading_config['risk']['breakeven_after_partial']
        self.stop_at_pivot = self.trading_config['risk'].get('stop_at_pivot', False)
        self.use_atr_stops = self.trading_config['risk'].get('use_atr_stops', True)
        self.atr_stop_multiplier = self.trading_config['risk'].get('atr_stop_multiplier', 2.0)
        self.atr_stop_period = self.trading_config['risk'].get('atr_stop_period', 20)
        self.account_size = self.trading_config.get('account_size', 100000)
        self.risk_per_trade = self.trading_config.get('risk_per_trade', 0.01)

        # 7-Minute Rule (PS60) - Changed from 15 to 7 minutes (Oct 11, 2025)
        # Analysis showed 84% of losers hit 15-min rule, PS60 recommends 5-7 minutes
        self.fifteen_minute_rule_enabled = self.trading_config['risk'].get('fifteen_minute_rule_enabled', True)
        self.fifteen_minute_threshold = self.trading_config['risk'].get('fifteen_minute_threshold', 7)  # Default 7 (was 15)
        self.fifteen_minute_min_gain = self.trading_config['risk'].get('fifteen_minute_min_gain', 0.001)

        # Position sizing
        position_sizing = self.trading_config.get('position_sizing', {})
        self.max_position_pct = position_sizing.get('max_position_pct', 10.0)
        self.max_position_value = position_sizing.get('max_position_value', 20000)  # Adaptive sizing

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

        # Entry position filter (Oct 15, 2025)
        # Prevent entering too far above resistance / below support (chasing stale retests)
        self.max_entry_above_resistance = self.filters.get('max_entry_above_resistance', 0.003)  # 0.3%
        self.max_entry_below_support = self.filters.get('max_entry_below_support', 0.003)  # 0.3%

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

        # RSI/MACD Momentum Filters (Oct 7, 2025)
        self.enable_rsi_filter = confirmation_config.get('enable_rsi_filter', False)
        self.rsi_period = confirmation_config.get('rsi_period', 14)
        self.rsi_threshold = confirmation_config.get('rsi_threshold', 50)
        self.rsi_timeframe = confirmation_config.get('rsi_timeframe', '1 hour')

        self.enable_macd_filter = confirmation_config.get('enable_macd_filter', False)
        self.macd_fast = confirmation_config.get('macd_fast', 12)
        self.macd_slow = confirmation_config.get('macd_slow', 26)
        self.macd_signal = confirmation_config.get('macd_signal', 9)
        self.macd_timeframe = confirmation_config.get('macd_timeframe', '1 hour')

        # Pullback/retest thresholds (patient entry)
        # FIXES (Oct 15, 2025): Strengthened to prevent weak retests of stale breakouts
        self.require_pullback_retest = confirmation_config.get('require_pullback_retest', True)
        self.pullback_distance_pct = confirmation_config.get('pullback_distance_pct', 0.003)
        self.max_pullback_bars = confirmation_config.get('max_pullback_bars', 24)
        self.pullback_volume_threshold = confirmation_config.get('pullback_volume_threshold', 2.0)  # Raised from 1.2
        self.pullback_candle_min_pct = confirmation_config.get('pullback_candle_min_pct', 0.005)  # NEW: 0.5% min candle
        self.max_retest_time_minutes = confirmation_config.get('max_retest_time_minutes', 30)  # NEW: 30 min staleness check

        # Sustained break logic (Oct 5, 2025) - Alternative to momentum candle
        # Catches "slow grind" breakouts that hold above resistance with volume
        self.sustained_break_enabled = confirmation_config.get('sustained_break_enabled', True)
        self.sustained_break_minutes = confirmation_config.get('sustained_break_minutes', 2)
        self.sustained_break_max_pullback_pct = confirmation_config.get('sustained_break_max_pullback_pct', 0.001)

        # FIX #2 (Oct 4, 2025): Entry position filter to prevent chasing
        self.enable_entry_position_filter = confirmation_config.get('enable_entry_position_filter', False)
        self.max_entry_position_pct = confirmation_config.get('max_entry_position_pct', 70)
        # Entry position lookback: 5 minutes of bars (dynamic based on bar resolution)
        entry_position_lookback_seconds = confirmation_config.get('entry_position_lookback_seconds', 300)  # 5 minutes default
        self.entry_position_lookback_bars = entry_position_lookback_seconds // self.bar_size_seconds  # e.g., 5 bars @ 1-min or 60 bars @ 5-sec

        # FIX #4 (Oct 4, 2025): Choppy filter to avoid consolidation entries
        self.enable_choppy_filter = confirmation_config.get('enable_choppy_filter', False)
        self.choppy_atr_multiplier = confirmation_config.get('choppy_atr_multiplier', 0.5)
        # Choppy lookback: 5 minutes of bars (dynamic based on bar resolution)
        choppy_lookback_seconds = confirmation_config.get('choppy_lookback_seconds', 300)  # 5 minutes default
        self.choppy_lookback_bars = choppy_lookback_seconds // self.bar_size_seconds  # e.g., 5 bars @ 1-min or 60 bars @ 5-sec

        # ATR period for stop calculation (needed by _calculate_atr)
        self.atr_period = self.atr_stop_period

        # STATE MACHINE (Oct 9, 2025): Memory-based breakout tracking
        # Replaces lookback loops with stateful tracking of key moments
        self.state_tracker = BreakoutStateTracker()
        self.max_breakout_age_bars = confirmation_config.get('max_breakout_age_bars', 600)  # 50 minutes

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

    def get_tick_data(self, symbol, bar_timestamp=None, backtester=None):
        """
        Fetch recent tick data for CVD calculation (PHASE 5 - Oct 19, 2025)
        Updated Oct 21, 2025: Support both live and backtest modes

        This method is used by the CVD filter to get accurate buy/sell volume data.

        Live Trading Mode:
            - Fetches last 10 seconds of real-time ticks
            - Uses datetime.now() as end time

        Backtest Mode:
            - Fetches historical ticks for specific timestamp
            - Uses bar_timestamp parameter
            - Delegates to backtester's get_historical_ticks()

        Args:
            symbol: Stock ticker symbol
            bar_timestamp: (Optional) Timestamp for historical tick fetching (backtest mode)
            backtester: (Optional) Backtester instance with get_historical_ticks() method

        Returns:
            List of tick objects with 'price' and 'size' attributes, or None
        """
        # BACKTEST MODE: Use historical ticks if timestamp and backtester provided
        if bar_timestamp is not None and backtester is not None:
            # Delegate to backtester's historical tick fetcher
            if hasattr(backtester, 'get_historical_ticks'):
                return backtester.get_historical_ticks(symbol, bar_timestamp)
            else:
                return None

        # LIVE TRADING MODE: Check if IB connection is available
        if not self.ib or not self.ib.isConnected():
            return None

        # Check if CVD is enabled
        cvd_config = self.config.get('confirmation', {}).get('cvd', {})
        if not cvd_config.get('enabled', False):
            return None

        try:
            from ib_insync import Stock
            from datetime import datetime, timedelta

            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Request recent historical ticks (last 10 seconds)
            # Use TRADES to get actual executed trades
            end_time = datetime.now()
            start_time = end_time - timedelta(seconds=10)

            ticks = self.ib.reqHistoricalTicks(
                contract,
                startDateTime=start_time,
                endDateTime=end_time,
                numberOfTicks=1000,
                whatToShow='TRADES',
                useRth=True
            )

            if not ticks:
                return None

            # Convert to format CVD calculator expects (objects with .price and .size)
            from dataclasses import dataclass

            @dataclass
            class TickData:
                price: float
                size: int

            tick_list = [TickData(price=t.price, size=t.size) for t in ticks]

            return tick_list

        except Exception as e:
            # Log error but don't crash - CVD will fall back to bar approximation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to fetch tick data for {symbol}: {e}")
            return None

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
        # Look back in retest window (e.g., 5 minutes = 5 bars @ 1-min or 60 bars @ 5-sec)
        window_bars = self.retest_window_minutes * (60 // self.bar_size_seconds)  # Dynamic based on bar resolution
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
        bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds  # Dynamic based on bar resolution

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

        # Calculate how many bars = sustained_break_minutes (dynamic based on bar resolution)
        bars_required = (self.sustained_break_minutes * 60) // self.bar_size_seconds  # e.g., 2 min = 2 bars @ 1-min or 24 bars @ 5-sec

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
        min_history_bars = (600 // self.bar_size_seconds)  # 10 minutes of history (dynamic)
        if breakout_bar >= min_history_bars:  # Need 10 min history
            pre_break_bars = bars[breakout_bar-min_history_bars:breakout_bar]
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

    def check_momentum_indicators(self, symbol, side='LONG', cached_hourly_bars=None):
        """
        Check RSI and MACD momentum indicators (Oct 7, 2025)

        Uses hourly bars from IBKR to validate trend direction and momentum.
        This filters out false breakouts and counter-trend entries.

        Args:
            symbol: Stock symbol (e.g., 'XPEV')
            side: 'LONG' or 'SHORT'
            cached_hourly_bars: Pre-fetched hourly bars (performance optimization for backtesting)

        Returns:
            tuple: (is_confirmed, reason, details)
        """
        # Skip if indicators disabled or no IB connection
        if not self.enable_rsi_filter and not self.enable_macd_filter:
            return True, "Momentum indicators disabled", {}

        if self.ib is None and cached_hourly_bars is None:
            return True, "No IB connection for momentum check", {}

        try:
            # Import momentum indicators module
            from strategy.momentum_indicators import check_momentum_confirmation_with_bars
            from ib_insync import Stock

            # If cached bars provided, use them directly (backtesting optimization)
            if cached_hourly_bars is not None:
                is_confirmed, reason, details = check_momentum_confirmation_with_bars(
                    bars=cached_hourly_bars,
                    side=side,
                    rsi_enabled=self.enable_rsi_filter,
                    rsi_period=self.rsi_period,
                    rsi_threshold=self.rsi_threshold,
                    macd_enabled=self.enable_macd_filter,
                    macd_fast=self.macd_fast,
                    macd_slow=self.macd_slow,
                    macd_signal=self.macd_signal
                )
            else:
                # Live trading: fetch bars from IBKR
                from strategy.momentum_indicators import check_momentum_confirmation

                contract = Stock(symbol, 'SMART', 'USD')
                is_confirmed, reason, details = check_momentum_confirmation(
                    ib=self.ib,
                    contract=contract,
                    side=side,
                    rsi_enabled=self.enable_rsi_filter,
                    rsi_period=self.rsi_period,
                    rsi_threshold=self.rsi_threshold,
                    rsi_timeframe=self.rsi_timeframe,
                    macd_enabled=self.enable_macd_filter,
                    macd_fast=self.macd_fast,
                    macd_slow=self.macd_slow,
                    macd_signal=self.macd_signal,
                    macd_timeframe=self.macd_timeframe
                )

            return is_confirmed, reason, details

        except Exception as e:
            print(f"⚠️  Error checking momentum for {symbol}: {e}")
            return True, f"Momentum check error: {e}", {}

    def check_hybrid_entry(self, bars, current_idx, pivot_price, side='LONG', target_price=None, symbol=None, cached_hourly_bars=None, absolute_idx=None, bar_buffer=None, backtester=None):
        """
        HYBRID Entry Strategy (Oct 4, 2025) - STATE MACHINE VERSION (Oct 9, 2025)

        Two entry types based on breakout strength:
        1. MOMENTUM BREAKOUT: Strong volume + large candle = immediate entry
        2. PULLBACK/RETEST: Weak initial break = wait for pullback

        STATE MACHINE APPROACH:
        - Stores key moments in memory (no lookback loops)
        - Tracks progression through decision tree
        - Remembers breakout for up to 50 minutes (configurable)

        Strategy:
        - Always require 1-min candle close above pivot (filters whipsaws)
        - If breakout candle has strong volume AND large size → MOMENTUM entry
        - If breakout candle is weak → wait for PULLBACK/RETEST OR SUSTAINED_BREAK

        Args:
            bars: List of bars (resolution determined by bar_size_seconds: 5-sec for live, 60-sec for backtest)
            current_idx: Current bar ARRAY index (for bars[] access)
            pivot_price: Resistance (long) or support (short)
            side: 'LONG' or 'SHORT'
            target_price: Target price (optional, for room-to-run filter)
            symbol: Stock symbol (REQUIRED for state tracking)
            cached_hourly_bars: Hourly bars for RSI/MACD (optional)
            absolute_idx: Absolute bar count (for state machine tracking)
            bar_buffer: BarBuffer instance (for candle mapping, PART 3 fix)
            backtester: (Optional) Backtester instance for historical tick fetching (Oct 21, 2025)

        Returns:
            tuple: (should_enter, reason, entry_state)
        """
        # USE STATE MACHINE (Oct 9, 2025)
        if symbol is not None:
            # CRITICAL FIX PART 2 (Oct 20, 2025): Pass absolute_idx to state machine
            # State machine uses absolute_idx for tracking bar numbers over time
            # current_idx is used for bars[] access
            # CRITICAL FIX PART 3 (Oct 20, 2025): Pass bar_buffer for candle mapping
            # Updated Oct 21, 2025: Pass backtester for tick-based CVD
            return check_entry_state_machine(
                strategy=self,
                symbol=symbol,
                bars=bars,
                current_idx=current_idx,
                pivot_price=pivot_price,
                side=side,
                target_price=target_price,
                cached_hourly_bars=cached_hourly_bars,
                absolute_idx=absolute_idx,
                bar_buffer=bar_buffer,
                backtester=backtester
            )

        # FALLBACK: Old logic if symbol not provided (shouldn't happen)
        if not self.require_candle_close:
            # Candle close disabled, allow immediate entry
            current_price = bars[current_idx].close
            if side == 'LONG':
                return (current_price > pivot_price), "Immediate entry (no symbol)", None
            else:
                return (current_price < pivot_price), "Immediate entry (no symbol)", None

        bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds  # Dynamic based on bar resolution

        # FIX (Oct 9, 2025): Don't search for original breakout - just check current price vs pivot
        # Old logic searched last 36 bars for initial breakout, failed 93% of the time
        # New logic: If price is currently through pivot, treat current candle as the breakout candle

        current_price = bars[current_idx].close

        # Check if price is currently through pivot
        if side == 'LONG':
            is_through_pivot = current_price > pivot_price
        else:  # SHORT
            is_through_pivot = current_price < pivot_price

        if not is_through_pivot:
            return False, "Price not through pivot", {'phase': 'no_breakout'}

        # STEP 1: Check if we're at the end of a 1-minute candle
        # Only enter at candle boundaries (every 12th bar)
        bars_into_candle = current_idx % bars_per_candle

        if bars_into_candle < (bars_per_candle - 1):
            # Not at candle close yet, wait
            candle_start = (current_idx // bars_per_candle) * bars_per_candle
            candle_end = candle_start + bars_per_candle
            return False, "Waiting for 1-min candle close", {
                'phase': 'waiting_candle_close',
                'breakout_bar': candle_start,
                'candle_closes_at': candle_end
            }

        # We're at the last bar of the candle (bar 11, 23, 35, etc.)
        # Check if this candle closed through the pivot
        candle_start = (current_idx // bars_per_candle) * bars_per_candle
        candle_close_price = current_price  # Current bar is the candle close

        if side == 'LONG' and candle_close_price <= pivot_price:
            return False, "1-min candle closed below resistance (failed)", {'phase': 'failed_close'}
        elif side == 'SHORT' and candle_close_price >= pivot_price:
            return False, "1-min candle closed above support (failed)", {'phase': 'failed_close'}

        # Candle closed correctly through pivot - proceed to volume/momentum checks
        candle_end = current_idx + 1  # For volume calculations
        breakout_bar = candle_start  # For tracking purposes

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
        # Updated Oct 7, 2025: Volume + RSI/MACD filters (candle size disabled)
        is_strong_volume = volume_ratio >= self.momentum_volume_threshold

        # Check if candle filters are disabled (set to 0)
        if self.momentum_candle_min_pct == 0 and self.momentum_candle_min_atr == 0:
            is_large_candle = True  # Disabled, always pass
        else:
            is_large_candle = (candle_size_pct >= self.momentum_candle_min_pct and
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

            # NEW (Oct 7, 2025): Check RSI/MACD momentum indicators
            if symbol and (self.enable_rsi_filter or self.enable_macd_filter):
                momentum_confirmed, momentum_reason, momentum_details = self.check_momentum_indicators(symbol, side, cached_hourly_bars)
                if not momentum_confirmed:
                    return False, f"Momentum filter: {momentum_reason}", {'phase': 'momentum_filter'}

            # CRITICAL FIX (Oct 14, 2025): Check room-to-run filter for MOMENTUM_BREAKOUT path
            # This was missing and allowed C SHORT (0.30% room) to enter
            blocked, room_reason = self._check_room_to_run(current_price, target_price, side)
            if blocked:
                if hasattr(self, 'logger'):
                    self.logger.info(f"[MOMENTUM_BREAKOUT] BLOCKED by room-to-run: {room_reason}")
                return False, room_reason, {'phase': 'room_to_run_filter'}

            # NEW (Oct 14, 2025): Directional Volume Filter
            # Check if volume spike confirms movement in the intended trade direction
            # Prevents entering on pullbacks/bounces with volume in opposite direction
            wrong_direction, direction_reason = self._check_directional_volume(bars, current_idx, side)
            if wrong_direction:
                if hasattr(self, 'logger'):
                    self.logger.info(f"[MOMENTUM_BREAKOUT] BLOCKED by directional volume: {direction_reason}")
                return False, direction_reason, {'phase': 'directional_volume_filter'}

            # All filters passed - MOMENTUM_BREAKOUT confirmed!
            if hasattr(self, 'logger'):
                self.logger.info(f"[MOMENTUM_BREAKOUT] Entry confirmed at ${current_price:.2f} (target=${target_price:.2f})")
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
                    if hasattr(self, 'logger'):
                        self.logger.info(f"[PULLBACK/RETEST] BLOCKED by room-to-run: {room_reason}")
                    return False, room_reason, {'phase': 'room_to_run_filter'}

                # NEW (Oct 14, 2025): Directional Volume Filter
                # Apply to PULLBACK/RETEST path for consistency
                wrong_direction, direction_reason = self._check_directional_volume(bars, current_idx, side)
                if wrong_direction:
                    if hasattr(self, 'logger'):
                        self.logger.info(f"[PULLBACK/RETEST] BLOCKED by directional volume: {direction_reason}")
                    return False, direction_reason, {'phase': 'directional_volume_filter'}

                # All filters passed - PULLBACK/RETEST confirmed!
                if hasattr(self, 'logger'):
                    self.logger.info(f"[PULLBACK/RETEST] Entry confirmed at ${current_price:.2f} (target=${target_price:.2f})")
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
                        if hasattr(self, 'logger'):
                            self.logger.info(f"[SUSTAINED_BREAK] BLOCKED by room-to-run: {room_reason}")
                        return False, room_reason, {'phase': 'room_to_run_filter'}

                    # NEW (Oct 14, 2025): Directional Volume Filter
                    # Apply to SUSTAINED_BREAK path for consistency
                    wrong_direction, direction_reason = self._check_directional_volume(bars, current_idx, side)
                    if wrong_direction:
                        if hasattr(self, 'logger'):
                            self.logger.info(f"[SUSTAINED_BREAK] BLOCKED by directional volume: {direction_reason}")
                        return False, direction_reason, {'phase': 'directional_volume_filter'}

                    if hasattr(self, 'logger'):
                        self.logger.info(f"[SUSTAINED_BREAK] Entry confirmed at ${current_price:.2f} (target=${target_price:.2f})")
                    # All filters passed - SUSTAINED_BREAK confirmed!
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

    def _check_directional_volume(self, bars, current_idx, side='LONG'):
        """
        Directional Volume Filter (Oct 14, 2025)

        Check if volume spike confirms movement in the intended trade direction.
        Prevents entering on pullbacks/bounces with volume in opposite direction.

        The Problem (GS Trade Example):
        - GS dropped from $758 to $742, then BOUNCED UP to $744
        - High volume (2.0x) on the UPWARD bounce
        - System entered SHORT into this upward bounce with volume
        - This is a "dead cat bounce" entry - worst possible timing

        The Fix:
        - For SHORT: Require RED candle (close < open) = selling pressure
        - For LONG: Require GREEN candle (close > open) = buying pressure

        Args:
            bars: List of price bars
            current_idx: Current bar index
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (blocked, reason)
                - blocked: True if volume confirms wrong direction
                - reason: Explanation string

        Example:
            SHORT entry with GREEN candle → BLOCKED (volume confirms buying)
            SHORT entry with RED candle → ALLOWED (volume confirms selling)
        """
        # Calculate 1-minute candle direction (12 five-second bars = 1 minute)
        bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds  # Dynamic based on bar resolution
        candle_start = (current_idx // bars_per_candle) * bars_per_candle
        candle_end = min(candle_start + bars_per_candle - 1, len(bars) - 1)

        candle_open = bars[candle_start].open
        candle_close = bars[candle_end].close
        candle_direction = candle_close - candle_open

        if side == 'LONG':
            # For LONG: Volume should confirm UPWARD movement (green candle)
            if candle_direction < 0:
                # Red candle with high volume = selling pressure, not buying
                return True, "Volume confirms DOWNWARD move (red candle), not LONG entry"
        else:  # SHORT
            # For SHORT: Volume should confirm DOWNWARD movement (red candle)
            if candle_direction > 0:
                # Green candle with high volume = buying pressure, not selling
                # This is what happened with GS - volume spike on UPWARD bounce
                return True, "Volume confirms UPWARD move (green candle), not SHORT entry"

        # Volume confirms intended direction
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
        # CRITICAL DEBUG (Oct 14, 2025): Log all filter checks
        # Helps diagnose why WFC LONG (0.68% room) wasn't blocked

        if not self.enable_room_to_run_filter:
            if hasattr(self, 'logger'):
                self.logger.debug(f"  [Room-to-Run] DISABLED - skipping check")
            return False, None

        if target_price is None:
            if hasattr(self, 'logger'):
                self.logger.debug(f"  [Room-to-Run] No target_price provided - skipping check")
            return False, None  # Can't check without target

        if side == 'LONG':
            room_pct = ((target_price - current_price) / current_price) * 100
        else:  # SHORT
            room_pct = ((current_price - target_price) / current_price) * 100

        if hasattr(self, 'logger'):
            self.logger.debug(f"  [Room-to-Run] {side}: entry=${current_price:.2f}, target=${target_price:.2f}, room={room_pct:.2f}%, threshold={self.min_room_to_target_pct:.1f}%")

        if room_pct < self.min_room_to_target_pct:
            if hasattr(self, 'logger'):
                self.logger.info(f"  [Room-to-Run] BLOCKED: {room_pct:.2f}% < {self.min_room_to_target_pct:.1f}% minimum")
            return True, f"Insufficient room to target: {room_pct:.2f}% < {self.min_room_to_target_pct:.1f}% minimum"

        if hasattr(self, 'logger'):
            self.logger.debug(f"  [Room-to-Run] PASSED: {room_pct:.2f}% >= {self.min_room_to_target_pct:.1f}% minimum")
        return False, None

    def _check_stochastic_filter(self, symbol, side='LONG'):
        """
        Stochastic Oscillator Filter (Oct 15, 2025)

        Confirms momentum and avoids overbought/oversold entries using hourly stochastic.

        User Requirements:
        - LONG entries: %K must be between 60-80 (momentum zone, not overbought)
        - SHORT entries: %K must be between 20-50 (momentum zone, not oversold)

        Applied to ALL entry paths (momentum, pullback, sustained).

        Args:
            symbol: Stock symbol
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (fails_filter, reason)
                - fails_filter: True if stochastic blocks entry
                - reason: Explanation string
        """
        if not self.stochastic_enabled:
            return False, None

        if not self.stochastic_calculator:
            # Stochastic calculator not initialized
            if self.stochastic_allow_if_unavailable:
                return False, None  # Allow entry if unavailable
            else:
                return True, "Stochastic calculator not available"

        # Get stochastic values
        stoch = self.stochastic_calculator.get_stochastic(symbol)

        if stoch is None:
            # Failed to calculate stochastic
            if self.stochastic_allow_if_unavailable:
                return False, None  # Allow entry if unavailable
            else:
                return True, f"Failed to calculate stochastic for {symbol}"

        k = stoch['%K']
        d = stoch['%D']

        # Check requirements based on direction
        if side == 'LONG':
            # LONG requirement: %K between 60-80
            if k < self.stochastic_long_min_k:
                return True, f"Stochastic too low for LONG (K={k:.1f}, need {self.stochastic_long_min_k}-{self.stochastic_long_max_k})"
            elif k > self.stochastic_long_max_k:
                return True, f"Stochastic overbought for LONG (K={k:.1f}, need {self.stochastic_long_min_k}-{self.stochastic_long_max_k})"
            else:
                return False, f"Stochastic confirmed (K={k:.1f}, D={d:.1f})"

        elif side == 'SHORT':
            # SHORT requirement: %K between 20-50
            if k < self.stochastic_short_min_k:
                return True, f"Stochastic oversold for SHORT (K={k:.1f}, need {self.stochastic_short_min_k}-{self.stochastic_short_max_k})"
            elif k > self.stochastic_short_max_k:
                return True, f"Stochastic too high for SHORT (K={k:.1f}, need {self.stochastic_short_min_k}-{self.stochastic_short_max_k})"
            else:
                return False, f"Stochastic confirmed (K={k:.1f}, D={d:.1f})"

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

    def should_enter_long(self, stock_data, current_price, attempt_count=0, bars=None, current_idx=None, absolute_idx=None, bar_buffer=None):
        """
        Check if should enter long position

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            attempt_count: Number of previous attempts on this pivot
            bars: Optional - List of bars for hybrid entry confirmation (live trader)
            current_idx: Optional - Current bar ARRAY index (for accessing bars[])
            absolute_idx: Optional - Absolute bar count (for state machine tracking)
            bar_buffer: Optional - BarBuffer instance (for candle mapping, live trader PART 3)

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

        # Check position size with adaptive sizing (Oct 7, 2025)
        stop_distance = abs(current_price - resistance)

        # Calculate using adaptive sizing formula
        shares_by_risk = self.account_size * self.risk_per_trade / stop_distance if stop_distance > 0 else 0
        shares_by_value = self.max_position_value / current_price
        shares = min(shares_by_risk, shares_by_value, 1000)  # Apply adaptive limit

        position_value = shares * current_price
        position_pct = (position_value / self.account_size) * 100

        # Position value should never exceed max_position_value due to adaptive sizing
        # This check is now redundant but kept for backwards compatibility
        if position_value > self.max_position_value * 1.1:  # 10% buffer for rounding
            return False, f"Position too large (${position_value:,.0f} > ${self.max_position_value:,.0f} max)"

        # NOTE: Gap filter is NOT checked here - it's applied at market open
        # by filter_scanner_for_gaps() in the backtester/live trader before
        # the stock is even added to the watchlist. Checking it here with
        # current_price would incorrectly use intraday price movement instead
        # of the actual overnight gap.

        # CRITICAL: If bars provided (live trader), check hybrid entry confirmation
        if bars is not None and current_idx is not None:
            # PHASE 7 (Oct 13, 2025): Dynamic target selection - use highest available target
            highest_target = stock_data.get('target3') or stock_data.get('target2') or stock_data.get('target1')

            # CRITICAL FIX PART 2 (Oct 20, 2025): Pass both indices
            # current_idx = array index (for bars[] access)
            # absolute_idx = absolute bar count (for state machine)
            # CRITICAL FIX PART 3 (Oct 20, 2025): Pass bar_buffer for candle mapping
            confirmed, path, reason = self.check_hybrid_entry(
                bars, current_idx, resistance, side='LONG', target_price=highest_target,
                symbol=stock_data.get('symbol'), absolute_idx=absolute_idx, bar_buffer=bar_buffer
            )

            if not confirmed:
                return False, reason

            return True, f"LONG confirmed via {path}"

        # Backtest path: Pivot broken (hybrid entry checked in backtester loop)
        return True, "Resistance broken"

    def should_enter_short(self, stock_data, current_price, attempt_count=0, bars=None, current_idx=None, absolute_idx=None, bar_buffer=None):
        """
        Check if should enter short position

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            attempt_count: Number of previous attempts on this pivot
            bars: Optional - List of bars for hybrid entry confirmation (live trader)
            current_idx: Optional - Current bar ARRAY index (for accessing bars[])
            absolute_idx: Optional - Absolute bar count (for state machine tracking)
            bar_buffer: Optional - BarBuffer instance (for candle mapping, live trader PART 3)

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

        # Check position size with adaptive sizing (Oct 7, 2025)
        stop_distance = abs(current_price - support)

        # Calculate using adaptive sizing formula
        shares_by_risk = self.account_size * self.risk_per_trade / stop_distance if stop_distance > 0 else 0
        shares_by_value = self.max_position_value / current_price
        shares = min(shares_by_risk, shares_by_value, 1000)  # Apply adaptive limit

        position_value = shares * current_price
        position_pct = (position_value / self.account_size) * 100

        # Position value should never exceed max_position_value due to adaptive sizing
        # This check is now redundant but kept for backwards compatibility
        if position_value > self.max_position_value * 1.1:  # 10% buffer for rounding
            return False, f"Position too large (${position_value:,.0f} > ${self.max_position_value:,.0f} max)"

        # CRITICAL: If bars provided (live trader), check hybrid entry confirmation
        if bars is not None and current_idx is not None:
            # PHASE 7 (Oct 13, 2025): Dynamic target selection - use lowest available downside target
            lowest_downside = stock_data.get('downside2') or stock_data.get('downside1')

            # CRITICAL FIX PART 2 (Oct 20, 2025): Pass both indices
            # current_idx = array index (for bars[] access)
            # absolute_idx = absolute bar count (for state machine)
            # CRITICAL FIX PART 3 (Oct 20, 2025): Pass bar_buffer for candle mapping
            confirmed, path, reason = self.check_hybrid_entry(
                bars, current_idx, support, side='SHORT', target_price=lowest_downside,
                symbol=stock_data.get('symbol'), absolute_idx=absolute_idx, bar_buffer=bar_buffer
            )

            if not confirmed:
                return False, reason

            return True, f"SHORT confirmed via {path}"

        # Backtest path: Pivot broken (hybrid entry checked in backtester loop)
        return True, "Support broken"

    def should_take_partial(self, position, current_price, bars=None):
        """
        Check if should take partial profit.

        Two systems available:
        1. NEW (Progressive): 25% at each SMA/target level
        2. LEGACY (Fallback): 50%-25% at 1R/2R

        Args:
            position: Position dict with entry, stop, side, etc.
            current_price: Current market price
            bars: Historical bars for SMA calculation (optional, for backtesting)

        Returns:
            (bool, pct, reason) - Should take partial, what %, and reason

        Example (Progressive System):
            >>> position = {
            >>>     'entry_price': 100.00,
            >>>     'exit_levels': [
            >>>         {'price': 101.20, 'name': 'SMA5'},
            >>>         {'price': 102.50, 'name': 'SMA10'},
            >>>         {'price': 103.80, 'name': 'TARGET1'},
            >>>         {'price': 105.00, 'name': 'SMA20'}
            >>>     ],
            >>>     'partials': [],  # None taken yet
            >>>     'side': 'LONG'
            >>> }
            >>> should_take, pct, reason = strategy.should_take_partial(position, 101.25)
            >>> print(f"{should_take}: Take {pct*100}% at {reason}")
            True: Take 25.0% at 25%_PARTIAL_SMA5
        """
        # Check if progressive system is enabled
        if self.use_sma_target_partials:
            return self._progressive_partial_logic(position, current_price, bars)
        else:
            return self._legacy_partial_logic(position, current_price)

    def _progressive_partial_logic(self, position, current_price, bars=None):
        """
        Progressive 25% partials at SMA/target levels.

        Logic:
        1. Create exit levels on first call (cached in position)
        2. Check if price reached next level
        3. Take 25% partial at each level
        4. Update stop to previous level after each partial

        Args:
            position: Position dict
            current_price: Current market price
            bars: Historical bars for SMA calculation (optional)

        Returns:
            (bool, pct, reason) - Whether to take partial

        Implementation Notes:
            - Exit levels are calculated once and cached in position['exit_levels']
            - Takes partials sequentially: level 0, then level 1, etc.
            - Falls back to 1R system if insufficient levels found
        """
        # Get or create exit levels
        if 'exit_levels' not in position:
            position['exit_levels'] = self._create_exit_levels(position, bars)
            # Format exit levels for logging
            levels_str = ', '.join([f"{l['name']}@${l['price']:.2f}" for l in position['exit_levels']])
            logger.info(
                f"{position['symbol']}: Created {len(position['exit_levels'])} exit levels: {levels_str}"
            )

        exit_levels = position['exit_levels']
        partials_taken = len(position.get('partials', []))

        # Check if we've exhausted all levels
        if partials_taken >= len(exit_levels):
            return False, 0, None

        # Get next level to hit
        next_level = exit_levels[partials_taken]

        # Check if price reached this level
        if self._price_reached_level(current_price, next_level, position['side']):
            logger.debug(
                f"{position['symbol']}: Hit level {partials_taken + 1}/{len(exit_levels)}: "
                f"{next_level['name']} @ ${next_level['price']:.2f}"
            )
            return True, self.partial_size, f"25%_PARTIAL_{next_level['name']}"

        return False, 0, None

    def _legacy_partial_logic(self, position, current_price):
        """
        Legacy 1R/2R partial system (50%-25%-25% runner).

        This is the original system used before progressive partials.
        Kept as fallback and for comparison testing.

        Args:
            position: Position dict
            current_price: Current market price

        Returns:
            (bool, pct, reason)

        Logic:
            - First partial: 50% at 1R (profit = risk)
            - Second partial: 25% at 2R/target1
            - Final 25%: Runner with trailing stop
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

    # ========================================================================
    # PROGRESSIVE PARTIAL SYSTEM - Helper Methods
    # ========================================================================

    def _create_exit_levels(self, position, bars=None) -> List[Dict]:
        """
        Create ordered list of exit levels from SMA + scanner targets.

        This is the core of the progressive partial system. It:
        1. Fetches SMA levels (hourly/daily)
        2. Adds scanner targets
        3. Filters by direction (LONG = levels above entry)
        4. Sorts by distance from entry
        5. Limits to max levels (default: 4)
        6. Falls back to 1R if insufficient levels

        Args:
            position: Position dict with symbol, entry, side, targets
            bars: Historical bars for SMA calculation (optional, for backtesting)

        Returns:
            List of level dicts: [
                {'price': 101.20, 'type': 'SMA', 'name': 'SMA5'},
                {'price': 102.50, 'type': 'SMA', 'name': 'SMA10'},
                ...
            ]

        Edge Cases:
            - Returns 1R/2R levels if insufficient technical levels found
            - Returns empty list if even 1R can't be calculated
            - Logs warnings for missing data
        """
        levels = []
        entry_price = position['entry_price']
        side = position['side']
        symbol = position.get('symbol', 'UNKNOWN')

        # ===== STEP 1: Get SMA Levels (Priority 1) =====
        if self.sma_enabled:
            sma_levels = self._get_sma_levels_for_position(position, bars)

            if sma_levels:
                for name, price in sma_levels.items():
                    if self._is_level_valid(price, entry_price, side):
                        levels.append({
                            'price': price,
                            'type': 'SMA',
                            'name': name.upper()  # 'sma5' -> 'SMA5'
                        })
                        logger.debug(f"{symbol}: Added {name.upper()} @ ${price:.2f}")
            else:
                logger.warning(f"{symbol}: No SMA levels available")

        # ===== STEP 2: Add Scanner Targets (Priority 2) =====
        if self.scanner_targets_enabled:
            target_mapping = {
                'target1': self.use_target1,
                'target2': self.use_target2,
                'target3': self.use_target3
            }

            for target_key, enabled in target_mapping.items():
                if not enabled:
                    continue

                if target_key in position:
                    target_price = position[target_key]
                    if self._is_level_valid(target_price, entry_price, side):
                        levels.append({
                            'price': target_price,
                            'type': 'TARGET',
                            'name': target_key.upper()  # 'target1' -> 'TARGET1'
                        })
                        logger.debug(f"{symbol}: Added {target_key.upper()} @ ${target_price:.2f}")

        # ===== STEP 3: Sort by Distance from Entry =====
        levels.sort(key=lambda x: abs(x['price'] - entry_price))

        # ===== STEP 4: Limit to Max Levels =====
        levels = levels[:self.max_partial_levels]

        # ===== STEP 5: Fallback to 1R if Insufficient Levels =====
        if len(levels) < self.min_levels_required and self.fallback_to_1r:
            logger.warning(
                f"{symbol}: Only {len(levels)} exit levels found (need {self.min_levels_required}), "
                f"falling back to 1R/2R system"
            )
            return self._create_1r_levels(position)

        if not levels:
            logger.error(f"{symbol}: No exit levels created!")
            return []

        return levels

    def _get_sma_levels_for_position(self, position, bars=None) -> Optional[Dict[str, float]]:
        """
        Get SMA levels for position (live trading or backtesting).

        Two modes:
        1. Live trading: Fetch from IBKR via SMA calculator
        2. Backtesting: Calculate from provided bars

        Args:
            position: Position dict with symbol
            bars: Historical bars (for backtesting mode)

        Returns:
            Dict of SMA levels: {'sma5': 150.45, 'sma10': 148.92, 'sma20': 147.33}
            Returns None if calculation fails
        """
        symbol = position.get('symbol', 'UNKNOWN')

        # Mode 1: Backtesting - calculate from bars
        if bars is not None:
            logger.debug(f"{symbol}: Calculating SMAs from {len(bars)} bars")
            sma_levels = {}

            for period in self.sma_periods:
                sma_value = calculate_sma_from_bars(bars, period)
                if sma_value:
                    sma_levels[f'sma{period}'] = sma_value

            return sma_levels if sma_levels else None

        # Mode 2: Live trading - fetch from IBKR
        if self.sma_calculator:
            try:
                return self.sma_calculator.get_sma_levels(
                    symbol,
                    periods=self.sma_periods,
                    timeframe=self.sma_timeframe
                )
            except Exception as e:
                logger.warning(f"{symbol}: Failed to fetch SMAs: {e}")
                return None

        logger.warning(f"{symbol}: No SMA calculator available and no bars provided")
        return None

    def _is_level_valid(self, level_price: float, entry_price: float, side: str) -> bool:
        """
        Check if exit level is in the right direction.

        Args:
            level_price: Exit level price
            entry_price: Entry price
            side: 'LONG' or 'SHORT'

        Returns:
            True if level is valid (above entry for LONG, below for SHORT)

        Examples:
            >>> _is_level_valid(102.0, 100.0, 'LONG')
            True  # 102 > 100 for LONG ✓

            >>> _is_level_valid(98.0, 100.0, 'LONG')
            False  # 98 < 100 for LONG ✗

            >>> _is_level_valid(98.0, 100.0, 'SHORT')
            True  # 98 < 100 for SHORT ✓
        """
        if side == 'LONG':
            return level_price > entry_price
        else:  # SHORT
            return level_price < entry_price

    def _price_reached_level(self, current_price: float, level: Dict, side: str) -> bool:
        """
        Check if price has reached exit level.

        Args:
            current_price: Current market price
            level: Level dict with 'price'
            side: 'LONG' or 'SHORT'

        Returns:
            True if price reached or exceeded level

        Logic:
            - LONG: current >= level (moving up)
            - SHORT: current <= level (moving down)
        """
        level_price = level['price']

        if side == 'LONG':
            return current_price >= level_price
        else:  # SHORT
            return current_price <= level_price

    def _create_1r_levels(self, position) -> List[Dict]:
        """
        Create fallback 1R/2R exit levels.

        Used when insufficient SMA/target levels are found.

        Args:
            position: Position dict

        Returns:
            List with 1R and 2R levels: [
                {'price': <entry+1R>, 'type': '1R', 'name': '1R'},
                {'price': <entry+2R>, 'type': '2R', 'name': '2R'}
            ]

        Note:
            Partial sizes are different for 1R system:
            - 1R: 50% (not 25%)
            - 2R: 25%
            - Runner: 25%
        """
        entry_price = position['entry_price']
        stop_price = position['stop']
        side = position['side']

        # Calculate 1R (initial risk)
        if side == 'LONG':
            risk = entry_price - stop_price
            level_1r = entry_price + risk  # 1:1 profit/risk
            level_2r = entry_price + (risk * 2)  # 2:1 profit/risk
        else:  # SHORT
            risk = stop_price - entry_price
            level_1r = entry_price - risk
            level_2r = entry_price - (risk * 2)

        levels = [
            {'price': level_1r, 'type': '1R', 'name': '1R'},
            {'price': level_2r, 'type': '2R', 'name': '2R'}
        ]

        logger.info(
            f"{position.get('symbol', 'UNKNOWN')}: Using 1R/2R levels: "
            f"1R@${level_1r:.2f}, 2R@${level_2r:.2f}"
        )

        return levels

    def update_stop_after_partial(self, position, current_price):
        """
        Update stop price after taking partial (progressive system).

        Two modes:
        1. Progressive: Move stop to previous exit level
        2. Legacy: Move to breakeven after first partial

        Args:
            position: Position dict
            current_price: Current market price

        Returns:
            New stop price

        Example (Progressive):
            Partials taken: 2 (at SMA5, SMA10)
            Exit levels: [SMA5@101.20, SMA10@102.50, TARGET1@103.80]
            New stop: SMA5 - 0.5% = $100.69

        Example (Legacy):
            Partials taken: 1
            New stop: Entry price (breakeven)
        """
        if not self.use_sma_target_partials or not self.progressive_stops_enabled:
            # Legacy mode: breakeven after first partial
            if position.get('partials'):
                return position['entry_price']
            return position['stop']

        # Progressive mode: move to previous level
        return self._progressive_stop_update(position)

    def _progressive_stop_update(self, position):
        """
        Progressive stop management: move stop to previous exit level.

        Logic:
            - After 1st partial: Move to breakeven
            - After 2nd partial: Move to 1st level (with buffer)
            - After 3rd partial: Move to 2nd level (with buffer)
            - After 4th partial: Keep at 3rd level, let trail work

        Args:
            position: Position dict

        Returns:
            New stop price
        """
        partials_taken = len(position.get('partials', []))
        current_stop = position['stop']
        entry_price = position['entry_price']
        side = position['side']

        if partials_taken == 0:
            # No partials yet, keep initial stop
            return current_stop

        elif partials_taken == 1:
            # First partial: Move to breakeven
            logger.debug(f"{position.get('symbol')}: Moving stop to breakeven @ ${entry_price:.2f}")
            return entry_price

        elif partials_taken >= 2:
            # Subsequent partials: Move to previous level with buffer
            exit_levels = position.get('exit_levels', [])
            previous_level_idx = partials_taken - 2  # 2nd partial -> 0th level

            if previous_level_idx < len(exit_levels):
                previous_level = exit_levels[previous_level_idx]
                new_stop = previous_level['price']

                # Add buffer to avoid immediate stop-out
                if side == 'LONG':
                    # Stop below level
                    new_stop = new_stop * (1 - self.min_stop_distance_pct)
                else:  # SHORT
                    # Stop above level
                    new_stop = new_stop * (1 + self.min_stop_distance_pct)

                logger.info(
                    f"{position.get('symbol')}: Moving stop to {previous_level['name']} "
                    f"(${previous_level['price']:.2f}) with {self.min_stop_distance_pct*100:.1f}% buffer "
                    f"= ${new_stop:.2f}"
                )

                return new_stop

        # Fallback: keep current stop
        return current_stop

    # ========================================================================
    # END: PROGRESSIVE PARTIAL SYSTEM
    # ========================================================================

    def check_fifteen_minute_rule(self, position, current_price, current_time):
        """
        Check if 7-minute rule should trigger (PS60 methodology)

        Changed from 15 to 7 minutes (Oct 11, 2025) based on analysis showing:
        - 84% of losers hit 15-min rule
        - Only 1 out of 18 (5.6%) was profitable
        - PS60 recommends 5-7 minutes, not 15

        Exit if position shows no progress after N minutes (configurable) - indicates
        "reload seller/buyer" blocking the move.

        Args:
            position: Position dict with entry_time, entry_price, remaining, etc.
            current_price: Current market price
            current_time: Current datetime

        Returns:
            (should_exit, reason) tuple
        """
        if not self.fifteen_minute_rule_enabled:
            return False, None

        # CRITICAL: Only apply BEFORE taking partials
        # After partials, let the runner work (remaining < 1.0 means partial taken)
        if position.get('remaining', 1.0) < 1.0:
            return False, None

        # Calculate time in trade
        entry_time = position['entry_time']
        time_in_trade = (current_time - entry_time).total_seconds() / 60  # minutes

        if time_in_trade < self.fifteen_minute_threshold:
            return False, None

        # Check if position has made progress
        entry_price = position['entry_price']
        side = position['side']

        if side == 'LONG':
            gain_pct = (current_price - entry_price) / entry_price
        else:  # SHORT
            gain_pct = (entry_price - current_price) / entry_price

        # If no meaningful progress, exit
        if gain_pct < self.fifteen_minute_min_gain:
            # Use actual threshold in message (was hardcoded "15MIN_RULE")
            return True, f"{self.fifteen_minute_threshold}MIN_RULE: No progress (${gain_pct*entry_price:+.2f}, {gain_pct*100:.2f}%)"

        return False, None

    def check_target_hit_stall(self, position, current_price, current_time):
        """
        Check if price is stalling after hitting target1 (Phase 9 - Oct 21, 2025)

        Problem: After hitting target, price often consolidates for extended periods.
                 Example: PATH hit target1 $16.42, then ranged $16.40-$16.42 for 86 min,
                         held 50% runner earning only $3 (+$0.01/share) = capital inefficiency

        Solution: Detect when price stays in tight range (0.2%) for 5+ minutes after
                 target hit → tighten trailing stop from 0.5% to 0.1% → exit quickly

        Args:
            position: Position dict with entry details
            current_price: Current market price
            current_time: Current datetime (timezone-aware)

        Returns:
            tuple: (is_stalled: bool, new_trail_pct: float or None)
                  - is_stalled: True if stall detected
                  - new_trail_pct: Tightened trail distance (e.g., 0.001 for 0.1%)

        Example:
            PATH @ 10:31: Target1 hit at $16.42
            PATH @ 10:36: Price in $16.40-$16.42 range for 5 min → STALL!
            Action: Tighten trail 0.5% → 0.1%, exit at $16.40 vs holding till 11:57
            Result: +$21 vs +$3 on runner = 7x better
        """
        # Get config
        config = self.config.get('trading', {}).get('exits', {}).get('target_hit_stall_detection', {})

        # Check if enabled
        if not config.get('enabled', False):
            return False, None

        # Guard #1: Only check if we have target1 price
        target1 = position.get('target1')
        if not target1:
            return False, None

        # Guard #2: Only check runner positions (after partials taken)
        # Rationale: Stall detection is for optimizing runner exits, not initial position
        if position.get('remaining', 1.0) >= 0.9:  # No partials taken yet
            return False, None

        # Initialize stall tracking fields if not present
        if 'target1_hit_time' not in position:
            position['target1_hit_time'] = None
            position['stall_window_start'] = None
            position['stall_window_high'] = None
            position['stall_window_low'] = None
            position['stall_detected'] = False

        # Detect if target1 was just hit
        side = position['side']
        if side == 'LONG':
            target_hit = current_price >= target1 and position['target1_hit_time'] is None
        else:  # SHORT
            target_hit = current_price <= target1 and position['target1_hit_time'] is None

        if target_hit:
            # Mark target1 as hit - start monitoring for stall
            position['target1_hit_time'] = current_time
            position['stall_window_start'] = current_time
            position['stall_window_high'] = current_price
            position['stall_window_low'] = current_price
            return False, None  # Just hit target, not stalled yet

        # If target1 not hit yet, nothing to check
        if position['target1_hit_time'] is None:
            return False, None

        # If stall already detected and trail tightened, don't re-trigger
        if position.get('stall_detected', False):
            return False, None

        # Update stall window high/low
        if current_price > position['stall_window_high']:
            # Price broke out above window - reset stall tracking
            position['stall_window_start'] = current_time
            position['stall_window_high'] = current_price
            position['stall_window_low'] = current_price
            return False, None

        if current_price < position['stall_window_low']:
            position['stall_window_low'] = current_price

        # Calculate how long price has been in current window
        window_duration = (current_time - position['stall_window_start']).total_seconds()
        stall_duration_threshold = config.get('stall_duration_seconds', 300)  # 5 minutes

        # Check if window duration exceeds threshold
        if window_duration < stall_duration_threshold:
            return False, None  # Not in window long enough yet

        # Calculate range within window
        window_range = (position['stall_window_high'] - position['stall_window_low']) / current_price
        stall_range_threshold = config.get('stall_range_pct', 0.002)  # 0.2%

        # Check if range is tight enough to be considered "stalled"
        if window_range > stall_range_threshold:
            # Range too wide - reset window
            position['stall_window_start'] = current_time
            position['stall_window_high'] = current_price
            position['stall_window_low'] = current_price
            return False, None

        # STALL DETECTED!
        # Price stayed in tight range for required duration after target hit
        position['stall_detected'] = True

        # Return tightened trail distance
        new_trail_pct = config.get('tighten_trail_to_pct', 0.001)  # 0.1%

        return True, new_trail_pct

    def get_current_candle_metrics(self, bars: List, current_idx: int) -> dict:
        """
        Get metrics for current 1-minute candle (Oct 28, 2025 - Issue #2 Fix)

        Aggregates 5-second bars to 1-minute candle (live trading)
        or uses 1-minute bar directly (backtesting)

        Handles both modes automatically using bars_per_candle.

        Args:
            bars: Bar array
            current_idx: Current bar index in array

        Returns:
            dict: {
                'open': float,
                'close': float,
                'volume': float,
                'size_pct': float,
            } or None if insufficient data
        """
        bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds

        if bars_per_candle > 1:
            # Live trading (5-second bars): aggregate to 1-minute candle
            candle_start_idx = (current_idx // bars_per_candle) * bars_per_candle
            candle_end_idx = min(candle_start_idx + bars_per_candle, len(bars))

            if candle_end_idx <= candle_start_idx:
                return None

            candle_bars = bars[candle_start_idx:candle_end_idx]

            if not candle_bars:
                return None

            candle_open = candle_bars[0].open
            candle_close = candle_bars[-1].close
            candle_volume = sum(b.volume for b in candle_bars)
        else:
            # Backtest (1-minute bars): current bar IS the candle
            if current_idx >= len(bars):
                return None

            current_bar = bars[current_idx]
            candle_open = current_bar.open
            candle_close = current_bar.close
            candle_volume = current_bar.volume

        # Calculate candle size percentage
        if candle_open == 0:
            return None

        candle_size_pct = abs(candle_close - candle_open) / candle_open

        return {
            'open': candle_open,
            'close': candle_close,
            'volume': candle_volume,
            'size_pct': candle_size_pct
        }

    def get_average_candle_volume(self, bars: List, current_idx: int, lookback_candles: int = 20) -> float:
        """
        Calculate average 1-minute candle volume over last N candles (Oct 28, 2025 - Issue #3 Fix)

        Aggregates 5-second bars to 1-minute candles (live trading)
        or uses 1-minute bars directly (backtesting)

        Handles both modes automatically using bars_per_candle.

        Args:
            bars: Bar array
            current_idx: Current bar index
            lookback_candles: Number of 1-minute candles to look back (default 20 = 20 minutes)

        Returns:
            float: Average candle volume, or None if insufficient data
        """
        bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds
        lookback_bars = lookback_candles * bars_per_candle  # e.g., 20 candles * 12 bars/candle = 240 bars

        if current_idx < lookback_bars - 1:
            # Not enough history, use what we have
            start_idx = 0
            end_idx = current_idx + 1
        else:
            # Full lookback available
            start_idx = current_idx - lookback_bars + 1
            end_idx = current_idx + 1

        if end_idx <= start_idx:
            return None

        past_bars = bars[start_idx:end_idx]

        if not past_bars:
            return None

        if bars_per_candle > 1:
            # Live trading (5-second bars): Aggregate to candle volumes
            candle_volumes = []
            for i in range(0, len(past_bars), bars_per_candle):
                candle_bars = past_bars[i:i+bars_per_candle]
                if len(candle_bars) == bars_per_candle:  # Only complete candles
                    candle_vol = sum(b.volume for b in candle_bars)
                    candle_volumes.append(candle_vol)

            if not candle_volumes:
                return None

            return sum(candle_volumes) / len(candle_volumes)
        else:
            # Backtest (1-minute bars): bars are already candles
            return sum(b.volume for b in past_bars) / len(past_bars)

    def calculate_atr_based_stop_width(self, atr_percent):
        """
        Calculate stop width based on ATR (volatility)

        Args:
            atr_percent: ATR as percentage of stock price

        Returns:
            float: Stop width as decimal (e.g., 0.012 for 1.2%)
        """
        if atr_percent < 2.0:
            return 0.007  # 0.7% for low volatility stocks
        elif atr_percent < 4.0:
            return 0.012  # 1.2% for medium volatility
        elif atr_percent < 6.0:
            return 0.018  # 1.8% for high volatility
        else:
            return 0.025  # 2.5% for very high volatility

    def calculate_candle_based_stop(self, bars, entry_bar_idx, side, pivot_price=None):
        """
        Calculate stop price based on last opposing candle (Oct 23, 2025)

        Logic:
        - LONG: Find last RED candle before entry, use its LOW as stop
        - SHORT: Find last GREEN candle before entry, use its HIGH as stop
        - Fallback: Use pivot price if no opposing candle found

        Args:
            bars: List of Bar objects (with open, high, low, close)
            entry_bar_idx: Index of entry candle in bars array
            side: 'LONG' or 'SHORT'
            pivot_price: Fallback pivot price (resistance for LONG, support for SHORT)

        Returns:
            float: Stop price
        """
        # Configuration
        lookback = self.config['trading']['risk'].get('candle_stop_lookback', 20)
        fallback_to_pivot = self.config['trading']['risk'].get('candle_stop_fallback_to_pivot', True)

        # Search backwards from entry candle (skip entry candle itself)
        start_idx = entry_bar_idx - 1
        end_idx = max(0, entry_bar_idx - lookback)

        for i in range(start_idx, end_idx - 1, -1):
            if i < 0:
                break

            bar = bars[i]
            is_red = bar.close < bar.open    # Red candle (bearish)
            is_green = bar.close > bar.open  # Green candle (bullish)

            if side == 'LONG':
                # Looking for last RED candle (selling pressure)
                if is_red:
                    stop = bar.low  # Use LOW of red candle
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"  Candle-based stop (LONG): Found red candle at idx {i}")
                        self.logger.debug(f"    Candle: O=${bar.open:.2f} H=${bar.high:.2f} L=${bar.low:.2f} C=${bar.close:.2f}")
                        self.logger.debug(f"    Stop: ${stop:.2f} (LOW of red candle)")
                    return stop

            elif side == 'SHORT':
                # Looking for last GREEN candle (buying pressure)
                if is_green:
                    stop = bar.high  # Use HIGH of green candle
                    if hasattr(self, 'logger'):
                        self.logger.debug(f"  Candle-based stop (SHORT): Found green candle at idx {i}")
                        self.logger.debug(f"    Candle: O=${bar.open:.2f} H=${bar.high:.2f} L=${bar.low:.2f} C=${bar.close:.2f}")
                        self.logger.debug(f"    Stop: ${stop:.2f} (HIGH of green candle)")
                    return stop

        # No opposing candle found - fallback to pivot
        if fallback_to_pivot and pivot_price:
            if hasattr(self, 'logger'):
                self.logger.debug(f"  Candle-based stop ({side}): No opposing candle found in {lookback} bars")
                self.logger.debug(f"    Falling back to pivot: ${pivot_price:.2f}")
            return pivot_price

        # Last resort: Use entry price (tight stop)
        entry_price = bars[entry_bar_idx].close
        if hasattr(self, 'logger'):
            self.logger.warning(f"  Candle-based stop ({side}): No opposing candle AND no pivot!")
            self.logger.warning(f"    Using entry price as stop: ${entry_price:.2f}")
        return entry_price

    def calculate_stop_price(self, position, current_price=None, stock_data=None, bars=None, entry_bar_idx=None):
        """
        Calculate stop price for position using configured method (ATR or candle-based)

        Args:
            position: Position dict with entry_price, side, partials, etc.
            current_price: Current market price (optional)
            stock_data: Stock data dict with ATR info (optional)
            bars: List of Bar objects for candle-based stops (optional)
            entry_bar_idx: Index of entry bar in bars array (optional)

        Returns:
            float - Stop price
        """
        # After partial: breakeven
        if position.get('partials', 0) > 0 and self.breakeven_after_partial:
            return position['entry_price']

        # Get stop loss method from config (Oct 23, 2025)
        stop_method = self.config['trading']['risk'].get('stop_loss_method', 'atr')

        # METHOD 1: Candle-based stops (price action)
        if stop_method == 'candle' and bars is not None and entry_bar_idx is not None:
            pivot_price = position.get('pivot')  # Fallback to pivot
            stop_price = self.calculate_candle_based_stop(
                bars=bars,
                entry_bar_idx=entry_bar_idx,
                side=position['side'],
                pivot_price=pivot_price
            )
            if hasattr(self, 'logger'):
                self.logger.info(f"  Stop (candle-based): ${stop_price:.2f}")
            return stop_price

        # METHOD 2: ATR-based stops (volatility)
        elif stop_method == 'atr' or (stop_method == 'candle' and (bars is None or entry_bar_idx is None)):
            # Use ATR-based stops if enabled and data available
            if self.use_atr_stops and stock_data:
                atr_pct = stock_data.get('atr%', 5.0)  # Default 5% if missing
                stop_width = self.calculate_atr_based_stop_width(atr_pct)

                entry_price = position['entry_price']
                if position['side'] == 'LONG':
                    stop_price = entry_price * (1 - stop_width)
                else:  # SHORT
                    stop_price = entry_price * (1 + stop_width)

                if hasattr(self, 'logger'):
                    self.logger.info(f"  Stop (ATR-based): ${stop_price:.2f} (width: {stop_width*100:.1f}%)")
                return stop_price

        # Fallback: Initial stop at pivot
        if self.stop_at_pivot and 'pivot' in position:
            if hasattr(self, 'logger'):
                self.logger.info(f"  Stop (pivot): ${position['pivot']:.2f}")
            return position['pivot']

        # Last resort: Use tight stop (not recommended)
        entry_price = position['entry_price']
        if position['side'] == 'LONG':
            stop_price = entry_price * 0.995  # 0.5% stop
        else:
            stop_price = entry_price * 1.005  # 0.5% stop

        if hasattr(self, 'logger'):
            self.logger.warning(f"  Stop (fallback 0.5%): ${stop_price:.2f}")
        return stop_price

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
        Calculate position size based on risk with adaptive sizing

        ADAPTIVE SIZING (Oct 7, 2025):
        - Limits position value to prevent over-concentration in high-priced stocks
        - Formula: shares = min(shares_by_risk, shares_by_value, max_shares)
        - Example: GS @ $794 with tight stop would create $794k position without this

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

        # Calculate shares based on risk (original method)
        shares_by_risk = int(risk_amount / stop_distance)

        # ADAPTIVE SIZING: Calculate max shares based on position value limit
        shares_by_value = int(self.max_position_value / entry_price)

        # Take the minimum of risk-based, value-based, and hard cap
        min_shares = self.trading_config['position_sizing']['min_shares']
        max_shares = self.trading_config['position_sizing']['max_shares']

        # Apply all three constraints
        shares = min(shares_by_risk, shares_by_value, max_shares)
        shares = max(min_shares, shares)  # Ensure minimum

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

    def filter_enhanced_scanner_results(self, scanner_results):
        """
        Filter enhanced scanner results using tier-based criteria (Oct 6, 2025)

        ENHANCED SCORING FILTERS:
        - Tier-based classification (TIER 1/2/3/AVOID)
        - Pivot width filtering (tight pivots = winners)
        - Test count filtering (heavily tested = higher success)
        - Symbol blacklisting (index ETFs, high-vol stocks)
        - Risk/reward minimum thresholds

        Based on Oct 6 validation showing 70% accuracy in top 10 ranked setups.

        Args:
            scanner_results: List of enhanced scanner result dicts with fields:
                - enhanced_long_score, enhanced_short_score, best_enhanced_score
                - pivot_width_pct
                - breakout_reason (contains test count)
                - symbol, risk_reward, etc.

        Returns:
            List of filtered results (TIER 1, TIER 2, and select TIER 3)
        """
        import re

        filtered = []

        # Load config filters
        min_enhanced_score = self.config.get('filters', {}).get('min_enhanced_score', 0)
        min_pivot_width_pct = self.config.get('filters', {}).get('min_pivot_width_pct', 0)
        max_pivot_width_pct = self.config.get('filters', {}).get('max_pivot_width_pct', 10.0)
        min_test_count = self.config.get('filters', {}).get('min_test_count', 0)
        tier_filter = self.config.get('filters', {}).get('tier_filter', ['TIER 1', 'TIER 2', 'TIER 3'])

        # Blacklists from validation
        index_etfs = ['SPY', 'QQQ', 'DIA', 'IWM']  # 100% false breakout rate
        high_vol_stocks = ['TSLA', 'NVDA', 'COIN', 'AMC', 'GME', 'HOOD', 'LCID', 'RIVN']  # 75% false breakout

        for stock in scanner_results:
            symbol = stock.get('symbol', '')

            # Blacklist filter - SKIP index ETFs and high-vol stocks
            if symbol in index_etfs:
                continue
            if symbol in high_vol_stocks:
                continue

            # Enhanced score filter
            best_score = stock.get('best_enhanced_score', stock.get('score', 0))
            if best_score < min_enhanced_score:
                continue

            # Risk/Reward filter
            if stock.get('risk_reward', 0) < self.min_risk_reward:
                continue

            # Pivot width filter (key insight from validation)
            pivot_width = stock.get('pivot_width_pct', 100)
            if pivot_width < min_pivot_width_pct or pivot_width > max_pivot_width_pct:
                continue

            # Test count filter (Oct 6 insight: tested ≥10x = 80% success)
            breakout_reason = stock.get('breakout_reason', '')
            match = re.search(r'Tested (\d+)x', breakout_reason)
            test_count = int(match.group(1)) if match else 0

            if test_count < min_test_count:
                continue

            # Tier classification for filtering
            tier = self._classify_stock_tier(stock)

            # Apply tier filter
            if tier not in tier_filter:
                continue

            # Symbol avoid list (from config)
            if symbol in self.avoid_symbols:
                continue

            # Store tier classification in stock data
            stock['tier'] = tier
            stock['test_count'] = test_count

            filtered.append(stock)

        return filtered

    def _classify_stock_tier(self, stock):
        """
        Classify stock into tiers based on enhanced scoring criteria

        TIER 1: Tight pivot (<2.5%) + Heavy testing (≥10x) = 70-80% success expected
        TIER 2: Good on one factor (pivot <3.5% OR tests ≥5x) = 50-60% success
        TIER 3: Weaker on both (pivot <5.0%) = 40-50% success
        AVOID: Too wide (pivot >5.0%) or blacklisted

        Args:
            stock: Dict with enhanced scoring data

        Returns:
            str: 'TIER 1', 'TIER 2', 'TIER 3', or 'AVOID'
        """
        import re

        pivot_width = stock.get('pivot_width_pct', 100)

        # Extract test count from breakout_reason
        breakout_reason = stock.get('breakout_reason', '')
        match = re.search(r'Tested (\d+)x', breakout_reason)
        test_count = int(match.group(1)) if match else 0

        # TIER 1: Tight pivot + heavy testing
        if pivot_width <= 2.5 and test_count >= 10:
            return 'TIER 1'

        # TIER 2: Good on one factor
        elif pivot_width <= 3.5 or test_count >= 5:
            return 'TIER 2'

        # TIER 3: Weaker on both
        elif pivot_width <= 5.0:
            return 'TIER 3'

        # AVOID: Too wide
        else:
            return 'AVOID'

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

    # ========================================================================
    # DYNAMIC RESISTANCE EXITS (October 15, 2025)
    # ========================================================================
    #
    # Purpose: Detect technical resistance levels and take partials when approaching them
    #
    # Why: Stocks often stall at technical levels (SMAs, Bollinger Bands, Linear Regression)
    #      Taking partials near resistance locks profits before potential reversal
    #      Much smarter than arbitrary 1% trailing stop - respects market structure
    #
    # Example: SOFI trade (Oct 15, 2025)
    #   - Entry: $28.55, Exit: $28.58 (15-min rule) = $10.50 profit
    #   - WITH dynamic resistance:
    #     - Price $28.83 approaching SMA50 @ $28.85 (0.07% away)
    #     - Take 25% partial @ $28.83 (+$98)
    #     - Activate 0.5% trailing stop on remainder
    #     - Trail captures move to $28.77 (+$231)
    #     - Total: $329 vs $10.50 (31x improvement!)
    #
    # How it works:
    #   1. Check overhead resistance every tick (SMAs, BB, LR on hourly bars)
    #   2. If resistance within 0.5% detected → take 25% partial
    #   3. Activate trailing stop on remainder (0.5% distance)
    #   4. Let trail capture remaining move or stop out
    #
    # ========================================================================

    def _calculate_bollinger_bands(self, bars, period=20, std_dev=2):
        """
        Calculate Bollinger Bands from hourly bars

        Bollinger Bands = SMA ± (N × Standard Deviation)
        Shows volatility-based support/resistance levels
        Price tends to bounce off or consolidate at bands

        Args:
            bars: List of hourly Bar objects
            period: Number of periods for SMA (default 20)
            std_dev: Number of standard deviations (default 2)

        Returns:
            tuple: (upper_band, middle_band, lower_band) or (None, None, None) if insufficient data

        Example:
            Entry: $28.55
            BB Upper: $29.20 (+2.3% from entry)
            → If price reaches $29.15, take partial (within 0.5% of BB)
        """
        if not bars or len(bars) < period:
            self.logger.debug(f"BB calculation: Insufficient bars ({len(bars) if bars else 0}/{period})")
            return None, None, None

        try:
            # Get closing prices for the period
            closes = [b.close for b in bars[-period:]]

            # Calculate middle band (20-period SMA on hourly bars)
            middle_band = sum(closes) / len(closes)

            # Calculate standard deviation (volatility measure)
            variance = sum((x - middle_band) ** 2 for x in closes) / len(closes)
            std = variance ** 0.5

            # Calculate upper and lower bands (2 std dev from middle)
            upper_band = middle_band + (std_dev * std)
            lower_band = middle_band - (std_dev * std)

            self.logger.debug(f"BB calculation: Upper=${upper_band:.2f}, Middle=${middle_band:.2f}, Lower=${lower_band:.2f}")

            return upper_band, middle_band, lower_band

        except Exception as e:
            self.logger.warning(f"Bollinger Bands calculation failed: {e}")
            return None, None, None

    def _calculate_linear_regression(self, bars, period=30):
        """
        Calculate 30-period linear regression trend channel

        Linear Regression = Best-fit line through price data
        Shows trend direction and strength
        Upper/lower channels show expected deviation range
        Price tends to revert toward regression line

        Args:
            bars: List of hourly Bar objects
            period: Number of periods for regression (default 30)

        Returns:
            tuple: (upper_channel, middle_line, lower_channel) or (None, None, None) if insufficient data

        Example:
            Entry: $28.55
            LR Upper: $28.95 (+1.4% from entry)
            → If price reaches $28.92, take partial (within 0.5% of LR)
        """
        if not bars or len(bars) < period:
            self.logger.debug(f"LR calculation: Insufficient bars ({len(bars) if bars else 0}/{period})")
            return None, None, None

        try:
            # Get closing prices for the period (last 30 hourly bars)
            closes = [b.close for b in bars[-period:]]
            x = list(range(len(closes)))

            # Simple linear regression: y = mx + b
            # Where m = slope (trend direction), b = intercept
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(closes)
            sum_xy = sum(xi * yi for xi, yi in zip(x, closes))
            sum_x2 = sum(xi ** 2 for xi in x)

            # Calculate slope (m) and intercept (b) using least squares method
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            intercept = (sum_y - slope * sum_x) / n

            # Project to current bar (end of period)
            current_x = len(closes) - 1
            lr_value = slope * current_x + intercept

            # Calculate channel width using standard error (measure of scatter)
            residuals = [closes[i] - (slope * x[i] + intercept) for i in range(n)]
            std_error = (sum(r ** 2 for r in residuals) / n) ** 0.5

            # Upper and lower channel boundaries (2 standard errors from regression line)
            upper_channel = lr_value + (2 * std_error)
            lower_channel = lr_value - (2 * std_error)

            self.logger.debug(f"LR calculation: Upper=${upper_channel:.2f}, Middle=${lr_value:.2f}, Lower=${lower_channel:.2f}, Slope={slope:.4f}")

            return upper_channel, lr_value, lower_channel

        except Exception as e:
            self.logger.warning(f"Linear Regression calculation failed: {e}")
            return None, None, None

    def check_overhead_resistance(self, symbol, current_price, hourly_bars=None):
        """
        Check if price is approaching ANY technical resistance level

        Purpose: Detect when price is near resistance so we can take partials
        Strategy: Check multiple technical levels in priority order
        Result: Take profits before potential reversal at resistance

        Checks (in priority order):
        1. Hourly SMAs (5, 10, 20, 50, 100) - Priority 1 (most respected)
        2. Bollinger Upper Band - Priority 2 (volatility-based)
        3. Linear Regression Upper - Priority 3 (trend-based)

        Args:
            symbol: Stock symbol
            current_price: Current market price
            hourly_bars: Cached hourly bars (optional, will fetch if not provided)

        Returns:
            tuple: (has_resistance, level_info) where level_info is dict with:
                {
                    'price': resistance price,
                    'type': 'SMA5' | 'SMA10' | 'SMA20' | 'SMA50' | 'SMA100' | 'BB_UPPER' | 'LR_UPPER',
                    'distance_pct': percentage away (e.g., 0.0007 for 0.07%),
                    'priority': 1-3 (1=highest priority)
                }

        Example:
            Price: $28.83
            SMA50: $28.85 (0.07% away)
            → (True, {'price': 28.85, 'type': 'SMA50', 'distance_pct': 0.0007, 'priority': 1})
        """
        # Get configuration settings
        config = self.config.get('exits', {}).get('dynamic_resistance_exits', {})
        if not config.get('enabled', True):
            self.logger.debug(f"{symbol}: Dynamic resistance exits disabled in config")
            return False, None

        resistance_distance_pct = config.get('resistance_distance_pct', 0.005)  # 0.5% default
        min_gain_before_check = config.get('min_gain_before_check', 0.005)  # 0.5% default

        # Get hourly bars if not provided (uses existing cache)
        if hourly_bars is None:
            hourly_bars = self._get_cached_hourly_bars(symbol)

        if not hourly_bars or len(hourly_bars) < 20:
            self.logger.debug(f"{symbol}: Insufficient hourly bars for resistance check ({len(hourly_bars) if hourly_bars else 0}/20)")
            return False, None

        # Log that we're checking resistance
        self.logger.debug(f"{symbol}: Checking overhead resistance at ${current_price:.2f} (threshold: {resistance_distance_pct*100:.1f}%)")

        resistance_levels = []

        # ====================================================================
        # Priority 1: Check hourly SMAs (most respected by traders)
        # ====================================================================
        if config.get('check_smas', True):
            sma_periods = config.get('sma_periods', [5, 10, 20, 50, 100])
            self.logger.debug(f"{symbol}: Checking SMAs {sma_periods}...")

            for period in sma_periods:
                if len(hourly_bars) >= period:
                    # Calculate SMA from last N hourly bars
                    sma = sum(b.close for b in hourly_bars[-period:]) / period

                    # Only check levels ABOVE current price (overhead resistance)
                    if sma > current_price:
                        distance_pct = (sma - current_price) / current_price

                        # If within resistance threshold (default 0.5%)
                        if distance_pct <= resistance_distance_pct:
                            self.logger.debug(f"{symbol}: SMA{period} @ ${sma:.2f} ({distance_pct*100:.2f}% away) - NEAR!")
                            resistance_levels.append({
                                'price': sma,
                                'type': f'SMA{period}',
                                'distance_pct': distance_pct,
                                'priority': 1
                            })
                        else:
                            self.logger.debug(f"{symbol}: SMA{period} @ ${sma:.2f} ({distance_pct*100:.2f}% away) - too far")

        # ====================================================================
        # Priority 2: Check Bollinger Bands upper (volatility-based resistance)
        # ====================================================================
        if config.get('check_bollinger_bands', True):
            bb_period = config.get('bb_period', 20)
            bb_std_dev = config.get('bb_std_dev', 2)

            self.logger.debug(f"{symbol}: Checking Bollinger Bands ({bb_period} period, {bb_std_dev} std dev)...")
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(
                hourly_bars, period=bb_period, std_dev=bb_std_dev
            )

            if bb_upper and bb_upper > current_price:
                distance_pct = (bb_upper - current_price) / current_price

                if distance_pct <= resistance_distance_pct:
                    self.logger.debug(f"{symbol}: BB_UPPER @ ${bb_upper:.2f} ({distance_pct*100:.2f}% away) - NEAR!")
                    resistance_levels.append({
                        'price': bb_upper,
                        'type': 'BB_UPPER',
                        'distance_pct': distance_pct,
                        'priority': 2
                    })
                else:
                    self.logger.debug(f"{symbol}: BB_UPPER @ ${bb_upper:.2f} ({distance_pct*100:.2f}% away) - too far")

        # ====================================================================
        # Priority 3: Check Linear Regression upper (trend-based resistance)
        # ====================================================================
        if config.get('check_linear_regression', True):
            lr_period = config.get('lr_period', 30)

            self.logger.debug(f"{symbol}: Checking Linear Regression ({lr_period} period)...")
            lr_upper, lr_middle, lr_lower = self._calculate_linear_regression(
                hourly_bars, period=lr_period
            )

            if lr_upper and lr_upper > current_price:
                distance_pct = (lr_upper - current_price) / current_price

                if distance_pct <= resistance_distance_pct:
                    self.logger.debug(f"{symbol}: LR_UPPER @ ${lr_upper:.2f} ({distance_pct*100:.2f}% away) - NEAR!")
                    resistance_levels.append({
                        'price': lr_upper,
                        'type': 'LR_UPPER',
                        'distance_pct': distance_pct,
                        'priority': 3
                    })
                else:
                    self.logger.debug(f"{symbol}: LR_UPPER @ ${lr_upper:.2f} ({distance_pct*100:.2f}% away) - too far")

        # No resistance found within threshold
        if not resistance_levels:
            self.logger.debug(f"{symbol}: No resistance detected within {resistance_distance_pct*100:.1f}%")
            return False, None

        # Return highest priority resistance with closest distance
        # Sort by: priority first (1=SMAs, 2=BB, 3=LR), then by distance (closest)
        resistance_levels.sort(key=lambda x: (x['priority'], x['distance_pct']))
        best_level = resistance_levels[0]

        self.logger.info(f"{symbol}: 🎯 RESISTANCE FOUND: {best_level['type']} @ ${best_level['price']:.2f} ({best_level['distance_pct']*100:.2f}% away)")

        return True, best_level

    # ========================================================================
    # END: DYNAMIC RESISTANCE EXITS
    # ========================================================================

    # ========================================================================
    # DYNAMIC PIVOT UPDATES (October 28, 2025)
    # ========================================================================
    # Ultra-simple 3-step logic for updating pivots based on market structure:
    # 1. Session Start: If gap above pivot → use session high as new pivot
    # 2. Target Hit: When Target1 reached → Target1 becomes pivot, aim for Target2
    # 3. Failure: When trade fails → update pivot to session high for next attempt
    # ========================================================================

    def get_session_high(self, symbol):
        """
        Get today's session high from IBKR real-time market data

        Uses IBKR's reqMktData which provides session high/low automatically.
        This is the EASIEST and most reliable approach - IBKR tracks it for us.

        Args:
            symbol: Stock symbol

        Returns:
            float: Session high price, or None if unavailable
        """
        if not self.ib:
            logger.warning(f"⚠️  No IBKR connection - cannot get session high for {symbol}")
            return None

        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')

            # Request market data snapshot (doesn't require subscription)
            ticker = self.ib.reqMktData(contract, '', True, False)
            self.ib.sleep(0.5)  # Give IBKR time to populate data

            # Get session high from ticker
            if ticker.high and ticker.high > 0:
                logger.info(f"📊 {symbol}: Session high from IBKR: ${ticker.high:.2f}")
                return ticker.high
            else:
                logger.warning(f"⚠️  {symbol}: Session high not available from IBKR ticker")
                return self._get_session_high_from_bars(symbol)

        except Exception as e:
            logger.error(f"❌ Error fetching session high for {symbol}: {e}")
            return self._get_session_high_from_bars(symbol)

    def _get_session_high_from_bars(self, symbol):
        """
        Fallback: Calculate session high from historical 1-minute bars

        Args:
            symbol: Stock symbol

        Returns:
            float: Session high price, or None if unavailable
        """
        if not self.ib:
            return None

        try:
            from ib_insync import Stock

            contract = Stock(symbol, 'SMART', 'USD')
            today = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y%m%d")

            # Request today's 1-minute bars
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=f'{today} 16:00:00',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if bars and len(bars) > 0:
                session_high = max(bar.high for bar in bars)
                logger.info(f"📊 {symbol}: Session high from bars: ${session_high:.2f}")
                return session_high
            else:
                logger.warning(f"⚠️  {symbol}: No bars available for session high calculation")
                return None

        except Exception as e:
            logger.error(f"❌ Error calculating session high from bars for {symbol}: {e}")
            return None

    def check_gap_and_update_pivot(self, stock, current_price, current_time=None):
        """
        Step 1: Check if stock gapped above pivot when trader initialized
        If yes, update pivot to session high

        Logic:
        - Called once per stock when trader starts (initialization)
        - Current price already above original pivot (gap condition)
        - Session high is higher than original pivot
        → Update pivot to session high (gap "ate up" the move)

        This checks at TRADER INITIALIZATION time, not just 9:30-9:35 AM.
        So if you start the trader at 10:00 AM and stock gapped, it still detects it.

        Args:
            stock: Stock dict with 'resistance', 'symbol', etc.
            current_price: Current stock price
            current_time: Current datetime (ET timezone), or None to use now

        Returns:
            bool: True if pivot was updated, False otherwise
        """
        # Skip if already checked (this runs once per stock at initialization)
        if stock.get('gap_check_done'):
            return False

        # Mark as checked (so we don't check repeatedly)
        stock['gap_check_done'] = True

        # Get current time in ET
        if current_time is None:
            current_time = datetime.now(pytz.timezone('US/Eastern'))
        elif not hasattr(current_time, 'tzinfo') or current_time.tzinfo is None:
            current_time = pytz.timezone('US/Eastern').localize(current_time)

        # Get original pivot (resistance for LONG)
        original_pivot = stock.get('original_resistance', stock.get('resistance'))

        # Check if price already above pivot (gap condition)
        if current_price <= original_pivot:
            return False

        # Get session high - prefer tracked value (backtesting), fallback to IBKR (live)
        # FIX (Oct 28, 2025): Backtester now tracks session_high in stock dict
        session_high = stock.get('session_high')
        if not session_high:
            # Live trading: query IBKR
            session_high = self.get_session_high(stock['symbol'])

        if not session_high or session_high <= original_pivot:
            return False

        # GAP DETECTED - Update pivot to session high
        logger.info(f"")
        logger.info(f"{'='*80}")
        logger.info(f"🔄 GAP DETECTED AT INITIALIZATION: {stock['symbol']}")
        logger.info(f"{'='*80}")
        logger.info(f"   Trader started: {current_time.strftime('%H:%M:%S ET')}")
        logger.info(f"   Current price: ${current_price:.2f}")
        logger.info(f"   Scanner pivot: ${original_pivot:.2f}")
        logger.info(f"   Session high: ${session_high:.2f}")
        logger.info(f"   Gap amount: ${current_price - original_pivot:.2f} ({((current_price - original_pivot) / original_pivot * 100):.1f}%)")
        logger.info(f"   📊 ACTION: Updating pivot to session high")
        logger.info(f"{'='*80}")

        # Store original pivot before updating
        if 'original_resistance' not in stock:
            stock['original_resistance'] = original_pivot

        # Update pivot to session high
        stock['resistance'] = session_high
        stock['pivot_updated_for_gap'] = True
        stock['pivot_update_time'] = current_time
        stock['pivot_update_reason'] = 'GAP_AT_INIT'

        return True

    def check_target_progression_pivot(self, position, current_price):
        """
        Step 2: Check if Target1 was hit and update pivot for Target2 run

        Logic:
        - Position has hit Target1 (partials already taken)
        - Target2 exists
        - Room from Target1 to Target2 is >= 1.5%
        → Update pivot to Target1, aim for Target2

        Args:
            position: Position dict with 'target1', 'target2', etc.
            current_price: Current stock price

        Returns:
            bool: True if pivot was updated, False otherwise
        """
        # Skip if already updated to Target1
        if position.get('pivot_updated_to_target1'):
            return False

        # Check if Target1 was hit
        target1 = position.get('target1')
        target2 = position.get('target2')

        if not target1 or not target2:
            return False

        # Check if price reached Target1
        side = position.get('side', 'LONG')
        if side == 'LONG':
            target1_hit = current_price >= target1
        else:
            target1_hit = current_price <= target1

        if not target1_hit:
            return False

        # Check room to Target2
        if side == 'LONG':
            room_pct = ((target2 - target1) / target1) * 100
        else:
            room_pct = ((target1 - target2) / target1) * 100

        if room_pct < 1.5:  # Need at least 1.5% room
            logger.debug(f"{position['symbol']}: Target1 hit but insufficient room to Target2 ({room_pct:.1f}%)")
            return False

        # TARGET1 HIT - Update pivot for Target2 run
        logger.info(f"")
        logger.info(f"{'='*80}")
        logger.info(f"🎯 TARGET1 HIT: {position['symbol']}")
        logger.info(f"{'='*80}")
        logger.info(f"   Old pivot: ${position.get('pivot', position.get('entry_price')):.2f}")
        logger.info(f"   New pivot: ${target1:.2f} (Target1)")
        logger.info(f"   Target2: ${target2:.2f}")
        logger.info(f"   Room to Target2: {room_pct:.1f}%")
        logger.info(f"   📊 ACTION: Updating pivot to Target1, aiming for Target2")
        logger.info(f"{'='*80}")

        # Update pivot to Target1
        position['pivot'] = target1
        position['stop'] = target1  # Move stop to Target1 (breakeven++)
        position['pivot_updated_to_target1'] = True
        position['pivot_update_time'] = datetime.now(pytz.timezone('US/Eastern'))
        position['pivot_update_reason'] = 'TARGET1_HIT'

        return True

    def check_failure_and_update_pivot(self, stock, current_price, failure_reason):
        """
        Step 3: Check if trade failed and update pivot to session high for next attempt

        Logic:
        - Trade stopped out, pulled back too deep, or hit 15-min rule
        - Session high is higher than original pivot
        - Pivot moved >= 1% from original
        → Update pivot to session high, reset attempts

        Args:
            stock: Stock dict with 'resistance', 'symbol', etc.
            current_price: Current stock price
            failure_reason: Reason for failure (e.g., 'STOP_HIT', '15MIN_RULE')

        Returns:
            bool: True if pivot was updated, False otherwise
        """
        # Check if this is a valid failure reason
        # FIX (Oct 28, 2025): Updated to match actual exit reasons used by system
        valid_failures = [
            'STOP',              # Backtester/Live: Stop-loss hit
            'STOP_HIT',          # Legacy compatibility
            'PULLBACK_TOO_DEEP', # Entry state machine rejection
            '7MIN_RULE',         # Backtester/Live: 7-minute timeout
            '15MIN_RULE',        # Live: 15-minute timeout
            'TRAIL_STOP'         # Trailing stop hit
        ]
        if failure_reason not in valid_failures:
            return False

        # Get original pivot
        original_pivot = stock.get('original_resistance', stock.get('resistance'))

        # Get session high - prefer tracked value (backtesting), fallback to IBKR (live)
        # FIX (Oct 28, 2025): Backtester now tracks session_high in stock dict
        session_high = stock.get('session_high')
        if not session_high:
            # Live trading: query IBKR
            session_high = self.get_session_high(stock['symbol'])

        if not session_high or session_high <= original_pivot:
            return False

        # Check if pivot moved significantly (at least 1%)
        pivot_move_pct = ((session_high - original_pivot) / original_pivot) * 100

        if pivot_move_pct < 1.0:
            logger.debug(f"{stock['symbol']}: Session high only {pivot_move_pct:.1f}% above pivot (need 1%+)")
            return False

        # FAILURE DETECTED - Update pivot to session high
        logger.info(f"")
        logger.info(f"{'='*80}")
        logger.info(f"💥 FAILURE PIVOT UPDATE: {stock['symbol']}")
        logger.info(f"{'='*80}")
        logger.info(f"   Failure reason: {failure_reason}")
        logger.info(f"   Old pivot: ${original_pivot:.2f}")
        logger.info(f"   Session high: ${session_high:.2f}")
        logger.info(f"   Pivot move: {pivot_move_pct:.1f}%")
        logger.info(f"   📊 ACTION: Updating pivot to session high for next attempt")
        logger.info(f"{'='*80}")

        # Store original pivot before updating
        if 'original_resistance' not in stock:
            stock['original_resistance'] = original_pivot

        # Update pivot to session high
        stock['resistance'] = session_high
        stock['pivot_updated_after_failure'] = True
        stock['pivot_update_time'] = datetime.now(pytz.timezone('US/Eastern'))
        stock['pivot_update_reason'] = failure_reason

        # Reset attempt counter (give new pivot a fresh chance)
        if pivot_move_pct >= 1.0:
            stock['long_attempts'] = 0
            logger.info(f"   ↻ Reset attempt counter (pivot moved {pivot_move_pct:.1f}%)")

        return True

    # ========================================================================
    # END: DYNAMIC PIVOT UPDATES
    # ========================================================================
