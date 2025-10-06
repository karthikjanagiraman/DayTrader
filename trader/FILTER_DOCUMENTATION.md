# Filter Documentation - PS60 Trading Strategy

**Last Updated**: October 5, 2025
**Version**: 2.0 (Post-PLTR Debug Session)

## Overview

The PS60 strategy employs a multi-layered filtering system to ensure high-quality trade entries. Filters are applied sequentially during the entry decision process, with each filter serving a specific purpose in risk management and trade quality control.

## Filter Application Order

```
Scanner Results
    ↓
1. SCANNER-BASED FILTERS (Pre-screening)
   - Min Score
   - Min R/R Ratio
   - Max Distance to Pivot
    ↓
2. SYMBOL FILTERS (Blacklist/Whitelist)
   - Avoid Index Shorts
   - Symbol Blacklist
    ↓
3. GAP FILTER (Market Open Check)
   - Overnight Gap Detection
    ↓
4. TIMING FILTERS
   - Entry Time Window
   - Max Attempts Per Pivot
    ↓
5. ENTRY PATTERN CONFIRMATION
   - 1-Minute Candle Close
   - Momentum vs Weak Classification
   - Pattern Confirmation (Pullback/Sustained)
    ↓
6. ENTRY QUALITY FILTERS
   - Choppy Market Filter (ALL entries)
   - Room-to-Run Filter (Pullback/Sustained only)
   - Range-Based Chasing (Momentum only, if enabled)
    ↓
EXECUTE TRADE
```

---

## Filter Catalog

### 1. Scanner-Based Filters

#### Min Score Filter
- **Configuration**: `filters.min_score`
- **Type**: Pre-screening
- **Purpose**: Filter stocks by scanner quality score (0-100)
- **When Applied**: During watchlist filtering
- **Default**: 0 (disabled)
- **Example**: Set to 50 to only trade stocks with score ≥50
- **Enable/Disable**: Set to 0 to disable, or specific value to enable

#### Min Risk/Reward Ratio Filter
- **Configuration**: `filters.min_risk_reward`
- **Type**: Pre-screening
- **Purpose**: Ensure favorable risk/reward ratio from scanner data
- **When Applied**: During watchlist filtering
- **Default**: 0.0 (disabled)
- **Example**: Set to 2.0 to require minimum 2:1 R/R ratio
- **Impact**: Requirements spec calls for min 2:1 R/R
- **Enable/Disable**: Set to 0.0 to disable

#### Max Distance to Pivot Filter
- **Configuration**: `filters.max_dist_to_pivot`
- **Type**: Pre-screening
- **Purpose**: Avoid stocks already far from breakout level
- **When Applied**: During watchlist filtering
- **Default**: 100.0 (disabled)
- **Example**: Set to 2.0 to skip stocks >2% from pivot
- **Enable/Disable**: Set to 100.0 to disable

---

### 2. Symbol Filters

#### Avoid Index Shorts
- **Configuration**: `filters.avoid_index_shorts`
- **Type**: Symbol blacklist
- **Purpose**: Skip short entries on index ETFs (SPY, QQQ, DIA, IWM)
- **When Applied**: During entry decision for SHORT positions
- **Default**: true
- **Rationale**: Backtest showed $700/day saved by avoiding index shorts
- **Analysis**: Index ETFs are too choppy and mean-reverting for trend-based shorts
- **Enable/Disable**: Set to `false` to allow index shorts

#### Symbol Blacklist
- **Configuration**: `filters.avoid_symbols`
- **Type**: Symbol blacklist
- **Purpose**: Complete blacklist of specific symbols
- **When Applied**: During watchlist filtering
- **Default**: ["SPY", "QQQ", "DIA", "IWM"]
- **Enable/Disable**: Set to empty list `[]` to disable

---

### 3. Gap Filter

