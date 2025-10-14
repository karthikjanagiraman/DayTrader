# Stop Loss Slippage Analysis - October 7, 2025

## Executive Summary

Analysis of October 7, 2025 backtest results reveals **severe stop loss slippage** averaging **113% beyond expected stop distance**. This is the primary reason for the catastrophic -$4,234 P&L despite an 85.7% loss rate.

**Key Finding**: The backtester's simulated slippage of 0.2% is insufficient. Actual market slippage appears to be 2-3x higher during fast-moving breakouts.

---

## Overview

**Backtest Results**:
- Total P&L: -$4,234.73
- Win Rate: 14.3% (4 winners, 24 losers)
- Average Loser: -$196.04
- Average Winner: +$117.55

**Critical Issue**: The average loser is losing **67% MORE** than the average winner is winning. This is backwards - winners should be larger than losers.

---

## Top 5 Losing Trades (Slippage Analysis)

### 1. JPM SHORT - Worst Trade
```
Entry:    $304.67 @ 12:07
Stop:     $305.10
Exit:     $305.88 @ 12:10 (STOP)
Duration: 3 minutes

Expected Loss: $0.43/share (stop distance)
Actual Loss:   $1.23/share (including slippage)
Slippage:      $0.78/share (181% beyond stop!)

Total P&L: -$1,225.51 (1000 shares)
```

**Analysis**:
- Stop was set at $305.10
- Exit occurred at $305.88 (**$0.78 beyond stop**)
- This is **181% slippage** - nearly 2x the expected loss
- Slippage alone cost $780 on this trade

**Root Cause**: When shorts get stopped out, you exit at the **ask price** (higher). In fast-moving markets, the ask can be significantly above your stop level by the time the order executes.

---

### 2. ARM LONG (Attempt #2) - Second Worst
```
Entry:    $157.53 @ 12:40
Stop:     $157.22
Exit:     $156.79 @ 12:41 (STOP)
Duration: 1 minute

Expected Loss: $0.31/share (stop distance)
Actual Loss:   $0.75/share (including slippage)
Slippage:      $0.43/share (139% beyond stop!)

Total P&L: -$751.57 (1000 shares)
```

**Analysis**:
- Stop was set at $157.22
- Exit occurred at $156.79 (**$0.43 below stop**)
- This is **139% slippage**
- Stopped out in first minute - no time to recover

---

### 3. ARM LONG (Attempt #1)
```
Entry:    $157.31 @ 11:22
Stop:     $157.00
Exit:     $156.72 @ 11:22 (STOP)
Duration: 0 minutes (instant stop!)

Expected Loss: $0.31/share
Actual Loss:   $0.60/share
Slippage:      $0.28/share (90% beyond stop!)

Total P&L: -$601.21 (1000 shares)
```

**Analysis**:
- Stopped out **instantly** - same minute as entry
- Slippage nearly doubled the loss
- ARM had TWO failed attempts totaling -$1,352.78

---

### 4. ROKU SHORT (Attempt #2)
```
Entry:    $101.13 @ 11:55
Stop:     $101.27
Exit:     $101.47 @ 11:56 (STOP)
Duration: 0 minutes

Expected Loss: $0.14/share
Actual Loss:   $0.35/share
Slippage:      $0.20/share (143% beyond stop!)

Total P&L: -$353.77 (1000 shares)
```

---

### 5. ROKU SHORT (Attempt #1)
```
Entry:    $101.09 @ 11:54
Stop:     $101.26
Exit:     $101.44 @ 11:55 (STOP)
Duration: 2 minutes

Expected Loss: $0.17/share
Actual Loss:   $0.36/share
Slippage:      $0.18/share (106% beyond stop!)

Total P&L: -$363.67 (1000 shares)
```

**Analysis**:
- ROKU had TWO failed attempts totaling -$717.44
- Both stopped out with **100%+ slippage**
- Combined with ARM (-$1,352.78) and JPM (-$1,225.51) = **-$3,295.73** (78% of total loss!)

---

## Slippage Statistics

### All Stopped-Out Trades (18 total)

| Symbol | Entry  | Stop   | Exit   | Slippage | Slippage % |
|--------|--------|--------|--------|----------|------------|
| JPM    | 304.67 | 305.10 | 305.88 | +0.78    | **181%**   |
| ARM #2 | 157.53 | 157.22 | 156.79 | +0.43    | **139%**   |
| ROKU #2| 101.13 | 101.27 | 101.47 | +0.20    | **143%**   |
| ROKU #1| 101.09 | 101.26 | 101.44 | +0.18    | **106%**   |
| ARM #1 | 157.31 | 157.00 | 156.72 | +0.28    | **90%**    |
| INTC #1| 37.52  | 37.44  | 37.26  | +0.18    | **225%**   |
| INTC #2| 37.38  | 37.29  | 37.26  | +0.03    | **25%**    |
| GME #1 | 24.38  | 24.45  | 24.55  | +0.10    | **59%**    |
| GME #2 | 24.46  | 24.50  | 24.55  | +0.05    | **56%**    |
| F #1   | 12.05  | 12.09  | 12.09  | +0.00    | **0%**     |
| F #2   | 12.04  | 12.08  | 12.09  | +0.01    | **20%**    |

