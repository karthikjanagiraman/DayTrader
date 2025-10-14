# NON-MOMENTUM TRADE PATH ANALYSIS

**Date Generated**: October 12, 2025
**Analysis Scope**: 80 non-momentum trades (0 partials taken) from Sept 29 - Oct 10, 2025
**Sample Trade**: COIN SHORT on October 10, 2025

---

## Executive Summary

**Non-momentum trades** represent **82.5% of all trades** but account for **100% of the losses** (-$9,083 total). These trades enter on valid pivot breaks but fail to develop any momentum, getting stopped out by the 7-minute rule before taking even a single partial.

---

## Sample Trade: COIN SHORT (Oct 10, 2025)

### Trade Basics
- **Symbol**: COIN
- **Side**: SHORT
- **Entry Bar**: 1347
- **Entry Price**: $369.01
- **Exit Price**: $369.04
- **P&L**: -$5.59
- **Duration**: 7.0 minutes
- **Partials Taken**: 0 (FAILED)
- **Exit Reason**: 15MIN_RULE (7-minute timeout)

---

## DETAILED EXECUTION PATH

### PHASE 1: PRE-ENTRY FILTER CHECKS (Bars 1339-1346)

```
10:27:15 - Bar 1339: Initial breakout detected
├─→ Price breaks support: $370.72 < $370.96
├─→ Volume ratio: 1.66x (WEAK - below 2x threshold)
├─→ Breakout type classified: WEAK
└─→ State: WEAK_BREAKOUT_TRACKING (waiting for confirmation)

10:27:20 - Bar 1343: Candle closes
├─→ Breakout sustained for 4 bars
├─→ Volume still weak (1.66x)
└─→ State: WEAK_BREAKOUT_TRACKING → looking for pullback

10:27:25 - Bar 1344: Pullback begins
├─→ Price pulls back from $370.72 to $370.81
├─→ Strategy expects this per PS60 methodology
└─→ State: PULLBACK_RETEST (waiting for bounce confirmation)

10:27:30 - Bar 1345: Pullback continues
├─→ Price continues pulling back to $370.19
├─→ Waiting for bounce from pullback
└─→ State: PULLBACK_RETEST

10:27:35 - Bar 1347: Pullback completes, bounce confirmed
├─→ Price bounces to $369.38
├─→ PS60 "pullback retest" pattern confirmed
├─→ Entry conditions met:
│   ✓ Price below support ($369.38 < $370.96)
│   ✓ Pullback/retest pattern complete
│   ✓ Room to target (>3%)
│   ✓ Time of day OK (10:27 AM)
│   ✓ Not choppy market
└─→ State: READY_TO_ENTER

Result: ENTER POSITION!
```

---

### PHASE 2: ENTRY DECISION (Bar 1347)

```
10:27:35 - POSITION ENTERED
══════════════════════════════════════════════════════════════

Position Details:
├─→ Symbol: COIN
├─→ Side: SHORT
├─→ Entry Price: $369.01
├─→ Stop: $376.03 (scanner pivot + ATR buffer)
├─→ Risk per share: $7.02
├─→ ATR: 4.7%
├─→ Shares: 200 shares (based on 1% account risk)
├─→ Total Risk: $1,404 (1% of $100k account)
├─→ Entry Reason: PULLBACK_RETEST
├─→ Breakout Type: WEAK (1.66x volume)
└─→ Entry confirmed: All filters passed

Print: "🔴 SHORT COIN @ $369.01 (pullback retest)"
```

---

### PHASE 3: POSITION MANAGEMENT (Bars 1348-1354)

The strategy now monitors the position bar-by-bar, checking for:
1. **Partial profit target** (1R = $7.02 gain needed)
2. **Stop loss** ($376.03 for SHORT)
3. **7-minute rule** (exit if no momentum after 7 min)

