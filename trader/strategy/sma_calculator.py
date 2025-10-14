#!/usr/bin/env python3
"""
SMA Calculator Module for Progressive Partial Profit System

This module calculates Simple Moving Average (SMA) levels from IBKR historical
bars to use as technical exit levels for partial profit taking.

Key Features:
- Fetch hourly or daily historical bars from IBKR
- Calculate SMA5, SMA10, SMA20 from bar closes
- Cache results to minimize API calls
- Handle errors gracefully (missing data, connection issues)

Usage:
    from ib_insync import IB
    from sma_calculator import SMACalculator

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)

    calc = SMACalculator(ib)
    levels = calc.get_sma_levels('AAPL', periods=[5, 10, 20], timeframe='1 hour')

    print(f"SMA5:  ${levels['sma5']:.2f}")
    print(f"SMA10: ${levels['sma10']:.2f}")
    print(f"SMA20: ${levels['sma20']:.2f}")

Dependencies:
- ib_insync: IBKR API wrapper
- statistics: For mean calculation

Author: Claude
Date: October 12, 2025
Version: 1.0
"""

from ib_insync import IB, Stock
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics
import logging

# Setup module logger
logger = logging.getLogger(__name__)


class SMACalculator:
    """
    Calculate Simple Moving Average levels from IBKR historical bars.

    This class fetches historical bars from IBKR and calculates SMA values
    for use as technical exit levels in the progressive partial system.

    Attributes:
        ib: IBKR connection object (ib_insync.IB)
        cache: Dict storing cached SMA results {symbol: {timestamp, data}}
        cache_duration_sec: How long to cache results (default: 300 sec = 5 min)

    Example:
        >>> ib = IB()
        >>> ib.connect('127.0.0.1', 7497, clientId=1)
        >>> calc = SMACalculator(ib)
        >>>
        >>> # Get hourly SMAs
        >>> levels = calc.get_sma_levels('TSLA', timeframe='1 hour')
        >>> print(levels)
        {'sma5': 245.67, 'sma10': 243.21, 'sma20': 240.89}
        >>>
        >>> # Get daily SMAs
        >>> levels = calc.get_sma_levels('AAPL', timeframe='1 day')
        >>> print(levels)
        {'sma5': 150.45, 'sma10': 148.92, 'sma20': 147.33}
    """

    def __init__(self, ib_connection: IB, cache_duration_sec: int = 300):
        """
        Initialize SMA calculator with IBKR connection.

        Args:
            ib_connection: Active IB() connection object
            cache_duration_sec: Cache lifetime in seconds (default: 300 = 5 min)

        Raises:
            ValueError: If ib_connection is not connected
        """
        if not ib_connection.isConnected():
            raise ValueError("IBKR connection must be connected before creating SMACalculator")

        self.ib = ib_connection
        self.cache = {}  # {symbol: {'timestamp': datetime, 'data': {sma5: ...}}}
        self.cache_duration_sec = cache_duration_sec

        logger.info(f"SMACalculator initialized (cache: {cache_duration_sec}s)")

    def get_sma_levels(
        self,
        symbol: str,
        periods: List[int] = [5, 10, 20],
        timeframe: str = '1 hour'
    ) -> Optional[Dict[str, float]]:
        """
        Calculate SMA levels for given symbol and timeframe.

        This is the main entry point for getting SMA levels. It handles:
        - Cache lookup (returns cached if fresh)
        - Bar fetching from IBKR
        - SMA calculation
        - Error handling

        Args:
            symbol: Stock ticker (e.g., 'AAPL', 'TSLA')
            periods: List of SMA periods to calculate (default: [5, 10, 20])
            timeframe: Bar timeframe - '1 hour' or '1 day' (default: '1 hour')

        Returns:
            Dict of SMA values: {'sma5': 150.45, 'sma10': 148.92, 'sma20': 147.33}
            Returns None if calculation fails (insufficient data, API error, etc.)

        Example:
            >>> calc = SMACalculator(ib)
            >>> levels = calc.get_sma_levels('AAPL', periods=[5, 10], timeframe='1 hour')
            >>> if levels:
            >>>     print(f"SMA5: ${levels['sma5']:.2f}")
            >>> else:
            >>>     print("Failed to calculate SMAs")

        Edge Cases:
            - Returns None if insufficient bars for largest period
            - Returns None if IBKR API call fails
            - Skips specific periods if insufficient data for that period
            - Returns cached result if fresh (within cache_duration_sec)
        """
        # Check cache first
        cached = self._get_cached_sma(symbol)
        if cached is not None:
            logger.debug(f"Using cached SMA for {symbol}")
            return cached

        logger.info(f"Calculating SMA for {symbol} (timeframe: {timeframe})")

        # Fetch historical bars
        max_period = max(periods)
        bars = self._fetch_bars(symbol, timeframe, lookback_periods=max_period)

        if not bars or len(bars) < max_period:
            logger.warning(
                f"Insufficient bars for {symbol}: got {len(bars) if bars else 0}, "
                f"need {max_period}"
            )
            return None

        # Calculate SMAs
        sma_levels = self._calculate_smas(bars, periods)

        if not sma_levels:
            logger.warning(f"Failed to calculate any SMAs for {symbol}")
            return None

        # Cache the result
        self._cache_sma(symbol, sma_levels)

        logger.info(
            f"Calculated SMAs for {symbol}: "
            f"{', '.join([f'{k}=${v:.2f}' for k, v in sma_levels.items()])}"
        )

        return sma_levels

    def _fetch_bars(
        self,
        symbol: str,
        timeframe: str,
        lookback_periods: int
    ) -> Optional[List]:
        """
        Fetch historical bars from IBKR API.

        Args:
            symbol: Stock ticker
            timeframe: '1 hour' or '1 day'
            lookback_periods: Number of periods to fetch (e.g., 20 for SMA20)

        Returns:
            List of bar objects with .close attribute
            Returns None if fetch fails

        Implementation Notes:
            - Adds buffer periods to lookback to account for gaps/holidays
            - For hourly: Fetches (periods + 5) days to ensure enough bars
            - For daily: Fetches (periods + 10) days to ensure enough bars
            - Uses RTH (Regular Trading Hours) only
            - Handles IBKR API errors gracefully

        Example:
            >>> bars = calc._fetch_bars('AAPL', '1 hour', lookback_periods=20)
            >>> print(f"Fetched {len(bars)} hourly bars")
            >>> print(f"Last close: ${bars[-1].close:.2f}")
        """
        # Create contract
        contract = Stock(symbol, 'SMART', 'USD')

        # Map timeframe to IBKR bar size and duration
        if timeframe == '1 hour':
            bar_size = '1 hour'
            # Need enough days to get required hourly bars
            # ~6.5 trading hours per day, so add buffer
            duration_days = lookback_periods + 5
            duration = f'{duration_days} D'
        elif timeframe == '1 day':
            bar_size = '1 day'
            # Daily bars: Add buffer for weekends/holidays
            duration_days = lookback_periods + 10
            duration = f'{duration_days} D'
        else:
            logger.error(f"Unsupported timeframe: {timeframe}")
            return None

        logger.debug(
            f"Fetching {symbol} bars: size={bar_size}, duration={duration}, "
            f"lookback={lookback_periods}"
        )

        try:
            # Request historical data from IBKR
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',  # Current time
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',  # Trade prices
                useRTH=True,  # Regular trading hours only (9:30-16:00 ET)
                formatDate=1,  # Unix timestamp format
                keepUpToDate=False  # One-time request, not streaming
            )

            if not bars:
                logger.warning(f"No bars returned for {symbol}")
                return None

            logger.debug(f"Fetched {len(bars)} bars for {symbol}")
            return bars

        except Exception as e:
            logger.error(f"Error fetching bars for {symbol}: {e}")
            return None

    def _calculate_smas(
        self,
        bars: List,
        periods: List[int]
    ) -> Dict[str, float]:
        """
        Calculate SMA values from bar data.

        Args:
            bars: List of bar objects with .close attribute
            periods: List of periods to calculate (e.g., [5, 10, 20])

        Returns:
            Dict of SMA values: {'sma5': 150.45, 'sma10': 148.92}
            Empty dict if no SMAs could be calculated

        Algorithm:
            1. Extract close prices from bars
            2. For each period:
               a. Check if enough bars available
               b. Take last N closes
               c. Calculate mean
               d. Round to 2 decimals
            3. Return dict with sma{period} keys

        Example:
            >>> bars = fetch_bars('AAPL', '1 hour', 20)
            >>> smas = calc._calculate_smas(bars, periods=[5, 10, 20])
            >>> print(smas)
            {'sma5': 150.45, 'sma10': 148.92, 'sma20': 147.33}

        Edge Cases:
            - Skips periods where len(bars) < period
            - Handles bars with None close prices
            - Returns empty dict if no SMAs calculated
        """
        if not bars:
            return {}

        # Extract close prices
        closes = [bar.close for bar in bars if bar.close is not None]

        if not closes:
            logger.warning("No valid close prices in bars")
            return {}

        sma_levels = {}

        # Calculate each SMA period
        for period in periods:
            if len(closes) < period:
                logger.warning(
                    f"Insufficient data for SMA{period}: "
                    f"got {len(closes)} bars, need {period}"
                )
                continue

            # Take last N closes and calculate mean
            period_closes = closes[-period:]
            sma_value = statistics.mean(period_closes)

            # Round to 2 decimals (price precision)
            sma_levels[f'sma{period}'] = round(sma_value, 2)

            logger.debug(f"SMA{period} = ${sma_value:.2f} (from {len(period_closes)} bars)")

        return sma_levels

    def _get_cached_sma(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Retrieve cached SMA data if still fresh.

        Args:
            symbol: Stock ticker

        Returns:
            Cached SMA dict if fresh, None if expired or not found

        Cache Structure:
            cache[symbol] = {
                'timestamp': datetime object,
                'data': {'sma5': 150.45, 'sma10': 148.92, ...}
            }

        Cache Logic:
            - Returns data if (now - timestamp) < cache_duration_sec
            - Returns None if expired (time to refresh)
            - Returns None if symbol not in cache
        """
        if symbol not in self.cache:
            return None

        cached_entry = self.cache[symbol]
        age_seconds = (datetime.now() - cached_entry['timestamp']).total_seconds()

        if age_seconds < self.cache_duration_sec:
            logger.debug(f"Cache HIT for {symbol} (age: {age_seconds:.1f}s)")
            return cached_entry['data']
        else:
            logger.debug(f"Cache EXPIRED for {symbol} (age: {age_seconds:.1f}s)")
            return None

    def _cache_sma(self, symbol: str, sma_data: Dict[str, float]):
        """
        Store SMA data in cache with timestamp.

        Args:
            symbol: Stock ticker
            sma_data: SMA dict to cache

        Side Effects:
            Updates self.cache[symbol] with current timestamp and data
        """
        self.cache[symbol] = {
            'timestamp': datetime.now(),
            'data': sma_data
        }
        logger.debug(f"Cached SMA for {symbol}")

    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear cached SMA data.

        Args:
            symbol: Specific symbol to clear, or None to clear all

        Example:
            >>> # Clear specific symbol
            >>> calc.clear_cache('AAPL')
            >>>
            >>> # Clear all cached data
            >>> calc.clear_cache()
        """
        if symbol:
            if symbol in self.cache:
                del self.cache[symbol]
                logger.info(f"Cleared cache for {symbol}")
        else:
            self.cache.clear()
            logger.info("Cleared all cached SMAs")

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dict with cache stats: {
                'size': 5,
                'symbols': ['AAPL', 'TSLA', ...],
                'oldest_age_sec': 245,
                'newest_age_sec': 12
            }

        Useful for:
            - Monitoring cache effectiveness
            - Debugging cache issues
            - Performance tuning
        """
        if not self.cache:
            return {'size': 0, 'symbols': [], 'oldest_age_sec': None, 'newest_age_sec': None}

        now = datetime.now()
        ages = [(now - entry['timestamp']).total_seconds() for entry in self.cache.values()]

        return {
            'size': len(self.cache),
            'symbols': list(self.cache.keys()),
            'oldest_age_sec': max(ages) if ages else None,
            'newest_age_sec': min(ages) if ages else None
        }


# Module-level convenience function
def calculate_sma_from_bars(bars: List, period: int) -> Optional[float]:
    """
    Calculate a single SMA from bars (no IBKR connection needed).

    This is a standalone utility function for calculating SMA when you already
    have the bars loaded (e.g., from backtesting).

    Args:
        bars: List of bar objects with .close attribute
        period: SMA period (e.g., 5, 10, 20)

    Returns:
        SMA value rounded to 2 decimals, or None if insufficient data

    Example:
        >>> # In backtester where bars are already loaded
        >>> from sma_calculator import calculate_sma_from_bars
        >>>
        >>> sma20 = calculate_sma_from_bars(bars, period=20)
        >>> if sma20:
        >>>     print(f"SMA20: ${sma20:.2f}")

    Edge Cases:
        - Returns None if bars is empty or None
        - Returns None if len(bars) < period
        - Skips bars with None close prices
        - Returns None if no valid closes after filtering
    """
    if not bars or len(bars) < period:
        return None

    # Extract close prices, filter None values
    closes = [bar.close for bar in bars[-period:] if bar.close is not None]

    if len(closes) < period:
        return None

    # Calculate mean and round
    return round(statistics.mean(closes), 2)
