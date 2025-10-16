# September 15, 2025 - Comprehensive Backtest Analysis

**Date**: October 14, 2025  
**Test Date**: September 15, 2025  
**Filters Applied**: Room-to-Run (1.5% minimum) + Directional Volume

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
| **Profit Factor** | 0.66 (losers > winners) |

---

## 🔍 Filter Effectiveness

### Room-to-Run Filter
- **Entries Blocked**: 179 potential trades blocked ✅
- **Reason**: Insufficient room to target (<1.5%)
- **Examples**:
  - TSLA Bar 1308: -3.58% room (already past target!)
  - TSLA Bar 3732: 1.34% room (too close to target)
  - LYFT Bar 864: 0.87% room (insufficient)
  - MU Bar 696: 0.41% room (too tight)

**Impact**: Filter successfully prevented entries where price had already consumed most/all of the move to target.

### Directional Volume Filter
- **Entries Blocked**: 0 on September 15
- **Reason**: No counter-trend volume spikes detected
- **Status**: Filter integrated and functional, just no violations on this specific day

---

## ⏰ Timeline Analysis - Hourly Breakdown

### 09:00 - 10:00 ET (Market Open)
**Trades**: 11 | **P&L**: -$508.64 | **Winners**: 3/11 (27.3%)

**Best Trade**:
- ✅ **INTC LONG** - $312.42 profit
  - Entry: 09:45 @ $24.82
  - Exit: 15:05 @ $25.14 (TRAIL_STOP)
  - Duration: 79.8 minutes
  - **Decision Path**: MOMENTUM_BREAKOUT (2.1x vol, 0.5% candle)
  - Partials: 1 taken
  - **Key**: Early momentum entry + held for 80min runner

**Worst Trades**:
- ❌ **BBBY LONG** - -$170.58
  - Entry: 09:59 @ $10.59
  - Exit: 14:06 @ $10.43 (7MIN_RULE)
  - Duration: 7 minutes
  - **Issue**: Quick 7-min rule exit, -1.61% loss

### 10:00 - 11:00 ET (Peak Activity)
**Trades**: 28 | **P&L**: -$1,771.22 | **Winners**: 5/28 (17.9%)

**Worst Trade**:
- ❌ **QCOM LONG** - -$347.53
  - Entry: 09:58 @ $162.74
  - Exit: 14:05 @ $161.28 (7MIN_RULE)
  - Duration: 7 minutes
  - **Decision Path**: MOMENTUM_BREAKOUT (2.7x vol, 0.2% candle)
  - **Issue**: Strong volume but move failed, hit 7-min rule
  - Loss per share: -$1.47 (-0.90%)

**Notable Winners**:
- ✅ **RBLX LONG** - $98.08
  - Entry: 10:00 @ $136.82
  - Exit: 14:18 @ $136.54 (TRAIL_STOP)
  - Duration: 17.8 minutes
  - Partials: 4 taken (excellent scaling)

### 11:00 - 12:00 ET
**Trades**: 11 | **P&L**: -$505.72 | **Winners**: 2/11 (18.2%)

**Best Trade**:
- ✅ **NIO LONG** - $43.57
  - Entry: 11:18 @ $6.44
  - Exit: 19:59 @ $6.48 (EOD)
  - Duration: 281 minutes (longest trade of day!)
  - **Decision Path**: MOMENTUM_BREAKOUT (delayed, 3.4x vol on candle 108)
  - Partials: 4 taken
  - **Key**: Delayed momentum detection caught this after initial weak breakout
  - Held for 4+ hours until EOD close

### 12:00 - 13:00 ET (Lunch Hour)
**Trades**: 5 | **P&L**: -$195.66 | **Winners**: 0/5 (0%)

**Observation**: All 5 trades losers during lunch consolidation period.

### 13:00 - 14:00 ET
**Trades**: 3 | **P&L**: -$75.27 | **Winners**: 0/3 (0%)

### 14:00 - 15:00 ET (Late Day)
**Trades**: 3 | **P&L**: -$32.43 | **Winners**: 2/3 (66.7%)

