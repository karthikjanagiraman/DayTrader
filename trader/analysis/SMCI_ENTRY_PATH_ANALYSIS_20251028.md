# SMCI Entry Path Analysis - October 28, 2025

**Generated**: October 28, 2025
**Symbol**: SMCI
**Total Attempts**: 4 trades
**Results**: 1 winner (+$38.33), 3 losers (-$59.02)
**Net P&L**: -$20.69

---

## Scanner Setup Data

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Symbol** | SMCI | Super Micro Computer |
| **Previous Close** | $52.10 | Oct 27 close |
| **Resistance** | $51.63 | Long breakout level |
| **Support** | $49.72 | Short breakout level |
| **Target1** | $52.59 | First profit target |
| **Target2** | $53.54 | Second profit target |
| **Target3** | $54.72 | Extended target |
| **Scanner Score** | 50 | Minimum acceptable (threshold) |
| **Risk/Reward** | 0.61 | Below 1.5:1 threshold ⚠️ |
| **Setup** | "Strong up +7.4% \| High volatility 7.3%" | |

**Key Observations**:
- ⚠️ **Low R/R Ratio**: 0.61 is below the 1.5:1 minimum filter
- ✅ **Score**: 50 meets minimum threshold
- ⚠️ **Already Above Resistance**: Closed at $52.10, resistance at $51.63 (-0.9% "dist_to_R%")
- ⚠️ **Gap Situation**: Stock gapped up through resistance overnight

---

## Trade #1: LONG @ $53.30 (11:54:34 AM ET)

### Entry Details
- **Entry Price**: $53.30
- **Entry Time**: 11:54:34 AM ET (08:54:34 AM PST)
- **Shares**: 300 (approximate, based on typical sizing)
- **Exit**: STOP_HIT @ $53.19
- **Duration**: ~10 seconds (whipsaw)
- **P&L**: -$33.00

### Filter Analysis

#### 1. Distance from Pivot Filter ⚠️ MISSING
```python
Entry Price: $53.30
Resistance (Pivot): $51.63
Distance: $53.30 - $51.63 = $1.67
Distance %: ($1.67 / $51.63) × 100 = 3.24%

Status: ❌ TOO FAR (>1% threshold)
Recommendation: BLOCK or require 5.0x volume
```

**Issue**: Entered 3.24% above resistance - this is a LATE entry after the breakout already moved significantly.

#### 2. Room-to-Run Filter
```python
Entry Price: $53.30
Target1: $52.59 ← ALREADY PASSED! ❌
Target2: $53.54
Target3: $54.72

Room to Target2: ($53.54 - $53.30) / $53.30 = 0.45%
Room to Target3: ($54.72 - $53.30) / $53.30 = 2.66%

Status: ✅ PASS (2.66% > 1.5% minimum)
```

**Observation**: Target1 already hit before entry. Room-to-run filter passed using Target3, but this is a late entry chasing the move.

#### 3. Direction Check ✅
```python
Side: LONG
Entry Price: $53.30
Resistance: $51.63

Check: $53.30 > $51.63 ✅ PASS
```

**Status**: Correct direction (above resistance for long).

#### 4. Entry State Machine Path

Based on log patterns:
```
State 1: BREAKOUT_DETECTED
  ↓
State 2: Waiting for 1-minute candle close (12 five-second bars)
  ↓
State 3: CVD_MONITORING (classified as WEAK breakout)
  ↓
CVD Signal Detected (likely buy imbalance)
  ↓
ENTRY EXECUTED @ $53.30
```

**Entry Path**: CVD_MONITORING → CVD signal → Entry
**Breakout Type**: WEAK (did not meet momentum criteria)

#### 5. What Happened
- Stock was already $1.67 above resistance at entry
- Immediate reversal after entry (whipsaw)
- Stopped out in ~10 seconds
- **Root Cause**: Late entry, chasing the move

---

## Trade #2: LONG @ $53.21 (11:58:35 AM ET)

### Entry Details
- **Entry Price**: $53.21
- **Entry Time**: 11:58:35 AM ET (08:58:35 AM PST)
- **Shares**: 300 (approximate)
- **Exit**: STOP_HIT @ $52.97
- **Duration**: ~4 minutes
- **P&L**: -$7.14

### Filter Analysis

