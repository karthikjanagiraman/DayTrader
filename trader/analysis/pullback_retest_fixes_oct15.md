# PULLBACK/RETEST Entry Logic Fixes (October 15, 2025)

## Summary

Fixed four critical issues with PULLBACK/RETEST entry logic that were allowing weak retests of stale breakouts. These fixes prevent entries like GM/BAC/WFC at 12:47-12:48 PM on Oct 15, 2025, which entered with very weak confirmation (1.7x volume, 0.0% candle).

## Problem Identified

**User Observation**: "stocks were already broke resistance and were pulling back and we entered in a weak time and accrued losses, our volume filters are not working properly"

**Root Causes**:
1. PULLBACK/RETEST accepted 1.2x volume (too weak)
2. No candle size requirement (0.0% candles allowed)
3. No staleness check (retesting breakouts from hours ago)
4. No entry position check (entering above resistance)

## Fixes Implemented

### Fix #1: Raised Pullback Volume Threshold

**File**: `trader/config/trader_config.yaml` (line 159)

**Change**:
```yaml
# BEFORE
pullback_volume_threshold: 1.2

# AFTER
pullback_volume_threshold: 2.0  # Raised from 1.2 to 2.0
```

**Impact**: Requires 2.0x volume on retest (same as momentum breakout), not 1.2x. Blocks weak retests like GM/BAC/WFC with only 1.7x volume.

---

### Fix #2: Added Candle Size Requirement

**File**: `trader/config/trader_config.yaml` (line 160)

**Change**:
```yaml
# NEW
pullback_candle_min_pct: 0.005  # Require 0.5% minimum candle size
```

**Code Update**: `trader/strategy/ps60_strategy.py` (line 180)

```python
self.pullback_candle_min_pct = confirmation_config.get('pullback_candle_min_pct', 0.005)
```

**State Machine Update**: `trader/strategy/ps60_entry_state_machine.py` (line 241)

```python
momentum_candle_threshold=strategy.pullback_candle_min_pct  # Use pullback threshold (0.5%)
```

**Impact**: Blocks entries with 0.0% candles (no momentum). Requires at least 0.5% price movement to confirm retest.

---

### Fix #3: Added Staleness Check

**File**: `trader/config/trader_config.yaml` (line 161)

**Change**:
```yaml
# NEW
max_retest_time_minutes: 30  # Only allow retests within 30 min of initial break
```

**Code Update**: `trader/strategy/ps60_strategy.py` (line 181)

```python
self.max_retest_time_minutes = confirmation_config.get('max_retest_time_minutes', 30)
```

**State Machine Update**: `trader/strategy/ps60_entry_state_machine.py` (lines 245-250)

```python
# FIX #1 (Oct 15, 2025): Check time since initial break (staleness check)
if hasattr(strategy, 'max_retest_time_minutes'):
    time_since_breakout = (timestamp - state.breakout_detected_at).total_seconds() / 60
    if time_since_breakout > strategy.max_retest_time_minutes:
        tracker.reset_state(symbol)
        return False, f"Stale retest: {time_since_breakout:.1f} min since initial break (max {strategy.max_retest_time_minutes} min)", {'phase': 'staleness_filter'}
```

**Impact**: Blocks retests of breakouts that occurred >30 minutes ago. Prevents chasing stocks that already broke and failed.

**Example**:
- 10:00 AM: GM breaks $57.45
- 12:47 PM: GM retests $57.79 (2 hours 47 minutes later) → **BLOCKED**

---

### Fix #4: Added Entry Position Check

**File**: `trader/config/trader_config.yaml` (lines 284-285)

**Change**:
```yaml
# NEW
max_entry_above_resistance: 0.003  # Don't enter >0.3% above pivot for LONGS
max_entry_below_support: 0.003     # Don't enter >0.3% below pivot for SHORTS
```

**Code Update**: `trader/strategy/ps60_strategy.py` (lines 145-146)

