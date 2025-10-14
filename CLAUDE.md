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
├── stockscanner/              # Pre-market scanner (completed)
│   ├── scanner.py            # Main scanner script
│   ├── config/               # YAML configuration files
│   ├── output/               # Scanner results (CSV/JSON)
│   └── CLAUDE.md            # Scanner-specific documentation
│
├── trader/                   # Trading module (in progress)
│   ├── trader.py            # Main live trading engine
│   ├── position_manager.py  # Position sizing and risk management
│   ├── order_executor.py    # IBKR order execution
│   ├── strategy/            # Strategy modules
│   │   ├── ps60_strategy.py # Core PS60 strategy logic
│   │   └── position_manager.py
│   ├── backtest/            # Backtesting framework
│   │   ├── backtester.py   # Historical 1-min bar backtester
│   │   ├── run_monthly_backtest.py
│   │   ├── logs/           # Backtest logs
│   │   └── monthly_results/ # Historical results
│   ├── config/              # Trading configuration
│   │   └── trader_config.yaml  # Filter ON/OFF controls
│   ├── logs/                # Trade logs and performance
│   ├── FILTER_DOCUMENTATION.md     # Complete filter reference (Oct 5)
│   ├── PLTR_DEBUG_SESSION.md       # Oct 5 debug session
│   ├── STRATEGY_EVOLUTION_LOG.md   # Master evolution log (Oct 5)
│   └── REQUIREMENTS_IMPLEMENTATION_LOG.md
│
├── scanner_validation/       # ✅ Scanner validation system (Oct 6, 2025)
│   ├── validate_scanner.py          # Daily validation script
│   ├── analyze_validation_metrics.py # Metrics analyzer
│   ├── enhanced_scoring.py          # ML-based improved scoring
│   ├── compare_scoring_accuracy.py  # Accuracy measurement
│   ├── verify_with_ibkr.py         # IBKR double-check
│   ├── analyze_missed_winners_detailed.py # Detailed analysis
│   ├── README.md                    # Complete system guide
│   ├── DAILY_VALIDATION_GUIDE.md   # Daily workflow
│   ├── validation_YYYYMMDD.csv     # Daily validation results
│   ├── validation_metrics.json     # ML metrics data
│   └── Reports/                     # Analysis reports
│       ├── SCANNER_VALIDATION_SUMMARY_YYYYMMDD.md
│       ├── TRADING_PLAN_YYYYMMDD.md
│       └── QUICK_REFERENCE_YYYYMMDD.md
│
└── PS60ProcessComprehensiveDayTradingGuide.md  # Complete PS60 theory
```

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

### Overview

The strategy uses a comprehensive **11-filter system** to ensure trade quality and prevent common losing patterns. Filters are applied in stages: pre-entry screening, entry decision, and exit management.

**Complete Reference**: `trader/FILTER_DOCUMENTATION.md` (300+ lines, detailed explanations)
**Debug Session**: `trader/PLTR_DEBUG_SESSION.md` (PLTR investigation, Oct 5)
**Evolution Log**: `trader/STRATEGY_EVOLUTION_LOG.md` (master consolidation log)

### Filter Application Order

```
Stock breaks resistance
    ↓
Wait for 1-minute candle close (0-60 seconds)
    ↓
Calculate volume & candle metrics
    ↓
┌─────────────────────────────┐
│ Is it MOMENTUM breakout?    │
│ (vol ≥1.3x AND candle large)│
└─────────────┬───────────────┘
              │
        ┌─────┴─────┐
        │           │
       YES          NO (WEAK)
        │           │
        ↓           ↓
   MOMENTUM    CONFIRMATION NEEDED
   PATH              │
        │       ┌────┴────┐
        │       │         │
        │   PULLBACK  SUSTAINED
        │   (0-120s)  (120s)
        │       │         │
        └───────┴─────────┘
                │
        Check choppy filter (ALL paths)
                │
        Check room-to-run filter
        (pullback/sustained only)
                │
            ENTER
```

### Critical Filters (October 5, 2025)

#### 1. Choppy Market Filter ⭐ CRITICAL
**Purpose**: Prevent entries during consolidation (high whipsaw risk)
**When Applied**: ALL entry types (momentum, pullback, sustained)
**Logic**: Block if 5-minute range < 0.5× ATR

**Configuration**:
```yaml
confirmation:
  enable_choppy_filter: true
  choppy_atr_multiplier: 0.5      # Range must exceed 0.5× ATR
  choppy_lookback_bars: 60        # Last 5 minutes
```

**Impact**:
- September analysis: 61% of losses from choppy conditions
- Lost $15,425 in one week from consolidation entries
- Win rate in choppy: 6.7% vs 40%+ in trending

**Example**:
```python
5-minute range: $0.80 ($182.20 - $183.00)
ATR(20): $2.10
Threshold: $2.10 × 0.5 = $1.05

$0.80 < $1.05 → CHOPPY → BLOCK ❌
```

#### 2. Room-to-Run Filter ⭐⭐⭐ NEW (Oct 5, 2025)
**Purpose**: Validate sufficient opportunity remaining at entry time
**When Applied**: Pullback/retest and sustained break entries ONLY
**Logic**: Block if (target - entry) / entry < 1.5%

**Configuration**:
```yaml
filters:
  enable_room_to_run_filter: true
  min_room_to_target_pct: 1.5     # Minimum 1.5% to target
```

**Why This Filter Was Created**:
- Scanner generates setups 8-13 hours before market open
- Market conditions change overnight (gaps, pre-market moves)
- Confirmation strategies wait for patterns (0-120 seconds)
- Price moves during confirmation wait
- Need to validate opportunity still exists at entry time

**Impact**:
- PLTR Oct 1: 0.61% room → BLOCKED ✅ (would have lost -$1,567)
- Oct 1 results: 5 trades (+$41) → 1 trade (+$796) with filter
- 19x P&L improvement by blocking marginal setups

**Example**:
```python
PLTR @ 9:48 AM:
  Entry: $183.03
  Target: $184.14
  Room: ($184.14 - $183.03) / $183.03 = 0.61%

0.61% < 1.5% → BLOCK ❌

COIN @ 10:05 AM:
  Entry: $345.92
  Target: $354.00
  Room: ($354.00 - $345.92) / $345.92 = 2.33%

2.33% > 1.5% → ALLOW ✅
```

**Paradigm Shift**:
- ❌ Old thinking: "Are we too high in the range?" (defensive)
- ❌ Old thinking: "Are we too far from pivot?" (pivot-centric)
- ✅ New thinking: **"Is there enough room to target?"** (opportunity-centric)

#### 3. Sustained Break Logic ⭐ NEW (Oct 5, 2025)
**Purpose**: Catch "slow grind" breakouts with weak candles but sustained hold
**When Applied**: Weak breakouts that don't qualify for momentum OR pullback
**Logic**: Price holds above/below pivot for 2 minutes with volume

**Configuration**:
```yaml
confirmation:
  sustained_break_enabled: true
  sustained_break_minutes: 2
  sustained_break_max_pullback_pct: 0.003  # 0.3% tolerance
