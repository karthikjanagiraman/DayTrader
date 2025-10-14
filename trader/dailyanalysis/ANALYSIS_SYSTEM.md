# Post-Trading Analysis System

**Date**: October 7, 2025
**Status**: ✅ COMPLETE

## Overview

The analysis system provides comprehensive post-trading evaluation to optimize strategy performance, validate filters, and improve decision-making.

## System Architecture

```
trader/
├── analysis/                           # Analysis module
│   ├── __init__.py                    # Module exports
│   ├── daily_analyzer.py              # Session performance
│   ├── trade_analyzer.py              # Trade patterns
│   ├── filter_analyzer.py             # Filter effectiveness
│   ├── scanner_analyzer.py            # Scanner validation
│   └── README.md                      # Detailed documentation
│
├── analyze.py                          # Unified CLI tool
│
└── logs/                               # Data sources
    ├── trader_YYYYMMDD.log            # Complete session log
    ├── trades_YYYYMMDD.json           # Trade records
    └── analysis_YYYYMMDD.json         # Analysis output
```

## Quick Start

### After Market Close

```bash
cd /Users/karthik/projects/DayTrader/trader

# Run complete analysis for today
./analyze.py all 20251007
```

This generates:
- ✅ P&L summary with win rate and profit factor
- ✅ Entry path breakdown (MOMENTUM vs PULLBACK vs SUSTAINED)
- ✅ Filter effectiveness report
- ✅ Hold time distribution
- ✅ Symbol/direction performance
- ✅ Scanner prediction validation

### Individual Analyses

```bash
# Daily session summary only
./analyze.py daily 20251007

# Trade patterns only
./analyze.py trades 20251007

# Filter effectiveness only
./analyze.py filters 20251007

# Scanner quality only
./analyze.py scanner 20251007
```

## What Each Analyzer Does

### 1. Daily Session Analyzer (`daily`)

**Purpose**: Evaluate overall session performance

**Analyzes**:
- Total P&L and win rate
- Best/worst trades
- Entry path distribution (MOMENTUM, PULLBACK, SUSTAINED)
- Filter blocking patterns
- Performance by hour
- Risk management effectiveness
- IBKR error statistics

**Key Metrics**:
- Daily P&L (target: $1,000 - $2,000)
- Win rate (target: 35-50%)
- Profit factor (target: ≥1.4)
- Average trade (target: $50-100)

**Example Output**:
```
📊 P&L ANALYSIS
Total P&L: $1,692.50
Total Trades: 5
Winners: 3 (60.0%)
Average Winner: $621.33
Profit Factor: 2.17

🎯 FILTER EFFECTIVENESS
Position too large: 42 blocks (33.1%)
→ Implement adaptive position sizing
```

### 2. Trade Performance Analyzer (`trades`)

**Purpose**: Deep dive into trade characteristics

**Analyzes**:
- Performance by symbol
- LONG vs SHORT comparison
- Hold time distribution
- Exit reason effectiveness
- Partials impact

**Key Insights**:
- Which symbols are most profitable
- Whether LONGS or SHORTS work better
- Optimal hold time ranges
- If partial profit-taking helps
- 5-minute rule effectiveness

**Example Output**:
```
📊 PERFORMANCE BY SYMBOL
AMAT: 2 trades, $2,100.00 total, 50% win rate
MU: 1 trade, -$1,180.00, 0% win rate

⏱️  HOLD TIME ANALYSIS
4-8hr: $2,420.00 avg (most profitable)
0-5min: -$166.67 avg (5-min rule needs review)

✂️  PARTIALS
With partials: $916.67 avg
Without partials: -$528.75 avg
→ Partial profit-taking strategy is WORKING
```

### 3. Filter Effectiveness Analyzer (`filters`)

**Purpose**: Optimize entry criteria and prevent over-filtering

**Analyzes**:
- Which filters block most trades
- Most blocked symbols
- Whether filters are too strict/loose
- Recommended threshold adjustments

**Key Insights**:
- If "Position too large" blocks >20% → Need adaptive sizing
- If "Choppy market" blocks >30% → May be too strict
- If "Max attempts" blocks >25% → Good, preventing whipsaws
- If any single filter blocks >40% → Review threshold

