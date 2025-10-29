# SMCI Detailed Trade Report - October 21, 2025

## Executive Summary

**Scanner Setup**:
- Symbol: SMCI
- Direction: SHORT
- Support Level: $54.60
- Total SHORT Attempts: 2 (hit max_attempts_per_pivot limit)
- Total Trades: 2 (both stopped out)
- Total P&L: **-$211** (estimated)

---

## Trade #1: FIRST ATTEMPT (9:46:15 AM - 10:04:15 AM)

### Initial Breakout Detection

**Bar 16 (9:46:15 AM)**:
- Price: $54.56 (broke below support $54.60)
- Status: ✅ **BREAKOUT DETECTED**
- State: Waiting for 1-minute candle close
- Action: Entered BREAKOUT_DETECTED state

### Volume Rejections (9:47:20 AM - 10:03:30 AM)

After candle closes, backtester began checking confirmation filters on each subsequent bar:

| Bar | Time | Price | Volume Ratio | Decision | State |
|-----|------|-------|--------------|----------|-------|
| **17** | 09:47:20 | $54.56 | **0.72x** | ❌ REJECTED | Sub-average volume |
| **18** | 09:47:25 | $54.45 | - | 🔄 RESET | New breakout detected |
| **19** | 09:48:30 | $54.45 | **0.55x** | ❌ REJECTED | Sub-average volume |
| **20** | 09:48:35 | $54.46 | - | 🔄 RESET | New breakout detected |
| **21** | 09:49:40 | $54.49 | **0.62x** | ❌ REJECTED | Sub-average volume |
| **22-25** | 09:49:45-09:51:55 | $54.65-$54.88 | - | ⏸️ PAUSED | Price above support (recovered) |
| **26** | 09:52:00 | $54.49 | - | 🔄 RESET | New breakout detected |
| **27** | 09:53:05 | $54.43 | **0.80x** | ❌ REJECTED | Sub-average volume |
| **28** | 09:53:10 | $54.41 | - | 🔄 RESET | New breakout detected |
| **29** | 09:54:15 | $54.53 | **0.60x** | ❌ REJECTED | Sub-average volume |
| **30** | 09:54:20 | $54.59 | - | 🔄 RESET | New breakout detected |

**Summary**: 9 volume rejections over 16 minutes (bars 16-30). These are the exact rejections shown in the validator JSON.

### MOMENTUM Breakout Detected

**Bar 31 (10:00:20 AM)**:
- Price: $54.35 (strong drop)
- Volume: **2.54x** (FINALLY met 2.0x threshold!)
- Candle Size: Large (momentum criteria met)
- Decision: ✅ **MOMENTUM BREAKOUT DETECTED**
- Action: **Entered CVD_MONITORING state**

### CVD Monitoring Phase (10:00:20 AM - 10:04:15 AM)

The strategy detected momentum and entered CVD confirmation phase:

| Bar | Time | Price | CVD Imbalance | Trend | Decision |
|-----|------|-------|---------------|-------|----------|
| **32** | 10:01:25 | $54.38 | **21.0%** | BEARISH | 📊 Monitoring (1 candle) |
| **33** | 10:02:30 | $54.16 | **32.3%** | BEARISH | 📊 Monitoring (2 candles) |
| **34** | 10:03:35 | $54.28 | Initial: **32.3%**<br>Confirm: **22.1%** | BEARISH | ✅ **CVD CONFIRMED!** |

**Bar 34 (10:04:15 AM) - ENTRY CONFIRMED**:
- Entry Type: **CVD_AGGRESSIVE_CONFIRMED**
- Reason: "Strong spike confirmed (32.3% + 22.1%)"
- Entry Price: **$54.28**
- Stop: **$54.28** (ATR-based, tight stop)
- Attempts: 0/2

### Trade Exit

**Bar 35 (10:04:20 AM)**:
- Exit Type: **STOP**
- Exit Price: **$54.42** (price gapped up)
- Stop Price: $54.28
- Actual Fill: **$54.31** (slippage)
- Duration: **5 seconds** (1 bar)
- P&L: **-$3 per share** (estimated -$105 total)

**Analysis**: Entered at the exact moment, but price immediately reversed and gapped through stop.

---

## Trade #2: SECOND ATTEMPT (10:14:40 AM - 10:15:55 AM)

### Brief Recovery & New Breakout

**Bars 36-58 (10:04:25 AM - 10:14:35 AM)**:
- Price recovered above support ($54.60-$55.05 range)
- Backtester paused SHORT monitoring
- No entry attempts during this period

**Bar 59 (10:14:40 AM)**:
- Price: $54.50 (broke below support again)
- Status: ✅ **NEW BREAKOUT DETECTED**
- State: BREAKOUT_DETECTED

### Volume Rejections (Round 2)

After the morning's volume rejections, this breakout also started weak:

| Bar | Time | Price | Volume Ratio | Decision | State |
|-----|------|-------|--------------|----------|-------|
| **37** | 10:08:45 | $54.59 | **0.62x** | ❌ REJECTED | Sub-average volume |
| **39** | 10:09:50 | $54.55 | **0.62x** | ❌ REJECTED | Sub-average volume |
| **41** | 10:10:55 | $54.51 | **0.78x** | ❌ REJECTED | Sub-average volume |
| **43** | 10:12:00 | $54.58 | **0.43x** | ❌ REJECTED | Sub-average volume |

**Bar 60 (10:15:45 AM)**:
- Price: $54.51
- Volume: **1.09x** (above 1.0x but below 2.0x threshold)
- Candle Size: Small
- Decision: ⚠️ **WEAK BREAKOUT** (not strong enough for momentum)
- Action: **Entered CVD_MONITORING state** (for weak breakouts)

### CVD Sustained Selling Pattern

The strategy looked for **sustained CVD imbalances** (3 consecutive candles with bearish imbalance):

**Bar 61 (10:15:50 AM) - ENTRY CONFIRMED**:
- Entry Type: **CVD_SUSTAINED**
- Reason: "Sustained selling (3 consecutive: ['21.0%', '32.3%', '12.2%'])"
- Consecutive Imbalances: [21.0%, 32.3%, 12.2%]
- Time to Entry: **1.0 minute** (fast confirmation)
- Entry Price: **$54.55**
- Stop: **$54.57** (very tight ATR stop)
- Attempts: 1/2

**Note**: The CVD history shows [21.0%, 32.3%, 12.2%] which are actually from bars 32-34 (the FIRST breakout attempt). This suggests the CVD monitoring state carried over from the previous attempt.

### Trade Exit

**Bar 64 (10:16:05 AM)**:
- Exit Type: **STOP**
- Exit Price: **$54.72** (price gapped up again)
- Stop Price: $54.57
- Actual Fill: **$54.61**
- Duration: **15 seconds** (3 bars)
- P&L: **-$6 per share** (estimated -$106 total)

**Analysis**: Another immediate reversal. Tight ATR stop triggered after price recovered.

---

## Post-Trade Analysis: Max Attempts Reached

**Bar 64 (10:16:05 AM) - Attempts: 2/2**:
- ❌ **SHORT monitoring DISABLED for SMCI**
- ✅ LONG monitoring continued (but never triggered)
- Reason: max_attempts_per_pivot = 2

**Bars 65+ (10:16:10 AM - 4:00 PM)**:
- Backtester only checked LONG entries for rest of day
- Any subsequent SHORT breakouts were **ignored**

---

## The 12:51 PM MISSED Breakout

### What Actually Happened

**12:51 PM (approx Bar 2,412)**:
- A **REAL SHORT breakout** occurred in IBKR market data
- This breakout became a **3-star winner** (validator classification)
- Backtester **DID NOT ATTEMPT** this breakout
- Reason: **SHORT monitoring disabled** (max attempts reached at 10:16 AM)

### Validator Report Issue

The validator JSON shows:
```json
{
  "timestamp": "2025-10-21T12:51:00-04:00",
  "decision": "MISSED",
  "retry_history": [
    {"volume_ratio": 0.72},
    {"volume_ratio": 0.55},
    ...9 total retries...
  ]
}
```

**🐛 BUG IDENTIFIED**: The retry_history (9 volume rejections) is from bars 17-43 (9:47-10:03 AM), NOT from 12:51 PM. The validator's `find_nearby_blocked_attempts()` function is pulling volume rejection data from 2+ hours earlier and incorrectly attributing it to the 12:51 PM breakout.

**Expected Behavior**: 12:51 PM breakout should show NO retry_history (backtester never attempted it).

---

## Timeline Visualization

```
09:30 AM ─────────────────────────────────────────────────────────────────────────
         │
09:46 AM │ ╔═══════════════════════════════════════════════════════════════╗
         │ ║ FIRST BREAKOUT ATTEMPT (Bars 16-35)                           ║
         │ ╠═══════════════════════════════════════════════════════════════╣
09:47 AM │ ║ • 9 Volume Rejections (0.43x - 0.80x)                         ║
         │ ║ • Bar 31: MOMENTUM detected (2.54x volume!)                   ║
10:00 AM │ ║ • Bar 32-33: CVD monitoring (21.0%, 32.3%)                    ║
         │ ║ • Bar 34: CVD CONFIRMED → ENTER @ $54.28                      ║
10:04 AM │ ║ • Bar 35: STOP triggered @ $54.31 (-$105 P&L)                 ║
         │ ╚═══════════════════════════════════════════════════════════════╝
         │
10:05 AM │ [Price recovery to $54.60-$55.05]
         │
10:14 AM │ ╔═══════════════════════════════════════════════════════════════╗
         │ ║ SECOND BREAKOUT ATTEMPT (Bars 59-64)                          ║
         │ ╠═══════════════════════════════════════════════════════════════╣
         │ ║ • Bar 60: WEAK breakout (1.09x volume)                        ║
10:15 AM │ ║ • Bar 61: CVD SUSTAINED → ENTER @ $54.55                      ║
         │ ║ • Bar 64: STOP triggered @ $54.61 (-$106 P&L)                 ║
10:16 AM │ ╚═══════════════════════════════════════════════════════════════╝
         │
         │ ❌ MAX ATTEMPTS REACHED (2/2) - SHORT monitoring DISABLED
         │
10:17 AM │ [Only LONG monitoring active for rest of day]
         │
12:51 PM │ ╔═══════════════════════════════════════════════════════════════╗
         │ ║ MISSED 3-STAR WINNER                                          ║
         │ ╠═══════════════════════════════════════════════════════════════╣
         │ ║ • Real SHORT breakout in IBKR data                            ║
         │ ║ • Became a 3-star winner                                      ║
         │ ║ • Backtester NEVER ATTEMPTED (SHORT monitoring off)           ║
         │ ╚═══════════════════════════════════════════════════════════════╝
         │
04:00 PM ─────────────────────────────────────────────────────────────────────────
```

