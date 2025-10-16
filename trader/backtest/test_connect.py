#!/usr/bin/env python3
"""Test IBKR connection"""

from ib_insync import IB
import time

print("1. Creating IB instance...")
ib = IB()
print("   ✓ IB instance created")

print("2. Attempting to connect to TWS on port 7497 with clientId=3000...")
print("   (This may hang if another process is using clientId 3000)")

try:
    ib.connect('127.0.0.1', 7497, clientId=3000, timeout=10)
    print("   ✓ Connected successfully!")

    print("3. Testing connection...")
    print(f"   Is connected: {ib.isConnected()}")

    print("4. Disconnecting...")
    ib.disconnect()
    print("   ✓ Disconnected")

except Exception as e:
    print(f"   ✗ Connection failed: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ Test complete")
