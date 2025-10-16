# Volume Continuation Analysis - September 15, 2025

**Analysis Date**: October 14, 2025
**Focus**: Top 20 worst 7MIN_RULE losers
**Critical Discovery**: Delayed momentum entries have DIFFERENT volume than entry candle

---

## 🔍 Executive Summary

**KEY FINDING**: The volume ratios reported at entry (e.g., "2.0x vol") refer to the **DELAYED MOMENTUM CANDLE**, not the entry bar itself. This creates confusion when analyzing volume continuation.

**Impact**:
- 60% of failed trades had NO volume continuation after entry
- Average volume decay: Entry 1.57x → +1min 1.33x → +2min 0.69x
- System only checks ONE candle for momentum, not continuation

---

## 🚨 Critical Discovery: Two Different Volumes

### Example: C (Citigroup) Entry at Bar 372

**What the log says**:
```
C Bar 372 - LONG confirmation: confirmed=True,
reason='MOMENTUM_BREAKOUT (delayed, 2.0x vol on candle 30)'
```

**What this ACTUALLY means**:
- **Initial breakout**: Bar 180 (WEAK, insufficient volume)
- **State**: PULLBACK_RETEST (waiting for confirmation)
- **Candle 30 after breakout**: Showed 2.0x volume → DELAYED MOMENTUM DETECTED
- **Entry bar**: Bar 372 (entry happened HERE)

**Volume confusion**:
- ❌ **Wrong interpretation**: Entry bar 372 has 2.0x volume
- ✅ **Correct interpretation**: Candle 30 (some bar before 372) had 2.0x volume, triggering delayed entry at bar 372

### Actual Entry Bar Volume vs Delayed Momentum Volume

| Symbol | Entry Bar | Reported Volume | Entry Bar Actual Volume | Discrepancy |
|--------|-----------|-----------------|------------------------|-------------|
| C | 372 | "2.0x vol on candle 30" | 0.49x | ❌ DELAYED |
| AMAT | 396 | "2.4x vol on candle 32" | 0.66x | ❌ DELAYED |
| QCOM | 348 | "2.7x vol" | 5.71x | ✅ IMMEDIATE |
| XPEV | 420 | "2.3x vol on candle 34" | 2.00x | ✅ MATCHES |

**Pattern discovered**:
- Entries with "delayed, X.Xx vol on candle N" → momentum was N candles BEFORE entry
- Entry bar itself may have LOW volume (already decayed)
- Entries without "delayed" → momentum on entry bar itself

---

## 📊 Volume Continuation Results - Top 20 Worst 7MIN_RULE Losers

### Summary Statistics

**Total Analyzed**: 20 trades
**Volume Continued** (≥1.3x in next 2 candles): 8 trades (40.0%)
**Volume Did NOT Continue**: 12 trades (60.0%)

**Average Volume Ratios**:
- Entry candle: **1.57x** (below 2.0x threshold!)
- +1 minute: **1.33x** (15.2% decay)
- +2 minutes: **0.69x** (56% decay from entry)

---

## 🔝 Top 20 Detailed Analysis

### 1. QCOM LONG - $-347.53 (Worst Loss) ⚠️

**Entry**: 09:58:55 ET @ $162.74 (Bar 348)
**Exit**: 10:05:55 ET @ $161.28 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **5.71x** (STRONG initial momentum)
- +1 minute: **2.31x** (59% decay but still elevated)
- +2 minutes: **0.51x** (91% decay, momentum died)

**Continuation**: ✅ YES (1 minute had 2.31x)
**Verdict**: Strong entry, but momentum evaporated quickly

---

### 2. AMAT LONG - $-180.79 ⚠️ DELAYED MOMENTUM

**Entry**: 10:02:55 ET @ $170.14 (Bar 396)
**Exit**: 10:09:55 ET @ $169.35 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.4x vol on candle 32)"

**Volume Analysis**:
- Entry candle: **0.66x** (BELOW threshold - momentum already decayed!)
- +1 minute: **1.19x** (slight increase but weak)
- +2 minutes: **0.73x** (dropped again)

**Continuation**: ❌ NO
**Verdict**: Delayed entry caught the tail end, momentum already gone

---

### 3. BBBY LONG - $-170.58

