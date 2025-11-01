# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📖 Implementation Progress

**For detailed implementation history and all completed work, see**: `trader/PROGRESS_LOG.md`

The progress log is the **single source of truth** for:
- ✅ Completed implementations (October 2025)
- 🔧 Bug fixes and lessons learned
- 📊 Backtest results and strategy evolution
- 📝 Documentation index

**⚠️ IMPORTANT**: Always update `PROGRESS_LOG.md` after completing major implementations, bug fixes, or system enhancements.

## Project Overview

**DayTrader** is an automated trading system implementing Dan Shapiro's **PS60 Process** for day trading. The project consists of two main modules:

1. **stockscanner** - Pre-market scanner that identifies high-probability breakout setups
2. **trader** - Automated trading module (✅ COMPLETE - Ready for paper trading)

## Project Structure

```
DayTrader/
├── stockscanner/          # Pre-market scanner (completed)
├── trader/                # Trading module (✅ COMPLETE - In paper trading)
│   ├── trader.py          # Main live trading engine
│   ├── strategy/          # PS60 strategy logic  
│   ├── backtest/          # Historical 1-min bar backtester
│   ├── config/            # trader_config.yaml (filter controls)
│   ├── logs/              # Trade logs and performance
│   ├── analysis/          # Daily trade analysis (Oct 15+)
│   └── explained/         # Detailed concept explanations
├── scanner_validation/    # Scanner validation system (Oct 6)
└── PS60ProcessComprehensiveDayTradingGuide.md  # Complete PS60 theory
```

**Full structure**: See `trader/PROGRESS_LOG.md`

## 📊 Historical Data Infrastructure (November 2025)

**Status**: ✅ COMPLETE - October 2025 dataset with full market context

### Data Coverage

**Quick Scan Stocks** (9 symbols): QQQ, TSLA, NVDA, AMD, PLTR, SOFI, HOOD, SMCI, PATH
**Time Period**: October 2025 (22 trading days)
**Total Files**: 574 1-min bars + 198 context indicators + 25 CVD bars
**Storage Location**: `/Users/karthik/projects/DayTrader/trader/backtest/data/`
**Total Size**: ~1.5 GB

**Complete Coverage per Stock**:
- ✅ QQQ: 22/22 days (1-min bars + context)
- ✅ TSLA: 22/22 days (1-min bars + context)
- ✅ NVDA: 22/22 days (1-min bars + context)
- ✅ AMD: 22/22 days (1-min bars + context)
- ✅ PLTR: 22/22 days (1-min bars + context)
- ✅ SOFI: 22/22 days (1-min bars + context)
- ✅ HOOD: 22/22 days (1-min bars + context)
- ✅ SMCI: 22/22 days (1-min bars + context)
- ✅ PATH: 22/22 days (1-min bars + context)

### File Types and Structure

#### 1. 1-Minute OHLCV Bars (`SYMBOL_YYYYMMDD_1min.json`)

**Purpose**: Price action data for backtesting
**Source**: IBKR historical data API
**Resolution**: 390 bars per day (09:30-16:00 ET)
**File Size**: ~72-75 KB per file

**Format**:
```json
[
  {
    "date": "2025-10-31T09:30:00-04:00",
    "open": 259.5,
    "high": 259.72,
    "low": 258.69,
    "close": 258.84,
    "volume": 324024.0,
    "average": 259.491,
    "barCount": 848
  },
  // ... 389 more bars
]
```

**Key Fields**:
- `date`: ISO 8601 timestamp with timezone (MUST be 'date' not 'timestamp' for backtester compatibility)
- `open/high/low/close`: OHLC prices
- `volume`: Share volume
- `average`: VWAP for the bar
- `barCount`: Number of ticks aggregated into this bar

#### 2. Context Indicators (`context/SYMBOL_YYYYMMDD_context.json`)

**Purpose**: Technical indicators for filter logic and strategy decisions
**Source**: Calculated from IBKR historical daily bars (250-day lookback) + 1-min bars
**File Size**: ~3-4 KB per file

**Format**:
```json
{
  "symbol": "AMD",
  "date": "2025-10-31",
  "daily": {
    "sma_5": 258.594,
    "sma_10": 248.97,
    "sma_20": 236.451,
    "sma_50": 191.269,
    "sma_100": 172.607,
    "sma_200": 139.414,
    "ema_9": 250.253,
    "ema_20": 233.387,
    "ema_50": 203.738,
    "rsi_14": 71.185,
    "atr_14": 11.021,
    "bb_upper": 271.296,
    "bb_middle": 236.451,
    "bb_lower": 201.606,
    "prev_close": 254.84,
    "prev_high": 263.88,
    "prev_low": 252.31
  },
  "hourly": {
    "09:00": { "sma_5": null, "ema_9": null, "rsi_14": null, /* ... all null early hours */ },
    "10:00": { /* ... */ },
    "13:00": { "sma_5": 257.938, /* ... populated values */ },
    // Hours 09:00-15:00, null if insufficient history
  },
  "intraday": {
    "vwap": 258.144,
    "opening_range_high": 261.21,
    "opening_range_low": 257.55,
    "volume_first_hour": 6361226
  },
  "metadata": {
    "bars_1min": 390,
    "bars_hourly": 7,
    "bars_daily": 250,
    "processed_at": "2025-11-01T13:23:10.892456"
  }
}
```

**Daily Indicators** (200-250 day lookback from IBKR):
- SMAs: 5, 10, 20, 50, 100, 200-period
- EMAs: 9, 20, 50-period
- RSI(14): Relative Strength Index
- ATR(14): Average True Range
- Bollinger Bands: Upper, middle (SMA-20), lower
- Previous day: Close, high, low

**Hourly Indicators** (calculated from 1-min bars):
- SMAs: 5, 10, 20, 50-period hourly bars
- EMAs: 9, 20-period
- RSI(14), Stochastic(14,3,3), MACD(12,26,9)
- ATR(14), Bollinger Bands
- Note: Early hours may have null values (insufficient history)

**Intraday Indicators** (calculated from 1-min bars):
- VWAP: Volume Weighted Average Price (full day)
- Opening Range: First 30 minutes high/low
- First Hour Volume: Total volume 09:30-10:30

#### 3. CVD Bars (`cvd_bars/SYMBOL_YYYYMMDD_cvd.json`)

**Purpose**: Cumulative Volume Delta (buy/sell pressure) - Used for CVD_MONITORING filter
**Coverage**: Partial (25 files, not all stocks/dates)
**Note**: CVD filter currently disabled in backtester configuration

### Data Download and Processing

#### Download Tool: `trader/data-downloader/download_october_data.py`

**Features**:
- Downloads 1-minute bars from IBKR for specified date range
- Automatic resume capability (tracks progress in `download_progress.json`)
- Rate limiting: 50 requests per 10 minutes, 1-second pacing
- Client ID: 4000 (avoid conflicts with backtester/trader)

**Usage**:
```bash
cd trader/data-downloader
python3 download_october_data.py --port 7497

# Downloads:
# - Quick scan stocks: QQQ, TSLA, NVDA, AMD, PLTR, SOFI, HOOD, SMCI, PATH
# - October 2025 trading days: 22 days
# - Total: 9 stocks × 22 days = 198 files
```

**Configuration** (lines 306-332):
- Hardcoded quick scan stock list (not reading from scanner files)
- Hardcoded October 2025 trading days
- Guarantees complete coverage regardless of scanner variations

#### Context Processing Tool: `trader/data-downloader/process_context_indicators.py`

