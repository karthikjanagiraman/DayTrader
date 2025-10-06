# PS60 Trader - Requirements Specification
**Version**: 2.0
**Date**: October 3, 2025
**Status**: CRITICAL FIXES REQUIRED

---

## Executive Summary

This document specifies the architectural and functional requirements for the PS60 automated trading system, addressing critical flaws discovered during initial paper trading sessions. The current implementation has multiple P0 bugs that prevent production deployment.

**Current Status**: ⚠️ **NOT PRODUCTION READY**

**Critical Issues Found**:
- Session crashes on every exit (KeyError)
- Position desynchronization between trader and position manager
- No IBKR position reconciliation
- Orphan positions left open after crashes
- Missing exception handling in core loops
- 128+ errors per trading session

---

## 1. Core Architecture Requirements

### 1.1 Single Source of Truth for Position State

**Current Problem**: Dual position tracking causes desynchronization
- `trader.py` maintains `self.positions` dict
- `position_manager.py` maintains `self.pm.positions` dict
- These can become out of sync, causing zombie positions

**Requirement**:
```
REQ-ARCH-001: Position Manager as Single Source of Truth
- Position Manager shall be the ONLY authoritative source for position state
- Trader shall query Position Manager for all position data
- Trader shall NOT maintain separate position dictionary
- All position mutations shall go through Position Manager methods only
```

**Implementation**:
```python
# trader.py - BEFORE (WRONG)
self.positions[symbol] = position  # ❌ Dual tracking
if symbol in self.positions:       # ❌ Using local dict

# trader.py - AFTER (CORRECT)
self.pm.create_position(...)       # ✅ PM is source
if self.pm.has_position(symbol):   # ✅ Query PM
position = self.pm.get_position(symbol)  # ✅ Get from PM
```

---

### 1.2 State Persistence and Recovery

**Current Problem**: All position state lost on crash, no recovery mechanism

**Requirement**:
```
REQ-ARCH-002: Position State Persistence
- System shall persist position state to disk after every state change
- State file shall include: all open positions, entry times, partials taken, stops
- On startup, system shall restore positions from state file
- State file format: JSON, located at logs/position_state.json
- State shall include timestamp of last update
- State older than 24 hours shall trigger warning on restore
```

**Requirement**:
```
REQ-ARCH-003: Crash Recovery
- On startup, system shall detect if previous session crashed
- System shall compare state file with IBKR actual positions
- System shall reconcile differences and alert user
- System shall offer options: close orphans, adopt orphans, or abort
```

---

### 1.3 IBKR Position Synchronization

**Current Problem**: Trader never verifies its view matches IBKR reality

**Requirement**:
```
REQ-ARCH-004: IBKR Position Reconciliation on Startup
- On startup, system shall query all IBKR positions
- For each IBKR position not in Position Manager:
  - Log WARNING with position details
  - Optionally close position (configurable)
  - Optionally adopt position (create PM entry)
- For each PM position not in IBKR:
  - Log ERROR - position was closed externally
  - Remove from Position Manager
```

**Requirement**:
```
REQ-ARCH-005: Periodic Position Reconciliation
- Every 5 minutes during trading, system shall reconcile positions
- Compare PM position count with IBKR position count
- Compare PM position shares with IBKR position shares
- If mismatch detected:
  - Log ERROR with full diff
  - Alert user (console warning)
  - Optionally halt trading (configurable)
```

---

### 1.4 Exception Handling and Fault Tolerance

**Current Problem**: Exceptions in one position crash entire session

**Requirement**:
```
REQ-ARCH-006: Position-Level Exception Isolation
- Exceptions in processing one position shall NOT affect other positions
- Each position operation shall be wrapped in try/except
- Exceptions shall be logged with full traceback
- Position with repeated errors (>3) shall be force-closed
- System shall continue monitoring other positions
```

**Implementation**:
```python
def manage_positions(self):
    for symbol in self.pm.get_all_symbols():
        try:
            position = self.pm.get_position(symbol)
            # ... manage this position ...
        except Exception as e:
            self.logger.error(f"Error managing {symbol}: {e}", exc_info=True)
            self.error_counts[symbol] = self.error_counts.get(symbol, 0) + 1

            if self.error_counts[symbol] >= 3:
                self.logger.error(f"Force closing {symbol} due to repeated errors")
                self.force_close_position(symbol)
            continue  # Don't crash - continue with other positions
```

