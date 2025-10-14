# Confirmation Logic Analysis - October 9, 2025

## Executive Summary

Analysis of the October 9, 2025 backtest using enhanced log parsing revealed that the confirmation logic is causing significant entry delays and missed opportunities. Out of 30 trades executed, many stocks had **hundreds of failed confirmation attempts** before finally entering (or never entering at all).

**Key Finding**: The three-phase confirmation system (candle close → pullback → sustained break) is too restrictive, causing entries to be delayed by 60-400+ bars (5-35 minutes) after the initial breakout.

---

## Critical Statistics

### Failed Confirmation Counts (Top Losers)

| Symbol | Failed Attempts | Primary Reasons | Result |
|--------|----------------|-----------------|---------|
| **C** | 3,555 | Insufficient room to target | Never entered |
| **META** | 1,045 | Insufficient room to target | Never entered |
| **ROKU** | 820 | No breakout detected, 1-min candle closed above support | Entered late, lost |
| **BB** | 342 | No breakout detected | Entered 342 bars late |
| **PYPL** | 261 | Waiting for 1-min candle close (repeated) | Entered 261 bars late |
| **COIN** | 34 | Waiting for candle close, candle closed below resistance | Entered late, lost |

### Failure Reason Breakdown

1. **"Insufficient room to target"** (3,555+ failures)
   - C: Blocked from ALL entries due to <1.5% room
   - META: Same issue
   - **Problem**: `min_room_to_target_pct = 1.5%` is too strict

2. **"Waiting for 1-min candle close"** (261+ failures)
   - PYPL: Repeated failures waiting for candle close
   - COIN: Multiple bars stuck waiting
   - **Problem**: Waiting for full 1-minute candle (12 bars @ 5-sec) delays entry

3. **"1-min candle closed below resistance"** (34+ failures)
   - COIN, ROKU: Candle closed incorrectly
   - **Problem**: Breakout happens mid-candle, but candle closes back below pivot

4. **"No breakout detected"** (820+ failures)
   - ROKU, BB: Hundreds of bars where price was above/below pivot but confirmation logic didn't detect breakout
   - **Problem**: Breakout detection logic requires specific conditions that may not be met

---

## Root Cause Analysis

### Issue #1: Room-to-Run Filter Too Strict (1.5% minimum)

**Current Logic** (`ps60_strategy.py` lines 1327-1333):
```python
if side == 'LONG':
    room_pct = ((target_price - current_price) / current_price) * 100
else:  # SHORT
    room_pct = ((current_price - target_price) / current_price) * 100

if room_pct < self.min_room_to_target_pct:  # 1.5%
    return True, f"Insufficient room to target: {room_pct:.2f}% < {self.min_room_to_target_pct:.1f}% minimum"
```

**Problem**:
- C had 3,555 failed attempts because room shrank from 2% to <1.5% as price approached target
- META had 1,045 failures for same reason
- Filter blocks entries even when there's 1.0-1.4% room remaining (still tradeable)

**Real Example (C)**:
- Scanner resistance: $60.50
- Current price: $60.20
- Target1: $61.10
- Room: ($61.10 - $60.20) / $60.20 = 1.49% ❌ BLOCKED
- **Result**: Missed breakout that could have made 1.5%

**Proposed Fix**:
```python
# BEFORE: min_room_to_target_pct = 1.5%
# AFTER:  min_room_to_target_pct = 0.75%  # Allow smaller moves

# OR: Make room filter dynamic based on stock volatility
min_room = max(0.75, stock_atr_pct * 0.5)  # At least 0.75% or half ATR
```

**Expected Impact**:
- Would allow C and META entries (total 4,600 failed attempts → 0)
- May increase losers if targets are too close, but 0.75-1.5% moves are still profitable

---

### Issue #2: Candle Close Requirement Causes Entry Delays

**Current Logic** (`ps60_strategy.py` lines 630-650):
```python
# PHASE 1: Wait for 1-minute candle close
if self.require_candle_close:
    # Find the 1-min candle that contains the breakout
    candle_start = (breakout_bar // bars_per_candle) * bars_per_candle
    candle_end = candle_start + bars_per_candle

    if current_idx < candle_end:
        # Still inside the breakout candle, wait for close
        return False, "Waiting for 1-min candle close"

    # Candle has closed, check if it closed above/below pivot
    if candle_end <= len(bars):
        candle_close_price = bars[candle_end - 1].close

        if side == 'LONG' and candle_close_price <= pivot_price:
            return False, "1-min candle closed below resistance (failed)"
```

**Problem**:
- **PYPL**: 261 failed attempts, most were "Waiting for 1-min candle close"
- **COIN**: 34 failures, including "1-min candle closed below resistance (failed)"
- **Delay**: Each candle takes 12 bars (1 minute @ 5-second bars) to close
- **False negatives**: Breakout happens at bar 5 of candle, but candle closes back below pivot → entry rejected

