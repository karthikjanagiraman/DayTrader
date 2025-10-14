# Critical Missing Features in Live Trader
## October 9, 2025

## Summary

The live trader is missing 3 critical entry/exit features that exist in the backtester:

1. ❌ **BOUNCE entry path** (pullback to support + reversal for longs)
2. ❌ **REJECTION entry path** (failed breakout at resistance → short)
3. ❌ **Trailing stop logic** (update and check trailing stops for runners)

---

## Feature #1: BOUNCE Entry Path

### What It Is

BOUNCE = Pullback to support + reversal confirmation → LONG entry

**Example**:
- Stock was trending up
- Pulls back to support level ($100)
- Bounces off support with volume
- Enter LONG on bounce confirmation

### Where It Exists

**Backtester** (backtester.py:517-524):
```python
# Check BOUNCE long entry (pullback to support + reversal)
if position is None and long_attempts < max_attempts and price > support * 0.99 and self.enable_longs:
    bounce_confirmed, bounce_reason = self.strategy.check_bounce_setup(
        bars, bar_count, support, side='LONG'
    )

    if bounce_confirmed:
        position = self.enter_long(stock, price, timestamp, bar_count, setup_type='BOUNCE')
        long_attempts += 1
```

### Where It's Missing

**Live Trader** (trader.py): No call to `check_bounce_setup()`

### Impact

**Medium** - BOUNCE setups are profitable (pullback entries often have better R/R than breakouts)

Without this, live trader misses:
- Lower-risk entries (buy closer to support)
- Better R/R ratios (stop at support, target at resistance)
- Pullback continuation trades

### Fix Required

Add to live trader's `check_setup()` method after breakout checks:

```python
# After breakout checks (line ~620)

# Check BOUNCE long entry (pullback to support + reversal)
if symbol not in self.positions and long_attempts < max_attempts:
    # Only check if price near support (within 1%)
    if current_price > support * 0.99 and current_price < support * 1.01:
        bounce_confirmed, bounce_reason = self.strategy.check_bounce_setup(
            bars, current_idx, support, side='LONG'
        )

        if bounce_confirmed:
            self.logger.info(f"\n🔄 {symbol}: BOUNCE SIGNAL @ ${current_price:.2f}")
            return 'LONG', support, bounce_reason
```

---

## Feature #2: REJECTION Entry Path

### What It Is

REJECTION = Price breaks resistance but fails (gets rejected) → SHORT entry

**Example**:
- Stock breaks above resistance ($110)
- Sellers reject the breakout
- Price falls back below resistance
- Enter SHORT on rejection confirmation

### Where It Exists

**Backtester** (backtester.py:528-535):
```python
# Check REJECTION short entry (failed breakout at resistance)
if position is None and short_attempts < max_attempts and price < resistance * 1.01 and self.enable_shorts:
    rejection_confirmed, rejection_reason = self.strategy.check_rejection_setup(
        bars, bar_count, resistance, side='SHORT'
    )

    if rejection_confirmed:
        position = self.enter_short(stock, price, timestamp, bar_count, setup_type='REJECTION')
        short_attempts += 1
```

### Where It's Missing

**Live Trader** (trader.py): No call to `check_rejection_setup()`

### Impact

**Medium** - REJECTION setups are profitable (fading false breakouts is a PS60 core strategy)

Without this, live trader misses:
- False breakout shorts (high probability)
- Better entries for shorts (near resistance)
- Rejection/fade opportunities

### Fix Required

Add to live trader's `check_setup()` method:

```python
# After bounce checks

# Check REJECTION short entry (failed breakout at resistance)
if symbol not in self.positions and short_attempts < max_attempts:
    # Only check if price near resistance (within 1%)
    if current_price < resistance * 1.01 and current_price > resistance * 0.99:
        rejection_confirmed, rejection_reason = self.strategy.check_rejection_setup(
            bars, current_idx, resistance, side='SHORT'
        )

        if rejection_confirmed:
            self.logger.info(f"\n⬇️ {symbol}: REJECTION SIGNAL @ ${current_price:.2f}")
            return 'SHORT', resistance, rejection_reason
```

---

## Feature #3: Trailing Stop Logic

### What It Is

Trailing stops follow price to lock in gains as position moves in your favor.

**Example (LONG)**:
- Enter at $100, stop at $99
- Take 50% partial at $101, move stop to $100 (breakeven)
- Price reaches $103 → Trail stop to $102 (lock in $2 gain)
- Price reaches $105 → Trail stop to $104 (lock in $4 gain)
- Price drops to $104 → Trailing stop hit, exit at $104 (+$4/share on runner)

### Where It Exists

**Backtester** (backtester.py:805-820):
```python
# Update trailing stop for runners (per requirements)
stop_updated, new_stop, trail_reason = self.strategy.update_trailing_stop(pos, price)
if stop_updated:
    pos['stop'] = new_stop

# Check trailing stop hit (for runners)
trail_hit, trail_reason = self.strategy.check_trailing_stop_hit(pos, price)
if trail_hit:
    # Apply stop slippage
    if pos['side'] == 'LONG':
        exit_price = price * (1 - self.stop_slippage)
    else:
        exit_price = price * (1 + self.stop_slippage)
    return None, self.close_position(pos, exit_price, timestamp, trail_reason.split()[0], bar_num)
```

