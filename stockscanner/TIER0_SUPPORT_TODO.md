# Tier 0 Support Analysis - TODO

## Current Status

**✅ Implemented:** Tier 0 hourly analysis for RESISTANCE (long setups)
**❌ Missing:** Tier 0 hourly analysis for SUPPORT (short setups)

## Why This Matters

Short setups need the same precision as long setups:
- Daily support may be stale (e.g., support from 10 days ago)
- Intraday bounces show where buyers are defending TODAY
- Gap-downs can invalidate daily support levels
- Tight consolidations create immediate support levels

## What Needs to Be Added

### 1. Support Detection in `check_tier0_hourly()`

Currently the function only analyzes resistance. It needs to also check for support using **bounces** instead of rejections:

```python
# Current (RESISTANCE only):
rejections = []  # Close 0.5%+ BELOW high

# Needed (SUPPORT analysis):
bounces = []     # Close 0.5%+ ABOVE low
```

### 2. Five Criteria for Support (Mirror of Resistance)

#### Criterion 1: Multiple Intraday Bounces
```python
# Bounce signature: close 0.5%+ above low
for idx, bar in df_hourly.iterrows():
    wick_size = bar['close'] - bar['low']  # Opposite of rejection
    wick_pct = (wick_size / bar['close']) * 100

    if wick_pct >= 0.5:
        bounces.append(bar['low'])  # Collect lows, not highs

# Find cluster of bounces
if len(bounces) >= 2:
    median_low = sorted(bounces)[len(bounces) // 2]
    cluster = [b for b in bounces if abs(b - median_low) <= 2.0]

    if len(cluster) >= 2:
        support_result = {
            'activated': True,
            'level': median_low,
            'reason': f'Bounced {len(cluster)}x intraday at ${median_low:.2f}',
            'confidence': 'HIGH',
            'touches': len(cluster),
            'criterion': 'Multiple Bounces'
        }
```

#### Criterion 2: Fresh Intraday Low
```python
# If TODAY's low is >2% different from daily support
daily_vs_hourly_pct = abs(todays_low - daily_support) / daily_support * 100

if daily_vs_hourly_pct > 2.0:
    support_result = {
        'activated': True,
        'level': todays_low,
        'reason': f"TODAY's low ${todays_low:.2f} (daily stale by {daily_vs_hourly_pct:.1f}%)",
        'confidence': 'MEDIUM',
        'criterion': 'Fresh Intraday Low'
    }
```

#### Criterion 3: SMA Confluence at Intraday Level
```python
# Check if hourly support aligns with SMA (within 1%)
for sma_name, sma_price in sma_levels.items():
    distance_pct = abs(todays_low - sma_price) / sma_price * 100
    if distance_pct < 1.0:
        # Check if daily support has NO SMA confluence
        if not daily_has_sma_support:
            support_result = {
                'activated': True,
                'level': sma_price,
                'reason': f'Intraday at {sma_name} ${sma_price:.2f} (confluence)',
                'confidence': 'HIGH',
                'criterion': 'SMA Confluence'
            }
```

#### Criterion 4: Tight Intraday Consolidation
```python
# If TODAY's range <2% and lower boundary tested 2+ times
if range_pct < 2.0:
    boundary_touches = sum(1 for _, bar in df_hourly.iterrows()
                         if abs(bar['low'] - todays_low) < 1.0)

    if boundary_touches >= 2:
        support_result = {
            'activated': True,
            'level': todays_low,
            'reason': f'Tight consolidation, tested {boundary_touches}x',
            'confidence': 'HIGH',
            'criterion': 'Tight Consolidation'
        }
```

#### Criterion 5: Gap-Down Case
```python
# If stock gapped down >3%
prev_close = df_daily.iloc[-2]['close']
todays_open = df_hourly.iloc[0]['open']
gap_pct = (todays_open - prev_close) / prev_close * 100

if gap_pct < -3.0:  # Negative gap (gap down)
    support_result = {
        'activated': True,
        'level': todays_low,
        'reason': f'Gap down {abs(gap_pct):.1f}% (daily support obsolete)',
        'confidence': 'MEDIUM',
        'criterion': 'Gap Adjustment'
    }
```

