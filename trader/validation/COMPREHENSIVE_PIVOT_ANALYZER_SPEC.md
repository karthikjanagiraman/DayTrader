# Comprehensive Pivot Behavior & Strategy Analysis Specification

**Version**: 1.0
**Date**: October 30, 2025
**Purpose**: Complete specification for analyzing pivot behavior with full PS60 strategy simulation

---

## 1. Overview

This analyzer provides complete analysis of scanner-identified pivots, simulating the entire PS60 trading strategy decision process to understand:
- Which breakouts would be entered vs blocked
- Why specific filters pass or fail
- How to optimize filter thresholds
- Complete state machine progression
- Multi-bar confirmation sequences
- Market context impact

---

## 2. Data Requirements

### 2.1 Primary Data Sources

#### Scanner Results (`scanner_results_YYYYMMDD.json`)
```json
{
  "symbol": "NVDA",
  "close": 185.50,
  "resistance": 186.20,
  "support": 184.00,
  "target1": 188.50,
  "target2": 190.00,
  "target3": 192.00,
  "downside1": 182.00,
  "downside2": 180.00,
  "score": 72,
  "setup": "Momentum breakout",
  "risk_reward": 3.2,
  "pivot_tests": 5,
  "atr_pct": 2.1
}
```

#### Historical Bars (1-minute resolution)
- OHLCV data for full trading day
- Cached locally or fetched from IBKR
- Required: 390 bars (6.5 hour trading day)

#### Historical Bars (5-second resolution) - Optional
- For accurate CVD calculation
- If available, provides better buy/sell volume estimation

#### Configuration (`trader_config.yaml`)
- All filter thresholds
- Entry window times
- Risk parameters
- State machine settings

### 2.2 Market Context Data

#### SPY Data
- 1-minute bars for market direction
- Calculate trend and strength
- Compare timing with breakouts

#### VIX Data (Optional)
- Volatility regime classification
- Risk-on vs risk-off environment

#### Opening Prices
- For gap analysis
- Compare open vs previous close
- Detect gap-through-pivot scenarios

---

## 3. Analysis Components

### 3.1 Breakout Detection

#### Criteria
- **LONG**: Close > resistance
- **SHORT**: Close < support
- **Time**: First occurrence after market open

#### Data Collected
```python
breakout = {
    'symbol': str,
    'direction': 'LONG' | 'SHORT',
    'pivot_price': float,
    'breakout_time': datetime,
    'breakout_bar_idx': int,
    'breakout_price': float,
    'bars_since_open': int,
    'opening_price': float,
    'previous_close': float
}
```

### 3.2 Gap Analysis

#### Types
1. **No Gap**: Open within ±0.5% of pivot
2. **Small Gap**: 0.5-1.0% through pivot
3. **Large Gap**: >1.0% through pivot
4. **Gap Away**: Gapped opposite direction

#### Calculations
```python
gap_analysis = {
    'has_gap': bool,
    'gap_type': str,
    'gap_size_pct': float,
    'gap_through_pivot': bool,
    'room_after_gap': float,
    'gap_invalidates_setup': bool
}
```

### 3.3 Entry Window Validation

#### Time Filters
- **No Entry Before**: 9:45 AM (15 min after open)
- **No Entry After**: 3:00 PM (60 min before close)
- **Optimal Windows**: 9:45-10:30, 14:00-15:00

```python
time_validation = {
    'in_entry_window': bool,
    'minutes_from_open': int,
    'minutes_to_close': int,
    'time_zone': 'EARLY' | 'MID' | 'LATE',
    'optimal_time': bool
}
```

### 3.4 State Machine Simulation

#### States
```python
STATES = [
    'INIT',
    'MONITORING_BREAKOUT',
    'WAITING_FOR_CANDLE_CLOSE',
    'MOMENTUM_BREAKOUT_DETECTED',
    'WEAK_BREAKOUT_TRACKING',
    'PULLBACK_TRACKING',
    'WAITING_FOR_PULLBACK',
    'CVD_MONITORING',
    'SUSTAINED_BREAK_TRACKING',
    'ENTERING_POSITION',
    'POSITION_ACTIVE'
]
```

#### Tracking
```python
state_progression = {
    'states_visited': [str],
    'bars_in_each_state': [int],
    'state_transitions': int,
    'final_state': str,
    'total_bars_to_decision': int,
    'decision_bar_idx': int
}
```

