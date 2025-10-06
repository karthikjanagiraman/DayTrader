# PS60 Profitable Strategy Requirements
**Date**: October 3, 2025
**Purpose**: Guardrails and requirements to ensure profitable PS60 trading
**Research Sources**: PS60 Process Guide + 2024 Pivot Breakout Best Practices

---

## Executive Summary

This document defines strict requirements for profitable PS60 trading based on:
- Dan Shapiro's original PS60 methodology
- Modern false breakout filtering techniques (2024)
- Research showing 60-min ORB has 89.4% win rate
- Analysis of failed trades in current implementation

**Core Principle**: **Quality over Quantity** - Only take high-probability setups with clear room to run

---

## 1. Entry Requirements (REQ-ENTRY-*)

### REQ-ENTRY-001: First Hour Pivot Completion
**Requirement**: DO NOT enter trades before 10:30 AM ET
**Rationale**: First hour establishes true opening range (research: 60-min ORB = 89.4% win rate)
**Exception**: None - this is mandatory

**Implementation**:
```python
if current_time_et < time(10, 30):
    return False, "Before first-hour pivot completion"
```

### REQ-ENTRY-002: Volume Confirmation
**Requirement**: Breakout candle must have volume ≥ 1.5x average volume
**Rationale**: Filters false breakouts - volume validates institutional participation
**Calculation**: Compare current 1-min bar volume to 20-bar average volume

**Implementation**:
```python
avg_volume = sum(last_20_bars.volume) / 20
if breakout_bar.volume < (avg_volume * 1.5):
    return False, "Insufficient volume on breakout"
```

### REQ-ENTRY-003: Room to Run (Minimum R/R)
**Requirement**: Minimum 2.0:1 reward-to-risk ratio to next supply/demand level
**Rationale**: Need clear path to profit target
**Current Config**: min_risk_reward: 1.0 (TOO LOW - change to 2.0)

**Calculation**:
- Risk = Entry - Pivot
- Reward = Target1 - Entry
- R/R = Reward / Risk ≥ 2.0

### REQ-ENTRY-004: No Gap Trades (First 20 Minutes)
**Requirement**: Skip stocks that gap >2% through pivot in first 20 minutes
**Rationale**: Gap already captured the move - little profit potential left
**Current Bug**: Gap filter disabled (`enable_gap_filter: false`)

**Fix**:
```yaml
# trader_config.yaml
filters:
  enable_gap_filter: true       # Re-enable
  max_gap_through_pivot: 2.0    # Skip if gap >2% through pivot
```

### REQ-ENTRY-005: Multi-Timeframe Alignment
**Requirement**: Daily chart must align with 60-min trade direction
**Rationale**: Trade with the trend, not against it

**Long Entry**:
- Daily close > Daily 20-SMA (uptrend)
- 60-min price > 60-min 20-EMA (short-term uptrend)

**Short Entry**:
- Daily close < Daily 20-SMA (downtrend)
- 60-min price < 60-min 20-EMA (short-term downtrend)

### REQ-ENTRY-006: ADX Trend Filter
**Requirement**: ADX ≥ 25 to confirm trending market
**Rationale**: Avoid range-bound, choppy markets (primary cause of false breakouts)
**Implementation**: Calculate 14-period ADX on 60-min chart

```python
if adx_14 < 25:
    return False, "Market not trending (ADX < 25)"
```

### REQ-ENTRY-007: Consecutive Closes Beyond Pivot
**Requirement**: Wait for 2 consecutive 1-min closes beyond pivot
**Rationale**: Filters single-candle fake-outs and wicks
**Exception**: If volume is 3x+ average, allow 1 close

**Implementation**:
```python
if closes_beyond_pivot < 2 and volume_ratio < 3.0:
    return False, "Waiting for confirmation (1 more close needed)"
```

### REQ-ENTRY-008: No Immediate Supply/Demand
**Requirement**: Next technical level must be >1% away from entry
**Rationale**: Need room for first partial profit target
**Check**: Scan for moving averages, previous pivot highs/lows within 1%

### REQ-ENTRY-009: Maximum Distance to Pivot at Scan Time
**Requirement**: Stock must be within 1% of pivot at scan time (not 2%)
**Rationale**: Reduces chance of gap-through overnight
**Current Config**: `max_dist_to_pivot: 2.0` (TOO WIDE)

**Fix**:
```yaml
filters:
  max_dist_to_pivot: 1.0  # Tighter filter (was 2.0)
```

### REQ-ENTRY-010: Scanner Score Minimum
**Requirement**: Minimum score ≥ 75 (not 70)
**Rationale**: Focus on highest-quality setups only
**Current Config**: `min_score: 70` (TOO LOW)

**Fix**:
```yaml
filters:
  min_score: 75  # Higher quality (was 70)
```