**Requirement**:
```
REQ-ARCH-007: Trading Loop Exception Handling
- Main trading loop shall catch all exceptions
- Exceptions shall NOT terminate the trading session
- System shall log exception and continue
- Circuit breaker shall trip after N consecutive exceptions (default: 10)
- Circuit breaker shall pause trading for M seconds (default: 60)
```

---

### 1.5 Graceful Shutdown and Cleanup

**Current Problem**: Session crashes on exit with KeyError

**Requirement**:
```
REQ-ARCH-008: Clean Session Termination
- System shall close all positions before exit
- System shall save final state to disk
- System shall disconnect from IBKR cleanly
- System shall generate daily summary report
- System shall save all trades to JSON file
- Exit code shall indicate success (0) or failure (1+)
```

**Requirement**:
```
REQ-ARCH-009: Signal Handling
- System shall handle SIGINT (Ctrl+C) gracefully
- System shall handle SIGTERM gracefully
- On signal, system shall:
  1. Stop accepting new entries
  2. Close all positions at market
  3. Save state
  4. Print summary
  5. Exit cleanly
```

---

## 2. Data Integrity Requirements

### 2.1 Position Manager Contract

**Requirement**:
```
REQ-DATA-001: Position Manager Interface Contract
- create_position() shall return position dict or raise exception
- get_position() shall return position dict or None (never KeyError)
- close_position() shall return trade record dict or None
- get_daily_summary() shall return dict with ALL required keys:
  - total_trades: int
  - daily_pnl: float
  - winners: int
  - losers: int
  - win_rate: float
  - avg_winner: float
  - avg_loser: float
  - trades: List[dict]  # ❌ MISSING - causes KeyError crash
```

**Requirement**:
```
REQ-DATA-002: Position Dict Schema Validation
- Every position dict shall conform to schema:
  {
    'symbol': str,
    'side': 'LONG' | 'SHORT',
    'entry_price': float,
    'entry_time': datetime (timezone-aware UTC),
    'shares': int,
    'remaining': float (0.0 to 1.0),
    'pivot': float,
    'stop': float,
    'partials': List[dict],
    'contract': ib_insync.Stock,
    'target1': float (optional),
    'target2': float (optional)
  }
- Schema validation shall occur on create and restore
```

---

### 2.2 Timezone Consistency

**Current Status**: ✅ Fixed (all timestamps now UTC)

**Requirement**:
```
REQ-DATA-003: Timezone Awareness
- ALL datetime objects shall be timezone-aware UTC
- position['entry_time'] shall be UTC
- partial['time'] shall be UTC
- trade['entry_time'] and trade['exit_time'] shall be UTC
- When comparing times, both shall be converted to UTC
- When displaying times, convert to Eastern Time for logging only
```

---

## 3. Position Management Requirements

### 3.1 Position Lifecycle

**Requirement**:
```
REQ-POS-001: Position Entry
- Position shall only be created via Position Manager
- Entry time shall be set to datetime.now(pytz.UTC)
- Position shall include IBKR contract object
- Position shall include target prices from scanner data
- Position shall initialize remaining = 1.0
- Position shall initialize partials = []
```

**Requirement**:
```
REQ-POS-002: Partial Profit Taking
- Partial shall be recorded in position['partials'] list
- Partial shall update position['remaining']
- Partial timestamp shall be datetime.now(pytz.UTC)
- Remaining shall never be negative
- Remaining shall be checked before each partial
```

**Requirement**:
```
REQ-POS-003: Position Close
- close_position() shall calculate total P&L across all partials
- close_position() shall record trade in trades_today list
- close_position() shall remove position from PM.positions dict
- close_position() shall return complete trade record
- IF shares remaining is 0, close_position() shall still be called
  (Current bug: early return without calling PM.close_position)
```

---

### 3.2 Position Age Monitoring

**Requirement**:
```
REQ-POS-004: Position Age Alerts
- System shall track time since position entry
- If position open > 2 hours, log WARNING
- If position open > 4 hours, log ERROR and alert
- If position open > 6 hours, force close (emergency)
- Partials extend timeout (after partial, timeout resets)
```

---

### 3.3 Stop Loss Management

