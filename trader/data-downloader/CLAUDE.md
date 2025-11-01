# CLAUDE.md - Data Downloader Guide

This folder contains tools and scripts for downloading, caching, and managing historical market data from IBKR.

## 📁 Folder Purpose

The `data-downloader/` folder provides:
- **Batch historical data downloaders** - Pre-fetch data for multiple dates/symbols
- **Cache management tools** - Organize, validate, and clean cached data
- **Data validation scripts** - Verify data integrity and completeness
- **IBKR rate limit handling** - Smart pacing to avoid API throttling
- **Data format converters** - Transform between different data formats

## 🎯 Why Separate Data Downloader?

**Problem**: Running backtests on-demand is slow because:
- Each backtest fetches historical data from IBKR in real-time
- IBKR has rate limits (60 requests per 10 minutes)
- Multiple concurrent backtests overwhelm the API
- Network issues cause incomplete data fetches

**Solution**: Pre-download and cache data in batches
- Download once, backtest many times
- Run overnight batch jobs to populate cache
- Validate data completeness before backtesting
- Reuse cached data across multiple strategy tests

## 📊 Data Types and Storage

### Data Storage Structure

```
trader/backtest/data/
├── SYMBOL_YYYYMMDD_1min.json           # 1-minute OHLCV bars
├── SYMBOL_YYYYMMDD_1min_bars.json      # Alternative format
├── cvd_bars/
│   └── SYMBOL_YYYYMMDD_cvd.json        # Cumulative Volume Delta bars
└── ticks/
    └── SYMBOL_YYYYMMDD_HHMMSS_ticks.json  # Tick-by-tick data (30-60 days max)
```

### 1-Minute Bar Format

**File**: `AMD_20251031_1min.json`

**Structure** (FLAT ARRAY - matches backtester requirement):
```json
[
  {
    "date": "2025-10-31T09:30:00-04:00",
    "open": 162.45,
    "high": 162.78,
    "low": 162.32,
    "close": 162.65,
    "volume": 245678,
    "average": 162.55,
    "barCount": 1523
  },
  {
    "date": "2025-10-31T09:31:00-04:00",
    "open": 162.65,
    "high": 162.92,
    "low": 162.58,
    "close": 162.88,
    "volume": 189234,
    "average": 162.75,
    "barCount": 1234
  }
]
```

**CRITICAL NOTES**:
- ✅ **Flat array format** - NOT wrapped in object with metadata
- ✅ **Field name is `date`** - NOT `timestamp` (backtester requires this exact name)
- ✅ **ISO format timestamps** - Includes timezone offset (e.g., -04:00 for ET)
- ✅ **All fields required**: open, high, low, close, volume, average, barCount

**Coverage**: Full trading day (09:30 - 16:00 ET) = 390 bars (6.5 hours × 60 min)

### CVD Bar Format

**File**: `cvd_bars/AMD_20251031_cvd.json`

**Structure**:
```json
{
  "symbol": "AMD",
  "date": "2025-10-31",
  "cvd_bars": [
    {
      "timestamp": "2025-10-31T09:30:00-04:00",
      "buy_volume": 145678,
      "sell_volume": 100000,
      "net_volume": 45678,
      "cumulative_volume_delta": 45678,
      "buy_percentage": 59.3,
      "sell_percentage": 40.7,
      "imbalance": 19.3
    }
  ],
  "total_bars": 390
}
```

**Note**: CVD data is computed from tick data or order flow (not always available from IBKR historical bars)

### Tick Data Format

**File**: `ticks/AMD_20251031_093000_ticks.json`

**Structure**:
```json
{
  "symbol": "AMD",
  "date": "2025-10-31",
  "minute": "09:30:00",
  "ticks": [
    {
      "time": "2025-10-31T09:30:00.123-04:00",
      "price": 162.45,
      "size": 100,
      "exchange": "NASDAQ",
      "conditions": ["Regular"]
    },
    {
      "time": "2025-10-31T09:30:00.456-04:00",
      "price": 162.47,
      "size": 250,
      "exchange": "NASDAQ",
      "conditions": ["Regular"]
    }
  ],
  "total_ticks": 1523
}
```

**Availability**: Only 30-60 days of tick history from IBKR
**Use Case**: High-fidelity backtesting, CVD calculation

## 🚀 Data Downloader Scripts

### 1. Batch Date Range Downloader

**Purpose**: Download 1-min bars for multiple dates/symbols in one job

**Script**: `download_date_range.py`

**Usage**:
```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Download single symbol for date range
python3 download_date_range.py \
  --symbol TSLA \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --data-type 1min

# Download multiple symbols
python3 download_date_range.py \
  --symbols TSLA,NVDA,AMD,PLTR \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --data-type 1min

# Download from scanner results file
python3 download_date_range.py \
  --scanner ../../stockscanner/output/scanner_results_20251031.json \
  --start-date 2025-10-15 \
  --end-date 2025-10-31 \
  --data-type 1min
```

