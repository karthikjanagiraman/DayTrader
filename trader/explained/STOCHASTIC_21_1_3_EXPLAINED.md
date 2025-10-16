# Stochastic Oscillator (21, 1, 3) - Complete Explanation

**Date**: October 15, 2025
**Purpose**: Detailed explanation of how to calculate and use Stochastic (21, 1, 3) for hourly bars

---

## Overview

The **Stochastic Oscillator** is a momentum indicator that compares a stock's closing price to its price range over a specific period. It shows where the current price sits relative to the recent high-low range.

**Value Range**: 0 to 100
- **Above 80**: Overbought condition (price near top of range)
- **Below 20**: Oversold condition (price near bottom of range)

---

## The (21, 1, 3) Settings Explained

The three numbers represent:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| **Lookback Period** | 21 | Look back 21 bars to find highest high and lowest low |
| **%K Smoothing** | 1 | No smoothing on %K (raw stochastic) |
| **%D Smoothing** | 3 | 3-period moving average of %K |

**For Hourly Bars**: This means looking back **21 hours** of price data.

---

## Calculation Formula

### Step 1: Calculate Raw %K (Fast Stochastic)

```
%K = ((Current Close - Lowest Low (21)) / (Highest High (21) - Lowest Low (21))) × 100
```

Where:
- **Current Close** = Most recent hourly bar's closing price
- **Lowest Low (21)** = Lowest low price in last 21 hourly bars
- **Highest High (21)** = Highest high price in last 21 hourly bars

### Step 2: Smooth %K (if smoothing > 1)

```
Smoothed %K = SMA(%K, smoothing_period)
```

With smoothing = 1, **no smoothing is applied** (we use raw %K).

### Step 3: Calculate %D (Signal Line)

```
%D = SMA(%K, 3)
```

%D is a **3-period simple moving average** of %K values.

---

## Example Calculation

### Example: TSLA on Hourly Chart

**Given**: Last 21 hourly bars of TSLA

| Hour | High | Low | Close |
|------|------|-----|-------|
| ... | ... | ... | ... |
| 21 bars ago | $445.50 | $443.20 | $444.00 |
| ... | ... | ... | ... |
| Current bar | $452.30 | $450.10 | **$451.80** |

**Step 1: Find Range**
- Highest High (21 bars) = **$454.00**
- Lowest Low (21 bars) = **$442.50**
- Current Close = **$451.80**

**Step 2: Calculate %K**
```
%K = (451.80 - 442.50) / (454.00 - 442.50) × 100
%K = 9.30 / 11.50 × 100
%K = 80.87
```

**Interpretation**: TSLA is at **80.87%** of its 21-hour range → Near overbought territory

**Step 3: Calculate %D**

Assume previous %K values:
- 2 bars ago: %K = 78.50
- 1 bar ago: %K = 79.20
- Current: %K = 80.87

```
%D = (78.50 + 79.20 + 80.87) / 3
%D = 79.52
```

**Result**:
- %K = **80.87** (current momentum)
- %D = **79.52** (smoothed signal line)
- %K > %D → Bullish momentum (uptrend)

---

## Python Implementation

### Using IBKR Historical Bars

