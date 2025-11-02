#!/usr/bin/env python3
"""
Enhanced Historical Data Downloader with CVD Support.

Features:
- Downloads 1-min OHLCV bars
- Downloads tick data for CVD calculation
- Builds CVD-enriched bars (combining OHLCV + CVD metrics)
- Flexible date range configuration (not limited to October)
- Resume capability (saves progress to state file)
- IBKR rate limiting (50 requests per 10 minutes)
- Automatic retry on connection failures
- Validates downloaded data
- Can be terminated and restarted

Usage:
    # Download specific date range
    python3 download_october_data.py --start-date 2025-10-01 --end-date 2025-10-31

    # Download single day
    python3 download_october_data.py --start-date 2025-10-31 --end-date 2025-10-31

    # Download from scanner files (auto-detect dates)
    python3 download_october_data.py --scanner-dir ../../stockscanner/output

    # Quick scan stocks only (9 symbols)
    python3 download_october_data.py --start-date 2025-10-01 --end-date 2025-10-31 --quick-scan

    # Skip CVD building (1-min bars + ticks only)
    python3 download_october_data.py --start-date 2025-10-31 --end-date 2025-10-31 --no-cvd
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
from indicators.cvd_calculator import CVDCalculator


class DownloadState:
    """Tracks download progress for resume capability"""

    def __init__(self, state_file):
        self.state_file = state_file
        self.completed_bars = set()
        self.completed_ticks = set()
        self.completed_cvd = set()
        self.failed = []
        self.load_state()

    def load_state(self):
        """Load progress from state file"""
        if os.path.exists(self.state_file):
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                # Support both old format (completed) and new format (completed_bars, completed_ticks, completed_cvd)
                if 'completed' in state:
                    # Old format - migrate to new
                    self.completed_bars = set(state.get('completed', []))
                    self.completed_ticks = set()
                    self.completed_cvd = set()
                else:
                    # New format
                    self.completed_bars = set(state.get('completed_bars', []))
                    self.completed_ticks = set(state.get('completed_ticks', []))
                    self.completed_cvd = set(state.get('completed_cvd', []))
                self.failed = state.get('failed', [])
            print(f"📂 Loaded state:")
            print(f"   1-min bars: {len(self.completed_bars)} completed")
            print(f"   Tick data: {len(self.completed_ticks)} completed")
            print(f"   CVD bars: {len(self.completed_cvd)} completed")
            print(f"   Failed: {len(self.failed)}")
        else:
            print("📂 Starting fresh (no previous state)")

    def save_state(self):
        """Save progress to state file"""
        state = {
            'completed_bars': list(self.completed_bars),
            'completed_ticks': list(self.completed_ticks),
            'completed_cvd': list(self.completed_cvd),
            'failed': self.failed,
            'last_updated': datetime.now().isoformat()
        }
        # Atomic write
        temp_file = self.state_file + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(temp_file, self.state_file)

    def mark_bars_completed(self, symbol, date):
        key = f"{symbol}_{date}"
        self.completed_bars.add(key)
        self.save_state()

    def mark_ticks_completed(self, symbol, date):
        key = f"{symbol}_{date}"
        self.completed_ticks.add(key)
        self.save_state()

    def mark_cvd_completed(self, symbol, date):
        key = f"{symbol}_{date}"
        self.completed_cvd.add(key)
        self.save_state()

    def mark_failed(self, symbol, date, step, error):
        """Mark a download as failed"""
        self.failed.append({
            'symbol': symbol,
            'date': date,
            'step': step,
            'error': str(error),
            'timestamp': datetime.now().isoformat()
        })
        self.save_state()

    def is_bars_completed(self, symbol, date):
        return f"{symbol}_{date}" in self.completed_bars

    def is_ticks_completed(self, symbol, date):
        return f"{symbol}_{date}" in self.completed_ticks

    def is_cvd_completed(self, symbol, date):
        return f"{symbol}_{date}" in self.completed_cvd


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
    """Downloads and validates historical 1-min bars + tick data + CVD bars"""

    def __init__(self, port=7497, client_id=3000, enable_cvd=True):
        self.port = port
        self.client_id = client_id
        self.ib = None
        self.rate_limiter = RateLimiter(max_requests=50, window_seconds=600)
        self.state = DownloadState('download_progress.json')
        self.running = True
        self.enable_cvd = enable_cvd

        # CVD calculator (only if enabled)
        if self.enable_cvd:
            self.cvd_calculator = CVDCalculator(slope_lookback=5, imbalance_threshold=10.0)
        else:
            self.cvd_calculator = None

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
        if self.state.is_bars_completed(symbol, date_str):
            print(f"  ⏭️  Bars skipped (already completed)")
            return True

        # Check if file already exists and is valid
        date_formatted = date_str.replace('-', '')
        filename = f"{symbol}_{date_formatted}_1min.json"
        filepath = output_dir / filename

        if filepath.exists():
            if self.validate_cached_file(filepath):
                print(f"  ✅ Bars cached (valid)")
                self.state.mark_bars_completed(symbol, date_str)
                return True
            else:
                print(f"  ⚠️  Cached file invalid, re-downloading...")
                filepath.unlink()

        # Ensure connection
        if not self.reconnect_if_needed():
            print(f"  ❌ Connection failed")
            self.state.mark_failed(symbol, date_str, "bars", "Connection failed")
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
                self.state.mark_failed(symbol, date_str, "bars", "No data returned")
                return False

            # Validate bar count
            if len(bars) < 300:
                print(f"  ⚠️  Incomplete data ({len(bars)} bars, expected ~390)")
                # Still save it, but note it
                self.state.mark_failed(symbol, date_str, "bars", f"Only {len(bars)} bars")

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

            print(f"  ✅ Bars downloaded ({len(bars)} bars)")
            self.state.mark_bars_completed(symbol, date_str)

            # Add pacing
            self.rate_limiter.add_pacing(1.0)

            return True

        except Exception as e:
            error_str = str(e)
            print(f"  ❌ Bars error: {error_str}")

            # Handle specific errors
            if 'No market data permissions' in error_str:
                self.state.mark_failed(symbol, date_str, "bars", "No subscription")
            elif 'pacing violation' in error_str.lower():
                print(f"  ⏳ Pacing violation, backing off 2 minutes...")
                time.sleep(120)
                self.state.mark_failed(symbol, date_str, "bars", "Pacing violation")
            elif 'HMDS' in error_str:
                print(f"  ⏳ HMDS error, waiting 30s...")
                time.sleep(30)
                self.state.mark_failed(symbol, date_str, "bars", "HMDS error")
            else:
                self.state.mark_failed(symbol, date_str, "bars", error_str)

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

    def download_tick_data(self, symbol, date_str, ticks_dir):
        """Download tick data for entire trading day (390 minutes)"""

        # Check if already completed
        if self.state.is_ticks_completed(symbol, date_str):
            print(f"  ⏭️  Ticks skipped (already completed)")
            return True

        # Ensure connection
        if not self.reconnect_if_needed():
            print(f"  ❌ Ticks: Connection failed")
            self.state.mark_failed(symbol, date_str, "ticks", "Connection failed")
            return False

        # Create ticks directory
        ticks_dir.mkdir(parents=True, exist_ok=True)

        # Parse date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_formatted = date_str.replace('-', '')

        # Create contract
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
        except Exception as e:
            print(f"  ❌ Ticks: Failed to qualify contract: {e}")
            self.state.mark_failed(symbol, date_str, "ticks", str(e))
            return False

        # Trading day: 09:30 - 16:00 ET (390 minutes)
        start_time = date_obj.replace(hour=9, minute=30, second=0)
        tick_count = 0
        failed_minutes = 0

        print(f"  📥 Downloading ticks (390 minutes)...", end=' ', flush=True)

        for minute_offset in range(390):
            if not self.running:
                print(f"\n  ⚠️  Interrupted at minute {minute_offset}")
                return False

            # Calculate timestamp for this minute
            current_time = start_time + timedelta(minutes=minute_offset)
            time_str = current_time.strftime('%H%M%S')

            # Check if tick file already exists
            tick_file = ticks_dir / f'{symbol}_{date_formatted}_{time_str}_ticks.json'
            if tick_file.exists():
                tick_count += 1
                continue

            # Rate limiting
            self.rate_limiter.wait_if_needed()

            try:
                # Request tick data for this minute
                end_datetime = current_time + timedelta(minutes=1)

                ticks = self.ib.reqHistoricalTicks(
                    contract,
                    startDateTime='',
                    endDateTime=end_datetime,
                    numberOfTicks=1000,
                    whatToShow='TRADES',
                    useRth=True
                )

                if not ticks:
                    failed_minutes += 1
                    continue

                # Save ticks to file (flat array format)
                tick_data = [
                    {
                        'time': tick.time.isoformat(),
                        'price': float(tick.price),
                        'size': int(tick.size)
                    }
                    for tick in ticks
                ]

                with open(tick_file, 'w') as f:
                    json.dump(tick_data, f, indent=2)

                tick_count += 1

                # Progress indicator every 50 minutes
                if (minute_offset + 1) % 50 == 0:
                    print(f"{minute_offset + 1}/390", end=' ', flush=True)

            except Exception as e:
                error_str = str(e)

                # Handle specific errors
                if 'No market data permissions' in error_str:
                    print(f"\n  ❌ Ticks: No subscription")
                    self.state.mark_failed(symbol, date_str, "ticks", "No subscription")
                    return False
                elif 'pacing violation' in error_str.lower():
                    print(f"\n  ⏳ Pacing violation, backing off...")
                    time.sleep(120)
                    failed_minutes += 1
                elif 'Not connected' in error_str or 'Socket' in error_str:
                    # Try to reconnect
                    print(f"\n  ⚠️  Connection lost, reconnecting...")
                    if not self.reconnect_if_needed():
                        print(f"  ❌ Ticks: Reconnection failed")
                        self.state.mark_failed(symbol, date_str, "ticks", "Connection lost")
                        return False
                    failed_minutes += 1
                else:
                    failed_minutes += 1

            # Small pacing between requests
            time.sleep(0.5)

        # Summary
        success_rate = (tick_count / 390) * 100
        print(f"\n  ✅ Ticks: {tick_count}/390 minutes ({success_rate:.1f}%)")

        # Mark as completed if we got at least 50% of ticks
        if tick_count >= 195:
            self.state.mark_ticks_completed(symbol, date_str)
            return True
        else:
            print(f"  ❌ Ticks: Insufficient coverage ({tick_count}/390)")
            self.state.mark_failed(symbol, date_str, "ticks", f"Only {tick_count}/390 minutes")
            return False

    def build_cvd_bars(self, symbol, date_str, bars_file, ticks_dir, cvd_dir):
        """Build CVD-enriched bars from 1-min bars + tick data"""

        # Check if CVD is enabled
        if not self.enable_cvd:
            return True

        # Check if already completed
        if self.state.is_cvd_completed(symbol, date_str):
            print(f"  ⏭️  CVD skipped (already completed)")
            return True

        # Check if 1-min bars exist
        if not bars_file.exists():
            print(f"  ❌ CVD: Missing 1-min bars")
            self.state.mark_failed(symbol, date_str, "cvd", "Missing 1-min bars")
            return False

        # Load 1-min bars
        try:
            with open(bars_file) as f:
                bars_data = json.load(f)
        except Exception as e:
            print(f"  ❌ CVD: Failed to load bars: {e}")
            self.state.mark_failed(symbol, date_str, "cvd", f"Failed to load bars: {e}")
            return False

        if len(bars_data) < 300:
            print(f"  ❌ CVD: Incomplete bars ({len(bars_data)})")
            self.state.mark_failed(symbol, date_str, "cvd", f"Incomplete bars ({len(bars_data)})")
            return False

        # Build CVD bars
        date_formatted = date_str.replace('-', '')
        cvd_bars = []

        print(f"  🔧 Building CVD bars...", end=' ', flush=True)

        for i, bar in enumerate(bars_data, 1):
            bar_time = datetime.fromisoformat(bar['date'])
            time_str = bar_time.strftime('%H%M%S')

            # Load ticks for this minute
            tick_file = ticks_dir / f'{symbol}_{date_formatted}_{time_str}_ticks.json'

            if not tick_file.exists():
                # No ticks for this minute - skip
                continue

            try:
                with open(tick_file) as f:
                    tick_data = json.load(f)
            except Exception:
                continue

            # Convert to tick objects
            class Tick:
                def __init__(self, price, size):
                    self.price = price
                    self.size = size

            # Handle both flat array and wrapped format
            if isinstance(tick_data, list):
                ticks = [Tick(t['price'], t['size']) for t in tick_data]
            elif isinstance(tick_data, dict) and 'ticks' in tick_data:
                ticks = [Tick(t['price'], t['size']) for t in tick_data['ticks']]
            else:
                continue

            if not ticks:
                continue

            # Calculate CVD
            cvd_result = self.cvd_calculator.calculate_from_ticks(ticks)

            cvd_bar = {
                'minute': i,
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
                    'sell_volume': cvd_result.sell_volume,
                    'price_direction': cvd_result.price_direction,
                    'price_change_pct': cvd_result.price_change_pct,
                    'signals_aligned': cvd_result.signals_aligned,
                    'validation_reason': cvd_result.validation_reason
                }
            }
            cvd_bars.append(cvd_bar)

        if not cvd_bars:
            print(f"FAILED (no CVD data)")
            self.state.mark_failed(symbol, date_str, "cvd", "No CVD data generated")
            return False

        # Save CVD bars
        cvd_dir.mkdir(parents=True, exist_ok=True)
        cvd_file = cvd_dir / f'{symbol}_{date_formatted}_cvd.json'

        output = {
            'symbol': symbol,
            'date': date_str,
            'total_bars': len(cvd_bars),
            'bars': cvd_bars
        }

        try:
            with open(cvd_file, 'w') as f:
                json.dump(output, f, indent=2)
        except Exception as e:
            print(f"FAILED ({e})")
            self.state.mark_failed(symbol, date_str, "cvd", f"Failed to save: {e}")
            return False

        print(f"✅ ({len(cvd_bars)} bars)")
        self.state.mark_cvd_completed(symbol, date_str)
        return True

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
        """Main download loop - Three-stage pipeline: bars → ticks → CVD"""

        # Scan for work
        downloads = self.scan_october_files(scanner_dir)

        if not downloads:
            print("\n❌ No scanner files found for October 2025")
            return

        # Create directories
        ticks_dir = output_dir / 'ticks'
        cvd_dir = output_dir / 'cvd_bars'
        ticks_dir.mkdir(parents=True, exist_ok=True)
        cvd_dir.mkdir(parents=True, exist_ok=True)

        # Calculate total work
        total_symbols_dates = sum(len(symbols) for symbols in downloads.values())

        print(f"\n📊 Download Plan (3-Stage Pipeline):")
        print(f"   Total dates: {len(downloads)}")
        print(f"   Total symbol×date combinations: {total_symbols_dates}")
        print(f"   Stages: 1-min bars → tick data → CVD bars")
        print(f"   Already completed:")
        print(f"      1-min bars: {len(self.state.completed_bars)}")
        print(f"      Tick data: {len(self.state.completed_ticks)}")
        print(f"      CVD bars: {len(self.state.completed_cvd)}")
        print(f"\n🚀 Starting downloads...")
        print(f"   (Press Ctrl+C to stop gracefully)\n")

        # Connect to IBKR
        if not self.connect():
            print("❌ Failed to connect to IBKR. Exiting.")
            return

        # Process each date
        start_time = time.time()
        bars_success = 0
        ticks_success = 0
        cvd_success = 0

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

                print(f"[{i}/{len(symbols)}] {symbol}")

                # Stage 1: Download 1-min bars
                bars_file = output_dir / f"{symbol}_{date.replace('-', '')}_1min.json"
                if self.download_bars_for_date(symbol, date, output_dir):
                    bars_success += 1
                else:
                    print(f"  ⚠️  Skipping ticks and CVD (bars failed)")
                    continue

                # Stage 2: Download tick data
                if self.download_tick_data(symbol, date, ticks_dir):
                    ticks_success += 1
                else:
                    print(f"  ⚠️  Skipping CVD (ticks failed)")
                    continue

                # Stage 3: Build CVD bars
                if self.build_cvd_bars(symbol, date, bars_file, ticks_dir, cvd_dir):
                    cvd_success += 1

                # Progress update
                bars_progress = (bars_success / total_symbols_dates) * 100
                ticks_progress = (ticks_success / total_symbols_dates) * 100
                cvd_progress = (cvd_success / total_symbols_dates) * 100

                elapsed = time.time() - start_time
                avg_time_per_symbol = elapsed / max(i, 1)
                remaining_symbols = total_symbols_dates - (i + (date.count('-') * len(symbols)))
                eta = avg_time_per_symbol * remaining_symbols

                print(f"  📊 Progress: Bars {bars_progress:.0f}% | Ticks {ticks_progress:.0f}% | CVD {cvd_progress:.0f}% | ETA: {eta/60:.0f}m\n")

        # Final summary
        elapsed = time.time() - start_time
        print(f"\n" + "=" * 80)
        print(f"✅ Download Complete!")
        print(f"=" * 80)
        print(f"   1-min bars:  {bars_success}/{total_symbols_dates} ({(bars_success/total_symbols_dates)*100:.1f}%)")
        print(f"   Tick data:   {ticks_success}/{total_symbols_dates} ({(ticks_success/total_symbols_dates)*100:.1f}%)")
        print(f"   CVD bars:    {cvd_success}/{total_symbols_dates} ({(cvd_success/total_symbols_dates)*100:.1f}%)")
        print(f"   Failed:      {len(self.state.failed)}")
        print(f"   Duration:    {elapsed/60:.1f} minutes")

        if self.state.failed:
            # Group failures by step
            failures_by_step = {}
            for failure in self.state.failed:
                step = failure.get('step', 'unknown')
                if step not in failures_by_step:
                    failures_by_step[step] = []
                failures_by_step[step].append(failure)

            print(f"\n⚠️  Failures by stage:")
            for step, failures in failures_by_step.items():
                print(f"   {step}: {len(failures)} failures")
                for failure in failures[:3]:  # Show first 3
                    print(f"      - {failure['symbol']} on {failure['date']}: {failure['error']}")
                if len(failures) > 3:
                    print(f"      ... and {len(failures)-3} more")

        # Disconnect
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description='Historical Data Downloader with CVD Support',
        epilog='''
Examples:
  # Download all October 2025 (default)
  python3 download_october_data.py

  # Download specific date range
  python3 download_october_data.py --start-date 2025-10-01 --end-date 2025-10-31

  # Download single day
  python3 download_october_data.py --start-date 2025-10-31 --end-date 2025-10-31

  # Quick scan stocks only (9 symbols)
  python3 download_october_data.py --quick-scan

  # Skip CVD building (bars + ticks only)
  python3 download_october_data.py --no-cvd
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--start-date',
        type=str,
        help='Start date YYYY-MM-DD (default: 2025-10-01)'
    )
    parser.add_argument(
        '--end-date',
        type=str,
        help='End date YYYY-MM-DD (default: 2025-10-31)'
    )
    parser.add_argument(
        '--quick-scan',
        action='store_true',
        help='Use quick scan stocks only (QQQ, TSLA, NVDA, AMD, PLTR, SOFI, HOOD, SMCI, PATH)'
    )
    parser.add_argument(
        '--no-cvd',
        action='store_true',
        help='Skip CVD building (download bars + ticks only)'
    )
    parser.add_argument(
        '--scanner-dir',
        type=str,
        default='../../stockscanner/output',
        help='Scanner results directory (default: ../../stockscanner/output)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='../backtest/data',
        help='Output directory for cached data (default: ../backtest/data)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=7497,
        help='TWS/Gateway port (7497=paper, 7496=live) (default: 7497)'
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

    # Determine CVD mode
    enable_cvd = not args.no_cvd

    print("=" * 80)
    print("Historical Data Downloader with CVD Support")
    print("=" * 80)
    print(f"Scanner directory: {scanner_dir}")
    print(f"Output directory:  {output_dir}")
    print(f"IBKR port:         {args.port}")
    print(f"CVD enabled:       {enable_cvd}")
    print(f"Progress file:     download_progress.json")
    if args.start_date and args.end_date:
        print(f"Date range:        {args.start_date} to {args.end_date}")
    else:
        print(f"Date range:        October 2025 (default)")
    if args.quick_scan:
        print(f"Mode:              Quick scan (9 stocks)")
    print("=" * 80)

    # Run downloader
    downloader = HistoricalDataDownloader(port=args.port, client_id=4000, enable_cvd=enable_cvd)
    downloader.run(scanner_dir, output_dir)


if __name__ == '__main__':
    main()