```

**Why This Was Added**:
- 5-second bars show weak candles (0.04%) for strong 1-minute moves (0.22%)
- Bar resolution mismatch made momentum filter too strict
- Time-based confirmation works better than size-based for fine-resolution data

**Example - PLTR Oct 1**:
```
09:45:55 - Initial break @ $182.25
           1-minute candle: 0.22% ✅ (reasonable)
           5-second candle: 0.04% ❌ (too small for 0.8% threshold)
           Volume: 1.44x ✅ (good)
           → Classified as WEAK (not momentum)

09:46:00-09:47:55 - Sustained hold pattern
           Price stayed above $182.24 for 2 minutes
           Average volume: 1.3x
           Max pullback: 0.24% (within 0.3% tolerance)
           → SUSTAINED BREAK confirmed ✅

09:48:00 - Entry eligible @ $183.03
           BUT: Room to target only 0.61% < 1.5%
           → BLOCKED by room-to-run filter ✅
```

### Filter Configuration Matrix

**All filters can be independently enabled/disabled** via `trader/config/trader_config.yaml`:

| Filter | Config Key | Default | Applied To | Impact |
|--------|-----------|---------|------------|--------|
| Min Score | `filters.min_score` | 0 (disabled) | Pre-entry | Quality screening |
| Min R/R | `filters.min_risk_reward` | 0 (disabled) | Pre-entry | Risk validation |
| Gap Filter | `filters.enable_gap_filter` | false | Pre-entry | Overnight gap handling |
| **Choppy Filter** | `confirmation.enable_choppy_filter` | **true** | **All entries** | **-$15k/month saved** |
| **Room-to-Run** | `filters.enable_room_to_run_filter` | **true** | **Pullback/sustained** | **19x P&L improvement** |
| Max Attempts | `trading.attempts.max_attempts_per_pivot` | 2 | Entry decision | Prevent overtrading |
| Entry Time Window | `trading.entry.min/max_entry_time` | 09:45-15:00 | Entry decision | Avoid volatility |
| Index Shorts | `filters.avoid_index_shorts` | true | Entry decision | +$700/day saved |
| Symbol Blacklist | `filters.avoid_symbols` | SPY/QQQ/DIA/IWM | Pre-entry | Remove bad actors |
| 8-Minute Rule | (automatic) | true | Exit decision | +$2,334/month net |
| Trailing Stop | `trading.trailing_stop.enabled` | true | Exit management | Let winners run |

### October 4 Evening: Three Critical Entry Filters

**Based on Sept 23-30 Analysis** (-$19,315 loss, 10.6% win rate, 123 trades)

Comprehensive analysis of all 123 trades revealed three major issues causing losses:

#### Problem #1: Momentum Criteria Too Strict
- **Only 1 out of 123 trades qualified as "momentum breakout"**
- 99% of trades went through pullback logic
- Result: Late entries after pullback → chasing moves

**Fix #1: Relaxed Momentum Criteria**
```yaml
# OLD (too strict)
momentum_volume_threshold: 2.0    # 2.0x volume
momentum_candle_min_pct: 0.015    # 1.5% candle

# NEW (realistic)
momentum_volume_threshold: 1.3    # 1.3x volume (-35%)
momentum_candle_min_pct: 0.008    # 0.8% candle (-47%)
```

**Expected Impact**: More trades will enter on initial breakout (momentum) instead of waiting for pullback, reducing chasing.

#### Problem #2: Chasing Entries (69.1% of trades) - SUPERSEDED
- **Winners entered at 36% of 5-minute range**
- **Losers entered at 81% of 5-minute range**
- Chasing trades lost $13,099 (68% of all losses)

**Fix #2: Entry Position Filter (DEPRECATED - Oct 5, 2025)**
```yaml
enable_entry_position_filter: false  # DISABLED - superseded by room-to-run filter
max_entry_position_pct: 70           # Don't enter above 70% of 5-min range
```

**Logic Conflict Discovered (Oct 5)**:
- Pullback/retest strategies NEED TIME to confirm patterns
- Chasing filter PENALIZED waiting for confirmation
- Self-defeating logic

**Replacement**: Room-to-run filter (measures distance to target instead)

#### Problem #3: Choppy Entries (61% of trades)
- **75 trades had choppy price action** (first minute move <0.15%)
- These choppy trades: 6.7% win rate, -$15,425 total loss
- Issue: Entering during consolidation, not trending moves

**Fix #3: Choppy Filter** (See detailed explanation above)
```yaml
enable_choppy_filter: true
choppy_atr_multiplier: 0.5        # Recent range must be >0.5× ATR
```

**Logic**: Skip entry if 5-minute range is less than 50% of ATR (indicates consolidation).

**Expected Impact**: Eliminate ~55 choppy trades, save ~$11,000.

#### Combined Expected Impact

**BEFORE Fixes** (Sept 23-30):
- 123 trades
- 10.6% win rate
- -$19,315 P&L

**AFTER Fixes (estimated)**:
- ~40 high-quality trades (-67% trade count)
- ~25-30% win rate (+150% win rate)
- +$2,000 to +$5,000 P&L (improvement: +$21K to +$24K)

**Implementation Details**: See `trader/OCT_4_2025_FIXES_IMPLEMENTATION.md`

### Filter Evolution Timeline (Oct 4-5, 2025)

| Date | Filter | Action | Rationale |
|------|--------|--------|-----------|
| Oct 4 | Min R/R 2:1 | Added | Per requirements |
| Oct 4 | Choppy filter | Added | 61% losses from consolidation |
| Oct 4 | Range chasing | Added | Losers at 81% of range |
| Oct 4 | Max 2 attempts | Added | Prevent overtrading |
| Oct 5 | Sustained break | Added | Catch slow grinds |
| Oct 5 | Pullback tolerance | Increased | 0.1% → 0.3% (5-sec bars) |
| Oct 5 | Range chasing | **Removed** | Conflicted with confirmation |
| Oct 5 | **Room-to-run** | **Added** | Smart opportunity validation |

### Key Lessons Learned

**Technical Lessons**:
1. **Bar Resolution Matters**: 5-second vs 1-minute requires different thresholds
2. **Filters Must Align**: Don't penalize strategies for being patient
3. **Ask Right Question**: "Room to target?" not "Position in range?"
4. **Quality Over Quantity**: 1 good trade > 5 marginal trades

**Strategic Lessons**:
1. **Multi-Path Entry System**: Different paths need different filters
2. **Adaptive Filtering**: ATR-based > fixed thresholds
3. **Entry-Time Validation**: Scanner data is 8-13 hours old, validate at entry

### Related Documentation

- **FILTER_DOCUMENTATION.md**: Complete 300+ line filter reference
- **PLTR_DEBUG_SESSION.md**: Oct 5 debug session (7 phases, 3 hours)
- **STRATEGY_EVOLUTION_LOG.md**: Master evolution log (consolidates all progress)
- **trader_config.yaml**: Live configuration with filter ON/OFF controls

**PS60 Exception Rule** (Future Enhancement):

Per PS60 methodology, if a stock gaps significantly through a pivot but still has room to run, use the **first hour's high/low** as the new pivot instead of scanner levels. This is not yet implemented but is on the roadmap.

**Backtester Implementation** (backtester.py:191-248):

The backtester also includes gap detection to properly simulate overnight gaps in historical data:

```python
# Detect gap at market open
opening_price = bars[0].open
prev_close = stock['close']
gap_pct = ((opening_price - prev_close) / prev_close) * 100

