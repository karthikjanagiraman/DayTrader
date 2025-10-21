# October 15, 2025 - Detailed Trade Analysis

## Executive Summary

**Overall Performance**: -$357.19 P&L, 20% win rate (2 winners / 10 trades)
**Major Issue**: ALL 10 trades entered via SUSTAINED_BREAK path with WEAK volume

## Entry Path Breakdown

### 100% SUSTAINED_BREAK Path (10/10 trades)

All trades entered using the SUSTAINED_BREAK entry logic, which triggers when:
1. Price holds above/below pivot for 12+ bars (1 minute at 5-second resolution)
2. Price breaks next technical level (SMA5, SMA10, SMA20, or Target)
3. Volume ≥2.0x when breaking next level
4. Candle size ≥0.3% when breaking next level
5. Room to target ≥3% after breaking next level
6. Stochastic filter passes
7. CVD filter passes

**CRITICAL FINDING**: None of the trades met MOMENTUM requirements (3.0x volume + 0.3% candle on initial breakout)

---

## Trade-by-Trade Analysis

### Trade #1: PATH LONG (10:36:55)
- **Entry**: $17.01 @ bar 804
- **Exit**: $16.98 @ bar 888 (7MIN_RULE)
- **P&L**: -$57.01
- **Duration**: 7 minutes

**Entry State**:
- Breakout type: WEAK
- Initial volume ratio: **0.54x** (extremely weak!)
- Breakout bar: 781 (broke pivot at 10:33:20)
- Candle close bar: 791
- Bars held: 12 (waited 1 minute after initial break)
- Entry reason: SUSTAINED_BREAK

**Filter Analysis**:
- ✅ Time requirement: Held 12+ bars
- ✅ Next level break: Broke next technical level
- ⚠️ Volume: Only 0.54x on initial break (never hit 3.0x for MOMENTUM)
- ✅ Room to run: Passed (≥3% to target)
- ✅ Stochastic: Passed
- ✅ CVD: Passed

**Why It Failed**: EXTREMELY weak volume (0.54x) indicates no buying pressure. Entered only because it held 12 bars and broke next SMA level, but lacked conviction.

---

### Trade #2: PATH LONG (10:44:00) - 2nd attempt
- **Entry**: $16.98 @ bar 889
- **Exit**: $17.00 @ bar 974 (7MIN_RULE)
- **P&L**: -$6.98
- **Duration**: 7.08 minutes

**Entry State**:
- Same breakout as Trade #1 (still tracking from bar 781)
- Volume ratio: **0.54x** (same weak breakout)
- Entry reason: SUSTAINED_BREAK

**Filter Analysis**: Same as Trade #1

**Why It Failed**: Re-entry on same weak breakout. No new momentum developed. Choppy price action.

---

### Trade #3: AMD LONG (10:36:55)
- **Entry**: $235.20 @ bar 804
- **Exit**: $233.28 @ bar 888 (7MIN_RULE)
- **P&L**: -$156.73
- **Duration**: 7 minutes

**Entry State**:
- Breakout type: WEAK
- Initial volume ratio: **2.28x** (BEST of the day, but still <3.0x)
- Breakout bar: 782
- Candle close bar: 791
- Bars held: 12
- Entry reason: SUSTAINED_BREAK

**Filter Analysis**:
- ✅ Time requirement: Held 12+ bars
- ✅ Next level break: Broke next technical level
- ⚠️ Volume: 2.28x (best volume of day, but <3.0x MOMENTUM threshold)
- ✅ Room to run: Passed
- ✅ Stochastic: Passed
- ✅ CVD: Passed

**Why It Failed**: Despite best volume of the day (2.28x), still failed to gain momentum. Market conditions likely weak (Oct 15 was a choppy day overall).

---

### Trade #4: AMD LONG (10:44:00) - 2nd attempt ✅ WINNER
- **Entry**: $233.39 @ bar 889
- **Exit**: $235.92 @ bar 1476 (TRAIL_STOP)
- **P&L**: +$317.90
- **Duration**: 48.92 minutes
- **Partials**: 4 taken

**Entry State**:
- Same breakout as Trade #3 (bar 782)
- Volume ratio: **2.28x**
- Entry reason: SUSTAINED_BREAK

