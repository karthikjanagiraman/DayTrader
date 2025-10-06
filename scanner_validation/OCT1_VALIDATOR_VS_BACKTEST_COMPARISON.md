# Validator vs Backtest Comparison - October 1, 2025

**Date**: October 5, 2025
**Purpose**: Compare scanner validation results with backtest performance to identify discrepancies

---

## Summary

| Metric | Validator | Backtest (With Filters) | Backtest Gap |
|--------|-----------|------------------------|--------------|
| **Total Breakouts** | 6 longs | 1 long (COIN) | -5 trades |
| **Success Rate** | 50% (3/6) | 100% (1/1) | N/A |
| **Total P&L** | N/A | +$795.99 | N/A |

---

## Stock-by-Stock Comparison

### 1. COIN - ✅ MATCH
**Validator**:
- Broke: YES ($343.44 → max $349.87)
- Outcome: UNCONFIRMED (78.3% to target)
- Target: $351.65

**Backtest**:
- Entry: $345.92 @ 10:05 AM
- Exit: $345.16 @ 11:04 AM (TRAIL_STOP)
- P&L: +$795.99 (+0.25%)
- Took 50% partial @ $348.45

**Analysis**: ✅ Both systems caught this trade

---

### 2. PLTR - ❌ MISMATCH
**Validator**:
- Broke: YES ($182.24 → max $186.28)
- Outcome: SUCCESS (hit target $184.14)
- This was a WINNER that should have been caught

**Backtest**:
- NO TRADE ENTERED
- Breakout time: **9:45 AM** (within entry window!)
- Resistance: $182.24

**Why Missed**:
- First break at exactly 9:45 AM (backtest starts monitoring at 9:45)
- Likely filtered by volume/momentum confirmation requirements
- **Opportunity cost**: Missed winner (would have hit $184.14 target)

---

### 3. TSLA - ❌ MISMATCH (Expected)
**Validator**:
- Broke: YES ($444.77 → max $462.27)
- Outcome: SUCCESS (hit target $450.84)
- Strong move: +$17.50 to max

**Backtest**:
- NO TRADE ENTERED
- Breakout time: **9:36 AM** (BEFORE entry window)
- Entry window: 9:45 AM - 3:00 PM

**Why Missed**:
- Broke resistance at 9:36 AM, **9 minutes before** backtest starts monitoring
- This is by design (config: min_entry_time = 9:45)
- **Opportunity cost**: Missed winner (would have hit $450.84 target)

**Note**: Per config, we avoid first 15 minutes after open (volatility filter)

---

### 4. AMD - ❌ MISMATCH (Expected)
**Validator**:
- Broke: YES ($161.26 → max $164.18)
- Outcome: SUCCESS (hit target $161.97)
- Clean breakout with follow-through

**Backtest**:
- NO TRADE ENTERED
- Breakout time: **9:32 AM** (BEFORE entry window)
- Entry window: 9:45 AM - 3:00 PM

**Why Missed**:
- Broke resistance at 9:32 AM, **13 minutes before** backtest starts monitoring
- This is by design (config: min_entry_time = 9:45)
- **Opportunity cost**: Missed winner (would have hit $161.97 target)

---

### 5. NVDA - ❌ MISMATCH
**Validator**:
- Broke: YES ($187.35 → max $188.14)
- Outcome: FALSE_BREAKOUT (reversed to $187.18)
- This was a LOSER (correctly filtered?)

**Backtest**:
- NO TRADE ENTERED
- Breakout time: **10:36 AM** (within entry window!)
- Resistance: $187.35

**Why Missed**:
- Broke at 10:36 AM (backtest should have caught this)
- Likely filtered by volume/momentum confirmation
- **Good filter**: This was a false breakout, so NOT entering saved a loss

---

### 6. QQQ - ⚠️ WHIPSAW
**Validator**:
- LONG broke: YES ($602.05 → max $603.79)
- LONG outcome: UNCONFIRMED (72.2% to target)
- SHORT broke: YES ($597.22 → min $596.34)
- SHORT outcome: FALSE_BREAKOUT (reversed to $603.29)
- Whipsaw day (broke both directions)

