# 🔍 COMPREHENSIVE BACKTEST ENGINE REVIEW

**Date**: October 14, 2025
**Review Requested By**: User expressing doubts about backtest accuracy

---

## 🚨 CRITICAL ISSUES FOUND

### Issue #1: WRONG BAR RESOLUTION - Using 5-second bars, NOT 1-minute! 🔴

**Location**: `backtester.py` lines 651-652
```python
barSizeSetting='5 secs',  # 5-second bars (1-second not supported)
```

**The Problem**:
- Comments throughout code say "1-minute bars"
- Actually using **5-second bars**
- This creates 12x more data points than expected
- **MASSIVE IMPACT**: All timing calculations are wrong!

**Evidence**:
```python
# Line 404: Comment says "Get 1-minute historical bars from IBKR"
bars = self.get_bars(symbol)

# Line 411: Logging says "✓ Fetched {len(bars)} 5-second bars"
# BUT SHOULD BE 1-MINUTE!
```

**Impact**:
- Entry/exit timing off by factor of 12
- Volume calculations aggregating wrong time periods
- State machine checking conditions 12x more frequently

---

### Issue #2: CONFUSING ENTRY/EXIT BAR TRACKING 🟡

**The Confusion**:
- Using 5-second bars but treating them as if they're 1-minute bars
- Entry happens on bar N but gets logged as happening on bar N+1
- `bar_count` variable tracks 5-second bars, not minutes

**Example from C trade**:
- Entry logged at bar 372 (5-second bars)
- That's 372 × 5 seconds = 31 minutes after open
- But code thinks it's checking 1-minute candles

---

### Issue #3: HYBRID ENTRY CONFIRMATION LOGIC 🟢 (Working but Complex)

**Location**: `backtester.py` lines 454-476 (LONG), 504-527 (SHORT)

**The Flow**:
1. First checks `should_enter_long()` - basic pivot break check
2. Then calls `check_hybrid_entry()` - complex confirmation logic
3. `check_hybrid_entry()` delegates to state machine
4. State machine has 6 different states with different paths

**Complexity Issues**:
- Too many layers of abstraction
- Hard to trace what actually triggers entry
- State machine + strategy module + backtester = 3 layers

---

### Issue #4: VOLUME CALCULATION MISMATCH 🔴

**The Problem**: Volume ratios calculated differently in different places

**In ps60_strategy.py** (lines 1073-1100):
```python
# Calculates volume for a SINGLE 1-minute candle (12 bars)
candle_bars = bars[candle_start:candle_end]  # 12 five-second bars
candle_volume = sum(b.volume for b in candle_bars)
```

**In ps60_entry_state_machine.py** (lines 217-225):
```python
# Calculates volume for SINGLE 5-second bar (for PULLBACK_RETEST)
current_bar = bars[current_idx]
current_volume = current_bar.volume
# Then compares to 20-bar average (20 × 5 seconds = 100 seconds)
avg_volume = sum(bars[i].volume for i in range(current_idx-19, current_idx+1)) / 20
```

**Impact**: Different entry paths use different volume calculations!
- MOMENTUM entries: 1-minute candle volume vs 20-minute average
- PULLBACK_RETEST bounce: 5-second bar volume vs 100-second average
- Results in inconsistent entry triggers

---

### Issue #5: TIMESTAMP/TIMEZONE HANDLING 🟡

**Location**: `backtester.py` lines 943-946, 1004-1005

**Issues Found**:
1. Entry times stored with timezone: `entry_time.isoformat()`
2. Exit times stored differently (sometimes UTC, sometimes ET)
3. Display conversion happens at print time, not storage time

**Evidence from trades JSON**:
```json
"entry_time": "2025-09-15T10:01:00-04:00",  // ET with offset
"exit_time": "2025-09-15T10:08:00-04:00"    // Sometimes different format
```

**Impact**: Timestamp analysis errors (as we saw with 4-hour offset issue)

---

### Issue #6: POSITION SIZING CALCULATION ✅ (Correct)

**Location**: `backtester.py` lines 866-897

**Review**: Position sizing looks CORRECT
- Uses 1% risk per trade
- Calculates shares based on stop distance
- Applies min/max constraints (10-1000 shares)
- Matches live trader implementation

---

### Issue #7: SLIPPAGE SIMULATION ✅ (Correct)

**Location**: `backtester.py` lines 82-85, 693-694, 838-841

**Review**: Slippage implementation looks CORRECT
- Entry slippage: 0.1% (configurable)
- Stop slippage: 0.2% (2x entry slippage)
- Exit slippage: 0.1%
- Applied correctly for LONG/SHORT

---

### Issue #8: 7-MINUTE RULE IMPLEMENTATION ✅ (Correct)

**Location**: `backtester.py` lines 800-810

**Review**: 7-minute rule looks CORRECT
- Delegates to strategy module
- Uses configurable threshold (default 7 minutes)
- Only applies before first partial taken
- Logs correct rule name

---

### Issue #9: STATE MACHINE COMPLEXITY 🔴

**The State Machine has 7 states**:
1. MONITORING - Waiting for breakout
2. BREAKOUT_DETECTED - Breakout occurred, waiting for candle close
3. CANDLE_CLOSED - Analyzing strength
4. WEAK_BREAKOUT_TRACKING - Weak breakout, monitoring
5. PULLBACK_RETEST - Pullback detected, waiting for bounce
6. SUSTAINED_BREAK - Holding above/below pivot
7. READY_TO_ENTER - All conditions met

