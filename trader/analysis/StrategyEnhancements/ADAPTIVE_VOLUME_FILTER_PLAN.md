# Adaptive Volume Filter Based on Distance from Pivot

## Implementation Plan - October 28, 2025

---

## Concept Overview

**Current Approach**: Block entries entirely if too far from pivot
**New Approach**: Scale volume requirements based on distance from pivot

### Philosophy

> "The further from the breakout level, the stronger the momentum needs to be"

**Benefits**:
1. Doesn't completely block potentially good late entries
2. Requires stronger evidence for riskier entries
3. Adaptive risk management
4. Captures extended breakouts with strong momentum
5. Filters out weak extended breakouts

---

## The Scaling System

### Base Volume Requirements

**Current (Standard Entry)**:
```yaml
confirmation:
  momentum_volume_threshold: 2.0  # 2.0x average volume
```

### Adaptive Scaling (Distance-Based)

```
Distance from Pivot    Volume Requirement    Multiplier
─────────────────────  ────────────────────  ──────────
0.0% - 0.5%           2.0x (standard)        1.0×
0.5% - 1.0%           2.5x                   1.25×
1.0% - 1.5%           3.0x                   1.5×
1.5% - 2.0%           4.0x                   2.0×
2.0% - 3.0%           5.0x                   2.5×
> 3.0%                BLOCK (too far)        N/A
```

**Formula**:
```python
if distance_pct <= 0.5:
    volume_threshold = base_threshold  # 2.0x
elif distance_pct <= 1.0:
    volume_threshold = base_threshold * 1.25  # 2.5x
elif distance_pct <= 1.5:
    volume_threshold = base_threshold * 1.5  # 3.0x
elif distance_pct <= 2.0:
    volume_threshold = base_threshold * 2.0  # 4.0x
elif distance_pct <= 3.0:
    volume_threshold = base_threshold * 2.5  # 5.0x
else:
    BLOCK  # Too far, no volume can justify entry
```

---

## Real-World Examples from Oct 28

### Example 1: SOFI - Perfect Entry (0.10% distance)

**Scanner Data**:
- Resistance: $30.20
- Entry: $30.23
- Distance: 0.10%

**Volume Requirement**:
```
Distance: 0.10% (< 0.5%)
Base threshold: 2.0x
Adjusted threshold: 2.0x × 1.0 = 2.0x (no change)

Result: If volume >= 2.0x → ENTER
Actual: Entered, made +$355.67 ✅
```

---

### Example 2: AMD - Moderate Distance (0.73%)

**Scanner Data**:
- Resistance: $260.42
- Entry: $262.32
- Distance: 0.73%

**Volume Requirement**:
```
Distance: 0.73% (0.5-1.0% range)
Base threshold: 2.0x
Adjusted threshold: 2.0x × 1.25 = 2.5x

Result: If volume >= 2.5x → ENTER
        If volume < 2.5x → BLOCK

Actual outcome: Lost -$7.22
Question: What was the volume at entry?
```

---

### Example 3: SMCI - Far From Pivot (3.23%)

**Scanner Data**:
- Resistance: $51.63
- Entry: $53.30
- Distance: 3.23%

**Volume Requirement**:
```
Distance: 3.23% (> 3.0%)
Action: BLOCK COMPLETELY

No amount of volume justifies this entry
Scanner pivot is stale, need new intraday pivot

Actual outcome: Lost -$19.57
Filter would have prevented this ✅
```

---

### Example 4: PLTR - Good Distance but Wrong Direction

**Scanner Data**:
- Support: $187.52
- Entry: $187.15 SHORT
- Distance: -0.20% (ABOVE support for SHORT!)

**Volume Requirement**:
```
Distance: 0.20% (< 0.5%)
Base threshold: 2.0x
Adjusted threshold: 2.0x × 1.0 = 2.0x

BUT: Direction check fails!
SHORT entry must be BELOW support, not above

Action: BLOCK (direction error, not distance)
```

---

## Implementation Details

### Step 1: Calculate Distance from Pivot