**Features**:
- Fetches 250 days of daily bars from IBKR for SMA-200 calculation
- Calculates daily, hourly, and intraday indicators
- Caching: Fetches daily bars once per symbol, reuses for all 22 days
- Rate limiting: 1-second pacing between IBKR requests
- Client ID: 5000 (avoid conflicts)

**Usage**:
```bash
cd trader/data-downloader

# Process all quick scan stocks for October 2025
python3 process_context_indicators.py \
  --quick-scan \
  --start-date 2025-10-01 \
  --end-date 2025-10-31 \
  --use-ibkr

# Output: 198 context files in trader/backtest/data/context/
```

**Processing Flow**:
1. Load 1-min bars for the day
2. Fetch 250 days of daily bars from IBKR (cached per symbol)
3. Calculate daily indicators (SMAs, EMAs, RSI, ATR, BB)
4. Resample 1-min bars to hourly bars
5. Calculate hourly indicators (SMAs, EMAs, RSI, Stochastic, MACD)
6. Calculate intraday indicators (VWAP, opening range, first hour volume)
7. Save to JSON file

### How Backtester Uses This Data

**File**: `trader/backtest/backtester.py`

**Data Loading Flow**:
1. **Load scanner results** - Get pivot levels for the day
2. **Load 1-min bars** - Read `SYMBOL_YYYYMMDD_1min.json`
3. **Load context indicators** - Read `context/SYMBOL_YYYYMMDD_context.json`
4. **Simulate tick-by-tick** - Process bars sequentially, detect pivot breaks
5. **Apply filters** - Use context indicators for choppy filter, room-to-run, etc.

**Example** (backtester.py):
```python
# Load 1-min bars
bars_file = f"data/{symbol}_{date_str}_1min.json"
with open(bars_file, 'r') as f:
    bars = json.load(f)

# Load context indicators
context_file = f"data/context/{symbol}_{date_str}_context.json"
with open(context_file, 'r') as f:
    context = json.load(f)

# Use in strategy
daily_atr = context['daily']['atr_14']
daily_sma200 = context['daily']['sma_200']
vwap = context['intraday']['vwap']

# Apply choppy filter
five_min_range = calculate_5min_range(bars)
if five_min_range < 0.5 * daily_atr:
    # Skip choppy stock
```

**Key Filters Using Context Data**:
- **Choppy Filter**: 5-min range vs daily ATR(14)
- **Room-to-Run**: Distance to highest available target
- **Dynamic Resistance Exits**: Price vs hourly SMAs, Bollinger Bands
- **VWAP Reference**: Intraday equilibrium level

**Running a Backtest**:
```bash
cd trader/backtest

# Single day backtest
python3 backtester.py \
  --scanner ../../stockscanner/output/scanner_results_20251031.json \
  --date 2025-10-31 \
  --account-size 50000

# Output:
# - Loads AMD_20251031_1min.json
# - Loads context/AMD_20251031_context.json
# - Applies PS60 strategy with all filters
# - Generates trade log and P&L summary
```

### How Live Trader Uses This Data

**File**: `trader/trader.py`

**Live Trader DOES NOT use historical 1-min files** - it subscribes to **real-time tick data** from IBKR.

**However, context indicators CAN be used** (optional enhancement):
1. **Pre-market**: Run `process_context_indicators.py` to generate today's context
2. **At startup**: Load `context/SYMBOL_YYYYMMDD_context.json` for today
3. **During trading**: Use daily ATR, SMA-200, VWAP for filters
4. **Real-time bars**: Build 1-min bars from live ticks using BarBuffer

**Current Status**: Live trader does NOT load context files (uses real-time data only)

**Future Enhancement**: Load today's context at startup for filter consistency with backtest

**Example** (future implementation):
```python
# At trader startup
today = datetime.now().strftime('%Y-%m-%d')
context_file = f"backtest/data/context/{symbol}_{today}_context.json"

if os.path.exists(context_file):
    with open(context_file, 'r') as f:
        context = json.load(f)
    daily_atr = context['daily']['atr_14']
    daily_sma200 = context['daily']['sma_200']
else:
    # Fall back to calculating from real-time data
    daily_atr = calculate_atr_from_live_bars()
```

### Data Validation and Quality

**Verification Commands**:
```bash
cd /Users/karthik/projects/DayTrader/trader/backtest/data

# Count files
ls -1 *.json | wc -l          # Should be 574 1-min bar files
ls -1 context/*.json | wc -l  # Should be 198 context files

# Check quick scan coverage (should be 22 files each)
for stock in QQQ TSLA NVDA AMD PLTR SOFI HOOD SMCI PATH; do
  echo "$stock: $(ls -1 ${stock}_2025*_1min.json | wc -l)"
done

# Verify context file structure
cat context/AMD_20251031_context.json | python3 -m json.tool | head -50

# Check data quality
python3 -c "
import json
with open('AMD_20251031_1min.json', 'r') as f:
    bars = json.load(f)
print(f'Bars: {len(bars)}')  # Should be 390
print(f'First: {bars[0][\"date\"]}')  # Should be 09:30
print(f'Last: {bars[-1][\"date\"]}')  # Should be 16:00
"
```

**Quality Checks**:
- ✅ All 198 files created (9 stocks × 22 days)
- ✅ Each 1-min file has exactly 390 bars
- ✅ Field name is 'date' (not 'timestamp') - backtester compatible
- ✅ All context files have daily SMA-200 populated (250-day history)
- ✅ VWAP and opening range calculated correctly
- ✅ No missing data or gaps

### Data Expansion

**To add more dates or symbols**:

1. **Edit download_october_data.py** (lines 306-332):
```python
def scan_october_files(self, scanner_dir):
    quick_scan_stocks = ['QQQ', 'TSLA', 'NVDA', 'AMD', 'PLTR', 'SOFI', 'HOOD', 'SMCI', 'PATH']

    # Add more dates
    october_trading_days = [
        '2025-10-01', '2025-10-02', # ... existing dates
        '2025-11-01', '2025-11-02', # Add November days
    ]
```

2. **Run download**:
```bash
cd trader/data-downloader
python3 download_october_data.py
```

3. **Process context indicators**:
```bash
python3 process_context_indicators.py \
  --quick-scan \
  --start-date 2025-10-01 \
  --end-date 2025-11-30 \
  --use-ibkr
```

**IMPORTANT**: Always update BOTH 1-min bars AND context files together to maintain consistency.

## 📋 Requirements Specification

**Reference Document**: `trader/Automated Trading System for PS60 Strategy – Requirements Specification.md`

All trader implementation must follow the official requirements specification. This document is the source of truth for:
- Setup identification (Breakout, Bounce, Rejection/Fade)
- Trade confirmation logic (Volume surge, Momentum candle, Sustained break)
- Profit-taking rules (1R-based partials)
- Risk management (Min 2:1 R/R ratio)
- Slippage and commission simulation

**Implementation Status**: See `trader/REQUIREMENTS_IMPLEMENTATION_LOG.md` for detailed tracking of requirements implementation, test results, and development progress.

**Phase 1 (✅ COMPLETE - October 4, 2025)**:
- Min 2.0:1 risk/reward filter
- 1R-based partial profit-taking (profit = risk)
- Three-part confirmation logic (volume + momentum + sustained break)
- Slippage simulation (0.1% entry/exit, -1.2% stops)
- Commission costs ($0.005/share)
- **8-minute rule** (exit if no progress after 8 min, no partials taken)
- **Risk-based position sizing** (1% account risk per trade)
- **Hybrid entry strategy** (momentum breakout vs pullback/retest)
- Exit timestamp fix (correct market time tracking)
- Bounds checking in entry logic (prevents edge case crashes)
- **Relaxed momentum criteria** (1.3x volume, 0.8% candle - Oct 4 evening)
- **Entry position filter** (anti-chasing - skip if >70% of 5-min range)
- **Choppy filter** (anti-consolidation - skip if range <0.5× ATR)

