# Resistance Detection Gap Analysis - TSLA $440 Case Study

**Date**: October 16, 2025
**Issue**: Both V1 and V2 scanners miss TSLA's actual resistance at $440, instead reporting lower levels ($447 for V1, $434 for V2)

---

## Executive Summary

**Root Cause**: Both scanners rely on **rejection signatures** (price closes well below highs with wicks), which misses **"soft" resistance zones** where price repeatedly hits the same level but closes near the high without dramatic rejection wicks.

**Real-World Example - TSLA**:
- **User Observation**: "Today's high was $440, Monday's high is around $436.8, and Friday's high is $440"
- **Actual Pattern**: Multiple days testing $440 zone = clear resistance
- **V1 Scanner**: Reports $447.37 (too high, uses 10-day 95th percentile of closes)
- **V2 Scanner**: Reports $434.20 (too low, clusters lower rejections with strong wicks)

---

## Detailed Analysis

### V1 Scanner Behavior (Daily Bars)

**Data Used**: 30 days of daily bars

**Resistance Calculation Logic** (lines 211-232):
```python
resistance_5d_spike = df['high'].iloc[-5:].max()     # $443.13
resistance_5d_close = df['close'].iloc[-5:].max()    # $435.47
resistance_10d_close = df['close'].iloc[-10:].quantile(0.95)  # $447.37

# Spike detection: if spike >1% above closing high
if (spike - close) / close > 0.01:
    resistance = max(5d_close, 10d_close)  # Uses $447.37
```

**Why It Missed $440**:

| Date | High | Close | Wick | In $440 Zone? |
|------|------|-------|------|---------------|
| Oct 2 | $479.38 | $439.35 | $40.03 (9.1%) | ✅ |
| Oct 3 | $446.77 | $430.00 | $16.77 (3.9%) | ✅ |
| Oct 6 | $454.97 | $453.93 | $1.04 (0.2%) | ✅ |
| Oct 7 | $456.03 | $437.00 | $19.03 (4.4%) | ✅ |
| Oct 8 | $441.33 | $437.96 | $3.37 (0.8%) | ✅ |
| Oct 10 | $443.13 | $408.00 | $35.13 (8.6%) | ✅ |
| Oct 15 | $440.51 | $434.41 | $6.10 (1.4%) | ✅ |

**7 out of 10 days tested $440+ zone**, but:
- 5-day spike high = $443.13 (Oct 10)
- Spike detected (1.76% above closing high)
- Algorithm switched to 10-day 95th percentile of **closes** = $447.37
- **Result**: Reported $447.37 (too high, +2.98% away)

**Problem**: Spike detection triggered by Oct 10's large wick, causing algorithm to use closing highs instead of actual highs. This overshot the real resistance.

---

### V2 Scanner Behavior (5-Day Hourly Bars)

**Data Used**: Last 5 trading days of hourly bars (28 bars total)

**Resistance Calculation Logic** - Criterion 1 (lines 136-162):
```python
# Find hourly bars with rejection signature (close 0.5%+ below high)
rejections = []
for bar in hourly_bars:
    wick_pct = (high - close) / close * 100
    if wick_pct >= 0.5:
        rejections.append(high)

# Cluster rejections within ±$2
median = sorted(rejections)[len // 2]
cluster = [r for r in rejections if abs(r - median) <= 2.0]

if len(cluster) >= 2:
    resistance = median
```

**What It Found**:

**Rejections Detected**: 17 hourly bars with 0.5%+ wicks

**Rejection Cluster**:
- Median: **$434.20**
- Cluster (±$2): 5 rejections at [$433.20, $434.15, $434.20, $435.11, $435.59]
- **Result**: Reported $434.20 (already broken, -0.05% away)

**$440 Zone Analysis** ($438-$442):

| Date/Time | High | Close | Wick | Rejection? |
|-----------|------|-------|------|------------|
| Oct 10 10:00 AM | $440.25 | $434.94 | $5.31 (1.22%) | ✅ YES |
| Oct 15 09:30 AM | $438.81 | $435.62 | $3.19 (0.73%) | ✅ YES |
| Oct 15 10:00 AM | $440.51 | $436.90 | $3.61 (0.83%) | ✅ YES |
| Oct 15 11:00 AM | $438.19 | $433.40 | $4.79 (1.11%) | ✅ YES |

**$440 zone had 4 rejection signatures!** So why wasn't it detected?

**Problem**: The clustering algorithm found the **median** of ALL 17 rejections was $434.20, which formed a tight cluster of 5 rejections. The $440 rejections were:
- Only 4 in total (vs 5 at $434)
- Spread across $438-$441 range
- Didn't form a tight enough cluster (>±$2 from median)
- Algorithm prioritized the tighter, lower cluster

---

## The Core Gap in Both Scanners

### What Both Scanners Require:
**REJECTION SIGNATURES** = Price closes significantly below high with visible wick