**Features**:
- Rate limit handling (60 requests per 10 min)
- Automatic retry on failures
- Skip already cached files
- Progress tracking
- Error logging

**Expected Implementation**:
```python
#!/usr/bin/env python3
"""
Download historical data for date ranges in batch.
Smart pacing to respect IBKR rate limits.
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from ib_insync import IB, Stock, util

def download_bars_for_date(ib, symbol, date, output_dir):
    """Download 1-min bars for a specific date"""
    # Check if already cached
    filename = f"{symbol}_{date.strftime('%Y%m%d')}_1min.json"
    filepath = output_dir / filename

    if filepath.exists():
        print(f"✅ Cached: {filename}")
        return True

    # Fetch from IBKR
    contract = Stock(symbol, 'SMART', 'USD')

    # Request 1-min bars for the entire trading day
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=date.strftime('%Y%m%d 16:00:00 US/Eastern'),
        durationStr='1 D',
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=True  # Regular trading hours only
    )

    if not bars:
        print(f"❌ No data: {symbol} on {date}")
        return False

    # Save to JSON
    data = {
        'symbol': symbol,
        'date': date.strftime('%Y-%m-%d'),
        'bars': [
            {
                'timestamp': bar.date.isoformat(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'average': bar.average,
                'barCount': bar.barCount
            }
            for bar in bars
        ],
        'total_bars': len(bars)
    }

    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ Downloaded: {filename} ({len(bars)} bars)")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', type=str, help='Single symbol')
    parser.add_argument('--symbols', type=str, help='Comma-separated symbols')
    parser.add_argument('--scanner', type=str, help='Scanner results JSON file')
    parser.add_argument('--start-date', required=True, help='Start date YYYY-MM-DD')
    parser.add_argument('--end-date', required=True, help='End date YYYY-MM-DD')
    parser.add_argument('--data-type', default='1min', choices=['1min', 'cvd', 'ticks'])
    parser.add_argument('--port', type=int, default=7497, help='TWS/Gateway port')
    args = parser.parse_args()

    # Parse dates
    start = datetime.strptime(args.start_date, '%Y-%m-%d')
    end = datetime.strptime(args.end_date, '%Y-%m-%d')

    # Get symbol list
    if args.scanner:
        with open(args.scanner) as f:
            scanner_data = json.load(f)
        symbols = [setup['symbol'] for setup in scanner_data]
    elif args.symbols:
        symbols = args.symbols.split(',')
    elif args.symbol:
        symbols = [args.symbol]
    else:
        raise ValueError("Must provide --symbol, --symbols, or --scanner")

    # Output directory
    output_dir = Path(__file__).parent.parent / 'backtest' / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', args.port, clientId=3000)

    # Download data
    total_requests = 0
    request_times = []

    date = start
    while date <= end:
        # Skip weekends
        if date.weekday() >= 5:
            date += timedelta(days=1)
            continue

        for symbol in symbols:
            # Rate limiting: max 60 requests per 10 minutes
            request_times = [t for t in request_times if time.time() - t < 600]

            if len(request_times) >= 58:  # Leave buffer
                wait_time = 600 - (time.time() - request_times[0]) + 5
                print(f"⏳ Rate limit approaching, waiting {wait_time:.0f}s...")
                time.sleep(wait_time)
                request_times = []

            # Download
            success = download_bars_for_date(ib, symbol, date, output_dir)
            request_times.append(time.time())
            total_requests += 1

            # Pacing between requests
            time.sleep(1.0)

        date += timedelta(days=1)

    ib.disconnect()
    print(f"\n✅ Complete: {total_requests} requests")

if __name__ == '__main__':
    main()
```

### 2. Cache Validator

**Purpose**: Verify cached data is complete and valid

**Script**: `validate_cache.py`

**Usage**:
```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Validate all cached data
python3 validate_cache.py --data-dir ../backtest/data

# Validate specific date range
python3 validate_cache.py \
  --data-dir ../backtest/data \
  --start-date 2025-10-01 \
  --end-date 2025-10-31

# Check for missing dates
python3 validate_cache.py --check-missing
```

**Checks**:
- ✅ File exists and is readable
- ✅ JSON is valid
- ✅ Bar count matches expected (390 bars for full day)
- ✅ No gaps in timestamps
- ✅ OHLCV values are reasonable
- ✅ Timestamps are in ET timezone
- ❌ Corrupted files flagged for re-download

### 3. Scanner-Driven Bulk Downloader

**Purpose**: Download data for all stocks in scanner results (multiple dates)

**Script**: `download_scanner_history.py`

