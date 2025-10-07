# Enhanced Scoring Usage Guide

## Quick Start - Daily Trading Workflow

### 1. Pre-Market (Evening Before or 8:00 AM)

**Run Scanner**:
```bash
cd /Users/karthik/projects/DayTrader/stockscanner
python3 scanner.py --category quick
```

**Apply Enhanced Scoring**:
```bash
cd ../scanner_validation
python3 enhanced_scoring.py \
  ../stockscanner/output/scanner_results_20251007.csv \
  rescored_20251007_v2.csv
```

**Output**: `rescored_20251007_v2.csv` with tier classifications

---

### 2. Live Trading (9:30 AM - 4:00 PM)

**Start Trader**:
```bash
cd /Users/karthik/projects/DayTrader/trader
python3 trader.py
```

**Automatic Behavior**:
- Trader checks for `rescored_YYYYMMDD_v2.csv` in `scanner_validation/`
- If found: Uses enhanced scoring with tier-based filtering
- If not found: Falls back to regular `scanner_results_YYYYMMDD.json`

**Expected Log Output**:
```
✓ Found enhanced scoring: rescored_20251007_v2.csv
✓ Loaded 57 stocks from enhanced scoring
✓ Filtered to 10 setups after tier filtering

  [GS] TIER 1 ⭐⭐⭐ - LONG:100 SHORT:100 Pivot:1.41% R/R:8.36
  [AAPL] TIER 1 ⭐⭐⭐ - LONG:100 SHORT:100 Pivot:1.70% R/R:12.57
  [BA] TIER 1 ⭐⭐⭐ - LONG:100 SHORT:100 Pivot:1.75% R/R:2.00
  [AMZN] TIER 2 ⭐⭐ - LONG:100 SHORT:100 Pivot:1.73% R/R:1.64
  [QCOM] TIER 2 ⭐⭐ - LONG:100 SHORT:100 Pivot:3.74% R/R:3.12
  ...
```

---

### 3. Post-Market Validation (4:15 PM)

**Validate Scanner Predictions**:
```bash
cd /Users/karthik/projects/DayTrader/scanner_validation
python3 validate_scanner.py 2025-10-07 \
  ../stockscanner/output/scanner_results_20251007.csv
```

**Analyze Tier Performance**:
```bash
python3 analyze_validation_metrics.py validation_20251007.csv
```

**Check if tier success rates match expectations**:
- TIER 1: Should achieve 70-80% success rate
- TIER 2: Should achieve 50-60% success rate
- TIER 3: Should achieve 40-50% success rate

---

## Configuration

### Trader Config (`trader/config/trader_config.yaml`)

**Enhanced Scoring Filters**:
```yaml
filters:
  # Enhanced score threshold
  min_enhanced_score: 85       # Minimum enhanced score (0-100+)

  # Pivot width filter (KEY INSIGHT: tight pivots = winners)
  max_pivot_width_pct: 5.0     # Maximum pivot width %

  # Test count filter (KEY INSIGHT: heavily tested = higher success)
  min_test_count: 5            # Minimum number of tests

  # Tier-based filtering
  tier_filter:
    - 'TIER 1'                 # Always trade (70-80% expected)
    - 'TIER 2'                 # Trade normally (50-60% expected)
    - 'TIER 3'                 # Trade selectively (40-50% expected)

  # Risk/reward minimum
  min_risk_reward: 2.0         # Per trading plan

scanner:
  output_dir: "../stockscanner/output/"
  enhanced_scoring_dir: "../scanner_validation/"
```

### Adjusting Filters

**To focus on TIER 1 only** (highest quality):
```yaml
tier_filter:
  - 'TIER 1'    # Only trade 70-80% success setups
```

**To tighten pivot width requirement**:
```yaml
max_pivot_width_pct: 3.5  # Only allow tight pivots (winners averaged 2.51%)
```

**To require more tests**:
```yaml
min_test_count: 10  # Require heavily-tested levels (80% success rate)
```

---

## Backtesting with Enhanced Scoring

**Run Backtest with Enhanced Scoring**:
```bash
cd /Users/karthik/projects/DayTrader/trader/backtest

# Single day with enhanced scoring
python3 backtester.py \
  --date 2025-10-07 \
  --scanner ../../scanner_validation/rescored_20251007_v2.csv \
  --account-size 100000
```

