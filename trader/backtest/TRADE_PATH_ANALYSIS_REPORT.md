# Trade Path Analysis - Complete Breakdown
## October 7-9, 2025 (24 Total Trades)

**Analysis Date**: October 12, 2025
**Data Source**: 7-minute timeout rule backtests
**Purpose**: Understand which trade patterns win vs lose

---

## Executive Summary: The Four Trade Paths

The analysis reveals **4 distinct paths** that trades follow:

| Path | % of Trades | Win Rate | Avg P&L | Total P&L | Pattern |
|------|-------------|----------|---------|-----------|---------|
| **🔴 SLOW BLEED** | **37.5%** (9) | **0%** | **-$289** | **-$2,597** | Large losses via timeout |
| **⚠️ QUICK TIMEOUT** | **33.3%** (8) | **0%** | **-$50** | **-$403** | Small losses via timeout |
| **⚡ TIMEOUT SCRATCH** | **20.8%** (5) | **60%** | **+$16** | **+$78** | Near-breakeven exits |
| **🎯 PARTIAL WINNER** | **8.3%** (2) | **100%** | **+$250** | **+$500** | Winners with partials |

**KEY INSIGHT**: Only **8.3%** of trades follow the "partial winner" path (the profitable path). **70.8%** of trades are losing paths (slow bleed + quick timeout).

---

## Path 1: 🔴 SLOW BLEED (37.5% of trades)

**Description**: Hit 7-15 minute timeout with **large loss** (>$100)

### Statistics
- **Count**: 9 trades (most common path!)
- **Win Rate**: 0% (all losers)
- **Total P&L**: -$2,597 (largest loss category)
- **Avg P&L**: -$289 per trade
- **Avg Duration**: 13.2 minutes
- **Exit Reason**: 15MIN_RULE timeout

### Characteristics
- ❌ Price moves **immediately against entry**
- ❌ No recovery within 7-15 minutes
- ❌ Large position sizes = large dollar losses
- ❌ Trend was already established AGAINST our direction

### Examples

**1. C SHORT (2 trades) - DISASTER**
```
Entry: $96.59 → Exit $96.88 @ 7min = -$236 (-0.31%)
Entry: $96.73 → Exit $97.02 @ 7min = -$236 (-0.31%)
Total: -$472 from 2 trades (stock kept rising)
```

**2. COIN LONG (2 trades) - DISASTER**
```
Entry: $389.17 → Exit $387.89 @ 15min = -$174 (-0.33%)
Entry: $388.40 → Exit $388.02 @ 15min = -$52 (-0.10%)
Total: -$226 (stock kept falling after entry)
```

**3. TSLA SHORT (2 trades)**
```
Entry: $430.41 → Exit $431.80 @ 15min = -$171 (-0.33%)
Entry: $431.43 → Exit $432.97 @ 15min = -$188 (-0.36%)
Total: -$359 (stock kept rising)
```

### Root Cause
- **Wrong direction**: Entered shorts in uptrends, longs in downtrends
- **Setup quality**: Low-scoring stocks (C=60, COIN=85-95)
- **Market conditions**: Choppy days (Oct 8 especially)
- **No confirmation**: Breakouts failed immediately

### How to Avoid This Path
✅ **Filter by market trend**: Don't short strong uptrends
✅ **Require higher scores**: Min score 85+ (vs current 50+)
✅ **Wait for confirmation**: 1-2 minute sustained break
✅ **Check recent bars**: If last 3 bars all green/red, wait for pullback

---

## Path 2: ⚠️ QUICK TIMEOUT (33.3% of trades)

**Description**: Hit 7-15 minute timeout with **small loss** (<$100)

### Statistics
- **Count**: 8 trades (second most common)
- **Win Rate**: 0% (all losers)
- **Total P&L**: -$403
- **Avg P&L**: -$50 per trade
- **Avg Duration**: 12.5 minutes
- **Exit Reason**: 15MIN_RULE timeout