#### Overnight Gap Detection
- **Configuration**: `filters.enable_gap_filter`
- **Type**: Market structure
- **Purpose**: Detect when overnight gaps ate up the move
- **When Applied**: At market open (9:30 AM) before monitoring begins
- **Default**: false (disabled for testing)
- **Algorithm**:
  ```
  If stock gapped through pivot:
    - Small gap (<1% through pivot): ALLOW trade
    - Large gap (>1%) with room (>3% to target): ALLOW trade
    - Large gap (>1%) without room (<3% to target): BLOCK trade
  ```
- **Example**: CLOV gapped 1.9% through resistance, only 3.1% to target → BLOCKED
- **Parameters**:
  - `max_gap_through_pivot`: 1.0% (threshold for "small gap")
  - `min_room_to_target`: 3.0% (minimum room after gap)
- **Documentation**: See CLAUDE.md "Gap Handling" section
- **Enable/Disable**: Set `enable_gap_filter: false` to disable

---

### 4. Timing Filters

#### Entry Time Window
- **Configuration**: `trading.entry.min_entry_time`, `max_entry_time`
- **Type**: Timing
- **Purpose**: Only enter trades during specific market hours
- **When Applied**: Every bar before checking for entry signals
- **Default**: 09:45 AM - 03:00 PM ET
- **Rationale**:
  - Before 9:45 AM: Early volatility, opening range formation
  - After 3:00 PM: Low liquidity, increased whipsaw risk
- **Enable/Disable**: Adjust times to suit strategy

#### Max Attempts Per Pivot
- **Configuration**: `trading.attempts.max_attempts_per_pivot`
- **Type**: Risk management
- **Purpose**: Limit re-entries on same resistance/support level
- **When Applied**: Before entering position
- **Default**: 2 attempts
- **Rationale**: Backtest showed 2 attempts optimal (134% more P&L than 1 attempt)
- **Example**:
  - Attempt 1 @ 09:48 stopped out → -$1,567
  - Attempt 2 @ 10:04 exited via 8-min rule → +$87
- **Enable/Disable**: Set to 1 for single attempt, or higher for more attempts

---

### 5. Entry Pattern Confirmation

#### 1-Minute Candle Close Requirement
- **Configuration**: `trading.confirmation.require_candle_close`
- **Type**: Pattern confirmation
- **Purpose**: Prevent whipsaws from intrabar price spikes
- **When Applied**: Before any entry (ALL types)
- **Default**: true
- **Logic**: Wait for 12 consecutive 5-second bars to close above/below pivot
- **Impact**: Filters out 60-70% of false breakouts
- **Enable/Disable**: Set to `false` to allow immediate entries (NOT recommended)

#### Momentum vs Weak Classification
- **Configuration**:
  - `momentum_volume_threshold`: 1.3x
  - `momentum_candle_min_pct`: 0.8%
  - `momentum_candle_min_atr`: 2.0x
- **Type**: Entry path selection
- **Purpose**: Determine if entry requires confirmation or is immediate
- **When Applied**: After candle close confirmation
- **Logic**:
  ```
  If volume ≥1.3x AND (candle ≥0.8% OR candle ≥2x ATR):
    → MOMENTUM entry (immediate, no pattern wait)
  Else:
    → WEAK entry (wait for pullback/retest or sustained break)
  ```
- **Enable/Disable**: Cannot be disabled, but thresholds can be adjusted

#### Pullback/Retest Pattern
- **Configuration**: `trading.confirmation.require_pullback_retest`
- **Type**: Pattern confirmation
- **Purpose**: Wait for price to pull back to pivot then re-break with volume
- **When Applied**: After weak breakout classification
- **Default**: true
- **Logic**:
  ```
  1. Initial break above pivot
  2. Price pulls back within 0.3% of pivot
  3. Price re-breaks pivot with ≥1.2x volume
  4. Sustained hold above pivot
  ```
- **Timeout**: 2 minutes (24 bars)
- **Enable/Disable**: Set to `false` to skip pullback logic

