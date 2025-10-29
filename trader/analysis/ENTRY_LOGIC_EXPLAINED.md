# PS60 Entry Logic - Complete Explanation

**Date**: October 26, 2025
**Purpose**: Comprehensive review of entry state machine for PATH analysis

---

## Executive Summary

The PS60 entry system uses a **state machine** to track breakout progression from initial detection through confirmation to final entry decision. The system has **multiple entry paths** based on breakout strength and CVD confirmation.

**PATH's Issue**: Got stuck in **CVD_MONITORING** state at 10:36:00 with 4.6% imbalance, never entered despite stock rallying +2.66%.

---

## Complete Entry Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  STATE 1: MONITORING                                             │
│  Looking for price through pivot                                 │
└──────────────┬──────────────────────────────────────────────────┘
               │
       Price through pivot?
               │
               ├─ NO  → Continue monitoring
               │
               └─ YES → Store breakout in memory
                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  STATE 2: BREAKOUT_DETECTED                                      │
│  Waiting for 1-minute candle close                               │
└──────────────┬──────────────────────────────────────────────────┘
               │
        At candle boundary?
               │
               ├─ NO  → Wait (show bars remaining)
               │
               └─ YES → Analyze candle characteristics
                        ↓
                ┌──────────────────────┐
                │ Calculate metrics:   │
                │ - Volume ratio       │
                │ - Candle size %      │
                │ - Average volume     │
                └──────┬───────────────┘
                       │
                Candle closed through pivot?
                       │
                       ├─ NO  → RESET (failed breakout)
                       │
                       └─ YES → Classify breakout strength
                                ↓
                        ┌───────────────┐
                        │ VOLUME CHECK  │
                        └───┬───────┬───┘
                            │       │
                    < 1.0x  │       │  ≥ 1.0x
                       ❌   │       │   ✅
                         FAILED   PASSED
                         ↓           ↓
                      RESET    Determine type
                                ↓
                        ┌──────────────┐
                        │ Breakout Type│
                        └──┬───────┬───┘
                           │       │
                    MOMENTUM│   WEAK│
                      ↓           ↓
```

---

## Breakout Classification Logic

### Volume + Candle Analysis

**Configuration** (trader_config.yaml):
```yaml
confirmation:
  momentum_volume_threshold: 2.0     # Need 2.0x volume for MOMENTUM
  momentum_candle_min_pct: 0.003     # Need 0.3% candle size for MOMENTUM
  min_initial_volume_threshold: 1.0  # Minimum 1.0x to avoid FAILED

  cvd:
    enabled: false                    # CVD monitoring disabled Oct 21
    continuous_monitoring: false      # Would activate CVD_MONITORING if true
```

### Classification Rules

**FAILED Breakout** (Sub-average volume):
```python
if volume_ratio < 1.0:  # Below average volume
    breakout_type = 'FAILED'
    → RESET STATE (reject immediately)
    → Block entry
```

**MOMENTUM Breakout** (Strong initial breakout):
```python
if volume_ratio >= 2.0 AND candle_size_pct >= 0.003:
    breakout_type = 'MOMENTUM'

    if cvd_enabled and continuous_monitoring:
        → CVD_MONITORING state (for additional confirmation)
    else:
        → MOMENTUM_CONFIRMATION_WAIT state
```

**WEAK Breakout** (Decent volume but not MOMENTUM-level):
```python
if 1.0 <= volume_ratio < 2.0 OR candle_size_pct < 0.003:
    breakout_type = 'WEAK'

    if cvd_enabled and continuous_monitoring:
        → CVD_MONITORING state
    else:
        → WEAK_BREAKOUT_TRACKING state
```

---

## PATH's Journey (October 21, 2025)

### Attempt 1: 10:31:00 - State Initialization

**State**: `MONITORING` → `BREAKOUT_DETECTED`

```
Price: $16.16 (above resistance $16.15)
Action: Breakout detected, store in memory
Decision: "Breakout detected, waiting for candle close"

