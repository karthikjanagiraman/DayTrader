# Candle Handling: Live Trading vs Backtesting
## October 28, 2025

## Executive Summary

The system handles bar/candle data **differently** between live trading and backtesting, using a **configurable bar resolution** approach.

**Key Difference**:
- **Live Trading**: Uses **5-second bars** (aggregated from ticks)
- **Backtesting**: Uses **1-minute bars** (from IBKR historical data)

**Why This Works**: All candle calculations use `strategy.bar_size_seconds` to dynamically calculate `bars_per_candle`, making the logic **resolution-agnostic**.

---

## Architecture Overview

### Core Design Pattern

```python
# Strategy initialization (configurable bar resolution)
class PS60Strategy:
    def __init__(self, config, ib_connection=None, bar_size_seconds=5):
        self.bar_size_seconds = bar_size_seconds  # 5 for live, 60 for backtest
        self.candle_timeframe_seconds = 60  # Always 1-minute decisions

        # Calculate bars per candle DYNAMICALLY
        self.bars_per_candle = self.candle_timeframe_seconds // self.bar_size_seconds
        # Live: 60 // 5 = 12 bars per candle
        # Backtest: 60 // 60 = 1 bar per candle
```

**Result**: Same strategy code works for both 5-second and 1-minute bars!

---

## Mode #1: Live Trading (5-Second Bars)

### Data Flow

```
Real-time Ticks (IBKR)
    ↓
BarBuffer (aggregates ticks → 5-second bars)
    ↓
bars[] array (last 240 bars = 20 minutes)
    ↓
Strategy (checks every 12 bars = 1-minute candle)
    ↓
Entry Decision
```

### Initialization

**File**: `trader/trader.py` (line 311)
```python
# Live trader does NOT pass bar_size_seconds
self.strategy = PS60Strategy(self.config)
# Defaults to bar_size_seconds=5 (from ps60_strategy.py line 34)
```

**Default Parameter** (`trader/strategy/ps60_strategy.py` line 34):
```python
def __init__(self, config, ib_connection=None, bar_size_seconds=5):
    # ⬆️ Defaults to 5-second bars for live trading
```

### Bar Buffer

**File**: `trader/trader.py` (lines 321-322)
```python
# Bar buffers for tick-to-bar conversion
self.bar_buffers = {}  # symbol -> BarBuffer
```

**Creation** (when subscribing to market data):
```python
self.bar_buffers[symbol] = BarBuffer(symbol, bar_size_seconds=5)
```

**BarBuffer Purpose**:
1. Receives real-time ticks from IBKR
2. Aggregates ticks into 5-second OHLCV bars
3. Stores last 240 bars (20 minutes) in rolling buffer
4. Provides `total_bar_count` (absolute bar index: 0, 1, 2, ... ∞)

### Candle Boundary Detection

**Calculation** (`ps60_entry_state_machine.py` line 330-331):
```python
bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds
# Live: 60 // 5 = 12 bars

bars_into_candle = tracking_idx % bars_per_candle
# tracking_idx is absolute bar count from BarBuffer
# bars_into_candle: 0, 1, 2, ..., 11, 0, 1, 2, ..., 11 (repeats)

if bars_into_candle == (bars_per_candle - 1):
    # At 1-minute candle close (bars 11, 23, 35, 47, ...)
    check_cvd_and_enter()
```

**Example Timeline** (Live Trading):
```
Bar 0-10:   Wait (bars_into_candle = 0-10)
Bar 11:     ✅ CANDLE CLOSE (bars_into_candle = 11 = 12-1)
Bar 12-22:  Wait
Bar 23:     ✅ CANDLE CLOSE
Bar 24-34:  Wait
Bar 35:     ✅ CANDLE CLOSE
```

### CVD Calculation (Live)

**Uses TICKS directly** (`cvd_calculator.py` line 378):
```python
def calculate_auto(self, bars, current_idx, ticks):
    if ticks and len(ticks) > 0:
        # Use tick data for CVD calculation
        return self.calculate_from_ticks(ticks, bar=None)
```

**Candle Color from Ticks** (Oct 28, 2025 fix):
```python
first_tick_price = ticks[0].price   # "Open"
last_tick_price = ticks[-1].price   # "Close"
price_change_pct = (last_tick_price - first_tick_price) / first_tick_price * 100

if abs(price_change_pct) < 0.02:  # 0.02% = DOJI threshold
    price_direction = 'NEUTRAL'
elif price_change > 0:
    price_direction = 'UP'  # GREEN
else:
    price_direction = 'DOWN'  # RED
```