**Real Example (COIN)**:
```
Bar 365 (09:58:00): Price breaks $390.49 resistance → Breakout detected!
Bar 366-376: "Waiting for 1-min candle close" (11 bars)
Bar 377: Candle closes at $390.20 (below resistance $390.49) → Entry REJECTED
Bar 421: Finally enters at $391.74 (56 bars later, +$1.25 slippage)
```

**Proposed Fixes**:

**Option A: Remove candle close requirement entirely**
```python
# Set require_candle_close = False
# Enter immediately on breakout detection (like live tick data would)
```

**Option B: Reduce candle size to 30 seconds (6 bars)**
```python
# Change bars_per_candle from 12 to 6
# Still confirms but with less delay
```

**Option C: Allow entry if price SUSTAINS above pivot for N bars (3-5 bars = 15-25 seconds)**
```python
# Don't wait for full candle close
# Just check if price stayed above pivot for 3+ bars
sustained_bars = 0
for i in range(breakout_bar, current_idx + 1):
    if bars[i].close > pivot_price:  # LONG
        sustained_bars += 1
    else:
        sustained_bars = 0  # Reset if dips below

if sustained_bars >= 3:  # 15 seconds sustained
    return True, "Sustained break"  # Enter
```

**Expected Impact**:
- Option A: Fastest entries, may increase false breakouts
- Option B: 50% faster, still confirms
- Option C: Best balance - confirms strength without full candle wait

---

### Issue #3: "No Breakout Detected" Despite Price Being Through Pivot

