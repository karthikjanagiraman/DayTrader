# Post-Trading Analysis Module

**Comprehensive analysis tools for PS60 trading system performance evaluation**

## Overview

This module provides systematic post-trading analysis to:
- ✅ Validate scanner predictions against actual market movements
- ✅ Compare live trading with same-day backtest
- ✅ Create detailed session walkthrough narratives
- ✅ Evaluate daily trading performance
- ✅ Identify winning/losing patterns
- ✅ Optimize filter thresholds
- ✅ Improve strategy parameters

## Module Structure

**Note**: All analysis files have been reorganized into the `dailyanalysis/` folder for better organization.

```
dailyanalysis/
├── __init__.py                  # Module exports
├── daily_analyzer.py            # Daily session performance
├── trade_analyzer.py            # Trade-level patterns
├── filter_analyzer.py           # Filter effectiveness
├── scanner_analyzer.py          # Scanner prediction quality
├── market_validator.py         # Market data validation (NEW)
├── backtest_comparator.py      # Same-day backtest comparison (NEW)
├── session_walkthrough.py      # Chronological session narrative (NEW)
├── eod_report.py               # Comprehensive EOD orchestrator (NEW)
├── analyze_oct2_trades.py       # October 2nd analysis
├── analyze_retest_trades.py     # Pullback/retest analysis
├── analyze_short_stops.py       # Short stop analysis
├── analyze_volume_confirmation.py # Volume confirmation
├── deepdive_oct2_analysis.py    # Deep dive analysis
└── README.md                    # This file
```

## Quick Start - NEW COMPREHENSIVE EOD WORKFLOW

### 🎯 RECOMMENDED: Complete EOD Analysis (3 Steps)

After market close, run the comprehensive EOD analysis which automatically:
1. Validates scanner predictions against actual market data
2. Runs same-day backtest and compares with live results
3. Creates detailed session walkthrough

```bash
cd /Users/karthik/projects/DayTrader/trader

# Run complete EOD analysis (RECOMMENDED)
./analyze.py eod 20251007

# Skip IBKR connection if TWS not available
./analyze.py eod 20251007 --skip-ib
```

This generates:
- **Step 1**: Market validation showing which breakouts were real vs false
- **Step 2**: Backtest comparison showing if strategy logic worked correctly
- **Step 3**: Session walkthrough documenting every trade decision
- **Step 4**: Standard performance metrics and insights
- **Executive Summary**: Actionable recommendations

## Quick Start - Standard Analysis

### 1. Daily Session Analysis

Analyzes complete trading session with P&L breakdown, entry paths, and filter effectiveness.

```bash
cd /Users/karthik/projects/DayTrader/trader

# Analyze today's session
python3 analysis/daily_analyzer.py 20251007

# Outputs:
# - P&L summary (win rate, avg trade, profit factor)
# - Entry path breakdown (MOMENTUM vs PULLBACK vs SUSTAINED)
# - Filter blocking analysis (which filters blocked trades)
# - Timing analysis (performance by hour)
# - Risk management effectiveness
```

**Example Output:**
```
================================================================================
DAILY SESSION ANALYSIS - 20251007
================================================================================

📊 P&L ANALYSIS
--------------------------------------------------------------------------------
Total P&L: $1,692.50
Total Trades: 5
  Winners: 3 (60.0%)
  Losers: 2 (40.0%)

Average Trade: $338.50
Average Winner: $621.33
Average Loser: -$287.00

Profit Factor: 2.17

💰 Best Trade:
  AMAT LONG: $2,419.99
  Entry: $219.12 → Exit: $223.70
  Reason: EOD

❌ Worst Trade:
  MU LONG: -$1,180.00
  Entry: $182.84 → Exit: $181.66
  Reason: 5MIN_RULE

📈 ENTRY PATH ANALYSIS
--------------------------------------------------------------------------------
Total Entries: 5

  MOMENTUM_BREAKOUT: 3 (60.0%)
    → Immediate entry (volume ≥1.3x, candle ≥0.8%)
  SUSTAINED_BREAK: 2 (40.0%)
    → Grinding entry (held 2+ minutes above pivot)

🎯 FILTER EFFECTIVENESS ANALYSIS
--------------------------------------------------------------------------------
Total Blocks: 127

Top Blocking Filters:

  Position too large: 42 (33.1%)
    → Check position sizing - may need adaptive sizing
  Max attempts reached: 31 (24.4%)
    → Good - prevents whipsaw losses
  Choppy market filter: 28 (22.0%)
    → Saved ~$2,800 (estimated)
  Waiting for pullback to pivot: 15 (11.8%)
    → Confirmation logic working - patience required
```

### 2. Trade Performance Analysis

Deep dive into trade characteristics and patterns.