# Check if gap went through resistance
if opening_price > resistance and prev_close < resistance:
    gap_pct_through = ((opening_price - resistance) / resistance) * 100

    if gap_pct_through > 0.5:  # Significant gap
        room_to_target = ((target1 - opening_price) / opening_price) * 100

        if room_to_target < 3.0:
            skip_trade = True  # Not enough room left
        else:
            # Future: Adjust to first-hour pivot
            pivot_adjusted = True
```

### Chart Setup Requirements

**60-minute chart with**:
- SMAs: 5, 10, 20, 50, 100, 200
- EMAs: 4, 9, 10, 13, 20, 50, 100, 200
- Bollinger Bands (20, 2)
- Linear Regression (30-period)

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

```python
# backtest/backtester.py

from ib_insync import IB, Stock
from datetime import datetime, timedelta
import json
import pandas as pd

class PS60Backtester:
    """
    Backtest PS60 strategy using 1-minute historical bars from IBKR
    Simulates tick-by-tick monitoring of scanner-identified pivots
    """

    def __init__(self, scanner_file, start_date, end_date):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=3000)

        # Load scanner results
        with open(scanner_file) as f:
            self.scanner_results = json.load(f)

        self.start_date = start_date
        self.end_date = end_date
        self.trades = []

    def run(self):
        """Run backtest over date range"""
        current_date = self.start_date
        while current_date <= self.end_date:
            print(f"\n=== Backtesting {current_date} ===")
            self.backtest_day(current_date)
            current_date += timedelta(days=1)

        self.print_results()

    def backtest_day(self, date):
        """Backtest single trading day"""
        # Filter scanner for tradeable setups
        watchlist = [s for s in self.scanner_results
                     if s['score'] >= 50 and s['risk_reward'] >= 1.5]

        for stock in watchlist:
            self.backtest_stock(stock, date)

    def backtest_stock(self, stock, date):
        """Backtest single stock for the day"""
        symbol = stock['symbol']
        resistance = stock['resistance']
        support = stock['support']

        # Get 1-minute historical bars from IBKR
        bars = self.get_bars(symbol, date)

        if not bars:
            return

        position = None

        # Simulate tick-by-tick monitoring
        for bar in bars:
            timestamp = bar.date
            price = bar.close

            # Entry logic - check for pivot breaks
            if position is None:
                if price > resistance:
                    position = self.enter_long(stock, price, timestamp)
                elif price < support:
                    position = self.enter_short(stock, price, timestamp)

            # Exit logic - manage open position
            else:
                position, closed_trade = self.manage_position(
                    position, price, timestamp
                )
                if closed_trade:
                    self.trades.append(closed_trade)
                    position = None

    def get_bars(self, symbol, date):
        """Fetch 1-minute bars from IBKR"""
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=f'{date.strftime("%Y%m%d")} 16:00:00',
                durationStr='1 D',
                barSizeSetting='1 min',  # 1-minute bars
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )
            return bars
        except Exception as e:
            print(f"    Error fetching {symbol}: {e}")
            return []

    def enter_long(self, stock, price, timestamp):
        """Enter long position"""
        shares = self.calculate_position_size(price, stock['resistance'])

        position = {
            'symbol': stock['symbol'],
            'side': 'LONG',
            'entry_price': price,
            'entry_time': timestamp,
            'stop': stock['resistance'],  # Initial stop at pivot
            'target1': stock['target1'],
            'shares': shares,
            'remaining': 1.0  # 100% of position
        }

        print(f"  {stock['symbol']}: LONG @ ${price:.2f} "
              f"(pivot ${stock['resistance']:.2f})")
        return position

    def manage_position(self, pos, price, timestamp):
        """
        Manage open position per PS60 rules:
        - Take 50% profit on first move
        - Move stop to breakeven
        - Exit at target or stop
        - 5-7 minute rule
        """
        time_in_trade = (timestamp - pos['entry_time']).total_seconds() / 60

        if pos['side'] == 'LONG':
            gain = price - pos['entry_price']

            # Take 50% profit on first favorable move (0.25-0.75)
            if pos['remaining'] == 1.0 and gain >= 0.25:
                print(f"    Partial: 50% @ ${price:.2f} (+${gain:.2f})")
                pos['remaining'] = 0.5
                pos['stop'] = pos['entry_price']  # Move to breakeven
                pos['partial1_price'] = price

            # Hit target1 - take another 25%
            elif pos['remaining'] > 0.25 and price >= pos['target1']:
                print(f"    Target1: 25% @ ${price:.2f}")
                pos['remaining'] = 0.25

            # Stop hit - exit remaining
            elif price <= pos['stop']:
                print(f"    Stop: Exit remaining @ ${price:.2f}")
                return None, self.close_position(pos, price, timestamp, 'STOP')

            # 5-7 minute rule - no movement
            elif time_in_trade >= 7 and gain < 0.10:
                print(f"    5-min rule: Exit @ ${price:.2f}")
                return None, self.close_position(
                    pos, price, timestamp, '5MIN_RULE'
                )

        # Similar logic for shorts...

        return pos, None

    def calculate_position_size(self, entry, stop):
        """Calculate shares based on 1% risk"""
        account_value = 100000
        risk_per_trade = account_value * 0.01
        stop_distance = abs(entry - stop)
        shares = int(risk_per_trade / stop_distance)
        return min(shares, 1000)  # Cap at max

    def close_position(self, pos, exit_price, timestamp, reason):
        """Close position and record trade"""
        if pos['side'] == 'LONG':
            pnl_per_share = exit_price - pos['entry_price']
        else:
            pnl_per_share = pos['entry_price'] - exit_price

        total_pnl = pnl_per_share * pos['shares'] * pos['remaining']

        trade = {
            'symbol': pos['symbol'],
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': exit_price,
            'pnl': total_pnl,
            'reason': reason
        }
        return trade

    def print_results(self):
        """Print backtest performance metrics"""
        if not self.trades:
            print("\nNo trades executed")
            return

        df = pd.DataFrame(self.trades)

        print("\n=== BACKTEST RESULTS ===")
        print(f"Total trades: {len(df)}")
        print(f"Winners: {len(df[df['pnl'] > 0])}")
        print(f"Win rate: {len(df[df['pnl'] > 0]) / len(df) * 100:.1f}%")
        print(f"Total P&L: ${df['pnl'].sum():.2f}")
        print(f"Avg winner: ${df[df['pnl'] > 0]['pnl'].mean():.2f}")
        print(f"Avg loser: ${df[df['pnl'] < 0]['pnl'].mean():.2f}")