**Result**: Candle color determined from full tick window, **not individual 5-second bars** ✅

---

## Mode #2: Backtesting (1-Minute Bars)

### Data Flow

```
IBKR Historical API (1-minute bars)
    ↓
backtester.reqHistoricalData()
    ↓
bars[] array (full day of 1-minute bars)
    ↓
Strategy (checks every 1 bar = 1-minute candle)
    ↓
Entry Decision
```

### Initialization

**File**: `trader/backtest/backtester.py` (line 68)
```python
# Backtester EXPLICITLY passes bar_size_seconds=60
self.strategy = PS60Strategy(self.config, ib_connection=None, bar_size_seconds=60)
# Forces 1-minute bar resolution
```

### Historical Bars

**Request** (`backtester.py` line 291-301):
```python
bars = self.ib.reqHistoricalData(
    contract,
    endDateTime=end_time,
    durationStr='1 D',
    barSizeSetting='1 min',  # ⬅️ 1-minute bars from IBKR
    whatToShow='TRADES',
    useRTH=True,
    formatDate=1
)
```

**Result**: `bars[]` contains ~390 1-minute bars (6.5 hours × 60 minutes)

### Candle Boundary Detection

**Same Calculation** (`ps60_entry_state_machine.py` line 330-331):
```python
bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds
# Backtest: 60 // 60 = 1 bar

bars_into_candle = tracking_idx % bars_per_candle
# bars_into_candle: Always 0 (every bar is a candle!)

if bars_into_candle == (bars_per_candle - 1):
    # Backtest: bars_into_candle = 0, so (1-1) = 0
    # Every bar triggers candle close check ✅
```

**Example Timeline** (Backtesting):
```
Bar 0:   ✅ CANDLE CLOSE (bars_into_candle = 0 = 1-1)
Bar 1:   ✅ CANDLE CLOSE
Bar 2:   ✅ CANDLE CLOSE
Bar 3:   ✅ CANDLE CLOSE
```

**Every 1-minute bar IS a complete candle** ✅

### CVD Calculation (Backtesting)

**Option 1: Use Tick Cache** (if available, Oct 21, 2025 feature):
```python
# Fetch historical ticks for this 1-minute bar
ticks = self.get_tick_data(symbol, bar.date)

if ticks:
    # Use actual ticks for accurate CVD (same as live)
    return calculator.calculate_auto(bars, idx, ticks=ticks)
```

**Option 2: Bar Approximation** (fallback):
```python
# No ticks available, approximate from OHLC
cvd = calculator.calculate_from_bars(bars, current_idx)
```

**Candle Color from Bar** (backtesting):
```python
# 1-minute bar already has open/close
bar_open = bars[current_idx].open
bar_close = bars[current_idx].close
price_change_pct = (bar_close - bar_open) / bar_open * 100

if abs(price_change_pct) < 0.02:
    price_direction = 'NEUTRAL'
elif bar_close > bar_open:
    price_direction = 'UP'  # GREEN
else:
    price_direction = 'DOWN'  # RED
```

**Result**: Candle color from 1-minute OHLC bar ✅

---

## Comparison Table

| Aspect | Live Trading (5-sec bars) | Backtesting (1-min bars) |
|--------|---------------------------|--------------------------|
| **Bar Resolution** | 5 seconds | 60 seconds |
| **bar_size_seconds** | 5 (default) | 60 (explicit) |
| **bars_per_candle** | 12 (60/5) | 1 (60/60) |
| **Data Source** | Real-time ticks → BarBuffer | IBKR historical API |
| **Bar Storage** | Last 240 bars (20 min) | Full day (~390 bars) |
| **Candle Close Check** | Every 12 bars | Every 1 bar |
| **CVD Source** | Ticks (tick-by-tick) | Ticks (cached) or Bars (approx) |
| **Candle Color** | From ticks (first→last) | From bar (open→close) |
| **DOJI Threshold** | 0.02% | 0.02% |
| **Example Check** | Bars 11, 23, 35... | Bars 0, 1, 2, 3... |

---

## Why Dynamic Bar Resolution Works

### Example: Sustained Break Check

**Code** (`ps60_entry_state_machine.py` line 1280):
```python
required_bars = (strategy.sustained_break_minutes * 60) // strategy.bar_size_seconds
# Live: (2 * 60) // 5 = 24 bars (2 minutes)
# Backtest: (2 * 60) // 60 = 2 bars (2 minutes)
```

