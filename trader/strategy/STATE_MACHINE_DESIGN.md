# Breakout State Machine - Memory-Based Approach

## Problem with Old Approach (Lookback Loop)

**Every bar**, the system would:
1. Search backwards through bars to find breakout
2. Search again for candle close
3. Search again for pullback
4. **Result**: Constant re-searching, aging out of narrow windows, high failure rate

## New Approach (State Machine with Memory)

**Store key moments ONCE** when they happen, then track progression:

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATE MACHINE FLOW                            │
└─────────────────────────────────────────────────────────────────┘

STATE 1: MONITORING
   ↓
   Price breaks pivot ($175 > $174.50 resistance)
   ↓
   📝 STORE IN MEMORY:
      - breakout_bar = 100
      - breakout_price = $175.02
      - breakout_time = 10:45:30
      - pivot_price = $174.50
      - side = LONG
   ↓
STATE 2: BREAKOUT_DETECTED
   ↓
   Wait for candle close (12 bars)
   ↓
   Candle closes at bar 111
   ↓
   📝 STORE IN MEMORY:
      - candle_close_bar = 111
      - candle_close_price = $175.25
      - volume_ratio = 0.6x (WEAK!)
      - candle_size_pct = 0.14%
   ↓
STATE 3: CANDLE_CLOSED
   ↓
   Analyze: volume = 0.6x (< 1.5x required)
           candle = 0.14% (< 0.3% required)
   ↓
   Classification: WEAK BREAKOUT
   ↓
STATE 4: WEAK_BREAKOUT_TRACKING
   ↓
   📝 START TRACKING:
      - sustained_hold_start_bar = 111
      - bars_held = 0
   ↓
   ┌───────────────┬─────────────────┐
   │               │                 │
   v               v                 v
OPTION A:      OPTION B:        OPTION C:
Pullback       Sustained        Failure
   │              │                 │
   v              v                 v
Bar 125:       Bar 135:         Bar 140:
Price          Held 24 bars     Price breaks
pulls to       (2 min)          back below
$174.60        above pivot      pivot
(0.2% from     ✓ CONFIRMED      ✗ RESET
pivot)
   │
   v
STATE 5: PULLBACK_RETEST
   ↓
   📝 STORE:
      - pullback_detected_at = bar 125
      - pullback_closest_price = $174.60
   ↓
   Wait for bounce (price > $174.85)
   ↓
   Bar 130: Price = $175.10 ✓ BOUNCED
   ↓
STATE 6: READY_TO_ENTER
   ↓
   entry_reason = "PULLBACK_RETEST"
   ↓
   ✅ ENTER TRADE
```

---

## Memory Structure

Instead of searching, we **store and update**:

```python
{
    'AAPL': {
        'state': 'WEAK_BREAKOUT_TRACKING',

        # Stored ONCE when detected:
        'breakout_bar': 100,
        'breakout_price': 175.02,
        'breakout_time': datetime(2025, 10, 9, 10, 45, 30),
        'pivot_price': 174.50,
        'side': 'LONG',

        # Stored when candle closes:
        'candle_close_bar': 111,
        'candle_close_price': 175.25,
        'volume_ratio': 0.6,
        'candle_size_pct': 0.0014,
        'breakout_type': 'WEAK',

        # Updated every bar:
        'highest_since_breakout': 175.80,
        'lowest_since_breakout': 174.60,
        'bars_held_above_pivot': 24,
        'last_check_bar': 135,

        # Entry readiness:
        'entry_reason': None  # or 'PULLBACK_RETEST', 'SUSTAINED_BREAK'
    }
}
```

---

## Key Benefits

### 1. No More Lookback Loops ✅

**Old way** (every bar):
```python
for i in range(current_idx - 36, current_idx):
    if bars[i].close > pivot:  # Search for breakout
        breakout_bar = i
        break

if breakout_bar is None:  # Aged out!
    return False, "No breakout detected"
```

**New way** (store once):
```python
# Bar 100: Store breakout ONCE
state.breakout_bar = 100
state.breakout_price = 175.02

# Bar 500: Just check state
if state.breakout_bar is not None:
    # We know there was a breakout, no search needed!
    bars_since = current_bar - state.breakout_bar  # 400 bars
```

---

### 2. Time-Based Freshness ✅

**Check if breakout is stale**:
```python
def check_freshness(symbol, current_bar, max_age_bars=600):
    age = current_bar - state.breakout_bar

    if age > 600:  # 50 minutes old
        state.reset()  # Too stale, forget it
        return False

    return True  # Still fresh
```

This replaces the broken 36-bar window with a configurable freshness check.

---

### 3. State Progression Tracking ✅

**Know exactly where we are**:
```python
if state.state == 'MONITORING':
    # Looking for breakout

elif state.state == 'BREAKOUT_DETECTED':
    # Found breakout, waiting for candle

elif state.state == 'WEAK_BREAKOUT_TRACKING':
    # Weak break, monitoring for pullback OR sustained

