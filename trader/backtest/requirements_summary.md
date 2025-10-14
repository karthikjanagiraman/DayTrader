# BREAKOUT VALIDATION SCRIPT - REQUIREMENTS SUMMARY

## Executive Summary

Created comprehensive requirements for a validation script that will analyze the **actual price action** of all 30 October 9 trades to determine:

1. **TRUE vs FALSE breakouts** - Did the pivot genuinely break or was it a fake?
2. **Whipsaws** - Were our stops too tight? Would wider stops have saved us?
3. **Re-entry opportunities** - Did the setup work on 2nd attempt after 1st failed?
4. **Entry timing** - Did we enter too late (at the peak vs at the break)?

## Key Analysis Components

### 1. Breakout Timeline (Per Trade)
- **When did price first break the pivot?** (exact timestamp)
- **How much follow-through?** (max move in first 5 minutes)
- **When did WE enter?** (how many bars after breakout?)
- **Where in the range?** (0% = early, 100% = chasing top)
- **What happened after our stop hit?** (reverse to profit = whipsaw!)

### 2. Six Classification Categories

1. **TRUE BREAKOUT - Clean Winner** (BA example: +$1,544)
2. **TRUE BREAKOUT - Stop Too Tight** (stop hit → price reversed to profit)
3. **FALSE BREAKOUT - Immediate Reversal** (COIN, AVGO: instant fails)
4. **FALSE BREAKOUT - Failed After Move** (some follow-through, then failed)
5. **CHOPPY/INDECISION** (multiple whipsaws, should skip)
6. **RE-ENTRY WINNER** (1st attempt failed, 2nd succeeded)

### 3. Critical Questions Answered

**Whipsaw Analysis:**
- How many stops were "whipsaws"? (price reversed to profit after stop)
- Would 0.5% wider stops have saved us?
- Would 1.0% wider stops have saved us?
- Estimated P&L improvement with wider stops

**Entry Timing:**
- Winners: Avg entry X bars after breakout
- Losers: Avg entry X bars after breakout
- **Optimal entry window**: When should we enter?

**Re-entry Opportunities:**
- How many stopped trades had winning 2nd attempts?
- Pattern: Weak first → Strong second?
- Should we allow 3 attempts instead of 2?

**Volume/Strength:**
- Win rate by volume surge (weak/medium/strong)
- Win rate by candle size
- What's the minimum volume we should require?

## Data Sources

1. **Scanner results** (pivot levels, targets)
2. **Backtest results** (our entry/exit/P&L)
3. **IBKR 1-minute bars** (actual price action all day)

## Output Deliverables

### 1. Detailed Trade-by-Trade Report
Example for each of 30 trades:
```
TRADE #15: BA SHORT @ $219.92
Breakout: 10:05 AM @ $221.00 (volume 2.3x)
Our Entry: 10:21 AM (16 bars after breakout, 45% of range) ✅ GOOD
Exit: 3:59 PM (EOD) @ $216.04
P&L: +$1,544.86

CLASSIFICATION: TRUE BREAKOUT - Clean Winner
- Strong volume (2.3x)
- Sustained move (held below pivot 5+ hours)
- Reached downside1 target
- No whipsaw
- ✅ Perfect trade
```

### 2. Summary Statistics
- Breakout classification distribution (% in each category)
- Whipsaw analysis (how many, $ cost)
- Entry timing stats (winners vs losers)
- Volume/strength correlation
- **CONCLUSION: Stops are [TOO TIGHT / OK / TOO WIDE]**

### 3. Recommendations Report
- Stop placement: wider/narrower/keep same?
- Entry timing: enter earlier/later?
- Volume filter: require higher threshold?
- Re-entry: allow more attempts?
- **Expected P&L improvement**: +$X,XXX

### 4. CSV Data Export
All metrics in spreadsheet format for deeper analysis

## Implementation Plan

**Script**: `trader/backtest/validate_breakouts.py`

**Execution**:
```bash
python3 validate_breakouts.py \
  --date 2025-10-09 \
  --scanner ../../stockscanner/output/scanner_results_20251009.json \
  --trades monthly_results/all_trades_202510.json
```

**Duration**: ~5-10 minutes (fetching 1-min bars for 30 stocks)

## Key Design Decisions for Review

### 1. Data Granularity
**Question**: Use 1-minute bars or 5-second bars?

**Recommendation**: **1-minute bars**
- ✅ Faster to fetch (30 stocks × 390 bars = 11,700 vs 234,000)
- ✅ Cleaner candles (less noise)
- ✅ Sufficient for whipsaw detection
- ⚠️ Might miss intra-minute wicks

**Alternative**: Start with 1-min, upgrade to 5-sec if needed

### 2. Breakout Definition
**Question**: What confirms a breakout?

**Options**:
- A: Close >0.1% above pivot
- B: Close above pivot for 2 consecutive bars
- C: Close above pivot with ≥1.5x volume

**Recommendation**: **Option C** (matches our strategy)

### 3. Whipsaw Testing
**Question**: How much wider to test stops?

**Recommendation**: Test **+0.5%** and **+1.0%** wider
- These are practical ranges (0.5% = ~$2 on $400 stock)
- Too wide (>1%) defeats purpose of tight stops

### 4. Re-entry Window
**Question**: How long to watch for re-entry opportunity?

**Recommendation**: **2 hours** after stop
- Practical re-entry window
- Most setups develop within 1-2 hours
- Beyond that, it's a different setup

### 5. Output Format
**Question**: Console only or multiple files?

**Recommendation**: **Three outputs**:
- **Console**: Summary statistics (quick view)
- **Text file**: Detailed trade-by-trade (readable report)
- **CSV**: Raw data (Excel analysis)

## Expected Insights

This script will definitively answer:

1. **Were most losses due to false breakouts or bad execution?**
   - If mostly FALSE BREAKOUTS → Need better entry filters
   - If mostly WHIPSAWS → Need wider stops
   - If mostly LATE ENTRIES → Need faster entry confirmation

2. **What's the optimal entry timing?**
   - Should we enter immediately on breakout?
   - Or wait 2-3 bars for confirmation?
   - Current 1-min candle close causing too much delay?

3. **Are our stops too tight?**
   - If 50%+ are whipsaws → stops too tight
   - If <10% are whipsaws → stops appropriate

4. **Should we allow more re-entry attempts?**
   - If many 2nd attempts win → keep 2 attempts
   - If need 3rd attempts → increase limit

## Next Steps

1. **Review requirements** (this document)
2. **Implement script** (~1-2 hours)
3. **Run analysis** on Oct 9 data (~10 minutes)
4. **Review results** and create action plan
5. **Apply fixes** to strategy
6. **Re-run backtest** to validate improvements