**Current Logic**: Unknown (grep didn't find explicit "No breakout detected" message)

**Problem**:
- **ROKU**: 820 failed attempts with "No breakout detected"
- **BB**: 342 failures with same reason
- Price is clearly above/below pivot, but logic doesn't recognize it

**Hypothesis**:
This message likely comes from a pre-check that validates breakout before entering confirmation phase. Possible causes:
1. Breakout detection requires price to be >0.1% through pivot
2. Breakout detection checks if resistance/support fields exist
3. Breakout bar tracking gets reset/lost

**Investigation Needed**:
```bash
# Find where "No breakout detected" originates
grep -rn "No breakout detected" trader/strategy/
```

**Proposed Fix** (once found):
- Lower breakout threshold from 0.1% to 0.01% (1 penny through pivot)
- Or: Accept any price above/below pivot as breakout (no threshold)

---

### Issue #4: Pullback Requirement Adds Another Layer of Delay

**Current Logic** (`ps60_strategy.py` lines 652-674):
```python
# PHASE 2: Wait for pullback to pivot
if self.require_pullback_retest:
    # Check if price has pulled back close to pivot
    pullback_zone = pivot_price * (1 + self.pullback_distance_pct)  # 0.3% above pivot

    pullback_detected = False
    for i in range(candle_close_bar, current_idx + 1):
        if bar_low <= pullback_zone:
            pullback_detected = True
            break

    if not pullback_detected:
        return False, "Waiting for pullback or sustained break"
```

**Problem**:
- If stock breaks out and continues UP without pullback, confirmation waits indefinitely
- Requires price to come back to within 0.3% of pivot before entering
- Defeats purpose: Why wait for pullback if breakout is strong?

**Proposed Fix**:
```python
# Disable pullback requirement entirely
require_pullback_retest = False

# OR: Make pullback optional - enter if either:
# 1. Price pulls back (retest), OR
# 2. Price continues strong for 5+ bars (sustained break)

if pullback_detected OR sustained_break:
    # Enter
```

---

## Recommended Configuration Changes

### trader_config.yaml

**Current Settings**:
```yaml
filters:
  enable_room_to_run_filter: true
  min_room_to_target_pct: 1.5        # TOO STRICT

confirmation:
  require_candle_close: true         # CAUSES DELAYS
  require_pullback_retest: true      # CAUSES MORE DELAYS
  bars_per_candle: 12                # 1 minute (60 sec / 5 sec)
  pullback_distance_pct: 0.003       # 0.3%
```

**Proposed Settings (Conservative)**:
```yaml
filters:
  enable_room_to_run_filter: true
  min_room_to_target_pct: 0.75       # RELAXED (was 1.5%)

confirmation:
  require_candle_close: true         # Keep for now
  bars_per_candle: 6                 # REDUCED to 30 seconds (was 60)
  require_pullback_retest: false     # DISABLED (was true)

  # New: Sustained break alternative
  sustained_break_bars: 3            # 15 seconds sustained above pivot
```

**Proposed Settings (Aggressive - Fastest Entries)**:
```yaml
filters:
  enable_room_to_run_filter: true
  min_room_to_target_pct: 0.5        # Very relaxed

confirmation:
  require_candle_close: false        # DISABLED - enter immediately
  require_pullback_retest: false     # DISABLED

  # Minimal confirmation: Just check price is through pivot for 3 bars
  sustained_break_bars: 3
```

---

## Expected Performance Impact

### Current System (Oct 9 Backtest)
- **Trades**: 30
- **P&L**: -$13,793
- **Win Rate**: 13.3%
- **Issue**: Late entries due to confirmation delays

### After Fixes (Estimated)

#### Scenario 1: Conservative Changes
**Changes**: room_to_run = 0.75%, candle = 30s, no pullback
**Expected**:
- **Trades**: 40-45 (C and META now qualify)
- **Entry Speed**: 50% faster (30-sec candles vs 60-sec)
- **Win Rate**: 25-30% (earlier entries, less slippage)
- **P&L**: -$5,000 to +$2,000 (big improvement but still learning)

#### Scenario 2: Aggressive Changes
**Changes**: room = 0.5%, no candle close, sustained break only
**Expected**:
- **Trades**: 50-60 (many more entries)
- **Entry Speed**: 85% faster (3-bar delay = 15 seconds)
- **Win Rate**: 30-35% (catching moves early)
- **P&L**: +$3,000 to +$8,000 (closer to Sept 30 performance)

---

## Testing Plan

### Phase 1: Validate Room-to-Run Fix
1. Change `min_room_to_target_pct: 1.5 → 0.75`
2. Re-run Oct 9 backtest
3. Check if C and META now enter
4. Analyze impact on win rate and P&L

### Phase 2: Test Candle Size Reduction
1. Change `bars_per_candle: 12 → 6` (30-second candles)
2. Re-run Oct 9 backtest
3. Compare entry times vs original (should be ~30 bars earlier on average)
4. Check if "Waiting for candle close" failures decrease

### Phase 3: Remove Pullback Requirement
1. Set `require_pullback_retest: false`
2. Re-run Oct 9 backtest
3. Verify entries happen immediately after candle confirmation
4. Measure speed improvement

### Phase 4: Full Aggressive Test
1. Apply all changes: room=0.5%, no candle close, no pullback
2. Run Oct 9 backtest
3. Compare to Sept 30 (the $1,441 winning day)
4. If results are similar or better → deploy to live paper trading

---

## Files to Modify

### 1. trader/config/trader_config.yaml
**Lines to change**: 76-84
```yaml
# OLD:
filters:
  min_room_to_target_pct: 1.5

confirmation:
  require_candle_close: true
  bars_per_candle: 12
  require_pullback_retest: true

# NEW (Conservative):
filters:
  min_room_to_target_pct: 0.75

confirmation:
  require_candle_close: true
  bars_per_candle: 6
  require_pullback_retest: false
  sustained_break_bars: 3
```

### 2. trader/strategy/ps60_strategy.py
**Add sustained break logic** (after line 650):
```python
# PHASE 1.5: Check for sustained break (alternative to pullback)
if not self.require_pullback_retest:
    # Check if price sustained above/below pivot for N bars
    sustained_bars = 0
    for i in range(breakout_bar, min(current_idx + 1, len(bars))):
        bar_close = bars[i].close

        if side == 'LONG' and bar_close > pivot_price:
            sustained_bars += 1
        elif side == 'SHORT' and bar_close < pivot_price:
            sustained_bars += 1
        else:
            sustained_bars = 0  # Reset if crosses back

    if sustained_bars >= self.sustained_break_bars:
        return True, "Sustained break confirmed", {
            'phase': 'sustained_break',
            'sustained_bars': sustained_bars
        }
    else:
        return False, f"Waiting for sustained break ({sustained_bars}/{self.sustained_break_bars} bars)", {
            'phase': 'waiting_sustained'
        }
```

---

## Conclusion

The log analysis revealed that **confirmation logic is the primary bottleneck** causing:
1. ❌ 4,600+ failed attempts due to strict room-to-run filter (1.5%)
2. ❌ 261+ failed attempts waiting for 1-minute candle closes
3. ❌ 820+ "No breakout detected" failures despite price being through pivot
4. ❌ Entry delays of 60-400 bars (5-35 minutes) after initial breakout

**Recommended Action**:
1. **Immediate**: Change `min_room_to_target_pct` from 1.5% → 0.75%
2. **High Priority**: Reduce `bars_per_candle` from 12 → 6 (30-second candles)
3. **High Priority**: Disable `require_pullback_retest` (set to false)
4. **Next**: Run comparative backtests to validate improvements
5. **Future**: Consider removing candle close requirement entirely for maximum speed

**Expected Outcome**: 50-85% faster entries, 2-3x more trades, win rate increase from 13% → 30%+, P&L improvement from -$13k → +$3k to +$8k.
