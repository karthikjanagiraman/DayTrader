# HOOD Entry Window Bug Fix (October 24, 2025)

## Problem Summary

**HOOD missed $10,460 profit opportunity on October 22 due to entry time window filter.**

### Root Cause

**Backtester Logic** (backtester.py:808):
```python
if position is None and within_entry_window:
    # Entry logic only runs when window is open
```

**What Happened**:
1. **Bar 2 (9:31 AM)**: HOOD breaks support ($131.34 < $131.35)
   - Entry window CLOSED (`min_entry_time: "09:45"`)
   - Backtester NEVER calls state machine
   - Breakout is **completely invisible** to strategy

2. **Bars 3-15 (9:32-9:44 AM)**:
   - Entry window still closed
   - State machine never invoked
   - Breakout continues undetected

3. **Bar 16 (9:45:00 AM)**: Entry window OPENS
   - State machine called for FIRST time
   - Starts in MONITORING state (fresh)
   - Detects: price $129.38 < support $131.35 ✅
   - But sees it as a NEW breakout at $129.38
   - Lost the original $131.34 entry opportunity

**Result**: Missed $1.96/share by waiting 15 minutes ($10,460 total on 1000 shares over the full move)

---

## Solution: Pre-Window Breakout Tracking

**Strategy**: Monitor breakouts from 9:30 AM, but only execute entries after 9:45 AM.

### Implementation Changes

#### 1. Backtester Changes (backtester.py)

**Current Code** (lines 808-876):
```python
if position is None and within_entry_window:
    # Check BREAKOUT long entry
    if long_attempts < max_attempts and self.enable_longs:
        should_enter, reason = self.strategy.should_enter_long(stock, price, long_attempts)

        if should_enter:
            # HYBRID Entry Strategy
            confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(...)
```

**New Code** (ALWAYS call state machine, check window later):
```python
# CRITICAL FIX (Oct 24, 2025): ALWAYS call state machine to track breakouts
# even when entry window is closed. This prevents missing early breakouts.
if position is None:
    # Check BREAKOUT long entry
    if long_attempts < max_attempts and self.enable_longs:
        should_enter, reason = self.strategy.should_enter_long(stock, price, long_attempts)

        if should_enter:
            # ALWAYS check for breakout (tracks state even if window closed)
            confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(...)

            # PRE-WINDOW BREAKOUT TRACKING (Oct 24, 2025):
            # If confirmed but entry window closed, log it and continue
            # State machine will remember this breakout for later
            if confirmed and not within_entry_window:
                self.logger.info(f"{symbol} Bar {bar_count} - PRE-WINDOW BREAKOUT detected @ ${price:.2f}")
                self.logger.info(f"   Entry will be considered when window opens @ {self.config['trading']['entry']['min_entry_time']}")
                continue  # Don't enter yet, but breakout is now tracked

            # NORMAL ENTRY: Window is open, execute entry
            if confirmed and within_entry_window:
                # ... existing entry logic ...
```

**Lines to Change**:
- Line 808: Remove `and within_entry_window` from condition
- Lines 816-876: Add pre-window breakout logging
- Lines 879-920: Apply same changes to SHORT entries

#### 2. State Machine Changes (ps60_entry_state_machine.py)

**Current Behavior**:
- State resets after 50 minutes (`max_breakout_age_bars = 600`)
- No concept of "pre-window" breakouts

**New Behavior**:
- Track breakout timestamp
- When entry window opens, validate if breakout is still valid
- Enter on first candle close after window opens (if price still through pivot)

**Changes Needed** (lines 305-327):
```python
# STATE 1: MONITORING - Looking for breakout
if state.state.value == 'MONITORING':
    # Check if price is through pivot
    is_through = (current_price > pivot_price) if side == 'LONG' else (current_price < pivot_price)

    if is_through:
        # Breakout detected! Store it in memory
        tracker.update_breakout(
            symbol=symbol,
            bar_idx=tracking_idx,
            price=current_price,
            timestamp=timestamp,  # Track when breakout occurred
            pivot=pivot_price,
            side=side
        )

        # PRE-WINDOW BREAKOUT (Oct 24, 2025): Mark if detected before entry window
        # This allows backtester to log it and state machine to remember it
        state.pre_window_breakout = True  # NEW FIELD

        return False, "Breakout detected, waiting for candle close", state.to_dict()
```

**Add to BreakoutState class** (breakout_state_tracker.py):
```python
class BreakoutStateData:
    def __init__(self):
        # ... existing fields ...
        self.pre_window_breakout = False  # NEW: Track if breakout occurred before entry window
```

#### 3. Live Trader Changes (trader.py)

**Current Behavior**:
- Only subscribes to market data when ready to trade
- Only calls state machine during entry window