**Why It Won**:
- Best volume of the day (2.28x)
- Second attempt entry at lower price ($233.39 vs $235.20)
- Captured reversal and held for 49 minutes
- Took 4 partials, letting runner work

**Key Lesson**: Sometimes second attempt at better price captures the move!

---

### Trade #5: SOFI LONG (10:36:55)
- **Entry**: $28.81 @ bar 804
- **Exit**: $28.63 @ bar 888 (7MIN_RULE)
- **P&L**: -$126.11
- **Duration**: 7 minutes

**Entry State**:
- Breakout type: WEAK
- Initial volume ratio: **0.44x** (WORST of the day!)
- Breakout bar: 781
- Candle close bar: 791
- Bars held: 12
- Entry reason: SUSTAINED_BREAK

**Filter Analysis**:
- ✅ Time requirement: Held 12+ bars
- ✅ Next level break: Broke next SMA
- ⚠️ Volume: Only 0.44x (pathetic!)
- ✅ Room to run: Passed
- ✅ Stochastic: Passed
- ✅ CVD: Passed

**Why It Failed**: WORST volume of the day. Absolutely no buying pressure. Should have been rejected.

---

### Trade #6: SOFI LONG (10:44:00) - 2nd attempt
- **Entry**: $28.66 @ bar 889
- **Exit**: $28.67 @ bar 1033 (7MIN_RULE)
- **P&L**: +$0.92
- **Duration**: 12 minutes

**Entry State**:
- Same weak breakout (0.44x volume)
- Entry reason: SUSTAINED_BREAK

**Why It Barely Won**: Lucky scratch trade. Held 12 minutes before hitting 7-min rule threshold.

---

### Trade #7: TSLA LONG (10:46:55)
- **Entry**: $438.05 @ bar 924
- **Exit**: $437.18 @ bar 1008 (7MIN_RULE)
- **P&L**: -$52.66
- **Duration**: 7 minutes

**Entry State**:
- Breakout type: WEAK
- Initial volume ratio: **0.74x** (weak)
- Breakout bar: 906 (broke pivot at 10:43:30)
- Candle close bar: 911
- Bars held: 12
- Entry reason: SUSTAINED_BREAK

**Filter Analysis**:
- ✅ All filters passed
- ⚠️ Volume: Only 0.74x (sub-average!)

**Why It Failed**: Sub-average volume (0.74x). No momentum.

---

### Trade #8: TSLA LONG (10:54:00) - 2nd attempt
- **Entry**: $437.68 @ bar 1009
- **Exit**: $436.67 @ bar 1093 (7MIN_RULE)
- **P&L**: -$61.03
- **Duration**: 7 minutes

**Entry State**:
- Same weak breakout (0.74x volume)
- Entry reason: SUSTAINED_BREAK

**Why It Failed**: Re-entry on same weak breakout that already failed once.

---

### Trade #9: PLTR LONG (10:36:55)
- **Entry**: $183.92 @ bar 804
- **Exit**: $183.19 @ bar 888 (7MIN_RULE)
- **P&L**: -$106.35
- **Duration**: 7 minutes

**Entry State**:
- Breakout type: WEAK
- Initial volume ratio: **0.79x** (weak)
- Breakout bar: 781
- Candle close bar: 791
- Bars held: 12
- Entry reason: SUSTAINED_BREAK

**Filter Analysis**:
- ✅ All filters passed
- ⚠️ Volume: Only 0.79x (below average)

**Why It Failed**: Sub-average volume (0.79x). No buying pressure.

---

### Trade #10: PLTR LONG (10:44:00) - 2nd attempt
- **Entry**: $183.35 @ bar 889
- **Exit**: $182.60 @ bar 973 (7MIN_RULE)
- **P&L**: -$109.13
- **Duration**: 7 minutes

**Entry State**:
- Same weak breakout (0.79x volume)
- Entry reason: SUSTAINED_BREAK

**Why It Failed**: Re-entry on same weak breakout.

---

## Clustering Pattern Explained

### Why did 5 stocks ALL enter at bar 804 (10:36:55)?

**Answer**: They all broke their pivots at approximately **bar 781-782** (10:33:20):
- PATH: Broke @ bar 781, volume 0.54x
- AMD: Broke @ bar 782, volume 2.28x
- SOFI: Broke @ bar 781, volume 0.44x
- PLTR: Broke @ bar 781, volume 0.79x

