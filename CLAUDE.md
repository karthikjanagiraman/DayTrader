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

**Implementation** (ps60_strategy.py:180-250):

```python
def _check_gap_filter(self, stock_data, current_price, side='LONG'):
    """Check if trade should be skipped due to gap through pivot"""

    previous_close = stock_data.get('close')

    if side == 'LONG':
        pivot = stock_data['resistance']
        target = stock_data.get('target1')

        # Check if gapped through pivot
        if previous_close < pivot and current_price > pivot:
            gap_pct = ((current_price - pivot) / pivot) * 100

            # Small gap (<1%) - OK to enter
            if gap_pct <= 1.0:
                return False, None

            # Large gap - check room to target
            room_to_target = ((target - current_price) / current_price) * 100

            # Plenty of room (>3%) - OK to enter
            if room_to_target >= 3.0:
                return False, None

            # Gap ate up the move - SKIP
            return True, f"Gap {gap_pct:.1f}% through pivot, only {room_to_target:.1f}% to target"
```

**Configuration** (trader_config.yaml):

```yaml
filters:
  enable_gap_filter: true           # Enable gap detection
  max_gap_through_pivot: 1.0        # 1% threshold for "small gap"
  min_room_to_target: 3.0           # 3% minimum room to target after gap
```

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

## Trader Module (to be built)

### Architecture Requirements

The trader module must:

1. **Read Scanner Output**
   - Parse daily scanner results (JSON/CSV) from `stockscanner/output/`
   - Filter setups by score, R/R ratio, distance to resistance
   - Prioritize high-scoring setups with good R/R (>1.5:1)
   - Extract pre-defined pivots: `resistance` (long) and `support` (short)

2. **Monitor Real-Time Price (Tick-by-Tick)**
   - Subscribe to real-time price data for all scanner symbols
   - Monitor continuously from market open (9:30 AM)
   - Check current price against scanner-identified pivots
   - Enter immediately when pivot breaks (no waiting for candle close)

3. **Execute Trades per PS60 Rules**
   - **Entry**: Market order when scanner pivot breaks
   - **Initial Stop**: Place stop at pivot level (resistance for longs, support for shorts)
   - **Partial Exits**: Automated scaling (sell 50% on first move of 0.25-0.75)
   - **Stop Management**: Move to breakeven after partial
   - **Final Exit**: Trail stop on remainder or close by EOD

4. **Risk Management**
   - Position sizing based on account size and distance to stop
   - Max risk per trade (1-2% of account)
   - Daily loss limits
   - Max concurrent positions (5-7 max)

5. **5-7 Minute Rule Implementation**
   - Start timer upon entry
   - Monitor price movement progress
   - Auto-exit if no favorable movement within 5-7 minutes
   - Indicates "reload seller/buyer" blocking the move

### Trading Workflow (Scanner-Driven)

```
Daily Workflow:
1. 8:00 AM (or prior evening) - Scanner runs, generates watchlist
2. 8:00-9:30 AM - Trader loads watchlist, prepares monitoring
3. 9:30 AM - Market opens, begin tick-by-tick monitoring
4. 9:30 AM - 4:00 PM - Monitor scanner pivots continuously
5. 3:55 PM - Close all remaining positions (flat by EOD)

Per-Trade Workflow (Scanner Pivot):
1. Load scanner output with pre-defined pivots
   - TSLA: resistance=$444.77, support=$432.63
2. Monitor real-time price from market open
3. Price breaks resistance ($445.00) → ENTER LONG immediately
4. Set initial stop at $444.77 (the pivot)
5. Take 50% profit on first move (e.g., $445.50-$446.00)
6. Move stop to breakeven ($445.00)
7. Take 25% at target1 ($450.84 from scanner)
8. Hold 25% as runner with trailing stop
9. Exit by 3:55 PM or if stop hits

Example Timeline:
9:30 AM - Market opens, TSLA = $442.00
9:47 AM - TSLA breaks $444.77 → Enter long at $444.85
9:52 AM - TSLA hits $445.75 → Sell 50% (+$0.90)
9:52 AM - Move stop to $444.85 (breakeven)
10:15 AM - TSLA hits $447.50 → Sell 25% at target (+$2.65)
11:30 AM - TSLA pulls back to $444.85 → Stop hits, exit 25% (scratch)
Result: +$0.45 avg on 50%, +$2.65 on 25%, $0 on 25% = +$1.11/share avg
```

### IBKR Integration

**Connection**:
- Use `ib_insync` library (same as scanner)
- Port 7497 (paper) or 7496 (live)
- Separate client ID from scanner (e.g., 2000+)

**Order Types**:
- Market orders for entries (fast execution when pivot breaks)
- Stop-loss orders for risk management (at pivot level)
- Limit orders for partial profit-taking (optional)
- Bracket orders to combine entry/stop/target (optional)

**Real-time Data Requirements**:
- Subscribe to **real-time tick data** (not bar data) for watchlist symbols
- Use `reqMktData()` for continuous price updates
- Monitor bid/ask/last price
- No need for 60-minute bar subscriptions (pivots pre-defined by scanner)

### Position Management

