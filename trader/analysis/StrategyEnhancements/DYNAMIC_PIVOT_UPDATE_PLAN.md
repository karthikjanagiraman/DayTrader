# Dynamic Pivot Update Plan - Simplified Approach

**Created**: October 28, 2025
**Status**: 🟡 UNDER REVIEW
**Priority**: HIGH
**Complexity**: LOW (much simpler than adaptive volume filter)
**Expected Impact**: +20-40% P&L improvement

---

## 📝 Quick Summary

### Ultra-Simple 3-Step Logic

1. **Session Start Check**: If price already above pivot (gap) → immediately use today's high as pivot
2. **Target Progression**: When price hits Target1 → Target1 becomes new pivot → check room to Target2
3. **Failure Detection**: When pivot breaks but price falls back OR trade stops out → update pivot to today's high

That's it! One check at start, then continuous monitoring.

### Why This Is Ultra-Simple

- ✅ **Session start gap check** - handles overnight gaps immediately
- ✅ **No complex state tracking** - just watch for pivot breaks + failures
- ✅ **Three simple triggers**:
  1. Session start: Price already > pivot? → Use today's high
  2. Breakout failure: Price broke pivot but fell back? → Use today's high
  3. Stop out: Trade stopped? → Use today's high (if higher)
- ✅ **One parameter** - min room to next target (1.5%)

### The Logic in Plain English

**LONG (Session Start)**:
- At 9:30 AM: If current price > scanner pivot → update pivot to today's high immediately
- Reason: Stock gapped up overnight, scanner pivot is stale

**LONG (During Trading)**:
- When pivot breaks: Track that breakout happened
- If price falls back below pivot: Update pivot to today's high
- If trade stops out: Update pivot to today's high (if today's high > current pivot)
- Always check: Is there 1.5% room to next target?

**SHORT (Mirror Logic)**:
- Session start: Price < pivot → update to today's low
- Breakout failure: Price broke but rallied back → update to today's low
- Stop out: Update to today's low (if lower)

---

## Problem Statement

### Current Issues

1. **Stale Pivots**: Scanner provides resistance/support from yesterday's data, but intraday price may have already moved past these levels
2. **Target Confusion**: SMCI entered at $53.30 when Target1 ($52.59) was already breached
3. **Repeated False Breakouts**: Same pivot level triggers multiple failed entries (whipsaws)
4. **No Progressive Validation**: System doesn't recognize when price successfully reaches targets

### Real Example: SMCI October 28, 2025

```
Scanner Data:
  Resistance (pivot): $51.63
  Target1: $52.59
  Target2: $53.54
  Target3: $54.72

SMCI Entries:
  Trade #1: Entry $53.30 (Target1 already passed!) → STOP -$33.00
  Trade #2: Entry $53.21 (Target1 already passed!) → STOP -$7.14
  Trade #3: Entry $53.26 (Target1 already passed!) → 15MIN -$18.88
  Trade #4: Entry $53.26 (Target1 already passed!) → PARTIAL +$38.33

Issue: All 4 entries used $51.63 as pivot when price was already at $53+
```

---

## Proposed Solution: Dynamic Pivot Updates

### Core Concept

**Simple Rule**: The pivot (entry validation level) moves UP as targets are achieved, and updates after false breakouts to prevent re-entry at failed levels.

---

## Implementation Logic

### Rule 1: Target-Based Pivot Progression (LONG)

```python
# Initialize with scanner data
current_pivot = resistance  # $51.63 (scanner)
next_target = target1       # $52.59

# As price progresses:

if current_price >= target1:
    # Price reached Target1 → Promote Target1 to new pivot
    current_pivot = target1    # $52.59 becomes new validation level
    next_target = target2      # $53.54 is next goal

    print(f"✅ PIVOT UPDATED: {target1:.2f} (Target1 achieved)")

if current_price >= target2:
    # Price reached Target2 → Promote Target2 to new pivot
    current_pivot = target2    # $53.54 becomes new validation level
    next_target = target3      # $54.72 is next goal

    print(f"✅ PIVOT UPDATED: {target2:.2f} (Target2 achieved)")

# Now check room-to-run to NEXT target
room_to_run = (next_target - current_price) / current_price * 100

if room_to_run >= 1.5:
    print(f"✅ Entry valid: {room_to_run:.2f}% room to {next_target:.2f}")
else:
    print(f"❌ Block entry: Only {room_to_run:.2f}% to next target")
```

