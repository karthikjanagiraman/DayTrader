# Daily Scanner Validation Guide

## Overview

This guide explains how to validate scanner results daily to ensure:
1. Scanner is producing accurate resistance/support levels
2. Breakouts identified actually occur in live trading
3. Targets are realistic and achievable
4. Live trader performance aligns with expectations

---

## Validation Workflow

### Step 1: Run Scanner (8:00 AM ET)

```bash
cd /Users/karthik/projects/DayTrader/stockscanner
python3 scanner.py --category all
```

**Output**: `output/scanner_results_YYYYMMDD.json`

---

### Step 2: Start Live Trader (9:30 AM ET Sharp)

```bash
cd /Users/karthik/projects/DayTrader/trader
python3 trader.py > logs/trader_$(date +%Y%m%d).log 2>&1 &
```

**Critical**: Must start at EXACTLY 9:30 AM ET to capture breakouts

---

### Step 3: Run End-of-Day Validation (4:15 PM ET)

Wait 15 minutes after market close for data to settle.

```bash
cd /Users/karthik/projects/DayTrader/scanner_validation
python3 validate_scanner.py $(date +%Y-%m-%d) ../stockscanner/output/scanner_results_$(date +%Y%m%d).json
```

**Output**:
- Console report
- `validation_YYYYMMDD.csv`

---

### Step 4: Double-Check with IBKR (Optional but Recommended)

```bash
python3 verify_with_ibkr.py $(date +%Y-%m-%d) validation_$(date +%Y%m%d).csv
```

**Purpose**:
- Verifies validation script accuracy
- Uses actual IBKR historical data as source of truth
- Confirms breakouts and targets

---

### Step 5: Analyze Trader Performance

```bash
python3 analyze_session.py $(date +%Y%m%d)
```

This script compares:
- Scanner validation winners vs trader captured
- Why winners were missed
- Filter statistics
- Entry timing analysis

---

## Validation Scripts Explained

### 1. `validate_scanner.py`

**What it does**:
- Connects to IBKR
- For each stock in scanner output:
  - Monitors if resistance/support was broken
  - Checks if target was hit after breakout
  - Determines if it was a real or false breakout
- Generates success rate statistics

**Key Metrics**:
- LONG success rate (target: 35-45%)
- SHORT success rate (target: 20-30%)
- False breakout percentage (target: <50%)

**Example Output**:
```
LONG Breakouts: 23 occurred, 8 successful (34.8%)
SHORT Breakouts: 18 occurred, 4 successful (22.2%)
```

---

### 2. `verify_with_ibkr.py`

**What it does**:
- Reads validation CSV
- Fetches 1-minute historical bars from IBKR
- Re-validates each breakout using raw price data
- Compares results with validation script

**Purpose**: Double-check validation accuracy

**Key Metrics**:
- Match rate (target: >95%)
- Mismatches indicate validation script issues

**Example Output**:
```
Matches: 38/40 (95.0%)
Mismatches: 2/40 (5.0%)
✓ VALIDATION ACCURACY: EXCELLENT
```

---

### 3. `analyze_session.py` (To Be Created)

**What it does**:
- Compares validation winners with trader logs
- Identifies which winners trader captured
- Analyzes why winners were missed:
  - Filter blocks (position size, no_breakout, etc.)
  - Timing issues (late start)
  - Already in position
- Generates recommendations

**Key Metrics**:
- Winner capture rate (target: >70%)
- Most common miss reasons
- Filter effectiveness

---

## Interpreting Results

### Scanner Success Rates

| Metric | Target | Interpretation |
|--------|--------|----------------|
| LONG success | 35-45% | Higher = better resistance levels |
| SHORT success | 20-30% | Lower = support levels less reliable |
| False breakouts | <50% | Lower = cleaner setups |
| Total setups | 40-60 | More = more opportunities |

### Trader Capture Rates

| Metric | Target | Interpretation |
|--------|--------|----------------|
| Winners captured | >70% | % of validation winners traded |
| Miss reason: late start | 0% | Should be ZERO (start at 9:30) |
| Miss reason: position size | <20% | Filter may be too strict |
| Miss reason: no_breakout | <10% | Hybrid logic issue |

### Red Flags

⚠️ **Scanner Issues**:
- LONG success rate <25%: Resistance levels too aggressive
- Total false breakouts >60%: Pivot calculation may be wrong
- No breakouts for full day: Scanner may have failed

⚠️ **Trader Issues**:
- Winner capture rate <30%: Check filters and timing
- High "no_breakout" misses: Started too late
- High "position size" misses: Filter too restrictive

---

## Daily Checklist

### Morning (Before Market Open)

- [ ] Scanner ran successfully (check for JSON output)
- [ ] Scanner found 40-60 setups
- [ ] No errors in scanner log
- [ ] IBKR TWS is running (port 7497)
- [ ] Trader ready to start at 9:30 AM

### Market Hours

- [ ] Trader started at 9:30 AM ET (not later!)
- [ ] First entry signal within 30 minutes (if breakouts occur)
- [ ] No crashes or errors
- [ ] Positions being entered/managed

### After Market Close

- [ ] Run validation script by 4:30 PM
- [ ] Review validation report
- [ ] Check success rates (LONG: 35-45%, SHORT: 20-30%)
- [ ] Identify winning setups
- [ ] Run session analysis
- [ ] Compare trader vs validation
- [ ] Document issues/observations