#### 1. Distance from Pivot Filter ⚠️ MISSING
```python
Entry Price: $53.21
Resistance (Pivot): $51.63
Distance: $53.21 - $51.63 = $1.58
Distance %: ($1.58 / $51.63) × 100 = 3.06%

Status: ❌ TOO FAR (>1% threshold)
Recommendation: BLOCK or require 5.0x volume
```

**Issue**: Still 3.06% above resistance - another late entry (2nd attempt on same symbol).

#### 2. Room-to-Run Filter
```python
Entry Price: $53.21
Target1: $52.59 ← ALREADY PASSED! ❌
Target2: $53.54
Target3: $54.72

Room to Target2: ($53.54 - $53.21) / $53.21 = 0.62%
Room to Target3: ($54.72 - $53.21) / $53.21 = 2.84%

Status: ✅ PASS (2.84% > 1.5% minimum)
```

**Observation**: Same issue - Target1 already passed, using Target3 for room-to-run calculation.

#### 3. Retry Limit Check ⚠️ MISSING
```python
SMCI Attempt #2 (same symbol, same session)

Configured Max: Unlimited (no retry limit)
Status: ❌ NO LIMIT ENFORCED

Recommendation: Max 2 attempts per symbol per session
```

**Issue**: No mechanism to prevent overtrading same symbol.

#### 4. Entry State Machine Path

```
State 1: BREAKOUT_DETECTED (price re-broke $51.63)
  ↓
State 2: Waiting for candle close
  ↓
State 3: CVD_MONITORING
  ↓
CVD Signal
  ↓
ENTRY EXECUTED @ $53.21
```