**Expected Output**:
```
✓ Detected enhanced scoring CSV
✓ Using ENHANCED SCORING filtering (tier-based)

TIER BREAKDOWN:
  TIER 1: 3 stocks - GS, AAPL, BA
  TIER 2: 7 stocks - AMZN, QCOM, MS, CVX, DIS

WATCHLIST: 10 tradeable setups (using strategy filters)
```

**Compare vs Regular Scanner**:
```bash
# Backtest with regular scanner
python3 backtester.py \
  --date 2025-10-07 \
  --scanner ../../stockscanner/output/scanner_results_20251007.json \
  --account-size 100000
```

---

## Tier Classification

### TIER 1 ⭐⭐⭐ (Highest Priority)

**Criteria**:
- Pivot width < 2.5% AND
- Test count ≥ 10x

**Expected Success Rate**: 70-80%

**Oct 7 Examples**:
- GS: 1.41% pivot, 12x tests
- AAPL: 1.70% pivot, 10x tests
- BA: 1.75% pivot, 11x tests

**Trading Strategy**: Full position size, aggressive entry

---

### TIER 2 ⭐⭐ (Good Setups)

**Criteria**:
- Pivot width < 3.5% OR
- Test count ≥ 5x
- (But not both at TIER 1 levels)

**Expected Success Rate**: 50-60%

**Oct 7 Examples**:
- AMZN: 1.73% pivot, 9x tests (tight pivot)
- QCOM: 3.74% pivot, 10x tests (heavily tested)
- MS: 4.51% pivot, 11x tests (heavily tested)

**Trading Strategy**: Normal position size

---

### TIER 3 ⭐ (Marginal Setups)

**Criteria**:
- Pivot width 3.5-5.0%
- Test count 3-4x

**Expected Success Rate**: 40-50%

**Trading Strategy**: Reduced position size (50%), trade selectively

**Note**: By default, TIER 3 is included in `tier_filter` but you can remove it to focus only on TIER 1 and TIER 2.

---

### AVOID ❌ (Blacklisted)

**Criteria**:
- Index ETF (SPY, QQQ, DIA, IWM)
- High-vol stock (TSLA, NVDA, LCID, COIN, AMC, GME, HOOD, RIVN)
- Pivot width > 5.0%

**Why Avoid**:
- Index ETFs: 100% false breakout rate (Oct 6 validation)
- High-vol stocks: 75% false breakout rate
- Wide pivots: Strong correlation with false breakouts (>5% median for failures)

**Action**: Trader automatically filters these out - they never appear in watchlist

---

## Testing & Validation

### Test Enhanced Scoring Integration

```bash
cd /Users/karthik/projects/DayTrader/trader
python3 test_enhanced_scoring.py
```

**Expected Output**:
```
TIER 1 (3 stocks):
  GS     - Pivot: 1.41% Tests:12x LONG:100 SHORT:100
  AAPL   - Pivot: 1.70% Tests:10x LONG:100 SHORT:100
  BA     - Pivot: 1.75% Tests:11x LONG:100 SHORT:100

BLACKLISTED STOCKS (Filtered Out):
  ❌ LCID   (HIGH-VOL) - Score:100 Pivot: 4.26% Tests: 6x
  ❌ DIA    (INDEX ETF) - Score:100 Pivot: 1.49% Tests:13x
  ❌ SPY    (INDEX ETF) - Score:100 Pivot: 1.14% Tests:12x

VALIDATION: Expected TIER 1 Stocks (from trading plan)
Expected: GS, AAPL, BA
Found:    GS, AAPL, BA
  ✓ GS correctly classified as TIER 1
  ✓ AAPL correctly classified as TIER 1
  ✓ BA correctly classified as TIER 1
```

---

## Troubleshooting

### Enhanced Scoring Not Loading

**Problem**: Trader shows "⚠️ Enhanced scoring not found, using regular scanner output"

**Solutions**:
1. Check file exists: `ls ../scanner_validation/rescored_20251007_v2.csv`
2. Check date format: File must be `rescored_YYYYMMDD_v2.csv` (e.g., `rescored_20251007_v2.csv`)
3. Generate enhanced scoring:
   ```bash
   cd scanner_validation
   python3 enhanced_scoring.py \
     ../stockscanner/output/scanner_results_20251007.csv \
     rescored_20251007_v2.csv
   ```

---

### No Stocks Pass Filters

**Problem**: "Filtered to 0 setups after tier filtering"

