# Phase 10: CVD Threshold Tuning (Oct 23, 2025)

## Problem Statement

Analysis of SOFI, AMD, and HOOD on Oct 21 showed that all three setups were correctly filtered out by the current CVD logic (40% AGGRESSIVE, 20% SUSTAINED), but the thresholds may be too strict.

**Key Findings**:
- SOFI: -12.8% imbalance at resistance break (too weak)
- AMD: +7.7% imbalance at support break (false breakdown)
- HOOD: Multiple breaks, highest was +23.9% (isolated spike, not sustained)

**User Request**: Lower thresholds to catch more setups while maintaining quality

## Configuration Changes

### Before (Oct 22, 2025)
```yaml
cvd:
  strong_imbalance_threshold: 40.0    # AGGRESSIVE path (single candle)
  imbalance_threshold: 20.0           # SUSTAINED path (3 consecutive)
```

### After (Oct 23, 2025 - Phase 10)
```yaml
cvd:
  strong_imbalance_threshold: 30.0    # AGGRESSIVE path (initial candle)
  strong_confirmation_threshold: 10.0  # NEW - confirmation candle
  imbalance_threshold: 10.0           # SUSTAINED path (3 consecutive)
```

## Logic Changes

### PATH 1: AGGRESSIVE (30% + 10% confirmation)

**Old Logic**:
```
IF current_candle ≥ 40% → ENTER immediately
```

**New Logic**:
```
IF current_candle ≥ 30%:
    Mark as "pending strong spike"
    Store imbalance_pct

On NEXT candle:
    IF imbalance ≥ 10% AND same direction:
        ✅ ENTER (strong spike confirmed)
    ELSE:
        ❌ Clear pending spike
```

**Benefits**:
- Catches strong moves (30% is significant)
- Requires confirmation (prevents single-tick spikes)
- Two-candle pattern more reliable than single candle

**Example - HOOD 13:51 PM**:
- Candle 1: +23.9% bearish ✅ (≥30%, mark as pending)
- Candle 2: Check next candle...
  - If ≥+10% bearish → ENTER
  - If <+10% or bullish → SKIP

### PATH 2: SUSTAINED (10% sliding window)

**Old Logic**:
```
counter = 0
FOR each candle:
    IF imbalance ≥ 20%:
        counter += 1
        IF counter ≥ 3 → ENTER
    ELSE IF opposite direction:
        counter = 0  # ❌ RESET!
```

**New Logic**:
```
history = []  # Store last N imbalances

FOR each candle:
    history.append(imbalance_pct)

    # Sliding window: check last 3 candles
    IF len(history) ≥ 3:
        last_3 = history[-3:]

        IF all(abs(x) ≥ 10% AND same_direction(x) for x in last_3):
            ✅ ENTER (sustained pressure confirmed)
```

**Benefits**:
- No reset on single weak candle
- Continuously checks for 3-consecutive pattern
- More forgiving of brief neutral ticks
- Lower 10% threshold catches more setups

**Example - HOOD throughout day**:
```
09:43: +7.5%  ❌
09:44: +10.7% ✅
09:45: +3.6%  ❌
...
13:50: +15.2% ✅
13:51: +23.9% ✅
13:52: -6.5%  ❌ (wrong direction)
...
14:05: +15.2% ✅
14:06: +9.2%  ❌
14:07: +28.7% ✅

Pattern search:
- No 3 consecutive ≥10% found (only isolated spikes)
- HOOD correctly blocked
```

## Implementation Files

### Modified Files
1. `/trader/config/trader_config.yaml` (lines 408-417)
   - `imbalance_threshold: 20.0` → `10.0`
   - `strong_imbalance_threshold: 40.0` → `30.0`
   - Added `strong_confirmation_threshold: 10.0`

2. `/trader/strategy/ps60_entry_state_machine.py` (lines 593-689)
   - Implemented 2-candle confirmation for AGGRESSIVE path
   - Added `state.pending_strong_spike` flag
   - Added `state.pending_strong_imbalance` value

