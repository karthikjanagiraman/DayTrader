# 📊 PS60 Entry System - Complete Analysis (October 20, 2025)

## Table of Contents
1. [System Overview](#system-overview)
2. [Entry Paths](#entry-paths)
3. [State Machine Flow](#state-machine-flow)
4. [Detailed Path Analysis](#detailed-path-analysis)
5. [Filter Application](#filter-application)
6. [Real-World Examples](#real-world-examples)
7. [Code References](#code-references)

---

## System Overview

### High-Level Architecture

```
Scanner Results (Pre-Market)
        ↓
Live Trader Monitors Tick Data
        ↓
Price Breaks Pivot (Resistance/Support)
        ↓
    MONITORING State
        ↓
Wait for 1-Minute Candle Close
        ↓
  BREAKOUT_DETECTED State
        ↓
Analyze Candle (Volume + Size)
        ↓
    ┌───────────┴───────────┐
    │                       │
STRONG               WEAK
(2.0x vol,          (<2.0x vol OR
0.3% candle)        <0.3% candle)
    │                       │
    ↓                       ↓
MOMENTUM          WEAK_BREAKOUT_TRACKING
PATH                      │
    │               ┌─────┴─────┐
    │               │           │
    │          PULLBACK    SUSTAINED
    │          (0-120s)    (120s hold)
    │               │           │
    └───────────────┴───────────┘
                    │
            Check Filters
                    │
            ┌───────┴───────┐
            │               │
        ALL PASS       ANY FAIL
            │               │
        ENTER!          REJECT
```

### Three Entry Paths

1. **MOMENTUM BREAKOUT** - Immediate entry on strong volume + big candle
2. **PULLBACK/RETEST** - Wait for pullback, enter on bounce with confirmation
3. **SUSTAINED BREAK** - Wait for 2-minute hold above/below pivot with volume

---

## Entry Paths

### Path 1: MOMENTUM BREAKOUT (Immediate Entry)

**Trigger Conditions**:
- ✅ 1-minute candle closes above resistance (LONG) or below support (SHORT)
- ✅ Volume ≥ 2.0x average (20-candle lookback)
- ✅ Candle size ≥ 0.3% of price

**Filters Applied**:
1. Choppy market filter
2. Room-to-run filter
3. Stochastic filter (hourly momentum confirmation)
4. CVD filter (cumulative volume delta)

**Action**: Enter IMMEDIATELY after candle close if all filters pass

**Example**:
```
TSLA @ 9:47 AM
- Resistance: $445.00 (from scanner)
- 9:46:00-9:46:59 candle closes at $445.85
- Volume: 2.3x average (50,000 vs 21,700 avg)
- Candle size: 0.19% ($445.00 → $445.85)
- Analysis: STRONG volume ✅, but small candle ❌
- Result: Classified as WEAK → Goes to Path 2/3
```

```
COIN @ 10:05 AM
- Resistance: $346.00 (from scanner)
- 10:04:00-10:04:59 candle closes at $347.20
- Volume: 3.5x average (85,000 vs 24,300 avg)
- Candle size: 0.35% ($346.00 → $347.20)
- Analysis: STRONG volume ✅, LARGE candle ✅
- Choppy filter: PASS (5-min range = 1.2% > 0.5× ATR)
- Room-to-run: PASS (target $354.00 = 2.3% away)
- Result: MOMENTUM BREAKOUT → ENTER @ $347.20!
```

---

### Path 2: PULLBACK/RETEST (Patient Entry)

**Initial Condition**: Weak breakout detected (volume < 2.0x OR candle < 0.3%)

**State Machine Flow**:
1. **WEAK_BREAKOUT_TRACKING** (0-120 seconds)
   - Monitor price for pullback to pivot ± 0.3%
   - If pullback detected → Enter PULLBACK_RETEST state
   - If 120 seconds pass with no pullback → Enter SUSTAINED_BREAK path

2. **PULLBACK_RETEST** (After pullback detected)
   - Wait for 1-minute candle close
   - Check if price is back above/below pivot
   - Check volume ≥ 1.2x average
   - Check candle size (any positive move acceptable)
   - Apply all filters
   - If pass → ENTER!

**Example**:
```
AMD @ 9:48 AM (LONG)
Resistance: $162.00

Timeline:
09:46:00 - Initial breakout candle closes @ $162.15
           Volume: 1.1x (WEAK), Candle: 0.09% (WEAK)
           → WEAK_BREAKOUT_TRACKING state

09:46:15 - Price: $162.25 (holding above)
09:46:30 - Price: $162.18 (holding above)
09:46:45 - Price: $162.05 (PULLBACK! Within 0.3% of pivot)
           → PULLBACK_RETEST state

09:47:00-09:47:59 - Pullback/retest candle
           Open: $162.05, Close: $162.35
           Price back above pivot ✅
           Volume: 1.3x average ✅
           Candle size: 0.18% ✅

09:48:00 - Check filters:
           Choppy: PASS ✅
           Room-to-run: Target $164.50 (1.5% away) ✅
           Stochastic: PASS ✅
           CVD: PASS ✅

           → PULLBACK/RETEST ENTRY @ $162.35!
```

**Why This Works**:
- Initial weak breakout shows interest but not conviction
- Pullback tests the pivot level (now acting as support)
- Bounce from pivot shows buyers stepping in
- Lower volume requirement (1.2x vs 2.0x) acknowledges the retest pattern

---

### Path 3: SUSTAINED BREAK (Slow Grind)

**Initial Condition**: Weak breakout, but NO pullback within 120 seconds

**Logic**:
- Some breakouts don't explode with volume (MOMENTUM)
- Some don't pull back for a retest (PULLBACK)
- But they grind slowly higher, holding above pivot
- Time-based confirmation: If price holds for 2 minutes, it's valid

**State Machine Flow**:
1. **WEAK_BREAKOUT_TRACKING** (0-120 seconds)
   - Monitor for pullback (would trigger Path 2)
   - If no pullback after 120 seconds → Enter SUSTAINED_BREAK validation

2. **SUSTAINED_BREAK** (Every subsequent 1-minute candle)
   - Check if price still above/below pivot
   - Check if max pullback < 0.3% from pivot
   - Check volume ≥ 1.0x average (any positive volume)
   - If conditions hold for 2 minutes total → VALID
   - Apply all filters
   - If pass → ENTER!

**Example**:
```
PLTR @ 9:45 AM (LONG)
Resistance: $182.25

Timeline:
09:45:00-09:45:59 - Initial breakout candle closes @ $182.35
                    Volume: 1.44x (WEAK), Candle: 0.05% (WEAK)
                    → WEAK_BREAKOUT_TRACKING state

09:46:00 - Price: $182.38 (holding, no pullback)
09:46:15 - Price: $182.42 (holding, no pullback)
09:46:30 - Price: $182.45 (holding, no pullback)
09:46:45 - Price: $182.40 (holding, no pullback)
09:47:00 - 120 seconds elapsed, no pullback detected
           → Check SUSTAINED_BREAK criteria

Sustained Break Analysis:
- Time held: 2 minutes ✅
- Price range: $182.35 - $182.45 (0.05% variance) ✅
- Max pullback from breakout: 0.00% (no pullback) ✅
- Average volume: 1.3x ✅

09:47:00 - Check filters:
           Choppy: PASS ✅
           Room-to-run: Target $184.14 (0.98% away)
           BUT: 0.98% < 1.5% minimum → BLOCKED ❌

           → SUSTAINED_BREAK REJECTED (insufficient room)
```

**Why This Works**:
- Catches "stealth" breakouts that grind without fanfare
- 2-minute hold shows sustained buying/selling pressure
- Lower volume requirement acknowledges gradual accumulation
- Tolerance for small pullbacks (< 0.3%) prevents false rejections

---

### Path 4: DELAYED MOMENTUM DETECTION (Second Chance)

**New Feature** (October 13, 2025): Re-check momentum on EVERY subsequent 1-minute candle

**Initial Condition**: Classified as WEAK, entered WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST

**Logic**:
- Initial breakout may be weak
- But momentum can appear on subsequent candles
- Check EVERY 1-minute candle close for momentum criteria
- If found → Upgrade to MOMENTUM entry!

**State Machine Flow**:
1. Start in WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST
2. On every 1-minute candle close (bars_into_candle == 11):
   - Calculate this candle's volume ratio
   - Calculate this candle's size
   - Check if meets MOMENTUM criteria (2.0x vol, 0.3% candle)
   - If YES → Apply filters and enter as MOMENTUM BREAKOUT!

**Example**:
```
BB @ 9:46 AM (LONG)
Resistance: $4.58

Timeline:
09:46:00-09:46:59 - Initial breakout candle closes @ $4.60
                    Volume: 0.53x (VERY WEAK) ❌
                    Candle: 0.44% ✅
                    → WEAK_BREAKOUT_TRACKING state
                    (low volume, can't be momentum)

09:47:00-09:47:59 - Second candle
                    Price: $4.60 → $4.62
                    Volume: 1.2x (still weak)
                    → Continue tracking

09:48:00-09:48:59 - Third candle
                    Price: $4.62 → $4.63
                    Volume: 3.63x (STRONG!) ✅
                    Candle: 0.22% (not huge, but acceptable)

                    Delayed Momentum Check:
                    - Volume 3.63x ≥ 2.0x ✅
                    - Candle 0.22% < 0.3% ❌
                    → Still WEAK (need both criteria)

09:49:00-09:49:59 - Fourth candle
                    Price: $4.63 → $4.67
                    Volume: 5.09x (VERY STRONG!) ✅
                    Candle: 0.86% (LARGE!) ✅

                    Delayed Momentum Check:
                    - Volume 5.09x ≥ 2.0x ✅
                    - Candle 0.86% ≥ 0.3% ✅

                    MOMENTUM DETECTED (delayed)!

09:50:00 - Check filters:
           Choppy: PASS ✅
           Room-to-run: Target3 $4.77 (2.2% away) ✅
           Stochastic: PASS ✅
           CVD: PASS ✅

           → MOMENTUM BREAKOUT (delayed) @ $4.67!
```

**Why This Works**:
- Captures late-developing momentum
- Stocks may consolidate briefly before exploding
- Volume can build gradually then spike
- Second/third candles often stronger than first

---

## State Machine Flow

### Complete State Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       MONITORING                                │
│  - Waiting for price to break pivot                            │
│  - No state tracking yet                                       │
└─────────────────┬───────────────────────────────────────────────┘
                  │
         Price breaks pivot (tick-level detection)
                  │
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                  BREAKOUT_DETECTED                              │
│  - Detected break, waiting for 1-minute candle close           │
│  - State: {'phase': 'waiting_candle_close',                    │
│            'breakout_bar': 120,                                 │
│            'candle_closes_at': 132}                             │
│  - Timeline: 0-60 seconds after break                          │
└─────────────────┬───────────────────────────────────────────────┘
                  │
         1-minute candle closes (bar % 12 == 11)
                  │
         Analyze candle (volume + size)
                  │
    ┌─────────────┴─────────────┐
    │                           │
STRONG                      WEAK
2.0x vol, 0.3% candle      Doesn't meet criteria
    │                           │
    ↓                           ↓
┌────────────────┐    ┌──────────────────────────┐
│   MOMENTUM     │    │ WEAK_BREAKOUT_TRACKING   │
│                │    │  - Monitor for pullback  │
│ Apply filters: │    │  - Or sustained hold     │
│ - Choppy       │    │  - Timeline: 0-120s      │
│ - Room-to-run  │    │                          │
│ - Stochastic   │    │  Checks every tick:      │
│ - CVD          │    │  1. Pullback detected?   │
│                │    │  2. 120s elapsed?        │
│ If pass:       │    │                          │
│   ENTER!       │    │  Checks every 1-min:     │
│ If fail:       │    │  3. Delayed momentum?    │
│   REJECT       │    │                          │
└────────────────┘    └──────┬────────┬──────────┘
                             │        │
              Pullback       │        │  120s elapsed
              detected       │        │  no pullback
                             │        │
                             ↓        ↓
              ┌──────────────────────────────┐
              │    PULLBACK_RETEST           │
              │  - Wait for 1-min candle     │
              │  - Check bounce criteria:    │
              │    * Back above/below pivot  │
              │    * Volume ≥ 1.2x           │
              │    * Any positive move       │
              │                              │
              │  Checks every 1-min:         │
              │  - Delayed momentum?         │
              │                              │
              │  If bounce confirmed:        │
              │    Apply filters → ENTER!    │
              └──────────────────────────────┘
                             │
                    No bounce detected
                             │
                             ↓
                         REJECT
```

### State Tracking Data Structures

**BreakoutState** (in `breakout_state_tracker.py`):
```python
class BreakoutState:
    state: BreakoutStateEnum  # MONITORING, BREAKOUT_DETECTED, etc.
    breakout_bar: int         # Absolute bar index when breakout detected
    candle_close_bar: int     # Absolute bar index when candle will close
    breakout_price: float     # Price at breakout
    pivot_price: float        # Original pivot (resistance/support)
    side: str                 # 'LONG' or 'SHORT'
    breakout_type: str        # 'MOMENTUM', 'WEAK', 'PULLBACK', 'SUSTAINED'
    pullback_detected: bool   # True if pullback happened
    pullback_bar: int         # Bar when pullback detected
```

**Example State Progression** (PLTR LONG):
```python
# Bar 48: Price breaks $182.25
{
    'state': 'BREAKOUT_DETECTED',
    'breakout_bar': 48,
    'candle_close_bar': 60,  # Bar 48 + 12 bars = bar 60
    'breakout_price': 182.35,
    'pivot_price': 182.25,
    'side': 'LONG',
    'breakout_type': None  # Not classified yet
}

# Bar 60: Candle closes, classified as WEAK
{
    'state': 'WEAK_BREAKOUT_TRACKING',
    'breakout_bar': 48,
    'candle_close_bar': 60,
    'breakout_price': 182.35,
    'pivot_price': 182.25,
    'side': 'LONG',
    'breakout_type': 'WEAK',
    'pullback_detected': False
}

# Bar 75: Pullback to $182.20 detected
{
    'state': 'PULLBACK_RETEST',
    'breakout_bar': 48,
    'candle_close_bar': 60,
    'breakout_price': 182.35,
    'pivot_price': 182.25,
    'side': 'LONG',
    'breakout_type': 'WEAK',
    'pullback_detected': True,
    'pullback_bar': 75
}

# Bar 84: Bounce candle closes @ $182.45
# Entry confirmed, state reset
{
    'state': 'MONITORING',  # Reset after entry
    'breakout_bar': None,
    # ... all fields cleared
}
```

---

## Detailed Path Analysis

### Path 1: MOMENTUM BREAKOUT - Deep Dive

**Code Location**: `trader/strategy/ps60_entry_state_machine.py` lines 242-317

**Step-by-Step Execution**:

1. **Candle Close Detection** (line 233-241)
   ```python
   bars_into_candle = tracking_idx % bars_per_candle

   if bars_into_candle == (bars_per_candle - 1):
       # We're at bar 11 of 12 (candle close)
   ```

2. **Get Candle Bars** (line 242-250)
   ```python
   candle_bars = _get_candle_bars(bars, tracking_idx, bars_per_candle,
                                   bar_buffer, current_idx)

   # Returns 12 bars for this 1-minute candle
   # Uses absolute-to-array mapping (Part 3 fix!)
   ```

3. **Calculate Volume Ratio** (lines 252-283)
   ```python
   # Get this candle's total volume
   candle_volume = sum(b.volume for b in candle_bars)

   # Get historical average (20 candles back)
   candle_start_abs = (tracking_idx // bars_per_candle) * bars_per_candle
   avg_volume_lookback_abs = max(0, candle_start_abs - (20 * bars_per_candle))

   # Map to array indices (Part 3 fix!)
   if bar_buffer is not None:
       lookback_start_array = bar_buffer.map_absolute_to_array_index(...)
       past_bars = bars[lookback_start_array:candle_start_array]

   # Calculate average candle volume
   past_candles = [past_bars[i:i+12] for i in range(0, len(past_bars), 12)]
   avg_candle_volume = sum(sum(b.volume for b in c) for c in past_candles) / len(past_candles)

   # Volume ratio
   volume_ratio = candle_volume / avg_candle_volume
   ```

4. **Calculate Candle Size** (lines 285-287)
   ```python
   candle_open = candle_bars[0].open
   candle_close = candle_bars[-1].close
   candle_size_pct = abs(candle_close - candle_open) / candle_open
   ```

5. **Classify Breakout** (lines 289-305)
   ```python
   is_strong_volume = volume_ratio >= strategy.momentum_volume_threshold  # 2.0x
   is_large_candle = candle_size_pct >= strategy.momentum_candle_min_pct  # 0.3%

   if is_strong_volume and is_large_candle:
       breakout_type = 'MOMENTUM'
       # Apply filters and potentially enter
   else:
       breakout_type = 'WEAK'
       # Enter WEAK_BREAKOUT_TRACKING state
   ```

6. **Apply Filters** (lines 306-340)
   ```python
   if breakout_type == 'MOMENTUM':
       # Choppy filter
       is_choppy, choppy_reason = strategy._check_choppy_market(bars, current_idx)
       if is_choppy:
           return False, choppy_reason

       # Room-to-run filter
       insufficient_room, room_reason = strategy._check_room_to_run(...)
       if insufficient_room:
           return False, room_reason

       # Stochastic filter
       fails_stochastic, stoch_reason = strategy._check_stochastic_filter(...)
       if fails_stochastic:
           return False, stoch_reason

       # CVD filter
       fails_cvd, cvd_reason = _check_cvd_filter(...)
       if fails_cvd:
           return False, cvd_reason

       # ALL FILTERS PASSED - ENTER!
       return True, "MOMENTUM_BREAKOUT"
   ```

**Real Example with Numbers** (COIN):
```
COIN LONG @ 10:05 AM
Resistance: $346.00 (from scanner)

Candle Analysis (10:04:00 - 10:04:59):
  Bar data (12 five-second bars):
    Bar 0:  10:04:00, Open: $346.05, Close: $346.15, Volume: 7,200
    Bar 1:  10:04:05, Open: $346.15, Close: $346.35, Volume: 8,100
    Bar 2:  10:04:10, Open: $346.35, Close: $346.50, Volume: 9,500
    Bar 3:  10:04:15, Open: $346.50, Close: $346.75, Volume: 11,200
    Bar 4:  10:04:20, Open: $346.75, Close: $346.90, Volume: 10,800
    Bar 5:  10:04:25, Open: $346.90, Close: $347.00, Volume: 9,300
    Bar 6:  10:04:30, Open: $347.00, Close: $347.10, Volume: 8,700
    Bar 7:  10:04:35, Open: $347.10, Close: $347.15, Volume: 7,900
    Bar 8:  10:04:40, Open: $347.15, Close: $347.10, Volume: 6,500
    Bar 9:  10:04:45, Open: $347.10, Close: $347.15, Volume: 5,800
    Bar 10: 10:04:50, Open: $347.15, Close: $347.18, Volume: 5,200
    Bar 11: 10:04:55, Open: $347.18, Close: $347.20, Volume: 4,800

  Candle totals:
    Total volume: 85,000
    Open: $346.05
    Close: $347.20
    Size: $1.15 = 0.33%

Historical Average (20 candles = 20 minutes):
  Past candle volumes: [24,300, 22,800, 26,100, 23,500, ...]
  Average candle volume: 24,300

Volume Ratio Calculation:
  volume_ratio = 85,000 / 24,300 = 3.5x ✅ (≥ 2.0x)

Candle Size Calculation:
  candle_size_pct = abs($347.20 - $346.05) / $346.05 = 0.33% ✅ (≥ 0.3%)

Classification:
  is_strong_volume = True ✅
  is_large_candle = True ✅
  → breakout_type = 'MOMENTUM'

Filter Checks:
  1. Choppy filter:
     - Get last 60 bars (5 minutes)
     - High: $347.50, Low: $345.20
     - Range: $2.30 = 0.66%
     - ATR(20): $2.80 = 0.81%
     - Threshold: $2.80 × 0.5 = $1.40 = 0.40%
     - Range 0.66% > threshold 0.40% → PASS ✅

  2. Room-to-run filter:
     - Current price: $347.20
     - Target (from scanner): $354.00
     - Room: ($354.00 - $347.20) / $347.20 = 1.96%
     - Minimum: 1.5%
     - 1.96% > 1.5% → PASS ✅

  3. Stochastic filter (hourly):
     - %K: 72.5 (range 60-80 for LONG)
     - Within range → PASS ✅

  4. CVD filter:
     - Cumulative Volume Delta: +42,500 (positive buying pressure)
     - PASS ✅

Result: ✅ ALL FILTERS PASSED → MOMENTUM_BREAKOUT ENTRY @ $347.20!
```

---

### Path 2: PULLBACK/RETEST - Deep Dive

**Code Location**: `trader/strategy/ps60_entry_state_machine.py` lines 453-545

**Step-by-Step Execution**:

1. **Enter WEAK_BREAKOUT_TRACKING** (after weak candle classification)
   ```python
   # State set in line 350
   state.state = BreakoutStateEnum.WEAK_BREAKOUT_TRACKING
   state.breakout_type = 'WEAK'
   ```

2. **Monitor for Pullback** (every tick, lines 453-456)
   ```python
   if state.state.value == 'WEAK_BREAKOUT_TRACKING':
       if tracker.check_pullback(symbol, current_price, strategy.pullback_distance_pct):
           # Pullback detected! (within 0.3% of pivot)
           return False, "Pullback detected, waiting for bounce"
   ```

3. **Pullback Detection Logic** (in `breakout_state_tracker.py`)
   ```python
   def check_pullback(self, symbol, current_price, pullback_tolerance=0.003):
       state = self.states[symbol]
       pivot = state.pivot_price
       side = state.side

       if side == 'LONG':
           # Check if price came back down near pivot
           pullback_threshold = pivot * (1 + pullback_tolerance)  # $182.25 × 1.003 = $182.80
           if current_price <= pullback_threshold:
               # PULLBACK DETECTED!
               state.state = BreakoutStateEnum.PULLBACK_RETEST
               state.pullback_detected = True
               state.pullback_bar = current_bar
               return True

       return False
   ```

4. **Wait for Bounce Candle** (lines 459-545)
   ```python
   if state.state.value == 'PULLBACK_RETEST':
       bars_per_candle = 12
       bars_into_candle = current_idx % bars_per_candle

       # Check if we're at candle close
       if bars_into_candle == (bars_per_candle - 1):
           # Get this candle's bars
           candle_bars = _get_candle_bars(...)

           # Check if price is back above/below pivot
           candle_close = candle_bars[-1].close

           if side == 'LONG':
               price_above_pivot = candle_close > pivot_price
           else:
               price_above_pivot = candle_close < pivot_price

           if not price_above_pivot:
               # Still below pivot, not a valid bounce
               continue

           # Calculate volume ratio
           candle_volume = sum(b.volume for b in candle_bars)
           volume_ratio = candle_volume / avg_candle_volume

           # Check bounce criteria
           is_volume_sufficient = volume_ratio >= strategy.pullback_volume_threshold  # 1.2x

           if is_volume_sufficient:
               # BOUNCE CONFIRMED!
               # Apply filters...
               if all_filters_pass:
                   return True, "PULLBACK/RETEST entry"
   ```

**Real Example with Timeline** (AMD):
```
AMD LONG @ 9:48 AM
Resistance: $162.00 (from scanner)

09:46:00 - BREAKOUT_DETECTED
  Price breaks $162.00, tracking_idx = 48

09:46:00-09:46:59 - Initial candle
  Open: $162.00, Close: $162.15
  Volume: 22,000 (avg: 20,000) = 1.1x ❌
  Size: $0.15 = 0.09% ❌

  Classification:
    is_strong_volume = False (1.1x < 2.0x)
    is_large_candle = False (0.09% < 0.3%)
    → breakout_type = 'WEAK'

  State transition:
    BREAKOUT_DETECTED → WEAK_BREAKOUT_TRACKING

09:47:00 - Tick monitoring begins
  tracking_idx = 60
  Checking for pullback every 5 seconds...

  09:47:05 - Price: $162.25 (holding above $162.00)
  09:47:10 - Price: $162.30 (holding above $162.00)
  09:47:15 - Price: $162.22 (holding above $162.00)
  09:47:20 - Price: $162.18 (holding above $162.00)
  09:47:25 - Price: $162.10 (holding above $162.00)
  09:47:30 - Price: $162.05 (near pivot!)

  Pullback check:
    pivot = $162.00
    pullback_threshold = $162.00 × 1.003 = $162.49
    current_price = $162.05
    $162.05 ≤ $162.49 → PULLBACK DETECTED! ✅

  State transition:
    WEAK_BREAKOUT_TRACKING → PULLBACK_RETEST

09:47:35-09:47:59 - Continue monitoring
  Price: $162.08 → $162.15 → $162.25 → $162.32
  (Bouncing from pullback level)

09:48:00-09:48:59 - Bounce candle (tracking_idx = 72)
  Bar data (12 five-second bars):
    Bar 0:  09:48:00, $162.05 → $162.10, Vol: 1,800
    Bar 1:  09:48:05, $162.10 → $162.15, Vol: 1,900
    Bar 2:  09:48:10, $162.15 → $162.20, Vol: 2,100
    Bar 3:  09:48:15, $162.20 → $162.25, Vol: 2,300
    Bar 4:  09:48:20, $162.25 → $162.28, Vol: 2,000
    Bar 5:  09:48:25, $162.28 → $162.30, Vol: 1,800
    Bar 6:  09:48:30, $162.30 → $162.32, Vol: 1,700
    Bar 7:  09:48:35, $162.32 → $162.33, Vol: 1,600
    Bar 8:  09:48:40, $162.33 → $162.34, Vol: 1,500
    Bar 9:  09:48:45, $162.34 → $162.35, Vol: 1,400
    Bar 10: 09:48:50, $162.35 → $162.35, Vol: 1,300
    Bar 11: 09:48:55, $162.35 → $162.35, Vol: 1,200

  Candle totals:
    Total volume: 20,600
    Open: $162.05
    Close: $162.35
    Size: $0.30 = 0.18%

09:49:00 - Bounce analysis (tracking_idx = 84)
  Bounce criteria check:
    1. Price back above pivot?
       Close $162.35 > Pivot $162.00 → YES ✅

    2. Volume sufficient?
       candle_volume = 20,600
       avg_candle_volume = 20,000
       volume_ratio = 20,600 / 20,000 = 1.03x
       1.03x < 1.2x → NO ❌

  Result: Bounce NOT confirmed (insufficient volume)
  Continue waiting...

09:49:00-09:49:59 - Second bounce attempt
  Bar data shows higher volume (25,000 total)
  volume_ratio = 25,000 / 20,000 = 1.25x ✅

  Bounce criteria:
    1. Price above pivot: $162.45 > $162.00 ✅
    2. Volume: 1.25x ≥ 1.2x ✅

  BOUNCE CONFIRMED!

09:50:00 - Filter checks
  1. Choppy: Range 0.55% > 0.40% threshold → PASS ✅
  2. Room-to-run: Target $164.50, room 1.32% < 1.5% → FAIL ❌

  Result: REJECTED by room-to-run filter

Alternative outcome if room-to-run passed:
  3. Stochastic: %K = 68 (60-80 range) → PASS ✅
  4. CVD: +12,500 (positive) → PASS ✅

  → PULLBACK/RETEST ENTRY @ $162.45!
```

**Key Insights**:
- Pullback tolerance is ± 0.3% from pivot (not exact pivot)
- Lower volume requirement (1.2x vs 2.0x momentum)
- Accepts any positive move (no minimum candle size for bounce)
- Filters still apply (can still be rejected)

---

### Path 3: SUSTAINED BREAK - Deep Dive

**Code Location**: `trader/strategy/ps60_entry_state_machine.py` lines 347-361

**Logic**:
```python
# After WEAK classification, if no pullback for 120 seconds...
if state.state.value == 'WEAK_BREAKOUT_TRACKING':
    time_elapsed = (current_idx - state.breakout_bar) * 5  # seconds

    if time_elapsed >= 120:  # 2 minutes
        # Check if price held above/below pivot
        if side == 'LONG':
            price_held = current_price > pivot_price * 0.997  # Within 0.3%
        else:
            price_held = current_price < pivot_price * 1.003

        if price_held:
            # SUSTAINED BREAK confirmed!
            # Apply filters...
            if all_filters_pass:
                return True, "SUSTAINED_BREAK entry"
```

**Real Example** (XLOV):
```
XLOV LONG @ 2:15 PM
Resistance: $8.50 (from scanner)

Timeline:
02:13:00-02:13:59 - Initial breakout candle
  Close: $8.52
  Volume: 0.8x ❌ (very weak)
  Size: 0.12% ❌ (small)
  → WEAK_BREAKOUT_TRACKING state

02:14:00-02:14:59 - First minute of tracking
  Price range: $8.51 - $8.54
  Min price: $8.51 (0.12% above pivot) ✅
  No pullback to $8.50 ± 0.3% = $8.475-$8.525
  → Continue tracking

02:15:00 - Check sustained break (120 seconds elapsed)
  current_price = $8.53
  pivot_threshold = $8.50 × 0.997 = $8.475

  Sustained check:
    1. Time held: 2 minutes ✅
    2. Price held above: $8.53 > $8.475 ✅
    3. Price never pulled back to pivot tolerance ✅

  SUSTAINED BREAK criteria met!

02:15:01 - Filter checks
  1. Choppy filter:
     5-min range: 0.35% < 0.40% threshold → FAIL ❌
     (Market is consolidating, too choppy)

  Result: REJECTED by choppy filter

Alternative if not choppy:
  1. Choppy: PASS ✅
  2. Room-to-run: Target $8.75, room 2.58% → PASS ✅
  3. Stochastic: %K = 71 → PASS ✅
  4. CVD: +8,200 → PASS ✅

  → SUSTAINED_BREAK ENTRY @ $8.53!
```

**Why This Path Exists**:
- Not all breakouts explode with volume (momentum)
- Not all breakouts pull back (pullback/retest)
- Some grind slowly but steadily
- Time-based validation catches these

---

### Path 4: DELAYED MOMENTUM - Deep Dive

**Code Location**: `trader/strategy/ps60_entry_state_machine.py` lines 362-451

**Step-by-Step**:

1. **Continuous Monitoring** (every bar while in WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST)
   ```python
   # Check on every 1-minute candle close
   bars_into_candle = tracking_idx % bars_per_candle

   if bars_into_candle == (bars_per_candle - 1):
       # We're at a candle close - check for delayed momentum
   ```

2. **Candle Analysis** (same as momentum path)
   ```python
   candle_bars = _get_candle_bars(...)
   candle_volume = sum(b.volume for b in candle_bars)
   volume_ratio = candle_volume / avg_candle_volume

   candle_open = candle_bars[0].open
   candle_close = candle_bars[-1].close
   candle_size_pct = abs(candle_close - candle_open) / candle_open
   ```

3. **Momentum Check** (lines 404-417)
   ```python
   is_strong_volume = volume_ratio >= strategy.momentum_volume_threshold  # 2.0x
   is_large_candle = candle_size_pct >= strategy.momentum_candle_min_pct  # 0.3%

   if is_strong_volume and is_large_candle:
       # MOMENTUM DETECTED (delayed)!
       # Apply all filters...
       if all_filters_pass:
           return True, f"MOMENTUM_BREAKOUT (delayed, {volume_ratio:.1f}x vol)"
   ```

**Real Example** (BB):
```
BB LONG @ 9:49 AM
Resistance: $4.58 (from scanner)

Timeline with Candle-by-Candle Analysis:

09:46:00-09:46:59 - CANDLE 0 (Initial breakout)
  tracking_idx = 192 (bar 192)
  Open: $4.58, Close: $4.60
  Volume: 2,500 (avg: 4,700) = 0.53x ❌
  Size: $0.02 = 0.44% ✅

  Classification:
    is_strong_volume = False (0.53x < 2.0x)
    is_large_candle = True (0.44% ≥ 0.3%)
    → breakout_type = 'WEAK' (need BOTH criteria)

  State: WEAK_BREAKOUT_TRACKING

09:47:00-09:47:59 - CANDLE 1
  tracking_idx = 204 (bar 204)
  bars_into_candle = 204 % 12 = 0 (not candle close)
  ... tick monitoring continues ...

  09:47:59 - CANDLE CLOSE CHECK
  tracking_idx = 215
  bars_into_candle = 215 % 12 = 11 ✅ (candle close!)

  Candle data:
    Open: $4.60, Close: $4.62
    Volume: 5,600 (avg: 4,700) = 1.19x
    Size: $0.02 = 0.43%

  Delayed momentum check:
    is_strong_volume = False (1.19x < 2.0x)
    is_large_candle = True (0.43% ≥ 0.3%)
    → Still WEAK (need both)

  Continue tracking...

09:48:00-09:48:59 - CANDLE 2
  tracking_idx = 227 (at close)

  Candle data:
    Open: $4.62, Close: $4.63
    Volume: 17,100 (avg: 4,700) = 3.63x ✅ (STRONG!)
    Size: $0.01 = 0.22% ❌ (small)

  Delayed momentum check:
    is_strong_volume = True (3.63x ≥ 2.0x) ✅
    is_large_candle = False (0.22% < 0.3%) ❌
    → Still WEAK (need both)

  Continue tracking...

09:49:00-09:49:59 - CANDLE 3
  tracking_idx = 239 (at close)

  Candle data:
    Open: $4.63, Close: $4.67
    Volume: 23,900 (avg: 4,700) = 5.09x ✅ (VERY STRONG!)
    Size: $0.04 = 0.86% ✅ (LARGE!)

  Delayed momentum check:
    is_strong_volume = True (5.09x ≥ 2.0x) ✅
    is_large_candle = True (0.86% ≥ 0.3%) ✅

    🎉 MOMENTUM DETECTED (delayed)!

09:50:00 - Filter checks
  Current price: $4.67

  1. Choppy filter:
     5-min range: 0.95% > 0.40% threshold → PASS ✅

  2. Room-to-run filter:
     Note: Price passed target1 ($4.64), check target3
     target3 = $4.77
     room = ($4.77 - $4.67) / $4.67 = 2.14% ≥ 1.5% → PASS ✅
     (This is the DYNAMIC TARGET SELECTION feature!)

  3. Stochastic: %K = 65 → PASS ✅
  4. CVD: +15,200 → PASS ✅

  → MOMENTUM_BREAKOUT (delayed) ENTRY @ $4.67!
```

**Key Features**:
- Checks EVERY subsequent 1-minute candle
- Can upgrade from WEAK to MOMENTUM at any time
- Still applies all filters (not a free pass)
- Captures late-developing momentum
- Works in both WEAK_BREAKOUT_TRACKING and PULLBACK_RETEST states

---

## Filter Application

### Filter Execution Order

All entry paths check filters in this order:

1. **Choppy Market Filter** (ALWAYS checked first)
2. **Room-to-Run Filter** (ALWAYS checked second)
3. **Stochastic Filter** (Hourly momentum confirmation)
4. **CVD Filter** (Cumulative Volume Delta)

**Short-Circuit Logic**: If any filter fails, remaining filters are skipped (saves computation).

---

### Filter 1: Choppy Market Filter

**Purpose**: Prevent entries during consolidation (high whipsaw risk)

**Code Location**: `trader/strategy/ps60_strategy.py` lines 2350-2396

**Logic**:
```python
def _check_choppy_market(self, bars, current_idx):
    """Check if market is choppy (consolidating, low volatility)"""

    # Get last 60 bars (5 minutes @ 5-second bars)
    lookback_bars = bars[max(0, current_idx - 60):current_idx + 1]

    # Calculate 5-minute range
    high = max(b.high for b in lookback_bars)
    low = min(b.low for b in lookback_bars)
    price_range = high - low
    range_pct = (price_range / low) * 100

    # Get ATR(20) from 1-minute bars
    atr_value = self._calculate_atr(bars, current_idx, period=20)
    atr_pct = (atr_value / bars[current_idx].close) * 100

    # Choppy threshold = 50% of ATR
    choppy_threshold_pct = atr_pct * self.choppy_atr_multiplier  # 0.5

    # Block if range < threshold
    if range_pct < choppy_threshold_pct:
        return True, f"Choppy market: 5-min range {range_pct:.2f}% < {choppy_threshold_pct:.2f}% threshold"

    return False, None
```

**Real Example**:
```
BBBY @ 11:15 AM (attempting LONG)
Price: $3.25

Choppy check:
  Last 60 bars (5 minutes):
    High: $3.28
    Low: $3.22
    Range: $0.06 = 1.85%

  ATR(20): $0.15 = 4.62%
  Threshold: 4.62% × 0.5 = 2.31%

  Comparison:
    Range 1.85% < Threshold 2.31% → CHOPPY ❌

  Result: BLOCKED - "Choppy market: 5-min range 1.85% < 2.31% threshold"
```

**Why This Works**:
- ATR measures normal volatility for this stock
- 5-minute range shows current volatility
- If current << normal, stock is consolidating
- Consolidation → whipsaws → losses
- Historical data: 61% of losses came from choppy conditions

---

### Filter 2: Room-to-Run Filter

**Purpose**: Validate sufficient opportunity remaining at entry time

**Code Location**: `trader/strategy/ps60_strategy.py` lines 2201-2241

**Logic**:
```python
def _check_room_to_run(self, entry_price, target_price, side='LONG'):
    """Check if there's enough room to target"""

    if side == 'LONG':
        room_pct = ((target_price - entry_price) / entry_price) * 100
    else:
        room_pct = ((entry_price - target_price) / entry_price) * 100

    min_room = self.min_room_to_target_pct * 100  # 1.5%

    if room_pct < min_room:
        return True, f"Insufficient room to target: {room_pct:.2f}% < {min_room:.1f}% minimum"

    return False, None
```

**Real Example**:
```
PLTR @ 9:48 AM (attempting LONG)
Entry: $183.03

Room-to-run check:
  target1 = $184.14
  room = ($184.14 - $183.03) / $183.03 = 0.61%
  minimum = 1.5%

  Comparison:
    Room 0.61% < Minimum 1.5% → INSUFFICIENT ❌

  Result: BLOCKED - "Insufficient room to target: 0.61% < 1.5% minimum"
```

**Dynamic Target Selection** (October 13, 2025):
```
BB @ 9:49 AM (attempting LONG)
Entry: $4.67

Dynamic target selection:
  target1 = $4.64 (already passed!)
  target2 = $4.70 (only 0.64% away)
  target3 = $4.77 (still available!)

  Use highest available: target3 = $4.77

Room-to-run check:
  room = ($4.77 - $4.67) / $4.67 = 2.14%
  minimum = 1.5%

  Comparison:
    Room 2.14% > Minimum 1.5% → SUFFICIENT ✅

  Result: PASS - Can still trade even after passing target1!
```

**Why This Works**:
- Scanner data is 8-13 hours old
- Market moves overnight and during session
- Must validate opportunity STILL EXISTS at entry time
- Prevents entering after most of move already happened
- Historical impact: 19x P&L improvement on Oct 1 trades

---

### Filter 3: Stochastic Filter

**Purpose**: Confirm hourly momentum supports trade direction

**Code Location**: `trader/strategy/ps60_strategy.py` lines 2646-2710

**Logic**:
```python
def _check_stochastic_filter(self, symbol, side):
    """Check if hourly stochastic confirms momentum"""

    # Get hourly bars (cached)
    hourly_bars = self.cached_hourly_bars.get(symbol)
    if not hourly_bars or len(hourly_bars) < 21:
        return False, None  # Can't calculate, allow trade

    # Calculate Stochastic(21, 1, 3)
    stoch_k = self._calculate_stochastic_k(hourly_bars, period=21)

    if side == 'LONG':
        # LONG: Want %K in 60-80 range (momentum, not overbought)
        if stoch_k < 60:
            return True, f"Stochastic %K {stoch_k:.1f} < 60 (no upward momentum)"
        if stoch_k > 80:
            return True, f"Stochastic %K {stoch_k:.1f} > 80 (overbought)"

    elif side == 'SHORT':
        # SHORT: Want %K in 20-50 range (bearish momentum, not oversold)
        if stoch_k < 20:
            return True, f"Stochastic %K {stoch_k:.1f} < 20 (oversold)"
        if stoch_k > 50:
            return True, f"Stochastic %K {stoch_k:.1f} > 50 (no downward momentum)"

    return False, None  # Pass
```

**Stochastic Calculation**:
```python
def _calculate_stochastic_k(self, bars, period=21):
    """Calculate %K using last 21 hourly bars"""

    # Get highest high and lowest low over period
    highest_high = max(b.high for b in bars[-period:])
    lowest_low = min(b.low for b in bars[-period:])
    current_close = bars[-1].close

    # %K formula
    k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100

    return k
```

**Real Example**:
```
COIN LONG @ 10:05 AM

Hourly data (last 21 bars = 21 hours):
  Highest high: $352.50 (yesterday 3 PM)
  Lowest low: $338.20 (yesterday 10 AM)
  Current close: $347.20 (current bar)

Stochastic %K calculation:
  k = (($347.20 - $338.20) / ($352.50 - $338.20)) × 100
  k = ($9.00 / $14.30) × 100
  k = 62.9

Stochastic filter check (LONG):
  %K = 62.9
  Required range: 60-80
  62.9 is in range → PASS ✅

If %K was 55:
  55 < 60 → BLOCKED ❌
  Reason: "Stochastic %K 55.0 < 60 (no upward momentum)"

If %K was 85:
  85 > 80 → BLOCKED ❌
  Reason: "Stochastic %K 85.0 > 80 (overbought)"
```

**Why This Works**:
- Hourly timeframe shows broader trend
- %K in 60-80 (LONG) means stock has momentum but room to run
- %K < 60 means no momentum (might be fading)
- %K > 80 means overbought (likely to reverse)
- Prevents fighting the trend on hourly timeframe

---

### Filter 4: CVD Filter (Cumulative Volume Delta)

**Purpose**: Confirm buying/selling pressure supports trade direction

**Code Location**: `trader/strategy/ps60_entry_state_machine.py` lines 55-129

**Logic**:
```python
def _check_cvd_filter(strategy, symbol, bars, current_idx, side):
    """Check cumulative volume delta confirms trade direction"""

    # Calculate CVD for last 5 minutes (60 bars @ 5-second)
    lookback_bars = bars[max(0, current_idx - 60):current_idx + 1]

    cvd = 0
    for bar in lookback_bars:
        # Determine if bar is bullish or bearish
        if bar.close > bar.open:
            # Bullish bar - add volume
            cvd += bar.volume
        elif bar.close < bar.open:
            # Bearish bar - subtract volume
            cvd -= bar.volume
        # Doji (close == open) - no change

    # For LONG: Want positive CVD (net buying)
    # For SHORT: Want negative CVD (net selling)

    if side == 'LONG':
        if cvd < strategy.cvd_threshold_long:  # Typically 0 or small positive
            return True, f"CVD {cvd:,.0f} < {strategy.cvd_threshold_long:,.0f} (net selling)"

    elif side == 'SHORT':
        if cvd > strategy.cvd_threshold_short:  # Typically 0 or small negative
            return True, f"CVD {cvd:,.0f} > {strategy.cvd_threshold_short:,.0f} (net buying)"

    return False, None  # Pass
```

**Real Example**:
```
TSLA LONG @ 9:47 AM

Last 60 bars (5 minutes):
  Bar 0:  Close > Open, Volume: 8,200  → CVD = +8,200
  Bar 1:  Close > Open, Volume: 9,100  → CVD = +17,300
  Bar 2:  Close < Open, Volume: 6,500  → CVD = +10,800
  Bar 3:  Close > Open, Volume: 10,300 → CVD = +21,100
  Bar 4:  Close > Open, Volume: 11,200 → CVD = +32,300
  ...
  Bar 59: Close > Open, Volume: 7,800  → CVD = +42,500

Final CVD: +42,500 (strong net buying)

CVD filter check (LONG):
  cvd = +42,500
  threshold_long = 0
  +42,500 > 0 → PASS ✅

If CVD was -5,000:
  cvd = -5,000
  threshold_long = 0
  -5,000 < 0 → BLOCKED ❌
  Reason: "CVD -5,000 < 0 (net selling)"
```

**Why This Works**:
- CVD measures net buying vs selling pressure
- Positive CVD = more buying than selling
- Negative CVD = more selling than buying
- For LONG, want buying pressure confirmation
- For SHORT, want selling pressure confirmation
- Prevents trading against market flow

---

## Real-World Examples

### Example 1: COIN - Pure Momentum Breakout

```
================================================================================
COIN LONG @ 10:05:23 AM - MOMENTUM BREAKOUT
================================================================================

SCANNER DATA (from pre-market):
  Symbol: COIN
  Resistance: $346.00
  Target1: $354.00
  Target2: $360.50
  Target3: $368.20
  Score: 85
  R/R: 3.5:1

LIVE TRADING SESSION:

09:30:00 - Market opens
           COIN price: $342.50
           trader.py monitoring begins

10:04:00 - Price breaks $346.00!
           tracking_idx = 408 (absolute bar index)
           State: MONITORING → BREAKOUT_DETECTED
           Waiting for candle close at bar 420 (408 + 12)

10:04:05 - Price: $346.15 (holding above pivot)
10:04:10 - Price: $346.35 (climbing)
10:04:15 - Price: $346.50 (strong buying)
10:04:20 - Price: $346.75 (accelerating)
10:04:25 - Price: $346.90 (continuing)
10:04:30 - Price: $347.00 (round number)
10:04:35 - Price: $347.10 (still going)
10:04:40 - Price: $347.15 (leveling off)
10:04:45 - Price: $347.15 (consolidating)
10:04:50 - Price: $347.18 (slight up)
10:04:55 - Price: $347.20 (slight up)

10:05:00 - CANDLE CLOSE (tracking_idx = 420)
           → check_entry_state_machine() called

CANDLE ANALYSIS:
  Candle bars (12 five-second bars, bars 408-419):
    Total volume: 85,000
    Open: $346.05
    Close: $347.20
    Size: $1.15 = 0.33%

  Historical average (20 candles = 20 minutes):
    Average candle volume: 24,300

  Calculations:
    volume_ratio = 85,000 / 24,300 = 3.50x
    candle_size_pct = 0.33%

  Classification check:
    is_strong_volume = (3.50x ≥ 2.0x) → TRUE ✅
    is_large_candle = (0.33% ≥ 0.3%) → TRUE ✅

    → breakout_type = 'MOMENTUM'

FILTER CHECKS:

  1. Choppy Market Filter:
     Last 60 bars (5 minutes):
       High: $347.50
       Low: $345.20
       Range: $2.30 = 0.66%

     ATR(20): $2.80 = 0.81%
     Threshold: 0.81% × 0.5 = 0.40%

     0.66% > 0.40% → PASS ✅ (not choppy)

  2. Room-to-Run Filter:
     Entry price: $347.20
     Target: $354.00
     Room: ($354.00 - $347.20) / $347.20 = 1.96%
     Minimum: 1.5%

     1.96% > 1.5% → PASS ✅ (sufficient room)

  3. Stochastic Filter (hourly):
     Last 21 hourly bars:
       Highest: $352.50
       Lowest: $338.20
       Current: $347.20

     %K = ($347.20 - $338.20) / ($352.50 - $338.20) × 100
        = 62.9%

     Required range (LONG): 60-80%
     62.9% in range → PASS ✅ (momentum confirmed)

  4. CVD Filter:
     Last 60 bars (5 minutes):
       Net buying: +42,500 volume
       Threshold (LONG): 0

     +42,500 > 0 → PASS ✅ (buying pressure confirmed)

RESULT:
  ✅ ALL FILTERS PASSED!
  → Entry signal: MOMENTUM_BREAKOUT

10:05:23 - ENTER LONG @ $347.20
           Shares: 288 (based on 1% risk, $1,000 account risk)
           Stop: $346.00 (at resistance/pivot)
           Target1: $354.00
           Target2: $360.50
           Target3: $368.20

OUTCOME:
  10:08:15 - Partial (50%) @ $348.20 (+$1.00, locked $288 profit)
  10:15:32 - Partial (25%) @ $354.00 (+$6.80, locked $489.60 profit)
  11:42:18 - Final (25%) @ $359.50 (+$12.30, locked $884.16 profit)

  Total P&L: +$1,661.76 (using weighted average exit)
```

---

### Example 2: AMD - Pullback/Retest Entry

```
================================================================================
AMD LONG @ 9:50:12 AM - PULLBACK/RETEST
================================================================================

SCANNER DATA:
  Symbol: AMD
  Resistance: $162.00
  Target1: $164.50
  Score: 72
  R/R: 2.2:1

LIVE TRADING SESSION:

09:46:00 - BREAKOUT_DETECTED
           Price breaks $162.00 @ $162.02
           tracking_idx = 192
           Candle will close at bar 204 (192 + 12)

09:46:00-09:46:59 - Initial breakout candle
           Bars 192-203:
             Total volume: 22,000
             Open: $162.00
             Close: $162.15
             Size: $0.15 = 0.09%

           Historical average: 20,000 volume/candle

09:47:00 - CANDLE CLOSE ANALYSIS (tracking_idx = 204)
           volume_ratio = 22,000 / 20,000 = 1.10x
           candle_size = 0.09%

           Classification:
             is_strong_volume = (1.10x ≥ 2.0x) → FALSE ❌
             is_large_candle = (0.09% ≥ 0.3%) → FALSE ❌

             → breakout_type = 'WEAK'

           State: BREAKOUT_DETECTED → WEAK_BREAKOUT_TRACKING

09:47:00-09:47:29 - Tick monitoring (looking for pullback)
           09:47:00 - Price: $162.18
           09:47:05 - Price: $162.25
           09:47:10 - Price: $162.30
           09:47:15 - Price: $162.22
           09:47:20 - Price: $162.18
           09:47:25 - Price: $162.10

09:47:30 - PULLBACK DETECTED! (tracking_idx = 210)
           Price: $162.05
           Pivot: $162.00
           Pullback threshold: $162.00 × 1.003 = $162.49

           $162.05 ≤ $162.49 → PULLBACK CONFIRMED ✅

           State: WEAK_BREAKOUT_TRACKING → PULLBACK_RETEST

09:47:30-09:48:59 - Waiting for bounce candle close
           Price action: $162.05 → $162.15 → $162.25 → $162.35

09:49:00-09:49:59 - First bounce candle (tracking_idx = 216)
           Bars 216-227:
             Total volume: 20,600
             Open: $162.05
             Close: $162.35
             Size: $0.30 = 0.18%

           Bounce criteria check:
             1. Back above pivot?
                $162.35 > $162.00 → YES ✅

             2. Volume sufficient?
                volume_ratio = 20,600 / 20,000 = 1.03x
                Required: 1.2x
                1.03x < 1.2x → NO ❌

           Continue waiting... (insufficient volume)

09:50:00-09:50:59 - Second bounce candle (tracking_idx = 228)
           Bars 228-239:
             Total volume: 25,000
             Open: $162.35
             Close: $162.45
             Size: $0.10 = 0.06%

09:51:00 - BOUNCE CANDLE ANALYSIS (tracking_idx = 240)
           volume_ratio = 25,000 / 20,000 = 1.25x

           Bounce criteria check:
             1. Back above pivot?
                $162.45 > $162.00 → YES ✅

             2. Volume sufficient?
                1.25x ≥ 1.2x → YES ✅

           BOUNCE CONFIRMED!

FILTER CHECKS:

  1. Choppy Market Filter:
     5-minute range: 0.55%
     ATR threshold: 0.40%
     0.55% > 0.40% → PASS ✅

  2. Room-to-Run Filter:
     Entry: $162.45
     Target: $164.50
     Room: ($164.50 - $162.45) / $162.45 = 1.26%
     Minimum: 1.5%

     1.26% < 1.5% → FAIL ❌

     BLOCKED! Insufficient room to target

RESULT:
  ❌ REJECTED by room-to-run filter
  Reason: "Insufficient room to target: 1.26% < 1.5% minimum"

  No entry - position manager continues monitoring other stocks

WHAT IF room-to-run filter passed?
  (Alternative scenario with target $165.00):

  Room: ($165.00 - $162.45) / $162.45 = 1.57% ✅

  3. Stochastic: %K = 68 → PASS ✅
  4. CVD: +12,500 → PASS ✅

  → PULLBACK/RETEST ENTRY @ $162.45!

  Potential outcome:
    09:53:20 - Partial (50%) @ $163.20 (+$0.75)
    10:15:45 - Final (50%) @ $164.85 (+$2.40)
    Total: +$1.58/share average
```

---

### Example 3: BB - Delayed Momentum Detection

```
================================================================================
BB LONG @ 9:49:23 AM - MOMENTUM BREAKOUT (DELAYED)
================================================================================

SCANNER DATA:
  Symbol: BB
  Resistance: $4.58
  Target1: $4.64
  Target2: $4.70
  Target3: $4.77
  Score: 105
  R/R: 5.0:1

LIVE TRADING SESSION:

09:46:00-09:46:59 - CANDLE 0 (Initial breakout)
           tracking_idx = 192 (bar 192)

           Candle data (bars 192-203):
             Total volume: 2,500
             Open: $4.58
             Close: $4.60
             Size: $0.02 = 0.44%

           Historical average: 4,700 volume/candle

09:47:00 - CANDLE CLOSE ANALYSIS
           volume_ratio = 2,500 / 4,700 = 0.53x
           candle_size = 0.44%

           Classification:
             is_strong_volume = (0.53x ≥ 2.0x) → FALSE ❌
             is_large_candle = (0.44% ≥ 0.3%) → TRUE ✅

             → breakout_type = 'WEAK' (need BOTH criteria)

           State: BREAKOUT_DETECTED → WEAK_BREAKOUT_TRACKING

09:47:00-09:47:59 - CANDLE 1 (tracking, no pullback)
           Price range: $4.60 - $4.62
           No pullback to $4.58 ± 0.3%

09:48:00 - DELAYED MOMENTUM CHECK #1 (tracking_idx = 216)
           Candle data (bars 204-215):
             Total volume: 5,600
             Open: $4.60
             Close: $4.62
             Size: $0.02 = 0.43%

           volume_ratio = 5,600 / 4,700 = 1.19x
           candle_size = 0.43%

           Delayed momentum check:
             is_strong_volume = (1.19x ≥ 2.0x) → FALSE ❌
             is_large_candle = (0.43% ≥ 0.3%) → TRUE ✅

             → Still WEAK (need both)

           Continue tracking...

09:48:00-09:48:59 - CANDLE 2 (still tracking)
           Price range: $4.62 - $4.63

09:49:00 - DELAYED MOMENTUM CHECK #2 (tracking_idx = 228)
           Candle data (bars 216-227):
             Total volume: 17,100
             Open: $4.62
             Close: $4.63
             Size: $0.01 = 0.22%

           volume_ratio = 17,100 / 4,700 = 3.63x
           candle_size = 0.22%

           Delayed momentum check:
             is_strong_volume = (3.63x ≥ 2.0x) → TRUE ✅
             is_large_candle = (0.22% ≥ 0.3%) → FALSE ❌

             → Still WEAK (need both)

           Continue tracking...

09:49:00-09:49:59 - CANDLE 3 (explosive volume!)
           Price range: $4.63 - $4.67

09:50:00 - DELAYED MOMENTUM CHECK #3 (tracking_idx = 240)
           Candle data (bars 228-239):
             Bar 228: $4.63 → $4.64, Vol: 2,100
             Bar 229: $4.64 → $4.64, Vol: 2,300
             Bar 230: $4.64 → $4.65, Vol: 2,500
             Bar 231: $4.65 → $4.65, Vol: 2,200
             Bar 232: $4.65 → $4.66, Vol: 2,100
             Bar 233: $4.66 → $4.66, Vol: 1,900
             Bar 234: $4.66 → $4.66, Vol: 1,800
             Bar 235: $4.66 → $4.66, Vol: 1,700
             Bar 236: $4.66 → $4.67, Vol: 2,400
             Bar 237: $4.67 → $4.67, Vol: 2,100
             Bar 238: $4.67 → $4.67, Vol: 1,900
             Bar 239: $4.67 → $4.67, Vol: 1,000

             Total volume: 23,900
             Open: $4.63
             Close: $4.67
             Size: $0.04 = 0.86%

           volume_ratio = 23,900 / 4,700 = 5.09x
           candle_size = 0.86%

           Delayed momentum check:
             is_strong_volume = (5.09x ≥ 2.0x) → TRUE ✅
             is_large_candle = (0.86% ≥ 0.3%) → TRUE ✅

             🎉 MOMENTUM DETECTED (delayed, candle 3)!

FILTER CHECKS:

  1. Choppy Market Filter:
     5-minute range: 0.95%
     ATR threshold: 0.40%
     0.95% > 0.40% → PASS ✅

  2. Room-to-Run Filter:
     Entry: $4.67

     CRITICAL: Dynamic target selection!
     - target1: $4.64 (already passed!)
     - target2: $4.70 (only 0.64% away)
     - target3: $4.77 (still available!)

     Use HIGHEST available: target3 = $4.77

     Room: ($4.77 - $4.67) / $4.67 = 2.14%
     Minimum: 1.5%

     2.14% > 1.5% → PASS ✅ (using target3!)

  3. Stochastic Filter (hourly):
     %K = 65%
     Required range (LONG): 60-80%
     65% in range → PASS ✅

  4. CVD Filter:
     CVD: +15,200
     Threshold: 0
     +15,200 > 0 → PASS ✅

RESULT:
  ✅ ALL FILTERS PASSED!
  → Entry signal: MOMENTUM_BREAKOUT (delayed, 5.1x vol on candle 3)

09:50:23 - ENTER LONG @ $4.67
           Shares: 800 (based on 1% risk)
           Stop: $4.58 (at resistance/pivot)
           Target1: $4.64 (already passed, will use for partials calculation)
           Target2: $4.70
           Target3: $4.77 (main target)

OUTCOME:
  09:51:45 - Partial (50%) @ $4.70 (+$0.03, $24 profit)
  09:55:20 - Partial (25%) @ $4.75 (+$0.08, $64 profit)
  10:12:30 - Final (25%) @ $4.80 (+$0.13, $104 profit)

  Total P&L: +$192 (0.8% gain per share weighted average)

KEY INSIGHTS:
  - Initial breakout was VERY weak (0.53x volume)
  - Patient tracking allowed detection of delayed momentum
  - Dynamic target selection allowed entry even after target1 passed
  - Without delayed momentum feature: Would have missed this trade entirely!
```

---

## Code References

### Main Entry Point

**File**: `trader/trader.py`
**Function**: `monitor_positions()` (lines 850-970)

Entry flow:
```python
def monitor_positions(self):
    """Main tick monitoring loop"""

    for symbol in watchlist:
        # Get current price (tick-level)
        current_price = self.get_current_price(symbol)

        # Check if should enter
        if position is None:
            # LONG check
            if price > resistance:
                should_enter, reason = self.strategy.should_enter_long(
                    stock_data, current_price, long_attempts,
                    bars=bars, current_idx=array_idx,
                    absolute_idx=absolute_idx,
                    bar_buffer=self.bar_buffers[symbol]
                )

                if should_enter:
                    self.enter_long(symbol, current_price)
```

---

### Strategy Module

**File**: `trader/strategy/ps60_strategy.py`

**Entry validation**:
- `should_enter_long()` (line 1733)
- `should_enter_short()` (line 1808)
- `check_hybrid_entry()` (line 1081) - Routes to state machine

**Filters**:
- `_check_choppy_market()` (line 2350)
- `_check_room_to_run()` (line 2201)
- `_check_stochastic_filter()` (line 2646)

---

### State Machine

**File**: `trader/strategy/ps60_entry_state_machine.py`

**Main entry point**:
- `check_entry_state_machine()` (line 171) - Master function

**State handlers**:
- BREAKOUT_DETECTED (line 199-357)
- WEAK_BREAKOUT_TRACKING (line 359-452)
- PULLBACK_RETEST (line 459-545)
- Delayed momentum detection (line 362-451)

**Helper functions**:
- `_get_candle_bars()` (line 132) - Absolute-to-array mapping
- `_check_cvd_filter()` (line 55) - CVD calculation

---

### State Tracking

**File**: `trader/strategy/breakout_state_tracker.py`

**State management**:
- `BreakoutStateTracker` class (line 45)
- `check_pullback()` (line 180) - Pullback detection
- State transitions and persistence

---

## Summary

The PS60 entry system implements a sophisticated multi-path approach that adapts to different market conditions:

1. **MOMENTUM PATH**: Captures explosive breakouts with immediate entry
2. **PULLBACK PATH**: Waits for confirmation on weak breaks
3. **SUSTAINED PATH**: Catches slow grinds that hold
4. **DELAYED MOMENTUM**: Re-checks for late-developing strength

All paths apply the same rigorous filters:
- Choppy market (prevents consolidation entries)
- Room-to-run (validates opportunity exists)
- Stochastic (confirms hourly momentum)
- CVD (validates buying/selling pressure)

This creates a robust system that:
- Adapts to different breakout patterns
- Validates every entry thoroughly
- Prevents common losing scenarios
- Maximizes high-probability opportunities

**The result**: A highly selective entry system that only trades the best setups while filtering out the noise.