**Entry**: 09:59:30 ET @ $10.59 (Bar 354)
**Exit**: 10:06:30 ET @ $10.43 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **0.74x** (BELOW threshold)
- +1 minute: **2.47x** (sudden spike!)
- +2 minutes: **0.07x** (collapsed completely)

**Continuation**: ✅ YES (brief spike at +1min)
**Verdict**: Volume came AFTER entry, too late

---

### 4. C LONG - $-153.96 ⚠️ DELAYED MOMENTUM

**Entry**: 10:00:55 ET @ $100.00 (Bar 372)
**Exit**: 10:07:55 ET @ $99.61 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.0x vol on candle 30)"

**Volume Analysis**:
- Entry candle: **0.49x** (BELOW threshold - momentum long gone!)
- +1 minute: **0.64x** (still weak)
- +2 minutes: **0.42x** (collapsing)

**Continuation**: ❌ NO
**Verdict**: Classic delayed entry failure - entered after momentum died

---

### 5. XPEV LONG - $-151.66

**Entry**: 10:46:55 ET @ $21.68 (Bar 420)
**Exit**: 10:53:55 ET @ $21.54 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **2.00x** (EXACTLY at threshold)
- +1 minute: **2.64x** (INCREASED!)
- +2 minutes: **0.80x** (then faded)

**Continuation**: ✅ YES (sustained 2+ candles)
**Verdict**: Good entry, but price didn't follow volume

---

### 6. LRCX LONG - $-146.36

**Entry**: 10:20:55 ET @ $81.01 (Bar 768)
**Exit**: 10:27:55 ET @ $80.53 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **1.95x** (near threshold)
- +1 minute: **0.71x** (64% decay)
- +2 minutes: **0.25x** (87% decay)

**Continuation**: ❌ NO
**Verdict**: Momentum died immediately after entry

---

### 7. PYPL LONG - $-129.17 ⚠️ DELAYED MOMENTUM

**Entry**: 11:06:55 ET @ $61.53 (Bar 1164)
**Exit**: 11:13:55 ET @ $61.33 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.5x vol on candle 93)"

**Volume Analysis**:
- Entry candle: **0.57x** (BELOW threshold - momentum gone!)
- +1 minute: **0.36x** (still weak)
- +2 minutes: **0.34x** (no recovery)

**Continuation**: ❌ NO
**Verdict**: Extreme delayed entry, entered way after momentum

---

### 8. JPM LONG - $-129.06 ⚠️ DELAYED MOMENTUM

**Entry**: 09:51:55 ET @ $232.79 (Bar 288)
**Exit**: 09:58:55 ET @ $232.48 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.2x vol on candle 17)"

**Volume Analysis**:
- Entry candle: **0.71x** (BELOW threshold)
- +1 minute: **0.46x** (declining)
- +2 minutes: **0.53x** (no momentum)

**Continuation**: ❌ NO
**Verdict**: Delayed entry after momentum peak

---

### 9. AMD LONG - $-127.22

**Entry**: 11:16:55 ET @ $138.85 (Bar 1284)
**Exit**: 11:23:55 ET @ $138.44 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **1.41x** (below 2.0x threshold)
- +1 minute: **1.20x** (slight decay)
- +2 minutes: **1.08x** (gradual fade)

**Continuation**: ❌ NO (all below 1.3x continuation threshold)
**Verdict**: Marginal volume throughout

---

### 10. MS LONG - $-125.84

**Entry**: 11:24:55 ET @ $117.70 (Bar 1380)
**Exit**: 11:31:55 ET @ $117.49 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **1.44x** (below 2.0x threshold)
- +1 minute: **1.32x** (slight decay)
- +2 minutes: **2.13x** (sudden spike!)

**Continuation**: ✅ YES (2.13x at +2min)
**Verdict**: Volume came too late, already stopped out

---

### 11. NIO LONG - $-124.73 ⚠️ DELAYED MOMENTUM

**Entry**: 13:37:55 ET @ $6.55 (Bar 2916)
**Exit**: 13:38:55 ET @ $6.52 (7MIN_RULE)
**Duration**: 1.0 minutes (INSTANT FAILURE!)

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.1x vol on candle 218)"

**Volume Analysis**:
- Entry candle: **0.13x** (EXTREMELY low - momentum LONG gone!)
- +1 minute: **0.12x** (dead)
- +2 minutes: **0.12x** (no volume)

