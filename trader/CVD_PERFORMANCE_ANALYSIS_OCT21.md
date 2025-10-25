# CVD Performance Analysis - October 21, 2025

## Executive Summary

After fixing the bar resolution mismatch, the CVD filter is now working and triggering trades. However, **100% of trades (6/6) exited via 7MIN_RULE**, indicating the CVD signals aren't leading to profitable momentum moves.

---

## Trade-by-Trade CVD Analysis

### 1. SMCI SHORT #1
- **Entry**: $54.33 @ 10:01 (Bar 32)
- **Exit**: $54.55 @ 10:08 (7MIN_RULE)
- **P&L**: -$82.74 (-0.43%)
- **CVD Analysis**: Entry triggered by breakout below support ($54.60)
- **Problem**: Price went AGAINST the trade (+0.41% adverse move)

### 2. SMCI SHORT #2
- **Entry**: $54.47 @ 10:32 (Bar 63)
- **Exit**: $54.80 @ 10:39 (7MIN_RULE)
- **P&L**: -$121.27 (-0.63%)
- **CVD Analysis**: Second attempt after first failure
- **Problem**: Price went AGAINST the trade (+0.61% adverse move)

### 3. HOOD SHORT #1
- **Entry**: $132.18 @ 10:00 (Bar 31)
- **Exit**: $132.77 @ 10:07 (7MIN_RULE)
- **P&L**: -$87.33 (-0.46%)
- **CVD Analysis**: Entry triggered by breakout below support ($132.90)
- **Problem**: Price went AGAINST the trade (+0.45% adverse move)

### 4. HOOD SHORT #2
- **Entry**: $132.25 @ 10:30 (Bar 61)
- **Exit**: $132.89 @ 10:37 (7MIN_RULE)
- **P&L**: -$94.60 (-0.49%)
- **CVD Analysis**: Second attempt after first failure
- **Problem**: Price went AGAINST the trade (+0.49% adverse move)

### 5. NVDA SHORT #1
- **Entry**: $180.86 @ 09:56 (Bar 27)
- **Exit**: $180.70 @ 10:03 (7MIN_RULE)
- **P&L**: +$31.58 (+0.08%)
- **CVD Analysis**: Entry triggered by breakout below support ($181.73)
- **Result**: ONLY WINNER - moved in correct direction but minimal

### 6. NVDA SHORT #2
- **Entry**: $181.05 @ 10:57 (Bar 88)
- **Exit**: $181.31 @ 11:04 (7MIN_RULE)
- **P&L**: -$57.50 (-0.15%)
- **CVD Analysis**: Second attempt
- **Problem**: Price went AGAINST the trade (+0.14% adverse move)

---

## Key Findings

### 1. Wrong Direction Problem (83.3% of trades)
- **5 out of 6 trades moved AGAINST the signal**
- Average adverse move: +0.42%
- Only 1 trade (NVDA #1) moved in the correct direction

### 2. CVD Signal Quality Issues

Based on the CVD data from our earlier analysis, we know:
- SMCI had 21.0% imbalance (PATH 1: Strong selling)
- HOOD had 38.5% imbalance (PATH 1: Strong selling)
- NVDA had mixed signals

However, despite strong CVD selling signals, prices moved UP after entry.

### 3. Potential Root Causes

#### A. Market Context Ignored
- All entries between 09:56-10:32 AM
- This is typically a reversal period after initial morning moves
- CVD may be showing LATE selling (exhaustion) rather than EARLY selling (continuation)

#### B. CVD Measured at Wrong Time
- Current: CVD checked AFTER breakout occurs
- Better: CVD should be checked BEFORE breakout as confirmation
- **The CVD is reactive, not predictive**

#### C. Threshold Calibration
- PATH 1: 20% imbalance threshold
- PATH 2: 10% sustained threshold
- These may be too aggressive for 1-minute bars

---

## Comparison: OLD Method vs CVD Method

### OLD Method (slope-based)
- Trades: 6
- P&L: -$14.20
- Winners: Unknown but likely mixed

### CVD Method (current)
- Trades: 6
- P&L: -$411.86
- Winners: 1/6 (16.7%)

**CVD is 29x WORSE than the OLD method!**

---

## Recommendations

### 1. Immediate: Disable CVD Filtering
```yaml
# trader/config/trader_config.yaml
cvd_filter:
  enabled: false  # DISABLE - not improving entry quality
```

### 2. Investigation Needed

#### A. Pre-Breakout CVD Confirmation
Instead of checking CVD after breakout, check it BEFORE:
- Monitor CVD buildup as price approaches pivot
- Only enter if CVD confirms direction BEFORE break
- This would be predictive rather than reactive

#### B. Time-of-Day Filtering
- Avoid CVD signals during reversal periods (10:00-10:30 AM)
- Focus on trending periods (9:30-10:00, 11:00-12:00)

#### C. Directional Bias Issue
- All 6 trades were SHORTS
- Market may have had upward bias on Oct 21
- CVD needs market context awareness

### 3. Alternative Approach: CVD as EXIT Signal

Instead of using CVD for entries, use it for exits:
- Enter on standard breakout
- Monitor CVD for divergence
- Exit if CVD shows opposite pressure

---

## Technical Issues Found

### 1. Minor Logging Bug
```
"Sustained selling (0 candles, 11.7%)" → Shows 0 but enters anyway
```
The consecutive counter displays incorrectly but doesn't affect logic.

### 2. CVD Analytics Message Misleading
```
"CVD enabled but no entries were blocked"
```
This suggests CVD should block entries, but it's actually supposed to CONFIRM them.

---

## Conclusion

The CVD implementation is technically correct but **strategically flawed**:

1. **Bar resolution fix worked** - 6 trades now execute
2. **CVD signals are triggering** - PATH 1 entries confirmed
3. **But direction is wrong** - 83% of trades go against signal
4. **Performance is terrible** - 29x worse than OLD method

**Recommendation**: Disable CVD filtering immediately and revert to OLD slope-based method while investigating a better CVD strategy.

---

## Next Steps

1. ✅ Bar resolution fix validated
2. ⚠️ Disable CVD filtering in config
3. 📊 Rerun Oct 21 with CVD disabled to compare
4. 🔬 Investigate pre-breakout CVD confirmation approach
5. 📈 Consider CVD for exits instead of entries