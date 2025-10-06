# PS60 Profitable Strategy - Implementation Action Plan
**Date**: October 3, 2025
**Goal**: Implement profitable trading guardrails from research
**Reference**: PS60_PROFITABLE_STRATEGY_REQUIREMENTS.md

---

## Quick Start: Immediate Config Changes (5 minutes)

These changes can be made RIGHT NOW to trader_config.yaml:

```yaml
# trader/config/trader_config.yaml

trading:
  entry:
    min_entry_time: "10:30"   # ✅ CHANGE from "09:45" - wait for first-hour pivot
    max_entry_time: "14:30"   # ✅ CHANGE from "15:00" - stop entries earlier

filters:
  min_score: 75                # ✅ CHANGE from 70 - higher quality setups
  min_risk_reward: 2.0         # ✅ CHANGE from 1.0 - require better R/R
  max_dist_to_pivot: 1.0       # ✅ CHANGE from 2.0 - tighter distance filter

  enable_gap_filter: true      # ✅ CHANGE from false - re-enable gap protection
  max_gap_through_pivot: 2.0   # ✅ Keep as-is
  min_room_to_target: 3.0      # ✅ Keep as-is
```

**Expected Impact**: Reduce trades by ~50%, increase win rate to 55%+

---

## Phase 1: Critical Entry Filters (Next 2-3 hours)

### 1.1 Volume Confirmation Filter
**File**: `trader/strategy/ps60_strategy.py`
**Location**: Add to `should_enter_long()` and `should_enter_short()`

```python
def check_volume_confirmation(self, symbol, current_time):
    """Check if breakout has sufficient volume"""
    # Get last 20 x 1-min bars
    bars = self.get_recent_bars(symbol, count=20)

    if len(bars) < 20:
        return True  # Can't confirm - allow entry

    avg_volume = sum(bar.volume for bar in bars[:-1]) / 19
    current_volume = bars[-1].volume

    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

    if volume_ratio < 1.5:
        return False, f"Low volume on breakout ({volume_ratio:.1f}x avg)"

    return True, f"Volume confirmed ({volume_ratio:.1f}x avg)"
```

**Integration**:
```python
# In should_enter_long() after pivot break check:
volume_ok, volume_reason = self.check_volume_confirmation(symbol, current_time)
if not volume_ok:
    return False, volume_reason
```

### 1.2 ADX Trend Filter
**File**: `trader/strategy/ps60_strategy.py`
**Add**: ADX calculation helper (or use ta-lib)

```python
def check_adx_filter(self, symbol):
    """Check if market is trending (ADX >= 25)"""
    # Calculate 14-period ADX on 60-min bars
    bars_60min = self.get_bars(symbol, period='60min', count=30)

    if len(bars_60min) < 14:
        return True  # Can't calculate - allow entry

    adx = calculate_adx(bars_60min, period=14)

    if adx < 25:
        return False, f"Choppy market (ADX={adx:.1f} < 25)"

    return True, f"Trending market (ADX={adx:.1f})"
```

**Note**: May need to add pandas_ta or ta-lib for ADX calculation

### 1.3 Consecutive Closes Confirmation
**File**: `trader/strategy/ps60_strategy.py`

```python
def check_consecutive_closes(self, symbol, pivot, side, volume_ratio):
    """Require 2 consecutive 1-min closes beyond pivot"""
    bars = self.get_recent_bars(symbol, count=2)

    if len(bars) < 2:
        return False, "Waiting for price confirmation"

    if side == 'LONG':
        closes_beyond = sum(1 for bar in bars if bar.close > pivot)
    else:
        closes_beyond = sum(1 for bar in bars if bar.close < pivot)

    # Exception: 3x volume allows 1 close
    if volume_ratio >= 3.0 and closes_beyond >= 1:
        return True, "Strong volume override"

    if closes_beyond < 2:
        return False, f"Waiting for confirmation ({closes_beyond}/2 closes)"

    return True, "Consecutive closes confirmed"
```