**Entry Path**: CVD_MONITORING → CVD signal → Entry (same path as Trade #1)

---

## Trade #3: LONG @ $53.26 (1:52:34 PM ET)

### Entry Details
- **Entry Price**: $53.26
- **Entry Time**: 1:52:34 PM ET (10:52:34 AM PST)
- **Shares**: 300 (approximate)
- **Exit**: 15MIN_RULE @ $53.20
- **Duration**: 15 minutes
- **P&L**: -$18.88

### Filter Analysis

#### 1. Distance from Pivot Filter ⚠️ MISSING
```python
Entry Price: $53.26
Resistance (Pivot): $51.63
Distance: $53.26 - $51.63 = $1.63
Distance %: ($1.63 / $51.63) × 100 = 3.16%

Status: ❌ TOO FAR (>1% threshold)
Recommendation: BLOCK or require 5.0x volume
```

**Issue**: THIRD attempt, still 3.16% above pivot.

#### 2. Room-to-Run Filter
```python
Entry Price: $53.26
Target1: $52.59 ← ALREADY PASSED! ❌
Target2: $53.54
Target3: $54.72

Room to Target2: ($53.54 - $53.26) / $53.26 = 0.53%
Room to Target3: ($54.72 - $53.26) / $53.26 = 2.74%

Status: ✅ PASS (2.74% > 1.5% minimum)
```

#### 3. Retry Limit Check ⚠️ MISSING
```python
SMCI Attempt #3 (same symbol, same session)

Status: ❌ NO LIMIT ENFORCED
```

#### 4. What Happened
- Price stalled after entry (no movement for 15 minutes)
- 15-minute rule triggered
- Exited with small loss
- **Root Cause**: Lack of momentum at this level, late entry

---

## Trade #4: LONG @ $53.26 (2:11:35 PM ET) ✅ WINNER

### Entry Details
- **Entry Price**: $53.26
- **Entry Time**: 2:11:35 PM ET (11:11:35 AM PST)
- **Shares**: 300 (approximate)
- **Exit**: PARTIAL @ $53.54 (TARGET2)
- **Duration**: ~20+ minutes
- **P&L**: +$38.33 ✅

### Filter Analysis

#### 1. Distance from Pivot Filter ⚠️ MISSING
```python
Entry Price: $53.26
Resistance (Pivot): $51.63
Distance: $53.26 - $51.63 = $1.63
Distance %: ($1.63 / $51.63) × 100 = 3.16%

Status: ❌ TOO FAR (>1% threshold)
BUT: This one worked! 🤔
```

**Observation**: Same late entry (3.16% above pivot) as trades #1-3, but this time it worked because momentum continued to Target2.

#### 2. Room-to-Run Filter
```python
Entry Price: $53.26
Target1: $52.59 ← ALREADY PASSED!
Target2: $53.54
Target3: $54.72

Room to Target2: ($53.54 - $53.26) / $53.26 = 0.53%
Room to Target3: ($54.72 - $53.26) / $53.26 = 2.74%

Status: ✅ PASS (2.74% > 1.5% minimum)
```

#### 3. Retry Limit Check ⚠️ MISSING
```python
SMCI Attempt #4 (same symbol, same session)

Status: ❌ NO LIMIT ENFORCED
Result: This 4th attempt was the winner!
```

**Critical Question**: Should we have been blocked after 2 failed attempts? Or does the 4th attempt prove persistence pays off?

#### 4. Why This One Worked
- Same entry price as Trade #3 ($53.26)
- Difference: Market had momentum this time
- Price pushed to Target2 ($53.54)
- Partial profit taken at +0.53%
- **Key Factor**: Market timing, not entry quality

---

## Adaptive Volume Filter - What Would Have Happened?

### Proposed Scaling Table

| Distance from Pivot | Required Volume | Status | SMCI Entries |
|---------------------|-----------------|--------|--------------|
| 0.0% - 0.5% | 2.0x (standard) | ✅ Good entry | Would allow |
| 0.5% - 1.0% | 2.5x | ⚠️ Cautious | Would allow with higher vol |
| 1.0% - 1.5% | 3.0x | ⚠️ Late | Would require strong vol |
| 1.5% - 2.0% | 4.0x | 🔴 Very late | Would require very strong vol |
| 2.0% - 3.0% | 5.0x | 🔴 Chasing | **ALL 4 SMCI entries here** |
| >3.0% | BLOCK | ❌ Too far | Would block if exceeded |

### Analysis of Each Entry with Adaptive Filter

**Trade #1: $53.30 (3.24% above pivot)**
```python
Distance: 3.24%
Required Volume: 5.0x (highest tier before block)

Actual Volume: Unknown (log doesn't show, but likely 1.0-2.0x)
Adaptive Filter Decision: ❌ BLOCK (insufficient volume for 3.24% distance)

Result if blocked: SAVED -$33.00 ✅
```

**Trade #2: $53.21 (3.06% above pivot)**
```python
Distance: 3.06%
Required Volume: 5.0x

Adaptive Filter Decision: ❌ BLOCK (likely insufficient volume)

Result if blocked: SAVED -$7.14 ✅
```

**Trade #3: $53.26 (3.16% above pivot)**
```python
Distance: 3.16%
Required Volume: 5.0x

Adaptive Filter Decision: ❌ BLOCK (likely insufficient volume)

Result if blocked: SAVED -$18.88 ✅
```

**Trade #4: $53.26 (3.16% above pivot) - THE WINNER**
```python
Distance: 3.16%
Required Volume: 5.0x

Adaptive Filter Decision: Depends on volume
  - If volume was 5.0x+: ✅ ALLOW → Keep winner +$38.33
  - If volume was <5.0x: ❌ BLOCK → Miss winner -$38.33

Critical Question: What was the actual volume ratio at entry?
```

---

## Summary of Issues Found

### Critical Bugs

| Issue | Impact | Trades Affected | Lost P&L |
|-------|--------|-----------------|----------|
| **1. No Distance-to-Pivot Filter** | Entered 3.06-3.24% above resistance | ALL 4 trades | -$20.69 net |
| **2. No Retry Limit** | Attempted same symbol 4 times | Trade #2, #3, #4 | -$22.48 (trades 2-3) |
| **3. Target1 Already Passed** | Using Target3 for room-to-run | ALL 4 trades | Inflated opportunity |

### Filter Performance

| Filter | Status | Result |
|--------|--------|--------|
| Room-to-Run | ✅ Activated | Used Target3 (2.66-2.84% room) |
| Direction Check | ✅ Activated | All entries above resistance |
| Distance-to-Pivot | ❌ MISSING | Would have blocked all 4 entries |
| Retry Limit | ❌ MISSING | Allowed 4 attempts on same symbol |
| Volume Scaling | ❌ MISSING | Would require 5.0x volume at 3%+ distance |

---

## Recommendations

### Immediate Fixes

1. **Implement Distance-to-Pivot Filter with Adaptive Scaling**
   - 0-1%: Allow with 2.0x volume
   - 1-2%: Allow with 4.0x volume
   - 2-3%: Allow with 5.0x volume
   - >3%: BLOCK entirely

2. **Add Retry Limit**
   - Max 2 attempts per symbol per session
   - Would have prevented trades #3 and #4
   - **Trade-off**: Would have missed the $38.33 winner on 4th attempt

3. **Fix Room-to-Run Logic**
   - If Target1 already passed, recalculate risk/reward
   - Consider blocking entry if first target is already hit
   - Or require exceptional volume (5.0x+) to continue

### Expected Impact

**If Adaptive Filter Applied to SMCI:**
```
Scenario 1: Block ALL 4 trades (if volume <5.0x)
  - Saved: -$59.02 (3 losers)
  - Missed: +$38.33 (1 winner)
  - Net Impact: -$20.69 (BREAK EVEN)

Scenario 2: Allow trade #4 ONLY (if it had 5.0x volume)
  - Saved: -$59.02 (3 losers)
  - Kept: +$38.33 (1 winner)
  - Net Impact: -$20.69 → +$38.33 (IMPROVEMENT: +$59.02)

Scenario 3: Block first 2, allow last 2 (if volume increased)
  - Saved: -$40.14 (trades #1-2)
  - Kept: -$18.88 + $38.33 = +$19.45 (trades #3-4)
  - Net Impact: -$20.69 (NO CHANGE)
```

**Key Insight**: Effectiveness depends on whether volume actually increased for the winning trade #4.

---

## Trade-Off Analysis

### The 4th Attempt Dilemma

**Argument FOR Retry Limit (Max 2 attempts)**:
- ✅ Prevents overtrading same symbol
- ✅ Saves capital on repeated failures
- ✅ Forces discipline
- ✅ Would have saved -$40.14 on SMCI trades #1-2

**Argument AGAINST Strict Limit**:
- ❌ Would have missed +$38.33 winner on 4th attempt
- ❌ Market conditions change throughout day
- ❌ Persistence sometimes pays off
- ❌ Late-day momentum can be different from morning

**Proposed Hybrid Solution**:
```yaml
retry_policy:
  max_attempts_per_symbol: 3  # Allow up to 3 tries

  # Increase difficulty for retries
  retry_1_volume_multiplier: 1.0  # Standard (2.0x base)
  retry_2_volume_multiplier: 1.5  # Higher bar (3.0x base)
  retry_3_volume_multiplier: 2.0  # Much higher (4.0x base)

  # Require cooling off period
  min_time_between_attempts: 900  # 15 minutes
```

**How This Would Affect SMCI**:
- Trade #1 (11:54 AM): First attempt, 2.0x volume required
- Trade #2 (11:58 AM): BLOCKED (only 4 min after trade #1, need 15 min gap)
- Trade #3 (1:52 PM): Second attempt, 3.0x volume required
- Trade #4 (2:11 PM): Third attempt, 4.0x volume required

---

## Entry State Machine Path Summary

All 4 SMCI trades followed the SAME path:

```
1. BREAKOUT_DETECTED
   ↓
2. Waiting for 1-minute candle close (12 five-second bars)
   ↓
3. CVD_MONITORING (breakout classified as WEAK, not MOMENTUM)
   ↓
4. CVD buy imbalance signal detected
   ↓
5. ENTRY EXECUTED
```

**Key Observations**:
- None met MOMENTUM criteria (would need 2.0x volume + large candle)
- All relied on CVD signals for entry confirmation
- All were 3%+ above the resistance pivot
- All happened after resistance was already broken

**Question**: Were the CVD signals reliable at 3%+ above pivot? Or were they giving false signals on late entries?

---

## Conclusions

1. **Distance-to-Pivot Filter is CRITICAL**: All 4 SMCI entries were 3%+ above resistance (late entries)
2. **Adaptive Volume Scaling is Smarter Than Blocking**: Hard block at 1% would miss potential winners
3. **Retry Limit Needs Nuance**: Max 2 attempts is too strict, max 4 is too loose, max 3 with cooling period is optimal
4. **Room-to-Run Filter Needs Enhancement**: Should flag when Target1 is already passed
5. **CVD Signals May Be Unreliable at Late Entries**: Need to validate if CVD works well >3% from pivot

**Overall SMCI Performance**: -$20.69 (3 losers + 1 winner)
**With Adaptive Filter**: Likely -$0 to +$38.33 (depending on volume ratios)

**Expected Improvement**: +$20.69 to +$59.02 per session on late-entry prevention alone.

---

**Next Step**: Implement adaptive volume filter and validate on full Oct 28 session (all 12 trades).