**Best late-day entry**:
- ✅ **JD SHORT** - $16.48
  - Entry: 14:56 @ $33.49
  - Exit: 19:10 @ $33.46 (7MIN_RULE)
  - Duration: 13.7 minutes

---

## 🏆 Top 5 Winners - Decision Path Analysis

### 1. INTC LONG - $312.42 ⭐

**Setup**:
- Entry: 09:45 @ $24.82 (1000 shares)
- Exit: 15:05 @ $25.14 (TRAIL_STOP)
- Duration: 79.8 minutes
- P&L per share: $0.3124 (1.26%)

**Decision Path**:
```
Bar 192: LONG check - price=$24.80 vs resistance=$24.45 ✅
         Confirmation: MOMENTUM_BREAKOUT (2.1x vol, 0.5% candle)
         Breakout Type: MOMENTUM
         Entry State: READY_TO_ENTER
         
ENTRY @ $24.80, stop=$24.50 (ATR: 3.0%)

Position Management:
- 1 partial taken during 80-minute hold
- Exited via TRAIL_STOP (let winner run!)
```

**Why It Worked**:
- Strong momentum entry (2.1x volume)
- 0.5% candle size met threshold
- Held position for 80 minutes instead of 7-min exit
- Partial profit secured, runner allowed to develop

---

### 2. LCID LONG - $109.72

**Setup**:
- Entry: 09:53 @ $19.62 (981 shares)
- Exit: 14:01 @ $19.58 (TRAIL_STOP)
- Duration: 7.3 minutes
- P&L per share: $0.1118 (0.57%)
- Partials: 3 (excellent scaling!)

**Why It Worked**: Quick TRAIL_STOP exit with 3 partials locked in profits early

---

### 3. RBLX LONG - $98.08

**Setup**:
- Entry: 10:00 @ $136.82 (192 shares)
- Exit: 14:18 @ $136.54 (TRAIL_STOP)
- Duration: 17.8 minutes
- Partials: 4 (maximum scaling)

**Why It Worked**: 4 partials = aggressive profit taking on small position size

---

### 4. NIO LONG - $43.57 ⭐⭐

**Setup**:
- Entry: 11:18 @ $6.44 (1000 shares)
- Exit: 19:59 @ $6.48 (EOD)
- Duration: 281 minutes (longest trade)
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
- Held until EOD close (19:59)
```

**Why It Worked**:
- **Delayed momentum detection** caught this trade!
- System was tracking weak breakout for 43 minutes
- When 3.4x volume appeared, upgraded to momentum entry
- Held for 4+ hours until EOD

**KEY INSIGHT**: This trade proves the value of delayed momentum detection - would have been missed without continuous monitoring!

---

### 5. ARM LONG - $40.61

**Setup**:
- Entry: 10:16 @ $153.49 (250 shares)
- Exit: 14:30 @ $153.17 (TRAIL_STOP)
- Duration: 13.2 minutes
- Partials: 3

---

## 💀 Top 5 Losers - What Went Wrong

### 1. QCOM LONG - -$347.53 (Worst Loss)

**Setup**:
- Entry: 09:58 @ $162.74 (236 shares)
- Exit: 14:05 @ $161.28 (7MIN_RULE)
- Duration: 7 minutes
- P&L per share: -$1.47 (-0.90%)

**Decision Path**:
```
Bar 348: LONG check - price=$162.58 vs resistance=$162.33 ✅
         Confirmation: MOMENTUM_BREAKOUT (2.7x vol, 0.2% candle)
         Breakout Type: MOMENTUM
         
ENTRY @ $162.58, stop=$160.63 (ATR: 2.2%)