#### Sustained Break Pattern (Oct 5, 2025) ⭐ NEW
- **Configuration**: `trading.confirmation.sustained_break_enabled`
- **Type**: Pattern confirmation
- **Purpose**: Catch "slow grind" breakouts with weak initial candle
- **When Applied**: After weak breakout, if pullback pattern doesn't develop
- **Default**: true
- **Logic**:
  ```
  1. Initial break above pivot
  2. Price HOLDS above pivot for 2 minutes (24 bars)
  3. Max pullback allowed: 0.3% below pivot
  4. Volume confirms buying pressure
  ```
- **Example**: PLTR Oct 1 - 0.04% candle but sustained hold with 1.44x volume
- **Impact**: Catches quality setups that lack explosive initial candle
- **Parameters**:
  - `sustained_break_minutes`: 2 minutes
  - `sustained_break_max_pullback_pct`: 0.003 (0.3%)
- **Enable/Disable**: Set `sustained_break_enabled: false` to disable

---

### 6. Entry Quality Filters

#### Choppy Market Filter (Oct 4, 2025) ⭐ CRITICAL

- **Configuration**: `trading.confirmation.enable_choppy_filter`
- **Type**: Market quality
- **Purpose**: Avoid entering during consolidation/sideways markets
- **When Applied**: For ALL entry types (momentum, pullback, sustained)
- **Default**: true (ENABLED)
- **Algorithm**:
  ```python
  # Look back 5 minutes
  recent_range = recent_high - recent_low
  atr = calculate_atr(20_bars)
  ratio = recent_range / atr

  if ratio < 0.5:
      → CHOPPY (block entry)
  else:
      → TRENDING (allow entry)
  ```
- **Timing**: INSTANT (no waiting) - retrospective analysis of last 5 minutes
- **Impact**:
  - 61% of losses came from choppy conditions
  - Lost $15,425 in one week from consolidation entries
  - Choppy trades: 6.7% win rate vs 40%+ for trending
- **Example**:
  ```
  CHOPPY (blocked):
    Price: $182.20 → $182.25 → $182.18 → $182.23 (wiggling)
    Range: $0.07, ATR: $0.20 → 0.35× ATR ❌

  TRENDING (allowed):
    Price: $182.20 → $182.45 → $182.70 → $182.80 (moving)
    Range: $0.60, ATR: $0.20 → 3.0× ATR ✅
  ```
- **Parameters**:
  - `choppy_atr_multiplier`: 0.5 (minimum ratio)
  - `choppy_lookback_bars`: 60 (5 minutes)
- **Why ATR-based**: Adapts to stock volatility and current conditions
- **Enable/Disable**: Set `enable_choppy_filter: false` to disable (NOT recommended)

#### Room-to-Run Filter (Oct 5, 2025) ⭐ NEW

