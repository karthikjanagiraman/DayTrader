# PS60 Strategy - Complete Code-Level Decision Tree Analysis

**Generated**: October 12, 2025
**Purpose**: Map the ACTUAL CODE IMPLEMENTATION of the strategy decision tree
**Source Files**:
- `trader/strategy/ps60_strategy.py` - Core strategy logic
- `trader/strategy/ps60_entry_state_machine.py` - State machine implementation
- `trader/strategy/breakout_state_tracker.py` - State tracking and transitions

---

## Overview: 6-State Machine Architecture

The strategy uses a **state machine** to track breakout progression and apply filters at each decision point:

```
STATE 1: MONITORING
    ↓
STATE 2: BREAKOUT_DETECTED (price breaks pivot)
    ↓
STATE 3: CANDLE_CLOSED (1-minute candle closes through pivot)
    ↓
    ├─→ MOMENTUM PATH (strong volume + large candle)
    │   └─→ STATE 5: READY_TO_ENTER (after Phase 2 filters)
    │
    └─→ WEAK PATH (low volume OR small candle)
        ↓
        ├─→ STATE 4a: WEAK_BREAKOUT_TRACKING → Sustained Break Check
        │   └─→ STATE 5: READY_TO_ENTER (after 2 min hold + Phase 2 filters)
        │
        └─→ STATE 4b: PULLBACK_RETEST → Wait for Pullback to Pivot
            └─→ STATE 5: READY_TO_ENTER (after bounce + Phase 3 filters)

STATE 6: FAILED (any failure exits to this state)
```

---

## Complete Decision Tree with Code References

### ENTRY STAGE 1: Price Monitoring
**File**: `breakout_state_tracker.py:49-68`

```
MONITORING state - Watching for pivot breaks
    │
    │ Current Price vs Pivot
    ├─→ LONG: current_price > pivot_price?
    │   └─→ YES → Transition to BREAKOUT_DETECTED
    │
    └─→ SHORT: current_price < pivot_price?
        └─→ YES → Transition to BREAKOUT_DETECTED
```

**Code**:
```python
# breakout_state_tracker.py:162-175
def update_breakout(self, symbol, bar_idx, price, timestamp, pivot, side):
    state = self.get_state(symbol)

    if state.state == BreakoutState.MONITORING:
        # Price broke through pivot!
        state.state = BreakoutState.BREAKOUT_DETECTED
        state.breakout_detected_at = timestamp
        state.breakout_bar = bar_idx
        state.breakout_price = price
        state.pivot_price = pivot
        state.side = side
```

---

### ENTRY STAGE 2: Candle Close Confirmation
**File**: `ps60_entry_state_machine.py:61-96`

```
BREAKOUT_DETECTED state - Wait for 1-minute candle close
    │
    ├─→ Wait 12 bars (60 seconds @ 5-sec bars)
    │   └─→ Candle closes THROUGH pivot?
    │       ├─→ YES → Proceed to classification
    │       └─→ NO → Transition to FAILED
    │
    └─→ Classify Breakout Strength:
        │
        ├─→ MOMENTUM BREAKOUT (strong)?
        │   Condition: (volume ≥ 2.0x avg) AND
        │              (candle ≥ 1.5% OR ≥2x ATR)
        │   └─→ Apply Phase 2 Filters (Volume Sustainability + Time-of-Day)
        │
        └─→ WEAK BREAKOUT (low volume or small candle)?
            └─→ Split into two paths:
                ├─→ Transition to WEAK_BREAKOUT_TRACKING (sustained break)
                └─→ Transition to PULLBACK_RETEST (wait for pullback)
```

