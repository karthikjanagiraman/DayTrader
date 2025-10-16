# CRITICAL ISSUE: Weak Pullback/Retest Entries (October 15, 2025)

## Problem Summary

Three trades entered at 12:47-12:48 PM ET via PULLBACK/RETEST strategy with **VERY WEAK** confirmation:
- GM @ $57.79
- BAC @ $52.09
- WFC @ $86.53

**Entry confirmation**: "weak initial: 1.7x vol, 0.0% candle"

##  What This Means

### PULLBACK/RETEST Logic (Hybrid Strategy)

**When it applies**:
- Initial breakout is WEAK (volume <2.0x OR small candle)
- Wait for pullback within 0.3% of pivot
- Enter on retest with 1.2x volume

**The Problem with These Entries**:

1. **Initial breakout was VERY weak**: 1.7x volume (barely above 1.2x minimum)
2. **Candle size was 0.0%**: Essentially no movement
3. **This suggests**: Stock already broke out EARLIER, pulled back, and we're chasing a weak retest

### Entry Analysis

| Symbol | Resistance | Entry | % Above | Volume | Candle | Entry Type |
|--------|-----------|-------|---------|--------|--------|------------|
| GM | $57.45 | $57.79 | +0.59% | 1.7x | 0.0% | PULLBACK/RETEST |
| BAC | $52.03 | $52.09 | +0.12% | 1.7x | 0.0% | PULLBACK/RETEST |
| WFC | $86.51 | $86.53 | +0.02% | ? | ? | PULLBACK/RETEST |

**Red Flags**:
- ❌ Entry ABOVE resistance (not at resistance)
- ❌ Very weak volume (1.7x barely above minimum 1.2x)
- ❌ Tiny candle (0.0% - no momentum)
- ❌ All three entered within 1 minute (12:47-12:48) - suggests simultaneous weak retests

### What Likely Happened

**Hypothesis**:
1. All three stocks broke resistance earlier in the day (maybe 10-11 AM)
2. They pulled back below resistance
3. At 12:47 PM, they re-crossed resistance with WEAK volume
4. PULLBACK/RETEST logic triggered entry
5. **But the real breakout already happened and failed**

## Root Cause Analysis

### Issue #1: PULLBACK/RETEST Accepts Too-Weak Retests

**Current Logic**:
```python
# pullback_volume_threshold: 1.2x
if volume_ratio >= 1.2:
    # Enter on retest
```

**Problem**: 1.2x volume is NOT sufficient confirmation
- **1.7x volume** (what these trades had) is still weak
- Should require 2.0x+ for retest, not just 1.2x

### Issue #2: No Candle Size Check on Retest

**Current Logic**: Only checks volume on retest, NOT candle size

**Problem**: **0.0% candle** = no momentum
- Price barely moved, just ticked above resistance
- Not a real breakout confirmation

### Issue #3: No "Time Since Initial Break" Check

**Missing Logic**: How long ago was the initial breakout?

**Problem**: If initial break was 2+ hours ago, retest is stale
- GM/BAC/WFC all entered at 12:47 PM (3 hours after market open)
- Initial break could have been at 10 AM (2.75 hours ago)
- Retesting old resistance = chasing failed breakouts

### Issue #4: No Check for "Already Above Resistance"

**Current Logic**: Enters if price crosses resistance

**Problem**: Entry prices were ABOVE resistance:
- GM: Entered at $57.79, resistance $57.45 (+0.59%)
- This means price was already above when retest triggered
- Not catching the breakout, catching the pullback from failed breakout

## Recommended Fixes

### Fix #1: Raise Pullback/Retest Volume Threshold

**Current**: 1.2x volume for retest
**Proposed**: 2.0x volume minimum (same as momentum breakout)

**Rationale**: If initial breakout was weak, retest must be STRONG

```yaml
confirmation:
  pullback_volume_threshold: 2.0  # Raised from 1.2
```

### Fix #2: Add Candle Size Requirement for Retest

**Proposed**: Require 0.5% minimum candle size on retest

**Rationale**: 0.0% candle = no momentum, just noise

```yaml
confirmation:
  pullback_candle_min_pct: 0.005  # NEW: 0.5% minimum candle
```

### Fix #3: Add "Max Time Since Initial Break" Filter

**Proposed**: Only allow retest within 30 minutes of initial break

**Rationale**: Old breakouts are stale, don't chase them

```yaml
confirmation:
  max_retest_time_minutes: 30  # NEW: Max 30 min since initial break
```

### Fix #4: Stricter Entry Position Check

**Proposed**: Don't enter if price is >0.3% above resistance

**Rationale**: Already missed the breakout, don't chase

```yaml
filters:
  max_entry_above_resistance: 0.003  # NEW: Max 0.3% above pivot
```

## Testing Required

### Backtest with Fixes

Run Oct 1-15 backtest with:
1. Pullback volume: 1.2x → 2.0x
2. Pullback candle min: 0% → 0.5%
3. Max retest time: None → 30 minutes
4. Max entry above resistance: None → 0.3%

**Expected Result**:
- GM/BAC/WFC on Oct 15 @ 12:47 PM would be BLOCKED
- Fewer weak retest entries
- Higher win rate on pullback/retest entries

### Manual Verification

Check IBKR historical 5-minute bars for:
1. GM: When did it first break $57.45?
2. BAC: When did it first break $52.03?
3. WFC: When did it first break $86.51?

**If first breaks were >30 minutes before 12:47 PM entry → Confirms stale retest issue**

## Impact Assessment

### Current Results (Need Data)

Check if GM/BAC/WFC from 12:47 PM entry:
- ❌ Hit stops immediately?
- ❌ Exited via 15-minute rule with minimal profit?
- ❌ Turned into losers?

**If yes → Confirms these were bad entries**

### Expected Monthly Impact (Conservative)

If these types of weak retests happen 2x per day:
- Blocked entries: ~40 per month
- Avg loss on weak retests: -$50 per trade
- **Monthly savings: $2,000**

## Implementation Priority

🚨 **HIGH PRIORITY** - These fixes should be implemented immediately:

1. ✅ Easy: Raise pullback_volume_threshold to 2.0x (1 line change)
2. ✅ Easy: Add pullback_candle_min_pct 0.5% (5 lines of code)
3. ⚠️ Medium: Add max_retest_time_minutes check (15 lines of code)
4. ⚠️ Medium: Add max_entry_above_resistance check (10 lines of code)

**Total implementation time**: ~30 minutes

## Conclusion

**Your observation was CORRECT**:
- ✅ These stocks likely broke resistance EARLIER in the day
- ✅ We entered on WEAK pullback/retests
- ✅ Volume filters are too lenient (1.2x is not enough)
- ✅ No candle size check on retests (0.0% candle allowed)
- ✅ No staleness check (old breakouts being retested)

**Next Steps**:
1. Verify with IBKR historical data (when did first breaks occur?)
2. Check current P&L on these three trades
3. Implement the four fixes above
4. Backtest Oct 1-15 with fixes
5. Monitor next trades for improvement
