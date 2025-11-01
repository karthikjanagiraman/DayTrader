# PS60 Trading System Configuration Details
## Complete Answer to Configuration Questions

**Date**: October 30, 2025
**Purpose**: Provide full picture of system design and implementation

---

## 1. Risk Model

### Per-Trade Risk
```yaml
risk_per_trade: 0.01  # 1% of account per trade
```

**Calculation Method**:
```python
risk_amount = account_size * 0.01  # $50,000 × 1% = $500
stop_distance = abs(entry_price - stop_price)
shares = int(risk_amount / stop_distance)
shares = max(10, min(shares, 1000))  # Constrained 10-1000 shares
```

### Position Sizing Rules
```yaml
position_sizing:
  min_shares: 10                    # Minimum position size
  max_shares: 1000                  # Hard cap (prevent over-concentration)
  max_position_value: 10000         # $10k max per position (20% of $50k account)
  max_position_pct: 100.0           # Legacy - superseded by max_position_value
```

**Example (October 21)**:
- NVDA entry: $181.08, stop: $181.41, distance: $0.33
- Risk: $500 / $0.33 = 1,515 shares → Capped at 1,000
- SMCI entry: $54.22, stop: $54.70, distance: $0.48
- Risk: $500 / $0.48 = 1,042 shares → Capped at 1,000

### Stop Type Hierarchy

**Primary Method** (Configurable):
```yaml
risk:
  stop_loss_method: 'candle'  # Current setting
```

**Option 1: Candle-Based Stops** (CURRENT - Active on Oct 21)
```yaml
candle_stop_lookback: 20              # Search last 20 bars
candle_stop_fallback_to_pivot: true   # Use pivot if no candle found
candle_stop_buffer_pct: 0.005         # ⭐ 0.5% buffer beyond candle extreme
```

**Logic**:
- For LONG: Find most recent RED candle, stop at its LOW - 0.5% buffer
- For SHORT: Find most recent GREEN candle, stop at its HIGH + 0.5% buffer
- Fallback: Use pivot level if no opposing candle in last 20 bars

**Actual October 21 Behavior** (no buffer applied):
- SMCI SHORT: Entry $54.22, green candle HIGH $54.70 → Stop $54.70 (0.88%)
- PATH SHORT: Entry $15.43, green candle HIGH $15.64 → Stop $15.64 (1.36%)
- PATH LONG: Entry $16.59, red candle LOW $16.46 → Stop $16.46 (0.78%)
- NVDA SHORT: Entry $181.08, green candle HIGH $181.41 → Stop $181.41 (0.18%)

**Option 2: ATR-Based Stops** (Available but not active)
```yaml
use_atr_stops: true
atr_stop_multiplier: 0.5              # Stop = Entry ± (0.5 × ATR)
atr_stop_period: 20                   # 20-bar ATR
min_stop_distance: 0.10               # Minimum $0.10
max_stop_distance_pct: 0.01           # Maximum 1.0%
```

**Option 3: Pivot-Based Stops** (Legacy)
```yaml
stop_at_pivot: false  # Disabled
```

### Breakeven After Partials
```yaml
risk:
  breakeven_after_partial: true
```

**Intended behavior**: After taking first partial (50% at 1R), move stop on remaining 50% to entry price.

**October 21 Reality**: ALL 5 trades showed `partials: 0`
- No partials were taken before exit
- Breakeven logic never triggered

---

## 2. Intended Holding Time / Payoff Profile

### Design Intent (From Requirements Spec)

**Primary Goal**: Measured-move breakouts to next supply/demand zone
- **Target holding**: 15-45 minutes to first target (Target1)
- **Runner holding**: 30-90 minutes (until trailing stop hit or Target2/3)

**Profit Targets** (Progressive Partials System):
```yaml
exits:
  use_sma_target_partials: true
  partial_size: 0.25              # 25% at each level
  max_partial_levels: 4           # Up to 4 exits

  # Priority 1: SMA resistance levels (hourly bars)
  sma:
    enabled: true
    periods: [5, 10, 20, 50, 100]
    timeframe: '1 hour'

  # Priority 2: Scanner targets
  scanner_targets:
    use_target1: true
    use_target2: true
    use_target3: false
```

**Intended flow**:
1. Enter on breakout confirmation
2. Take 25% at first SMA resistance or Target1 (typically 15-30 min)
3. Take 25% at next level
4. Take 25% at third level
5. Trail remaining 25% with 1% trailing stop

### 7-Minute Rule (Actual Implementation)

**Configuration**:
```yaml
risk:
  fifteen_minute_rule_enabled: true
  fifteen_minute_threshold: 7           # Exit after 7 minutes
  fifteen_minute_min_gain: 0.001        # Need 0.1% progress to avoid exit
```

