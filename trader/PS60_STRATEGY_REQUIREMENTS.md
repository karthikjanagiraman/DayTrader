# PS60 Automated Trading Strategy - Complete Requirements Specification

**Last Updated**: October 4, 2025
**Version**: 2.0
**Status**: Active Development

This is the **master requirements document** for the PS60 automated trading strategy. All other requirement documents are superseded by this consolidated specification.

---

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Entry Logic](#entry-logic)
3. [Exit Logic](#exit-logic)
4. [Risk Management](#risk-management)
5. [Filters & Validation](#filters--validation)
6. [Position Management](#position-management)
7. [Configuration](#configuration)
8. [Implementation Status](#implementation-status)

---

## Strategy Overview

### Core Concept
The PS60 strategy is a **scanner-driven breakout trading system** based on Dan Shapiro's PS60 Process. The scanner identifies resistance/support levels pre-market, and the trader executes when these pivots are broken with proper confirmation.

### Key Principles
- **Scanner-driven**: All pivots are pre-identified by the scanner
- **Confirmation-based**: Never enter on first tick, require confirmation
- **Risk-first**: Position sizing based on stop distance (1% account risk)
- **Intraday only**: Close all positions by 3:55 PM (flat EOD)

---

## Entry Logic

### Two-Scenario Retest Confirmation Strategy

The entry logic uses a **two-scenario approach** to distinguish between strong breakouts and weak pokes that need retest confirmation.

#### Scenario 1: Weak Breakout → Retest Entry

**When to Apply**:
- Price breaks resistance with move **<1%** above resistance
- This is considered a "weak breakout"

**Entry Logic**:
1. **Do NOT enter** on first weak break
2. Wait for price to **fall back below resistance**
3. Watch for **retest within 5-minute window**
4. **Enter on retest** when price breaks resistance again
5. **Stop placement**: **0.3% below resistance** (buffer needed, it's second attempt)

**Example (LONG)**:
```
Resistance: $100
1. Price breaks to $100.50 (0.5% above) → WAIT (weak break)
2. Price falls to $99.80 → Mark for retest
3. Price breaks to $100.60 → ENTER (retest confirmed)
4. Stop: $99.70 (0.3% below $100 resistance)
```

**Rationale**:
- Weak breakouts often fail
- Retest shows genuine buying pressure
- 0.3% buffer gives room for noise on second attempt

#### Scenario 2: Strong Breakout → Immediate Entry

**When to Apply**:
- Price breaks resistance with move **≥1%** above resistance
- Price **sustains** above resistance (doesn't whipsaw back)

**Entry Logic**:
1. Verify move is ≥1% above resistance
2. Check price has NOT fallen below resistance in recent bars (last 5 bars = 25 seconds)
3. **Enter immediately** (strong confirmation)
4. **Stop placement**: **At exact resistance** (0% buffer)

**Example (LONG)**:
```
Resistance: $100
1. Price breaks to $101.20 (1.2% above) → CHECK sustain
2. Last 5 bars all above $100 → ENTER (strong sustained)
3. Stop: $100.00 (at resistance, no buffer)
```

**Rationale**:
- Strong 1%+ move indicates commitment
- Sustained action (no whipsaw) validates strength
- Resistance becomes support (0% buffer at pivot)

#### Re-Entry Logic (Scenario 2)

**If stopped out from strong breakout entry**:
- Stock fell below resistance → Stop hit
- **Can re-enter** if price breaks resistance again
- This re-entry is treated as **Scenario 1 (Retest)**
- Use **0.3% buffer stop** on re-entry
- **Max 2 total attempts** per pivot (initial + 1 re-entry)

**Example**:
```
Resistance: $100
1. Strong break to $101.20 → ENTER with stop at $100
2. Stopped at $100 → First attempt failed
3. Price breaks to $100.60 → RE-ENTER (now a retest)
4. Stop: $99.70 (0.3% buffer for retest)
```

### Entry Validation Checklist

Before entering, verify:
- [ ] Price is above resistance (LONG) or below support (SHORT)
- [ ] Within entry time window (9:45 AM - 3:00 PM)
- [ ] Not already in position for this symbol
- [ ] Attempt count < max attempts (2)
- [ ] Gap filter passed (if gap occurred)
- [ ] Not in avoid list (SPY, QQQ, DIA, IWM for shorts)

### SHORT Entry Logic

Same two-scenario logic applies for shorts:
- **Weak break (<1% below support)**: Wait for retest, 0.3% buffer above support
- **Strong break (≥1% below support)**: Enter immediately, stop at support (0% buffer)

---

## Exit Logic

### Partial Profit Taking (1R-based)

**Philosophy**: Take profits at 1R (when profit = risk), not percentage-based.

**1R Calculation**:
```python
risk_per_share = entry_price - stop_price
profit_1R = entry_price + risk_per_share  # Profit = Risk
```

**Example**:
```
Entry: $100
Stop: $99.50
Risk: $0.50
1R Target: $100.50 (when profit equals risk)
```

**Partial Exit Schedule**:
1. **50% at 1R** (when profit = risk)
   - Sell half position
   - Move stop to **breakeven** on remaining 50%
2. **25% at Target1** (scanner-provided target, typically ~2R)
   - Sell quarter of original position
   - Keep trailing stop on remaining 25%
3. **25% runner** with trailing stop
   - Trail by 1% below recent high
   - Close at 3:55 PM if still open

### Stop Management

**Initial Stop Placement**:
- **Retest entries**: 0.3% below resistance (above support for shorts)
- **Strong breakout entries**: At exact resistance (0% buffer)

**Stop Updates**:
1. **After 50% partial (1R)**: Move stop to breakeven
2. **After 25% partial (Target1)**: Keep trailing stop active
3. **Runner (final 25%)**: Trail stop 1% below recent high

**Stop Types**:
- Initial stop: Fixed at entry
- Breakeven stop: At entry price (after 1R partial)
- Trailing stop: Percentage-based (1% trail)

### Time-Based Exits

**5-7 Minute Rule** (ONLY before taking partials):
- If **no partials taken** after 5-7 minutes → Exit entire position
- Indicates "reload seller/buyer" blocking the move
- **CRITICAL**: Rule does NOT apply after taking partials (let runners work)

**End of Day Close**:
- Close ALL positions at **3:55 PM** (5 min before close)
- No exceptions - flat by EOD

### Exit Reasons

All exits must be tagged with reason:
- `PARTIAL_1R` - 50% at 1R profit
- `PARTIAL_TARGET1` - 25% at scanner target1
- `STOP` - Stop loss hit
- `BREAKEVEN_STOP` - Breakeven stop hit after partial
- `TRAIL_STOP` - Trailing stop hit on runner
- `5MIN_RULE` - No movement within 5-7 minutes
- `EOD_CLOSE` - End of day liquidation

---

## Risk Management

### Position Sizing

**1% Account Risk Rule**:
```python
account_value = 100000
risk_per_trade = account_value * 0.01  # $1,000 risk per trade
stop_distance = abs(entry_price - stop_price)
shares = risk_per_trade / stop_distance

# Example:
# Entry: $100, Stop: $99.50
# Risk: $0.50 per share
# Shares: $1,000 / $0.50 = 2,000 shares
```

**Position Limits**:
- Min shares: 10
- Max shares: 1,000 (cap for safety)
- Max positions: 5 concurrent
- Max daily loss: 3% (circuit breaker)

### Risk/Reward Requirements

**Minimum R/R Ratio**: 1.0:1 (changed from 2.0:1)
- Distance to target1 ≥ distance to stop
- Scanner calculates R/R during pre-market scan
- Filter out setups with R/R < 1.0

**Target Distance**:
- Target1: Conservative (scanner-calculated using measured moves)
- Target2: Standard (scanner-calculated)
- Must have reasonable room to run (≥3% to target after gaps)

---

## Filters & Validation

### Gap Filter

**Problem**: When stock gaps overnight, it may already be through resistance, invalidating the setup.

**Three-Tier Gap Filter**:

1. **Small Gaps (<1% through pivot)**: Allow trade
   - Gap insignificant, pivot still valid

2. **Large Gaps (>1%) with Room (>3% to target)**: Allow trade
   - Gap significant BUT plenty of upside remains

3. **Large Gaps (>1%) without Room (<3% to target)**: Skip trade
   - Gap ate up the move, risk/reward no longer favorable

**Implementation**:
```python
if previous_close < resistance and current_price > resistance:
    gap_pct = ((current_price - resistance) / resistance) * 100

    if gap_pct <= 1.0:
        # Small gap - OK
        return False, None

    room_to_target = ((target1 - current_price) / current_price) * 100

    if room_to_target >= 3.0:
        # Big gap but room remains - OK
        return False, None

    # Gap ate the move - SKIP
    return True, f"Gap {gap_pct:.1f}% through pivot, only {room_to_target:.1f}% to target"
```

**Configuration**:
```yaml
filters:
  enable_gap_filter: true
  max_gap_through_pivot: 1.0    # 1% threshold
  min_room_to_target: 3.0       # 3% minimum room
```

### Scanner Filters

**Pre-Trade Filters**:
- Min scanner score: 70 (quality threshold)
- Min R/R ratio: 1.0:1
- Max distance to pivot at scan time: 2% (don't chase)

**Symbol Filters**:
- Avoid index shorts: SPY, QQQ, DIA, IWM (too choppy)
- Blacklist: User-configurable symbol list

### Time Filters

**Entry Window**:
- Min entry time: **9:45 AM** (avoid opening volatility)
- Max entry time: **3:00 PM** (no entries in last hour)

**Rationale**:
- 9:30-9:45 AM: Opening range, too volatile
- After 3:00 PM: Not enough time for trade to develop

---

## Position Management

### Attempt Tracking

**Max 2 Attempts Per Pivot**:
- Track long_attempts and short_attempts separately
- Increment after each entry (not just stops)
- Reset only when pivot changes or new trading day

**Example**:
```python
# TSLA resistance $450
long_attempts = 0

# First entry at $451 → long_attempts = 1
# Stopped out
# Second entry at $451.20 → long_attempts = 2
# Stopped out
# No more entries for TSLA today (max attempts reached)
```

### Position States

**State Machine**:
1. `NO_POSITION` - Not in trade
2. `FULL_POSITION` - 100% position, no partials taken
3. `PARTIAL_1_TAKEN` - 50% sold at 1R, 50% remaining
4. `PARTIAL_2_TAKEN` - 75% sold (50% + 25%), 25% runner remaining

**State Transitions**:
```
NO_POSITION → (entry) → FULL_POSITION
FULL_POSITION → (1R hit) → PARTIAL_1_TAKEN
PARTIAL_1_TAKEN → (Target1 hit) → PARTIAL_2_TAKEN
ANY_STATE → (stop/EOD) → NO_POSITION
```

### Commission & Slippage

**Commissions**:
- $0.005 per share (IBKR standard)
- Applied on entry and all exits
- Deducted from P&L

**Slippage Simulation**:
- Entry slippage: 0.1% (buy at worse price)
- Exit slippage: 0.1% (sell at worse price)
- Stop slippage: 0.2% (worse execution on stops)

**Configuration**:
```yaml
slippage:
  enabled: true
  entry_slippage: 0.001      # 0.1%
  exit_slippage: 0.001       # 0.1%
  stop_slippage: 0.002       # 0.2%

commissions:
  enabled: true
  per_share: 0.005           # $0.005
```

---

## Configuration

### Complete Configuration Reference

```yaml
# trader/config/trader_config.yaml

trading:
  account_size: 100000
  risk_per_trade: 0.01           # 1% risk
  max_positions: 5
  max_daily_loss: 0.03           # 3% circuit breaker

  position_sizing:
    min_shares: 10
    max_shares: 1000

  entry:
    use_market_orders: true
    min_entry_time: "09:45"      # Wait 15 min after open
    max_entry_time: "15:00"      # No entries after 3 PM

  exits:
    partial_1_pct: 0.50          # 50% at 1R
    partial_2_pct: 0.25          # 25% at Target1
    runner_pct: 0.25             # 25% runner
    eod_close_time: "15:55"      # Close all 5 min before close

  trailing_stop:
    enabled: true
    type: "percentage"
    percentage: 0.01             # 1% trail
    min_profit_to_activate: 0.02 # Activate after 2% profit

  risk:
    breakeven_after_partial: true
    close_all_by_eod: true

  # Retest confirmation strategy (Oct 4, 2025)
  confirmation:
    enabled: true
    retest_strategy_enabled: true
    strong_breakout_threshold: 0.01    # 1% = strong
    retest_window_minutes: 5           # 5-min retest window
    sustained_check_bars: 5            # Check last 5 bars (25 sec)
    stop_buffer_pct: 0.003             # 0.3% buffer for retests

    # Original confirmation (volume, momentum) - still used as secondary
    volume_surge_required: true
    volume_surge_multiplier: 1.5
    momentum_candle_required: true
    momentum_candle_size: 1.5
    sustained_break_minutes: 2

  # Setup types
  setup_types:
    breakout: true
    bounce: true                       # Pullback + reversal (not implemented)
    rejection: false                   # Fade setups (not implemented)

  # Direction filter
  enable_shorts: false                 # Scanner support unreliable
  enable_longs: true

  attempts:
    max_attempts_per_pivot: 2          # Max 2 tries per pivot

filters:
  min_score: 70
  min_risk_reward: 1.0                 # Changed from 2.0 to 1.0
  max_dist_to_pivot: 2.0               # Max 2% from pivot at scan

  # Gap filter (Oct 4, 2025)
  enable_gap_filter: true
  max_gap_through_pivot: 1.0           # 1% threshold
  min_room_to_target: 3.0              # 3% room needed

  # Symbol filters
  avoid_index_shorts: true
  avoid_symbols:
    - "SPY"
    - "QQQ"
    - "DIA"
    - "IWM"

slippage:
  enabled: true
  percentage: 0.001                    # 0.1% entry/exit
  stop_slippage: 0.002                 # 0.2% stop slippage

commissions:
  enabled: true
  per_share: 0.005

ibkr:
  host: "127.0.0.1"
  port: 7497                           # Paper trading
  client_id: 2001

scanner:
  output_dir: "../stockscanner/output/"

logging:
  log_dir: "./logs/"
  log_level: "INFO"
  log_trades: true
  save_daily_report: true
```

---

## Implementation Status

### ✅ Completed (Phase 1)

**Core Strategy**:
- [x] Two-scenario retest confirmation logic
- [x] 1R-based partial profit taking
- [x] Breakeven stop management
- [x] 5-7 minute rule (only before partials)
- [x] End-of-day close (3:55 PM)

**Entry Logic**:
- [x] Weak breakout detection (<1%)
- [x] Strong breakout detection (≥1% sustained)
- [x] Retest pattern identification
- [x] Stop placement based on scenario (0% or 0.3% buffer)

**Filters**:
- [x] Gap filter (3-tier logic)
- [x] Scanner score filter (min 70)
- [x] R/R filter (min 1.0:1)
- [x] Time window filter (9:45-3:00 PM)
- [x] Max attempts per pivot (2)
- [x] Symbol blacklist (index shorts)

**Risk Management**:
- [x] 1% account risk position sizing
- [x] Slippage simulation (0.1-0.2%)
- [x] Commission costs ($0.005/share)
- [x] Daily loss circuit breaker (3%)

**Backtesting**:
- [x] IBKR 5-second bar historical data
- [x] Position manager integration
- [x] Trade logging with all details
- [x] Monthly backtest framework

### 🔧 In Progress (Phase 2)

**Setup Types**:
- [ ] Bounce setup detection (infrastructure ready, logic pending)
- [ ] Rejection/fade setup (infrastructure ready, logic pending)

**Advanced Features**:
- [ ] Volume confirmation (implemented but not enforced)
- [ ] Momentum candle confirmation (implemented but not enforced)

### 🔜 Planned (Phase 3)

**Live Trading**:
- [ ] Live paper trading validation (2-4 weeks)
- [ ] Real-time tick monitoring
- [ ] Order execution via IBKR API

**Optimization**:
- [ ] Parameter optimization based on backtest results
- [ ] Adaptive stop placement (market condition-based)
- [ ] Dynamic position sizing

**Monitoring**:
- [ ] Real-time dashboard
- [ ] Alert system (Telegram/SMS)
- [ ] Performance analytics

---

## Key Lessons Learned

### 1. Stop Placement is Critical
- Difference between 0% and 0.3% buffer: ~150% performance swing
- Retest entries need 0.3% buffer (second attempt)
- Strong breakout entries use 0% buffer (resistance becomes support)

### 2. Retest Strategy Reduces Whipsaws
- Entering on first weak poke = 70% failure rate
- Waiting for retest confirmation = 45-50% win rate
- Strong breakouts (≥1%) can enter immediately

### 3. Gap Filter is Essential
- 6 out of 17 setups filtered on Oct 2nd (35%)
- Gaps >1% through pivot with <3% room = skip
- Saves capital from low R/R setups

### 4. 5-Minute Rule Only Before Partials
- **CRITICAL**: Rule must NOT apply after taking partials
- After partials, let runners work to EOD or trail stop
- Premature exit after partials kills winners

### 5. Scanner Quality Matters
- Production scanner vs embedded scanner: $16,881 difference
- Support levels less reliable than resistance
- LONGS ONLY may be safer (scanner resistance more accurate)

---

## Version History

### Version 2.0 (October 4, 2025)
- ✅ Implemented two-scenario stop placement
  - Retest entries: 0.3% buffer
  - Strong breakouts: 0% buffer (at resistance)
- ✅ Fixed pullback detection (close vs wick)
- ✅ Consolidated all requirements into single document
- ✅ Updated configuration with all parameters

### Version 1.0 (October 3, 2025)
- ✅ Initial retest confirmation strategy
- ✅ 1R-based partials
- ✅ Gap filter implementation
- ✅ September backtest framework

---

## Related Documentation

- **`REQUIREMENTS_IMPLEMENTATION_LOG.md`** - Detailed implementation log (superseded)
- **`RETEST_CONFIRMATION_STRATEGY.md`** - Retest strategy deep-dive (superseded)
- **`PS60_PROFITABLE_STRATEGY_REQUIREMENTS.md`** - Original requirements (superseded)
- **`TRADER_REQUIREMENTS_SPEC.md`** - Initial spec (superseded)
- **`OCT2_RETEST_STRATEGY_FAILURE_ANALYSIS.md`** - Oct 2nd analysis
- **`IMPLEMENTATION_LESSONS_LEARNED.md`** - Bug fixes and lessons

**Note**: All previous requirement documents are now superseded by this consolidated specification. This is the single source of truth.

---

**Next Steps**:
1. Test updated stop placement logic with October 2nd backtest
2. Validate that retest entries get 0.3% buffer, strong breakouts get 0% buffer
3. Run September full month backtest with updated logic
4. Proceed to live paper trading if results validate

---

*This document is actively maintained. All strategy changes must be documented here.*