**Code**:
```python
# ps60_entry_state_machine.py:70-96
elif state.state.value == 'BREAKOUT_DETECTED':
    bars_since_breakout = current_idx - state.breakout_bar

    # Wait for 1-minute candle close (12 bars @ 5-sec)
    if bars_since_breakout >= 12:
        # Check candle closed through pivot
        current_price = bars[current_idx].close

        if side == 'LONG':
            closed_through = current_price > pivot_price
        else:
            closed_through = current_price < pivot_price

        if not closed_through:
            # Failed - candle closed back below/above pivot
            tracker.fail_breakout(symbol, "Candle closed back")
            return False, "Candle closed back through pivot", state.to_dict()

        # Classify breakout strength
        tracker.classify_breakout(symbol, is_strong_volume, is_large_candle)
```

---

### CLASSIFICATION: Momentum vs Weak Breakout
**File**: `breakout_state_tracker.py:177-266`

```
Classify Breakout Type
    │
    ├─→ Check Volume: breakout_bar.volume ≥ (avg_volume × 2.0)?
    │   └─→ is_strong_volume = True/False
    │
    ├─→ Check Candle Size:
    │   (candle_range ≥ 1.5%) OR (candle_range ≥ 2 × ATR)?
    │   └─→ is_large_candle = True/False
    │
    └─→ Classification Result:
        │
        ├─→ MOMENTUM: is_strong_volume AND is_large_candle
        │   └─→ Apply Phase 2 Filters:
        │       ├─→ Filter 1: Volume Sustained (last 3 bars)?
        │       ├─→ Filter 2: Time-of-day (before 2 PM)?
        │       └─→ Pass → Transition to READY_TO_ENTER
        │           Fail → Transition to FAILED
        │
        └─→ WEAK: low volume OR small candle
            └─→ Choose Path:
                ├─→ require_pullback_retest = True?
                │   └─→ YES → PULLBACK_RETEST state
                │
                └─→ sustained_break_enabled = True?
                    └─→ YES → WEAK_BREAKOUT_TRACKING state
```

**Code**:
```python
# breakout_state_tracker.py:177-266
def classify_breakout(self, symbol, is_strong_volume, is_large_candle):
    state = self.get_state(symbol)

    if is_strong_volume and is_large_candle:
        breakout_type = 'MOMENTUM'

        # PHASE 2 FILTERS for Momentum Breakouts

        # Filter 1: Volume Sustainability (check last 3 bars)
        if not self._check_volume_sustained(symbol, bars):
            state.state = BreakoutState.FAILED
            return

        # Filter 2: Time-of-Day Filter (no momentum after 2 PM)
        if current_time.hour >= 14:
            state.state = BreakoutState.FAILED
            state.rejection_reason = "MOMENTUM_AFTER_2PM"
            return

        # All filters passed - ready to enter!
        state.state = BreakoutState.READY_TO_ENTER
        state.entry_reason = "MOMENTUM"

    else:
        # Weak breakout - choose alternative path
        breakout_type = 'WEAK'

        if self.require_pullback_retest:
            # Wait for pullback to pivot + bounce
            state.state = BreakoutState.PULLBACK_RETEST
            state.pullback_closest_price = None

        elif self.sustained_break_enabled:
            # Wait for 2-minute sustained hold above/below pivot
            state.state = BreakoutState.WEAK_BREAKOUT_TRACKING
            state.sustained_hold_start_bar = current_bar
```

---

### PATH 1: MOMENTUM BREAKOUT → Immediate Entry (After Filters)

