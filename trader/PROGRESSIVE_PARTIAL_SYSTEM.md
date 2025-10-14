# Progressive Partial Profit System with SMA + Target Levels

**Implemented:** October 12, 2025
**Version:** 1.0
**Strategy:** PS60 Enhanced Exit System

---

## Executive Summary

This system replaces the traditional **50%-25%-25% (1R-2R-Runner)** exit strategy with a more adaptive **25%-25%-25%-25%** exit at technical levels (SMAs + scanner targets), with progressive stop tightening.

### Key Innovation

**OLD System:**
- 50% at 1R (when profit = risk)
- 25% at 2R (target)
- 25% runner with trailing stop
- Stop to breakeven after first partial

**NEW System:**
- 25% at each technical level (SMA5, SMA10, Target1, SMA20)
- Stop moves to **previous level** after each partial
- Uses real market structure (SMAs) not arbitrary 1R/2R
- Faster profit locking, better protection

---

## Problem Statement

### Issue #1: Variable 1R Based on Volatility

The 1R rule creates inconsistent behavior:

| Stock Type | ATR % | Stop Width | 1R Distance | Time to 1R |
|------------|-------|------------|-------------|------------|
| Low Vol    | 1.5%  | 0.7%       | $0.70       | 2-3 min ✓  |
| High Vol   | 7.0%  | 2.5%       | $2.50       | 15+ min ❌ |

**Result:** High volatility stocks often hit 15-min timeout before reaching 1R.

### Issue #2: Breakeven Stop Vulnerability

After taking 50% at 1R, stop moves to breakeven. If price reverses:
- **Give back all gains** on remaining 50%
- No protection from previous technical levels

### Issue #3: Missing Market Structure

1R and 2R are arbitrary profit levels that ignore:
- SMA support/resistance zones
- Natural pause points in price action
- Where other traders are likely to take action

---

## Solution: SMA + Target Progressive System

### Core Concept

**Use real technical levels from market structure:**

1. **Primary:** Hourly SMA levels (5, 10, 20) - where price naturally pauses
2. **Secondary:** Scanner targets (measured moves) - fill gaps between SMAs
3. **Progressive:** Take 25% at each level, move stop to previous level

### Example Trade Flow

**Stock: AAPL LONG @ $150.00**

**Step 1: Entry**
```
Entry:          $150.00
Initial Stop:   $148.20 (1.2% ATR)
Position Size:  1600 shares

Calculate Exit Levels:
✓ SMA5 hourly:  $151.50 (1.0% away)  ← Level 1
✓ SMA10 hourly: $153.00 (2.0% away)  ← Level 2
✓ Target1:      $154.80 (3.2% away)  ← Level 3
✓ SMA20 hourly: $156.50 (4.3% away)  ← Level 4

Plan: 25% at each level, stop follows
```

**Step 2: Hit SMA5 @ $151.50 (First Partial)**
```
Action:  Exit 25% (400 shares) @ $151.50
Profit:  $1.50 × 400 = $600 locked ✓
Stop:    $148.20 → $150.00 (breakeven)
Reason:  "25%_PARTIAL_SMA5"
```

**Step 3: Hit SMA10 @ $153.00 (Second Partial)**
```
Action:  Exit 25% (400 shares) @ $153.00
Profit:  $3.00 × 400 = $1,200 locked ✓
Stop:    $150.00 → $151.50 (SMA5 level)
Reason:  "25%_PARTIAL_SMA10"

🔑 KEY: Stop now protected by SMA5 support!
```

**Step 4: Hit Target1 @ $154.80 (Third Partial)**
```
Action:  Exit 25% (400 shares) @ $154.80
Profit:  $4.80 × 400 = $1,920 locked ✓
Stop:    $151.50 → $153.00 (SMA10 level)
Reason:  "25%_PARTIAL_TARGET1"

🔑 KEY: Stop now protected by SMA10 support!
```

**Step 5: Runner @ $156.50+ (Fourth Partial)**
```
Best Price:     $158.00
Trailing Stop:  0.5% = $157.21
Price Reverses: $157.00
Exit:           400 shares @ $157.21
Profit:         $7.21 × 400 = $2,884 locked ✓
Reason:         "TRAIL_STOP"
```

