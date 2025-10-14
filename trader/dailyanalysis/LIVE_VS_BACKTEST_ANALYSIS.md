# Live Trader vs Backtest: Critical Differences

**Date**: October 6, 2025
**Purpose**: Identify potential issues with tick-by-tick data vs 5-second bars

---

## Key Differences

### 1. Data Granularity

| Aspect | Backtest | Live Trader | Risk |
|--------|----------|-------------|------|
| **Data Type** | 5-second bars | Tick-by-tick | ⚠️ HIGH |
| **Update Frequency** | Every 5 seconds | Every 100ms+ | ⚠️ MEDIUM |
| **Price Points** | OHLC bars | Last/Bid/Ask | ⚠️ MEDIUM |
| **Candle Close** | Known at bar end | Must calculate | ⚠️ HIGH |

### 2. Confirmation Logic Issues

#### CRITICAL: 1-Minute Candle Close Requirement

**Backtest Logic**:
```python
# In backtest: Wait for 1-minute bar to close
# We have discrete 5-second bars, check if 60 seconds elapsed
if (current_bar_time - breakout_bar_time) >= 60 seconds:
    # Candle closed, check for entry
```

**Live Trader Reality**:
```python
# Tick-by-tick data - NO DISCRETE BARS!
# Need to track when 1-minute window completes

# PROBLEM: How do we know when a 1-minute candle closes?
# - Backtest: Check bar timestamps
# - Live: Must track elapsed time since pivot break
```

**RISK**: 🔴 **CRITICAL** - May enter immediately on pivot break instead of waiting for 1-minute candle close

#### CRITICAL: Pullback/Retest Pattern Detection

**Backtest Logic**:
```python
# Check last 24 bars (2 minutes at 5-second resolution)
# Look for pullback pattern in discrete bars
for bar in last_24_bars:
    if bar.low < pivot * (1 - tolerance):
        # Found pullback
```

**Live Trader Reality**:
```python
# Ticks arrive continuously - NO BARS
# How do we detect pullback pattern?
# - Need to track min/max prices over time window
# - Need to track volume over time window
# - Need to recalculate on EVERY tick?
```

**RISK**: 🔴 **CRITICAL** - Pullback pattern may not be detected correctly

#### CRITICAL: Sustained Break Logic

**Backtest Logic**:
```python
# Check if price held above pivot for 2 minutes (24 bars)
# Count bars where price stayed above pivot
sustained_bars = 0
for bar in last_24_bars:
    if bar.low >= pivot * (1 - tolerance):
        sustained_bars += 1

if sustained_bars >= 24:  # All 24 bars
    # Sustained break confirmed
```

**Live Trader Reality**:
```python
# Ticks arrive irregularly
# How long has price been above pivot?
# - Track time since first break
# - Check if price EVER dipped below pivot - tolerance
# - Volume calculation over time window?
```

**RISK**: 🔴 **CRITICAL** - Sustained break may trigger too early or too late

### 3. Choppy Filter Issues

**Backtest Logic**:
```python
# Calculate 5-minute range from last 60 bars (5 seconds each)
bars_5min = bars[-60:]
range_5min = max(b.high for b in bars_5min) - min(b.low for b in bars_5min)

# Compare to ATR (calculated from bars)
atr = calculate_atr(bars[-20:])

if range_5min < atr * 0.5:
    # Choppy - block entry
```

**Live Trader Reality**:
```python
# Need to track high/low over last 5 minutes
# Ticks don't have OHLC - just last price
# How do we calculate 5-minute range?
# - Track max/min of last prices over 5 minutes?
# - Need time-windowed min/max tracking
```

**RISK**: 🟡 **MEDIUM** - Choppy filter may not work correctly without bars

### 4. Volume Calculation Issues

**Backtest Logic**:
```python
# 1-minute candle volume = sum of 12 five-second bars
candle_volume = sum(bar.volume for bar in last_12_bars)

# Average volume = average of recent candles
avg_volume = mean([sum(bars[i:i+12]) for i in range(...)])

if candle_volume >= avg_volume * 1.3:
    # Momentum confirmed
```