**Backtest**:
- NO TRADE ENTERED
- QQQ is on blacklist (avoid_symbols: QQQ)
- Reason: Index ETFs too choppy

**Why Skipped**:
- QQQ is blacklisted per config (line 121)
- **Good filter**: This was a whipsaw day (both long and short failed)

---

## Opportunity Cost Analysis

### Missed Winners (Entry Window Issue)
- **TSLA**: Broke 9:36 AM → Would have hit $450.84 target ✅
- **AMD**: Broke 9:32 AM → Would have hit $161.97 target ✅

**Total Opportunity Cost**: 2 winners missed due to 9:45 AM entry restriction

### Missed Winners (Confirmation Filter Issue)
- **PLTR**: Broke 9:45 AM → Would have hit $184.14 target ✅

**Total Opportunity Cost**: 1 winner missed due to volume/momentum filters

### Correctly Filtered
- **NVDA**: False breakout (reversed) → Saved a loss ✅
- **QQQ**: Blacklisted choppy index → Saved whipsaw ✅

---

## Configuration Impact

### Entry Time Window (9:45 AM - 3:00 PM)
**Config**: `min_entry_time: "09:45"`

**Impact on Oct 1**:
- Missed 2 winners (TSLA @ 9:36, AMD @ 9:32)
- These were both clean breakouts that hit targets

**Recommendation**:
- Consider earlier start time (9:35 AM or 9:40 AM)?
- OR accept missing early breakouts as cost of avoiding opening volatility
- **Trade-off**: Catch more winners vs avoid false opens

### Volume/Momentum Confirmation
**Config**:
```yaml
confirmation:
  enabled: true
  volume_surge_required: true
  volume_surge_multiplier: 1.2
  momentum_candle_required: true
```

**Impact on Oct 1**:
- Missed 1 winner (PLTR)
- Correctly filtered 1 loser (NVDA)
- Net: Possibly too strict?

**Recommendation**:
- Analyze PLTR breakout candle (was it weak momentum?)
- If PLTR had strong candle/volume, confirmation may be misconfigured
- If PLTR was weak breakout, filters working correctly (got lucky it worked anyway)

---

## Summary & Recommendations

### What Worked
1. ✅ Caught COIN breakout → +$795.99 profit
2. ✅ Filtered NVDA false breakout → Saved loss
3. ✅ Filtered QQQ whipsaw → Saved loss

### What Didn't Work
1. ❌ Missed TSLA (9:36 AM - before entry window)
2. ❌ Missed AMD (9:32 AM - before entry window)
3. ❌ Missed PLTR (9:45 AM - filtered by confirmation)

### Recommendations

**Option 1: Keep Conservative Approach**
- Accept missing early breakouts (TSLA, AMD)
- Investigate PLTR filter (why was it rejected?)
- Current P&L: +$795.99 (1 trade, 100% win rate)
- **Philosophy**: Quality over quantity

**Option 2: Relax Entry Window**
- Change `min_entry_time` from 9:45 to 9:35
- Catch TSLA and AMD (both winners on Oct 1)
- Risk: More exposure to opening volatility
- **Expected P&L**: Higher but more trades

**Option 3: Relax Confirmation Filters**
- Reduce `momentum_candle_required` threshold
- Catch PLTR (winner on Oct 1)
- Risk: More false breakouts (like NVDA)
- **Trade-off**: More winners but also more losers

### Next Steps
1. ✅ Run validator for more days (Sept 23-30)
2. ✅ Compare backtest vs validator across full month
3. ✅ Analyze which filters help vs hurt
4. ⏳ Optimize entry window and confirmation thresholds
5. ⏳ Test Option 2 and Option 3 on historical data

---

**Report generated**: October 5, 2025
**Confidence**: HIGH (based on 1-minute IBKR data)