```

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

### Latest Backtest Results (October 4, 2025)

**Test Period**: October 1-4, 2025
**Configuration**:
- 8-minute rule enabled
- Risk-based position sizing (1% per trade)
- Hybrid entry strategy (momentum vs pullback)
- Bounds checking and timestamp fixes applied

**Performance**:
```
Total Trades: 42
Win Rate: 23.8%
Total P&L: +$5,461
Avg Daily P&L: +$1,820
Monthly Return: 5.46%

Winners: 10 trades
Losers: 32 trades
Profit Factor: 1.65
Avg Winner: $1,093
Avg Loser: -$226

Exit Reasons:
- 8MIN_RULE: 10 trades (prevented larger losses)
- STOP: 9 trades
- TRAIL_STOP: 15 trades
- EOD: 2 trades
```

**Daily Breakdown**:
- Oct 1: -$755 (2W/2L, PLTR caught by 8-min rule)
- Oct 2: -$1,349 (3W/7L, saved ARM -$1,572 with 8-min rule)
- Oct 3: +$7,565 (5W/23L, TSLA short +$4,605, saved AMAT -$1,385)

**Key Findings**:
- 8-minute rule saved ~$3,900 on quick losers
- 8-minute rule cost ~$1,578 on slow starters (PLTR, INTC)
- Net benefit of 8-minute rule: +$2,334
- Risk-based sizing varied positions from 362-1,000 shares
- Most entries were pullback/retest (no momentum breakouts)

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

### 🚦 Session Management (October 13, 2025)

The trader includes robust session management for clean startup and graceful shutdown.

#### **Starting a Trading Session**

```bash
cd trader
python3 trader.py
```

**What happens at startup:**
1. ✅ **Connects to IBKR** (port 7497 for paper trading)
2. 🧹 **Automatic cleanup:**
   - Cancels all pending orders
   - Closes all open positions from previous crashes
   - Verifies clean slate before trading
3. 📊 **Loads scanner results** for today's date
4. 📡 **Subscribes to market data** for watchlist symbols
5. 🔄 **Recovers state** from previous session (if any)
6. ▶️ **Starts monitoring** at 9:30 AM ET

**Startup logs to expect:**
```
================================================================================
🧹 SESSION CLEANUP - Preparing for fresh start...
================================================================================
✓ No open orders to cancel
📊 Found 2 open positions - closing...
   Closing SHORT BB: 3000 shares @ avg $4.62
   ✓ Closed BB
   Closing SHORT SNAP: 1000 shares @ avg $8.61
   ✓ Closed SNAP
================================================================================
✅ SESSION CLEANUP COMPLETE - Starting fresh!
================================================================================
✓ Loaded 53 setups from scanner_results_20251013.json
✓ Subscribed to 53/53 symbols
```

#### **Stopping a Trading Session (Graceful Shutdown)**

**Method 1: Ctrl+C (Recommended)**
```bash
# Press Ctrl+C in the terminal where trader is running
^C
```

**Method 2: Kill Command**
```bash
# Find the trader process ID
ps aux | grep "python3 trader.py"

# Send graceful shutdown signal
kill <pid>
```

**Method 3: Kill All Python Traders**
```bash
pkill -f "python3 trader.py"
```

**What happens during graceful shutdown:**
1. 🛑 **Catches shutdown signal** (SIGINT/SIGTERM)
2. 📊 **Closes all open positions** with market orders
3. 💾 **Saves session state** to `logs/trader_state.json`
4. 📋 **Generates final P&L report**
5. 🔌 **Disconnects from IBKR** cleanly
6. ✅ **Exits with success**

**Shutdown logs to expect:**
```
================================================================================
🛑 GRACEFUL SHUTDOWN INITIATED
================================================================================
📊 Closing 5 open positions...
  🛑 CLOSE TSLA @ $447.13 (SHUTDOWN)
     P&L: $-15.95
  🛑 CLOSE AAPL @ $225.50 (SHUTDOWN)
     P&L: $+8.25
  ...
💾 Saving session state...
📊 Generating final report...
  Total Trades: 12
  Daily P&L: $245.67
  Win Rate: 41.7%
🔌 Disconnecting from IBKR...
================================================================================
✅ GRACEFUL SHUTDOWN COMPLETE
   Session state saved for potential restart
================================================================================
```

#### **Mid-Session Restart**

If you need to restart the trader during market hours (e.g., after code changes):

```bash
# 1. Stop current session (Ctrl+C)
^C
# Wait for graceful shutdown to complete

# 2. Make any code/config changes
vim config/trader_config.yaml

# 3. Restart trader
python3 trader.py
# Automatic cleanup will close any orphaned positions
# State recovery will restore context from previous session
```

**Benefits of graceful shutdown:**
- ✅ No orphaned positions left in IBKR account
- ✅ All orders cancelled before exit
- ✅ State saved for audit trail
- ✅ P&L calculated and logged
- ✅ Can resume trading immediately after restart

#### **Emergency Stop (Not Recommended)**

If the trader becomes unresponsive:

```bash
# Force kill (use only if graceful shutdown fails)
kill -9 <pid>

# Manually close positions in TWS/Gateway
# Run cleanup on next startup
```

⚠️ **Note:** Force kill (`kill -9`) bypasses graceful shutdown and may leave positions open. The automatic cleanup on next startup will handle this, but it's better to use graceful shutdown when possible.

#### **Checking Session Status**

```bash
# Check if trader is running
ps aux | grep "python3 trader.py"

# Check recent logs
tail -50 trader/logs/trader_$(date +%Y%m%d).log

# Check saved state
cat trader/logs/trader_state.json | python3 -m json.tool
```

#### **Account Size Configuration**

**Current setting:** $50,000 (changed from $100,000 on Oct 13, 2025)

**Why 50K:**
- Prevents margin errors in paper account
- Reduces position sizes by 50%
- Matches typical paper account balance

**To change:**
```yaml
# trader/config/trader_config.yaml
trading:
  account_size: 50000  # Change this value