**Sizing Algorithm** (Risk-Based, October 4, 2025):
```python
# Calculate 1% risk per trade
risk_amount = account_value * 0.01  # $1,000 on $100k account

# Calculate stop distance
stop_distance = abs(entry_price - stop_price)

# Calculate shares to risk exactly $1,000
shares = int(risk_amount / stop_distance)

# Apply constraints
shares = max(10, min(shares, 1000))  # Between 10-1000 shares

# Examples:
# TSLA: Entry $435.29, Stop $435.67, Distance $0.38 → 2,632 shares → 1000 (capped)
# AVGO: Entry $337.55, Stop $334.79, Distance $2.76 → 362 shares ✅
# BA:   Entry $217.09, Stop $215.32, Distance $1.77 → 565 shares ✅
# MS:   Entry $156.02, Stop $154.77, Distance $1.25 → 800 shares ✅
```

**Scaling Out** (1R-Based Partials):
- Sell 50% at 1R (profit = risk distance)
- Sell 25% at target1 (2R or scanner target)
- Hold 25% as runner with trailing stop

### Configuration

**trader_config.yaml** should include:
```yaml
trading:
  account_size: 100000
  risk_per_trade: 0.01  # 1%
  max_positions: 5
  max_daily_loss: 0.03  # 3%

  position_sizing:
    min_shares: 10
    max_shares: 1000

  entry:
    use_market_orders: true
    slippage_tolerance: 0.02  # 2%

  exits:
    partial_1_pct: 0.50  # Sell 50% first
    partial_2_pct: 0.25  # Sell 25% second
    runner_pct: 0.25     # Hold 25%

  risk:
    five_minute_rule: true
    breakeven_after_partial: true
    close_all_by_eod: true
    eod_close_time: "15:55"

  filters:
    min_score: 50
    min_risk_reward: 1.5
    max_dist_to_pivot: 2.0  # Max 2% from pivot

backtest:
  use_1min_bars: true        # Use 1-min bars (not tick data)
  start_date: "2025-09-01"
  end_date: "2025-09-30"
  scanner_output_dir: "../stockscanner/output/"
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

**Scanner Performance**:
- 57 stocks scanned, 12 winners identified (21%)
- LONG success rate: 40%
- SHORT success rate: 25%
- Overall success rate: 33.3%

**Critical Pattern Discovered**:
```
Pivot Width = (Resistance - Support) / Support × 100

Winners:         2.70% average (2.51% median)
False Breakouts: 7.67% average (4.92% median)

TIGHT PIVOTS = SUCCESS
WIDE PIVOTS = FALSE BREAKOUT
```

**Top-Ranked Accuracy**:
- Top 5: 60% success rate
- Top 10: **70% success rate** ⭐
- Top 15: 66.7% success rate

**Problem Areas Identified**:
- Index ETFs (SPY, QQQ, DIA, IWM): 100% false breakout rate
- High-vol stocks (TSLA, COIN, HOOD): 75% false breakout rate
- SHORT setups: Only 25% success rate

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

## PS60 Principles Summary

**The Core Philosophy**:
- Wait patiently for clear pivot breaks (don't predict)
- Enter only with confirmation and room to run
- Take quick partial profits (cash flow first)
- Keep losses small with tight stops at pivot
- Let runners capture trend moves
- Stay disciplined - no exceptions to rules

**Psychological Edge**:
- Pre-defined levels eliminate guesswork
- Partial profits reduce fear of giving back gains
- Breakeven stops remove stress on runners
- 5-minute rule prevents hope-based holding
- Structure removes emotional decision-making

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

## Development Priority (Scanner-Driven Approach)

**Phase 1: Core Infrastructure**
1. Scanner output parser (read JSON/CSV from `stockscanner/output/`)
2. Watchlist filter (by score, R/R, distance to pivot)
3. Position manager (calculate position sizes based on risk)
4. IBKR connection manager (separate client ID from scanner)

**Phase 2: Real-Time Monitoring**
5. Real-time tick data subscription for watchlist symbols
6. Pivot break detection (monitor price vs. scanner resistance/support)
7. Entry signal generation (when pivot breaks)

**Phase 3: Order Execution**
8. Market order execution (enter on pivot break)
9. Stop-loss order placement (at pivot level)
10. Order status tracking and confirmations

**Phase 4: Exit Management**
11. Partial profit-taking logic (sell 50% on first move)
12. Breakeven stop adjustment (after partial)
13. Target-based exits (at scanner target1, target2)
14. Trailing stop for runners

**Phase 5: Risk Management**
15. 5-7 minute rule implementation (timer-based exit)
16. Position size calculator (based on stop distance)
17. Daily loss limits and position count limits
18. End-of-day liquidation (close all by 3:55 PM)

**Phase 6: Testing & Validation**
19. Paper trading mode (real market, simulated orders)
20. Trade logging and performance tracking
21. Backtest framework (replay historical scanner results)
22. Live paper trading validation (2-4 weeks minimum)

**Phase 7: Production**
23. Live trading mode (after validation)
24. Monitoring dashboard
25. Alert system for critical events

**Note**: Phases 3-7 from original plan (intraday pivots, gap plays) are **deferred** since we're focusing on scanner-identified pivots only.

Each phase must be tested thoroughly before proceeding to the next.

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

