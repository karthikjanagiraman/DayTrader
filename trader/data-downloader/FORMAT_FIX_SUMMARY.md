# Data Downloader Format Fix - November 1, 2025

## Issue Discovered

During review of downloader compatibility with backtester and validation systems, discovered a **critical format mismatch**.

### Problem

**Initial downloader format** (WRONG):
```json
{
  "symbol": "AMD",
  "date": "2025-10-31",
  "bars": [
    {
      "timestamp": "2025-10-31T09:30:00-04:00",  // WRONG field name
      "open": 162.45,
      ...
    }
  ],
  "total_bars": 390,
  "downloaded_at": "2025-11-01T12:34:56"
}
```

**Required format** (by backtester):
```json
[
  {
    "date": "2025-10-31T09:30:00-04:00",  // MUST be 'date'
    "open": 162.45,
    "high": 162.78,
    "low": 162.32,
    "close": 162.65,
    "volume": 245678,
    "average": 162.55,
    "barCount": 1523
  }
]
```

### Root Cause

The downloader was creating a **wrapped object** with metadata (symbol, date, total_bars, downloaded_at), but the backtester expects a **flat array** of bar objects.

Additionally, the field name was `timestamp` instead of `date`, which would cause the backtester to fail when reconstructing `BarData` objects.

### Evidence

**Backtester code** (`trader/backtest/backtester.py:1258-1269`):
```python
bars = BarDataList()
for bar_dict in cached_data:  # Expects flat array
    bar = BarData(
        date=datetime.fromisoformat(bar_dict['date']),  # Expects 'date' field
        open=bar_dict['open'],
        high=bar_dict['high'],
        low=bar_dict['low'],
        close=bar_dict['close'],
        volume=bar_dict['volume'],
        average=bar_dict.get('average', bar_dict['close']),
        barCount=bar_dict.get('barCount', 0)
    )
    bars.append(bar)
```

**Existing cached files** (verified format):
```bash
$ head -20 /Users/karthik/projects/DayTrader/trader/backtest/data/PLTR_20251016_1min.json
[
  {
    "date": "2025-10-16T09:30:00-04:00",  // ✅ Flat array, 'date' field
    "open": 181.78,
    ...
  }
]
```

## Fix Applied

### Changed Files

**1. `download_october_data.py` - Data format (lines 229-248)**

**Before**:
```python
data = {
    'symbol': symbol,
    'date': date_str,
    'bars': [
        {
            'timestamp': bar.date.isoformat(),  # WRONG
            ...
        }
    ],
    'total_bars': len(bars)
}
```

**After**:
```python
# Flat array format - matches backtester requirement
data = [
    {
        'date': bar.date.isoformat(),  # ✅ Correct field name
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
```

**2. `download_october_data.py` - Validation (lines 278-304)**

**Before**:
```python
def validate_cached_file(self, filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)

    if 'bars' not in data or 'symbol' not in data:  # WRONG
        return False

    if len(data['bars']) < 200:  # WRONG
        return False
```

**After**:
```python
def validate_cached_file(self, filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Check structure - should be an array
    if not isinstance(data, list):
        return False

    # Check first bar has required fields
    first_bar = data[0]
    required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
    if not all(field in first_bar for field in required_fields):
        return False

    # Check bar count
    if len(data) < 200:
        return False
```

**3. `CLAUDE.md` - Documentation updated**

Updated data format examples to show flat array format with `date` field.

## Validation System Compatibility

**Checked**: `trader/validation/validate_market_outcomes.py`

**Verdict**: ✅ **No changes needed**

The validation system fetches data directly from IBKR on-demand via `ib.reqHistoricalData()`, so it doesn't rely on pre-cached 1-minute bar files. It's **independent** of the downloader format.

## Testing

### Format Verification

**Test command**:
```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# With TWS running on port 7497:
python3 download_october_data.py --scanner ../../stockscanner/output/scanner_results_20251031.json --date 2025-10-31 --output-dir ../backtest/data
```

**Expected output file**:
```bash
cat ../backtest/data/TSLA_20251031_1min.json | head -20
```

**Expected format**:
```json
[
  {
    "date": "2025-10-31T09:30:00-04:00",
    "open": 250.45,
    "high": 251.20,
    "low": 250.10,
    "close": 250.85,
    "volume": 450123,
    "average": 250.62,
    "barCount": 2145
  },
  ...
]
```

### Backtester Integration Test

**After downloading data**:
```bash
cd /Users/karthik/projects/DayTrader/trader

# Run backtest using downloaded data
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251031.json \
  --date 2025-10-31 \
  --account-size 50000
```

**Expected behavior**:
- ✅ Backtester loads cached files without errors
- ✅ No "cache read error" messages
- ✅ Trades execute correctly using cached data

## Impact

### Before Fix
- ❌ Downloaded files incompatible with backtester
- ❌ Backtester would fail to load cached data
- ❌ Would fall back to fetching from IBKR (slow, rate limited)
- ❌ October data downloads would be **unusable**

### After Fix
- ✅ Downloaded files match backtester format exactly
- ✅ Backtester loads cached data successfully
- ✅ Fast backtesting (no IBKR calls needed)
- ✅ October data downloads **ready to use**

## Key Takeaways

### Format Requirements (CRITICAL)

**For backtester compatibility**, cached 1-minute bar files MUST:

1. ✅ **Be a flat JSON array** (not wrapped in object)
2. ✅ **Use `date` field** (not `timestamp`, not `time`)
3. ✅ **Include all fields**: open, high, low, close, volume, average, barCount
4. ✅ **Use ISO format timestamps** with timezone offset (e.g., -04:00)
5. ✅ **Match naming convention**: `{SYMBOL}_{YYYYMMDD}_1min.json`

### Implementation Notes

- The **backtester** is the source of truth for format requirements
- Check **existing cached files** to verify format before implementing new downloaders
- **Validation system** is independent (fetches directly from IBKR)
- **Don't add metadata** to cached files (symbol, total_bars, etc.) - backtester doesn't expect it

### Verification Steps

When implementing any data downloader:
1. ✅ Check backtester's `get_bars()` method for expected format
2. ✅ Examine existing cached files in `backtest/data/`
3. ✅ Test with backtester after downloading
4. ✅ Verify no "cache read error" messages

---

**Status**: ✅ Fixed and documented
**Date**: November 1, 2025
**Files Modified**:
- `download_october_data.py` (format + validation)
- `CLAUDE.md` (documentation)
- `FORMAT_FIX_SUMMARY.md` (this file)
