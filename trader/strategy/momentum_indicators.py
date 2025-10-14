"""
Momentum Indicators for PS60 Strategy

Provides RSI and MACD calculations optimized for intraday breakout trading.
Fetches 5-minute bars directly from IBKR API.
"""

import numpy as np
from datetime import datetime, timedelta


def fetch_bars(ib, contract, bar_size='5 mins', lookback_bars=100):
    """
    Fetch historical bars directly from IBKR API

    Args:
        ib: IB connection object (ib_insync)
        contract: Stock contract
        bar_size: Bar size ('1 min', '5 mins', '15 mins', etc.)
        lookback_bars: How many bars to fetch

    Returns:
        List of IBKR BarData objects
    """
    try:
        # Calculate duration needed based on bar size
        if bar_size == '1 min':
            # 100 bars * 1 min = 100 min = ~1.7 hours
            duration_str = '1 D'  # Get 1 day to be safe
        elif bar_size == '5 mins':
            # 100 bars * 5 min = 500 min = ~8.3 hours
            duration_str = '1 D' if lookback_bars <= 78 else '2 D'
        elif bar_size == '15 mins':
            # 100 bars * 15 min = 1500 min = 25 hours
            duration_str = '2 D'
        else:
            duration_str = '1 D'

        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',  # Current time
            durationStr=duration_str,
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1,
            keepUpToDate=False
        )

        # Return the most recent lookback_bars
        return bars[-lookback_bars:] if len(bars) > lookback_bars else bars

    except Exception as e:
        print(f"Error fetching {bar_size} bars: {e}")
        return []


def fetch_5min_bars(ib, contract, lookback_bars=100):
    """
    Fetch 5-minute bars directly from IBKR API

    Args:
        ib: IB connection object (ib_insync)
        contract: Stock contract
        lookback_bars: How many 5-min bars to fetch (default 100 = ~8 hours)

    Returns:
        List of IBKR BarData objects with 5-min bars
    """
    return fetch_bars(ib, contract, bar_size='5 mins', lookback_bars=lookback_bars)


def fetch_1min_bars(ib, contract, lookback_bars=60):
    """
    Fetch 1-minute bars directly from IBKR API

    Args:
        ib: IB connection object (ib_insync)
        contract: Stock contract
        lookback_bars: How many 1-min bars to fetch (default 60 = 1 hour)

    Returns:
        List of IBKR BarData objects with 1-min bars
    """
    return fetch_bars(ib, contract, bar_size='1 min', lookback_bars=lookback_bars)


def fetch_1hour_bars(ib, contract, lookback_bars=50):
    """
    Fetch 1-hour bars directly from IBKR API

    Args:
        ib: IB connection object (ib_insync)
        contract: Stock contract
        lookback_bars: How many 1-hour bars to fetch (default 50 = ~2 weeks)

    Returns:
        List of IBKR BarData objects with 1-hour bars
    """
    try:
        # 50 bars * 1 hour = 50 hours = ~7-8 trading days
        # Use 10 D to get enough data
        duration_str = '10 D' if lookback_bars <= 50 else '20 D'

        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',  # Current time
            durationStr=duration_str,
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1,
            keepUpToDate=False
        )

        # Return the most recent lookback_bars
        return bars[-lookback_bars:] if len(bars) > lookback_bars else bars

    except Exception as e:
        print(f"Error fetching 1 hour bars: {e}")
        return []