**Requirement**:
```
REQ-POS-005: Stop Loss Verification
- Every position shall have a stop price
- Stop shall be verified against current price every cycle
- Stop hit shall trigger immediate close
- Stop order shall be placed in IBKR (not just software stop)
- Stop order shall be tracked and verified filled
```

**Current Gap**: Software stops only, no IBKR stop orders

---

## 4. Error Handling Requirements

### 4.1 Error Classification

**Requirement**:
```
REQ-ERR-001: Error Severity Levels
- CRITICAL: System cannot continue (e.g., IBKR disconnection)
- ERROR: Position affected but system can continue
- WARNING: Potential issue but no immediate action needed
- INFO: Normal operational message
```

**Requirement**:
```
REQ-ERR-002: Error Response Actions
CRITICAL errors shall:
  - Close all positions at market
  - Save state
  - Disconnect
  - Exit with code 1

ERROR errors shall:
  - Affect only specific position
  - Log with full traceback
  - Continue with other positions
  - Increment error counter

WARNING errors shall:
  - Log message
  - Continue normally
```

---

### 4.2 Circuit Breakers

**Requirement**:
```
REQ-ERR-003: Error Rate Circuit Breaker
- Track errors per minute
- If errors/minute > 10, trigger circuit breaker
- Circuit breaker shall:
  - Pause new entries for 60 seconds
  - Continue managing existing positions
  - Log WARNING
  - Reset counter after pause
```

**Requirement**:
```
REQ-ERR-004: Consecutive Error Circuit Breaker
- Track consecutive errors in trading loop
- If consecutive errors > 10, trigger circuit breaker
- Circuit breaker shall:
  - Stop trading loop
  - Close all positions
  - Save state
  - Exit
```

---

### 4.3 Network Error Handling

**Requirement**:
```
REQ-ERR-005: IBKR Connection Loss Handling
- Detect IBKR disconnection
- Attempt reconnection (max 3 attempts, 10 second intervals)
- If reconnection succeeds:
  - Reconcile positions with IBKR
  - Resume trading
- If reconnection fails:
  - Log CRITICAL error
  - Exit (positions remain in IBKR, cannot manage)
```

---

## 5. Logging and Monitoring Requirements

### 5.1 Structured Logging

**Requirement**:
```
REQ-LOG-001: Log Levels and Content
- DEBUG: Variable values, loop iterations, detailed flow
- INFO: Trade entries/exits, position updates, EOD summary
- WARNING: Unusual conditions, failed orders, reconciliation mismatches
- ERROR: Exceptions, failed operations, data inconsistencies
- CRITICAL: System failures, IBKR disconnections
```

**Requirement**:
```
REQ-LOG-002: Log File Management
- Daily log files: logs/trader_YYYYMMDD.log
- Log rotation: keep last 30 days
- Log format: timestamp - logger - level - message
- Include stack traces for ERROR and above
```

---

### 5.2 Trade Logging

**Requirement**:
```
REQ-LOG-003: Trade Records
- Every trade shall be saved to JSON file
- File location: logs/trades_YYYYMMDD.json
- Trade record schema:
  {
    'symbol': str,
    'side': str,
    'entry_price': float,
    'entry_time': str (ISO format),
    'exit_price': float,
    'exit_time': str (ISO format),
    'shares': int,
    'pnl': float,
    'duration_min': float,
    'exit_reason': str,
    'partials': List[dict]
  }
```

---

### 5.3 Daily Summary

**Requirement**:
```
REQ-LOG-004: End-of-Day Summary
- Daily summary shall include:
  - Total trades
  - Total P&L
  - Win count, loss count, win rate
  - Average winner, average loser
  - Largest winner, largest loser
  - Average trade duration
  - Exit reason breakdown (5MIN_RULE, STOP, TARGET, EOD counts)
- Summary shall be logged to console and file
- Summary shall be saved to JSON: logs/daily_summary_YYYYMMDD.json
```

---

## 6. Testing Requirements

### 6.1 Unit Testing

**Requirement**:
```
REQ-TEST-001: Position Manager Unit Tests
- Test create_position() with valid and invalid data
- Test take_partial() boundary conditions (remaining = 0, > 1.0, negative)
- Test close_position() with various states
- Test get_daily_summary() returns all required keys
- Test timezone handling in all datetime operations
```