**Live Trader Reality**:
```python
# Tick data shows CUMULATIVE volume for the day
# ticker.volume = total volume since market open

# How do we calculate 1-minute candle volume?
# - Track volume at start of 1-minute window
# - Subtract from current volume
# - But volume only updates when trades occur!
```

**RISK**: 🟡 **MEDIUM** - Volume calculations may be inaccurate

### 5. ATR Calculation Issues

**Backtest Logic**:
```python
# ATR calculated from 20 bars (100 seconds)
atr_values = []
for bar in bars[-20:]:
    tr = max(bar.high - bar.low,
             abs(bar.high - prev_close),
             abs(bar.low - prev_close))
    atr_values.append(tr)

atr = mean(atr_values)
```

**Live Trader Reality**:
```python
# Ticks don't have high/low
# Where do we get ATR from?
# - IBKR may provide it as a calculated field
# - Or we need to calculate from historical bars
# - Can't calculate from ticks alone!
```

**RISK**: 🟡 **MEDIUM** - ATR may not be available or accurate

---

## Critical Issues Identified

### Issue #1: Strategy Module Expects Bars, Live Trader Has Ticks

**Location**: `strategy/ps60_strategy.py` - `check_hybrid_entry()`

**Problem**:
```python
def check_hybrid_entry(self, bars, current_idx, pivot_price, side='LONG', target_price=None):
    """
    Check hybrid entry confirmation

    Parameters:
    - bars: List of 5-second bars  # ⚠️ LIVE TRADER DOESN'T HAVE BARS!
    - current_idx: Current bar index  # ⚠️ NO BAR INDEX IN LIVE!
    """
```

**Impact**: 🔴 **CRITICAL** - Live trader cannot call `check_hybrid_entry()` directly

**Solution Required**: Need adapter layer to convert tick data to bar-like structure

### Issue #2: Live Trader Calls `should_enter_long/short()` But Needs Bar Data

**Location**: `trader/trader.py` - `check_pivot_break()`

**Current Code**:
```python
should_long, reason = self.strategy.should_enter_long(
    stock_data, current_price, long_attempts
)
```

**Problem**: `should_enter_long()` internally calls `check_hybrid_entry()` which expects bars!

**Impact**: 🔴 **CRITICAL** - Strategy checks will fail or produce incorrect results

### Issue #3: No Candle Close Tracking

**Location**: Live trader has no mechanism to track 1-minute candle boundaries

**Required Tracking**:
- Time when pivot was first broken
- High/low/volume over the 1-minute window
- Whether 1-minute has elapsed

**Impact**: 🔴 **CRITICAL** - May enter immediately without waiting for candle close

### Issue #4: No Pullback Pattern Tracking

**Location**: Live trader has no buffer to store recent price/volume data

**Required Tracking**:
- Price history over last 2 minutes
- Volume history over last 2 minutes
- Min/max prices in the window

**Impact**: 🔴 **CRITICAL** - Pullback/retest pattern cannot be detected

### Issue #5: No Sustained Break Tracking

**Location**: Live trader has no time-windowed tracking

**Required Tracking**:
- Time since first pivot break
- Minimum price seen since break
- Whether price stayed above pivot - tolerance

**Impact**: 🔴 **CRITICAL** - Sustained break cannot be detected

---

## Recommended Solutions

### Solution #1: Add Bar Buffer to Live Trader

Create a bar buffer that converts tick data into 5-second bars:

```python
class BarBuffer:
    """Convert tick data into 5-second bars for strategy module"""

    def __init__(self, symbol, bar_size=5):
        self.symbol = symbol
        self.bar_size = bar_size  # seconds
        self.current_bar = None
        self.bars = []  # Last 120 bars (10 minutes)

    def update(self, tick_time, price, volume):
        """Update with new tick"""
        # Round time to bar boundary
        bar_time = self.round_to_bar(tick_time)

        # Start new bar if needed
        if self.current_bar is None or self.current_bar['time'] != bar_time:
            if self.current_bar:
                self.bars.append(self.current_bar)
                if len(self.bars) > 120:
                    self.bars.pop(0)

            self.current_bar = {
                'time': bar_time,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume
            }
        else:
            # Update current bar
            self.current_bar['high'] = max(self.current_bar['high'], price)
            self.current_bar['low'] = min(self.current_bar['low'], price)
            self.current_bar['close'] = price
            self.current_bar['volume'] = volume  # IBKR volume is cumulative

    def get_bars(self):
        """Get completed bars + current bar"""
        all_bars = self.bars.copy()
        if self.current_bar:
            all_bars.append(self.current_bar)
        return all_bars
```

