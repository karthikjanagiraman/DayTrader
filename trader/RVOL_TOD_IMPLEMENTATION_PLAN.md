# RVOL-TOD Implementation Plan
## Relative Volume - Time of Day Calculation Method

**Date**: October 25, 2025
**Status**: PLANNING - Awaiting Approval
**Priority**: CRITICAL - Current volume calculation is incorrect

---

## Executive Summary

### Problem
Current volume calculation uses **rolling 20-candle average** which:
- Doesn't account for intraday volume patterns (higher volume at open/close)
- Produces volume ratios that don't match what users see on trading charts
- Example: User sees >1.0x volume on charts, but system shows 0.50x-0.80x

### Solution
Implement **RVOL-TOD (Relative Volume - Time of Day)** method:
- Compare current 9:45 AM bar to **average of all historical 9:45 AM bars**
- Uses time-of-day matching across multiple days (10-50 day lookback)
- Industry-standard method used by professional day traders

### Expected Impact
- ✅ Volume ratios will match what users see on TradingView/ThinkOrSwim charts
- ✅ More accurate entry signals (volume filter works correctly)
- ✅ Better alignment with professional trader expectations
- ⚠️ Will require historical data storage/caching for backtesting

---

## Current Method (INCORRECT)

### Code Location
`trader/strategy/ps60_entry_state_machine.py` lines 357-383

### Current Algorithm
```python
# Step 1: Get current candle volume (sum of 12 five-second bars)
candle_volume = sum(b.volume for b in candle_bars)

# Step 2: Look back 20 candles (ANY time of day)
candle_start_array = (current_idx // bars_per_candle) * bars_per_candle
avg_volume_lookback_array = max(0, candle_start_array - (20 * bars_per_candle))
past_bars = bars[avg_volume_lookback_array:candle_start_array]

# Step 3: Calculate average from those 20 candles
avg_volume_per_bar = sum(b.volume for b in past_bars) / len(past_bars)
avg_candle_volume = avg_volume_per_bar * bars_per_candle

# Step 4: Calculate ratio
volume_ratio = candle_volume / avg_candle_volume
```

### Example Problem (SMCI @ 09:45 AM)
```
Current Method:
  Current: 9:45 AM bar with 115,200 shares
  Lookback: Past 20 candles (9:25 AM - 9:44 AM) - mixed times
  Average: 144,000 shares/candle
  Ratio: 115,200 / 144,000 = 0.80x ❌

RVOL-TOD Method (what it SHOULD be):
  Current: 9:45 AM bar with 115,200 shares
  Lookback: All historical 9:45 AM bars from past 20 days
  Average: 85,000 shares/candle (9:45 AM typical volume)
  Ratio: 115,200 / 85,000 = 1.35x ✅

User sees 1.35x on charts, we calculate 0.80x → MISMATCH!
```

### Why This Happens
The first 15-20 minutes of trading (9:30-9:50 AM) have naturally higher volume than later in the day. Comparing a 9:45 AM bar to bars from 9:25-9:44 AM includes the opening bell surge, inflating the average. RVOL-TOD solves this by comparing 9:45 AM to historical 9:45 AM averages.

---

## Proposed Method (RVOL-TOD)

### Professional Standard
From StockCharts.com:
> "For intraday charts, this indicator allows you to easily track volume throughout the trading session relative to the average volume traded at that time of day across a customizable range of your choosing. On a 5-minute chart, the RVOL-TOD value for today's 9:30 bar would compare volume for that bar with the average volume on previous 9:30 AM 5-minute bars."

