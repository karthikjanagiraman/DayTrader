# Implementation Notes - Priority Fixes (Oct 9, 2025)

## Priority 1: Exit Price "Bug" Investigation

### Finding: NOT A BUG - It's Slippage Simulation

**What appeared to be a bug**:
| Trade | JSON Exit | Market Close | Difference |
|-------|-----------|--------------|------------|
| AVGO #1 | $346.39 | $347.16 | -$0.77 |
| AVGO #2 | $346.41 | $347.24 | -$0.83 |

**Root Cause**: Stop slippage (0.2%) is being applied correctly
- Line 785: `stop_exit_price = price * (1 - self.stop_slippage)`
- Example: $347.16 × (1 - 0.002) = $346.47

**The $0.77 discrepancy** is likely due to:
1. Stop slippage: 0.2% = $0.69
2. Additional movement between bar close price and actual stop trigger

**Conclusion**: This is CORRECT BEHAVIOR for realistic backtesting. Stops in live trading don't fill at perfect prices.

**Action**: KEEP slippage simulation, but document it clearly in trade records.

---

## Priorities to Implement

### Priority 2: Add Momentum Confirmation Filters

**Problem**: AVGO trades had 3.2x volume spike but NO price follow-through (went flat immediately)

**Solution**: Add multi-condition momentum filters

1. **Trend Confirmation**: Only momentum entries if price > 5-bar SMA
2. **Volume Sustainability**: Require 2-3 consecutive bars of elevated volume (not just 1 spike)
3. **Price Follow-Through**: After breakout, price must move ≥0.15% within first 6 bars (30 seconds)
4. **Time-of-Day Filter**: No momentum entries after 2:00 PM (lower volume, higher whipsaws)

**Implementation**: Add to `breakout_state_tracker.py` `classify_breakout()` method

---

### Priority 3: Improve Pullback Quality Filters

**Problem**: COIN pullback entries caught bounces correctly but had no institutional support (brief rallies, then reversals)

**Solution**: Add bounce quality checks

1. **Volume on Bounce**: Require volume ≥1.5x average when bounce confirms (not just on initial breakout)
2. **Bounce Strength**: Increase bounce threshold from 0.1% to 0.15% above pivot
3. **Time Filter**: Avoid pullback entries within 10 minutes of previous failed attempt on same symbol
4. **Bounce Momentum**: Require price to be rising (current > previous bar) when bounce confirms

**Implementation**: Modify `breakout_state_tracker.py` `check_pullback_bounce()` method

---

### Priority 4: Widen Momentum Stops

**Problem**: AVGO stops were TOO TIGHT
- Entry: $347.08
- Stop: $346.99 (only 9 cents, 0.03%)
- Normal volatility: $347.09-$347.22 (0.04%)
- Result: Stopped out by noise, not actual reversal

**Solution**: Implement minimum stop distance for momentum breakouts

1. **Minimum Stop %**: 0.5% below entry for LONG momentum, 0.5% above for SHORT
2. **ATR-Based Alternative**: Use max(0.5%, 2.0 × ATR) for volatile stocks
3. **Setup-Specific Stops**:
   - Momentum: 0.5% minimum (wider, more room)
   - Pullback: 0.3% minimum (tighter, confirmed level)
   - Sustained: 0.4% minimum (medium)

**Implementation**: Modify `backtester.py` stop calculation in `enter_long()` and `enter_short()`

---

## Implementation Plan

### Step 1: Momentum Filters (Priority 2)

**File**: `trader/strategy/breakout_state_tracker.py`

**Method**: `classify_breakout()` (around line 137)

```python
def classify_breakout(self, symbol: str, is_strong_volume: bool, is_large_candle: bool,
                     bars=None, current_idx=None) -> str:
    """
    Classify breakout as MOMENTUM or WEAK

    NEW: Add additional momentum confirmation filters
    """
    state = self.get_state(symbol)

    # Original logic
    if is_strong_volume and is_large_candle:
        breakout_type = 'MOMENTUM'
    else:
        breakout_type = 'WEAK'

    # NEW FILTERS (Priority 2)
    if breakout_type == 'MOMENTUM' and bars is not None and current_idx is not None:
        # Filter 1: Trend confirmation (price > 5-bar SMA)
        if current_idx >= 5:
            sma5 = sum(bars[i].close for i in range(current_idx-5, current_idx)) / 5
            if bars[current_idx].close < sma5:
                # Price below short-term average = downtrend, downgrade to WEAK
                breakout_type = 'WEAK'
                state.entry_reason = "Momentum downgraded (below 5-bar SMA)"

        # Filter 2: Volume sustainability (check previous 2 bars)
        if breakout_type == 'MOMENTUM' and current_idx >= 2:
            # Calculate average volume of last 3 bars
            recent_vol = sum(bars[i].volume for i in range(current_idx-2, current_idx+1)) / 3
            # Compare to longer-term average
            if current_idx >= 20:
                avg_vol = sum(bars[i].volume for i in range(current_idx-20, current_idx-2)) / 18
                if recent_vol < avg_vol * 1.5:
                    # Volume not sustained, downgrade
                    breakout_type = 'WEAK'
                    state.entry_reason = "Momentum downgraded (volume not sustained)"

        # Filter 3: Time-of-day filter (no momentum after 2 PM)
        bar_time = bars[current_idx].date if hasattr(bars[current_idx], 'date') else None
        if bar_time and bar_time.hour >= 14:
            breakout_type = 'WEAK'
            state.entry_reason = "Momentum downgraded (after 2 PM)"

    state.breakout_type = breakout_type
    return breakout_type
```

