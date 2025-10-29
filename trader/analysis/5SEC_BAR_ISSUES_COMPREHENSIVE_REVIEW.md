# 5-Second Bar Issues - Comprehensive Code Review
## October 28, 2025

## Executive Summary

**CRITICAL FINDING**: Multiple locations in the codebase are using **5-SECOND BAR** data for calculations that should use **1-MINUTE AGGREGATED CANDLE** data.

**Impact**: These issues are blocking valid entries and causing incorrect filter decisions.

---

## Issue #1: CVD Candle Color Validation ✅ **FIXED**

**File**: `trader/indicators/cvd_calculator.py`
**Lines**: 365, 166-197
**Status**: ✅ **FIXED** (Oct 28, 2025)

### Problem (Before Fix)
```python
# Line 365 - BUGGY
current_bar = bars[current_idx]  # Gets 5-second bar
return self.calculate_from_ticks(ticks, bar=current_bar)

# Line 174-188 - BUGGY
bar_open = bar.open   # 5-second bar's open
bar_close = bar.close  # 5-second bar's close
price_change_pct = (price_change / bar_open) * 100

if abs(price_change_pct) < 0.1:
    price_direction = 'NEUTRAL'  # DOJI
```

**Impact**:
- SMCI 11:36 ET: +0.076% GREEN candle classified as DOJI
- SMCI 11:37 ET: +0.246% GREEN candle classified as DOJI
- All entries blocked as "CVD BULLISH but DOJI (no winner)"

### Fix Applied
```python
# Now uses TICK DATA directly for candle color
first_tick_price = ticks[0].price  # "Open" of tick window
last_tick_price = ticks[-1].price  # "Close" of tick window
price_change_pct = (last_tick_price - first_tick_price) / first_tick_price * 100

DOJI_THRESHOLD = 0.02  # 0.02% (traditional definition)

if abs(price_change_pct) < DOJI_THRESHOLD:
    price_direction = 'NEUTRAL'  # True DOJI
elif price_change > 0:
    price_direction = 'UP'  # Green candle
else:
    price_direction = 'DOWN'  # Red candle
```

**Result**: Candle color now determined from ticks, not 5-second bars ✅

---

## Issue #2: Sustained Break Candle Size ⚠️ **NEEDS FIX**

**File**: `trader/strategy/ps60_entry_state_machine.py`
**Lines**: 1293-1304
**Status**: ⚠️ **NEEDS FIXING**

### Problem
```python
# Line 1293-1304 - BUGGY
current_bar = bars[current_idx]  # ❌ Gets 5-second bar
current_volume = current_bar.volume
candle_size_pct = abs(current_bar.close - current_bar.open) / current_bar.open

# Passes to check_sustained_hold()
tracker.check_sustained_hold(
    ...
    current_volume=current_volume,    # ❌ 5-second bar volume
    candle_size_pct=candle_size_pct,  # ❌ 5-second bar size!
    momentum_candle_threshold=0.003   # 0.3% threshold
)
```

### Impact
In `breakout_state_tracker.py` line 574-576:
```python
# PHASE 6 FILTER 2: Momentum Candle (≥0.3%)
if candle_size_pct < momentum_candle_threshold:
    return False  # ❌ Rejects based on 5-second bar size!
```

**Example**:
- 5-second bar: Open $52.84, Close $52.85 (0.02% change) → **REJECTED** ❌
- 1-minute candle: Open $52.82, Close $52.90 (0.15% change) → **Should PASS** ✅

**Consequence**: Valid sustained breaks are being rejected because a single 5-second bar doesn't meet the 0.3% threshold, even though the 1-minute candle does.

### Fix Needed
```python
# Instead of single bar, aggregate 1-minute candle
bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds  # 12
candle_start = (current_idx // bars_per_candle) * bars_per_candle
candle_bars = bars[candle_start:candle_start + bars_per_candle]

# Calculate 1-minute candle metrics
candle_open = candle_bars[0].open
candle_close = candle_bars[-1].close
candle_size_pct = abs(candle_close - candle_open) / candle_open

# Calculate 1-minute candle volume
candle_volume = sum(b.volume for b in candle_bars)

# Now pass aggregated metrics
tracker.check_sustained_hold(
    ...
    current_volume=candle_volume,     # ✅ 1-minute candle volume
    candle_size_pct=candle_size_pct,  # ✅ 1-minute candle size
    ...
)
```