### Solution #2: Add Confirmation State Tracking

Track confirmation state per symbol:

```python
class ConfirmationTracker:
    """Track confirmation state for each symbol"""

    def __init__(self):
        self.states = {}  # symbol -> state dict

    def track_pivot_break(self, symbol, break_time, pivot_price, side):
        """Record when pivot was broken"""
        if symbol not in self.states:
            self.states[symbol] = {}

        self.states[symbol] = {
            'break_time': break_time,
            'pivot_price': pivot_price,
            'side': side,
            'candle_close_pending': True,
            'high_since_break': pivot_price,
            'low_since_break': pivot_price,
            'volume_at_break': None,
            'pullback_detected': False,
            'sustained_confirmed': False
        }

    def update_price(self, symbol, current_time, price, volume):
        """Update with current price"""
        if symbol not in self.states:
            return

        state = self.states[symbol]

        # Update high/low since break
        state['high_since_break'] = max(state['high_since_break'], price)
        state['low_since_break'] = min(state['low_since_break'], price)

        # Check if 1-minute candle closed
        elapsed = (current_time - state['break_time']).total_seconds()
        if elapsed >= 60 and state['candle_close_pending']:
            state['candle_close_pending'] = False
            state['candle_closed_at'] = current_time
            state['candle_high'] = state['high_since_break']
            state['candle_low'] = state['low_since_break']

        # Check for pullback pattern
        if state['side'] == 'LONG':
            pullback_threshold = state['pivot_price'] * (1 - 0.003)
            if state['low_since_break'] < pullback_threshold:
                state['pullback_detected'] = True

        # Check for sustained break
        if elapsed >= 120:  # 2 minutes
            if state['side'] == 'LONG':
                sustained_threshold = state['pivot_price'] * (1 - 0.003)
                if state['low_since_break'] >= sustained_threshold:
                    state['sustained_confirmed'] = True
```

### Solution #3: Integrate Bar Buffer with Strategy Module

Modify live trader to use bar buffer:

```python
class PS60Trader:
    def __init__(self, config_path='config/trader_config.yaml'):
        # ... existing code ...

        # Add bar buffers for each symbol
        self.bar_buffers = {}  # symbol -> BarBuffer

        # Add confirmation tracking
        self.confirmation_tracker = ConfirmationTracker()

    def subscribe_market_data(self):
        """Subscribe to real-time market data for watchlist"""
        for stock_data in self.watchlist:
            symbol = stock_data['symbol']
            # ... existing code ...

            # Create bar buffer for symbol
            self.bar_buffers[symbol] = BarBuffer(symbol, bar_size=5)

    def check_pivot_break(self, stock_data, current_price):
        """Check with bar data from buffer"""
        symbol = stock_data['symbol']

        # Get bars from buffer
        bars = self.bar_buffers[symbol].get_bars()

        # Now we have bars! Can call strategy module
        if len(bars) < 20:
            return None, None  # Not enough data yet

        # Convert to format strategy expects
        # Call strategy with bars...
```

---

## Test Scenarios Required

### Scenario 1: Candle Close Confirmation
- [ ] Pivot breaks at 10:05:00
- [ ] Price stays above pivot
- [ ] Wait for 1-minute candle to close (10:06:00)
- [ ] Enter ONLY after candle close
- [ ] Test: Verify no entry before 10:06:00

### Scenario 2: Pullback Pattern
- [ ] Pivot breaks at 10:05:00
- [ ] Price pulls back below pivot at 10:05:30
- [ ] Price re-breaks above pivot at 10:05:45
- [ ] Verify pullback pattern detected
- [ ] Test: Entry occurs on re-break with volume

