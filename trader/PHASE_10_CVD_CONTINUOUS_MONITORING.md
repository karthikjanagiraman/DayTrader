# Phase 10: CVD Continuous Monitoring with Pre-Built Bars (October 21, 2025)

## Problem Statement

**Critical Bug**: CVD slopes returning 0.0 in all backtest scenarios

**Root Cause**: CVDCalculator was being recreated each minute with empty history (`cvd_history = []`), making slope calculation impossible (slope requires multiple data points over time).

**Example of Broken Flow**:
```
Bar 324: Create new CVDCalculator() → cvd_history = []
         Fetch 1,038 ticks → Calculate CVD = 12,500
         cvd_history = [12500] ← Only 1 value!
         Calculate slope → NEEDS 2+ values
         Result: slope = 0.0 (FAIL)

Bar 325: Create new CVDCalculator() → cvd_history = []  (RESET!)
         Fetch ticks → Calculate CVD = 13,200
         cvd_history = [13200] ← Only 1 value again!
         Calculate slope → FAIL
         Result: slope = 0.0 (FAIL)
```

## Solution: Pre-Built CVD-Enriched Bars

**Architecture**: Two-phase approach separating data building from backtesting

### Phase 1: Build CVD-Enriched Bars (Requires IBKR)

**Process**:
1. Fetch all 1-minute bars for trading day (9:30-16:00)
2. For each bar, fetch tick data from IBKR
3. Use **persistent CVDCalculator** across ALL bars (accumulates history)
4. Calculate CVD with growing history → accurate slopes
5. Save results to JSON cache

**Key Innovation**: Persistent CVDCalculator maintains `cvd_history` across all 390 bars

## Expected Benefits

### 1. **Fixes CVD Slope = 0 Bug**
- **Before**: All slopes = 0.0 (useless)
- **After**: Accurate slopes with full historical context

### 2. **IBKR Independence After First Run**
- First backtest: Requires IBKR connection (builds cache)
- Subsequent backtests: No IBKR needed (uses cache)

### 3. **Performance Improvement**
- **Before**: Fetch ticks 390 times per symbol per backtest
- **After**: Fetch ticks ONCE per symbol (cached forever)
- **Speedup**: ~390x faster on subsequent runs

## Implementation Details

**Files Modified**: 4 files, 311 lines total

**Testing Status**: ✅ IMPLEMENTATION COMPLETE - Ready for Testing