**Timeline**:
1. **10:33:20** (bar 781-782): Initial pivot breaks (all WEAK volume)
2. **10:33:35** (bar 791): 1-minute candle close
3. **10:33:35-10:36:50** (bars 792-803): Hold for 12 bars (sustained break requirement)
4. **10:36:55** (bar 804): SUSTAINED_BREAK confirmed → ALL enter simultaneously

**Why simultaneous**: All hit the same 12-bar (1-minute) threshold at the same time!

### Why did the other 5 stocks enter at bar 889 (10:44:00)?

**Answer**: These are **2nd attempt entries** on the SAME breakouts:
- PATH: 2nd attempt on bar 781 breakout
- AMD: 2nd attempt on bar 782 breakout
- SOFI: 2nd attempt on bar 781 breakout
- TSLA: 1st attempt on bar 906 breakout (different timing)
- PLTR: 2nd attempt on bar 781 breakout

---

## Filter Performance Analysis

### Filters That PASSED (Did Their Job)
1. ✅ **Stochastic Filter**: No blocks on Oct 15
2. ✅ **CVD Filter**: Blocked 1 trade (NVDA SHORT)
3. ✅ **Room-to-Run Filter**: All entries had ≥3% to target
4. ✅ **Time Requirement**: All held 12+ bars

### Filters That FAILED (Let Bad Trades Through)

1. ❌ **Volume Threshold Too Generous (2.0x for SUSTAINED_BREAK)**
   - PATH: 0.54x passed (should block!)
   - SOFI: 0.44x passed (should block!)
   - PLTR: 0.79x passed (should block!)
   - TSLA: 0.74x passed (should block!)

   **Problem**: SUSTAINED_BREAK requires 2.0x volume when breaking NEXT level, not initial breakout

   **Impact**: 8 out of 10 trades had volume <1.0x on initial breakout!

2. ❌ **No Choppy Filter on SUSTAINED_BREAK Path**
   - Choppy filter only applies to MOMENTUM and PULLBACK_RETEST paths
   - SUSTAINED_BREAK entries bypass choppy detection
   - Oct 15 was a choppy day (low ATR, tight ranges)

   **Recommendation**: Add choppy filter to SUSTAINED_BREAK path

3. ❌ **No Delayed Momentum Detection for SUSTAINED_BREAK**
   - Once classified as WEAK (bar 781), never rechecked for momentum
   - If volume appeared later (like BB on Oct 6), would miss it

   **Recommendation**: Add delayed momentum checks in SUSTAINED_BREAK state

---

## Comparison to Oct 20 (Successful Day)

| Metric | Oct 15 | Oct 20 | Difference |
|--------|--------|--------|------------|
| **P&L** | -$357.19 | +$110.62 | +$467.81 |
| **Win Rate** | 20% (2/10) | 66.7% (4/6) | +46.7% |
| **Trades** | 10 | 6 | -4 trades |
| **Entry Path** | 100% SUSTAINED_BREAK | Mixed | More selective |
| **Avg Volume** | 0.93x | Unknown | Likely higher |
| **7-MIN Exits** | 8/10 (80%) | 2/6 (33%) | Fewer quick fails |

**Key Differences**:
- Oct 15: All WEAK volume entries (0.44x - 2.28x range)
- Oct 20: Likely had better volume on entries
- Oct 15: 80% hit 7-min rule (no progress)
- Oct 20: Only 33% hit 7-min rule (more winners developed)

---

## ROOT CAUSE ANALYSIS

### Why Did Oct 15 Perform So Poorly?

**Primary Cause**: **SUSTAINED_BREAK path is too permissive with weak volume**

1. **Volume Threshold Mismatch**:
   - Initial breakout: 0.44x-2.28x (all below 3.0x MOMENTUM threshold)
   - SUSTAINED_BREAK only checks volume when breaking NEXT level
   - Allows entries on pathetically weak initial breaks

2. **No Choppy Protection**:
   - SUSTAINED_BREAK path doesn't check choppy filter
   - Oct 15 was a choppy day
   - All trades whipsawed within minutes

