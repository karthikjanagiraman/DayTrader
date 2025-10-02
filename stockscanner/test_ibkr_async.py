#!/usr/bin/env python3
"""
Test IBKR with async approach
"""

from ib_insync import *
import asyncio
from datetime import datetime

async def test_async():
    """Test with async approach"""
    print(f"Testing IBKR async at {datetime.now().strftime('%H:%M:%S')}")

    ib = IB()
    await ib.connectAsync('127.0.0.1', 7497, clientId=1000)
    print("✓ Connected")

    try:
        contract = Stock('SPY', 'SMART', 'USD')
        await ib.qualifyContractsAsync(contract)
        print("✓ Contract qualified")

        # Request with timeout
        print("Requesting data...")
        bars = await asyncio.wait_for(
            ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr='2 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False
            ),
            timeout=5.0
        )

        if bars:
            print(f"✓ Got {len(bars)} bars")
            latest = bars[-1]
            print(f"Latest: ${latest.close:.2f}")
        else:
            print("✗ No data")

    except asyncio.TimeoutError:
        print("✗ Timeout")
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(test_async())