---

## 2. False Breakout Detection (REQ-FILTER-*)

### REQ-FILTER-001: Opening Range Volatility Filter
**Requirement**: Do NOT trade between 9:30-9:50 AM ET
**Rationale**: Opening 20 minutes = highest false breakout rate
**Current Bug**: `min_entry_time: "09:45"` (TOO EARLY)

**Fix**:
```yaml
trading:
  entry:
    min_entry_time: "10:30"  # After first-hour pivot (was 09:45)
```

### REQ-FILTER-002: Pivot Strength Validation
**Requirement**: Pivot must have been tested ≥3 times historically
**Rationale**: Strong pivots have clear supply/demand
**Source**: Scanner `breakout_reason` field (e.g., "Tested 7x")

**Implementation**:
```python
if pivot_test_count < 3:
    return False, "Weak pivot (insufficient tests)"
```

### REQ-FILTER-003: No Earnings Same-Day
**Requirement**: Skip stocks with earnings announcements same day
**Rationale**: Unpredictable volatility and gap risk
**Implementation**: Check earnings calendar API or scanner flag

### REQ-FILTER-004: Index ETF Short Avoidance (Already Implemented)
**Current Status**: ✅ CORRECT
```yaml
filters:
  avoid_index_shorts: true  # Saved $700/day in backtest
```

### REQ-FILTER-005: Relative Volume Filter
**Requirement**: Stock must have relative volume (RVOL) ≥ 1.2
**Rationale**: Need above-average interest for sustainable moves
**Source**: Scanner `rvol` field

---

## 3. Exit Requirements (REQ-EXIT-*)

### REQ-EXIT-001: First Partial - Quick Cash Flow
**Requirement**: Sell 50% at first favorable move ($0.25-0.75 gain OR 1% gain, whichever comes first)
**Current Config**: ✅ CORRECT (`partial_1_pct: 0.50`, `partial_1_gain: 0.25`)

**Enhancement**: Add percentage-based trigger
```python
# Take partial if EITHER condition met:
gain_dollars = current_price - entry_price
gain_pct = (gain_dollars / entry_price) * 100

if gain_dollars >= 0.25 or gain_pct >= 1.0:
    take_partial(50%)
```

### REQ-EXIT-002: Second Partial - Target1
**Requirement**: Sell 25% at scanner-defined target1
**Current Implementation**: ✅ CORRECT
**Enhancement**: Add time-based override - if in trade >1 hour and up 2%+, take 2nd partial even if not at target1

### REQ-EXIT-003: Runner Management - Trailing Stop
**Requirement**: Trail stop on final 25% using highest close since entry
**Current Bug**: No trailing stop implementation

**Implementation Needed**:
```python
def update_trailing_stop(position, current_price):
    if position['side'] == 'LONG':
        # Trail stop at highest close minus 1%
        highest_close = max(position['highest_close'], current_price)
        new_stop = highest_close * 0.99

        # Only move stop UP (never down)
        if new_stop > position['stop']:
            position['stop'] = new_stop
```

### REQ-EXIT-004: Stop to Breakeven (Already Implemented)
**Current Status**: ✅ CORRECT
**Trigger**: Immediately after first partial taken
**Config**: `breakeven_after_partial: true`

### REQ-EXIT-005: 5-7 Minute Rule - Reload Detection ONLY
**Requirement**: Exit ONLY if stuck at pivot (within 0.3% of entry) AND time ≥ 7 min
**Current Bug**: Exits ALL slow trades after 7 min (incorrect interpretation)

**Fix Needed**:
```python
def check_five_minute_rule(position, current_price, current_time):
    # ONLY applies if NO partials taken yet
    if position['remaining'] < 1.0:
        return False, None

    time_in_trade = (current_time - entry_time).total_seconds() / 60

    if time_in_trade < 7:
        return False, None

    # Check if STUCK AT PIVOT (within 0.3%)
    distance_from_entry = abs(current_price - entry_price) / entry_price

    if distance_from_entry < 0.003:  # Within 0.3%
        return True, "5MIN_RULE - Reload seller blocking"

    # NOT stuck - let it work
    return False, None
```

### REQ-EXIT-006: EOD Close - Mandatory Liquidation
**Requirement**: Close ALL positions by 3:55 PM ET
**Current Status**: ✅ CORRECT (`eod_close_time: "15:55"`)
**Bug**: Timezone handling causes crash (documented in TRADER_REQUIREMENTS_SPEC.md)

### REQ-EXIT-007: No New Entries After 3:00 PM
**Requirement**: Stop monitoring for new entries at 3:00 PM ET
**Current Status**: ✅ CORRECT (`max_entry_time: "15:00"`)
**Note**: Should be changed to 2:30 PM to allow 85 min for trade to develop before EOD