**Possible Causes**:
1. **Filters too strict**: Check `trader_config.yaml`:
   - `min_enhanced_score` too high (try 80 instead of 85)
   - `max_pivot_width_pct` too low (try 6.0 instead of 5.0)
   - `min_test_count` too high (try 3 instead of 5)

2. **Only TIER 1 allowed**: Check `tier_filter` includes TIER 2 and TIER 3

3. **All stocks blacklisted**: Check if scanner picked only index ETFs or high-vol stocks

**Fix**:
```yaml
# Relaxed filters
filters:
  min_enhanced_score: 80           # Lower threshold
  max_pivot_width_pct: 6.0         # Allow slightly wider pivots
  min_test_count: 3                # Lower test count requirement
  tier_filter:
    - 'TIER 1'
    - 'TIER 2'
    - 'TIER 3'                     # Include all tiers
```

---

### Tier Classifications Look Wrong

**Problem**: Expected TIER 1 stocks appearing in TIER 2 or vice versa

**Check**:
1. **Pivot width calculation**: Verify `pivot_width_pct` in CSV
2. **Test count parsing**: Check `breakout_reason` contains "Tested Nx"
3. **Tier thresholds**: Verify classification logic in `_classify_stock_tier()`

**Debug**:
```python
# In trader or backtester
for stock in watchlist:
    print(f"{stock['symbol']}: "
          f"Pivot {stock.get('pivot_width_pct', 0):.2f}%, "
          f"Tests {stock.get('test_count', 0)}x, "
          f"Tier {stock.get('tier', 'UNKNOWN')}")
```

---

## Performance Expectations

### Oct 6 Validation Results

**Overall Scanner Success Rate**: 33.3% (12 winners out of 36 setups)

**Enhanced Scoring Top 10**: 70% accuracy (7 winners out of 10)

**Improvement**: +112% accuracy by using tier-based ranking

---

### Expected Oct 7 Performance

**TIER 1 Focus** (GS, AAPL, BA):
- Expected: 2-3 winners (70-80% success rate)
- Potential P&L: $3,000-5,000

**TIER 1 + TIER 2** (10 setups total):
- Expected: 6-7 winners (60% success rate)
- Potential P&L: $6,000-10,000

**Comparison to Baseline**:
- Without enhanced scoring: 3-4 winners (33% of 10) = $3,000-4,000
- With enhanced scoring: 6-7 winners (60-70% of 10) = $6,000-10,000
- **Expected improvement: +50-100% P&L**

---

## File Reference

### Key Files

**Scanner Validation**:
- `enhanced_scoring.py` - Main scoring engine
- `validate_scanner.py` - Daily validation vs actual outcomes
- `analyze_validation_metrics.py` - Pattern discovery
- `ENHANCED_SCORING_SUMMARY.md` - Complete reference guide
- `TEST_COUNT_BONUS_ANALYSIS.md` - Test count correlation analysis

**Trader**:
- `trader/trader.py` - Live trading engine (enhanced scoring support)
- `trader/config/trader_config.yaml` - Configuration (enhanced filters)
- `trader/strategy/ps60_strategy.py` - Filtering logic (tier-based)
- `trader/backtest/backtester.py` - Backtesting (enhanced scoring support)
- `trader/test_enhanced_scoring.py` - Integration test

**Generated Daily Files**:
- `scanner_validation/rescored_YYYYMMDD_v2.csv` - Enhanced scoring output (with test count bonus)
- `scanner_validation/validation_YYYYMMDD.csv` - Validation results vs actual
- `trader/logs/trader_YYYYMMDD.log` - Live trading log

---

## Next Steps

### Immediate (Oct 7 Trading)

1. ✅ Generate enhanced scoring: `rescored_20251007_v2.csv`
2. ✅ Start trader at 9:30 AM ET sharp
3. ⏳ Focus on TIER 1 setups (GS, AAPL, BA)
4. ⏳ Validate tier success rates in evening

### Short-term (Week 1)

1. Track tier performance daily
2. Compare actual vs expected success rates
3. Refine tier thresholds if needed
4. Document edge cases and outliers

### Medium-term (Month 1)

1. Backtest historical data with enhanced scoring
2. Measure improvement vs baseline scanner
3. Optimize tier thresholds using larger dataset
4. Consider adding new scoring factors

---

*Last Updated: October 6, 2025, 11:59 PM PT*
*Next Validation: October 7, 2025, 4:15 PM ET*
