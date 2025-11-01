# CLAUDE.md - Analysis Folder Guide

This folder contains **post-session analysis reports** and tools for evaluating trading performance.

## 📁 Folder Purpose

The `analysis/` folder is where we store:
- Daily session analysis reports
- Live trade parsing scripts
- Performance comparisons
- Strategy insights and learnings
- Filter effectiveness studies

## 📊 Session Analysis Reports

### When to Generate

Generate a comprehensive session analysis report when the user requests:
- "analyze today's session"
- "give me a report for [date]"
- "what happened today?"
- "session analysis"

### Report Requirements

**Follow**: `trader/TRADING_SESSION_REPORT_REQUIREMENTS.md` (10-section standardized format)

**Required Sections**:
1. **Executive Summary** - Key metrics, P&L, win rate, trade count
2. **Trade Inventory** - Complete details for every trade executed
3. **Filter Analysis** - All filter decisions with actual values
4. **Blocked Entry Analysis** - Why entries were rejected
5. **CVD Activity Log** - CVD signals and price validation checks
6. **Filter Performance Summary** - Activation/block rates per filter
7. **State Machine Path Analysis** - Entry paths taken
8. **Comparative Analysis** - vs backtest expectations
9. **Recommendations** - Data-driven improvements
10. **Appendices** - Configuration, raw data

### Data Sources

**For Live Sessions**:
```
trader/logs/trader_YYYYMMDD.log              # Main trading log
trader/logs/trades_YYYYMMDD.json             # Trade records
trader/logs/live_entry_decisions_YYYYMMDD.json  # Entry attempts
trader/logs/trader_state.json                # Session state
trader/config/trader_config.yaml             # Active config
stockscanner/output/scanner_results_YYYYMMDD.json  # Scanner data
```

**For Backtests**:
```
trader/backtest/results/backtest_trades_YYYYMMDD.json
trader/backtest/results/backtest_entry_decisions_YYYYMMDD.json
trader/backtest/logs/backtest_YYYYMMDD_HHMMSS.log
```

### File Naming Convention

**Session Analysis Reports**:
```
SESSION_ANALYSIS_YYYYMMDD.md           # Daily trading session
LIVE_SESSION_LEARNINGS_YYYYMMDD.md    # Key lessons from live session
BACKTEST_ANALYSIS_YYYYMMDD.md         # Backtest analysis
```

**Trade Data**:
```
live_trades_YYYYMMDD.json              # Parsed trade data
trades_summary_YYYYMMDD.csv            # CSV export
```

### Report Format