**Total P&L:**
- 1st partial: $600
- 2nd partial: $1,200
- 3rd partial: $1,920
- 4th partial: $2,884
- **TOTAL: $6,604 (+4.4%)**

---

## Technical Implementation

### Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Trade Entry System                        │
│  (Existing: Momentum/Sustained/Pullback state machine)      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              SMA Calculator Module (NEW)                     │
│  • Fetch hourly/daily bars from IBKR                        │
│  • Calculate SMA5, SMA10, SMA20                             │
│  • Cache results (5 min TTL)                                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│            Level Builder (NEW)                               │
│  • Merge SMA levels + Scanner targets                       │
│  • Order by distance from entry                             │
│  • Filter invalid levels (wrong direction)                  │
│  • Max 4 levels (for 25% each)                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│        Progressive Partial Logic (MODIFIED)                  │
│  • Check if price reached next level                        │
│  • Take 25% at each level                                   │
│  • Update stop to previous level                            │
│  • Track partials taken                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│           Trailing Stop for Runner                           │
│  (Existing: 0.5% trail after final partial)                 │
└─────────────────────────────────────────────────────────────┘
```

### File Structure

```
trader/
├── strategy/
│   ├── sma_calculator.py           # NEW - Fetch & calculate SMAs
│   ├── ps60_strategy.py            # MODIFIED - New partial logic
│   └── position_manager.py         # MODIFIED - Progressive stops
│
├── config/
│   └── trader_config.yaml          # UPDATED - New parameters
│
├── backtest/
│   └── backtester.py               # MODIFIED - Pass bars to strategy
│
└── PROGRESSIVE_PARTIAL_SYSTEM.md   # THIS FILE
```

---

## Configuration Reference

### trader_config.yaml

```yaml
exits:
  # Progressive partial system toggle
  use_sma_target_partials: true    # Enable new system (false = revert to 1R)
  partial_size: 0.25               # 25% at each level
  max_partial_levels: 4            # Max 4 exit levels

  # SMA Configuration (Priority 1)
  sma:
    enabled: true
    periods: [5, 10, 20]           # Which SMAs to calculate
    timeframe: '1 hour'            # '1 hour' or '1 day'
    cache_duration_sec: 300        # Cache SMAs for 5 minutes

  # Scanner Targets (Priority 2)
  scanner_targets:
    enabled: true
    use_target1: true              # Include scanner target1
    use_target2: true              # Include scanner target2
    use_target3: false             # Usually too far away

  # Progressive Stop Management
  progressive_stops:
    enabled: true
    move_to_previous_level: true   # Stop follows previous exit level
    min_stop_distance_pct: 0.005   # Keep 0.5% buffer below level

  # Fallback Settings
  fallback_to_1r: true             # Use 1R system if insufficient levels
  min_levels_required: 2           # Need at least 2 levels

  # Legacy 1R settings (used for fallback)
  partial_1_pct: 0.50
  partial_2_pct: 0.25
  runner_pct: 0.25
```

---

## SMA Timeframe Selection

### Hourly (RECOMMENDED for Day Trading)

**Characteristics:**
- SMA5 = Last 5 hours (~1 trading day)
- SMA10 = Last 10 hours (~1.5 days)
- SMA20 = Last 20 hours (~2.5 days)

**Pros:**
- Reacts quickly to intraday momentum
- Levels are closer to entry (faster partials)
- Captures intraday support/resistance

**Cons:**
- More noise, can whipsaw
- Levels may cluster together

**Best For:** Momentum breakouts, volatile stocks, day trading

### Daily (Alternative for Swing Context)

**Characteristics:**
- SMA5 = Last week
- SMA10 = Last 2 weeks
- SMA20 = Last month

**Pros:**
- Smoother, less noise
- Strong psychological levels
- Good for trend confirmation

**Cons:**
- Levels may be far from entry
- Slower to react to intraday moves
- May not provide enough nearby exits

**Best For:** Swing positions, trend trades, lower volatility

---

## Fallback to 1R System

If insufficient technical levels are found, the system automatically falls back to the traditional 1R/2R system.

### Trigger Conditions

Fallback occurs when:
1. `len(exit_levels) < min_levels_required` (default: 2)
2. SMA calculation fails (IBKR connection issue)
3. No scanner targets available
4. All levels are in wrong direction

### Fallback Behavior

```python
if len(exit_levels) < 2:
    # Use traditional system
    exit_levels = [
        {'price': entry + 1R, 'type': '1R', 'name': '1R'},
        {'price': entry + 2R, 'type': '2R', 'name': '2R'}
    ]
    partial_sizes = [0.50, 0.25]  # 50%-25%-25% runner