**Phase 2 (✅ COMPLETE - October 13, 2025)**:
- **Volume sustainability filter removed** (was rejecting valid breakouts)
- **Delayed momentum detection** (re-check volume on every subsequent 1-min candle)
- **Dynamic target selection** (always use highest available target for room-to-run filter)
- **Continuous momentum monitoring** (check in WEAK_BREAKOUT_TRACKING and PULLBACK_RETEST states)

**Phase 4 (🔜 PLANNED - Future Enhancements)**:
- Bounce setup detection (infrastructure ready, logic not implemented)
- Rejection/fade setup detection (infrastructure ready, logic not implemented)
- Trailing stop mechanism (not implemented)
- Dynamic stop adjustment based on crossed targets (planned)
- Live paper trading validation
- Parameter optimization based on results
- Production deployment

## PS60 Trading Methodology (Scanner-Driven Implementation)

This implementation focuses on **Scenario 1: Trading Scanner-Identified Pivots**. The scanner runs pre-market and identifies resistance/support levels from historical data. The trader monitors these pre-defined pivots and enters immediately when they break.

### Core Concepts

**Scanner-Defined Pivots**: The scanner analyzes historical data and identifies:
- **Resistance** (long pivot): Key level tested multiple times, distance to breakout
- **Support** (short pivot): Key support level, downside risk
- **Targets**: T1, T2, T3 calculated using measured moves
- **Risk/Reward**: Pre-calculated ratios for each setup

**Trading Approach**:
- Scanner runs **pre-market** (8:00 AM) or previous evening
- Pivots are **already defined** before market open
- Trader monitors **tick-by-tick** from 9:30 AM onwards
- Enter **immediately** when scanner-identified pivot breaks
- No need to wait for 60-minute candles (pivots already known)

**Supply & Demand Theory**: Stocks move from resistance to resistance (supply) or support to support (demand). Only trade when there's "air" to the next technical level (scanner calculates this as `dist_to_R%` and `dist_to_S%`).

### Entry Logic (Simplified)

**Long Entry**:
```
IF current_price > scanner['resistance']
AND not already in position
AND dist_to_R% was < 3% (reasonable distance at scan time)
THEN enter_long()
```

**Short Entry**:
```
IF current_price < scanner['support']
AND not already in position
AND dist_to_S% was < 3%
THEN enter_short()
```

**No waiting for hourly candles** - pivots are pre-defined by scanner analysis of historical support/resistance levels.

### Risk Management Rules (CRITICAL)

1. **Initial Stop**: Place at or just beyond pivot price (entry level)
2. **Risk-Based Position Sizing**: Calculate shares based on 1% account risk
   - Risk Amount = Account Size × 1%
   - Stop Distance = abs(Entry - Stop)
   - Shares = Risk Amount / Stop Distance (capped at 10-1000 shares)
3. **Take Partial Profits at 1R**: Sell 50% when profit equals risk (1R gain)
4. **Move Stop to Breakeven**: After taking partial, stop on remainder goes to entry price
5. **8-Minute Rule** (CRITICAL): If no progress (gain < $0.10/share) after 8 minutes AND no partials taken, exit immediately
   - Prevents "reload seller/buyer" scenarios
   - Only applies before first partial (once profitable, let it run)
   - Saves ~$2,300-3,000 per month on quick losers
   - May exit 1-2 slow starters per month (acceptable trade-off)
6. **Scale Out**: Take additional 25% at target levels (2R, 3R)
7. **Runner Management**: Trail stop on final 25%, close by EOD

### Gap Handling (CRITICAL - October 4, 2025)

**Problem**: Scanner data is generated 8-13 hours before market open (pre-market or previous evening). When a stock gaps overnight, the scanner's resistance/support levels may already be breached at the open, invalidating the setup.

**Example**:
- Scanner runs at 8 PM on Oct 1st: CLOV @ $2.70, resistance $3.24 (19.87% away)
- Stock gaps up at 9:30 AM on Oct 2nd: Opens at $3.30 (already through resistance)
- Problem: Gap "ate up" the move - insufficient room to target left

**Solution - Smart Gap Filter**:

The strategy implements a three-tier gap filter:

1. **Small Gaps (<1% through pivot)**: Allow trade
   - Gap is insignificant, pivot is still valid
   - Enter normally when price breaks pivot

2. **Large Gaps (>1%) with Room (>3% to target)**: Allow trade
   - Gap is significant BUT plenty of upside remains
   - Enter on continued strength after gap

3. **Large Gaps (>1%) without Room (<3% to target)**: Skip trade
   - Gap ate up most of the move
   - Risk/reward no longer favorable
   - **This is the most common reason to skip a scanner setup**

**Implementation**: `trader/strategy/ps60_strategy.py:180-250`
- Three-tier logic: small gaps (<1%), large gaps with room (>3% to target), large gaps without room (skip)
- Configuration: `trader_config.yaml` (enable_gap_filter, max_gap_through_pivot: 1.0%, min_room_to_target: 3.0%)

**Real-World Impact**:

Without gap filter:
- CLOV on Oct 2: Would enter at $3.30, target $3.40 (only 3% gain, too risky)

With gap filter:
- CLOV skipped: "Gap 1.9% through pivot, only 3.1% to target" (borderline case)
- Protects capital from low R/R setups after overnight gaps

**Code Reusability - Backtester & Live Trading**:

The gap filter logic is implemented in the **shared PS60Strategy class** (trader/strategy/ps60_strategy.py), ensuring identical behavior between backtesting and live trading:

- **Live Trader** (trader.py): Calls `strategy.should_enter_long()` which checks gap filter
- **Backtester** (backtest/backtester.py): Calls same `strategy.should_enter_long()` method
- **Single source of truth**: All trading logic lives in PS60Strategy class
- **Guaranteed consistency**: Backtest results accurately predict live trading behavior

**Gap Filtering Workflow** (October 4, 2025):

The system now performs **two-stage gap filtering**:

1. **At Market Open (9:30 AM)** - Pre-filter watchlist:
   ```python
   # Get opening prices for all stocks
   opening_prices = get_opening_prices(watchlist)  # {symbol: opening_price}

   # Filter out stocks where gap ate up the move
   filtered_watchlist, gap_report = strategy.filter_scanner_for_gaps(
       watchlist,
       opening_prices
   )
   ```

   This removes stocks **before** monitoring begins, saving resources.

2. **During Trading** - Entry validation:
   ```python
   # When price breaks pivot, double-check gap didn't invalidate setup
   should_enter, reason = strategy.should_enter_long(stock, current_price, attempts)
   ```

   This catches any edge cases where gaps occur during the trading session.

**Gap Filter Actions**:
- **SKIPPED**: Stock removed from watchlist (gap >1% through pivot, <3% room to target)
- **ADJUSTED**: Stock kept but noted (gap >1% but sufficient room remains)
- **NOTED**: Significant gap (>2%) reported for awareness

### Hybrid Entry Strategy (October 4, 2025)

The strategy uses a **two-tier entry approach** based on breakout strength:

#### Type 1: MOMENTUM BREAKOUT (Immediate Entry)
**Criteria**:
- 1-minute candle closes above resistance ✅
- Volume ≥ 2.0x average ✅
- Candle size ≥ 1.5% OR candle range ≥ 2x ATR ✅

