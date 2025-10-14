"""
Volatility Fetcher - Get real-time ATR and volatility metrics from IBKR

This module fetches real-time or recent volatility data from IBKR when:
- Scanner data is missing ATR
- We need updated volatility for intraday position management
- We want to verify scanner's ATR calculations
"""

from ib_insync import Stock, util
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz


class VolatilityFetcher:
    """Fetch and calculate volatility metrics from IBKR"""

    def __init__(self, ib_connection):
        """
        Initialize with existing IB connection

        Args:
            ib_connection: Active IB() instance
        """
        self.ib = ib_connection

    def calculate_atr(self, bars, period=14):
        """
        Calculate Average True Range from bars

        Args:
            bars: List of BarData objects from IBKR
            period: ATR period (default 14)

        Returns:
            float: ATR value
        """
        if not bars or len(bars) < period:
            return None

        # Convert to pandas for easier calculation
        df = util.df(bars)

        # Calculate True Range
        df['h-l'] = df['high'] - df['low']
        df['h-pc'] = abs(df['high'] - df['close'].shift(1))
        df['l-pc'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)

        # Calculate ATR (exponential moving average of TR)
        atr = df['tr'].ewm(span=period, adjust=False).mean().iloc[-1]

        return atr

    def get_atr_percentage(self, symbol, price=None):
        """
        Get ATR as percentage of current price

        Args:
            symbol: Stock symbol
            price: Current price (optional, will fetch if not provided)

        Returns:
            dict: {'atr': absolute ATR, 'atr%': ATR as percentage, 'price': current price}
        """
        try:
            contract = Stock(symbol, 'SMART', 'USD')

            # Get daily bars for ATR calculation
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',  # Current time
                durationStr='30 D',  # 30 days of data
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                return None

            # Calculate ATR
            atr = self.calculate_atr(bars, period=14)

            # Get current price if not provided
            if price is None:
                price = bars[-1].close

            # Calculate ATR percentage
            atr_pct = (atr / price) * 100 if price > 0 else 0

            return {
                'atr': atr,
                'atr%': atr_pct,
                'price': price,
                'last_updated': datetime.now()
            }

        except Exception as e:
            print(f"Error fetching ATR for {symbol}: {e}")
            return None

    def get_intraday_volatility(self, symbol, minutes=60):
        """
        Get intraday volatility from recent minute bars

        Args:
            symbol: Stock symbol
            minutes: Number of minutes to analyze (default 60)

        Returns:
            dict: Volatility metrics including range, std dev, etc.
        """
        try:
            contract = Stock(symbol, 'SMART', 'USD')

            # Get minute bars
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=f'{minutes} M',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars or len(bars) < 10:
                return None

            df = util.df(bars)

            # Calculate various volatility metrics
            high = df['high'].max()
            low = df['low'].min()
            current = df['close'].iloc[-1]
            open_price = df['open'].iloc[0]

            # Intraday range
            range_pct = ((high - low) / low) * 100 if low > 0 else 0

            # Standard deviation of returns
            df['returns'] = df['close'].pct_change()
            volatility = df['returns'].std() * np.sqrt(390)  # Annualized

            # Average bar range
            df['bar_range'] = (df['high'] - df['low']) / df['close']
            avg_bar_range_pct = df['bar_range'].mean() * 100

            return {
                'symbol': symbol,
                'current_price': current,
                'intraday_high': high,
                'intraday_low': low,
                'intraday_range%': range_pct,
                'volatility_1hr': volatility * 100,  # As percentage
                'avg_bar_range%': avg_bar_range_pct,
                'bars_analyzed': len(bars),
                'timestamp': datetime.now()
            }

        except Exception as e:
            print(f"Error fetching intraday volatility for {symbol}: {e}")
            return None

    def get_historical_volatility(self, symbol, days=20):
        """
        Calculate historical volatility over N days

        Args:
            symbol: Stock symbol
            days: Number of days to analyze (default 20)

        Returns:
            dict: Historical volatility metrics
        """
        try:
            contract = Stock(symbol, 'SMART', 'USD')

            # Get daily bars
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=f'{days + 10} D',  # Extra days for calculations
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars or len(bars) < days:
                return None

            df = util.df(bars)

            # Calculate daily returns
            df['returns'] = df['close'].pct_change()

            # Historical volatility (standard deviation of returns)
            hist_vol = df['returns'].tail(days).std() * np.sqrt(252)  # Annualized

            # Average daily range
            df['daily_range'] = (df['high'] - df['low']) / df['close']
            avg_daily_range = df['daily_range'].tail(days).mean() * 100

            # Max daily move
            max_move = df['returns'].tail(days).abs().max() * 100

            return {
                'symbol': symbol,
                'historical_volatility': hist_vol * 100,  # As percentage
                'avg_daily_range%': avg_daily_range,
                'max_daily_move%': max_move,
                'days_analyzed': days,
                'current_price': df['close'].iloc[-1],
                'timestamp': datetime.now()
            }

        except Exception as e:
            print(f"Error calculating historical volatility for {symbol}: {e}")
            return None

    def enrich_scanner_data(self, scanner_data):
        """
        Add real-time volatility data to scanner results

        Args:
            scanner_data: List of scanner results (dicts)

        Returns:
            List of enriched scanner data with volatility metrics
        """
        enriched = []

        for stock in scanner_data:
            symbol = stock['symbol']

            # Skip if ATR already present and recent
            if 'atr%' in stock and stock.get('atr%', 0) > 0:
                enriched.append(stock)
                continue

            # Fetch ATR from IBKR
            atr_data = self.get_atr_percentage(symbol, stock.get('close'))

            if atr_data:
                # Add ATR data to stock dict
                stock['atr%'] = atr_data['atr%']
                stock['atr'] = atr_data['atr']
                stock['atr_source'] = 'IBKR_realtime'
                print(f"Added ATR for {symbol}: {atr_data['atr%']:.2f}%")
            else:
                # Use default if fetch failed
                stock['atr%'] = 5.0  # Conservative default
                stock['atr_source'] = 'default'
                print(f"Using default ATR for {symbol}: 5.0%")

            enriched.append(stock)

        return enriched


