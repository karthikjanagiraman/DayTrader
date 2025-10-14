# Using the Shared PS60 Strategy Module

## Overview

The `strategy/` module contains all PS60 trading logic in one place:
- **ps60_strategy.py** - Entry/exit rules, risk management, filters
- **position_manager.py** - Position tracking, P&L calculations

Both `trader.py` (live) and `backtester.py` import these modules.

---

## Usage Example

### 1. Initialize Strategy

```python
import yaml
from strategy import PS60Strategy, PositionManager

# Load config
with open('config/trader_config.yaml') as f:
    config = yaml.safe_load(f)

# Create strategy and position manager
strategy = PS60Strategy(config)
pm = PositionManager()
```

### 2. Check Entry Signals

```python
# Scanner data
stock_data = {
    'symbol': 'AAPL',
    'resistance': 150.50,
    'support': 148.00,
    'score': 75,
    'risk_reward': 2.5
}

current_price = 150.75  # Broken above resistance
attempt_count = 0

# Check if should enter long
should_enter, reason = strategy.should_enter_long(
    stock_data,
    current_price,
    attempt_count
)

if should_enter:
    # Calculate position size
    shares = strategy.calculate_position_size(
        account_size=100000,
        entry_price=current_price,
        stop_price=stock_data['resistance']  # Stop at pivot
    )

    # Create position
    position = pm.create_position(
        symbol='AAPL',
        side='LONG',
        entry_price=current_price,
        shares=shares,
        pivot=stock_data['resistance'],
        target1=stock_data.get('target1', 155.00)
    )
```

### 3. Manage Position (in trading loop)

```python
from datetime import datetime
import pytz

eastern = pytz.timezone('US/Eastern')
current_time = datetime.now(pytz.UTC).astimezone(eastern)

# Get position
position = pm.get_position('AAPL')
current_price = 151.50

# Check 5-minute rule
should_exit, reason = strategy.check_five_minute_rule(
    position,
    current_price,
    current_time
)

if should_exit:
    # Exit position
    trade = pm.close_position('AAPL', current_price, reason)
    print(f"Exited: {trade}")
else:
    # Check for partial profit
    should_partial, pct, reason = strategy.should_take_partial(
        position,
        current_price
    )

    if should_partial:
        # Take partial
        partial = pm.take_partial('AAPL', current_price, pct, reason)
        print(f"Partial taken: {partial}")

        # Update stop to breakeven
        if strategy.should_move_stop_to_breakeven(position):
            position['stop'] = position['entry_price']
```

### 4. End of Day Close

```python
# Check if near EOD
if strategy.is_near_eod(current_time):
    # Get current prices for all positions
    current_prices = {
        'AAPL': 152.00,
        'TSLA': 245.50
    }

    # Close all positions
    trades = pm.close_all_positions(current_prices, reason='EOD')

    # Get daily summary
    summary = pm.get_daily_summary()
    print(f"Daily P&L: ${summary['daily_pnl']:.2f}")
    print(f"Win Rate: {summary['win_rate']:.1f}%")
```

---

## Key Methods Reference

### PS60Strategy

**Entry Decisions:**
- `should_enter_long(stock_data, price, attempts)` → (bool, reason)
- `should_enter_short(stock_data, price, attempts)` → (bool, reason)
- `is_within_entry_window(time)` → bool

**Exit Decisions:**
- `check_five_minute_rule(position, price, time)` → (bool, reason)
- `should_take_partial(position, price)` → (bool, pct, reason)
- `should_move_stop_to_breakeven(position)` → bool
- `is_near_eod(time)` → bool

**Risk Management:**
- `calculate_position_size(account, entry, stop)` → shares
- `calculate_stop_price(position, price)` → stop_price

**Filtering:**
- `filter_scanner_results(results)` → filtered_results

### PositionManager

**Position Lifecycle:**
- `create_position(symbol, side, entry, shares, pivot, **kwargs)` → position
- `get_position(symbol)` → position
- `has_position(symbol)` → bool
- `get_attempt_count(symbol, pivot)` → int

**Partials & Exits:**
- `take_partial(symbol, price, pct, reason)` → partial_record
- `close_position(symbol, price, reason)` → trade_record
- `close_all_positions(prices, reason)` → [trade_records]

**P&L:**
- `calculate_pnl(position, exit_price)` → pnl
- `get_unrealized_pnl(symbol, price)` → pnl
- `get_daily_summary()` → summary_dict

---

## Benefits of This Architecture

1. **Single Source of Truth**
   - Trading rules defined once in `ps60_strategy.py`
   - Used by both live trader and backtester
   - Fix bugs once, applies everywhere

2. **Easy Testing**
   - Test strategy logic independently
   - Mock positions without IBKR connection
   - Validate rules against PS60 requirements

3. **Maintainability**
   - Clear separation of concerns
   - Strategy logic separate from execution
   - Easy to add new rules or modify existing ones

4. **Consistency**
   - Backtester uses EXACT same logic as live trader
   - No divergence between simulation and reality

