"""
Quick script to verify a single trade's entry filters

Usage:
    python3 verify_single_trade.py AMZN 2025-10-16T13:54:03
"""

import sys
from datetime import datetime, timedelta
import pytz
from pathlib import Path
import yaml
from ib_insync import IB, Stock
import time

# Load config
config_path = Path(__file__).parent / 'config' / 'trader_config.yaml'
with open(config_path) as f:
    config = yaml.safe_load(f)

# Get thresholds
pullback_volume_threshold = config['trading']['confirmation']['pullback_volume_threshold']
pullback_candle_threshold = config['trading']['confirmation']['pullback_candle_min_pct']

print(f"Pullback Thresholds:")
print(f"  Volume: ≥{pullback_volume_threshold:.1f}x")
print(f"  Candle: ≥{pullback_candle_threshold*100:.1f}%")
print()

if len(sys.argv) < 3:
    print("Usage: python3 verify_single_trade.py SYMBOL ENTRY_TIME")
    print("Example: python3 verify_single_trade.py AMZN 2025-10-16T13:54:03")
    sys.exit(1)

symbol = sys.argv[1]
entry_time_str = sys.argv[2]

# Parse entry time
eastern = pytz.timezone('US/Eastern')
entry_time = datetime.fromisoformat(entry_time_str)
if entry_time.tzinfo is None:
    entry_time = eastern.localize(entry_time)
else:
    entry_time = entry_time.astimezone(eastern)

print(f"Verifying: {symbol} at {entry_time.strftime('%H:%M:%S')} ET\n")

# Connect to IBKR
ib = IB()
print("Connecting to IBKR...")
ib.connect('127.0.0.1', 7497, clientId=5001)
print("✓ Connected\n")

try:
    # Fetch 5-second bars
    contract = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(contract)

    print(f"Fetching 1-minute bars around entry time...")
    print(f"(Note: Using 1-min bars instead of 5-sec due to IBKR reliability)")

    bars = ib.reqHistoricalData(
        contract,
        endDateTime=entry_time + timedelta(minutes=2),
        durationStr='10 M',
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
        timeout=60
    )

    print(f"✓ Fetched {len(bars)} bars\n")

    # Find bar closest to entry time
    entry_bar_idx = None
    min_diff = 999999

    for i, bar in enumerate(bars):
        bar_time = bar.date.astimezone(eastern)
        diff = abs((bar_time - entry_time).total_seconds())
        if diff < min_diff:
            min_diff = diff
            entry_bar_idx = i

    if entry_bar_idx is None:
        print("❌ Could not find entry bar")
        sys.exit(1)

    entry_bar = bars[entry_bar_idx]
    entry_bar_time = entry_bar.date.astimezone(eastern)

    print(f"Entry Bar:")
    print(f"  Time: {entry_bar_time.strftime('%H:%M:%S')} ET (±{min_diff:.1f}s)")
    print(f"  Price: ${entry_bar.close:.2f}")
    print(f"  Volume: {entry_bar.volume:,}")
    print(f"  Candle: ${entry_bar.open:.2f} → ${entry_bar.close:.2f}")

    # Calculate average volume (last 10 1-min bars, since we have limited history)
    lookback = min(10, entry_bar_idx)
    if entry_bar_idx >= lookback:
        avg_volume = sum(bars[i].volume for i in range(entry_bar_idx-lookback+1, entry_bar_idx+1)) / lookback
    else:
        avg_volume = sum(bars[i].volume for i in range(0, entry_bar_idx+1)) / (entry_bar_idx + 1)

    volume_ratio = entry_bar.volume / avg_volume if avg_volume > 0 else 1.0

    # Calculate candle size
    candle_size_pct = abs(entry_bar.close - entry_bar.open) / entry_bar.open

    # Check previous bar for rising price
    if entry_bar_idx > 0:
        prev_bar = bars[entry_bar_idx - 1]
        is_rising = entry_bar.close > prev_bar.close
    else:
        is_rising = True

    print(f"\nMetrics (1-minute candle):")
    print(f"  Avg Volume ({lookback} bars): {avg_volume:,.0f}")
    print(f"  Volume Ratio: {volume_ratio:.2f}x")
    print(f"  Candle Size: {candle_size_pct*100:.2f}%")
    print(f"  Price Rising: {is_rising}")

    # Check filters
    volume_passed = volume_ratio >= pullback_volume_threshold
    candle_passed = candle_size_pct >= pullback_candle_threshold

    print(f"\nFilter Results:")
    print(f"  Volume: {'✓ PASS' if volume_passed else '✗ FAIL'} ({volume_ratio:.2f}x vs {pullback_volume_threshold:.1f}x required)")
    print(f"  Candle: {'✓ PASS' if candle_passed else '✗ FAIL'} ({candle_size_pct*100:.2f}% vs {pullback_candle_threshold*100:.1f}% required)")
    print(f"  Rising: {'✓ PASS' if is_rising else '✗ FAIL'}")

    all_passed = volume_passed and candle_passed and is_rising

    print()
    if all_passed:
        print(f"✅ PULLBACK/RETEST ENTRY VERIFIED - All filters passed correctly")
    else:
        print(f"❌ PULLBACK/RETEST ENTRY FAILED - Filters should have blocked this entry")

    # Show surrounding bars for context
    print(f"\n{'=' * 80}")
    print("Surrounding Bars (3 before/after):")
    print(f"{'=' * 80}")

    start_idx = max(0, entry_bar_idx - 3)
    end_idx = min(len(bars), entry_bar_idx + 4)

    for i in range(start_idx, end_idx):
        bar = bars[i]
        bar_time = bar.date.astimezone(eastern)

        # Calculate metrics for this bar
        bar_lookback = min(10, i)
        if i >= bar_lookback:
            bar_avg_vol = sum(bars[j].volume for j in range(i-bar_lookback+1, i+1)) / bar_lookback
        else:
            bar_avg_vol = sum(bars[j].volume for j in range(0, i+1)) / (i + 1)

        bar_vol_ratio = bar.volume / bar_avg_vol if bar_avg_vol > 0 else 1.0
        bar_candle_pct = abs(bar.close - bar.open) / bar.open

        marker = " ← ENTRY" if i == entry_bar_idx else ""
        print(f"  {bar_time.strftime('%H:%M')}: ${bar.close:7.2f}  vol={bar.volume:8,} ({bar_vol_ratio:4.1f}x)  candle={bar_candle_pct*100:4.2f}%{marker}")

finally:
    ib.disconnect()
    print("\nDisconnected from IBKR")