**Usage**:
```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Download data for all scanner dates in October
python3 download_scanner_history.py \
  --scanner-dir ../../stockscanner/output \
  --month 2025-10

# Download specific date range
python3 download_scanner_history.py \
  --scanner-dir ../../stockscanner/output \
  --start-date 2025-10-15 \
  --end-date 2025-10-31
```

**Workflow**:
1. Scans `stockscanner/output/` for all `scanner_results_YYYYMMDD.json` files
2. Extracts unique symbols from each scanner file
3. Downloads 1-min bars for each symbol on that date
4. Skips already cached files
5. Respects rate limits with smart pacing

### 4. Cache Statistics

**Purpose**: Analyze cache coverage and storage

**Script**: `cache_stats.py`

**Usage**:
```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Get cache statistics
python3 cache_stats.py --data-dir ../backtest/data
```

**Output**:
```
CACHE STATISTICS
================================================================================

Storage:
  Total files: 1,247
  Total size: 2.4 GB
  1-min bars: 847 files (1.8 GB)
  CVD bars: 256 files (450 MB)
  Tick data: 144 files (150 MB)

Coverage:
  Date range: 2025-10-01 to 2025-10-31 (31 days, 22 trading days)
  Symbols: 45 unique symbols
  Completeness: 94.3% (873/925 expected files)

Missing Data:
  2025-10-15: TSLA, NVDA (2 files)
  2025-10-22: AMD, PLTR, COIN (3 files)
  ... (52 missing files total)

Top Symbols by Storage:
  1. TSLA: 156 MB (22 days)
  2. NVDA: 142 MB (22 days)
  3. SPY: 128 MB (22 days)
```

## 🔧 Cache Management

### Cache Directory Structure

```
trader/backtest/data/
├── 1min/                          # Organized by type
│   ├── 2025-10/                   # Organized by month
│   │   ├── TSLA_20251015_1min.json
│   │   ├── TSLA_20251016_1min.json
│   │   └── ...
│   └── 2025-11/
├── cvd_bars/
│   └── 2025-10/
└── ticks/
    └── 2025-10/
```

**Note**: Current structure is flat - reorganization script needed for better organization.

### Cache Cleaning

**Remove old tick data** (only keep last 30 days):
```bash
find trader/backtest/data/ticks -name "*_ticks.json" -mtime +30 -delete
```

**Remove incomplete files** (less than 300 bars):
```bash
python3 data-downloader/clean_incomplete.py --min-bars 300
```

**Free up space** (archive old data):
```bash
python3 data-downloader/archive_old_data.py --older-than 2025-09-01 --output archive.tar.gz
```

## 📡 IBKR API Best Practices

### Rate Limits

**Historical Data API**:
- **Hard limit**: 60 requests per 10 minutes
- **Recommended**: 50 requests per 10 minutes (leave buffer)
- **Pacing**: 1-2 seconds between requests
- **Concurrent**: Max 50 simultaneous requests

**Implementation**:
```python
import time
from collections import deque

class RateLimiter:
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
            print(f"⏳ Rate limit: waiting {wait_time:.0f}s")
            time.sleep(wait_time)
            self.request_times.clear()

        # Record this request
        self.request_times.append(now)
        time.sleep(1.0)  # Pacing between requests

# Usage
limiter = RateLimiter(max_requests=50, window_seconds=600)

for symbol in symbols:
    limiter.wait_if_needed()
    bars = ib.reqHistoricalData(...)
```

### Connection Management

**Reconnection Logic**:
```python
def connect_with_retry(port=7497, client_id=3000, max_retries=3):
    """Connect to IBKR with retry logic"""
    ib = IB()

    for attempt in range(max_retries):
        try:
            ib.connect('127.0.0.1', port, clientId=client_id)
            print(f"✅ Connected to IBKR on port {port}")
            return ib
        except Exception as e:
            print(f"❌ Connection attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
            else:
                raise

    return None
```

**Keep-Alive**:
```python
# Send periodic reqCurrentTime to keep connection alive
def keep_alive(ib):
    while ib.isConnected():
        ib.reqCurrentTime()
        time.sleep(60)  # Every minute
```

### Error Handling

**Common Errors**:
```python
try:
    bars = ib.reqHistoricalData(...)
except Exception as e:
    if 'No market data permissions' in str(e):
        print(f"❌ No data subscription for {symbol}")
    elif 'Historical Market Data Service error' in str(e):
        print(f"⚠️ HMDS error, retrying in 10s...")
        time.sleep(10)
    elif 'pacing violation' in str(e):
        print(f"⚠️ Rate limit hit, backing off...")
        time.sleep(120)
    else:
        print(f"❌ Unknown error: {e}")
```

## 🗓️ Recommended Download Schedule

### Daily (After Market Close)