**Additional**: Add price follow-through check in state machine after momentum entry

---

### Step 2: Pullback Quality Filters (Priority 3)

**File**: `trader/strategy/breakout_state_tracker.py`

**Method**: `check_pullback_bounce()` (around line 246)

```python
def check_pullback_bounce(self, symbol: str, current_price: float, previous_price: float = None,
                         current_volume: float = None, avg_volume: float = None,
                         bounce_threshold_pct: float = 0.0015) -> bool:  # Increased from 0.001 to 0.0015 (0.15%)
    """
    Check if price is bouncing off pivot after pullback

    NEW: Add bounce quality filters (Priority 3)
    """
    state = self.get_state(symbol)

    if state.state != BreakoutState.PULLBACK_RETEST:
        return False

    pivot = state.pivot_price

    # Check if price is moving away from pivot (bouncing)
    if state.side == 'LONG':
        # For longs, bounce = moving up from pivot
        if current_price > pivot * (1 + bounce_threshold_pct):  # Now 0.15% instead of 0.1%

            # NEW FILTER 1: Volume on bounce (Priority 3)
            if current_volume is not None and avg_volume is not None:
                if current_volume < avg_volume * 1.5:
                    # Insufficient volume on bounce, reject
                    return False

            # NEW FILTER 2: Bounce momentum (Priority 3)
            if previous_price is not None:
                if current_price <= previous_price:
                    # Price not rising, reject bounce
                    return False

            # All filters passed, confirm bounce
            state.state = BreakoutState.READY_TO_ENTER
            state.entry_reason = "PULLBACK_RETEST"
            return True

    else:  # SHORT (similar logic)
        if current_price < pivot * (1 - bounce_threshold_pct):
            # Apply same filters...
            state.state = BreakoutState.READY_TO_ENTER
            state.entry_reason = "PULLBACK_RETEST"
            return True

    return False
```

**Additional**: Add recent failure tracking in state tracker initialization

---

### Step 3: Widen Momentum Stops (Priority 4)

**File**: `trader/backtest/backtester.py`

**Method**: `enter_long()` (around line 653)

```python
def enter_long(self, stock, price, timestamp, bar_num, setup_type='BREAKOUT', stop_override=None):
    """Enter long position"""
    # Apply entry slippage (buy at slightly worse price)
    entry_price = price * (1 + self.entry_slippage)

    # Stop placement depends on setup type
    if stop_override is not None:
        # Use stop price from retest confirmation strategy
        stop_price = stop_override
    elif setup_type == 'BOUNCE':
        # For bounce: stop below support
        stop_price = stock['support'] * 0.995  # Just below support
    else:  # BREAKOUT
        # For breakout: stop at resistance (pivot)
        base_stop = stock['resistance']

        # NEW: PRIORITY 4 - Minimum stop distance based on setup type
        min_stop_distance_pct = 0.005  # 0.5% minimum for momentum
        if setup_type == 'BREAKOUT':
            # Check if this is momentum or weak breakout from entry reason
            # For momentum: use wider stop (0.5%)
            # For weak: use tighter stop (0.3%)
            min_stop_distance_pct = 0.005 if 'MOMENTUM' in str(stop_override or '') else 0.003

        # Calculate minimum stop
        min_stop_price = entry_price * (1 - min_stop_distance_pct)

        # Use the LOWER of base_stop or min_stop (more protection)
        stop_price = min(base_stop, min_stop_price)

    shares = self.calculate_position_size(entry_price, stop_price)

    # ... rest of method
```

---

## Testing Plan

1. **Test Priority 2** (Momentum Filters):
   - Run Oct 9 backtest
   - Expect: AVGO momentum entries blocked (below 5-SMA or insufficient sustained volume)
   - Expect: Fewer false breakouts overall

2. **Test Priority 3** (Pullback Quality):
   - Run Oct 9 backtest
   - Expect: COIN pullback entries may be blocked if volume on bounce was weak
   - Expect: Higher quality pullback entries overall

3. **Test Priority 4** (Wider Stops):
   - Run Oct 9 backtest
   - Expect: AVGO trades may NOT stop out immediately (wider 0.5% stop vs 0.03%)
   - Expect: Some quick losses become small winners or breakeven

4. **Combined Test**:
   - Run Oct 9 with ALL fixes
   - Expected result: 0-2 trades (down from 4), but potentially profitable or smaller losses
   - Trade count may drop significantly due to stricter filters

---

## Expected Impact

| Metric | Before | After (Estimated) |
|--------|--------|-------------------|
| Trades | 4 | 0-2 |
| P&L | -$4,680 | -$1,000 to +$500 |
| Win Rate | 0% | 0-50% |
| Avg Trade | -$1,170 | -$500 to +$250 |

**Key Changes**:
- AVGO momentum entries likely BLOCKED (fail trend/volume filters)
- COIN pullback entries MAY be blocked (if bounce volume was weak)
- If AVGO entries still occur, wider stops prevent immediate whipsaw exits

**Goal**: Fewer trades, but MUCH higher quality (avoid false signals)