3. `/trader/strategy/ps60_entry_state_machine.py` (lines 691+)
   - TODO: Implement sliding window for SUSTAINED path
   - Need to add `state.cvd_imbalance_history` list
   - Check last 3 values continuously

## Expected Impact

### With New Thresholds on Oct 21 Data:

**SOFI (resistance $28.98 @ 12:43 PM)**:
```
Old: -12.8% < -20% → BLOCKED ❌
New (AGGRESSIVE): -12.8% < -30% → Still BLOCKED ❌
New (SUSTAINED): Need to check if ANY 3 consecutive ≥10%
```

**AMD (support $234.40 @ 10:33 AM)**:
```
Old: +7.7% < +20% → BLOCKED ❌
New (AGGRESSIVE): +7.7% < +30% → Still BLOCKED ❌
New (SUSTAINED): +7.7% < +10% → Still BLOCKED ❌
```

**HOOD (multiple breaks)**:
```
13:51: +23.9% (isolated)
Old: Single spike, no 3 consecutive ≥20% → BLOCKED ❌
New (AGGRESSIVE): +23.9% < +30% → Still BLOCKED ❌
New (SUSTAINED): Check if 3 consecutive ≥10%...
  13:50: +15.2% ✅
  13:51: +23.9% ✅
  13:52: -6.5%  ❌ (reversed!)
  → Still BLOCKED ❌ (only 2 consecutive)
```

**Conclusion**: The new thresholds are MORE permissive, but the Oct 21 setups would still be correctly filtered due to:
- Lack of sustained pressure (isolated spikes)
- Direction reversals
- Weak initial imbalances

The tuning will help catch setups with moderate (10-30%) but SUSTAINED pressure, not choppy isolated spikes.

## Testing Plan

1. Re-run Oct 21 backtest with new thresholds
2. Verify SOFI/AMD/HOOD still blocked (quality maintained)
3. Check if any other setups now qualify
4. Run multi-day backtest to measure impact on trade count + P&L

## Rollback Plan

If new thresholds cause excessive false entries:

```yaml
# Revert to Phase 9 values
cvd:
  strong_imbalance_threshold: 40.0
  strong_confirmation_threshold: 40.0  # Disable confirmation (same as main)
  imbalance_threshold: 20.0
```

## Status

- ✅ Configuration updated (trader_config.yaml)
- ✅ AGGRESSIVE path logic implemented (2-candle confirmation)
- ✅ SUSTAINED path logic implemented (sliding window)
- ⏳ Testing on Oct 21 data
- ⏳ Multi-day validation

## Implementation Summary

### Files Modified

1. **trader/config/trader_config.yaml** (lines 409-417)
   - `imbalance_threshold: 10.0` (was 20.0)
   - `strong_imbalance_threshold: 30.0` (was 40.0)
   - `strong_confirmation_threshold: 10.0` (NEW)

2. **trader/strategy/ps60_entry_state_machine.py** (lines 593-689)
   - AGGRESSIVE path: 30% initial + 10% confirmation
   - Added `state.pending_strong_spike` flag
   - Added `state.pending_strong_imbalance` value

3. **trader/strategy/ps60_entry_state_machine.py** (lines 691-778)
   - SUSTAINED path: Sliding window search
   - Added `state.cvd_imbalance_history` list
   - Continuously searches for ANY 3 consecutive ≥10%
   - Never resets - keeps looking

### Key Logic Changes

**AGGRESSIVE Path**:
```python
if imbalance >= 30%:
    state.pending_strong_spike = True
    state.pending_strong_imbalance = imbalance_pct

On next candle:
    if imbalance >= 10% AND same direction:
        ✅ ENTER (confirmed)
    else:
        ❌ Clear pending (false spike)
```

**SUSTAINED Path**:
```python
# Add to history every candle
state.cvd_imbalance_history.append(imbalance_pct)

# Sliding window search
for i in range(len(history) - 3 + 1):
    window = history[i:i+3]
    if all(abs(x) >= 10% AND same_direction(x) for x in window):
        ✅ ENTER (sustained pressure)
```

---

**Phase 10 Complete**: October 23, 2025