### 3.5 Entry Path Determination

#### Path Types
1. **MOMENTUM_BREAKOUT**: Immediate strong break
2. **PULLBACK_RETEST**: Weak break, wait for pullback
3. **SUSTAINED_BREAK**: Holds above pivot for time
4. **CVD_MONITORING**: Volume delta imbalance

#### Criteria
```python
entry_paths = {
    'MOMENTUM_BREAKOUT': {
        'volume_threshold': 2.0,
        'candle_size_pct': 1.5,
        'atr_multiplier': 2.0
    },
    'PULLBACK_RETEST': {
        'pullback_zone_pct': 0.3,
        'retest_volume': 1.2
    },
    'SUSTAINED_BREAK': {
        'min_bars_above': 2,
        'min_volume': 0.8
    },
    'CVD_MONITORING': {
        'imbalance_threshold': 10.0,
        'confirmation_bars': 3
    }
}
```

### 3.6 Filter Calculations

#### A. Choppy Market Filter
```python
choppy_filter = {
    'enabled': bool,
    'lookback_bars': 60,
    'range_pct': float,  # (high - low) / low * 100
    'atr_ratio': float,  # range / atr
    'threshold': 0.5,    # % range minimum
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

#### B. Room-to-Run Filter
```python
room_to_run = {
    'enabled': bool,
    'target_used': 'target1' | 'target2' | 'target3',
    'room_pct': float,
    'threshold': 1.5,
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

#### C. Stochastic Oscillator
```python
stochastic = {
    'enabled': bool,
    'period': 14,
    'k_value': float,
    'd_value': float,
    'overbought': 80,
    'oversold': 20,
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

#### D. Cumulative Volume Delta (CVD)
```python
cvd_analysis = {
    'enabled': bool,
    'buy_volume': float,
    'sell_volume': float,
    'net_delta': float,
    'imbalance_pct': float,
    'trend': 'BULLISH' | 'BEARISH' | 'NEUTRAL',
    'alignment': bool,  # Does CVD align with direction?
    'threshold': 10.0,
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

#### E. Volume Confirmation
```python
volume_analysis = {
    'enabled': bool,
    'current_volume': int,
    'avg_volume_20': float,
    'volume_ratio': float,
    'surge_detected': bool,
    'threshold': 1.0,
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

#### F. Directional Volume Filter
```python
directional_volume = {
    'enabled': bool,
    'up_volume': float,
    'down_volume': float,
    'ratio': float,
    'alignment': bool,
    'threshold': 1.5,
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

#### G. Index ETF Filter
```python
index_filter = {
    'is_index': bool,
    'avoid_index_shorts': bool,
    'result': 'PASS' | 'BLOCK',
    'reason': str
}
```

### 3.7 Attempt Tracking

```python
attempt_tracking = {
    'attempt_number': int,
    'max_attempts': 2,
    'previous_attempts': [
        {
            'time': datetime,
            'blocked_by': str,
            'filters_failed': [str]
        }
    ],
    'cooldown_period': 5,  # minutes between attempts
    'attempt_allowed': bool
}
```

### 3.8 Multi-Bar Confirmation Sequence

```python
confirmation_sequence = [
    {
        'bar_idx': int,
        'time': datetime,
        'state': str,
        'price': float,
        'volume': int,
        'action': str,  # 'MONITORING', 'WAITING', 'CHECKING', etc
        'filters_checked': [str],
        'decision': str,  # 'CONTINUE', 'BLOCK', 'ENTER'
        'reason': str
    },
    # ... for each bar in sequence
]
```

### 3.9 Market Context Analysis

#### SPY Analysis
```python
market_context = {
    'spy_trend': 'UP' | 'DOWN' | 'FLAT',
    'spy_strength': float,  # % move
    'spy_volume': 'HIGH' | 'NORMAL' | 'LOW',
    'correlation': float,  # with our symbol
    'market_regime': 'TRENDING' | 'CHOPPY' | 'REVERSAL'
}
```

#### Volatility Context
```python
volatility = {
    'vix_level': float,
    'vix_trend': 'RISING' | 'FALLING' | 'STABLE',
    'risk_regime': 'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME',
    'adjustment_factor': float  # for filter thresholds
}
```

### 3.10 Entry Quality Scoring

```python
entry_quality = {
    'breakout_strength': float,  # % above/below pivot
    'volume_surge': float,       # multiple of average
    'candle_quality': {
        'body_pct': float,       # body/range ratio
        'close_position': float,  # where in range
        'wick_analysis': str     # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    },
    'momentum_score': float,     # 0-100
    'quality_grade': 'A' | 'B' | 'C' | 'D' | 'F'
}
```

### 3.11 Scanner Context Integration

```python
scanner_context = {
    'scanner_score': int,
    'setup_type': str,
    'pivot_test_count': int,
    'days_since_last_test': int,
    'risk_reward_ratio': float,
    'relative_volume': float,
    'pattern_name': str
}
```

### 3.12 Decision Engine

```python
strategy_decision = {
    'final_decision': 'ENTER' | 'BLOCK',
    'confidence_score': float,  # 0-100
    'primary_reason': str,
    'filters_passed': [str],
    'filters_failed': [str],
    'blocking_filters': [str],  # Critical ones that caused block
    'entry_type': str,          # If entering
    'risk_assessment': 'LOW' | 'MEDIUM' | 'HIGH'
}
```

### 3.13 Outcome Tracking

```python
actual_outcome = {
    'result': 'WINNER' | 'FALSE_BREAKOUT' | 'STOPPED_OUT',
    'target1_hit': bool,
    'target2_hit': bool,
    'target3_hit': bool,
    'max_favorable_excursion': float,
    'max_adverse_excursion': float,
    'bars_to_target': int,
    'bars_to_stop': int,
    'exit_reason': str,
    'profit_loss_pct': float
}
```

### 3.14 Decision Classification

```python
decision_accuracy = {
    'classification': str,  # One of below
    'correct_decision': bool,
    'opportunity_cost': float  # $ missed or saved
}

# Classifications:
# ✅ CORRECT_ENTRY: Entered winner
# ❌ BAD_ENTRY: Entered loser
# ✅ CORRECT_BLOCK: Blocked loser
# ❌ MISSED_WINNER: Blocked winner
```

---

## 4. Complete Data Structure

### 4.1 Per-Breakout Analysis Record

```python
breakout_analysis = {
    # Identification
    'id': str,  # symbol_direction_time
    'symbol': str,
    'direction': str,
    'date': str,

    # Breakout Details
    'breakout': {...},  # Section 3.1

    # Gap Analysis
    'gap': {...},  # Section 3.2

    # Timing
    'timing': {...},  # Section 3.3

    # State Machine
    'state_machine': {...},  # Section 3.4

    # Entry Path
    'entry_path': {...},  # Section 3.5

    # All Filters
    'filters': {
        'choppy': {...},
        'room_to_run': {...},
        'stochastic': {...},
        'cvd': {...},
        'volume': {...},
        'directional_volume': {...},
        'index': {...}
    },

    # Attempts
    'attempts': {...},  # Section 3.7

    # Confirmation
    'confirmation_sequence': [...],  # Section 3.8

    # Market Context
    'market': {...},  # Section 3.9

    # Quality
    'quality': {...},  # Section 3.10

    # Scanner
    'scanner': {...},  # Section 3.11

    # Decision
    'strategy_decision': {...},  # Section 3.12

    # Outcome
    'outcome': {...},  # Section 3.13

    # Accuracy
    'accuracy': {...}  # Section 3.14
}
```

---

## 5. CSV Output Specification

### 5.1 Column Structure (80+ columns)

```csv
# Identification
symbol,direction,date,breakout_time,

# Breakout
pivot_price,breakout_price,breakout_strength_pct,

# Gap
has_gap,gap_type,gap_size_pct,gap_through_pivot,room_after_gap,

# Timing
in_entry_window,minutes_from_open,time_zone,

# State Machine
states_visited,state_transitions,final_state,bars_to_decision,

# Entry Path
entry_path_determined,path_type,path_volume_ratio,path_candle_size,

# Filters (each filter has multiple columns)
choppy_enabled,choppy_result,choppy_range_pct,choppy_threshold,choppy_reason,
room_enabled,room_result,room_pct,room_threshold,room_target,room_reason,
stoch_enabled,stoch_result,stoch_k,stoch_d,stoch_threshold,stoch_reason,
cvd_enabled,cvd_result,cvd_imbalance,cvd_trend,cvd_alignment,cvd_reason,
vol_enabled,vol_result,vol_ratio,vol_threshold,vol_reason,
dir_vol_enabled,dir_vol_result,dir_vol_ratio,dir_vol_alignment,dir_vol_reason,
index_filter_result,is_index_etf,

# Attempts
attempt_number,previous_blocks,attempt_allowed,

# Confirmation Sequence
confirmation_bars,sequence_summary,

# Market Context
spy_trend,spy_strength,market_regime,vix_level,risk_regime,

# Quality Scores
entry_quality_score,momentum_score,quality_grade,

# Scanner Context
scanner_score,setup_type,pivot_tests,risk_reward,

# Decision
FINAL_DECISION,confidence_score,primary_reason,filters_passed,filters_failed,blocking_filters,

# Outcome
actual_outcome,target1_hit,max_favorable_excursion,max_adverse_excursion,profit_loss_pct,

# Classification
decision_classification,correct_decision,opportunity_cost
```

---

## 6. Analysis Reports

### 6.1 Summary Statistics

```
Total Breakouts Analyzed: X
Strategy Would Enter: Y (Z%)
Strategy Would Block: A (B%)

Decision Accuracy:
- Correct Entries: X/Y
- Bad Entries: X/Y
- Correct Blocks: X/Y
- Missed Winners: X/Y
- Overall Accuracy: X%

Filter Effectiveness:
- Most Valuable: [Filter] (blocked X false breakouts)
- Most Restrictive: [Filter] (blocked Y winners)
- Optimal Balance: [Filter] (best accuracy)
```

### 6.2 Filter Performance Matrix

```
Filter          Blocks  Winners  Losers  Accuracy  Value
Choppy            15       2       13      86.7%    +$2,600
Room-to-Run       12       3        9      75.0%    +$1,200
Stochastic        18       8       10      55.6%    -$600
CVD               20       4       16      80.0%    +$2,400
Volume            25       6       19      76.0%    +$2,600
```

### 6.3 Time-Based Analysis

```
Time Window     Attempts  Entries  Winners  Win Rate
09:30-10:00        8         3        2      66.7%
10:00-11:00       12         4        1      25.0%
11:00-14:00       15         5        3      60.0%
14:00-15:30       10         6        5      83.3%
15:30-16:00        5         1        0       0.0%
```

### 6.4 State Machine Analysis

```
Average State Progression:
INIT → MONITORING (2 bars) → WAITING (1 bar) → DECISION

Most Common Failure Point:
WEAK_BREAKOUT_TRACKING → BLOCK (volume insufficient)

Success Pattern:
MOMENTUM_BREAKOUT → ENTERING (immediate, 85% win rate)
```

### 6.5 Optimization Recommendations

```
CRITICAL CHANGES:
1. Stochastic: 80 → 90 (would capture 4 more winners)
2. Volume: 1.0x → 0.75x for pullbacks (3 more winners)
3. CVD: Keep current (working well)

EXPECTED IMPROVEMENT:
Current: 65% accuracy
Optimized: 82% accuracy
P&L Impact: +$4,500/day
```

---

## 7. Implementation Requirements

### 7.1 Dependencies

```python
# Required Libraries
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import yaml

# IBKR Connection
from ib_insync import IB, Stock, util

# Technical Indicators
import talib  # or custom implementations

# Statistical Analysis
from scipy import stats
from sklearn.preprocessing import StandardScaler
```

### 7.2 Configuration Loading

```python
def load_config() -> Dict:
    """Load trader_config.yaml"""
    with open('../../config/trader_config.yaml', 'r') as f:
        return yaml.safe_load(f)
```

### 7.3 Data Caching

```python
# Cache structure
cache/
├── bars/
│   ├── SYMBOL_YYYYMMDD_1min.json
│   └── SYMBOL_YYYYMMDD_5sec.json
├── scanner/
│   └── scanner_results_YYYYMMDD.json
└── market/
    ├── SPY_YYYYMMDD_1min.json
    └── VIX_YYYYMMDD_daily.json
```

---

## 8. Performance Considerations

### 8.1 Processing Optimization

- Cache all data locally to minimize IBKR calls
- Process bars in vectorized operations where possible
- Use parallel processing for multiple symbols
- Pre-calculate indicators once, reuse for all breakouts

### 8.2 Memory Management

- Process one day at a time for large datasets
- Stream CSV output instead of holding all in memory
- Use generators for bar sequence processing

---

## 9. Validation

### 9.1 Data Validation

- Verify bar continuity (no missing minutes)
- Check for market hours only
- Validate scanner data matches bar data dates
- Ensure config values are within reasonable ranges

### 9.2 Logic Validation

- State transitions must be valid
- Filters must have all required fields
- Decisions must have supporting data
- Outcomes must be deterministic

---

## 10. Error Handling

### 10.1 Data Errors

- Missing bars: Skip symbol with warning
- Invalid scanner data: Log and continue
- Connection failures: Use cached data

### 10.2 Calculation Errors

- Division by zero: Return None with flag
- Insufficient history: Use available data
- Invalid state: Log and reset to INIT

---

## 11. Output Files

### 11.1 Primary Outputs

```
validation/
├── comprehensive_pivot_analysis_YYYYMMDD.csv  # Full data
├── pivot_analysis_report_YYYYMMDD.md         # Human-readable
├── filter_optimization_YYYYMMDD.json         # Machine-readable
└── state_machine_analysis_YYYYMMDD.json      # State patterns
```

### 11.2 Debug Outputs

```
validation/debug/
├── failed_breakouts_YYYYMMDD.json
├── missed_winners_YYYYMMDD.json
└── filter_conflicts_YYYYMMDD.json
```

---

## 12. Usage

### 12.1 Command Line Interface

```bash
python comprehensive_pivot_analyzer.py \
    --scanner ../../stockscanner/output/scanner_results_20251021.json \
    --date 2025-10-21 \
    --config ../../config/trader_config.yaml \
    --output comprehensive_pivot_analysis_20251021.csv \
    --report pivot_analysis_report_20251021.md \
    --debug  # Optional: Save debug files
```

### 12.2 Multi-Day Analysis

```bash
# Process week of data
for date in 2025-10-21 2025-10-22 2025-10-23; do
    python comprehensive_pivot_analyzer.py \
        --scanner scanner_results_${date}.json \
        --date $date
done

# Aggregate results
python aggregate_pivot_analysis.py \
    --input comprehensive_pivot_analysis_*.csv \
    --output weekly_analysis.csv
```

---

## 13. Success Metrics

### 13.1 Key Performance Indicators

1. **Decision Accuracy**: >80% target
2. **Winner Capture Rate**: >90% of actual winners
3. **False Breakout Avoidance**: >85% blocked
4. **Filter Efficiency**: <3 filters blocking same trade
5. **Processing Speed**: <30 seconds per symbol per day

### 13.2 Validation Metrics

1. **Data Completeness**: 100% of breakouts analyzed
2. **State Coverage**: All states visited in test data
3. **Filter Coverage**: All filters tested
4. **Edge Cases**: Gaps, early/late trades handled

---

## 14. Future Enhancements

### 14.1 Machine Learning Integration

- Pattern recognition for breakout quality
- Dynamic threshold optimization
- Predictive filter weighting

### 14.2 Real-Time Integration

- Live strategy validation
- Real-time filter adjustment
- Performance tracking

### 14.3 Advanced Analytics

- Correlation with market microstructure
- Order flow analysis
- Level 2 book integration

---

## 15. Appendices

### A. State Transition Diagram

```
[INIT] → [MONITORING_BREAKOUT]
           ↓
    [BREAKOUT_DETECTED]
           ↓
    [CHECK_ENTRY_PATH]
       ↙    ↓    ↘
[MOMENTUM] [PULLBACK] [SUSTAINED]
     ↓        ↓          ↓
[CHECK_FILTERS] ← ← ← ← ←
     ↓
[DECISION_POINT]
   ↙        ↘
[ENTER]   [BLOCK]
```

### B. Filter Priority Order

1. Gap Filter (can invalidate entire setup)
2. Time Filter (market hours)
3. Index Filter (avoid index shorts)
4. Choppy Filter (market condition)
5. Room-to-Run Filter (profit potential)
6. Volume Confirmation
7. Stochastic (momentum)
8. CVD (volume delta)
9. Directional Volume

### C. Quality Grading Rubric

```
Grade A: All filters pass, strong momentum, clean break
Grade B: Most filters pass, decent momentum
Grade C: Marginal pass, some concerns
Grade D: Barely passes, high risk
Grade F: Should not enter
```

---

**END OF SPECIFICATION**

Total Features: 50+
Total Data Points Per Breakout: 200+
Total CSV Columns: 80+

This specification ensures comprehensive analysis with no compromises on data or functionality.