```

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

**See [Session Management](#-session-management-october-13-2025) for detailed startup/shutdown procedures.**

## Backtest Results (September 30, 2025)

### Backtest Configuration Evolution

**Final Optimal Settings:**
- ✅ **Max 2 attempts per pivot** (not 1, not unlimited)
- ✅ **Min R:R 2.0** (quality over quantity)
- ✅ **No trading after 3:00 PM** (last hour excluded)
- ✅ **Tight stops at pivot** (PS60 discipline)
- ✅ **50% partial profits** on first move

### Performance Summary

| Version | Trades | Win% | P&L | Avg/Trade | Profit Factor |
|---------|--------|------|-----|-----------|---------------|
| Original (buggy) | 126 | 47% | +$1,289 | +$10 | 1.13 |
| 1 Attempt | 16 | 38% | +$616 | +$39 | 1.44 |
| **2 Attempts (Final)** | **27** | **37%** | **+$1,441** | **+$53** | **1.55** |

**Key Findings:**
- **Max 2 attempts is optimal** (134% more P&L than 1 attempt)
- **Second chances pay off**: JPM 2nd attempt = +$1,000, BA 2nd = +$968
- **Let winners run**: Trades lasting >30 min = 100% win rate
- **Partial profits work**: Even losers reduced via partials

### Loss Analysis

**Total Losses**: $2,627 across 17 losing trades

**Top 3 Loss Categories:**
1. **Index Shorts** (26.6%, -$700): SPY/QQQ whipsawed near support
2. **Early Morning** (40%, -$1,060): 9:30-9:45 AM volatility
3. **Quick Stops** (68%, -$1,787): <3 min exits on tight stops

**Top 5 Individual Losses:**
1. BIDU LONG: -$600 (early failed breakout)
2. AVGO SHORT: -$560 (2nd attempt whipsaw)
3. SPY SHORT: -$390 (index whipsaw)
4. ROKU LONG: -$250 (resistance held)
5. QQQ SHORT: -$200 (index whipsaw)

### Recommended Filters (From Backtest)

**Additional Filters to Implement:**
1. ✅ **Avoid index shorts** → Save ~$700/day (SPY, QQQ, DIA)
2. ✅ **Wait until 9:45 AM** → Save ~$600/day (let opening volatility settle)
3. ✅ **Skip choppy 2nd attempts** → Save ~$400/day (if 1st failed badly)

**Expected Performance with Filters:**
- Trades: ~18-20 per day (vs 27)
- Win Rate: ~50% (vs 37%)
- P&L: ~$2,500-3,000/day (vs $1,441)

### Live Trading Expectations

**Conservative Estimate (50% of backtest):**
- Daily: $720
- Monthly (20 days): $14,400 (14.4% on $100k)
- Annual: ~170%

**Backtest Performance (100%):**
- Daily: $1,441 (1.44%)
- Monthly: $28,800 (28.8%)
- Annual: ~350%

**Target Range**: $1,000-2,000/day with discipline

## Live Trader Implementation (October 2025)

### Status: ✅ LIVE - In Paper Trading

The live trader has been implemented, tested in paper trading, and the critical timezone bug has been fixed.

### Architecture

```python
trader.py                    # Main trading engine
├── Load scanner results     # Filter by score ≥50, R/R ≥2.0
├── Connect to IBKR          # Port 7497 (paper trading)
├── Subscribe market data    # Real-time ticks for watchlist
├── Monitor pivot breaks     # Tick-by-tick price monitoring
├── Execute trades           # Market orders on pivot breaks
├── Manage positions         # Partials, stops, targets
└── Close at EOD            # 3:55 PM liquidation
```

### Key Features Implemented

**Entry Logic:**
- ✅ Max 2 attempts per pivot (per backtest optimal)
- ✅ No trading before 9:45 AM (avoid early volatility)
- ✅ No trading after 3:00 PM (avoid late chop)
- ✅ Skip index shorts (SPY, QQQ, DIA, IWM)
- ✅ Filter by min score 50, min R/R 2.0
- ✅ Max 5 concurrent positions

**Exit Logic:**
- ✅ 50% partial on first move ($0.25+ gain)
- ✅ Move stop to breakeven after partial
- ✅ 25% partial at target1
- ✅ 25% runner with trailing stop
- ✅ 5-7 minute rule (exit if no movement)
- ✅ Close all positions at 3:55 PM

**Risk Management:**
- ✅ Position sizing: 1% risk per trade
- ✅ Stop at pivot (tight discipline)
- ✅ Max daily loss: 3% (circuit breaker)
- ✅ Min/max shares: 10-1000

**Logging:**
- ✅ Detailed trade logs with timestamps
- ✅ JSON trade records for analysis
- ✅ Daily P&L summary
- ✅ Win rate and avg winner/loser tracking

### Configuration (trader_config.yaml)

```yaml
trading:
  account_size: 100000
  risk_per_trade: 0.01  # 1%
  max_positions: 5

  entry:
    min_entry_time: "09:45"   # Backtest finding
    max_entry_time: "15:00"   # Backtest finding

  exits:
    partial_1_pct: 0.50       # 50% first
    partial_1_gain: 0.25      # At $0.25 gain
    eod_close_time: "15:55"

  attempts:
    max_attempts_per_pivot: 2  # Backtest optimal

filters:
  min_score: 50
  min_risk_reward: 2.0        # Backtest finding
  avoid_index_shorts: true    # Backtest finding (saved $700/day)
```

### Example Trading Session

```
09:30:00 - Market opens
09:45:00 - Trader starts monitoring
09:47:23 - 🟢 LONG BIDU @ $137.70 (pivot $137.42 broken)
          Shares: 1000 | Stop: $137.42 | Target: $140.50
09:48:15 - 💰 PARTIAL 50% BIDU @ $138.20 (+$0.50)
          Stop moved to $137.70 (breakeven)
10:15:30 - 🎯 PARTIAL 25% BIDU @ $140.50 (TARGET1)
11:45:00 - 🛑 CLOSE 25% BIDU @ $139.00 (TRAIL_STOP)
          P&L: +$785 (50% @ +$0.50, 25% @ +$2.80, 25% @ +$1.30)
```

### Expected vs Actual (To Be Tracked)

| Metric | Backtest | Live (Target) | Actual |
|--------|----------|---------------|--------|
| Daily P&L | $1,441 | $720-1,400 | TBD |
| Win Rate | 37% | 35-45% | TBD |
| Avg Trade | $53 | $40-60 | TBD |
| Trades/Day | 27 | 20-30 | TBD |

### Paper Trading Validation Plan

**Week 1-2:**
- Track all trades vs backtest expectations
- Monitor slippage and execution quality
- Validate entry/exit logic
- Check 5-7 minute rule effectiveness

**Week 3-4:**
- Compare results to backtest
- Adjust filters if needed
- Fine-tune parameters
- Verify risk management

**Criteria for Going Live:**
- ✅ Win rate ≥35%
- ✅ Profit factor ≥1.4
- ✅ Daily P&L positive 75%+ of days
- ✅ Max drawdown <5%
- ✅ No system errors or crashes
- ✅ Consistent with backtest (±30%)

### Known Limitations

1. **Slippage**: Backtest assumes perfect fills, live will have slippage
2. **Market Impact**: 1000 share orders may move price
3. **Data Latency**: Real-time vs backtest 1-min bars
4. **Psychological**: Backtest is emotionless, live trading is not

### Critical Bugs Fixed

#### Bug #1: Timezone Bug in EOD Close Logic (October 1, 2025)

**Issue**: EOD close logic was using local PST time instead of Eastern Time
- **Impact**: Positions remained open overnight at 4:00 PM market close
- **Date**: October 1, 2025 - 3 runner positions (PLTR, COIN, TSLA) left open
- **Fix**: Updated EOD close check to use Eastern Time (lines 532-543 in trader.py)
- **Status**: ✅ FIXED

```python
# BEFORE (buggy):
now = datetime.now().time()  # Local PST time

