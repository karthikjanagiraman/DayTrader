from ib_insync import IB, Stock
from datetime import datetime
import pytz

ib = IB()
print('Connecting to IBKR...')
ib.connect('127.0.0.1', 7497, clientId=9999)
print('✓ Connected')

# Test fetching 1-min bars for SPY (more reliable)
contract = Stock('SPY', 'SMART', 'USD')
ib.qualifyContracts(contract)

print('\nFetching 1-min bars for SPY...')
bars = ib.reqHistoricalData(
    contract,
    endDateTime='',  # Use most recent data
    durationStr='1 D',
    barSizeSetting='1 min',
    whatToShow='TRADES',
    useRTH=True,
    formatDate=1,
    timeout=30
)

print(f'✓ Fetched {len(bars)} bars')
if bars:
    print(f'First bar: {bars[0].date} - ${bars[0].close:.2f} - vol={bars[0].volume:,}')
    print(f'Last bar: {bars[-1].date} - ${bars[-1].close:.2f} - vol={bars[-1].volume:,}')

ib.disconnect()
print('\n✓ IBKR APIs working!')