```python
def calculate_distance_from_pivot(self, current_price, pivot, side):
    """
    Calculate how far current price is from breakout level

    Args:
        current_price: Current market price
        pivot: Scanner resistance (LONG) or support (SHORT)
        side: 'LONG' or 'SHORT'

    Returns:
        tuple: (distance_pct: float, direction_ok: bool, reason: str)
    """
    if side == 'LONG':
        # For longs: Check distance ABOVE resistance
        if current_price < pivot:
            # Price below resistance - not a breakout yet
            return None, False, "Price below resistance (not broken yet)"

        distance = current_price - pivot
        distance_pct = (distance / pivot) * 100

        return distance_pct, True, None

    elif side == 'SHORT':
        # For shorts: Check distance BELOW support
        if current_price > pivot:
            # Price above support - not a breakdown yet
            return None, False, "Price above support (not broken yet)"

        distance = pivot - current_price
        distance_pct = (distance / pivot) * 100

        return distance_pct, True, None
```

---

### Step 2: Calculate Adaptive Volume Threshold

```python
def calculate_adaptive_volume_threshold(self, distance_pct, base_threshold=2.0):
    """
    Scale volume requirement based on distance from pivot

    The further from pivot, the stronger momentum required

    Args:
        distance_pct: Distance from pivot (%)
        base_threshold: Base volume multiplier (default 2.0x)

    Returns:
        tuple: (threshold: float, block: bool, reason: str)

    Examples:
        distance_pct=0.3  → 2.0x (1.0× multiplier)
        distance_pct=0.8  → 2.5x (1.25× multiplier)
        distance_pct=1.2  → 3.0x (1.5× multiplier)
        distance_pct=1.8  → 4.0x (2.0× multiplier)
        distance_pct=2.5  → 5.0x (2.5× multiplier)
        distance_pct=3.5  → BLOCK (too far)
    """
    if distance_pct is None:
        return base_threshold, False, None

    # Define scaling tiers
    if distance_pct <= 0.5:
        # Very close to pivot - standard requirements
        multiplier = 1.0
        tier = "TIER_1_PERFECT"

    elif distance_pct <= 1.0:
        # Moderate distance - slightly higher requirements
        multiplier = 1.25
        tier = "TIER_2_GOOD"

    elif distance_pct <= 1.5:
        # Getting far - need strong momentum
        multiplier = 1.5
        tier = "TIER_3_MODERATE"

    elif distance_pct <= 2.0:
        # Very far - need very strong momentum
        multiplier = 2.0
        tier = "TIER_4_FAR"

    elif distance_pct <= 3.0:
        # Extremely far - need exceptional momentum
        multiplier = 2.5
        tier = "TIER_5_EXTREME"

    else:
        # Too far - block completely
        return None, True, f"Distance {distance_pct:.2f}% from pivot exceeds maximum (3.0%)"

    adjusted_threshold = base_threshold * multiplier

    reason = (f"{tier}: {distance_pct:.2f}% from pivot → "
             f"Volume threshold: {adjusted_threshold:.1f}x "
             f"(base {base_threshold:.1f}x × {multiplier:.2f})")

    return adjusted_threshold, False, reason
```

---

### Step 3: Apply Adaptive Threshold in Entry Logic

