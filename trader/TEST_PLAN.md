# Live Trader Test Plan
## October 9, 2025

## Overview

This document defines test cases to verify all Phase 1-3 implementations are working correctly in the live trader before deploying to production.

---

## Phase 1: Minimum Stop Distance Tests

### Test 1.1: Momentum Long Stop Widening
**Setup**: AVGO breakout at $347.61, pivot at $347.10
**Expected Behavior**:
- Base stop (pivot): $347.10 (0.15% below entry)
- Min stop (0.5%): $345.87 (0.5% below entry)
- **Actual stop used**: $345.87 (min of both)
- Stop distance: $1.74 (0.5%)

**Test Steps**:
1. Load scanner with AVGO resistance = $347.10
2. Trigger breakout at $347.61
3. Verify stop order placed at $345.87
4. Verify log shows: "Stop: $345.87 (pivot: $347.10)"

**Pass Criteria**: ✅ Stop placed at $345.87 (widened, not tight pivot)

---

### Test 1.2: Pullback Long Stop Widening
**Setup**: COIN pullback bounce at $391.77, pivot at $390.49
**Expected Behavior**:
- Base stop (pivot): $390.49
- Min stop (0.3%): $390.62 (0.3% below entry)
- **Actual stop used**: $390.49 (min of both - pivot wider!)
- Stop distance: $1.28 (0.33%)

**Test Steps**:
1. Load scanner with COIN resistance = $390.49
2. Trigger pullback bounce at $391.77
3. Verify stop order placed at $390.49
4. Verify entry_reason contains "PULLBACK" or "BOUNCE"

**Pass Criteria**: ✅ Stop placed at $390.49 (0.3% min respected)

---

### Test 1.3: Short Rejection Stop Widening
**Setup**: GS rejection short at $528.42, pivot at $530.14
**Expected Behavior**:
- Base stop (pivot): $530.14 (0.33% above entry)
- Min stop (0.4%): $530.53 (0.4% above entry)
- **Actual stop used**: $530.53 (max of both)
- Stop distance: $2.11 (0.4%)

**Test Steps**:
1. Load scanner with GS support = $530.14
2. Trigger rejection short at $528.42
3. Verify stop order placed at $530.53
4. Verify entry_reason contains "REJECTION"

**Pass Criteria**: ✅ Stop placed at $530.53 (widened, not tight pivot)

---

### Test 1.4: Very Tight Pivot - Widening Saves Trade
**Setup**: Simulated stock with pivot 0.05% from entry
**Expected Behavior**:
- Base stop (pivot): $100.05 (0.05% below $100.10)
- Min stop (0.5%): $99.60 (0.5% below entry)
- **Actual stop used**: $99.60 (widening prevents noise stop)

**Test Steps**:
1. Create test scanner with very tight resistance
2. Trigger breakout
3. Verify stop is widened to 0.5%

**Pass Criteria**: ✅ Stop widened to minimum 0.5%, not placed at tight 0.05% pivot

---

## Phase 2: Momentum Filter Tests

### Test 2.1: Volume Sustainability Filter
**Setup**: Stock breaks pivot with volume spike, but volume drops after
**Expected Behavior**:
- Initial breakout: Strong volume (3x avg)
- Next 3 bars: Volume drops to 0.8x avg
- Result: Entry downgraded from STRONG to WEAK
- Entry: SKIPPED or entered as PULLBACK (not MOMENTUM)

**Test Steps**:
1. Monitor stock with 1-min bar buffer
2. Detect initial breakout with high volume
3. Check next 3 bars have sustained volume
4. Verify entry classification

**Pass Criteria**: ✅ Entry downgraded or skipped when volume not sustained

---

### Test 2.2: Time-of-Day Filter (After 2 PM)
**Setup**: Stock breaks pivot at 2:05 PM ET
**Expected Behavior**:
- Breakout type: Downgraded to WEAK
- Entry: SKIPPED (momentum entries disabled after 2 PM)
- Log: "Momentum downgraded (after 2 PM)"

**Test Steps**:
1. Set system clock to 2:05 PM ET (or use mock)
2. Trigger breakout
3. Verify entry is not taken as MOMENTUM
4. Check log message

**Pass Criteria**: ✅ No MOMENTUM entry after 2 PM

---

### Test 2.3: Time-of-Day Filter (Before 2 PM)
**Setup**: Stock breaks pivot at 1:55 PM ET
**Expected Behavior**:
- Time check: Before 2 PM ✅
- Breakout type: Classified as STRONG (if volume sustained)
- Entry: ALLOWED as MOMENTUM

