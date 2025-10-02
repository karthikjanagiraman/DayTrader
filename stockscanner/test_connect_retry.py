#!/usr/bin/env python3
"""
Test connection with different client IDs and retry logic
"""

from ib_insync import *
import time
import random

def test_connect():
    """Try different client IDs to find one that works"""

    client_ids = [random.randint(3000, 9999) for _ in range(5)]

    for client_id in client_ids:
        print(f"\nTrying client ID {client_id}...")

        ib = IB()
        try:
            ib.connect('127.0.0.1', 7497, clientId=client_id, timeout=5)
            print(f"✓ Connected with client ID {client_id}")

            # Quick test
            print("Testing contract qualification...")
            contract = Stock('SPY', 'SMART', 'USD')
            qualified = ib.qualifyContracts(contract)

            if qualified:
                print(f"✓ Contract qualified: {qualified[0].conId}")

                # Try a simple request
                print("Testing account info...")
                accounts = ib.managedAccounts()
                print(f"✓ Accounts: {accounts}")

                ib.disconnect()
                return client_id
            else:
                print("✗ Contract qualification failed")
                ib.disconnect()

        except Exception as e:
            print(f"✗ Failed: {e}")
            if ib.isConnected():
                ib.disconnect()

        time.sleep(1)

    return None

if __name__ == "__main__":
    working_id = test_connect()
    if working_id:
        print(f"\n✅ Success! Use client ID: {working_id}")
    else:
        print("\n❌ All connection attempts failed")
        print("\nPlease check:")
        print("1. TWS is running and logged in")
        print("2. API connections are enabled in TWS")
        print("3. Socket port is 7497")
        print("4. 'Enable ActiveX and Socket Clients' is checked")