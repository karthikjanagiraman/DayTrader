# Decision Tree Path Analysis - October 9, 2025 Backtest

## Critical Finding: 93% of Trades Stuck at STEP 1

**Root Cause**: The lookback loop that searches for the initial breakout is failing for almost all trades.

---

## Path Distribution

| Path | Trades | % | Avg Failed Attempts |
|------|--------|---|---------------------|
| **STEP 1: No breakout detected (lookback failed)** | **28** | **93.3%** | **383** |
| STEP 1: Candle closed wrong direction | 2 | 6.7% | 179 |

**Total Trades**: 30

---

## What "No Breakout Detected" Means

From the code (`ps60_strategy.py` lines 954-968):

```python
# Find where price first broke the pivot
lookback_start = max(0, current_idx - self.max_pullback_bars - bars_per_candle)

breakout_bar = None
for i in range(lookback_start, current_idx):
    bar_price = bars[i].close
    if side == 'LONG' and bar_price > pivot_price and (i == 0 or bars[i-1].close <= pivot_price):
        breakout_bar = i
        break
    elif side == 'SHORT' and bar_price < pivot_price and (i == 0 or bars[i-1].close >= pivot_price):
        breakout_bar = i
        break

if breakout_bar is None:
    return False, "No breakout detected", {'phase': 'no_breakout'}
```

**The lookback logic**:
- Looks back `max_pullback_bars + bars_per_candle` = 24 + 12 = **36 bars (3 minutes)**
- Searches for the FIRST bar where `close > pivot` AND `previous close <= pivot`
- If not found in the 3-minute window → "No breakout detected"

---

## Why the Lookback Loop Fails

### Issue #1: Lookback Window Too Short (3 Minutes)

**Config**: `max_pullback_bars: 24` (2 minutes) + `bars_per_candle: 12` (1 minute) = **36 bars total**

**Problem**: If the initial breakout happened >3 minutes ago, the loop can't find it.

**Example (BB - 282 bar delay)**:
- Bar 1: Price breaks $4.79 resistance
- Bar 282: System tries to enter
- Lookback window: Bars 246-282 (only last 36 bars)
- Bar 1 is WAY outside the window → "No breakout detected" × 342 failures

### Issue #2: Whipsaw Price Action

**The check requires**:
```python
bar_price > pivot_price and bars[i-1].close <= pivot_price
```

This means:
- Bar N-1 must be BELOW pivot
- Bar N must be ABOVE pivot
- It's looking for a CLEAN cross

**Problem**: If price whipsawed back and forth across the pivot:
```
Bar 100: $4.80 (above pivot $4.79)
Bar 101: $4.78 (below pivot)
Bar 102: $4.81 (above pivot)
Bar 103: $4.79 (at pivot)
Bar 104: $4.80 (above pivot)
```

The loop finds Bar 100 as the breakout, but if we're checking at Bar 250:
- Lookback: Bars 214-250
- Bar 100 is outside window → "No breakout detected"

### Issue #3: Lookback Resets Every Bar

**Every bar, the confirmation logic re-searches for the breakout**:
- Bar 50: Lookback 14-50 → Finds breakout at Bar 20 ✓
- Bar 100: Lookback 64-100 → Breakout at Bar 20 is outside window → "No breakout detected" ❌

Once the initial breakout ages beyond the 36-bar window, **the system forgets it ever happened**.

---

## Real Example: BB LONG

**Scenario**:
- Breakout at Bar 1 (9:33 AM) @ $4.82
- Entry at Bar 3418 (2:14 PM) @ $4.81
- Delay: **3417 bars** (28 minutes)

**What happened**:
1. **Bars 1-36**: Lookback finds breakout at Bar 1
2. **Bars 37+**: Breakout is now >36 bars ago → "No breakout detected"
3. **Bars 37-3418**: System keeps searching for breakout in last 36 bars, never finds it
4. **Result**: 342 failed attempts with "No breakout detected"

**Why did it finally enter at Bar 3418?**
Likely one of two scenarios:
1. Price whipsawed back below $4.79, then re-broke above → New breakout detected
2. Some other confirmation path succeeded (sustained break without needing to find initial breakout)

---

## The Actual Entry Flow (What Really Happened)

Based on log analysis, here's what the 30 trades actually experienced:

### Path 1: No Breakout Detected Loop (28 trades, 93%)

```
Bar N: Price > pivot (should_enter_long returns True)
  │
  └─→ check_hybrid_entry() called
      │
      ├─→ Lookback loop (lines 954-968)
      │   └─→ Search bars [N-36 to N] for initial breakout
      │       └─→ NOT FOUND (breakout happened >36 bars ago)
      │           └─→ Return "No breakout detected"
      │
      └─→ Backtester logs: "confirmed=False, reason='No breakout detected'"
          └─→ Keep checking every bar...
              └─→ Eventually:
                  ├─→ Price whipsaws, creates NEW breakout in window, OR
                  └─→ Entry happens via different code path
```