**Test Steps**:
1. Set system clock to 1:55 PM ET
2. Trigger breakout with sustained volume
3. Verify entry is taken as MOMENTUM

**Pass Criteria**: ✅ MOMENTUM entry allowed before 2 PM cutoff

---

## Phase 3: Pullback Quality Tests

### Test 3.1: Bounce Threshold (0.15%)
**Setup**: COIN pullback, price bounces 0.10% above pivot
**Expected Behavior**:
- Bounce threshold: 0.15% required
- Actual bounce: 0.10%
- Result: Bounce NOT confirmed, entry SKIPPED

**Test Steps**:
1. Load COIN with resistance $390.49
2. Price pulls back to $390.00
3. Price bounces to $390.39 (+0.10%)
4. Verify NO entry (threshold not met)

**Pass Criteria**: ✅ Entry skipped for weak bounce (<0.15%)

---

### Test 3.2: Volume on Bounce Filter
**Setup**: Stock bounces 0.20% but on low volume
**Expected Behavior**:
- Bounce: 0.20% (above 0.15% threshold)
- Volume: 0.8x average (below 1.5x requirement)
- Result: Entry SKIPPED (insufficient volume)

**Test Steps**:
1. Configure bounce with 0.20% move
2. Set bar volume to 0.8x average
3. Verify bounce check fails
4. Check log for volume rejection

**Pass Criteria**: ✅ Entry skipped when bounce volume <1.5x avg

---

### Test 3.3: Rising Price Filter
**Setup**: Stock bounces 0.20% with volume, but price not rising
**Expected Behavior**:
- Bounce: 0.20% ✅
- Volume: 2.0x average ✅
- Price action: Current bar close < previous bar close
- Result: Entry SKIPPED (price not rising)

**Test Steps**:
1. Previous bar close: $100.50
2. Current bar close: $100.40 (lower, despite bounce)
3. Verify bounce check fails
4. Check for "price not rising" in logs

**Pass Criteria**: ✅ Entry skipped when price declining on bounce

---

### Test 3.4: Perfect Pullback Entry
**Setup**: All Phase 3 filters passed
**Expected Behavior**:
- Bounce: 0.20% above pivot ✅
- Volume: 2.0x average ✅
- Price rising: Current > previous ✅
- Result: Entry CONFIRMED as PULLBACK_BOUNCE

**Test Steps**:
1. Configure all parameters correctly
2. Trigger bounce meeting all criteria
3. Verify entry is taken
4. Check entry_reason = "PULLBACK_BOUNCE"

**Pass Criteria**: ✅ Entry taken when all filters pass

---

## Integration Tests

### Test 4.1: October 9 Replay Test
**Goal**: Replay October 9, 2025 trading day and verify P&L matches backtest

**Backtest Results** (Oct 9):
- Total P&L: -$2,774.17
- Trades: 4 (AVGO, GS, BA, COIN)
- Win Rate: 0%

**Expected Live Behavior**:
- Same 4 entries triggered
- Same stop prices (widened by Phase 1)
- P&L within ±5% of backtest (-$2,774)

**Test Steps**:
1. Use Oct 9 scanner results
2. Fetch Oct 9 historical 1-min bars
3. Simulate tick-by-tick replay
4. Compare trades vs backtest
5. Verify Phase 1 stop widening prevented earlier exits

**Pass Criteria**:
- ✅ Same entry triggers
- ✅ Same stop prices (widened)
- ✅ P&L matches backtest ±5%

---

### Test 4.2: Phase 1 Impact Verification
**Goal**: Prove Phase 1 improves P&L by 41%

**Test Setup**:
- Day: October 9, 2025
- WITHOUT Phase 1: P&L = -$4,679.70 (tight stops)
- WITH Phase 1: P&L = -$2,774.17 (widened stops)
- Improvement: +$1,905 (41%)

**Test Steps**:
1. Run live trader WITH Phase 1 enabled
2. Record all stop hits and P&L
3. Manually calculate what P&L would be with tight stops
4. Verify 40%+ improvement from widening

**Pass Criteria**: ✅ Phase 1 prevents at least $1,500 in losses vs tight stops

---

### Test 4.3: State Recovery Test
**Goal**: Verify trader recovers positions correctly after crash/restart

**Test Steps**:
1. Enter COIN long at $391.77
2. Save state file
3. Kill trader process (simulate crash)
4. Restart trader
5. Verify COIN position recovered with:
   - Entry price: $391.77
   - Stop: $390.49
   - Target: $396.56
   - Shares: 774

**Pass Criteria**:
- ✅ Position fully recovered
- ✅ Stop orders re-placed
- ✅ Can continue managing position

---