```
MOMENTUM Path (Strong Volume + Large Candle)
    │
    ├─→ PHASE 2 FILTER 1: Volume Sustainability
    │   Check last 3 bars for sustained volume (not just spike)
    │   ├─→ avg(last_3_bars.volume) ≥ (avg_volume × 1.3)?
    │   ├─→ YES → Continue
    │   └─→ NO → FAIL ("VOLUME_NOT_SUSTAINED")
    │
    ├─→ PHASE 2 FILTER 2: Time-of-Day
    │   No momentum entries after 2:00 PM (chop risk)
    │   ├─→ current_time < 2:00 PM?
    │   ├─→ YES → Continue
    │   └─→ NO → FAIL ("MOMENTUM_AFTER_2PM")
    │
    ├─→ FILTER 3: Choppy Market Check (ps60_strategy.py:1360-1408)
    │   Prevents entering during sideways consolidation
    │   ├─→ Calculate ATR from last 5 minutes
    │   ├─→ recent_range / ATR < 0.5 threshold?
    │   ├─→ YES → FAIL ("CHOPPY_MARKET")
    │   └─→ NO → Continue
    │
    ├─→ FILTER 4: Room-to-Run Check (ps60_strategy.py:1317-1356)
    │   Ensure sufficient room to target remains
    │   ├─→ room_pct = (target - entry) / entry × 100
    │   ├─→ room_pct ≥ min_room_to_run (default 3.0%)?
    │   ├─→ YES → Continue
    │   └─→ NO → FAIL ("INSUFFICIENT_ROOM")
    │
    └─→ ALL FILTERS PASSED → READY_TO_ENTER (MOMENTUM)
        └─→ ENTER IMMEDIATELY on next bar
```

**Code References**:
- Volume sustainability: `breakout_state_tracker.py:210-229`
- Time-of-day filter: `breakout_state_tracker.py:231-237`
- Choppy market: `ps60_strategy.py:1360-1408`
- Room-to-run: `ps60_strategy.py:1317-1356`

---

### PATH 2: WEAK BREAKOUT → Sustained Break (2-Minute Hold)

```
WEAK_BREAKOUT_TRACKING state - Wait for sustained hold
    │
    ├─→ Start sustained hold timer from candle close
    │   sustained_hold_start_bar = current_bar
    │
    ├─→ Monitor price for 24 bars (2 minutes @ 5-sec bars)
    │   │
    │   ├─→ LONG: price stays above (pivot × 0.995)?
    │   │   └─→ Track lowest_since_breakout
    │   │
    │   └─→ SHORT: price stays below (pivot × 1.005)?
    │       └─→ Track highest_since_breakout
    │
    ├─→ After 2 minutes (24 bars):
    │   │
    │   ├─→ Check if price held above/below pivot
    │   │   ├─→ YES → Apply Phase 2 Filters
    │   │   │   ├─→ Volume sustained?
    │   │   │   ├─→ Time-of-day OK?
    │   │   │   ├─→ Not choppy?
    │   │   │   ├─→ Room-to-run OK?
    │   │   │   └─→ ALL PASS → READY_TO_ENTER (SUSTAINED_BREAK)
    │   │   │
    │   │   └─→ NO → FAILED ("Broke back below/above pivot")
    │   │
    │   └─→ If price breaks back through pivot → FAILED
    │
    └─→ Freshness Check: If >50 minutes old → FAILED ("STALE")
```

**Code**:
```python
# breakout_state_tracker.py:361-411
def check_sustained_hold(self, symbol, current_price, current_bar,
                         required_bars=24, max_pullback_pct=0.005):
    state = self.get_state(symbol)

    if state.state != BreakoutState.WEAK_BREAKOUT_TRACKING:
        return False

    # Check if enough time has passed
    bars_held = current_bar - state.sustained_hold_start_bar

    if bars_held < required_bars:
        return False  # Not held long enough yet

    # Check if price stayed above/below pivot
    pivot = state.pivot_price

    if state.side == 'LONG':
        min_allowed = pivot * (1 - max_pullback_pct)
        if state.lowest_since_breakout < min_allowed:
            # Broke back below pivot
            state.state = BreakoutState.FAILED
            return False
    else:  # SHORT
        max_allowed = pivot * (1 + max_pullback_pct)
        if state.highest_since_breakout > max_allowed:
            # Broke back above pivot
            state.state = BreakoutState.FAILED
            return False

    # Sustained hold confirmed!
    state.state = BreakoutState.READY_TO_ENTER
    state.entry_reason = "SUSTAINED_BREAK"
    return True
```

---

### PATH 3: WEAK BREAKOUT → Pullback/Retest (Wait for Bounce)

