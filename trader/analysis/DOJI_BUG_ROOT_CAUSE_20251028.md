# DOJI Bug Root Cause Analysis - October 28, 2025

## Executive Summary

**BUG**: Clear GREEN candles (+0.076%, +0.246%) are being misclassified as "DOJI (no winner)", blocking valid SMCI entries.

**ROOT CAUSE**: Candle color validation is checking **5-SECOND BAR** open/close instead of **1-MINUTE CANDLE** open/close.

**IMPACT**: CVD shows strong buying pressure, 1-minute candle is GREEN, but system blocks entry because a single 5-second bar within that minute had minimal movement.

---

## The Bug in Detail

### What the User Saw (IBKR 1-Minute Data)

**11:36 ET - 1-Minute Candle**:
```
Open:   $52.82
Close:  $52.86
Change: +$0.04 (+0.076%)
Type:   GREEN ✅ (buyers won)
```

**11:37 ET - 1-Minute Candle**:
```
Open:   $52.87
Close:  $53.00
Change: +$0.13 (+0.246%)
Type:   GREEN ✅ (buyers won - clear directional move!)
```

### What the System Logged

**08:36:31 (11:36:31 ET) - Bar 131**:
```
CVD Signal: -44.6% imbalance (BULLISH - strong buying pressure)
Buy: 1,944 | Sell: 745
❌ BLOCKED: "CVD BULLISH (-44.59% buying) but DOJI (no winner)"
```

**08:37:32 (11:37:32 ET) - Bar 143**:
```
CVD Signal: -32.1% imbalance (BULLISH - buying pressure)
❌ BLOCKED: "CVD BULLISH but DOJI (no winner)"
```

---

## Code Path Analysis

### Step 1: CVD Monitoring State Machine
**File**: `trader/strategy/ps60_entry_state_machine.py`
**Lines**: 488-629

```python
# STATE 2.1: CVD_MONITORING - Continuous CVD checks
elif state.state.value == 'CVD_MONITORING':
    # At candle close - get CVD data
    try:
        # Get tick data
        ticks = strategy.get_tick_data(symbol, bar_timestamp=timestamp, backtester=effective_backtester)

        # Calculate CVD from ticks
        from indicators.cvd_calculator import CVDCalculator
        calculator = CVDCalculator(...)

        # ❌ BUG HERE: Passes CURRENT 5-SECOND BAR to CVD calculator
        cvd_result = calculator.calculate_auto(bars, current_idx, ticks=ticks)

        # Check candle color alignment
        signals_aligned = cvd_result.signals_aligned  # ← This uses 5-second bar data!
        validation_reason = cvd_result.validation_reason

        if not signals_aligned:
            logger.info(f"❌ CANDLE COLOR CONFLICT - {validation_reason}")
            tracker.reset_state(symbol)
            return False, f"Candle color conflict: {validation_reason}", {...}
```

### Step 2: CVD Calculator Auto Mode
**File**: `trader/indicators/cvd_calculator.py`
**Lines**: 339-372

```python
def calculate_auto(self, bars: List, current_idx: int, ticks: Optional[List] = None) -> CVDResult:
    if ticks and len(ticks) > 0:
        # Use tick data
        logger.info(f"✅ CVD: Using TICK data ({len(ticks)} ticks)")

        # ❌ BUG: Passes CURRENT 5-SECOND BAR for candle color validation
        current_bar = bars[current_idx] if bars and current_idx < len(bars) else None

        return self.calculate_from_ticks(ticks, bar=current_bar)
```

**The Problem**: `bars[current_idx]` returns the **current 5-second bar**, not a 1-minute candle.

### Step 3: Candle Color Validation Logic
**File**: `trader/indicators/cvd_calculator.py`
**Lines**: 166-197