### Characteristics
- ⚠️ Price goes **slightly negative** (-0.1% to -1.0%)
- ⚠️ No clear directional move (choppy)
- ⚠️ Smaller position sizes OR smaller % moves
- ⚠️ "Nothing trades" - no momentum

### Examples

**1. CLOV LONG (2 trades)**
```
Entry: $2.75 → Exit $2.72 @ 7min = -$38 (-1.37%)
Entry: $2.76 → Exit $2.76 @ 11min = -$11 (-0.40%)
Total: -$49 (stock just chopped around)
```

**2. SNAP SHORT**
```
Entry: $8.25 → Exit $8.25 @ 7min = -$8 (-0.10%)
Near-breakeven but still a loser (commissions)
```

**3. BBBY SHORT**
```
Entry: $10.82 → Exit $10.81 @ 83min = -$1 (-0.01%)
Held for 83 MINUTES and still a scratch!
```

### Root Cause
- **No momentum**: Breakout lacked volume/conviction
- **Consolidation**: Stock was in tight range, not trending
- **False breakout**: Pivot broke but no follow-through
- **Low volatility**: ATR too low, not enough room to move

### How to Avoid This Path
✅ **Require volume surge**: 2x+ average volume on breakout
✅ **Check momentum candle**: Breakout bar must be 1.5x ATR
✅ **Avoid tight pivots**: Skip setups with <1% room to target
✅ **Check recent action**: If last hour was flat, skip

---

## Path 3: ⚡ TIMEOUT SCRATCH (20.8% of trades)

**Description**: Hit timeout **near breakeven** (±$50)

### Statistics
- **Count**: 5 trades
- **Win Rate**: 60% (3 winners, 2 losers!)
- **Total P&L**: +$78
- **Avg P&L**: +$16 per trade
- **Avg Duration**: 40.9 minutes (held longer)
- **Exit Reason**: 15MIN_RULE timeout

### Characteristics
- ✅ Price moves **slightly in favor** (+0.02% to +0.08%)
- ✅ Small wins from good entries
- ⚠️ Not enough momentum to trigger partials
- ⚠️ Long holding times (12-78 minutes)

### Examples

**1. BIDU SHORT (3 trades) - MIXED**
```
Entry: $141.05 → Exit $140.92 @ 12min = +$44 (0.08%) ✅ WINNER
Entry: $140.71 → Exit $140.67 @ 78min = +$11 (0.02%) ✅ WINNER
Entry: $137.93 → Exit $137.85 @ 16min = +$27 (0.05%) ✅ WINNER

Total: +$82 from 3 scratch winners
Pattern: Small profits, held waiting for more movement
```

**2. BBBY SHORT**
```
Entry: $10.79 → Exit $10.81 @ 15min = -$31 (-0.29%)
Near-scratch but slightly negative
```

### Why This Path Happens
- ✅ **Good entry**: Entered near pivot, minimal slippage
- ⚠️ **Weak momentum**: Not enough follow-through for partials
- ⚠️ **Patient waiting**: Held hoping for bigger move
- ⚠️ **Timeout exit**: Eventually bailed at small profit/loss

### Strategic Value
- **Positive EV**: 60% win rate, +$16 avg = profitable path!
- **Capital preservation**: Not bleeding large amounts
- **Better than paths 1-2**: At least breaking even

### How to Get More of This Path
✅ **Better entries**: Enter closer to pivot (reduce slippage)
✅ **Tighter stops**: Exit faster if no momentum
✅ **Dynamic targets**: Lower partial threshold (0.25% vs 0.50%)

---

## Path 4: 🎯 PARTIAL WINNER (8.3% of trades)

**Description**: Took **partials**, exited via **trailing stop**

### Statistics
- **Count**: 2 trades (ONLY 8.3% of all trades!)
- **Win Rate**: 100% (both winners)
- **Total P&L**: +$500 (carried entire 3-day P&L)
- **Avg P&L**: +$250 per trade
- **Avg Duration**: 106 minutes (held for hours!)
- **Exit Reason**: TRAIL_STOP