# AFTER (fixed):
import pytz
eastern = pytz.timezone('US/Eastern')
now_et = datetime.now(pytz.UTC).astimezone(eastern)
now = now_et.time()  # Eastern Time
```

#### Bug #2: Embedded Scanner in Backtest (October 3, 2025)

**Issue**: `run_monthly_backtest.py` was using an embedded/simplified scanner instead of production scanner
- **Impact**: Catastrophic - September backtest showed -$56k P&L vs +$8.9k with production scanner
- **Root Cause**: Created `HistoricalScanner` class inside backtest script instead of using `stockscanner/scanner.py`
- **Performance Difference**:
  - Embedded scanner: -$56,362 P&L, 26.8% win rate (WRONG)
  - Production scanner: +$8,895 P&L, 39.9% win rate (CORRECT)
  - **$65k difference** due to using wrong scanner!

#### Bug #3: 5-Minute Rule Firing After Partials (October 3, 2025) ⚠️ CRITICAL

**Issue**: Strategy module extraction lost critical condition in 5-minute rule logic
- **Date Discovered**: October 3, 2025
- **Impact**: Would have broken live trading - winners exited prematurely after taking partials
- **Severity**: CRITICAL - Live trading would have failed tomorrow

**Root Cause**:
When the `strategy/` module was extracted from `trader.py`, the 5-minute rule lost a critical check:

**Original working logic in trader.py:**
```python
# 5-7 minute rule
elif time_in_trade >= 7 and position['remaining'] == 1.0 and gain < 0.10:
    self.close_position(position, current_price, '5MIN_RULE')
```
**Key**: `position['remaining'] == 1.0` - only applies BEFORE taking partials

**Broken logic in extracted strategy module:**
```python
# Missing the remaining == 1.0 check!
if gain < self.five_minute_min_gain:
    return True, "5MIN_RULE"
```

**Impact on Results:**
- Oct 2 backtest WITHOUT fix: -$11,285 (88% losers)
- Oct 2 backtest WITH fix: -$3,401 (70% improvement)
- Oct 2 live trading (used original embedded logic): +$1,692 ✅

**Why This Matters:**
- After taking 50% partial profit, the original logic STOPS checking the 5-minute rule
- This allows profitable positions to run until EOD or target
- Examples from Oct 2 live trading:
  - AMAT: Took 1 partial, then held until EOD → +$2,420
  - LRCX: Took 1 partial, then held until EOD → +$1,425
  - INTC: Took 2 partials, then held until EOD → +$863

**The Fix:**
```python
# CRITICAL: Only apply 5-minute rule if NO partials taken yet
# If we've taken partials (remaining < 1.0), let the runner work
if position.get('remaining', 1.0) < 1.0:
    return False, None

# ... rest of 5-min rule logic
```

**Status**: ✅ **FIXED** (Line 244-247 in `trader/strategy/ps60_strategy.py`)

**Verification**: Full audit documented in `trader/STRATEGY_MODULE_AUDIT.md`

#### Bug #4: Backtester Not Respecting Entry Time Window (October 3, 2025)

**Issue**: Backtester was ignoring `min_entry_time` configuration
- **Location**: `trader/backtest/backtester.py` lines 202-206
- **Impact**: Backtest entering trades at 9:30 AM even when config said 10:13 AM
- **Root Cause**: Hardcoded check for `hour >= 15` (3 PM cutoff) instead of using strategy module's `is_within_entry_window()`

**The Bug:**
```python
# WRONG - only checks if NOT after 3 PM
time_cutoff = (hour >= 15)
if position is None and not time_cutoff:
    # Enter trade...
```

**The Fix:**
```python
# CORRECT - uses strategy module to check min AND max entry time
within_entry_window = self.strategy.is_within_entry_window(timestamp)
if position is None and within_entry_window:
    # Enter trade...
