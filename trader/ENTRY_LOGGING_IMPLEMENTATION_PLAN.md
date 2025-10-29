# Entry Decision Logging - Implementation Plan
**Date**: October 25, 2025
**Purpose**: Enable backtest validation by logging ALL entry decisions with complete filter data

## Problem Statement

User needs to validate backtest results by analyzing:
- Why certain entries were **blocked** (filter values at decision time)
- Whether backtest **missed any valid entries**
- Which filters are **most restrictive**
- Filter **parameter effectiveness**

Current logging captures:
- ✅ Entries that were taken (basic trade data)
- ✅ Some filter decisions in DEBUG logs (incomplete)
- ❌ **NO logging for blocked entry attempts**
- ❌ **NO structured filter data for analysis**

## Solution Design

### Architecture

```
backtester.py (main loop)
    ↓
    For each bar:
      ↓
      should_enter_long/short? (pivot check)
      ↓
      check_hybrid_entry (main filter chain)
        ↓
        check_entry_state_machine (state-based logic)
          ↓
          Multiple filter checks (choppy, room-to-run, stochastic, CVD)
          ↓
          DECISION: ENTER or BLOCK
          ↓
      LOG DECISION (← NEW: capture all filter data)
```

### Data to Capture

For EVERY entry attempt (entered + blocked):

1. **Basic Info**:
   - Timestamp, symbol, side, bar index, price, pivot price

2. **Pivot Checks**:
   - Price vs pivot (PASS/FAIL)
   - Attempt count (N/max)
   - Symbol avoid list (PASS/FAIL)
   - Position size check (PASS/FAIL)

3. **Entry Path**:
   - Volume ratio vs threshold
   - Candle size % vs threshold
   - Path chosen (MOMENTUM / PULLBACK / SUSTAINED)

4. **Filter Results** (for specific path):
   - **Choppy Filter**: range, ATR, ratio, threshold, result
   - **Room-to-Run**: entry, target, room%, threshold, result
   - **Stochastic**: %K, %D, min/max, result
   - **CVD**: value, imbalance%, consecutive, threshold, trend, result
   - **Directional Volume**: result, reason

5. **Decision**:
   - ENTERED or BLOCKED
   - Phase/state
   - Final reason

### Implementation Files

1. **NEW: `entry_decision_logger.py`** ✅ CREATED
   - `EntryDecisionLogger` class
   - `capture_filter_data()` helper function
   - JSON output writer
   - Summary statistics

2. **MODIFY: `backtester.py`**
   - Initialize EntryDecisionLogger
   - Log pivot check results
   - Log entry attempt with all filter data
   - Save JSON at end + print summary

3. **MODIFY: `ps60_strategy.py`**
   - Enhanced filter methods to return full data
   - Support for logger parameter

4. **MODIFY: `ps60_entry_state_machine.py`**
   - Log CVD filter data
   - Support for decision logger

## Integration Points

### Point 1: Backtester Initialization (backtester.py line ~115)

```python
from backtest.entry_decision_logger import EntryDecisionLogger

# In __init__():
self.entry_logger = EntryDecisionLogger(self.test_date)
```

### Point 2: Entry Attempt Logging (backtester.py line ~810-875)

**Current code**:
```python
if long_attempts < max_attempts and price > resistance and self.enable_longs:
    should_enter, reason = self.strategy.should_enter_long(stock, price, long_attempts)

    if should_enter:
        confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(...)

        if confirmed:
            # ENTER TRADE
            position = self.enter_long(...)
```

