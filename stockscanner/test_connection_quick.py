#!/usr/bin/env python3
"""
Quick test of IBKR connection
"""

from ib_insync import IB, Stock
import time

def quick_test():
    """Quick connection test"""
    print("Testing IBKR connection...")

    ib = IB()
    try:
        # Try different client IDs in case one is stuck
        for client_id in [999, 998, 997]:
            try:
                print(f"Trying client_id {client_id}...")
                ib.connect('127.0.0.1', 7497, clientId=client_id, timeout=5)
                print(f"✓ Connected with client_id {client_id}")

                # Test basic functionality
                contract = Stock('AAPL', 'SMART', 'USD')
                ib.qualifyContracts(contract)
                print(f"✓ Contract qualified: {contract.conId}")

                # Quick data test
                bars = ib.reqHistoricalData(
                    contract,
                    endDateTime='',
                    durationStr='1 D',
                    barSizeSetting='1 hour',
                    whatToShow='TRADES',
                    useRTH=False
                )
                print(f"✓ Got {len(bars)} bars")

                ib.disconnect()
                return True

            except Exception as e:
                print(f"✗ Client {client_id} failed: {e}")
                if ib.isConnected():
                    ib.disconnect()
                time.sleep(1)

    except Exception as e:
        print(f"Connection test failed: {e}")

    return False

if __name__ == "__main__":
    if quick_test():
        print("\n✅ IBKR connection working!")
    else:
        print("\n❌ IBKR connection failed!")