elif state.state == 'READY_TO_ENTER':
    # All conditions met, enter now!
```

No more confusion about which check failed.

---

### 4. Price Action Memory ✅

**Track extremes without re-scanning**:
```python
# Update every bar (O(1) operation):
if current_price > state.highest_since_breakout:
    state.highest_since_breakout = current_price

if current_price < state.lowest_since_breakout:
    state.lowest_since_breakout = current_price

# Then use for checks:
if state.lowest_since_breakout < pivot * 0.995:
    # Broke back through pivot, setup failed
    state.reset()
```

---

## Usage Example

```python
from breakout_state_tracker import BreakoutStateTracker

tracker = BreakoutStateTracker()

# Bar 100: Price breaks resistance
if current_price > resistance:
    tracker.update_breakout(
        symbol='AAPL',
        bar_idx=100,
        price=175.02,
        timestamp=datetime.now(),
        pivot=174.50,
        side='LONG'
    )

# Bar 111: Candle closes
if bar_idx == 111:
    tracker.update_candle_close(
        symbol='AAPL',
        bar_idx=111,
        price=175.25,
        timestamp=datetime.now(),
        volume_ratio=0.6,
        candle_size_pct=0.0014
    )

    # Classify breakout
    breakout_type = tracker.classify_breakout(
        symbol='AAPL',
        is_strong_volume=False,  # 0.6x < 1.5x
        is_large_candle=False    # 0.14% < 0.3%
    )
    # Result: 'WEAK' → Enters WEAK_BREAKOUT_TRACKING state

# Bars 112-135: Monitor price action
for bar_idx in range(112, 136):
    tracker.update_price_action(
        symbol='AAPL',
        current_price=bars[bar_idx].close,
        current_bar=bar_idx,
        timestamp=bars[bar_idx].time
    )

    # Check for pullback
    if tracker.check_pullback(symbol='AAPL', current_price=bars[bar_idx].close):
        print(f"Bar {bar_idx}: Pullback detected!")

    # Check for sustained hold
    if tracker.check_sustained_hold(
        symbol='AAPL',
        current_price=bars[bar_idx].close,
        current_bar=bar_idx,
        required_bars=24  # 2 minutes
    ):
        print(f"Bar {bar_idx}: Sustained break confirmed!")
        break

# Check if ready to enter
ready, reason, state_dict = tracker.is_ready_to_enter('AAPL')
if ready:
    print(f"Enter {reason}: {state_dict}")
```

---

## State Transitions

```
MONITORING
   ↓ (price breaks pivot)
BREAKOUT_DETECTED
   ↓ (candle closes)
CANDLE_CLOSED
   ↓ (analyze volume/momentum)
   ├─→ READY_TO_ENTER (if strong momentum)
   └─→ WEAK_BREAKOUT_TRACKING (if weak)
       ↓ (monitor price action)
       ├─→ PULLBACK_RETEST (if pullback detected)
       │   ↓ (bounce confirmed)
       │   └─→ READY_TO_ENTER
       ├─→ SUSTAINED_BREAK (if held 2+ min)
       │   └─→ READY_TO_ENTER
       └─→ FAILED (if breaks back through pivot)
           └─→ MONITORING (reset)
```

---

## Comparison: Old vs New

| Aspect | Old (Lookback Loop) | New (State Machine) |
|--------|---------------------|---------------------|
| **Breakout Detection** | Search 36 bars EVERY check | Store ONCE, remember forever |
| **Memory Usage** | Re-scan bars each time | O(1) per symbol |
| **Aging Out** | 93% fail after 36 bars | Configurable freshness (600 bars) |
| **State Tracking** | Implicit (via bar search) | Explicit (state enum) |
| **Price Extremes** | Re-scan window | Update incrementally |
| **Complexity** | O(n) searches per bar | O(1) state checks |
| **Failures** | "No breakout detected" after 36 bars | Only fails if setup actually fails |
| **Clarity** | Unclear which check failed | Exact state known at all times |

---

## Integration with Existing Code

The state tracker can replace the lookback loops in:

1. `check_hybrid_entry()` - Main confirmation logic
2. `check_pullback_retest()` - Pullback detection
3. `check_sustained_break()` - Sustained hold tracking

Each symbol gets its own state, tracked independently.

---

## Expected Performance Improvement

**With state machine**:
- ✅ No more "No breakout detected" after 3 minutes
- ✅ Tracks breakouts for up to 50 minutes (configurable)
- ✅ Clear state progression (know exactly where we are)
- ✅ O(1) complexity instead of O(n) searches
- ✅ Accurate time-based freshness checks
- ✅ Can implement complex logic (pullback + re-break)

**Backtest expectations**:
- Entries should happen within 1-5 minutes (not 47 minutes!)
- Win rate should improve (entering fresh setups)
- Fewer "Waiting for pullback" loops
- Clearer logging (state transitions visible)
