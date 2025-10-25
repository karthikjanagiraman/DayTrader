# Trading Session Analysis Report - Requirements Document

**Date**: October 23, 2025
**Session**: Live Paper Trading
**Log File**: `trader/logs/trader_20251023.log`
**Status**: ⏳ **PENDING USER APPROVAL**

---

## 1. Executive Summary Section

**Deliverable**: High-level overview of trading session

**Content**:
- Trading date and session type (live/paper)
- Start time and end time of monitoring
- Total number of trades executed
- Overall P&L for the session
- Win rate (% of profitable trades)
- Number of stocks monitored
- Active filter configuration summary

**Format**: Markdown table + bullet points

---

## 2. Trade Inventory

**Deliverable**: Complete list of all trades executed during the session

**For Each Trade, Report**:

### 2.1 Basic Trade Information
- Symbol
- Side (LONG/SHORT)
- Entry price
- Entry time (HH:MM:SS ET)
- Exit price
- Exit time (HH:MM:SS ET)
- Shares traded
- Total P&L (including commissions)
- P&L per share
- P&L percentage
- Duration (minutes)

### 2.2 Entry Details
- **Entry path taken**:
  - MOMENTUM (immediate entry)
  - PULLBACK_RETEST (waited for pullback)
  - CVD_MONITORING (triggered by CVD signal)
  - Other entry type
- **Entry reason** (extracted from logs)
- **Resistance/Support level** (pivot price)
- **Distance from pivot at entry** (%)
- **Attempt number** (1st or 2nd attempt)

### 2.3 Exit Details
- **Exit reason**:
  - 7MIN_RULE / 8MIN_RULE
  - STOP_HIT
  - TARGET_HIT
  - PARTIAL_TAKEN
  - EOD_CLOSE
  - MANUAL
  - Other
- **Number of partials taken**
- **Partial details** (if any):
  - Partial 1: % sold, price, time, P&L
  - Partial 2: % sold, price, time, P&L
  - etc.

### 2.4 Scanner Setup Information
- Scanner score
- Risk/Reward ratio from scanner
- Target levels (T1, T2, T3)
- ATR at entry time

**Format**: One detailed table per trade (or structured markdown sections)

---

## 3. Filter Analysis Per Trade

**Deliverable**: Detailed filter decision tracking for each trade

**For Each Trade Entry Attempt, Report**:

### 3.1 Pre-Entry Filters (Applied Before Entry Decision)
- **Gap Filter**:
  - Status: PASSED / BLOCKED / N/A
  - Gap percentage (if applicable)
  - Room to target after gap

- **Choppy Market Filter**:
  - Status: PASSED / BLOCKED
  - 5-minute range value
  - ATR value
  - Range/ATR ratio
  - Threshold used

- **Stochastic Filter**:
  - Status: PASSED / BLOCKED / N/A
  - %K value
  - %D value
  - Interpretation (oversold/overbought/neutral)
  - Threshold range used

- **Room-to-Run Filter**:
  - Status: PASSED / BLOCKED
  - Distance to target (%)
  - Target price used
  - Threshold (usually 1.5%)

### 3.2 Entry Confirmation Filters
- **Volume Filter**:
  - 1-minute candle volume
  - Average volume
  - Volume ratio (actual/average)
  - Threshold (e.g., 2.0x)
  - Status: PASSED / FAILED

- **Candle Size Filter**:
  - Candle size (%)
  - Candle range
  - Threshold (e.g., 0.3%)
  - Status: PASSED / FAILED

- **Sustained Break Logic** (if applicable):
  - Enabled: YES / NO
  - Bars held above/below pivot
  - Max pullback tolerance
  - Status: PASSED / FAILED

### 3.3 CVD Filters (If CVD Enabled)
- **CVD Monitoring Status**:
  - Triggered: YES / NO
  - Entry state: CVD_MONITORING / OTHER

- **CVD Price Validation** (✅ NEW - Oct 23 Fix):
  - Status: PASSED / BLOCKED
  - Current price at CVD trigger
  - Pivot price
  - Price still in breakout: YES / NO
  - Rejection reason (if blocked)

- **CVD Imbalance Data**:
  - Path: PATH1 (aggressive) / PATH2 (sustained)
  - Imbalance percentage
  - Buy volume
  - Sell volume
  - Trend direction (BULLISH/BEARISH/NEUTRAL)
  - Threshold used (20% or 10%)