**Example Flow**:
```
09:30 AM - Price $50.50
  Current Pivot: $51.63 (scanner resistance)
  Next Target: $52.59 (Target1)
  Status: Below pivot, wait for breakout

10:00 AM - Price breaks $51.63
  ✅ Breakout detected
  Room to Target1: ($52.59 - $51.63) / $51.63 = 1.86% ✅ PASS
  🟢 ENTRY ALLOWED

10:30 AM - Price reaches $52.70 (Target1 passed)
  ✅ PIVOT UPDATE: $52.59 → New pivot
  Next Target: $53.54 (Target2)

11:00 AM - Price at $53.00, another entry signal
  Current Pivot: $52.59 (updated)
  Room to Target2: ($53.54 - $53.00) / $53.00 = 1.02% ❌ BLOCK
  Reason: Only 1.02% to Target2 (need 1.5% minimum)

11:30 AM - Price reaches $53.60 (Target2 passed)
  ✅ PIVOT UPDATE: $53.54 → New pivot
  Next Target: $54.72 (Target3)
```

---

### Rule 2: Pivot Protection (LONG) - CORRECTED LOGIC

**Three Triggers for Pivot Updates**:

```python
def initialize_session(self, current_price, intraday_bars):
    """
    Session start check (9:30 AM or when monitoring begins)
    Handle gap scenarios
    """
    # Check if we gapped above scanner pivot
    if current_price > self.current_long_pivot:
        todays_high = max([bar.high for bar in intraday_bars])

        if todays_high > self.current_long_pivot:
            old_pivot = self.current_long_pivot
            self.current_long_pivot = todays_high

            return f"SESSION START: Gapped above pivot, using today's high ${todays_high:.2f} (was ${old_pivot:.2f})"

    return None

def update_pivot_protection(self, current_price, intraday_bars, position=None):
    """
    During-session pivot protection
    Updates on breakout failures or stop outs
    """

    # Trigger 1: Breakout + Failure Detection
    # Track if pivot was broken
    if current_price > self.current_long_pivot:
        self.breakout_detected = True

    # If breakout happened but price fell back below pivot
    if self.breakout_detected and current_price < self.current_long_pivot:
        todays_high = max([bar.high for bar in intraday_bars])

        if todays_high > self.current_long_pivot:
            old_pivot = self.current_long_pivot
            self.current_long_pivot = todays_high
            self.breakout_detected = False  # Reset for next breakout

            return f"FAILED BREAKOUT: Pivot ${old_pivot:.2f} → ${todays_high:.2f} (today's high)"

    # Trigger 2: Stop Out Detection
    if position and position.get('stop_hit'):
        todays_high = max([bar.high for bar in intraday_bars])

        # Only update if today's high is actually higher than current pivot
        if todays_high > self.current_long_pivot:
            old_pivot = self.current_long_pivot
            self.current_long_pivot = todays_high

            return f"STOP HIT: Pivot ${old_pivot:.2f} → ${todays_high:.2f} (today's high)"

    return None

def can_enter_long(self, current_price):
    """Entry validation - ultra simple"""

    # Must be above pivot
    if current_price <= self.current_long_pivot:
        return False, f"Price ${current_price:.2f} below pivot ${self.current_long_pivot:.2f}"

    # Check room to next target
    room_pct = (self.next_long_target - current_price) / current_price * 100

    if room_pct < 1.5:
        return False, f"Only {room_pct:.2f}% room to next target (need 1.5%)"

    return True, f"Valid: {room_pct:.2f}% room to ${self.next_long_target:.2f}"
```

**Example Flows**:

**Scenario 1: Gap Up at Open**
```
Scanner (from yesterday):
  Pivot: $51.63

09:30 AM - Market opens, SMCI at $52.10
  Check: $52.10 > $51.63 (already above pivot!)
  Today's high: $52.10 (current is the high)

  🔄 SESSION START: Pivot $51.63 → $52.10 (gapped above)

10:00 AM - Price at $53.00
  Current pivot: $52.10
  Room to Target1 ($52.59): Only 0.45%
  ❌ BLOCK: Insufficient room

  → This would have blocked all 4 SMCI trades!
```

**Scenario 2: Normal Breakout + Failure**
```
09:30 AM - Price $51.50 (below pivot $51.63)
  Keep scanner pivot: $51.63

10:15 AM - Price breaks to $51.70
  breakout_detected = True
  ✅ Can enter (if room to target)

10:15:30 - Price drops to $51.50 (fell back below pivot!)
  🔄 FAILED BREAKOUT: Pivot $51.63 → $51.90 (today's high)
  breakout_detected = False

10:16 AM - Price at $51.70
  ❌ Block: Price $51.70 below new pivot $51.90
```

**Scenario 3: Stop Out**
```
11:00 AM - Entered LONG @ $52.00 (pivot $51.63)
  Today's high at entry: $52.20

11:02 AM - Stopped out @ $51.63
  Check: Today's high $52.20 > current pivot $51.63?
  ✅ Yes

  🔄 STOP HIT: Pivot $51.63 → $52.20 (today's high)

11:15 AM - Price at $52.00
  ❌ Block: Price $52.00 below new pivot $52.20
```

**Key Corrections**:
- ✅ **Session start check** - handles gaps immediately
- ✅ **Breakout tracking** - need ONE flag to know when pivot was broken
- ✅ **Conditional updates** - only update if today's high > current pivot
- ✅ **Three triggers** - gap, failure, stop out

---

### Rule 3: SHORT Trades (Mirror Logic) - ULTRA-SIMPLE

**Target Progression (SHORT)**:
```python
# Initialize
current_pivot = support     # Scanner support level
next_target = downside1     # First downside target

if current_price <= downside1:
    # Price reached Downside1 → Promote to new pivot
    current_pivot = downside1
    next_target = downside2

# Check room to run DOWN
room_to_run = (current_price - next_target) / current_price * 100
```

**Pivot Protection (SHORT) - ULTRA-SIMPLE**:
```python
def update_pivot_protection_short(self, current_price, intraday_bars, position=None):
    """Ultra-simple pivot protection for shorts"""

    # Check 1: Price rallied above pivot?
    if current_price > self.current_short_pivot:
        todays_low = min([bar.low for bar in intraday_bars])

        if todays_low < self.current_short_pivot:
            old_pivot = self.current_short_pivot
            self.current_short_pivot = todays_low

            return f"PIVOT UPDATED: ${old_pivot:.2f} → ${todays_low:.2f} (price above pivot)"

    # Check 2: Trade stopped out?
    if position and position.get('stop_hit'):
        todays_low = min([bar.low for bar in intraday_bars])

        if todays_low < self.current_short_pivot:
            old_pivot = self.current_short_pivot
            self.current_short_pivot = todays_low

            return f"PIVOT UPDATED: ${old_pivot:.2f} → ${todays_low:.2f} (stop hit)"

    return None

def can_enter_short(self, current_price):
    """Entry validation for shorts - ultra simple"""

    # Must be below pivot
    if current_price >= self.current_short_pivot:
        return False, f"Price ${current_price:.2f} above pivot ${self.current_short_pivot:.2f}"

    # Check room to next downside target
    room_pct = (current_price - self.next_short_target) / current_price * 100

    if room_pct < 1.5:
        return False, f"Only {room_pct:.2f}% room to next target (need 1.5%)"

    return True, f"Valid: {room_pct:.2f}% room to ${self.next_short_target:.2f}"
```

**Same ultra-simple rules**:
1. Price > pivot? → Update pivot to today's low
2. Stop hit? → Update pivot to today's low
3. Price < pivot + 1.5% room down? → Can enter

---

## Complete Example: SMCI with Dynamic Pivots

### What Actually Happened (Static Pivots)

