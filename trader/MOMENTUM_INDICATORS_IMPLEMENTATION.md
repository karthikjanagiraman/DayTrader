# Momentum Indicators Implementation Guide

## Overview

Added RSI and MACD momentum indicators to improve breakout validation and reduce false breakouts. Uses 5-minute IBKR bars directly instead of stitching 5-second bars.

**Status:** ✅ Module Created, Ready for Integration
**Date:** October 7, 2025

---

## Why Momentum Indicators?

### Problem Identified
Analysis of October 7 backtest showed **20% win rate** and **-$6,528 P&L** due to:
1. Weak breakouts qualifying as "momentum" entries
2. No RSI/MACD confirmation
3. Low volume breakouts (XPEV: 1.13x RVOL, JD: 0.5x RVOL)
4. Tiny candles with high volume bypassing validation

### Solution
Add RSI and MACD filters on **5-minute bars** to confirm:
- Directional bias (RSI > 50 for longs, < 50 for shorts)
- Momentum alignment (MACD line vs signal line)
- Strong momentum (RSI > 60 for longs, < 40 for shorts)

---

## Implementation Details

### Module Location
`/Users/karthik/projects/DayTrader/trader/strategy/momentum_indicators.py`

### Key Functions

#### 1. Fetch Bars from IBKR
```python
fetch_bars(ib, contract, bar_size='5 mins', lookback_bars=100)
fetch_5min_bars(ib, contract, lookback_bars=100)
fetch_1min_bars(ib, contract, lookback_bars=60)
```

**Why IBKR bars instead of stitching 5-sec bars?**
- ✅ More efficient (1 API call vs building candles)
- ✅ Cleaner data (IBKR-calculated OHLCV)
- ✅ Less code complexity
- ✅ No synchronization issues

#### 2. Calculate RSI
```python
calculate_rsi(bars, period=14)
```

**Settings:**
- Standard: `period=14` (balanced)
- Sensitive: `period=9` (faster signals)
- Returns: RSI value (0-100)

**Interpretation:**
- RSI > 70: Overbought
- RSI > 60: Strong bullish momentum
- RSI > 50: Bullish bias
- RSI < 50: Bearish bias
- RSI < 40: Strong bearish momentum
- RSI < 30: Oversold

#### 3. Calculate MACD
```python
calculate_macd(bars, fast=12, slow=26, signal=9)
```

**Settings:**
- Standard: `(12, 26, 9)` - Conservative
- Day Trading: `(3, 10, 16)` - More sensitive
- Returns: `(macd_line, signal_line, histogram)`

**Interpretation:**
- MACD > Signal: Bullish momentum
- MACD < Signal: Bearish momentum
- Histogram: Momentum strength

#### 4. Complete Momentum Check
```python
is_confirmed, reason, details = check_momentum_confirmation(
    ib=ib,
    contract=stock_contract,
    side='LONG',  # or 'SHORT'
    rsi_enabled=True,
    rsi_period=14,
    rsi_threshold=60,  # Strong momentum threshold
    macd_enabled=True,
    macd_fast=3,       # Day trading
    macd_slow=10,      # Day trading
    macd_signal=16,    # Day trading
    lookback_bars=100
)
```

**Returns:**
```python
{
    'rsi': 62.5,
    'rsi_confirmed': True,
    'macd': 0.15,
    'signal': 0.08,
    'macd_confirmed': True
}
```

---

## Optimal Settings (Research-Based)

### For 5-Minute Charts (Day Trading)

**RSI:**
- Period: `14` (standard) or `9` (sensitive)
- Threshold: `50` (neutral) or `60` (strong)
- Logic:
  - LONG: RSI > 50 (allow), RSI > 60 (strong)
  - SHORT: RSI < 50 (allow), RSI < 40 (strong)

**MACD:**
- Fast EMA: `3` (day trading) vs `12` (standard)
- Slow EMA: `10` (day trading) vs `26` (standard)
- Signal: `16` (day trading) vs `9` (standard)
- Logic:
  - LONG: MACD > Signal (bullish)
  - SHORT: MACD < Signal (bearish)

### Volume Helper
```python
avg_volume = get_average_1min_volume(ib, contract, lookback_bars=20)
```