### Characteristics
- ✅ Price moves **strongly in favor** (+2.5%)
- ✅ Triggered partial exits (locked profit)
- ✅ Runner continued with trailing stop
- ✅ Long duration (78-134 minutes)
- ✅ This is the **ONLY profitable path**

### Examples

**1. BBBY SHORT - THE MODEL TRADE**
```
Entry:   $11.45 @ 11:23 AM
Partial 1: 50% @ $11.35 (+$0.10) → 11:24 AM (locked $50)
Partial 2: 25% @ $11.20 (+$0.25) → later
Trail:   25% @ $11.27 (stop) → 12:42 PM

Duration: 78 minutes
Partials: 2 taken
Exit: TRAIL_STOP
Total P&L: +$288 (+2.52%)

Timeline:
- Moved in our favor IMMEDIATELY
- Quick partial at 1 minute
- Runner held for 77+ minutes
- Trailing stop protected profit
```

**2. SNAP SHORT - LONG RUNNER**
```
Entry:   $8.35 @ 9:47 AM
Partial 1: 50% @ $8.30 (+$0.05) → early
Partial 2: 25% @ $8.20 (+$0.15) → mid-day
Trail:   25% @ $8.22 (stop) → 2:01 PM

Duration: 134 minutes (2+ hours!)
Partials: 2 taken
Exit: TRAIL_STOP
Total P&L: +$212 (+2.53%)

Timeline:
- Slow grind lower all morning
- Multiple partials locked profits
- Runner trailed stop for hours
- Big winner from patience
```

### What Makes This Path Work

**1. Strong Initial Move**
- Price moves 0.5%+ in first 5-10 minutes
- Triggers first partial exit (locks $50-100)
- Confirms trend direction

**2. Sustained Momentum**
- Trend continues for 60+ minutes
- Not a quick spike and reversal
- True directional move

**3. Trailing Stop Protection**
- After partials, remaining 25% protected
- Trail stop follows price
- Exits when trend finally reverses

**4. Setup Quality**
- BBBY: Score 55, tested 5+ times
- SNAP: Score 55, high volatility (8.3% ATR)
- Both had clear rejection patterns

### How to Get More of This Path

This is **THE GOAL** - we want MORE trades to follow this path!

✅ **Better setup selection**:
   - Require tighter pivots (<2.5% width)
   - Require 5+ tests of level
   - Avoid low-score stocks (<65)

✅ **Strong confirmation**:
   - 2x+ volume on breakout
   - 1.5x+ ATR momentum candle
   - Sustained 1-2 minute hold

✅ **Trend alignment**:
   - Check if stock in uptrend (longs) or downtrend (shorts)
   - Avoid counter-trend trades
   - Use daily/hourly trend

✅ **Volatility requirement**:
   - Require 4%+ ATR (enough room to move)
   - SNAP had 8.3% ATR (high volatility = big moves)

---

## Duration Analysis: Time Tells the Story

| Duration | Count | % | Win Rate | Avg P&L | Total P&L | Pattern |
|----------|-------|---|----------|---------|-----------|---------|
| **0-5 min** | 4 | 16.7% | 0% | -$129 | -$518 | Immediate failure |
| **5-10 min** | 0 | 0% | - | - | - | (none) |
| **10-15 min** | 14 | 58.3% | 7.1% | -$174 | -$2,439 | Timeout losers |
| **15-30 min** | 2 | 8.3% | 50% | +$12 | +$24 | Mixed |
| **30-60 min** | 0 | 0% | - | - | - | (none) |
| **60+ min** | 4 | 16.7% | 75% | +$128 | +$510 | Big winners |

### The "Valley of Death" (10-15 minutes)

**58.3% of trades** end in the 10-15 minute window with:
- 7.1% win rate (1 out of 14 trades)
- -$174 avg P&L
- -$2,439 total loss (largest bucket!)

**Why This Happens**:
- Trades hit 7-15 min timeout
- No momentum = no profit
- Price moved against entry
- This is where BAD SETUPS die

### The "Winner Zone" (60+ minutes)