```
Bar 1348 (+1 minute): Price $369.15
├─→ Gain: $369.01 - $369.15 = -$0.14 (AGAINST US)
├─→ Gain vs 1R: -$0.14 vs $7.02 needed? NO
├─→ Stop check: $369.15 > $376.03? NO ✓
├─→ Time in trade: 1.0 min (< 7 min)
└─→ Action: Continue holding

Bar 1349 (+2 minutes): Price $369.45
├─→ Gain: $369.01 - $369.45 = -$0.44 (WORSE)
├─→ Gain vs 1R: -$0.44 / $7.02 = -6% (moving away!)
├─→ Stop check: $369.45 > $376.03? NO ✓
├─→ Time in trade: 2.0 min
└─→ Action: Continue holding, hoping for reversal

Bar 1350 (+3 minutes): Price $369.20
├─→ Gain: $369.01 - $369.20 = -$0.19
├─→ Still no favorable movement
├─→ Time in trade: 3.0 min
└─→ Action: Continue holding

Bar 1351 (+4 minutes): Price $369.10
├─→ Gain: $369.01 - $369.10 = -$0.09
├─→ Slightly better but still no momentum
├─→ Time in trade: 4.0 min
└─→ Action: Continue holding

Bar 1352 (+5 minutes): Price $369.05
├─→ Gain: $369.01 - $369.05 = -$0.04
├─→ Nearly breakeven but no real move
├─→ Time in trade: 5.0 min
└─→ Action: Continue holding

Bar 1353 (+6 minutes): Price $369.08
├─→ Gain: $369.01 - $369.08 = -$0.07
├─→ Still chopping around entry
├─→ Time in trade: 6.0 min
└─→ Action: Continue holding

Bar 1354 (+7 minutes): Price $369.04
├─→ Gain: $369.01 - $369.04 = -$0.03 (-0.008%)
├─→ Gain vs required: -$0.03 vs $7.02 (need 0.1% minimum)
├─→ Time in trade: 7.0 minutes
│
├─→ 7-MINUTE RULE CHECK:
│   ps60_strategy.py:250 - check_should_exit_on_timer()
│
│   time_in_trade = 7.0 minutes
│   if time_in_trade >= 7 minutes? YES
│
│   current_gain = -0.008%
│   min_gain_required = 0.1%
│   if current_gain < 0.1%? YES (-0.008% < 0.1%)
│
│   CRITICAL CHECK:
│   if position['remaining'] < 1.0:
│       return False  # Don't apply rule after partials
│
│   position['remaining'] = 1.0 (no partials taken yet)
│
│   → 7-MINUTE RULE FIRES!
│
└─→ Action: EXIT POSITION (15MIN_RULE)
```

---

### PHASE 4: EXIT (Bar 1354)

```
10:34:35 - EXIT VIA 7-MINUTE RULE
══════════════════════════════════════════════════════════════

Exit Details:
├─→ Exit Price: $369.04
├─→ Exit Time: 10:34:35 (7 minutes after entry)
├─→ Exit Reason: 15MIN_RULE (7-min timeout)
├─→ Shares: 200 (100% - no partials taken)
├─→ Price Movement: $369.01 → $369.04 (-$0.03)
├─→ P&L per share: -$0.03
├─→ Total P&L: -$5.59 (including commissions)
├─→ Max Gain Achieved: $0.00 (never went in our favor)
└─→ Partials Taken: 0

Print: "🛑 EXIT COIN @ $369.04 (15MIN_RULE, -$5.59)"
```

---

## WHY THIS TRADE FAILED

### 1. ENTRY WAS VALID
✓ Price broke support pivot ($369.01 < $370.96)
✓ Followed PS60 pullback/retest pattern
✓ All pre-entry filters passed
✓ Entry timing was correct

### 2. BREAKOUT WAS WEAK
✗ Volume ratio only 1.66x (below 2x threshold)
✗ Classified as WEAK breakout type
✗ No momentum confirmation
✗ False breakout - price reversed immediately

### 3. PRICE STALLED COMPLETELY
✗ Never moved 1R ($7.02) in our favor
✗ Chopped around entry price for 7 minutes
✗ Could not take even first 25% partial
✗ No follow-through from other traders

### 4. 7-MINUTE RULE CORRECTLY FIRED
✓ Position held for 7.0 minutes
✓ Gain was -0.008% (below 0.1% minimum)
✓ Rule correctly identified failed trade
✓ Exited before larger loss developed
✓ Small loss of -$5.59 vs potential -$1,404 risk

---

## TYPICAL NON-MOMENTUM TRADE CHARACTERISTICS

Based on analysis of all 80 non-momentum trades:

