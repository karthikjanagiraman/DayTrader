# Tick Data Validation - October 16-22, 2025

**Generated**: 2025-10-24 00:30:00
**Purpose**: Validate tick data availability for backtesting October 16-22 sessions

---

## Scanner Files Available

| Date | Scanner File | Status | Stocks Count |
|------|-------------|--------|--------------|
| **Oct 16** | scanner_results_20251016.json | ✅ EXISTS | 8 stocks |
| **Oct 17** | N/A | ❌ MISSING | - |
| **Oct 20** | scanner_results_20251020.json | ✅ EXISTS | 8 stocks |
| **Oct 21** | scanner_results_20251021.json | ✅ EXISTS | 10 stocks |
| **Oct 22** | scanner_results_20251022.json | ✅ EXISTS | 10 stocks |

---

## Tick Data Availability by Date

### Dates with Tick Data Available

| Date | Tick Data | Scanner Data | Backtest Ready |
|------|-----------|--------------|----------------|
| **Oct 15** | ✅ YES | ❌ NO | ❌ NO |
| **Oct 16** | ✅ YES | ✅ YES | ✅ YES |
| **Oct 17** | ❌ NO | ❌ NO | ❌ NO |
| **Oct 20** | ✅ YES | ✅ YES | ✅ YES |
| **Oct 21** | ✅ YES | ✅ YES | ✅ YES |
| **Oct 22** | ✅ YES | ✅ YES | ✅ YES |

### Summary

- ✅ **Ready for Backtest**: Oct 16, 20, 21, 22 (4 dates)
- ❌ **Missing Scanner Data**: Oct 15, 17
- ⚠️ **Tick Data Without Scanner**: Oct 15 (orphaned)

---

## October 16, 2025 - COMPLETE ✅

### Scanner Stocks (8)
1. AMD
2. TSLA
3. GME
4. COIN
5. PLTR
6. NVDA
7. QQQ
8. SPY

### Tick Data Available
**Checking**: AMD, COIN, GME, HOOD, NVDA, PATH, PLTR, SMCI, SOFI, TSLA

### Cross-Reference

| Symbol | In Scanner | Has Tick Data | Status |
|--------|------------|---------------|--------|
| **AMD** | ✅ YES | ✅ YES | ✅ READY |
| **TSLA** | ✅ YES | ✅ YES | ✅ READY |
| **GME** | ✅ YES | ✅ YES | ✅ READY |
| **COIN** | ✅ YES | ✅ YES | ✅ READY |
| **PLTR** | ✅ YES | ✅ YES | ✅ READY |
| **NVDA** | ✅ YES | ✅ YES | ✅ READY |
| **QQQ** | ✅ YES | ❌ NO | ⚠️ MISSING TICKS |
| **SPY** | ✅ YES | ❌ NO | ⚠️ MISSING TICKS |
| HOOD | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| PATH | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| SMCI | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| SOFI | ❌ NO | ✅ YES | ℹ️ Extra tick data |

**Backtest Status**: ✅ READY (6/8 stocks have both scanner + tick data)

**Missing Tick Data**: QQQ, SPY (index ETFs - may not have tick downloads)

---

## October 20, 2025 - COMPLETE ✅

### Scanner Stocks (8)
1. TSLA
2. GME
3. PLTR
4. AMD
5. NVDA
6. COIN
7. QQQ
8. SPY

### Cross-Reference

| Symbol | In Scanner | Has Tick Data | Status |
|--------|------------|---------------|--------|
| **TSLA** | ✅ YES | ✅ YES | ✅ READY |
| **GME** | ✅ YES | ✅ YES | ✅ READY |
| **PLTR** | ✅ YES | ✅ YES | ✅ READY |
| **AMD** | ✅ YES | ✅ YES | ✅ READY |
| **NVDA** | ✅ YES | ✅ YES | ✅ READY |
| **COIN** | ✅ YES | ✅ YES | ✅ READY |
| **QQQ** | ✅ YES | ❌ NO | ⚠️ MISSING TICKS |
| **SPY** | ✅ YES | ❌ NO | ⚠️ MISSING TICKS |
| HOOD | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| PATH | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| SMCI | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| SOFI | ❌ NO | ✅ YES | ℹ️ Extra tick data |

**Backtest Status**: ✅ READY (6/8 stocks have both scanner + tick data)

**Same Pattern**: QQQ, SPY missing tick data (expected for indices)

---

## October 21, 2025 - COMPLETE ✅

### Scanner Stocks (10)
1. SMCI (Score 95)
2. SOFI (Score 85)
3. AMD (Score 85)
4. HOOD (Score 75)
5. PATH (Score 65)
6. NVDA (Score 60)
7. TSLA (Score 55)
8. PLTR (Score 55)
9. QQQ (Score 45)
10. (unlisted)

### Cross-Reference

