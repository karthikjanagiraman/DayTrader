# Unit Tests - PS60 Trading System

## Overview
Comprehensive unit test suite for all PS60 trader components.

## Test Structure

```
unit_tests/
├── README.md                          # This file
├── __init__.py                        # Test package init
├── test_state_manager.py              # State persistence/recovery tests
├── test_position_manager.py           # Position tracking and management
├── test_ps60_strategy.py              # Entry/exit strategy logic
├── test_trader_validation.py          # Startup validation (GAP #6)
├── test_graceful_shutdown.py          # Shutdown handler (GAP #7)
├── test_session_tracking.py           # Session duration (GAP #8)
├── test_entry_filters.py              # Entry confirmation filters
├── test_exit_management.py            # Partial exits, trailing stops
├── test_ibkr_resilience.py            # Connection resilience
├── test_sma_calculator.py             # SMA calculation logic
├── test_momentum_indicators.py        # RSI/MACD indicators
└── run_all_tests.py                   # Test runner

```

## Running Tests

### Run All Tests
```bash
cd /Users/karthik/projects/DayTrader/trader/unit_tests
python3 run_all_tests.py
```

### Run Specific Test File
```bash
python3 -m unittest test_state_manager.py
```

### Run Specific Test Class
```bash
python3 -m unittest test_state_manager.TestStateSaving
```

### Run With Verbose Output
```bash
python3 -m unittest test_state_manager.py -v
```

## Test Coverage Goals

### ✅ Completed
- (None yet - creating initial suite)

### 🔄 In Progress
- State Manager tests
- Position Manager tests
- Trader validation tests

### 📋 Planned
- Strategy logic tests
- Filter tests
- Exit management tests
- IBKR resilience tests

## Test Categories

### 1. State Management Tests
**File**: `test_state_manager.py`
- ✅ Save state to file
- ✅ Load state from file
- ✅ Recover positions from IBKR
- ✅ Reconcile state with IBKR portfolio
- ✅ Handle corrupted state files
- ✅ Backup state file recovery
- ✅ Date validation (ignore old state)

### 2. Position Manager Tests
**File**: `test_position_manager.py`
- ✅ Create position
- ✅ Track partial exits
- ✅ Calculate P&L
- ✅ Track attempt counts
- ✅ Daily summary generation
- ✅ Position size validation

### 3. Trader Validation Tests (GAP #6)
**File**: `test_trader_validation.py`
- ✅ IBKR connection check
- ✅ Scanner file existence
- ✅ Scanner file age (<24 hours)
- ✅ Account size validation (GAP #3)
- ✅ Watchlist validation
- ✅ Market hours validation
- ✅ Open positions check

### 4. Strategy Logic Tests
**File**: `test_ps60_strategy.py`
- ✅ Entry confirmation (momentum/pullback/sustained)
- ✅ Exit management (7-minute rule)
- ✅ Partial profit targets
- ✅ Trailing stop calculation
- ✅ Gap filter logic
- ✅ Room-to-run filter
- ✅ Choppy market filter

### 5. Graceful Shutdown Tests (GAP #7)
**File**: `test_graceful_shutdown.py`
- ✅ SIGINT handler registration
- ✅ SIGTERM handler registration
- ✅ Position closing on shutdown
- ✅ State save on shutdown
- ✅ Shutdown flag detection in loop

### 6. Session Tracking Tests (GAP #8)
**File**: `test_session_tracking.py`
- ✅ Session start time recording
- ✅ Session end time recording
- ✅ Duration calculation (seconds)
- ✅ Duration calculation (minutes)
- ✅ JSON serialization of times

### 7. Entry Filter Tests
**File**: `test_entry_filters.py`
- ✅ Candle close wait
- ✅ Volume surge detection
- ✅ Momentum candle size
- ✅ Sustained break logic
- ✅ Entry position filter (chasing)
- ✅ Choppy market detection

### 8. Exit Management Tests
**File**: `test_exit_management.py`
- ✅ First partial (50% at 1R)
- ✅ Second partial (25% at 2R)
- ✅ Runner management (25%)
- ✅ Breakeven stop move
- ✅ Trailing stop updates
- ✅ EOD close trigger
- ✅ 7-minute rule exit

### 9. IBKR Resilience Tests
**File**: `test_ibkr_resilience.py`
- ✅ Connection health monitoring
- ✅ Reconnection logic
- ✅ Failed connection handling
- ✅ Timeout detection

### 10. SMA Calculator Tests
**File**: `test_sma_calculator.py`
- ✅ SMA5, SMA10, SMA20 calculation
- ✅ Caching mechanism
- ✅ Historical bar fetching
- ✅ Invalid symbol handling

### 11. Momentum Indicator Tests
**File**: `test_momentum_indicators.py`
- ✅ RSI calculation
- ✅ MACD calculation
- ✅ Signal line crossover
- ✅ Timeframe handling

## Dependencies

Tests require:
- Python 3.9+
- unittest (built-in)
- unittest.mock (built-in)
- PyYAML
- pytz

## Test Principles

1. **Isolation**: Each test is independent
2. **Mocking**: Mock external dependencies (IBKR API, file I/O)
3. **Fast**: Tests should run in milliseconds
4. **Comprehensive**: Cover happy path, edge cases, and errors
5. **Readable**: Clear test names and assertion messages

## CI/CD Integration

These tests are designed to run in CI/CD pipelines:
- No external API calls (all mocked)
- No real IBKR connection required
- No file system dependencies (use temp files)
- Deterministic results

## Adding New Tests

1. Create test file: `test_<module_name>.py`
2. Import unittest and module under test
3. Create test class: `class Test<Feature>(unittest.TestCase)`
4. Add `setUp()` for test fixtures
5. Write test methods: `def test_<behavior>(self)`
6. Add to `run_all_tests.py`

## Test Naming Convention

```python
def test_<component>_<scenario>_<expected_result>(self):
    """Test that <component> <expected_result> when <scenario>"""
```

Example:
```python
def test_state_manager_loads_backup_when_primary_corrupted(self):
    """Test that StateManager loads backup file when primary is corrupted"""
```

## Created: October 13, 2025
## Last Updated: October 13, 2025