**Action**: Enter immediately after candle close (no pullback needed)

**Example**: TSLA breaks $445 resistance with 3.5x volume and 2.1% candle → Enter at $445.50

#### Type 2: PULLBACK/RETEST (Patient Entry)
**Criteria**:
- 1-minute candle closes above resistance ✅
- Volume < 2.0x OR small candle (weak breakout) ❌

**Action**: Wait for pullback within 0.3% of pivot, then enter on re-break with 1.2x volume

**Example**: AMD breaks $162 resistance with 1.1x volume → Wait for pullback to $162.20 → Enter on re-break

**Implementation**: `trader/strategy/ps60_strategy.py` (lines 697-857)

**Why This Works**:
- Strong breakouts capture immediate momentum moves (TSLA, COIN)
- Weak breakouts require patience and confirmation (AMD, PLTR)
- Reduces whipsaws on weak initial breaks
- Maximizes entries on high-conviction setups

**Performance**:
- Oct 1-4: 42 trades, 23.8% win rate, +$5,461
- Most trades were pullback/retest (no stocks met momentum criteria)
- 8-minute rule prevents weak pullbacks from becoming large losses

**Example Output**:
```
GAP ANALYSIS AT MARKET OPEN (9:30 AM)
================================================================================
❌ CLOV: Gap up 3.4% through resistance, only 1.5% to target
⚠️  TSLA: Gap up 2.1%, but 5.2% to target remains
📊 AMC: Gap +2.3%, now 0.8% from pivot

FINAL WATCHLIST: 2 setups (1 removed by gap filter)
```

## Filter System (October 5, 2025)

**Complete Reference**: `trader/FILTER_DOCUMENTATION.md` (300+ lines with detailed explanations)

The strategy uses an **11-filter system** applied in stages: pre-entry screening, entry decision, and exit management.

### Critical Filters

**Choppy Market Filter** ⭐ - Block if 5-min range < 0.5× ATR  
Impact: Saved $15k/month, win rate 6.7% → 40%+ in trending conditions

**Room-to-Run Filter** ⭐⭐⭐ - Block if (target - entry) / entry < 1.5%  
Impact: 19x P&L improvement by blocking marginal setups (PLTR Oct 1: 0.61% room blocked)

**Sustained Break Logic** - Price holds above/below pivot for 2 min with volume  
Use case: Catches "slow grind" breakouts with weak candles but sustained hold

### Filter Configuration

All filters independently enabled/disabled via `trader/config/trader_config.yaml`:

| Filter | Default | Applied To | Key Impact |
|--------|---------|------------|------------|
| Choppy Filter | true | All entries | -$15k/month saved |
| Room-to-Run | true | Pullback/sustained | 19x P&L improvement |
| Gap Filter | false | Pre-entry | Overnight gap handling |
| Max Attempts | 2 | Entry decision | Prevent overtrading |
| Index Shorts | true (avoid) | Entry decision | +$700/day saved |
| 8-Minute Rule | true | Exit decision | +$2,334/month net |

**Full Documentation**: See `trader/FILTER_DOCUMENTATION.md`, `trader/PLTR_DEBUG_SESSION.md`, and `trader/STRATEGY_EVOLUTION_LOG.md`


## Scanner Module (stockscanner/)

### Running the Scanner

```bash
cd stockscanner

# Quick scan (top 8 movers)
python scanner.py --category quick

# Full scan
python scanner.py

# Specific symbols
python scanner.py --symbols TSLA NVDA AMD

# By category
python scanner.py --category mega_tech
python scanner.py --category indices
```

### Scanner Output Format

**JSON/CSV files in `output/`** containing:
- `symbol` - Stock ticker
- `close` - Last close price
- `resistance` - Key resistance level (pivot high)
- `support` - Key support level (pivot low)
- `dist_to_R%` - Distance to resistance (%)
- `dist_to_S%` - Distance to support (%)
- `breakout_reason` - Why level is significant (e.g., "Tested 7x | 5-day high")
- `target1`, `target2`, `target3` - Price targets using measured moves
- `downside1`, `downside2` - Downside targets if support breaks
- `potential_gain%` - % gain to target1
- `risk%` - % risk to support
- `risk_reward` - R/R ratio
- `rvol` - Relative volume
- `atr%` - Average True Range %
- `score` - Overall setup score
- `setup` - Human-readable setup description

### Scanner Data Example

```json
{
  "symbol": "TSLA",
  "close": 442.11,
  "resistance": 444.77,
  "support": 432.63,
  "dist_to_R%": 0.6,
  "dist_to_S%": 2.14,
  "breakout_reason": "Tested 7x | 5-day closing high",
  "target1": 450.84,
  "target2": 456.91,
  "target3": 464.41,
  "risk_reward": 1.56,
  "score": 55,
  "setup": "High volatility 4.6% | Near breakout (0.6%) | Uptrend"
}
```

## Scanner Validation System (October 6, 2025)

### Overview

A comprehensive validation and enhanced scoring system that validates scanner predictions against actual market outcomes and uses machine learning insights to improve setup selection.

### Key Achievement

**Enhanced scoring achieves 70% accuracy in top 10 ranked setups** (vs 33% baseline).

### Core Components

1. **validate_scanner.py**: Validates scanner predictions using IBKR historical data
   - Checks if resistance/support levels were broken
   - Determines if targets were hit
   - Classifies outcomes: SUCCESS, FALSE_BREAKOUT, NO_BREAKOUT

2. **analyze_validation_metrics.py**: Deep analysis of validation patterns
   - Identifies distinguishing factors between winners and false breakouts
   - **Critical Discovery**: Pivot width predicts success
     - Winners: 2.51% median pivot width
     - False Breakouts: 4.92% median pivot width
     - **Rule**: Prefer tight pivots < 3.5%

3. **enhanced_scoring.py**: Improved scoring based on validation insights
   - Penalizes wide pivots (>7%): -30 points
   - Penalizes index ETFs: -40 points (100% false breakout rate)
   - Penalizes high-vol stocks: -25 points (75% false breakout rate)
   - Rewards tight pivots (<2.5%): +20 points
   - LONG bias: +10 points (40% vs 25% success)

4. **compare_scoring_accuracy.py**: Measures predictive accuracy
   - Validates enhanced scoring against actual outcomes
   - Top 10 ranked: 70% accuracy
   - Score separation: +16.2 points between winners/losers

### Validation Workflow

```bash
# End-of-day validation (4:15 PM ET)
python3 validate_scanner.py 2025-10-07 scanner_results_20251007.csv

# Analyze metrics (4:30 PM ET)
python3 analyze_validation_metrics.py validation_20251007.csv

# Apply enhanced scoring for next day (morning)
python3 enhanced_scoring.py scanner_results_20251007.csv rescored_20251007.csv
```

### Key Insights from Oct 6, 2025 Validation

**Critical Discovery**: Pivot width predicts success - tight pivots (2.51% median) succeed, wide pivots (4.92% median) fail. Top 10 ranked setups achieve 70% accuracy vs 33% baseline. LONG setups (40% success) outperform SHORTs (25%). Index ETFs and high-vol stocks underperform.

### Integration with Trading

**For Live Trading**:
1. Run scanner pre-market (8:00 AM ET)
2. Apply enhanced scoring (8:30 AM ET)
3. Focus on top 10 ranked setups
4. Filter by pivot width < 3.5%
5. Use LONGS ONLY (40% vs 25% success)
6. **START TRADER AT 9:30 AM ET SHARP**

