# Issues #2 and #3 - FIXED
## October 28, 2025

## Executive Summary

**Status**: ✅ **BOTH ISSUES FIXED**

Both issues stemmed from using **5-second bar data** for calculations that should use **1-minute aggregated candle data** in live trading.

**Solution**: Created two helper functions that automatically handle both live (5-second) and backtest (1-minute) modes.

---

## Issue #2: Sustained Break Candle Size ✅ FIXED

### The Problem (Before)

**Location**: `ps60_entry_state_machine.py` line 1293-1304

**Buggy Code**:
```python
# ❌ WRONG: Uses ONE 5-second bar in live trading
current_bar = bars[current_idx]
candle_size_pct = abs(current_bar.close - current_bar.open) / current_bar.open
```

**Impact**:
- Live: Checked if **ONE 5-second bar** meets 0.3% threshold
- Should check if **1-MINUTE CANDLE** (12 five-second bars) meets 0.3%
- Result: Valid sustained breaks rejected because a single 5-second bar was too small

**Example**:
- Bar 131 (5-second): Open $52.84, Close $52.85 (0.02% change) → **REJECTED** ❌
- Bars 120-131 (1-minute candle): Open $52.82, Close $52.90 (0.15% change) → **Should PASS** ✅

### The Fix

**New Helper Function** (`ps60_strategy.py` lines 2573-2633):
```python
def get_current_candle_metrics(self, bars, current_idx):
    """
    Get metrics for current 1-minute candle

    Automatically handles both modes:
    - Live: Aggregates 12 five-second bars
    - Backtest: Uses current 1-minute bar
    """
    bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds

    if bars_per_candle > 1:
        # Live: Aggregate to candle
        candle_start = (current_idx // bars_per_candle) * bars_per_candle
        candle_bars = bars[candle_start:candle_start + bars_per_candle]
        candle_open = candle_bars[0].open
        candle_close = candle_bars[-1].close
        candle_volume = sum(b.volume for b in candle_bars)
    else:
        # Backtest: Current bar IS the candle
        candle_open = bars[current_idx].open
        candle_close = bars[current_idx].close
        candle_volume = bars[current_idx].volume

    candle_size_pct = abs(candle_close - candle_open) / candle_open

    return {
        'volume': candle_volume,
        'size_pct': candle_size_pct,
        ...
    }
```

**New Usage** (`ps60_entry_state_machine.py` lines 1296-1303):
```python
# ✅ CORRECT: Gets 1-minute candle metrics in both modes
candle_metrics = strategy.get_current_candle_metrics(bars, current_idx)

current_volume = candle_metrics['volume']       # 1-minute candle volume
candle_size_pct = candle_metrics['size_pct']  # 1-minute candle size
```

**Result**:
- Live: Aggregates 12 five-second bars → checks full 1-minute candle ✅
- Backtest: Uses 1-minute bar → works as before ✅

---

## Issue #3: Sustained Break Volume Average ✅ FIXED

### The Problem (Before)

**Location**: `ps60_entry_state_machine.py` line 1296-1301

**Buggy Code**:
```python
# ❌ WRONG: Averages last 20 5-second bars (1min 40sec), not 20 1-minute candles!
if current_idx >= 20:
    avg_volume = sum(bars[i].volume for i in range(current_idx-19, current_idx+1)) / 20
```

**Impact**:
- Live: Averaged 20 **5-second bars** (1 minute 40 seconds)
- Should average 20 **1-minute candles** (20 minutes)
- Result: Wrong timeframe for volume comparison

**Example**:
- Old: Last 20 bars = 100 seconds of data
- New: Last 20 candles = 1200 seconds (20 minutes) of data

### The Fix

**New Helper Function** (`ps60_strategy.py` lines 2635-2687):
```python
def get_average_candle_volume(self, bars, current_idx, lookback_candles=20):
    """
    Calculate average 1-minute candle volume over last N candles

    Automatically handles both modes:
    - Live: Aggregates to 1-minute candles first, then averages
    - Backtest: Uses 1-minute bars directly
    """
    bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds
    lookback_bars = lookback_candles * bars_per_candle  # 20 candles worth of bars

    # Get bars for lookback period
    start_idx = max(0, current_idx - lookback_bars + 1)
    past_bars = bars[start_idx:current_idx+1]

    if bars_per_candle > 1:
        # Live: Aggregate to candle volumes
        candle_volumes = []
        for i in range(0, len(past_bars), bars_per_candle):
            candle_bars = past_bars[i:i+bars_per_candle]
            if len(candle_bars) == bars_per_candle:  # Only complete candles
                candle_vol = sum(b.volume for b in candle_bars)
                candle_volumes.append(candle_vol)
        return sum(candle_volumes) / len(candle_volumes)
    else:
        # Backtest: Bars are already candles
        return sum(b.volume for b in past_bars) / len(past_bars)
```

**New Usage** (`ps60_entry_state_machine.py` lines 1305-1308):
```python
# ✅ CORRECT: Averages last 20 1-minute candles (20 minutes)
avg_volume = strategy.get_average_candle_volume(bars, current_idx, lookback_candles=20)
# Live: 20 candles = 240 bars (20 minutes) ✅
# Backtest: 20 candles = 20 bars (20 minutes) ✅
```

