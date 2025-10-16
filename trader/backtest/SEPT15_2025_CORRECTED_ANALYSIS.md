# September 15, 2025 - Backtest Analysis (CORRECTED)

**Date Generated**: October 14, 2025
**Test Date**: September 15, 2025
**Filters Applied**: Room-to-Run (1.5% minimum) + Directional Volume
**Status**: ✅ All timestamps corrected to Eastern Time

---

## 📊 Executive Summary

| Metric | Value |
|--------|-------|
| **Total Trades** | 61 |
| **Winners** | 12 (19.7%) |
| **Losers** | 49 (80.3%) |
| **Total P&L** | **-$3,088.95** |
| **Avg Winner** | $61.49 |
| **Avg Loser** | -$78.10 |
| **Profit Factor** | 0.66 |

---

## 🔍 Filter Effectiveness

### Room-to-Run Filter ✅
- **Entries Blocked**: 179 potential trades
- **Reason**: Insufficient room to target (<1.5%)
- **Examples**:
  - TSLA Bar 1308: -3.58% room (already past target!)
  - TSLA Bar 3732: 1.34% room (too close to target)
  - LYFT Bar 864: 0.87% room (insufficient)
  - MU Bar 696: 0.41% room (too tight)

### Directional Volume Filter ✅
- **Entries Blocked**: 0 on September 15
- **Status**: Integrated and functional, no violations detected this day

---

## 🏆 Top 5 Winners

### 1. INTC LONG - $312.42 ⭐ (Best Trade)

**Setup**:
- Entry: **09:45:55 ET** @ $24.82 (1000 shares)
- Exit: **11:05:40 ET** @ $25.14 (TRAIL_STOP)
- Duration: **79.8 minutes**
- P&L per share: $0.31 (1.26%)
- Partials: 1 taken

**Decision Path**:
```
Bar 192: LONG check - price=$24.80 vs resistance=$24.45 ✅
         Confirmation: MOMENTUM_BREAKOUT (2.1x vol, 0.5% candle)
         Breakout Type: MOMENTUM
         Entry State: READY_TO_ENTER

ENTRY @ $24.80, stop=$24.50 (ATR: 3.0%)

Position Management:
- 1 partial taken during 80-minute hold
- Exited via TRAIL_STOP at 11:05 AM
```

**Why It Worked**:
- Strong momentum entry (2.1x volume)
- 0.5% candle size met threshold
- Held position for 80 minutes (avoided 7-min exit)
- Partial profit secured, runner allowed to develop
- Trail stop exit locked in gains

---

### 2. LCID LONG - $109.72

**Setup**:
- Entry: **09:53:55 ET** @ $19.62 (981 shares)
- Exit: **10:01:15 ET** @ $19.58 (TRAIL_STOP)
- Duration: **7.3 minutes**
- P&L per share: $0.11 (0.57%)
- Partials: 3 (excellent scaling!)

**Why It Worked**: Quick trail stop exit with 3 partials locked in profits

---

### 3. RBLX LONG - $98.08

**Setup**:
- Entry: **10:00:55 ET** @ $136.82 (192 shares)
- Exit: **10:18:40 ET** @ $136.54 (TRAIL_STOP)
- Duration: **17.8 minutes**
- Partials: 4 (maximum scaling)

**Why It Worked**: 4 partials = aggressive profit taking on small position

---

### 4. NIO LONG - $43.57 ⭐⭐ (Delayed Momentum Example)

**Setup**:
- Entry: **11:18:55 ET** @ $6.44 (1000 shares)
- Exit: **15:59:55 ET** @ $6.48 (EOD)
- Duration: **281 minutes** (4.7 hours - longest trade!)
- Partials: 4

**Decision Path**:
```
Bar 1308: LONG check - price=$6.43 vs resistance=$6.29 ✅
          Confirmation: MOMENTUM_BREAKOUT (delayed, 3.4x vol on candle 108)
          Breakout Type: Initially WEAK, upgraded to MOMENTUM

          Initial Breakout: Bar 781, price=$6.47, volume=1.4x (WEAK)
          Held for: 515 bars (43 minutes)

          DELAYED MOMENTUM DETECTED:
          - Candle 108 showed 3.4x volume
          - State upgraded from WEAK_BREAKOUT_TRACKING to READY_TO_ENTER

ENTRY @ $6.43, stop=$6.27 (ATR: 8.8%)

Position Management:
- 4 partials taken
- Held until EOD close (15:59)
```

**Why It Worked**:
- **Delayed momentum detection caught this!**
- System tracked weak breakout for 43 minutes
- Upgraded when 3.4x volume appeared
- Held for 4.7 hours until EOD

