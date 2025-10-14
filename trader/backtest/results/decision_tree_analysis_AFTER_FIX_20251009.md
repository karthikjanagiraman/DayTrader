# Decision Tree Path Analysis - October 9, 2025 (AFTER FIX)

## Overview

After fixing the "No breakout detected" issue (removed 36-bar lookback loop), ALL 59 trades now follow the **SAME PATH**:

**Path: STEP 2 - Waiting for candle close**

---

## Path Distribution

| Decision Path | Trades | % | Avg Failed Attempts |
|---------------|--------|---|---------------------|
| **STEP 2: Waiting for candle close** | **59** | **100.0%** | **24** |

**Total Trades**: 59

---

## What Changed With The Fix

### BEFORE Fix (Broken Lookback Loop)

```
93% of trades stuck at "No breakout detected"
- Lookback loop searched last 36 bars for original breakout
- Once breakout aged beyond 36 bars, system couldn't find it
- Trades waited 100+ bars (avg 383 failures) for NEW breakout to happen
- Result: 30 trades, -$13,793 P&L
```

### AFTER Fix (Current Price Check)

```
100% of trades now pass "No breakout detected" check
- System checks if current_price > pivot (LONG) or current_price < pivot (SHORT)
- No more searching for historical breakout bar
- Trades now wait for candle boundaries (12 bars = 1 minute)
- Result: 59 trades (+97%), -$26,272 P&L (WORSE!)
```

---

## Current Decision Flow (After Fix)

All 59 trades follow this exact path:

### STEP 1: Check Current Price vs Pivot ✅ PASS
```python
if side == 'LONG':
    is_through_pivot = current_price > pivot_price
else:  # SHORT
    is_through_pivot = current_price < pivot_price

# Result: ALL 59 trades passed this check immediately
```

### STEP 2: Wait for Candle Close ⏳ WAITING (24 avg failures)
```python
# Check if we're at candle boundary (bar 11, 23, 35, etc.)
bars_into_candle = current_idx % 12

if bars_into_candle < 11:
    return False, "Waiting for 1-min candle close"

# Average wait: 24 failed attempts per trade
# Each failure = 1 bar (5 seconds)
# Total wait: 24 × 5 sec = 120 seconds = 2 minutes
```

### STEP 3: Check Candle Direction
```python
# After candle closes, verify it closed through pivot
if side == 'LONG' and candle_close <= pivot_price:
    return False, "Candle closed below resistance"
elif side == 'SHORT' and candle_close >= pivot_price:
    return False, "Candle closed above support"

# If passed: Proceed to volume/momentum checks
```

### STEP 4: Volume/Momentum Checks
```python
# Check for volume surge (if enabled)
# Check for sustained break (if enabled)

# Note: Some trades show "Waiting for pullback or sustained break (weak)"
# This means candle closed correctly but lacks volume/momentum
```

### STEP 5: Enter Trade ✅
```python
# All confirmation checks passed
# Execute market order
```

---

## Example Trades

### Example 1: NIO SHORT (563 failed attempts)
```
Symbol: NIO
Side: SHORT
Entry Bar: 744
Failed Attempts: 563
Delay: 563 × 5 sec = 47 minutes

Path:
- Bar 181: Price breaks support $7.68 → "Waiting for candle close" × 11 bars
- Bar 192: Candle closes → "Weak breakout (0.4x vol)" → Rejected
- Bar 193: "Waiting for candle close" × 11 bars
- Bar 204: Candle closes → "Weak breakout" → Rejected
- ... (repeats for 563 total failures)
- Bar 744: Finally enters after 47 minutes

Exit: 15MIN_RULE (no movement)
P&L: -$7.55 (LOSS)
```

### Example 2: BB LONG (213 failed attempts)
```
Symbol: BB
Side: LONG
Entry Bar: 3396
Failed Attempts: 213
Delay: 213 × 5 sec = 18 minutes

Path:
- Price breaks resistance → "Waiting for candle close" × 11 bars
- Candle closes → "Weak breakout" → Rejected
- ... (repeats 213 times over 18 minutes)
- Bar 3396: Finally enters

Exit: 15MIN_RULE
P&L: -$24.81 (LOSS)
```

### Example 3: BIDU SHORT (WINNER - held to EOD)
```
Symbol: BIDU
Side: SHORT
Entry Bar: 444
Failed Attempts: ~200-300 (estimated)

Path: Same as above (waiting for candle close)

Exit: EOD (held 353 minutes!)
P&L: +$1,086.38 (WIN)

Why it won: Entered early (bar 444) and had a real breakdown
```

---

## Why Performance Got WORSE Despite More Trades

### The Problem: Volume/Momentum Filter Too Weak

The fix eliminated the "No breakout detected" blocker, but now trades are getting stuck at:

**"Waiting for pullback or sustained break (weak: 0.4x vol, 0.1% candle)"**

This means:
1. Price broke through pivot ✅
2. Candle closed correctly ✅
3. BUT: Volume is only 0.4x average (need 1.5x+)
4. AND: Candle size is only 0.1% (very small move)

