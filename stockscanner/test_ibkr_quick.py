#!/usr/bin/env python3
"""
Quick test to verify IBKR reqHistoricalData is working
"""

from ib_insync import *
from datetime import datetime
import sys

def test_historical_data():
    """Test if reqHistoricalData is working"""
    print(f"Testing IBKR at {datetime.now().strftime('%H:%M:%S')}")

    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=999)
        print("✓ Connected to IBKR")

        # Test with SPY
        contract = Stock('SPY', 'SMART', 'USD')
        ib.qualifyContracts(contract)
        print("✓ Contract qualified")

        # Request historical data
        print("Requesting historical data...", end=' ')
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='5 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False
        )

        if bars:
            print(f"✓ Got {len(bars)} bars")
            latest = bars[-1]
            print(f"Latest: ${latest.close:.2f} on {latest.date}")
            return True
        else:
            print("✗ No data received")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()

if __name__ == "__main__":
    success = test_historical_data()
    sys.exit(0 if success else 1)