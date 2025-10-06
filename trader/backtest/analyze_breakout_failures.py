#!/usr/bin/env python3
"""
Deep dive: Why did check_hybrid_entry() never confirm LONG breakouts?
Analyzes actual 5-second bar data to see if stocks ever met the criteria:
- Price > resistance
- Volume >= 1.3x average
- Candle >= 0.8% OR >= 2x ATR
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def analyze_breakout_opportunities(date_str='2025-09-25'):
    """
    For a given day, check if ANY stocks had breakout opportunities
    that met the hybrid entry criteria but weren't taken
    """

    # Load scanner data for that day
    scanner_file = Path(__file__).parent.parent.parent / "stockscanner" / "output" / f"scanner_results_{date_str.replace('-', '')}.json"

    if not scanner_file.exists():
        print(f"⚠️  Scanner file not found: {scanner_file}")
        return

    with open(scanner_file) as f:
        scanner_data = json.load(f)

    print("\n" + "="*80)
    print(f"BREAKOUT OPPORTUNITY ANALYSIS - {date_str}")
    print("="*80)

    # Filter to stocks that passed scanner filters
    min_score = 50
    min_rr = 1.0
    max_dist = 2.0

    filtered_stocks = []
    for stock in scanner_data:
        if (stock.get('score', 0) >= min_score and
            stock.get('risk_reward', 0) >= min_rr and
            abs(stock.get('dist_to_R%', 100)) <= max_dist):
            filtered_stocks.append(stock)

    print(f"\nStocks in watchlist (score>={min_score}, R/R>={min_rr}, dist<={max_dist}%):")
    print(f"  Total: {len(filtered_stocks)}")

    if not filtered_stocks:
        print("  No stocks passed filters!")
        return

    # Show top 10 by score
    top_stocks = sorted(filtered_stocks, key=lambda x: x.get('score', 0), reverse=True)[:10]

    print(f"\nTop 10 stocks by score:")
    print(f"{'Symbol':<8} {'Close':<10} {'Resistance':<12} {'Dist%':<8} {'Score':<8} {'R/R':<6}")
    print("-"*70)
    for s in top_stocks:
        print(f"{s['symbol']:<8} ${s['close']:<9.2f} ${s['resistance']:<11.2f} {s.get('dist_to_R%', 0):<7.2f}% {s.get('score', 0):<8} {s.get('risk_reward', 0):<6.2f}")

    # Now check if we have bar data for any of these stocks
    cache_dir = Path(__file__).parent / "cache"

    print("\n" + "-"*80)
    print("CHECKING FOR CACHED BAR DATA:")
    print("-"*80)

    stocks_with_data = []
    for stock in top_stocks[:5]:  # Check top 5
        symbol = stock['symbol']
        cache_file = cache_dir / f"{symbol}_{date_str.replace('-', '')}_bars.json"

        if cache_file.exists():
            stocks_with_data.append((stock, cache_file))
            print(f"  ✓ {symbol}: Found cached data")
        else:
            print(f"  ✗ {symbol}: No cached data")

    if not stocks_with_data:
        print("\n⚠️  No cached bar data found. Cannot analyze breakout opportunities.")
        print("Run backtest first to generate cached bar data.")
        return

    # Analyze each stock with data
    for stock, cache_file in stocks_with_data:
        analyze_stock_breakout_potential(stock, cache_file, date_str)

def analyze_stock_breakout_potential(stock, cache_file, date_str):
    """
    Analyze if this stock had any breakout opportunities during the day
    """

    symbol = stock['symbol']
    resistance = stock['resistance']
    close_price = stock['close']

    print("\n" + "="*80)
    print(f"ANALYZING: {symbol}")
    print("="*80)
    print(f"Prior close: ${close_price:.2f}")
    print(f"Resistance: ${resistance:.2f} ({abs((resistance - close_price)/close_price*100):.2f}% away)")

    # Load bar data
    with open(cache_file) as f:
        bars = json.load(f)

    if not bars:
        print("  No bar data available")
        return

    print(f"Total bars: {len(bars)}")

    # Simulate checking for breakout confirmation on each bar
    # This is what check_hybrid_entry() does

    breakout_attempts = []
    volume_history = []

    for i, bar_data in enumerate(bars):
        # Convert bar data to object-like access
        class Bar:
            def __init__(self, data):
                self.date = datetime.fromisoformat(data['date'].replace('Z', '+00:00'))
                self.open = data['open']
                self.high = data['high']
                self.low = data['low']
                self.close = data['close']
                self.volume = data['volume']

        bar = Bar(bar_data)

        # Track volume history for average calculation
        if bar.volume > 0:
            volume_history.append(bar.volume)

        # Check if price broke resistance
        if bar.close > resistance:
            # Calculate volume ratio
            if len(volume_history) >= 20:
                avg_volume = sum(volume_history[-20:]) / 20
                volume_ratio = bar.volume / avg_volume if avg_volume > 0 else 0
            else:
                volume_ratio = 0

            # Calculate candle size
            candle_size = abs(bar.close - bar.open)
            candle_pct = (candle_size / bar.open) if bar.open > 0 else 0

            # Calculate recent ATR (simplified - just use recent range)
            if i >= 20:
                recent_ranges = []
                for j in range(max(0, i-20), i):
                    prev_bar = Bar(bars[j])
                    recent_ranges.append(prev_bar.high - prev_bar.low)
                atr = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0
                candle_atr_ratio = candle_size / atr if atr > 0 else 0
            else:
                atr = 0
                candle_atr_ratio = 0

            # Check if this would qualify as momentum breakout
            is_strong_volume = volume_ratio >= 1.3
            is_large_candle = candle_pct >= 0.008 or candle_atr_ratio >= 2.0

            if bar.close > resistance and (is_strong_volume or is_large_candle or volume_ratio > 1.0):
                breakout_attempts.append({
                    'time': bar.date,
                    'bar_num': i,
                    'price': bar.close,
                    'volume_ratio': volume_ratio,
                    'candle_pct': candle_pct * 100,
                    'candle_atr': candle_atr_ratio,
                    'atr': atr,
                    'is_strong_volume': is_strong_volume,
                    'is_large_candle': is_large_candle,
                    'qualified': is_strong_volume and is_large_candle
                })

    # Report findings
    if not breakout_attempts:
        print("\n  ✗ NO breakout attempts above resistance during the day")
        print(f"  (Price never exceeded ${resistance:.2f})")
    else:
        print(f"\n  Found {len(breakout_attempts)} bars where price > resistance:")
        print("\n  Checking which ones met MOMENTUM BREAKOUT criteria:")
        print("  (Need: Volume ≥1.3x AND (Candle ≥0.8% OR Candle ≥2x ATR))")
        print()
        print(f"  {'Time':<12} {'Price':<10} {'Vol':<8} {'Candle%':<10} {'ATR':<8} {'Qualified?':<12}")
        print("  " + "-"*70)

        qualified = 0
        for attempt in breakout_attempts[:20]:  # Show first 20
            q = "✓ YES" if attempt['qualified'] else "✗ NO"
            print(f"  {attempt['time'].strftime('%H:%M:%S'):<12} "
                  f"${attempt['price']:<9.2f} "
                  f"{attempt['volume_ratio']:<7.2f}x "
                  f"{attempt['candle_pct']:<9.2f}% "
                  f"{attempt['candle_atr']:<7.2f}x "
                  f"{q:<12}")

            if attempt['qualified']:
                qualified += 1

        if len(breakout_attempts) > 20:
            print(f"  ... and {len(breakout_attempts) - 20} more")

        print()
        print(f"  QUALIFIED MOMENTUM BREAKOUTS: {qualified}/{len(breakout_attempts)}")

        if qualified == 0:
            print("\n  ANALYSIS: Why none qualified:")
            # Find best attempt
            best_volume = max(breakout_attempts, key=lambda x: x['volume_ratio'])
            best_candle = max(breakout_attempts, key=lambda x: x['candle_pct'])

            print(f"    Best volume: {best_volume['volume_ratio']:.2f}x (need ≥1.3x)")
            print(f"    Best candle: {best_candle['candle_pct']:.2f}% (need ≥0.8%)")
            print()
            print("  → Volume was TOO LOW (no surge)")
            print("  → Candles were TOO SMALL (no momentum)")
            print("  → This explains why NO long breakouts entered!")

def main():
    """Run analysis for Sept 25 (the day with 1 winner - PLTR)"""

    print("\n" + "="*80)
    print("WHY DID check_hybrid_entry() NEVER CONFIRM LONG BREAKOUTS?")
    print("="*80)
    print("\nAnalyzing Sept 25, 2025 (the day with the 1 winner)")

    analyze_breakout_opportunities('2025-09-25')

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)
    print("\nThe analysis will show:")
    print("  1. Were there stocks above resistance? (YES/NO)")
    print("  2. Did they have volume surges? (likely NO)")
    print("  3. Did they have large candles? (likely NO)")
    print("  4. Why didn't breakouts trigger? (criteria too strict for market)")
    print()
    print("If NO stocks met the criteria, then:")
    print("  → Breakout confirmation is TOO STRICT for this market")
    print("  → Need to RELAX volume/candle thresholds")
    print("  → OR accept that Sept 23-30 was just a bad market for breakouts")

if __name__ == "__main__":
    main()