```
Scanner: Resistance $51.63, Target1 $52.59, Target2 $53.54

11:54 AM - Trade #1 Entry $53.30
  Pivot: $51.63 (scanner, STALE)
  Room to run: ($53.54 - $53.30) / $53.30 = 0.45% ❌ Should have blocked!
  Result: STOP -$33.00

11:58 AM - Trade #2 Entry $53.21
  Pivot: $51.63 (still using stale pivot)
  Result: STOP -$7.14

1:52 PM - Trade #3 Entry $53.26
  Pivot: $51.63 (still stale)
  Result: 15MIN -$18.88

2:11 PM - Trade #4 Entry $53.26
  Pivot: $51.63 (still stale)
  Result: PARTIAL +$38.33

Net: -$20.69
```

### What Would Have Happened (Dynamic Pivots)

```
Scanner: Resistance $51.63, Target1 $52.59, Target2 $53.54

11:00 AM - Price reaches $52.70
  🔄 PIVOT UPDATE: $52.59 (Target1 achieved)
  Next Target: $53.54 (Target2)

11:54 AM - Trade #1 Attempt $53.30
  Pivot: $52.59 (updated, not $51.63)
  Room to Target2: ($53.54 - $53.30) / $53.30 = 0.45%
  ❌ BLOCKED: Only 0.45% to Target2 (need 1.5%)
  Saved: -$33.00 ✅

11:58 AM - Trade #2 Attempt $53.21
  Pivot: $52.59
  Room to Target2: ($53.54 - $53.21) / $53.21 = 0.62%
  ❌ BLOCKED: Only 0.62% to Target2
  Saved: -$7.14 ✅

12:30 PM - Price reaches $53.60
  🔄 PIVOT UPDATE: $53.54 (Target2 achieved)
  Next Target: $54.72 (Target3)

1:52 PM - Trade #3 Attempt $53.26
  Pivot: $53.54 (updated)
  Price: $53.26 < $53.54
  ❌ BLOCKED: Price below pivot (pullback from Target2)
  Saved: -$18.88 ✅

2:11 PM - Trade #4 Attempt $53.26
  Pivot: $53.54
  Price: $53.26 < $53.54
  ❌ BLOCKED: Price still below pivot
  Missed: +$38.33 ❌

Net Impact:
  Saved: -$59.02 (3 losers blocked)
  Missed: +$38.33 (1 winner blocked)
  Improvement: +$20.69 (from -$20.69 to $0)
```

---

## Implementation Details

### State Tracking Required - MINIMAL

```python
class SymbolState:
    def __init__(self, scanner_data):
        self.symbol = scanner_data['symbol']

        # Long setup (from scanner)
        self.resistance = scanner_data['resistance']
        self.target1 = scanner_data['target1']
        self.target2 = scanner_data['target2']
        self.target3 = scanner_data['target3']

        # Short setup (from scanner)
        self.support = scanner_data['support']
        self.downside1 = scanner_data['downside1']
        self.downside2 = scanner_data['downside2']

        # Dynamic pivots (start with scanner values, update as needed)
        self.current_long_pivot = self.resistance
        self.next_long_target = self.target1

        self.current_short_pivot = self.support
        self.next_short_target = self.downside1

        # Breakout tracking (ONE flag per direction)
        self.long_breakout_detected = False
        self.short_breakout_detected = False

        # No timing variables needed
        # No cooldown trackers needed
        # No entry tracking needed

    def update_long_pivot(self, current_price, intraday_bars=None):
        """Update pivot as targets are achieved"""

        # Target1 achieved?
        if current_price >= self.target1 and self.current_long_pivot == self.resistance:
            self.current_long_pivot = self.target1
            self.next_long_target = self.target2
            return f"Pivot updated to Target1 (${self.target1:.2f})"

        # Target2 achieved?
        if current_price >= self.target2 and self.current_long_pivot == self.target1:
            self.current_long_pivot = self.target2
            self.next_long_target = self.target3
            return f"Pivot updated to Target2 (${self.target2:.2f})"

        return None

    def update_pivot_protection(self, current_price, intraday_bars, position=None):
        """
        ULTRA-SIMPLE pivot protection
        Updates pivot whenever price shows weakness
        """

        # Check 1: Price fell below pivot?
        if current_price < self.current_long_pivot:
            todays_high = max([bar.high for bar in intraday_bars])

            if todays_high > self.current_long_pivot:
                old_pivot = self.current_long_pivot
                self.current_long_pivot = todays_high
                return f"PIVOT UPDATED: ${old_pivot:.2f} → ${todays_high:.2f} (price below pivot)"

        # Check 2: Trade stopped out?
        if position and position.get('stop_hit'):
            todays_high = max([bar.high for bar in intraday_bars])

            if todays_high > self.current_long_pivot:
                old_pivot = self.current_long_pivot
                self.current_long_pivot = todays_high
                return f"PIVOT UPDATED: ${old_pivot:.2f} → ${todays_high:.2f} (stop hit)"

        return None

    def can_enter_long(self, current_price):
        """Ultra-simple entry validation"""

        # Must be above pivot
        if current_price <= self.current_long_pivot:
            return False, f"Price ${current_price:.2f} below pivot ${self.current_long_pivot:.2f}"

        # Check room to next target
        room_pct = (self.next_long_target - current_price) / current_price * 100

        if room_pct < 1.5:
            return False, f"Only {room_pct:.2f}% room to next target (need 1.5%)"

        return True, f"Valid: {room_pct:.2f}% room to ${self.next_long_target:.2f}"
```