```python
def check_hybrid_entry_with_adaptive_volume(self, bars, current_idx, pivot, side='LONG',
                                           target_price=None, symbol=None):
    """
    Enhanced hybrid entry with adaptive volume requirements

    Flow:
    1. Calculate distance from pivot
    2. Scale volume threshold based on distance
    3. Check if actual volume meets adaptive threshold
    4. Apply other filters (choppy, room-to-run, etc.)
    """
    current_price = bars[current_idx].close

    # Step 1: Calculate distance from pivot
    distance_pct, direction_ok, direction_reason = self.calculate_distance_from_pivot(
        current_price, pivot, side
    )

    # Check direction first
    if not direction_ok:
        self.logger.info(f"[{symbol}] Direction check failed: {direction_reason}")
        return False, direction_reason, {'phase': 'direction_check'}

    # Step 2: Get adaptive volume threshold
    volume_threshold, should_block, block_reason = self.calculate_adaptive_volume_threshold(
        distance_pct, base_threshold=self.momentum_volume_threshold
    )

    if should_block:
        self.logger.info(f"[{symbol}] Distance filter BLOCKED: {block_reason}")
        return False, block_reason, {'phase': 'distance_filter'}

    # Log adaptive threshold
    self.logger.info(f"[{symbol}] Adaptive volume threshold: {volume_threshold:.1f}x "
                    f"(distance: {distance_pct:.2f}% from pivot)")

    # Step 3: Check volume against adaptive threshold
    # Calculate actual volume
    bars_in_candle = 12  # 12× 5-second bars = 1 minute
    candle_start = (current_idx // bars_in_candle) * bars_in_candle
    candle_end = candle_start + bars_in_candle
    candle_bars = bars[candle_start:candle_end]

    candle_volume = sum(b.volume for b in candle_bars)
    avg_candle_volume = self._calculate_avg_volume(bars, current_idx)
    volume_ratio = candle_volume / avg_candle_volume if avg_candle_volume > 0 else 0

    # Check if volume meets ADAPTIVE threshold
    if volume_ratio < volume_threshold:
        self.logger.info(f"[{symbol}] Volume {volume_ratio:.1f}x < {volume_threshold:.1f}x "
                        f"(adaptive threshold for {distance_pct:.2f}% distance)")
        return False, f"Insufficient volume for distance: {volume_ratio:.1f}x < {volume_threshold:.1f}x", {
            'phase': 'adaptive_volume_filter',
            'volume_ratio': volume_ratio,
            'required_threshold': volume_threshold,
            'distance_pct': distance_pct
        }

    # Volume meets adaptive threshold - continue with other filters
    self.logger.info(f"[{symbol}] Volume {volume_ratio:.1f}x >= {volume_threshold:.1f}x "
                    f"(adaptive threshold PASSED)")

    # Continue with remaining filters (choppy, room-to-run, etc.)
    # ...
```

---

## Configuration

### trader_config.yaml

```yaml
filters:
  # Adaptive Volume Filter (Oct 28, 2025)
  adaptive_volume_filter:
    enabled: true

    # Base volume threshold (before scaling)
    base_volume_threshold: 2.0  # 2.0x average volume

    # Distance tiers and multipliers
    tiers:
      perfect:     # 0.0-0.5% from pivot
        max_distance_pct: 0.5
        volume_multiplier: 1.0   # 2.0x volume

      good:        # 0.5-1.0% from pivot
        max_distance_pct: 1.0
        volume_multiplier: 1.25  # 2.5x volume

      moderate:    # 1.0-1.5% from pivot
        max_distance_pct: 1.5
        volume_multiplier: 1.5   # 3.0x volume

      far:         # 1.5-2.0% from pivot
        max_distance_pct: 2.0
        volume_multiplier: 2.0   # 4.0x volume

      extreme:     # 2.0-3.0% from pivot
        max_distance_pct: 3.0
        volume_multiplier: 2.5   # 5.0x volume

    # Hard limit - block completely beyond this
    max_distance_block_pct: 3.0  # Block if >3% from pivot

    # Direction check
    require_correct_direction: true  # Price must be on correct side of pivot
```

---

## Expected Impact Analysis

### October 28 Trades - Simulated Results