```python
def calculate_from_ticks(self, ticks: List, bar=None) -> CVDResult:
    # ... CVD calculation from ticks ...

    if bar is not None:
        # ❌ BUG: This 'bar' is a 5-SECOND bar, not 1-minute candle!
        bar_open = bar.open
        bar_close = bar.close
        price_change = bar_close - bar_open
        price_change_pct = (price_change / bar_open) * 100

        # Determine candle color
        if price_change > 0:
            price_direction = 'UP'  # Green candle
        elif price_change < 0:
            price_direction = 'DOWN'  # Red candle
        else:
            price_direction = 'NEUTRAL'  # ← DOJI when open == close

        # Check alignment with CVD trend
        if trend == 'BULLISH' and price_direction == 'NEUTRAL':
            signals_aligned = False
            validation_reason = f"CVD BULLISH ({imbalance_pct:+.2f}% buying) but DOJI (no winner)"
```

**The Core Issue**: When `bar` is a 5-second bar:
- A single 5-second bar might have TINY movement (+$0.01)
- Or it might have NO movement (open == close)
- This gets classified as DOJI
- But the 1-MINUTE CANDLE (12 five-second bars aggregated) is clearly GREEN!

---

## Example: 11:36 ET Candle Breakdown

**Bar 131 (08:36:31 PT) - A single 5-second bar**:
- This ONE 5-second bar might have: Open $52.84, Close $52.84 (no change = DOJI)
- CVD calculates from ticks: Strong buying (-44.6%)
- Validation: "CVD BULLISH but DOJI" → ❌ BLOCKED