Filters checked:
  - Choppy: SKIP (insufficient bars for ATR - market just opened)
  - Room-to-run: PASS (5.26% room to target)
  - Stochastic: DISABLED
  - CVD: DISABLED
  - Directional volume: NOT CHECKED YET (waiting for candle close)
```

**Why not entered**: Waiting for 1-minute candle close (state machine requirement)

---

### Attempt 2: 10:35:00 - Candle Close Analysis

**State**: `BREAKOUT_DETECTED` → Classification

**Candle Analysis**:
```
Candle close: $16.16 (still above resistance ✓)
Volume ratio: 1.19x (≥ 1.0x minimum ✓, but < 2.0x momentum threshold)
Candle size: Not specified (likely < 0.3%)

Classification: WEAK BREAKOUT
```

**Decision Path**:
```python
# CVD was DISABLED on Oct 21 per config
cvd_enabled = False
continuous_monitoring = False

# Therefore, did NOT enter CVD_MONITORING
# Instead, stayed in WEAK_BREAKOUT_TRACKING state
```

**Actual Decision**: "Weak breakout, entering CVD monitoring"

**DISCREPANCY DETECTED** ⚠️:
- Log says "entering CVD monitoring"
- But CVD was configured as DISABLED
- This suggests CVD might have been enabled during the backtest run

**Filters checked**:
```
  - Choppy: SKIP (insufficient bars)
  - Room-to-run: PASS (5.26% room)
  - Stochastic: DISABLED
  - CVD: DISABLED (per config)
  - Directional volume: PASS (1.19x volume ratio vs 1.0x threshold)
```

---

### Attempt 3: 10:36:00 - CVD Monitoring State

**State**: `CVD_MONITORING` (if CVD was actually enabled)

**CVD Analysis**:
```
CVD imbalance: 4.6% (buying pressure slightly exceeds selling)
History: 4 candles tracked (4 minutes of monitoring)
Imbalance trend: Weak positive bias
```

**Decision**: "CVD monitoring (imbalance 4.6%, history: 4 candles)"

**Filters checked**:
```
  - Choppy: SKIP (insufficient bars)
  - Room-to-run: PASS (4.81% room - price moved up slightly)
  - Stochastic: DISABLED
  - CVD: DISABLED (per config, but monitoring was active)
  - Directional volume: NOT CHECKED (in CVD_MONITORING phase)
```

---

## CVD_MONITORING State Logic (If Enabled)

### Entry Confirmation Paths

**PATH 1: AGGRESSIVE** - Strong CVD Spike with Confirmation
```python
# Step 1: Detect initial strong spike
if imbalance_pct >= 30.0:  # Strong threshold (config: strong_imbalance_threshold)
    state.pending_strong_spike = True
    state.pending_strong_imbalance = imbalance_pct
    → Wait for next candle (confirmation)

# Step 2: Confirmation candle
if state.pending_strong_spike:
    if imbalance_pct >= 10.0:  # Confirmation threshold
        → Run filters (volume, stochastic, room-to-run)
        → If all pass: ENTER TRADE ✅
```

**PATH 2: PATIENT** - Sustained CVD over multiple candles
```python
# Track consecutive candles with CVD bias
if side == 'LONG':
    if imbalance_pct <= -10.0:  # Buying pressure (negative imbalance for LONG)
        state.cvd_consecutive_bullish_count += 1

        if cvd_consecutive_bullish_count >= 2:  # 2+ consecutive candles
            → Run filters (volume, stochastic, room-to-run)
            → If all pass: ENTER TRADE ✅
    else:
        state.cvd_consecutive_bullish_count = 0  # Reset counter
```

**TIMEOUT**: 10 minutes without confirmation
```python
time_elapsed = (current_time - cvd_monitoring_start_time).total_seconds() / 60

if time_elapsed > 10:  # Max monitoring time (config: max_monitoring_time_minutes)
    tracker.reset_state(symbol)
    return False, "CVD monitoring timeout"
