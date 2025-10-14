# BREAKOUT VALIDATION SCRIPT - REQUIREMENTS SPECIFICATION

## Purpose
Analyze actual price action for all October 9, 2025 trades to determine:
1. Were they TRUE or FALSE breakouts?
2. Did our stops hit prematurely (whipsaws)?
3. Were there re-entry opportunities after stops?
4. What patterns distinguish winners from losers?

## Input Data Sources

### 1. Scanner Results
**File**: `stockscanner/output/scanner_results_20251009.json`
- Pivot levels: `resistance` (for longs), `support` (for shorts)
- Targets: `target1`, `target2` (longs), `downside1`, `downside2` (shorts)
- Risk/reward ratios
- Previous close price

### 2. Backtest Trade Results
**File**: `trader/backtest/monthly_results/all_trades_202510.json`
- Filter to Oct 9: `entry_time` contains "2025-10-09"
- Entry price, exit price, stop price
- Entry time, exit time, duration
- P&L, exit reason (STOP, TRAIL_STOP, 15MIN_RULE, EOD)
- Number of partials taken

### 3. Historical 1-Minute Bars (IBKR)
**Fetch from IBKR API** for each traded stock:
- Timeframe: 9:30 AM - 4:00 PM ET on 2025-10-09
- Bar size: 1 minute
- Data: Open, High, Low, Close, Volume
- Why 1-min? Good balance of detail vs data volume

## Analysis Requirements

### Phase 1: Breakout Timeline Analysis

For each trade, create a detailed timeline:

**A. Pre-Breakout Phase**
1. **First Touch**: When did price first touch the pivot?
   - Time of first bar where high >= resistance (long) or low <= support (short)
   - Price at first touch
   
2. **Consolidation**: Did price consolidate at pivot before breaking?
   - Count bars within 0.5% of pivot before breakout
   - Duration of consolidation in minutes
   
3. **Volume Build**: Was there volume accumulation before breakout?
   - Compare volume in 5 bars before breakout vs average
   - Volume ratio (pre-breakout volume / average volume)

**B. Breakout Phase**
1. **Initial Break**: When did price definitively break through pivot?
   - Definition: Bar closes >0.1% above resistance (long) or below support (short)
   - Break time (exact timestamp)
   - Break price (close of breakout bar)
   - Breakout candle size (close - open)
   - Breakout candle volume ratio
   
2. **Immediate Follow-Through** (Critical!)
   - Max move in first 5 bars (5 minutes) after breakout
   - Distance from pivot to max: `(max_price - pivot) / pivot * 100`
   - Did price stay above/below pivot for ≥3 consecutive bars?
   
3. **Initial Range** (First hour after breakout)
   - High and low in first 60 minutes
   - Range size in %
   - Did price return to pivot within first hour?

**C. Our Entry Analysis**
1. **Entry Timing**:
   - Time of our entry (from backtest results)
   - Bars elapsed since initial breakout
   - Price movement from breakout to our entry
   - Were we early, on-time, or late?
   
2. **Entry Quality**:
   - Where in the breakout range did we enter?
   - % position: `(entry - breakout_low) / (breakout_high - breakout_low) * 100`
   - 0-30% = early/good, 70-100% = late/chasing
   
3. **Stop Placement**:
   - Our stop price (from backtest)
   - Distance from entry to stop (in %)
   - Distance from pivot to stop (in %)
   - Was stop at pivot, below pivot, or ATR-based?

**D. Post-Entry Price Action**
1. **Best Price** (favorable direction):
   - Max price reached after our entry (longs)
   - Min price reached after our entry (shorts)
   - Unrealized profit at best: `(best - entry) / entry * 100`
   
2. **Stop Hit Analysis**:
   - Did our stop get hit? (from backtest: exit_reason == 'STOP')
   - Exact time stop was hit
   - Which bar hit our stop (close below stop or just a wick?)
   - Clean stop or whipsaw?
   
3. **Post-Stop Analysis** (CRITICAL):
   - After hitting our stop, what happened?
   - Did price reverse and go profitable? (the "whipsaw" pattern)
   - Max favorable move after stop hit
   - Would we have been profitable with wider stop?

### Phase 2: Breakout Classification

Classify each trade into one of these categories:

**1. TRUE BREAKOUT - Clean Winner**
- Criteria:
  - Price broke pivot with strong volume (≥2x avg)
  - Immediate follow-through ≥1.5% from pivot
  - Never returned to pivot within first 30 minutes
  - Reached target1 or beyond
- Example expected: BA SHORT (held until EOD, +$1,544)

**2. TRUE BREAKOUT - Our Stop Too Tight**
- Criteria:
  - Price broke pivot with good follow-through (≥1%)
  - Hit our stop (minor pullback)
  - Then resumed in breakout direction ≥2%
  - Would have been winner with wider stop