- **CVD Signal Sequence**:
  - Number of consecutive candles (if PATH2)
  - Imbalance values over time
  - When signal triggered

**Format**: Structured markdown with pass/fail indicators for each filter

---

## 4. Blocked Entry Analysis

**Deliverable**: Analysis of all attempted entries that were blocked

**For Each Blocked Entry, Report**:
- Symbol
- Time of block
- Price at block
- Side (LONG/SHORT)
- Blocking filter name
- Blocking reason (detailed message)
- State at time of block (e.g., CVD_MONITORING, BREAKOUT_DETECTED)
- Filter values that caused block

**Purpose**: Understand which filters are most active in preventing entries

**Format**: Table with one row per blocked entry

---

## 5. CVD Activity Log

**Deliverable**: Comprehensive CVD monitoring activity (since CVD is enabled)

**For Each Stock That Entered CVD_MONITORING State**:
- Symbol
- Entry into CVD_MONITORING time
- Breakout type (WEAK/MOMENTUM)
- Initial volume ratio
- CVD signals detected:
  - Bar number
  - Time
  - Imbalance %
  - Buy/Sell volumes
  - Trend (BULLISH/BEARISH/NEUTRAL)
  - Path (PATH1/PATH2)
  - Consecutive count (if PATH2)
- **CVD Price Validation Checks**:
  - Price at each signal
  - Pivot price
  - Validation result (PASS/BLOCK)
  - Reason if blocked
- Final outcome:
  - ENTERED (triggered trade)
  - BLOCKED (CVD signal but filtered out)
  - RESET (price reversed before entry)
  - TIMEOUT (never reached threshold)

**Purpose**: Validate that CVD price validation fix is working correctly

**Format**: Chronological log per stock with clear indicators

---

## 6. Filter Performance Summary

**Deliverable**: Statistical summary of filter activity

**Metrics to Report**:
- **Filter Activation Count** (how many times each filter was checked)
- **Filter Block Count** (how many times each filter blocked an entry)
- **Filter Pass Rate** (% of checks that passed)
- **Most Active Filter** (blocked most entries)
- **Least Active Filter** (blocked fewest entries)

**Breakdown By Filter**:
1. Gap Filter
2. Choppy Market Filter
3. Stochastic Filter
4. Room-to-Run Filter
5. Volume Filter
6. Candle Size Filter
7. Sustained Break Filter
8. CVD Price Validation Filter (new)
9. Max Attempts Filter
10. Entry Time Window Filter

**Format**: Table + bar chart (text-based)

---

## 7. State Machine Path Analysis

**Deliverable**: Analysis of which entry paths were taken

**For Each Trade, Report**:
- Initial state after breakout detection
- State transitions over time
- Final state that led to entry
- Time spent in each state

**State Transitions to Track**:
1. `IDLE` → `BREAKOUT_DETECTED`
2. `BREAKOUT_DETECTED` → `MOMENTUM` or `WEAK_BREAKOUT_TRACKING`
3. `WEAK_BREAKOUT_TRACKING` → `CVD_MONITORING` or `PULLBACK_RETEST`
4. `CVD_MONITORING` → `ENTRY` or `FAILED` or `RESET`
5. `PULLBACK_RETEST` → `ENTRY` or `FAILED`

**Format**: Flow diagram (text-based) showing state transitions

---

## 8. Comparative Analysis

**Deliverable**: Comparison with previous sessions (if applicable)

**Compare Against**:
- Previous live trading session (Oct 22, 2025)
- Expected backtest performance (Oct 21 backtest with CVD fix)

**Metrics to Compare**:
- Trade count
- Win rate
- Average P&L per trade
- Filter block rates
- CVD trigger frequency
- CVD price validation blocks (new metric)

**Format**: Side-by-side comparison table

---

## 9. Recommendations Section

**Deliverable**: Actionable insights based on analysis

**Content**:
- Filter adjustments needed (if any)
- Entry timing observations
- CVD performance assessment
- Risk management observations
- Configuration changes to consider

**Format**: Numbered list with rationale

---

## 10. Appendices

### Appendix A: Complete Configuration
- Full trader_config.yaml dump
- Filter thresholds used
- Strategy parameters

### Appendix B: Raw Data
- Log excerpts for each trade
- Filter decision logs
- CVD calculation details