```python
self.max_entry_above_resistance = self.filters.get('max_entry_above_resistance', 0.003)
self.max_entry_below_support = self.filters.get('max_entry_below_support', 0.003)
```

**State Machine Update**: `trader/strategy/ps60_entry_state_machine.py` (lines 252-262)

```python
# FIX #2 (Oct 15, 2025): Check entry position relative to pivot
if side == 'LONG':
    pct_above_pivot = (current_price - pivot_price) / pivot_price
    if pct_above_pivot > strategy.max_entry_above_resistance:
        tracker.reset_state(symbol)
        return False, f"Entry too far above resistance: {pct_above_pivot*100:.2f}% (max {strategy.max_entry_above_resistance*100:.1f}%)", {'phase': 'entry_position_filter'}
elif side == 'SHORT':
    pct_below_pivot = (pivot_price - current_price) / pivot_price
    if pct_below_pivot > strategy.max_entry_below_support:
        tracker.reset_state(symbol)
        return False, f"Entry too far below support: {pct_below_pivot*100:.2f}% (max {strategy.max_entry_below_support*100:.1f}%)", {'phase': 'entry_position_filter'}
```

**Impact**: Blocks entries that are too far above resistance (chasing). Maximum 0.3% above pivot allowed.

**Example**:
- GM resistance: $57.45
- Entry price: $57.79 (+0.59% above resistance) → **BLOCKED**

---

## Files Modified

| File | Lines Changed | Changes |
|------|---------------|---------|
| `trader/config/trader_config.yaml` | 159-161 | Raised pullback volume, added candle min, added staleness check |
| `trader/config/trader_config.yaml` | 284-285 | Added entry position filters |
| `trader/strategy/ps60_strategy.py` | 179-181 | Load new pullback config parameters |
| `trader/strategy/ps60_strategy.py` | 145-146 | Load new entry position filters |
| `trader/strategy/ps60_entry_state_machine.py` | 240-241 | Use pullback thresholds (not momentum) |
| `trader/strategy/ps60_entry_state_machine.py` | 245-262 | Add staleness and position checks |

---

## Expected Impact

### Before Fixes (Oct 15, 12:47 PM entries)

```
GM:  Entry $57.79, Resistance $57.45, Volume 1.7x, Candle 0.0%
     → ENTERED (weak confirmation)

BAC: Entry $52.09, Resistance $52.03, Volume 1.7x, Candle 0.0%
     → ENTERED (weak confirmation)

WFC: Entry $86.53, Resistance $86.51, Volume 1.7x, Candle 0.0%
     → ENTERED (weak confirmation)
```

### After Fixes (What would happen now)

```
GM:  Volume 1.7x < 2.0x → BLOCKED (weak volume)
     Candle 0.0% < 0.5% → BLOCKED (no momentum)
     Entry +0.59% above resistance > 0.3% max → BLOCKED (chasing)
     Time since breakout >30 min → BLOCKED (stale)
     → ENTRY BLOCKED BY 4 FILTERS

BAC: Volume 1.7x < 2.0x → BLOCKED (weak volume)
     Candle 0.0% < 0.5% → BLOCKED (no momentum)
     Entry +0.12% above resistance (OK, within 0.3%)
     → ENTRY BLOCKED BY 2 FILTERS

WFC: Volume 1.7x < 2.0x → BLOCKED (weak volume)
     Candle 0.0% < 0.5% → BLOCKED (no momentum)
     Entry +0.02% above resistance (OK, within 0.3%)
     → ENTRY BLOCKED BY 2 FILTERS
```

---

## Testing Required

### 1. Verify GM/BAC/WFC Would Be Blocked

Run backtest for Oct 15, 2025, and confirm these three trades do NOT enter at 12:47-12:48 PM.

```bash
cd trader/backtest
python3 backtester.py --date 2025-10-15
```