---

## Phase 2: Fix 5-Minute Rule (Next 1 hour)

### 2.1 Correct 5-Minute Rule Logic
**File**: `trader/strategy/ps60_strategy.py`
**Function**: `check_five_minute_rule()`
**Current Line**: 227-282

**REPLACE** with correct logic:

```python
def check_five_minute_rule(self, position, current_price, current_time):
    """
    Check if 5-7 minute rule should trigger exit

    CORRECT LOGIC: Exit ONLY if stuck at pivot (reload seller/buyer blocking)
    NOT: Exit all slow trades after 7 minutes

    Args:
        position: Position dict with entry_time, entry_price, side
        current_price: Current price
        current_time: Current datetime

    Returns:
        (bool, reason) - Should exit, and reason
    """
    if not self.five_minute_rule:
        return False, None

    # CRITICAL: Only apply 5-minute rule if NO partials taken yet
    # If we've taken partials (remaining < 1.0), let the runner work
    if position.get('remaining', 1.0) < 1.0:
        return False, None

    # Calculate time in trade - handle timezone awareness
    entry_time = position['entry_time']

    # Convert both to timezone-aware UTC if either is naive
    import pytz
    if current_time.tzinfo is None:
        current_time = pytz.UTC.localize(current_time)
    else:
        current_time = current_time.astimezone(pytz.UTC)

    if entry_time.tzinfo is None:
        entry_time = pytz.UTC.localize(entry_time)
    else:
        entry_time = entry_time.astimezone(pytz.UTC)

    time_in_trade = (current_time - entry_time).total_seconds() / 60

    # Only check at threshold (default 7 minutes)
    if time_in_trade < self.five_minute_threshold:
        return False, None

    entry_price = position['entry_price']

    # ✅ NEW LOGIC: Check if STUCK AT PIVOT (within 0.3% of entry)
    distance_from_entry_pct = abs(current_price - entry_price) / entry_price * 100

    # Exit ONLY if stuck near entry (< 0.3% movement) after 7 min
    if distance_from_entry_pct < 0.3:
        return True, "5MIN_RULE - Reload blocking (stuck at entry)"

    # Has moved favorably - let it work
    # (Old logic incorrectly exited here if gain < $0.10)
    return False, None
```

**Key Change**:
- OLD: `if gain < 0.10: exit`
- NEW: `if distance_from_entry < 0.3%: exit` (only if STUCK)

---

## Phase 3: Enhanced Exit Logic (Next 2 hours)

### 3.1 Trailing Stop for Runner
**File**: `trader/strategy/position_manager.py` or `trader/trader.py`
**Add**: Trailing stop update method

```python
def update_trailing_stop(self, symbol, current_price):
    """Update trailing stop for runner position"""
    if symbol not in self.positions:
        return

    position = self.positions[symbol]

    # Only trail on runner (after partials taken)
    if position['remaining'] >= 0.5:
        return  # Still have too much position

    if position['side'] == 'LONG':
        # Update highest price seen
        if current_price > position.get('highest_price', position['entry_price']):
            position['highest_price'] = current_price

        # Trail stop at highest price - 1%
        new_stop = position['highest_price'] * 0.99

        # Only move stop UP (never down), and not below breakeven
        if new_stop > position['stop'] and new_stop >= position['entry_price']:
            position['stop'] = new_stop
            return True  # Stop was updated

    else:  # SHORT
        # Update lowest price seen
        if current_price < position.get('lowest_price', position['entry_price']):
            position['lowest_price'] = current_price

        # Trail stop at lowest price + 1%
        new_stop = position['lowest_price'] * 1.01

        # Only move stop DOWN (never up), and not above breakeven
        if new_stop < position['stop'] and new_stop <= position['entry_price']:
            position['stop'] = new_stop
            return True  # Stop was updated

    return False
```