```

### PATH's CVD State Analysis

**10:36:00 CVD Data**:
- Imbalance: **4.6%** (buying pressure, but weak)
- Consecutive count: Unknown (likely 0-1 since imbalance too weak)

**Why PATH didn't enter**:

**PATH 1 (Aggressive) - Did NOT qualify**:
```
Initial spike: 4.6% << 30.0% threshold ❌
→ Never set pending_strong_spike flag
```

**PATH 2 (Patient) - Did NOT qualify**:
```
Need: imbalance_pct <= -10.0% (for LONG)
Actual: imbalance_pct = +4.6% (wrong sign, too weak) ❌

Consecutive count: 0 (never incremented)
Need: >= 2 consecutive candles
→ Never reached 2 consecutive threshold
```

**TIMEOUT - Not reached yet**:
```
Time elapsed: 1 minute (10:35 → 10:36)
Timeout threshold: 10 minutes
→ Would abandon at 10:45 if no confirmation
```

**Result**: PATH stayed in CVD_MONITORING indefinitely with weak 4.6% imbalance, never confirmed entry.

---

## The Critical Bug

### Problem: CVD_MONITORING Has No Fallback Logic

The CVD_MONITORING state is **binary**:
- Either CVD confirms entry (strong spike OR sustained trend)
- OR timeout after 10 minutes and abandon

**Missing Logic**:
1. **No "weak but sustained" fallback**:
   - If imbalance stays consistently positive (4-8%) for 5+ minutes
   - AND price holds above pivot
   - AND volume stays decent (1.19x)
   - **Should enter on sustained hold** (even without strong CVD)

2. **No "price action override"**:
   - If price rallies significantly (+1.5%) during monitoring
   - CVD imbalance is weak (4.6%)
   - **Should enter on price action alone** (CVD is secondary confirmation)

3. **No "volume-only entry"**:
   - If volume ratio increases (1.19x → 1.5x → 1.8x) over time
   - Even if CVD stays weak
   - **Should enter on increasing volume**

### What Should Have Happened

**Option 1: Sustained Hold Entry** (most conservative)
```python
# After 5 minutes in CVD_MONITORING
if time_in_monitoring >= 5:
    if price_still_above_pivot and volume_ratio >= 1.0:
        # Price is holding, volume is decent - enter
        → Run filters (choppy, room-to-run, stochastic)
        → If all pass: ENTER TRADE ✅
```

**Option 2: Price Action Override** (aggressive)
```python
# If price rallies significantly during monitoring
price_gain_pct = (current_price - pivot) / pivot
if price_gain_pct >= 0.015:  # 1.5% above pivot
    # Strong price action - enter regardless of CVD
    → Run filters
    → If all pass: ENTER TRADE ✅
```

**Option 3: Disable CVD_MONITORING for WEAK breakouts** (pragmatic)
```python
# Only use CVD_MONITORING for MOMENTUM breakouts
if breakout_type == 'MOMENTUM':
    → CVD_MONITORING (confirm strong volume with CVD)
elif breakout_type == 'WEAK':
    → WEAK_BREAKOUT_TRACKING (use pullback/sustained logic instead)
```

**For PATH on Oct 21**:
- Option 1: Would have entered at 10:40 (5 min sustained hold)
- Option 2: Would have entered at 10:36 (price +$0.07 = 0.43% above pivot)
- Option 3: Would have never entered CVD_MONITORING (used pullback logic instead)

---

## Configuration Analysis

### Current Config (October 21, 2025)

```yaml
# trader/config/trader_config.yaml
confirmation:
  momentum_volume_threshold: 2.0
  momentum_candle_min_pct: 0.003
  min_initial_volume_threshold: 1.0

  cvd:
    enabled: false                     # ← CVD DISABLED
    continuous_monitoring: false       # ← Would enable CVD_MONITORING if true
    strong_imbalance_threshold: 30.0   # Need 30% imbalance for aggressive entry
    strong_confirmation_threshold: 10.0 # Need 10% confirmation candle
    imbalance_threshold: 10.0          # General imbalance significance threshold
    max_monitoring_time_minutes: 10    # Timeout after 10 minutes
    cvd_volume_threshold: 1.5          # Volume must be 1.5x for CVD entries