### Where It's Missing

**Live Trader** (trader.py): ❌ NO trailing stop update OR check!

### Impact

**CRITICAL** - Without trailing stops, runners don't lock in gains

**Impact on P&L**:
- Runners give back profits (price goes up, then back down, stop at breakeven hits)
- Miss capturing large moves (PS60 relies on letting winners run)
- Lower average winner size

**Example**:
- Enter at $100, stop at $99
- Partial at $101, stop to $100
- Price runs to $110 without trailing stop
- Price drops back to $100 → Exit at breakeven ($0 on runner!)
- **WITH trailing stop**: Would have exited at $108-109 (+$8-9/share on runner)

### Fix Required

Add to live trader's position monitoring loop (after partial logic):

```python
# After partial profit-taking (line ~910)

# Update trailing stop for runners
stop_updated, new_stop, trail_reason = self.strategy.update_trailing_stop(
    position, current_price
)
if stop_updated:
    position['stop'] = new_stop
    self.logger.info(f"   ⬆️  {trail_reason}")

    # Update stop order with IBKR
    if 'stop_order' in position and position['stop_order']:
        self.cancel_order(position['stop_order'])
        stop_order = self.place_stop_order(
            position['contract'],
            position['side'],
            position['remaining'] * position['shares'],
            new_stop
        )
        position['stop_order'] = stop_order

# Check trailing stop hit
trail_hit, trail_reason = self.strategy.check_trailing_stop_hit(
    position, current_price
)
if trail_hit:
    self.logger.info(f"   🎯 {trail_reason} - closing runner")
    trade = self.close_position(position, current_price, trail_reason)
    if trade:
        trades_to_monitor.append(trade)
    continue
```

---

## Implementation Priority

### Priority 1: CRITICAL - Add Trailing Stops (Feature #3)

**Impact**: Massive - Required for letting runners capture large moves
**Complexity**: Medium - Need to update IBKR stop orders
**Risk**: High if not implemented - Runners won't lock in gains

### Priority 2: HIGH - Add BOUNCE Entry (Feature #1)

**Impact**: Medium - Adds pullback entry opportunities
**Complexity**: Low - Just add method call
**Risk**: Medium - Missing profitable setups

### Priority 3: MEDIUM - Add REJECTION Entry (Feature #2)

**Impact**: Medium - Adds short opportunities
**Complexity**: Low - Just add method call
**Risk**: Low - Rejection setups less frequent

---

## Implementation Plan

### Step 1: Add Trailing Stop Logic (30 min)

1. Add `update_trailing_stop()` call to position monitoring loop
2. Update IBKR stop orders when trailing stop moves
3. Add `check_trailing_stop_hit()` call
4. Test with paper trading

### Step 2: Add BOUNCE Entry (15 min)

1. Add `check_bounce_setup()` call after breakout checks
2. Only check when price near support (within 1%)
3. Log bounce signals
4. Test detection

### Step 3: Add REJECTION Entry (15 min)

1. Add `check_rejection_setup()` call
2. Only check when price near resistance (within 1%)
3. Log rejection signals
4. Test detection

---

## Testing Plan

### Test #1: Trailing Stop

**Setup**: Enter COIN long at $391.77, stop at $390.49
**Action**: Manually move price to $395, $398, $400
**Expected**:
- Stop trails from $390.49 → $393 → $396 → $398
- IBKR stop orders updated each time

### Test #2: BOUNCE Entry

**Setup**: COIN support at $390.49, price at $391.00
**Action**: Simulate pullback to $390.60, bounce to $391.20 with volume
**Expected**: BOUNCE signal generated, enter LONG

### Test #3: REJECTION Entry

**Setup**: AVGO resistance at $347.10, price breaks to $347.50
**Action**: Simulate rejection, price drops to $346.80
**Expected**: REJECTION signal generated, enter SHORT

---

## Risk if Not Fixed

### Without Trailing Stops:
- **Estimated Impact**: -30% on runner P&L
- **Example**: Oct 9 COIN runner - Could have captured $3-5 instead of breakeven

### Without BOUNCE Entry:
- **Estimated Impact**: Missing 20-30% of profitable entries
- **Example**: Lower-risk pullback entries not available

### Without REJECTION Entry:
- **Estimated Impact**: Missing 10-15% of short opportunities
- **Example**: False breakout shorts (high win rate) not available

---

## Conclusion

Live trader is missing **3 critical features** that exist in backtester:

1. ❌ **Trailing stops** (CRITICAL - required for runners)
2. ❌ **BOUNCE entry** (HIGH - missing profitable setups)
3. ❌ **REJECTION entry** (MEDIUM - missing short opportunities)

**Action Required**: Implement all 3 before live trading

**Estimated Time**: 1 hour total (30min + 15min + 15min)

**Next Steps**:
1. Implement trailing stops FIRST
2. Test with paper trading
3. Add BOUNCE/REJECTION after trailing stops verified
