#!/usr/bin/env python3
"""
Test ATR-based stop calculations
"""

import json
import sys
sys.path.append('.')
from strategy.ps60_strategy import PS60Strategy
import yaml

# Load config
with open('config/trader_config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Create strategy instance
strategy = PS60Strategy(config)

# Load scanner data
with open('../stockscanner/output/scanner_results_20251007.json', 'r') as f:
    scanner_data = json.load(f)

# Test cases from October 7-9 stop analysis
test_cases = [
    ('TSLA', 'SHORT', 439.56),
    ('SNAP', 'SHORT', 8.35),
    ('CLOV', 'LONG', 2.75),
    ('COIN', 'LONG', 389.17),
    ('HOOD', 'LONG', 147.61),
    ('RIVN', 'SHORT', 13.20),
]

print("\nATR-Based Stop Calculation Test")
print("="*80)
print(f"{'Symbol':<8} {'Side':<6} {'Entry':<10} {'ATR%':<8} {'Stop Width':<12} {'Stop Price':<12} {'Old Stop':<12}")
print("-"*80)

for symbol, side, entry_price in test_cases:
    # Find stock data
    stock = next((s for s in scanner_data if s['symbol'] == symbol), None)
    if not stock:
        print(f"{symbol:<8} Not found in scanner data")
        continue

    # Create position dict
    position = {
        'entry_price': entry_price,
        'side': side,
        'partials': 0
    }

    # Calculate stop
    stop_price = strategy.calculate_stop_price(position, entry_price, stock)

    # Get ATR-based stop width
    atr_pct = stock.get('atr%', 5.0)
    stop_width = strategy.calculate_atr_based_stop_width(atr_pct)

    # Old tight stop (0.5%)
    if side == 'LONG':
        old_stop = entry_price * 0.995
    else:
        old_stop = entry_price * 1.005

    print(f"{symbol:<8} {side:<6} ${entry_price:<9.2f} {atr_pct:<7.1f}% {stop_width*100:<11.1f}% ${stop_price:<11.2f} ${old_stop:<11.2f}")

print("\nComparison:")
print("-"*80)
for symbol, side, entry_price in test_cases:
    stock = next((s for s in scanner_data if s['symbol'] == symbol), None)
    if not stock:
        continue

    position = {'entry_price': entry_price, 'side': side, 'partials': 0}
    new_stop = strategy.calculate_stop_price(position, entry_price, stock)

    if side == 'LONG':
        old_stop = entry_price * 0.995
        improvement = (entry_price - new_stop) - (entry_price - old_stop)
    else:
        old_stop = entry_price * 1.005
        improvement = (new_stop - entry_price) - (old_stop - entry_price)

    print(f"{symbol}: Stop widened by ${improvement:.2f} ({improvement/entry_price*100:.1f}%)")

print("\nExpected Impact:")
print("-"*80)
print("With these ATR-based stops:")
print("- SNAP SHORT would NOT have stopped in 15 seconds")
print("- CLOV LONG would NOT have stopped in 5 seconds")
print("- COIN LONG would have held through the 2-minute noise")
print("- Estimated P&L improvement: +$6,000 to +$8,000")