**Both wait 2 minutes, just with different bar counts!**

### Example: Volume Lookback

**Code** (`ps60_strategy.py` line 241):
```python
choppy_lookback_bars = choppy_lookback_seconds // self.bar_size_seconds
# Live: 300 // 5 = 60 bars (5 minutes)
# Backtest: 300 // 60 = 5 bars (5 minutes)
```

**Both look back 5 minutes, just with different bar counts!**

### Example: Candle Boundary

**Code** (`ps60_entry_state_machine.py` line 1000-1004):
```python
bars_per_candle = strategy.candle_timeframe_seconds // strategy.bar_size_seconds
bars_into_candle = tracking_idx % bars_per_candle

if bars_into_candle == (bars_per_candle - 1):
    # At 1-minute candle close
    check_for_momentum()
```

**Live**: Checks bars 11, 23, 35 (every 12 bars)
**Backtest**: Checks bars 0, 1, 2 (every 1 bar)

**Result**: Both check at 1-minute intervals ✅

---

## The October 28, 2025 Bug (And Why It Happened)

### The Problem

**Live Trading**:
```python
# At bar 131 (11:36:31 ET) - 1-minute candle close
current_bar = bars[current_idx]  # Gets bar 131 (ONE 5-second bar)
candle_color = current_bar.close - current_bar.open  # ❌ Wrong!

# Bar 131 might be: Open $52.84, Close $52.84 (DOJI)
# But 1-minute candle (bars 120-131) is: Open $52.82, Close $52.86 (GREEN)
```

**Why It Happened**:
- Code waits for `bars_into_candle == 11` (1-minute boundary)
- Feels like you're "at a candle"
- But `bars[current_idx]` is **still just bar 131** (a single 5-second bar!)
- To get the full candle, need to aggregate bars[120:132]

### The Fix (Oct 28, 2025)

**Before**: Used `bars[current_idx]` (5-second bar) for candle color
**After**: Use **ticks directly** (first tick → last tick)

```python
# Now in cvd_calculator.py
first_tick_price = ticks[0].price   # Open of tick window
last_tick_price = ticks[-1].price   # Close of tick window
price_change_pct = (last_tick_price - first_tick_price) / first_tick_price * 100
```

**Why This Works**:
- Ticks span the full 1-minute window
- No need to aggregate 5-second bars
- More accurate (uses actual trade prices)

**Backtesting**: Not affected (uses 1-minute bars, so `bars[current_idx]` IS the full candle)

---

## Remaining Issues (From Comprehensive Review)

### Issue #2: Sustained Break Candle Size

**Location**: `ps60_entry_state_machine.py` line 1304

**Problem** (Live Trading):
```python
current_bar = bars[current_idx]  # ONE 5-second bar
candle_size_pct = abs(current_bar.close - current_bar.open) / current_bar.open
# Checks if THIS 5-second bar meets 0.3% threshold ❌
```

**Should Be**:
```python
# Aggregate 12 five-second bars into 1-minute candle
bars_per_candle = 12
candle_start = (current_idx // bars_per_candle) * bars_per_candle
candle_bars = bars[candle_start:candle_start + 12]

candle_open = candle_bars[0].open
candle_close = candle_bars[-1].close
candle_size_pct = abs(candle_close - candle_open) / candle_open
# Check if 1-MINUTE CANDLE meets 0.3% threshold ✅
```

**Backtesting**: Not affected (already uses 1-minute bars)

---

## Summary

### ✅ What Works

1. **Dynamic bar resolution** via `bar_size_seconds`
2. **Automatic candle boundary detection** via `bars_per_candle`
3. **Time-based calculations** scale correctly (5 minutes = 60 bars or 5 bars)
4. **CVD from ticks** works in both modes (with tick cache for backtest)
5. **Candle color from ticks** (Oct 28 fix) ✅

### ⚠️ What Needs Fixing

1. **Issue #2**: Sustained break candle size uses 5-second bar (should aggregate to 1-minute)
2. **Issue #3**: Sustained break volume average uses 20 5-second bars (should use 20 1-minute candles)

### 🎯 Design Philosophy

**"Write once, run anywhere"**: Same strategy code works for both live (5-second) and backtest (1-minute) by using:
- `bar_size_seconds` parameter
- Dynamic `bars_per_candle` calculation
- Time-based lookback windows (convert seconds → bars)

**Result**: Changes to strategy logic automatically work in both modes!

---

*Analysis Date: October 28, 2025*
*Last Updated: After CVD fix (ticks for candle color)*