**NEW code**:
```python
if long_attempts < max_attempts and price > resistance and self.enable_longs:
    # STEP 1: Pivot check
    should_enter, pivot_reason = self.strategy.should_enter_long(stock, price, long_attempts)

    # STEP 2: Build pivot check data
    pivot_checks = {
        'price_vs_pivot': 'PASS' if should_enter else 'FAIL',
        'attempt_count': f'{long_attempts}/{max_attempts}',
        'avoid_list': 'FAIL' if stock['symbol'] in self.avoid_symbols else 'PASS',
        'position_size': 'PASS'  # Calculated in should_enter_long
    }

    if should_enter:
        # STEP 3: Entry confirmation with filters
        confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(...)

        # STEP 4: Capture filter data
        from backtest.entry_decision_logger import capture_filter_data

        # Get entry path data
        entry_path_data = entry_state.get('entry_path_data', {})

        # Capture all filter values
        filters = capture_filter_data(
            self.strategy, bars, bar_count-1, 'LONG',
            entry_path_data, target_price=stock.get('target1'),
            symbol=stock['symbol']
        )

        # STEP 5: Log decision
        self.entry_logger.log_entry_attempt(
            timestamp=timestamp,
            symbol=stock['symbol'],
            side='LONG',
            bar_idx=bar_count,
            price=price,
            pivot_data={
                'resistance': resistance,
                'support': support,
                'through_pivot': True
            },
            pivot_checks=pivot_checks,
            entry_path=entry_path_data,
            filters=filters,
            decision='ENTERED' if confirmed else 'BLOCKED',
            phase=entry_state.get('phase', 'unknown'),
            reason=confirm_reason
        )

        if confirmed:
            # ENTER TRADE
            position = self.enter_long(...)
    else:
        # Pivot check failed - log blocked attempt
        self.entry_logger.log_entry_attempt(
            timestamp=timestamp,
            symbol=stock['symbol'],
            side='LONG',
            bar_idx=bar_count,
            price=price,
            pivot_data={'resistance': resistance, 'support': support, 'through_pivot': False},
            pivot_checks=pivot_checks,
            entry_path={},
            filters={},
            decision='BLOCKED',
            phase='pivot_check',
            reason=pivot_reason
        )
```

### Point 3: Entry State Machine Enhancement (ps60_entry_state_machine.py)

Modify `_check_cvd_filter()` to return complete CVD data:

```python
def _check_cvd_filter(...):
    # ... existing logic ...

    cvd_details = {
        'enabled': True,
        'value': cvd_result.cvd_value,
        'imbalance_pct': cvd_result.imbalance_pct,
        'consecutive': consecutive_count,
        'threshold': config.get('imbalance_threshold', 10.0),
        'trend': cvd_result.cvd_trend,
        'result': 'BLOCK' if fails_filter else 'PASS',
        'reason': reason if fails_filter else None
    }

    return fails_filter, reason, cvd_details  # Return details too
```

### Point 4: Save and Print (backtester.py line ~410)

```python
def run(self):
    try:
        # ... existing backtest logic ...
        self.backtest_day()
        self.save_trades_to_json()

        # NEW: Save entry decisions
        decision_file = self.entry_logger.save_to_json(Path(__file__).parent / 'results')
        print(f"\n💾 Saved entry decisions to: {decision_file}")

        # Print summaries
        self.print_results()
        self.entry_logger.print_summary()  # NEW
    finally:
        self.disconnect()
```

## Output Format

**File**: `backtest/results/backtest_entry_decisions_20251021.json`