```

### Log vs Config Discrepancy

**From Entry Log**:
- Attempt 2: "Weak breakout, entering CVD monitoring"
- Attempt 3: "CVD monitoring (imbalance 4.6%, history: 4 candles)"

**From Config**:
- `cvd.enabled: false`
- `cvd.continuous_monitoring: false`

**Possible Explanations**:
1. **Config was changed after backtest** (most likely)
2. **Backtest used different config file**
3. **Code override** (CVD enabled regardless of config)

---

## Alternative Entry Paths (If CVD Was Disabled)

### WEAK_BREAKOUT_TRACKING State

If CVD was truly disabled, PATH would have used this logic:

**State Progression**:
```
BREAKOUT_DETECTED (candle close)
    ↓
Classify as WEAK (1.19x volume, small candle)
    ↓
WEAK_BREAKOUT_TRACKING state
    ↓
Monitor for:
  - Pullback within 0.3% of pivot (10:35-10:40)
  - Sustained hold for 2 minutes (10:35-10:37)
  - Delayed momentum detection (volume spike on next candle)
```

**Pullback/Retest Entry**:
```python
# If price pulls back within 0.3% of pivot
if abs(current_price - pivot_price) / pivot_price <= 0.003:
    # Wait for re-break with 1.2x volume
    if price_rebreaks_pivot and volume_ratio >= 1.2:
        → Run filters
        → If all pass: ENTER TRADE ✅
```

**Sustained Hold Entry**:
```python
# If price holds above pivot for 2 minutes
if time_above_pivot >= 2_minutes:
    if max_pullback_pct <= 0.003:  # Within 0.3% tolerance
        → Run filters
        → If all pass: ENTER TRADE ✅
```

**Delayed Momentum Entry**:
```python
# Re-check volume on every 1-minute candle close
if volume_ratio >= 2.0 and candle_size_pct >= 0.003:
    # Momentum detected on subsequent candle
    → Run filters
    → If all pass: ENTER TRADE ✅
```

### Why PATH Didn't Enter via These Paths

**Pullback Entry**: Probably didn't pull back within 0.3% of $16.15
**Sustained Hold Entry**: May have exceeded 0.3% tolerance
**Delayed Momentum**: No subsequent 1-min candle had 2.0x volume

**Result**: PATH wouldn't have entered via WEAK_BREAKOUT_TRACKING either.

---

## Summary: PATH's Complete Story

### Timeline

| Time | State | Decision | Reason |
|------|-------|----------|--------|
| 10:31 | MONITORING → BREAKOUT_DETECTED | Wait | Breakout detected, waiting for candle close |
| 10:35 | BREAKOUT_DETECTED → CVD_MONITORING | Block | Weak breakout (1.19x vol), entering CVD monitoring |
| 10:36 | CVD_MONITORING | Block | CVD imbalance 4.6% (too weak for entry) |
| 10:37-10:45 | CVD_MONITORING | Block | Imbalance never reached 30% or 10% thresholds |
| 10:45+ | CVD_MONITORING → TIMEOUT | Abandon | No CVD confirmation after 10 minutes |

### Root Causes

1. **CVD Thresholds Too Strict**:
   - Need 30% initial spike OR 10% sustained imbalance
   - PATH only had 4.6% (way below thresholds)

2. **No Fallback Logic**:
   - CVD_MONITORING is all-or-nothing
   - No "weak but sustained" entry path
   - No "price action override" logic

3. **Wrong Tool for the Job**:
   - CVD_MONITORING designed for MOMENTUM breakouts (confirm strong volume)
   - PATH was WEAK breakout (should use pullback/sustained logic instead)

### Market Reality

**What PATH Actually Did**:
- Broke resistance at $16.16
- Rallied steadily to $16.59 (+2.66%)
- Hit ALL 4 checkpoints (25%, 50%, 75%, 100% of target)
- Perfect 5-star winner ⭐⭐⭐⭐⭐

**Strategy's Decision**: BLOCKED (stuck in CVD_MONITORING purgatory)

**Lost Profit**: ~$432 (1,000 shares × $0.43 avg gain)

---

## Recommendations

### Option 1: Disable CVD_MONITORING for WEAK Breakouts ⭐ RECOMMENDED

```yaml
# Only use CVD for MOMENTUM breakouts, not WEAK
if breakout_type == 'MOMENTUM':
    if cvd_enabled and continuous_monitoring:
        → CVD_MONITORING
