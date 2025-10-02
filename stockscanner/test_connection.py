#!/usr/bin/env python3
"""
Test basic IBKR connection and contract qualification
"""

from ib_insync import *
import time

def test_connection():
    """Test connection basics"""
    print("Testing IBKR connection...")

    ib = IB()

    try:
        # Connect
        ib.connect('127.0.0.1', 7497, clientId=2222)
        print(f"✓ Connected: {ib.isConnected()}")
        print(f"  Client ID: {ib.client.clientId}")
        print(f"  Server version: {ib.client.serverVersion()}")

        # Test contract qualification
        print("\nTesting contract qualification...")
        contract = Stock('SPY', 'SMART', 'USD')
        qualified = ib.qualifyContracts(contract)

        if qualified:
            c = qualified[0]
            print(f"✓ Contract qualified: {c.symbol}")
            print(f"  Exchange: {c.exchange}")
            print(f"  Currency: {c.currency}")
            print(f"  ConId: {c.conId}")
        else:
            print("✗ Contract qualification failed")

        # Test account info
        print("\nGetting account info...")
        accounts = ib.managedAccounts()
        print(f"  Accounts: {accounts}")

        # Test positions (quick check)
        print("\nChecking positions...")
        positions = ib.positions()
        print(f"  Positions count: {len(positions)}")

        print("\n✓ All basic tests passed")
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False

    finally:
        if ib.isConnected():
            ib.disconnect()
            print("\n✓ Disconnected")

if __name__ == "__main__":
    test_connection()