### Weekly Review (Friday)

- [ ] Compare full week: validation vs trader performance
- [ ] Calculate weekly capture rate
- [ ] Identify recurring miss patterns
- [ ] Adjust filters if needed
- [ ] Review position sizing limits

---

## Common Issues and Solutions

### Issue: No Breakouts All Day

**Symptoms**: Validation shows 0 breakouts

**Possible Causes**:
1. Market was ranging (no trending moves)
2. Scanner pivots were too far from current price
3. Scanner failed to run correctly

**Solution**:
- Check if scanner JSON has valid pivot levels
- Review market conditions (VIX, index movement)
- Verify scanner ran without errors

---

### Issue: High False Breakout Rate (>60%)

**Symptoms**: Many breakouts reverse back through pivot

**Possible Causes**:
1. Choppy market conditions
2. Pivot levels not validated properly
3. Too tight pivot/target spacing

**Solution**:
- Add volume confirmation to scanner
- Increase minimum distance to pivot filter
- Review scanner logic for pivot calculation

---

### Issue: Trader Misses Most Winners

**Symptoms**: Validation shows 10 winners, trader got 2

**Possible Causes**:
1. **Late start** (started after 9:30 AM)
2. Position size filter too strict
3. Hybrid entry logic issues

**Solution**:
- Ensure 9:30 AM start (SET ALARM!)
- Review position_size filter (increase max%)
- Check max_pullback_bars setting

---

### Issue: IBKR Verification Mismatches

**Symptoms**: verify_with_ibkr.py shows <90% match rate

**Possible Causes**:
1. Validation script using different data source
2. Timing differences (1-min bars vs ticks)
3. Bug in validation logic

**Solution**:
- Review mismatched symbols manually
- Check validation script pivot detection
- Ensure both use same timeframe

---

## Automation (Future Enhancement)

### Cron Jobs (macOS/Linux)

```bash
# Run scanner at 8:00 AM ET (5:00 AM PDT)
0 5 * * 1-5 cd /Users/karthik/projects/DayTrader/stockscanner && python3 scanner.py --category all

# Start trader at 9:30 AM ET (6:30 AM PDT)
30 6 * * 1-5 cd /Users/karthik/projects/DayTrader/trader && python3 trader.py

# Run validation at 4:30 PM ET (1:30 PM PDT)
30 13 * * 1-5 cd /Users/karthik/projects/DayTrader/scanner_validation && python3 validate_scanner.py

# Run analysis at 5:00 PM ET (2:00 PM PDT)
0 14 * * 1-5 cd /Users/karthik/projects/DayTrader/scanner_validation && python3 analyze_session.py
```

### Email Alerts

Add to validation script:
```python
if success_rate < 0.25:  # Less than 25% LONG success
    send_email("Scanner Alert", "LONG success rate below threshold")

if trader_capture_rate < 0.30:  # Captured less than 30% of winners
    send_email("Trader Alert", "Low winner capture rate")
```

---

## Files and Locations

```
DayTrader/
├── stockscanner/
│   └── output/
│       └── scanner_results_YYYYMMDD.json   # Scanner output
│
├── trader/
│   └── logs/
│       └── trader_YYYYMMDD.log             # Trader log
│
└── scanner_validation/
    ├── validate_scanner.py                  # Daily validation
    ├── verify_with_ibkr.py                  # IBKR double-check
    ├── analyze_session.py                   # Session analysis (TBD)
    ├── validation_YYYYMMDD.csv              # Validation results
    └── analysis_YYYYMMDD.md                 # Daily analysis report
```

---

## Success Criteria

### Daily

- ✅ Scanner runs without errors
- ✅ Validation success rate: LONG 35-45%, SHORT 20-30%
- ✅ Trader captures >70% of validation winners
- ✅ No critical errors or crashes

### Weekly

- ✅ Average daily winner capture rate >65%
- ✅ Scanner consistency: similar success rates across days
- ✅ Trader P&L aligns with backtest expectations (±30%)

### Monthly

- ✅ Scanner refinement based on validation feedback
- ✅ Trader filter tuning to improve capture rate
- ✅ Documentation of all issues and resolutions

---

## Support and Troubleshooting

### Logs to Check

1. **Scanner**: `stockscanner/logs/scanner_YYYYMMDD.log`
2. **Trader**: `trader/logs/trader_YYYYMMDD.log`
3. **Validation**: Console output (save with `tee`)

### Key Log Patterns

**Scanner Failed**:
```
✗ IBKR connection failed
✗ No data for symbol
```

**Trader Issues**:
```
❌ {SYMBOL}: LONG blocked @ ${PRICE} - {REASON}
✗ Order placement failed
```

**Validation Issues**:
```
✗ Error fetching {SYMBOL}
⚠ MISMATCH - Validation: True, IBKR: False
```

---

## Version History

- **v1.0** (Oct 6, 2025): Initial documentation
- Scanner validation working
- IBKR verification script created
- Session analysis pending

---

## Next Steps

1. Create `analyze_session.py` script
2. Add email alerting for anomalies
3. Create dashboard for visualization
4. Automate with cron jobs
5. Weekly summary reports