Gets average 1-minute volume from IBKR instead of stitching 5-sec bars.

---

## Integration Examples

### Example 1: Basic Integration in Strategy

```python
from strategy.momentum_indicators import check_momentum_confirmation

# In check_entry_confirmation() method
def check_entry_confirmation(self, stock, current_price, side='LONG'):
    # ... existing logic ...

    # Add momentum check
    if self.enable_momentum_filters:
        is_confirmed, reason, details = check_momentum_confirmation(
            ib=self.ib,
            contract=stock['contract'],
            side=side,
            rsi_enabled=self.rsi_enabled,
            rsi_period=self.rsi_period,
            rsi_threshold=self.rsi_threshold,
            macd_enabled=self.macd_enabled,
            macd_fast=self.macd_fast,
            macd_slow=self.macd_slow,
            macd_signal=self.macd_signal
        )

        if not is_confirmed:
            return False, f"Momentum check failed: {reason}"

        # Log momentum details
        self.logger.info(f"  ✅ Momentum confirmed: RSI={details['rsi']:.1f}, "
                        f"MACD={details['macd']:.2f}")

    return True, "Entry confirmed"
```

### Example 2: Conditional Filtering (Recommended)

```python
# Only require momentum confirmation for MOMENTUM_BREAKOUT entries
# Allow pullback/retest entries without strict momentum requirements

if entry_type == 'MOMENTUM_BREAKOUT':
    # Strict momentum requirements
    is_confirmed, reason, details = check_momentum_confirmation(
        ib=self.ib,
        contract=stock['contract'],
        side=side,
        rsi_threshold=60,  # Strong momentum required
        macd_enabled=True
    )

    if not is_confirmed:
        # Route to pullback/retest instead
        return check_pullback_retest(...)

elif entry_type == 'PULLBACK_RETEST':
    # Lighter momentum check (just bias, not strength)
    is_confirmed, reason, details = check_momentum_confirmation(
        ib=self.ib,
        contract=stock['contract'],
        side=side,
        rsi_threshold=50,  # Just bias required
        macd_enabled=False  # Skip MACD
    )
```

---

## Configuration (trader_config.yaml)

Add these settings to the `confirmation` section:

```yaml
trading:
  confirmation:
    # RSI Filter
    enable_rsi_filter: true             # Enable RSI momentum check
    rsi_period: 14                      # RSI period (9=sensitive, 14=standard)
    rsi_threshold_neutral: 50           # Minimum for bias confirmation
    rsi_threshold_strong: 60            # Minimum for strong momentum (longs)
                                        # Inverted for shorts (100-60=40)

    # MACD Filter
    enable_macd_filter: true            # Enable MACD momentum check
    macd_fast: 3                        # Fast EMA (3=day trading, 12=standard)
    macd_slow: 10                       # Slow EMA (10=day trading, 26=standard)
    macd_signal: 16                     # Signal EMA (16=day trading, 9=standard)

    # When to apply momentum filters
    require_momentum_for_momentum_breakout: true   # Strict check for momentum entries
    require_momentum_for_pullback: false           # Skip for pullback entries
    require_momentum_for_sustained: false          # Skip for sustained entries
```

---

## Areas Using Bar Stitching (Current State)

### 1. ✅ RSI/MACD (FIXED)
**Before:** Would have built 5-min candles from 5-sec bars
**After:** Uses `fetch_5min_bars()` from IBKR directly

### 2. ✅ Volume Averaging (OPTIONAL FIX)
**Before:** Stitches 5-sec bars to calculate 1-min volume average
**After:** Can use `get_average_1min_volume()` to fetch from IBKR
**Note:** Current stitching approach is OK for real-time, but helper is available

### 3. ⚪ 1-Minute Candle Close (KEEP AS-IS)
**Location:** `ps60_strategy.py:872-965`
**Purpose:** Wait for 1-min candle to close above/below pivot
**Why keep stitching:** Needs real-time candle formation, IBKR 1-min bars update every minute
**Status:** No change needed - stitching is appropriate here

### 4. ⚪ Volume Surge Check (KEEP AS-IS)
**Location:** `ps60_strategy.py:936-951`
**Purpose:** Compare current 1-min candle volume to 20-candle average
**Why keep stitching:** Real-time volume tracking during candle formation
**Status:** Could optionally use `get_average_1min_volume()` for the average, but stitching is fine

