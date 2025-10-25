# CVD Phase 1 Fix - Zero Trades Analysis
**Date**: October 22, 2025
**Backtest**: October 21, 2025 (8 symbols)
**Result**: ❌ **0 trades executed** (vs 6 trades with OLD slope-based method)

---

## ✅ What's Working

The CVD Phase 1 fix IS correctly implemented and calculating imbalance_pct:

**Evidence from logs** (`backtest_20251021_191653.log`):
```
Bar 216: CVD monitoring (imbalance -11.1%, consecutive 0)
Bar 228: CVD monitoring (imbalance -23.9%, consecutive 0)
Bar 240: CVD monitoring (imbalance -2.1%, consecutive 0)
Bar 252: CVD monitoring (imbalance -13.5%, consecutive 0)
```

✅ **Imbalance calculation working**
✅ **1-minute bars being used** (390 bars per day)
✅ **CVD-enriched cache includes new fields** (imbalance_pct, buy_volume, sell_volume)
✅ **Tick data properly cached** (100% hit rate)

---

## ❌ Root Cause: Consecutive Counter Bug

### Problem

**`consecutive_count` is ALWAYS 0**, even when imbalance exceeds thresholds!

### Evidence

| Bar | Symbol | Imbalance | Threshold | Expected | Actual | Status |
|-----|--------|-----------|-----------|----------|--------|--------|
| 216 | SMCI | **-11.1%** | -10% | Count → 1 | Count → 0 | ❌ BUG |
| 228 | SMCI | **-23.9%** | -20% (PATH 1!) | **ENTER NOW** | Count → 0 | ❌ BUG |
| 252 | SMCI | **-13.5%** | -10% | Count → 1 | Count → 0 | ❌ BUG |
| 300 | HOOD | **-11.6%** | -10% | Count → 1 | Count → 0 | ❌ BUG |
| 312 | HOOD | **+9.0%** | +10% | Count → 0 | Count → 0 | ✅ OK |
| 324 | HOOD | **+8.5%** | +10% | Count → 0 | Count → 0 | ✅ OK |

### Critical Finding

**SMCI Bar 228**: Imbalance = **-23.9%** (exceeds -20% aggressive threshold)
→ This SHOULD have triggered **PATH 1 (Aggressive Entry)** immediately
→ But it didn't! consecutive_count stayed at 0, no entry logged

---

## 📊 CVD Imbalance Distribution Analysis

I analyzed all 8 symbols to verify that strong imbalances ARE present:

| Symbol | Strong Buying (<-10%) | Strong Selling (>10%) | Total Bars |
|--------|----------------------|----------------------|------------|
| SMCI | 103 bars (26.4%) | 130 bars (33.3%) | 390 |
| SOFI | 131 bars (33.6%) | 107 bars (27.4%) | 390 |
| AMD | 60 bars (15.4%) | 120 bars (30.8%) | 390 |
| HOOD | 62 bars (15.9%) | 156 bars (40.0%) | 390 |
| PATH | 73 bars (18.7%) | 144 bars (36.9%) | 390 |
| NVDA | 51 bars (13.1%) | 206 bars (52.8%) | 390 |
| TSLA | 55 bars (14.1%) | 153 bars (39.2%) | 390 |
| PLTR | 61 bars (15.6%) | 180 bars (46.2%) | 390 |

**Conclusion**: Strong CVD signals ARE present (15-53% of bars exceed thresholds), but the entry logic isn't detecting them.

---

## 🔍 Expected Behavior vs Actual

### PATH 1: Aggressive Entry (Strong Spike)

**Criteria**: Single candle with imbalance ≥ 20% (buying) or ≤ -20% (selling)

**Expected**:
```
Bar 228: SMCI imbalance = -23.9% (buying)
→ imbalance_pct <= -20.0 ✅
→ ENTER LONG immediately (PATH 1)
→ Log: "🎯 PATH 1: AGGRESSIVE ENTRY (Strong buying pressure, imbalance -23.9%)"
```

**Actual**:
```
Bar 228: SMCI imbalance = -23.9%
→ consecutive_count = 0 (BUG!)
→ No entry
→ Log: "CVD monitoring (imbalance -23.9%, consecutive 0)"
```

### PATH 2: Sustained Entry (Consecutive Candles)

**Criteria**: 3 consecutive candles with imbalance ≥ 10% (same direction)