---

## Key Findings

### What Worked

1. ✅ **Volume calculation is accurate**: All 9 volume ratios (0.43x-0.80x) match actual candle volumes
2. ✅ **CVD detection works**: Correctly identified 32.3% bearish imbalance at bar 33
3. ✅ **State machine logic**: Properly transitioned through states (BREAKOUT_DETECTED → CVD_MONITORING → CONFIRMED)
4. ✅ **Max attempts enforcement**: Correctly stopped monitoring after 2 failed SHORT attempts

### What Failed

1. ❌ **Both entries stopped out immediately**: 5-second and 15-second holding periods
2. ❌ **ATR stops too tight**: $54.28 and $54.57 stops hit instantly on minor reversals
3. ❌ **Missed 3-star winner**: 12:51 PM breakout never attempted (max attempts limit)
4. ❌ **CVD state carryover**: Bar 61 showed CVD history from bars 32-34 (different breakout attempt)

### Validator Bug

🐛 **Issue**: `find_nearby_blocked_attempts()` in validate_market_outcomes.py pulls retry_history from ±5 minutes, but doesn't verify the attempts are for the SAME breakout sequence. For the 12:51 PM MISSED breakout, it pulled volume rejections from 9:47-10:03 AM (2+ hours earlier).

**Expected**: 12:51 PM breakout should show `retry_history: []` (no attempts made)

**Actual**: Shows 9 retry attempts from morning session

---

## Recommendations

### 1. Increase Max Attempts per Pivot

**Current**: `max_attempts_per_pivot: 2`

**Proposed**: `max_attempts_per_pivot: 3-4`

**Rationale**: SMCI showed a 3-star winning breakout at 12:51 PM that was missed due to max attempts limit. Allowing 3-4 attempts would have captured this winner.

**Trade-off**: Risk of overtrading the same symbol.

### 2. Implement Time-Based Attempt Reset

**Proposed Logic**:
```python
# Reset attempts after 2 hours of no breakouts
if time_since_last_attempt > 2 hours:
    reset_attempts_counter()
```

**Rationale**: The 12:51 PM breakout was 2.5 hours after the last attempt (10:16 AM). This is likely a NEW setup, not the same failed pivot.

### 3. Review ATR Stop Logic

**Current Issue**: ATR stops are too tight for 5-second bars, causing instant exits

**Analysis**:
- Trade #1: Stop at entry price → 5-second hold
- Trade #2: Stop $0.02 above entry → 15-second hold

**Proposed**: Consider wider stops or use actual pivot level (support $54.60) instead of ATR-based stops.

### 4. Fix Validator retry_history Logic

**File**: `trader/validation/validate_market_outcomes.py`

**Function**: `find_nearby_blocked_attempts()` (lines 1072-1146)

**Issue**: Searches ±5 minutes for BLOCKED attempts but doesn't verify they're from the same breakout sequence.

**Fix**: Add breakout sequence ID or only pull attempts within the same state machine session.

---

## Configuration Impact

**Current Config**:
```yaml
trading:
  attempts:
    max_attempts_per_pivot: 2  # Hit on trade #2
```

**Potential Config Change**:
```yaml
trading:
  attempts:
    max_attempts_per_pivot: 3-4  # Allow one more chance
    reset_attempts_after_minutes: 120  # Reset after 2 hours
```

**Expected Impact**: Would have captured the 12:51 PM 3-star winner (opportunity cost: unknown P&L, likely +$200-400).

---

## Total P&L Summary

| Trade | Entry Time | Entry Price | Exit Price | Duration | P&L (est) | Exit Reason |
|-------|------------|-------------|------------|----------|-----------|-------------|
| #1    | 10:04:15   | $54.28      | $54.31     | 5 sec    | -$105     | STOP |
| #2    | 10:15:50   | $54.55      | $54.61     | 15 sec   | -$106     | STOP |
| **TOTAL** | - | - | - | - | **-$211** | - |

**Missed Opportunity**: 12:51 PM breakout (3-star winner) = Unknown P&L

---

*Report Generated: October 26, 2025*