**16.7% of trades** last 60+ minutes with:
- 75% win rate (3 out of 4 trades)
- +$128 avg P&L
- +$510 total profit

**What This Means**:
- Good trades RUN for hours
- Bad trades fail in first 15 minutes
- **There's a huge gap** between 15-60 minutes (no trades)
- Either works immediately OR needs hours to develop

### Strategic Implication

**Bimodal Distribution**:
```
Winners: 0-5 min (small) OR 60+ min (big)
Losers:  10-15 min (large cluster)
```

**This validates PS60 methodology**:
- Good trades show immediate movement OR run all day
- Bad trades fail within 5-7 minutes
- The 7-minute rule is CORRECT - it catches the death zone

---

## Exit Reason Analysis

| Exit Reason | Count | % | Win Rate | Total P&L | Avg P&L |
|-------------|-------|---|----------|-----------|---------|
| **15MIN_RULE** | 22 | 91.7% | 13.6% | -$2,922 | -$133 |
| **TRAIL_STOP** | 2 | 8.3% | 100% | +$500 | +$250 |

### Critical Finding

**91.7% of trades hit 15MIN_RULE** (timeout):
- Only 13.6% win rate
- -$133 avg loss
- -$2,922 total loss

**8.3% of trades hit TRAIL_STOP** (winners):
- 100% win rate
- +$250 avg win
- +$500 total profit

**Implication**:
- **Timeout = loser** (92% of the time)
- **Trailing stop = winner** (100% of the time)
- Goal: Get MORE trades to trigger trailing stops
- This means: **Better setup selection**

---

## Symbol Performance Analysis

### Top 5 Best Performers

| Symbol | Trades | Win Rate | Total P&L | Avg P&L | Notes |
|--------|--------|----------|-----------|---------|-------|
| **BBBY** | 3 | 33.3% | **+$257** | +$86 | 1 big winner (+$288) saved it |
| **SNAP** | 2 | 50.0% | **+$203** | +$102 | 1 big winner (+$212) |
| **BIDU** | 4 | 75.0% | **-$12** | -$3 | 3 small winners, 1 loser |
| **CLOV** | 2 | 0% | -$49 | -$24 | Small losses |
| **RIVN** | 2 | 0% | -$76 | -$38 | Small losses |

**Key Insight**:
- BBBY and SNAP carried the entire 3-day P&L
- Without these 2 trades, total P&L would be -$2,000+
- **ONE good trade per day saves the account**

### Top 5 Worst Performers

| Symbol | Trades | Win Rate | Total P&L | Avg P&L | Scanner Score |
|--------|--------|----------|-----------|---------|---------------|
| **COIN** | 4 | 0% | **-$1,007** | -$252 | 85-95 (high!) |
| **AVGO** | 1 | 0% | **-$654** | -$654 | 60 |
| **C** | 2 | 0% | **-$472** | -$236 | 60 |
| **TSLA** | 2 | 0% | **-$359** | -$179 | 85-95 (high!) |
| **HOOD** | 2 | 0% | **-$255** | -$127 | 65 |

**Critical Finding**:
- COIN had HIGH scanner score (85-95) but failed completely!
- TSLA also high score (85-95) but failed
- **Scanner score alone is NOT predictive**
- Problem: Score doesn't account for:
  - Market trend (were we shorting an uptrend?)
  - Recent momentum (last 3 bars direction)
  - Distance from pivot (too far = bad)

---

## Long vs Short Analysis

| Side | Trades | % | Win Rate | Total P&L | Avg P&L |
|------|--------|---|----------|-----------|---------|
| **LONG** | 9 | 37.5% | **0%** | **-$1,964** | **-$218** |
| **SHORT** | 15 | 62.5% | **33.3%** | **-$458** | **-$31** |

### CRITICAL FINDING: Longs Failed Completely

**LONG trades (Oct 7-9)**:
- 9 trades, 0 winners (0% win rate!)
- -$1,964 total loss
- -$218 avg loss per trade
- **Every single long lost money**

