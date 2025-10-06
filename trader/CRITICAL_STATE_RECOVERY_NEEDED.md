# CRITICAL: State Recovery System Needed

**Date**: October 6, 2025
**Priority**: 🔴 **CRITICAL**
**Status**: ❌ **NOT IMPLEMENTED**

---

## Problem Statement

**CRITICAL ISSUE**: If the live trader crashes or restarts during trading hours, it has NO CONTEXT about:

1. ❌ **Open Positions**: What positions are currently held
2. ❌ **Partial Fills**: How many partials have been taken
3. ❌ **Stop Orders**: Which stop orders are active
4. ❌ **Attempt Counts**: How many attempts per pivot
5. ❌ **Bar Buffers**: Historical 5-second bars (loses warmup)
6. ❌ **Entry Prices**: Original entry price for P&L calculation
7. ❌ **Position Metadata**: Target prices, pivot levels, contract details

### Real-World Impact

**Scenario 1: Crash During Open Positions**
```
10:05 AM - Enter LONG TSLA @ $445.25 (100 shares)
10:08 AM - Take 50% partial @ $447.13
10:15 AM - TRADER CRASHES 💥
10:16 AM - Trader restarts...
         - Has NO idea TSLA position exists
         - Doesn't know 50% partial was taken
         - Can't manage remaining 50 shares
         - No stop order management
         - Could enter DUPLICATE position!
```

**Risk**: Unmanaged positions, duplicate entries, unclosed stops

**Scenario 2: Restart After Multiple Attempts**
```
10:05 AM - TSLA breaks resistance (attempt 1)
10:08 AM - Stopped out (loss)
10:15 AM - TSLA breaks resistance again (attempt 2)
10:20 AM - TRADER CRASHES 💥
10:21 AM - Trader restarts...
         - Has NO idea 2 attempts were already made
         - Could enter attempt 3 (should be blocked!)
```

**Risk**: Whipsaw losses, exceeding max attempts

**Scenario 3: Gap in Bar Data**
```
10:00 AM - Trader running, bar buffers accumulating
10:30 AM - TRADER CRASHES 💥
10:31 AM - Trader restarts...
         - Bar buffers empty (loses 30 minutes of data)
         - Warmup period starts over (100 seconds)
         - Can't check hybrid entry (needs 20 bars)
         - Misses entries for 100 seconds
```

**Risk**: Missed opportunities, incorrect filter decisions

---

## Required State Persistence

### 1. Open Positions (CRITICAL)

**What to Persist**:
```json
{
  "positions": {
    "TSLA": {
      "symbol": "TSLA",
      "side": "LONG",
      "entry_price": 445.25,
      "entry_time": "2025-10-06T10:05:47-04:00",
      "shares": 100,
      "remaining": 0.5,
      "pivot": 444.77,
      "target1": 460.25,
      "target2": 470.50,
      "stop_price": 445.25,
      "stop_order_id": 12345,
      "contract": {
        "symbol": "TSLA",
        "exchange": "SMART",
        "currency": "USD"
      },
      "partials_taken": [
        {
          "time": "2025-10-06T10:08:15-04:00",
          "price": 447.13,
          "shares": 50,
          "reason": "PARTIAL_50"
        }
      ]
    }
  }
}
```

**Why Critical**: Without this, we can't manage open positions after restart

### 2. Attempt Counts (CRITICAL)

**What to Persist**:
```json
{
  "attempt_counts": {
    "TSLA": {
      "long_attempts": 2,
      "short_attempts": 0,
      "resistance": 444.77,
      "support": 432.50
    },
    "NVDA": {
      "long_attempts": 1,
      "short_attempts": 0,
      "resistance": 725.50,
      "support": 710.30
    }
  }
}
```

**Why Critical**: Prevents exceeding max attempts, whipsaw protection

### 3. Session State (MEDIUM)

**What to Persist**:
```json
{
  "session": {
    "start_time": "2025-10-06T09:30:00-04:00",
    "watchlist": [...],
    "daily_pnl": 756.19,
    "trades_today": 3,
    "analytics": {
      "filter_blocks": {...},
      "entry_paths": {...}
    }
  }
}
```

**Why Important**: Continue analytics, track daily limits

### 4. Bar Buffers (MEDIUM)