### Integration with Entry Logic

```python
# In trader.py or strategy module

def start_monitoring(self):
    """Initialize monitoring session - called at 9:30 AM or when trader starts"""

    for symbol in self.watchlist:
        current_price = self.get_current_price(symbol)
        state = self.symbol_states[symbol]

        # Session start check - handle gaps
        gap_msg = state.initialize_session(current_price, self.intraday_bars[symbol])
        if gap_msg:
            logger.warning(f"🔄 {symbol}: {gap_msg}")

def monitor_symbols(self):
    """Main monitoring loop - runs every tick"""

    for symbol in self.watchlist:
        current_price = self.get_current_price(symbol)
        state = self.symbol_states[symbol]
        position = self.positions.get(symbol)  # Current position if any

        # Step 1: Check for target progression
        target_msg = state.update_long_pivot(current_price, self.intraday_bars[symbol])
        if target_msg:
            logger.info(f"🔄 {symbol}: {target_msg}")

        # Step 2: Update pivot protection (breakout failures or stop outs)
        protection_msg = state.update_pivot_protection(
            current_price,
            self.intraday_bars[symbol],
            position  # Pass current position to check for stops
        )
        if protection_msg:
            logger.warning(f"🔄 {symbol}: {protection_msg}")

        # Step 3: Check if entry is valid (if entry signal present)
        if self.entry_signal_detected(symbol, current_price):
            can_enter, reason = state.can_enter_long(current_price)

            if not can_enter:
                logger.debug(f"❌ {symbol}: Entry blocked - {reason}")
                continue

            logger.info(f"✅ {symbol}: Entry valid - {reason}")
            self.execute_entry(symbol, current_price)
```

**Key Features**:
- ✅ **Session initialization** - handles gaps at market open
- ✅ **Breakout tracking** - one flag to detect when pivot was broken
- ✅ **Three triggers** - gap, breakout failure, stop out
- ✅ **Conditional updates** - only update if today's high > current pivot
- **Total complexity**: ~70 lines of logic

---

## Configuration - ULTRA-MINIMAL

```yaml
# trader/config/trader_config.yaml

filters:
  dynamic_pivot_updates:
    enabled: true                    # Master switch

    # Only ONE parameter needed!
    min_room_to_next_target: 1.5     # 1.5% minimum to next target
```

**That's it!** No other parameters needed.

**Removed parameters** (no longer needed):
- ❌ `failed_breakout_cooldown_min` - No cooldowns
- ❌ `whipsaw_threshold_seconds` - No timing checks
- ❌ `use_intraday_high_low` - Always uses intraday high/low (hardcoded)

---

## Benefits of Ultra-Simple Approach