**Integration** in `trader.py` main loop:
```python
# In manage_positions(), after checking for exits:
if self.pm.update_trailing_stop(symbol, current_price):
    self.logger.info(f"  📈 Trailing stop updated: ${position['stop']:.2f}")
```

### 3.2 Percentage-Based First Partial
**File**: `trader/strategy/ps60_strategy.py`
**Function**: `should_take_partial()`

```python
# In should_take_partial(), update first partial logic:

# First partial (50%) - whichever comes FIRST
if remaining == 1.0:
    gain_dollars = current_price - entry_price if side == 'LONG' else entry_price - current_price
    gain_pct = (gain_dollars / entry_price) * 100

    # Take partial if EITHER $0.25 gain OR 1% gain (whichever first)
    if gain_dollars >= self.partial_1_gain or gain_pct >= 1.0:
        reason = f'FIRST_MOVE (${gain_dollars:.2f} / {gain_pct:.1f}%)'
        return True, self.partial_1_pct, reason
```

---

## Phase 4: Scanner Enhancements (Next 3-4 hours)

### 4.1 Add Volume Ratio to Scanner
**File**: `stockscanner/scanner.py`

Add to stock analysis:
```python
# Calculate volume ratio (current vs 20-day average)
volume_20d_avg = df['volume'].tail(20).mean()
current_volume = df['volume'].iloc[-1]
volume_ratio = current_volume / volume_20d_avg if volume_20d_avg > 0 else 0

stock_data['volume_ratio'] = round(volume_ratio, 2)
```

### 4.2 Add Pivot Test Count
**File**: `stockscanner/scanner.py`

Count how many times pivot level was tested:
```python
def count_pivot_tests(df, pivot_price, tolerance=0.005):
    """Count how many times price tested pivot level"""
    tests = 0
    for i in range(len(df)):
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]

        # Check if candle touched pivot (within tolerance)
        if low <= pivot_price * (1 + tolerance) and high >= pivot_price * (1 - tolerance):
            tests += 1

    return tests

# Add to analysis:
pivot_tests_resistance = count_pivot_tests(df, resistance)
pivot_tests_support = count_pivot_tests(df, support)

stock_data['resistance_tests'] = pivot_tests_resistance
stock_data['support_tests'] = pivot_tests_support
```

### 4.3 Add Sector Classification
**File**: `stockscanner/scanner.py`

```python
# Simple sector mapping (can enhance with yfinance later)
SECTOR_MAP = {
    'AAPL': 'Tech', 'MSFT': 'Tech', 'GOOGL': 'Tech', 'META': 'Tech',
    'TSLA': 'Auto', 'F': 'Auto', 'GM': 'Auto',
    'JPM': 'Finance', 'BAC': 'Finance', 'GS': 'Finance',
    # ... expand as needed
}

stock_data['sector'] = SECTOR_MAP.get(symbol, 'Other')
```

---

## Phase 5: Testing & Validation (Next 4 hours)

### 5.1 Backtest with New Settings
**File**: Create `test_profitable_settings.py`

```python
#!/usr/bin/env python3
"""Test new profitable strategy settings on September 2025"""

import sys
sys.path.insert(0, '..')

from backtest.backtester import PS60Backtester
from datetime import date

# Test new settings
config_overrides = {
    'trading': {
        'entry': {
            'min_entry_time': '10:30',  # NEW
            'max_entry_time': '14:30',  # NEW
        }
    },
    'filters': {
        'min_score': 75,              # NEW
        'min_risk_reward': 2.0,       # NEW
        'max_dist_to_pivot': 1.0,     # NEW
        'enable_gap_filter': True,    # NEW
    }
}

backtester = PS60Backtester(
    start_date=date(2025, 9, 1),
    end_date=date(2025, 9, 30),
    account_size=100000,
    config_overrides=config_overrides
)

backtester.run()
backtester.print_results()
```

**Run**:
```bash
cd trader
python3 test_profitable_settings.py
```

