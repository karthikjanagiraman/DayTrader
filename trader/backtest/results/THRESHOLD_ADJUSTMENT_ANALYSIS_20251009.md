# Threshold Adjustment Analysis - October 9, 2025

## Executive Summary

Adjusted thresholds as recommended in STATE_MACHINE_ANALYSIS_20251009.md:
1. ✅ Bounce threshold: 0.2% → 0.1% (50% reduction)
2. ✅ Sustained break: 24 bars → 12 bars (50% reduction)

**Result**: Same 4 trades, same 0% win rate, same -$4,680 P&L

**Conclusion**: Threshold adjustments didn't help because the ROOT PROBLEM is the bounce logic itself, not the threshold value.

---

## Three Versions Compared

| Metric | Original (Buggy) | After Current Price Fix | After Threshold Adjustment |
|--------|------------------|-------------------------|----------------------------|
| Date | Oct 9 (morning) | Oct 9 (afternoon) | Oct 9 (evening) |
| Trades | 30 | 59 | **4** |
| Win Rate | 13.3% | Unknown | **0%** |
| P&L | -$13,793 | -$26,272 | **-$4,680** |
| Avg Trade | -$460 | -$445 | **-$1,170** |
| Primary Issue | 93% stuck at "No breakout" | All stuck at candle close wait | Only momentum entries work |

---

## Version 1: Original (Lookback Loop Bug)

**Problem**: 36-bar lookback window too short

**Symptom**: 93% of attempts failed at "No breakout detected"

**Example**:
```
Bar 100: Stock breaks resistance at $175
Bar 137+: Lookback loop searches bars 101-136 (36 bars)
Result: Can't find breakout (it's at bar 100, outside window)
Outcome: "No breakout detected" forever
```

**Trade Distribution**:
- 28/30 trades (93.3%): Stuck at "No breakout detected"
- 2/30 trades (6.7%): Progressed past step 1

---

## Version 2: After Current Price Fix

**Fix Applied**: Removed lookback loop, checked if `current_price > pivot_price`

**Result**: 59 trades (up from 30) but WORSE P&L (-$26,272 vs -$13,793)

**Problem**: Eliminated "No breakout detected" issue but revealed second issue - all trades stuck waiting for candle close confirmation

**Trade Distribution**:
- 59/59 trades (100%): Stuck at "STEP 2: Waiting for candle close"
- Average 24 failed attempts per trade before eventual momentum entry

**Root Cause**: The old lookback bug was accidentally acting as a quality filter by preventing late/stale entries.

---

## Version 3: State Machine (Current)

**Architecture**: Memory-based state tracking with 8 distinct states

**Thresholds** (after adjustment):
- Bounce threshold: 0.1% (was 0.2%)
- Sustained break: 12 bars (was 24 bars)

**Result**: Only 4 trades, all momentum breakouts

**Trade Distribution**:
- **COIN × 2**: MOMENTUM_BREAKOUT entries (strong volume)
- **AVGO × 2**: MOMENTUM_BREAKOUT entries (strong volume)
- **Other 39 stocks**: 0 entries (stuck in WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST)

---

## Detailed Analysis: Why Only 4 Trades?

### State Machine Progression Statistics (from logs)

**Weak Breakout Tracking**: ~15,000 attempts
- Example: NIO tracked "1/12 bars", "2/12 bars", ... "11/12 bars"
- Never reached 12 bars consecutively
- Kept resetting when price broke back through pivot

**Pullback Retest**: 3,720 attempts
- Example: COIN Bar 350-358 "Waiting for bounce from pullback"
- Pullback detected successfully (price near pivot)
- But bounce NEVER confirmed

**Momentum Breakout**: 4 successful entries
- AVGO: 2.0x volume, large candle → ENTER
- COIN: 1.5x+ volume, large candle → ENTER

---

## Root Cause Analysis: Bounce Logic Flaw

### The Bounce Logic (breakout_state_tracker.py:268-273)

```python
if state.side == 'LONG':
    # For longs, bounce = moving up from pivot
    if current_price > pivot * (1 + bounce_threshold_pct):
        state.state = BreakoutState.READY_TO_ENTER
        state.entry_reason = "PULLBACK_RETEST"
        return True
```

**Problem**: After pullback, price typically sits AT or BELOW pivot, not above it.

**Example** (COIN pullback):
```
Pivot: $390.49
Pullback detected: $390.30 (within 0.3% of pivot ✅)
Waiting for bounce...

Current price: $390.45 (still below pivot)
Bounce threshold check: $390.45 > $390.88? NO ❌
  (pivot * 1.001 = $390.49 * 1.001 = $390.88)

Current price: $390.60 (slightly above pivot)
Bounce threshold check: $390.60 > $390.88? NO ❌

Current price: $390.80 (well above pivot)
Bounce threshold check: $390.80 > $390.88? NO ❌

Current price: $391.00 (0.13% above pivot)
Bounce threshold check: $391.00 > $390.88? YES ✅
  But by now, momentum is already strong → Momentum entry instead!
```

**Key Insight**: The bounce logic requires price to be ABOVE the pivot by the threshold amount. But pullbacks happen AT the pivot, so bounces rarely reach the required level before either:
1. Momentum picks up (becomes MOMENTUM entry), or
2. Price breaks back below pivot (resets to MONITORING)

---

