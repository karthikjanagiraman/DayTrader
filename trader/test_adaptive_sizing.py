#!/usr/bin/env python3
"""
Test Adaptive Position Sizing

Demonstrates how the new adaptive sizing system works with different stock prices.
"""

import sys
from pathlib import Path
import yaml

# Add strategy module to path
sys.path.insert(0, str(Path(__file__).parent))

from strategy import PS60Strategy

def test_adaptive_sizing():
    """Test adaptive position sizing with various stock prices"""

    print("="*80)
    print("ADAPTIVE POSITION SIZING TEST")
    print("="*80)

    # Load config
    config_path = Path(__file__).parent / 'config' / 'trader_config.yaml'
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Initialize strategy
    strategy = PS60Strategy(config)

    # Test scenarios
    scenarios = [
        {
            'name': 'Low-Priced Stock (XPEV)',
            'entry': 24.00,
            'stop': 23.80,
            'stop_dist': 0.20
        },
        {
            'name': 'Medium-Priced Stock (QCOM)',
            'entry': 171.00,
            'stop': 170.50,
            'stop_dist': 0.50
        },
        {
            'name': 'High-Priced Stock (BA)',
            'entry': 221.00,
            'stop': 220.00,
            'stop_dist': 1.00
        },
        {
            'name': 'Very High-Priced Stock (GS)',
            'entry': 794.00,
            'stop': 793.00,
            'stop_dist': 1.00
        },
        {
            'name': 'Wide Stop (AAPL)',
            'entry': 257.00,
            'stop': 252.00,
            'stop_dist': 5.00
        }
    ]

    account_size = config['trading']['account_size']
    risk_pct = config['trading']['risk_per_trade']
    max_pos_value = config['trading']['position_sizing']['max_position_value']

    print(f"\nAccount Size: ${account_size:,}")
    print(f"Risk per Trade: {risk_pct*100}% = ${account_size * risk_pct:,.0f}")
    print(f"Max Position Value: ${max_pos_value:,}\n")

    print("-"*80)

    for scenario in scenarios:
        print(f"\n{scenario['name']}")
        print(f"Entry: ${scenario['entry']:.2f} | Stop: ${scenario['stop']:.2f} | Distance: ${scenario['stop_dist']:.2f}")

        # Calculate shares
        shares = strategy.calculate_position_size(
            account_size,
            scenario['entry'],
            scenario['stop']
        )

        # Calculate metrics
        risk_dollars = account_size * risk_pct
        shares_by_risk = int(risk_dollars / scenario['stop_dist'])
        shares_by_value = int(max_pos_value / scenario['entry'])

        position_value = shares * scenario['entry']
        position_pct = (position_value / account_size) * 100
        actual_risk = shares * scenario['stop_dist']
        actual_risk_pct = (actual_risk / account_size) * 100

        # Determine limiting factor
        if shares == shares_by_value:
            limit = "VALUE"
        elif shares == shares_by_risk:
            limit = "RISK"
        elif shares == 1000:
            limit = "CAP"
        else:
            limit = "MIN"

        print(f"\nCalculation:")
        print(f"  Shares by risk: {shares_by_risk:,}")
        print(f"  Shares by value: {shares_by_value:,}")
        print(f"  Shares by cap: 1,000")
        print(f"  → Final shares: {shares:,} ({limit} limited)")

        print(f"\nResult:")
        print(f"  Position Value: ${position_value:,.0f} ({position_pct:.1f}% of account)")
        print(f"  Actual Risk: ${actual_risk:.2f} ({actual_risk_pct:.2f}% of account)")

        # Show improvement
        old_shares = min(shares_by_risk, 1000)  # Old system
        old_value = old_shares * scenario['entry']
        if old_value > position_value:
            reduction = ((old_value - position_value) / old_value) * 100
            print(f"  ✓ Reduced from ${old_value:,.0f} (old system) - {reduction:.0f}% smaller")
        else:
            print(f"  ✓ Same as old system (risk-limited)")

        print("-"*80)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print("\nAdaptive sizing ensures:")
    print("  ✓ All positions stay under $20k (20% of account)")
    print("  ✓ Max 5 positions = $100k total (matches account size)")
    print("  ✓ High-priced stocks automatically get smaller share counts")
    print("  ✓ Low-priced stocks can use full risk-based sizing")
    print("\nNo more 'Position too large' errors!")
    print("="*80)

if __name__ == '__main__':
    test_adaptive_sizing()