1. **✅ Maximum Simplicity**: Absolute minimum complexity - just 2 rules
2. **✅ Progressive Validation**: Pivot advances as price proves strength
3. **✅ Automatic Protection**: Updates pivot whenever weakness detected
4. **✅ No Arbitrary Thresholds**: Uses actual targets, not % from pivot
5. **✅ Zero State Tracking**: No flags, no timers, no counters
6. **✅ Works Universally**: Catches failures even on blocked entries
7. **✅ Easy to Debug**: Simple logic = simple troubleshooting
8. **✅ Fast to Implement**: ~50 lines of code total

---

## Complexity Comparison

### Original Complex Version (What We Avoided)
```
State Variables Needed:
  - breakout_detected (bool)
  - breakout_time (datetime)
  - entry_executed (bool)
  - entry_time (datetime)
  - stop_hit_time (datetime)
  - failed_breakout_time (datetime)
  - cooldown_minutes (int)

Logic Checks Required:
  - Did breakout happen?
  - Are we tracking it?
  - Did price fall back?
  - Did we enter a trade?
  - Did we get stopped out?
  - Was stop within 60 seconds?
  - Is cooldown still active?
  - How many minutes since failure?

Configuration Parameters:
  - whipsaw_threshold_seconds
  - failed_breakout_cooldown_min
  - use_intraday_high_low

Total Complexity: ~150 lines of code
```

### ✅ Simplified Version (What We're Using)
```
State Variables Needed:
  - current_long_pivot (float)
  - next_long_target (float)
  - long_breakout_detected (bool)

Logic Checks Required:
  - Session start: Price already > pivot?
  - During session: Pivot broken?
  - During session: Price fell back below pivot?
  - Stop hit: Update to today's high?
  - Entry: Room to next target ≥1.5%?

Configuration Parameters:
  - min_room_to_next_target

Total Complexity: ~70 lines of code
```

**Reduction**: 53% less code, 57% fewer state variables, 67% fewer parameters

---

## Expected Impact

### SMCI Example (Oct 28)

| Metric | Before (Static) | After (Dynamic) | Improvement |
|--------|-----------------|-----------------|-------------|
| **Trades** | 4 trades | 0 trades (all blocked) | -4 overtrading |
| **Winners** | 1 winner (+$38.33) | 0 winners | -$38.33 missed |
| **Losers** | 3 losers (-$59.02) | 0 losers | +$59.02 saved |
| **Net P&L** | -$20.69 | $0 | **+$20.69** |

### Full Session (Oct 28 - 12 trades)

Estimated impact on other whipsaw trades:
- NVDA whipsaw (7 sec): Would update pivot to today's high, prevent retry
- AMD whipsaw #1 (9 sec): Would update pivot, block 2nd attempt
- PATH whipsaws (2 trades): Would update to today's low after first

**Expected Session Impact**: +$50-80 improvement (prevent 3-4 additional whipsaws)

---

## Implementation Timeline

### Phase 1: Core Logic (3-5 days)
- Implement `SymbolState` class with pivot tracking
- Add target progression logic (Target1 → Target2 → Target3)
- Integrate with entry validation

### Phase 2: False Breakout Handling (2-3 days)
- Add whipsaw detection (<60 sec stops)
- Implement intraday high/low pivot updates
- Add cooldown mechanism

### Phase 3: Testing (1 week)
- Backtest on Oct 1-28 data
- Validate against SMCI scenario
- Compare P&L improvement

### Phase 4: Live Paper Trading (1 week)
- Deploy to paper account
- Monitor pivot updates in real-time
- Validate false breakout detection

---

## Comparison to Adaptive Volume Filter

| Approach | Complexity | Pros | Cons |
|----------|-----------|------|------|
| **Dynamic Pivots** | LOW | Simple, uses targets, auto-adapts | May miss some valid late entries |
| **Adaptive Volume** | MEDIUM | Granular control, volume-based | Harder to tune, more parameters |

**Recommendation**: Start with Dynamic Pivots (simpler), can add Adaptive Volume later if needed.

---

## Next Steps

1. **Review and approve** this plan
2. **Implement** `SymbolState` class
3. **Test** on SMCI scenario (Oct 28)
4. **Backtest** on full October data
5. **Deploy** to paper trading

---

**Status**: 🟡 UNDER REVIEW (awaiting approval)
**Expected Benefit**: +$20-80 per session
**Risk**: Low (can disable easily, backward compatible)