**Result**: 383 average failed attempts per trade before finally entering

### Path 2: Candle Closed Wrong Direction (2 trades, 7%)

```
TSLA SHORT × 2:
Bar N: Price < support
  │
  └─→ check_hybrid_entry() called
      │
      ├─→ Lookback finds breakout ✓
      ├─→ Wait for 1-min candle close
      └─→ Candle closes at $429.50 (ABOVE support $429.28)
          └─→ Return "1-min candle closed above support (failed)"
              └─→ Reject entry, restart search
```

**Result**: 179 average failed attempts (candle kept closing wrong direction)

---

## Why This Explains Everything

### Mystery #1: Why 100+ Bar Delays?

**Answer**: The lookback window is only 36 bars. Once the initial breakout ages beyond that, the system can't find it anymore and keeps rejecting with "No breakout detected" until:
- A new breakout happens within the window, OR
- Some other condition allows entry

### Mystery #2: Why Low Entry Slippage (0.23%)?

**Answer**: The system isn't actually tracking the original breakout. It's waiting for a NEW breakout to happen within the 36-bar lookback window. When that finally happens, entry is close to that NEW breakout point, not the original one.

### Mystery #3: Why 13% Win Rate?

**Answer**: By the time a new breakout happens within the lookback window, the original setup is stale:
- BB: Original breakout at 9:33 AM, entered at 2:14 PM (5 hours later!)
- The move is long gone, now just noise

---

## The Fix

The lookback window needs to be dramatically increased OR the logic needs to be fundamentally changed.

### Option 1: Increase Lookback Window

**Current**: 36 bars (3 minutes)
**Proposed**: 600 bars (50 minutes)

```yaml
# trader_config.yaml
max_pullback_bars: 600  # Was 24 (50 minutes vs 2 minutes)
```

**Impact**:
- Can find breakouts that happened up to 50 minutes ago
- Covers most of the trading session
- May still fail for all-day consolidations

### Option 2: Track Breakout State

**Better approach**: Don't re-search for breakout every bar. Track it once:

```python
# Pseudo-code
if breakout_bar_for_symbol is None:
    # First time checking this symbol
    breakout_bar = find_breakout_in_entire_session()  # Search ALL bars
    save_breakout_bar_for_symbol(symbol, breakout_bar)
else:
    # Already found breakout, reuse it
    breakout_bar = get_saved_breakout_bar(symbol)
```

**Impact**:
- Find breakout once, remember it for the entire session
- No more "No breakout detected" after initial detection
- Confirmation logic works as intended

### Option 3: Remove Breakout Detection Entirely

**Simplest fix**: Don't search for initial breakout at all.

```python
# Current logic requires finding the breakout bar
# New logic: Just check if price is currently through pivot

if current_price > pivot_price:
    # Don't care WHEN it first broke, just that it's above now
    # Still apply candle close, volume, sustained hold checks
    # But don't fail with "No breakout detected"
```

**Impact**:
- Eliminates 93% of failures
- Still has candle close confirmation
- Still has volume/sustained break checks
- Just removes the "find initial breakout bar" requirement

---

## Recommended Action

**Immediate**: Option 3 (Remove breakout detection requirement)

**Why**:
1. Eliminates 93% of entry failures
2. Simplest code change
3. Other confirmation layers still protect against false entries:
   - 1-minute candle close
   - Volume checks
   - Sustained hold checks
   - Room-to-run filter

**Code Change**:
Lines 954-968 in `ps60_strategy.py` - make breakout detection optional or remove it entirely for the candle close check.

**Expected Impact**:
- Trades will enter within 12-24 bars (1-2 minutes) instead of 100+ bars
- Win rate should improve dramatically (entering fresh setups vs stale ones)
- Entry slippage will remain low (already at 0.23%)

---

## Summary

**The 100+ bar delays are NOT caused by waiting for volume or sustained breaks.**

**The real problem**: 93% of trades never even reach the volume/sustained break checks because the lookback loop can't find the initial breakout (it happened >3 minutes ago and aged out of the 36-bar window).

**The irony**: The confirmation logic is designed to be conservative and wait for confirmation, but it's so conservative that it rejects 93% of valid setups with "No breakout detected" until a NEW breakout coincidentally happens within the narrow 3-minute lookback window.

**The solution**: Either dramatically increase the lookback window (36 → 600 bars), track breakout state instead of re-searching, or remove the breakout detection requirement entirely and rely on other confirmation layers.
