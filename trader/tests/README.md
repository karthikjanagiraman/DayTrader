# Trader Tests

This directory contains unit tests for the PS60 trading strategy implementation.

## Test Files

### `test_oct4_filters.py`
Tests for the October 4, 2025 entry filter fixes:

1. **TestRelaxedMomentumCriteria** - Tests for Fix #1
   - Verifies relaxed momentum thresholds (1.3x volume, 0.8% candle)
   - Tests that more breakouts qualify as momentum
   - Tests that weak breakouts still wait for pullback

2. **TestEntryPositionFilter** - Tests for Fix #2
   - Verifies entry position filter is enabled
   - Tests that chasing LONGs are rejected (>70% of range)
   - Tests that chasing SHORTs are rejected (<30% of range)
   - Tests that good entry positions are accepted
   - Tests boundary cases (exactly 70%)

3. **TestChoppyFilter** - Tests for Fix #4
   - Verifies choppy filter is enabled
   - Tests that consolidating markets are rejected (range <0.5× ATR)
   - Tests that trending markets are accepted
   - Tests boundary cases (exactly 0.5× ATR)

4. **TestIntegratedFilters** - Integration tests
   - Tests that all filters work together
   - Tests that bad setups are blocked by appropriate filter
   - Tests that clean setups pass all filters

## Running Tests

### Run All Tests
```bash
cd /Users/karthik/projects/DayTrader/trader/tests
python3 test_oct4_filters.py
```

### Run Specific Test Class
```python
python3 -m unittest test_oct4_filters.TestEntryPositionFilter
```

### Run Specific Test Method
```python
python3 -m unittest test_oct4_filters.TestEntryPositionFilter.test_chasing_long_rejected
```

### Run with Verbose Output
```bash
python3 test_oct4_filters.py -v
```

## Expected Output

```
test_config_loaded_correctly (__main__.TestRelaxedMomentumCriteria) ... ok
test_momentum_qualification_with_new_criteria (__main__.TestRelaxedMomentumCriteria) ... ok
test_weak_breakout_still_waits_for_pullback (__main__.TestRelaxedMomentumCriteria) ... ok
test_boundary_case_70_percent (__main__.TestEntryPositionFilter) ... ok
test_chasing_long_rejected (__main__.TestEntryPositionFilter) ... ok
test_chasing_short_rejected (__main__.TestEntryPositionFilter) ... ok
test_filter_enabled (__main__.TestEntryPositionFilter) ... ok
test_good_long_entry_accepted (__main__.TestEntryPositionFilter) ... ok
test_boundary_case_half_atr (__main__.TestChoppyFilter) ... ok
test_choppy_market_rejected (__main__.TestChoppyFilter) ... ok
test_filter_enabled (__main__.TestChoppyFilter) ... ok
test_trending_market_accepted (__main__.TestChoppyFilter) ... ok
test_all_filters_applied_to_momentum_entry (__main__.TestIntegratedFilters) ... ok
test_clean_entry_passes_all_filters (__main__.TestIntegratedFilters) ... ok

----------------------------------------------------------------------
Ran 14 tests in 0.074s

OK

======================================================================
TEST SUMMARY
======================================================================
Tests Run: 14
Successes: 14
Failures: 0
Errors: 0

✅ ALL TESTS PASSED!
```

## Test Coverage

These tests verify:
- ✅ Configuration values are loaded correctly
- ✅ Entry position filter rejects chasing entries
- ✅ Entry position filter accepts good entries
- ✅ Choppy filter rejects consolidation
- ✅ Choppy filter accepts trending markets
- ✅ Momentum criteria allow realistic breakouts
- ✅ All filters integrate correctly in hybrid entry logic
- ✅ Boundary cases are handled properly

## Adding New Tests

To add tests for new features:

1. Create a new test class inheriting from `unittest.TestCase`
2. Add `setUp()` method to load config and create strategy
3. Write test methods starting with `test_`
4. Use `self.assert*()` methods for validation
5. Add test class to `run_tests()` function

Example:
```python
class TestNewFeature(unittest.TestCase):
    def setUp(self):
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'trader_config.yaml')
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.strategy = PS60Strategy(self.config)

    def test_feature_works(self):
        # Test logic here
        self.assertTrue(condition, "Error message")
```

## Dependencies

Tests require:
- Python 3.9+
- PyYAML (for config loading)
- unittest (built-in)

No external test frameworks needed.
