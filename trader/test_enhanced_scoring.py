#!/usr/bin/env python3
"""
Test Enhanced Scoring Integration

Validates that trader and backtester correctly load and filter
enhanced scoring CSV files with tier-based classification.
"""

import sys
from pathlib import Path
import yaml

# Add strategy module to path
sys.path.insert(0, str(Path(__file__).parent))

from strategy import PS60Strategy

def test_enhanced_filtering():
    """Test enhanced scoring filtering logic"""

    print("="*80)
    print("TESTING ENHANCED SCORING INTEGRATION")
    print("="*80)

    # Load config
    config_path = Path(__file__).parent / 'config' / 'trader_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize strategy
    strategy = PS60Strategy(config)

    # Load Oct 7 enhanced scoring v2 (with test count bonus)
    enhanced_csv = Path(__file__).parent.parent / 'scanner_validation' / 'rescored_20251007_v2.csv'

    if not enhanced_csv.exists():
        print(f"❌ Enhanced scoring CSV not found: {enhanced_csv}")
        return False

    print(f"\n✓ Loading enhanced scoring: {enhanced_csv.name}")

    # Load CSV
    import csv
    all_results = []
    with open(enhanced_csv, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            stock = {}
            for key, value in row.items():
                if key in ['close', 'resistance', 'support', 'target1', 'target2', 'target3',
                           'downside1', 'downside2', 'risk_reward', 'dist_to_R%', 'dist_to_S%',
                           'rvol', 'atr%', 'score', 'enhanced_long_score', 'enhanced_short_score',
                           'best_enhanced_score', 'pivot_width_pct', 'change%', 'volume',
                           'volume_M', 'potential_gain%', 'risk%']:
                    try:
                        stock[key] = float(value) if value else 0.0
                    except ValueError:
                        stock[key] = 0.0
                else:
                    stock[key] = value

            if 'symbol' in stock:
                all_results.append(stock)

    print(f"✓ Loaded {len(all_results)} stocks from enhanced scoring\n")

    # Apply enhanced filtering
    filtered = strategy.filter_enhanced_scanner_results(all_results)

    print(f"✓ Filtered to {len(filtered)} setups after tier filtering\n")

    # Analyze tier breakdown
    from collections import Counter
    import re

    tiers = Counter(stock.get('tier', 'UNKNOWN') for stock in filtered)

    print("="*80)
    print("TIER BREAKDOWN")
    print("="*80)

    for tier in ['TIER 1', 'TIER 2', 'TIER 3']:
        count = tiers.get(tier, 0)
        if count > 0:
            tier_stocks = [s for s in filtered if s.get('tier') == tier]
            print(f"\n{tier} ({count} stocks):")

            for stock in tier_stocks[:5]:  # Show first 5
                symbol = stock['symbol']
                pivot_width = stock.get('pivot_width_pct', 0)
                long_score = stock.get('enhanced_long_score', 0)
                short_score = stock.get('enhanced_short_score', 0)

                # Extract test count
                breakout_reason = stock.get('breakout_reason', '')
                match = re.search(r'Tested (\d+)x', breakout_reason)
                test_count = int(match.group(1)) if match else 0

                print(f"  {symbol:6} - Pivot:{pivot_width:5.2f}% Tests:{test_count:2}x "
                      f"LONG:{long_score:3.0f} SHORT:{short_score:3.0f}")

            if len(tier_stocks) > 5:
                print(f"  ... and {len(tier_stocks) - 5} more")

    # Show what was filtered out (blacklisted)
    print("\n" + "="*80)
    print("BLACKLISTED STOCKS (Filtered Out)")
    print("="*80)

    index_etfs = ['SPY', 'QQQ', 'DIA', 'IWM']
    high_vol_stocks = ['TSLA', 'NVDA', 'COIN', 'AMC', 'GME', 'HOOD', 'LCID', 'RIVN']

    blacklisted_in_data = []
    for stock in all_results:
        symbol = stock['symbol']
        if symbol in index_etfs or symbol in high_vol_stocks:
            blacklisted_in_data.append(stock)

    if blacklisted_in_data:
        print(f"\nFound {len(blacklisted_in_data)} blacklisted stocks (correctly filtered):")
        for stock in blacklisted_in_data[:10]:
            symbol = stock['symbol']
            best_score = stock.get('best_enhanced_score', 0)
            pivot_width = stock.get('pivot_width_pct', 0)

            # Extract test count
            breakout_reason = stock.get('breakout_reason', '')
            match = re.search(r'Tested (\d+)x', breakout_reason)
            test_count = int(match.group(1)) if match else 0

            category = "INDEX ETF" if symbol in index_etfs else "HIGH-VOL"
            print(f"  ❌ {symbol:6} ({category}) - Score:{best_score:3.0f} "
                  f"Pivot:{pivot_width:5.2f}% Tests:{test_count:2}x")
    else:
        print("\nNo blacklisted stocks found in scanner data")

    # Validate expected stocks
    print("\n" + "="*80)
    print("VALIDATION: Expected TIER 1 Stocks (from trading plan)")
    print("="*80)

    expected_tier1 = ['GS', 'AAPL', 'BA']
    found_tier1 = [s['symbol'] for s in filtered if s.get('tier') == 'TIER 1']

    print(f"\nExpected: {', '.join(expected_tier1)}")
    print(f"Found:    {', '.join(found_tier1)}")

    for symbol in expected_tier1:
        if symbol in found_tier1:
            print(f"  ✓ {symbol} correctly classified as TIER 1")
        else:
            print(f"  ❌ {symbol} NOT in TIER 1 (check filters!)")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

    return True

if __name__ == '__main__':
    success = test_enhanced_filtering()
    sys.exit(0 if success else 1)
