# PLTR Deep Analysis - Why It Was Filtered Out (Oct 1, 2025)

**Date**: October 5, 2025
**Stock**: PLTR (Palantir)
**Outcome**: Missed winner due to momentum candle filter

---

## Executive Summary

**PLTR broke resistance at 9:45 AM and hit target by 11:03 AM (+2.21% gain), but the backtest filtered it out.**

**Root Cause**: **Momentum candle filter too strict**
- Volume: ✅ PASSED (1.44x > 1.2x threshold)
- Candle size: ❌ FAILED (0.04% < 0.8% threshold)
- Candle/ATR: ❌ FAILED (0.58x < 2.0x threshold)

**Result**: Backtest missed a winner that gained +2.21% to max

---

## Breakout Details

### 1-Minute Bar Analysis (Validator View)

**Breakout Bar @ 09:45**:
```
Open:   $181.85
High:   $182.25
Low:    $181.83
Close:  $182.25
Volume: 269,958

Candle size: $0.40 (0.22% move)
```

**Resistance**: $182.24
**First break**: 09:45 @ $182.25 (+$0.01 above resistance)

This is what the validator saw - a clean 1-minute candle close above resistance with 0.22% momentum.

---

### 5-Second Bar Analysis (Backtest View)

**Breakout Bar @ 09:45:55**:
```
Open:   $182.17
High:   $182.25
Low:    $182.16
Close:  $182.25
Volume: 20,579

Candle size: $0.08 (0.04% move)
```

**Why different from 1-minute bar?**
- The 1-minute bar aggregates 12 five-second bars (9:45:00 - 9:45:55)
- The specific 5-second bar at 9:45:55 had only 0.04% momentum
- Volume was concentrated across the full minute (269K total) vs this single 5-second bar (20K)

---

## Filter Analysis

### Current Backtest Thresholds

**From `trader_config.yaml` (lines 52-74)**:
```yaml
confirmation:
  enabled: true
  volume_surge_required: true
  volume_surge_multiplier: 1.2        # Need >= 1.2x average
  momentum_candle_required: true

  # Momentum requires EITHER:
  momentum_candle_min_pct: 0.008      # Candle >= 0.8% move OR
  momentum_candle_min_atr: 2.0        # Candle >= 2.0x ATR
```

### PLTR Performance vs Thresholds

| Metric | PLTR Value | Threshold | Result |
|--------|------------|-----------|--------|
| **Volume Ratio** | 1.44x | >= 1.2x | ✅ PASS |
| **Candle %** | 0.04% | >= 0.8% | ❌ FAIL |
| **Candle/ATR** | 0.58x | >= 2.0x | ❌ FAIL |
| **Overall** | - | Volume AND (Candle OR ATR) | ❌ FILTERED |

**Failing Condition**:
- Volume: ✅ 1.44x > 1.2x (PASS)
- Momentum: ❌ 0.04% < 0.8% AND 0.58x < 2.0x (FAIL)
- **Logic**: Requires Volume AND (Candle OR ATR)
- **Result**: FILTERED OUT

---

## Why This Is a Problem

### The 5-Second Bar Paradox

**Issue**: Using 5-second bars creates very granular data that often has weak individual candles even during strong 1-minute moves.

**Example - PLTR 09:45 Minute**:
- **1-minute view**: $0.40 candle (0.22% move) - looks decent
- **5-second view**: $0.08 candle (0.04% move) - looks weak
- **Reality**: Same breakout, different granularity

**The 5-second bar at 9:45:55 that broke resistance**:
- Had good volume (1.44x average) ✅
- But only 0.04% price move (too small for 0.8% threshold) ❌
- And only 0.58x ATR (too small for 2.0x threshold) ❌

This is a **data resolution issue** - the 5-second bar is too granular to meet momentum thresholds designed for 1-minute candles.

---

## Post-Breakout Performance

**Timeline**:
```
09:45:00 - Breakout @ $182.25 (resistance $182.24)
09:45:55 - First 5-sec bar close above resistance
11:03:00 - Reached max price $186.28
         - Hit target $184.14 ✅
```

