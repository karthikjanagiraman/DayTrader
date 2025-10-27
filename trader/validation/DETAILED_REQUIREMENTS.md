# Entry Decision Validation System - DETAILED REQUIREMENTS
**Date**: October 25, 2025
**Status**: ✅ REQUIREMENTS FINALIZED - READY FOR IMPLEMENTATION

---

## 📋 IMPLEMENTATION READY CHECKLIST

✅ All 6 open questions resolved (see Final Specifications section)
✅ Profit-taking checkpoints defined (every 25% toward target1)
✅ 5-star rating system specified (1-5 stars based on checkpoints)
✅ Full day analysis confirmed (until 16:00 ET, not 30 min)
✅ Stop logic defined (use backtester's actual strategy)
✅ Missing bars handling defined (download + CRITICAL ERROR)
✅ Re-run behavior defined (always overwrite)
✅ Very detailed comments required in implementation

**Next Step**: Implement `validate_market_outcomes.py` with detailed inline comments

---

## Core Insight

**User's Key Point**: "We don't need to fetch 1-min bars from IBKR, they're already available as the backtest runs on this data"

**Implication**:
- ✅ Backtester ALREADY CACHES 1-min bars to `backtest/data/SYMBOL_YYYYMMDD_1min.json`
- ✅ Validator simply LOADS these cached files (no re-fetching needed)
- ✅ No code changes needed in backtester
- ✅ Faster, no rate limits, consistent data

---

## Data Sources

### 1. Scanner Results (Input)
**File**: `stockscanner/output/scanner_results_YYYYMMDD.json`
**Contains**:
```json
{
  "symbol": "NVDA",
  "resistance": 182.50,
  "support": 180.00,
  "target1": 184.14,
  "target2": 185.50,
  "target3": 187.00,
  "score": 85,
  "risk_reward": 3.2
}
```

### 2. Entry Decision Log (Input)
**File**: `backtest/results/backtest_entry_decisions_YYYYMMDD.json`
**Contains**:
```json
{
  "backtest_date": "2025-10-21",
  "total_attempts": 87,
  "entered": 6,
  "blocked": 81,
  "attempts": [
    {
      "timestamp": "2025-10-21T09:47:23",
      "symbol": "NVDA",
      "side": "LONG",
      "price": 183.03,
      "decision": "BLOCKED",
      "reason": "room_to_run_filter - only 0.61% to target",
      "filters": {
        "choppy": {"enabled": true, "result": "PASS"},
        "room_to_run": {"enabled": true, "result": "BLOCK"},
        "cvd": {"enabled": true, "result": "BLOCK"}
      }
    }
  ]
}
```

### 3. Historical 1-Min Bars (Input) - ✅ **ALREADY AVAILABLE**
**File**: `backtest/data/SYMBOL_YYYYMMDD_1min.json`
**Status**: ✅ Already cached by backtester
**Action Required**: None - just load existing files

**Format** (actual cached format):
```json
[
  {
    "date": "2025-10-21T09:30:00-04:00",
    "open": 182.79,
    "high": 182.79,
    "low": 182.06,
    "close": 182.09,
    "volume": 757997.0,
    "average": 182.353,
    "barCount": 2927
  },
  {
    "date": "2025-10-21T09:31:00-04:00",
    "open": 182.09,
    "high": 182.35,
    "low": 181.86,
    "close": 182.02,
    "volume": 795448.0,
    "average": 182.061,
    "barCount": 2944
  }
]
```

**Note**: This is a JSON array of bar objects (not wrapped in a dict)

---

## Complete Workflow (Step-by-Step)

### Step 1: Validator Loads Cached Bars

**File**: `validation/validate_market_outcomes.py`

**Load Bars Method**:
```python
def load_saved_bars(self, symbol, date):
    """
    Load cached 1-min bars from backtest

    Args:
        symbol: Stock ticker
        date: Trading date

    Returns:
        List of bar dicts

    Raises:
        FileNotFoundError: If bars not cached (backtest didn't run)
    """
    bars_file = Path(__file__).parent.parent / 'backtest' / 'data' / \
                f"{symbol}_{date.strftime('%Y%m%d')}_1min.json"

    if not bars_file.exists():
        raise FileNotFoundError(
            f"Bars not found: {bars_file}\n"
            f"Did you run backtest first for {symbol} on {date}?"
        )

    with open(bars_file) as f:
        bars = json.load(f)  # Already a list of bar dicts

    return bars
```

**Note**: The cached file is already a JSON array, not wrapped in a dict.

---

## Detailed Validation Logic

### Step 1: Identify All Breakouts

**Input**: 1-min bars for stock
**Output**: List of breakout events

**Algorithm**:
```python
def identify_breakouts(self, bars, resistance, support):
    """
    Find ALL times price broke resistance or support

    Rules:
    - LONG breakout: Current bar close > resistance AND previous bar close <= resistance
    - SHORT breakout: Current bar close < support AND previous bar close >= support
    - Re-breaks count as separate breakouts

    Returns:
        List of breakout dicts
    """
    breakouts = []

    for i in range(1, len(bars)):  # Start at 1 (need previous bar)
        curr_bar = bars[i]
        prev_bar = bars[i-1]

        # LONG breakout detection
        if curr_bar['close'] > resistance and prev_bar['close'] <= resistance:
            breakouts.append({
                'timestamp': curr_bar['timestamp'],
                'type': 'LONG',
                'price': curr_bar['close'],
                'bar_index': i,
                'broke_level': resistance
            })

        # SHORT breakout detection
        elif curr_bar['close'] < support and prev_bar['close'] >= support:
            breakouts.append({
                'timestamp': curr_bar['timestamp'],
                'type': 'SHORT',
                'price': curr_bar['close'],
                'bar_index': i,
                'broke_level': support
            })

    return breakouts
```

**Edge Cases**:
1. **Gap opening already through pivot**: No breakout detected (correct - gap filter handles this)
2. **Re-breaks**: If price reverses and breaks again, each is a separate breakout
3. **Intrabar whipsaws**: Using 1-min close, not tick data (matches backtester)

### Step 2: Classify Breakout Outcome

**Input**: Breakout event, subsequent bars, target, stop
**Output**: Outcome classification

**Algorithm**:
```python
def classify_outcome(self, bars, breakout, target1, stop_level):
    """
    Analyze what happened after breakout

    Rules:
    - WINNER: Price reached target1 (for LONG: high >= target1)
    - STOPPED_OUT: Price hit stop within 5 minutes
    - FALSE_BREAKOUT: Price reversed immediately (max gain < 0.1%)
    - CHOPPY: Price stalled with no progress (max gain < 0.3%, duration > 8 min)
    - RUNNER: Made progress but didn't hit target (max gain >= 0.5%)

    Returns:
        Outcome dict with classification and metrics
    """
    start_idx = breakout['bar_index']
    entry_price = breakout['price']
    side = breakout['type']

    max_gain = 0.0
    max_loss = 0.0
    hit_target = False
    hit_stop = False
    time_to_target = None
    time_to_stop = None

    # Analyze next 30 bars (30 minutes)
    analyze_bars = min(30, len(bars) - start_idx - 1)

    for i in range(1, analyze_bars + 1):
        bar = bars[start_idx + i]
        minutes_elapsed = i

        if side == 'LONG':
            # Calculate gain/loss for LONG
            gain = (bar['high'] - entry_price) / entry_price
            loss = (bar['low'] - entry_price) / entry_price

            max_gain = max(max_gain, gain)
            max_loss = min(max_loss, loss)

            # Check target1 hit
            if bar['high'] >= target1 and not hit_target:
                hit_target = True
                time_to_target = minutes_elapsed

            # Check stop hit
            if bar['low'] <= stop_level and not hit_stop:
                hit_stop = True
                time_to_stop = minutes_elapsed

        else:  # SHORT
            # Calculate gain/loss for SHORT
            gain = (entry_price - bar['low']) / entry_price
            loss = (entry_price - bar['high']) / entry_price

            max_gain = max(max_gain, gain)
            max_loss = min(max_loss, loss)

            # Check target1 hit
            if bar['low'] <= target1 and not hit_target:
                hit_target = True
                time_to_target = minutes_elapsed

            # Check stop hit
            if bar['high'] >= stop_level and not hit_stop:
                hit_stop = True
                time_to_stop = minutes_elapsed

    # ========================================
    # UPDATED (Oct 25, 2025): NEW CHECKPOINT-BASED CLASSIFICATION
    # ========================================
    # Calculate profit-taking checkpoints (every 25% toward target1)
    if side == 'LONG':
        distance = target1 - entry_price
    else:  # SHORT
        distance = entry_price - target1

    checkpoints = {
        '25%': entry_price + (distance * 0.25) if side == 'LONG' else entry_price - (distance * 0.25),
        '50%': entry_price + (distance * 0.50) if side == 'LONG' else entry_price - (distance * 0.50),
        '75%': entry_price + (distance * 0.75) if side == 'LONG' else entry_price - (distance * 0.75),
        '100%': target1
    }

    # Re-analyze to find which checkpoints were hit
    checkpoints_hit = {'25%': False, '50%': False, '75%': False, '100%': False}
    for i in range(1, len(bars) - start_idx):
        bar = bars[start_idx + i]
        if side == 'LONG':
            if bar['high'] >= checkpoints['25%']:
                checkpoints_hit['25%'] = True
            if bar['high'] >= checkpoints['50%']:
                checkpoints_hit['50%'] = True
            if bar['high'] >= checkpoints['75%']:
                checkpoints_hit['75%'] = True
            if bar['high'] >= checkpoints['100%']:
                checkpoints_hit['100%'] = True
        else:
            if bar['low'] <= checkpoints['25%']:
                checkpoints_hit['25%'] = True
            if bar['low'] <= checkpoints['50%']:
                checkpoints_hit['50%'] = True
            if bar['low'] <= checkpoints['75%']:
                checkpoints_hit['75%'] = True
            if bar['low'] <= checkpoints['100%']:
                checkpoints_hit['100%'] = True

    # Calculate star rating (1-5 stars based on checkpoints)
    num_checkpoints = sum(checkpoints_hit.values())
    if num_checkpoints == 4:
        star_rating = 5  # ⭐⭐⭐⭐⭐ Hit target1
    elif num_checkpoints == 3:
        star_rating = 4  # ⭐⭐⭐⭐ Hit 75%
    elif num_checkpoints == 2:
        star_rating = 3  # ⭐⭐⭐ Hit 50%
    elif num_checkpoints == 1:
        star_rating = 2  # ⭐⭐ Hit 25%
    elif max_gain > 0:
        star_rating = 1  # ⭐ Positive but no checkpoints
    else:
        star_rating = 0  # No progress

    # Classify outcome based on checkpoints and stop
    if checkpoints_hit['100%']:
        classification = 'WINNER'  # Hit target1
    elif hit_stop:
        classification = 'STOPPED_OUT'
    elif max_gain < 0.001:  # Less than 0.1% gain
        classification = 'FALSE_BREAKOUT'
    elif max_gain < 0.003:  # Less than 0.3% gain
        classification = 'CHOPPY'
    elif any(checkpoints_hit.values()):
        classification = 'WINNER'  # Hit at least one checkpoint = partial winner
    elif max_gain >= 0.005:  # At least 0.5% gain
        classification = 'RUNNER'
    else:
        classification = 'UNCLEAR'

    # Check for early exit (stopped out but checkpoints were eventually hit)
    stopped_out_early = (hit_stop and any(checkpoints_hit.values()))

    return {
        'classification': classification,
        'star_rating': star_rating,  # NEW: 0-5 stars
        'max_gain_pct': max_gain * 100,
        'max_loss_pct': max_loss * 100,
        'hit_target': hit_target,
        'hit_stop': hit_stop,
        'time_to_target': time_to_target,
        'time_to_stop': time_to_stop,
        'stopped_out_early': stopped_out_early,
        'checkpoints': checkpoints,  # NEW: Checkpoint prices
        'checkpoints_hit': checkpoints_hit,  # NEW: Which checkpoints hit
        'num_checkpoints_hit': num_checkpoints  # NEW: Count
    }
```

**Classification Thresholds** (configurable):
```python
THRESHOLDS = {
    'stopped_out_minutes': 5,      # Quick stop = stopped out
    'false_breakout_gain': 0.001,  # 0.1% = false breakout
    'choppy_gain': 0.003,          # 0.3% = choppy
    'runner_gain': 0.005           # 0.5% = runner
}
```

### Step 3: Match to Entry Decision Log

**Input**: Breakout event, entry decision log
**Output**: Matching log entry (or None)

**Algorithm**:
```python
def find_matching_log_entry(self, symbol, timestamp, side):
    """
    Find matching entry attempt in log

    Matching Rules:
    - Same symbol
    - Same side (LONG/SHORT)
    - Timestamp within ±60 seconds (1-min bar tolerance)

    Returns:
        Matching attempt dict or None
    """
    breakout_time = datetime.fromisoformat(timestamp)

    for attempt in self.entry_log['attempts']:
        if attempt['symbol'] != symbol:
            continue

        if attempt['side'] != side:
            continue

        # Parse log timestamp
        log_time = datetime.fromisoformat(attempt['timestamp'].replace('Z', '+00:00'))

        # Check if within tolerance (60 seconds)
        time_diff = abs((breakout_time - log_time).total_seconds())

        if time_diff <= 60:
            return attempt

    return None
```

**Edge Cases**:
1. **Multiple breakouts same minute**: Match by closest timestamp
2. **No match found**: Breakout not detected (bug)
3. **Multiple matches**: Take first match (shouldn't happen with max 2 attempts)

### Step 4: Validate Decision

**Input**: Breakout outcome, our decision
**Output**: Validation result

**Algorithm**:
```python
def validate_decision(self, decision, outcome_data, reason, filters):
    """
    Validate if our decision was correct

    Args:
        decision: 'ENTERED', 'BLOCKED', or 'MISSED'
        outcome_data: Dict with classification and metrics (from classify_outcome)
        reason: Why we made this decision
        filters: Filter results from entry log

    Decision Matrix:

    ENTERED + WINNER = ✅ GOOD_ENTRY
    ENTERED + STOPPED_OUT (but WAS winner) = ⚠️ EARLY_EXIT (stop too tight)
    ENTERED + STOPPED_OUT (truly loser) = ⚠️ BAD_ENTRY
    ENTERED + FALSE_BREAKOUT/CHOPPY = ⚠️ BAD_ENTRY
    BLOCKED + WINNER = ⚠️ MISSED_WINNER
    BLOCKED + STOPPED_OUT/FALSE_BREAKOUT/CHOPPY = ✅ GOOD_BLOCK
    MISSED + WINNER = ⚠️⚠️ CRITICAL_MISS (bug)
    MISSED + other = 🟡 OK (no harm)

    Returns:
        Validation dict
    """
    outcome = outcome_data['classification']

    if decision == 'ENTERED':
        if outcome == 'WINNER':
            return {
                'result': 'GOOD_ENTRY',
                'emoji': '✅',
                'analysis': 'Correctly entered a winning breakout',
                'impact': 'Profit captured',
                'action': None
            }
        elif outcome == 'STOPPED_OUT':
            # Check if this was an early exit (stopped out but WAS a winner)
            if outcome_data.get('stopped_out_early'):
                return {
                    'result': 'EARLY_EXIT',
                    'emoji': '⚠️',
                    'analysis': 'Got stopped out but target was eventually hit',
                    'impact': 'Missed profit due to tight stop',
                    'action': 'Consider widening stop or trailing stop strategy'
                }
            else:
                # Truly a bad breakout that stopped out
                blocking_filter = self.find_responsible_filter(filters, outcome)
                return {
                    'result': 'BAD_ENTRY',
                    'emoji': '⚠️',
                    'analysis': f'Entered a {outcome} - filters failed',
                    'impact': 'Loss incurred',
                    'action': f'Review {blocking_filter} filter'
                }
        elif outcome == 'FALSE_BREAKOUT':
            # Find which filter should have blocked
            blocking_filter = self.find_responsible_filter(filters, outcome)
            return {
                'result': 'BAD_ENTRY',
                'emoji': '⚠️',
                'analysis': f'Entered a {outcome} - filters failed',
                'impact': 'Loss incurred',
                'action': f'Review {blocking_filter} filter'
            }
        elif outcome == 'CHOPPY':
            return {
                'result': 'BAD_ENTRY',
                'emoji': '⚠️',
                'analysis': 'Entered choppy breakout (8-min rule)',
                'impact': 'Capital tied up',
                'action': 'Tighten choppy filter'
            }
        else:
            return {
                'result': 'NEUTRAL',
                'emoji': '🟡',
                'analysis': f'Outcome unclear: {outcome}',
                'impact': 'Monitor',
                'action': None
            }

    elif decision == 'BLOCKED':
        if outcome == 'WINNER':
            # Find which filter blocked
            blocking_filter = self.find_blocking_filter(filters)
            return {
                'result': 'MISSED_WINNER',
                'emoji': '⚠️',
                'analysis': f'Blocked a winning breakout',
                'impact': 'Opportunity lost',
                'action': f'Loosen {blocking_filter} filter'
            }
        elif outcome in ['STOPPED_OUT', 'FALSE_BREAKOUT', 'CHOPPY']:
            blocking_filter = self.find_blocking_filter(filters)
            return {
                'result': 'GOOD_BLOCK',
                'emoji': '✅',
                'analysis': f'Correctly blocked {outcome}',
                'impact': 'Loss avoided',
                'action': f'Keep {blocking_filter} filter'
            }
        else:
            return {
                'result': 'NEUTRAL',
                'emoji': '🟡',
                'analysis': f'Blocked {outcome}',
                'impact': 'Monitor',
                'action': None
            }

    else:  # MISSED_DETECTION
        if outcome == 'WINNER':
            return {
                'result': 'CRITICAL_MISS',
                'emoji': '⚠️⚠️',
                'analysis': 'Breakout not detected - BUG!',
                'impact': 'Major opportunity lost',
                'action': 'Fix detection logic'
            }
        else:
            return {
                'result': 'MISSED_OK',
                'emoji': '🟡',
                'analysis': f'Breakout not detected, but was {outcome}',
                'impact': 'No harm',
                'action': 'Monitor detection coverage'
            }

def find_blocking_filter(self, filters):
    """Find which filter blocked the entry"""
    for filter_name, filter_data in filters.items():
        if isinstance(filter_data, dict) and filter_data.get('result') == 'BLOCK':
            return filter_name
    return 'unknown_filter'

def find_responsible_filter(self, filters, outcome):
    """Find which filter SHOULD have blocked"""
    if outcome == 'CHOPPY':
        return 'choppy_filter'
    elif outcome == 'FALSE_BREAKOUT':
        return 'room_to_run_filter or cvd_filter'
    elif outcome == 'STOPPED_OUT':
        return 'cvd_filter or stochastic_filter'
    return 'unknown'
```

---

## Output Requirements

### 1. Per-Stock Report (Console)

```
========================================================================
NVDA - Oct 21, 2025
========================================================================
Resistance: $182.50 | Support: $180.00 | Target1: $184.14

Analyzing 390 bars (9:30 - 16:00)...

------------------------------------------------------------------------
BREAKOUT #1 - LONG @ 09:47:00 ($183.03)
------------------------------------------------------------------------
OUTCOME:
  Classification: FALSE_BREAKOUT
  Max gain: +0.45%
  Max loss: -0.12%
  ✗ Hit stop in 4.5 min

OUR DECISION:
  Logged: YES
  Decision: BLOCKED
  Reason: room_to_run_filter - only 0.61% to target
  Blocking filter: room_to_run

VALIDATION:
  Result: ✅ GOOD_BLOCK
  Analysis: Correctly blocked FALSE_BREAKOUT
  Impact: Loss avoided (~$110)
  Action: Keep room_to_run filter

------------------------------------------------------------------------
BREAKOUT #2 - SHORT @ 10:55:12 ($179.85)
------------------------------------------------------------------------
OUTCOME:
  Classification: WINNER
  Max gain: +1.31%
  ✓ Hit target in 20.3 min

OUR DECISION:
  Logged: NO
  ⚠️⚠️ MISSED DETECTION - Breakout not logged!

VALIDATION:
  Result: ⚠️⚠️ CRITICAL_MISS
  Analysis: Breakout not detected - BUG!
  Impact: Major opportunity lost (~$327)
  Action: Fix detection logic (support break not detected)

------------------------------------------------------------------------
STOCK SUMMARY
------------------------------------------------------------------------
Total breakouts: 2
  ✅ Good decisions: 1
  ⚠️ Bad decisions: 0
  ⚠️ Missed detections: 1

Net impact: -$217 (lost opportunity)
```

### 2. Daily Summary Report (Console)

```
========================================================================
VALIDATION SUMMARY - Oct 21, 2025
========================================================================

BREAKOUT ANALYSIS:
  Total breakouts: 127 (across 53 stocks)
  - LONG breakouts: 89
  - SHORT breakouts: 38

DECISION QUALITY:
  ✅ Good entries: 4 (entered winners)
  ✅ Good blocks: 78 (blocked losers)
  ⚠️ Bad entries: 2 (entered losers)
  ⚠️ Missed winners: 5 (blocked winners)
  ⚠️ Missed detections: 3 (never logged)

FILTER EFFECTIVENESS:
  CVD Filter:
    Total blocks: 32
    - Blocked winners: 3 (⚠️ too restrictive)
    - Blocked losers: 29 (✅ good)
    Net impact: +$3,950 (saved $4,350, lost $400)
    Recommendation: Consider loosening threshold

  Choppy Filter:
    Total blocks: 18
    - Blocked winners: 1 (minor)
    - Blocked losers: 17 (✅ excellent)
    Net impact: +$2,450
    Recommendation: Keep current settings

  Room-to-Run Filter:
    Total blocks: 15
    - Blocked winners: 0 (✅ perfect)
    - Blocked losers: 15 (✅ perfect)
    Net impact: +$2,250
    Recommendation: Keep current settings

BUGS FOUND:
  1. Support break detection missing (3 instances)
     - Stocks: NVDA, AMD, TSLA
     - Lost opportunity: $927
     - Action: Fix state machine support break logic

  2. Choppy filter passed incorrectly (2 instances)
     - Stocks: COIN, HOOD
     - Losses incurred: $145
     - Action: Review choppy filter calculation

NET IMPACT:
  Avoided losses: $8,650
  Missed winners: $1,327
  Actual losses: $145
  Net benefit: +$7,178

RECOMMENDATIONS:
  1. 🔧 FIX: Support break detection (critical)
  2. 🔧 FIX: Choppy filter calculation
  3. 🔍 REVIEW: CVD filter threshold (blocked 3 winners)
  4. ✅ KEEP: Room-to-run filter (perfect record)
  5. ✅ KEEP: Choppy filter settings
```

### 3. JSON Output (Machine-Readable)

**File**: `validation/reports/validation_results_20251021.json`

```json
{
  "date": "2025-10-21",
  "total_breakouts": 127,
  "long_breakouts": 89,
  "short_breakouts": 38,

  "decision_quality": {
    "good_entries": 4,
    "good_blocks": 78,
    "bad_entries": 2,
    "missed_winners": 5,
    "missed_detections": 3
  },

  "filter_effectiveness": {
    "cvd_filter": {
      "total_blocks": 32,
      "blocked_winners": 3,
      "blocked_losers": 29,
      "net_impact_dollars": 3950,
      "recommendation": "Consider loosening"
    },
    "choppy_filter": {
      "total_blocks": 18,
      "blocked_winners": 1,
      "blocked_losers": 17,
      "net_impact_dollars": 2450,
      "recommendation": "Keep settings"
    }
  },

  "bugs": [
    {
      "type": "missed_detection",
      "description": "Support break detection missing",
      "count": 3,
      "impact_dollars": 927,
      "action": "Fix state machine"
    }
  ],

  "breakouts": [
    {
      "symbol": "NVDA",
      "timestamp": "2025-10-21T09:47:00",
      "type": "LONG",
      "price": 183.03,
      "outcome": "FALSE_BREAKOUT",
      "max_gain_pct": 0.45,
      "max_loss_pct": -0.12,
      "our_decision": "BLOCKED",
      "reason": "room_to_run_filter",
      "validation": "GOOD_BLOCK",
      "impact_dollars": 110
    }
  ],

  "net_impact": {
    "avoided_losses": 8650,
    "missed_winners": 1327,
    "actual_losses": 145,
    "net_benefit": 7178
  }
}
```

---

## Implementation Phases

### Phase 1: Validator Core (3-4 hours)
1. Create `validate_market_outcomes.py`
2. Implement `load_saved_bars()` - loads from `backtest/data/`
3. Implement `identify_breakouts()`
4. Implement `classify_outcome()` - with `stopped_out_early` flag
5. Test: Validate single stock (NVDA)

### Phase 2: Matching & Validation (2-3 hours)
1. Implement `find_matching_log_entry()`
2. Implement `validate_decision()` - handles EARLY_EXIT case
3. Implement filter analysis
4. Test: Complete validation for NVDA

### Phase 3: Reporting (2-3 hours)
1. Implement per-stock console report
2. Implement daily summary report
3. Implement JSON output
4. Test: Generate all reports

### Phase 4: Full Test (1-2 hours)
1. Ensure backtest ran for Oct 21 (bars already cached)
2. Run validator on all stocks
3. Review results
4. Fix any bugs found

**Total Estimated Time**: 8-12 hours

**Note**: No backtester changes needed - bars are already cached at `backtest/data/SYMBOL_YYYYMMDD_1min.json`

---

## Final Specifications (APPROVED - Oct 25, 2025)

### 1. Target Selection & Winner Rating ⭐⭐⭐

**Approach**: Profit-taking checkpoints every 25% toward target1 with 5-star rating system.

**Logic**:
- Calculate distance to target1: `distance = target1 - entry_price`
- Create checkpoints every 25% of distance: `checkpoint = entry_price + (distance × 0.25 × n)` where n = 1,2,3,4
- Track how many checkpoints price reached
- **Rating System**:
  - 5 stars ⭐⭐⭐⭐⭐: Reached target1 (100%)
  - 4 stars ⭐⭐⭐⭐: Reached 75% checkpoint
  - 3 stars ⭐⭐⭐: Reached 50% checkpoint
  - 2 stars ⭐⭐: Reached 25% checkpoint
  - 1 star ⭐: Reached entry but no checkpoints

**Example**:
```python
# LONG entry at $100, target1 at $110
# Distance: $10
# Checkpoints:
#   25%: $102.50 (1 star)
#   50%: $105.00 (2 stars)
#   75%: $107.50 (3 stars)
#  100%: $110.00 (4 stars)
#  Hit target1: 5 stars

# If price reached $106.50:
# - Passed 25% checkpoint ✓
# - Passed 50% checkpoint ✓
# - Did NOT pass 75% checkpoint ✗
# Rating: ⭐⭐ (2 stars)
```

### 2. Stop Level

**Approach**: Use backtester's actual stop loss logic from trading strategy.

**Implementation**:
- Load stop loss configuration from `trader/config/trader_config.yaml`
- Use same stop calculation as PS60Strategy class
- Do NOT hardcode stop at resistance/support
- For LONG: Typically `entry_price - (entry_price × stop_distance_pct)`
- For SHORT: Typically `entry_price + (entry_price × stop_distance_pct)`

**Note**: This requires importing or replicating the exact stop logic from `trader/strategy/ps60_strategy.py`.

### 3. Time Window

**Approach**: Watch until end of day session close (16:00 ET).

**Implementation**:
- Analyze ALL bars from breakout until 16:00 ET
- Do NOT limit to 30 minutes
- Track when outcomes occur (time to checkpoint, time to stop, etc.)
- Trade is considered closed at EOD if still open

**Example**:
```python
# Breakout at 09:47 AM
# Analyze bars from 09:47 AM through 16:00 PM
# Total analysis window: ~370 minutes (6+ hours)
# Track exact time when each checkpoint/stop hit
```

### 4. $ Impact Estimation

**Approach**: Use profit-taking checkpoints (from #1 above), but marked as "not important".

**Implementation**:
- Calculate theoretical profit at each checkpoint
- Use standard position size (e.g., 1000 shares or 1% risk)
- Estimate partial profit-taking (25% at each checkpoint)
- **Priority**: LOW (focus on classification accuracy first)

### 5. Re-run Behavior

**Approach**: Always overwrite, no duplicates.

**Implementation**:
```python
# Output files:
output_file = f"reports/validation_results_{date}.json"

# Always overwrite:
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)

# Include generation timestamp INSIDE JSON:
{
  "generated_at": "2025-10-25T15:42:30",
  "validation_date": "2025-10-21",
  ...
}
```

### 6. Missing Bars Handling

**Approach**: Download missing bars and report as CRITICAL ERROR.

**Implementation**:
```python
def load_saved_bars(self, symbol, date):
    """
    Load cached 1-min bars, download if missing

    Missing bars = CRITICAL ERROR (backtest should have cached all bars)
    """
    bars_file = f"backtest/data/{symbol}_{date}_1min.json"

    if not bars_file.exists():
        # CRITICAL ERROR - backtest should have saved this
        logger.critical(f"CRITICAL ERROR: Bars missing for {symbol}")
        logger.critical(f"  Expected: {bars_file}")
        logger.critical(f"  This indicates backtest did not run properly!")

        # Attempt to download
        logger.info(f"  Attempting emergency download...")
        bars = self.download_bars_from_ibkr(symbol, date)

        # Save for future use
        self.save_bars(bars, bars_file)

        logger.warning(f"  ⚠️ Downloaded and cached {len(bars)} bars")
        logger.warning(f"  ⚠️ But backtest should have done this!")

        return bars

    # Load normally
    with open(bars_file) as f:
        return json.load(f)
```

**Critical Error Report**:
```
========================================
⚠️⚠️ CRITICAL ERRORS DETECTED
========================================
Missing bars for 3 stocks:
  1. HOOD - backtest did not cache bars
  2. SNAP - backtest did not cache bars
  3. PATH - backtest did not cache bars

ACTION REQUIRED:
  Re-run backtest for 2025-10-21
  Ensure all stocks have cached bars
  Validate backtest completed successfully
========================================
```

---

## Success Criteria

### Validation is successful when:
1. ✅ All backtested stocks have saved bars
2. ✅ All breakouts identified correctly
3. ✅ All outcomes classified accurately
4. ✅ All matches found (no false negatives)
5. ✅ Bugs identified with clear action items
6. ✅ Filter effectiveness quantified in $$
7. ✅ Reports generated in 3 formats (console, summary, JSON)

---

## Next Steps

1. **Review these requirements** - Ensure nothing missing
2. **Answer open questions** - Clarify ambiguities
3. **Approve implementation plan** - Phase-by-phase approach
4. **Start Phase 1** - Modify backtester to save bars

**Ready for your feedback!** 🚀