```bash
# Analyze trade patterns
python3 analysis/trade_analyzer.py 20251007

# Outputs:
# - Performance by symbol
# - LONG vs SHORT comparison
# - Hold time distribution
# - Exit reason effectiveness
# - Partials impact
```

**Example Output:**
```
================================================================================
TRADE PERFORMANCE ANALYSIS
================================================================================

📊 PERFORMANCE BY SYMBOL
--------------------------------------------------------------------------------
Symbol   Trades   Total P&L    Avg P&L   Win%   Avg Shares
----------------------------------------------------------------------
AMAT          2   $2,100.00    $1,050.00  50.0%        1,000
INTC          2     $862.50      $431.25  50.0%        1,000
LRCX          2   $1,106.24      $553.12  50.0%          806
MU            1  -$1,180.00   -$1,180.00   0.0%        1,000

💰 Best Symbol: AMAT ($2,100.00)
❌ Worst Symbol: MU (-$1,180.00)

📈 PERFORMANCE BY DIRECTION
--------------------------------------------------------------------------------
Direction   Trades   Total P&L    Avg P&L   Win%
--------------------------------------------------
LONG             5   $1,692.50     $338.50  60.0%

⏱️  HOLD TIME ANALYSIS
--------------------------------------------------------------------------------
Hold Time     Trades   Total P&L    Avg P&L   Win%
--------------------------------------------------
0-5min             3    -$500.00    -$166.67  33.3%
10-30min           1      $35.00      $35.00 100.0%
4-8hr              1   $2,420.00   $2,420.00 100.0%

💰 Most Profitable Hold Time: 4-8hr ($2,420.00 avg)

⚡ Quick Exits (≤7 min): 3 trades, -$500.00 total, -$166.67 avg
   → 5-minute rule needs review

✂️  PARTIAL PROFIT ANALYSIS
--------------------------------------------------------------------------------
Strategy             Trades   Total P&L    Avg P&L   Win%
------------------------------------------------------------
With Partials             3   $2,750.00     $916.67  66.7%
Without Partials          2  -$1,057.50    -$528.75  50.0%

📊 Comparison:
  Taking partials improves avg P&L by $1,445.42
  → Partial profit-taking strategy is WORKING
```

### 3. Filter Effectiveness Analysis

Analyzes why trades were blocked and recommends filter adjustments.

```bash
# Analyze filter blocking patterns
python3 analysis/filter_analyzer.py logs/trader_20251007.log

# Outputs:
# - Filter blocking summary
# - Most blocked symbols
# - Recommended threshold adjustments
```

**Example Output:**
```
================================================================================
FILTER EFFECTIVENESS ANALYSIS
================================================================================

🎯 FILTER BLOCKING SUMMARY
--------------------------------------------------------------------------------
Total Blocks: 127

Filter Reason                                      Count        %   Action
--------------------------------------------------------------------------------
Position too large                                    42     33.1% ⚠️  FIX SIZING
Max attempts reached                                  31     24.4% ✓ GOOD
Choppy market filter                                  28     22.0% ✓ GOOD
Waiting for pullback to pivot                        15     11.8% ⚠️  TOO STRICT?
Insufficient room to target                           11      8.7% ✓ GOOD

📊 MOST BLOCKED SYMBOLS
--------------------------------------------------------------------------------
Symbol   Blocks   Top Reason
--------------------------------------------------
BA           12   Position too large
GOOGL         9   Position too large
GS            8   Position too large
AAPL          6   Max attempts reached

💡 RECOMMENDED ADJUSTMENTS
--------------------------------------------------------------------------------

1. [HIGH] Position Sizing
   Issue: 42 trades blocked (33.1%)
   Action: Implement adaptive position sizing (max_position_value)
   Impact: Could capture $2,100 - $6,300 additional profit

2. [MEDIUM] Room to Target
   Issue: 11 trades blocked (8.7%)
   Action: Consider lowering min_room_to_target_pct from 1.5% to 1.0%
   Impact: Allow trades with smaller targets

3. [LOW] Max Attempts
   Issue: 31 stocks whipsawed (24.4%)
   Action: No change needed - filter preventing losses
   Impact: Saved ~$3,100 in whipsaw losses
```

### 4. Scanner Quality Analysis

Validates scanner predictions vs actual outcomes.

```bash
# Analyze scanner prediction accuracy
python3 analysis/scanner_analyzer.py \
  ../stockscanner/output/rescored_20251007.csv \
  logs/trades_20251007.json

# Outputs:
# - Scanner coverage (% of scanned symbols traded)
# - TIER performance validation
# - Pivot width correlation
# - Scoring system effectiveness
```