```

**Status**: ✅ **FIXED** (Line 203 in `trader/backtest/backtester.py`)

#### Bug #5: Exit Time Display Corruption (October 3, 2025) - Cosmetic

**Issue**: Position manager shows exit times as current wall clock time instead of actual bar timestamp
- **Location**: `trader/strategy/position_manager.py` in `close_position()`
- **Impact**: All backtest exit times show as 11:45 PM instead of actual market time
- **Root Cause**: Uses `datetime.now()` for exit_time instead of accepting timestamp parameter

**Example of Bug:**
- Trade actually exits at 10:28 AM
- Display shows: "Exit: $219.49 @ 23:44" (11:44 PM - completely wrong!)

**Status**: ⚠️ **NOT FIXED** - Cosmetic issue, doesn't affect P&L calculations

### October 1, 2025 Trading Session

**Paper Trading Results (R/R 1.5:1 filter)**:
- **Realized P&L**: +$756.19
- **Win Rate**: 66.7% (2 winners, 1 loser)
- **Trades**: 3 total (COIN, PLTR, TSLA)

| Symbol | Entry | Exit | P&L | Result |
|--------|-------|------|-----|--------|
| COIN | $346.55 | $346.35 | -$29 | Quick stop |
| PLTR | $183.10 | $185.26 | +$378 | Winner (partial + target) |
| TSLA | $447.13 | $450.25 | +$423 | Winner (partial + target) |

**Overnight Positions** (due to timezone bug):
- PLTR: 250 shares @ $183.10 (runner position)
- COIN: 171 shares @ $346.55 (runner position)
- TSLA: 105 shares @ $447.13 (runner position)

**Key Observations**:
1. ✅ Lower R/R filter (1.5 vs 2.0) allowed PLTR (1.65) and TSLA (1.56) to qualify - both were winners
2. ✅ Entry logic working well - caught pivot breaks
3. ✅ Partial profit-taking working - locked in gains early
4. ❌ EOD close bug prevented closing runners at 3:55 PM EST
5. ✅ Trader performed well during live market conditions

### September 2025 Monthly Backtest - FINAL RESULTS

**Status**: ✅ COMPLETE (October 1, 2025)

**Configuration**:
- **Scanner**: Production scanner (`stockscanner/scanner.py`)
- **Filters**: Score ≥75, R/R ≥1.5
- **No Look-Ahead Bias**: Scanner uses previous day's data only

**Performance Results**:
- **Total Trading Days**: 22
- **Total Trades**: 183
- **Total P&L**: **+$8,895.23** (8.9% return on $100k account)
- **Win Rate**: 39.9%
- **Avg P&L per Day**: +$404.33
- **Avg Trades per Day**: 8.3

**Best Trading Days**:
1. Sept 23: +$4,882.50 (3 trades, 100% win rate)
2. Sept 12: +$2,069.80 (9 trades)
3. Sept 30: +$1,607.50 (10 trades)
4. Sept 17: +$1,395.00 (4 trades)
5. Sept 10: +$1,125.00 (7 trades)

**Worst Trading Days**:
1. Sept 22: -$2,185.00 (25 trades - overtrading)
2. Sept 5: -$1,015.00 (15 trades)
3. Sept 2: -$607.06 (11 trades)

**Critical Finding - Scanner Quality Matters**:
The type of scanner used made a MASSIVE difference:

| Scanner | P&L | Win Rate | Difference |
|---------|-----|----------|------------|
| **Production Scanner** | **+$8,895** | 39.9% | Baseline |
| Embedded Scanner | -$7,986 | 33.6% | -$16,881 worse! |

**Key Insights**:
1. ✅ Strategy IS profitable with proper scanner (+8.9% monthly)
2. ✅ Production scanner's sophisticated scoring works
3. ⚠️ Lower trade volume (8.3/day) but higher quality
4. ⚠️ Need to avoid overtrading (Sept 22: 25 trades = biggest loss)
5. ✅ Win rate of 40% is sufficient with proper R/R management

**Critical Finding - Look-Ahead Bias**:
- **Discovery Date**: September 30, 2025
- **Impact**: Scanner was using same-day data, creating unrealistic backtest results
- **Sept 30 Comparison**:
  - WITH bias: +$1,441 (unrealistic)
  - WITHOUT bias: -$1,528 (realistic)
  - **Difference**: ±$2,969 swing!

**Fix Applied**:
- Scanner now uses data from day BEFORE trading day
- Proper walk-forward testing methodology
- All September scanner files regenerated without bias
- Final backtest uses production scanner with proper historical dates

### Next Steps

1. ✅ **Paper trade 2-4 weeks** minimum
2. ✅ **Track performance daily** vs backtest
3. ✅ **Adjust filters** based on live results (tested 1.5 R/R)
4. ✅ **Document edge cases** and anomalies
5. ✅ **Fix timezone bug** in EOD close logic
6. ✅ **Complete September backtest** and analyze results
7. ⏳ **Test LONGS ONLY strategy** (scanner support levels unreliable)
8. ⚠️ **Only go live** after consistent results

## LONGS ONLY Analysis (October 4, 2025)

### Problem Discovery: Scanner Support Levels Unreliable

**Root Cause Analysis**:
- Deep analysis of 14 SHORT STOP losses using IBKR historical 1-minute bars
- Found that 42.9% of stopped-out shorts went back to profit zone
- However, only 21.4% would be winners even with proper stop placement
- **78.6% of shorts would still lose** even with correct stops (0.5% above entry)
- **Conclusion**: Scanner support level predictions are fundamentally unreliable

**Analysis Script**: `trader/analyze_short_stops.py`
**Results File**: `trader/short_stop_analysis.json`

### Configuration Change: Disable Shorts

**File**: `trader/config/trader_config.yaml` (lines 62-64)
```yaml
# Direction filter (testing scanner quality)
enable_shorts: false              # DISABLED - Scanner support levels unreliable
enable_longs: true                # ENABLED - Scanner resistance levels more reliable
```

**Implementation**: `trader/backtest/backtester.py` (lines 67-69, 215, 226, 236, 247)
```python
# Direction filters (for testing scanner quality)
self.enable_shorts = self.config['trading'].get('enable_shorts', True)
self.enable_longs = self.config['trading'].get('enable_longs', True)

# Entry checks now include direction filters
if long_attempts < max_attempts and price > resistance and self.enable_longs:
elif short_attempts < max_attempts and price < support and self.enable_shorts:
```

### Backtest Results: LONGS ONLY vs LONGS + SHORTS

**Test Period**: September 1-14, 2025 (first two weeks)

| Metric | LONGS ONLY | LONGS + SHORTS | Difference |
|--------|------------|----------------|------------|
| Total P&L | +$1,425 | TBD | TBD |
| Win Rate | 16.7% | TBD | TBD |
| Total Trades | 42 | TBD | TBD |
| Trading Days | 8 | 8 | Same |
| Winning Days | 1/8 (12.5%) | TBD | TBD |
| Monthly Return | +1.42% | TBD | TBD |

**Key Observations (LONGS ONLY)**:
- Only 1 winning day out of 8 (Sept 4: +$7,599)
- Saved by single huge winner: NFLX +$8,140
- Very low win rate (16.7%) but positive overall
- Sept 2 had NO trades (shorts disabled, no long triggers)
- Sept 12 was worst day: -$2,956

**Hypothesis**: Scanner resistance levels (for longs) may be more reliable than support levels (for shorts).

### Improved Logging System

**New Features**:
- Created `trader/backtest/logs/` directory for all backtest logs
- Timestamped log files: `{run_name}_{YYYYMM}_{timestamp}.log`
- Dual output: console + persistent log file
- Date range support: `--start-day` and `--end-day` parameters
- Run naming: `--run-name` for organizing different test configurations

**Example Usage**:
```bash
cd trader/backtest
python3 run_monthly_backtest.py \
  --year 2025 --month 9 \
  --start-day 1 --end-day 14 \
  --run-name longs_only \
  --account-size 100000
```

**Log Files**:
- `logs/longs_only_202509_20251004_012008.log` - LONGS ONLY Sept 1-14
- All backtest output preserved with timestamps for analysis

### Next Analysis Steps

1. ⏳ Run LONGS ONLY backtest for last week of September (Sept 23-30)
2. ⏳ Run full month LONGS + SHORTS backtest for comparison
3. ⏳ Compare win rates, P&L, and trade quality between strategies
4. ⏳ Decide: LONGS ONLY or fix scanner support level detection
5. ⏳ If LONGS ONLY is better, test on full September month

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

**Why**: The progress log serves as the single source of truth for all implementation history, making it easy to understand the project's evolution and decisions.

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

## 🚀 Phase 7: Delayed Momentum Detection & Dynamic Targets (October 13, 2025)

### Problem Discovery: BB Stock Missed Trade

**Scenario**: BB broke resistance ($4.58) on Oct 6 and ran to $4.80 (+4.8%), but wasn't traded.
- Scanner metrics: Score 105, R/R 5.0:1 (excellent setup)
- Initial breakout: 0.53x volume (classified as WEAK)
- Subsequent momentum: 3.63x volume at bar 263 (meets 2.0x threshold!)

**Root Cause Analysis**:
1. ~~**Volume Sustainability Bug**~~: FIXED - Removed lines 196-210 from breakout_state_tracker.py
   - Was requiring sustained high volume over 3+ bars
   - Natural pattern: volume spikes then normalizes
   - Example: BBBY had 5.78x volume on breakout but downgraded to WEAK because volume decreased afterward

2. **State Machine Never Re-Checked Momentum**: FIXED - Added delayed momentum detection
   - BB classified as WEAK at bar 192 (initial breakout)
   - State machine counted bars held but never rechecked volume
   - BB showed 3.63x volume at bar 263 but wasn't detected

3. **Room-to-Run Filter Used target1 Instead of target3**: FIXED - Dynamic target selection
   - BB at bar 263: price=$4.63, target1=$4.64 (only 0.22% room) ❌
   - But target3=$4.77 (2.2% room) ✅
   - Filter was rejecting entries that already passed target1 but had room to target2/target3

### Solutions Implemented

#### 1. Removed Volume Sustainability Filter (breakout_state_tracker.py:193-204)

**Before (BUGGY)**:
```python
if is_strong_volume and is_large_candle:
    breakout_type = 'MOMENTUM'

    # Check if volume was sustained over last 3 bars
    recent_vol = sum(bars[i].volume for i in range(current_idx-2, current_idx+1)) / 3
    avg_vol = sum(bars[i].volume for i in range(current_idx-22, current_idx-2)) / 20

    # Require recent volume to be elevated (≥1.5x average)
    if recent_vol < avg_vol * 1.5:
        breakout_type = 'WEAK'  # Downgrade!