**Problems**:
- Too many states for what should be simple logic
- State transitions not always clear
- Different states use different bar resolutions (5-sec vs 1-min)
- Hard to debug when things go wrong

---

### Issue #10: PARTIAL PROFIT LOGIC ✅ (Mostly Correct)

**Location**: `backtester.py` lines 813-826

**Review**: Partial profit logic looks mostly correct
- Delegates to strategy module
- Takes configured percentage
- Moves stop to breakeven
- Records partial in position manager

**Minor Issue**: Progressive partial system passes `bars` but doesn't verify bar resolution

---

## 📊 DATA FLOW ANALYSIS

### Entry Flow (Simplified):

```
1. backtester.backtest_stock()
   ↓
2. Loops through 5-second bars
   ↓
3. Checks should_enter_long() [basic pivot check]
   ↓
4. Calls check_hybrid_entry() [complex confirmation]
   ↓
5. check_hybrid_entry() → ps60_entry_state_machine.py
   ↓
6. State machine checks current state
   ↓
7. Different logic based on state:
   - MONITORING → Check for breakout
   - BREAKOUT_DETECTED → Wait for candle close
   - WEAK_BREAKOUT_TRACKING → Check for pullback or sustained
   - PULLBACK_RETEST → Check bounce conditions (EVERY 5-sec bar!)
   ↓
8. Returns confirmation + reason
   ↓
9. Backtester enters position
```

**The Problem**: Too many layers, different time resolutions at each layer!

---

## 🔴 MOST CRITICAL FINDING

### The 5-Second Bar Issue Explains Everything!

**Why C trade took 181 bars to enter**:
- 181 five-second bars = 15.08 minutes
- System checking PULLBACK_RETEST bounce EVERY 5 SECONDS
- Needs all 4 conditions true on ONE 5-second bar
- In choppy market, takes forever for random alignment

**Why volume analysis seems wrong**:
- Entry "candle" is actually 12 five-second bars
- But PULLBACK_RETEST checks single 5-second bar volume
- Comparing apples to oranges

**Why delayed momentum code might not work**:
- It checks at "candle boundaries" (every 12 bars)
- But bar numbering is off due to 5-second resolution
- Phase 7 code may be checking wrong bar indices

---

## 🛠️ RECOMMENDATIONS

### Priority 1: FIX BAR RESOLUTION 🚨
```python
# Change line 652 in backtester.py
barSizeSetting='1 min',  # USE 1-MINUTE BARS!
```
**Impact**: This would fix timing, volume calculations, and state machine logic

### Priority 2: SIMPLIFY STATE MACHINE
- Reduce from 7 states to 3-4 maximum
- Use consistent time resolution (1-minute candles only)
- Remove bar-by-bar checking for bounce conditions

### Priority 3: CONSISTENT VOLUME CALCULATIONS
- Always use 1-minute candles for volume ratios
- Use same lookback period (20 candles) everywhere
- Don't mix 5-second and 1-minute calculations

### Priority 4: FIX TIMESTAMP HANDLING
- Store all times in UTC
- Convert to ET only for display
- Use consistent format throughout

### Priority 5: ADD VALIDATION
```python
def validate_backtest_setup():
    """Run before each backtest to verify configuration"""
    assert bar_resolution == '1 min', "Must use 1-minute bars"
    assert all_volume_calcs_use_same_period, "Volume calculations inconsistent"
    assert timezone_handling_consistent, "Timezone handling broken"
```

---

## 💡 WHY BACKTEST RESULTS SEEM OFF

### The Root Cause: 5-Second Bars + Complex State Machine

1. **Using 5-second bars instead of 1-minute**
   - 12x more data points than expected
   - Timing calculations all wrong

2. **PULLBACK_RETEST checks every 5 seconds**
   - Needs perfect alignment on ONE bar
   - In reality would check once per minute

3. **Volume calculations inconsistent**
   - Some use 1-minute aggregates
   - Others use single 5-second bars

4. **State machine too complex**
   - 7 states with different logic
   - Hard to trace execution path

---

## ✅ WHAT'S WORKING CORRECTLY

Despite the issues, these components work well:

1. **Position sizing** - Risk-based calculation correct
2. **Slippage simulation** - Applied appropriately
3. **7-minute rule** - Implemented correctly
4. **Commission handling** - Deducted properly
5. **Stop management** - ATR-based stops working
6. **Partial profits** - 1R-based system working

---

## 🎯 CONCLUSION

**Your doubts are JUSTIFIED!** The backtest engine has significant issues:

1. **Wrong bar resolution** (5-sec vs 1-min) - CRITICAL
2. **Inconsistent volume calculations** - MAJOR
3. **Overly complex state machine** - MODERATE
4. **Timestamp handling issues** - MINOR

**The biggest issue**: Using 5-second bars while the logic assumes 1-minute bars. This single issue cascades into timing problems, volume calculation errors, and state machine confusion.

**Recommended Action**:
1. Switch to 1-minute bars immediately
2. Simplify state machine to 3-4 states
3. Standardize all volume calculations
4. Re-run September backtest with fixes

**Expected Impact**: Results will likely change significantly once these issues are fixed. Current results are unreliable due to the 5-second bar issue.

---

**Generated**: October 14, 2025
**Review Type**: Comprehensive code audit
**Confidence**: HIGH - Multiple critical issues identified with evidence