**Example Output:**
```
================================================================================
SCANNER PREDICTION QUALITY ANALYSIS
================================================================================

📊 SCANNER COVERAGE ANALYSIS
--------------------------------------------------------------------------------
Total Scanned Symbols: 57
Symbols Traded: 5
Traded from Scanner: 5 (8.8% coverage)

Top 10 Scanner Symbols NOT Traded:
  GS     (Score: 100, Tier: TIER 1) - Position too large (547.4% > 200.0% max)
  BA     (Score:  95, Tier: TIER 1) - Position too large (233.3% > 200.0% max)
  AMZN   (Score:  92, Tier: TIER 1) - Position too large (425.6% > 200.0% max)
  UBER   (Score:  88, Tier: TIER 2) - Waiting for pullback to pivot
  GOOGL  (Score:  85, Tier: TIER 2) - Position too large (2054.1% > 200.0% max)

🎯 TIER PERFORMANCE ANALYSIS
--------------------------------------------------------------------------------
Tier       Trades   Win%   Avg P&L    Total P&L
--------------------------------------------------
TIER 1          2  100.0%   $1,341.25    $2,682.50
TIER 2          2   50.0%     $113.12      $226.24
TIER 3          1    0.0%  -$1,180.00   -$1,180.00

📈 TIER 1 Validation:
   Expected: 70-80% win rate
   Actual: 100.0%
   ✓ TIER 1 classification is ACCURATE

📏 PIVOT WIDTH ANALYSIS
--------------------------------------------------------------------------------
Pivot Width   Trades   Win%   Avg P&L
----------------------------------------
<1%                1  100.0%  $2,420.00
1-2%               2   50.0%     $56.25
2-3%               1    0.0%  -$143.22
>10%               1    0.0% -$1,180.00

📊 Key Finding:
   Tight Pivots (≤2.5%): 75.0% win rate
   Wide Pivots (>2.5%): 0.0% win rate
   ✓ Pivot width filter is EFFECTIVE - keep max at 5%

🎯 SCORING CORRELATION ANALYSIS
--------------------------------------------------------------------------------
Score Range   Trades   Win%   Avg P&L
----------------------------------------
85-100             3   66.7%    $766.16
70-85              1  100.0%     $35.00
<70                1    0.0% -$1,180.00

📊 Score-P&L Correlation: 0.427
   ✓ STRONG positive correlation - scoring system is WORKING
```

## Typical Workflow

### After Market Close (Daily Routine)

1. **Daily Session Analysis** (5 minutes)
   ```bash
   python3 analysis/daily_analyzer.py 20251007
   ```
   - Review P&L and win rate
   - Check which entry paths worked best
   - Identify top-blocking filters

2. **Trade Pattern Analysis** (3 minutes)
   ```bash
   python3 analysis/trade_analyzer.py 20251007
   ```
   - See which symbols/directions performed best
   - Verify partials are helping
   - Check if hold times are optimal

3. **Filter Review** (if needed)
   ```bash
   python3 analysis/filter_analyzer.py logs/trader_20251007.log
   ```
   - Only if many trades were blocked
   - Check for over-filtering
   - Adjust thresholds if recommended

4. **Scanner Validation** (weekly)
   ```bash
   python3 analysis/scanner_analyzer.py \
     ../stockscanner/output/rescored_20251007.csv \
     logs/trades_20251007.json
   ```
   - Verify TIER 1 stocks still have 70%+ win rate
   - Check pivot width correlation
   - Validate scoring system

### Weekly Review

Compare multiple days:
```bash
# Analyze full week
for day in 07 08 09 10 11; do
  python3 analysis/daily_analyzer.py 202510$day
done

# Compare patterns across days
# Identify consistent winners/losers
# Adjust filters based on week's data
```

## Key Metrics to Monitor

### Daily Targets
- **Total P&L**: $1,000 - $2,000 (1-2% of account)
- **Win Rate**: 35-50% (acceptable with good R/R)
- **Profit Factor**: ≥1.4 (winners larger than losers)
- **Avg Trade**: $50 - $100

### Warning Signs
- ⚠️ Win rate <30% (filters too loose)
- ⚠️ Win rate >70% (filters too tight, missing trades)
- ⚠️ Profit factor <1.2 (winners not large enough)
- ⚠️ Max loss >$1,500 (position sizing issue)
- ⚠️ Most trades hit 5-min rule (confirmation too strict)

### Filter Health
- ✅ 10-30% of pivot checks blocked (healthy filtering)
- ✅ Top blocker is "Max attempts" (prevents whipsaws)
- ✅ Choppy filter saves $500+ per day
- ❌ >40% blocked by "Waiting for..." (too strict)
- ❌ >20% "Position too large" (need adaptive sizing)

### Scanner Health
- ✅ TIER 1 win rate ≥60% (70% target)
- ✅ Tight pivots (<2.5%) win >60%
- ✅ Enhanced score correlates with P&L (r>0.3)
- ❌ Many top-scored symbols untapped (filters too strict)
- ❌ Traded symbols not in scanner (watchlist issue)

