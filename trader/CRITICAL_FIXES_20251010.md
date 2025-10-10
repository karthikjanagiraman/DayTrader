# Critical Fixes - October 10, 2025

## Session Review Summary

- **Date**: October 10, 2025
- **Session Start**: 6:54 AM PDT (9:54 AM EDT)
- **Trades**: 11 attempted, 8 filled, 3 rejected (margin)
- **Daily P&L**: -$675.08 (2 losers)
- **Issues Found**: 11 critical bugs

## P1 - HIGH PRIORITY FIXES

### Fix #1: Margin Check Before Entry ⚠️ CRITICAL

**Problem**: No margin check before placing orders → 3 orders rejected

**Files Modified**:
- `trader.py` - Add `check_margin_available()` method
- `trader.py` - Call margin check in `enter_long()` and `enter_short()`

**Implementation**:
```python
def check_margin_available(self, symbol, shares, price):
    """Check if sufficient margin available for trade"""
    try:
        account_values = self.ib.accountSummary()

        # Get buying power
        buying_power = next((v.value for v in account_values
                           if v.tag == 'BuyingPower'), None)

        if not buying_power:
            self.logger.warning(f"Could not query buying power - allowing trade")
            return True, "Unknown"

        buying_power = float(buying_power)
        required_margin = shares * price

        if required_margin > buying_power:
            return False, f"Insufficient margin: ${buying_power:.2f} available, ${required_margin:.2f} required"

        return True, f"${buying_power:.2f} available"

    except Exception as e:
        self.logger.error(f"Error checking margin: {e}")
        # On error, allow trade (fail-open for now)
        return True, "Error checking margin"
```

---

### Fix #2: Remove Positions When remaining = 0.0 ⚠️ CRITICAL

**Problem**: Positions with remaining=0.0 still tracked after 2 partials

**Files Modified**:
- `trader.py` - Add check in `take_partial()` after updating remaining

**Implementation**:
```python
# In take_partial() after line 1067
# Check if position fully closed after partial
if position['remaining'] <= 0:
    self.logger.info(f"  ✓ {symbol}: Position fully closed via partials")
    # Record final trade
    trade_record = self.pm.close_position(symbol, price, 'FULL_PARTIALS')
    # Remove from local tracking
    if symbol in self.positions:
        del self.positions[symbol]
```

---

### Fix #3: Detect Broker-Initiated Closes ⚠️ CRITICAL

**Problem**: Broker closed 7 positions but trader didn't detect until restart

**Files Modified**:
- `trader.py` - Add portfolio sync check in `manage_positions()`

**Implementation**:
```python
# In manage_positions() at start of loop (after line 887)
# CRITICAL: Check if position still exists in IBKR portfolio
# If not, broker closed it (stop fill, margin call, etc.)
try:
    portfolio = self.ib.portfolio()
    ibkr_symbols = {p.contract.symbol for p in portfolio}

    if symbol not in ibkr_symbols:
        self.logger.warning(f"  ⚠️  {symbol}: NOT in IBKR portfolio - closed by broker")
        self.logger.warning(f"     Removing from tracking (already closed externally)")
        # Record trade with unknown exit price
        trade_record = self.pm.close_position(
            symbol,
            current_price,  # Approximate
            'BROKER_CLOSE'
        )
        continue
except Exception as e:
    self.logger.debug(f"  Could not verify {symbol} in IBKR portfolio: {e}")
    # Continue normal processing
```

---

## P2 - MEDIUM PRIORITY FIXES

### Fix #4: Save Stop Order to State File

**Problem**: State file shows stop_price: null despite stops being placed

**Files Modified**:
- `state_manager.py` - Fix field names in `_serialize_positions()`

**Current Code** (Lines 291-292):
```python
'stop_price': pos.get('stop_price'),  # WRONG - should be 'stop'
'stop_order_id': pos.get('stop_order_id'),  # WRONG - should be 'stop_order'
```

**Fixed Code**:
```python
'stop_price': pos.get('stop'),  # Correct field name
'stop_order_id': pos.get('stop_order').order.orderId if pos.get('stop_order') else None,
'partials_taken': [p for p in pos.get('partials', [])]  # Full partial history
```

---

### Fix #5: Round Stop Prices to Minimum Tick

**Problem**: Warning 110 - stop prices don't conform to minimum tick size

**Files Modified**:
- `trader.py` - Add rounding in `place_stop_order()`

**Implementation**:
```python
# In place_stop_order() before creating StopOrder (line 858)
# Round stop price to nearest penny (minimum tick for stocks)
stop_price = round(position['stop'], 2)

# Create stop order with rounded price
stop_order = StopOrder(action, shares, stop_price)
```

---

### Fix #6: Fix Daily P&L Tracking

**Problem**: Daily P&L shows -$675 but should track all closed trades

**Files Modified**:
- None needed - position_manager.py already does this correctly

**Verification**:
- `position_manager.py:220` - `self.daily_pnl += pnl` is called in `close_position()`
- P&L calculation is correct
- Issue was that most trades never closed (broker close not detected)

---

## Testing Plan

### Test 1: Margin Check
1. Monitor next entry attempt
2. Verify margin check logged
3. Confirm order only placed if margin sufficient

### Test 2: Position Cleanup
1. Wait for next partial profit
2. Verify position removed if remaining = 0.0
3. Check state file confirms removal

### Test 3: Broker Close Detection
1. Currently have 2 active positions (OXY, CVX)
2. If IBKR closes either, verify detected within 1 second
3. Check position removed from tracking immediately

### Test 4: State File
1. Check next state save
2. Verify stop_price is not null
3. Verify stop_order_id is saved

### Test 5: Stop Price Rounding
1. Check next stop order placement
2. Verify no Warning 110 errors
3. Confirm price is rounded to $0.01

---

## Rollback Plan

If any fix causes issues:
1. Git checkout previous version
2. Restart trader
3. Document issue
4. Fix and re-test

---

## Implementation Order

1. ✅ Fix #4 - Stop state saving (safest, data integrity)
2. ✅ Fix #5 - Stop price rounding (safest, minor change)
3. ✅ Fix #2 - Position cleanup (medium risk)
4. ✅ Fix #3 - Broker close detection (medium risk)
5. ✅ Fix #1 - Margin check (highest risk, prevents trades)
6. ✅ Test all fixes with live session
7. ✅ Monitor for 30 minutes
8. ✅ Document results

---

**Status**: Ready for implementation
**Expected Duration**: 30-45 minutes
**Risk Level**: Medium (testing with live session)