**Expected Performance**:
- Top 10 filtered setups: 70% success rate
- Estimated daily P&L: $4,000-8,000 (vs $0 with late start)

### Documentation

- `scanner_validation/README.md`: Complete system guide
- `scanner_validation/DAILY_VALIDATION_GUIDE.md`: Daily workflow
- `SCANNER_VALIDATION_SUMMARY_YYYYMMDD.md`: Validation reports
- `TRADING_PLAN_YYYYMMDD.md`: Daily trading plans

## Backtesting with IBKR Historical Data

### Overview

The backtesting module uses **1-minute historical bars** from IBKR to simulate tick-by-tick trading. This provides sufficient resolution to detect pivot breaks while having years of historical data available.

### Why 1-Minute Bars (Not Tick Data)

**1-Minute Bars**:
- ✅ Years of historical data available
- ✅ Sufficient resolution for pivot break detection
- ✅ Faster processing (fewer data points)
- ✅ No pagination complexity
- ⚠️ Assumes entry at bar close (minor inaccuracy)

**Tick-by-Tick Data**:
- ✅ Most accurate simulation
- ❌ Only 30-60 days history available
- ❌ Limited to 1000 ticks per request (requires pagination)
- ❌ Much slower processing
- ❌ Rate limited (60 requests per 10 minutes)

### Backtest Architecture

**Architecture**: See `trader/backtest/backtester.py` for full implementation.

### Running Backtests

```bash
cd trader

# Backtest single day
python backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20250930.json \
  --date 2025-09-30

# Backtest date range
python backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results.json \
  --start-date 2025-09-01 \
  --end-date 2025-09-30

# Generate performance report
python backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results.json \
  --date 2025-09-30 \
  --report backtest_report.html
```

### Backtest Validation Strategy

1. **Historical Scanner Results**: Run scanner on historical dates to get past pivots
2. **Fetch Historical Bars**: Use IBKR API to get 1-min bars for those dates
3. **Simulate Trading**: Process bars sequentially, enter/exit per PS60 rules
4. **Compare with Actual**: Validate backtest results match expected behavior
5. **Iterate**: Refine entry/exit logic based on backtest findings

### Key Backtest Metrics

```python
# Performance metrics to track
metrics = {
    'total_trades': len(trades),
    'win_rate': winners / total_trades,
    'profit_factor': gross_profit / abs(gross_loss),
    'avg_winner': avg_winning_trade,
    'avg_loser': avg_losing_trade,
    'avg_trade': total_pnl / total_trades,
    'max_drawdown': calculate_max_drawdown(trades),
    'sharpe_ratio': calculate_sharpe(returns),
    '8min_rule_exits': count_by_reason('8MIN_RULE'),  # Updated Oct 4, 2025
    'stop_exits': count_by_reason('STOP'),
    'target_exits': count_by_reason('TARGET'),
    'trail_stop_exits': count_by_reason('TRAIL_STOP'),
    'eod_exits': count_by_reason('EOD')
}
```

### Backtest Results Summary

**Latest**: October 1-4, 2025: 42 trades, 23.8% win rate, +$5,461 (+5.46% monthly)
**September 2025**: 183 trades, 39.9% win rate, +$8,895 (+8.9% monthly)
**Configuration**: 8-min rule, risk-based sizing, hybrid entry

**Complete results**: See `trader/backtest/monthly_results/` and `trader/PROGRESS_LOG.md`

### IBKR Historical Data Limits

- **Bar data**: Available for several years back
- **Rate limits**: ~60 historical data requests per 10 minutes
- **Concurrent requests**: Max 50 simultaneous
- **Pacing**: Add 0.5-1 second delay between requests

### Project Structure with Backtest

```
trader/
├── backtest/
│   ├── backtester.py           # Main backtest engine
│   ├── historical_data.py      # IBKR data fetcher
│   ├── performance_metrics.py  # Calculate metrics
│   └── reports.py             # Generate HTML reports
├── trader.py                   # Live trader
├── position_manager.py
├── order_executor.py
└── config/
    ├── trader_config.yaml
    └── backtest_config.yaml
```

## Key Commands (Once Built)

### Scanner Commands
```bash
cd stockscanner
python scanner.py --category quick  # Generate daily watchlist
```

### Trader Commands

```bash
cd trader

# Backtest single day
python3 backtest/backtester.py --date 2025-09-30 \
  --scanner ../stockscanner/output/scanner_results_20250930.json \
  --account-size 100000

# Live paper trading (RECOMMENDED - start here)
python3 trader.py

# With custom config
python3 trader.py --config config/trader_config.yaml
```

### 🚦 Session Management

**Start**: `cd trader && python3 trader.py`
- Automatic cleanup: cancels orders, closes orphaned positions
- Loads today's scanner results, subscribes to market data

**Stop**: Press `Ctrl+C` for graceful shutdown
- Closes all positions, saves state, generates P&L report

**Account Size**: $50,000 (configured in `trader_config.yaml`)

### Daily Trading Workflow

**Morning (8:00-9:30 AM):**
1. Run scanner: `cd stockscanner && python3 scanner.py --category quick`
2. Review scanner results in `stockscanner/output/scanner_results.json`
3. Start TWS/Gateway on port 7497 (paper trading)
4. Start trader: `cd trader && python3 trader.py`
   - Automatic cleanup runs at startup
   - Closes any orphaned positions from previous day
   - Loads today's scanner results

**Trading Hours (9:30 AM - 4:00 PM):**
5. Trader monitors pivots and executes trades automatically
6. Entry window: 9:45 AM - 3:00 PM ET
7. EOD close: 3:55 PM ET (all positions auto-closed)
8. **To stop early:** Press **Ctrl+C** for graceful shutdown

**After Market (4:00+ PM):**
9. Graceful shutdown completes automatically at EOD
10. Review logs in `trader/logs/trader_YYYYMMDD.log`
11. Review trades in `trader/logs/trades_YYYYMMDD.json`
12. Compare performance vs backtest expectations
13. **Generate session analysis report** (see Session Reporting section below)

