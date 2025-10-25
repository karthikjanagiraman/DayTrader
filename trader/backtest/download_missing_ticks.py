#!/usr/bin/env python3
"""
Download Missing Tick Data - October 24, 2025

Downloads specific symbol-date combinations to achieve 100% coverage.
Bypasses scanner filtering to download any requested symbol.

Missing data to download (14 combinations):
- COIN: Oct 15, 21, 22
- GME: Oct 15, 21, 22
- HOOD: Oct 16, 20
- PATH: Oct 16, 20
- SMCI: Oct 16, 20
- SOFI: Oct 16, 20
"""

from ib_insync import IB, Stock
from datetime import datetime, timedelta
import json
from pathlib import Path
import time
import pytz

# Missing symbol-date combinations
MISSING_DATA = [
    ('COIN', '2025-10-15'),
    ('COIN', '2025-10-21'),
    ('COIN', '2025-10-22'),
    ('GME', '2025-10-15'),
    ('GME', '2025-10-21'),
    ('GME', '2025-10-22'),
    ('HOOD', '2025-10-16'),
    ('HOOD', '2025-10-20'),
    ('PATH', '2025-10-16'),
    ('PATH', '2025-10-20'),
    ('SMCI', '2025-10-16'),
    ('SMCI', '2025-10-20'),
    ('SOFI', '2025-10-16'),
    ('SOFI', '2025-10-20'),
]