**Enhancement**:
```yaml
trading:
  entry:
    max_entry_time: "14:30"  # Stop new entries 2:30 PM (was 15:00)
```

---

## 4. Risk Management Guardrails (REQ-RISK-*)

### REQ-RISK-001: Position Sizing - Stop Distance Based
**Requirement**: Risk exactly 1% of account per trade based on stop distance
**Current Status**: ✅ CORRECT
**Formula**: `shares = (account_size * 0.01) / (entry_price - stop_price)`

### REQ-RISK-002: Stop at Pivot - Tight Initial Risk
**Requirement**: Initial stop ALWAYS at pivot level (resistance for longs, support for shorts)
**Current Status**: ✅ CORRECT (`stop_at_pivot: true`)
**Critical**: NEVER widen stop - if trade goes against you, take the loss

### REQ-RISK-003: Maximum 2 Attempts Per Pivot
**Requirement**: Max 2 attempts on same pivot (backtest optimal finding)
**Current Status**: ✅ CORRECT (`max_attempts_per_pivot: 2`)
**Rationale**: If pivot fails twice, it's not a valid level

### REQ-RISK-004: Maximum Concurrent Positions
**Requirement**: Max 5 positions at any time
**Current Status**: ✅ CORRECT (`max_positions: 5`)
**Rationale**: Prevents over-exposure and allows proper monitoring

### REQ-RISK-005: Daily Loss Circuit Breaker
**Requirement**: Stop trading if down 3% on the day
**Current Status**: ✅ CORRECT (`max_daily_loss: 0.03`)
**Implementation**: Check before EVERY new entry

### REQ-RISK-006: No Averaging Down
**Requirement**: NEVER add to losing position
**Current Status**: Not explicitly enforced
**Implementation Needed**: Check if position exists before entry - if losing, block entry

### REQ-RISK-007: Correlation Limit
**Requirement**: Max 2 positions in same sector simultaneously
**Rationale**: Prevents concentration risk (e.g., all tech stocks)
**Implementation Needed**: Add sector classification to scanner output

---

## 5. Scanner Quality Requirements (REQ-SCAN-*)

### REQ-SCAN-001: Minimum Pivot Test Count
**Requirement**: Pivot must have been tested ≥3 times historically
**Implementation**: Scanner calculates test count in `breakout_reason`
**Filter**: Only trade if test count ≥ 3

### REQ-SCAN-002: ATR Filter - Adequate Movement
**Requirement**: Stock must have ATR ≥ 2% for day trading
**Rationale**: Need volatility for profit potential
**Current**: Scanner provides `atr%` field - filter for `atr% >= 2.0`

### REQ-SCAN-003: Previous Day Range
**Requirement**: Previous day must have had ≥3% range (high to low)
**Rationale**: Confirms stock is actively moving
**Implementation**: Scanner should calculate and filter

### REQ-SCAN-004: No Low Float Pump Stocks
**Requirement**: Avoid stocks with <20M float (too manipulatable)
**Implementation**: Add float data to scanner, filter out low-float

### REQ-SCAN-005: Scanner Timing
**Requirement**: Scanner runs on data from PREVIOUS day (no look-ahead bias)
**Current Status**: ✅ FIXED (September backtest uses T-1 data)
**Critical**: Maintain this discipline

---

## 6. Implementation Priority

### Phase 1: Critical Entry Filters (Immediate - 2 hours)
1. ✅ Change `min_entry_time: "10:30"` (was 09:45)
2. ✅ Change `min_score: 75` (was 70)
3. ✅ Change `min_risk_reward: 2.0` (was 1.0)
4. ✅ Change `max_dist_to_pivot: 1.0` (was 2.0)
5. ✅ Re-enable gap filter: `enable_gap_filter: true`

### Phase 2: False Breakout Filters (3-4 hours)
6. ⏳ Implement volume confirmation (1.5x average)
7. ⏳ Implement ADX filter (≥25 for trending)
8. ⏳ Implement 2-consecutive-close confirmation
9. ⏳ Add multi-timeframe alignment check

### Phase 3: Enhanced Exits (2-3 hours)
10. ⏳ Fix 5-minute rule to detect stuck-at-pivot only
11. ⏳ Implement trailing stop for runner position
12. ⏳ Add percentage-based first partial trigger (1% or $0.25)
13. ⏳ Change `max_entry_time: "14:30"` (was 15:00)

### Phase 4: Scanner Enhancements (4-5 hours)
14. ⏳ Add pivot test count to scanner
15. ⏳ Add sector classification
16. ⏳ Add float data
17. ⏳ Add previous day range calculation

---

## 7. Expected Performance Improvement