---

## File Structure

```
trader/
├── strategy/
│   ├── __init__.py              # Module exports
│   ├── ps60_strategy.py         # Core strategy logic
│   ├── position_manager.py      # Position tracking
│   └── USAGE_EXAMPLE.md         # This file
│
├── trader.py                    # Live trader (imports strategy/)
├── backtest/
│   └── backtester.py            # Backtester (imports strategy/)
│
└── config/
    └── trader_config.yaml       # Configuration
```

---

## Migration Plan

### Current (Before):
```python
# trader.py
class PS60Trader:
    def check_five_minute_rule(self, position):
        # Logic here
        ...

    def take_partial(self, position):
        # Logic here
        ...
```

```python
# backtester.py
class PS60Backtester:
    def check_five_minute_rule(self, position):
        # DUPLICATE logic here (must keep in sync!)
        ...
```

**Problem:** Changes must be made in TWO places!

### New (After):
```python
# trader.py
from strategy import PS60Strategy, PositionManager

class PS60Trader:
    def __init__(self, config):
        self.strategy = PS60Strategy(config)
        self.pm = PositionManager()

    def manage_positions(self):
        should_exit, reason = self.strategy.check_five_minute_rule(...)
        # Use strategy methods
```

```python
# backtester.py
from strategy import PS60Strategy, PositionManager

class PS60Backtester:
    def __init__(self, config):
        self.strategy = PS60Strategy(config)
        self.pm = PositionManager()

    def simulate_trading(self):
        should_exit, reason = self.strategy.check_five_minute_rule(...)
        # Uses SAME strategy methods!
```

**Solution:** Changes made in ONE place (`strategy/`), automatically used by both!

---

*Last updated: October 2, 2025*