**See [Session Management](#-session-management-october-13-2025) for detailed startup/shutdown procedures.**

---

## 🚀 Complete Usage Guide: Live Trading, Backtesting & Validation

### 1. Starting the Live Trader

**Prerequisites:**
- ✅ TWS/Gateway running on port 7497 (paper trading) or 7496 (live)
- ✅ Scanner results generated for today: `stockscanner/output/scanner_results_YYYYMMDD.json`
- ✅ Account size configured in `trader/config/trader_config.yaml` (default: $50,000)

**Command:**
```bash
cd /Users/karthik/projects/DayTrader/trader
python3 trader.py
```

**What Happens:**
1. **Automatic Cleanup**:
   - Cancels all pending orders
   - Closes any orphaned positions from previous sessions
   - Verifies clean slate before starting

2. **Scanner Loading**:
   - Automatically loads `scanner_results_YYYYMMDD.json` based on today's date
   - Example: On 2025-10-28, loads `scanner_results_20251028.json`
   - Filters setups by score, R/R ratio, and gap analysis

3. **Market Data Subscription**:
   - Subscribes to real-time data for all watchlist symbols
   - Monitors tick-by-tick price action

4. **Trading Session**:
   - Entry window: 9:45 AM - 3:00 PM ET
   - EOD close: 3:55 PM ET (automatic)
   - All positions closed by market close

**Monitoring the Session:**
```bash
# Watch live logs (in another terminal)
tail -f logs/live_session_YYYYMMDD.log

# Filter for trades only
tail -f logs/live_session_YYYYMMDD.log | grep -E "🟢|🔴|ENTERING|EXIT|P&L"

# Check watchlist status
grep "WATCHLIST\|Subscribed" logs/live_session_YYYYMMDD.log
```

**Stopping the Trader:**
```bash
# Graceful shutdown (recommended)
Ctrl+C

# What happens:
# - Closes all open positions
# - Saves session state
# - Generates P&L summary
# - Disconnects from IBKR
```

**Output Files:**
- `logs/trader_YYYYMMDD.log` - Detailed trading log with all decisions
- `logs/trades_YYYYMMDD.json` - JSON trade records
- `logs/live_entry_decisions_YYYYMMDD.json` - All entry attempts with filter results
- `logs/trader_state.json` - Session state (for recovery)

---

### 2. Running Backtests

**Prerequisites:**
- ✅ Scanner results file for the date you want to test
- ✅ IBKR connection (for fetching historical data)
- ✅ Historical data cached in `backtest/data/SYMBOL_YYYYMMDD_*.json` (or will be downloaded)

**Basic Backtest (Single Day):**
```bash
cd /Users/karthik/projects/DayTrader/trader

# Backtest a specific date
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251021.json \
  --date 2025-10-21 \
  --account-size 50000
```

**Output:**
```
================================================================================
BACKTEST RESULTS
================================================================================

📊 TRADE SUMMARY:
  Total trades: 8
  Winners: 1 (12.5%)
  Losers: 7 (87.5%)

💰 P&L ANALYSIS:
  Total P&L: $-2,478.87
  Avg trade: $-309.86
  Avg winner: $15.92
  Avg loser: $-356.40
  Profit factor: 0.01

⏱️  TRADE DURATION:
  Avg duration: 4.9 minutes

🎯 EXIT REASONS:
  7MIN_RULE: 3 trades
  STOP: 5 trades
```

**Advanced Options:**
```bash
# Backtest with custom account size
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251021.json \
  --date 2025-10-21 \
  --account-size 100000

# Backtest will use cached data if available, otherwise downloads from IBKR
```

**Output Files:**
- `backtest/results/backtest_trades_YYYYMMDD.json` - All trade records
- `backtest/results/backtest_entry_decisions_YYYYMMDD.json` - Complete entry decision log
- `backtest/logs/backtest_YYYYMMDD_HHMMSS.log` - Detailed backtest log

**Understanding Entry Decisions File:**
```json
{
  "backtest_date": "2025-10-21",
  "total_attempts": 265,
  "entered": 8,
  "blocked": 257,
  "blocks_by_filter": {
    "unknown": 134,
    "volume_filter": 72,
    "cvd_monitoring": 32,
    "cvd_price_validation_failed": 17,
    "room_to_run_filter": 2
  }
}
```

This shows:
- **97% block rate** - Filters are working (maybe too strict?)
- **Volume filter blocking 28%** of attempts
- **CVD monitoring blocking 12.5%** - Never confirms

---

### 3. Running Validation Analysis

**Prerequisites:**
- ✅ Scanner results file
- ✅ Backtest entry decisions file (generated from backtest)
- ✅ IBKR connection (for fetching actual market outcomes)

**Basic Validation:**
```bash
cd /Users/karthik/projects/DayTrader/trader

# Validate a backtest against actual market outcomes
python3 validation/validate_market_outcomes.py \
  --scanner ../stockscanner/output/scanner_results_20251021.json \
  --entry-log backtest/results/backtest_entry_decisions_20251021.json \
  --date 2025-10-21 \
  --account-size 50000
```

**What It Does:**
1. **Loads scanner setups** - What stocks were identified pre-market
2. **Loads entry decisions** - What the strategy decided (ENTERED or BLOCKED)
3. **Fetches market data** - Gets actual 1-minute bars from IBKR for the day
4. **Classifies outcomes**:
   - ✅ **WINNER**: Price moved ≥2% in breakout direction
   - ⚠️ **MODERATE**: Price moved 1-2%
   - ❌ **STOPPED_OUT**: Would have hit stop (0.5-1% move)
   - 🔴 **CHOPPY**: False breakout (<0.5% move)

5. **Generates comprehensive report** showing:
   - **Missed winners**: Setups that were BLOCKED but became winners
   - **Correct blocks**: Setups that were BLOCKED and failed (good filter!)
   - **Bad entries**: Setups that were ENTERED but lost
   - **Correct entries**: Setups that were ENTERED and won

**Output:**
```
================================================================================
VALIDATION REPORT - 2025-10-21
================================================================================

DECISION ACCURACY
  Correct Entries: 1/8 (12.5%)
  Correct Blocks: 12/257 (4.7%)
  Overall Accuracy: 13/265 (4.9%)

⭐⭐⭐⭐⭐ MISSED WINNERS (High Priority)
  1. NVDA SHORT (+8.5%)
     Entry confirmation sequence (4 attempts):
       Attempt 1 [State Init]: Breakout detected, waiting for candle close
       Attempt 2 [Filter Result]: BLOCKED by volume_filter (0.93x < 1.0x)
       Attempt 3 [State Init]: Breakout detected, waiting for candle close
       Attempt 4 [Filter Result]: BLOCKED by volume_filter (0.97x < 1.0x)

     Analysis: Volume filter too strict - missed by 0.03x!
     Recommendation: Lower volume threshold from 1.0x to 0.75x

  2. SMCI LONG (+12.2%)
     Entry confirmation sequence (6 attempts):
       Attempt 1-6: All blocked by volume filter (0.55x-0.72x)

     Analysis: Consistent volume rejection across all attempts
     Recommendation: Volume threshold needs adjustment
```

**Output Files:**
- `validation/reports/validation_results_YYYYMMDD.json` - Machine-readable validation data
- Terminal output with color-coded analysis

---

### 4. Complete Analysis Workflow

**Daily Post-Market Analysis (Recommended):**

```bash
cd /Users/karthik/projects/DayTrader/trader

# Step 1: Run backtest for today
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_20251021.json \
  --date 2025-10-21 \
  --account-size 50000

# Step 2: Validate backtest against market outcomes
python3 validation/validate_market_outcomes.py \
  --scanner ../stockscanner/output/scanner_results_20251021.json \
  --entry-log backtest/results/backtest_entry_decisions_20251021.json \
  --date 2025-10-21 \
  --account-size 50000

# Step 3: Review validation report
cat validation/reports/validation_results_20251021.json | python3 -m json.tool

# Step 4: Generate session analysis (if live trading)
# Ask Claude: "analyze today's session" (see Session Reporting section)
```

**Weekly/Monthly Analysis:**
```bash
# Run backtests for date range
for date in 20251021 20251022 20251023; do
  python3 backtest/backtester.py \
    --scanner ../stockscanner/output/scanner_results_$date.json \
    --date ${date:0:4}-${date:4:2}-${date:6:2} \
    --account-size 50000
done

# Aggregate results
python3 validation/analyze_weekly_performance.py --start 2025-10-21 --end 2025-10-25
```

---

### 5. Quick Reference Commands

**Start Live Trading:**
```bash
cd /Users/karthik/projects/DayTrader/trader && python3 trader.py
```

**Run Today's Backtest:**
```bash
cd /Users/karthik/projects/DayTrader/trader && \
python3 backtest/backtester.py \
  --scanner ../stockscanner/output/scanner_results_$(date +%Y%m%d).json \
  --date $(date +%Y-%m-%d) \
  --account-size 50000
```

**Validate Today's Backtest:**
```bash
cd /Users/karthik/projects/DayTrader/trader && \
python3 validation/validate_market_outcomes.py \
  --scanner ../stockscanner/output/scanner_results_$(date +%Y%m%d).json \
  --entry-log backtest/results/backtest_entry_decisions_$(date +%Y%m%d).json \
  --date $(date +%Y-%m-%d) \
  --account-size 50000
```

**Monitor Live Session:**
```bash
tail -f /Users/karthik/projects/DayTrader/trader/logs/live_session_$(date +%Y%m%d).log
```

**Check Today's Trades:**
```bash
cat /Users/karthik/projects/DayTrader/trader/logs/trades_$(date +%Y%m%d).json | python3 -m json.tool
```

---

## 📊 Session Reporting (October 23, 2025)

### Automated Session Analysis

**When user requests**: "analyse today's session" or "give me a report for today"

**Use this standardized process**:

1. **Follow Requirements Document**: `trader/TRADING_SESSION_REPORT_REQUIREMENTS.md`
2. **Generate Comprehensive Report**: `trader/analysis/TRADING_SESSION_ANALYSIS_YYYYMMDD.md`
3. **Include All 10 Required Sections**:
   - Executive Summary
   - Trade Inventory (complete details per trade)
   - Filter Analysis (all filter decisions with values)
   - Blocked Entry Analysis
   - CVD Activity Log (with price validation checks)
   - Filter Performance Summary
   - State Machine Path Analysis
   - Comparative Analysis
   - Recommendations
   - Appendices

### Report Requirements

**Data Sources**:
- `trader/logs/trader_YYYYMMDD.log` - Main trading log
- `trader/logs/trades_YYYYMMDD.json` - Trade records (if exists)
- `trader/logs/trader_state.json` - State recovery data
- `trader/config/trader_config.yaml` - Configuration
- `stockscanner/output/scanner_results_YYYYMMDD.json` - Scanner data

**For Each Trade, Document**:
- Entry/exit times, prices, shares, P&L
- Entry path (MOMENTUM / PULLBACK_RETEST / CVD_MONITORING)
- All filter checks with actual values:
  - Gap, Choppy, Stochastic, Room-to-Run filters
  - Volume, Candle Size filters
  - **CVD Price Validation** (verify Oct 23 fix)
  - CVD imbalance data (buy/sell volumes, %)
- State transitions through entry state machine
- Resistance/Support levels
- Exit reason and partials taken

**For Blocked Entries, Document**:
- Symbol, time, price, side
- Blocking filter name and reason
- State at time of block
- Filter values that caused rejection

**For CVD Activity, Document**:
- All CVD_MONITORING events
- CVD signals detected (imbalance %, buy/sell volumes)
- **CVD Price Validation checks** (CRITICAL):
  - Price at signal vs pivot price
  - Validation result (PASS/BLOCK)
  - Rejection reason if blocked
- Final outcome (ENTERED/BLOCKED/RESET/TIMEOUT)

**Filter Performance Metrics**:
- Activation count per filter
- Block count per filter
- Pass rate per filter
- Most/least active filters

**Output Format**: Clean Markdown with tables, organized by the 10 required sections

**Acceptance Criteria**:
- ✅ All trades fully documented
- ✅ All filter decisions extracted with values
- ✅ CVD price validation fix verified
- ✅ Recommendations are data-driven
- ✅ Report is complete and actionable

**File Naming**: `trader/analysis/TRADING_SESSION_ANALYSIS_YYYYMMDD.md`

**Reference**: See `trader/TRADING_SESSION_REPORT_REQUIREMENTS.md` for complete specification

---

## Live Trader Implementation (October 2025)

**Status**: ✅ LIVE - In Paper Trading

### Key Features
- Max 2 attempts per pivot, no trading before 9:45 AM or after 3:00 PM
- Skip index shorts (SPY, QQQ, DIA, IWM)
- 50% partial on first move, 25% at target1, 25% runner
- 8-minute rule, close all at 3:55 PM
- Position sizing: 1% risk per trade, stops at pivot

### Configuration
**Account**: $50,000 (paper trading)  
**Risk**: 1% per trade, max 5 positions  
**Entry Window**: 09:45-15:00 ET  
**Config**: `trader/config/trader_config.yaml`

### Paper Trading Results
**September 2025**: 183 trades, 39.9% win rate, +$8,895 (+8.9% monthly)  
**October 1-4**: 42 trades, 23.8% win rate, +$5,461 (+5.46% monthly)

**Complete implementation details**: See `trader/PROGRESS_LOG.md`


## Historical Analysis

**LONGS ONLY Testing** (Oct 4, 2025): Scanner support levels found unreliable (78.6% shorts would still lose with correct stops). Configuration available: `enable_shorts: false` in `trader_config.yaml`.

**Details**: See `trader/PROGRESS_LOG.md` and `trader/analyze_short_stops.py`


## Critical Implementation Rules

### DO NOT:
1. **NEVER create simplified/embedded versions without asking** - Always use the actual production code
2. **NEVER make architectural decisions independently** - Always ask the user first
3. **NEVER create duplicate/alternative implementations** - Update existing code in place
4. Use fake data - only real IBKR market data
5. Skip the 5-7 minute rule - it prevents large losses
6. Skip partial profit-taking - critical for cash flow

### 🚨 CRITICAL LESSON LEARNED - SCANNER DUPLICATION BUG 🚨

**THIS MISTAKE HAS BEEN MADE TWICE - IT MUST NEVER HAPPEN AGAIN**

#### Incident #1 (October 1, 2025):
**Problem**: Created an "embedded scanner" inside `run_monthly_backtest.py` instead of using the production scanner from `stockscanner/scanner.py`

**Impact**:
- Embedded scanner: -$7,986 P&L (33.6% win rate)
- Production scanner: **+$8,895 P&L (39.9% win rate)**
- **Difference**: $16,881 swing due to using simplified code!

#### Incident #2 (October 3, 2025):
**Problem**: SAME MISTAKE - `run_monthly_backtest.py` still using embedded `HistoricalScanner` class

**Impact**:
- Embedded scanner: -$56,362 P&L (26.8% win rate)
- Production scanner: **+$8,895 P&L (39.9% win rate)**
- **Difference**: $65,257 swing - CATASTROPHIC!

**Root Cause**: Took initiative to "simplify" without asking, creating inferior duplicate logic

**Lesson**: **ALWAYS ask before creating ANY alternative/simplified versions**. The production code exists for a reason - use it. If there's a problem (like IBKR connection issues), ask the user rather than creating workarounds.

### 🛑 MANDATORY RULE - NO EXCEPTIONS:

When implementing features that need existing functionality (scanner, strategy, position manager, etc.), **ALWAYS**:

1. ✅ **Import and use the actual production module** from its original location
2. ✅ **Ask the user** if modifications are needed
3. ✅ **Verify the code you're using** matches the production version
4. ❌ **NEVER create embedded/simplified versions** - this is BANNED
5. ❌ **NEVER assume simplification is acceptable** - always ask first
6. ❌ **NEVER duplicate logic** that already exists in production code

**If you find yourself copying code or creating a "simpler version":**
- **STOP IMMEDIATELY**
- **Ask the user** if this is the right approach
- **Explain why** you think duplication is needed
- **Wait for approval** before proceeding
5. Allow stops to be moved wider - discipline is key
6. Hold positions overnight - PS60 is day trading only
7. Chase trades - only enter when scanner pivot breaks
8. Wait for 60-minute candles - scanner pivots are pre-defined, enter on tick break
9. Recalculate resistance/support - use scanner values exactly
10. Trade stocks not in scanner output - scanner did the pre-qualification

### 📝 DOCUMENTATION MAINTENANCE:

**CRITICAL**: After completing any major implementation, bug fix, or system enhancement:

1. ✅ **Update `trader/PROGRESS_LOG.md`** with:
   - Date and status of implementation
   - Problem description
   - Solution implemented
   - Files created/modified
   - Impact and results
   - Documentation references

2. ✅ **Create standalone documentation** (if needed) for:
   - New systems (e.g., IBKR_RESILIENCE_COMPLETE.md)
   - Complex integrations (e.g., BARBUFFER_INTEGRATION.md)
   - Usage guides (e.g., LOGGING_GUIDE.md)

3. ✅ **Update CLAUDE.md** to reference new documentation

4. ✅ **Create detailed explanations** in `trader/explained/` for:
   - Complex algorithms or filters (e.g., VOLUME_FILTER_EXPLAINED.md)
   - User questions requiring in-depth clarification
   - Technical concepts that benefit from visual diagrams
   - System behavior explanations with examples

   **Format**: Use markdown with visual diagrams, code examples, and real trade examples
   **Naming**: `CONCEPT_NAME_EXPLAINED.md` (e.g., `VOLUME_FILTER_EXPLAINED.md`)
   **Purpose**: Bridge the gap between technical implementation and user understanding

**Why**: The progress log serves as the single source of truth for all implementation history, making it easy to understand the project's evolution and decisions. The explained folder provides deep dives into specific concepts when users need clarification.

### ALWAYS:
1. Use IBKR API exclusively for market data and execution
2. Implement strict stop discipline (no exceptions)
3. Take partial profits on first favorable move (50% on 0.25-0.75 gain)
4. Move stops to breakeven after partial
5. Close all positions by 15:55 ET (5 min before close)
6. Validate scanner data before trading (check file exists, parse correctly)
7. Log all trades with entry/exit reasoning
8. Implement the 5-7 minute rule for all trades
9. Calculate position size based on stop distance (risk = entry - pivot)
10. Use scanner pre-defined pivots (resistance/support) - no manual calculations
11. Enter immediately when pivot breaks - monitor tick-by-tick
12. Respect scanner filters (only trade stocks with score > 50, R/R > 1.5)

### Testing Strategy
1. **Unit tests**: Test each component (position manager, order executor, risk rules)
2. **Paper trading**: Minimum 2-4 weeks before live
3. **Backtest validation**: Compare against historical scanner results
4. **Manual verification**: Watch first trades execute and verify PS60 compliance

## Documentation Files

### Core Documentation
- **PS60ProcessComprehensiveDayTradingGuide.md** - Complete PS60 theory and examples
- **CLAUDE.md** (this file) - Master project documentation and guidance
- **trader/PROGRESS_LOG.md** - ⭐ **SINGLE SOURCE OF TRUTH** - Complete implementation history (Oct 2025)
- **trader/REQUIREMENTS_IMPLEMENTATION_LOG.md** - Detailed requirements tracking

### Live Trader Documentation (October 6, 2025)
- **trader/IBKR_RESILIENCE_COMPLETE.md** - IBKR error handling system (400+ lines)
  - Retry logic with exponential backoff
  - Circuit breaker pattern
  - Connection monitoring
  - Error statistics and alerts
  - Testing scenarios

- **trader/STATE_RECOVERY_COMPLETE.md** - Crash recovery system (500+ lines)
  - Hybrid recovery (state file + IBKR)
  - Atomic file writes
  - Position reconciliation
  - Edge case handling

- **trader/BARBUFFER_INTEGRATION.md** - Tick-to-bar conversion system
  - Architecture analysis
  - Live vs backtest compatibility
  - BarBuffer implementation
  - Testing framework

- **trader/LOGGING_GUIDE.md** - Comprehensive logging system
  - Filter decision logging
  - Entry path tracking
  - Position state tracking
  - Daily summary analytics

- **trader/LIVE_TRADER_READY_FOR_TESTING.md** - Pre-launch checklist
  - System integration status
  - Testing requirements
  - Known limitations

### Filter System Documentation (October 5, 2025)
- **trader/FILTER_DOCUMENTATION.md** - Complete filter reference (300+ lines)
  - Detailed explanation of all 11 filters
  - Filter application order diagram
  - Configuration matrix with ON/OFF controls
  - Performance impact analysis
  - Testing framework

- **trader/PLTR_DEBUG_SESSION.md** - Oct 5 debug session log
  - 7-phase investigation (3 hours)
  - Timeline of discovery
  - Technical deep dive
  - Code changes summary
  - Key lessons learned

- **trader/STRATEGY_EVOLUTION_LOG.md** - Master evolution log
  - Implementation phases (Sept-Oct 2025)
  - Filter evolution timeline
  - Performance metrics
  - Lessons learned
  - Next steps roadmap

### Scanner Documentation
- **stockscanner/CLAUDE.md** - Scanner implementation details
- **stockscanner/README.md** - Scanner user guide
- **stockscanner/IBKR_API_SETUP.md** - TWS configuration

## Success Metrics

**Scanner Performance**:
- Complete scan in <5 minutes
- Identify 5-15 quality candidates daily
- Score accuracy >80%

**Trader Performance** (targets):
- Win rate >50% (with proper execution)
- Average winner > average loser (by 2-3x)
- Max drawdown <5% monthly
- Consistency over home runs
- Respect all PS60 rules (audit compliance)

## Recent Enhancements (October 2025)

### Phase 7: Delayed Momentum Detection & Dynamic Targets (Oct 13)
Captures stocks that start with weak breakouts but build momentum later. State machine now re-checks volume on every 1-minute candle after initial WEAK classification. Dynamic target selection uses highest available target (target3 > target2 > target1) for room-to-run validation.

**Files**: `breakout_state_tracker.py`, `ps60_entry_state_machine.py`, `backtester.py`  
**Documentation**: `trader/PROGRESS_LOG.md` (Phase 7 section)

### Phase 8: Dynamic Resistance Exits (Oct 15)
Exit system that checks for technical resistance (SMAs, Bollinger Bands, Linear Regression) on hourly bars. Takes 25% partial when price approaches resistance (0.5% threshold), activates trailing stop on remainder. Prevents minimal-profit exits on winning trades.

**Expected Impact**: 27x improvement on example trades (SOFI: $10.50 → $288)  
**Files**: `ps60_strategy.py` (lines 2987-3269), `trader.py` (lines 1215-1306)  
**Configuration**: `trader_config.yaml` (exits.dynamic_resistance_exits)  
**Documentation**: `trader/PROGRESS_LOG.md` (Phase 8 section)

### Phase 9: Target-Hit Stall Detection (Oct 21)
Detects when runner positions stall after hitting target1. If price stays in tight range (0.2%) for 5+ minutes, tightens trailing stop from 0.5% → 0.1% for quick exit. Frees capital from low-return consolidation holds.

**Expected Impact**: 7x improvement in runner P&L, 5.7x faster capital utilization  
**Files**: `ps60_strategy.py` (lines 2429-2542), `trader.py`, `backtester.py`  
**Configuration**: `trader_config.yaml` (exits.target_hit_stall_detection)  
**Documentation**: `trader/PROGRESS_LOG.md` (Phase 9 section), `trader/PHASE9_STALL_DETECTION_COMPLETE.md`

**Complete Implementation Details**: See `trader/PROGRESS_LOG.md` for full technical specifications, code examples, and testing results.