### Algorithm Overview
```python
# Step 1: Get current bar timestamp
current_time = bars[current_idx].date  # e.g., 2025-10-21 09:45:00

# Step 2: Extract time-of-day (ignore date)
time_of_day = current_time.time()  # e.g., 09:45:00

# Step 3: Collect historical bars at SAME time of day
historical_bars = []
for day in range(1, lookback_days + 1):
    historical_date = current_date - timedelta(days=day)

    # Find bar at same time on that day
    bar_at_time = get_bar_at_time(symbol, historical_date, time_of_day)

    if bar_at_time:
        historical_bars.append(bar_at_time)

# Step 4: Calculate average volume from historical bars
if len(historical_bars) >= min_historical_bars:
    avg_volume = sum(b.volume for b in historical_bars) / len(historical_bars)
else:
    # Fallback to current method if insufficient history
    avg_volume = calculate_rolling_average(bars, current_idx, 20)

# Step 5: Calculate ratio
volume_ratio = current_volume / avg_volume
```

### Data Requirements
**For Live Trading:**
- Need to query IBKR for historical 1-minute bars at specific times
- Cache results for the day (don't re-fetch)
- Use 20-50 day lookback (configurable)

**For Backtesting:**
- Need to pre-download historical 1-minute bars for all dates
- Store in local cache (e.g., `backtest/data/historical_volume_cache/`)
- Query cache instead of IBKR during backtest

---

## Implementation Details

### 1. New Configuration (trader_config.yaml)

```yaml
confirmation:
  volume_calculation:
    method: "rvol_tod"              # "rolling" (old) or "rvol_tod" (new)

    # RVOL-TOD specific settings
    rvol_tod:
      lookback_days: 20             # How many historical days to average
      min_historical_bars: 10       # Minimum bars required (fallback if less)
      cache_enabled: true           # Cache historical data for day
      cache_duration_sec: 86400     # 24 hours

      # Backtesting settings
      preload_historical_data: true # Pre-download all needed historical data
      historical_data_dir: "./backtest/data/rvol_tod_cache/"

    # Fallback to rolling average if RVOL-TOD fails
    fallback_to_rolling: true
    rolling_candles: 20             # Number of candles for rolling average
```

### 2. Code Changes

#### A. New Historical Volume Cache Module
**File**: `trader/strategy/historical_volume_cache.py` (NEW)

```python
"""
Historical Volume Cache for RVOL-TOD Calculation

Fetches and caches historical 1-minute bars for volume comparison
"""

from datetime import datetime, timedelta, time as time_obj
from pathlib import Path
import json
import logging
from typing import Dict, List, Optional
from ib_insync import IB, Stock

logger = logging.getLogger(__name__)


class HistoricalVolumeCache:
    """
    Cache for historical intraday volume data used in RVOL-TOD calculation
    """

    def __init__(self, ib_connection, config):
        self.ib = ib_connection
        self.config = config
        self.cache = {}  # {symbol: {time_str: [volumes]}}
        self.cache_dir = Path(config.get('historical_data_dir', './backtest/data/rvol_tod_cache/'))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_historical_average_volume(
        self,
        symbol: str,
        current_date: datetime,
        time_of_day: time_obj
    ) -> Optional[float]:
        """
        Get average historical volume for this symbol at this time of day

        Args:
            symbol: Stock ticker
            current_date: Current trading date
            time_of_day: Time to compare (e.g., 09:45:00)

        Returns:
            Average volume from historical bars, or None if insufficient data
        """
        lookback_days = self.config.get('lookback_days', 20)
        min_bars = self.config.get('min_historical_bars', 10)

        # Check cache first
        cache_key = f"{symbol}_{time_of_day.strftime('%H:%M')}"
        if cache_key in self.cache:
            return self._calculate_average(self.cache[cache_key])

        # Fetch historical data
        historical_volumes = []

        for day_offset in range(1, lookback_days + 1):
            historical_date = current_date - timedelta(days=day_offset)

            # Skip weekends
            if historical_date.weekday() >= 5:
                continue

            # Fetch 1-minute bar at this time
            volume = self._fetch_bar_volume(symbol, historical_date, time_of_day)

            if volume is not None:
                historical_volumes.append(volume)

        # Cache results
        if len(historical_volumes) >= min_bars:
            self.cache[cache_key] = historical_volumes
            return self._calculate_average(historical_volumes)

        return None

    def _fetch_bar_volume(
        self,
        symbol: str,
        date: datetime,
        time_of_day: time_obj
    ) -> Optional[float]:
        """
        Fetch volume for a specific 1-minute bar from IBKR

        Args:
            symbol: Stock ticker
            date: Trading date
            time_of_day: Time of the bar (e.g., 09:45:00)

        Returns:
            Volume for that bar, or None if unavailable
        """
        try:
            contract = Stock(symbol, 'SMART', 'USD')

            # Request 1-minute bars for this day
            end_datetime = f"{date.strftime('%Y%m%d')} {time_of_day.strftime('%H:%M:00')}"

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                return None

            # Find the bar at the exact time
            for bar in bars:
                bar_time = bar.date.time()
                if bar_time == time_of_day:
                    return bar.volume

            return None

        except Exception as e:
            logger.debug(f"Failed to fetch historical volume for {symbol} on {date} at {time_of_day}: {e}")
            return None

    def _calculate_average(self, volumes: List[float]) -> float:
        """Calculate average volume from list"""
        if not volumes:
            return 0.0
        return sum(volumes) / len(volumes)

    def preload_for_backtest(self, symbols: List[str], start_date: datetime, end_date: datetime):
        """
        Pre-download historical volume data for backtesting

        This downloads all needed historical data upfront to avoid
        repeated IBKR API calls during backtest execution
        """
        logger.info(f"Preloading RVOL-TOD data for {len(symbols)} symbols...")

        # For each symbol, download all 1-minute bars for the date range
        for symbol in symbols:
            self._download_symbol_history(symbol, start_date, end_date)

    def _download_symbol_history(self, symbol: str, start_date: datetime, end_date: datetime):
        """Download and cache all 1-minute bars for a symbol"""
        cache_file = self.cache_dir / f"{symbol}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"

        if cache_file.exists():
            logger.debug(f"Loading cached data for {symbol}")
            with open(cache_file) as f:
                self.cache[symbol] = json.load(f)
            return

        # Download from IBKR
        # ... implementation ...
```

#### B. Updated Entry State Machine
**File**: `trader/strategy/ps60_entry_state_machine.py`

Replace lines 357-383 with:

```python
# Calculate volume ratio using configured method (Oct 25, 2025)
volume_config = strategy.config['trading']['confirmation'].get('volume_calculation', {})
volume_method = volume_config.get('method', 'rolling')

if volume_method == 'rvol_tod':
    # RVOL-TOD: Compare to historical average at same time of day
    volume_ratio = strategy.calculate_rvol_tod(
        bars=bars,
        current_idx=current_idx,
        candle_volume=candle_volume,
        symbol=symbol,
        bar_buffer=bar_buffer
    )
else:
    # Rolling average (old method)
    volume_ratio = strategy.calculate_rolling_volume_ratio(
        bars=bars,
        current_idx=current_idx,
        candle_volume=candle_volume,
        bars_per_candle=bars_per_candle,
        bar_buffer=bar_buffer
    )
```

#### C. New Methods in PS60Strategy
**File**: `trader/strategy/ps60_strategy.py`

```python
def calculate_rvol_tod(
    self,
    bars: List,
    current_idx: int,
    candle_volume: float,
    symbol: str,
    bar_buffer=None
) -> float:
    """
    Calculate Relative Volume - Time of Day (RVOL-TOD)

    Compares current bar volume to historical average volume at
    the same time of day across multiple days.

    Args:
        bars: List of bars
        current_idx: Index of current bar
        candle_volume: Volume of current candle
        symbol: Stock ticker
        bar_buffer: Optional bar buffer for live trading

    Returns:
        Volume ratio (e.g., 1.5 = 150% of historical average)
    """
    # Get current bar timestamp
    current_bar = bars[current_idx]
    current_time = current_bar.date
    time_of_day = current_time.time()

    # Get historical average volume at this time
    if not hasattr(self, 'volume_cache'):
        self._init_volume_cache()

    avg_historical_volume = self.volume_cache.get_historical_average_volume(
        symbol=symbol,
        current_date=current_time,
        time_of_day=time_of_day
    )

    # Fallback to rolling average if insufficient historical data
    if avg_historical_volume is None or avg_historical_volume == 0:
        logger.warning(f"{symbol}: Insufficient RVOL-TOD data, falling back to rolling average")
        return self.calculate_rolling_volume_ratio(
            bars, current_idx, candle_volume,
            12,  # bars_per_candle
            bar_buffer
        )

    # Calculate ratio
    volume_ratio = candle_volume / avg_historical_volume if avg_historical_volume > 0 else 1.0

    logger.debug(
        f"{symbol} RVOL-TOD: Current={candle_volume:,.0f} @ {time_of_day}, "
        f"Hist Avg={avg_historical_volume:,.0f}, Ratio={volume_ratio:.2f}x"
    )

    return volume_ratio

def calculate_rolling_volume_ratio(
    self,
    bars: List,
    current_idx: int,
    candle_volume: float,
    bars_per_candle: int,
    bar_buffer=None
) -> float:
    """
    Calculate volume ratio using rolling average (old method)

    Kept as fallback when RVOL-TOD data unavailable
    """
    # Original implementation from lines 358-383
    # ... (move existing code here) ...
```

### 3. Backtester Integration

**File**: `trader/backtest/backtester.py`

Add preloading step:

```python
def __init__(self, ...):
    # ... existing init ...

    # Preload RVOL-TOD data if enabled
    volume_config = self.config['trading']['confirmation'].get('volume_calculation', {})
    if volume_config.get('method') == 'rvol_tod':
        if volume_config['rvol_tod'].get('preload_historical_data', True):
            self._preload_rvol_tod_data()

def _preload_rvol_tod_data(self):
    """Pre-download all historical volume data needed for backtest"""
    logger.info("Preloading RVOL-TOD historical data...")

    symbols = [s['symbol'] for s in self.scanner_results]

    self.strategy.volume_cache.preload_for_backtest(
        symbols=symbols,
        start_date=self.start_date,
        end_date=self.end_date
    )

    logger.info("✅ RVOL-TOD data preloaded")
```

---

## Migration Strategy

### Phase 1: Implement RVOL-TOD (Keep Old Method Available)
1. Add `historical_volume_cache.py` module
2. Add new methods to `ps60_strategy.py`
3. Update `ps60_entry_state_machine.py` to support both methods
4. Add configuration to `trader_config.yaml`
5. **Default to OLD method** (`method: "rolling"`)

### Phase 2: Test RVOL-TOD
1. Enable RVOL-TOD for Oct 21 backtest: `method: "rvol_tod"`
2. Compare volume ratios to user's charts
3. Verify volume ratios now match (should see 1.0x+ where user sees 1.0x+)
4. Run validator to see if missed entries are now captured

### Phase 3: Deploy RVOL-TOD
1. Update default to `method: "rvol_tod"`
2. Remove old rolling method (or keep as fallback only)
3. Update documentation

---

## Testing Plan

### Test Case 1: SMCI @ 09:45 AM (Oct 21)
**Current (Rolling Average)**:
- Bars checked: Past 20 candles (9:25-9:44 AM)
- Volume ratio: 0.57x, 0.50x, 0.62x, 0.80x
- Result: BLOCKED ❌

**Expected (RVOL-TOD)**:
- Bars checked: All 9:45 AM bars from past 20 days
- Volume ratio: Should be >1.0x (match user's chart)
- Result: PASS ✅ (if volume truly elevated)

### Test Case 2: Multiple Symbols on Oct 21
Run backtest with RVOL-TOD and compare:
- Entry count (should increase if volume filter was incorrectly blocking)
- Volume ratios logged (should match TradingView/ThinkOrSwim)
- P&L (should improve if we were missing valid setups)

### Test Case 3: Live Trading Validation
1. Enable RVOL-TOD in live trader
2. Monitor volume ratios logged vs TradingView display
3. Verify they match within 5%

---

## Expected Impact

### Positive Impacts
✅ **Accuracy**: Volume ratios match professional trading platforms
✅ **Entry Quality**: Capture valid high-volume setups that were incorrectly blocked
✅ **User Confidence**: System behaves as expected based on chart analysis
✅ **Industry Standard**: Using same method as professional day traders

### Potential Risks
⚠️ **Historical Data**: Requires fetching/caching additional historical data
⚠️ **API Load**: More IBKR API calls (mitigated by caching)
⚠️ **Backtest Speed**: Preloading data adds startup time (one-time cost)
⚠️ **Complexity**: Additional module and configuration options

### Mitigation Strategies
- **Aggressive Caching**: Cache results for entire trading day
- **Preloading**: Download all data upfront for backtesting
- **Fallback**: Keep rolling average as fallback if RVOL-TOD fails
- **Configuration**: Allow disabling RVOL-TOD if issues arise

---

## Configuration Example

### Conservative Deployment (Default to Old Method)
```yaml
confirmation:
  volume_calculation:
    method: "rolling"              # Keep old method as default
    fallback_to_rolling: true
    rolling_candles: 20
```

### Test RVOL-TOD (User Can Enable)
```yaml
confirmation:
  volume_calculation:
    method: "rvol_tod"             # Enable new method for testing
    rvol_tod:
      lookback_days: 20
      min_historical_bars: 10
      cache_enabled: true
    fallback_to_rolling: true      # Fallback if RVOL-TOD fails
    rolling_candles: 20
```

### Production (After Validation)
```yaml
confirmation:
  volume_calculation:
    method: "rvol_tod"             # Use RVOL-TOD by default
    rvol_tod:
      lookback_days: 20
      min_historical_bars: 10
      cache_enabled: true
    fallback_to_rolling: true      # Keep fallback for safety
```

---

## Success Criteria

Before deploying RVOL-TOD as default:

1. ✅ Volume ratios match user's charts within 10%
2. ✅ Oct 21 backtest shows improved entry quality
3. ✅ No API rate limit issues with caching
4. ✅ Backtesting completes without errors
5. ✅ Live trader produces expected volume ratios
6. ✅ Documentation updated with new method

---

## Questions for Review

1. **Lookback Period**: Is 20 days appropriate, or should we use 50 days?
   - Professional default is 50-period SMA on 1-min charts
   - More days = more stable, but less responsive to recent changes

2. **Fallback Strategy**: Should we always fallback to rolling average, or error if RVOL-TOD fails?
   - Current plan: Fallback to rolling (safer)
   - Alternative: Block entry if RVOL-TOD unavailable (stricter)

3. **Cache Persistence**: Should we save cache to disk between sessions?
   - Current plan: In-memory cache, reload daily
   - Alternative: Persist to disk, reload on startup

4. **Minimum Historical Bars**: Is 10 bars sufficient, or require more?
   - Current plan: 10 minimum (50% of 20 days)
   - Alternative: 15 minimum (75% of 20 days)

---

## Files to Modify

| File | Action | Lines | Complexity |
|------|--------|-------|------------|
| `trader/strategy/historical_volume_cache.py` | CREATE | ~200 | Medium |
| `trader/strategy/ps60_strategy.py` | ADD METHODS | +50 | Low |
| `trader/strategy/ps60_entry_state_machine.py` | REPLACE | 357-383 | Low |
| `trader/config/trader_config.yaml` | ADD CONFIG | +15 | Low |
| `trader/backtest/backtester.py` | ADD PRELOAD | +30 | Low |
| `trader/validation/reports/VOLUME_CALCULATION_EXPLAINED.md` | UPDATE | Full rewrite | Low |

**Total**: ~300 lines of new code + configuration

---

## Next Steps (After Approval)

1. ✅ Create `historical_volume_cache.py` module
2. ✅ Add `calculate_rvol_tod()` method to `ps60_strategy.py`
3. ✅ Update `ps60_entry_state_machine.py` to use new method
4. ✅ Add configuration to `trader_config.yaml`
5. ✅ Test with Oct 21 data
6. ✅ Verify volume ratios match user's charts
7. ✅ Update documentation

---

**Status**: 🟡 AWAITING APPROVAL

Please review this plan and approve before implementation.