### What They Miss:
**"SOFT" RESISTANCE** = Multiple tests of same high level WITHOUT dramatic rejection wicks

**Real-World Pattern**:
```
$440 zone tested 7 times over 10 days (daily view)
$440 zone tested 4 times over 5 days (hourly view)

But some closes were NEAR the high:
- Oct 6: High $454.97, Close $453.93 (only 0.2% wick) ❌ Not counted as rejection
- Oct 8: High $441.33, Close $437.96 (only 0.8% wick) ❌ Not counted as rejection
- Oct 13: High $436.89, Close $435.47 (only 0.3% wick) ❌ Not counted as rejection

These bars TESTED resistance but didn't show dramatic rejection = MISSED
```

---

## Why This Matters

### User's Perspective:
"I see TSLA hitting $440 multiple times - that's clearly resistance"

### Scanner's Perspective:
"I see some bars with big wicks at $434 - that's the cluster"

### The Disconnect:
Traders recognize resistance when **price repeatedly fails to break higher**, even if it closes near the high. Scanners only recognize resistance when **price shows dramatic rejection** (large wicks).

**Example**:
- Price hits $440 and closes at $439 → Trader sees resistance, scanner sees "no rejection"
- Price hits $440 and closes at $432 → Both see resistance

---

## Proposed Solution

### Add New Criterion: "Multiple Highs at Same Level"

**Logic**:
1. Identify all bars (daily or hourly) that hit similar high levels (±1%)
2. **No rejection wick required**
3. If 3+ bars hit same zone, it's resistance
4. Use the highest level in that zone as resistance

**Pseudo-Code**:
```python
# Collect all highs
highs = [bar['high'] for bar in bars]

# Group into zones (±1%)
for candidate_high in sorted(highs, reverse=True):
    zone_highs = [h for h in highs if abs(h - candidate_high) / candidate_high < 0.01]

    if len(zone_highs) >= 3:
        # Found resistance zone!
        resistance = max(zone_highs)  # Use highest in zone
        break
```

**Applied to TSLA**:
- $440 zone (±1% = $436-$444)
- Highs in zone: [$440.25, $440.51, $438.81, $438.19, $441.33, $443.13, $436.89]
- Count: **7 bars** (well above 3 threshold)
- **Resistance**: $443.13 (highest in zone)

**Result**: Would correctly identify ~$440-443 as resistance zone

---

## Implementation Priority

### High Priority (V2 Scanner):
V2 is designed for precision and has tiered criteria system - should be augmented with "Multiple Highs" criterion

**Implementation**:
- Add as **Criterion 5** (after rejections, fresh highs, SMA confluence, consolidation)
- Require 3+ hourly bars in ±1% zone
- Use highest bar in zone as resistance
- Lower confidence than rejection-based detection

### Medium Priority (V1 Scanner):
V1 uses simpler statistical approach - could add as alternative to spike detection

**Implementation**:
- Before spike detection, check for "repeated highs" pattern
- If 3+ daily highs in ±1% zone, use that instead of quantile
- Fallback to current logic if no pattern found

---

## Expected Impact

### With Fix Applied to TSLA:
- **V1**: Would report ~$443 (actual tested high in $440 zone)
- **V2**: Would report ~$441 (consolidated view of hourly $440 tests)
- **User Observation**: ~$440 is resistance
- **Result**: ✅ Much closer alignment!

### General Benefits:
1. **Catches consolidation zones** (tight ranges without wicks)
2. **Detects supply zones** (price stalls but doesn't reject)
3. **More intuitive levels** (where price actually stopped, not where wicks appeared)
4. **Better trader alignment** (matches visual chart analysis)

---

## Testing Recommendations

1. **Implement "Multiple Highs" criterion** in V2 scanner
2. **Run on Oct 16th historical data** - verify TSLA now detects $440 zone
3. **Compare across multiple stocks** - ensure doesn't create false positives
4. **Validate with user** - "does this level match what you see on the chart?"
5. **Backtest historical scans** - measure improvement in resistance accuracy

---

## Conclusion

Both scanners missed TSLA's $440 resistance because they require **rejection signatures** (large wicks), but resistance can exist as **"soft" zones** where price repeatedly tests but closes near highs without dramatic rejection.

**The Fix**: Add criterion to detect "Multiple Highs at Same Level" - if 3+ bars test similar high (±1%), it's resistance regardless of wick size.

**Expected Outcome**: Scanners will catch both **hard rejections** (with wicks) AND **soft supply zones** (repeated tests), providing more complete and accurate resistance levels.

---

**Action Items**:
1. ✅ Diagnostic complete - gap identified
2. ⏳ Implement "Multiple Highs" criterion in V2
3. ⏳ Test on TSLA Oct 16th data
4. ⏳ Validate with user
5. ⏳ Consider adding to V1 scanner

**User Impact**: Resistance levels will better match what traders see visually on charts, improving scanner utility and trust.