**Requirement**:
```
REQ-TEST-002: Strategy Module Unit Tests
- Test 5-minute rule with timezone-aware datetimes
- Test 5-minute rule skips after partials (remaining < 1.0)
- Test partial profit triggering
- Test EOD detection in Eastern Time
- Test entry window detection
```

---

### 6.2 Integration Testing

**Requirement**:
```
REQ-TEST-003: Crash Recovery Testing
- Test: Start trader, create positions, kill -9, restart
- Verify: Positions restored from state file
- Test: Positions in IBKR but not in state file
- Verify: Orphan positions detected and handled
```

**Requirement**:
```
REQ-TEST-004: Exception Handling Testing
- Test: Inject exception in manage_positions() for one symbol
- Verify: Other positions continue to be managed
- Test: Inject consecutive exceptions
- Verify: Circuit breaker trips, trading stops
```

---

### 6.3 Backtester Compatibility

**Requirement**:
```
REQ-TEST-005: Shared Strategy Module Testing
- Backtester shall use SAME strategy module as live trader
- All strategy methods shall work with both bar timestamps (backtester)
  and live datetimes (trader)
- No backtest-specific logic in strategy module
- All timezone handling shall work for both historical and live data
```

---

## 7. Configuration Requirements

### 7.1 Config Validation

**Requirement**:
```
REQ-CFG-001: Configuration Schema Validation
- System shall validate trader_config.yaml on startup
- Required fields shall be checked
- Type validation shall occur (int, float, str, time)
- Invalid config shall cause immediate exit with helpful error
```

---

### 7.2 Runtime Configuration

**Requirement**:
```
REQ-CFG-002: Runtime Adjustable Parameters
The following shall be adjustable without restart:
- Risk per trade percentage (via console command or signal)
- Max positions (via console command)
- Entry window paused/resumed

The following shall NOT be adjustable at runtime:
- IBKR connection settings
- Scanner output directory
- Logging settings
```

---

## 8. Critical Bugs to Fix (P0)

### BUG-001: KeyError on Session Exit
**File**: `trader.py:560`
**Line**: `if summary['trades']:`
**Error**: `KeyError: 'trades'` - key doesn't exist in summary dict

**Fix**: Add `'trades': self.trades_today` to `position_manager.get_daily_summary()` return value

**Test**: Verify daily summary prints without crash

---

### BUG-002: Position Desync on Early Close
**File**: `trader.py:382-384`
**Code**:
```python
if shares == 0:
    del self.positions[symbol]
    return None  # ❌ Doesn't call pm.close_position()!
```

**Fix**:
```python
if shares == 0:
    self.pm.close_position(symbol, price, reason)
    del self.positions[symbol]
    return None
```

**Test**: Verify position removed from both trader and PM

---

### BUG-003: No IBKR Position Sync
**File**: `trader.py` - missing functionality
**Issue**: On startup, doesn't check for orphan IBKR positions

**Fix**: Add `sync_ibkr_positions()` method called in `__init__()`

**Test**:
1. Manually open position in TWS
2. Start trader
3. Verify trader detects and handles orphan position

---

### BUG-004: No Exception Handling in manage_positions()
**File**: `trader.py:319-356`
**Issue**: Exception in one position crashes entire loop

**Fix**: Wrap loop body in try/except

**Test**: Inject exception, verify other positions still managed

---

### BUG-005: Missing 'trades' Key in Summary
**File**: `position_manager.py:313-321`
**Issue**: get_daily_summary() doesn't return 'trades' key

**Fix**: Add `'trades': self.trades_today` to return dict

**Test**: Verify summary contains trades list

---

## 9. Implementation Priority

### Phase 1: Critical Stability (1-2 hours)
- [ ] Fix BUG-001: KeyError crash
- [ ] Fix BUG-002: Position desync
- [ ] Fix BUG-004: Exception handling
- [ ] Fix BUG-005: Missing trades key
- [ ] Test: Run paper trading for 1 hour without crash

### Phase 2: Position Sync (1-2 hours)
- [ ] Fix BUG-003: IBKR position sync
- [ ] Implement REQ-ARCH-004: Startup reconciliation
- [ ] Implement REQ-ARCH-005: Periodic reconciliation
- [ ] Test: Kill trader mid-session, restart, verify recovery