## Edge Cases

### Test 5.1: Gap Through Pivot
**Setup**: Stock gaps up 2% overnight, opens above resistance
**Expected Behavior**:
- Gap filter detects gap through pivot
- Entry: SKIPPED (or adjusted to new intraday pivot)
- Log: "Gap through pivot detected"

**Pass Criteria**: ✅ Setup skipped when gap invalidates pivot

---

### Test 5.2: Tight Stop Near Min Threshold
**Setup**: Pivot exactly 0.5% below entry (edge case)
**Expected Behavior**:
- Base stop: $99.50 (0.5% below $100)
- Min stop: $99.50 (0.5% minimum)
- Result: Both equal, use $99.50

**Pass Criteria**: ✅ Works correctly when pivot = minimum stop

---

### Test 5.3: Multiple Attempts on Same Pivot
**Setup**: Enter AVGO, stop out, price breaks again
**Expected Behavior**:
- 1st attempt: Entry at $347.61, stop at $345.87
- Stop hits: Exit position
- 2nd attempt: Can re-enter (max 2 attempts allowed)
- 3rd attempt: SKIP (max attempts reached)

**Pass Criteria**: ✅ Respects max 2 attempts per pivot

---

### Test 5.4: EOD Close with Partial Position
**Setup**: 3:55 PM ET, holding 50% runner after partials
**Expected Behavior**:
- Time check: 3:55 PM ET (5 min before close)
- Action: Close ALL remaining positions
- Result: 50% runner liquidated at market

**Pass Criteria**: ✅ All positions flat by 3:55 PM ET (no overnight holds)

---

## Performance Tests

### Test 6.1: Real-Time Bar Processing
**Goal**: Verify 5-second bars update correctly for 17 stocks

**Test Steps**:
1. Subscribe to 17 stocks
2. Monitor bar buffer updates
3. Verify bars arrive every 5 seconds
4. Check for missing bars or delays

**Pass Criteria**:
- ✅ All 17 symbols receive bars
- ✅ Bars arrive within 1 second of expected time
- ✅ No dropped bars over 1 hour period

---

### Test 6.2: Entry Detection Latency
**Goal**: Measure time from pivot break to order placement

**Test Steps**:
1. Trigger breakout at 10:00:00.000
2. Record order placement timestamp
3. Calculate latency

**Pass Criteria**: ✅ Order placed within 500ms of breakout detection

---

### Test 6.3: Stop Order Execution
**Goal**: Verify stop orders execute properly when hit

**Test Steps**:
1. Enter COIN long at $391.77, stop at $390.49
2. Manually or via simulation, move price to $390.48
3. Verify stop order fills
4. Check position is closed

**Pass Criteria**:
- ✅ Stop order triggers at correct price
- ✅ Fill received within 2 seconds
- ✅ Position removed from active positions

---

## Logging & Monitoring Tests

### Test 7.1: Log Output Verification
**Goal**: Ensure logs show all critical information

**Check Log Contains**:
- ✅ Entry: Symbol, price, shares, entry_reason
- ✅ Stop: Both widened stop AND original pivot
- ✅ Risk calculation: Using widened stop
- ✅ Room to target: Percentage calculation
- ✅ Phase 1 comment: "PHASE 1 FIX" present

**Example Expected Log**:
```
🟢 LONG AVGO @ $347.61 (10:05:23 AM ET)
   Entry Path: MOMENTUM_BREAKOUT (strong volume + large candle)
   Shares: 574 | Risk: $1.74 | Room: 2.4%
   Stop: $345.87 (pivot: $347.10) | Target1: $356.21
```

**Pass Criteria**: ✅ All fields present and accurate

---

### Test 7.2: Trade JSON Recording
**Goal**: Verify trades written to JSON correctly

**Check JSON Contains**:
- ✅ Entry timestamp (ET timezone)
- ✅ Entry price and reason
- ✅ Stop price (widened)
- ✅ Exit price and reason
- ✅ P&L calculation
- ✅ Shares traded

**Pass Criteria**: ✅ JSON parseable and complete

---

## Regression Tests

### Test 8.1: Phase 2 Still Works After Phase 1 Addition
**Goal**: Ensure Phase 1 didn't break Phase 2 filters

**Test Steps**:
1. Trigger momentum entry with unsustained volume
2. Verify downgrade to WEAK
3. Trigger entry after 2 PM
4. Verify downgrade to WEAK

**Pass Criteria**: ✅ Phase 2 filters still active and working

---

### Test 8.2: Phase 3 Still Works After Phase 1 Addition
**Goal**: Ensure Phase 1 didn't break Phase 3 filters