**Success Criteria**:
- Win Rate ≥ 55% (currently 39.9%)
- Monthly P&L ≥ $15,000 (currently $8,895)
- Profit Factor ≥ 2.0
- Fewer trades (80-100 vs 183)
- Higher avg/trade ($150+ vs $48)

### 5.2 Compare Results
Create comparison report:

| Metric | Old Settings | New Settings | Improvement |
|--------|--------------|--------------|-------------|
| Trades | 183 | ~90 | -51% |
| Win Rate | 39.9% | 55%+ | +38% |
| P&L | $8,895 | $15,000+ | +69% |
| Avg/Trade | $48.60 | $167+ | +244% |
| Profit Factor | ~1.4 | 2.0+ | +43% |

---

## Phase 6: Paper Trading Validation (2 weeks)

### 6.1 Deploy to Paper Trading
After backtest validation:

```bash
# Update config
vim trader/config/trader_config.yaml
# (Apply all changes from Quick Start section)

# Run paper trading
python3 trader.py
```

### 6.2 Daily Monitoring Checklist
- [ ] Win rate ≥ 55%
- [ ] Daily P&L positive (≥70% of days)
- [ ] Average winner > $200
- [ ] No system crashes
- [ ] All filters working correctly
- [ ] Execution matches backtest (±20%)

### 6.3 Weekly Review
- [ ] Compare to backtest expectations
- [ ] Review skipped trades (filter effectiveness)
- [ ] Analyze losing trades (pattern recognition)
- [ ] Check compliance with all requirements
- [ ] Document any edge cases or issues

---

## Critical Success Metrics

### Must Achieve in Backtest
✅ Win Rate ≥ 55%
✅ Profit Factor ≥ 2.0
✅ Monthly P&L ≥ $15,000 (15% return)
✅ Avg Winner ≥ $200
✅ Max Drawdown < 5%

### Must Achieve in Paper Trading
✅ Daily P&L positive ≥70% of days
✅ Performance within ±20% of backtest
✅ No system crashes or critical errors
✅ All filters executing correctly
✅ 100% compliance with entry/exit rules

### Ready for Live Trading When
✅ 2 weeks successful paper trading
✅ All backtest metrics met
✅ User confidence in system
✅ Risk management proven
✅ Edge cases documented

---

## Next Steps

### Immediate (Today)
1. ✅ Update trader_config.yaml with Quick Start changes
2. ⏳ Run backtest with new settings
3. ⏳ Compare results vs old settings

### This Week
4. ⏳ Implement Phase 1 filters (volume, ADX, consecutive closes)
5. ⏳ Fix 5-minute rule logic
6. ⏳ Add trailing stop for runner
7. ⏳ Re-run backtest with all enhancements

### Next Week
8. ⏳ Enhance scanner (pivot tests, sectors, volume ratios)
9. ⏳ Begin 2-week paper trading validation
10. ⏳ Daily monitoring and adjustment

### Week 3-4
11. ⏳ Continue paper trading validation
12. ⏳ Final tuning based on live market behavior
13. ⏳ Document lessons learned
14. ⏳ Prepare for live trading (if validated)

---

## Risk Warnings

⚠️ **Do NOT skip the testing phases** - Each phase validates the previous
⚠️ **Do NOT go live without 2+ weeks paper trading** - Need real market validation
⚠️ **Do NOT trade with real money if any metrics are off** - Discipline required
⚠️ **Do NOT modify rules mid-testing** - Let the system prove itself first

---

## Support Documentation

- **Requirements**: PS60_PROFITABLE_STRATEGY_REQUIREMENTS.md
- **Architecture**: TRADER_REQUIREMENTS_SPEC.md
- **PS60 Theory**: PS60ProcessComprehensiveDayTradingGuide.md
- **Bug Analysis**: trader/analysis/PS60_5min_rule_clarification.md
- **Backtest Results**: trader/backtest/monthly_results_production/

---

**Remember**: Profitable trading = Discipline + Patience + Following ALL Rules

Quality setups that meet ALL criteria > Quantity of "good enough" setups