**Purpose**: Exit if no progress after 7 minutes (PS60 methodology - detect "reload seller/buyer")

**October 21 Reality**:
- 4 of 5 trades exited via 7-minute rule
- Average duration when 7-min triggered: 7-13 minutes
- This indicates **scalp-like exits**, not measured moves

### Actual Payoff Profile (October 21)

```
Trade Durations:
- SMCI: 13 minutes → 7-min rule
- PATH SHORT: 7 minutes → 7-min rule
- PATH LONG: 7 minutes → 7-min rule
- NVDA SHORT #1: 6 minutes → STOP
- NVDA SHORT #2: 7 minutes → 7-min rule
```

**Conclusion**: System is behaving as a **7-minute scalper**, not a measured-move trader.

**Design vs Reality Gap**:
- **Designed for**: 15-45 min holds with progressive partials
- **Actually performing**: 6-13 min holds, all exits before ANY partials
- **Root cause**: Late CVD entries + tight stops = no room for partials

---

## 3. CVD Configuration

### Source Data

**Backtest** (October 21):
```yaml
backtest:
  use_tick_based_cvd: true            # Attempts tick data if available
  tick_cache_enabled: true            # Cache to avoid rate limits
```

**Reality on Oct 21**: Used **1-minute bar approximation** (tick data not available for that date)

**Bar Approximation Method**:
```python
# Simplified CVD calculation from 1-min bars
def calculate_cvd_from_bar(bar):
    range_size = bar.high - bar.low
    if range_size == 0:
        return 0

    # Buying volume: close in upper half
    buy_volume = bar.volume * (bar.close - bar.low) / range_size

    # Selling volume: close in lower half
    sell_volume = bar.volume * (bar.high - bar.close) / range_size

    # Imbalance percentage
    imbalance_pct = (sell_volume - buy_volume) / bar.volume * 100

    # Positive = selling pressure (BEARISH)
    # Negative = buying pressure (BULLISH)
    return imbalance_pct
```

### Imbalance Thresholds

**Sustained Path** (Patient - 3 consecutive candles):
```yaml
confirmation:
  cvd:
    imbalance_threshold: 10.0              # ⭐ 10% sustained imbalance required
    min_consecutive_bullish: 1             # 3 consecutive (config says 1, likely bug)
    min_consecutive_bearish: 1
```

**Aggressive Path** (Spike + confirmation):
```yaml
confirmation:
  cvd:
    strong_imbalance_threshold: 20.0       # ⭐ >20% initial spike
    strong_confirmation_threshold: 10.0    # ⭐ >10% on next candle
```

**October 21 Examples**:
```
SMCI Bar 37-43: CVD oscillated -26.5% → -7.9% → +7.9% → -36.4%
Never maintained 10% for 3 consecutive bars → BLOCKED

SMCI Bar 204-205: CVD spiked 46.5%, confirmed 17.0%
Strong aggressive confirmation → ENTERED
```

### Lookback & Calculation

```yaml
confirmation:
  cvd:
    slope_lookback: 2                      # 2 bars for trend detection
    continuous_monitoring: true
    max_monitoring_time_minutes: 999       # No timeout
    check_every_candle: true               # Check on EVERY 1-min bar
```

**Continuous Monitoring Flow**:
1. Breakout detected → Enter CVD_MONITORING state
2. Check CVD on every subsequent 1-min candle close
3. Two exit paths:
   - **Aggressive**: Spike ≥20% + confirm ≥10% → ENTER
   - **Sustained**: 3 consecutive bars ≥10% → ENTER
4. Monitor indefinitely until entry window closes (no timeout)

### Wick/Absorption Treatment

**Current implementation**: Uses bar approximation (close position in range)
- Does NOT explicitly handle wicks/absorption
- Simple ratio: close in upper half = buying, lower half = selling

**No debounce/smoothing**: CVD values used raw (no moving average)

### CVD Price Validation

```yaml
# Not explicitly in config, but implemented in code
```

**Logic** (from logs):
```python
# Block if CVD contradicts price action
if cvd_signal == 'BEARISH' and candle_color == 'GREEN':
    BLOCK("CVD BEARISH but GREEN candle")
elif cvd_signal == 'BEARISH' and candle_type == 'DOJI':
    BLOCK("CVD BEARISH but DOJI (no winner)")
```

**October 21 Impact**: 37 blocks due to CVD/price mismatch

---

## 4. Volume Normalization

### Calculation Method

**Configuration**:
```yaml
confirmation:
  min_initial_volume_threshold: 1.5       # Initial breakout must have 1.5x
  momentum_volume_threshold: 1.0          # Momentum entry needs 1.0x
  pullback_volume_threshold: 2.0          # Retest needs 2.0x
```

**Baseline Calculation** (from code inspection):
```python
# Volume is compared to session average (rolling baseline)
avg_volume = calculate_average_volume(bars[:current_bar_idx])
volume_ratio = current_bar.volume / avg_volume
```