### Appendix C: Validation Checklist
- CVD price validation fix verification
- All filters operational: YES/NO
- Data quality checks: PASS/FAIL

---

## Data Sources

**Primary**:
- `/Users/karthik/projects/DayTrader/trader/logs/trader_20251023.log` (main log)
- `/Users/karthik/projects/DayTrader/trader/logs/trades_20251023.json` (if exists)
- `/Users/karthik/projects/DayTrader/trader/logs/trader_state.json` (state recovery)

**Secondary**:
- `/Users/karthik/projects/DayTrader/trader/config/trader_config.yaml` (configuration)
- `/Users/karthik/projects/DayTrader/stockscanner/output/scanner_results_20251023.json` (scanner data)

---

## Output Format

**File Name**: `TRADING_SESSION_ANALYSIS_20251023.md`

**Structure**:
```markdown
# Trading Session Analysis - October 23, 2025

## Executive Summary
[Section 1 content]

## Trade Inventory
### Trade 1: [SYMBOL] [SIDE]
[Section 2 content]

## Filter Analysis
### Trade 1: [SYMBOL] [SIDE]
[Section 3 content]

## Blocked Entries
[Section 4 content]

## CVD Activity Log
[Section 5 content]

## Filter Performance Summary
[Section 6 content]

## State Machine Path Analysis
[Section 7 content]

## Comparative Analysis
[Section 8 content]

## Recommendations
[Section 9 content]

## Appendices
[Section 10 content]
```

---

## Special Requirements

### 1. CVD Price Validation Verification

**CRITICAL**: Verify the Oct 23 fix is working correctly

**Check For**:
- CVD signals detected while price was ABOVE pivot (LONG) → Should be BLOCKED
- CVD signals detected while price was BELOW pivot (SHORT) → Should be BLOCKED
- Log messages showing: "❌ BLOCKED - Price rose/fell through pivot"
- Phase: `cvd_price_reversal` in rejection metadata

**Expected Behavior**:
- CVD only triggers entries when price maintains breakout state
- No CVD entries after price reversed through pivot

### 2. Trade Completeness Check

**Ensure All Trades Are Captured**:
- Check for orphaned positions (entered but not exited in log)
- Verify all partials are accounted for
- Confirm final exit for each entry
- Cross-check with IBKR execution reports (if available)

### 3. Filter Value Extraction

**Log Patterns to Search**:
- Choppy filter: `5-min range:`, `ATR:`, `range/ATR:`
- Stochastic: `%K:`, `%D:`, `OVERSOLD/OVERBOUGHT`
- Room-to-run: `distance to target:`, `threshold:`
- CVD: `imbalance:`, `buy:`, `sell:`, `trend:`
- Volume: `volume ratio:`, `avg volume:`

---

## Acceptance Criteria

**Report Will Be Considered Complete When**:
- ✅ All 10 sections are populated with actual data (not placeholders)
- ✅ Every trade has complete filter analysis
- ✅ All CVD activity is documented with price validation checks
- ✅ Filter performance metrics are calculated
- ✅ Recommendations are data-driven and actionable
- ✅ Report is formatted in clean, readable Markdown
- ✅ All data sources are cited with line numbers
- ✅ CVD price validation fix is verified as working/not working

---

## Estimated Scope

**Number of Trades Expected**: 1-5 (based on current session activity)
**Number of Blocked Entries Expected**: 10-50 (based on filter activity)
**CVD Monitoring Events Expected**: 5-20 (based on log samples)

**Report Length**: 50-100 pages (depending on trade count and detail level)

---

## Questions for User Approval

**Before proceeding, please confirm**:

1. ✅ Is the level of detail in Section 3 (Filter Analysis) sufficient?
2. ✅ Do you want visual diagrams for state transitions (Section 7)?
3. ✅ Should I include raw log excerpts for each trade or summarize?
4. ✅ Do you want comparison with Oct 22 session or skip Comparative Analysis?
5. ✅ Any additional metrics or sections you want included?
6. ✅ Preferred format: Single MD file or split by section?

---

## Timeline

**Estimated Time to Generate Report**: 15-30 minutes
**Dependencies**: User approval of this requirements document

---

**Status**: ⏳ **AWAITING USER SIGN-OFF**

Please review this requirements document and provide approval or request changes before I proceed with analysis.