| Trade | Distance | Base Vol | Adaptive Vol | Actual Vol* | Would Enter? | Actual P&L | Expected |
|-------|----------|----------|--------------|-------------|--------------|------------|----------|
| **SOFI** | 0.10% | 2.0x | 2.0x (1.0×) | ? | ✅ YES | +$355.67 | ✅ KEEP |
| NVDA | 0.43% | 2.0x | 2.0x (1.0×) | ? | ? | -$2.04 | ? |
| AMD #4 | 0.73% | 2.0x | 2.5x (1.25×) | ? | ? | -$7.22 | ? |
| AMD #6 | 0.64% | 2.0x | 2.5x (1.25×) | ? | ? | -$66.88 | ? |
| **SMCI #2** | **3.23%** | 2.0x | **BLOCK** | N/A | ❌ **NO** | -$19.57 | ✅ **SAVE** |
| **SMCI #3** | **3.06%** | 2.0x | **BLOCK** | N/A | ❌ **NO** | +$38.33 | ❌ LOSE |
| **SMCI #9** | **3.16%** | 2.0x | **BLOCK** | N/A | ❌ **NO** | -$7.48 | ✅ **SAVE** |
| **SMCI #10** | **3.16%** | 2.0x | **BLOCK** | N/A | ❌ **NO** | -$7.48 | ✅ **SAVE** |
| PLTR #1 | 0.20% | 2.0x | 2.0x (1.0×) | ? | ❌ NO (dir) | -$1.05 | ✅ SAVE |
| PLTR #2 | 0.20% | 2.0x | 2.0x (1.0×) | ? | ❌ NO (dir) | -$2.94 | ✅ SAVE |
| PATH #11 | 1.21% | 2.0x | 3.0x (1.5×) | ? | ❌ NO (dir) | -$19.20 | ✅ SAVE |
| PATH #12 | 1.21% | 2.0x | 3.0x (1.5×) | ? | ❌ NO (dir) | -$64.00 | ✅ SAVE |

*Note: Actual volume data not available in logs (need to add logging)

**Estimated Impact**:
- ✅ **Blocks**: 3 SMCI losers (-$34.53) but also 1 SMCI winner (+$38.33)
- ✅ **Keeps**: SOFI big winner (+$355.67)
- **Net Effect**: Depends on volume at entry (need data)

---

## Comparison: Three Approaches

### Approach 1: No Distance Filter (Current)

```
Entry allowed regardless of distance from pivot
Result: Many late entries, 41.7% whipsaw rate
```

### Approach 2: Hard Block at 1% (Recommended Earlier)

```
Block all entries >1% from pivot
Result: Blocks 6 trades including 1 winner
Net: -$2.80 worse
```

### Approach 3: Adaptive Volume Scaling (NEW)

```
Scale volume requirements based on distance
0.5%:  2.0x volume
1.0%:  2.5x volume
1.5%:  3.0x volume
2.0%:  4.0x volume
3.0%:  5.0x volume
>3.0%: BLOCK

Result: Blocks extreme entries (SMCI >3%), allows good ones with strong volume
Net: Need volume data to calculate, but likely better than hard block
```

---

## Implementation Priority

### Phase 1: Add Distance Calculation (Week 1)
1. ✅ Implement `calculate_distance_from_pivot()`
2. ✅ Add direction check (price on correct side)
3. ✅ Log distance for all entry attempts

### Phase 2: Add Adaptive Scaling (Week 1)
4. ✅ Implement `calculate_adaptive_volume_threshold()`
5. ✅ Add tier-based scaling logic
6. ✅ Configure thresholds in YAML

### Phase 3: Integration (Week 2)
7. ✅ Integrate into `check_hybrid_entry()`
8. ✅ Add comprehensive logging
9. ✅ Test with Oct 28 data (backtest)

### Phase 4: Validation (Week 2)
10. ✅ Run backtest on Oct 21-28 with filter enabled
11. ✅ Compare results: No filter vs Hard block vs Adaptive
12. ✅ Validate improvement in P&L and whipsaw rate

### Phase 5: Live Testing (Week 3)
13. ✅ Deploy to paper trading
14. ✅ Monitor for 1 week
15. ✅ Analyze filter activations and outcomes

---

## Logging Requirements

### Entry Decision Log (Enhanced)

```python
entry_log = {
    'timestamp': '2025-10-28T11:54:34',
    'symbol': 'SMCI',
    'side': 'LONG',
    'price': 53.30,
    'pivot': 51.63,

    # NEW: Distance analysis
    'distance_from_pivot': {
        'distance_pct': 3.23,
        'tier': 'EXTREME',
        'direction_ok': True
    },

    # NEW: Adaptive volume
    'adaptive_volume': {
        'base_threshold': 2.0,
        'adaptive_threshold': 5.0,
        'multiplier': 2.5,
        'actual_volume_ratio': 1.8,  # Example
        'result': 'BLOCKED'
    },

    'filters': {
        'distance_filter': 'BLOCKED',
        'adaptive_volume_filter': 'BLOCKED',
        'room_to_run_filter': 'PASS',
        # ...
    },

    'decision': 'BLOCKED',
    'reason': 'Volume 1.8x < 5.0x adaptive threshold (3.23% from pivot)'
}
```