I'll explain the decision tree for handling weak breakouts and the pullback monitoring system.

  Decision Tree for Breakout Entry Logic

  Price breaks pivot (resistance/support)
      │
      ├─→ Check 1: Is this MOMENTUM breakout?
      │   │
      │   ├─→ YES (Volume ≥1.3x AND Candle ≥0.8% OR ≥2x ATR)
      │   │   │
      │   │   ├─→ Check: 1-minute candle closed?
      │   │   │   │
      │   │   │   ├─→ YES → ENTER IMMEDIATELY (momentum entry)
      │   │   │   └─→ NO → Wait for candle close
      │   │   │
      │   │   └─→ Skip pullback monitoring (strong breakout)
      │   │
      │   └─→ NO (Weak breakout - volume <1.3x OR small candle)
      │       │
      │       └─→ PULLBACK/RETEST PATH
      │           │
      │           ├─→ Phase 1: Wait for 1-min candle close
      │           │   └─→ Ensures breakout is real, not spike
      │           │
      │           ├─→ Phase 2: Wait for pullback to pivot
      │           │   │
      │           │   ├─→ Monitor next 24 bars (2 minutes max)
      │           │   ├─→ Looking for: Price comes within 0.3% of pivot
      │           │   │
      │           │   ├─→ Pullback detected?
      │           │   │   │
      │           │   │   ├─→ YES → Go to Phase 3
      │           │   │   └─→ NO (2 min timeout) → Skip trade
      │           │   │
      │           │   └─→ LONG: bar.low ≤ resistance × 1.003
      │           │       SHORT: bar.high ≥ support × 0.997
      │           │
      │           └─→ Phase 3: Wait for re-break with volume
      │               │
      │               ├─→ Check: Price re-breaking pivot?
      │               │   │
      │               │   ├─→ LONG: price > resistance
      │               │   └─→ SHORT: price < support
      │               │
      │               ├─→ Check: Volume surge during re-break?
      │               │   └─→ 1.2x volume in recent bars
      │               │
      │               ├─→ Both conditions met?
      │               │   │
      │               │   ├─→ YES → ENTER (pullback/retest entry)
      │               │   └─→ NO → Keep monitoring
      │               │
      │               └─→ If stays above pivot too long
      │                   └─→ Check SUSTAINED BREAK logic

  Alternative Path: Sustained Break (Slow Grind)

  If pullback never comes BUT price sustains above/below pivot:
      │
      ├─→ Check: Held above/below for 2 minutes?
      │   └─→ With max 0.3% pullback allowed
      │
      ├─→ Check: Had volume during the grind?
      │   └─→ Recent bars show 1.2x+ volume
      │
      └─→ Both met?
          │
          ├─→ YES → ENTER (sustained break entry)
          └─→ NO → Keep waiting or skip

  Pullback Monitoring Implementation

  How It Works Without Persistence

  The system uses rolling bar buffers - it doesn't need to remember "I'm waiting for a pullback on TSLA." Instead, every 5 seconds it
  reconstructs the state from recent bars:

  # Every 5 seconds, for each stock in watchlist:

  1. Get last 60 bars (5 minutes of history)
     └─→ bars = stock_data.get('bar_buffer', [])

  2. Scan backwards through bars to find breakout moment
     └─→ When did price first break resistance?
     └─→ breakout_bar_idx = find_first_break(bars, pivot)

  3. Determine current phase from bar analysis
     │
     ├─→ Phase 1: Candle Close Check
     │   │
     │   ├─→ Breakout happened in current 1-min candle?
     │   │   └─→ breakout_bar < current_candle_end
     │   │       └─→ Status: "Waiting for 1-min candle close"
     │   │
     │   └─→ Candle has closed?
     │       └─→ current_idx >= candle_end
     │           └─→ Move to Phase 2
     │
     ├─→ Phase 2: Pullback Detection
     │   │
     │   ├─→ Scan bars AFTER candle close for pullback
     │   │   └─→ for bar in bars[candle_close_idx : current_idx]:
     │   │           if bar.low <= resistance × 1.003:  # LONG
     │   │               pullback_detected = True
     │   │
     │   ├─→ Pullback found?
     │   │   └─→ Move to Phase 3
     │   │
     │   └─→ No pullback yet?
     │       │
     │       ├─→ Still within 24-bar window (2 minutes)?
     │       │   └─→ Status: "Waiting for pullback to pivot"
     │       │
     │       └─→ Exceeded 2 minutes?
     │           └─→ Check sustained break logic instead
     │
     └─→ Phase 3: Re-break Confirmation
         │
         ├─→ Pullback was detected in past bars
         │
         ├─→ Current price re-breaking pivot?
         │   └─→ price > resistance (LONG)
         │
         └─→ Volume surge in recent bars?
             │
             ├─→ YES → ENTER NOW
             └─→ NO → Status: "Re-breaking but no volume surge"

  Key Insight: Stateless Monitoring

  The system doesn't track "state" per stock. Instead:

  Every 5-second tick, it looks at the bar buffer and asks:
  1. "Did this stock break resistance recently?" (scan last 60 bars)
  2. "If yes, what phase should we be in based on the pattern?"
  3. "Do current conditions meet entry criteria for that phase?"

  This is why there's no pullback_state[symbol] = 'WAITING_FOR_PULLBACK' variable. The state is implicit in the bar pattern itself.

  Concrete Example: AAPL Pullback Scenario

  Time: 10:15:23 AM
  AAPL resistance: $257.50

  Bar Buffer (last 12 bars, 1 minute):
  Bar 48 (10:14:18): 257.30 (below resistance)
  Bar 49 (10:14:23): 257.45 (below)
  Bar 50 (10:14:28): 257.65 ← BREAKS resistance, weak volume 0.9x
  Bar 51 (10:14:33): 257.70
  Bar 52 (10:14:38): 257.80
  ... (bars 53-59: price stays above)
  Bar 60 (10:15:23): 257.75 ← Current bar

  Decision Tree at 10:15:23:
  1. Scan: Found breakout at bar 50 (10:14:28)
  2. Volume check: 0.9x (WEAK) → Not momentum
  3. Candle check:
     - Breakout in 1-min candle starting 10:14:00
     - Candle ends at bar 60 (10:15:00)
     - Current bar 60 = candle closed ✓
  4. Pullback check:
     - Scan bars 60-60 (after candle close)
     - Need: bar.low ≤ $257.50 × 1.003 = $257.77
     - Bar 60 low: $257.70 ✓ PULLBACK DETECTED
  5. Re-break check:
     - Current price: $257.75 < $257.50 ✗
     - Status: "Pullback detected, waiting for re-break"

  Next tick (10:15:28):
  Bar 61: Price jumps to $257.85
  1. Breakout still at bar 50
  2. Pullback was detected (bar 60 had low of $257.70)
  3. Re-break: $257.85 > $257.50 ✓
  4. Volume: Check bars 58-61 for surge
     - If ≥1.2x → ENTER LONG
     - If <1.2x → Status: "Re-breaking but no volume"

  Why This Works

  Advantages:
  1. ✅ No state management - No need to track "AAPL is in pullback phase"
  2. ✅ Crash recovery - If trader restarts, bar buffers rebuild from market data
  3. ✅ Handles 17 stocks simultaneously - Same logic for all
  4. ✅ Self-correcting - If pattern changes, decision changes automatically

  The Bar Buffer IS The State:
  - Buffer shows breakout → Check if momentum
  - Buffer shows weak breakout + no pullback yet → Wait for pullback
  - Buffer shows weak breakout + pullback occurred → Check for re-break
  - Buffer shows sustained hold → Check sustained break criteria

  Code Location

  This logic lives in /Users/karthik/projects/DayTrader/trader/strategy/ps60_strategy.py:

  Lines 548-697: check_pullback_retest() method
  - Scans bar buffer for breakout moment
  - Determines phase from bar pattern
  - Returns entry decision with detailed reason

  Lines 699-760: check_sustained_break() method
  - Alternative path for slow grind breakouts
  - Checks if price held above/below for 2 minutes
  - Verifies volume during sustained period

  The trader calls this every 5 seconds for each stock via should_enter_long() or should_enter_short().

