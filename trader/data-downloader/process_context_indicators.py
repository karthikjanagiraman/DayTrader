#!/usr/bin/env python3
"""
Process 1-minute bar data to calculate context indicators for backtesting.

Calculates and stores:
- Daily indicators: SMAs, EMAs, RSI, ATR, Bollinger Bands
- Hourly indicators: EMAs, RSI, Stochastic, MACD, ATR, Bollinger Bands
- Intraday context: VWAP, opening range, previous day levels

Output: {SYMBOL}_{YYYYMMDD}_context.json files for fast backtesting lookup
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from ib_insync import IB, Stock


class ContextIndicatorProcessor:
    """Process 1-min bars to calculate context indicators"""

    def __init__(self, data_dir, output_dir, use_ibkr=False, port=7497):
        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.use_ibkr = use_ibkr
        self.port = port
        self.ib = None
        self.daily_cache = {}  # Cache historical daily bars per symbol

    def load_1min_bars(self, symbol, date):
        """Load 1-minute bars for a symbol/date"""
        date_str = date.strftime('%Y%m%d')
        filename = f"{symbol}_{date_str}_1min.json"
        filepath = self.data_dir / filename

        if not filepath.exists():
            return None

        with open(filepath, 'r') as f:
            bars = json.load(f)

        # Convert to DataFrame
        df = pd.DataFrame(bars)
        df['timestamp'] = pd.to_datetime(df['date'])
        df = df.set_index('timestamp')

        return df

    def resample_to_hourly(self, df_1min):
        """Resample 1-minute bars to hourly bars"""
        hourly = df_1min.resample('1H').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        return hourly

    def resample_to_daily(self, df_1min):
        """Resample 1-minute bars to daily bars"""
        daily = df_1min.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()

        return daily

    def connect_ibkr(self):
        """Connect to IBKR for fetching historical daily data"""
        if self.ib is None or not self.ib.isConnected():
            self.ib = IB()
            try:
                self.ib.connect('127.0.0.1', self.port, clientId=5000)
                print(f"✅ Connected to IBKR on port {self.port}")
                return True
            except Exception as e:
                print(f"❌ Failed to connect to IBKR: {e}")
                return False
        return True

    def fetch_daily_bars_from_ibkr(self, symbol, end_date, days=250):
        """Fetch historical daily bars from IBKR"""
        # Check cache first
        cache_key = f"{symbol}_{end_date.strftime('%Y%m%d')}"
        if cache_key in self.daily_cache:
            return self.daily_cache[cache_key]

        if not self.connect_ibkr():
            return None

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Request daily bars
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date.strftime('%Y%m%d 16:00:00 US/Eastern'),
                durationStr=f'{days} D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                print(f"    ⚠️  No daily data from IBKR for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame([
                {
                    'timestamp': bar.date,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume)
                }
                for bar in bars
            ])

            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')

            # Cache it
            self.daily_cache[cache_key] = df

            # Pacing
            time.sleep(1.0)

            print(f"    ✅ Fetched {len(df)} daily bars from IBKR")
            return df

        except Exception as e:
            print(f"    ❌ Error fetching daily bars: {e}")
            return None

    def calculate_sma(self, series, period):
        """Calculate Simple Moving Average"""
        return series.rolling(window=period).mean()

    def calculate_ema(self, series, period):
        """Calculate Exponential Moving Average"""
        return series.ewm(span=period, adjust=False).mean()

    def calculate_rsi(self, series, period=14):
        """Calculate Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def calculate_stochastic(self, df, k_period=14, d_period=3):
        """Calculate Stochastic Oscillator"""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()

        stoch_k = 100 * ((df['close'] - low_min) / (high_max - low_min))
        stoch_d = stoch_k.rolling(window=d_period).mean()

        return stoch_k, stoch_d

    def calculate_macd(self, series, fast=12, slow=26, signal=9):
        """Calculate MACD"""
        ema_fast = self.calculate_ema(series, fast)
        ema_slow = self.calculate_ema(series, slow)

        macd_line = ema_fast - ema_slow
        signal_line = self.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    def calculate_atr(self, df, period=14):
        """Calculate Average True Range"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def calculate_bollinger_bands(self, series, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        sma = self.calculate_sma(series, period)
        std = series.rolling(window=period).std()

        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)

        return upper_band, sma, lower_band

    def calculate_vwap(self, df):
        """Calculate Volume Weighted Average Price"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()

        return vwap

    def get_daily_context(self, df_daily, current_date):
        """Calculate daily timeframe indicators"""
        if df_daily is None or len(df_daily) == 0:
            return None

        # Get the row for the current date (or last available if multi-day data)
        if current_date in df_daily.index:
            latest = df_daily.loc[:current_date].iloc[-1]
        else:
            latest = df_daily.iloc[-1]

        context = {}

        # SMAs
        for period in [5, 10, 20, 50, 100, 200]:
            sma = self.calculate_sma(df_daily['close'], period)
            context[f'sma_{period}'] = float(sma.iloc[-1]) if not pd.isna(sma.iloc[-1]) else None

        # EMAs
        for period in [9, 20, 50]:
            ema = self.calculate_ema(df_daily['close'], period)
            context[f'ema_{period}'] = float(ema.iloc[-1]) if not pd.isna(ema.iloc[-1]) else None

        # RSI
        rsi = self.calculate_rsi(df_daily['close'], 14)
        context['rsi_14'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None

        # ATR
        atr = self.calculate_atr(df_daily, 14)
        context['atr_14'] = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df_daily['close'], 20, 2)
        context['bb_upper'] = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None
        context['bb_middle'] = float(bb_middle.iloc[-1]) if not pd.isna(bb_middle.iloc[-1]) else None
        context['bb_lower'] = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None

        # Previous day levels (if we have at least 2 days)
        if len(df_daily) >= 2:
            prev_day = df_daily.iloc[-2]
            context['prev_close'] = float(prev_day['close'])
            context['prev_high'] = float(prev_day['high'])
            context['prev_low'] = float(prev_day['low'])
        else:
            context['prev_close'] = None
            context['prev_high'] = None
            context['prev_low'] = None

        return context

    def get_hourly_context(self, df_hourly):
        """Calculate hourly timeframe indicators for each hour"""
        if df_hourly is None or len(df_hourly) == 0:
            return {}

        hourly_context = {}

        for timestamp, row in df_hourly.iterrows():
            hour_key = timestamp.strftime('%H:%M')

            context = {}

            # SMAs (use up to this hour)
            df_up_to_now = df_hourly.loc[:timestamp]

            for period in [5, 10, 20, 50]:
                if len(df_up_to_now) >= period:
                    sma = self.calculate_sma(df_up_to_now['close'], period)
                    context[f'sma_{period}'] = float(sma.iloc[-1])
                else:
                    context[f'sma_{period}'] = None

            # EMAs
            for period in [9, 20]:
                if len(df_up_to_now) >= period:
                    ema = self.calculate_ema(df_up_to_now['close'], period)
                    context[f'ema_{period}'] = float(ema.iloc[-1])
                else:
                    context[f'ema_{period}'] = None

            # RSI
            if len(df_up_to_now) >= 14:
                rsi = self.calculate_rsi(df_up_to_now['close'], 14)
                context['rsi_14'] = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else None
            else:
                context['rsi_14'] = None

            # Stochastic
            if len(df_up_to_now) >= 14:
                stoch_k, stoch_d = self.calculate_stochastic(df_up_to_now, 14, 3)
                context['stoch_k'] = float(stoch_k.iloc[-1]) if not pd.isna(stoch_k.iloc[-1]) else None
                context['stoch_d'] = float(stoch_d.iloc[-1]) if not pd.isna(stoch_d.iloc[-1]) else None
            else:
                context['stoch_k'] = None
                context['stoch_d'] = None

            # MACD
            if len(df_up_to_now) >= 26:
                macd, signal, histogram = self.calculate_macd(df_up_to_now['close'])
                context['macd'] = float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else None
                context['macd_signal'] = float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else None
                context['macd_histogram'] = float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
            else:
                context['macd'] = None
                context['macd_signal'] = None
                context['macd_histogram'] = None

            # ATR
            if len(df_up_to_now) >= 14:
                atr = self.calculate_atr(df_up_to_now, 14)
                context['atr_14'] = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else None
            else:
                context['atr_14'] = None

            # Bollinger Bands
            if len(df_up_to_now) >= 20:
                bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df_up_to_now['close'], 20, 2)
                context['bb_upper'] = float(bb_upper.iloc[-1]) if not pd.isna(bb_upper.iloc[-1]) else None
                context['bb_middle'] = float(bb_middle.iloc[-1]) if not pd.isna(bb_middle.iloc[-1]) else None
                context['bb_lower'] = float(bb_lower.iloc[-1]) if not pd.isna(bb_lower.iloc[-1]) else None
            else:
                context['bb_upper'] = None
                context['bb_middle'] = None
                context['bb_lower'] = None

            hourly_context[hour_key] = context

        return hourly_context

    def get_intraday_context(self, df_1min):
        """Calculate intraday context (VWAP, opening range, etc.)"""
        if df_1min is None or len(df_1min) == 0:
            return {}

        context = {}

        # VWAP
        vwap = self.calculate_vwap(df_1min)
        context['vwap'] = float(vwap.iloc[-1]) if not pd.isna(vwap.iloc[-1]) else None

        # Opening range (first 30 minutes: 9:30 - 10:00)
        market_open = df_1min.index[0].replace(hour=9, minute=30, second=0, microsecond=0)
        opening_range_end = market_open + timedelta(minutes=30)

        opening_range = df_1min[(df_1min.index >= market_open) & (df_1min.index < opening_range_end)]

        if len(opening_range) > 0:
            context['opening_range_high'] = float(opening_range['high'].max())
            context['opening_range_low'] = float(opening_range['low'].min())
        else:
            context['opening_range_high'] = None
            context['opening_range_low'] = None

        # First hour volume
        first_hour_end = market_open + timedelta(hours=1)
        first_hour = df_1min[(df_1min.index >= market_open) & (df_1min.index < first_hour_end)]

        if len(first_hour) > 0:
            context['volume_first_hour'] = int(first_hour['volume'].sum())
        else:
            context['volume_first_hour'] = None

        return context

    def process_symbol_date(self, symbol, date):
        """Process all indicators for a symbol on a specific date"""
        print(f"Processing {symbol} on {date.strftime('%Y-%m-%d')}...")

        # Load 1-min bars
        df_1min = self.load_1min_bars(symbol, date)

        if df_1min is None or len(df_1min) == 0:
            print(f"  ❌ No 1-min data found")
            return False

        # Build hourly bars
        df_hourly = self.resample_to_hourly(df_1min)

        # Get daily bars - either from IBKR (with history) or just today's intraday data
        if self.use_ibkr:
            df_daily = self.fetch_daily_bars_from_ibkr(symbol, date, days=250)
        else:
            df_daily = self.resample_to_daily(df_1min)

        # Calculate context indicators
        daily_context = self.get_daily_context(df_daily, date)
        hourly_context = self.get_hourly_context(df_hourly)
        intraday_context = self.get_intraday_context(df_1min)

        # Build output structure
        output = {
            'symbol': symbol,
            'date': date.strftime('%Y-%m-%d'),
            'daily': daily_context,
            'hourly': hourly_context,
            'intraday': intraday_context,
            'metadata': {
                'bars_1min': len(df_1min),
                'bars_hourly': len(df_hourly),
                'bars_daily': len(df_daily),
                'processed_at': datetime.now().isoformat()
            }
        }

        # Save to file
        output_filename = f"{symbol}_{date.strftime('%Y%m%d')}_context.json"
        output_path = self.output_dir / output_filename

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"  ✅ Saved: {output_filename} ({len(hourly_context)} hourly bars)")

        return True

    def process_all(self, symbols, start_date, end_date):
        """Process all symbols for a date range"""
        print("=" * 80)
        print("Context Indicator Processor")
        print("=" * 80)
        print(f"Symbols: {', '.join(symbols)}")
        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print(f"Output: {self.output_dir}")
        print(f"IBKR: {'Enabled (daily SMAs will be populated)' if self.use_ibkr else 'Disabled (daily SMAs will be null)'}")
        print("=" * 80)

        # Connect to IBKR if needed
        if self.use_ibkr:
            if not self.connect_ibkr():
                print("❌ Cannot continue without IBKR connection")
                return

        total = 0
        success = 0
        current_date = start_date

        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue

            print(f"\n📅 {current_date.strftime('%Y-%m-%d (%A)')}")

            for symbol in symbols:
                if self.process_symbol_date(symbol, current_date):
                    success += 1
                total += 1

            current_date += timedelta(days=1)

        # Disconnect from IBKR
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("\n✅ Disconnected from IBKR")

        print("\n" + "=" * 80)
        print(f"✅ Complete: {success}/{total} processed successfully")
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Process 1-min bars to calculate context indicators')

    parser.add_argument(
        '--symbols',
        type=str,
        help='Comma-separated list of symbols (e.g., TSLA,NVDA,AMD)'
    )
    parser.add_argument(
        '--quick-scan',
        action='store_true',
        help='Process quick scan stocks (QQQ, TSLA, NVDA, AMD, PLTR, SOFI, HOOD, SMCI, PATH)'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        required=True,
        help='Start date YYYY-MM-DD'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        required=True,
        help='End date YYYY-MM-DD'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default='../backtest/data',
        help='Directory containing 1-min bar data'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='../backtest/data/context',
        help='Output directory for context files'
    )
    parser.add_argument(
        '--use-ibkr',
        action='store_true',
        help='Fetch historical daily bars from IBKR for complete daily SMAs'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=7497,
        help='TWS/Gateway port (7497=paper, 7496=live)'
    )

    args = parser.parse_args()

    # Parse dates
    start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    end_date = datetime.strptime(args.end_date, '%Y-%m-%d')

    # Get symbol list
    if args.quick_scan:
        symbols = ['QQQ', 'TSLA', 'NVDA', 'AMD', 'PLTR', 'SOFI', 'HOOD', 'SMCI', 'PATH']
    elif args.symbols:
        symbols = args.symbols.split(',')
    else:
        print("Error: Must provide --symbols or --quick-scan")
        return 1

    # Resolve paths
    script_dir = Path(__file__).parent
    data_dir = (script_dir / args.data_dir).resolve()
    output_dir = (script_dir / args.output_dir).resolve()

    # Process
    processor = ContextIndicatorProcessor(data_dir, output_dir, use_ibkr=args.use_ibkr, port=args.port)
    processor.process_all(symbols, start_date, end_date)

    return 0


if __name__ == '__main__':
    main()