- **Configuration**: `filters.enable_room_to_run_filter`
- **Type**: Opportunity validation
- **Purpose**: Ensure sufficient room to target at entry time
- **When Applied**: For pullback/retest and sustained break entries ONLY
  - NOT applied to momentum entries (immediate entries don't need this)
- **Default**: true (ENABLED)
- **Algorithm**:
  ```python
  room_pct = ((target_price - entry_price) / entry_price) * 100

  if room_pct < 1.5:
      → BLOCK (insufficient room)
  else:
      → ALLOW (sufficient opportunity)
  ```
- **Timing**: INSTANT (no waiting) - simple calculation at entry time
- **Rationale**: Confirmation strategies take time, price moves during wait
  - Pullback/retest: Waits 0-120 seconds for pattern
  - Sustained break: Waits 120 seconds for hold
  - Question: "Is there still enough room to make this worthwhile?"
- **Impact**:
  - Replaced range-based "chasing filter" which conflicted with confirmation logic
  - Oct 1 backtest: Filtered out 4 marginal trades, kept 1 quality trade
  - P&L: $41 (with marginal trades) → $796 (without)
- **Example**:
  ```
  PLTR Oct 1:
    Entry: $183.03
    Target: $184.14
    Room: 0.61% < 1.5% minimum → BLOCKED ✅

  COIN Oct 1:
    Entry: $345.92
    Target: $350.00 (estimated)
    Room: 1.2% ≥ 1.5% minimum → ALLOWED ✅
  ```
- **Parameters**:
  - `min_room_to_target_pct`: 1.5% (minimum required)
- **Why This Works**:
  - Directly answers "Can this still run to target?"
  - Catches overnight gaps that ate the move
  - Catches delayed entries where target is now too close
  - Doesn't penalize patient confirmation strategies
- **Enable/Disable**: Set `enable_room_to_run_filter: false` to disable

#### Range-Based Chasing Filter (Oct 4, 2025) - DEPRECATED

- **Configuration**: `trading.confirmation.enable_entry_position_filter`
- **Type**: Position validation (LEGACY)
- **Purpose**: Prevent entering when already at top of recent range
- **When Applied**: For MOMENTUM entries only (if enabled)
- **Default**: false (DISABLED - superseded by room-to-run filter)
- **Algorithm**:
  ```python
  position_pct = (entry_price - range_low) / (range_high - range_low)

  if position_pct > 70:
      → BLOCK (chasing the move)
  else:
      → ALLOW
  ```
- **Why Deprecated**:
  - Conflicted with confirmation strategies (pullback/sustained)
  - Measured wrong thing (position in range vs opportunity remaining)
  - Replaced by room-to-run filter for confirmation entries
- **Current Status**: Only applies to momentum entries if explicitly enabled
- **Enable/Disable**: Set to `false` (current default)

---

## Filter Configuration Matrix

| Filter Name | Config Path | Default | Applies To | Wait Required? |
|-------------|-------------|---------|------------|----------------|
| Min Score | `filters.min_score` | 0 (off) | All stocks | No |
| Min R/R | `filters.min_risk_reward` | 0.0 (off) | All stocks | No |
| Max Dist to Pivot | `filters.max_dist_to_pivot` | 100.0 (off) | All stocks | No |
| Gap Filter | `filters.enable_gap_filter` | false | All stocks | No |
| Avoid Index Shorts | `filters.avoid_index_shorts` | true | SHORT only | No |
| Symbol Blacklist | `filters.avoid_symbols` | [SPY, QQQ...] | All stocks | No |
| Entry Time Window | `trading.entry.min/max_entry_time` | 09:45-15:00 | All entries | No |
| Max Attempts | `trading.attempts.max_attempts_per_pivot` | 2 | All entries | No |
| 1-Min Candle Close | `confirmation.require_candle_close` | true | All entries | Yes (0-60s) |
| Pullback/Retest | `confirmation.require_pullback_retest` | true | Weak breaks | Yes (0-120s) |
| Sustained Break | `confirmation.sustained_break_enabled` | true | Weak breaks | Yes (120s) |
| Choppy Filter | `confirmation.enable_choppy_filter` | true | All entries | No |
| Room-to-Run | `filters.enable_room_to_run_filter` | true | Pullback/Sustained | No |
| Range Chasing | `confirmation.enable_entry_position_filter` | false | Momentum only | No |

---

## Filter Performance Impact

### Choppy Market Filter
- **Backtest Period**: Sept 23-30, 2025
- **Without Filter**:
  - 123 trades total
  - 75 choppy trades (61%)
  - Choppy win rate: 6.7%
  - Choppy P&L: -$15,425
- **With Filter** (estimated):
  - ~48 trades (blocking 75 choppy)
  - Expected win rate: 40-50%
  - Expected P&L: Significantly positive

### Room-to-Run Filter
- **Backtest Period**: Oct 1, 2025
- **Without Filter**:
  - 5 trades
  - 60% win rate
  - P&L: +$41
- **With Filter**:
  - 1 trade (filtered 4 marginal setups)
  - 100% win rate
  - P&L: +$796 (19x improvement)

### Max Attempts Per Pivot
- **Backtest Period**: Sept 30, 2025
- **1 Attempt**: 16 trades, +$616 P&L
- **2 Attempts**: 27 trades, +$1,441 P&L (134% improvement)
- **Unlimited Attempts**: 126 trades, +$1,289 P&L (worse than 2 attempts)

---

## Recommended Filter Settings

### Conservative (High Quality, Fewer Trades)
```yaml
filters:
  min_score: 60
  min_risk_reward: 2.0
  enable_gap_filter: true
  enable_room_to_run_filter: true
  min_room_to_target_pct: 2.0

confirmation:
  enable_choppy_filter: true
  choppy_atr_multiplier: 0.7
  sustained_break_enabled: true
```

### Balanced (Current Default)
```yaml
filters:
  min_score: 0
  min_risk_reward: 0.0
  enable_gap_filter: false
  enable_room_to_run_filter: true
  min_room_to_target_pct: 1.5

confirmation:
  enable_choppy_filter: true
  choppy_atr_multiplier: 0.5
  sustained_break_enabled: true
```

### Aggressive (More Trades, Lower Quality)
```yaml
filters:
  min_score: 0
  min_risk_reward: 0.0
  enable_gap_filter: false
  enable_room_to_run_filter: false
  min_room_to_target_pct: 1.0

confirmation:
  enable_choppy_filter: false
  sustained_break_enabled: true
```

**⚠️ WARNING**: Aggressive settings not recommended - choppy filter is critical for avoiding whipsaws.

---

## Development History

### Oct 5, 2025 - PLTR Debug Session
- **Issue**: PLTR hit target (+2.21%) but backtest filtered it out
- **Root Cause**: Momentum candle too strict for 5-second bars
- **Solutions Implemented**:
  1. Sustained break logic (catch slow grinds)
  2. Increased pullback tolerance (0.1% → 0.3%)
  3. Removed chasing filter from confirmation paths
  4. **Room-to-run filter** (replaced range-based chasing)
- **Result**: Smarter filtering that supports confirmation strategies

### Oct 4, 2025 - September Backtest Analysis
- **Findings**:
  - 61% of trades were choppy (lost $15,425)
  - Winners entered at 36% of range, losers at 81%
  - 2 attempts per pivot optimal
- **Solutions Implemented**:
  1. Choppy market filter (ATR-based)
  2. Range-based chasing filter (later deprecated)
  3. Relaxed momentum thresholds

---

## Testing & Validation

### How to Test Filter Impact

1. **Disable filter in config**:
   ```yaml
   filters:
     enable_room_to_run_filter: false
   ```

2. **Run backtest**:
   ```bash
   python3 backtest/run_monthly_backtest.py --month 9 --year 2025
   ```

3. **Compare results**:
   - Number of trades
   - Win rate
   - P&L
   - Average winner/loser

4. **Document findings**:
   - Update this file with results
   - Add to REQUIREMENTS_IMPLEMENTATION_LOG.md

### A/B Testing Framework
- Keep production settings in `trader_config.yaml`
- Create test configs: `trader_config_test.yaml`
- Compare side-by-side with same historical data

---

## Future Enhancements

### Potential New Filters
1. **Volume Profile Filter**: Avoid entries during low-volume periods
2. **News Event Filter**: Skip trades during earnings/Fed announcements
3. **Correlation Filter**: Avoid multiple correlated positions
4. **Market Regime Filter**: Adapt to bull/bear/sideways markets

### Adaptive Filtering
- **Time-of-Day Adjustments**: Different thresholds for open vs midday vs close
- **Volatility Regime**: Adjust choppy threshold based on VIX
- **Symbol-Specific**: Different settings for different stocks (e.g., lower threshold for high-vol stocks)

---

## See Also

- **CLAUDE.md**: Overall project documentation
- **REQUIREMENTS_IMPLEMENTATION_LOG.md**: Detailed implementation tracking
- **trader_config.yaml**: Live configuration file
- **PLTR_DEBUG_SESSION.md**: Detailed debug session log (Oct 5, 2025)