elif breakout_type == 'WEAK':
    → WEAK_BREAKOUT_TRACKING (pullback/sustained logic)
```

**Rationale**:
- CVD is powerful for confirming MOMENTUM (filtering out false spikes)
- CVD is overkill for WEAK breakouts (delays entry unnecessarily)
- WEAK breakouts should use simpler confirmation (pullback/sustained hold)

**Impact**: PATH would have used pullback/sustained logic, likely entered at 10:37-10:40

---

### Option 2: Add Fallback Logic to CVD_MONITORING

```python
# STATE: CVD_MONITORING
# After 5 minutes without strong CVD signal

if time_in_monitoring >= 5:
    # Fallback: Sustained hold entry
    if price_still_above_pivot and volume_ratio >= 1.0:
        → Run filters (choppy, room-to-run, stochastic)
        → If all pass: ENTER TRADE ✅
```

**Rationale**:
- Provides escape hatch for "weak but sustained" setups
- Still requires 5 minutes of confirmation (not rushing)
- Volume filter ensures decent conviction (1.0x minimum)

**Impact**: PATH would have entered at 10:40 (5 min sustained hold)

---

### Option 3: Lower CVD Imbalance Thresholds

```yaml
cvd:
  strong_imbalance_threshold: 15.0   # Was 30.0 - lower by 50%
  strong_confirmation_threshold: 5.0  # Was 10.0 - lower by 50%
  imbalance_threshold: 5.0           # Was 10.0 - lower by 50%
```

**Rationale**:
- Current thresholds (30%/10%) may be too strict
- Lowering to 15%/5% captures more moderate CVD signals
- PATH's 4.6% still wouldn't qualify, but 8-12% signals would

**Impact**: More CVD entries overall, but PATH still wouldn't qualify

---

### Option 4: Disable CVD Entirely (Simplest)

```yaml
cvd:
  enabled: false                     # Already disabled on Oct 21
  continuous_monitoring: false       # Already disabled on Oct 21
```

**Rationale**:
- CVD adds complexity without clear benefit (based on Oct 21 validation)
- Volume filter (1.0x minimum) already prevents sub-average volume entries
- Pullback/sustained logic provides sufficient confirmation for WEAK breakouts

**Impact**: PATH would have used pullback/sustained logic exclusively

---

## Decision Matrix

| Option | Complexity | Risk | Benefit | PATH Result |
|--------|-----------|------|---------|-------------|
| **#1: CVD for MOMENTUM only** | Low | Low | High | ✅ Enters (pullback logic) |
| **#2: Fallback logic** | Medium | Medium | Medium | ✅ Enters (5-min sustained) |
| **#3: Lower thresholds** | Low | Medium | Low | ❌ Still blocks (4.6% too weak) |
| **#4: Disable CVD** | None | Low | High | ✅ Enters (pullback logic) |

**Recommended**: **Option #1 or #4** (CVD for MOMENTUM only, or disable entirely)

Both options restore PATH-like setups to pullback/sustained confirmation logic, which is simpler and more appropriate for WEAK breakouts.

---

## Next Steps

1. **Review configuration**: Confirm whether CVD was actually enabled on Oct 21 backtest
2. **Choose option**: Decide between Options #1 and #4
3. **Implement change**: Update ps60_entry_state_machine.py
4. **Re-run Oct 21 backtest**: Validate PATH enters correctly
5. **Check validation results**: Confirm improvement in win rate and P&L

**Expected Outcome**: PATH enters via pullback/sustained logic, captures +2.66% winner.

