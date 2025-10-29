# PS60 Backtesting System - Complete Process Documentation

**Created**: October 25, 2025
**Purpose**: Comprehensive guide to the PS60 backtesting architecture, data pipeline, and execution flow

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Input Data Sources](#input-data-sources)
3. [Data Preparation Pipeline](#data-preparation-pipeline)
4. [Backtest Execution](#backtest-execution)
5. [Output & Results](#output--results)
6. [File Locations](#file-locations)
7. [Running Your Own Backtest](#running-your-own-backtest)

---

## Architecture Overview

The PS60 backtesting system simulates live trading using historical data from IBKR. It processes scanner-identified setups, downloads tick-level and 1-minute bar data, calculates CVD (Cumulative Volume Delta), and executes the same trading logic used in live trading.

### Complete Execution Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         BACKTEST EXECUTION FLOW                          │
└──────────────────────────────────────────────────────────────────────────┘

1. INPUT DATA SOURCES
   ├── Scanner Results (Pre-defined pivots & setups)
   │   └── stockscanner/output/scanner_results_YYYYMMDD.json
   │       - Resistance/Support levels
   │       - Targets, Scores, Risk/Reward ratios
   │
   ├── Historical Market Data (from IBKR)
   │   ├── Tick Data (raw trades for CVD)
   │   │   └── trader/backtest/data/ticks/SYMBOL_YYYYMMDD_ticks.json
   │   └── 1-Minute Bars (OHLCV price action)
   │       └── trader/backtest/data/SYMBOL_YYYYMMDD_1min.json
   │
   └── Configuration
       └── trader/config/trader_config.yaml

           ↓

2. DATA PREPARATION (DataProcessor)
   ├── Phase 1: Check/Download Tick Data
   │   - Queries IBKR for historical tick data
   │   - Saves to data/ticks/SYMBOL_YYYYMMDD_ticks.json
   │
   ├── Phase 2: Check/Download 1-Minute Bars
   │   - Queries IBKR for 1-min OHLCV bars
   │   - Saves to data/SYMBOL_YYYYMMDD_1min.json
   │
   └── Phase 3: Build CVD-Enriched Bars
       - Combines tick data → CVD calculation
       - Merges with 1-min bars
       - Saves to data/cvd_bars/SYMBOL_YYYYMMDD_cvd.json
       - This is the FINAL backtesting data source

           ↓

3. BACKTEST EXECUTION (backtester.py)
   ├── Load CVD-enriched bars from cache
   │
   ├── For each symbol in watchlist:
   │   ├── Process 1-min bars sequentially
   │   ├── Check entry conditions (hybrid state machine)
   │   │   - MOMENTUM breakout path
   │   │   - PULLBACK/RETEST path
   │   │   - CVD monitoring path
   │   ├── Apply filters (choppy, stochastic, CVD, room-to-run)
   │   ├── Execute trades (position sizing, stops)
   │   └── Manage exits (partials, targets, trailing stops)
   │
   └── Track all trades + analytics

           ↓

4. OUTPUT & RESULTS
   ├── Trade Records (JSON)
   │   └── trader/backtest/results/backtest_trades_YYYYMMDD.json
   │       - Entry/exit prices, times, P&L
   │       - Filter decisions, state transitions
   │       - CVD data, exit reasons
   │
   ├── Log Files
   │   └── trader/backtest/logs/backtest_YYYYMMDD_HHMMSS.log
   │       - Detailed execution trace
   │       - Filter checks, decision logic
   │
   └── Console Summary
       - Total P&L, win rate, avg trade
       - Exit reason breakdown
       - CVD filter analytics
```

---

## Input Data Sources

### 1. Scanner Results (Pre-defined Setups)

**Location**: `stockscanner/output/scanner_results_YYYYMMDD.json`

**Purpose**: Provides pre-identified breakout levels and targets. Scanner runs BEFORE market open, backtester uses these levels to determine entries.

**Example Structure**:
```json
{
  "symbol": "TSLA",
  "resistance": 449.30,    // LONG pivot (breakout level)
  "support": 442.05,       // SHORT pivot
  "target1": 454.50,       // First profit target
  "target2": 458.00,       // Second profit target
  "target3": 462.00,       // Third profit target
  "downside1": 438.00,     // SHORT target 1
  "downside2": 434.50,     // SHORT target 2
  "score": 75,             // Setup quality (0-100)
  "risk_reward": 3.5,      // R/R ratio
  "close": 447.11,         // Previous day's close
  "dist_to_R%": 0.49,      // Distance to resistance
  "dist_to_S%": 1.13       // Distance to support
}
```

**Key Fields**:
- `resistance`: Price level to break for LONG entry
- `support`: Price level to break for SHORT entry
- `target1/2/3`: Profit-taking levels
- `score`: Scanner quality score (filters by min_score in config)
- `risk_reward`: Pre-calculated R/R ratio

### 2. Historical Tick Data (for CVD Calculation)

**Location**: `trader/backtest/data/ticks/SYMBOL_YYYYMMDD_ticks.json`

**Purpose**: Raw trade-by-trade data used to calculate Cumulative Volume Delta (buy vs sell pressure)

**Source**: Downloaded from IBKR via `ib.reqHistoricalTicks()`

**Example Structure**:
```json
[
  {
    "time": "2025-10-22 09:30:15",
    "price": 449.25,
    "size": 150,
    "tickAttribLast": {
      "pastLimit": false,
      "unreported": false
    }
  },
  {
    "time": "2025-10-22 09:30:18",
    "price": 449.30,
    "size": 200,
    "tickAttribLast": {
      "pastLimit": false,
      "unreported": false
    }
  }
]
```

**CVD Calculation Logic**:
- If tick price > previous tick price → **BUY volume**
- If tick price < previous tick price → **SELL volume**
- CVD Delta = Buy Volume - Sell Volume
- CVD Imbalance % = (Buy - Sell) / (Buy + Sell) × 100

**Coverage**: 9:30 AM - 4:00 PM ET (regular trading hours)

### 3. 1-Minute Bars (for Price Action)

**Location**: `trader/backtest/data/SYMBOL_YYYYMMDD_1min.json`

**Purpose**: OHLCV bars for price action analysis, momentum detection, and entry/exit logic

**Source**: Downloaded from IBKR via `ib.reqHistoricalData(barSizeSetting='1 min')`

**Example Structure**:
```json
[
  {
    "date": "2025-10-22 09:30:00",
    "open": 449.20,
    "high": 449.80,
    "low": 449.15,
    "close": 449.75,
    "volume": 45200,
    "average": 449.48,
    "barCount": 152
  }
]
```

**Key Fields**:
- `date`: Bar timestamp (1-minute intervals)
- `open/high/low/close`: OHLC prices
- `volume`: Total volume for the 1-minute period
- `barCount`: Number of trades in the bar

**Coverage**: 390 bars per day (9:30 AM - 4:00 PM)

### 4. Configuration

**Location**: `trader/config/trader_config.yaml`

**Purpose**: All trading parameters, filter settings, and system behavior

**Key Sections**:
```yaml
trading:
  account_size: 50000
  risk_per_trade: 0.01  # 1% risk per trade
  max_positions: 5

filters:
  enable_gap_filter: true
  enable_choppy_filter: true
  enable_room_to_run_filter: true
  min_room_to_target_pct: 0.015  # 1.5%

confirmation:
  choppy_atr_multiplier: 0.5
  momentum_volume_threshold: 1.3  # 1.3x volume
  momentum_candle_min_pct: 0.008  # 0.8% candle

  cvd:
    enabled: true
    price_validation_enabled: true
    max_price_deviation_pct: 0.003  # 0.3%
```

---

## Data Preparation Pipeline

The `DataProcessor` module orchestrates a 3-phase pipeline to prepare all required data before backtesting.

### Module: `data_processor.py`

**Purpose**: Download and prepare all historical data for backtesting

**Key Class**: `DataProcessor`

### Phase 1: Tick Data Download

**Method**: `_download_tick_data(symbol, date)`

**Process**:
```python
# Check if tick data already exists
tick_file = f"data/ticks/{symbol}_{date_str}_ticks.json"

if tick_file.exists():
    log("✓ Tick data exists")
    return

# Download from IBKR
contract = Stock(symbol, 'SMART', 'USD')
ticks = ib.reqHistoricalTicks(
    contract=contract,
    startDateTime=f'{date} 09:30:00 US/Eastern',
    endDateTime=f'{date} 16:00:00 US/Eastern',
    numberOfTicks=1000,  # Max per request
    whatToShow='TRADES',
    useRTH=True
)

# Pagination if needed (>1000 ticks)
all_ticks = []
while ticks:
    all_ticks.extend(ticks)
    if len(ticks) < 1000:
        break
    # Request next batch
    ticks = ib.reqHistoricalTicks(...)

# Save to JSON
save_json(tick_file, all_ticks)
```

**Output**: `data/ticks/SYMBOL_YYYYMMDD_ticks.json`

**Typical Size**: 50,000-200,000 ticks per symbol per day

### Phase 2: 1-Minute Bars Download

**Method**: `_download_1min_bars(symbol, date)`

**Process**:
```python
# Check if bars already exist
bars_file = f"data/{symbol}_{date_str}_1min.json"

if bars_file.exists():
    log("✓ 1-minute bars exist")
    return

# Download from IBKR
contract = Stock(symbol, 'SMART', 'USD')
bars = ib.reqHistoricalData(
    contract=contract,
    endDateTime=f'{date} 16:00:00 US/Eastern',
    durationStr='1 D',
    barSizeSetting='1 min',  # 1-minute bars
    whatToShow='TRADES',
    useRTH=True,  # Regular trading hours only
    formatDate=1
)

# Save to JSON
save_json(bars_file, bars)
```

**Output**: `data/SYMBOL_YYYYMMDD_1min.json`

**Typical Size**: 390 bars per symbol per day

### Phase 3: CVD-Enriched Bars (Final Data)

**Method**: `_build_cvd_enriched_bars(symbol, date)`

**Purpose**: Combine tick data + 1-minute bars to create final backtesting data

**Process**:
```python
# Check if CVD-enriched bars already exist
cvd_file = f"data/cvd_bars/{symbol}_{date_str}_cvd.json"

if cvd_file.exists():
    log("✓ CVD-enriched bars exist")
    return

# 1. Load tick data
ticks = load_json(f"data/ticks/{symbol}_{date_str}_ticks.json")

# 2. Load 1-minute bars
bars = load_json(f"data/{symbol}_{date_str}_1min.json")

# 3. Initialize CVD calculator
cvd_calc = CVDCalculator(config)

# 4. For each 1-minute bar, calculate CVD
enriched_bars = []
for bar in bars:
    # Get ticks that occurred during this bar
    bar_start = bar.date
    bar_end = bar.date + timedelta(minutes=1)
    bar_ticks = [t for t in ticks if bar_start <= t.time < bar_end]

    # Calculate CVD for this bar
    cvd_data = cvd_calc.calculate_cvd(bar_ticks)

    # Merge CVD data into bar
    enriched_bar = {
        'date': bar.date,
        'open': bar.open,
        'high': bar.high,
        'low': bar.low,
        'close': bar.close,
        'volume': bar.volume,
        'buy_volume': cvd_data['buy_volume'],
        'sell_volume': cvd_data['sell_volume'],
        'cvd_delta': cvd_data['delta'],
        'cvd_imbalance': cvd_data['imbalance_pct'],
        'tick_count': len(bar_ticks)
    }
    enriched_bars.append(enriched_bar)

# 5. Save CVD-enriched bars
save_json(cvd_file, enriched_bars)
```

**Output**: `data/cvd_bars/SYMBOL_YYYYMMDD_cvd.json`

**This is the FINAL data source used by backtester** - combines price action + volume pressure.

### Complete Pipeline Execution

**Entry Point**: `DataProcessor.prepare_data_for_date(symbols, date)`

```python
stats = {
    'symbols_processed': 0,
    'tick_data_downloaded': 0,
    'bars_downloaded': 0,
    'cvd_bars_built': 0,
    'already_cached': 0,
    'errors': 0
}

for symbol in symbols:
    try:
        # Phase 1: Tick data
        if not tick_data_exists(symbol, date):
            download_tick_data(symbol, date)
            stats['tick_data_downloaded'] += 1

        # Phase 2: 1-minute bars
        if not bars_exist(symbol, date):
            download_1min_bars(symbol, date)
            stats['bars_downloaded'] += 1

        # Phase 3: CVD-enriched bars
        if not cvd_bars_exist(symbol, date):
            build_cvd_enriched_bars(symbol, date)
            stats['cvd_bars_built'] += 1
        else:
            stats['already_cached'] += 1

        stats['symbols_processed'] += 1

    except Exception as e:
        log(f"Error processing {symbol}: {e}", level='ERROR')
        stats['errors'] += 1

return stats
```

**Console Output Example**:
```
================================================================================
DATA PROCESSOR - Preparing data for 2025-10-22
================================================================================

[1/8] Processing TSLA...
  ✓ Tick data exists
  ✓ 1-minute bars exist
  ✓ CVD-enriched bars exist

[2/8] Processing NVDA...
  ✓ Tick data exists
  ✓ 1-minute bars exist
  ✓ CVD-enriched bars exist

[3/8] Processing PATH...
  ⬇️ Downloading tick data... (50,234 ticks)
  ⬇️ Downloading 1-minute bars... (390 bars)
  🔨 Building CVD-enriched bars...

================================================================================
DATA PROCESSOR SUMMARY
================================================================================
Symbols processed: 8/8
Tick data downloaded: 1
1-minute bars downloaded: 1
CVD-enriched bars built: 1
Already cached: 7
Errors: 0
================================================================================
```

---

## Backtest Execution

### Module: `backtester.py`

**Main Class**: `PS60Backtester`

### Command Line Usage

```bash
cd trader/backtest
python3 backtester.py \
  --scanner /path/to/scanner_results_YYYYMMDD.json \
  --date YYYY-MM-DD \
  --account-size 50000
```

**Example**:
```bash
python3 backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251022.json \
  --date 2025-10-22 \
  --account-size 50000
```

### Initialization Phase

```python
def __init__(self, scanner_file, test_date, account_size):
    # 1. Load configuration
    config = load_yaml('trader/config/trader_config.yaml')

    # 2. Connect to IBKR (for data download only)
    self.ib = IB()
    self.ib.connect('127.0.0.1', 7497, clientId=3938)

    # 3. Initialize strategy module (same code as live trading)
    self.strategy = PS60Strategy(
        config,
        ib_connection=self.ib,
        bar_size_seconds=60  # 1-minute bars
    )

    # 4. Initialize position manager
    self.pm = PositionManager()

    # 5. Load scanner results
    self.scanner_results = load_json(scanner_file)

    # 6. Initialize data processor
    self.data_processor = DataProcessor(self.ib, config)

    # 7. Initialize caches
    self.bars_cache = {}          # In-memory bar cache
    self.hourly_bars_cache = {}   # Hourly SMA data
    self.cvd_enriched_bars = {}   # CVD-enriched bars
```

### Execution Flow

#### Step 1: Filter Scanner Results

```python
def run(self):
    # Filter scanner results by config criteria
    watchlist = []
    for stock in self.scanner_results:
        # Apply scanner filters
        if stock['score'] >= config['filters']['min_score']:
            if stock['risk_reward'] >= config['filters']['min_risk_reward']:
                watchlist.append(stock)

    print(f"WATCHLIST: {len(watchlist)} tradeable setups")
```

**Filters Applied**:
- Minimum score (e.g., 50)
- Minimum R/R ratio (e.g., 2.0)
- Symbol blacklist (SPY, QQQ, etc.)
- Direction filters (enable_longs, enable_shorts)

#### Step 2: Prepare Data

```python
# Extract symbols from watchlist
symbols = [stock['symbol'] for stock in watchlist]

# Run data processor
stats = self.data_processor.prepare_data_for_date(symbols, self.test_date)

print(f"Data prepared: {stats['symbols_processed']} symbols")
```

#### Step 3: Load CVD-Enriched Bars

```python
# Load CVD-enriched bars for all symbols
for stock in watchlist:
    symbol = stock['symbol']
    date_str = self.test_date.strftime('%Y%m%d')

    cvd_file = f"data/cvd_bars/{symbol}_{date_str}_cvd.json"
    bars = load_json(cvd_file)

    self.cvd_enriched_bars[symbol] = bars
    print(f"  ✓ Loaded {len(bars)} CVD-enriched bars for {symbol}")
```

#### Step 4: Pre-fetch Hourly Bars (for SMA indicators)

```python
# Cache hourly bars for momentum indicators
for stock in watchlist:
    symbol = stock['symbol']

    # Fetch 50 hourly bars (for SMAs)
    hourly_bars = self.ib.reqHistoricalData(
        contract=Stock(symbol, 'SMART', 'USD'),
        endDateTime=self.test_date,
        durationStr='50 D',
        barSizeSetting='1 hour',
        whatToShow='TRADES',
        useRTH=True
    )

    self.hourly_bars_cache[symbol] = hourly_bars
```

#### Step 5: Simulate Trading

```python
def backtest_stock(self, stock):
    """Backtest single stock for the day"""
    symbol = stock['symbol']
    resistance = stock['resistance']
    support = stock['support']

    # Get CVD-enriched bars
    bars = self.cvd_enriched_bars[symbol]

    position = None
    long_attempts = 0
    short_attempts = 0
    max_attempts = config['trading']['attempts']['max_attempts_per_pivot']

    # Process each 1-minute bar sequentially
    for bar_idx, bar in enumerate(bars):
        timestamp = bar['date']
        price = bar['close']

        # Check if within trading hours (9:45 AM - 3:00 PM)
        within_entry_window = self.strategy.is_within_entry_window(timestamp)

        # ENTRY LOGIC
        if position is None and within_entry_window:
            # Check LONG entry
            if price > resistance and long_attempts < max_attempts:
                confirmed, reason, state = self.strategy.check_hybrid_entry(
                    bars=bars,
                    bar_idx=bar_idx,
                    pivot_price=resistance,
                    side='LONG',
                    target_price=stock['target1'],
                    symbol=symbol,
                    cached_hourly_bars=self.hourly_bars_cache[symbol]
                )

                if confirmed:
                    # Enter trade
                    position = self.enter_long(stock, bar, bar_idx)
                    long_attempts += 1
                else:
                    # Log rejection reason
                    log(f"{symbol} LONG blocked: {reason}")

            # Check SHORT entry
            elif price < support and short_attempts < max_attempts:
                confirmed, reason, state = self.strategy.check_hybrid_entry(
                    bars=bars,
                    bar_idx=bar_idx,
                    pivot_price=support,
                    side='SHORT',
                    target_price=stock.get('downside1'),
                    symbol=symbol,
                    cached_hourly_bars=self.hourly_bars_cache[symbol]
                )

                if confirmed:
                    # Enter trade
                    position = self.enter_short(stock, bar, bar_idx)
                    short_attempts += 1
                else:
                    log(f"{symbol} SHORT blocked: {reason}")

        # EXIT LOGIC
        elif position is not None:
            position, closed_trade = self.manage_position(
                position, bar, bar_idx
            )

            if closed_trade:
                self.trades.append(closed_trade)
                position = None
```

### Entry Logic Details

**Method**: `check_hybrid_entry()`

**Three Entry Paths**:

1. **MOMENTUM Breakout** (immediate entry)
   - Volume ≥ 1.3x average
   - Candle size ≥ 0.8%
   - Filters: Choppy, Stochastic, Room-to-Run

2. **PULLBACK/RETEST** (patient entry)
   - Weak initial breakout
   - Wait for pullback to pivot (±0.3%)
   - Re-break with 1.2x volume
   - Filters: Choppy, Stochastic, Room-to-Run

3. **CVD Monitoring** (volume pressure)
   - Price near pivot (within 0.3%)
   - CVD shows strong imbalance (>15%)
   - Price validation check
   - Filters: Choppy, Stochastic, Room-to-Run

### Filter Application

**All Filters Checked for EVERY Entry**:

```python
# 1. Gap Filter
gap_blocked, gap_reason = self.strategy.check_gap_filter(stock, price, side)
if gap_blocked:
    return (False, f"GAP: {gap_reason}", None)

# 2. Choppy Filter
choppy_blocked, choppy_reason = self.strategy.check_choppy_filter(bars, bar_idx)
if choppy_blocked:
    return (False, f"CHOPPY: {choppy_reason}", None)

# 3. Stochastic Filter
stoch_blocked, stoch_reason = self.strategy.check_stochastic_filter(
    hourly_bars, side
)
if stoch_blocked:
    return (False, f"STOCHASTIC: {stoch_reason}", None)

# 4. Room-to-Run Filter
room_blocked, room_reason = self.strategy.check_room_to_run_filter(
    price, target_price, side
)
if room_blocked:
    return (False, f"ROOM: {room_reason}", None)

# 5. CVD Price Validation (if CVD entry)
if entry_state == 'CVD_MONITORING':
    cvd_price_blocked, cvd_reason = self.strategy.check_cvd_price_validation(
        price, pivot_price
    )
    if cvd_price_blocked:
        return (False, f"CVD_PRICE: {cvd_reason}", None)

# All filters passed
return (True, f"{entry_state} confirmed", entry_state)
```

### Position Management

**Method**: `manage_position(position, bar, bar_idx)`

**Exit Scenarios**:

1. **Stop Loss Hit**
   ```python
   if side == 'LONG' and price <= position['stop']:
       return close_position(position, price, 'STOP')
   ```

2. **7-Minute Rule** (no progress)
   ```python
   time_in_trade = (bar.date - position['entry_time']).seconds / 60
   gain = price - position['entry_price']

   if time_in_trade >= 7 and gain < 0.10 and position['remaining'] == 1.0:
       return close_position(position, price, '7MIN_RULE')
   ```

3. **Partial Profits**
   ```python
   # Take 50% at 1R (profit = risk)
   if position['remaining'] == 1.0:
       risk_distance = abs(position['entry_price'] - position['stop'])
       if gain >= risk_distance:
           take_partial(position, 0.50, price, 'PROFIT_1R')
           position['stop'] = position['entry_price']  # Move to breakeven

   # Take 25% at target1
   if position['remaining'] > 0.25 and price >= position['target1']:
       take_partial(position, 0.25, price, 'TARGET1')
   ```

4. **Target Hit Stall Detection** (Phase 9)
   ```python
   if target_hit_and_stalling(position, price):
       # Tighten trail from 0.5% → 0.1%
       position['trailing_distance'] = 0.001
   ```

5. **Trailing Stop**
   ```python
   if position['trailing_stop_active']:
       new_stop = price * (1 - position['trailing_distance'])
       if new_stop > position['stop']:
           position['stop'] = new_stop
   ```

6. **End of Day** (3:55 PM)
   ```python
   if bar.date.time() >= time(15, 55):
       return close_position(position, price, 'EOD')
   ```

---

## Output & Results

### 1. Trade Records JSON

**Location**: `trader/backtest/results/backtest_trades_YYYYMMDD.json`

**Structure**:
```json
[
  {
    "symbol": "PATH",
    "side": "SHORT",
    "entry_price": 15.35,
    "entry_time": "2025-10-22 09:54:00",
    "exit_price": 15.48,
    "exit_time": "2025-10-22 09:58:00",
    "pnl": -136.27,
    "pnl_pct": -0.85,
    "shares": 1000,
    "duration_minutes": 4,
    "exit_reason": "STOP",
    "partials_taken": 0,
    "entry_path": "MOMENTUM_BREAKOUT",
    "resistance": 15.42,
    "support": 15.42,
    "stop_price": 15.45,
    "target1": 15.20,
    "filters_checked": {
      "gap": "PASS",
      "choppy": "PASS",
      "stochastic": "PASS",
      "room_to_run": "PASS"
    },
    "cvd_data": {
      "buy_volume": 15420,
      "sell_volume": 18950,
      "delta": -3530,
      "imbalance_pct": -10.3
    },
    "partials": [],
    "max_gain": 0.00,
    "max_loss": -0.85
  }
]
```

**Key Fields**:
- `entry_path`: Which entry strategy was used (MOMENTUM/PULLBACK_RETEST/CVD_MONITORING)
- `filters_checked`: All filter results (PASS/BLOCK)
- `cvd_data`: Volume pressure data at entry
- `partials`: Array of partial exits taken
- `exit_reason`: Why trade was closed

### 2. Console Summary

```
================================================================================
BACKTEST RESULTS
================================================================================

📊 TRADE SUMMARY:
  Total trades: 2
  Winners: 0 (0.0%)
  Losers: 2 (100.0%)

💰 P&L ANALYSIS:
  Total P&L: $-201.58
  Avg trade: $-100.79
  Avg winner: $0.00
  Avg loser: $-100.79
  Profit factor: 0.00

⏱️  TRADE DURATION:
  Avg duration: 5.5 minutes
  Shortest: 4 minutes
  Longest: 7 minutes

🎯 EXIT REASONS:
  STOP: 1 trades (50.0%)
  7MIN_RULE: 1 trades (50.0%)

📊 ENTRY PATHS:
  MOMENTUM_BREAKOUT: 2 trades
  PULLBACK_RETEST: 0 trades
  CVD_MONITORING: 0 trades

🔬 CVD FILTER ANALYTICS:
  CVD enabled but no entries were blocked

================================================================================
DETAILED TRADE LOG:
================================================================================

1. PATH SHORT
   Entry: $15.35 @ 09:54
   Exit:  $15.48 @ 09:58 (STOP)
   P&L:   $-136.27 (-0.89%) | Duration: 4 min
   Entry Path: MOMENTUM_BREAKOUT (1.8x volume, 0.65% candle)
   Partials: 0
   CVD: buy=15420, sell=18950, delta=-3530, imbalance=-10.3%

2. PATH SHORT
   Entry: $15.29 @ 10:13
   Exit:  $15.35 @ 10:20 (7MIN_RULE)
   P&L:   $-65.31 (-0.43%) | Duration: 7 min
   Entry Path: MOMENTUM_BREAKOUT (2.1x volume, 0.82% candle)
   Partials: 0
   CVD: buy=12350, sell=16200, delta=-3850, imbalance=-13.5%
```

### 3. Log File

**Location**: `trader/backtest/logs/backtest_YYYYMMDD_HHMMSS.log`

**Contents**: Detailed execution trace with DEBUG-level information

**Example**:
```
INFO - ================================================================================
INFO - PS60 BACKTEST - 2025-10-22 00:00:00
INFO - ================================================================================
INFO - Scanner file: scanner_results_20251022.json
INFO - Loaded 9 scanner results
INFO - ✓ Connected to IBKR (Client ID: 3938)

DEBUG - Filtering watchlist by score >= 45, R/R >= 0.0
INFO - WATCHLIST: 8 tradeable setups

INFO - 📊 Pre-fetching hourly bars for momentum indicators...
INFO -   ✓ SMCI: 50 hourly bars cached
INFO -   ✓ SOFI: 50 hourly bars cached
...

INFO - [PATH] Testing setup...
INFO -   Resistance: $16.59 | Support: $15.42
INFO -   Score: 45 | R/R: 1.96:1
INFO -   ✓ Fetched 390 1-minute bars

DEBUG - PATH Bar 25 - Price $15.35 < Support $15.42 (SHORT trigger)
DEBUG -   Checking hybrid entry for SHORT...
DEBUG -   Entry state: MOMENTUM_BREAKOUT
DEBUG -   Volume: 1.8x (threshold: 1.3x) ✓
DEBUG -   Candle size: 0.65% (threshold: 0.8%) ✗
DEBUG -   Falling back to WEAK_BREAKOUT_TRACKING

DEBUG -   Choppy filter: PASS (range 0.8% > 0.5% threshold)
DEBUG -   Stochastic filter: PASS (K=45.2 in 20-50 range for SHORT)
DEBUG -   Room-to-run filter: PASS (2.8% to target > 1.5%)

INFO - PATH Bar 25 - ENTERING SHORT @ $15.37, stop=$15.45
INFO -   Shares: 1000 | Risk: $500 (1% of account)
INFO -   Entry path: MOMENTUM_BREAKOUT

INFO - PATH Bar 29 - Price $15.45 >= Stop $15.45
INFO - PATH Bar 29 - EXIT (STOP) SHORT @ $15.48
INFO -   Duration: 4 minutes
INFO -   P&L: $-136.27 (-0.85%)
```

---

## File Locations

### Complete Directory Structure

```
trader/backtest/
├── backtester.py                       # Main backtest engine
├── data_processor.py                   # Data download & preparation
├── download_tick_data.py              # Standalone tick downloader
│
├── data/                               # Historical market data
│   ├── ticks/                          # Raw tick data (input)
│   │   ├── TSLA_20251022_ticks.json
│   │   ├── NVDA_20251022_ticks.json
│   │   └── PATH_20251022_ticks.json
│   │
│   ├── cvd_bars/                       # CVD-enriched bars (final data)
│   │   ├── TSLA_20251022_cvd.json
│   │   ├── NVDA_20251022_cvd.json
│   │   └── PATH_20251022_cvd.json
│   │
│   ├── TSLA_20251022_1min.json        # 1-minute OHLCV bars
│   ├── NVDA_20251022_1min.json
│   └── PATH_20251022_1min.json
│
├── results/                            # Backtest outputs
│   ├── backtest_trades_20251015.json
│   ├── backtest_trades_20251016.json
│   ├── backtest_trades_20251020.json
│   ├── backtest_trades_20251021.json
│   └── backtest_trades_20251022.json
│
└── logs/                               # Execution logs
    ├── backtest_20251022_002858.log
    ├── backtest_20251021_145632.log
    └── backtest_20251020_183045.log
```

### File Naming Conventions

**Tick Data**: `data/ticks/{SYMBOL}_{YYYYMMDD}_ticks.json`
**1-Min Bars**: `data/{SYMBOL}_{YYYYMMDD}_1min.json`
**CVD Bars**: `data/cvd_bars/{SYMBOL}_{YYYYMMDD}_cvd.json`
**Trade Results**: `results/backtest_trades_{YYYYMMDD}.json`
**Logs**: `logs/backtest_{YYYYMMDD}_{HHMMSS}.log`

### Typical File Sizes

| File Type | Typical Size | Count per Day |
|-----------|--------------|---------------|
| Tick data | 5-20 MB | 1 per symbol |
| 1-min bars | 50-200 KB | 1 per symbol |
| CVD bars | 100-300 KB | 1 per symbol |
| Trade results | 5-50 KB | 1 per backtest |
| Log file | 100-500 KB | 1 per backtest |

---

## Running Your Own Backtest

### Prerequisites

1. **IBKR Connection**:
   - TWS or Gateway running on port 7497 (paper trading)
   - API connections enabled
   - Permissions for historical data

2. **Scanner Results**:
   - Pre-generated scanner file for the date
   - Location: `stockscanner/output/scanner_results_YYYYMMDD.json`

3. **Python Environment**:
   - Python 3.8+
   - ib_insync library
   - pandas, numpy, yaml

### Step-by-Step Process

#### Step 1: Run Scanner (Day Before)

```bash
cd stockscanner
python3 scanner.py --category quick

# Output: stockscanner/output/scanner_results_20251025.json
```

#### Step 2: Run Backtest

```bash
cd trader/backtest

python3 backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251022.json \
  --date 2025-10-22 \
  --account-size 50000
```

**What Happens**:
1. Connects to IBKR
2. Loads scanner results (8 stocks)
3. Checks if data exists:
   - ✓ Tick data cached
   - ✓ 1-min bars cached
   - ✓ CVD bars cached
4. Runs backtest (processes 390 bars per stock)
5. Outputs results to console + JSON + log

#### Step 3: View Results

**JSON Output**:
```bash
cat results/backtest_trades_20251022.json | python3 -m json.tool
```

**Log File**:
```bash
cat logs/backtest_20251022_*.log
```

**Detailed Analysis**:
```bash
python3 analyze_session.py results/backtest_trades_20251022.json
```

### Downloading Data for Multiple Days

**Use batch download script**:

```bash
cd trader/backtest

# Edit batch_download.sh to add dates
DATES="2025-10-15 2025-10-16 2025-10-20 2025-10-21 2025-10-22"

# Run batch download
./batch_download.sh
```

**This will**:
1. Download tick data for all dates
2. Download 1-min bars for all dates
3. Build CVD-enriched bars for all dates
4. Cache everything for future backtests

### Running Backtests Offline (After Data Download)

Once data is downloaded, you can backtest **without IBKR connection**:

```bash
# Data already exists, no IBKR needed
python3 backtester.py \
  --scanner scanner_results_20251022.json \
  --date 2025-10-22 \
  --account-size 50000 \
  --offline
```

The system will use cached CVD-enriched bars.

---

## Key Advantages of This Architecture

### 1. **Caching & Performance**
- Downloads data once, reuses indefinitely
- CVD pre-calculated, no recalculation during backtest
- 390 bars processed in ~2-5 seconds per symbol
- Full day backtest (8 stocks) in ~30 seconds

### 2. **Accuracy**
- Uses same tick data as live trading would see
- Same strategy module for backtest & live trading
- CVD calculation matches live trading exactly
- No look-ahead bias (scanner uses previous day data)

### 3. **Shared Code**
- `PS60Strategy` module used by both backtest & live trader
- Position management logic identical
- Filter application identical
- Guarantees backtest results match live performance

### 4. **Data Quality**
- Tick-level CVD calculation (most accurate)
- 1-minute bars for price action (industry standard)
- Hourly bars for SMA indicators
- All data from IBKR (same source as live trading)

### 5. **Offline Capability**
- After initial download, can backtest without IBKR
- Useful for parameter optimization
- Batch testing multiple configurations
- Historical analysis without live connection

### 6. **Comprehensive Logging**
- DEBUG-level logs show all decision logic
- Filter checks logged with values
- Entry path tracking
- CVD data logging
- Exit reason tracking

---

## Common Issues & Solutions

### Issue: "No data found for symbol"
**Cause**: IBKR doesn't have historical data for that date
**Solution**: Check if stock was actively traded that day, try different date

### Issue: "Tick data incomplete (< 10,000 ticks)"
**Cause**: Low-volume stock or market holiday
**Solution**: Normal for low-volume stocks, CVD calculation will work with available data

### Issue: "Connection timeout during download"
**Cause**: IBKR rate limiting (60 requests per 10 minutes)
**Solution**: Use batch download script with delays between requests

### Issue: "CVD bars missing buy_volume field"
**Cause**: Old CVD bars format (pre-Oct 21, 2025)
**Solution**: Delete old CVD bars, re-run data processor to rebuild with new format

### Issue: "Backtest shows no trades"
**Cause**: Filters too strict, no stocks broke pivots
**Solution**: Check filter settings in config, review scanner quality scores

---

## Future Enhancements

### Planned Features
1. **Multi-day backtesting**: Run backtests across date ranges
2. **Parameter optimization**: Grid search for optimal filter values
3. **Walk-forward analysis**: Progressive validation
4. **Monte Carlo simulation**: Risk analysis
5. **HTML report generation**: Visual backtest reports

### Data Enhancements
1. **5-second bars**: Higher resolution for more accurate entries
2. **Options chain data**: For options trading strategies
3. **Level 2 data**: Order book analysis
4. **News sentiment**: Fundamental filter

---

## Related Documentation

- **Strategy Logic**: `trader/strategy/ps60_strategy.py`
- **Position Management**: `trader/strategy/position_manager.py`
- **CVD Calculator**: `trader/indicators/cvd_calculator.py`
- **Configuration**: `trader/config/trader_config.yaml`
- **Progress Log**: `trader/PROGRESS_LOG.md`
- **Filter Documentation**: `trader/FILTER_DOCUMENTATION.md`

---

**Last Updated**: October 25, 2025
**Maintainer**: Claude Code
**Version**: 2.0 (Tick-based CVD implementation)