---

## Issue #3: Sustained Break Volume ⚠️ **NEEDS FIX**

**File**: `trader/strategy/ps60_entry_state_machine.py`
**Lines**: 1296-1301
**Status**: ⚠️ **NEEDS FIXING**

### Problem
```python
# Line 1296-1301 - BUGGY
# Calculate average volume (last 20 bars of 5-second data)
if current_idx >= 20:
    avg_volume = sum(bars[i].volume for i in range(current_idx-19, current_idx+1)) / 20
```

**Issue**: Calculates average of 20 **5-second bars** (1 minute 40 seconds), not 20 **1-minute candles** (20 minutes).

### Impact
In `breakout_state_tracker.py` line 567-570:
```python
# PHASE 6 FILTER 1: Momentum Volume (≥2.0x)
volume_ratio = current_volume / avg_volume
if volume_ratio < momentum_volume_threshold:
    return False  # ❌ Comparing wrong timeframes!
```

**Comparing**:
- `current_volume` = ONE 5-second bar (e.g., 100 shares)
- `avg_volume` = Average of 20 5-second bars (e.g., 50 shares)
- Ratio = 100/50 = 2.0x ✅ (looks good)

**But SHOULD compare**:
- `current_volume` = ONE 1-minute candle (e.g., 1,200 shares = 12 bars × 100)
- `avg_volume` = Average of 20 1-minute candles (e.g., 600 shares = 12 bars × 50)
- Ratio = 1,200/600 = 2.0x ✅ (same result)

**Verdict**: This might accidentally work if checked on every bar, but it's conceptually wrong. Should aggregate to 1-minute candles for consistency.

### Fix Needed
```python
# Calculate average volume over 20 1-minute candles
bars_per_candle = 12
lookback_candles = 20
lookback_bars = lookback_candles * bars_per_candle  # 240 bars = 20 minutes

if current_idx >= lookback_bars:
    # Get last 20 1-minute candles worth of bars
    past_bars = bars[current_idx - lookback_bars + 1 : current_idx + 1]

    # Calculate average 1-minute candle volume
    total_volume = sum(b.volume for b in past_bars)
    avg_candle_volume = total_volume / lookback_candles
else:
    # Not enough history
    avg_candle_volume = None
```

---

## Issue #4: Other `bars[current_idx]` Usages

### Locations Found
1. **ps60_strategy.py:476** - `_check_bounce_setup()`
2. **ps60_strategy.py:3230** - `_detect_bounce_setup_detailed()`
3. **ps60_strategy.py:3334** - `_detect_rejection_setup_detailed()`

### Analysis
These appear to be for **bounce** and **rejection** setup detection (Phase 4, not implemented yet). They use `current_bar = bars[current_idx]` to check if price touched support/resistance.

**Status**: ⚠️ **REVIEW WHEN IMPLEMENTING BOUNCE/REJECTION**

Since these features aren't active yet, they don't affect current trading. But when implemented, they should aggregate to 1-minute candles.

---

## Common Pattern Analysis

### The Bug Pattern
```python
# ❌ WRONG: Using single 5-second bar for decisions
current_bar = bars[current_idx]
candle_size = abs(current_bar.close - current_bar.open) / current_bar.open

if candle_size < threshold:
    reject_entry()
```

### The Correct Pattern
```python
# ✅ CORRECT: Aggregate to 1-minute candle
bars_per_candle = 12  # 60 seconds / 5 seconds
candle_start = (current_idx // bars_per_candle) * bars_per_candle
candle_bars = bars[candle_start:candle_start + bars_per_candle]

candle_open = candle_bars[0].open
candle_close = candle_bars[-1].close
candle_size = abs(candle_close - candle_open) / candle_open

if candle_size < threshold:
    reject_entry()
```

---

## Root Cause Analysis

### Why This Happened
1. **Bar Buffer Design**: System stores 5-second bars in `bars[]` array
2. **CVD Timing**: CVD checks happen at 1-minute boundaries (every 12 bars)
3. **Assumption Error**: Code assumes `bars[current_idx]` represents the "current candle"
4. **Reality**: `bars[current_idx]` is the **current 5-second bar**, not the full 1-minute candle