**Expected**:
```
Bar 216: SMCI imbalance = -11.1% → consecutive_count = 1
Bar 228: SMCI imbalance = -23.9% → consecutive_count = 2
Bar 252: SMCI imbalance = -13.5% → consecutive_count = 3
→ ENTER LONG (PATH 2)
→ Log: "🎯 PATH 2: SUSTAINED ENTRY (3 consecutive buying candles)"
```

**Actual**:
```
Bar 216: consecutive_count = 0 (BUG!)
Bar 228: consecutive_count = 0 (BUG!)
Bar 252: consecutive_count = 0 (BUG!)
→ No entry
```

---

## 🐛 Code Location of Bug

The consecutive counter logic is in:

**File**: `trader/strategy/ps60_entry_state_machine.py`

**Functions**:
- `_check_cvd_path1_aggressive()` (lines ~160-200)
- `_check_cvd_path2_sustained()` (lines ~200-250)

**Suspected Issue**:

The state machine is NOT incrementing `consecutive_count` when imbalance exceeds thresholds. Possible reasons:

1. **Logical bug**: Condition check is wrong (e.g., checking opposite direction)
2. **State reset bug**: Counter is being reset every candle instead of accumulated
3. **Wrong state field**: Reading/writing to wrong state variable
4. **Missing implementation**: Counter increment code never written

---

## 📋 Next Steps to Fix

### Step 1: Review Consecutive Counter Logic

Read the actual code in `ps60_entry_state_machine.py` to find where consecutive_count should be incremented:

```python
# Expected logic (PATH 2 - Sustained)
if side == 'LONG':
    if imbalance_pct <= -10.0:  # 10% more buying
        consecutive_count += 1  # Should increment here!
    else:
        consecutive_count = 0   # Reset if not sustained
```

### Step 2: Add Debug Logging

Add logging at the point where consecutive_count SHOULD be incremented:

```python
if imbalance_pct <= -10.0:
    consecutive_count += 1
    logger.debug(f"PATH 2: Buying pressure detected ({imbalance_pct:.1f}%), "
                 f"consecutive_count={consecutive_count}/3")
```

### Step 3: Test with One Symbol

Run backtest on just SMCI (has -23.9% imbalance at bar 228):

```bash
cd /Users/karthik/projects/DayTrader/trader
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251021.json \
  --date 2025-10-21 \
  --symbols SMCI
```

Expected output:
```
Bar 228: 🎯 PATH 1: AGGRESSIVE ENTRY (imbalance -23.9%)
SMCI: LONG @ $54.xx (PATH 1: Strong buying pressure)
```

### Step 4: Run Full Backtest

Once fixed, run full Oct 21 backtest and expect:
- **15-30 trades** (based on imbalance distribution)
- **40-60% MOMENTUM breakouts** (imbalance >20%)
- **40-60% SUSTAINED breakouts** (3 consecutive >10%)

---

## 📂 Related Files

- **CVD Calculator**: `trader/indicators/cvd_calculator.py` ✅ (working correctly)
- **State Machine**: `trader/strategy/ps60_entry_state_machine.py` ❌ (has bug)
- **Backtester**: `trader/backtest/backtester.py` ✅ (working correctly)
- **Config**: `trader/config/trader_config.yaml` ✅ (thresholds correct)
- **CVD Data**: `trader/backtest/data/cvd_bars/*.json` ✅ (new fields present)

---

## 🎯 Expected Impact After Fix

| Metric | Before Fix | After Fix (Estimated) |
|--------|------------|---------------------|
| Trades | 0 | 15-30 |
| PATH 1 (Aggressive) | 0 | 5-10 (strong spikes >20%) |
| PATH 2 (Sustained) | 0 | 10-20 (3+ consecutive >10%) |
| Win Rate | N/A | 35-45% (same as OLD method) |
| P&L | $0 | $-500 to +$2,000 (need to tune) |

---

## ✅ Summary

1. **CVD Phase 1 fix is correctly implemented** (imbalance_pct calculating properly)
2. **Strong imbalance signals ARE present** (15-53% of bars exceed thresholds)
3. **Bug is in consecutive counter logic** (always stays at 0)
4. **Bar 228 SMCI should have entered** (-23.9% imbalance, exceeds -20% PATH 1 threshold)
5. **Next step**: Fix consecutive counter in `ps60_entry_state_machine.py`

**Status**: ⚠️ **Implementation complete, but entry logic bug preventing trades**