**What to Persist**:
```json
{
  "bar_buffers": {
    "TSLA": {
      "bars": [
        {"time": "2025-10-06T10:00:00-04:00", "open": 444.50, "high": 444.85, ...},
        {"time": "2025-10-06T10:00:05-04:00", "open": 444.77, "high": 445.00, ...}
      ]
    }
  }
}
```

**Why Important**: Avoid re-warmup period, maintain filter accuracy

---

## Solution Design

### Option 1: Query IBKR Portfolio (RECOMMENDED)

**Pros**:
- ✅ Broker is source of truth
- ✅ Handles broker-side fills we missed
- ✅ Automatically syncs on restart

**Cons**:
- ⚠️ Doesn't recover metadata (pivot, targets, attempt counts)
- ⚠️ Need separate file for metadata

**Implementation**:
```python
def recover_state_from_ibkr(self):
    """
    Recover open positions from IBKR on restart

    CRITICAL: Call this immediately after connecting
    """
    # Get all open positions from IBKR
    positions = self.ib.positions()

    for pos in positions:
        symbol = pos.contract.symbol

        # Only recover positions in today's watchlist
        if symbol in [s['symbol'] for s in self.watchlist]:
            self.logger.warning(f"🔄 RECOVERED POSITION: {symbol} {pos.position} shares @ avg ${pos.avgCost:.2f}")

            # Try to load metadata from state file
            metadata = self.load_position_metadata(symbol)

            if metadata:
                # Full recovery with metadata
                self.positions[symbol] = metadata
                self.positions[symbol]['shares'] = pos.position
                self.positions[symbol]['entry_price'] = pos.avgCost
            else:
                # Partial recovery - create minimal position
                self.logger.error(f"⚠️  No metadata for {symbol} - creating minimal position")
                self.positions[symbol] = self.create_minimal_position(pos)

    # Get all open orders
    orders = self.ib.openOrders()

    for order in orders:
        symbol = order.contract.symbol
        if symbol in self.positions:
            self.logger.info(f"🔄 RECOVERED STOP ORDER: {symbol} @ ${order.lmtPrice:.2f}")
            self.positions[symbol]['stop_order_id'] = order.orderId
```

### Option 2: State File Persistence

**Pros**:
- ✅ Preserves all metadata
- ✅ Fast recovery
- ✅ Can recover attempt counts, bar buffers

**Cons**:
- ⚠️ Out of sync if broker-side fills occur
- ⚠️ File corruption risk

**Implementation**:
```python
def save_state(self):
    """
    Save trading state to file (called every 10 seconds)

    CRITICAL: Save frequently to minimize data loss
    """
    state = {
        'timestamp': datetime.now(pytz.UTC).isoformat(),
        'positions': self.serialize_positions(),
        'attempt_counts': self.pm.get_attempt_counts(),
        'bar_buffers': self.serialize_bar_buffers(),
        'analytics': {
            'filter_blocks': dict(self.analytics['filter_blocks']),
            'entry_paths': dict(self.analytics['entry_paths']),
            'daily_pnl': self.pm.get_daily_summary()['daily_pnl']
        }
    }

    state_file = Path('logs/trader_state.json')

    # Atomic write (write to temp, then rename)
    temp_file = state_file.with_suffix('.tmp')
    with open(temp_file, 'w') as f:
        json.dump(state, f, indent=2)

    temp_file.rename(state_file)

def load_state(self):
    """
    Load trading state from file (called on startup)

    CRITICAL: Validate state is from today
    """
    state_file = Path('logs/trader_state.json')

    if not state_file.exists():
        self.logger.info("No previous state found (clean start)")
        return

    with open(state_file) as f:
        state = json.load(f)

    # Validate state is from today
    state_time = datetime.fromisoformat(state['timestamp'])
    eastern = pytz.timezone('US/Eastern')
    now_et = datetime.now(pytz.UTC).astimezone(eastern)

    if state_time.date() != now_et.date():
        self.logger.warning("State file is from previous day - ignoring")
        return

    # Restore positions
    self.restore_positions(state['positions'])

    # Restore attempt counts
    self.pm.restore_attempt_counts(state['attempt_counts'])

    # Restore bar buffers (optional)
    self.restore_bar_buffers(state['bar_buffers'])

    # Restore analytics
    self.analytics.update(state['analytics'])

    self.logger.info(f"🔄 STATE RECOVERED from {state_time.strftime('%I:%M:%S %p')} ET")
    self.logger.info(f"   Positions: {len(state['positions'])}")
    self.logger.info(f"   Daily P&L: ${state['analytics']['daily_pnl']:.2f}")
```