### Why It's Hard to Spot
- Code waits for 1-minute candle close: `bars_into_candle == 11`
- At that moment, `current_idx` points to bar 11, 23, 35, etc.
- **Feels** like you're at a candle boundary
- But `bars[current_idx]` is **still just bar 11** (a single 5-second bar)
- To get the full candle, you need bars[0:12], bars[12:24], bars[24:36], etc.

---

## Testing Plan

### Test #1: Verify CVD Fix (Issue #1)
**Status**: ✅ Fixed

**Test**:
1. Run trader on Oct 28 data
2. Check SMCI entries at 11:36-11:41 ET
3. Verify no "DOJI" blocks on green candles

**Expected**: SMCI entries no longer blocked as DOJI ✅

### Test #2: Verify Sustained Break Issue (Issue #2)
**Status**: ⚠️ Needs testing after fix

**Test**:
1. Find cases where sustained break logic runs
2. Check if candle_size_pct is calculated from 1-minute candle
3. Verify 0.3% threshold is applied to full candle, not 5-second bar

**Expected**: More sustained break entries pass momentum filter

### Test #3: Volume Calculation (Issue #3)
**Status**: ⚠️ Needs testing after fix

**Test**:
1. Log both methods:
   - Old: 20 5-second bars average
   - New: 20 1-minute candles average
2. Compare ratios
3. Check if entry decisions change

**Expected**: Volume ratios should be similar, but calculation is conceptually correct

---

## Recommendations

### Priority 1: Fix Issue #2 (Sustained Break Candle Size) - IMMEDIATE
- **Impact**: HIGH - Blocking valid sustained break entries
- **Complexity**: LOW - Same pattern as CVD fix
- **Files**: `trader/strategy/ps60_entry_state_machine.py` lines 1293-1318

### Priority 2: Fix Issue #3 (Sustained Break Volume) - HIGH
- **Impact**: MEDIUM - Conceptually wrong, may affect edge cases
- **Complexity**: LOW - Same aggregation pattern
- **Files**: `trader/strategy/ps60_entry_state_machine.py` lines 1296-1301

### Priority 3: Review Issue #4 (Bounce/Rejection) - LOW
- **Impact**: NONE - Features not implemented yet
- **Complexity**: MEDIUM - Multiple files
- **Action**: Document for future implementation

### Priority 4: Add Helper Function - MEDIUM
Create a centralized helper:
```python
def get_current_candle_metrics(bars, current_idx, bars_per_candle):
    """
    Get metrics for current 1-minute candle (aggregated from 5-second bars)

    Returns:
        dict: {
            'open': float,
            'close': float,
            'high': float,
            'low': float,
            'volume': float,
            'size_pct': float,
            'direction': str  # 'UP', 'DOWN', 'NEUTRAL'
        }
    """
    candle_start = (current_idx // bars_per_candle) * bars_per_candle
    candle_bars = bars[candle_start:candle_start + bars_per_candle]

    if not candle_bars or len(candle_bars) < bars_per_candle:
        return None

    candle_open = candle_bars[0].open
    candle_close = candle_bars[-1].close
    candle_high = max(b.high for b in candle_bars)
    candle_low = min(b.low for b in candle_bars)
    candle_volume = sum(b.volume for b in candle_bars)

    size_pct = abs(candle_close - candle_open) / candle_open
    direction = 'UP' if candle_close > candle_open else ('DOWN' if candle_close < candle_open else 'NEUTRAL')

    return {
        'open': candle_open,
        'close': candle_close,
        'high': candle_high,
        'low': candle_low,
        'volume': candle_volume,
        'size_pct': size_pct,
        'direction': direction
    }
```

**Usage**:
```python
# Instead of: current_bar = bars[current_idx]
candle_metrics = get_current_candle_metrics(bars, current_idx, 12)
if candle_metrics:
    candle_size_pct = candle_metrics['size_pct']
    candle_volume = candle_metrics['volume']
```

---

## Lessons Learned

1. **Always aggregate to decision timeframe**: If making decisions on 1-minute candles, aggregate 5-second bars first
2. **Don't assume array indices match candles**: `bars[current_idx]` is a bar, not a candle
3. **Consistent timeframes**: Use same timeframe for all related calculations
4. **Test with real data**: IBKR 1-minute data revealed the discrepancy
5. **User feedback is valuable**: User correctly identified "there were no DOJI candles"

---

*Analysis completed: October 28, 2025*
*Issues found: 4*
*Issues fixed: 1*
*Issues pending: 3*