| Symbol | In Scanner | Has Tick Data | Status |
|--------|------------|---------------|--------|
| **SMCI** | ✅ YES | ✅ YES | ✅ READY |
| **SOFI** | ✅ YES | ✅ YES | ✅ READY |
| **AMD** | ✅ YES | ✅ YES | ✅ READY |
| **HOOD** | ✅ YES | ✅ YES | ✅ READY |
| **PATH** | ✅ YES | ✅ YES | ✅ READY |
| **NVDA** | ✅ YES | ✅ YES | ✅ READY |
| **TSLA** | ✅ YES | ✅ YES | ✅ READY |
| **PLTR** | ✅ YES | ✅ YES | ✅ READY |
| **QQQ** | ✅ YES | ❌ NO | ⚠️ MISSING TICKS |
| COIN | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| GME | ❌ NO | ✅ YES | ℹ️ Extra tick data |

**Backtest Status**: ✅ READY (8/10 stocks have both scanner + tick data)

**Excellent Coverage**: 8 out of 10 scanner stocks ready!

---

## October 22, 2025 - COMPLETE ✅

### Scanner Stocks (10)
1. SMCI (Score 75)
2. SOFI (Score 75)
3. AMD (Score 75)
4. NVDA (Score 70)
5. QQQ (Score 55)
6. PLTR (Score 55)
7. TSLA (Score 55)
8. HOOD (Score 50)
9. PATH (Score 45)
10. (unlisted)

### Cross-Reference

| Symbol | In Scanner | Has Tick Data | Status |
|--------|------------|---------------|--------|
| **SMCI** | ✅ YES | ✅ YES | ✅ READY |
| **SOFI** | ✅ YES | ✅ YES | ✅ READY |
| **AMD** | ✅ YES | ✅ YES | ✅ READY |
| **NVDA** | ✅ YES | ✅ YES | ✅ READY |
| **PLTR** | ✅ YES | ✅ YES | ✅ READY |
| **TSLA** | ✅ YES | ✅ YES | ✅ READY |
| **HOOD** | ✅ YES | ✅ YES | ✅ READY |
| **PATH** | ✅ YES | ✅ YES | ✅ READY |
| **QQQ** | ✅ YES | ❌ NO | ⚠️ MISSING TICKS |
| COIN | ❌ NO | ✅ YES | ℹ️ Extra tick data |
| GME | ❌ NO | ✅ YES | ℹ️ Extra tick data |

**Backtest Status**: ✅ READY (8/10 stocks have both scanner + tick data)

**Excellent Coverage**: 8 out of 10 scanner stocks ready!

---

## Summary Statistics

### Overall Coverage

| Metric | Count | Percentage |
|--------|-------|------------|
| **Total Backtest Days Ready** | 4 | 80% (4/5 requested) |
| **Avg Scanner Stocks/Day** | 9 | - |
| **Avg Stocks with Tick Data** | 7 | 78% coverage |
| **Total Unique Symbols** | 12 | - |
| **Symbols with Complete Data** | 8 | 67% |

### Symbols Coverage Across All Dates

| Symbol | Oct 16 | Oct 20 | Oct 21 | Oct 22 | Coverage |
|--------|--------|--------|--------|--------|----------|
| **AMD** | ✅✅ | ✅✅ | ✅✅ | ✅✅ | 100% (4/4) |
| **TSLA** | ✅✅ | ✅✅ | ✅✅ | ✅✅ | 100% (4/4) |
| **PLTR** | ✅✅ | ✅✅ | ✅✅ | ✅✅ | 100% (4/4) |
| **NVDA** | ✅✅ | ✅✅ | ✅✅ | ✅✅ | 100% (4/4) |
| **SMCI** | ❌✅ | ❌✅ | ✅✅ | ✅✅ | 50% (2/4) |
| **SOFI** | ❌✅ | ❌✅ | ✅✅ | ✅✅ | 50% (2/4) |
| **HOOD** | ❌✅ | ❌✅ | ✅✅ | ✅✅ | 50% (2/4) |
| **PATH** | ❌✅ | ❌✅ | ✅✅ | ✅✅ | 50% (2/4) |
| **GME** | ✅✅ | ✅✅ | ❌✅ | ❌✅ | 50% (2/4) |
| **COIN** | ✅✅ | ✅✅ | ❌✅ | ❌✅ | 50% (2/4) |
| **QQQ** | ✅❌ | ✅❌ | ✅❌ | ✅❌ | 0% (0/4) |
| **SPY** | ✅❌ | ✅❌ | ❌❌ | ❌❌ | 0% (0/2) |

**Legend**: ✅✅ = Scanner + Tick Data, ✅❌ = Scanner Only, ❌✅ = Tick Data Only

---

## Missing Data Analysis

### Consistently Missing Tick Data

**QQQ** (index ETF):
- In scanner: Oct 16, 20, 21, 22 (4 dates)
- Has tick data: 0 dates
- **Reason**: Index ETF tick data may not have been downloaded

**SPY** (index ETF):
- In scanner: Oct 16, 20 (2 dates)
- Has tick data: 0 dates
- **Reason**: Index ETF tick data may not have been downloaded

**Recommendation**: Exclude QQQ/SPY from scanner OR download tick data for indices

---

### Tick Data Without Scanner (Orphaned)

These stocks have tick data but weren't in the scanner for certain dates:

**Oct 16, 20**:
- HOOD, PATH, SMCI, SOFI (have tick data, not in scanner)
- **Reason**: Scanner didn't identify these as setups on those days

**Oct 21, 22**:
- COIN, GME (have tick data, not in scanner)
- **Reason**: Scanner didn't identify these as setups on those days

**Impact**: No issue - extra tick data doesn't hurt

---

## Backtesting Recommendations

### ✅ Ready to Backtest (High Confidence)

**October 16, 2025**:
- Backtest symbols: AMD, TSLA, GME, COIN, PLTR, NVDA (6 stocks)
- Skip: QQQ, SPY (no tick data)
- **Command**:
  ```bash
  python3 backtest/backtester.py \
    --scanner ../stockscanner/output/scanner_results_20251016.json \
    --date 2025-10-16 \
    --account-size 50000
  ```

**October 20, 2025**:
- Backtest symbols: TSLA, GME, PLTR, AMD, NVDA, COIN (6 stocks)
- Skip: QQQ, SPY
- **Command**:
  ```bash
  python3 backtest/backtester.py \
    --scanner ../stockscanner/output/scanner_results_20251020.json \
    --date 2025-10-20 \
    --account-size 50000
  ```

**October 21, 2025**:
- Backtest symbols: SMCI, SOFI, AMD, HOOD, PATH, NVDA, TSLA, PLTR (8 stocks)
- Skip: QQQ
- **Command**:
  ```bash
  python3 backtest/backtester.py \
    --scanner ../stockscanner/output/scanner_results_20251021.json \
    --date 2025-10-21 \
    --account-size 50000
  ```

**October 22, 2025**:
- Backtest symbols: SMCI, SOFI, AMD, NVDA, PLTR, TSLA, HOOD, PATH (8 stocks)
- Skip: QQQ
- **Command**:
  ```bash
  python3 backtest/backtester.py \
    --scanner ../stockscanner/output/scanner_results_20251022.json \
    --date 2025-10-22 \
    --account-size 50000
  ```

---

### ❌ Cannot Backtest

**October 17, 2025**:
- Missing scanner data
- Missing tick data
- **Status**: Cannot backtest without both

**October 15, 2025**:
- Has tick data (AMD, COIN, GME, HOOD, NVDA, PATH, PLTR, SMCI, SOFI, TSLA)
- Missing scanner data
- **Status**: Need to generate scanner file for Oct 15

---

## Tick Data Storage Details

**Location**: `/Users/karthik/projects/DayTrader/trader/backtest/data/ticks/`

**Format**: `{SYMBOL}_{DATE}_{HHMMSS}_ticks.json`

**Example**: `AMD_20251016_093000_ticks.json`

**File Sizes**: ~70-100 KB per 1-minute tick file

**Coverage**: 1-minute tick files for full trading day (9:30 AM - 4:00 PM ET)

**Total Files**:
- Oct 15: ~2,500 files (10 symbols × ~250 minutes)
- Oct 16: ~2,500 files (estimated)
- Oct 20: ~2,500 files (estimated)
- Oct 21: ~2,500 files (estimated)
- Oct 22: ~2,500 files (estimated)

**Total Storage**: ~1-1.2 GB tick data for Oct 15-22

---

## Next Steps

### Immediate Actions

1. ✅ **Run October 21 Backtest** (already in progress)
   - Best coverage: 8/10 stocks ready
   - CVD fix validation target

2. ✅ **Run October 16, 20, 22 Backtests**
   - Validate strategy across multiple dates
   - Compare pre/post CVD fix performance

3. ⚠️ **Handle Missing Index Data**
   - Option A: Download QQQ/SPY tick data
   - Option B: Exclude QQQ/SPY from scanner output
   - **Recommendation**: Option B (indices don't fit PS60 strategy)

4. ❌ **October 17 Data**
   - Market was closed? (check calendar)
   - OR: Need to generate scanner + download ticks

### Data Quality Checks

**Before Running Backtests**:
1. Verify tick data file counts per symbol
2. Check for corrupted JSON files
3. Validate time ranges (9:30 AM - 4:00 PM ET)
4. Confirm CVD calculation can handle tick data format

**During Backtests**:
1. Monitor for "tick data not found" errors
2. Log which symbols successfully loaded tick data
3. Track CVD calculation success rate per symbol

---

## Validation Status

| Date | Scanner | Tick Data | Cross-Check | Ready |
|------|---------|-----------|-------------|-------|
| **Oct 16** | ✅ | ✅ | ✅ 6/8 stocks | ✅ YES |
| **Oct 17** | ❌ | ❌ | ❌ | ❌ NO |
| **Oct 20** | ✅ | ✅ | ✅ 6/8 stocks | ✅ YES |
| **Oct 21** | ✅ | ✅ | ✅ 8/10 stocks | ✅ YES |
| **Oct 22** | ✅ | ✅ | ✅ 8/10 stocks | ✅ YES |

**Overall Status**: ✅ **80% READY** (4 out of 5 requested dates)

---

**Document Status**: ✅ COMPLETE
**Generated**: 2025-10-24 00:30:00
**Data Sources**: Scanner output files, tick data folder listing