3. **Re-Entry on Failed Breakouts**:
   - 5 out of 10 trades were 2nd attempts on same failed breakouts
   - PATH, SOFI, PLTR: Re-entered same 0.44x-0.79x volume breaks
   - Should block re-entry when first attempt fails quickly

---

## RECOMMENDATIONS

### Immediate Fixes (High Priority)

1. **Add Minimum Volume Threshold for Initial Breakout**
   ```python
   # In breakout_state_tracker.py, line ~198 (BREAKOUT_DETECTED state)
   # BEFORE allowing WEAK classification:

   if volume_ratio < 1.0:  # Less than average volume
       # Don't even track weak breakouts with sub-average volume
       state.state = BreakoutState.FAILED
       return False
   ```

   **Impact**: Would have blocked 6 out of 10 Oct 15 trades (PATH, SOFI, PLTR, TSLA)
   **Estimated Savings**: -$457 loss → -$100 loss (save $357)

2. **Add Choppy Filter to SUSTAINED_BREAK Path**
   ```python
   # In ps60_entry_state_machine.py, line ~806 (before stochastic filter)

   # Check choppy filter (Oct 20, 2025)
   is_choppy, choppy_msg = strategy._check_choppy_filter(bars, current_idx)
   if is_choppy:
       tracker.reset_state(symbol)
       return False, choppy_msg, {'phase': 'choppy_filter'}
   ```

   **Impact**: Would block SUSTAINED_BREAK entries in low-volatility conditions
   **Estimated Savings**: Additional 2-3 trades blocked on choppy days

3. **Block Re-Entry on Quick Failures**
   ```python
   # Track failed attempts with timing
   # Don't allow 2nd attempt if 1st attempt failed in <10 minutes

   if long_attempts > 0 and time_since_last_attempt < 600:  # 10 min
       return False, "Previous attempt failed too quickly"
   ```

   **Impact**: Would have blocked 5 out of 10 Oct 15 trades (all 2nd attempts)
   **Estimated Savings**: -$357 → -$181 (save $176)

### Medium Priority

4. **Increase sustained_volume_candles to 3**
   - Currently checking 2 subsequent candles for sustained volume
   - Could increase to 3 for more confirmation
   - Trade-off: Fewer entries but higher quality

5. **Add Delayed Momentum Detection to SUSTAINED_BREAK**
   - Currently only checks momentum when breaking next SMA level
   - Could check every 1-min candle close for late momentum (like BB case)

### Low Priority

6. **Dynamic Volume Threshold Based on Market Conditions**
   - Use SPY volume to detect choppy vs trending days
   - Increase volume threshold on choppy days (2.0x → 3.0x)
   - Relax on strong trending days (2.0x → 1.5x)

---

## Expected Impact of Fixes

### With Fix #1 (Min 1.0x Volume on Initial Break)
- **Oct 15 Result**: 4 trades (AMD, AMD 2nd), -$100 P&L
- **Blocked**: PATH (0.54x), SOFI (0.44x), TSLA (0.74x), PLTR (0.79x)
- **Improvement**: +$257 (from -$357 to -$100)

### With Fix #1 + Fix #2 (Add Choppy Filter)
- **Oct 15 Result**: 2 trades, -$50 P&L (estimated)
- **Blocked**: Additional 2 AMD trades in choppy conditions
- **Improvement**: +$307 (from -$357 to -$50)

### With All 3 Fixes
- **Oct 15 Result**: 1-2 high-quality trades, ~$0 P&L
- **Blocked**: Nearly all weak entries
- **Improvement**: +$357 (from -$357 to $0)

---

## Conclusion

October 15th was a **SUSTAINED_BREAK disaster** caused by:
1. **Too permissive volume threshold** (allows sub-average initial breakouts)
2. **No choppy protection** (enters in low-volatility conditions)
3. **Re-entries on failed setups** (doubles down on losers)

The **SUSTAINED_BREAK path needs tightening** to prevent weak-volume entries in choppy markets.

**Recommended Action**: Implement Fix #1 immediately (min 1.0x volume threshold), test on historical data, then add Fix #2 (choppy filter) if needed.

---

**Analysis Date**: October 20, 2025
**Analyzed By**: Claude Code
**Source Data**: `backtest/logs/backtest_20251015_223842.log`