**Performance Metrics**:
- Entry: $182.25
- Target: $184.14
- Max: $186.28
- Gain to target: +1.04%
- Gain to max: +2.21%
- **Result**: CLEAN WINNER

**What backtest would have done** (if it entered):
1. Enter @ $182.25
2. Take 50% partial @ +$0.60-1.00 gain
3. Hit target @ $184.14 (take 25%)
4. Trail stop on 25% runner
5. **Estimated P&L**: +$800-1,200

---

## Why Was This a Winner Despite Weak Candle?

### Key Observation
**PLTR had a "slow grind" breakout, not explosive momentum**

**Characteristics**:
- Broke resistance at exactly 9:45:00 (market opened at 9:30)
- 15 minutes of consolidation at resistance before break
- Small 5-second candles but sustained buying pressure
- Volume was good (1.44x) showing institutional accumulation
- Slow grind up to $186.28 over 1.5 hours

**This is a valid PS60 setup**:
- Clear resistance level tested ($182.24)
- Volume confirmation (1.44x surge)
- Sustained break (never fell back below resistance)
- Hit target with room to spare

**But it doesn't fit "momentum breakout" profile**:
- No explosive 0.8%+ candle
- No 2x ATR volatility expansion
- Slow, steady climb vs explosive move

---

## Comparison: Configuration Philosophy

### Current Config (Strict Momentum)
**Philosophy**: Only enter explosive momentum breakouts
- Requires 0.8% candle OR 2.0x ATR
- Designed to catch "rocket ship" moves
- Filters out slow grinds

**Pros**:
- Avoids weak breakouts that reverse
- Higher win rate on entries (quality over quantity)
- Less whipsaw

**Cons**:
- Misses slow grind winners like PLTR
- Too strict for 5-second bar resolution
- Reduces number of trades

### Alternative: Sustained Break Logic
**Philosophy**: Enter any break with volume that holds
- Require volume (1.2x+)
- Require 1-minute candle close above resistance
- Check if price HOLDS above resistance for 1-2 minutes
- Don't require explosive candle size

**Pros**:
- Catches slow grind winners like PLTR
- Better suited for 5-second bar resolution
- More trades

**Cons**:
- More false breakouts (weak breaks that reverse)
- Lower win rate (more whipsaw)
- Need tighter stops

---

## Root Cause: 5-Second Bars vs 1-Minute Thresholds

### The Mismatch

**Backtest uses**: 5-second bars (for granular entry timing)
**Thresholds designed for**: 1-minute candles (0.8% move, 2.0x ATR)

**Math**:
- 1-minute candle with 0.8% move = $0.40 on PLTR ($182 stock)
- 5-second candle would need same $0.40 = 0.8% move in 5 seconds!
- This is unrealistic - most 5-second bars are $0.05-0.15 range

**PLTR Example**:
- 1-minute bar: $0.40 candle (0.22%) - reasonable
- 5-second bar: $0.08 candle (0.04%) - very small for 5 seconds
- **Neither meets 0.8% threshold**, but 1-min shows better momentum

### Solution Options

**Option 1: Use 1-minute bars for confirmation**
- Switch backtest to 1-minute bars
- Lose granularity for entry timing
- Thresholds (0.8%, 2.0x ATR) now make sense

**Option 2: Adjust thresholds for 5-second bars**
- Reduce candle requirement from 0.8% → 0.1% (for 5-sec bars)
- Reduce ATR requirement from 2.0x → 0.5x (for 5-sec bars)
- Keep 5-second granularity

**Option 3: Hybrid approach**
- Use 1-minute candle to confirm momentum
- Use 5-second bars to find exact entry timing
- Best of both worlds

**Option 4: Add "sustained break" logic**
- Don't require large initial candle
- Instead: Check if price HOLDS above resistance for 1-2 minutes
- Volume + sustained break = entry (no candle size check)

---

## Recommended Fix

### Recommendation: **Option 4 - Sustained Break Logic**