Use **clean Markdown** with:
- ✅ Tables for structured data
- ✅ Code blocks for configuration
- ✅ Bullet points for lists
- ✅ Headers (##, ###) for organization
- ✅ Emojis for visual cues (⭐, 🟢, 🔴, ⚠️)
- ✅ Horizontal rules (---) for section breaks

**Example Header**:
```markdown
# Trading Session Analysis - October 31, 2025

**Account**: Paper Trading ($50,000)
**Strategy**: PS60 Automated Breakout
**Scanner Results**: 8 setups (3 LONG, 5 SHORT)

## Executive Summary

**Performance**:
- Total Trades: 5
- Winners: 2 (40.0%)
- Losers: 3 (60.0%)
- Total P&L: -$234.56 (-0.47%)
- Avg Trade: -$46.91

**Key Findings**:
- Volume filter too strict (blocked 3 winners)
- CVD price validation working correctly
- 8-minute rule saved $500 on PLTR
```

## 📈 Trade Inventory Requirements

**For Each Trade, Document**:

```markdown
### Trade #1: NVDA LONG

**Entry**:
- Time: 10:23:45 ET
- Price: $437.85
- Shares: 456
- Entry Path: MOMENTUM_BREAKOUT
- Resistance: $437.50
- Volume: 2.3x average (PASS ✅)
- Candle Size: 1.8% (PASS ✅)

**Filter Results**:
- Gap Filter: PASS (no gap)
- Choppy Filter: PASS (5-min range 2.1% > 0.5×ATR)
- Stochastic: PASS (below 80)
- Room-to-Run: PASS (3.2% to target1)
- CVD Price Validation: PASS (price $437.85 > pivot $437.50)

**Exit**:
- Time: 10:31:20 ET
- Price: $436.92
- Duration: 7.6 minutes
- Exit Reason: 8MIN_RULE (no progress after 8 min)
- P&L: -$423.48 (-0.93%)

**Analysis**:
- Correct entry (all filters passed)
- Weak follow-through after breakout
- 8-minute rule prevented larger loss
```

## 🔍 Filter Analysis Requirements

**Document ALL filter checks** with actual values:

```markdown
## Filter Analysis

### Trade #1 - NVDA LONG (10:23:45)

| Filter | Result | Value | Threshold | Pass |
|--------|--------|-------|-----------|------|
| Gap Filter | PASS | No gap detected | N/A | ✅ |
| Choppy Filter | PASS | 5-min range 2.1% | > 0.5×ATR (1.0%) | ✅ |
| Stochastic | PASS | Stoch(14,3,3) = 68 | < 80 | ✅ |
| Room-to-Run | PASS | 3.2% to target1 | > 1.5% | ✅ |
| Volume Filter | PASS | 2.3x average | > 1.0x | ✅ |
| Candle Size | PASS | 1.8% candle | > 0.8% | ✅ |
| CVD Price Valid | PASS | Price $437.85 > Pivot $437.50 | Must be above | ✅ |
| Max Attempts | PASS | Attempt 1 of 2 | ≤ 2 | ✅ |

**Outcome**: ENTERED (all filters passed)
```

## 🚫 Blocked Entry Analysis

**Document rejected entries**:

```markdown
## Blocked Entry Analysis

### TSLA LONG - BLOCKED by Volume Filter (09:47:22)

**Context**:
- Pivot: $445.00
- Price: $445.25 (broke resistance)
- State: WEAK_BREAKOUT_TRACKING

**Filter Results**:
| Filter | Result | Value | Threshold | Pass |
|--------|--------|-------|-----------|------|
| Volume Filter | FAIL | 0.87x average | > 1.0x | ❌ |

**Outcome**: Stock moved +4.2% by EOD (MISSED WINNER ⭐)

**Recommendation**: Lower volume threshold from 1.0x to 0.75x
```

## 📊 CVD Activity Log

**Document CVD monitoring events**:

```markdown
## CVD Activity Log

### SMCI LONG - CVD_MONITORING (10:15:00 - 10:23:00)

**Entry Sequence** (8 attempts):

| Time | Event | CVD Signal | Price | Pivot | Price Valid? | Result |
|------|-------|------------|-------|-------|--------------|--------|
| 10:15:00 | CVD_START | - | $235.20 | $235.50 | BELOW | MONITORING |
| 10:16:12 | CVD_SIGNAL | 68% buy | $235.30 | $235.50 | BELOW | BLOCKED |
| 10:17:45 | CVD_SIGNAL | 72% buy | $235.45 | $235.50 | BELOW | BLOCKED |
| 10:19:03 | CVD_SIGNAL | 65% buy | $235.52 | $235.50 | ABOVE ✅ | ENTERED |

**Outcome**: CVD price validation working correctly - entered only after price broke pivot

**CVD Imbalance Data**:
- Average buy volume: 1,245,000 shares (68%)
- Average sell volume: 587,000 shares (32%)
- Duration in monitoring: 8 minutes
```

## 🎯 Filter Performance Summary

**Aggregate filter statistics**:

```markdown
## Filter Performance Summary

| Filter | Activations | Blocks | Pass Rate | Most Common Block |
|--------|-------------|--------|-----------|-------------------|
| Volume Filter | 42 | 28 | 33.3% | 0.85x-0.95x range |
| Choppy Filter | 42 | 12 | 71.4% | Range < 0.5×ATR |
| Room-to-Run | 42 | 8 | 81.0% | < 1.5% to target |
| CVD Price Valid | 15 | 7 | 53.3% | Price below pivot |
| Stochastic | 42 | 3 | 92.9% | Stoch > 80 |
| Gap Filter | 42 | 2 | 95.2% | Gap > 1% w/o room |
| Max Attempts | 42 | 1 | 97.6% | > 2 attempts |

**Key Insights**:
- Volume filter is the strictest (66.7% block rate)
- CVD price validation blocking 46.7% of CVD signals (working as designed)
- Stochastic rarely triggers (only 7.1% block rate)
```

## 📁 File Organization

### Current Files in Analysis Folder

```
analysis/
├── CLAUDE.md                              # This file (guidance)
├── SESSION_ANALYSIS_20251031.md           # Oct 31 session report
├── LIVE_SESSION_LEARNINGS_20251029.md     # Oct 29 learnings
├── live_trades_20251031.json              # Oct 31 parsed trades
└── parse_live_trades.py                   # Trade parsing script
```

### parse_live_trades.py

**Purpose**: Extracts trade data from log files for analysis

**Usage**:
```bash
cd /Users/karthik/projects/DayTrader/trader/analysis
python3 parse_live_trades.py --log ../logs/trader_20251031.log --output live_trades_20251031.json
```

**Output Format**:
```json
{
  "trades": [
    {
      "symbol": "NVDA",
      "side": "LONG",
      "entry_time": "2025-10-31T10:23:45",
      "entry_price": 437.85,
      "shares": 456,
      "exit_time": "2025-10-31T10:31:20",
      "exit_price": 436.92,
      "pnl": -423.48,
      "exit_reason": "8MIN_RULE"
    }
  ]
}
```

## 🔄 Analysis Workflow

### Daily Workflow (After Market Close)

1. **Collect Data**:
   ```bash
   cd /Users/karthik/projects/DayTrader/trader/analysis
   python3 parse_live_trades.py \
     --log ../logs/trader_$(date +%Y%m%d).log \
     --output live_trades_$(date +%Y%m%d).json
   ```

2. **Generate Report**:
   - User requests: "analyze today's session"
   - Claude generates: `SESSION_ANALYSIS_YYYYMMDD.md`
   - Follow all 10 required sections

3. **Review & Iterate**:
   - Identify filter issues
   - Document missed winners
   - Recommend parameter adjustments
   - Track improvements over time

### Weekly Workflow

1. **Aggregate Performance**:
   - Collect all daily session reports
   - Calculate weekly metrics
   - Identify recurring patterns

2. **Filter Optimization**:
   - Analyze blocked entries across multiple days
   - Calculate optimal thresholds
   - Test parameter changes in backtest

3. **Strategy Evolution**:
   - Document major changes in `trader/PROGRESS_LOG.md`
   - Update configuration in `trader/config/trader_config.yaml`
   - Run validation backtests

## 🎯 Quality Standards

### Report Must Include

✅ **Complete trade inventory** - Every trade documented
✅ **All filter checks** - With actual values and thresholds
✅ **CVD price validation** - Verify Oct 23 fix working
✅ **Blocked entries** - With reasons and outcomes
✅ **Filter performance** - Activation/block rates
✅ **Recommendations** - Data-driven, actionable
✅ **Comparative analysis** - vs backtest expectations
✅ **Configuration snapshot** - Active settings used

### Report Must NOT Include

❌ Generic commentary without data
❌ Missing filter values
❌ Incomplete trade details
❌ Recommendations without supporting evidence
❌ Vague conclusions

## 📚 Reference Documentation

**Master Guides**:
- `trader/TRADING_SESSION_REPORT_REQUIREMENTS.md` - Report specification
- `trader/PROGRESS_LOG.md` - Implementation history
- `trader/FILTER_DOCUMENTATION.md` - Filter reference
- `trader/CLAUDE.md` - Project overview

**Session Management**:
- `trader/LIVE_TRADER_READY_FOR_TESTING.md` - Pre-launch checklist
- `trader/LOGGING_GUIDE.md` - Log file format

**Validation**:
- `trader/validation/CLAUDE.md` - Validation system guide
- `trader/validation/validate_market_outcomes.py` - Outcome validator

## 🚀 Quick Commands

**Generate today's session analysis** (manual prompt to Claude):
```
"analyze today's session"
```

**Parse today's trades**:
```bash
cd /Users/karthik/projects/DayTrader/trader/analysis
python3 parse_live_trades.py \
  --log ../logs/trader_$(date +%Y%m%d).log \
  --output live_trades_$(date +%Y%m%d).json
```

**View recent trades**:
```bash
cat live_trades_$(date +%Y%m%d).json | python3 -m json.tool
```

**Check filter statistics** (from log):
```bash
grep -E "Filter Result|BLOCKED" ../logs/trader_$(date +%Y%m%d).log | wc -l
```

## 💡 Pro Tips

1. **Generate reports immediately after session** - Data is fresh, insights are clearer
2. **Compare with backtest** - Validate strategy execution vs expected behavior
3. **Track filter changes over time** - Document evolution in PROGRESS_LOG.md
4. **Focus on missed winners** - These are the highest-value optimizations
5. **Validate CVD price validation** - Ensure Oct 23 fix is working correctly
6. **Use tables liberally** - Makes filter analysis scannable
7. **Include raw values** - Not just PASS/FAIL, show actual numbers

---

**Last Updated**: November 1, 2025
**Status**: Active - Daily session analysis ongoing
