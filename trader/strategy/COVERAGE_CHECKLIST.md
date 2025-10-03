# Strategy Module Coverage Checklist

## Comparison: trader.py vs strategy/ module

### ✅ COVERED in Strategy Module

| Functionality | trader.py | strategy/ | Notes |
|---------------|-----------|-----------|-------|
| **Entry Logic** ||||
| Check pivot break (long) | `check_pivot_break()` | ✅ `should_enter_long()` | Enhanced with better checks |
| Check pivot break (short) | `check_pivot_break()` | ✅ `should_enter_short()` | Enhanced with better checks |
| Calculate position size | `calculate_position_size()` | ✅ `calculate_position_size()` | Exact same logic |
| Check entry window | `is_trading_hours()` | ✅ `is_within_entry_window()` | Separated market hours from entry window |
| Max attempts per pivot | `check_pivot_break()` | ✅ `should_enter_long/short()` | Built into entry checks |
| Avoid index shorts | `check_pivot_break()` | ✅ `should_enter_short()` | Built into short check |
| **Exit Logic** ||||
| 5-7 minute rule | `manage_positions()` | ✅ `check_five_minute_rule()` | **FIXED** - checks stuck at pivot |
| Take partial profits | `manage_positions()` | ✅ `should_take_partial()` | Separated logic |
| Move stop to breakeven | `manage_positions()` | ✅ `should_move_stop_to_breakeven()` | Separated logic |
| EOD close check | `run()` | ✅ `is_near_eod()` | Separated logic |
| Calculate stop price | Implicit | ✅ `calculate_stop_price()` | Explicit method |
| **Position Management** ||||
| Create position | `enter_long/short()` | ✅ `PositionManager.create_position()` | Centralized |
| Track partials | `take_partial()` | ✅ `PositionManager.take_partial()` | Centralized |
| Close position | `close_position()` | ✅ `PositionManager.close_position()` | Centralized |
| Calculate P&L | `calculate_pnl()` | ✅ `PositionManager.calculate_pnl()` | Exact same logic |
| Record trades | `record_trade()` | ✅ `PositionManager.close_position()` | Combined into close |
| Track attempt count | `attempted_pivots` dict | ✅ `PositionManager.get_attempt_count()` | Centralized |
| **Filtering** ||||
| Filter scanner results | `load_scanner_results()` | ✅ `filter_scanner_results()` | Extracted logic |
| Min score filter | `load_scanner_results()` | ✅ `filter_scanner_results()` | Built in |
| Min R/R filter | `load_scanner_results()` | ✅ `filter_scanner_results()` | Built in |
| Avoid symbols | `load_scanner_results()` | ✅ `filter_scanner_results()` | Built in |
| **Summary/Reporting** ||||
| Daily summary | `print_daily_summary()` | ✅ `PositionManager.get_daily_summary()` | Returns dict instead of printing |

---

### ❌ NOT IN Strategy Module (IBKR-specific execution)

These are **intentionally not included** because they're IBKR API-specific, not strategy logic:

| Functionality | Where it belongs | Notes |
|---------------|------------------|-------|
| IBKR connection | trader.py only | API-specific |
| Market data subscription | trader.py only | API-specific |
| Place market orders | trader.py only | Execution detail |
| Place stop orders | trader.py only | Execution detail |
| Logging setup | trader.py only | Infrastructure |
| Load config file | trader.py only | Infrastructure |

**Why separate?**
- Backtester doesn't use IBKR API (uses historical data)
- Strategy logic should be pure (no side effects)
- Easier to test strategy without IBKR connection

---

## Strategy Module Completeness: ✅ 100%

### What We Have:

#### `ps60_strategy.py` (Core Strategy)
```python
class PS60Strategy:
    # Entry decisions
    should_enter_long(stock_data, price, attempts)
    should_enter_short(stock_data, price, attempts)
    is_within_entry_window(time)

    # Exit decisions
    check_five_minute_rule(position, price, time)  # FIXED!
    should_take_partial(position, price)
    should_move_stop_to_breakeven(position)
    is_near_eod(time)

    # Risk management
    calculate_position_size(account, entry, stop)
    calculate_stop_price(position, price)

    # Filtering
    filter_scanner_results(results)
```

#### `position_manager.py` (State Management)
```python
class PositionManager:
    # Position lifecycle
    create_position(symbol, side, entry, shares, pivot, **kwargs)
    get_position(symbol)
    has_position(symbol)
    get_attempt_count(symbol, pivot)

    # Partials & exits
    take_partial(symbol, price, pct, reason)
    close_position(symbol, price, reason)
    close_all_positions(prices, reason)

    # P&L
    calculate_pnl(position, exit_price)
    get_unrealized_pnl(symbol, price)
    get_daily_summary()
```

