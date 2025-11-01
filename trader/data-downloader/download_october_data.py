#!/usr/bin/env python3
"""
Robust downloader for October 2025 historical data.

Features:
- Scans all October scanner result files
- Downloads 1-min bars for each symbol/date combination
- Resume capability (saves progress to state file)
- IBKR rate limiting (50 requests per 10 minutes)
- Automatic retry on connection failures
- Validates downloaded data
- Can be terminated and restarted
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
import signal

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from ib_insync import IB, Stock, util


class DownloadState:
    """Tracks download progress for resume capability"""

    def __init__(self, state_file):
        self.state_file = state_file
        self.completed = set()
        self.failed = []
        self.load_state()

    def load_state(self):
        """Load progress from state file"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                self.completed = set(state.get('completed', []))
                self.failed = state.get('failed', [])
            print(f"📂 Loaded state: {len(self.completed)} completed, {len(self.failed)} failed")
        else:
            print("📂 Starting fresh (no previous state)")

    def save_state(self):
        """Save progress to state file"""
        state = {
            'completed': list(self.completed),
            'failed': self.failed,
            'last_updated': datetime.now().isoformat()
        }
        # Atomic write
        temp_file = self.state_file + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(temp_file, self.state_file)

    def mark_completed(self, symbol, date):
        """Mark a download as completed"""
        key = f"{symbol}_{date}"
        self.completed.add(key)
        self.save_state()

    def mark_failed(self, symbol, date, error):
        """Mark a download as failed"""
        self.failed.append({
            'symbol': symbol,
            'date': date,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        })
        self.save_state()

    def is_completed(self, symbol, date):
        """Check if already downloaded"""
        key = f"{symbol}_{date}"
        return key in self.completed