**KEY INSIGHT**: Proves value of continuous momentum monitoring

---

### 5. ARM LONG - $40.61

**Setup**:
- Entry: **10:16:55 ET** @ $153.49 (250 shares)
- Exit: **10:30:10 ET** @ $153.17 (TRAIL_STOP)
- Duration: **13.2 minutes**
- Partials: 3

---

## 💀 Top 5 Losers

### 1. QCOM LONG - -$347.53 (Worst Loss)

**Setup**:
- Entry: **09:58:55 ET** @ $162.74 (236 shares)
- Exit: **10:05:55 ET** @ $161.28 (7MIN_RULE)
- Duration: **7 minutes**
- P&L per share: -$1.47 (-0.90%)

**Decision Path**:
```
Bar 348: LONG check - price=$162.58 vs resistance=$162.33 ✅
         Confirmation: MOMENTUM_BREAKOUT (2.7x vol, 0.2% candle)
         Breakout Type: MOMENTUM

ENTRY @ $162.58, stop=$160.63 (ATR: 2.2%)

Position Management:
- No partials taken
- Hit 7MIN_RULE at 10:05 (7 minutes after entry)
- Lost -$1.47/share
```

**What Went Wrong**:
- Strong volume (2.7x) but move failed immediately
- 0.2% candle was at minimum threshold (barely qualified)
- Quick reversal after entry
- 7-minute rule prevented even larger loss

**Lesson**: Volume alone doesn't guarantee success

---

### 2. AMAT LONG - -$180.79

- Entry: **10:02:55 ET** @ $170.14 (226 shares)
- Exit: **10:09:55 ET** @ $169.35 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.80/share (-0.47%)

---

### 3. BBBY LONG - -$170.58

- Entry: **09:59:30 ET** @ $10.59 (1000 shares)
- Exit: **10:06:30 ET** @ $10.43 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.17/share (-1.61%)

---

### 4. C LONG - -$153.96

- Entry: **10:00:55 ET** @ $100.00 (385 shares)
- Exit: **10:07:55 ET** @ $99.61 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.40/share (-0.40%)

---

### 5. XPEV LONG - -$151.66

- Entry: **10:46:55 ET** @ $21.68 (1000 shares)
- Exit: **10:53:55 ET** @ $21.54 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.15/share (-0.70%)

---

## ⏰ Hourly Timeline (Corrected Times)

### 09:00 - 10:00 ET (Market Open)
- **Trades**: 11
- **P&L**: -$508.64
- **Win Rate**: 27.3% (3/11)
- **Best**: INTC LONG (+$312.42, 09:45→11:05)
- **Worst**: QCOM LONG (-$347.53, 09:58→10:05)

### 10:00 - 11:00 ET (Peak Activity)
- **Trades**: 28
- **P&L**: -$1,771.22
- **Win Rate**: 17.9% (5/28)
- **Best**: RBLX LONG (+$98.08, 10:00→10:18)
- **Worst**: AMAT LONG (-$180.79, 10:02→10:09)

### 11:00 - 12:00 ET
- **Trades**: 11
- **P&L**: -$505.72
- **Win Rate**: 18.2% (2/11)
- **Best**: NIO LONG (+$43.57, 11:18→15:59 EOD)
- **Worst**: AMD LONG (-$127.22, 11:16→11:23)

### 12:00 - 13:00 ET (Lunch Hour)
- **Trades**: 5
- **P&L**: -$195.66
- **Win Rate**: **0%** (0/5) ❌
- **Worst**: RBLX LONG (-$86.10, 12:57→13:04)

**⚠️ CRITICAL**: All 5 lunch hour trades were losers!

### 13:00 - 14:00 ET
- **Trades**: 3
- **P&L**: -$75.27
- **Win Rate**: **0%** (0/3) ❌
- **Worst**: SNAP LONG (-$25.95, 13:37→13:38)

### 14:00 - 15:00 ET (Late Day)
- **Trades**: 3
- **P&L**: -$32.43
- **Win Rate**: 66.7% (2/3) ✅
- **Best**: JD SHORT (+$16.48, 14:56→15:10)
- **Worst**: AVGO LONG (-$61.55, 14:11→14:18)

---

## 📉 Exit Reason Analysis

### 7MIN_RULE - 51 trades (83.6%)
- **Win Rate**: 13.7% (7 winners, 44 losers)
- **Total P&L**: -$3,516.20
- **Avg P&L**: -$68.95

**Observation**: Vast majority hitting 7-minute rule = insufficient momentum

### TRAIL_STOP - 9 trades (14.8%)
- **Win Rate**: 44.4% (4 winners, 5 losers)
- **Total P&L**: $383.69
- **Avg P&L**: $42.63