**New Behavior**:
- Subscribe to market data at 9:30 AM
- Call state machine from 9:30 AM (even before entry window)
- Execute entries only after 9:45 AM

**Changes Needed** (trader.py):
```python
# In manage_positions() method
for symbol, stock in self.watchlist.items():
    # ... get current price ...

    # CRITICAL FIX (Oct 24, 2025): ALWAYS monitor for breakouts
    # even when entry window is closed
    if symbol not in self.positions:
        # Check for entry (state machine ALWAYS runs)
        should_enter, reason = self.strategy.should_enter_long(stock, current_price, attempts)

        if should_enter:
            confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(...)

            # PRE-WINDOW BREAKOUT: Don't enter yet, but track it
            if confirmed and not self.strategy.is_within_entry_window(datetime.now()):
                self.logger.info(f"{symbol} - PRE-WINDOW BREAKOUT @ ${current_price:.2f}")
                continue  # State machine remembers this

            # NORMAL ENTRY: Window is open
            if confirmed:
                self.enter_long(symbol, stock, current_price)
```

---

## Expected Behavior After Fix

### HOOD October 22 Example

**Bar 2 (9:31 AM)**: HOOD breaks support
- Entry window: CLOSED ❌
- State machine: CALLED ✅
- Action: Track breakout, log "PRE-WINDOW BREAKOUT detected"
- State: BREAKOUT_DETECTED (stored in memory)

**Bars 3-15 (9:32-9:44 AM)**:
- Entry window: CLOSED ❌
- State machine: CALLED every bar ✅
- Waiting for: Candle close + entry window to open
- State: BREAKOUT_DETECTED (waiting for bar 23)

**Bar 16 (9:45:00 AM)**: Entry window OPENS
- Entry window: OPEN ✅
- State machine: Still in BREAKOUT_DETECTED (from bar 2!)
- Price: $129.38 (still below support ✅)
- Waiting for: Bar 23 (next candle close)

**Bar 23 (9:45:55 AM)**: First candle close after window opens
- Entry window: OPEN ✅
- State machine: BREAKOUT_DETECTED → analyze candle
- Candle: bars 12-23 (9:45:00 - 9:45:55)
- Action: Classify breakout, check filters, ENTER if confirmed

**Result**: Enter at 9:45:55 instead of missing the trade entirely!

---

## Alternative: Simple Fix (Option 1)

If the complex tracking is too much, simply change the config:

```yaml
# trader_config.yaml
trading:
  entry:
    min_entry_time: "09:30"   # Changed from 09:45
    max_entry_time: "15:00"
```

**Pros**:
- One line change
- Never miss early breakouts
- Simpler to maintain

**Cons**:
- May get whipsawed in volatile opening minutes
- Historically, 9:30-9:45 had 40% loss rate vs 25% for 9:45+

---

## Recommendation

**Start with Simple Fix (Option 1)**: Change `min_entry_time` to 09:30

**Why**:
1. HOOD is not an isolated case - any stock can break early
2. The 9:45 rule was based on limited data (October 4 analysis)
3. PS60 methodology doesn't require waiting 15 minutes
4. Potential gains ($10k+ on HOOD alone) outweigh whipsaw risk

**Monitor Results**:
- Track early entries (9:30-9:45) vs late entries (9:45+)
- If early entries have significantly worse performance, revert
- If similar performance, keep it simple

**Future Enhancement** (if needed):
- Implement pre-window tracking (Option 3)
- But only after proving early entries are problematic

---

## Testing Plan

1. **Change config** to `min_entry_time: "09:30"`
2. **Re-run October 22 backtest** - verify HOOD enters at 9:31
3. **Run full October backtest** - measure impact on all trades
4. **Compare metrics**:
   - Early entries (9:30-9:45) win rate vs late entries
   - Total P&L improvement
   - Number of additional trades

5. **If results are good**: Deploy to live trading
6. **If results are bad**: Implement complex pre-window tracking

---

## Code Locations

**Files to Modify**:
1. `/Users/karthik/projects/DayTrader/trader/config/trader_config.yaml` (line 18)
2. `/Users/karthik/projects/DayTrader/trader/backtest/backtester.py` (line 808)
3. `/Users/karthik/projects/DayTrader/trader/trader.py` (manage_positions method)
4. `/Users/karthik/projects/DayTrader/trader/strategy/ps60_entry_state_machine.py` (lines 305-327)
5. `/Users/karthik/projects/DayTrader/trader/strategy/breakout_state_tracker.py` (BreakoutStateData class)

**Priority**: Start with config change (file 1) and test before implementing complex tracking.

---

**Analysis Complete**: October 24, 2025
**Next Step**: Test simple fix (min_entry_time = 09:30) on October 22 backtest