**Test Steps**:
1. Trigger bounce with 0.10% move (below 0.15% threshold)
2. Verify entry skipped
3. Trigger bounce with low volume
4. Verify entry skipped
5. Trigger bounce with declining price
6. Verify entry skipped

**Pass Criteria**: ✅ All Phase 3 filters still active and working

---

## Test Execution Plan

### Pre-Production Checklist

**Step 1: Unit Tests** (30 minutes)
- Run Tests 1.1-1.4 (Phase 1 stops)
- Run Tests 3.1-3.4 (Phase 3 filters)

**Step 2: Integration Tests** (2 hours)
- Run Test 4.1 (October 9 replay)
- Run Test 4.2 (Phase 1 impact verification)
- Run Test 4.3 (State recovery)

**Step 3: Edge Cases** (1 hour)
- Run Tests 5.1-5.4 (edge cases)

**Step 4: Live Paper Trading** (1 full day)
- Deploy to paper account
- Monitor all trades
- Verify against backtest expectations
- Check all phases working in real-time

**Step 5: Final Validation** (Review)
- Compare paper trading results to backtest
- Verify P&L within ±30% of backtest
- Confirm all phases operational
- Review logs for errors

---

## Success Criteria for Production Deployment

✅ **Must Pass ALL of the Following**:

1. **Phase 1 Tests**: All stop widening tests pass (Tests 1.1-1.4)
2. **Phase 2 Tests**: Volume and time filters working (Tests 2.1-2.3)
3. **Phase 3 Tests**: Pullback quality filters working (Tests 3.1-3.4)
4. **October 9 Replay**: P&L within ±5% of backtest -$2,774
5. **No Regression**: Phases 2-3 still work after Phase 1 addition
6. **State Recovery**: Positions recovered correctly after restart
7. **Paper Trading**: 1 full day with ≥80% match to backtest behavior
8. **No Critical Bugs**: Zero crashes, no missing stops, no data loss

**If ANY test fails**: Fix issue and re-run full test suite

---

## Known Issues & Workarounds

### Issue 1: Timezone Bug (FIXED)
**Problem**: EOD close using PST instead of ET
**Fix**: Updated to use `datetime.now(pytz.UTC).astimezone(eastern)`
**Status**: ✅ FIXED (Lines 532-543)

### Issue 2: Market Open Wait Bug (FIXED)
**Problem**: `datetime.combine()` causing timezone mismatch
**Fix**: Use `now_et.replace()` for timezone-aware calculations
**Status**: ✅ FIXED (Lines 1153-1154)

### Issue 3: Entry Reason Parsing
**Problem**: Live trader uses string parsing vs backtester's enum
**Workaround**: Both methods equivalent, no issue
**Status**: ✅ OK (Different but correct)

---

## Test Automation (Future)

**Priority**: Medium (after manual validation)

Create automated test suite:
```python
# test_phase1_stops.py
def test_momentum_stop_widening():
    entry = 347.61
    pivot = 347.10
    expected_stop = 345.87  # 0.5% min
    actual_stop = trader.calculate_stop('MOMENTUM', entry, pivot)
    assert actual_stop == expected_stop

def test_pullback_stop_widening():
    entry = 391.77
    pivot = 390.49
    expected_stop = 390.49  # Pivot already > 0.3% min
    actual_stop = trader.calculate_stop('PULLBACK', entry, pivot)
    assert actual_stop == expected_stop
```

---

## Test Results Log

| Test ID | Description | Status | Date | Notes |
|---------|-------------|--------|------|-------|
| 1.1 | Momentum stop widening | ⏳ | - | - |
| 1.2 | Pullback stop widening | ⏳ | - | - |
| 1.3 | Short rejection stop | ⏳ | - | - |
| 1.4 | Very tight pivot | ⏳ | - | - |
| 2.1 | Volume sustainability | ⏳ | - | - |
| 2.2 | Time filter (after 2 PM) | ⏳ | - | - |
| 2.3 | Time filter (before 2 PM) | ⏳ | - | - |
| 3.1 | Bounce threshold 0.15% | ⏳ | - | - |
| 3.2 | Volume on bounce | ⏳ | - | - |
| 3.3 | Rising price filter | ⏳ | - | - |
| 3.4 | Perfect pullback entry | ⏳ | - | - |
| 4.1 | October 9 replay | ⏳ | - | - |
| 4.2 | Phase 1 impact | ⏳ | - | - |
| 4.3 | State recovery | ⏳ | - | - |

**Legend**: ⏳ Pending | ✅ Pass | ❌ Fail

---

**Next Action**: Run Test 4.1 (October 9 replay) to validate full system