**SHORT trades**:
- 15 trades, 5 winners (33.3% win rate)
- -$458 total loss
- -$31 avg loss per trade
- **ALL winners were shorts** (BBBY, SNAP, BIDU)

### Why Did Longs Fail?

**Market Environment (Oct 7-9)**:
- Oct 7: Neutral/mixed day
- Oct 8: Choppy/whipsaw day
- Oct 9: Downtrend day

**Common Pattern**:
- Stocks opened strong (gap up)
- Broke resistance early
- **Immediately reversed** (gap fill)
- Longs entered at the top

**Examples**:
- COIN: Entered $389-392, fell to $386-388 (-$1,007 total)
- AVGO: Entered $347.61, fell to $344.66 (-$654)
- HOOD: Entered $147, fell to $147-146 (-$255)

### Why Did Some Shorts Win?

**Successful SHORT pattern**:
- Stock broke support
- Continued falling (trend)
- Sustained downward move
- Examples: BBBY (-$11.45 → $11.27), SNAP ($8.35 → $8.22)

**Failed SHORT pattern**:
- Stock broke support
- Immediately bounced back
- False breakdown

### Strategic Implication

**Market bias matters!**:
- Don't blindly trade both sides
- Check market trend (SPY/QQQ direction)
- If market trending down → shorts have edge
- If market trending up → longs have edge
- If market choppy → **SKIP TRADING**

---

## Key Patterns and Insights

### 1. The "Immediate Failure" Pattern (0-5 min)

**4 trades, all losers, -$518**

What happens:
1. Enter at pivot break
2. Price immediately reverses
3. Hits stop within 5 minutes
4. Fast exit, limited damage

Examples:
- All immediate stops were <5 min
- Avg loss: -$129
- Better than holding (timeout losses avg -$174)

**Lesson**: Quick exits are GOOD when trade fails

### 2. The "Slow Bleed" Pattern (10-15 min)

**14 trades, 1 winner, -$2,439**

What happens:
1. Enter at pivot break
2. Price moves slightly against
3. Hold hoping for reversal
4. Hit 7-15 min timeout
5. Large loss accumulated

Examples:
- C SHORT: -$236 each (held 7 min)
- COIN LONG: -$174, -$52 (held 15 min)
- This is the **DEATH ZONE**

**Lesson**: 7-minute rule saves us from even worse losses

### 3. The "Winner" Pattern (60+ min)

**4 trades, 3 winners, +$510**

What happens:
1. Enter at pivot break
2. Price moves favorably FAST
3. Take partial profit (lock gains)
4. Runner holds for hours
5. Trail stop exits on reversal

Examples:
- BBBY: 78 min, +$288
- SNAP: 134 min, +$212
- BIDU: 78 min, +$11 (scratch but held)

**Lesson**: Winners run for HOURS, not minutes

### 4. The "False Breakout" Pattern

**Most common pattern (70% of trades)**

What happens:
1. Price breaks pivot (triggers entry)
2. NO follow-through volume
3. Price reverses immediately
4. Trades fail within 15 minutes

Why it happens:
- Low volume breakout (retail, not institutions)
- Choppy market (no trend)
- Counter-trend entry (shorting uptrend)
- Wide pivot (too much room, whipsaw)

**Lesson**: Need STRONG confirmation to filter false breakouts

---

## Recommendations: How to Get More "Partial Winner" Trades

Currently only **8.3%** of trades follow the profitable path. How do we get to 30-40%?

### 1. Stricter Setup Filters

**Current filters are too loose:**
- ❌ Min score 50 (allows C=60, BBBY=55)
- ❌ Any R/R ratio (allows 1.0:1)
- ❌ No volatility requirement

**Recommended filters:**
- ✅ Min score **85** (top-tier only)
- ✅ Min R/R **2.0:1** (require 2x potential)
- ✅ Min ATR **4%** (enough room to move)
- ✅ Pivot width **<2.5%** (tight = tested = reliable)
- ✅ Test count **≥5** (heavily tested level)

### 2. Market Trend Filter