class RateLimiter:
    """IBKR rate limit handler (50 requests per 10 minutes)"""

    def __init__(self, max_requests=50, window_seconds=600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_times = deque()

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove old requests outside window
        while self.request_times and now - self.request_times[0] > self.window_seconds:
            self.request_times.popleft()

        # Check if at limit
        if len(self.request_times) >= self.max_requests:
            wait_time = self.window_seconds - (now - self.request_times[0]) + 5
            print(f"⏳ Rate limit approaching, waiting {int(wait_time)}s...")
            time.sleep(wait_time)
            self.request_times.clear()

        # Record this request
        self.request_times.append(now)

    def add_pacing(self, seconds=1.0):
        """Add pacing between requests"""
        time.sleep(seconds)


class HistoricalDataDownloader:
    """Downloads and validates historical 1-min bars"""

    def __init__(self, port=7497, client_id=3000):
        self.port = port
        self.client_id = client_id
        self.ib = None
        self.rate_limiter = RateLimiter(max_requests=50, window_seconds=600)
        self.state = DownloadState('download_progress.json')
        self.running = True

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n⚠️  Interrupt received, saving state and shutting down...")
        self.running = False
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        print("✅ State saved. You can restart to continue from here.")
        sys.exit(0)

    def connect(self, max_retries=3):
        """Connect to IBKR with retry logic"""
        for attempt in range(max_retries):
            try:
                self.ib = IB()
                self.ib.connect('127.0.0.1', self.port, clientId=self.client_id)
                print(f"✅ Connected to IBKR on port {self.port}")
                return True
            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    print(f"   Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    print(f"   Max retries reached. Please check TWS/Gateway is running.")
                    return False
        return False

    def reconnect_if_needed(self):
        """Check connection and reconnect if needed"""
        if not self.ib or not self.ib.isConnected():
            print("⚠️  Connection lost, attempting to reconnect...")
            return self.connect()
        return True

    def download_bars_for_date(self, symbol, date_str, output_dir):
        """Download 1-min bars for a specific symbol/date"""

        # Check if already completed
        if self.state.is_completed(symbol, date_str):
            print(f"  ⏭️  Skipped (already completed)")
            return True

        # Check if file already exists and is valid
        date_formatted = date_str.replace('-', '')
        filename = f"{symbol}_{date_formatted}_1min.json"
        filepath = output_dir / filename

        if filepath.exists():
            if self.validate_cached_file(filepath):
                print(f"  ✅ Cached (valid)")
                self.state.mark_completed(symbol, date_str)
                return True
            else:
                print(f"  ⚠️  Cached file invalid, re-downloading...")
                filepath.unlink()

        # Ensure connection
        if not self.reconnect_if_needed():
            print(f"  ❌ Connection failed")
            self.state.mark_failed(symbol, date_str, "Connection failed")
            return False

        # Rate limiting
        self.rate_limiter.wait_if_needed()

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Parse date
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')

            # Request 1-min bars for the entire trading day
            end_datetime = f"{date_obj.strftime('%Y%m%d')} 16:00:00 US/Eastern"

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1   # UTC format
            )

            if not bars:
                print(f"  ⚠️  No data returned from IBKR")
                self.state.mark_failed(symbol, date_str, "No data returned")
                return False

            # Validate bar count
            if len(bars) < 300:
                print(f"  ⚠️  Incomplete data ({len(bars)} bars, expected ~390)")
                # Still save it, but note it
                self.state.mark_failed(symbol, date_str, f"Only {len(bars)} bars")

            # Convert to JSON format (FLAT ARRAY - matches backtester format)
            # CRITICAL: Backtester expects array of bars, NOT wrapped in object
            # Field name must be 'date' (not 'timestamp') for backtester compatibility
            data = [
                {
                    'date': bar.date.isoformat(),  # MUST be 'date' not 'timestamp'
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close),
                    'volume': int(bar.volume),
                    'average': float(bar.average),
                    'barCount': int(bar.barCount)
                }
                for bar in bars
            ]

            # Save to file (flat array format)
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            print(f"  ✅ Downloaded ({len(bars)} bars)")
            self.state.mark_completed(symbol, date_str)

            # Add pacing
            self.rate_limiter.add_pacing(1.0)

            return True

        except Exception as e:
            error_str = str(e)
            print(f"  ❌ Error: {error_str}")

            # Handle specific errors
            if 'No market data permissions' in error_str:
                self.state.mark_failed(symbol, date_str, "No subscription")
            elif 'pacing violation' in error_str.lower():
                print(f"  ⏳ Pacing violation, backing off 2 minutes...")
                time.sleep(120)
                self.state.mark_failed(symbol, date_str, "Pacing violation")
            elif 'HMDS' in error_str:
                print(f"  ⏳ HMDS error, waiting 30s...")
                time.sleep(30)
                self.state.mark_failed(symbol, date_str, "HMDS error")
            else:
                self.state.mark_failed(symbol, date_str, error_str)

            return False

    def validate_cached_file(self, filepath):
        """Validate a cached data file (flat array format)"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Check structure - should be an array of bar objects
            if not isinstance(data, list):
                return False

            if len(data) == 0:
                return False

            # Check first bar has required fields
            first_bar = data[0]
            required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
            if not all(field in first_bar for field in required_fields):
                return False

            # Check bar count (at least 200 for a partial trading day)
            if len(data) < 200:
                return False

            return True

        except Exception:
            return False

    def scan_october_files(self, scanner_dir):
        """Generate download plan for quick scan stocks across all October trading days"""
        downloads = {}  # {date: [symbols]}

        # Quick scan stock list (9 stocks)
        quick_scan_stocks = ['QQQ', 'TSLA', 'NVDA', 'AMD', 'PLTR', 'SOFI', 'HOOD', 'SMCI', 'PATH']

        # October 2025 trading days (22 days)
        october_trading_days = [
            '2025-10-01', '2025-10-02', '2025-10-03',  # Week 1
            '2025-10-06', '2025-10-07', '2025-10-08', '2025-10-09', '2025-10-10',  # Week 2
            '2025-10-13', '2025-10-14', '2025-10-15', '2025-10-16',  # Week 3
            '2025-10-20', '2025-10-21', '2025-10-22', '2025-10-23', '2025-10-24',  # Week 4
            '2025-10-27', '2025-10-28', '2025-10-29', '2025-10-30', '2025-10-31'   # Week 5
        ]

        print(f"\n📁 Quick Scan Download Plan")
        print(f"   Stocks: {', '.join(quick_scan_stocks)} ({len(quick_scan_stocks)} symbols)")
        print(f"   Dates:  {len(october_trading_days)} trading days")
        print(f"   Total:  {len(quick_scan_stocks)} × {len(october_trading_days)} = {len(quick_scan_stocks) * len(october_trading_days)} files")

        # Create download plan: same 9 stocks for every trading day
        for date in october_trading_days:
            downloads[date] = quick_scan_stocks
            print(f"   ✅ {date}: {len(quick_scan_stocks)} symbols")

        return downloads

    def run(self, scanner_dir, output_dir):
        """Main download loop"""

        # Scan for work
        downloads = self.scan_october_files(scanner_dir)

        if not downloads:
            print("\n❌ No scanner files found for October 2025")
            return

        # Calculate total work
        total_downloads = sum(len(symbols) for symbols in downloads.values())
        completed_count = len(self.state.completed)
        remaining = total_downloads - completed_count

        print(f"\n📊 Download Plan:")
        print(f"   Total dates: {len(downloads)}")
        print(f"   Total downloads: {total_downloads}")
        print(f"   Already completed: {completed_count}")
        print(f"   Remaining: {remaining}")
        print(f"\n🚀 Starting downloads...")
        print(f"   (Press Ctrl+C to stop gracefully)\n")

        # Connect to IBKR
        if not self.connect():
            print("❌ Failed to connect to IBKR. Exiting.")
            return

        # Process each date
        start_time = time.time()
        current_count = completed_count

        for date in sorted(downloads.keys()):
            if not self.running:
                break

            symbols = downloads[date]
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')

            # Skip weekends
            if date_obj.weekday() >= 5:
                print(f"\n⏭️  {date} ({day_name}) - Weekend, skipping")
                continue

            print(f"\n📅 {date} ({day_name}) - {len(symbols)} symbols")
            print("=" * 80)

            for i, symbol in enumerate(symbols, 1):
                if not self.running:
                    break

                print(f"  [{i}/{len(symbols)}] {symbol}", end='')

                success = self.download_bars_for_date(symbol, date, output_dir)

                if success:
                    current_count += 1

                # Progress update
                progress = (current_count / total_downloads) * 100
                elapsed = time.time() - start_time
                avg_time = elapsed / max(current_count - completed_count, 1)
                remaining_count = total_downloads - current_count
                eta = avg_time * remaining_count

                print(f"  [{progress:.1f}% | ETA: {eta/60:.0f}m]")

        # Final summary
        elapsed = time.time() - start_time
        print(f"\n" + "=" * 80)
        print(f"✅ Download Complete!")
        print(f"   Total completed: {current_count}/{total_downloads}")
        print(f"   Failed: {len(self.state.failed)}")
        print(f"   Duration: {elapsed/60:.1f} minutes")

        if self.state.failed:
            print(f"\n⚠️  {len(self.state.failed)} downloads failed:")
            for failure in self.state.failed[-10:]:  # Show last 10
                print(f"   - {failure['symbol']} on {failure['date']}: {failure['error']}")

        # Disconnect
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description='Download October 2025 historical data from scanner results'
    )
    parser.add_argument(
        '--scanner-dir',
        type=str,
        default='../../stockscanner/output',
        help='Scanner results directory'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='../backtest/data',
        help='Output directory for cached data'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=7497,
        help='TWS/Gateway port (7497=paper, 7496=live)'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset progress and start fresh'
    )

    args = parser.parse_args()

    # Reset state if requested
    if args.reset:
        state_file = 'download_progress.json'
        if os.path.exists(state_file):
            os.remove(state_file)
            print("✅ Progress reset")

    # Resolve paths
    script_dir = Path(__file__).parent
    scanner_dir = (script_dir / args.scanner_dir).resolve()
    output_dir = (script_dir / args.output_dir).resolve()

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("October 2025 Historical Data Downloader")
    print("=" * 80)
    print(f"Scanner directory: {scanner_dir}")
    print(f"Output directory:  {output_dir}")
    print(f"IBKR port:         {args.port}")
    print(f"Progress file:     download_progress.json")
    print("=" * 80)

    # Run downloader
    downloader = HistoricalDataDownloader(port=args.port, client_id=4000)
    downloader.run(scanner_dir, output_dir)


if __name__ == '__main__':
    main()