**4:30 PM ET** - Download today's data:
```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Download today's scanner stocks
python3 download_date_range.py \
  --scanner ../../stockscanner/output/scanner_results_$(date +%Y%m%d).json \
  --start-date $(date +%Y-%m-%d) \
  --end-date $(date +%Y-%m-%d) \
  --data-type 1min
```

### Weekly (Sunday Night)

**8:00 PM ET** - Backfill last week:
```bash
# Download entire previous week
python3 download_scanner_history.py \
  --scanner-dir ../../stockscanner/output \
  --start-date 2025-10-21 \
  --end-date 2025-10-25
```

### Monthly (First Weekend)

**Validate entire month's cache**:
```bash
# Check for missing data
python3 validate_cache.py \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --check-missing

# Re-download missing files
python3 download_missing.py --from-validation-report validation_report.json
```

## 📊 Data Requirements by Use Case

### Backtesting (1-min bars)

**Required**: 1-min OHLCV bars
**Coverage**: Full trading day (09:30 - 16:00 ET)
**Storage**: ~2 MB per symbol per day
**Retention**: 1 year recommended

### CVD Analysis (Tick data → CVD bars)

**Required**: Tick-by-tick data (or L2 book data)
**Coverage**: Only available for last 30-60 days
**Storage**: ~50 MB per symbol per day (compressed)
**Retention**: 30 days rolling window

### High-Fidelity Testing (Tick replay)

**Required**: Full tick data with order book
**Coverage**: 30 days max from IBKR
**Storage**: ~200 MB per symbol per day
**Retention**: Delete after 30 days (storage intensive)

## 🚨 Data Quality Issues

### Common Problems

1. **Incomplete Trading Days** (<390 bars)
   - Market early close (holidays)
   - Data fetch timeout
   - Trading halt

2. **Missing Bars** (gaps in timestamps)
   - Low liquidity stocks
   - After-hours data included incorrectly
   - IBKR data quality issue

3. **Incorrect Timezone** (not ET)
   - IBKR returns UTC, need conversion
   - Daylight saving time transitions

4. **Outlier Prices** (data spikes)
   - Flash crash artifacts
   - Bad ticks from exchange
   - Need price validation

### Validation Checklist

```python
def validate_bar_data(data):
    """Validate 1-min bar data quality"""
    errors = []

    # Check bar count
    if len(data['bars']) < 300:
        errors.append(f"Incomplete day: {len(data['bars'])} bars")

    # Check for gaps
    timestamps = [bar['timestamp'] for bar in data['bars']]
    for i in range(1, len(timestamps)):
        gap = (timestamps[i] - timestamps[i-1]).seconds
        if gap > 60:
            errors.append(f"Gap detected at {timestamps[i]}")

    # Check for price outliers
    closes = [bar['close'] for bar in data['bars']]
    median_price = sorted(closes)[len(closes)//2]

    for bar in data['bars']:
        if abs(bar['close'] - median_price) / median_price > 0.20:
            errors.append(f"Outlier price: {bar['close']} at {bar['timestamp']}")

    # Check volumes
    if any(bar['volume'] == 0 for bar in data['bars']):
        errors.append("Zero volume bars detected")

    return errors
```

## 🔄 Integration with Backtester

**Backtester looks for cached data first**:

```python
# In backtester.py
def get_historical_bars(self, symbol, date):
    """Get 1-min bars from cache or IBKR"""

    # Try cache first
    cache_file = f"backtest/data/{symbol}_{date.strftime('%Y%m%d')}_1min.json"
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            data = json.load(f)
        return data['bars']

    # Fetch from IBKR if not cached
    bars = self.fetch_from_ibkr(symbol, date)

    # Save to cache for next time
    self.save_to_cache(symbol, date, bars)

    return bars
```

**Workflow**:
1. **Pre-download data** using scripts in this folder
2. **Run backtest** - uses cached data (fast)
3. **Missing data?** - Backtest fetches on-demand (slow)

## 📚 Quick Reference

**Download today's data**:
```bash
python3 download_date_range.py --scanner ../../stockscanner/output/scanner_results_$(date +%Y%m%d).json --start-date $(date +%Y-%m-%d) --end-date $(date +%Y-%m-%d)
```

**Download last week**:
```bash
python3 download_scanner_history.py --scanner-dir ../../stockscanner/output --start-date 2025-10-21 --end-date 2025-10-25
```

**Validate cache**:
```bash
python3 validate_cache.py --data-dir ../backtest/data --check-missing
```

**Cache stats**:
```bash
python3 cache_stats.py --data-dir ../backtest/data
```

**Clean old tick data**:
```bash
find ../backtest/data/ticks -name "*_ticks.json" -mtime +30 -delete
```

---

**Last Updated**: November 1, 2025
**Status**: Planned - Scripts need implementation