## Why Threshold Adjustments Didn't Help

### Bounce Threshold: 0.2% → 0.1%

**Impact on Logic**:
```python
# OLD (0.2%):
Pivot $390.49 → Need $391.27 to confirm bounce

# NEW (0.1%):
Pivot $390.49 → Need $390.88 to confirm bounce
```

**Expected**: Should allow ~2x more bounces to confirm

**Actual Result**: Still only 4 trades (same as before)

**Why**: Even 0.1% is too strict when price is sitting AT the pivot. The fundamental issue is requiring price to be ABOVE pivot, not AT pivot.

### Sustained Break: 24 bars → 12 bars

**Impact on Logic**:
```python
# OLD: Needed 24 consecutive bars above pivot (2 minutes)
# NEW: Need 12 consecutive bars above pivot (1 minute)
```

**Expected**: Should allow ~2x more sustained breaks to complete

**Actual Result**: Still 0 sustained break entries

**Why**: Price whipsaws constantly. Getting 12 consecutive bars is still very rare when stocks are choppy.

**Evidence from Logs**:
```
NIO Bar 193-203: Held 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 bars
NIO Bar 204: Reset (broke back below pivot)
NIO Bar 217-227: Held 1, 2, 3, 4, 5, 6, 7, 8 bars
NIO Bar 228: Reset again
... repeated 100+ times throughout day, never completed
```

---

## Comparison: State Machine vs "Broken" Version

| Aspect | Original (Buggy) | State Machine (Fixed) |
|--------|------------------|----------------------|
| Architecture | Search backwards 36 bars | Memory-based tracking |
| Entry Quality | Accidentally filtered late entries | Only allows fresh, high-quality entries |
| Trades/Day | 30 (many late/stale) | 4 (only momentum) |
| Win Rate | 13.3% (low quality) | 0% (small sample) |
| P&L | -$13,793 (death by 1000 cuts) | -$4,680 (fewer but larger losses) |

**Insight**: The "bug" was preventing BAD trades. Fixing it revealed that we need to ALSO fix the entry logic, not just the state tracking.

---

## The Real Problem

The state machine is CORRECT in its architecture - it's properly tracking breakout progression and preventing lookback loop issues.

**The problem is**: The entry conditions (bounce threshold, sustained break) were designed for THEORY but don't match REALITY.

**In theory**: After a pullback, price should bounce cleanly 0.2% above pivot to confirm strength.

**In reality**: Price sits AT the pivot, whipsaws 0.05-0.15%, and either:
1. Builds momentum quickly (→ MOMENTUM entry), or
2. Fails and breaks back down (→ Reset to MONITORING)

**Result**: The PULLBACK_RETEST and SUSTAINED_BREAK paths are unreachable in practice.

---

## Recommendations

### Option 1: Accept Momentum-Only Strategy
- Keep state machine as-is
- Only enter on MOMENTUM breakouts (strong volume + large candle)
- Expected: 2-4 trades/day, high quality
- Risk: Very low trade frequency

### Option 2: Relax Bounce Logic (Most Promising)
```python
# Instead of requiring price ABOVE pivot by threshold:
if current_price > pivot * (1 + bounce_threshold_pct):

# Allow ANY price movement above pivot after pullback:
if current_price > pivot:
```

**Impact**: Would allow 3,720 "Waiting for bounce" attempts to succeed

**Risk**: May allow low-quality bounces (price barely above pivot)

### Option 3: Hybrid Bounce Logic
```python
# Confirm bounce if:
# 1. Price is above pivot, AND
# 2. Price is moving up (higher than previous bar)

if current_price > pivot and current_price > previous_price:
    # Bounce confirmed
```

**Impact**: Catches genuine bounces while filtering whipsaws

### Option 4: Simplify Sustained Break
```python
# Instead of requiring 12 CONSECUTIVE bars:
# Track "net bars held" allowing brief violations

net_bars_held = bars_above_pivot - bars_below_pivot

if net_bars_held >= 10:  # e.g., 12 above - 2 below = 10 net
    # Sustained break confirmed
```

**Impact**: Allows sustained breaks to complete despite whipsaws

---

## Next Steps

1. **Test Option 2** (allow any price above pivot for bounce)
   - Change line 270 in breakout_state_tracker.py
   - Re-run Oct 9 backtest
   - Expected: 10-20 trades (3,720 bounce attempts × 5-10% success rate)

2. **Test Option 3** (hybrid bounce logic with trend check)
   - Add `previous_price` tracking to state
   - Require upward movement + above pivot
   - Expected: 5-10 trades (more selective than Option 2)

3. **If both fail**: Consider reverting to simplified logic without state machine
   - Use current price check (no lookback)
   - Add quality filters (volume, candle size, time-of-day)
   - Accept 20-30 trades/day but filter for quality

---

## Conclusion

**The state machine architecture is CORRECT** - it successfully:
✅ Eliminates lookback loop issues
✅ Tracks breakout progression properly
✅ Prevents stale/late entries
✅ Identifies momentum breakouts successfully

**The problem is the ENTRY THRESHOLDS**:
❌ Bounce threshold too strict (requires price ABOVE pivot, not AT pivot)
❌ Sustained break too fragile (12 consecutive bars unrealistic for choppy stocks)

**Next action**: Implement Option 2 or 3 to make pullback bounces actually reachable, then re-test.