```json
{
  "backtest_date": "2025-10-21",
  "total_attempts": 87,
  "entered": 6,
  "blocked": 81,
  "blocks_by_filter": {
    "cvd_filter": 32,
    "choppy_filter": 18,
    "room_to_run_filter": 15,
    "pivot_check": 10,
    "stochastic_filter": 6
  },
  "blocks_by_symbol": {
    "NVDA": 12,
    "PLTR": 8,
    "AMD": 6
  },
  "attempts": [
    {
      "timestamp": "2025-10-21T09:47:00-04:00",
      "symbol": "NVDA",
      "side": "LONG",
      "bar_idx": 34,
      "price": 181.05,
      "pivot": {
        "resistance": 185.20,
        "support": 181.73,
        "through_pivot": true
      },
      "pivot_checks": {
        "price_vs_pivot": "PASS",
        "attempt_count": "1/2",
        "avoid_list": "PASS",
        "position_size": "PASS"
      },
      "entry_path": {
        "volume_ratio": 1.45,
        "volume_threshold": 2.0,
        "candle_size_pct": 0.25,
        "candle_threshold_pct": 0.3,
        "path_chosen": "PULLBACK"
      },
      "filters": {
        "choppy": {
          "enabled": true,
          "range_5min": 1.45,
          "atr": 2.10,
          "ratio": 0.69,
          "threshold": 0.5,
          "result": "PASS"
        },
        "room_to_run": {
          "enabled": true,
          "entry": 181.05,
          "target": 185.20,
          "room_pct": 2.29,
          "threshold": 1.5,
          "result": "PASS"
        },
        "stochastic": {
          "enabled": true,
          "k_value": 22.3,
          "d_value": 18.5,
          "min_k": 20,
          "max_k": 50,
          "result": "PASS"
        },
        "cvd": {
          "enabled": true,
          "value": -1250.5,
          "imbalance_pct": -14.2,
          "consecutive": 3,
          "threshold": 10.0,
          "trend": "BEARISH",
          "result": "BLOCK",
          "reason": "BEARISH trend blocking LONG entry"
        }
      },
      "decision": "BLOCKED",
      "phase": "cvd_filter",
      "reason": "BEARISH trend blocking LONG entry"
    }
  ]
}
```

## Validation Use Cases

### 1. Find Missed Valid Entries
```python
# Load decision JSON
with open('backtest_entry_decisions_20251021.json') as f:
    data = json.load(f)

# Find BLOCKED attempts where ALL filters passed
for attempt in data['attempts']:
    if attempt['decision'] == 'BLOCKED':
        filters = attempt['filters']
        all_passed = all(f.get('result') == 'PASS'
                        for f in filters.values()
                        if f.get('enabled'))
        if all_passed:
            print(f"POTENTIAL MISS: {attempt['symbol']} @ {attempt['timestamp']}")
            print(f"  Reason: {attempt['reason']}")
```

### 2. Analyze Filter Effectiveness
```python
# Which filter blocks most entries?
for filter_name, count in data['blocks_by_filter'].items():
    pct = count / data['blocked'] * 100
    print(f"{filter_name}: {count} ({pct:.1f}%)")
```

### 3. Check Invalid Breakouts
```python
# Find ENTERED trades where key filter values look suspicious
for attempt in data['attempts']:
    if attempt['decision'] == 'ENTERED':
        cvd = attempt['filters'].get('cvd', {})
        # Check if CVD trend opposes trade direction
        if attempt['side'] == 'LONG' and cvd.get('trend') == 'BEARISH':
            print(f"POTENTIAL INVALID ENTRY: {attempt['symbol']}")
            print(f"  LONG entry but BEARISH CVD trend!")
```

## Implementation Status

- ✅ **EntryDecisionLogger class created** (entry_decision_logger.py)
- ✅ **capture_filter_data() helper created** (entry_decision_logger.py)
- ⏳ **Backtester integration** (backtester.py) - NEXT STEP
- ⏳ **State machine CVD data** (ps60_entry_state_machine.py) - NEXT STEP
- ⏳ **Testing on Oct 21 backtest** - VALIDATION

## Next Steps

1. Integrate EntryDecisionLogger into backtester.py
2. Enhance state machine to return CVD filter data
3. Run backtest on Oct 21, 2025 to generate decision JSON
4. Validate output format and data completeness
5. Create analysis scripts for validation use cases
6. Document findings

## Expected Benefits

1. **100% Visibility**: Every entry attempt logged (not just trades)
2. **Filter Validation**: Can verify each filter is working correctly
3. **Parameter Tuning**: Analyze which filter thresholds need adjustment
4. **Missed Opportunities**: Identify valid setups that were incorrectly blocked
5. **Invalid Entries**: Identify trades that shouldn't have been taken
6. **Performance Attribution**: Understand which filters save/cost money

## Notes

- **Performance**: Minimal impact - only adds ~50-100 JSON records per backtest day
- **Storage**: ~100KB per backtest day (negligible)
- **Backwards Compatible**: Doesn't change existing trade logging
- **Optional**: Can be disabled via config flag if needed
