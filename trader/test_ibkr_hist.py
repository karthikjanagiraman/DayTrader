from ib_insync import IB, Stock
from datetime import datetime, timedelta
import pytz

ib = IB()
print('Connecting to IBKR...')
ib.connect('127.0.0.1', 7497, clientId=9997)
print('✓ Connected')

try:
    # Test fetching yesterday's data (more reliable)
    contract = Stock('AAPL', 'SMART', 'USD')
    ib.qualifyContracts(contract)
    print(f'✓ Contract qualified: {contract}')

    eastern = pytz.timezone('US/Eastern')
    yesterday = datetime.now(eastern) - timedelta(days=1)
    yesterday_eod = yesterday.replace(hour=16, minute=0, second=0, microsecond=0)

    print(f'\nFetching 5-min bars for AAPL (yesterday {yesterday_eod.date()})...')
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=yesterday_eod,
        durationStr='1 D',
        barSizeSetting='5 mins',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
        timeout=20
    )

    print(f'✓ Fetched {len(bars)} bars')
    if bars:
        print(f'First: {bars[0].date} - ${bars[0].close:.2f}')
        print(f'Last: {bars[-1].date} - ${bars[-1].close:.2f}')
    else:
        print('⚠️  No bars returned')

except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()

finally:
    ib.disconnect()
    print('\nDisconnected')