def calculate_rsi(bars, period=14):
    """
    Calculate RSI (Relative Strength Index) from IBKR bars

    Args:
        bars: List of IBKR BarData objects (5-min bars)
        period: RSI period (default 14, use 9 for more sensitive)

    Returns:
        Current RSI value (0-100), or None if insufficient data
    """
    if len(bars) < period + 1:
        return None

    # Get close prices from IBKR bars
    closes = np.array([bar.close for bar in bars])

    # Calculate price changes
    deltas = np.diff(closes)

    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Calculate average gains and losses using Wilder's smoothing
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    # Calculate smoothed averages for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    # Calculate RS and RSI
    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(bars, fast=12, slow=26, signal=9):
    """
    Calculate MACD (Moving Average Convergence Divergence) from IBKR bars

    Args:
        bars: List of IBKR BarData objects (5-min bars)
        fast: Fast EMA period (default 12, use 3 for day trading)
        slow: Slow EMA period (default 26, use 10 for day trading)
        signal: Signal line period (default 9, use 16 for day trading)

    Returns:
        tuple: (macd_line, signal_line, histogram) or (None, None, None) if insufficient data
    """
    if len(bars) < slow + signal:
        return None, None, None

    # Get close prices from IBKR bars
    closes = np.array([bar.close for bar in bars])

    # Calculate EMA arrays (not just final value)
    ema_fast_array = _calculate_ema_array(closes, fast)
    ema_slow_array = _calculate_ema_array(closes, slow)

    # MACD line = Fast EMA - Slow EMA (array of values)
    macd_line_array = ema_fast_array - ema_slow_array

    # Signal line = 9-period EMA of MACD line array
    signal_line_array = _calculate_ema_array(macd_line_array, signal)

    # Get current values (last element)
    macd_line = macd_line_array[-1]
    signal_line = signal_line_array[-1]

    # Histogram = MACD - Signal
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def _calculate_ema(data, period):
    """
    Calculate Exponential Moving Average (returns single value)

    Args:
        data: NumPy array of prices
        period: EMA period

    Returns:
        Current EMA value
    """
    multiplier = 2 / (period + 1)

    # Start with SMA
    ema = np.mean(data[:period])

    # Calculate EMA for remaining values
    for i in range(period, len(data)):
        ema = (data[i] * multiplier) + (ema * (1 - multiplier))

    return ema


def _calculate_ema_array(data, period):
    """
    Calculate Exponential Moving Average array (returns all values)

    Args:
        data: NumPy array of prices
        period: EMA period

    Returns:
        NumPy array of EMA values (same length as input)
    """
    if len(data) < period:
        return np.array([])

    multiplier = 2 / (period + 1)
    ema_array = np.zeros(len(data))

    # Start with SMA for first value
    ema_array[period - 1] = np.mean(data[:period])

    # Calculate EMA for remaining values
    for i in range(period, len(data)):
        ema_array[i] = (data[i] * multiplier) + (ema_array[i - 1] * (1 - multiplier))

    return ema_array


def check_rsi_momentum(bars, side='LONG', rsi_period=14, threshold_neutral=50, threshold_strong=60):
    """
    Check if RSI confirms breakout momentum

    Args:
        bars: List of IBKR BarData objects (5-min bars)
        side: 'LONG' or 'SHORT'
        rsi_period: RSI calculation period (default 14)
        threshold_neutral: RSI neutral threshold (default 50)
        threshold_strong: RSI strong momentum threshold (default 60 for longs, 40 for shorts)

    Returns:
        tuple: (is_confirmed, rsi_value, reason)
    """
    rsi = calculate_rsi(bars, period=rsi_period)

    if rsi is None:
        return False, None, "Insufficient data for RSI calculation"

    if side == 'LONG':
        if rsi < threshold_neutral:
            return False, rsi, f"RSI too weak for LONG ({rsi:.1f} < {threshold_neutral})"
        elif rsi >= threshold_strong:
            return True, rsi, f"RSI confirms strong LONG momentum ({rsi:.1f})"
        else:
            return True, rsi, f"RSI confirms LONG bias ({rsi:.1f})"

    else:  # SHORT
        threshold_strong_short = 100 - threshold_strong  # 40 for shorts
        if rsi > threshold_neutral:
            return False, rsi, f"RSI too strong for SHORT ({rsi:.1f} > {threshold_neutral})"
        elif rsi <= threshold_strong_short:
            return True, rsi, f"RSI confirms strong SHORT momentum ({rsi:.1f})"
        else:
            return True, rsi, f"RSI confirms SHORT bias ({rsi:.1f})"


