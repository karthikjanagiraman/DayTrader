# Hybrid Strategy Debug Log - October 4, 2025

## Problem Statement

Hybrid momentum/pullback strategy was implemented and tested on Oct 1-4, 2025. Results showed:
- 42 trades, 26.2% win rate, +$4,531 P&L
- **IDENTICAL results to pullback-only strategy** (same 42 trades)
- Expected to capture TSLA and NVDA momentum breakouts on Oct 1, but didn't

## Investigation Process

### Step 1: Check if momentum logic is being called

**Action**: Added debug logging to `check_hybrid_entry()` to print volume_ratio and candle_size_pct

**Code added** (line 811-815 in ps60_strategy.py):
```python
# DEBUG: Log breakout analysis
print(f"    📊 Breakout analysis: vol={volume_ratio:.2f}x (need {self.momentum_volume_threshold}x), "
      f"candle={candle_size_pct*100:.2f}% (need {self.momentum_candle_min_pct*100:.2f}%), "
      f"ATR={candle_atr_ratio:.2f}x (need {self.momentum_candle_min_atr}x)")
print(f"       Strong volume: {is_strong_volume}, Large candle: {is_large_candle}")
```

**Result**: Ran Oct 1 backtest - TSLA and NVDA showed NO "Breakout analysis" lines
- This means they never triggered ANY breakout detection
- Other stocks (PLTR, AMD, GME) showed debug output

### Step 2: Check if TSLA/NVDA actually broke resistance

**Action**: Analyzed raw market data for TSLA on Oct 1

**Finding - TSLA**:
```
Resistance: $444.77
Bar 0 (9:30:00): Close $444.93 - BROKE RESISTANCE
Bar 1 (9:30:05): Close $445.33 - BROKE RESISTANCE
Total bars above resistance: 4608/4680 (98.5% of day)
```

**Conclusion**: TSLA broke resistance at market open and stayed above it all day

**Finding - NVDA**:
```
Resistance: $187.35
Market Open (9:30:00): $185.81 - Below resistance
9:45 AM: $185.40 - Below resistance
First breakout: Bar 795 (10:36:15 AM) - $187.45
```

**Conclusion**: NVDA broke resistance at 10:36 AM (within trading window)

### Step 3: Check trading time window

**Action**: Checked trader_config.yaml entry time restrictions

**Finding**:
```yaml
min_entry_time: "09:45"   # Wait 15 min after open
max_entry_time: "15:00"   # No new entries after 3:00 PM
```

**Impact on TSLA**:
- TSLA broke at 9:30:00 AM
- Strategy can't trade until 9:45 AM
- By 9:45 AM, TSLA is at $447.41 (0.59% above resistance)

**Hypothesis**: TSLA breakout might be considered "too old" by the time 9:45 arrives

### Step 4: Analyze NVDA breakout at 10:36 AM

**Action**: Checked NVDA 1-minute candle that broke resistance

**Finding - Candle data**:
```
Time: 10:36:00-10:36:55
Open: $187.20
Close: $187.56 (above $187.35 resistance ✓)
Volume: 2.20x average (meets 2.0x threshold ✓)
Candle size: 0.19% (needs 1.5% ✗)
ATR ratio: Not large enough
```

**Entry type determination**:
- Strong volume: TRUE (2.20x ≥ 2.0x)
- Large candle: FALSE (0.19% < 1.5% AND ATR < 2.0x)
- **Result**: Routed to PULLBACK/RETEST logic (not momentum entry)

**What happened after breakout**:
```
Bar 804 (10:37:00): $187.63 - 0.15% above resistance
Bar 805-827: Price stayed within 0.3% of resistance for 2 minutes
```

**Conclusion**: NVDA never pulled back below resistance and re-broke. It just consolidated AT the pivot level. The pullback/retest logic expects:
1. Pullback TO pivot (within 0.3%)
2. Re-break ABOVE pivot with volume

But NVDA stayed above the pivot the whole time, so no "re-break" could occur.

### Step 5: Check TSLA breakout expiration

**Action**: Calculated time since TSLA's 9:30 breakout when we can trade at 9:45

**Finding**:
```
Breakout time: 9:30:00 AM (bar 0)
Entry window starts: 9:45:00 AM (bar 180)
Time elapsed: 15 minutes = 180 bars

Max breakout age (from config):
- max_pullback_bars: 24 (2 minutes)
- bars_per_candle: 12 (1 minute)
- Total max age: 36 bars = 3 minutes

Breakout age check:
- 180 bars > 36 bars → EXPIRED ✗
```

**Code location**: trader/strategy/ps60_strategy.py line 747
```python
if bars_since_breakout > self.max_pullback_bars + bars_per_candle:
    return False, "Breakout too old", {'phase': 'expired'}
```

**Conclusion**: TSLA's breakout is rejected as "too old" by the time the trading window opens at 9:45 AM

## Root Causes Summary

