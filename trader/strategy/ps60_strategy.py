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

        # Exit rules
        self.partial_1_pct = self.trading_config['exits']['partial_1_pct']
        self.partial_1_gain = self.trading_config['exits']['partial_1_gain']
        self.partial_2_pct = self.trading_config['exits'].get('partial_2_pct', 0.25)
        self.runner_pct = self.trading_config['exits'].get('runner_pct', 0.25)

        self.eod_close_time = self._parse_time(
            self.trading_config['exits']['eod_close_time']
        )

        # Risk management
        self.five_minute_rule = self.trading_config['risk']['five_minute_rule']
        self.five_minute_threshold = self.trading_config['risk'].get('five_minute_threshold', 7)
        self.five_minute_min_gain = self.trading_config['risk'].get('five_minute_min_gain', 0.10)

        self.breakeven_after_partial = self.trading_config['risk']['breakeven_after_partial']
        self.stop_at_pivot = self.trading_config['risk']['stop_at_pivot']

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

    def _parse_time(self, time_str):
        """Parse time string to time object"""
        return datetime.strptime(time_str, '%H:%M').time()

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

    def should_enter_long(self, stock_data, current_price, attempt_count=0):
        """
        Check if should enter long position

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            attempt_count: Number of previous attempts on this pivot

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

        # Check gap filter (skip if gap ate up the move)
        should_skip, reason = self._check_gap_filter(stock_data, current_price, side='LONG')
        if should_skip:
            return False, reason

        return True, "Resistance broken"

    def should_enter_short(self, stock_data, current_price, attempt_count=0):
        """
        Check if should enter short position

        Args:
            stock_data: Scanner data dict
            current_price: Current price
            attempt_count: Number of previous attempts on this pivot

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

        # Check gap filter (skip if gap ate up the move)
        should_skip, reason = self._check_gap_filter(stock_data, current_price, side='SHORT')
        if should_skip:
            return False, reason

        return True, "Support broken"

    def check_five_minute_rule(self, position, current_price, current_time):
        """
        Check if 5-7 minute rule should trigger exit

        ORIGINAL LOGIC (REVERTED): Exit if no favorable movement within 5-7 min

        Args:
            position: Position dict with entry_time, entry_price, side
            current_price: Current price
            current_time: Current datetime

        Returns:
            (bool, reason) - Should exit, and reason
        """
        if not self.five_minute_rule:
            return False, None

        # CRITICAL: Only apply 5-minute rule if NO partials taken yet
        # If we've taken partials (remaining < 1.0), let the runner work
        if position.get('remaining', 1.0) < 1.0:
            return False, None

        # Calculate time in trade
        time_in_trade = (current_time - position['entry_time']).total_seconds() / 60

        # Only check at threshold (default 7 minutes)
        if time_in_trade < self.five_minute_threshold:
            return False, None

        entry_price = position['entry_price']

        # Calculate gain
        if position['side'] == 'LONG':
            gain = current_price - entry_price
        else:
            gain = entry_price - current_price

        # Exit if gain is less than minimum required gain
        if gain < self.five_minute_min_gain:
            return True, "5MIN_RULE"

        return False, None

    def should_take_partial(self, position, current_price):
        """
        Check if should take partial profit

        Returns:
            (bool, pct, reason) - Should take partial, what %, and reason
        """
        entry_price = position['entry_price']
        side = position['side']
        remaining = position['remaining']
        partials_taken = len(position['partials'])

        # Calculate current gain
        if side == 'LONG':
            gain = current_price - entry_price
        else:
            gain = entry_price - current_price

        # First partial (50%)
        if remaining == 1.0 and gain >= self.partial_1_gain:
            return True, self.partial_1_pct, 'FIRST_MOVE'

        # Second partial (25% at target1) - only if we took first partial
        if remaining == 0.5 and partials_taken == 1:
            # Check if at target1 (from scanner)
            if side == 'LONG':
                target1 = position.get('target1', entry_price + 1.0)
                if current_price >= target1:
                    # Calculate pct relative to remaining (25% of original = 50% of remaining)
                    return True, 0.50, 'TARGET1'
            else:
                target1 = position.get('target1', entry_price - 1.0)
                if current_price <= target1:
                    return True, 0.50, 'TARGET1'

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
