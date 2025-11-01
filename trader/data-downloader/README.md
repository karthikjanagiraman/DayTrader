# Data Downloader - October 2025 Historical Data

Robust batch downloader for historical 1-minute bar data from IBKR.

## Features

✅ **Resume capability** - Can be stopped and restarted without losing progress
✅ **Rate limit handling** - Respects IBKR limits (50 req/10 min)
✅ **Connection resilience** - Auto-reconnect on disconnection
✅ **Progress tracking** - Saves state to `download_progress.json`
✅ **Data validation** - Validates downloaded files
✅ **Graceful shutdown** - Press Ctrl+C to stop safely

## Prerequisites

**Before running the downloader:**

1. **Start TWS or IB Gateway**:
   - **Paper Trading**: Port 7497
   - **Live Trading**: Port 7496

2. **Enable API access**:
   - TWS: File → Global Configuration → API → Settings
   - Check "Enable ActiveX and Socket Clients"
   - Check "Allow connections from localhost only"
   - Socket Port: 7497 (paper) or 7496 (live)
   - Read-only API: No (need historical data access)

3. **Verify connection**:
   ```bash
   # Test connection
   cd /Users/karthik/projects/DayTrader/trader
   python3 -c "from ib_insync import IB; ib = IB(); ib.connect('127.0.0.1', 7497, clientId=3000); print('✅ Connected'); ib.disconnect()"
   ```

## Quick Start

### Download October 2025 Data

```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Start the download (uses scanner files to determine what to download)
python3 download_october_data.py
```

**What it does**:
1. Scans `stockscanner/output/scanner_results_202510*.json` files
2. Extracts unique symbols per date
3. Downloads 1-min bars for each symbol/date combination
4. Skips weekends automatically
5. Saves to `../backtest/data/SYMBOL_YYYYMMDD_1min.json`

### Monitor Progress

**In another terminal**:
```bash
# Watch the log file
tail -f /Users/karthik/projects/DayTrader/trader/data-downloader/download_october.log

# Check progress state
cat /Users/karthik/projects/DayTrader/trader/data-downloader/download_progress.json | python3 -m json.tool

# Count downloaded files
ls -1 /Users/karthik/projects/DayTrader/trader/backtest/data/*_1min.json | wc -l
```

### Resume After Interruption

**If the downloader stops or is terminated:**

```bash
# Just run it again - it will resume from where it left off
python3 download_october_data.py
```

The downloader tracks progress in `download_progress.json` and automatically skips already-downloaded files.

### Reset and Start Fresh

```bash
# Delete progress file and start over
python3 download_october_data.py --reset
```

## Command-Line Options

```bash
python3 download_october_data.py [OPTIONS]

Options:
  --scanner-dir PATH    Scanner results directory (default: ../../stockscanner/output)
  --output-dir PATH     Output directory for data (default: ../backtest/data)
  --port PORT           TWS/Gateway port (default: 7497)
  --reset               Reset progress and start fresh
  -h, --help            Show help message
```

### Examples

**Use live trading port**:
```bash
python3 download_october_data.py --port 7496
```

**Custom output directory**:
```bash
python3 download_october_data.py --output-dir /path/to/custom/data
```

**Reset progress**:
```bash
python3 download_october_data.py --reset
```

## Progress Tracking

The downloader saves progress to `download_progress.json`:

```json
{
  "completed": [
    "TSLA_2025-10-01",
    "NVDA_2025-10-01",
    "AMD_2025-10-01"
  ],
  "failed": [
    {
      "symbol": "XYZ",
      "date": "2025-10-02",
      "error": "No market data permissions",
      "timestamp": "2025-11-01T12:34:56"
    }
  ],
  "last_updated": "2025-11-01T12:35:00"
}
```

**Resume logic**:
- Checks `download_progress.json` on startup
- Skips symbols/dates marked as `completed`
- Retries failed downloads (in case of transient errors)
- Validates existing cached files before skipping

## Output Format

**Downloaded files**: `../backtest/data/SYMBOL_YYYYMMDD_1min.json`

**File structure**:
```json
{
  "symbol": "TSLA",
  "date": "2025-10-01",
  "bars": [
    {
      "timestamp": "2025-10-01T09:30:00-04:00",
      "open": 245.67,
      "high": 246.12,
      "low": 245.45,
      "close": 245.89,
      "volume": 234567,
      "average": 245.78,
      "barCount": 1234
    }
  ],
  "total_bars": 390,
  "downloaded_at": "2025-11-01T12:34:56"
}
```

**Expected bar count**: ~390 bars (6.5 trading hours × 60 min)

## Error Handling

### Common Errors

**1. Connection Refused**
```
❌ Connection attempt 1 failed: ConnectionRefusedError
```

**Solution**: Start TWS or IB Gateway on port 7497

---

**2. No Market Data Permissions**
```
❌ Error: No market data permissions for XYZ
```

**Solution**: Stock requires subscription you don't have (will be marked as failed, but won't stop downloader)

---

**3. Pacing Violation**
```
⏳ Pacing violation, backing off 2 minutes...
```

**Solution**: IBKR rate limit hit, downloader automatically waits (this is normal)

---

**4. HMDS Error**
```
⏳ HMDS error, waiting 30s...
```

**Solution**: Historical Market Data Service temporary issue, downloader retries automatically

---

**5. Incomplete Data**
```
⚠️  Incomplete data (245 bars, expected ~390)
```

**Possible causes**:
- Stock had trading halt
- Early market close (holiday)
- Low liquidity stock
- Data quality issue

**Action**: File is still saved but marked as incomplete in failed list

