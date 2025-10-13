"""
Breakout State Tracker - Stateful Memory Management for PS60 Strategy

Instead of constantly searching through bars, we maintain state for each symbol
and track key moments in memory. This eliminates the lookback loop problem.

Author: Claude Code
Date: October 9, 2025
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class BreakoutState(Enum):
    """States in the breakout tracking state machine"""
    MONITORING = "MONITORING"                    # Watching for initial breakout
    BREAKOUT_DETECTED = "BREAKOUT_DETECTED"      # Breakout occurred, waiting for candle close
    CANDLE_CLOSED = "CANDLE_CLOSED"              # Candle closed, analyzing strength
    WEAK_BREAKOUT_TRACKING = "WEAK_BREAKOUT_TRACKING"  # Weak breakout, monitoring for pullback/sustained
    PULLBACK_RETEST = "PULLBACK_RETEST"          # Pullback detected, waiting for bounce
    SUSTAINED_BREAK = "SUSTAINED_BREAK"          # Holding above/below pivot, accumulating bars
    READY_TO_ENTER = "READY_TO_ENTER"            # All conditions met, ready for entry
    FAILED = "FAILED"                            # Setup failed, reset to monitoring


@dataclass
class BreakoutMemory:
    """
    Memory structure for tracking a symbol's breakout progression

    This replaces the lookback loop approach - we store key moments in time
    and make decisions based on current state + stored history.
    """

    # Current state
    state: BreakoutState = BreakoutState.MONITORING
    side: Optional[str] = None  # 'LONG' or 'SHORT'

    # Key moments (stored ONCE when they happen)
    breakout_detected_at: Optional[datetime] = None
    breakout_bar: Optional[int] = None
    breakout_price: Optional[float] = None

    candle_closed_at: Optional[datetime] = None
    candle_close_bar: Optional[int] = None
    candle_close_price: Optional[float] = None

    # Breakout characteristics
    breakout_type: Optional[str] = None  # 'MOMENTUM', 'WEAK'
    volume_ratio: Optional[float] = None
    candle_size_pct: Optional[float] = None

    # Tracking for weak breakouts
    pullback_detected_at: Optional[datetime] = None
    pullback_closest_price: Optional[float] = None

    # PHASE 5 (Oct 12, 2025): Track pullback extremes for dynamic pivot adjustment
    pullback_high: Optional[float] = None  # Highest point during pullback (for SHORTS)
    pullback_low: Optional[float] = None   # Lowest point during pullback (for LONGS)

    sustained_hold_start: Optional[datetime] = None
    sustained_hold_start_bar: Optional[int] = None
    bars_held_above_pivot: int = 0

    # Price action memory
    highest_since_breakout: Optional[float] = None
    lowest_since_breakout: Optional[float] = None

    # Tracking
    last_check_bar: int = 0
    last_update: Optional[datetime] = None

    # Config stored at breakout time
    pivot_price: Optional[float] = None
    target_price: Optional[float] = None

    # Entry readiness
    entry_reason: Optional[str] = None
    entry_state: Dict[str, Any] = field(default_factory=dict)

    def reset(self):
        """Reset to initial monitoring state"""
        self.__init__()

    def to_dict(self):
        """Convert to dict for logging/debugging"""
        return {
            'state': self.state.value,
            'side': self.side,
            'breakout_bar': self.breakout_bar,
            'breakout_price': self.breakout_price,
            'breakout_type': self.breakout_type,
            'candle_close_bar': self.candle_close_bar,
            'volume_ratio': self.volume_ratio,
            'bars_held': self.bars_held_above_pivot,
            'entry_reason': self.entry_reason
        }


class BreakoutStateTracker:
    """
    Manages state for all symbols being tracked

    This eliminates the need for lookback loops - we remember key events
    and make decisions based on current price + stored state.
    """

    def __init__(self):
        self.states: Dict[str, BreakoutMemory] = {}

    def get_state(self, symbol: str) -> BreakoutMemory:
        """Get or create state for a symbol"""
        if symbol not in self.states:
            self.states[symbol] = BreakoutMemory()
        return self.states[symbol]

    def reset_state(self, symbol: str):
        """Reset a symbol back to monitoring"""
        if symbol in self.states:
            self.states[symbol].reset()

    def update_breakout(self, symbol: str, bar_idx: int, price: float,
                       timestamp: datetime, pivot: float, side: str):
        """
        Record breakout detection - called ONCE when price first breaks pivot

        Args:
            symbol: Stock symbol
            bar_idx: Bar index where breakout occurred
            price: Price at breakout
            timestamp: Time of breakout
            pivot: Pivot price (resistance or support)
            side: 'LONG' or 'SHORT'
        """
        state = self.get_state(symbol)

        # Only record if we're in monitoring state (first breakout)
        if state.state == BreakoutState.MONITORING:
            state.state = BreakoutState.BREAKOUT_DETECTED
            state.side = side
            state.breakout_detected_at = timestamp
            state.breakout_bar = bar_idx
            state.breakout_price = price
            state.pivot_price = pivot
            state.last_update = timestamp

            # Initialize price tracking
            state.highest_since_breakout = price
            state.lowest_since_breakout = price

    def update_candle_close(self, symbol: str, bar_idx: int, price: float,
                           timestamp: datetime, volume_ratio: float,
                           candle_size_pct: float):
        """
        Record candle close - called when breakout candle completes

        Args:
            symbol: Stock symbol
            bar_idx: Bar index where candle closed
            price: Close price
            timestamp: Time of close
            volume_ratio: Volume vs average (e.g., 1.5x)
            candle_size_pct: Candle size as % (e.g., 0.008 = 0.8%)
        """
        state = self.get_state(symbol)

        if state.state == BreakoutState.BREAKOUT_DETECTED:
            state.state = BreakoutState.CANDLE_CLOSED
            state.candle_closed_at = timestamp
            state.candle_close_bar = bar_idx
            state.candle_close_price = price
            state.volume_ratio = volume_ratio
            state.candle_size_pct = candle_size_pct
            state.last_update = timestamp

    def classify_breakout(self, symbol: str, is_strong_volume: bool,
                         is_large_candle: bool, bars=None, current_idx=None) -> str:
        """
        Classify breakout as MOMENTUM or WEAK

        PHASE 2 FILTERS (Updated Oct 13, 2025):
        - Volume check: 1-minute breakout candle only (≥2.0x avg volume)
        - Candle size: ≥0.3% (momentum candle)
        - Time-of-day filter: No momentum entries after 2 PM

        REMOVED (Oct 13, 2025):
        - Volume sustainability check (was rejecting valid high-volume breakouts)

        Returns:
            'MOMENTUM' or 'WEAK'
        """
        state = self.get_state(symbol)

        if is_strong_volume and is_large_candle:
            breakout_type = 'MOMENTUM'

            # REMOVED: Volume Sustainability Check (Oct 13, 2025)
            # Was rejecting valid breakouts with strong initial volume
            # (e.g., BBBY with 5.78x volume rejected because volume decreased after spike)
            # Now: Only check volume on 1-minute breakout candle itself

            # PHASE 2 FILTER: Time-of-Day Filter
            # No momentum entries after 2 PM (14:00) - higher whipsaws, lower volume
            if bars is not None and current_idx is not None:
                bar_time = bars[current_idx].date if hasattr(bars[current_idx], 'date') else None
                if bar_time and bar_time.hour >= 14:
                    # After 2 PM, downgrade to WEAK
                    breakout_type = 'WEAK'
                    state.entry_reason = "Momentum downgraded (after 2 PM)"

            # Apply classification
            if breakout_type == 'MOMENTUM':
                state.breakout_type = 'MOMENTUM'
                state.state = BreakoutState.READY_TO_ENTER
                state.entry_reason = "MOMENTUM_BREAKOUT"
            else:
                state.breakout_type = 'WEAK'
                state.state = BreakoutState.WEAK_BREAKOUT_TRACKING
                state.sustained_hold_start = state.candle_closed_at
                state.sustained_hold_start_bar = state.candle_close_bar
        else:
            state.breakout_type = 'WEAK'
            state.state = BreakoutState.WEAK_BREAKOUT_TRACKING
            # Start tracking sustained hold from now
            state.sustained_hold_start = state.candle_closed_at
            state.sustained_hold_start_bar = state.candle_close_bar

        return state.breakout_type

    def update_price_action(self, symbol: str, current_price: float,
                           current_bar: int, timestamp: datetime):
        """
        Update price tracking (high/low since breakout, pullback detection)

        Called every bar for symbols in WEAK_BREAKOUT_TRACKING state

        PHASE 5 (Oct 12, 2025): Track pullback extremes for dynamic pivot adjustment
        """
        state = self.get_state(symbol)

        # Update price extremes
        if state.highest_since_breakout is None or current_price > state.highest_since_breakout:
            state.highest_since_breakout = current_price
        if state.lowest_since_breakout is None or current_price < state.lowest_since_breakout:
            state.lowest_since_breakout = current_price

        # PHASE 5: Track pullback extremes during PULLBACK_RETEST state
        # These become the new entry pivot and stop levels
        if state.state == BreakoutState.PULLBACK_RETEST:
            if state.side == 'LONG':
                # Track the lowest point during pullback (becomes the stop)
                if state.pullback_low is None or current_price < state.pullback_low:
                    state.pullback_low = current_price
            elif state.side == 'SHORT':
                # Track the highest point during pullback (becomes the stop)
                if state.pullback_high is None or current_price > state.pullback_high:
                    state.pullback_high = current_price

        state.last_check_bar = current_bar
        state.last_update = timestamp

    def check_pullback(self, symbol: str, current_price: float,
                      pullback_distance_pct: float = 0.003) -> bool:
        """
        Check if price has pulled back close to pivot

        Args:
            symbol: Stock symbol
            current_price: Current price
            pullback_distance_pct: Max distance from pivot (e.g., 0.003 = 0.3%)

        Returns:
            True if pullback detected
        """
        state = self.get_state(symbol)

        if state.state != BreakoutState.WEAK_BREAKOUT_TRACKING:
            return False

        pivot = state.pivot_price
        distance = abs(current_price - pivot) / pivot

        if distance <= pullback_distance_pct:
            # Pullback detected!
            state.state = BreakoutState.PULLBACK_RETEST
            state.pullback_detected_at = state.last_update
            state.pullback_closest_price = current_price
            return True

        return False

    def check_pullback_bounce(self, symbol: str, current_price: float,
                             bounce_threshold_pct: float = 0.0015,
                             previous_price: float = None,
                             current_volume: float = None,
                             avg_volume: float = None,
                             candle_size_pct: float = None,
                             momentum_volume_threshold: float = 2.0,
                             momentum_candle_threshold: float = 0.003) -> tuple:
        """
        Check if price is bouncing off pivot after pullback

        PHASE 5 (Oct 12, 2025) - DYNAMIC PIVOT ADJUSTMENT:
        - Use actual breakout high/low as entry trigger (not scanner level)
        - Use pullback low/high as stop level
        - Aligns entries with real price action, not theoretical levels

        PHASE 4 FILTERS (Oct 12, 2025) - CRITICAL FIX:
        - INCREASED volume requirement: 1.5x → 2.0x (match MOMENTUM)
        - NEW candle size requirement: ≥0.3% (match MOMENTUM)
        - Rising price with momentum confirmation

        WHY: 82.5% of trades failed because PULLBACK_RETEST had weaker
        filters than MOMENTUM. Now both paths require identical strength.

        PREVIOUS FILTERS (Oct 9, 2025):
        - Increased bounce threshold: 0.1% → 0.15%
        - Volume on bounce: Require ≥1.5x average volume
        - Rising price: Price must be increasing when bounce confirms

        Args:
            symbol: Stock symbol
            current_price: Current price
            bounce_threshold_pct: Min bounce % (e.g., 0.0015 = 0.15%, increased from 0.1%)
            previous_price: Previous bar's price (for rising price check)
            current_volume: Current bar volume (for volume filter)
            avg_volume: Average volume (for volume filter)
            candle_size_pct: Candle size as % (for momentum candle check)
            momentum_volume_threshold: Min volume ratio (default 2.0x, matches MOMENTUM)
            momentum_candle_threshold: Min candle size (default 0.3%, matches MOMENTUM)

        Returns:
            tuple: (bounce_confirmed, adjusted_entry_pivot, adjusted_stop)
                - bounce_confirmed: True if bounce confirmed, ready to enter
                - adjusted_entry_pivot: Actual breakout high/low to use as entry trigger
                - adjusted_stop: Pullback low/high to use as stop level
        """
        state = self.get_state(symbol)

        if state.state != BreakoutState.PULLBACK_RETEST:
            return False, None, None

        pivot = state.pivot_price
        closest = state.pullback_closest_price

        # PHASE 5 (Oct 12, 2025): Use actual breakout high/low as new pivot
        # Instead of scanner resistance/support, use the actual price level reached
        # This aligns entries with real price action, not theoretical levels

        # Check if price is moving away from pivot (bouncing)
        if state.side == 'LONG':
            # PHASE 5: Use actual breakout high as entry trigger (not scanner resistance)
            # Entry trigger = highest_since_breakout (the actual breakout high)
            entry_pivot = state.highest_since_breakout if state.highest_since_breakout else pivot

            # For longs, bounce = moving up above the actual breakout high
            if current_price > entry_pivot * (1 + bounce_threshold_pct):

                # PHASE 4 FILTER 1: MOMENTUM-LEVEL Volume (≥2.0x)
                # CRITICAL: Match MOMENTUM entry requirements
                # Previously was 1.5x, now 2.0x to match momentum_volume_threshold
                if current_volume is not None and avg_volume is not None:
                    # Safety check: avoid division by zero
                    if avg_volume == 0:
                        # Can't calculate ratio with zero volume, reject entry
                        return False, None, None
                    volume_ratio = current_volume / avg_volume
                    if volume_ratio < momentum_volume_threshold:
                        # Insufficient volume on bounce (same as MOMENTUM rejection)
                        return False, None, None

                # PHASE 4 FILTER 2: MOMENTUM-LEVEL Candle Size (≥0.3%)
                # NEW: Require strong candle, not just any bounce
                if candle_size_pct is not None:
                    if candle_size_pct < momentum_candle_threshold:
                        # Weak candle on bounce, reject (same as MOMENTUM rejection)
                        return False, None, None

                # PHASE 4 FILTER 3: Bounce Momentum (Rising Price)
                # Price must be rising when bounce confirms
                if previous_price is not None:
                    if current_price <= previous_price:
                        # Price not rising, reject bounce
                        return False, None, None

                # All MOMENTUM-LEVEL filters passed, confirm bounce
                # PHASE 5: Return adjusted entry pivot and stop
                state.state = BreakoutState.READY_TO_ENTER
                state.entry_reason = "PULLBACK_RETEST"
                adjusted_stop = state.pullback_low if state.pullback_low else pivot
                return True, entry_pivot, adjusted_stop

        else:  # SHORT
            # PHASE 5: Use actual breakdown low as entry trigger (not scanner support)
            # Entry trigger = lowest_since_breakout (the actual breakdown low)
            entry_pivot = state.lowest_since_breakout if state.lowest_since_breakout else pivot

            # For shorts, bounce = moving down below the actual breakdown low
            if current_price < entry_pivot * (1 - bounce_threshold_pct):

                # PHASE 4 FILTER 1: MOMENTUM-LEVEL Volume (≥2.0x)
                if current_volume is not None and avg_volume is not None:
                    # Safety check: avoid division by zero
                    if avg_volume == 0:
                        # Can't calculate ratio with zero volume, reject entry
                        return False, None, None
                    volume_ratio = current_volume / avg_volume
                    if volume_ratio < momentum_volume_threshold:
                        return False, None, None

                # PHASE 4 FILTER 2: MOMENTUM-LEVEL Candle Size (≥0.3%)
                if candle_size_pct is not None:
                    if candle_size_pct < momentum_candle_threshold:
                        return False, None, None

                # PHASE 4 FILTER 3: Bounce Momentum (Falling Price)
                if previous_price is not None:
                    if current_price >= previous_price:
                        return False, None, None

                # All MOMENTUM-LEVEL filters passed
                # PHASE 5: Return adjusted entry pivot and stop
                state.state = BreakoutState.READY_TO_ENTER
                state.entry_reason = "PULLBACK_RETEST"
                adjusted_stop = state.pullback_high if state.pullback_high else pivot
                return True, entry_pivot, adjusted_stop

        return False, None, None

    def check_sustained_hold(self, symbol: str, current_price: float,
                            current_bar: int, required_bars: int = 24,
                            max_pullback_pct: float = 0.005,
                            hourly_sma_levels: dict = None,
                            target_price: float = None,
                            current_volume: float = None,
                            avg_volume: float = None,
                            candle_size_pct: float = None,
                            momentum_volume_threshold: float = 2.0,
                            momentum_candle_threshold: float = 0.003,
                            min_room_to_target_pct: float = 0.03) -> bool:
        """
        Check if price has held above/below pivot for required duration

        PHASE 6 (Oct 12, 2025): SUSTAINED_BREAK Momentum Filter
        - Require breaking next SMA level (SMA5, SMA10, SMA20, or Target)
        - Apply momentum filters when breaking (2.0x volume + 0.3% candle)
        - Ensure room to run after breaking next level (≥3%)

        Args:
            symbol: Stock symbol
            current_price: Current price
            current_bar: Current bar index
            required_bars: Bars needed (e.g., 24 = 2 minutes)
            max_pullback_pct: Max pullback allowed (e.g., 0.005 = 0.5%)
            hourly_sma_levels: Dict of hourly SMAs {'sma5': 100.5, 'sma10': 101.0, ...}
            target_price: Scanner target price (for room-to-run check)
            current_volume: Current bar volume (for momentum filter)
            avg_volume: Average volume (for momentum filter)
            candle_size_pct: Candle size % (for momentum filter)
            momentum_volume_threshold: Min volume ratio (default 2.0x)
            momentum_candle_threshold: Min candle size (default 0.3%)
            min_room_to_target_pct: Min room to target after next level (default 3%)

        Returns:
            True if sustained hold confirmed, ready to enter
        """
        state = self.get_state(symbol)

        if state.state != BreakoutState.WEAK_BREAKOUT_TRACKING:
            return False

        # Check if enough time has passed
        if state.sustained_hold_start_bar is None:
            return False

        bars_held = current_bar - state.sustained_hold_start_bar
        state.bars_held_above_pivot = bars_held

        if bars_held < required_bars:
            return False  # Not held long enough yet

        # Check if price stayed above/below pivot (with tolerance)
        pivot = state.pivot_price

        if state.side == 'LONG':
            min_allowed = pivot * (1 - max_pullback_pct)
            if state.lowest_since_breakout < min_allowed:
                # Broke back below pivot - reset
                state.state = BreakoutState.FAILED
                return False
        else:  # SHORT
            max_allowed = pivot * (1 + max_pullback_pct)
            if state.highest_since_breakout > max_allowed:
                # Broke back above pivot - reset
                state.state = BreakoutState.FAILED
                return False

        # PHASE 6 (Oct 12, 2025): Require breaking next SMA level with momentum
        # Only enter if price breaks through next technical level AND shows momentum
        if hourly_sma_levels and target_price:
            # Find next resistance/support level
            next_level = self._find_next_technical_level(
                current_price, hourly_sma_levels, target_price, state.side
            )

            if next_level is None:
                # No next level found (shouldn't happen, but safety check)
                return False

            next_level_price = next_level['price']
            next_level_name = next_level['name']

            # Check if price has broken through next level
            level_broken = False
            if state.side == 'LONG':
                level_broken = current_price > next_level_price
            else:  # SHORT
                level_broken = current_price < next_level_price

            if not level_broken:
                # Price hasn't broken next level yet, keep waiting
                return False

            # PHASE 6 FILTER 1: Momentum Volume (≥2.0x)
            if current_volume is not None and avg_volume is not None:
                if avg_volume == 0:
                    return False  # Safety check
                volume_ratio = current_volume / avg_volume
                if volume_ratio < momentum_volume_threshold:
                    # Weak volume on level break, reject
                    return False

            # PHASE 6 FILTER 2: Momentum Candle (≥0.3%)
            if candle_size_pct is not None:
                if candle_size_pct < momentum_candle_threshold:
                    # Weak candle on level break, reject
                    return False

            # PHASE 6 FILTER 3: Room to Run (≥3% to target)
            if target_price:
                if state.side == 'LONG':
                    room_pct = (target_price - current_price) / current_price
                else:  # SHORT
                    room_pct = (current_price - target_price) / current_price

                if room_pct < min_room_to_target_pct:
                    # Insufficient room to target after breaking next level
                    return False

        # Sustained hold confirmed WITH momentum!
        state.state = BreakoutState.READY_TO_ENTER
        state.entry_reason = "SUSTAINED_BREAK"
        return True

    def _find_next_technical_level(self, current_price: float, hourly_sma_levels: dict,
                                   target_price: float, side: str) -> dict:
        """
        Find the next technical resistance/support level above/below current price.

        For LONG: Find closest level ABOVE current price (SMA5, SMA10, SMA20, TARGET)
        For SHORT: Find closest level BELOW current price (SMA5, SMA10, SMA20, TARGET)

        Args:
            current_price: Current price
            hourly_sma_levels: Dict of hourly SMAs {'sma5': 100.5, 'sma10': 101.0, ...}
            target_price: Scanner target price
            side: 'LONG' or 'SHORT'

        Returns:
            Dict with next level: {'price': 101.5, 'name': 'SMA10'}
            None if no suitable level found
        """
        candidates = []

        # Add SMA levels
        for sma_name, sma_price in hourly_sma_levels.items():
            if sma_price is not None:
                candidates.append({'price': sma_price, 'name': sma_name.upper()})

        # Add target
        if target_price:
            candidates.append({'price': target_price, 'name': 'TARGET1'})

        if side == 'LONG':
            # Find closest level ABOVE current price
            above_levels = [c for c in candidates if c['price'] > current_price]
            if not above_levels:
                return None
            # Return closest (minimum distance)
            return min(above_levels, key=lambda x: x['price'])
        else:  # SHORT
            # Find closest level BELOW current price
            below_levels = [c for c in candidates if c['price'] < current_price]
            if not below_levels:
                return None
            # Return closest (maximum price, smallest distance down)
            return max(below_levels, key=lambda x: x['price'])

    def is_ready_to_enter(self, symbol: str) -> tuple[bool, str, dict]:
        """
        Check if symbol is ready for entry

        Returns:
            (ready, reason, state_dict)
        """
        state = self.get_state(symbol)

        if state.state == BreakoutState.READY_TO_ENTER:
            return True, state.entry_reason, state.to_dict()

        return False, f"State: {state.state.value}", state.to_dict()

    def check_freshness(self, symbol: str, current_bar: int,
                       max_age_bars: int = 600) -> bool:
        """
        Check if breakout is still fresh (not too old)

        Args:
            symbol: Stock symbol
            current_bar: Current bar index
            max_age_bars: Max age in bars (e.g., 600 = 50 minutes)

        Returns:
            True if fresh, False if stale
        """
        state = self.get_state(symbol)

        if state.breakout_bar is None:
            return True  # No breakout yet

        age = current_bar - state.breakout_bar

        if age > max_age_bars:
            # Too old - reset to monitoring
            state.state = BreakoutState.FAILED
            return False

        return True
