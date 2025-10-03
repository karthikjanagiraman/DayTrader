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