**Current: Trade any direction anytime**
- Result: 0% win rate on longs (Oct 7-9)

**Recommended:**
- ✅ Check SPY/QQQ daily trend
- ✅ If market down → shorts only
- ✅ If market up → longs only
- ✅ If market choppy → **NO TRADING**

### 3. Confirmation Requirements

**Current: Break pivot = instant entry**

**Recommended:**
- ✅ Wait 1-2 minutes (sustained break)
- ✅ Require 2x+ volume
- ✅ Require 1.5x+ ATR momentum candle
- ✅ Check last 3 bars (all same color = wait for pullback)

### 4. Dynamic Position Sizing

**Current: Fixed risk (1% per trade)**

**Recommended:**
- ✅ High-confidence setups: 1.5-2% risk
  - Score 90+, test count 10+, tight pivot
- ✅ Medium confidence: 1% risk
  - Score 85-90, test count 5-10
- ✅ Low confidence: 0.5% risk or SKIP
  - Score <85, wide pivot, choppy market

### 5. Time-of-Day Filter

**Current: Trade 9:45 AM - 3:00 PM**

**Observation from data:**
- Most losers entered 10:00-11:00 AM
- Winners entered 9:45-10:00 AM OR 11:00+ AM

**Recommended:**
- ✅ **9:45-10:30 AM**: Morning momentum (best time)
- ⚠️ **10:30-11:30 AM**: Choppy zone (be selective)
- ✅ **11:30 AM-2:00 PM**: Midday trends (good)
- ❌ **2:00-3:00 PM**: Late chop (skip)

---

## Summary: The Path to Profitability

### Current Reality (Oct 7-9)

| Path | % | Win Rate | Avg P&L | What It Means |
|------|---|----------|---------|---------------|
| 🔴 Slow Bleed | 37.5% | 0% | -$289 | Losing big |
| ⚠️ Quick Timeout | 33.3% | 0% | -$50 | Losing small |
| ⚡ Timeout Scratch | 20.8% | 60% | +$16 | Barely breakeven |
| 🎯 Partial Winner | **8.3%** | 100% | +$250 | **THE GOAL** |

**Problem**: Only 8.3% of trades are profitable. 70.8% are losers.

### Goal: Shift Distribution

**Target distribution (with better filters):**

| Path | Current % | Target % | How |
|------|-----------|----------|-----|
| 🔴 Slow Bleed | 37.5% | **10%** | Better setups, trend filter |
| ⚠️ Quick Timeout | 33.3% | **20%** | Confirmation requirements |
| ⚡ Timeout Scratch | 20.8% | **30%** | Good entries, more scratches OK |
| 🎯 Partial Winner | **8.3%** | **40%** | High-quality setups only |

**If we achieve 40% partial winners:**
- 40% × $250 avg = **+$100 avg per trade**
- 20 trades/day × $100 = **+$2,000/day**
- 20 days/month × $2,000 = **+$40,000/month** (40% return)

---

## Action Items

### Immediate (Next Backtest)
1. ✅ Increase min score to 85 (from 50)
2. ✅ Increase min R/R to 2.0 (from 1.0)
3. ✅ Add market trend filter (check SPY daily)
4. ✅ Require pivot width <3.0% (reject wide pivots)

### Short-term (Next Week)
5. ✅ Add test count filter (≥5 tests)
6. ✅ Add ATR filter (≥4% volatility)
7. ✅ Implement 1-2 minute sustained break
8. ✅ Add time-of-day filter (skip 10:30-11:30 AM chop)

### Medium-term (Next Month)
9. ✅ Dynamic position sizing (0.5-2% based on confidence)
10. ✅ Pre-market gap analysis (skip gap-filled setups)
11. ✅ Recent momentum check (last 3 bars direction)
12. ✅ Volume profile analysis (avoid low-volume pivots)

---

**Report Generated**: October 12, 2025
**Data Source**: 24 trades from October 7-9, 2025
**Methodology**: Path categorization based on exit reason, duration, P&L, and partials