**Result**:
- Live: Aggregates 240 five-second bars into 20 candles → averages 20 minutes ✅
- Backtest: Uses 20 one-minute bars → averages 20 minutes ✅

---

## How The Fixes Work

### Key Insight: `bars_per_candle` Detection

Both helpers use `bars_per_candle` to automatically detect the mode:

```python
bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds

# Live: 60 // 5 = 12 bars per candle
# Backtest: 60 // 60 = 1 bar per candle

if bars_per_candle > 1:
    # Live mode: Aggregate needed
    ...
else:
    # Backtest mode: No aggregation needed
    ...
```

**Result**: Same code works in both modes!

### Live Trading Flow

```
5-Second Bars: [0][1][2]...[11][12][13]...[23]...
                └────────────┘  └────────────┘
                1-min candle     1-min candle

get_current_candle_metrics(bars, 131):
    bars_per_candle = 12
    candle_start = (131 // 12) * 12 = 120
    candle_bars = bars[120:132]  # 12 bars
    candle_open = bars[120].open
    candle_close = bars[131].close
    candle_size = (close - open) / open
    → Returns 1-minute candle metrics ✅

get_average_candle_volume(bars, 131, 20):
    lookback_bars = 20 * 12 = 240
    past_bars = bars[0:132]  # All bars up to current
    # Aggregate every 12 bars into candles
    candle_volumes = [vol(0-11), vol(12-23), ..., vol(120-131)]
    → Returns average of candle volumes ✅
```

### Backtest Flow

```
1-Minute Bars: [0][1][2][3]...[19][20]...
                ↑   ↑   ↑
          Each bar IS a candle

get_current_candle_metrics(bars, 20):
    bars_per_candle = 1
    # Current bar IS the candle
    candle_open = bars[20].open
    candle_close = bars[20].close
    candle_size = (close - open) / open
    → Returns current bar metrics ✅

get_average_candle_volume(bars, 20, 20):
    lookback_bars = 20 * 1 = 20
    past_bars = bars[1:21]  # Last 20 bars
    # Bars are already candles
    → Returns average of bar volumes ✅
```

---

## Files Modified

| File | Lines | Description |
|------|-------|-------------|
| `trader/strategy/ps60_strategy.py` | 2573-2633 | Added `get_current_candle_metrics()` helper |
| `trader/strategy/ps60_strategy.py` | 2635-2687 | Added `get_average_candle_volume()` helper |
| `trader/strategy/ps60_entry_state_machine.py` | 1292-1308 | Updated to use new helpers |

**Total**: 117 lines added (53 + 52 + 12)

---

## Testing Verification

### Test #1: Live Trading (5-Second Bars)

**Scenario**: Bar 131 (11:36:31 ET), price breaks next technical level

**Before (Buggy)**:
```python
current_bar = bars[131]  # ONE 5-second bar
candle_size_pct = 0.02%  # Bar 131: $52.84 → $52.85
avg_volume = average of last 20 5-second bars (100 seconds)

# Check: 0.02% < 0.3% → REJECTED ❌
```

**After (Fixed)**:
```python
candle_metrics = get_current_candle_metrics(bars, 131)
candle_size_pct = 0.15%  # Candle (bars 120-131): $52.82 → $52.90
avg_volume = average of last 20 1-minute candles (20 minutes)

# Check: 0.15% < 0.3% → REJECTED (still fails, but for correct reason)
# If it was 0.35%: 0.35% >= 0.3% → PASSED ✅
```

### Test #2: Backtesting (1-Minute Bars)

**Scenario**: Bar 20, checking sustained break

**Before (Buggy for live, OK for backtest)**:
```python
current_bar = bars[20]   # 1-minute bar
candle_size_pct = (bar.close - bar.open) / bar.open
avg_volume = average of last 20 bars

# Works because bars ARE candles ✅
```

**After (Fixed, still works)**:
```python
candle_metrics = get_current_candle_metrics(bars, 20)
# bars_per_candle = 1, so uses bars[20] directly
candle_size_pct = (bar.close - bar.open) / bar.open
avg_volume = get_average_candle_volume(bars, 20, 20)
# bars_per_candle = 1, so uses bars[1:21] directly

# Same result as before ✅
```

---

## Expected Impact

### Live Trading
✅ **Sustained break candle size check now uses full 1-minute candle**
- More accurate detection of momentum
- Fewer false rejections of valid breakouts
- Candle size reflects actual 1-minute price movement

✅ **Volume average now uses 20 minutes of data**
- More stable volume baseline
- Better detection of volume spikes
- Matches intended strategy design

### Backtesting
✅ **No change in behavior**
- Already used 1-minute bars correctly
- Helpers detect `bars_per_candle = 1` and use bars directly
- Same logic, just wrapped in helper functions

---

## Summary

**Problem**: Live trading used 5-second bars for 1-minute decisions
**Solution**: Helper functions that auto-aggregate based on `bars_per_candle`
**Result**: ✅ Works correctly in both live (5-sec) and backtest (1-min) modes

**Code Quality**:
- ✅ Single source of truth (helpers in ps60_strategy.py)
- ✅ Resolution-agnostic (automatically detects mode)
- ✅ Reusable (can be called from anywhere)
- ✅ Well-documented (comments explain live vs backtest)

---

*Fix completed: October 28, 2025*
*Tested: Code logic verified*
*Status: Ready for live testing*
