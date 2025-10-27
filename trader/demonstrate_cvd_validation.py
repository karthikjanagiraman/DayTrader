#!/usr/bin/env python3
"""
Demonstrate CVD Price Validation (Oct 26, 2025 - Phase 2 Fix)

Shows enhanced CVD calculator output with price validation for SMCI bars.
Demonstrates how CVD signal alignment with price movement is detected.
"""

import json
import sys
from pathlib import Path

# Add trader directory to path
sys.path.insert(0, str(Path(__file__).parent))

from indicators.cvd_calculator import CVDCalculator

class MockTick:
    """Mock tick object for CVD calculator"""
    def __init__(self, time, price, size):
        self.time = time
        self.price = price
        self.size = size

def analyze_bar_with_validation(bar_time, tick_file, bar_data):
    """Analyze a single bar with CVD price validation"""

    # Load tick data
    with open(tick_file) as f:
        tick_data = json.load(f)

    if not tick_data:
        print(f"❌ {bar_time}: No tick data")
        return

    # Convert to MockTick objects
    ticks = [MockTick(t['time'], t['price'], t['size']) for t in tick_data]

    # Create mock bar object for validation
    class MockBar:
        def __init__(self, bar_dict):
            self.open = bar_dict['open']
            self.close = bar_dict['close']
            self.high = bar_dict['high']
            self.low = bar_dict['low']
            self.volume = bar_dict['volume']

    mock_bar = MockBar(bar_data) if bar_data else None

    # Calculate CVD with price validation (now using bar open/close)
    calculator = CVDCalculator(imbalance_threshold=10.0)
    result = calculator.calculate_from_ticks(ticks, bar=mock_bar)

    # Print detailed analysis
    print(f"\n{'='*80}")
    print(f"SMCI Bar {bar_time} - CVD with Price Validation")
    print(f"{'='*80}")

    print(f"\n📊 Tick Classification:")
    print(f"   Total Ticks: {len(ticks):,}")
    print(f"   Buy Volume:  {result.buy_volume:>10,.0f}")
    print(f"   Sell Volume: {result.sell_volume:>10,.0f}")
    print(f"   Total Volume: {result.buy_volume + result.sell_volume:>10,.0f}")
    print(f"   CVD Imbalance: {result.imbalance_pct:+.2f}%")
    print(f"   CVD Trend: {result.cvd_trend}")

    print(f"\n📈 Candle Analysis (Open vs Close):")
    if bar_data:
        candle_color = 'GREEN' if result.price_direction == 'UP' else ('RED' if result.price_direction == 'DOWN' else 'DOJI')
        print(f"   Open:  ${bar_data['open']:.2f}")
        print(f"   Close: ${bar_data['close']:.2f}")
        print(f"   Change: ${bar_data['close'] - bar_data['open']:+.2f} ({result.price_change_pct:+.2f}%)")
        print(f"   Candle Color: {candle_color} ({result.price_direction})")
    else:
        print(f"   No bar data available")

    # Add bar data if available
    if bar_data:
        print(f"\n📊 1-Minute Bar Data:")
        print(f"   Open:  ${bar_data['open']:.2f}")
        print(f"   High:  ${bar_data['high']:.2f}")
        print(f"   Low:   ${bar_data['low']:.2f}")
        print(f"   Close: ${bar_data['close']:.2f}")
        print(f"   Volume: {bar_data['volume']:,.0f}")

    print(f"\n✅ Validation Result:")
    if result.signals_aligned:
        print(f"   Signals Aligned: YES ✅")
        candle_color = 'GREEN' if result.price_direction == 'UP' else ('RED' if result.price_direction == 'DOWN' else 'DOJI')
        print(f"   CVD {result.cvd_trend} matches {candle_color} candle")
        print(f"   → This would be a VALID entry signal")
    else:
        print(f"   Signals Aligned: NO ❌")
        print(f"   {result.validation_reason}")
        print(f"   → This should BLOCK entry (CVD and candle color disagree)")

    return result

def main():
    """Analyze SMCI bars 10:00-10:03 with CVD price validation"""

    base_path = Path('/Users/karthik/projects/DayTrader/trader/backtest/data/ticks')
    bar_file = Path('/Users/karthik/projects/DayTrader/trader/backtest/data/SMCI_20251021_1min.json')

    # Load 1-minute bar data
    with open(bar_file) as f:
        bars_data = json.load(f)

    # Create bar lookup by time
    bars_by_time = {}
    for bar in bars_data:
        time_str = bar['date'].split('T')[1].split('-')[0][:5]
        bars_by_time[time_str] = bar

    # Bars to analyze
    bars = [
        ('10:00', 'SMCI_20251021_100000_ticks.json'),
        ('10:01', 'SMCI_20251021_100100_ticks.json'),
        ('10:02', 'SMCI_20251021_100200_ticks.json'),
        ('10:03', 'SMCI_20251021_100300_ticks.json')
    ]

    print("="*80)
    print("SMCI CVD PRICE VALIDATION DEMONSTRATION")
    print("October 21, 2025 - Bars 10:00-10:03")
    print("="*80)
    print("\nThis demonstrates the NEW price validation feature that checks if CVD")
    print("signals align with candle color (Open vs Close).")
    print("\nKey Concept:")
    print("  • BEARISH CVD (more selling) should produce RED candle (Close < Open)")
    print("  • BULLISH CVD (more buying) should produce GREEN candle (Close > Open)")
    print("  • If CVD and candle color disagree → BLOCK entry (absorption/reversal)")

    results = []
    for time, filename in bars:
        tick_file = base_path / filename

        if not tick_file.exists():
            print(f"\n❌ {time}: File not found - {filename}")
            continue

        bar_data = bars_by_time.get(time)
        result = analyze_bar_with_validation(time, tick_file, bar_data)
        results.append((time, result))

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY - Which bars should be tradeable?")
    print(f"{'='*80}")

    for time, result in results:
        candle_color = 'GREEN' if result.price_direction == 'UP' else ('RED' if result.price_direction == 'DOWN' else 'DOJI')
        if result.signals_aligned:
            print(f"✅ {time}: CVD {result.cvd_trend} + {candle_color} candle = ALIGNED → Trade OK")
        else:
            print(f"❌ {time}: CVD {result.cvd_trend} + {candle_color} candle = MISALIGNED → BLOCK ENTRY")

    # Highlight the critical bar 34 (10:03)
    print(f"\n{'='*80}")
    print("CRITICAL FINDING - Bar 34 (10:03)")
    print(f"{'='*80}")
    print("\nThis is the bar that caused the bad SMCI SHORT entry on Oct 21:")
    print("  • CVD showed BEARISH (+22.08% selling pressure) → System wanted to SHORT")
    print("  • But candle was GREEN (Close $54.28 > Open $54.19) → Buyers won!")
    print("  • Result: Entered SHORT into GREEN candle → Immediate loss -$202.90")
    print("\nWith price validation (Open vs Close):")
    print("  • CVD calculator detects: signals_aligned = False")
    print("  • Validation reason: 'CVD BEARISH but GREEN candle'")
    print("  • Entry logic checks: if not signals_aligned → BLOCK entry")
    print("  • Result: Entry blocked, loss avoided ✅")

if __name__ == '__main__':
    main()