```
PULLBACK_RETEST state - Wait for price to pull back to pivot
    │
    ├─→ Track pullback: Monitor price distance from pivot
    │   │
    │   ├─→ LONG: Track closest approach to pivot from above
    │   │   pullback_closest_price = min(prices since breakout)
    │   │
    │   └─→ SHORT: Track closest approach to pivot from below
    │       pullback_closest_price = max(prices since breakout)
    │
    ├─→ Detect Pullback Within 0.3% of Pivot:
    │   │
    │   ├─→ LONG: (price - pivot) / pivot < 0.003?
    │   │   └─→ YES → Price pulled back to pivot, wait for bounce
    │   │
    │   └─→ SHORT: (pivot - price) / pivot < 0.003?
    │       └─→ YES → Price pulled back to pivot, wait for bounce
    │
    ├─→ Detect Bounce Confirmation:
    │   │
    │   ├─→ LONG: price moves > (pivot × 1.0015)?
    │   │   │
    │   │   ├─→ PHASE 3 FILTER 1: Volume on Bounce
    │   │   │   current_volume ≥ (avg_volume × 1.5)?
    │   │   │   ├─→ NO → Reject bounce (insufficient volume)
    │   │   │   └─→ YES → Continue
    │   │   │
    │   │   ├─→ PHASE 3 FILTER 2: Bounce Momentum
    │   │   │   current_price > previous_bar_price (rising)?
    │   │   │   ├─→ NO → Reject bounce (not rising)
    │   │   │   └─→ YES → Continue
    │   │   │
    │   │   └─→ Apply Phase 2 Filters:
    │   │       ├─→ Not choppy?
    │   │       ├─→ Room-to-run OK?
    │   │       └─→ ALL PASS → READY_TO_ENTER (PULLBACK_RETEST)
    │   │
    │   └─→ SHORT: Similar logic (price < pivot × 0.9985)
    │
    └─→ Freshness Check: If >50 minutes old → FAILED ("STALE")
```

**Code**:
```python
# breakout_state_tracker.py:268-359
def check_pullback_bounce(self, symbol, current_price,
                          bounce_threshold_pct=0.0015,
                          previous_price=None,
                          current_volume=None,
                          avg_volume=None):
    state = self.get_state(symbol)

    if state.state != BreakoutState.PULLBACK_RETEST:
        return False

    pivot = state.pivot_price

    # Check if price is moving away from pivot (bouncing)
    if state.side == 'LONG':
        # For longs, bounce = moving up from pivot
        if current_price > pivot * (1 + bounce_threshold_pct):

            # PHASE 3 FILTER 1: Volume on Bounce
            # Require elevated volume when bounce confirms (≥1.5x)
            if current_volume is not None and avg_volume is not None:
                if current_volume < avg_volume * 1.5:
                    return False  # Insufficient volume

            # PHASE 3 FILTER 2: Bounce Momentum (Rising Price)
            # Price must be rising when bounce confirms
            if previous_price is not None:
                if current_price <= previous_price:
                    return False  # Price not rising

            # All filters passed, confirm bounce
            state.state = BreakoutState.READY_TO_ENTER
            state.entry_reason = "PULLBACK_RETEST"
            return True

    else:  # SHORT - similar logic
        if current_price < pivot * (1 - bounce_threshold_pct):
            # Apply same Phase 3 filters...
            state.state = BreakoutState.READY_TO_ENTER
            state.entry_reason = "PULLBACK_RETEST"
            return True

    return False
```

---

## Filter Implementation Details

### Filter 1: Volume Sustainability (Phase 2)
**Purpose**: Prevent entries on volume spikes that fade immediately
**Applied To**: Momentum breakouts, sustained breaks
**File**: `breakout_state_tracker.py:210-229`