```python
from ib_insync import IB, Stock, util
import pandas as pd

class StochasticCalculator:
    """
    Calculate Stochastic (21, 1, 3) using IBKR hourly bars
    """

    def __init__(self, ib_connection):
        self.ib = ib_connection

    def get_hourly_bars(self, symbol, lookback_bars=50):
        """
        Fetch hourly bars from IBKR

        Args:
            symbol: Stock symbol (e.g., 'TSLA')
            lookback_bars: Number of hourly bars to fetch (need extra for %D calculation)

        Returns:
            DataFrame with OHLC data
        """
        contract = Stock(symbol, 'SMART', 'USD')

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime='',  # Current time
            durationStr=f'{lookback_bars} D',  # Enough days to get 50+ hourly bars
            barSizeSetting='1 hour',  # Hourly bars
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1
        )

        # Convert to DataFrame
        df = util.df(bars)
        return df

    def calculate_stochastic(self, df, k_period=21, k_smooth=1, d_smooth=3):
        """
        Calculate Stochastic (21, 1, 3)

        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            k_period: Lookback period (21)
            k_smooth: %K smoothing period (1 = no smoothing)
            d_smooth: %D smoothing period (3)

        Returns:
            DataFrame with %K and %D columns added
        """
        # Step 1: Calculate rolling highest high and lowest low
        df['highest_high'] = df['high'].rolling(window=k_period).max()
        df['lowest_low'] = df['low'].rolling(window=k_period).min()

        # Step 2: Calculate raw %K
        df['%K_raw'] = (
            (df['close'] - df['lowest_low']) /
            (df['highest_high'] - df['lowest_low']) * 100
        )

        # Step 3: Smooth %K if k_smooth > 1
        if k_smooth > 1:
            df['%K'] = df['%K_raw'].rolling(window=k_smooth).mean()
        else:
            df['%K'] = df['%K_raw']  # No smoothing

        # Step 4: Calculate %D (moving average of %K)
        df['%D'] = df['%K'].rolling(window=d_smooth).mean()

        # Clean up intermediate columns
        df.drop(columns=['highest_high', 'lowest_low', '%K_raw'], inplace=True)

        return df

    def get_current_stochastic(self, symbol):
        """
        Get current Stochastic (21, 1, 3) values for a symbol

        Returns:
            dict: {'%K': float, '%D': float, 'signal': str}
        """
        # Fetch enough bars for calculation (21 + 3 + buffer = 50)
        df = self.get_hourly_bars(symbol, lookback_bars=50)

        # Calculate stochastic
        df = self.calculate_stochastic(df, k_period=21, k_smooth=1, d_smooth=3)

        # Get most recent values
        current_k = df['%K'].iloc[-1]
        current_d = df['%D'].iloc[-1]

        # Determine signal
        if current_k > 80:
            signal = 'OVERBOUGHT'
        elif current_k < 20:
            signal = 'OVERSOLD'
        elif current_k > current_d:
            signal = 'BULLISH (K > D)'
        else:
            signal = 'BEARISH (K < D)'

        return {
            '%K': round(current_k, 2),
            '%D': round(current_d, 2),
            'signal': signal
        }


# Example Usage
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2000)

calc = StochasticCalculator(ib)

# Get current stochastic for TSLA
result = calc.get_current_stochastic('TSLA')
print(f"TSLA Stochastic (21,1,3): %K={result['%K']}, %D={result['%D']}, Signal={result['signal']}")

# Get full DataFrame with stochastic values
df = calc.get_hourly_bars('TSLA', lookback_bars=50)
df = calc.calculate_stochastic(df, k_period=21, k_smooth=1, d_smooth=3)
print(df[['date', 'close', '%K', '%D']].tail(10))

ib.disconnect()
```

---

## Trading Signals

### Classic Stochastic Signals

1. **Overbought/Oversold**
   - %K > 80 → Overbought (potential reversal down)
   - %K < 20 → Oversold (potential reversal up)

2. **Crossovers**
   - %K crosses above %D → Bullish signal (buy)
   - %K crosses below %D → Bearish signal (sell)

3. **Divergence**
   - Price makes new high, but %K doesn't → Bearish divergence
   - Price makes new low, but %K doesn't → Bullish divergence

### Example: Using Stochastic for Entry Confirmation

```python
def should_enter_long_with_stochastic(symbol, current_price, resistance):
    """
    Check if stochastic confirms a long entry

    Returns:
        bool: True if stochastic confirms entry
        str: Reason
    """
    # Get current stochastic
    stoch = calc.get_current_stochastic(symbol)
    k = stoch['%K']
    d = stoch['%D']

    # Entry rules for LONG
    # 1. Price breaks resistance
    if current_price <= resistance:
        return False, "Price hasn't broken resistance"

    # 2. Stochastic should NOT be overbought (avoid late entries)
    if k > 85:
        return False, f"Overbought (K={k:.1f})"

    # 3. Stochastic should show bullish momentum (K > D)
    if k <= d:
        return False, f"Bearish momentum (K={k:.1f} < D={d:.1f})"

    # 4. Ideally stochastic is rising from oversold/neutral
    if k > 50:
        return True, f"Confirmed (K={k:.1f}, D={d:.1f}, momentum strong)"
    else:
        return True, f"Early momentum (K={k:.1f}, D={d:.1f}, rising)"
```

---

## Why Use (21, 1, 3) for Hourly Bars?

### Comparison with Other Settings