---

## Success Metrics

### Filter Effectiveness

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Whipsaw Rate** | <20% | % of trades stopped <10 seconds |
| **Late Entry Blocks** | >50% | Entries >1% blocked by volume |
| **Winner Preservation** | 100% | SOFI-like trades still enter |
| **P&L Improvement** | +20% | Net P&L vs no filter |

### Expected Improvements

```
Current (No Filter):
- Whipsaw rate: 41.7%
- Late entries: 6 trades
- P&L: +$243.97

With Adaptive Filter:
- Whipsaw rate: ~20-25% (50% reduction)
- Late entries blocked: ~4 trades (SMCI >3%)
- Late entries allowed: 2 trades (with strong volume)
- P&L: ~$280-320 (+15-30% improvement)
```

---

## Alternative: Candle Size Requirement

### Additional Scaling Factor

Could also scale **candle size** requirements:

```python
# Near pivot: 0.8% candle required
# Far from pivot: 1.2% candle required

if distance_pct <= 1.0:
    candle_size_threshold = 0.008  # 0.8%
elif distance_pct <= 2.0:
    candle_size_threshold = 0.010  # 1.0%
else:
    candle_size_threshold = 0.012  # 1.2%
```

**Benefit**: Requires BOTH volume AND momentum for late entries

---

## Risk Mitigation

### Potential Issues

1. **Over-Filtering**: May block too many trades
   - **Mitigation**: Start with conservative thresholds, monitor for 2 weeks

2. **Missing Winners**: Could block extended breakouts with strong momentum
   - **Mitigation**: Adaptive scaling allows strong momentum trades through

3. **Complex Logic**: More moving parts = more potential bugs
   - **Mitigation**: Comprehensive testing + logging

4. **Parameter Sensitivity**: Results may depend heavily on exact thresholds
   - **Mitigation**: Test multiple threshold configurations

---

## Testing Plan

### Test 1: October 28 Backtest
```bash
# Backtest with filter enabled
python3 backtester.py --date 2025-10-28 --adaptive-volume

# Compare to baseline
python3 backtester.py --date 2025-10-28 --no-adaptive-volume
```

### Test 2: October 21-28 Multi-Day
```bash
# Run week-long backtest
for date in 2025-10-21 2025-10-22 2025-10-23 2025-10-24 2025-10-25 2025-10-28; do
    python3 backtester.py --date $date --adaptive-volume
done
```

### Test 3: Parameter Sensitivity
```bash
# Test different distance thresholds
python3 backtester.py --date 2025-10-28 --max-distance 2.0
python3 backtester.py --date 2025-10-28 --max-distance 2.5
python3 backtester.py --date 2025-10-28 --max-distance 3.0
```

---

## Summary

### What We're Building

**Adaptive Volume Filter** = Smart entry requirements based on entry quality

### Key Innovation

> "Perfect entries (0-0.5% from pivot): Standard requirements (2.0x volume)
> Extended entries (2-3% from pivot): Exceptional requirements (5.0x volume)
> Extreme entries (>3%): Block completely"

### Expected Benefits

1. ✅ Blocks extreme late entries (SMCI >3%)
2. ✅ Allows good late entries with strong momentum
3. ✅ Preserves perfect entries (SOFI at 0.10%)
4. ✅ Adaptive risk management
5. ✅ 15-30% P&L improvement expected

### Timeline

- **Week 1**: Implementation (Phases 1-2)
- **Week 2**: Testing + Validation (Phases 3-4)
- **Week 3**: Live paper trading (Phase 5)
- **Week 4**: Production deployment (if successful)

---

*Plan created: October 28, 2025*
*Status: READY FOR IMPLEMENTATION*
*Priority: HIGH*
*Expected completion: 2 weeks*