```

**Fallback is logged:**
```
⚠️  Insufficient exit levels for AAPL (found 1, need 2)
    Falling back to 1R/2R system
```

---

## Stop Management Details

### Progressive Stop Tightening

After each partial, the stop moves to the **previous exit level** (with buffer):

| Partials Taken | Stop Location | Protection |
|----------------|---------------|------------|
| 0 (entry)      | Initial ATR stop | Entry risk |
| 1 (SMA5)       | Breakeven | Zero risk ✓ |
| 2 (SMA10)      | SMA5 - 0.5% | SMA5 support ✓ |
| 3 (Target1)    | SMA10 - 0.5% | SMA10 support ✓ |
| 4 (runner)     | Trailing 0.5% | Runner trail ✓ |

### Buffer Calculation

**For LONG:**
```python
new_stop = previous_level_price * (1 - 0.005)  # 0.5% below
```

**For SHORT:**
```python
new_stop = previous_level_price * (1 + 0.005)  # 0.5% above
```

**Purpose:** Avoid premature stop-out from minor wicks through level

---

## Level Ordering Algorithm

### Priority System

1. **Collect all valid levels:**
   - SMA5, SMA10, SMA20 (if in right direction)
   - Target1, Target2 (from scanner)

2. **Filter by direction:**
   - LONG: Keep levels > entry
   - SHORT: Keep levels < entry

3. **Sort by distance:**
   - Closest to entry = Level 1
   - Farthest = Level 4

4. **Limit to max levels:**
   - Take first 4 (for 25% each)

### Example Ordering

**LONG @ $100:**

```
Candidates:
- SMA5: $101.20 (1.2% away)
- SMA10: $102.50 (2.5% away)
- Target1: $103.00 (3.0% away)
- SMA20: $105.00 (5.0% away)
- Target2: $107.50 (7.5% away)

Sorted: [SMA5, SMA10, Target1, SMA20, Target2]
Limited: [SMA5, SMA10, Target1, SMA20]  ← First 4

Exit Plan:
Level 1: $101.20 (SMA5)
Level 2: $102.50 (SMA10)
Level 3: $103.00 (Target1)
Level 4: $105.00 (SMA20)
```

---

## Edge Cases & Error Handling

### Case 1: No SMA Levels Found

**Scenario:** Stock recently IPO'd, insufficient history

**Handling:**
```python
if not sma_levels:
    # Use scanner targets only
    levels = [target1, target2]

    if len(levels) < 2:
        # Fallback to 1R
        return create_1r_levels(position)
```

### Case 2: All Levels Too Close

**Scenario:** All SMAs within 0.5% of entry

**Handling:**
```python
MIN_LEVEL_SPACING = 0.005  # 0.5%

for level in levels:
    if abs(level['price'] - entry) / entry < MIN_LEVEL_SPACING:
        continue  # Skip this level
```

### Case 3: IBKR Connection Failure

**Scenario:** Cannot fetch historical bars for SMAs

**Handling:**
```python
try:
    sma_levels = sma_calculator.get_sma_levels(symbol)
except Exception as e:
    logger.warning(f"SMA calculation failed: {e}")
    # Use scanner targets only
    sma_levels = None
```

### Case 4: Levels in Wrong Direction

**Scenario:** Entering LONG but all SMAs are below entry

**Handling:**
```python
# This is a RED FLAG - likely counter-trend trade
if len(valid_levels) == 0:
    logger.warning(f"No exit levels above entry for LONG {symbol}")
    logger.warning(f"SMAs below entry - possible counter-trend setup")

    # Still allow trade but use 1R fallback
    return create_1r_levels(position)
