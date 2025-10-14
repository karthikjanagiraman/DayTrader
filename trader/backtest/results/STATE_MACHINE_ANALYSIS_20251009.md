# State Machine Analysis - October 9, 2025

## Executive Summary

The state machine successfully tracked breakout progression BUT is getting stuck in specific states and never reaching entry.

**Key Finding**: **8,941 "Waiting for bounce from pullback"** rejections - trades are stuck waiting for pullback bounces that never happen!

---

## Overall Statistics

- **Symbols Processed**: 41
- **Symbols with Entries**: 2 (COIN, AVGO)
- **Total Trades**: 4
- **Total Rejection Attempts**: 47,000+

---

## Top Rejection Reasons (Aggregated)

| Rank | Rejection Reason | Count | % of Total |
|------|------------------|-------|------------|
| 1 | **Waiting for 1-min candle close** | **21,216** | **45%** |
| 2 | **Waiting for bounce from pullback** | **8,941** | **19%** |
| 3 | Breakout detected, waiting for candle close | 2,316 | 5% |
| 4-13 | Tracking weak breakout (held 1-10/24 bars) | ~15,000 | 32% |

---

## Problem #1: Waiting for Pullback Bounce (8,941 rejections)

**What's happening**:
1. Stock breaks pivot → State: MONITORING → BREAKOUT_DETECTED
2. Candle closes (weak volume) → State: WEAK_BREAKOUT_TRACKING
3. Price pulls back to pivot → State: PULLBACK_RETEST ✅
4. **STUCK**: Waiting for bounce, but price NEVER bounces → Stuck forever!

**Example (any of 10+ stocks)**:
```
Bar 100: Price breaks $175 resistance → BREAKOUT_DETECTED
Bar 111: Candle closes, weak volume → WEAK_BREAKOUT_TRACKING
Bar 125: Price pulls back to $174.80 (within 0.3% of pivot) → PULLBACK_RETEST
Bar 126-4680: "Waiting for bounce from pullback" × 8,941 times
  - Price is sitting at $174.80
  - Needs to bounce to $175.10 (0.2% above pivot)
  - But price just stays flat or drifts lower
  - State machine keeps waiting... forever
  - NEVER ENTERS
```

**Root Cause**: The `check_pullback_bounce()` logic requires:
```python
# For LONG
if current_price > pivot * (1 + bounce_threshold_pct):  # pivot * 1.002
    # Bounce confirmed!
```

If price pulls back to $174.80 but only bounces to $174.95 (not reaching $175.10), the bounce is NEVER confirmed.

---

## Problem #2: Tracking Weak Breakout But Never Completing (15,000+ rejections)

**What's happening**:
1. Weak breakout detected → WEAK_BREAKOUT_TRACKING
2. Tracks for sustained break (needs 24 bars = 2 minutes)
3. But resets every time it sees a new breakout or fails sustained hold check

**Example**:
```
NIO, XPEV, NVDA, LI, BIDU, AAPL, NFLX, BABA, C, LYFT (all 3,781 attempts each!)

Pattern:
- "Tracking weak breakout (held 1/24 bars)" × 101
- "Tracking weak breakout (held 2/24 bars)" × 100
- "Tracking weak breakout (held 3/24 bars)" × 99
- ...never reaches 24 bars

Why?
- Price keeps breaking back below pivot before 24 bars elapse
- Each time it breaks back, state resets to MONITORING
- Then breaks again, restarts tracking at 1/24 bars
- Infinite loop of tracking 1-10 bars, resetting, tracking again
```

**Root Cause**: The `check_sustained_hold()` logic checks if price stayed above pivot for 24 bars, but stocks keep whipsawing:
```
Bar 100-110: Above pivot (10 bars held)
Bar 111: Breaks below pivot → RESET to MONITORING
Bar 115-125: Above pivot again (start counting from 0 again)
Bar 126: Breaks below → RESET again
... repeats forever
```

---

## Problem #3: 21,216 "Waiting for 1-min candle close"

This is actually NORMAL - just waiting for candle boundaries. Not a problem.

---

## Stocks That Successfully Entered

### AVGO (2 entries)

**Entry Type**: MOMENTUM_BREAKOUT