### Why TSLA didn't trade on Oct 1:
1. Stock broke resistance at 9:30:00 AM (market open)
2. Strategy has min_entry_time = 9:45 AM (15-minute wait)
3. By 9:45 AM, the 9:30 breakout is 15 minutes old
4. Hybrid logic rejects breakouts older than 3 minutes (36 bars)
5. **Result**: Breakout expired before trading window opened

### Why NVDA didn't trade on Oct 1:
1. Stock broke resistance at 10:36:15 AM (within trading window ✓)
2. Breakout candle had strong volume (2.20x) but small size (0.19%)
3. Routed to PULLBACK/RETEST logic (not momentum entry)
4. After breakout, price stayed AT resistance (within 0.3%) for 2+ minutes
5. Never pulled back and re-broke - just consolidated at pivot
6. **Result**: Pullback/retest entry never triggered (no re-break occurred)

### Why results were identical to pullback-only:
- **NO stocks met momentum criteria** (2.0x volume + 1.5% candle)
- All 42 trades were pullback/retest entries
- Momentum breakout code path never executed

## Trade Examples from Oct 1 Debug Run

### Stocks that DID trade:

**PLTR #1** (9:48 AM):
```
📊 Breakout analysis: vol=1.20x (need 2.0x), candle=0.22% (need 1.50%), ATR=3.61x (need 2.0x)
   Strong volume: False, Large candle: True
→ Entry type: PULLBACK/RETEST
```

**AMD** (9:53 AM):
```
📊 Breakout analysis: vol=0.98x (need 2.0x), candle=0.22% (need 1.50%), ATR=3.65x (need 2.0x)
   Strong volume: False, Large candle: True
→ Entry type: PULLBACK/RETEST
```

**GME** (9:47 AM):
```
📊 Breakout analysis: vol=0.65x (need 2.0x), candle=0.29% (need 1.50%), ATR=6.25x (need 2.0x)
   Strong volume: False, Large candle: True
→ Entry type: PULLBACK/RETEST
```

**Pattern**: All had large ATR ratios (>2.0x) but failed volume or candle size checks

## Solution Options

### Option 1: Remove min_entry_time restriction
**Pros**: Captures market open breakouts like TSLA
**Cons**: Early morning volatility can cause whipsaws

### Option 2: Increase max_pullback_bars
**Current**: 24 bars (2 minutes)
**Proposed**: 180+ bars (15 minutes) to cover 9:30-9:45 gap
**Pros**: Allows TSLA-style gap breakouts
**Cons**: May enter stale breakouts that have lost momentum

### Option 3: Special market open logic
**Approach**: For stocks above resistance at 9:45, treat as fresh breakout
**Pros**: Captures strong gap-ups that hold
**Cons**: Adds complexity

### Option 4: Fix pullback/retest logic for consolidation
**Current issue**: Requires pullback below pivot and re-break above
**Proposed**: If price consolidates at pivot (within 0.3%) for X bars with volume, allow entry
**Pros**: Captures NVDA-style consolidation breakouts
**Cons**: May enter choppy consolidations

## Recommended Next Steps

1. **Test Option 2**: Increase `max_pullback_bars` from 24 to 180 (15 minutes)
   - This would allow TSLA Oct 1 entry at 9:45 AM
   - Run Oct 1-4 backtest to see impact

2. **Analyze momentum threshold calibration**:
   - Current: 2.0x volume + 1.5% candle
   - Reality: Most breakouts have <2.0x volume or <1.5% candles
   - Consider lowering thresholds to 1.5x volume + 1.0% candle

3. **Add consolidation entry logic**:
   - If price stays within 0.3% of pivot for 12+ bars (1 minute) with volume
   - Allow entry even without pullback/re-break

## Files Modified During Debug

1. `/Users/karthik/projects/DayTrader/trader/strategy/ps60_strategy.py`
   - Added debug logging (lines 811-815) - REMOVED after testing
   - check_hybrid_entry() method (lines 697-856)

2. `/Users/karthik/projects/DayTrader/trader/config/trader_config.yaml`
   - Hybrid strategy configuration (lines 46-70)

## Test Results Summary

| Configuration | Trades | Win Rate | P&L | Notes |
|---------------|--------|----------|-----|-------|
| Pullback-only | 42 | 26.2% | +$5,022 | Oct 1-3, volume 1.2x |
| Hybrid (current) | 42 | 26.2% | +$4,531 | Oct 1-3, identical trades |
| Expected with TSLA/NVDA | ~48-50 | TBD | TBD | If breakout issues fixed |

## Key Metrics from Oct 1-4 Backtest

```
Trading Days: 3
Total Trades: 42
Total P&L: $4,531.46
Avg Daily P&L: $1,510.49
Win Rate: 26.2%
Winning Days: 2/3 (66.7%)
Monthly Return: 4.53%
```

## Timestamp

**Debug Session**: October 4, 2025, 6:25 PM - 6:31 PM
**Issue Resolved**: Root causes identified, solutions proposed
**Status**: Awaiting user decision on which solution to implement