### Option 3: Hybrid (BEST)

**Combine both approaches**:

1. **Load state file** (metadata, attempt counts, bar buffers)
2. **Query IBKR portfolio** (validate positions, recover missed fills)
3. **Reconcile differences** (IBKR is source of truth for shares)

```python
def recover_full_state(self):
    """
    HYBRID RECOVERY: Load state file + validate with IBKR

    CRITICAL: Best of both worlds
    """
    # Step 1: Load state file (metadata)
    state = self.load_state()

    # Step 2: Query IBKR (source of truth for positions)
    ibkr_positions = {p.contract.symbol: p for p in self.ib.positions()}

    # Step 3: Reconcile
    for symbol, pos_data in state['positions'].items():
        if symbol in ibkr_positions:
            # IBKR confirms position exists
            ibkr_pos = ibkr_positions[symbol]

            # Validate shares match
            if abs(ibkr_pos.position - pos_data['shares']) > 0.1:
                self.logger.error(f"⚠️  {symbol}: State file shows {pos_data['shares']} shares, IBKR shows {ibkr_pos.position}")
                self.logger.error(f"    Using IBKR value (source of truth)")
                pos_data['shares'] = ibkr_pos.position

            # Restore position with metadata
            self.positions[symbol] = pos_data
            self.logger.info(f"🔄 RECOVERED: {symbol} {pos_data['shares']} shares (state + IBKR validated)")
        else:
            # State file shows position but IBKR doesn't
            self.logger.error(f"⚠️  {symbol}: State file shows position but NOT in IBKR portfolio")
            self.logger.error(f"    Possible: closed by broker, or state file stale")
            # Don't restore this position

    # Step 4: Check for positions in IBKR but not in state file
    for symbol, ibkr_pos in ibkr_positions.items():
        if symbol not in state['positions']:
            self.logger.warning(f"⚠️  {symbol}: In IBKR portfolio but NOT in state file")
            self.logger.warning(f"    Creating minimal position (metadata lost)")
            self.positions[symbol] = self.create_minimal_position(ibkr_pos)
```

---

## Implementation Priority

### Phase 1: CRITICAL (Must Have Before Paper Trading) 🔴

1. **IBKR Position Recovery** (Option 1)
   - Query `ib.positions()` on startup
   - Recover open positions
   - Log recovered positions
   - **Timeline**: 1-2 hours

2. **State File Persistence** (Option 2)
   - Save positions/metadata every 10 seconds
   - Load on startup
   - Validate against IBKR
   - **Timeline**: 2-3 hours

3. **Testing**:
   - Simulate crash during open position
   - Verify recovery works
   - **Timeline**: 1 hour

### Phase 2: IMPORTANT (Should Have for Production) 🟡

1. **Attempt Count Persistence**
   - Save to state file
   - Restore on startup
   - **Timeline**: 30 minutes

2. **Analytics Persistence**
   - Continue daily P&L tracking
   - Preserve filter block counts
   - **Timeline**: 30 minutes

### Phase 3: NICE TO HAVE (Performance Optimization) 🟢

1. **Bar Buffer Persistence**
   - Save to state file (large data)
   - Restore to avoid warmup
   - **Timeline**: 1 hour

---

## Code Structure

```
trader/
├── state_manager.py           # NEW - State persistence module
│   ├── StateManager class
│   ├── save_state()
│   ├── load_state()
│   ├── recover_from_ibkr()
│   └── reconcile_state()
│
├── trader.py                  # MODIFY - Add state recovery
│   └── run() method
│       ├── Connect to IBKR
│       ├── Load scanner results
│       ├── StateManager.recover_full_state()  # NEW
│       ├── Subscribe to market data
│       └── Main loop
│           └── StateManager.save_state() every 10s  # NEW
│
└── logs/
    ├── trader_state.json      # NEW - Current state
    └── trader_state_backup.json  # NEW - Previous state (safety)
```

---

## Testing Plan

### Test 1: Crash During Open Position

**Steps**:
1. Start trader, enter LONG TSLA
2. Kill trader process (simulate crash)
3. Restart trader
4. **Expected**: TSLA position recovered, stop order active