**Normalization**: Uses **session-to-date average** (not opening hour or fixed baseline)

**Problem**: Early bars (9:30-10:00 AM) have volatile averages
- Bar at 9:45: Average based on only 15 bars
- Bar at 10:30: Average based on 60 bars
- This creates inconsistent thresholds during 9:45-10:15 window

**October 21 Examples**:
```
SMCI 09:46: Volume 0.57x → BLOCKED
SMCI 09:47: Volume 0.50x → BLOCKED
SMCI 09:48: Volume 0.72x → BLOCKED

Baseline likely artificially high from opening spike
```

### Volume Filter for CVD Entries

```yaml
confirmation:
  cvd:
    cvd_volume_threshold: 1.2              # ⭐ 1.2x required for CVD paths
```

**Applied to**: All CVD_MONITORING entries (aggressive + sustained)

**October 21**: All 5 entries went through CVD paths, so this threshold applied to all

---

## 5. Re-Entry Policy / Attempt Limits

### Configuration

```yaml
attempts:
  max_attempts_per_pivot: 2              # Max 2 entry attempts per pivot
```

### October 21 Behavior

**Actual attempt counts**:
```
SMCI: 52 attempts, 1 entry (attempt 36)
PATH: 40+ attempts, 2 entries
NVDA: 38 attempts, 2 entries
```

**Why so many attempts?**:
- Each 1-min bar closing through pivot = new attempt
- State machine resets after timeouts
- Counter resets after certain blocks

**Attempt tracking** (from logs):
```json
"attempt_count": "0/2"  // Shown in most entry decisions
```

**Issue**: The `0/2` count appears repeatedly, suggesting:
1. Counter never increments properly, OR
2. Counter resets on state transitions

**Technical blocks vs structural blocks**:
- **Technical block** (volume filter): Counter resets? (unclear)
- **Structural block** (price validation): Counter resets? (unclear)

**From logs**: Most sequences never reach 2nd attempt limit
- SMCI had 52 attempts over the day (counter clearly resetting)
- No evidence of 2-attempt limit being enforced

**Conclusion**: Re-entry limit is **NOT functioning as designed**. System is re-attempting indefinitely.

---

## 6. Slippage/Fill Assumptions

### Configuration

```yaml
trading:
  slippage:
    enabled: true
    percentage: 0.001                    # 0.1% slippage

  commissions:
    enabled: true
    per_share: 0.005                     # $0.005/share
```

### Backtest Implementation

**Entry slippage**:
```python
entry_price = bar.close * (1 + 0.001)  # LONG: +0.1%
entry_price = bar.close * (1 - 0.001)  # SHORT: -0.1%
```

**Stop slippage**:
```python
# From requirements: -1.2% slippage on stops
stop_exit_price = stop_price * (1 - 0.012)  # LONG
stop_exit_price = stop_price * (1 + 0.012)  # SHORT
```

**Target/7-min exit slippage**:
```python
exit_price = current_price * (1 - 0.001)  # LONG: -0.1%
exit_price = current_price * (1 + 0.001)  # SHORT: +0.1%
```

### Paper Trading Fills

**Entry orders**: MARKET orders (immediate fill)
```yaml
entry:
  use_market_orders: true
```

**Paper account behavior**:
- Fills at mid-point of bid/ask
- No partial fills in paper (assumes full fill)
- No queue position simulation

### Symbol-Specific Spread Assumptions

**Tight spreads** (Large caps):
- NVDA: ~$0.01-0.02 (0.01%)
- TSLA: ~$0.02-0.05 (0.01-0.02%)
- AMD: ~$0.01-0.02 (0.01%)

**Wide spreads** (Small caps):
- PATH ($15): ~$0.03-0.05 (0.2-0.3%)
- SMCI ($54): ~$0.05-0.10 (0.09-0.18%)
- HOOD ($40): ~$0.02-0.05 (0.05-0.12%)

**October 21 Reality**:
- PATH SHORT: Entry $15.43, exit $15.61 (against 7-min, likely wider spread)
- No explicit spread modeling beyond 0.1% slippage

**Recommendation**: Add symbol-specific slippage based on ATR or average spread

---

## 7. Objective & KPIs

### Design Objectives (From Requirements)

**Primary Goal**:
> "Automate PS60 strategy with robust risk management and profit-taking aligned with PS60 principles"

**Key Design Principles**:
1. **Risk Control**: Max 1% risk per trade, logical stop placement
2. **Selectivity**: Only trade setups with ≥2:1 R/R potential
3. **Confirmation**: Volume surge + momentum + sustained break
4. **Partial Profits**: Take 50% at 1R, move stop to BE, let 50% run

### Target Metrics (From Requirements)