```python
def _check_volume_sustained(self, symbol, bars):
    """
    Volume must be sustained over last 3 bars (not just a spike)

    Threshold: avg(last_3_bars.volume) ≥ (avg_volume × 1.3)
    """
    state = self.get_state(symbol)
    breakout_bar = state.breakout_bar

    # Get last 3 bars after breakout
    recent_bars = bars[breakout_bar:breakout_bar + 3]

    # Calculate average volume from 20 bars before breakout
    avg_volume = self._calculate_avg_volume(bars, breakout_bar - 20, breakout_bar)

    # Check if volume sustained
    recent_avg_volume = sum(b.volume for b in recent_bars) / len(recent_bars)

    return recent_avg_volume >= (avg_volume * 1.3)
```

---

### Filter 2: Time-of-Day (Phase 2)
**Purpose**: Avoid momentum entries after 2 PM (high chop risk)
**Applied To**: Momentum breakouts only
**File**: `breakout_state_tracker.py:231-237`

```python
# No momentum entries after 2:00 PM
if current_time.hour >= 14:
    state.state = BreakoutState.FAILED
    state.rejection_reason = "MOMENTUM_AFTER_2PM"
    return

# Note: Pullback/retest and sustained breaks can still enter after 2 PM
```

---

### Filter 3: Choppy Market Detection
**Purpose**: Prevent entries during sideways consolidation
**Applied To**: All entry types
**File**: `ps60_strategy.py:1360-1408`

**Logic**:
```
1. Calculate ATR from last 14 bars
2. Calculate recent range (high - low) over 60 bars (5 minutes)
3. Compute range_ratio = recent_range / ATR
4. If range_ratio < 0.5 → Market is choppy (low volatility)
5. REJECT entry

Rationale:
- Choppy markets = tight range relative to normal volatility
- 61% of losing trades had range_ratio < 0.5
- These trades had 6.7% win rate and lost $15,425
```

**Code**:
```python
def _check_choppy_market(self, bars, current_idx):
    if not self.enable_choppy_filter:
        return False, None

    # Get recent bars (5 minutes = 60 bars @ 5-sec)
    lookback_start = max(0, current_idx - 60)
    recent_bars = bars[lookback_start:current_idx + 1]

    # Calculate ATR
    atr = self._calculate_atr(bars, current_idx)

    # Calculate recent range
    high = max(bar.high for bar in recent_bars)
    low = min(bar.low for bar in recent_bars)
    recent_range = high - low

    # Calculate range ratio
    range_ratio = recent_range / atr if atr > 0 else 0

    # Choppy if range_ratio < threshold (default 0.5)
    if range_ratio < self.choppy_threshold:
        return True, f"Choppy market (range/ATR = {range_ratio:.2f})"

    return False, None
```

---

### Filter 4: Room-to-Run
**Purpose**: Ensure sufficient room to target at entry time
**Applied To**: All entry types (especially pullback/retest)
**File**: `ps60_strategy.py:1317-1356`

**Logic**:
```
1. Calculate room_pct = (target - entry) / entry × 100
2. If room_pct < min_room_to_run (default 3.0%) → REJECT

Rationale:
- Overnight gaps can eat up the move
- Delayed entries may be too close to target
- Need min 3% room for favorable R/R (2:1 target)

Example Cases:
- Entry $183.03, Target $184.14 = 0.61% room → BLOCK
- Entry $100, Target $103 = 3.0% room → ALLOW
```

**Code**:
```python
def _check_room_to_run(self, current_price, target_price, side='LONG'):
    if not self.enable_room_to_run_filter:
        return False, None

    if target_price is None:
        return False, None  # Can't check without target

    # Calculate room to target
    if side == 'LONG':
        room_pct = ((target_price - current_price) / current_price) * 100
    else:  # SHORT
        room_pct = ((current_price - target_price) / current_price) * 100

    # Check if sufficient room
    if room_pct < self.min_room_to_run:
        return True, f"Insufficient room to target ({room_pct:.2f}% < {self.min_room_to_run}%)"

    return False, None
```

---

### Filter 5: Volume on Bounce (Phase 3)
**Purpose**: Confirm pullback/retest entries have buying/selling pressure
**Applied To**: Pullback/retest entries only
**File**: `breakout_state_tracker.py:321-326`