## Rate Limiting

**IBKR Limits**:
- 60 requests per 10 minutes (hard limit)
- Downloader uses 50 requests per 10 minutes (safety buffer)
- 1 second pacing between requests

**What this means**:
- **50 symbols per 10 minutes** = ~5 per minute
- **For 100 symbols**: ~20 minutes
- **For 1000 symbols**: ~3.5 hours

**Example October 2025**:
```
20 trading days × 8 symbols/day = 160 total downloads
At 50 downloads per 10 min = ~35 minutes total
```

## Graceful Shutdown

**Press Ctrl+C at any time**:

```
^C
⚠️  Interrupt received, saving state and shutting down...
✅ State saved. You can restart to continue from here.
```

The downloader:
1. Catches the interrupt signal
2. Saves current progress to `download_progress.json`
3. Disconnects from IBKR cleanly
4. Exits gracefully

**Restart to continue**:
```bash
python3 download_october_data.py
```

## Validation

### Data Validation Checks

The downloader validates each file:

✅ JSON is valid
✅ Contains 'bars' and 'symbol' fields
✅ Has at least 200 bars (allows for partial days)
✅ File exists and is readable

**Files that fail validation**:
- Are deleted and re-downloaded
- Or marked in progress file if download fails

### Manual Validation

```bash
# Check a specific file
python3 -c "
import json
with open('../backtest/data/TSLA_20251001_1min.json') as f:
    data = json.load(f)
    print(f'Symbol: {data[\"symbol\"]}')
    print(f'Bars: {len(data[\"bars\"])}')
    print(f'First: {data[\"bars\"][0][\"timestamp\"]}')
    print(f'Last: {data[\"bars\"][-1][\"timestamp\"]}')
"
```

## Expected Timeline

**For October 2025** (based on scanner files):

| Date | Symbols | Expected Time |
|------|---------|---------------|
| Oct 1-7 | ~60 symbols | ~15 minutes |
| Oct 8-14 | ~55 symbols | ~12 minutes |
| Oct 15-21 | ~48 symbols | ~10 minutes |
| Oct 22-31 | ~50 symbols | ~11 minutes |

**Total**: ~160 downloads = **~35-45 minutes**

**Progress Example**:
```
📅 2025-10-01 (Tuesday) - 8 symbols
================================================================================
  [1/8] TSLA  ✅ Downloaded (390 bars)  [0.6% | ETA: 42m]
  [2/8] NVDA  ✅ Downloaded (390 bars)  [1.2% | ETA: 41m]
  [3/8] AMD   ✅ Downloaded (390 bars)  [1.9% | ETA: 40m]
  [4/8] PLTR  ✅ Downloaded (390 bars)  [2.5% | ETA: 39m]
  [5/8] COIN  ✅ Downloaded (390 bars)  [3.1% | ETA: 38m]
  [6/8] GME   ✅ Downloaded (378 bars)  [3.7% | ETA: 37m]
  [7/8] HOOD  ✅ Downloaded (390 bars)  [4.4% | ETA: 36m]
  [8/8] SOFI  ✅ Downloaded (390 bars)  [5.0% | ETA: 35m]
```

## Troubleshooting

### Downloader Hangs

**Symptoms**: No progress for > 2 minutes

**Solution**:
1. Press Ctrl+C
2. Check TWS/Gateway is still running
3. Restart downloader: `python3 download_october_data.py`

### Too Many Failures

**Symptoms**: Many "No market data permissions" errors

**Cause**: Missing data subscriptions for some stocks

**Solution**: These are tracked in `failed` list but don't stop the downloader. You can:
- Manually remove failed symbols from scanner files
- Or accept that some stocks won't have data

### Out of Order Downloads

**Symptoms**: Dates not in chronological order

**Explanation**: This is normal! The downloader processes files in the order it finds them. Progress is still tracked correctly.

## Next Steps

**After downloading all October data:**

1. **Validate cache**:
   ```bash
   cd /Users/karthik/projects/DayTrader/trader/data-downloader
   python3 validate_cache.py --data-dir ../backtest/data --start-date 2025-10-01 --end-date 2025-10-31
   ```

2. **Run backtests** (now much faster with cached data):
   ```bash
   cd /Users/karthik/projects/DayTrader/trader/backtest
   python3 backtester.py --scanner ../../stockscanner/output/scanner_results_20251001.json --date 2025-10-01 --account-size 50000
   ```

3. **Generate monthly report**:
   ```bash
   cd /Users/karthik/projects/DayTrader/trader
   python3 generate_monthly_report.py --month 2025-10
   ```

## Files Created

```
data-downloader/
├── download_october_data.py    # Main downloader script
├── download_progress.json      # Progress tracking (auto-generated)
├── download_october.log        # Log file (auto-generated)
└── README.md                   # This file

../backtest/data/
├── TSLA_20251001_1min.json    # Downloaded data files
├── NVDA_20251001_1min.json
├── AMD_20251001_1min.json
└── ...
```

## Summary

**To download October 2025 data:**

1. Start TWS/Gateway on port 7497
2. Run: `python3 download_october_data.py`
3. Wait ~35-45 minutes (or monitor progress in another terminal)
4. Press Ctrl+C to stop gracefully (can resume later)
5. Restart with same command to resume

**The downloader handles**:
- ✅ Rate limiting
- ✅ Connection issues
- ✅ Progress tracking
- ✅ Data validation
- ✅ Graceful shutdown
- ✅ Resume capability

---

**Questions?** See `CLAUDE.md` in this directory for detailed technical documentation.