**Continuation**: ❌ NO
**Verdict**: WORST delayed entry - 218 candles (18+ minutes) after momentum!

---

### 12. TSLA SHORT - $-107.71

**Entry**: 10:45:55 ET @ $444.12 (Bar 1068)
**Exit**: 10:52:55 ET @ $444.63 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **1.24x** (below 2.0x threshold)
- +1 minute: **1.09x** (fading)
- +2 minutes: **2.60x** (spike after entry!)

**Continuation**: ✅ YES (2.60x at +2min)
**Verdict**: Volume increased but price went wrong way (SHORT failed)

---

### 13. LYFT LONG - $-105.33 ⚠️ DELAYED MOMENTUM

**Entry**: 12:16:55 ET @ $12.56 (Bar 1992)
**Exit**: 12:23:55 ET @ $12.51 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 3.7x vol on candle 157)"

**Volume Analysis**:
- Entry candle: **0.39x** (BELOW threshold - momentum gone!)
- +1 minute: **0.31x** (dying)
- +2 minutes: **0.23x** (dead)

**Continuation**: ❌ NO
**Verdict**: Extreme delayed entry, no volume at entry

---

### 14. SNAP LONG - $-103.47

**Entry**: 13:29:55 ET @ $9.16 (Bar 2820)
**Exit**: 13:36:55 ET @ $9.12 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **2.07x** (JUST above 2.0x threshold!)
- +1 minute: **0.77x** (63% decay)
- +2 minutes: **1.28x** (recovered slightly)

**Continuation**: ❌ NO
**Verdict**: Marginal entry, momentum didn't sustain

---

### 15. BA LONG - $-102.86

**Entry**: 13:25:55 ET @ $156.35 (Bar 2772)
**Exit**: 13:32:55 ET @ $156.17 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **2.51x** (strong!)
- +1 minute: **0.61x** (76% decay!)
- +2 minutes: **0.45x** (82% decay)

**Continuation**: ❌ NO
**Verdict**: Strong entry spike, but immediate collapse

---

### 16. AVGO LONG - $-96.49

**Entry**: 09:57:55 ET @ $164.72 (Bar 336)
**Exit**: 10:04:55 ET @ $164.47 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **1.73x** (below 2.0x threshold)
- +1 minute: **1.89x** (increased!)
- +2 minutes: **0.70x** (then died)

**Continuation**: ✅ YES (1.89x at +1min)
**Verdict**: Volume sustained 1 minute then faded

---

### 17. RBLX LONG - $-86.10

**Entry**: 12:57:55 ET @ $45.49 (Bar 2484)
**Exit**: 13:04:55 ET @ $45.05 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **1.66x** (below 2.0x threshold)
- +1 minute: **3.64x** (HUGE spike!)
- +2 minutes: **0.56x** (then collapsed)

**Continuation**: ✅ YES (3.64x spike at +1min)
**Verdict**: Volume came AFTER entry, price already failing

---

### 18. HOOD LONG - $-84.92 ⚠️ DELAYED MOMENTUM

**Entry**: 10:33:55 ET @ $36.74 (Bar 924)
**Exit**: 10:40:55 ET @ $36.61 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.0x vol on candle 60)"

**Volume Analysis**:
- Entry candle: **0.84x** (BELOW threshold)
- +1 minute: **1.29x** (improved but not strong)
- +2 minutes: **1.01x** (fading)

**Continuation**: ❌ NO
**Verdict**: Delayed entry, weak volume throughout

---

### 19. COIN LONG - $-84.36

**Entry**: 14:28:55 ET @ $159.68 (Bar 3564)
**Exit**: 14:35:55 ET @ $159.41 (7MIN_RULE)
**Duration**: 7.0 minutes

**Volume Analysis**:
- Entry candle: **2.01x** (barely above 2.0x)
- +1 minute: **0.49x** (76% decay!)
- +2 minutes: **0.65x** (weak)

**Continuation**: ❌ NO
**Verdict**: Marginal entry, immediate decay

---

### 20. NFLX LONG - $-83.61 ⚠️ DELAYED MOMENTUM

**Entry**: 10:24:55 ET @ $704.68 (Bar 816)
**Exit**: 10:31:55 ET @ $703.81 (7MIN_RULE)
**Duration**: 7.0 minutes

