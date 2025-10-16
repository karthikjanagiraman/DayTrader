"""
Stochastic Oscillator Calculator (21, 1, 3) for Hourly Bars

Calculates stochastic momentum indicator using IBKR historical hourly data.
Used as entry confirmation filter in PS60 strategy.

Created: October 15, 2025
"""

from ib_insync import Stock, util
import pandas as pd
from datetime import datetime, timedelta


class StochasticCalculator:
    """
    Calculate Stochastic (21, 1, 3) for hourly bars
    Used as entry confirmation filter in PS60 strategy

    User Requirements (Oct 15, 2025):
    - LONG entries: Stochastic %K between 60-80
    - SHORT entries: Stochastic %K between 20-50
    """

    def __init__(self, ib_connection, k_period=21, k_smooth=1, d_smooth=3, cache_duration_sec=3600):
        """
        Initialize Stochastic Calculator

        Args:
            ib_connection: Active IB connection object
            k_period: Lookback period for %K (default: 21)
            k_smooth: Smoothing period for %K (default: 1, no smoothing)
            d_smooth: Smoothing period for %D (default: 3)
            cache_duration_sec: Cache duration in seconds (default: 3600 = 1 hour)
        """
        self.ib = ib_connection
        self.k_period = k_period
        self.k_smooth = k_smooth
        self.d_smooth = d_smooth
        self.cache = {}  # Cache results: {symbol: (result, timestamp)}
        self.cache_duration = cache_duration_sec

    def _calculate_stochastic(self, df):
        """
        Calculate stochastic values on DataFrame

        Formula:
        %K = (Close - Lowest Low) / (Highest High - Lowest Low) × 100
        %D = SMA(%K, d_smooth)

        Args:
            df: DataFrame with 'high', 'low', 'close' columns

        Returns:
            DataFrame with '%K' and '%D' columns added
        """
        # Step 1: Calculate rolling highest high and lowest low
        df['highest_high'] = df['high'].rolling(window=self.k_period).max()
        df['lowest_low'] = df['low'].rolling(window=self.k_period).min()

        # Step 2: Calculate raw %K
        df['%K_raw'] = (
            (df['close'] - df['lowest_low']) /
            (df['highest_high'] - df['lowest_low']) * 100
        )

        # Handle division by zero (when highest_high == lowest_low)
        df['%K_raw'].fillna(50.0, inplace=True)  # Neutral value

        # Step 3: Smooth %K if k_smooth > 1
        if self.k_smooth > 1:
            df['%K'] = df['%K_raw'].rolling(window=self.k_smooth).mean()
        else:
            df['%K'] = df['%K_raw']  # No smoothing

        # Step 4: Calculate %D (moving average of %K)
        df['%D'] = df['%K'].rolling(window=self.d_smooth).mean()

        # Clean up intermediate columns
        df.drop(columns=['highest_high', 'lowest_low', '%K_raw'], inplace=True)

        return df

    def get_stochastic(self, symbol):
        """
        Get current stochastic values with caching

        Args:
            symbol: Stock symbol (e.g., 'TSLA')

        Returns:
            dict: {'%K': float, '%D': float, 'timestamp': datetime}
            None if calculation fails
        """
        now = datetime.now()

        # Check cache
        if symbol in self.cache:
            cached_data, cached_time = self.cache[symbol]
            if (now - cached_time).total_seconds() < self.cache_duration:
                return cached_data

        # Fetch fresh data from IBKR
        try:
            contract = Stock(symbol, 'SMART', 'USD')

            # Fetch enough hourly bars for calculation
            # Need k_period + d_smooth + buffer = 21 + 3 + 10 = 34+ bars
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',  # Current time
                durationStr='10 D',  # Get 10 days to ensure 50+ hourly bars
                barSizeSetting='1 hour',  # Hourly bars
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )

            if not bars or len(bars) < self.k_period + self.d_smooth:
                print(f"⚠️  Insufficient bars for {symbol}: got {len(bars) if bars else 0}, need {self.k_period + self.d_smooth}")
                return None

            # Convert to DataFrame
            df = util.df(bars)

            # Calculate stochastic
            df = self._calculate_stochastic(df)

            # Get current values (most recent bar)
            current_k = df['%K'].iloc[-1]
            current_d = df['%D'].iloc[-1]

            # Handle NaN values
            if pd.isna(current_k) or pd.isna(current_d):
                print(f"⚠️  NaN stochastic values for {symbol}")
                return None

            result = {
                '%K': round(float(current_k), 2),
                '%D': round(float(current_d), 2),
                'timestamp': now
            }

            # Cache result
            self.cache[symbol] = (result, now)

            return result

        except Exception as e:
            print(f"⚠️  Failed to calculate stochastic for {symbol}: {e}")
            return None

    def check_stochastic_filter(self, symbol, side='LONG'):
        """
        Check if stochastic confirms entry based on user requirements

        User Requirements (Oct 15, 2025):
        - LONG entries: %K between 60-80 (momentum zone, not overbought)
        - SHORT entries: %K between 20-50 (momentum zone, not oversold)

        Args:
            symbol: Stock symbol
            side: 'LONG' or 'SHORT'

        Returns:
            tuple: (bool: passes_filter, str: reason)
        """
        stoch = self.get_stochastic(symbol)

        if stoch is None:
            # If we can't calculate stochastic, allow entry (don't block)
            return True, "Stochastic unavailable (allowed)"

        k = stoch['%K']
        d = stoch['%D']

        if side == 'LONG':
            # LONG requirement: %K between 60-80
            if k < 60:
                return False, f"Stochastic too low for LONG (K={k:.1f}, need 60-80)"
            elif k > 80:
                return False, f"Stochastic overbought for LONG (K={k:.1f}, need 60-80)"
            else:
                return True, f"Stochastic confirmed (K={k:.1f}, D={d:.1f})"

        elif side == 'SHORT':
            # SHORT requirement: %K between 20-50
            if k < 20:
                return False, f"Stochastic oversold for SHORT (K={k:.1f}, need 20-50)"
            elif k > 50:
                return False, f"Stochastic too high for SHORT (K={k:.1f}, need 20-50)"
            else:
                return True, f"Stochastic confirmed (K={k:.1f}, D={d:.1f})"

        else:
            return False, f"Invalid side: {side}"

    def is_overbought(self, symbol, threshold=80):
        """Check if symbol is overbought"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] > threshold

    def is_oversold(self, symbol, threshold=20):
        """Check if symbol is oversold"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] < threshold

    def has_bullish_momentum(self, symbol):
        """Check if %K > %D (bullish momentum)"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] > stoch['%D']

    def has_bearish_momentum(self, symbol):
        """Check if %K < %D (bearish momentum)"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] < stoch['%D']

    def clear_cache(self):
        """Clear all cached stochastic values"""
        self.cache = {}

    def get_cache_status(self):
        """Get cache statistics"""
        return {
            'cached_symbols': len(self.cache),
            'symbols': list(self.cache.keys())
        }
