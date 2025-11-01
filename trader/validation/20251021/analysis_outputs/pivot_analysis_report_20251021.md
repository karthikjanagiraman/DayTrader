# Comprehensive Pivot Behavior & Strategy Analysis Report

**Date**: 2025-10-21
**Total Breakouts Analyzed**: 7

## Summary Statistics

- **Strategy Would Enter**: 3/7 (42.9%)
- **Strategy Would Block**: 4/7 (57.1%)

### Decision Accuracy

- ✅ **Correct Entries**: 1
- ❌ **Bad Entries**: 2
- ✅ **Correct Blocks**: 3
- ❌ **Missed Winners**: 1
- **Overall Accuracy**: 57.1%

## Filter Effectiveness

| Filter | Blocks | Percentage |
|--------|--------|------------|
| volume | 2 | 28.6% |
| timing_filter | 2 | 28.6% |
| cvd | 1 | 14.3% |

## Detailed Breakout Analysis

### ✅ SMCI SHORT

- **Decision**: BLOCK
- **Outcome**: STOPPED_OUT
- **Classification**: CORRECT_BLOCK
- **Entry Path**: PULLBACK_RETEST
- **Blocking Filters**: cvd, volume
- **Max Favorable Excursion**: 1.19%
- **Max Adverse Excursion**: 1.32%

### ❌ SOFI LONG

- **Decision**: ENTER
- **Outcome**: STOPPED_OUT
- **Classification**: BAD_ENTRY
- **Entry Path**: MOMENTUM_BREAKOUT
- **Blocking Filters**: None
- **Max Favorable Excursion**: 0.28%
- **Max Adverse Excursion**: 1.93%

### ❌ AMD SHORT

- **Decision**: ENTER
- **Outcome**: STOPPED_OUT
- **Classification**: BAD_ENTRY
- **Entry Path**: SUSTAINED_BREAK
- **Blocking Filters**: None
- **Max Favorable Excursion**: 0.07%
- **Max Adverse Excursion**: 2.86%

### ✅ HOOD SHORT

- **Decision**: BLOCK
- **Outcome**: STOPPED_OUT
- **Classification**: CORRECT_BLOCK
- **Entry Path**: PULLBACK_RETEST
- **Blocking Filters**: volume
- **Max Favorable Excursion**: 0.96%
- **Max Adverse Excursion**: 1.74%

### ✅ PATH SHORT

- **Decision**: BLOCK
- **Outcome**: STOPPED_OUT
- **Classification**: CORRECT_BLOCK
- **Entry Path**: SUSTAINED_BREAK
- **Blocking Filters**: timing_filter
- **Max Favorable Excursion**: 1.22%
- **Max Adverse Excursion**: 6.28%

### ✅ PATH LONG

- **Decision**: ENTER
- **Outcome**: WINNER
- **Classification**: CORRECT_ENTRY
- **Entry Path**: SUSTAINED_BREAK
- **Blocking Filters**: None
- **Max Favorable Excursion**: 2.66%
- **Max Adverse Excursion**: 0.31%

### ❌ NVDA SHORT

- **Decision**: BLOCK
- **Outcome**: WINNER
- **Classification**: MISSED_WINNER
- **Entry Path**: SUSTAINED_BREAK
- **Blocking Filters**: timing_filter
- **Max Favorable Excursion**: 0.94%
- **Max Adverse Excursion**: 0.64%