---

## Expected Impact

### Before (Oct 7 Results)
- Backtest: -$6,528, 20% win rate, 15 trades
- Issues: XPEV (1.13x RVOL), SNAP (0.87x RVOL), JD (0.5x RVOL)
- Problem: Weak breakouts qualifying as momentum entries

### After (Projected)
- Win rate: 20% → 40-50%
- Trades: 15 → 8-10 (higher quality)
- P&L: Negative → Positive
- Better R/R: Stricter entry = better setups

---

## Testing Plan

### Phase 1: Standalone Testing
```python
# Test with historical data
from strategy.momentum_indicators import check_momentum_confirmation

is_confirmed, reason, details = check_momentum_confirmation(
    ib=ib,
    contract=Stock('XPEV', 'SMART', 'USD'),
    side='LONG',
    rsi_enabled=True,
    macd_enabled=True
)

print(f"Confirmed: {is_confirmed}")
print(f"Reason: {reason}")
print(f"RSI: {details.get('rsi')}")
print(f"MACD: {details.get('macd')}")
```

### Phase 2: Integration Testing
1. Add config parameters to `trader_config.yaml`
2. Import module in `ps60_strategy.py`
3. Add momentum check to `check_entry_confirmation()`
4. Test with Oct 7 backtest data
5. Compare results before/after

### Phase 3: Live Validation
1. Enable in paper trading
2. Monitor entry blocks due to momentum
3. Verify RSI/MACD values match expectations
4. Track win rate improvement

---

## Usage Examples

### Example 1: Check Before Entry
```python
# Before entering momentum breakout
if entry_type == 'MOMENTUM_BREAKOUT':
    is_confirmed, reason, details = check_momentum_confirmation(
        ib=self.ib,
        contract=stock['contract'],
        side='LONG',
        rsi_enabled=True,
        rsi_period=14,
        rsi_threshold=60,
        macd_enabled=True,
        macd_fast=3,
        macd_slow=10,
        macd_signal=16
    )

    if not is_confirmed:
        self.logger.info(f"  ❌ {stock['symbol']}: Momentum check failed")
        self.logger.info(f"     {reason}")
        return False

    self.logger.info(f"  ✅ {stock['symbol']}: Momentum confirmed")
    self.logger.info(f"     RSI: {details['rsi']:.1f}, MACD: {details['macd']:.2f}")
```

### Example 2: Get Average Volume
```python
from strategy.momentum_indicators import get_average_1min_volume

# Get 20-bar average 1-min volume
avg_volume = get_average_1min_volume(
    ib=self.ib,
    contract=stock['contract'],
    lookback_bars=20
)

# Compare to current 1-min volume
current_volume = sum(bar.volume for bar in current_1min_bars)
volume_ratio = current_volume / avg_volume

if volume_ratio < 2.0:
    return False, f"Volume too low ({volume_ratio:.1f}x)"
```

---

## API Rate Limits

**IBKR Historical Data Limits:**
- Max 60 requests per 10 minutes
- Pacing: ~10 second delay between requests recommended
- Each `fetch_5min_bars()` call = 1 request
- Each `fetch_1min_bars()` call = 1 request

**Optimization:**
- Cache bars in memory (don't re-fetch every second)
- Fetch once per symbol at market open
- Update every 5 minutes during trading hours

---

## Next Steps

1. ✅ Module created (`momentum_indicators.py`)
2. ⏳ Add config parameters to `trader_config.yaml`
3. ⏳ Import and integrate in `ps60_strategy.py`
4. ⏳ Test with Oct 7 backtest data
5. ⏳ Compare results before/after
6. ⏳ Enable in live paper trading
7. ⏳ Monitor and tune thresholds

---

## Files Modified

- ✅ `strategy/momentum_indicators.py` - New module created
- ⏳ `config/trader_config.yaml` - Add RSI/MACD settings
- ⏳ `strategy/ps60_strategy.py` - Integrate momentum checks
- ⏳ `trader.py` - Pass IB connection to strategy

---

**Implementation Status:** Ready for Integration
**Estimated Impact:** +20-30% win rate improvement
**Risk:** Low (can be disabled via config)