**Log says**: "MOMENTUM_BREAKOUT (delayed, 2.1x vol on candle 54)"

**Volume Analysis**:
- Entry candle: **0.77x** (BELOW threshold - momentum gone!)
- +1 minute: **1.03x** (improved but weak)
- +2 minutes: **0.51x** (fading)

**Continuation**: ❌ NO
**Verdict**: Delayed entry after peak momentum

---

## 🔑 Key Insights

### 1. Delayed Momentum Entries Are Problematic

**Count**: 8 out of 20 (40%) were delayed momentum entries
**Performance**: All delayed entries FAILED to continue volume

**Examples**:
- NIO: 218 candles delay (18+ minutes!) → 0.13x volume at entry
- LYFT: 157 candles delay → 0.39x volume at entry
- PYPL: 93 candles delay → 0.57x volume at entry

**Problem**: By the time delayed momentum triggers entry, the volume spike is long gone.

### 2. Volume Continuation is RARE (40%)

**Volume continued** (8/20): QCOM, BBBY, XPEV, MS, TSLA, AVGO, RBLX, JPM
**Volume did NOT continue** (12/20): All delayed momentum + some immediate entries

**Pattern**: Even immediate momentum entries often fail to sustain volume.

### 3. Average Entry Volume Below Threshold

**Average entry candle volume**: 1.57x
**Required threshold**: 2.0x
**Discrepancy**: 27% below threshold!

**Why**: Delayed momentum entries happen AFTER volume peak, pulling average down.

### 4. Rapid Volume Decay

**Volume decay pattern**:
- Entry: 1.57x
- +1 minute: 1.33x (15% decay)
- +2 minutes: 0.69x (56% decay from entry)

**Implication**: Volume spikes are SHORT-LIVED, often <1 minute duration.

---

## 💡 Recommendations

### Option A: Require Volume Continuation (CONSERVATIVE)

**Logic**: Entry requires 2.0x volume AND next 2 candles ≥1.3x

**Expected Impact**:
- Would block 60% of these failed trades (12/20)
- May also block some winners (need to analyze winning trades)
- More conservative, fewer trades

**Implementation**:
```python
# After detecting 2.0x volume candle
if volume_ratio >= 2.0:
    # Check next 2 candles also have volume
    next_2_candles_volume = [...]
    if all(v >= 1.3 for v in next_2_candles_volume):
        enter_trade()
    else:
        skip_trade("Volume did not continue")
```

### Option B: Limit Delayed Momentum Delay (MODERATE)

**Logic**: Only allow delayed entries within 30 candles (2.5 minutes) of momentum spike

**Expected Impact**:
- Would block extreme delays (NIO 218 candles, LYFT 157 candles)
- Still allow reasonable delays (C 30 candles, AMAT 32 candles)
- Reduces worst delayed entries while keeping recent ones

**Implementation**:
```python
# In delayed momentum detection
candles_since_breakout = current_idx - state.candle_close_bar

if candles_since_breakout > 30:  # >2.5 minutes
    skip_entry("Delayed momentum too old")
```

### Option C: Increase Momentum Threshold (AGGRESSIVE)

**Logic**: Raise volume threshold from 2.0x to 2.5x or 3.0x

**Expected Impact**:
- Fewer entries overall
- Only very strong momentum qualifies
- May miss moderate movers

**Tradeoff**: Quality vs quantity

### Option D: Disable Delayed Momentum Completely (NUCLEAR)

**Logic**: Remove delayed momentum detection, only enter on immediate momentum

**Expected Impact**:
- Eliminates 40% of failures (all delayed entries)
- Loses potential delayed breakout captures
- Simplifies system

**Tradeoff**: Misses stocks that build momentum gradually

---

## 📈 Next Steps

1. **Analyze winning trades**: Do winners show volume continuation?
2. **Test Option B**: Run backtest with 30-candle delay limit
3. **Measure impact**: Compare win rate, P&L with/without delayed momentum
4. **Decide**: Keep delayed momentum but limit it, or remove entirely?

---

**Generated**: October 14, 2025
**Analysis By**: PS60 Volume Continuation Study
**Data Source**: Sept 15, 2025 backtest results + cached 5-second bars