**Example Output**:
```
🎯 FILTER BLOCKING SUMMARY
Position too large: 42 (33.1%) ⚠️  FIX SIZING
Choppy market: 28 (22.0%) ✓ GOOD
Max attempts: 31 (24.4%) ✓ GOOD

💡 RECOMMENDATIONS
[HIGH] Position Sizing
  Issue: 42 trades blocked
  Action: Implement adaptive position sizing
  Impact: Could capture $2,100-$6,300 additional profit
```

### 4. Scanner Quality Analyzer (`scanner`)

**Purpose**: Validate scanner predictions vs reality

**Analyzes**:
- Scanner coverage (% of scanned symbols traded)
- TIER performance validation (TIER 1 should have 70%+ win rate)
- Pivot width correlation
- Enhanced scoring effectiveness

**Key Insights**:
- If TIER 1 win rate <60% → Scoring needs improvement
- If tight pivots (<2.5%) win >60% → Filter is working
- If many top-scored symbols untapped → Filters too strict
- If score-P&L correlation >0.3 → Scoring system working

**Example Output**:
```
🎯 TIER PERFORMANCE
TIER 1: 2 trades, 100% win rate ✓ ACCURATE
TIER 2: 2 trades, 50% win rate
TIER 3: 1 trade, 0% win rate

📏 PIVOT WIDTH ANALYSIS
Tight (<2.5%): 75% win rate
Wide (>2.5%): 0% win rate
✓ Pivot width filter is EFFECTIVE

🎯 SCORING CORRELATION
Correlation: 0.427
✓ STRONG positive correlation
```

## Daily Workflow

### Step 1: After Market Close (3:56 PM ET)

Session ends automatically, generating:
- `logs/trader_20251007.log` (complete session log)
- `logs/trades_20251007.json` (trade records)

### Step 2: Run Analysis (4:00 PM ET)

```bash
cd /Users/karthik/projects/DayTrader/trader
./analyze.py all 20251007
```

Review output for:
1. **P&L**: Did we hit target ($1,000-$2,000)?
2. **Win rate**: Is it in range (35-50%)?
3. **Profit factor**: Is it healthy (≥1.4)?
4. **Filters**: Are they blocking too many/too few trades?

### Step 3: Take Action (if needed)

Based on analysis:

**If many "Position too large" blocks:**
```yaml
# trader/config/trader_config.yaml
position_sizing:
  max_position_value: 20000  # Adaptive sizing
```

**If "Choppy market" blocks >40%:**
```yaml
# trader/config/trader_config.yaml
confirmation:
  choppy_atr_multiplier: 0.4  # Lower from 0.5
```

**If 5-minute rule losses >$500:**
```yaml
# trader/config/trader_config.yaml
# Review confirmation logic or raise min_gain threshold
```

**If TIER 1 win rate <60%:**
```bash
# Review scanner scoring logic
cd /Users/karthik/projects/DayTrader/scanner_validation
# Adjust tier thresholds or pivot width criteria
```

### Step 4: Document Changes

Keep a log of adjustments:
```
Oct 7, 2025: Implemented adaptive position sizing
  - Reason: 42 trades blocked by "Position too large"
  - Change: Added max_position_value: 20000
  - Expected: +$2,100-$6,300 additional monthly profit
```

## Weekly Review

### Every Friday After Close

Run aggregated analysis:

```bash
# Analyze full week
for day in 07 08 09 10 11; do
  ./analyze.py daily 202510$day > weekly_analysis.txt
done

# Review weekly_analysis.txt for:
# - Consistent losing symbols (blacklist?)
# - Consistent winning setups (prioritize?)
# - Filter patterns across days
# - Scanner accuracy trends
```

**Key Questions**:
1. Which day was most/least profitable? Why?
2. Did any symbol lose money all week? → Blacklist
3. Did LONGS or SHORTS perform better? → Adjust mix
4. Were filters consistent or erratic? → Tune thresholds
5. Did TIER 1 stocks maintain 60%+ win rate? → Validate

## Monthly Review

### First Weekend of Month

1. **Aggregate monthly metrics**:
   ```bash
   # Calculate monthly totals
   python3 -c "
   from analysis import DailySessionAnalyzer
   import json

   dates = [f'202509{d:02d}' for d in range(1, 31)]
   total_pnl = 0
   total_trades = 0

   for date in dates:
       try:
           with open(f'logs/analysis_{date}.json') as f:
               metrics = json.load(f)
               total_pnl += metrics.get('daily_pnl', 0)
               total_trades += metrics.get('total_trades', 0)
       except:
           pass

   print(f'Monthly P&L: ${total_pnl:.2f}')
   print(f'Total Trades: {total_trades}')
   "
   ```