**Actual 11:36 ET 1-Minute Candle (12 five-second bars: 131-142)**:
- Open $52.82 (first 5-sec bar's open)
- Close $52.86 (last 5-sec bar's close)
- Change +$0.04 (+0.076%) = GREEN ✅

**Mismatch**: System checked ONE 5-second bar (Bar 131), but should have checked the ENTIRE 1-minute candle (Bars 131-142 aggregated).

---

## Why This Happens

### CVD Monitoring Checks Every 5-Second Bar

From state machine code:
```python
# Wait for 1-minute candle close
bars_per_candle = 12  # (60 seconds / 5 seconds)
bars_into_candle = tracking_idx % bars_per_candle

if bars_into_candle < (bars_per_candle - 1):
    return False, "Waiting for candle close"

# At candle close (bar 11, 23, 35, ...)
# Calculate CVD and check candle color
cvd_result = calculator.calculate_auto(bars, current_idx, ticks=ticks)
```

**The system waits for 1-minute candle close**, but then **checks the 5-second bar at that moment** instead of the full 1-minute candle.

---

## The Fix

### Current (Buggy) Code

```python
# In calculate_auto() - line 365
current_bar = bars[current_idx]  # ❌ Gets 5-second bar
return self.calculate_from_ticks(ticks, bar=current_bar)
```

### Correct Implementation

**Option 1: Aggregate 1-Minute Candle**
```python
# In calculate_auto() - Aggregate 12 five-second bars into 1-minute candle
bars_per_candle = 12
candle_start = (current_idx // bars_per_candle) * bars_per_candle
candle_end = candle_start + bars_per_candle

if candle_end <= len(bars):
    candle_bars = bars[candle_start:candle_end]

    # Create 1-minute candle
    candle_open = candle_bars[0].open
    candle_close = candle_bars[-1].close

    # Create aggregated candle object
    from dataclasses import dataclass
    @dataclass
    class AggregatedBar:
        open: float
        close: float

    aggregated_bar = AggregatedBar(open=candle_open, close=candle_close)

    return self.calculate_from_ticks(ticks, bar=aggregated_bar)
```

**Option 2: Pass Candle Bars to CVD Calculator**
```python
# In ps60_entry_state_machine.py - Pass candle bars instead of single bar
candle_bars = _get_candle_bars(bars, tracking_idx, bars_per_candle, bar_buffer, current_idx)

# Modify calculate_auto signature to accept candle_bars
cvd_result = calculator.calculate_auto(
    bars, current_idx, ticks=ticks,
    candle_bars=candle_bars,  # NEW parameter
    bars_per_candle=bars_per_candle
)
```

**Option 3: Remove Candle Color Validation (Temporary Fix)**
```python
# In cvd_calculator.py - Skip validation for 5-second bars
if bar is not None and hasattr(bar, 'is_aggregated'):
    # Only validate if bar is aggregated 1-minute candle
    # ... validation logic ...
else:
    # Skip validation for 5-second bars
    signals_aligned = True
    validation_reason = ''
```

---

## Impact Analysis

### Trades Blocked by This Bug

**SMCI on Oct 28, 2025**:
- 11:36-11:41 ET: 5 minutes of strong CVD signals (-44.6%, -32.1%) blocked
- All 1-minute candles were GREEN (+0.076%, +0.246%, etc.)
- System incorrectly blocked all entries as "DOJI"
- **Opportunity lost**: SMCI ran from $52.80 to $53.30+ (nearly 1%)

### Why User is Correct

**User's Statement**: "there were no doji candle at this time"
- ✅ **CORRECT**: The 1-minute candles were GREEN
- ✅ **CORRECT**: "if open and close are same then only its doji"
- ✅ **CORRECT**: 0.10% threshold is too strict
- ✅ **CORRECT**: +0.246% is a clear green candle, not DOJI

**System's Mistake**: Checking 5-second bars instead of 1-minute candles

---

## Recommended Solution

### Priority 1: Fix Timeframe Mismatch (IMMEDIATE)

**Change**: Pass aggregated 1-minute candle to CVD validator, not 5-second bar

**Implementation**: Use Option 1 (aggregate candle) or Option 2 (pass candle_bars)

**Files to Modify**:
1. `trader/indicators/cvd_calculator.py:339-372` - calculate_auto()
2. `trader/strategy/ps60_entry_state_machine.py:488-629` - CVD_MONITORING state

### Priority 2: Adjust DOJI Threshold (MEDIUM)

**Current**: Any bar with open == close is DOJI
**Proposed**: Use 0.02% threshold (more traditional)

```python
# In cvd_calculator.py - line 174-179
DOJI_THRESHOLD = 0.0002  # 0.02%

if abs(price_change_pct) < DOJI_THRESHOLD:
    price_direction = 'NEUTRAL'  # DOJI
elif price_change > 0:
    price_direction = 'UP'
else:
    price_direction = 'DOWN'
```

### Priority 3: Logging Improvement (LOW)

Add logging to show which timeframe is being validated:
```python
logger.debug(f"Candle color validation: bar_type=5SEC, open={bar.open}, close={bar.close}, change={price_change_pct:.3f}%")
```

---

## Testing Plan

### Test 1: Verify Bug with Oct 28 Data

**Steps**:
1. Run backtester on Oct 28, 2025 with current code
2. Verify SMCI entries are blocked at 11:36-11:41 ET
3. Check logs for "CANDLE COLOR CONFLICT"

**Expected**: Bug reproduces (entries blocked as DOJI)

### Test 2: Verify Fix with Aggregated Candles

**Steps**:
1. Apply fix (aggregate 1-minute candles)
2. Re-run backtester on Oct 28, 2025
3. Check SMCI entries at 11:36-11:41 ET

**Expected**: Entries NOT blocked, system recognizes GREEN candles

### Test 3: Verify with IBKR Data

**Steps**:
1. Fetch IBKR 1-minute historical data for SMCI Oct 28
2. Compare system's aggregated candles vs IBKR candles
3. Verify open/close/change% match

**Expected**: Perfect match between system and IBKR

---

## Lessons Learned

1. **Timeframe Awareness**: Always verify which timeframe is being used for calculations
2. **Data Aggregation**: When working with 5-second bars, aggregate to 1-minute before validating
3. **User Feedback**: User was correct - always verify with source data (IBKR)
4. **Logging Clarity**: Log which timeframe is being validated to catch mismatches

---

*Analysis completed: October 28, 2025*
*Bug found in: cvd_calculator.py (line 365) and ps60_entry_state_machine.py (line 598)*
*Priority: CRITICAL - Blocking valid entries*
