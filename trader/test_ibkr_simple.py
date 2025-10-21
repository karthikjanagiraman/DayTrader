from ib_insync import IB
import time

ib = IB()
print('Connecting to IBKR...')
try:
    ib.connect('127.0.0.1', 7497, clientId=9998, timeout=10)
    print('✓ Connected successfully')

    print(f'Connection state: {ib.isConnected()}')
    print(f'Client ID: {ib.client.clientId}')

    # Check active connections
    print('\nWaiting 2 seconds...')
    time.sleep(2)

    print('✓ Connection stable')

    ib.disconnect()
    print('✓ Disconnected')

except Exception as e:
    print(f'❌ Error: {e}')
    import traceback
    traceback.print_exc()