2. **Compare vs targets**:
   - Target: $20,000 - $40,000 per month
   - Target: 300-500 trades per month
   - Target: 40%+ win rate maintained

3. **Strategic adjustments**:
   - If underperforming: Relax filters slightly
   - If overperforming but low volume: Relax filters more
   - If losing money: Tighten filters, review risk management

## Advanced Analysis

### Custom Queries

```python
# Find all AMAT trades across multiple days
from pathlib import Path
import json

amat_trades = []
for trades_file in Path('logs').glob('trades_*.json'):
    with open(trades_file) as f:
        trades = json.load(f)
        amat_trades.extend([t for t in trades if t['symbol'] == 'AMAT'])

# Analyze AMAT performance
total_pnl = sum(t['pnl'] for t in amat_trades)
win_rate = sum(1 for t in amat_trades if t['pnl'] > 0) / len(amat_trades) * 100

print(f"AMAT: {len(amat_trades)} trades, ${total_pnl:.2f}, {win_rate:.1f}% win rate")
```

### Filter A/B Testing

```bash
# Test filter threshold change
# 1. Backup current config
cp trader_config.yaml trader_config_backup.yaml

# 2. Adjust threshold
# choppy_atr_multiplier: 0.5 → 0.4

# 3. Run backtest with new threshold
python3 backtest/run_monthly_backtest.py --month 9

# 4. Compare results
./analyze.py all 20250930

# 5. Revert if worse, keep if better
```

## Data Retention

### Log Files
- **Keep**: Last 30 days in `logs/`
- **Archive**: Older logs to `logs/archive/YYYY-MM/`
- **Backup**: Monthly to external storage

### Analysis Reports
- **Keep**: All `analysis_YYYYMMDD.json` files permanently
- **Use**: For long-term trend analysis
- **Size**: ~10KB per day, ~3MB per year

## Troubleshooting

### No Trades File
**Symptom**: `⚠️  No trades file found`
**Cause**: Session ended without trades or crashed
**Fix**: Check trader log for errors, verify session ran

### Empty Filter Analysis
**Symptom**: `⚠️  No filter blocks detected`
**Cause**: Filters not working
**Fix**: Check trader_config.yaml, verify filters enabled

### Scanner File Not Found
**Symptom**: `⚠️  No scanner results found`
**Cause**: Enhanced scoring not run
**Fix**: Run scanner with enhanced scoring or use standard JSON

### Import Errors
**Symptom**: `ModuleNotFoundError: No module named 'analysis'`
**Cause**: Running from wrong directory
**Fix**: Always run from `/Users/karthik/projects/DayTrader/trader`

## Performance Benchmarks

### Analysis Speed
- Daily analysis: <5 seconds
- Trade analysis: <3 seconds
- Filter analysis: <2 seconds
- Scanner analysis: <5 seconds
- **Total (all 4)**: ~15 seconds

### File Sizes
- `trades_YYYYMMDD.json`: 2-10 KB (depends on trade count)
- `trader_YYYYMMDD.log`: 5-20 MB (full session)
- `analysis_YYYYMMDD.json`: 5-15 KB (metrics only)

## Future Enhancements

### Planned Features
- [ ] HTML reports with charts (matplotlib/plotly)
- [ ] Automated email reports at EOD
- [ ] Real-time dashboard during trading
- [ ] Multi-day comparison charts
- [ ] Statistical significance testing
- [ ] ML-based filter optimization

### Integration Ideas
- [ ] Slack notifications with daily summary
- [ ] Google Sheets export for tracking
- [ ] Grafana dashboard for visualization
- [ ] Automatic filter tuning based on weekly results

## Related Documentation

- **analysis/README.md**: Detailed module documentation
- **CLAUDE.md**: Overall project context
- **FILTER_DOCUMENTATION.md**: Filter logic reference
- **ENHANCED_SCORING_USAGE.md**: Scanner tier system

---

**Summary**: The analysis system provides comprehensive post-trading evaluation in ~15 seconds, enabling data-driven optimization of filters, position sizing, and strategy parameters. Run `./analyze.py all YYYYMMDD` after each session to track performance and identify improvement opportunities.