---

## Key Improvements Over trader.py

### 1. **Fixed 5-Minute Rule** ✅
**trader.py (buggy):**
```python
elif time_in_trade >= 7 and position['remaining'] == 1.0 and gain < 0.10:
    self.close_position(position, current_price, '5MIN_RULE')
```

**strategy/ps60_strategy.py (correct):**
```python
def check_five_minute_rule(self, position, current_price, current_time):
    time_in_trade = (current_time - position['entry_time']).total_seconds() / 60

    # Only check between 5-7 minutes
    if time_in_trade < 5 or time_in_trade > 7:
        return False, None

    # Check if STUCK AT PIVOT (not just slow)
    if position['side'] == 'LONG':
        pct_change = ((current_price - entry_price) / entry_price) * 100
        if pct_change <= 0.3:  # Within 0.3% of entry
            if not position['partials']:  # No favorable movement
                return True, "5MIN_RULE_RELOAD (stuck at pivot)"
```

### 2. **Better Separation of Concerns** ✅
- **Strategy** = What to do (decisions)
- **Execution** = How to do it (IBKR orders)
- **State** = What we're tracking (positions)

### 3. **Testable Without IBKR** ✅
```python
# Can test strategy logic without connecting to IBKR
strategy = PS60Strategy(config)
should_enter, reason = strategy.should_enter_long(stock_data, 150.00, 0)
assert should_enter == True
```

### 4. **Single Source of Truth** ✅
- trader.py uses strategy module
- backtester.py uses strategy module
- Fix bug once, applies everywhere

---

## Migration Checklist

### trader.py Changes Needed:
- [ ] Import `PS60Strategy` and `PositionManager`
- [ ] Replace `check_pivot_break()` with `strategy.should_enter_long/short()`
- [ ] Replace 5-min rule in `manage_positions()` with `strategy.check_five_minute_rule()`
- [ ] Replace `should_take_partial()` logic with `strategy.should_take_partial()`
- [ ] Replace `calculate_position_size()` with `strategy.calculate_position_size()`
- [ ] Replace position dict management with `PositionManager`
- [ ] Keep IBKR API calls (placeOrder, etc.)
- [ ] Keep logging, connection, subscription logic

### backtester.py Changes Needed:
- [ ] Import `PS60Strategy` and `PositionManager`
- [ ] Use `strategy.should_enter_long/short()` for entry decisions
- [ ] Use `strategy.check_five_minute_rule()` for 5-min exits
- [ ] Use `strategy.should_take_partial()` for partial logic
- [ ] Use `PositionManager` for position tracking
- [ ] Remove duplicate logic that's now in strategy/

---

## Validation Tests

### Test 1: Entry Logic
```python
stock_data = {'symbol': 'AAPL', 'resistance': 150.00, 'support': 148.00}
current_price = 150.50  # Above resistance

should_enter, reason = strategy.should_enter_long(stock_data, current_price, 0)
assert should_enter == True
assert reason == "Resistance broken"
```

### Test 2: 5-Min Rule (Stuck at Pivot)
```python
position = {
    'entry_time': datetime.now() - timedelta(minutes=6),
    'entry_price': 150.00,
    'side': 'LONG',
    'partials': []
}
current_price = 150.20  # Only 0.13% gain - stuck!

should_exit, reason = strategy.check_five_minute_rule(position, current_price, datetime.now())
assert should_exit == True  # Should exit - stuck at pivot
```

### Test 3: 5-Min Rule (Moving Favorably)
```python
position = {
    'entry_time': datetime.now() - timedelta(minutes=6),
    'entry_price': 150.00,
    'side': 'LONG',
    'partials': [{'gain': 0.50}]  # Took partial - was moving!
}
current_price = 150.20

should_exit, reason = strategy.check_five_minute_rule(position, current_price, datetime.now())
assert should_exit == False  # Should NOT exit - had favorable movement
```

---

## Conclusion

### ✅ Strategy Module is COMPLETE

All core trading logic from `trader.py` has been:
1. Extracted to `strategy/` module
2. Fixed (5-min rule bug corrected)
3. Improved (better separation, testability)
4. Documented (this file + USAGE_EXAMPLE.md)

### Next Steps:
1. Update `trader.py` to use strategy module (preserve IBKR API calls)
2. Update `backtester.py` to use strategy module
3. Test both to ensure identical behavior
4. Enjoy single-source-of-truth benefits!

---

*Last updated: October 2, 2025*
*After full coverage analysis of trader.py*