| Setting | Sensitivity | Use Case |
|---------|-------------|----------|
| **(14, 3, 3)** | Default | General purpose, balanced |
| **(21, 1, 3)** | Less sensitive | Longer trends, less noise |
| **(5, 3, 3)** | Very sensitive | Scalping, quick reversals |
| **(21, 5, 5)** | Very smooth | Long-term trends |

**Why 21, 1, 3?**
- **21-period lookback**: Captures ~2.5 trading days of hourly data (more stable than 14)
- **1-period smoothing**: No smoothing on %K → More responsive to recent moves
- **3-period %D**: Smooth enough to filter noise, but still responsive

**Best For**:
- Hourly chart swing trades (holding 1-3 days)
- Avoiding overbought entries on breakouts
- Confirming momentum after resistance breaks
- Filtering out weak breakouts (low stochastic = weak momentum)

---

## Integration with PS60 Strategy

### Potential Use Case: Entry Confirmation

**Current PS60 Entry**: Volume + Candle size + Sustained break

**Enhanced with Stochastic**:
```
ENTRY CRITERIA (with Stochastic filter):
1. Price breaks resistance ✓
2. Volume ≥ 2.0x average ✓
3. Candle ≥ 0.3% ✓
4. NEW: Stochastic (21,1,3) %K < 85 (not overbought)
5. NEW: Stochastic %K > %D (bullish momentum)
```

**Benefits**:
- **Avoid late entries**: Block entries when stochastic is overbought (>85)
- **Confirm momentum**: Only enter when %K is rising (%K > %D)
- **Reduce whipsaws**: Avoid breakouts with weak underlying momentum

**Example**:
```
TSLA breaks $450 resistance at 10:00 AM
- Volume: 3.5x ✓
- Candle: 0.8% ✓
- Stochastic: %K=88.5, %D=85.2
- Result: BLOCKED (overbought, likely late entry)

AMD breaks $165 resistance at 10:00 AM
- Volume: 2.8x ✓
- Candle: 0.6% ✓
- Stochastic: %K=62.3, %D=58.7 (%K > %D, not overbought)
- Result: ENTER (confirmed by momentum)
```

---

## Code Implementation for PS60 Strategy

### File: `trader/strategy/stochastic_calculator.py` (NEW)

```python
from ib_insync import IB, Stock, util
import pandas as pd
from datetime import datetime

class StochasticCalculator:
    """
    Calculate Stochastic (21, 1, 3) for hourly bars
    Used as entry confirmation filter in PS60 strategy
    """

    def __init__(self, ib_connection, k_period=21, k_smooth=1, d_smooth=3):
        self.ib = ib_connection
        self.k_period = k_period
        self.k_smooth = k_smooth
        self.d_smooth = d_smooth
        self.cache = {}  # Cache results for 1 hour
        self.cache_duration = 3600  # 1 hour in seconds

    def calculate_stochastic(self, df):
        """Calculate stochastic values"""
        df['highest_high'] = df['high'].rolling(window=self.k_period).max()
        df['lowest_low'] = df['low'].rolling(window=self.k_period).min()

        df['%K_raw'] = (
            (df['close'] - df['lowest_low']) /
            (df['highest_high'] - df['lowest_low']) * 100
        )

        if self.k_smooth > 1:
            df['%K'] = df['%K_raw'].rolling(window=self.k_smooth).mean()
        else:
            df['%K'] = df['%K_raw']

        df['%D'] = df['%K'].rolling(window=self.d_smooth).mean()

        return df

    def get_stochastic(self, symbol):
        """
        Get current stochastic values with caching

        Returns:
            dict: {'%K': float, '%D': float, 'timestamp': datetime}
        """
        now = datetime.now()

        # Check cache
        if symbol in self.cache:
            cached_data, cached_time = self.cache[symbol]
            if (now - cached_time).total_seconds() < self.cache_duration:
                return cached_data

        # Fetch fresh data
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='10 D',  # Get 10 days to ensure 50+ hourly bars
                barSizeSetting='1 hour',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            df = util.df(bars)
            df = self.calculate_stochastic(df)

            # Get current values
            current_k = df['%K'].iloc[-1]
            current_d = df['%D'].iloc[-1]

            result = {
                '%K': round(current_k, 2),
                '%D': round(current_d, 2),
                'timestamp': now
            }

            # Cache result
            self.cache[symbol] = (result, now)

            return result

        except Exception as e:
            print(f"⚠️  Failed to calculate stochastic for {symbol}: {e}")
            return None

    def is_overbought(self, symbol, threshold=85):
        """Check if symbol is overbought (avoid late entries)"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] > threshold

    def is_oversold(self, symbol, threshold=15):
        """Check if symbol is oversold (potential reversal)"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] < threshold

    def has_bullish_momentum(self, symbol):
        """Check if %K > %D (bullish momentum)"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] > stoch['%D']

    def has_bearish_momentum(self, symbol):
        """Check if %K < %D (bearish momentum)"""
        stoch = self.get_stochastic(symbol)
        if stoch is None:
            return False
        return stoch['%K'] < stoch['%D']
```

