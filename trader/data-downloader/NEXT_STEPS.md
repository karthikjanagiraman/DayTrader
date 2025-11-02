# Data Downloader - Next Steps

## ✅ What's Been Completed

1. **Enhanced Downloader** (`download_october_data.py`)
   - ✅ 3-stage pipeline: 1-min bars → tick data → CVD bars
   - ✅ Resilient with retry logic, reconnection, and state tracking
   - ✅ Flexible date range support
   - ✅ Command-line arguments for configuration
   - ✅ Graceful shutdown with Ctrl+C

2. **Current Data Status**
   - 1-min bars: 200/198 (100%+ - some extra symbols)
   - Tick data: ~22,781 files (partial coverage)
   - CVD bars: 58/198 (29% coverage)
   - **Missing**: 140 CVD files

## 🚀 Next Steps

### Step 1: Start IBKR TWS/Gateway

**Current Issue**: IBKR connection refused on port 7497

**Action Required**:
```bash
# Start TWS or IB Gateway on your machine
# Configure API settings:
#   - Enable API connections
#   - Socket port: 7497 (paper trading)
#   - Read-Only API: No
#   - Download open orders on connection: No
```

**Verify Connection**:
```bash
# Test that TWS is running and accepting connections
telnet localhost 7497
# Should connect successfully (Ctrl+C to exit)
```

### Step 2: Run the Enhanced Downloader

Once TWS is running, execute:

```bash
cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Download all October 2025 tick data + build CVD bars
python3 download_october_data.py 2>&1 | tee download_log_$(date +%Y%m%d_%H%M%S).log
```

**What This Will Do**:
1. Download 1-min bars for missing symbols (fast - skips existing)
2. Download tick data for 390 minutes per day (slow - 10-16 hours total)
3. Build CVD bars from ticks + 1-min bars (fast - local processing)

**Progress Tracking**:
- State saved to `download_progress.json` after each completion
- Can Ctrl+C and resume anytime without losing progress
- Real-time progress display with ETA

### Step 3: Monitor Progress

**Check Progress**:
```bash
# Watch the log in real-time
tail -f download_log_*.log

# Check state file
cat download_progress.json | python3 -m json.tool

# Count CVD files
ls -1 ../backtest/data/cvd_bars/*.json | wc -l
# Should reach 198 when complete
```

**Expected Timeline**:
- 1-min bars: ~5-10 minutes (most already cached)
- Tick data: **10-16 hours** (390 API calls per symbol×date, rate limited)
- CVD building: ~5-10 minutes (local processing)

**Completion Indicators**:
```
✅ Download Complete!
   1-min bars:  198/198 (100.0%)
   Tick data:   198/198 (100.0%)
   CVD bars:    198/198 (100.0%)
   Duration:    ~10-16 hours
```

### Step 4: Re-run Batch Backtests

Once all CVD data is downloaded:

```bash
cd /Users/karthik/projects/DayTrader/trader/backtest

# Re-run October backtests with complete CVD data
python3 run_october_backtests.py 2>&1 | tee logs/october_2025_backtest_FINAL.log
```

**Expected Improvements**:
- All 22 days should complete (vs 5/22 before)
- No timeouts (CVD data pre-built, no runtime downloading)
- Faster execution (~30-40 minutes for all 22 days)
- Complete monthly statistics

### Step 5: Generate Final Report

```bash
# Monthly summary will be auto-generated
cat results/october_2025_backtest_summary.json
```

## 🔧 Troubleshooting

### Issue: Still timing out after CVD download

**Cause**: Backtester might still be trying to download data

**Fix**:
```bash
# Verify CVD files exist
ls -l ../backtest/data/cvd_bars/AMD_20251031_cvd.json

# If missing, re-run downloader for specific date
python3 download_october_data.py \
  --start-date 2025-10-31 \
  --end-date 2025-10-31
```

### Issue: Connection errors during download

**Cause**: IBKR connection lost or rate limit hit

**Fix**:
- Downloader will auto-reconnect
- Progress is saved - just let it continue
- If needed, press Ctrl+C and restart (resumes from saved state)

### Issue: Disk space running low

**Check Usage**:
```bash
du -sh ../backtest/data/
# Tick data: ~4-5 GB
# CVD bars: ~500 MB
# 1-min bars: ~200 MB
# Total: ~5-6 GB
```

**Cleanup** (if needed):
```bash
# Remove old tick data after CVD building
# (Only do this AFTER all CVD bars are built!)
rm -rf ../backtest/data/ticks/
```

## 📊 Expected Final Results

**Data Inventory** (after completion):
```
trader/backtest/data/
├── {symbol}_{date}_1min.json         # 198 files (2 MB)
├── cvd_bars/
│   └── {symbol}_{date}_cvd.json      # 198 files (500 MB)
└── ticks/                             # 77,220 files (4-5 GB)
    └── {symbol}_{date}_{time}_ticks.json
```

**Backtest Results** (expected):
- All 22 October trading days completed
- ~150-250 total trades (vs 36 partial results)
- Win rate: ~35-45% (based on September results)
- Monthly P&L: TBD (will be calculated)
- Average trade duration: ~5-10 minutes

## ⏱️ Timeline Estimate

| Task | Duration | Status |
|------|----------|--------|
| Downloader enhancement | 2 hours | ✅ DONE |
| Start TWS | 5 minutes | ⏸️ Waiting on you |
| Download tick data | 10-16 hours | ⏸️ Waiting on TWS |
| Build CVD bars | 10 minutes | ⏸️ Auto after ticks |
| Re-run backtests | 30-40 minutes | ⏸️ After CVD complete |
| Generate report | 1 minute | ⏸️ After backtests |
| **Total** | **~12-18 hours** | **In Progress** |

## 🎯 Success Criteria

✅ **Complete** when:
1. 198 CVD files exist in `backtest/data/cvd_bars/`
2. All 22 October backtests complete without timeout
3. Monthly summary generated in `results/october_2025_backtest_summary.json`
4. Win rate, P&L, and trade statistics available

## 📝 Quick Command Reference

```bash
# Start TWS/Gateway (do this first!)
# Then run:

cd /Users/karthik/projects/DayTrader/trader/data-downloader

# Download all October data
python3 download_october_data.py 2>&1 | tee download.log

# Monitor progress
tail -f download.log

# Check CVD count
ls -1 ../backtest/data/cvd_bars/*.json | wc -l

# After download completes, run backtests
cd ../backtest
python3 run_october_backtests.py

# View final results
cat results/october_2025_backtest_summary.json | python3 -m json.tool
```

---

**Next Action**: Start IBKR TWS/Gateway, then run the downloader command above.

**Estimated Time to Completion**: 10-16 hours (mostly automated, can run overnight)

**Questions?** See `DOWNLOADER_ENHANCEMENT_COMPLETE.md` for technical details.