def check_macd_alignment(bars, side='LONG', fast=12, slow=26, signal=9):
    """
    Check if MACD aligns with breakout direction

    Args:
        bars: List of IBKR BarData objects (5-min bars)
        side: 'LONG' or 'SHORT'
        fast: Fast EMA period (use 3 for day trading)
        slow: Slow EMA period (use 10 for day trading)
        signal: Signal EMA period (use 16 for day trading)

    Returns:
        tuple: (is_aligned, macd_value, signal_value, reason)
    """
    macd_line, signal_line, histogram = calculate_macd(bars, fast, slow, signal)

    if macd_line is None:
        return False, None, None, "Insufficient data for MACD calculation"

    if side == 'LONG':
        if macd_line > signal_line:
            return True, macd_line, signal_line, f"MACD bullish (MACD {macd_line:.2f} > Signal {signal_line:.2f})"
        else:
            return False, macd_line, signal_line, f"MACD bearish (MACD {macd_line:.2f} < Signal {signal_line:.2f})"

    else:  # SHORT
        if macd_line < signal_line:
            return True, macd_line, signal_line, f"MACD bearish (MACD {macd_line:.2f} < Signal {signal_line:.2f})"
        else:
            return False, macd_line, signal_line, f"MACD bullish (MACD {macd_line:.2f} > Signal {signal_line:.2f})"


def get_average_1min_volume(ib, contract, lookback_bars=20):
    """
    Get average 1-minute volume from IBKR bars (instead of stitching 5-sec bars)

    Args:
        ib: IB connection object
        contract: Stock contract
        lookback_bars: How many 1-min bars to average (default 20)

    Returns:
        Average 1-minute volume, or None if insufficient data
    """
    bars = fetch_1min_bars(ib, contract, lookback_bars)

    if len(bars) < lookback_bars:
        return None

    avg_volume = np.mean([bar.volume for bar in bars])
    return avg_volume


def check_momentum_confirmation_with_bars(bars, side='LONG',
                                         rsi_enabled=True, rsi_period=14, rsi_threshold=50,
                                         macd_enabled=True, macd_fast=12, macd_slow=26, macd_signal=9):
    """
    Check momentum confirmation using PRE-FETCHED bars (performance optimization)

    This version is used by backtester with cached hourly bars to avoid
    redundant IBKR API calls. The bars are fetched once and reused.

    Args:
        bars: Pre-fetched IBKR BarData objects (hourly bars)
        side: 'LONG' or 'SHORT'
        rsi_enabled: Enable RSI filter
        rsi_period: RSI period (14 standard)
        rsi_threshold: RSI threshold (50 for neutral, 60 for strong)
        macd_enabled: Enable MACD filter
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period

    Returns:
        tuple: (is_confirmed, reason, details)
    """
    details = {}
    reasons = []
    all_confirmed = True

    # Check RSI
    if rsi_enabled:
        if len(bars) < rsi_period + 1:
            return False, f"Insufficient bars for RSI calculation ({len(bars)} < {rsi_period + 1})", {}

        rsi_confirmed, rsi_value, rsi_reason = check_rsi_momentum(
            bars, side, rsi_period, threshold_neutral=50, threshold_strong=rsi_threshold
        )
        details['rsi'] = rsi_value
        details['rsi_confirmed'] = rsi_confirmed
        reasons.append(rsi_reason)

        if not rsi_confirmed:
            all_confirmed = False

    # Check MACD
    if macd_enabled:
        if len(bars) < macd_slow + macd_signal:
            return False, f"Insufficient bars for MACD calculation ({len(bars)} < {macd_slow + macd_signal})", {}

        macd_confirmed, macd_value, signal_value, macd_reason = check_macd_alignment(
            bars, side, macd_fast, macd_slow, macd_signal
        )
        details['macd'] = macd_value
        details['signal'] = signal_value
        details['macd_confirmed'] = macd_confirmed
        reasons.append(macd_reason)

        if not macd_confirmed:
            all_confirmed = False

    # If neither enabled, allow entry
    if not rsi_enabled and not macd_enabled:
        return True, "Momentum filters disabled", details

    # Combine results
    combined_reason = " | ".join(reasons)

    return all_confirmed, combined_reason, details