### Scenario 3: Sustained Break
- [ ] Pivot breaks at 10:05:00
- [ ] Price stays above pivot for 2 minutes
- [ ] Small pullbacks (<0.3%) are OK
- [ ] Verify sustained break confirmed at 10:07:00
- [ ] Test: Entry occurs after 2 minutes

### Scenario 4: Choppy Filter
- [ ] Price oscillates ±0.2% around pivot
- [ ] 5-minute range is only 0.4%
- [ ] ATR is 1.2%
- [ ] Range < 0.5× ATR = choppy
- [ ] Test: Entry blocked by choppy filter

### Scenario 5: Room-to-Run Filter
- [ ] Pivot breaks at 10:05:00
- [ ] Wait for confirmation (pullback pattern)
- [ ] By confirmation time, price is at target-1%
- [ ] Only 0.8% room to target
- [ ] Test: Entry blocked by room-to-run filter

### Scenario 6: Multiple Ticks Per Second
- [ ] Receive 10+ ticks per second during volatile period
- [ ] Verify bar buffer aggregates correctly
- [ ] Verify no duplicate entries
- [ ] Test: Only one entry per confirmed signal

### Scenario 7: Gap in Tick Data
- [ ] No ticks for 30 seconds
- [ ] Then ticks resume
- [ ] Verify bar buffer handles gap
- [ ] Test: Confirmation logic still works

### Scenario 8: Volume Spike Detection
- [ ] Volume increases 3x in one bar
- [ ] Verify detected as momentum
- [ ] Test: Immediate entry (no pullback needed)

### Scenario 9: Whipsaw Protection
- [ ] Price breaks pivot by $0.01
- [ ] Immediately falls back below
- [ ] Repeats 5 times in 30 seconds
- [ ] Test: Max 2 attempts enforced

### Scenario 10: EOD Close
- [ ] Position open at 3:54:59 PM ET
- [ ] Verify close triggered at 3:55:00 PM ET
- [ ] Test: Timezone handling correct

---

## Critical Code Review Required

### File: trader/trader.py

**Lines to Review**:
1. Lines 248-314: `check_pivot_break()` - Does it handle tick data?
2. Lines 455-517: `manage_positions()` - Relies on tick price updates
3. Lines 656-720: Main loop - Updates every 0.1 seconds

**Issues**:
- ❌ No bar buffer implementation
- ❌ No confirmation state tracking
- ❌ Calls strategy methods expecting bars
- ❌ No time-windowed calculations

### File: strategy/ps60_strategy.py

**Lines to Review**:
1. Lines 835-1048: `check_hybrid_entry()` - EXPECTS BARS
2. Lines 1071-1107: `should_enter_long()` - Calls check_hybrid_entry()
3. Lines 1109-1145: `should_enter_short()` - Calls check_hybrid_entry()

**Issues**:
- ❌ Entire confirmation system designed for bar data
- ❌ No adapter for tick data
- ❌ Live trader cannot use this directly!

---

## Immediate Actions Required

1. 🔴 **STOP** - Live trader CANNOT run as-is with tick data
2. 🔴 **Implement** BarBuffer class to convert ticks to bars
3. 🔴 **Implement** ConfirmationTracker to track state
4. 🔴 **Test** with simulated tick data before live use
5. 🔴 **Verify** all confirmation logic works with tick-to-bar conversion

---

## Risk Assessment

| Component | Risk Level | Can Run Live? |
|-----------|------------|---------------|
| Entry Logic | 🔴 CRITICAL | ❌ NO |
| Confirmation System | 🔴 CRITICAL | ❌ NO |
| Choppy Filter | 🟡 MEDIUM | ⚠️ UNCERTAIN |
| Room-to-Run Filter | 🟢 LOW | ✅ YES |
| 8-Minute Rule | 🟢 LOW | ✅ YES |
| EOD Close | 🟢 LOW | ✅ YES |
| **OVERALL** | 🔴 **CRITICAL** | ❌ **NOT READY** |

---

**RECOMMENDATION**: Do NOT run live trader until bar buffer and confirmation tracking are implemented and tested.

**Last Updated**: October 6, 2025