**Path**:
```
Bar X: Price breaks pivot → BREAKOUT_DETECTED
Bar X+11: Candle closes → Analyze
  Volume: HIGH (>1.5x)
  Candle: LARGE (>0.3%)
→ MOMENTUM_BREAKOUT → ENTER IMMEDIATELY ✅
```

**Rejections before entry**: Only 3 total (minimal)
- 1 × "Breakout detected, waiting for candle close"
- 1 × "Waiting for 1-min candle close"
- 1 × (second attempt same pattern)

**Why it worked**: Strong volume + large candle = bypassed pullback/sustained logic entirely

---

### COIN (2 entries)

**Entry Type**: PULLBACK_RETEST

**Path**:
```
Bar X: Price breaks $391 → BREAKOUT_DETECTED
Bar X+11: Candle closes (weak) → WEAK_BREAKOUT_TRACKING
Bar Y: Price pulls back to $390.70 → PULLBACK_RETEST
Bar Y+5: Price bounces to $391.50 → BOUNCE CONFIRMED → ENTER ✅
```

**Rejections before entry**: 29 total
- 18 × "Waiting for bounce from pullback"
- 8 × "Waiting for 1-min candle close"
- 1 × "Weak breakout, tracking for pullback/sustained"
- 1 × "Pullback detected, waiting for bounce"
- 1 × "Breakout detected, waiting for candle close"

**Why it worked**: Price actually bounced >0.2% above pivot after pullback (rare!)

---

## Stocks That NEVER Entered (Top 10)

All have ~3,781 failed attempts (full day of checking):

| Symbol | Primary Stuck State | Count |
|--------|---------------------|-------|
| NIO | Waiting for 1-min candle close | 1,140 (30%) |
| XPEV | Waiting for 1-min candle close | 1,150 (30%) |
| NVDA | Waiting for 1-min candle close | 1,060 (28%) |
| LI | Waiting for 1-min candle close | 1,150 (30%) |
| BIDU | Waiting for 1-min candle close | 1,170 (31%) |
| AAPL | Waiting for 1-min candle close | 1,080 (29%) |
| NFLX | Waiting for 1-min candle close | 1,150 (30%) |
| BABA | Waiting for 1-min candle close | 1,110 (29%) |
| C | Waiting for 1-min candle close | 1,137 (30%) |
| LYFT | Waiting for bounce from pullback | 134 (3.6%) |

**Pattern**:
- All stocks are continuously checking (3,781 attempts = every bar all day)
- Getting through candle close checks
- But then stuck in either:
  - "Waiting for bounce from pullback" (never bounces enough)
  - "Tracking weak breakout" (never holds 24 bars without resetting)

---

## State Progression Analysis

### Successful Entry (AVGO - Momentum)
```
MONITORING (waiting for breakout)
   ↓
BREAKOUT_DETECTED (price broke pivot)
   ↓ (11 bars)
CANDLE_CLOSED (candle completed)
   ↓
READY_TO_ENTER (strong volume + large candle)
   ↓
✅ ENTERED (MOMENTUM_BREAKOUT)
```
**Time to entry**: ~1 minute (12 bars)

---

### Successful Entry (COIN - Pullback/Retest)
```
MONITORING
   ↓
BREAKOUT_DETECTED
   ↓ (11 bars)
CANDLE_CLOSED (weak volume)
   ↓
WEAK_BREAKOUT_TRACKING
   ↓ (multiple bars, watching price)
PULLBACK_RETEST (price near pivot)
   ↓ (18 attempts waiting for bounce)
READY_TO_ENTER (bounce >0.2% confirmed)
   ↓
✅ ENTERED (PULLBACK_RETEST)
```
**Time to entry**: ~2-5 minutes (multiple candles)

---

### Failed Entry Pattern #1 (NIO, XPEV, NVDA, etc. - Never Sustained)
```
MONITORING
   ↓
BREAKOUT_DETECTED
   ↓
CANDLE_CLOSED (weak)
   ↓
WEAK_BREAKOUT_TRACKING (held 1 bar)
   ↓
Price breaks back below pivot
   ↓
MONITORING (reset)
   ↓
Breaks above pivot again
   ↓
BREAKOUT_DETECTED (new breakout)
   ↓
... repeats 100+ times, never completes
```
**Result**: Infinite loop, never enters

