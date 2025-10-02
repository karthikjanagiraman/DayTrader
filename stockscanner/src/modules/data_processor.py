"""
Data Processor Module
Computes technical indicators, patterns, and key metrics
Following PS60 requirements exactly
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
# Fix pandas_ta numpy compatibility issue
import numpy
if not hasattr(numpy, 'NaN'):
    numpy.NaN = numpy.nan

import pandas_ta as ta
from loguru import logger


class DataProcessor:
    """Process market data and compute technical indicators"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize data processor

        Args:
            config: Configuration dictionary with indicator settings
        """
        self.config = config
        self.indicators_config = config.get('indicators', {})
        self.filters_config = config.get('filters', {})

    def calculate_gap_percentage(
        self,
        current_price: float,
        previous_close: float
    ) -> float:
        """
        Calculate gap percentage from previous close

        Args:
            current_price: Current pre-market or opening price
            previous_close: Previous day's closing price

        Returns:
            Gap percentage
        """
        if previous_close == 0:
            return 0

        gap_pct = ((current_price - previous_close) / previous_close) * 100
        return round(gap_pct, 2)

    def calculate_relative_volume(
        self,
        current_volume: float,
        avg_volume: float
    ) -> float:
        """
        Calculate relative volume (RVOL)

        Args:
            current_volume: Current period volume
            avg_volume: Average volume for comparison

        Returns:
            RVOL ratio
        """
        if avg_volume == 0:
            return 0

        rvol = current_volume / avg_volume
        return round(rvol, 2)

    def calculate_moving_averages(
        self,
        df: pd.DataFrame,
        periods: List[int] = None
    ) -> pd.DataFrame:
        """
        Calculate simple moving averages for specified periods

        Args:
            df: DataFrame with OHLCV data
            periods: List of periods for SMAs

        Returns:
            DataFrame with added SMA columns
        """
        if periods is None:
            periods = self.indicators_config.get('sma_periods', [5, 10, 20, 50, 100, 200])

        for period in periods:
            if len(df) >= period:
                df[f'SMA_{period}'] = ta.sma(df['close'], length=period)
            else:
                df[f'SMA_{period}'] = np.nan

        return df

    def calculate_bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = None,
        std_dev: float = None
    ) -> pd.DataFrame:
        """
        Calculate Bollinger Bands

        Args:
            df: DataFrame with OHLCV data
            period: Period for moving average
            std_dev: Number of standard deviations

        Returns:
            DataFrame with Bollinger Bands columns
        """
        if period is None:
            period = self.indicators_config.get('bollinger_period', 20)
        if std_dev is None:
            std_dev = self.indicators_config.get('bollinger_std', 2)

        if len(df) >= period:
            bbands = ta.bbands(df['close'], length=period, std=std_dev)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)

        return df

    def calculate_linear_regression(
        self,
        df: pd.DataFrame,
        period: int = None
    ) -> Dict[str, float]:
        """
        Calculate linear regression line for 60-min chart

        Args:
            df: DataFrame with OHLCV data
            period: Period for regression

        Returns:
            Dictionary with regression slope and current value
        """
        if period is None:
            period = self.indicators_config.get('regression_period', 30)

        if len(df) < period:
            return {'slope': 0, 'value': 0}

        # Get last n periods
        recent_data = df['close'].tail(period)
        x = np.arange(len(recent_data))
        y = recent_data.values

        # Calculate linear regression
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]
        current_value = np.polyval(coeffs, len(recent_data) - 1)

        return {
            'slope': round(slope, 4),
            'value': round(current_value, 2)
        }

    def identify_pivot_levels(
        self,
        daily_df: pd.DataFrame,
        current_price: float = None
    ) -> Dict[str, float]:
        """
        Identify pivot levels according to PS60 rules

        Args:
            daily_df: DataFrame with daily OHLCV data
            current_price: Current pre-market price

        Returns:
            Dictionary with pivot high and low
        """
        if len(daily_df) < 2:
            return {'pivot_high': 0, 'pivot_low': 0}

        # Get previous day's data
        prev_day = daily_df.iloc[-2]

        pivot_levels = {
            'pivot_high': prev_day['high'],
            'pivot_low': prev_day['low'],
            'prev_close': prev_day['close']
        }

        # Check if pre-market already exceeded pivot
        if current_price:
            if current_price > pivot_levels['pivot_high']:
                # Pivot already broken, will use first hour high
                pivot_levels['pivot_high_exceeded'] = True
            if current_price < pivot_levels['pivot_low']:
                # Pivot already broken, will use first hour low
                pivot_levels['pivot_low_exceeded'] = True

        return pivot_levels

    def detect_chart_patterns(
        self,
        df: pd.DataFrame,
        lookback_days: int = None
    ) -> Dict[str, Any]:
        """
        Detect chart patterns (bases, consolidations, breakouts)

        Args:
            df: DataFrame with OHLCV data
            lookback_days: Days to look back for pattern detection

        Returns:
            Dictionary with detected patterns
        """
        if lookback_days is None:
            lookback_days = self.filters_config.get('consolidation_days', 5)

        patterns = {
            'base_detected': False,
            'consolidation': False,
            'breakout_pending': False,
            'pattern_description': ''
        }

        if len(df) < lookback_days:
            return patterns

        # Get recent data
        recent = df.tail(lookback_days)

        # Calculate price range
        high_range = recent['high'].max()
        low_range = recent['low'].min()
        price_range = high_range - low_range
        avg_price = recent['close'].mean()

        # Check for base/consolidation (tight range)
        range_pct = (price_range / avg_price) * 100

        if range_pct < 5:  # Tight consolidation
            patterns['consolidation'] = True
            patterns['base_detected'] = True
            patterns['pattern_description'] = f"Tight {lookback_days}-day consolidation between ${low_range:.2f}-${high_range:.2f}"

            # Check if approaching breakout
            last_close = df.iloc[-1]['close']
            if last_close > (high_range * 0.98):  # Within 2% of range high
                patterns['breakout_pending'] = True
                patterns['pattern_description'] += " - approaching breakout"

        # Check for multi-day highs/lows
        if len(df) >= 20:
            twenty_day = df.tail(20)
            if df.iloc[-1]['high'] >= twenty_day['high'].max():
                patterns['pattern_description'] = "At 20-day high"
            elif df.iloc[-1]['low'] <= twenty_day['low'].min():
                patterns['pattern_description'] = "At 20-day low"

        return patterns

    def check_room_to_run(
        self,
        current_price: float,
        df: pd.DataFrame,
        direction: str = 'long'
    ) -> Dict[str, Any]:
        """
        Check for nearby resistance/support (room to run)

        Args:
            current_price: Current stock price
            df: DataFrame with technical indicators
            direction: 'long' or 'short'

        Returns:
            Dictionary with room to run analysis
        """
        room_analysis = {
            'has_room': True,
            'next_level': None,
            'distance_pct': 0,
            'obstacle': None
        }

        if len(df) == 0:
            return room_analysis

        last_row = df.iloc[-1]

        # Check moving averages as resistance/support
        ma_levels = []
        for period in [50, 100, 200]:
            ma_col = f'SMA_{period}'
            if ma_col in last_row and not pd.isna(last_row[ma_col]):
                ma_levels.append((period, last_row[ma_col]))

        if direction == 'long':
            # Find nearest resistance above current price
            resistances = [(p, v) for p, v in ma_levels if v > current_price]
            if resistances:
                resistances.sort(key=lambda x: x[1])
                nearest_period, nearest_level = resistances[0]
                distance_pct = ((nearest_level - current_price) / current_price) * 100

                if distance_pct < self.filters_config.get('room_to_run_pct', 1.0):
                    room_analysis['has_room'] = False
                    room_analysis['obstacle'] = f"{nearest_period}-day SMA"

                room_analysis['next_level'] = nearest_level
                room_analysis['distance_pct'] = round(distance_pct, 2)

        else:  # short
            # Find nearest support below current price
            supports = [(p, v) for p, v in ma_levels if v < current_price]
            if supports:
                supports.sort(key=lambda x: x[1], reverse=True)
                nearest_period, nearest_level = supports[0]
                distance_pct = ((current_price - nearest_level) / current_price) * 100

                if distance_pct < self.filters_config.get('room_to_run_pct', 1.0):
                    room_analysis['has_room'] = False
                    room_analysis['obstacle'] = f"{nearest_period}-day SMA"

                room_analysis['next_level'] = nearest_level
                room_analysis['distance_pct'] = round(distance_pct, 2)

        return room_analysis

    def calculate_average_volume(
        self,
        df: pd.DataFrame,
        lookback_days: int = None
    ) -> float:
        """
        Calculate average volume over lookback period

        Args:
            df: DataFrame with volume data
            lookback_days: Number of days to average

        Returns:
            Average volume
        """
        if lookback_days is None:
            lookback_days = self.indicators_config.get('volume_lookback_days', 20)

        if len(df) < lookback_days:
            return df['volume'].mean() if len(df) > 0 else 0

        return df.tail(lookback_days)['volume'].mean()

    def process_stock_data(
        self,
        symbol: str,
        daily_df: pd.DataFrame,
        intraday_df: Optional[pd.DataFrame],
        quote: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process all data for a single stock

        Args:
            symbol: Stock ticker symbol
            daily_df: Daily OHLCV data
            intraday_df: 60-minute OHLCV data
            quote: Current quote data

        Returns:
            Dictionary with all processed metrics
        """
        try:
            processed = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'valid': False
            }

            if daily_df is None or len(daily_df) < 2:
                logger.warning(f"Insufficient daily data for {symbol}")
                return processed

            # Calculate moving averages
            daily_df = self.calculate_moving_averages(daily_df)

            # Calculate Bollinger Bands
            daily_df = self.calculate_bollinger_bands(daily_df)

            # Get pivot levels
            current_price = quote.get('last', daily_df.iloc[-1]['close'])
            pivots = self.identify_pivot_levels(daily_df, current_price)

            # Calculate gap percentage
            gap_pct = self.calculate_gap_percentage(
                current_price,
                pivots['prev_close']
            )

            # Calculate RVOL
            avg_volume = self.calculate_average_volume(daily_df)
            current_volume = quote.get('volume', 0)
            rvol = self.calculate_relative_volume(current_volume, avg_volume)

            # Detect patterns
            patterns = self.detect_chart_patterns(daily_df)

            # Check room to run
            direction = 'long' if gap_pct > 0 else 'short'
            room_analysis = self.check_room_to_run(current_price, daily_df, direction)

            # Process intraday data if available
            intraday_metrics = {}
            if intraday_df is not None and len(intraday_df) > 0:
                regression = self.calculate_linear_regression(intraday_df)
                intraday_metrics = {
                    'regression_slope': regression['slope'],
                    'regression_value': regression['value']
                }

            # Compile all metrics
            processed.update({
                'valid': True,
                'current_price': current_price,
                'prev_close': pivots['prev_close'],
                'pivot_high': pivots['pivot_high'],
                'pivot_low': pivots['pivot_low'],
                'gap_pct': gap_pct,
                'volume': current_volume,
                'avg_volume': avg_volume,
                'rvol': rvol,
                'patterns': patterns,
                'room_analysis': room_analysis,
                'daily_high': daily_df.iloc[-1]['high'],
                'daily_low': daily_df.iloc[-1]['low'],
                'sma_50': daily_df.iloc[-1].get('SMA_50'),
                'sma_200': daily_df.iloc[-1].get('SMA_200'),
                **intraday_metrics
            })

            return processed

        except Exception as e:
            logger.error(f"Error processing data for {symbol}: {e}")
            return {'symbol': symbol, 'valid': False, 'error': str(e)}