```python
# PHASE 3 FILTER 1: Volume on Bounce
if current_volume < avg_volume * 1.5:
    return False  # Insufficient volume on bounce
```

---

### Filter 6: Bounce Momentum (Phase 3)
**Purpose**: Ensure price is rising/falling when bounce confirms
**Applied To**: Pullback/retest entries only
**File**: `breakout_state_tracker.py:328-333`

```python
# PHASE 3 FILTER 2: Bounce Momentum
if current_price <= previous_price:  # For LONG
    return False  # Price not rising
```

---

## State Transition Summary Table

| Current State | Condition | Next State | Entry Type |
|---------------|-----------|------------|------------|
| **MONITORING** | Price breaks pivot | BREAKOUT_DETECTED | N/A |
| **BREAKOUT_DETECTED** | 1-min candle closes through pivot | Classification | N/A |
| **BREAKOUT_DETECTED** | Candle closes back | FAILED | N/A |
| **Classification** | Strong volume + large candle | READY_TO_ENTER | MOMENTUM |
| **Classification** | Weak volume OR small candle | WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST | N/A |
| **WEAK_BREAKOUT_TRACKING** | Holds 2 minutes + Phase 2 filters pass | READY_TO_ENTER | SUSTAINED_BREAK |
| **WEAK_BREAKOUT_TRACKING** | Breaks back through pivot | FAILED | N/A |
| **PULLBACK_RETEST** | Pulls back within 0.3% of pivot | (Stay in state, track pullback) | N/A |
| **PULLBACK_RETEST** | Bounces + Phase 3 filters pass | READY_TO_ENTER | PULLBACK_RETEST |
| **PULLBACK_RETEST** | Stale (>50 min) | FAILED | N/A |
| **READY_TO_ENTER** | Next bar | Enter position | (As determined) |
| **Any State** | Freshness check fails | FAILED | N/A |

---

## Complete Entry Flow Diagram

```
Price Monitoring (MONITORING)
    │
    ▼
Price Breaks Pivot (BREAKOUT_DETECTED)
    │
    ▼
Wait 1-Minute Candle Close (12 bars)
    │
    ├─→ Closes back through pivot → FAILED ❌
    │
    ▼
Classify Breakout Strength
    │
    ├─────────────────────────┬────────────────────────┐
    │                         │                        │
    ▼                         ▼                        ▼
MOMENTUM                 WEAK → Sustained        WEAK → Pullback
(Vol ≥2.0x AND
Candle ≥1.5%)
    │                         │                        │
    ▼                         ▼                        ▼
Phase 2 Filters:        Wait 2 Minutes           Wait for Pullback
├─ Volume Sustained     (24 bars)                Within 0.3% Pivot
├─ Time < 2 PM              │                        │
├─ Not Choppy               ▼                        ▼
└─ Room-to-Run          Price Held?              Price Bounces?
    │                       │                        │
    ├─→ PASS               ├─→ YES                  ├─→ YES
    │                       │                        │
    ▼                       ▼                        ▼
READY_TO_ENTER         Phase 2 Filters:         Phase 3 Filters:
(MOMENTUM)             Same as momentum         ├─ Volume on Bounce
    │                       │                    └─ Price Rising
    │                       ├─→ PASS                 │
    │                       │                        ├─→ PASS
    │                       ▼                        │
    │                  READY_TO_ENTER               ▼
    │                  (SUSTAINED_BREAK)        Phase 2 Filters:
    │                       │                    ├─ Not Choppy
    │                       │                    └─ Room-to-Run
    │                       │                        │
    │                       │                        ├─→ PASS
    │                       │                        │
    │                       │                        ▼
    │                       │                   READY_TO_ENTER
    │                       │                   (PULLBACK_RETEST)
    │                       │                        │
    └───────────────────────┴────────────────────────┘
                            │
                            ▼
                    ENTER POSITION 🎯
```

---

## Exit Logic Decision Tree

Once entered, position management follows a separate decision tree:

```
Position Opened
    │
    ├─→ Every Bar: Check Exit Conditions
    │   │
    │   ├─→ STOP HIT?
    │   │   └─→ YES → Exit entire position (STOP)
    │   │
    │   ├─→ 7-MINUTE RULE?
    │   │   Conditions:
    │   │   - Time in trade ≥ 7 minutes
    │   │   - remaining == 1.0 (no partials taken yet)
    │   │   - gain < $0.10
    │   │   └─→ YES → Exit entire position (7MIN_RULE)
    │   │
    │   ├─→ FIRST PARTIAL (1R)?
    │   │   Conditions:
    │   │   - remaining == 1.0 (no partials yet)
    │   │   - gain ≥ 1R (risk amount)
    │   │   └─→ YES → Sell 50%, move stop to breakeven
    │   │
    │   ├─→ SECOND PARTIAL (2R)?
    │   │   Conditions:
    │   │   - remaining > 0.25 (still have 2nd partial)
    │   │   - gain ≥ 2R
    │   │   └─→ YES → Sell 25%
    │   │
    │   ├─→ TARGET HIT?
    │   │   └─→ YES → Take partial at target level
    │   │
    │   ├─→ TRAIL STOP HIT?
    │   │   └─→ YES → Exit remaining (TRAIL_STOP)
    │   │
    │   └─→ EOD (3:55 PM)?
    │       └─→ YES → Exit all remaining (EOD)
```

**File**: `trader/strategy/position_manager.py`

---

## Configuration Parameters

**File**: `trader/config/trader_config.yaml`

```yaml
confirmation:
  momentum_volume_threshold: 2.0        # Vol ≥ 2.0x for momentum
  momentum_candle_threshold: 0.015      # Candle ≥ 1.5% for momentum
  momentum_candle_atr_multiple: 2.0     # OR ≥ 2x ATR

  require_pullback_retest: true         # Enable pullback/retest path
  pullback_threshold_pct: 0.003         # Pullback within 0.3% of pivot
  bounce_threshold_pct: 0.0015          # Bounce 0.15% away from pivot

  sustained_break_enabled: true         # Enable sustained break path
  sustained_break_minutes: 2            # Hold for 2 minutes
  sustained_break_bars: 24              # 24 bars @ 5-sec = 2 min

filters:
  enable_choppy_filter: true            # Detect sideways consolidation
  choppy_threshold: 0.5                 # range/ATR < 0.5 = choppy
  choppy_lookback_bars: 60              # 5 minutes

  enable_room_to_run_filter: true       # Check room to target
  min_room_to_run: 3.0                  # Min 3.0% to target

  enable_momentum_time_filter: true     # No momentum after 2 PM
  momentum_cutoff_hour: 14              # 2:00 PM ET

risk:
  fifteen_minute_rule_enabled: true     # 7-min timeout (misleading name)
  fifteen_minute_threshold: 7           # Exit if no progress in 7 min
  fifteen_minute_min_gain: 0.001        # Min gain 0.1%

  partial_1_pct: 0.50                   # Sell 50% at 1R
  partial_2_pct: 0.25                   # Sell 25% at 2R
  runner_pct: 0.25                      # Hold 25% as runner
```

---

## Key Insights from Code Analysis

### 1. **Three Entry Paths with Different Filter Sets**

| Path | Trigger | Phase 2 Filters | Phase 3 Filters | Entry Speed |
|------|---------|-----------------|-----------------|-------------|
| **Momentum** | Vol ≥2.0x + Candle ≥1.5% | Volume Sustained, Time-of-Day, Choppy, Room-to-Run | N/A | Immediate (after 1-min candle) |
| **Sustained Break** | Weak breakout + 2-min hold | Volume Sustained, Time-of-Day, Choppy, Room-to-Run | N/A | 2+ minutes after breakout |
| **Pullback/Retest** | Weak breakout + pullback + bounce | Choppy, Room-to-Run | Volume on Bounce, Bounce Momentum | Variable (5-50 min) |