- Pattern: STOP → REVERSE → PROFIT
- This is the "whipsaw" we need to identify!

**3. FALSE BREAKOUT - Immediate Reversal**
- Criteria:
  - Price broke pivot
  - No follow-through (<0.5% from pivot)
  - Reversed back through pivot within ≤5 bars
  - Never recovered
- Example expected: COIN, AVGO (instant stops)

**4. FALSE BREAKOUT - Failed After Initial Move**
- Criteria:
  - Price broke pivot
  - Initial follow-through (0.5-1.5%)
  - Then reversed and failed
  - Returned through pivot within 10-30 bars
- Example expected: Some of the 4-minute stop losses

**5. CHOPPY/INDECISION**
- Criteria:
  - Price crossed pivot multiple times
  - No clear direction
  - Range-bound price action
  - Multiple whipsaws above/below pivot
- Pattern: Consolidation that should have been skipped

**6. RE-ENTRY WINNER**
- Criteria:
  - First breakout failed (our trade stopped out)
  - Second breakout attempt succeeded
  - Would have been profitable on 2nd attempt
- This tells us: 2 attempts per pivot is correct!

### Phase 3: Pattern Analysis

**A. Whipsaw Detection**
For each STOP exit, check:
1. Did price hit stop by <0.3%? (tight stop)
2. After stop, did price reverse ≥1% in original direction?
3. Would a stop 0.5% wider have kept us in?
4. Would a stop 1.0% wider have kept us in?

Calculate "whipsaw cost":
- P&L we would have had with 0.5% wider stop
- P&L we would have had with 1.0% wider stop

**B. Re-entry Opportunity Detection**
For each stopped-out trade:
1. Did pivot break again within 2 hours?
2. Was second breakout stronger? (more volume, larger candle)
3. Did second breakout succeed? (≥1.5% follow-through)
4. What would P&L have been on 2nd entry?

**C. Entry Timing Analysis**
Compare entry timing for winners vs losers:
- Winners: Entered how many bars after breakout?
- Losers: Entered how many bars after breakout?
- Winners: Entry at what % of breakout range?
- Losers: Entry at what % of breakout range?

Calculate "optimal entry window":
- Bars after breakout with highest win rate
- Position in range with highest win rate

### Phase 4: Volume & Strength Analysis

**A. Breakout Strength Metrics**
For each trade:
1. **Volume Surge**:
   - Breakout bar volume vs 20-bar average
   - Classification: <1.5x (weak), 1.5-2.5x (medium), >2.5x (strong)
   
2. **Candle Size**:
   - Breakout candle % size vs ATR
   - Classification: <0.5 ATR (weak), 0.5-1.0 ATR (medium), >1.0 ATR (strong)
   
3. **Momentum Score**:
   - Combined: Volume ratio × Candle/ATR ratio
   - Classification: <2.0 (weak), 2.0-4.0 (medium), >4.0 (strong)

**B. Success Correlation**
- Win rate by volume surge (weak/medium/strong)
- Win rate by candle size (weak/medium/strong)
- Win rate by momentum score (weak/medium/strong)
- Avg P&L by each category

### Phase 5: Stop Placement Analysis

**A. Stop Distance Analysis**
For all trades, calculate:
1. **Actual stop distance**: `abs(entry - stop) / entry * 100`
2. **Pivot-based distance**: `abs(entry - pivot) / entry * 100`
3. **ATR distance**: `stop_distance / ATR`

**B. Optimal Stop Calculation**
For each trade, determine:
1. **Minimum stop needed**: Distance to max adverse move before reversal
2. **Recommended stop**: Max adverse move + 0.3% buffer
3. **Stop efficiency**: `min_stop_needed / actual_stop * 100`
   - >100% = our stop was too tight
   - <100% = our stop was appropriate

**C. Stop Type Comparison**
Compare outcomes:
- Pivot-based stops (stop at resistance/support)
- ATR-based stops (stop at entry ± 2×ATR)
- Fixed % stops (stop at entry ± 0.5%)

Which stop type had:
- Highest win rate?
- Lowest whipsaw rate?
- Best profit factor?

## Output Requirements

### 1. Trade-by-Trade Report
For each of 30 trades, generate:

```
================================================================================
TRADE #1: BB LONG @ $4.81
================================================================================
Scanner Data:
  Resistance: $4.79
  Support: $4.68
  Target1: $4.89
  R/R Ratio: 1.43:1

Breakout Timeline:
  09:47 AM - First touch of resistance ($4.79)
  10:05 AM - Initial breakout (close $4.80, +0.21% above pivot)
  10:06 AM - Follow-through to $4.82 (+0.63% from pivot)
  10:08 AM - Pullback to $4.78 (-0.21% through pivot)
  
  ❌ CLASSIFICATION: FALSE BREAKOUT - Immediate Reversal
  - No strong follow-through (<1%)
  - Returned through pivot in 3 bars
  
Our Trade:
  Entry: $4.81 @ 2:14 PM (bar 3418)
  Entry Timing: 247 bars AFTER initial breakout (VERY LATE!)
  Entry Position: 85% of range (chasing)
  Stop: $4.80 (-0.21%)
  Exit: $4.78 @ 2:28 PM (STOP hit)
  
  Duration: 14 minutes
  P&L: -$44.39
  
Post-Stop Analysis:
  After our stop @ 2:28 PM:
  - Price dropped to $4.70 (low of day)
  - Never recovered above $4.80
  - ✓ Stop was CORRECT - this was a real loser
  
Whipsaw Analysis: NO WHIPSAW
  - Wider stop would NOT have helped
  - This was a genuine false breakout
  
Re-entry Analysis: NO RE-ENTRY
  - No second breakout attempt
  - Skip was correct decision

Recommendations:
  ❌ Should NOT have entered
  - Entry way too late (247 bars after breakout)
  - Entered at 85% of range (chasing top)
  - Weak initial breakout (<1% follow-through)
  - Entry confirmation should have blocked this
```

### 2. Summary Statistics Report

```
================================================================================
OCTOBER 9, 2025 - BREAKOUT VALIDATION SUMMARY
================================================================================

BREAKOUT CLASSIFICATIONS:
  1. TRUE BREAKOUT - Clean Winner:           1 trades (3.3%)  | Avg P&L: +$1,544
  2. TRUE BREAKOUT - Stop Too Tight:         X trades (X%)    | Avg P&L: $XXX
  3. FALSE BREAKOUT - Immediate Reversal:   12 trades (40%)   | Avg P&L: -$XXX
  4. FALSE BREAKOUT - Failed After Move:     8 trades (27%)   | Avg P&L: -$XXX
  5. CHOPPY/INDECISION:                      6 trades (20%)   | Avg P&L: -$XXX
  6. RE-ENTRY WINNER:                        3 trades (10%)   | Avg P&L: +$XXX

WHIPSAW ANALYSIS:
  Total whipsaws: X trades (X% of stops)
  Avg whipsaw cost: -$XXX per trade
  With 0.5% wider stops: X trades saved, +$XXX P&L improvement
  With 1.0% wider stops: X trades saved, +$XXX P&L improvement
  
  CONCLUSION: Stops are [TOO TIGHT / APPROPRIATE / TOO WIDE]

ENTRY TIMING ANALYSIS:
  Winners avg entry: X bars after breakout (X% of range)
  Losers avg entry: X bars after breakout (X% of range)
  
  OPTIMAL ENTRY WINDOW: X-X bars after breakout, <X% of range
  
RE-ENTRY OPPORTUNITIES:
  Trades with re-entry chance: X trades (X%)
  Re-entry success rate: X%
  Missed P&L from not re-entering: $XXX
  
  CONCLUSION: 2 attempts per pivot [IS / IS NOT] sufficient

VOLUME/STRENGTH CORRELATION:
  Strong volume (≥2.5x):  Win rate XX% | Avg P&L: $XXX
  Medium volume (1.5-2.5x): Win rate XX% | Avg P&L: $XXX
  Weak volume (<1.5x):    Win rate XX% | Avg P&L: $XXX
  
  CONCLUSION: Require minimum [X.Xx] volume ratio
```

### 3. Recommendations Report

```
================================================================================
RECOMMENDATIONS BASED ON VALIDATION
================================================================================

CRITICAL FIXES:
1. STOP PLACEMENT: [Current stops too tight/appropriate/too wide]
   - Whipsaw rate: XX%
   - Recommended: [Use ATR stops / Use 0.5% wider / Keep current]
   
2. ENTRY TIMING: Entry delay causing XX% of losses
   - Current: Avg XX bars after breakout
   - Recommended: Enter within X-X bars of breakout
   - Implementation: [Reduce candle close time / Use 30-sec candles / etc]
   
3. VOLUME FILTER: Weak volume breakouts XX% failure rate
   - Current: ≥2.0x volume required
   - Recommended: ≥2.5x volume required
   - Expected impact: Block XX% of false breakouts

ENTRY CONFIRMATION:
- [ ] Add room-to-run filter to MOMENTUM path (CRITICAL BUG)
- [ ] Require minimum X.Xx volume surge
- [ ] Require minimum X% follow-through before entry
- [ ] Block entries >XX% into breakout range

RE-ENTRY STRATEGY:
- XX% of stopped trades had winning re-entry opportunities
- Recommended: [Keep 2 attempts / Allow 3 attempts / Require stronger confirmation on 2nd]
- Pattern to watch: [First weak, second strong / Both strong / etc]

EXPECTED IMPROVEMENT:
With recommended fixes:
- Estimated trades blocked: XX (XX% of false breakouts)
- Estimated P&L improvement: +$X,XXX
- Estimated new win rate: XX%
```

