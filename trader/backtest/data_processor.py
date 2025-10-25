#!/usr/bin/env python3
"""
Data Processor Module for Backtester (October 24, 2025)

Handles the complete data pipeline:
1. Check/download tick data for CVD calculation
2. Check/download 1-minute bars for price action
3. Build CVD-enriched bars combining both

This module ensures all required data is available before backtesting.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
from ib_insync import Stock, util
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indicators.cvd_calculator import CVDCalculator


class DataProcessor:
    """
    Manages the complete data pipeline for backtesting.

    Data Flow:
    1. Tick data (raw trades) → CVD calculation
    2. 1-minute bars (OHLCV) → Price action
    3. CVD-enriched bars → Combined data for fast backtesting
    """

    def __init__(self, ib_connection, config, logger=None):
        """
        Initialize data processor.

        Args:
            ib_connection: Connected IB instance
            config: Trading configuration dict
            logger: Optional logger instance
        """
        self.ib = ib_connection
        self.config = config
        self.logger = logger

        # Data directories
        self.data_dir = Path(__file__).parent / 'data'
        self.ticks_dir = self.data_dir / 'ticks'
        self.cvd_bars_dir = self.data_dir / 'cvd_bars'

        # Create directories if needed
        self.data_dir.mkdir(exist_ok=True)
        self.ticks_dir.mkdir(exist_ok=True)
        self.cvd_bars_dir.mkdir(exist_ok=True)

        # CVD calculator config
        cvd_config = self.config.get('confirmation', {}).get('cvd', {})
        self.cvd_config = cvd_config

    def log(self, message, level='INFO'):
        """Log message to logger or console."""
        if self.logger:
            if level == 'ERROR':
                self.logger.error(message)
            elif level == 'WARNING':
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(message)

    def prepare_data_for_date(self, symbols, date):
        """
        Complete data pipeline for a trading day.

        This is the main entry point that orchestrates the entire data preparation:
        1. Download tick data if missing
        2. Download 1-minute bars if missing
        3. Build CVD-enriched bars if missing

        Args:
            symbols: List of symbols to process
            date: Date object for the trading day

        Returns:
            dict: Statistics about data processing
        """
        date_str = date.strftime('%Y%m%d')

        self.log("\n" + "="*80)
        self.log(f"DATA PROCESSOR - Preparing data for {date.strftime('%Y-%m-%d')}")
        self.log("="*80)

        stats = {
            'symbols_processed': 0,
            'tick_data_downloaded': 0,
            'bars_downloaded': 0,
            'cvd_bars_built': 0,
            'already_cached': 0,
            'errors': 0
        }

        for i, symbol in enumerate(symbols, 1):
            self.log(f"\n[{i}/{len(symbols)}] Processing {symbol}...")

            try:
                # Step 1: Check/download tick data
                if not self.check_tick_data_exists(symbol, date):
                    self.log(f"  Tick data missing - downloading...")
                    success = self.download_tick_data(symbol, date)
                    if success:
                        stats['tick_data_downloaded'] += 1
                    else:
                        self.log(f"  ⚠️  Tick data download failed", 'WARNING')
                        stats['errors'] += 1
                        continue
                else:
                    self.log(f"  ✓ Tick data exists")

                # Step 2: Check/download 1-minute bars
                if not self.check_1min_bars_exist(symbol, date):
                    self.log(f"  1-minute bars missing - downloading...")
                    success = self.download_1min_bars(symbol, date)
                    if success:
                        stats['bars_downloaded'] += 1
                    else:
                        self.log(f"  ⚠️  1-minute bars download failed", 'WARNING')
                        stats['errors'] += 1
                        continue
                else:
                    self.log(f"  ✓ 1-minute bars exist")

                # Step 3: Check/build CVD-enriched bars
                if not self.check_cvd_bars_exist(symbol, date):
                    self.log(f"  CVD-enriched bars missing - building...")
                    success = self.build_cvd_enriched_bars(symbol, date)
                    if success:
                        stats['cvd_bars_built'] += 1
                    else:
                        self.log(f"  ⚠️  CVD-enriched bars build failed", 'WARNING')
                        stats['errors'] += 1
                        continue
                else:
                    self.log(f"  ✓ CVD-enriched bars exist")
                    stats['already_cached'] += 1

                stats['symbols_processed'] += 1

            except Exception as e:
                self.log(f"  ❌ ERROR processing {symbol}: {str(e)}", 'ERROR')
                stats['errors'] += 1
                import traceback
                traceback.print_exc()

        # Summary
        self.log("\n" + "="*80)
        self.log("DATA PROCESSOR SUMMARY")
        self.log("="*80)
        self.log(f"Symbols processed: {stats['symbols_processed']}/{len(symbols)}")
        self.log(f"Tick data downloaded: {stats['tick_data_downloaded']}")
        self.log(f"1-minute bars downloaded: {stats['bars_downloaded']}")
        self.log(f"CVD-enriched bars built: {stats['cvd_bars_built']}")
        self.log(f"Already cached: {stats['already_cached']}")
        self.log(f"Errors: {stats['errors']}")
        self.log("="*80 + "\n")

        return stats

    def check_tick_data_exists(self, symbol, date):
        """
        Check if tick data exists for this symbol/date.

        We expect 390 tick files (one per minute, 9:30 AM - 4:00 PM).
        """
        date_str = date.strftime('%Y%m%d')
        pattern = f"{symbol}_{date_str}_*_ticks.json"
        tick_files = list(self.ticks_dir.glob(pattern))

        # Should have ~390 files (one per minute)
        return len(tick_files) >= 350  # Allow some missing (early close, etc.)

    def download_tick_data(self, symbol, date):
        """
        Download tick data for one symbol on one date.

        This downloads ~390 files (one per minute) to data/ticks/
        """
        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Market hours: 9:30 AM - 4:00 PM ET (390 minutes)
            market_open = datetime.combine(date, datetime.strptime('09:30', '%H:%M').time())
            market_close = datetime.combine(date, datetime.strptime('16:00', '%H:%M').time())

            current_time = market_open
            minutes_downloaded = 0

            while current_time < market_close:
                # Format: YYYYMMDD_HHMMSS
                time_str = current_time.strftime('%Y%m%d_%H%M%S')
                tick_file = self.ticks_dir / f"{symbol}_{time_str}_ticks.json"

                # Skip if already exists
                if tick_file.exists():
                    current_time += timedelta(minutes=1)
                    continue

                # Request historical ticks for this minute
                try:
                    ticks = self.ib.reqHistoricalTicks(
                        contract,
                        startDateTime='',
                        endDateTime=current_time,
                        numberOfTicks=1000,
                        whatToShow='TRADES',
                        useRth=True
                    )

                    if ticks:
                        # Save to file
                        tick_data = []
                        for tick in ticks:
                            tick_data.append({
                                'time': tick.time.isoformat() if hasattr(tick.time, 'isoformat') else str(tick.time),
                                'price': tick.price,
                                'size': tick.size
                            })

                        with open(tick_file, 'w') as f:
                            json.dump(tick_data, f)

                        minutes_downloaded += 1

                        # Log progress every 60 minutes
                        if minutes_downloaded % 60 == 0:
                            self.log(f"    Downloaded {minutes_downloaded}/390 minutes...")

                    # Rate limiting
                    time.sleep(0.1)

                except Exception as e:
                    self.log(f"    Warning: Failed to download minute {current_time.strftime('%H:%M')}: {str(e)}", 'WARNING')

                current_time += timedelta(minutes=1)

            self.log(f"    ✓ Downloaded {minutes_downloaded} tick files")
            return minutes_downloaded > 350  # Success if we got most of them

        except Exception as e:
            self.log(f"    ERROR downloading tick data: {str(e)}", 'ERROR')
            return False

    def check_1min_bars_exist(self, symbol, date):
        """Check if 1-minute bars file exists."""
        date_str = date.strftime('%Y%m%d')
        bars_file = self.data_dir / f'{symbol}_{date_str}_1min.json'
        return bars_file.exists()

    def download_1min_bars(self, symbol, date):
        """
        Download 1-minute bars from IBKR for one symbol on one date.

        This downloads one file with 390 bars to data/
        """
        try:
            date_str = date.strftime('%Y%m%d')

            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Fetch 1-minute bars
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=f'{date_str} 16:00:00',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                self.log(f"    No bars returned from IBKR", 'WARNING')
                return False

            # Convert to JSON
            bars_data = []
            for bar in bars:
                bars_data.append({
                    'date': bar.date.isoformat(),
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'average': bar.average,
                    'barCount': bar.barCount
                })

            # Save to file
            bars_file = self.data_dir / f'{symbol}_{date_str}_1min.json'
            with open(bars_file, 'w') as f:
                json.dump(bars_data, f, indent=2)

            self.log(f"    ✓ Downloaded {len(bars)} 1-minute bars")
            return True

        except Exception as e:
            self.log(f"    ERROR downloading 1-minute bars: {str(e)}", 'ERROR')
            return False

    def check_cvd_bars_exist(self, symbol, date):
        """Check if CVD-enriched bars file exists."""
        date_str = date.strftime('%Y%m%d')
        cvd_file = self.cvd_bars_dir / f'{symbol}_{date_str}_cvd.json'
        return cvd_file.exists()

    def build_cvd_enriched_bars(self, symbol, date):
        """
        Build CVD-enriched bars from tick data + 1-minute bars.

        This is the core data processing step that combines:
        - Price action from 1-minute bars
        - CVD data calculated from tick data

        Result is saved to data/cvd_bars/
        """
        try:
            date_str = date.strftime('%Y%m%d')

            # Load 1-minute bars
            bars_file = self.data_dir / f'{symbol}_{date_str}_1min.json'
            with open(bars_file, 'r') as f:
                bars_data = json.load(f)

            if not bars_data:
                self.log(f"    No bars data found", 'WARNING')
                return False

            # Create CVD calculator
            cvd_calculator = CVDCalculator(
                slope_lookback=self.cvd_config.get('slope_lookback', 5),
                bullish_threshold=self.cvd_config.get('bullish_slope_threshold', 1000),
                bearish_threshold=self.cvd_config.get('bearish_slope_threshold', -1000),
                imbalance_threshold=self.cvd_config.get('imbalance_threshold', 10.0)
            )

            # Build enriched bars
            enriched_bars = []
            bars_processed = 0

            for i, bar in enumerate(bars_data):
                bar_num = i + 1
                bar_timestamp = datetime.fromisoformat(bar['date'])

                # Load tick data for this minute
                time_str = bar_timestamp.strftime('%Y%m%d_%H%M%S')
                tick_file = self.ticks_dir / f"{symbol}_{time_str}_ticks.json"

                if not tick_file.exists():
                    # Skip this bar if no tick data
                    continue

                # Load ticks
                with open(tick_file, 'r') as f:
                    tick_data = json.load(f)

                if not tick_data:
                    continue

                # Convert to tick objects
                class MockTick:
                    def __init__(self, price, size, time):
                        self.price = price
                        self.size = size
                        self.time = time

                ticks = [MockTick(t['price'], t['size'], t['time']) for t in tick_data]

                # Calculate CVD
                try:
                    cvd_result = cvd_calculator.calculate_from_ticks(ticks)

                    # Build enriched bar
                    enriched_bar = {
                        'minute': bar_num,
                        'timestamp': bar['date'],
                        'open': bar['open'],
                        'high': bar['high'],
                        'low': bar['low'],
                        'close': bar['close'],
                        'volume': bar['volume'],
                        'tick_count': len(ticks),
                        'cvd': {
                            'value': cvd_result.cvd_value,
                            'slope': cvd_result.cvd_slope,
                            'trend': cvd_result.cvd_trend,
                            'divergence': cvd_result.divergence,
                            'data_source': cvd_result.data_source,
                            'confidence': cvd_result.confidence,
                            'imbalance_pct': cvd_result.imbalance_pct,
                            'buy_volume': cvd_result.buy_volume,
                            'sell_volume': cvd_result.sell_volume
                        }
                    }

                    enriched_bars.append(enriched_bar)
                    bars_processed += 1

                    # Log progress
                    if bars_processed % 30 == 0:
                        self.log(f"    Processed {bars_processed}/{len(bars_data)} bars...")

                except Exception as e:
                    self.log(f"    Warning: CVD calculation failed for bar {bar_num}: {str(e)}", 'WARNING')

            if not enriched_bars:
                self.log(f"    No enriched bars created", 'WARNING')
                return False

            # Save enriched bars
            enriched_data = {
                'symbol': symbol,
                'date': date.strftime('%Y-%m-%d'),
                'total_bars': len(enriched_bars),
                'bars': enriched_bars
            }

            cvd_file = self.cvd_bars_dir / f'{symbol}_{date_str}_cvd.json'
            with open(cvd_file, 'w') as f:
                json.dump(enriched_data, f, indent=2)

            self.log(f"    ✓ Built {len(enriched_bars)} CVD-enriched bars")
            return True

        except Exception as e:
            self.log(f"    ERROR building CVD-enriched bars: {str(e)}", 'ERROR')
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    """
    Test the data processor independently.
    """
    from ib_insync import IB
    import yaml

    print("Testing Data Processor...")

    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=5000)
    print("✓ Connected to IBKR")

    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'trader_config.yaml'
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Create processor
    processor = DataProcessor(ib, config)

    # Test with one symbol/date
    test_symbols = ['TSLA']
    test_date = datetime(2025, 10, 22)

    stats = processor.prepare_data_for_date(test_symbols, test_date)

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print(f"Results: {stats}")

    ib.disconnect()