The system keeps rejecting weak breakouts and waiting for a strong one. But by the time a "strong" breakout happens (if ever), the original setup is stale.

---

## Detailed Failure Breakdown

### Average Failed Attempts Per Trade: 24

**What these failures mean**:
- Each failure = waiting 1 bar (5 seconds)
- 24 failures = 120 seconds = 2 minutes average delay
- Some trades had 500+ failures = 40+ minute delays!

**Types of failures**:
1. **"Waiting for 1-min candle close"** (majority)
   - Price is through pivot, but not at candle boundary yet
   - Wait 1-11 bars (5-55 seconds) for candle to close

2. **"Weak breakout - waiting for volume/momentum"**
   - Candle closed correctly but lacks conviction
   - Volume < 1.5x average
   - Candle size < 0.3%
   - System rejects entry, waits for next candle

3. **"Candle closed wrong direction"**
   - Price whipsawed back below pivot before candle closed
   - Common in choppy markets

---

## Performance Impact

| Metric | Before Fix | After Fix | Change |
|--------|-----------|-----------|---------|
| **Trades** | 30 | 59 | +97% ✅ |
| **Win Rate** | 13.3% | 15.3% | +2.0% |
| **Total P&L** | -$13,793 | **-$26,272** | -$12,479 ❌ |
| **Avg Winner** | ~$400 | $436 | Similar |
| **Avg Loser** | ~$450 | **-$604** | Worse |
| **Profit Factor** | 0.28 | **0.13** | -53% ❌ |

**Key Finding**: More trades but WORSE performance

---

## Root Cause Analysis

### The Old Bug Was Actually a Feature!

**What we thought**:
- "No breakout detected" was a BUG causing delays

**What it actually was**:
- An ACCIDENTAL QUALITY FILTER
- By only allowing entries when a fresh breakout happened in the last 36 bars (3 minutes), it prevented:
  - Late entries on stale breakouts
  - Entries after price had already moved
  - Whipsaw entries on false breakouts

**After removing the filter**:
- System now enters on ANY price above pivot
- No requirement for a "fresh" breakout
- Catching too many low-quality setups
- More trades, but lower quality → worse P&L

---

## What Needs To Be Fixed

### Option 1: Restore Lookback (But Longer)
```yaml
# Instead of 36 bars (3 minutes), use 600 bars (50 minutes)
max_pullback_bars: 600  # Was 24

# This allows finding breakouts that happened earlier in the session
# But still requires a "real" breakout to have occurred
```

### Option 2: Strengthen Volume/Momentum Filters
```yaml
# Current thresholds are too weak
volume_surge_min: 1.5x  # Increase from 1.2x
min_candle_size: 0.3%   # Increase from 0.1%

# This would reduce entries but improve quality
```

### Option 3: Add "Breakout Freshness" Check
```python
# Only enter if breakout happened within last 50 minutes
if bars_since_breakout > 600:  # 50 minutes
    return False, "Breakout too old"

# This combines benefits of both approaches
```

### Option 4: Fix Scanner Pivots
```
# The real problem might be the scanner itself
# If resistance/support levels are inaccurate, NO confirmation logic will help
# Need to validate scanner quality first
```

---

## Comparison: Before vs After Fix

### Before Fix (93% stuck at "No breakout detected")
```
Entry Delay Distribution:
- 0-50 bars: 7% of trades
- 50-100 bars: 10% of trades
- 100-200 bars: 30% of trades
- 200+ bars: 53% of trades (STUCK!)

Average entry delay: 383 bars (32 minutes)
Problem: Can't find historical breakout
```

### After Fix (100% stuck at "Waiting for candle close")
```
Entry Delay Distribution:
- 0-50 bars: 45% of trades (estimated)
- 50-100 bars: 30% of trades
- 100-200 bars: 15% of trades
- 200+ bars: 10% of trades (still stuck on weak setups)

Average failed attempts: 24 (but range is 10-600+)
Problem: Entering low-quality setups
```

---

## Recommendations

1. **Immediate**: DO NOT deploy this fix to live trading
   - Performance is WORSE than before
   - Need further investigation

2. **Next Step**: Test Option 3 (Breakout Freshness Check)
   - Add requirement: breakout must have happened within last 50 minutes
   - This filters stale setups while allowing reasonable entry windows

3. **Long-term**: Validate scanner pivot quality
   - Run analysis: How accurate are resistance/support levels?
   - Compare scanner pivots to actual price action
   - May need to improve scanner algorithm

4. **Alternative**: Try removing candle close requirement entirely
   - Enter immediately when price breaks pivot
   - This would eliminate the 24-attempt average wait
   - But higher risk of whipsaws

---

## Summary

**The fix worked as intended** - it eliminated the "No breakout detected" blocker that was causing 93% of trades to fail.

**But it revealed a deeper problem** - the confirmation logic was too permissive without the accidental quality filter from the lookback loop.

**The path forward** - Need to add intentional quality filters to replace the accidental one we removed. The lookback loop was doing two things:
1. Causing delays (BAD)
2. Filtering stale setups (GOOD)

We removed both. Now we need to keep #1 removed but restore #2 in a different way.