```

**After (FIXED)**:
```python
if is_strong_volume and is_large_candle:
    breakout_type = 'MOMENTUM'

    # REMOVED: Volume Sustainability Check (Oct 13, 2025)
    # Now: Only check volume on 1-minute breakout candle itself
```

**Impact**: Stops rejecting valid high-volume breakouts like BBBY (5.78x volume).

#### 2. Delayed Momentum Detection (ps60_entry_state_machine.py:141-205)

**New Logic**: Re-check momentum on EVERY subsequent 1-minute candle after WEAK classification

```python
# STATE 3/4: WEAK_BREAKOUT_TRACKING or PULLBACK_RETEST
elif state.state.value in ['WEAK_BREAKOUT_TRACKING', 'PULLBACK_RETEST']:
    # PHASE 7 (Oct 13, 2025): Re-check for momentum on subsequent 1-minute candles
    bars_per_candle = 12  # 12 five-second bars = 1 minute
    bars_into_candle = current_idx % bars_per_candle

    # Check if we're at a new 1-minute candle close
    if bars_into_candle == (bars_per_candle - 1) and current_idx > state.candle_close_bar:
        # Calculate this candle's volume and size
        candle_volume = sum(b.volume for b in candle_bars)
        volume_ratio = candle_volume / avg_candle_volume
        candle_size_pct = abs(candle_close - candle_open) / candle_open

        # Check if this candle meets MOMENTUM criteria
        is_strong_volume = volume_ratio >= strategy.momentum_volume_threshold  # 2.0x
        is_large_candle = candle_size_pct >= strategy.momentum_candle_min_pct  # 0.3%

        if is_strong_volume and is_large_candle:
            # Momentum detected on subsequent candle - upgrade to MOMENTUM entry!
            # Check remaining filters (choppy, room-to-run)
            if all_filters_pass:
                return True, f"MOMENTUM_BREAKOUT (delayed, {volume_ratio:.1f}x vol)"
```

**Key Features**:
- Checks EVERY 1-minute candle close (bars_into_candle == 11)
- Works in BOTH WEAK_BREAKOUT_TRACKING and PULLBACK_RETEST states
- Only checks candles AFTER initial breakout (current_idx > state.candle_close_bar)
- Still validates all filters (choppy, room-to-run) before entering

**Example with BB**:
- Bar 192: Initial breakout, 0.53x volume → WEAK
- Bar 263: 1-min candle close, 3.63x volume → MOMENTUM DETECTED!
- Bar 347: 1-min candle close, 5.09x volume → Another chance!
- Bar 383: 1-min candle close, 2.53x volume → Third chance!

#### 3. Dynamic Target Selection (backtester.py:462-470, 512-520)

**Problem**: Room-to-run filter always checked target1, rejecting entries after price passed it.

**Solution**: Always use the highest available target (target3 > target2 > target1).

**LONG Entries** (backtester.py:462-470):
```python
# PHASE 7 (Oct 13, 2025): Dynamic target selection - use highest available target
# Allows delayed momentum entries even after price passes target1
highest_target = stock.get('target3') or stock.get('target2') or stock.get('target1')

confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(
    bars, bar_count - 1, resistance, side='LONG',
    target_price=highest_target,  # Use highest available target
    symbol=stock['symbol'],
    cached_hourly_bars=cached_bars
)
```

**SHORT Entries** (backtester.py:512-520):
```python
# PHASE 7 (Oct 13, 2025): Dynamic target selection - use lowest available downside target
lowest_downside = stock.get('downside2') or stock.get('downside1')

confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(
    bars, bar_count - 1, support, side='SHORT',
    target_price=lowest_downside,  # Use lowest available downside target
    symbol=stock['symbol'],
    cached_hourly_bars=cached_bars
)
```

**Impact with BB**:
- Bar 263: price=$4.63, target1=$4.64 (0.22% room) ❌ BLOCKED BEFORE
- Bar 263: price=$4.63, target3=$4.77 (2.2% room) ✅ PASSES NOW
- Allows entry even after target1 is reached if target2/target3 still have room

### Expected Benefits

1. **Capture Delayed Momentum Breakouts**: Stocks like BB that start weak but build momentum
2. **Multi-Target Optimization**: Can still enter after target1 if target2/target3 have room
3. **Continuous Monitoring**: Never miss momentum that appears later in the setup
4. **Natural Volume Patterns**: Accept volume spikes without requiring sustained elevation

### Files Modified

| File | Lines | Change |
|------|-------|--------|
| `trader/strategy/breakout_state_tracker.py` | 196-210 | Removed volume sustainability filter |
| `trader/strategy/ps60_entry_state_machine.py` | 141-205 | Added delayed momentum detection |
| `trader/backtest/backtester.py` | 462-470 | Dynamic target selection (LONG) |
| `trader/backtest/backtester.py` | 512-520 | Dynamic target selection (SHORT) |

### Testing Required

1. ✅ Verify BB gets entered on Oct 6 backtest at bar 263 (3.63x volume)
2. ⏳ Run full Oct 6-9 backtest to measure impact on trade count and P&L
3. ⏳ Check if other missed opportunities (XLOV, etc.) now get captured
4. ⏳ Verify no false entries from overly aggressive delayed checks

### Future Enhancement: Dynamic Stop Adjustment

**Planned**: Automatically adjust stops as price crosses intermediate targets.

**Example**:
- Entry at $4.58 (resistance), stop at $4.58, aiming for target3=$4.77
- Price reaches $4.65 (crosses target1=$4.64) → Move stop to $4.64 (lock profit)
- Price reaches $4.71 (crosses target2=$4.70) → Move stop to $4.70 (lock more profit)
- Now price can run to target3 with reduced risk

**Benefits**: Lock in profits while letting winners run to maximum targets.