### 4. Detailed Data Export (CSV)

Columns:
- symbol
- side (LONG/SHORT)
- pivot_price
- target1_price
- breakout_time
- breakout_price
- breakout_volume_ratio
- breakout_candle_size_pct
- max_followthrough_pct (first 5 bars)
- stayed_above_pivot_bars (consecutive)
- our_entry_time
- our_entry_price
- bars_after_breakout (entry delay)
- entry_position_in_range_pct (0-100)
- our_stop_price
- stop_distance_pct
- our_exit_time
- our_exit_price
- exit_reason
- pnl
- best_price_after_entry (unrealized profit)
- post_stop_reversal (did it reverse after stop?)
- post_stop_max_move_pct
- whipsaw (TRUE/FALSE)
- wider_stop_05pct_would_help (TRUE/FALSE)
- wider_stop_10pct_would_help (TRUE/FALSE)
- classification (TRUE_BREAKOUT_WINNER / FALSE_BREAKOUT / etc)
- had_reentry_opportunity (TRUE/FALSE)
- reentry_would_win (TRUE/FALSE)
- momentum_score (volume × candle/ATR)
- recommendation (GOOD_TRADE / ENTRY_TOO_LATE / STOP_TOO_TIGHT / etc)

## Implementation Details

### Technology Stack
- Python 3.9+
- ib_insync for IBKR API
- pandas for data analysis
- matplotlib for visualization (optional)

### Script Structure
```python
# File: trader/backtest/validate_breakouts.py

class BreakoutValidator:
    def __init__(self, date, scanner_file, trades_file):
        """Initialize validator with date and data files"""
        
    def fetch_1min_bars(self, symbols):
        """Fetch 1-min bars from IBKR for all symbols"""
        
    def analyze_breakout_timeline(self, symbol, bars, pivot, side):
        """Analyze breakout phase (pre-break, break, post-break)"""
        
    def classify_breakout(self, timeline, our_trade):
        """Classify: TRUE/FALSE/WHIPSAW/RE-ENTRY"""
        
    def detect_whipsaws(self, bars, our_entry, our_stop, our_exit):
        """Check if wider stop would have helped"""
        
    def find_reentry_opportunities(self, bars, pivot, first_trade):
        """Look for second breakout after first failed"""
        
    def calculate_optimal_stop(self, bars, entry_bar, side):
        """Calculate minimum stop needed"""
        
    def generate_trade_report(self, trade, analysis):
        """Generate detailed report for one trade"""
        
    def generate_summary_report(self, all_analyses):
        """Generate summary statistics"""
        
    def export_to_csv(self, all_analyses):
        """Export detailed data to CSV"""
        
    def run(self):
        """Run full validation analysis"""
```

### Execution
```bash
cd trader/backtest
python3 validate_breakouts.py \
  --date 2025-10-09 \
  --scanner ../../stockscanner/output/scanner_results_20251009.json \
  --trades monthly_results/all_trades_202510.json \
  --output validation_report_20251009.txt \
  --csv validation_data_20251009.csv
```

## Success Criteria

The script is successful if it:
1. ✅ Analyzes all 30 trades from Oct 9
2. ✅ Classifies each trade accurately
3. ✅ Identifies whipsaws (stop too tight cases)
4. ✅ Identifies re-entry opportunities
5. ✅ Calculates optimal stop distances
6. ✅ Provides concrete, actionable recommendations
7. ✅ Exports data for further analysis

## Questions for Review

1. **Data granularity**: Is 1-minute bars sufficient or should we use 5-second bars?
   - Pro 1-min: Easier to fetch, less data, clear candles
   - Pro 5-sec: More detail, see exact whipsaw wicks
   - **Recommendation**: Start with 1-min, can upgrade to 5-sec if needed

2. **Breakout definition**: What confirms a breakout?
   - Option A: Close >0.1% above pivot
   - Option B: Close above pivot for 2 consecutive bars
   - Option C: Close above pivot with ≥1.5x volume
   - **Recommendation**: Use Option C (matches our strategy)

3. **Whipsaw threshold**: How much wider to test stops?
   - Test +0.3%, +0.5%, +0.75%, +1.0% wider?
   - **Recommendation**: Test 0.5% and 1.0% (practical ranges)

4. **Re-entry timing**: How long to watch for re-entry?
   - 1 hour after stop?
   - 2 hours?
   - Rest of day?
   - **Recommendation**: 2 hours (practical re-entry window)

5. **Output format**: Single report or multiple files?
   - **Recommendation**: 
     - Console: Summary statistics
     - Text file: Detailed trade-by-trade
     - CSV: Raw data for Excel analysis