```

---

## Performance Metrics to Track

### Before/After Comparison

| Metric | Old (1R/2R) | New (SMA/Target) | Expected Δ |
|--------|-------------|------------------|------------|
| Avg time to 1st partial | 5-20 min | 2-10 min | ↓ 50% |
| 15-min timeout rate | 91.7% | <50% | ↓ 45% |
| Avg profit per trade | $53 | $80+ | ↑ 50% |
| Stop-outs after partial | High | Low | ↓ 60% |
| Runner capture | 25% | 25% | Same |

### Key Metrics to Monitor

1. **Partial Hit Rate:**
   - % of trades that reach each level
   - Level 1: Should be >80%
   - Level 2: Should be >60%
   - Level 3: Should be >40%
   - Level 4: Should be >20%

2. **Stop Tightening Effectiveness:**
   - % of trades stopped at previous level
   - Profit saved by progressive stops vs breakeven

3. **Level Quality:**
   - How often price bounces at SMA levels
   - SMA vs Target level performance

4. **System Reliability:**
   - SMA calculation success rate
   - Fallback frequency

---

## Testing Strategy

### Phase 1: Backtest Validation (Oct 7-9)

Run new system on existing backtest data:
```bash
cd trader/backtest
python3 backtester.py --date 2025-10-07 \
  --scanner ../../stockscanner/output/scanner_results_20251007.json \
  --account-size 100000 \
  --config-override exits.use_sma_target_partials=true
```

**Compare:**
- Total P&L: Old vs New
- Trade count: Same setups, different exits
- Timeout rate: Should decrease significantly
- Avg winner: Should increase

### Phase 2: Paper Trading (1 week)

Test in live market with paper account:
- Monitor SMA calculation performance
- Check IBKR historical data reliability
- Validate level ordering logic
- Track partial execution

### Phase 3: Small Live Test (1 week)

Run with 10% of normal size:
- Verify real executions at levels
- Monitor slippage at SMAs
- Check stop management
- Validate P&L calculations

### Phase 4: Full Production

Roll out to 100% size after validation

---

## Rollback Plan

If new system underperforms:

1. **Immediate Rollback:**
   ```yaml
   # trader_config.yaml
   exits:
     use_sma_target_partials: false  # Revert to 1R system
   ```

2. **Code Preservation:**
   - Old logic preserved in `_legacy_partial_logic()`
   - Can switch with single config change
   - No code modifications required

3. **Hybrid Mode:**
   ```yaml
   # Use new system for low-vol, old for high-vol
   exits:
     use_sma_target_partials: true
     fallback_atr_threshold: 6.0  # Use 1R if ATR > 6%
   ```

---

## Code Documentation Standards

All new code follows these documentation standards:

1. **Module-level docstrings:**
   - Purpose of module
   - Dependencies
   - Usage examples

2. **Function docstrings:**
   - Purpose (what it does)
   - Args with types
   - Returns with types
   - Example usage
   - Edge cases

3. **Inline comments:**
   - Why (not what)
   - Complex logic explanation
   - Edge case handling

4. **Type hints:**
   - All function parameters
   - All return values

**Example:**
```python
def calculate_sma(bars: List[Bar], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average from historical bars.

    Args:
        bars: List of IBKR bar objects with .close attribute
        period: Number of bars to average (e.g., 5, 10, 20)

    Returns:
        SMA value rounded to 2 decimals, or None if insufficient data

    Example:
        >>> bars = fetch_bars('AAPL', '1 hour', lookback=20)
        >>> sma20 = calculate_sma(bars, period=20)
        >>> print(f"SMA20: ${sma20:.2f}")
        SMA20: $150.45

    Edge Cases:
        - Returns None if len(bars) < period
        - Handles bars with None close prices
        - Rounds to 2 decimals for price precision
    """
    if not bars or len(bars) < period:
        return None

    # Extract close prices, skip None values
    closes = [bar.close for bar in bars[-period:] if bar.close is not None]

    if len(closes) < period:
        return None

    # Calculate mean and round to 2 decimals
    return round(statistics.mean(closes), 2)
```

---

## Change Log

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-12 | 1.0 | Initial design and documentation | Claude |

---

## References

- **Original Requirements:** `trader/Automated Trading System for PS60 Strategy – Requirements Specification.md`
- **PS60 Methodology:** `PS60ProcessComprehensiveDayTradingGuide.md`
- **Backtest Results:** `trader/backtest/results/`
- **Code Path Analysis:** `CODE_PATH_WIN_RATE_REPORT.md`

---

**End of Documentation**