Position Management:
- No partials taken
- Hit 7MIN_RULE at $161.28
- Lost -$1.47/share in 7 minutes
```

**What Went Wrong**:
- Strong volume (2.7x) but move failed immediately
- 0.2% candle was at minimum threshold
- Quick reversal after entry
- 7-minute rule prevented larger loss
- Stop at $160.63 would have been hit anyway

**Lesson**: Volume alone doesn't guarantee success - this had 2.7x volume but still failed

---

### 2. AMAT LONG - -$180.79

**Details**:
- Entry: 10:02 @ $170.14 (226 shares)
- Exit: 14:09 @ $169.35 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.80/share (-0.47%)

**Issue**: Quick 7-min exit, no momentum follow-through

---

### 3. BBBY LONG - -$170.58

**Details**:
- Entry: 09:59 @ $10.59 (1000 shares)
- Exit: 14:06 @ $10.43 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.17/share (-1.61%)

**Issue**: Largest percentage loss of top losers

---

### 4. C LONG - -$153.96

**Details**:
- Entry: 10:00 @ $100.00 (385 shares)
- Exit: 14:07 @ $99.61 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.40/share (-0.40%)

---

### 5. XPEV LONG - -$151.66

**Details**:
- Entry: 10:46 @ $21.68 (1000 shares)
- Exit: 14:53 @ $21.54 (7MIN_RULE)
- Duration: 7 minutes
- Loss: -$0.15/share (-0.70%)

---

## 📉 Exit Reason Analysis

### 7MIN_RULE - 51 trades (83.6%)
- **Win Rate**: 13.7% (7 winners, 44 losers)
- **Total P&L**: -$3,516.20
- **Avg P&L**: -$68.95

**Observation**: Vast majority of trades hitting 7-minute rule = insufficient momentum or quick reversals.

### TRAIL_STOP - 9 trades (14.8%)
- **Win Rate**: 44.4% (4 winners, 5 losers)
- **Total P&L**: $383.69
- **Avg P&L**: $42.63

**Observation**: Trailing stops = better outcomes! These are positions that had enough strength to survive initial 7 minutes.

### EOD - 1 trade (1.6%)
- **Win Rate**: 100% (1 winner, 0 losers)
- **Total P&L**: $43.57
- **Avg P&L**: $43.57

**Observation**: NIO LONG held all day successfully.

---

## 📊 Stock-by-Stock Performance (Top 10)

| Symbol | Trades | Winners | Total P&L | Avg P&L | Notes |
|--------|--------|---------|-----------|---------|-------|
| **INTC** | 2 | 1/2 | $247.59 | $123.79 | Best performer |
| **LCID** | 2 | 1/2 | $91.27 | $45.64 | Strong |
| **NIO** | 1 | 1/1 | $43.57 | $43.57 | EOD hold |
| **JD** | 1 | 1/1 | $16.48 | $16.48 | Short winner |
| **RBLX** | 2 | 1/2 | $11.98 | $5.99 | Neutral |
| **AMC** | 2 | 0/2 | -$22.52 | -$11.26 | - |
| **GME** | 2 | 1/2 | -$30.69 | -$15.34 | - |
| **CLOV** | 2 | 0/2 | -$36.21 | -$18.10 | - |
| ... | ... | ... | ... | ... | ... |
| **QCOM** | 1 | 0/1 | -$347.53 | -$347.53 | Worst |

---

## 🔍 Key Insights

### What Worked ✅

1. **Delayed Momentum Detection**:
   - NIO trade caught after 43-minute weak tracking
   - 3.4x volume upgrade triggered entry
   - Resulted in $43.57 winner held until EOD

2. **Trail Stop Exits**:
   - 44.4% win rate vs 13.7% for 7MIN_RULE
   - Avg $42.63 profit vs -$68.95 loss
   - Letting winners run = better outcomes

3. **Multiple Partials**:
   - RBLX: 4 partials
   - NIO: 4 partials
   - LCID: 3 partials
   - ARM: 3 partials
   - Scaling out protected profits

4. **Room-to-Run Filter**:
   - Blocked 179 entries with <1.5% room
   - Prevented entries where move already consumed
   - Examples: TSLA at -3.58% room (already past target)

### What Didn't Work ❌

1. **83.6% of trades hit 7-minute rule**:
   - Only 13.7% win rate on 7MIN exits
   - Avg loss -$68.95 per trade
   - **Issue**: Entries not developing momentum quickly enough

2. **Low overall win rate (19.7%)**:
   - Only 12 winners out of 61 trades
   - **Issue**: Too many weak entries still getting through

3. **Lunch hour trades (12:00-13:00)**:
   - 0% win rate (0/5)
   - All 5 trades losers
   - **Suggestion**: Consider avoiding lunch consolidation period

4. **Volume ≠ Success**:
   - QCOM had 2.7x volume, still lost -$347.53
   - **Lesson**: Volume alone insufficient, need follow-through

---

## 🎯 Recommendations

### Immediate Actions

1. **Add Time-of-Day Filter**:
   - Avoid entries 12:00-13:00 ET (lunch hour)
   - 0% win rate observed during this period
   - Save ~$195 per day

2. **Strengthen Momentum Criteria**:
   - Current: 2.0x volume + 0.3% candle
   - Consider: Require sustained momentum (2+ candles)
   - QCOM example: Strong volume but immediate failure

3. **Increase Room-to-Run Minimum**:
   - Current: 1.5% minimum
   - Consider: 2.0% minimum
   - May reduce marginal entries

### Further Analysis Needed

1. **Compare to Oct 14**:
   - Oct 14 had C (0.30% room) and WFC (0.68% room) losses
   - Sept 15 had 179 blocked entries
   - **Question**: Did filter prevent those types of losses?

2. **Directional Volume Effectiveness**:
   - 0 blocks on Sept 15
   - Need to test on days with counter-trend volume spikes
   - Run Oct 14 backtest to validate

3. **7-Minute Rule Threshold**:
   - 83.6% of trades hitting this
   - **Question**: Is 7 minutes too aggressive?
   - Consider 10-minute threshold testing

---

## 📈 Comparison to Previous Results

| Metric | Sept 15, 2025 | Oct 14, 2025 (Pre-Filter) |
|--------|---------------|---------------------------|
| Total Trades | 61 | Unknown |
| Win Rate | 19.7% | Unknown |
| Total P&L | -$3,088.95 | -$1,680 (est) |
| Room Blocks | 179 | 0 |
| Directional Blocks | 0 | 0 |

**Need**: Run Oct 14 backtest with same filters to compare effectiveness.

---

## ✅ Filter Validation

### Room-to-Run Filter
**Status**: ✅ Working perfectly

**Evidence**:
- 179 entries blocked successfully
- Examples show filter catching entries past target
- TSLA -3.58% room = already consumed move
- LYFT 0.87% room = insufficient opportunity

**Conclusion**: Filter is functioning as designed and preventing low-opportunity entries.

### Directional Volume Filter
**Status**: ✅ Integrated, no violations on Sept 15

**Evidence**:
- 0 blocks on this day
- Filter code confirmed present in logs
- No counter-trend volume spikes detected

**Next Step**: Test on day with counter-trend moves (Oct 14 backtest).

---

## 🔧 Technical Notes

### Logging
- **Log File**: `backtest_20250915_194459.log` (65MB, 364,744 lines)
- **Filter Visibility**: ✅ Excellent - can see every decision
- **Bar-Level Detail**: ✅ Complete entry path analysis available

### Entry Paths Used
1. **MOMENTUM_BREAKOUT**: Immediate entry (INTC, QCOM)
2. **MOMENTUM_BREAKOUT (delayed)**: Upgraded after tracking (NIO) ⭐
3. **PULLBACK/RETEST**: Not seen on Sept 15
4. **SUSTAINED_BREAK**: Not seen on Sept 15

---

## 📝 Conclusions

1. **Filters are working**: Room-to-run blocked 179 entries successfully
2. **Delayed momentum detection working**: NIO trade proves concept
3. **Win rate still low**: 19.7% suggests more filtering needed
4. **7-minute rule dominant**: 83.6% of trades = insufficient follow-through
5. **Trail stops = winners**: 44.4% win rate when trades survive 7 minutes
6. **Lunch hour avoid**: 0% win rate 12:00-13:00 ET

**Next Steps**:
1. Run Oct 14 backtest with filters
2. Add lunch hour time filter
3. Consider stricter momentum requirements
4. Analyze 7-minute vs 10-minute threshold

---

**Generated**: October 14, 2025  
**Analysis By**: Backtester with Room-to-Run + Directional Volume Filters