**Why**:
- Catches both explosive (COIN) and grind (PLTR) breakouts
- Doesn't require adjusting thresholds for bar size
- PS60-compliant (Dan Shapiro uses "sustained break" concept)
- Reduces false breakouts (must hold for 1-2 min)

**Implementation**:
```yaml
confirmation:
  enabled: true

  # OPTION A: Momentum breakout (explosive)
  momentum_candle_min_pct: 0.008      # 0.8% on 1-min aggregated bars
  momentum_candle_min_atr: 2.0        # 2x ATR volatility

  # OPTION B: Sustained break (grind)
  sustained_break_required: true      # Must hold above resistance
  sustained_break_minutes: 2          # For 2 minutes (24 five-second bars)
  sustained_break_max_pullback: 0.001 # Allow 0.1% pullback (noise)

  # Volume required for BOTH
  volume_surge_required: true
  volume_surge_multiplier: 1.2
```

**Logic**: Enter if **Volume AND (Momentum OR Sustained)**
- Explosive breakout (0.8% candle) → Enter immediately
- Slow grind (holds 2 min) → Enter after confirmation
- No volume → Skip (both require volume)

**PLTR Example with this logic**:
- Volume: ✅ 1.44x (PASS)
- Momentum candle: ❌ 0.04% (FAIL)
- Sustained break: Check if held above $182.24 for 2 minutes...
  - 09:45:55 - Broke @ $182.25
  - 09:47:55 - Still above @ $182.50+ ✅
  - **Result**: WOULD ENTER via sustained break logic

---

## Historical Context: Why Current Thresholds Exist

**From Sept 23-30 analysis** (COMPREHENSIVE_BREAKOUT_FINDINGS.md):

All 3 breakouts that occurred failed to reach targets:
- HOOD: 0.68x vol, 0.61% candle - filtered ✅
- COIN: 0.95x vol, 0.42% candle - filtered ✅
- BIDU: 1.49x vol, 0.40% candle - filtered ✅

**Conclusion from Sept 23-30**: "Filters are working perfectly"

**But Oct 1 shows different story**:
- PLTR: 1.44x vol, 0.04% candle - filtered ❌ (but was a winner!)
- COIN: Volume surge - entered ✅ (winner)
- TSLA/AMD: Early breakouts - timing issue

**Key Insight**: Sept 23-30 was a DOWN/CHOPPY market where only explosive moves worked. Oct 1 was NEUTRAL market where slow grinds also worked.

---

## Impact Analysis

### Oct 1 Missed Opportunity

**If PLTR had been entered**:
- Entry: $182.25 @ 09:45
- Exit (partial): ~$183.00 @ 10:00 (50% @ +0.75)
- Exit (target): $184.14 @ 11:03 (25%)
- Exit (trail): $185.50+ (25% runner)
- **Estimated P&L**: +$900-1,200 (vs missed)

### Full Month Impact (Speculation)

If sustained break logic catches 1-2 additional "slow grind" winners per day:
- Current: +$795.99 (1 trade, COIN only)
- With fix: +$2,000-2,500 (2-3 trades per day)
- **Potential upside**: +$1,200-1,700 per day

**Risk**: Also catches more slow breaks that fail (need to validate on more days)

---

## Conclusion

**PLTR was filtered out because**:
1. Used 5-second bars for entry timing
2. Applied 1-minute candle momentum thresholds (0.8%, 2.0x ATR)
3. PLTR had 0.04% five-second candle (too small for threshold)
4. PLTR was a "slow grind" breakout, not explosive momentum

**This was a valid PS60 setup that should have been caught**:
- ✅ Clear resistance level
- ✅ Volume surge (1.44x)
- ✅ Sustained break (held for 1+ hours)
- ✅ Hit target with follow-through

**Fix needed**: Add "sustained break" logic to catch slow grinds that hold above resistance with volume, even without explosive initial candle.

---

**Report generated**: October 5, 2025
**Analysis confidence**: HIGH (based on 5-second IBKR data)
**Recommendation**: Implement sustained break logic (Option 4)