def check_momentum_confirmation(ib, contract, side='LONG',
                                rsi_enabled=True, rsi_period=14, rsi_threshold=50, rsi_timeframe='1 hour',
                                macd_enabled=True, macd_fast=12, macd_slow=26, macd_signal=9, macd_timeframe='5 mins',
                                lookback_bars=100):
    """
    Complete momentum confirmation check using RSI and MACD

    This is the main function to call from ps60_strategy.py or trader.py

    Args:
        ib: IB connection object
        contract: Stock contract
        side: 'LONG' or 'SHORT'
        rsi_enabled: Enable RSI filter
        rsi_period: RSI period (14 standard, 9 sensitive)
        rsi_threshold: RSI threshold (50 for neutral, 60 for strong)
        rsi_timeframe: '1 hour', '5 mins', or '1 min' (1 hour recommended for day trading)
        macd_enabled: Enable MACD filter
        macd_fast: MACD fast period (12 standard, 3 for day trading)
        macd_slow: MACD slow period (26 standard, 10 for day trading)
        macd_signal: MACD signal period (9 standard, 16 for day trading)
        macd_timeframe: '5 mins', '1 min', or '1 hour'
        lookback_bars: How many bars to fetch (default 100)

    Returns:
        tuple: (is_confirmed, reason, details)
            details = {
                'rsi': rsi_value,
                'rsi_timeframe': '1 hour',
                'macd': macd_value,
                'signal': signal_value,
                'macd_timeframe': '5 mins',
                'rsi_confirmed': bool,
                'macd_confirmed': bool
            }
    """
    details = {}
    reasons = []
    all_confirmed = True

    # Check RSI
    if rsi_enabled:
        # Fetch bars based on RSI timeframe
        if rsi_timeframe == '1 hour':
            bars_rsi = fetch_1hour_bars(ib, contract, lookback_bars=max(50, rsi_period + 1))
        elif rsi_timeframe == '5 mins':
            bars_rsi = fetch_5min_bars(ib, contract, lookback_bars=lookback_bars)
        else:  # 1 min
            bars_rsi = fetch_1min_bars(ib, contract, lookback_bars=lookback_bars)

        if len(bars_rsi) < rsi_period + 1:
            return False, f"Insufficient {rsi_timeframe} bars for RSI calculation", {}

        rsi_confirmed, rsi_value, rsi_reason = check_rsi_momentum(
            bars_rsi, side, rsi_period, threshold_neutral=50, threshold_strong=rsi_threshold
        )
        details['rsi'] = rsi_value
        details['rsi_timeframe'] = rsi_timeframe
        details['rsi_confirmed'] = rsi_confirmed
        reasons.append(f"{rsi_reason} ({rsi_timeframe})")

        if not rsi_confirmed:
            all_confirmed = False

    # Check MACD
    if macd_enabled:
        # Fetch bars based on MACD timeframe
        if macd_timeframe == '1 hour':
            bars_macd = fetch_1hour_bars(ib, contract, lookback_bars=max(50, macd_slow + macd_signal))
        elif macd_timeframe == '5 mins':
            bars_macd = fetch_5min_bars(ib, contract, lookback_bars=lookback_bars)
        else:  # 1 min
            bars_macd = fetch_1min_bars(ib, contract, lookback_bars=lookback_bars)

        if len(bars_macd) < macd_slow + macd_signal:
            return False, f"Insufficient {macd_timeframe} bars for MACD calculation", {}

        macd_confirmed, macd_value, signal_value, macd_reason = check_macd_alignment(
            bars_macd, side, macd_fast, macd_slow, macd_signal
        )
        details['macd'] = macd_value
        details['signal'] = signal_value
        details['macd_timeframe'] = macd_timeframe
        details['macd_confirmed'] = macd_confirmed
        reasons.append(f"{macd_reason} ({macd_timeframe})")

        if not macd_confirmed:
            all_confirmed = False

    # If neither enabled, allow entry
    if not rsi_enabled and not macd_enabled:
        return True, "Momentum filters disabled", details

    # Combine results
    combined_reason = " | ".join(reasons)

    return all_confirmed, combined_reason, details