### Configuration Addition to `trader/config/trader_config.yaml`

```yaml
# Stochastic Oscillator Filter (NEW - Oct 15, 2025)
stochastic:
  enabled: false                    # Enable stochastic confirmation filter
  k_period: 21                      # Lookback period (21 hourly bars)
  k_smooth: 1                       # %K smoothing (1 = no smoothing)
  d_smooth: 3                       # %D smoothing (3-period SMA)

  overbought_threshold: 85          # Block entries above this %K value
  require_bullish_momentum: true    # Require %K > %D for LONG entries
  require_bearish_momentum: true    # Require %K < %D for SHORT entries

  cache_duration_sec: 3600          # Cache stochastic values for 1 hour
```

---

## Testing & Validation

### Test Script: `trader/test_stochastic.py`

```python
from ib_insync import IB
from strategy.stochastic_calculator import StochasticCalculator

# Connect to IBKR
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2000)

# Initialize calculator
calc = StochasticCalculator(ib, k_period=21, k_smooth=1, d_smooth=3)

# Test symbols
symbols = ['TSLA', 'AAPL', 'NVDA', 'AMD', 'COIN']

print("=" * 80)
print("STOCHASTIC (21, 1, 3) - HOURLY BARS")
print("=" * 80)

for symbol in symbols:
    stoch = calc.get_stochastic(symbol)

    if stoch:
        k = stoch['%K']
        d = stoch['%D']

        # Determine status
        if k > 85:
            status = "OVERBOUGHT"
        elif k < 15:
            status = "OVERSOLD"
        elif k > d:
            status = "BULLISH (K > D)"
        else:
            status = "BEARISH (K < D)"

        print(f"{symbol:6s}: %K={k:6.2f}, %D={d:6.2f} | {status}")
    else:
        print(f"{symbol:6s}: ERROR - Could not calculate")

ib.disconnect()
```

**Expected Output**:
```
================================================================================
STOCHASTIC (21, 1, 3) - HOURLY BARS
================================================================================
TSLA  : %K= 88.45, %D= 85.23 | OVERBOUGHT
AAPL  : %K= 62.10, %D= 58.30 | BULLISH (K > D)
NVDA  : %K= 45.67, %D= 48.12 | BEARISH (K < D)
AMD   : %K= 72.88, %D= 69.45 | BULLISH (K > D)
COIN  : %K= 18.23, %D= 22.67 | OVERSOLD
```

---

## Related Documentation

- **Configuration**: `trader/config/trader_config.yaml` (stochastic section)
- **Implementation**: `trader/strategy/stochastic_calculator.py` (NEW)
- **PS60 Strategy**: `trader/strategy/ps60_strategy.py` (integrate stochastic filter)
- **Volume Filter**: `trader/explained/VOLUME_FILTER_EXPLAINED.md`
- **Filter Documentation**: `trader/FILTER_DOCUMENTATION.md`

---

## Summary

**Stochastic (21, 1, 3) for Hourly Bars**:
- **Lookback**: 21 hourly bars (~2.5 trading days)
- **%K**: Raw stochastic (no smoothing)
- **%D**: 3-period moving average of %K
- **Use Case**: Entry confirmation filter to avoid overbought breakouts
- **Implementation**: Python class using IBKR historical hourly bars
- **Benefits**: Reduces late entries, confirms momentum, filters weak breakouts

**Key Insight**: By requiring stochastic %K < 85 and %K > %D for long entries, we can avoid entering breakouts that are already extended and likely to reverse.

---

**Status**: ✅ **READY FOR IMPLEMENTATION** (October 15, 2025)