def calculate_stop_with_volatility(entry_price, side, volatility_data):
    """
    Calculate stop price based on volatility metrics

    Args:
        entry_price: Entry price for the position
        side: 'LONG' or 'SHORT'
        volatility_data: Dict with volatility metrics

    Returns:
        dict: Stop price and calculation details
    """
    atr_pct = volatility_data.get('atr%', 5.0)

    # Use our proven formula
    if atr_pct < 2.0:
        stop_width = 0.007  # 0.7%
    elif atr_pct < 4.0:
        stop_width = 0.012  # 1.2%
    elif atr_pct < 6.0:
        stop_width = 0.018  # 1.8%
    else:
        stop_width = 0.025  # 2.5%

    if side == 'LONG':
        stop_price = entry_price * (1 - stop_width)
    else:  # SHORT
        stop_price = entry_price * (1 + stop_width)

    return {
        'stop_price': stop_price,
        'stop_width%': stop_width * 100,
        'atr%': atr_pct,
        'stop_distance': abs(entry_price - stop_price),
        'calculation': f"ATR {atr_pct:.1f}% → Stop {stop_width*100:.1f}%"
    }


# Example usage
if __name__ == "__main__":
    from ib_insync import IB

    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=5000)

    # Create fetcher
    fetcher = VolatilityFetcher(ib)

    # Test with a stock
    symbol = 'AAPL'

    # Get ATR
    atr_data = fetcher.get_atr_percentage(symbol)
    print(f"\nATR for {symbol}:")
    print(f"  ATR: ${atr_data['atr']:.2f}")
    print(f"  ATR%: {atr_data['atr%']:.2f}%")

    # Get intraday volatility
    intraday = fetcher.get_intraday_volatility(symbol)
    print(f"\nIntraday volatility for {symbol}:")
    print(f"  Range: {intraday['intraday_range%']:.2f}%")
    print(f"  Avg bar range: {intraday['avg_bar_range%']:.3f}%")

    # Calculate stop
    stop_info = calculate_stop_with_volatility(
        entry_price=intraday['current_price'],
        side='LONG',
        volatility_data=atr_data
    )
    print(f"\nStop calculation:")
    print(f"  Entry: ${intraday['current_price']:.2f}")
    print(f"  Stop: ${stop_info['stop_price']:.2f}")
    print(f"  Width: {stop_info['stop_width%']:.1f}%")
    print(f"  Calculation: {stop_info['calculation']}")

    ib.disconnect()