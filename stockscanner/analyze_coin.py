#!/usr/bin/env python3
"""Analyze COIN resistance calculation for Oct 9, 2025"""

from ib_insync import IB, Stock
from datetime import datetime

# Connect to IBKR
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=5001)

# Get COIN contract
contract = Stock('COIN', 'SMART', 'USD')
ib.qualifyContracts(contract)

# Request daily bars for the week before Oct 9
end_date = datetime(2025, 10, 9)
bars = ib.reqHistoricalData(
    contract,
    endDateTime=end_date.strftime('%Y%m%d 23:59:59'),
    durationStr='10 D',
    barSizeSetting='1 day',
    whatToShow='TRADES',
    useRTH=True
)

print('COIN Daily Bars (Oct 9 lookback):')
print('='*80)
for bar in bars:
    print(f'{bar.date.strftime("%Y-%m-%d")}: High=${bar.high:.2f}, Low=${bar.low:.2f}, Close=${bar.close:.2f}, Volume={bar.volume:,}')

print()
print('Scanner resistance: $390.49')
print('Scanner says: "Tested 3x"')
print()

# Check which days had highs near $390.49
print('Analysis: Which highs cluster near $390.49?')
near_resistance = []
for bar in bars:
    diff = abs(bar.high - 390.49)
    pct_diff = (diff / 390.49) * 100
    if pct_diff < 1.0:  # Within 1%
        near_resistance.append(bar)
        print(f'  {bar.date.strftime("%Y-%m-%d")}: High ${bar.high:.2f} (${diff:.2f} or {pct_diff:.2f}% away)')

print(f'\nTotal bars within 1% of $390.49: {len(near_resistance)}')

# Check all daily highs
print('\nAll daily highs (last 10 days):')
sorted_highs = sorted([(b.date, b.high) for b in bars], key=lambda x: x[1], reverse=True)
for date, high in sorted_highs:
    print(f'  {date.strftime("%Y-%m-%d")}: ${high:.2f}')

ib.disconnect()