## Data Sources

### Input Files
- **logs/trades_YYYYMMDD.json**: Closed trades with P&L
  ```json
  [
    {
      "symbol": "AMAT",
      "side": "LONG",
      "entry_price": 219.12,
      "exit_price": 223.70,
      "shares": 1000,
      "pnl": 2419.99,
      "entry_time": "2025-10-07T07:20:58",
      "exit_time": "2025-10-07T12:55:00",
      "reason": "EOD",
      "partials": 1
    }
  ]
  ```

- **logs/trader_YYYYMMDD.log**: Complete session log
  - Entry/exit timestamps
  - Filter blocking reasons
  - Position management events
  - IBKR error messages

- **../stockscanner/output/rescored_YYYYMMDD.csv**: Enhanced scoring
  ```csv
  symbol,enhanced_score,tier,pivot_width_pct,test_count,notes
  GS,100,TIER 1,1.85,12,Tight pivot 1.85% | Heavily tested (12x)
  AAPL,95,TIER 1,2.23,10,Tight pivot 2.23% | Heavily tested (10x)
  ```

### Output Files
- **logs/analysis_YYYYMMDD.json**: Metrics in JSON format
  - Programmatically accessible
  - Can be aggregated across days
  - Used for trend analysis

## Advanced Usage

### Batch Analysis (Multiple Days)

```python
from analysis import DailySessionAnalyzer

# Analyze full month
dates = [f"202510{d:02d}" for d in range(1, 32)]

all_metrics = []
for date_str in dates:
    analyzer = DailySessionAnalyzer(date_str)
    metrics = analyzer.analyze()
    all_metrics.append(metrics)

# Aggregate metrics
total_pnl = sum(m['daily_pnl'] for m in all_metrics)
avg_win_rate = sum(m['win_rate'] for m in all_metrics) / len(all_metrics)

print(f"Monthly P&L: ${total_pnl:.2f}")
print(f"Avg Win Rate: {avg_win_rate:.1f}%")
```

### Custom Analysis

```python
from analysis import TradePerformanceAnalyzer
import pandas as pd

# Load trades
analyzer = TradePerformanceAnalyzer(date_str="20251007")

# Access trade data directly
df = analyzer.df

# Custom analysis
high_volume_trades = df[df['shares'] >= 1000]
avg_pnl = high_volume_trades['pnl'].mean()

print(f"1000-share trades avg: ${avg_pnl:.2f}")
```

### Filter Tuning

```python
from analysis import FilterEffectivenessAnalyzer

# Analyze filter effectiveness
analyzer = FilterEffectivenessAnalyzer("logs/trader_20251007.log")
analyzer.analyze()

# Get specific filter data
position_blocks = analyzer.get_blocked_trades("Position too large")

# Count high-priced stocks
high_priced = sum(1 for b in position_blocks if 'GS' in b['symbol'] or 'AMZN' in b['symbol'])

print(f"High-priced stocks blocked: {high_priced}")
print(f"→ Implement adaptive position sizing")
```

## Integration with Trading System

The trader automatically generates analysis-ready data:

1. **During Trading**: Logs all filter blocks, entry paths, position events
2. **At EOD**: Saves `trades_YYYYMMDD.json` with complete trade records
3. **After Close**: Run analysis modules manually

**Future Enhancement**: Automated EOD analysis email/report.

## Troubleshooting

### No Trades File
```
⚠️  No trades file found: logs/trades_20251007.json
```
**Cause**: No trades were executed or session ended abnormally
**Solution**: Check trader log for errors, verify session ran

### Empty Analysis
```
⚠️  No filter blocks detected
```
**Cause**: Filters may not be working correctly
**Solution**: Check trader_config.yaml, verify filter logic is enabled

### Scanner File Not Found
```
⚠️  Scanner file not found: ../stockscanner/output/rescored_20251007.csv
```
**Cause**: Enhanced scoring not run for this date
**Solution**: Run scanner with enhanced scoring or use standard scanner JSON

## Best Practices

1. **Run analysis daily** - Don't let data pile up
2. **Track trends** - Save analysis JSONs for historical comparison
3. **Act on insights** - Adjust filters based on recommendations
4. **Validate scanner** - Weekly scanner quality checks
5. **Document changes** - Note why filter thresholds were adjusted

## Future Enhancements

- [ ] HTML report generation with charts
- [ ] Automated email reports at EOD
- [ ] Multi-day trend visualization
- [ ] Statistical significance testing
- [ ] ML-based filter optimization
- [ ] Real-time dashboard during trading

---

**Created**: October 7, 2025
**Last Updated**: October 7, 2025
**Author**: PS60 Trading System
