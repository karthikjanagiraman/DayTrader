#!/usr/bin/env python3
"""
Tick Data Downloader for Backtesting (October 21, 2025)

Downloads all tick data needed for CVD-enriched backtesting from IBKR.
Handles connection issues with retry logic and can resume interrupted downloads.

Usage:
    python3 download_tick_data.py --date 2025-10-21 --scanner ../stockscanner/output/scanner_results_20251021.json
"""

from ib_insync import IB, Stock
from datetime import datetime, timedelta
import json
import argparse
from pathlib import Path
import sys
import time
import pytz

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from strategy import PS60Strategy

class TickDataDownloader:
    """
    Robust tick data downloader with connection resilience
    """

    def __init__(self, scanner_file, test_date, max_retries=5, retry_delay=2):
        """
        Initialize downloader

        Args:
            scanner_file: Path to scanner results JSON
            test_date: Date to download data for (datetime object)
            max_retries: Maximum retry attempts per symbol
            retry_delay: Initial delay between retries (seconds, exponential backoff)
        """
        self.scanner_file = scanner_file
        self.test_date = test_date
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # IBKR connection
        self.ib = None
        self.client_id = 3100  # Unique client ID for downloader

        # Cache directories
        self.tick_cache_dir = Path(__file__).parent / 'data' / 'ticks'
        self.tick_cache_dir.mkdir(parents=True, exist_ok=True)

        # Progress tracking
        self.progress_file = Path(__file__).parent / 'data' / f'download_progress_{test_date.strftime("%Y%m%d")}.json'
        self.progress = self._load_progress()

        # Statistics
        self.stats = {
            'symbols_total': 0,
            'symbols_completed': 0,
            'symbols_failed': 0,
            'bars_total': 0,
            'bars_cached': 0,
            'bars_downloaded': 0,
            'connection_losses': 0,
            'retries': 0
        }

        # Load scanner results
        with open(scanner_file) as f:
            self.scanner_results = json.load(f)

        print(f"\n{'='*80}")
        print(f"TICK DATA DOWNLOADER - {test_date.strftime('%Y-%m-%d')}")
        print(f"{'='*80}")
        print(f"Scanner: {scanner_file}")
        print(f"Max retries: {max_retries}")
        print(f"Retry delay: {retry_delay}s (exponential backoff)")

    def _load_progress(self):
        """Load download progress from file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {}

    def _save_progress(self):
        """Save download progress to file"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def connect(self):
        """Connect to IBKR with retry logic"""
        for attempt in range(self.max_retries):
            try:
                if self.ib and self.ib.isConnected():
                    return True

                self.ib = IB()
                self.ib.connect('127.0.0.1', 7497, clientId=self.client_id)
                print(f"✓ Connected to IBKR (Client ID: {self.client_id})")
                return True

            except Exception as e:
                print(f"✗ Connection attempt {attempt+1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"  Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print(f"✗ Failed to connect after {self.max_retries} attempts")
                    return False

        return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    def download_all_tick_data(self):
        """Download tick data for all symbols in scanner"""
        # Filter scanner to get watchlist
        from strategy import PS60Strategy
        import yaml

        config_path = Path(__file__).parent.parent / 'config' / 'trader_config.yaml'
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        strategy = PS60Strategy(config, ib_connection=None)
        watchlist = strategy.filter_scanner_results(self.scanner_results)

        self.stats['symbols_total'] = len(watchlist)
        print(f"\n{'='*80}")
        print(f"Watchlist: {len(watchlist)} symbols")
        print(f"{'='*80}\n")

        # Connect to IBKR
        if not self.connect():
            print("✗ Cannot proceed without IBKR connection")
            return False

        # Download data for each symbol
        for i, stock in enumerate(watchlist):
            symbol = stock['symbol']
            print(f"\n[{i+1}/{len(watchlist)}] {symbol}")

            # Check if already completed
            if self.progress.get(symbol, {}).get('status') == 'completed':
                print(f"  ✓ Already downloaded (skipping)")
                self.stats['symbols_completed'] += 1
                continue

            # Download tick data for this symbol
            success = self._download_symbol_ticks(symbol)

            if success:
                self.stats['symbols_completed'] += 1
                self.progress[symbol] = {
                    'status': 'completed',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                self.stats['symbols_failed'] += 1
                self.progress[symbol] = {
                    'status': 'failed',
                    'timestamp': datetime.now().isoformat()
                }

            # Save progress after each symbol
            self._save_progress()

        # Final statistics
        self._print_statistics()

        return self.stats['symbols_failed'] == 0

    def _download_symbol_ticks(self, symbol):
        """
        Download tick data for a specific symbol

        Args:
            symbol: Stock symbol

        Returns:
            bool: True if successful, False otherwise
        """
        # Get 1-minute bars for the trading day
        bars = self._get_bars_with_retry(symbol)

        if not bars:
            print(f"  ✗ Failed to get 1-minute bars")
            return False

        print(f"  ✓ Fetched {len(bars)} 1-minute bars")
        self.stats['bars_total'] += len(bars)

        # Download ticks for each 1-minute bar (OPTIMIZED: 1 request per minute instead of 12)
        bars_downloaded = 0
        bars_cached = 0
        bars_failed = 0

        for i, bar in enumerate(bars):
            bar_timestamp = bar.date

            # Check cache first
            cache_file = self._get_tick_cache_file(symbol, bar_timestamp)

            if cache_file.exists():
                bars_cached += 1
                # Progress update every 30 bars
                if (i + 1) % 30 == 0:
                    print(f"  Progress: {i+1}/{len(bars)} bars ({bars_cached} cached, {bars_downloaded} downloaded, {bars_failed} failed)")
                continue

            # Download 1 minute of ticks from IBKR with retry
            ticks = self._fetch_ticks_with_retry(symbol, bar_timestamp)

            if ticks is None:
                bars_failed += 1
                print(f"  ✗ Bar {i+1}/{len(bars)}: Failed")
                continue

            # Save to cache
            self._save_ticks_to_cache(symbol, bar_timestamp, ticks)
            bars_downloaded += 1

            # Progress update every 30 bars
            if (i + 1) % 30 == 0:
                print(f"  Progress: {i+1}/{len(bars)} bars ({bars_cached} cached, {bars_downloaded} downloaded, {bars_failed} failed)")

        self.stats['bars_cached'] += bars_cached
        self.stats['bars_downloaded'] += bars_downloaded

        if bars_failed > 0:
            print(f"  ⚠️  Completed with {bars_failed} failed bars")
            return False
        else:
            print(f"  ✓ Completed ({bars_cached} cached, {bars_downloaded} downloaded)")
            return True

    def _get_bars_with_retry(self, symbol):
        """Get 1-minute bars with retry logic"""
        for attempt in range(self.max_retries):
            try:
                # Ensure connection
                if not self.ib or not self.ib.isConnected():
                    if not self.connect():
                        raise Exception("Cannot reconnect to IBKR")

                contract = Stock(symbol, 'SMART', 'USD')

                # Eastern timezone for market hours
                eastern = pytz.timezone('US/Eastern')
                market_open = eastern.localize(datetime.combine(self.test_date, datetime.min.time().replace(hour=9, minute=30)))
                market_close = eastern.localize(datetime.combine(self.test_date, datetime.min.time().replace(hour=16, minute=0)))

                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=market_close,
                    durationStr='1 D',
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )

                return bars

            except Exception as e:
                print(f"  ✗ Bar fetch attempt {attempt+1}/{self.max_retries}: {e}")

                # Check if connection lost
                if "1100" in str(e) or "not connected" in str(e).lower():
                    self.stats['connection_losses'] += 1
                    print(f"  ⚠️  Connection lost, reconnecting...")
                    self.disconnect()
                    if not self.connect():
                        print(f"  ✗ Reconnection failed")
                        return None

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"  Retrying in {delay}s...")
                    time.sleep(delay)
                    self.stats['retries'] += 1
                else:
                    return None

        return None

    def _fetch_ticks_with_retry(self, symbol, bar_timestamp):
        """
        Fetch historical ticks with retry logic

        OPTIMIZED: Fetches 1 minute of ticks per request (instead of 5-second intervals)
        Reduces total requests from 42,120 to 3,510 (92% reduction)
        """
        for attempt in range(self.max_retries):
            try:
                # Ensure connection
                if not self.ib or not self.ib.isConnected():
                    if not self.connect():
                        raise Exception("Cannot reconnect to IBKR")

                contract = Stock(symbol, 'SMART', 'USD')

                # Fetch 60 seconds of ticks (1 minute)
                start_time = bar_timestamp
                end_time = bar_timestamp + timedelta(seconds=60)

                ticks = self.ib.reqHistoricalTicks(
                    contract,
                    startDateTime=start_time,
                    endDateTime=end_time,
                    numberOfTicks=1000,
                    whatToShow='TRADES',
                    useRth=True
                )

                return ticks

            except Exception as e:
                # Check if connection lost
                if "1100" in str(e) or "not connected" in str(e).lower():
                    self.stats['connection_losses'] += 1
                    self.disconnect()
                    if not self.connect():
                        return None

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                    self.stats['retries'] += 1
                else:
                    return None

        return None

    def _get_tick_cache_file(self, symbol, timestamp):
        """Get cache file path for tick data"""
        date_str = self.test_date.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S')
        return self.tick_cache_dir / f'{symbol}_{date_str}_{time_str}_ticks.json'

    def _save_ticks_to_cache(self, symbol, timestamp, ticks):
        """Save tick data to cache file"""
        cache_file = self._get_tick_cache_file(symbol, timestamp)

        # Convert ticks to JSON-serializable format
        tick_data = [
            {'time': tick.time.isoformat(), 'price': tick.price, 'size': tick.size}
            for tick in ticks
        ]

        with open(cache_file, 'w') as f:
            json.dump(tick_data, f)

    def _print_statistics(self):
        """Print download statistics"""
        print(f"\n{'='*80}")
        print(f"DOWNLOAD COMPLETE")
        print(f"{'='*80}")
        print(f"Symbols:")
        print(f"  Total: {self.stats['symbols_total']}")
        print(f"  Completed: {self.stats['symbols_completed']}")
        print(f"  Failed: {self.stats['symbols_failed']}")
        print(f"\nBars:")
        print(f"  Total: {self.stats['bars_total']}")
        print(f"  Cached (pre-existing): {self.stats['bars_cached']}")
        print(f"  Downloaded: {self.stats['bars_downloaded']}")
        print(f"\nResilience:")
        print(f"  Connection losses: {self.stats['connection_losses']}")
        print(f"  Retry attempts: {self.stats['retries']}")
        print(f"\nProgress file: {self.progress_file}")
        print(f"{'='*80}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Download tick data for backtesting')
    parser.add_argument('--date', required=True, help='Date to download (YYYY-MM-DD)')
    parser.add_argument('--scanner', required=True, help='Path to scanner results JSON')
    parser.add_argument('--max-retries', type=int, default=5, help='Max retry attempts per symbol')
    parser.add_argument('--retry-delay', type=int, default=2, help='Initial retry delay (seconds)')

    args = parser.parse_args()

    # Parse date
    test_date = datetime.strptime(args.date, '%Y-%m-%d')

    # Create downloader
    downloader = TickDataDownloader(
        scanner_file=args.scanner,
        test_date=test_date,
        max_retries=args.max_retries,
        retry_delay=args.retry_delay
    )

    try:
        # Download all data
        success = downloader.download_all_tick_data()

        if success:
            print("\n✅ All data downloaded successfully!")
            sys.exit(0)
        else:
            print("\n⚠️  Download completed with some failures")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        print(f"Progress saved to: {downloader.progress_file}")
        print("Run again to resume from where you left off")
        sys.exit(2)

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)

    finally:
        downloader.disconnect()


if __name__ == '__main__':
    main()