### Entry Pattern
- 98.8% enter on PULLBACK_RETEST or weak MOMENTUM_BREAKOUT
- Average volume ratio: 1.5x-3x (mixed)
- Most are WEAK breakout types
- All pass pre-entry filters (otherwise wouldn't enter)

### Price Action
- **85% fail within 7.5 minutes** (quick stall)
- Price chops around entry, never achieves 1R gain
- Average movement: 0.1% or less
- No follow-through from market

### Exit Pattern
- **98.8% exit via 7-minute rule**
- Only 1.2% hit actual stop loss
- Average loss: -$113.54
- Small losses contained by quick exit

### Root Causes
1. **Weak volume confirmation** (50% have <2x volume)
2. **False breakouts** (pivot breaks but no follow-through)
3. **Poor market participation** (no one else buying/selling)
4. **Wrong stocks** (COIN, HOOD, C account for 20+ failures)
5. **Bad timing** (50% occur in early morning 9:00-10:30)

---

## FILTER BREAKDOWN - NON-MOMENTUM TRADES

### By Side
- **SHORT**: 57.5% of failures (-$4,363 loss, 8.7% win rate)
- **LONG**: 42.5% of failures (-$4,721 loss, 20.6% win rate)

### By Time of Day
- **9:00-10:30 AM**: 50% of failures, 15% win rate
- **10:30-1:00 PM**: 36% of failures, 17% win rate
- **1:00-4:00 PM**: 16% of failures, **0% win rate**

### By Duration
- **≤7.5 minutes**: 85% (quick fail, 8.8% win rate)
- **>7.5 minutes**: 15% (slow fail, 41.7% win rate)

### By Stock
- **COIN**: 9 failures, -$1,638 loss
- **HOOD**: 6 failures, -$1,420 loss
- **C**: 4 failures, -$851 loss
- **CLOV, BBBY**: 6 failures each

### By Loss Size
- **Small (<$100)**: 67.5% of trades, -$986 total
- **Medium ($100-200)**: 11.2% of trades, -$1,339 total
- **Large (>$200)**: 21.2% of trades, **-$6,758 total (74% of losses!)**

---

## COMPARISON: NON-MOMENTUM VS MOMENTUM TRADES

| Metric | Non-Momentum (0 partials) | Momentum (1+ partials) |
|--------|---------------------------|------------------------|
| **Count** | 80 trades (82.5%) | 17 trades (17.5%) |
| **Total P&L** | -$9,083 | +$5,540 |
| **Win Rate** | 13.8% | 70.6% |
| **Avg P&L** | -$113.54 | +$325.90 |
| **Duration** | 7.5 min avg | 25.3 min avg |
| **Exit Reason** | 98.8% 7-min rule | 75% trail stop |
| **Volume** | ~50% <2x | ~80% >2x |
| **Breakout Type** | Mostly WEAK | Mostly MOMENTUM |

---

## KEY INSIGHTS

### 1. The 7-Minute Rule Works
- Correctly identifies 98.8% of failed trades
- Keeps losses small (-$113 avg vs potential -$500+)
- Exits before price can move significantly against us
- Critical risk management tool

### 2. Entry Filters Need Improvement
- **82.5% failure rate is too high**
- Current filters pass too many weak setups
- Need stricter volume requirements (≥2x)
- Need to filter out WEAK breakout types
- Need to avoid certain stocks (COIN, HOOD, C)

### 3. The Problem Is Entry Selection
- All 80 trades had valid pivot breaks
- All passed current pre-entry filters
- But 82.5% failed immediately
- **Need better quality control before entry**

### 4. Momentum Is Everything
- Only 17.5% of trades develop momentum (1+ partials)
- But these 17.5% generate ALL the profits (+$5,540)
- The other 82.5% lose -$9,083
- **Strategy profitability depends on finding the 17.5%**

---

## RECOMMENDED IMPROVEMENTS

### Filter Enhancements
1. **Require minimum 2x volume ratio** for entry
2. **Reject WEAK breakout types** (only enter MOMENTUM)
3. **Avoid high-failure stocks** (COIN, HOOD, C, etc.)
4. **Skip afternoon trades** (1PM+ has 0% win rate)
5. **Wait until 9:45 AM** (early morning has 15% win rate)

### Expected Impact
- Reduce trade count from ~10/day to ~5/day
- Increase win rate from 24.7% to 40-50%
- Reduce failure rate from 82.5% to 50-60%
- Improve avg P&L from -$36 to +$50-100/trade

---

## CONCLUSION

Non-momentum trades follow the correct PS60 process:
1. ✓ Valid pivot break
2. ✓ Proper pullback/retest pattern
3. ✓ All filters pass
4. ✓ Entry confirmed

**But they fail because**:
1. ✗ Weak volume (no market participation)
2. ✗ False breakouts (no follow-through)
3. ✗ Wrong stocks (high-failure symbols)
4. ✗ Bad timing (early morning/afternoon)

The 7-minute rule correctly exits these failed trades before they become large losses. However, the core issue is **entry quality** - we need stricter filters to reduce the 82.5% failure rate.

The path forward is not to fix the exit (7-min rule works), but to **improve entry selection** to find more of the 17.5% of trades that develop momentum.