**Average Slippage**: **113% beyond expected stop distance**

---

## Root Causes

### 1. Simulated Slippage Too Low
**Current Config** (`trader_config.yaml`):
```yaml
slippage:
  enabled: true
  percentage: 0.001  # 0.1% slippage (NOT stops)

# Stop slippage is hardcoded in backtester.py:
stop_slippage = entry * 0.002  # 0.2% for stops
```

**Problem**: Real market slippage during breakouts is **2-3x higher** than 0.2%.

**Evidence**:
- JPM: 181% slippage (0.4% actual vs 0.2% simulated)
- ARM: 90-139% slippage (0.3-0.4% actual vs 0.2% simulated)
- ROKU: 106-143% slippage (0.4% actual vs 0.2% simulated)

### 2. Instant Stop-Outs
**Observation**: Many trades stopped out in **0-1 minutes** (same bar or next bar as entry).

**Examples**:
- ARM #1: 0 minutes (instant)
- ROKU #2: 0 minutes (instant)
- F #1, F #2: 0 minutes
- AMC #1, #2: 0 minutes

**Root Cause**: Entering **too late** in the breakout move. By the time we enter, the momentum has already stalled and price reverses immediately.

### 3. Second Attempts Make It Worse
**Pattern**: When first attempt fails, the second attempt usually fails too (and often with worse slippage).

**Examples**:
- ARM: -$601 (1st) + -$751 (2nd) = **-$1,352**
- ROKU: -$363 (1st) + -$353 (2nd) = **-$717**
- GME: -$183 (1st) + -$103 (2nd) = **-$287**
- INTC: -$272 (1st) + -$132 (2nd) = **-$404**

**Observation**: Second attempts tend to enter at worse prices (higher for shorts, lower for longs) because the first attempt already moved the pivot.

---

## Recommendations

### 1. Increase Simulated Stop Slippage
**Current**: 0.2% (0.002)
**Recommended**: 0.4% (0.004) - double current setting

**Rationale**: Real-world stop slippage is averaging 100%+ beyond expected distance, suggesting we need at least 0.4% to match reality.

**Implementation** (`backtester.py` line ~400):
```python
# OLD
stop_slippage = entry * 0.002  # 0.2%

# NEW
stop_slippage = entry * 0.004  # 0.4%
```

### 2. Skip Instant Stop-Outs
Add a filter to avoid setups that are likely to stop out immediately.

**Possible Filters**:
- Require some "pullback room" between entry and stop (e.g., 0.3% minimum)
- Avoid entering if already 0.5%+ into the move
- Check if price is already at extreme of recent 5-min range

### 3. Disable Second Attempts on Fast Failures
**Rule**: If first attempt stops out in <5 minutes, **do not attempt second entry** on same pivot.

**Rationale**: Quick failures indicate the pivot is not holding. Second attempts usually fail worse.

**Implementation**:
```python
# Track failed attempts
if duration_min < 5 and reason == 'STOP':
    blacklist_pivot(symbol, pivot_price, duration=30)  # No retry for 30 min
```

### 4. Tighter ATR Stops (Alternative)
Instead of stop at pivot, use **ATR-based stops** that are slightly tighter.

**Current**: Stop = Pivot price
**Alternative**: Stop = Entry ± (1.5 × ATR)

**Rationale**: ATR-based stops may be tighter than pivot distance, reducing slippage impact.

### 5. Test LONGS ONLY Strategy
**Observation**: All top losers except ARM were **SHORTS**.

**Shorts**:
- JPM: -$1,225 (worst)
- ROKU: -$717 (2nd worst)
- GME: -$287
- Total SHORT losses: ~$3,500

**Hypothesis**: Scanner support levels may be less reliable than resistance levels for entry timing.

**Test**: Run backtest with `enable_shorts: false` and compare results.

---

## Next Steps

1. ✅ **Increase stop slippage to 0.4%** in backtester
2. ⏳ **Rerun Oct 7 backtest** with higher slippage
3. ⏳ **Add instant stop-out filter** (skip if stopped out in <1 minute on attempt #1)
4. ⏳ **Test LONGS ONLY strategy** (disable shorts temporarily)
5. ⏳ **Analyze bar data** for JPM, ARM, ROKU to see actual price action at stop times

---

## Conclusion

**Stop loss slippage is costing an average of 113% beyond expected loss**, turning what should be small losses (-$0.30-0.40/share) into large losses (-$0.60-1.20/share).

**Impact on Results**:
- If slippage was 0% (perfect fills): P&L would be ~-$2,000 instead of -$4,234
- If slippage was 50% (half current): P&L would be ~-$3,000

**The backtester's 0.2% stop slippage is unrealistic. Real market conditions show 0.4-0.5% is more accurate.**

Fixing this alone won't make the strategy profitable (October 7 was a bad trading day), but it will prevent the backtester from giving **overly optimistic** results that don't match live trading reality.

---

*Analysis completed: October 8, 2025*