**Observation**: Trailing stops = MUCH better outcomes (44% vs 14% win rate)

### EOD - 1 trade (1.6%)
- **Win Rate**: 100% (1 winner, 0 losers)
- **Total P&L**: $43.57
- **Trade**: NIO LONG (held 4.7 hours)

---

## 📊 Stock-by-Stock Performance

| Symbol | Trades | Winners | Total P&L | Avg P&L |
|--------|--------|---------|-----------|---------|
| **INTC** | 2 | 1/2 | $247.59 | $123.79 |
| **LCID** | 2 | 1/2 | $91.27 | $45.64 |
| **NIO** | 1 | 1/1 | $43.57 | $43.57 |
| **JD** | 1 | 1/1 | $16.48 | $16.48 |
| **RBLX** | 2 | 1/2 | $11.98 | $5.99 |
| ... | ... | ... | ... | ... |
| **QCOM** | 1 | 0/1 | -$347.53 | -$347.53 |

---

## 🔍 Key Insights

### What Worked ✅

1. **Delayed Momentum Detection**:
   - NIO: Caught after 43-minute weak tracking
   - Upgraded when 3.4x volume appeared
   - Result: $43.57 profit, held 4.7 hours

2. **Trail Stop Exits**:
   - 44.4% win rate vs 13.7% for 7-min exits
   - Letting winners run = better outcomes
   - Examples: INTC (80min), RBLX (18min)

3. **Multiple Partials**:
   - RBLX: 4 partials
   - NIO: 4 partials
   - LCID: 3 partials
   - Protected profits while holding runners

4. **Room-to-Run Filter**:
   - Blocked 179 entries successfully
   - Prevented entries past target (TSLA -3.58%)

### What Didn't Work ❌

1. **83.6% hitting 7-minute rule**:
   - Only 13.7% win rate
   - Avg loss -$68.95
   - Entries not developing momentum

2. **Low win rate (19.7%)**:
   - 49 losers vs 12 winners
   - Too many weak entries

3. **Lunch hour disaster (12:00-14:00)**:
   - 8 trades, **0% win rate**
   - -$270.93 total loss
   - **Recommendation**: Avoid 12:00-14:00 ET

4. **Volume ≠ Success**:
   - QCOM: 2.7x volume, still lost -$347.53
   - Need more than volume alone

---

## 🎯 Recommendations

### Immediate Actions

1. **Add Lunch Hour Filter**:
   - Block entries 12:00-14:00 ET
   - Would save ~$271 on Sept 15
   - 0% win rate observed

2. **Strengthen Momentum Criteria**:
   - Current: 2.0x volume + 0.3% candle
   - Consider: 2.5x volume + 0.4% candle
   - Or require 2 consecutive strong candles

3. **Increase Room-to-Run Minimum**:
   - Current: 1.5%
   - Consider: 2.0% or 2.5%
   - Reduce marginal entries

### Further Testing

1. **Run Oct 14 backtest**:
   - Compare filter effectiveness
   - Validate directional volume filter

2. **Test 10-minute vs 7-minute rule**:
   - 83.6% hitting 7-min seems high
   - May need more time for development

3. **Analyze trail stop threshold**:
   - What allows 44% win rate on trail stops?
   - Can we predict which trades will survive?

---

## ✅ Technical Validation

### Logging System
- **Log File**: 65MB, 364,744 lines ✅
- **Filter Visibility**: Complete decision paths visible ✅
- **Timestamp Accuracy**: Entry times correct, exit times needed conversion ⚠️

### Entry Paths Used
1. **MOMENTUM_BREAKOUT**: INTC, QCOM (immediate entry)
2. **MOMENTUM_BREAKOUT (delayed)**: NIO (after 43-min tracking) ⭐
3. **PULLBACK/RETEST**: Not observed
4. **SUSTAINED_BREAK**: Not observed

---

## 📝 Conclusions

1. ✅ **Filters working**: 179 entries blocked by room-to-run
2. ✅ **Delayed momentum working**: NIO trade proves concept
3. ❌ **Win rate too low**: 19.7% needs improvement
4. ❌ **7-minute rule dominant**: 83.6% of trades
5. ✅ **Trail stops = winners**: 44% win rate when surviving
6. ❌ **Lunch hour avoid**: 0% win rate 12:00-14:00 ET

### Next Steps
1. Run Oct 14 backtest with filters
2. Implement lunch hour time filter
3. Test stricter momentum requirements
4. Analyze 7-min vs 10-min threshold

---

**Generated**: October 14, 2025
**Corrected**: October 14, 2025 (all timestamps verified)
**Analysis By**: PS60 Backtester v2 with Room-to-Run + Directional Volume Filters