```
Win Rate: ≥40-50% (with 2:1 R/R, this is profitable)
Profit Factor: ≥2.0
Risk/Reward per trade: ≥2:1
Expected R multiple per trade: 0.5R to 1.0R average
Max Drawdown: <10% per month
Daily P/L: Positive expectancy
```

### Tuning Philosophy

**Selectivity vs Frequency Trade-off**:
- **Current**: 1.2% entry rate (hyper-selective)
- **Design intent**: 5-8% entry rate (selective but active)

**Quality vs Quantity**:
- **Current focus**: Avoid all bad trades (98.8% rejection)
- **Better approach**: Accept some losers, capture more winners (30-40% win rate with 2:1 R/R)

### October 21 Performance vs Targets

| Metric | Target | Actual | Gap |
|--------|--------|--------|-----|
| Entry Rate | 5-8% | 1.2% | **Too selective** |
| Win Rate | 40-50% | 0% | **All losers** |
| Avg R Multiple | 0.5-1.0R | -0.5R | **Negative expectancy** |
| Profit Factor | ≥2.0 | 0.0 | **Complete failure** |
| Daily P/L | +$500-1,500 | -$1,412 | **Opposite direction** |

### KPIs by Priority

**Tier 1 (Critical)**:
1. Entry rate: 5-8% (balance selectivity with activity)
2. Win rate: 30-40% (with 2:1 R/R = profitable)
3. Avg winner/loser ratio: ≥2:1
4. Max drawdown: <3% per day

**Tier 2 (Important)**:
5. Profit factor: ≥2.0
6. Average holding time: 15-45 min
7. Partial success rate: ≥60% (first partial taken)
8. Runner success rate: ≥20% (hit Target2+)

**Tier 3 (Monitoring)**:
9. Filter effectiveness (blocks/value)
10. CVD confirmation rate
11. Entry delay (breakout to entry)
12. Stop-out rate vs 7-min rule rate

---

## 🎯 Critical Answers to Specific Questions

### Q: "All 5 trades show partials: 0; is that by design?"

**A: NO, this is a BUG or misconfiguration.**

**Design intent**:
- Take 25% partials at SMA resistance or Target1
- Progressive exits at 4 levels
- `use_sma_target_partials: true` is enabled

**Why it didn't happen**:
1. **7-minute rule triggered first** (4 of 5 trades)
   - Trades exited before reaching ANY resistance level
   - No time for partials (6-13 min holds)
2. **One stop hit** (NVDA in 6 minutes)
   - Stopped before reaching 1R or any target
3. **Late CVD entry + tight stops** = no room for profit development

**This reveals core system failure**: Trades can't survive long enough to hit partials.

### Q: "What's the actual holding time design?"

**A: CONFLICT between design and implementation**

**Design**: 15-45 min measured moves
**Implementation**: 7-minute scalp due to:
- 7-minute rule too aggressive
- CVD delays entry (3-4 bars)
- Stops too tight (average 0.7%)
- No momentum when finally entering

**Recommendation**: Either:
1. Remove/extend 7-minute rule to 15+ minutes, OR
2. Embrace scalp design: tighter targets, faster exits, higher entry rate

### Q: "CVD configuration complete?"

**A: YES, but fundamentally flawed**

**Complete config documented above**, but key issues:
1. **10% sustained threshold too strict** (market rarely maintains)
2. **1-minute bar approximation loses granularity** (need 5-sec or tick)
3. **No debounce/smoothing** (wild oscillations: -36% to +8%)
4. **Price validation too rigid** (blocks on DOJI, minor conflicts)

**All 5 CVD-confirmed entries lost** → CVD not adding value

---

## 📊 Summary Configuration Matrix

| Aspect | Design | Config | Oct 21 Reality |
|--------|--------|--------|----------------|
| Risk/Trade | 1% | 1% | 1% ✅ |
| Stop Method | Pivot/ATR | Candle | Candle (too tight) ❌ |
| Holding Time | 15-45 min | 7-min rule | 6-13 min ❌ |
| Partials | 25% at 4 levels | Enabled | 0 taken ❌ |
| CVD Source | Tick data | 1-min bars | 1-min bars ❌ |
| CVD Threshold | Configurable | 10% sustained | Too strict ❌ |
| Volume Baseline | Session avg | Session avg | Volatile in AM ⚠️ |
| Re-entry Limit | 2 attempts | 2 attempts | Not enforced ❌ |
| Slippage | 0.1-0.5% | 0.1% | Fixed (need symbol-specific) ⚠️ |
| Win Rate Target | 40-50% | N/A | 0% ❌ |
| Entry Rate Target | 5-8% | N/A | 1.2% ❌ |

---

**Configuration Complete**: October 30, 2025
**All questions answered with specifics from code and config**
**Ready for LLM analysis**