### Test 2: Crash After Partial

**Steps**:
1. Start trader, enter LONG TSLA (100 shares)
2. Take 50% partial
3. Kill trader process
4. Restart trader
5. **Expected**: TSLA position shows 50 shares remaining, stop at breakeven

### Test 3: Crash After Max Attempts

**Steps**:
1. Start trader, enter TSLA (attempt 1), get stopped
2. Enter TSLA (attempt 2), get stopped
3. Kill trader process
4. Restart trader
5. Price breaks pivot again
6. **Expected**: Entry blocked (max 2 attempts)

### Test 4: IBKR Fill During Downtime

**Steps**:
1. Start trader, enter LONG TSLA
2. Kill trader process
3. Manually fill TSLA stop order in TWS
4. Restart trader
5. **Expected**: Detects TSLA position is closed, removes from tracking

---

## Risk Mitigation

### Risk 1: State File Corruption

**Mitigation**:
- Atomic writes (write to .tmp, then rename)
- Keep backup of previous state
- Validate JSON on load (try/except)
- Fall back to IBKR-only recovery

### Risk 2: IBKR API Unavailable

**Mitigation**:
- Retry connection 3 times
- If IBKR unavailable, use state file only
- Log warning about potential drift

### Risk 3: Clock Skew (State from Yesterday)

**Mitigation**:
- Always validate state timestamp
- Reject if not from today
- Log reason for rejection

### Risk 4: Duplicate Positions

**Mitigation**:
- Always check if symbol already in self.positions
- Never enter if position exists (unless intentional scaling)
- Log warning if duplicate detected

---

## Example Logs

### Normal Recovery
```
PS60 LIVE TRADER - PAPER TRADING SESSION
Date: 2025-10-06 Monday
Time: 10:16:32 AM ET
================================================================================
✓ Connected to IBKR (Paper: Port 7497, Client ID: 2001)
🔄 RECOVERING STATE from previous session...

🔄 STATE RECOVERED from 10:05:47 AM ET (11 minutes ago)
   Positions: 3
   Daily P&L: $756.19

🔄 VALIDATING WITH IBKR PORTFOLIO...
   TSLA: State file shows 50 shares, IBKR confirms 50 shares ✓
   NVDA: State file shows 100 shares, IBKR confirms 100 shares ✓
   AMD: State file shows 200 shares, IBKR shows 0 shares ⚠️
       → Position was closed by broker during downtime

FINAL RECOVERED STATE:
  Positions: 2 (TSLA, NVDA)
  Daily P&L: $756.19 (continuing from previous session)

✓ State recovery complete - resuming trading
```

### First Start (No State)
```
PS60 LIVE TRADER - PAPER TRADING SESSION
Date: 2025-10-06 Monday
Time: 09:30:15 AM ET
================================================================================
✓ Connected to IBKR (Paper: Port 7497, Client ID: 2001)
ℹ️  No previous state found (clean start)
✓ Loaded 8 setups from scanner_results_20251006.json
```

---

## Next Steps

1. ✅ **Read this document** - Understand the problem
2. ⏳ **Implement StateManager class** - Phase 1 (CRITICAL)
3. ⏳ **Add to trader.py** - Integrate recovery logic
4. ⏳ **Test crash scenarios** - Validate recovery works
5. ⏳ **Update documentation** - Add to LIVE_TRADER_READY_FOR_TESTING.md

---

## CRITICAL DECISION NEEDED

**Question**: Should we implement state recovery BEFORE or AFTER simulated testing?

**Option A: BEFORE Simulated Testing** (RECOMMENDED)
- ✅ More realistic testing
- ✅ Can test crash recovery
- ⏳ Delays testing by 4-6 hours

**Option B: AFTER Simulated Testing**
- ✅ Faster to testing
- ❌ Testing won't catch recovery issues
- ❌ Risk in paper trading

**RECOMMENDATION**: Implement Phase 1 (IBKR recovery + state file) BEFORE simulated testing

---

**Status**: ❌ **NOT IMPLEMENTED**
**Priority**: 🔴 **CRITICAL**
**Estimated Time**: 4-6 hours (Phase 1 only)
**Blocking**: Paper trading should NOT start without this

**Last Updated**: October 6, 2025