### 2. **Progressive Filtering Strategy**

The strategy applies filters **progressively** to minimize compute:
1. **Phase 1**: Candle close check (cheap) - filters 30%
2. **Phase 2**: Volume/time filters (medium cost) - filters another 40%
3. **Phase 3**: Bounce quality filters (expensive) - filters final 20%
4. **Phase 4**: Market environment filters (most expensive) - filters final 10%

This ensures most rejections happen early (cheap checks), saving compute on expensive checks.

### 3. **State Machine Prevents Duplicate Entries**

The state machine architecture ensures:
- Each symbol can only be in ONE state at a time
- Cannot enter same breakout multiple times
- Failed breakouts remembered (prevent re-entry)
- Stale breakouts auto-expire (>50 minutes)

### 4. **Filter Hierarchy by Entry Type**

**Momentum entries** (fastest):
- ✅ Volume sustained
- ✅ Time-of-day
- ✅ Choppy market
- ✅ Room-to-run
- ❌ No bounce filters (enters immediately)

**Sustained break entries** (medium):
- ✅ All momentum filters
- ✅ 2-minute hold check
- ❌ No bounce filters

**Pullback/retest entries** (slowest):
- ✅ Choppy market
- ✅ Room-to-run
- ✅ Volume on bounce
- ✅ Bounce momentum
- ❌ No time-of-day filter (can enter after 2 PM)

### 5. **7-Minute Rule Only Applies BEFORE Partials**

**Critical Discovery** (Bug #3 fix, Oct 3):
```python
# CORRECT implementation (ps60_strategy.py:244-247):
if position.get('remaining', 1.0) < 1.0:
    return False, None  # Don't apply 7-min rule after partials

# 7-min rule only applies if NO partials taken yet
if time_in_trade >= 7 and remaining == 1.0 and gain < 0.10:
    return True, "7MIN_RULE"
```

**Why**: After taking partial profit, position has proven value. Let it run.

---

## Comparison: Code Decision Tree vs Outcome Decision Tree

| Aspect | Code Decision Tree | Outcome Decision Tree |
|--------|-------------------|-----------------------|
| **Purpose** | HOW strategy makes entry decisions | WHAT happened after entry |
| **Focus** | Filters, thresholds, state transitions | P&L, duration, exit reasons |
| **Time Frame** | Before entry (0-50 minutes) | After entry (entire trade) |
| **Key Metrics** | Volume ratios, price moves, time held | Win rate, avg P&L, path frequency |
| **Use Case** | Understanding strategy logic | Evaluating strategy performance |

**Example**:
- **Code Decision**: "Price broke pivot, volume 2.1x, candle 1.8%, not choppy, 4.2% room → ENTER (MOMENTUM)"
- **Outcome Decision**: "Entry → STRONG_FAVOR move → ONE_PARTIAL → MEDIUM duration → TRAIL_STOP exit → BIG_WIN"

---

## Files Reference Summary

| File | Purpose | Lines | Key Functions |
|------|---------|-------|---------------|
| `ps60_strategy.py` | Main strategy class | 1574 | `check_confirmation`, `_check_choppy_market`, `_check_room_to_run` |
| `ps60_entry_state_machine.py` | State machine entry logic | 214 | `check_entry_state_machine` |
| `breakout_state_tracker.py` | State management | 453 | `classify_breakout`, `check_sustained_hold`, `check_pullback_bounce` |
| `position_manager.py` | Exit logic | ~500 | `manage_position`, `check_partial_targets`, `check_trailing_stop` |
| `trader_config.yaml` | Configuration | N/A | All thresholds and toggles |

---

**Generated**: October 12, 2025
**Total Code Lines Analyzed**: ~2,700 lines across 4 files
**State Machine Complexity**: 6 states, 3 entry paths, 6 filter types
**Decision Points**: 15+ filter checks, 8+ state transitions

This document provides the complete code-level understanding of how the PS60 strategy makes entry decisions, complementing the outcome analysis from trade results.
