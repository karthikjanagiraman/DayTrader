# Open Questions - Detailed Explanations
**Date**: October 25, 2025

---

## Question 1: Target Selection

**Question**: Should we check target1, target2, or target3 when classifying if a breakout was a "WINNER"?

### The Problem

Scanner provides 3 targets:
```json
{
  "symbol": "NVDA",
  "resistance": 182.50,
  "target1": 184.14,  // 0.9% gain
  "target2": 185.50,  // 1.6% gain
  "target3": 187.00   // 2.5% gain
}
```

When we analyze a breakout, which target should price reach for us to call it a "WINNER"?

### Example Scenario

**NVDA Breakout**:
- Entry: $183.00
- After 30 minutes:
  - Reached $184.20 (hit target1 ✓)
  - Never reached target2 ($185.50)
  - Never reached target3 ($187.00)

**If we use target1**: This is a WINNER ✅
**If we use target2**: This is NOT a winner (maybe RUNNER)
**If we use target3**: This is NOT a winner (maybe RUNNER)

### Why It Matters

**Affects classification**:
- Using target1 (conservative): More breakouts classified as WINNER
- Using target3 (aggressive): Fewer breakouts classified as WINNER

**Affects validation**:
- If we ENTERED this trade and it hit target1 only:
  - With target1 check: GOOD_ENTRY ✅ (we entered a winner)
  - With target3 check: BAD_ENTRY or NEUTRAL ⚠️ (didn't reach target)

### My Recommendation

**Use target1** because:
1. That's where we take our first partial (50%)
2. Most conservative - if it hits target1, we made money
3. Matches our actual trading (we don't hold for target3)

---

## Question 2: Stop Level

**Question**: For LONG trades, where should we place the stop for outcome analysis?

### The Problem

Scanner identifies resistance at $182.50. We enter LONG at $183.00 (broke resistance).

**Where should we check if stop was hit?**
- Option A: At resistance ($182.50) - the original pivot
- Option B: Below resistance ($182.40) - slightly below pivot
- Option C: At entry price ($183.00) - breakeven

### Example Scenario

**Price action after entry**:
```
09:47:00 - Entry $183.00 (broke resistance $182.50)
09:48:00 - Price dips to $182.45 (below resistance)
09:49:00 - Price recovers to $184.50 (hits target1)
```

**If stop at resistance ($182.50)**:
- 09:48:00 - STOPPED OUT ✗
- Classification: STOPPED_OUT (even though it later hit target)
- This would trigger EARLY_EXIT flag ⚠️

**If stop below resistance ($182.40)**:
- 09:48:00 - NOT stopped out ✓
- 09:49:00 - Hit target1
- Classification: WINNER ✅

### Why It Matters

**Affects outcome classification**:
- Tighter stop (at pivot): More STOPPED_OUT outcomes
- Looser stop (below pivot): More WINNER outcomes

**Affects validation accuracy**:
- We want stop placement to match what backtester actually uses
- If backtester uses stop at resistance, validator should too

### My Recommendation

**Use stop at resistance ($182.50)** because:
1. PS60 methodology: Initial stop goes at the pivot
2. Matches backtester implementation
3. Captures "stop too tight" scenarios (EARLY_EXIT flag)

---

## Question 3: Time Window for Outcome Analysis

**Question**: How many minutes after breakout should we analyze to classify the outcome?

### The Problem

We need to decide: how long do we watch the trade play out?

**Options**:
- 15 minutes - short window
- 30 minutes - medium window (proposed)
- 60 minutes - long window
- Full day - until market close

### Example Scenario

**NVDA Breakout at 09:47:00**:

**After 15 minutes (10:02:00)**:
- Price at $183.50 (+0.27% gain)
- Never hit target1 ($184.14)
- Classification: CHOPPY or RUNNER

**After 30 minutes (10:17:00)**:
- Price at $184.20 (+0.66% gain)
- Hit target1 at 10:15:00 ✓
- Classification: WINNER

**After 60 minutes (10:47:00)**:
- Price at $187.50 (+2.46% gain)
- Hit all 3 targets
- Classification: WINNER (huge winner)

### Why It Matters

**Affects outcome classification**:
- Shorter window (15 min): Misses slower winners → false negatives
- Longer window (60 min): Catches late-developing trades
- Full day: Unrealistic (we use 8-min rule, take partials)

**Affects trade realism**:
- We typically hold 15-30 minutes
- After 30 min, we've taken partials or exited
- Analyzing beyond our typical hold time is unrealistic

### My Recommendation

**Use 30 minutes** because:
1. Matches our typical hold time
2. Catches both fast and slow winners
3. Realistic - beyond 30 min we've likely taken partials/exited
4. Not too short (15 min misses slow starters)
5. Not too long (60 min unrealistic for our strategy)

---

## Question 4: $ Impact Estimation

**Question**: How do we calculate the dollar impact of missed winners or avoided losses?

### The Problem

When we find a MISSED_WINNER or GOOD_BLOCK, we want to estimate:
- "How much money did we lose by missing this?"
- "How much money did this filter save us?"

But we don't know the exact position size that would have been used.

### Example Scenario

**MISSED_WINNER: AMD @ $162.50**
- Entry: $162.50
- Target1: $165.00 (+1.54% gain)
- We BLOCKED this trade (it was a winner)

**How much did we miss?**

**Option A: Fixed shares (1000 shares)**
```
Profit = 1000 × ($165.00 - $162.50) = $2,500
```

**Option B: 1% risk position sizing (proposed)**
```
Risk Amount = $50,000 × 1% = $500
Stop Distance = $162.50 - $162.50 = assume $0.50
Shares = $500 / $0.50 = 1,000 shares
Profit (50% partial) = 500 × $2.50 = $1,250
```

**Option C: Percentage only**
```
Gain = 1.54%
Impact = "1.54% opportunity"
```

### Why It Matters

**Affects filter value calculation**:
- CVD Filter blocked 32 trades
- If we estimate $150 saved per block → Filter value = $4,800
- If we estimate $50 saved per block → Filter value = $1,600

**Affects recommendations**:
- MISSED_WINNER with $2,500 impact → "Critical - fix filter!"
- MISSED_WINNER with $250 impact → "Minor - acceptable trade-off"

### My Recommendation

**Use 1% risk position sizing with 50% partial** because:
1. Matches our actual trading (1% risk per trade)
2. Accounts for stop distance (realistic sizing)
3. Uses 50% partial (we don't hold 100% to target)
4. Conservative estimate (doesn't assume full position to target)
5. Gives realistic $ values for decision-making

**Formula**:
```python
risk_amount = account_size × 0.01  # $500 on $50k
stop_distance = abs(entry - stop)   # Estimate if not in log
shares = risk_amount / stop_distance
profit = shares × 0.5 × (target - entry)  # 50% partial only
```

---

## Question 5: Re-run on Same Data

**Question**: If we run the validator twice on the same date, should it overwrite the old report or create a new timestamped one?

### The Problem

**Scenario**: You run validator for Oct 21:
```bash
# First run
python3 validate_market_outcomes.py ... 2025-10-21

# Creates: reports/validation_results_20251021.json

# Second run (after fixing a bug)
python3 validate_market_outcomes.py ... 2025-10-21
```

**What should happen?**

**Option A: Overwrite** (proposed)
```
reports/validation_results_20251021.json (updated)
```

**Option B: Create timestamped version**
```
reports/validation_results_20251021_153045.json (first run)
reports/validation_results_20251021_154230.json (second run)
```

### Why It Matters

**Option A (Overwrite)**:
- ✅ Cleaner - one file per date
- ✅ Latest run is always authoritative
- ✅ No confusion about which file to use
- ❌ Lose history of previous runs

**Option B (Timestamped)**:
- ✅ Preserves history
- ✅ Can compare multiple runs
- ❌ Many files accumulate
- ❌ Unclear which is current

### My Recommendation

**Overwrite (Option A)** because:
1. Results are deterministic (same inputs = same outputs)
2. If code changes, old results are outdated anyway
3. Cleaner file organization
4. If you need history, use git to track changes

**But**: Add a timestamp INSIDE the JSON so you know when it was generated:
```json
{
  "validation_date": "2025-10-21",
  "generated_at": "2025-10-25T15:42:30",
  "total_breakouts": 127,
  ...
}
```

---

## Question 6: Error Handling

**Question**: What if the validator can't find cached bars for some stocks?

### The Problem

**Scenario**: Scanner has 53 stocks, but only 50 have cached bars.

```bash
# Trying to load bars for HOOD
bars_file = backtest/data/HOOD_20251021_1min.json
# File NOT FOUND!
```

**Why might bars be missing?**
1. Backtest crashed before processing this stock
2. IBKR data unavailable for this stock on that date
3. Stock was filtered out before bars were fetched
4. File was accidentally deleted

**What should validator do?**

**Option A: Skip with warning** (proposed)
```
⚠️  HOOD: Bars not found, skipping
⚠️  SNAP: Bars not found, skipping

Validated 51/53 stocks (2 skipped)
```

**Option B: Error and stop**
```
ERROR: Bars not found for HOOD
Validation aborted
```

**Option C: Try to fetch from IBKR**
```
⚠️  HOOD: Bars not cached, fetching from IBKR...
✓ Fetched and cached
```

### Why It Matters

**Option A (Skip with warning)**:
- ✅ Validator completes for available stocks
- ✅ Doesn't crash entire validation
- ❌ Incomplete validation (missing stocks)

**Option B (Error and stop)**:
- ✅ Forces you to fix missing data
- ❌ Can't validate ANY stocks if ONE is missing
- ❌ Frustrating if data truly unavailable

**Option C (Fetch on demand)**:
- ✅ Complete validation even with missing cache
- ❌ Adds complexity
- ❌ Rate limiting issues if many missing
- ❌ Makes validator depend on IBKR connection

### My Recommendation

**Skip with warning (Option A)** because:
1. Validator should be read-only (no side effects)
2. Can still validate 51/53 stocks
3. Warning message tells you what's missing
4. You can investigate why bars are missing separately

**Implementation**:
```python
try:
    bars = self.load_saved_bars(symbol, date)
except FileNotFoundError:
    print(f"⚠️  {symbol}: Bars not found, skipping")
    self.skipped_symbols.append(symbol)
    continue

# ... continue with next stock
```

**Summary report includes skipped count**:
```
========================================
VALIDATION SUMMARY
========================================
Stocks analyzed: 51
Stocks skipped: 2 (HOOD, SNAP)
Total breakouts: 127
...
```

---

## Summary & Recommendations

| Question | My Recommendation | Rationale |
|----------|-------------------|-----------|
| 1. Target | **target1** | Conservative, matches our 50% partial strategy |
| 2. Stop | **At resistance** | Matches PS60 methodology and backtester |
| 3. Time Window | **30 minutes** | Realistic hold time, catches slow winners |
| 4. $ Impact | **1% risk + 50% partial** | Realistic position sizing, conservative profit estimate |
| 5. Re-run | **Overwrite** | Deterministic results, cleaner organization |
| 6. Missing Bars | **Skip with warning** | Complete partial validation, non-blocking |

---

## Do You Agree?

Please review each question and let me know:
- ✅ Agree with recommendation → We proceed
- 🔄 Different approach → Tell me your preference
- ❓ Still unclear → I'll explain further with more examples

**Ready to finalize requirements once you approve these decisions!** 🚀