### 3. Return Structure Change

Function needs to return BOTH resistance and support:

```python
return {
    'resistance': {
        'activated': True/False,
        'level': price,
        'reason': string,
        'confidence': 'HIGH'/'MEDIUM',
        'touches': count,
        'criterion': string
    },
    'support': {
        'activated': True/False,
        'level': price,
        'reason': string,
        'confidence': 'HIGH'/'MEDIUM',
        'touches': count,
        'criterion': 'Multiple Bounces'
    }
}
```

### 4. Call Site Updates in `scan_symbol()`

Currently:
```python
tier0 = self.check_tier0_hourly(symbol, daily_resistance, current_price, df)

if tier0['activated']:  # Only checks resistance
    resistance = tier0['resistance']
    # ... use hourly resistance
```

Needs to become:
```python
tier0 = self.check_tier0_hourly(symbol, daily_resistance, daily_support, current_price, df)

# Check RESISTANCE
if tier0['resistance']['activated']:
    resistance = tier0['resistance']['level']
    resistance_tier = 'TIER_0_HOURLY'
    resistance_reason = tier0['resistance']['reason']
    # ... etc

# Check SUPPORT
if tier0['support']['activated']:
    support = tier0['support']['level']
    support_tier = 'TIER_0_HOURLY'
    support_reason = tier0['support']['reason']
    # ... etc
else:
    # Use daily support (current logic)
    support_tier = 'DAILY'
    # ... etc
```

### 5. Output Fields to Add

Each stock result should include:

```python
return {
    # ... existing fields ...

    # NEW: Support tier fields (mirror resistance)
    'support_tier': 'TIER_0_HOURLY' or 'DAILY',
    'support_confidence': 'HIGH'/'MEDIUM',
    'daily_support': daily_support_value,
    'support_touches_daily': daily_touch_count,
    'support_touches_hourly': hourly_touch_count,
    'support_reason': "Bounced 3x intraday at $425.50",
    'support_override_note': "Hourly override (Multiple Bounces) - daily $400.56"
}
```

### 6. Display Updates

Console output should show support tier:

```
🎯 KEY LEVELS:
  Resistance: $438.81 (+1.3% away) [TIER_0_HOURLY]
  Confidence: HIGH

  Support: $432.50 (-0.2% below) [TIER_0_HOURLY]  ← NEW
  Confidence: HIGH                                  ← NEW
  Daily reference: $400.56                          ← NEW
```

### 7. Statistics Tracking

Tier 0 stats should track BOTH:

```python
self.tier0_stats = {
    'resistance_activated': 0,
    'resistance_skipped': 0,
    'support_activated': 0,
    'support_skipped': 0,
    'errors': 0
}
```

Display:
```
TIER 0 ANALYSIS STATS
Tier 0 Resistance: 6 stocks (6 activated)
Tier 0 Support: 4 stocks (4 activated)
Daily Baseline: 2 stocks
Errors: 0
```

## Priority

**Medium Priority for current usage:**
- Scanner is primarily used for LONG setups (resistance is most important)
- Support is still useful but less critical for breakout trading
- Daily support is "good enough" for most cases

**However:**
- Should be implemented for completeness
- Critical if you start trading SHORT setups
- Provides symmetry and professional polish
- Gap-down scenarios benefit greatly from hourly support

## Estimated Implementation Time

- **Code changes:** ~1-2 hours
- **Testing:** ~30 minutes
- **Total:** ~2 hours

## Current Workaround

For now, the scanner V2:
- ✅ Has precise hourly RESISTANCE for longs
- ⚠️ Uses daily SUPPORT (less precise but functional)
- Works well for long-biased trading
- Should be enhanced before trading shorts heavily

---

**Decision:** Do you want me to implement Tier 0 support analysis now, or is the current resistance-only version sufficient for your needs?