### Phase 3: State Persistence (1 hour)
- [ ] Implement REQ-ARCH-002: Position state persistence
- [ ] Implement REQ-ARCH-003: Crash recovery
- [ ] Test: Crash scenarios

### Phase 4: Single Source of Truth (2 hours)
- [ ] Refactor: Remove trader.positions dict
- [ ] Use PM as single source
- [ ] Test: Full day paper trading

### Phase 5: Enhanced Monitoring (1 hour)
- [ ] Implement REQ-POS-004: Position age monitoring
- [ ] Implement REQ-ERR-003/004: Circuit breakers
- [ ] Test: Error injection scenarios

**Total Estimated Time**: 6-8 hours

---

## 10. Acceptance Criteria

Before live trading, system shall demonstrate:

1. ✅ **Stability**: Run 5 consecutive full trading days without crash
2. ✅ **Recovery**: Survive 3 deliberate kill -9 crashes and recover positions
3. ✅ **Accuracy**: Position count/shares match IBKR within 1 second after every trade
4. ✅ **Error Handling**: Inject 10 random exceptions, system continues trading
5. ✅ **EOD Close**: All positions closed by configured time, no orphans
6. ✅ **State Persistence**: State file written after every position change
7. ✅ **Logging**: Zero CRITICAL or ERROR logs during normal operation
8. ✅ **Performance**: < 100ms latency from pivot break to order submission

---

## 11. Non-Functional Requirements

### Performance
- Position monitoring loop: < 100ms per iteration
- Order submission: < 50ms from signal to IBKR
- State file write: < 10ms (non-blocking)

### Reliability
- Uptime target: 99.9% during market hours
- Mean time between failures: > 40 trading hours
- Mean time to recover: < 60 seconds

### Maintainability
- Code coverage: > 80%
- Cyclomatic complexity: < 10 per function
- Function length: < 50 lines
- Module coupling: Low (strategy module independent)

---

## Appendix A: Current vs Required Architecture

### Current (Broken):
```
Trader
├── self.positions (dict)         ❌ Dual tracking
├── self.pm.positions (dict)      ❌ Can desync
├── No IBKR sync                  ❌ Orphans possible
├── No state persistence          ❌ Lost on crash
└── Crashes on exit               ❌ KeyError
```

### Required (Fixed):
```
Trader
├── self.pm (Position Manager)    ✅ Single source
│   ├── positions (dict)          ✅ Authoritative
│   ├── trades_today (list)       ✅ Complete record
│   └── state_file (JSON)         ✅ Persisted
├── IBKR position sync            ✅ On startup + periodic
├── Exception isolation           ✅ Per-position try/except
└── Clean exit                    ✅ All positions closed
```

---

## Appendix B: Critical Code Paths

### Path 1: Position Entry
```
1. check_pivot_break() detects signal
2. enter_long() or enter_short()
3. pm.create_position()            ✅ Creates in PM
4. IBKR order submission
5. State file update              ⚠️ TODO
6. Log trade entry
```

### Path 2: Position Management
```
1. manage_positions() loop
2. For each symbol in pm.get_all_symbols():  ✅ Query PM
3.   try:                          ✅ Exception isolation
4.     Get position from PM        ✅ Single source
5.     Check 5-min rule
6.     Check partial triggers
7.     Update stops
8.   except Exception:             ✅ Don't crash
9.     Log error, continue
```

### Path 3: Position Close
```
1. close_position() called
2. Calculate shares to close
3. IBKR order submission
4. pm.close_position()             ✅ Always called
5. Remove from pm.positions        ✅ PM handles
6. State file update              ⚠️ TODO
7. Log trade result
```

### Path 4: Session Exit
```
1. EOD detected or user interrupt
2. close_all_positions()
3. pm.get_daily_summary()          ✅ Returns ALL keys
4. Save trades to JSON             ✅ summary['trades'] exists
5. Print summary                   ✅ No KeyError
6. Save state file                 ⚠️ TODO
7. Disconnect IBKR
8. Exit with code 0                ✅ Clean exit
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Oct 3, 2025 | Claude | Initial requirements based on bug analysis |
| 2.0 | Oct 3, 2025 | Claude | Added implementation priority, acceptance criteria |

**Next Review**: After Phase 1 fixes implemented

**Status**: DRAFT - Awaiting approval and implementation