---

### Failed Entry Pattern #2 (LYFT, etc. - Waiting for Bounce Forever)
```
MONITORING
   ↓
BREAKOUT_DETECTED
   ↓
CANDLE_CLOSED (weak)
   ↓
WEAK_BREAKOUT_TRACKING
   ↓
PULLBACK_RETEST (price pulls back)
   ↓
"Waiting for bounce from pullback" × 134 times
   ↓
Price never bounces >0.2% above pivot
   ↓
❌ NEVER ENTERS
```
**Result**: Stuck waiting for bounce that never comes

---

## Root Causes

### 1. Pullback Bounce Threshold Too Strict

**Current logic**:
```python
bounce_threshold_pct = 0.002  # 0.2%

if current_price > pivot * (1 + bounce_threshold_pct):
    # Bounce confirmed
```

**Problem**: If pivot is $175, needs $175.35 to confirm bounce. But price might only bounce to $175.20 (not enough).

**Solution**: Lower threshold to 0.1% or use relative movement from pullback low instead of absolute threshold.

---

### 2. Sustained Break Too Fragile

**Current logic**:
- Needs to hold above pivot for 24 consecutive bars (2 minutes)
- If price breaks back below pivot ONCE, resets entirely
- Then needs ANOTHER 24 consecutive bars

**Problem**: Stocks whipsaw across pivot constantly. Very rare to get 24 clean bars.

**Solution**: Allow small violations (e.g., 1-2 bars below pivot) without full reset, or reduce required bars to 12 (1 minute).

---

### 3. State Resets Too Aggressive

**Current logic**:
- Any break back through pivot → Full reset to MONITORING
- Loses all progress (e.g., if held 20/24 bars, then breaks back → starts over)

**Problem**: Too punishing for choppy price action.

**Solution**: Allow state to persist through small violations, or track "best progress" and resume from there.

---

## Comparison: Why Old Version Had 59 Trades

**Old version (Oct 9 fix)**:
- No state tracking
- Just checked: "Is price > pivot? Is candle closed? → Enter"
- Entered on EVERY candle close above pivot (weak or strong)
- Result: 59 trades, many low-quality

**State machine version**:
- Tracks full progression
- Requires either:
  - Strong momentum (rare: only AVGO × 2), OR
  - Pullback bounce (rare: only COIN × 2), OR
  - Sustained hold 24 bars (never happened due to whipsaws)
- Result: 4 trades, very high quality but TOO few

---

## Recommendations

### Option 1: Relax Pullback Bounce Threshold
```python
# Change from 0.002 (0.2%) to 0.001 (0.1%)
bounce_threshold_pct = 0.001
```
**Expected impact**: Would allow 8,941 "waiting for bounce" attempts to succeed

### Option 2: Reduce Sustained Break Requirement
```python
# Change from 24 bars (2 min) to 12 bars (1 min)
required_bars = 12
```
**Expected impact**: Would allow 15,000 "tracking weak breakout" attempts to complete

### Option 3: Allow State Persistence Through Violations
```python
# Allow 1-2 bars below pivot without full reset
if bars_below_pivot < 3:
    # Continue tracking, don't reset
    pass
```
**Expected impact**: Fewer resets, more sustained breaks completing

### Option 4: Implement "Best Progress" Tracking
```python
# Remember max bars held, resume from there
state.best_bars_held = max(state.best_bars_held, current_bars_held)

if state.best_bars_held >= required_bars:
    # Enter based on best progress, not current
    pass
```
**Expected impact**: Tracks progress across multiple attempts

---

## Conclusion

**The state machine architecture is CORRECT** - it's properly tracking breakout progression and preventing lookback loop issues.

**The problem is the THRESHOLDS**:
- Bounce threshold (0.2%) too strict → 8,941 stuck waiting for bounces
- Sustained hold (24 bars) too fragile → 15,000 attempts resetting before completion
- State resets too aggressive → Losing progress on minor violations

**Next step**: Relax thresholds (Option 1 + Option 2) to allow more entries while maintaining quality filtering.