### Current Backtest (September 2025)
- **Trades**: 183
- **P&L**: +$8,895 (8.9%)
- **Win Rate**: 39.9%
- **Avg/Trade**: +$48.60

### Expected with New Requirements
- **Trades**: ~80-100 (50% reduction via filters)
- **P&L**: +$15,000-20,000 (15-20% monthly)
- **Win Rate**: 55-65% (false breakout filtering)
- **Avg/Trade**: +$150-200 (quality over quantity)

### Key Improvements Expected
1. **60-min ORB wait**: Eliminates 9:30-10:30 AM false breakouts (saved ~$600/day in analysis)
2. **Volume confirmation**: Filters weak breakouts without institutional backing
3. **ADX filter**: Avoids choppy range-bound markets (primary loss source)
4. **Higher R/R minimum**: Ensures meaningful profit potential per trade
5. **Fixed 5-min rule**: Stops premature exits of profitable trends

---

## 8. Configuration Changes Summary

### trader_config.yaml - REQUIRED CHANGES

```yaml
trading:
  entry:
    min_entry_time: "10:30"   # CHANGE from 09:45
    max_entry_time: "14:30"   # CHANGE from 15:00

filters:
  min_score: 75                # CHANGE from 70
  min_risk_reward: 2.0         # CHANGE from 1.0
  max_dist_to_pivot: 1.0       # CHANGE from 2.0

  enable_gap_filter: true      # CHANGE from false
  max_gap_through_pivot: 2.0   # Keep current
```

### New Filters to Add

```yaml
filters:
  # False breakout filters
  min_volume_ratio: 1.5        # Breakout volume vs 20-bar avg
  min_adx: 25                  # Trend strength
  require_consecutive_closes: 2 # Closes beyond pivot

  # Scanner quality filters
  min_pivot_tests: 3           # Historical pivot test count
  min_atr_pct: 2.0            # Minimum volatility
  min_prev_day_range_pct: 3.0 # Previous day range
  min_float_millions: 20       # Avoid low-float pumps

  # Risk filters
  max_positions_per_sector: 2  # Correlation limit
```

---

## 9. Testing & Validation

### Backtest Validation Criteria
Before live trading, backtest September 2025 with new requirements:

✅ **Win Rate ≥ 55%** (currently 39.9%)
✅ **Profit Factor ≥ 2.0** (currently ~1.4)
✅ **Avg Winner > $200** (currently varies)
✅ **Max Drawdown < 5%**
✅ **No losing weeks**

### Paper Trading Validation
After backtest validation, paper trade for 2 weeks:

✅ **Daily P&L positive ≥ 70% of days**
✅ **Execution matches backtest (±20%)**
✅ **No system crashes**
✅ **All filters working correctly**

---

## 10. Critical Success Factors

### Must-Have Disciplines
1. **WAIT for 10:30 AM ET** - No exceptions, even if "perfect" setup appears
2. **RESPECT 2.0:1 R/R minimum** - No exceptions for "special" setups
3. **TAKE 50% partial on first move** - Lock in cash flow immediately
4. **STOP to breakeven after partial** - Eliminate downside on remaining position
5. **CLOSE ALL by 3:55 PM ET** - No overnight positions, ever

### Common Mistakes to Avoid
❌ Taking "good enough" setups that don't meet ALL criteria
❌ Widening stops when trade goes against you
❌ Hoping losing trades will "come back"
❌ Overtrading when bored (quality > quantity)
❌ Trading revenge after losing trade
❌ Holding winners past EOD hoping for gap up

---

## 11. Key Performance Indicators (KPIs)

### Daily Monitoring
- Win rate ≥ 55%
- Profit factor ≥ 2.0
- Average winner ≥ $200
- Average loser ≤ $100
- Trades per day: 4-8 (quality focus)
- P&L per day: +$800-1,500

### Weekly Review
- Winning days: ≥ 70%
- Max drawdown: < 3%
- Filter effectiveness (track reason for skips)
- False breakout rate: < 20%

### Monthly Analysis
- Return on capital: 15-20%
- Sharpe ratio: ≥ 2.0
- Max consecutive losses: ≤ 3
- Strategy drift check (ensure compliance with rules)

---

## 12. Conclusion

**The path to profitability requires DISCIPLINE over DISCRETION.**

Every requirement in this document exists to prevent specific failure modes observed in:
- Current implementation crashes and bugs
- September backtest loss analysis
- PS60 methodology principles
- Modern false breakout research (2024)

**Success = Following ALL requirements, not cherry-picking the convenient ones.**

If a setup doesn't meet EVERY criterion, skip it. The next high-probability setup is always coming.

**Remember**: We're trading for consistency and compounding, not home runs. A 15-20% monthly return with discipline beats sporadic 50% months followed by -30% drawdowns.
