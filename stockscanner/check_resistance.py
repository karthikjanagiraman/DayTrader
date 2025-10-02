#!/usr/bin/env python3
"""
Check TSLA's actual price action to find real resistance
"""

import json

print('REVIEWING TSLA RESISTANCE CALCULATION')
print('='*70)

with open('output/scanner_results.json', 'r') as f:
    data = json.load(f)

for stock in data:
    if stock['symbol'] == 'TSLA':
        print(f"Current Price: ${stock['close']:.2f}")
        print(f"Scanner shows resistance: ${stock['resistance']:.2f}")
        print(f"Scanner shows support: ${stock['support']:.2f}")
        print(f"Distance to resistance: {stock['dist_to_R%']:.2f}%")
        print()
        print('ISSUE IDENTIFIED:')
        print('-'*70)
        print('The scanner is using the 5-day HIGH (intraday high) as resistance.')
        print('But if TSLA only briefly spiked to $450.98 and immediately')
        print('fell back to $444, then the REAL resistance is where it')
        print('got rejected multiple times - likely around $444-445.')
        print()
        print('What the scanner SHOULD look for:')
        print('1. Consolidation zone ceiling (where price spent TIME)')
        print('2. Level tested multiple times without breaking through')
        print('3. NOT just the spike high that was immediately rejected')
        print()
        print('RECOMMENDATION:')
        print('The scanner needs to differentiate between:')
        print('  - Spike highs (brief touches)')
        print('  - True resistance (tested multiple times, price consolidates below)')
        break