class MissingTickDownloader:
    """Download tick data for specific symbol-date combinations"""

    def __init__(self, max_retries=5, retry_delay=2):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.ib = None
        self.client_id = 3200  # Unique client ID

        # Cache directory
        self.tick_cache_dir = Path(__file__).parent / 'data' / 'ticks'
        self.tick_cache_dir.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.stats = {
            'total_combinations': len(MISSING_DATA),
            'completed': 0,
            'failed': 0,
            'bars_downloaded': 0,
            'bars_cached': 0
        }

    def connect(self):
        """Connect to IBKR with retry"""
        for attempt in range(self.max_retries):
            try:
                if self.ib and self.ib.isConnected():
                    return True

                self.ib = IB()
                self.ib.connect('127.0.0.1', 7497, clientId=self.client_id)
                print(f"✓ Connected to IBKR (Client ID: {self.client_id})")
                return True

            except Exception as e:
                print(f"✗ Connection attempt {attempt+1}/{self.max_retries}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"  Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    return False

        return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    def download_all(self):
        """Download all missing tick data"""
        print("=" * 80)
        print("MISSING TICK DATA DOWNLOADER")
        print("=" * 80)
        print(f"Total combinations to download: {len(MISSING_DATA)}\n")

        # Connect
        if not self.connect():
            print("✗ Cannot connect to IBKR")
            return False

        # Download each combination
        for i, (symbol, date_str) in enumerate(MISSING_DATA):
            print(f"\n[{i+1}/{len(MISSING_DATA)}] {symbol} - {date_str}")

            test_date = datetime.strptime(date_str, '%Y-%m-%d')

            # Check if already exists
            if self._check_existing_data(symbol, test_date):
                print(f"  ✓ Already exists (390 files)")
                self.stats['completed'] += 1
                continue

            # Download
            success = self._download_symbol_date(symbol, test_date)

            if success:
                self.stats['completed'] += 1
                print(f"  ✓ Download complete")
            else:
                self.stats['failed'] += 1
                print(f"  ✗ Download failed")

        # Print summary
        self._print_summary()

        return self.stats['failed'] == 0

    def _check_existing_data(self, symbol, test_date):
        """Check if tick data already exists for this symbol-date"""
        date_str = test_date.strftime('%Y%m%d')
        pattern = f"{symbol}_{date_str}_*_ticks.json"
        existing = list(self.tick_cache_dir.glob(pattern))
        return len(existing) >= 380  # Allow some tolerance

    def _download_symbol_date(self, symbol, test_date):
        """Download tick data for specific symbol and date"""
        # Get 1-minute bars
        bars = self._get_bars(symbol, test_date)

        if not bars:
            print(f"  ✗ Failed to fetch 1-minute bars")
            return False

        print(f"  ✓ Fetched {len(bars)} 1-minute bars")

        # Download ticks for each bar
        bars_downloaded = 0
        bars_cached = 0
        bars_failed = 0

        for i, bar in enumerate(bars):
            bar_timestamp = bar.date

            # Check cache
            cache_file = self._get_cache_file(symbol, test_date, bar_timestamp)

            if cache_file.exists():
                bars_cached += 1
                if (i + 1) % 50 == 0:
                    print(f"  Progress: {i+1}/{len(bars)} ({bars_cached} cached, {bars_downloaded} new)")
                continue

            # Download ticks
            ticks = self._fetch_ticks(symbol, bar_timestamp)

            if ticks is None:
                bars_failed += 1
                continue

            # Save to cache
            self._save_ticks(cache_file, ticks)
            bars_downloaded += 1

            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(bars)} ({bars_cached} cached, {bars_downloaded} new)")

            # Rate limiting
            time.sleep(0.1)  # 100ms between requests

        self.stats['bars_downloaded'] += bars_downloaded
        self.stats['bars_cached'] += bars_cached

        print(f"  Summary: {bars_downloaded} downloaded, {bars_cached} cached, {bars_failed} failed")

        return bars_failed == 0

    def _get_bars(self, symbol, test_date):
        """Get 1-minute bars for symbol on date"""
        for attempt in range(self.max_retries):
            try:
                # Ensure connection
                if not self.ib or not self.ib.isConnected():
                    if not self.connect():
                        return None

                contract = Stock(symbol, 'SMART', 'USD')

                # Eastern timezone
                eastern = pytz.timezone('US/Eastern')
                market_close = eastern.localize(
                    datetime.combine(test_date, datetime.min.time().replace(hour=16, minute=0))
                )

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
                print(f"  ✗ Bar fetch attempt {attempt+1}: {e}")
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    return None

        return None

    def _fetch_ticks(self, symbol, bar_timestamp):
        """Fetch ticks for 1-minute bar"""
        for attempt in range(self.max_retries):
            try:
                # Ensure connection
                if not self.ib or not self.ib.isConnected():
                    if not self.connect():
                        return None

                contract = Stock(symbol, 'SMART', 'USD')

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
                if attempt < self.max_retries - 1:
                    time.sleep(0.5)
                else:
                    return None

        return None

    def _get_cache_file(self, symbol, test_date, timestamp):
        """Get cache file path"""
        date_str = test_date.strftime('%Y%m%d')
        time_str = timestamp.strftime('%H%M%S')
        return self.tick_cache_dir / f'{symbol}_{date_str}_{time_str}_ticks.json'

    def _save_ticks(self, cache_file, ticks):
        """Save ticks to cache"""
        tick_data = [
            {'time': tick.time.isoformat(), 'price': tick.price, 'size': tick.size}
            for tick in ticks
        ]

        with open(cache_file, 'w') as f:
            json.dump(tick_data, f)

    def _print_summary(self):
        """Print download summary"""
        print("\n" + "=" * 80)
        print("DOWNLOAD SUMMARY")
        print("=" * 80)
        print(f"Total combinations: {self.stats['total_combinations']}")
        print(f"  Completed: {self.stats['completed']}")
        print(f"  Failed: {self.stats['failed']}")
        print(f"\nBars:")
        print(f"  Downloaded: {self.stats['bars_downloaded']}")
        print(f"  Cached: {self.stats['bars_cached']}")
        print("=" * 80)


def main():
    """Main entry point"""
    downloader = MissingTickDownloader()

    try:
        success = downloader.download_all()

        if success:
            print("\n✅ All missing data downloaded successfully!")
            print("\nRun validate_tick_completeness.py to verify 100% coverage")
            return 0
        else:
            print("\n⚠️  Download completed with some failures")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
        return 2

    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 3

    finally:
        downloader.disconnect()


if __name__ == '__main__':
    import sys
    sys.exit(main())