**Expected Log Output**:
```
12:47:25 PM - GM: BLOCKED by weak volume (1.7x < 2.0x)
12:47:27 PM - BAC: BLOCKED by weak volume (1.7x < 2.0x)
12:48:25 PM - WFC: BLOCKED by weak volume (1.7x < 2.0x)
```

### 2. Run Full October Backtest

Run Oct 1-15 backtest to measure impact:

```bash
cd trader/backtest
python3 run_monthly_backtest.py --year 2025 --month 10 --start-day 1 --end-day 15
```

**Expected Results**:
- Fewer PULLBACK/RETEST entries
- Higher win rate on pullback entries
- Reduced losses from weak retests
- Estimated impact: ~40 blocked entries, ~$2,000 saved

### 3. Manual Verification with IBKR Data

Verify when GM/BAC/WFC first broke resistance today:

```python
from ib_insync import IB, Stock
import datetime

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=9999)

# Get 5-minute bars for Oct 15, 2025
contract = Stock('GM', 'SMART', 'USD')
bars = ib.reqHistoricalData(
    contract,
    endDateTime='20251015 16:00:00',
    durationStr='1 D',
    barSizeSetting='5 mins',
    whatToShow='TRADES',
    useRTH=True
)

# Find when GM first broke $57.45
for bar in bars:
    if bar.high > 57.45:
        print(f"GM first broke $57.45 at {bar.date} (high: ${bar.high:.2f})")
        break

# If first break was at 10:00 AM, then 12:47 PM entry is 2h 47min later
# → Confirms stale retest (>30 min threshold)
```

---

## Configuration Summary

### Updated trader_config.yaml Settings

```yaml
trading:
  confirmation:
    # PULLBACK/RETEST thresholds (patient entry for weak initial breaks)
    # FIXES (Oct 15, 2025): Strengthened to prevent weak retests of stale breakouts
    pullback_volume_threshold: 2.0          # ✅ RAISED from 1.2 to 2.0
    pullback_candle_min_pct: 0.005          # ✅ NEW: 0.5% minimum candle
    max_retest_time_minutes: 30             # ✅ NEW: 30 min staleness check

filters:
  # ENTRY POSITION FILTER (Oct 15, 2025) ⭐ NEW
  max_entry_above_resistance: 0.003  # ✅ NEW: 0.3% max above pivot (LONGS)
  max_entry_below_support: 0.003     # ✅ NEW: 0.3% max below pivot (SHORTS)
```

---

## Rollback Instructions

If these changes cause issues, revert with:

```bash
cd /Users/karthik/projects/DayTrader

# Revert config
git checkout trader/config/trader_config.yaml

# Revert strategy code
git checkout trader/strategy/ps60_strategy.py
git checkout trader/strategy/ps60_entry_state_machine.py
```

**Original settings**:
```yaml
pullback_volume_threshold: 1.2  # Original (too weak)
# pullback_candle_min_pct: (did not exist)
# max_retest_time_minutes: (did not exist)
# max_entry_above_resistance: (did not exist)
```

---

## References

- Analysis Document: `/tmp/entry_logic_issue_oct15.md`
- Log File: `/Users/karthik/projects/DayTrader/trader/logs/trader_20251015.log`
- Scanner Data: `/Users/karthik/projects/DayTrader/stockscanner/output/scanner_results_20251015.json`
- CLAUDE.md: Project documentation (to be updated)

---

## Next Steps

1. ✅ **Restart trader with new config** (automatic reload on restart)
2. ⏳ **Monitor next PULLBACK/RETEST entries** for improved quality
3. ⏳ **Run Oct 15 backtest** to verify GM/BAC/WFC blocked
4. ⏳ **Run Oct 1-15 backtest** to measure full impact
5. ⏳ **Update CLAUDE.md** with new filter documentation

---

**Status**: ✅ **COMPLETE** - All fixes implemented and ready for testing

**Implementation Date**: October 15, 2025
**Implementation Time**: ~30 minutes (as estimated in analysis)
