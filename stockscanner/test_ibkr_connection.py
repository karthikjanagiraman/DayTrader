#!/usr/bin/env python3
"""
Test IBKR connection and identify timeout issues
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ib_insync import IB, Stock, util
import asyncio
import time
from datetime import datetime, timedelta
import threading

def test_basic_connection():
    """Test basic IB connection"""
    print("Test 1: Basic connection...")
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=200)
        print(f"✓ Connected: {ib.isConnected()}")

        # Test contract creation
        contract = Stock('AAPL', 'SMART', 'USD')
        ib.qualifyContracts(contract)
        print(f"✓ Contract qualified: {contract.conId}")

        # Test data fetch with timeout
        print("Fetching data with 5s timeout...")
        start = time.time()
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='5 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False
        )
        elapsed = time.time() - start
        print(f"✓ Got {len(bars)} bars in {elapsed:.2f}s")

        ib.disconnect()
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False

def test_event_loop_in_thread():
    """Test running IB in a thread with its own event loop"""
    print("\nTest 2: Thread with event loop...")

    def worker():
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        ib = IB()
        try:
            ib.connect('127.0.0.1', 7497, clientId=201)
            print(f"  ✓ Thread connected: {ib.isConnected()}")

            contract = Stock('TSLA', 'SMART', 'USD')
            ib.qualifyContracts(contract)

            bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='5 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False
            )
            print(f"  ✓ Thread got {len(bars)} bars")

            ib.disconnect()
            loop.close()
            return True
        except Exception as e:
            print(f"  ✗ Thread error: {e}")
            if ib.isConnected():
                ib.disconnect()
            loop.close()
            return False

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=10)

    if thread.is_alive():
        print("  ✗ Thread timed out!")
        return False
    return True

def test_multiple_sequential():
    """Test multiple sequential requests"""
    print("\nTest 3: Multiple sequential requests...")
    ib = IB()

    try:
        ib.connect('127.0.0.1', 7497, clientId=202)
        symbols = ['AAPL', 'TSLA', 'NVDA']

        for symbol in symbols:
            contract = Stock(symbol, 'SMART', 'USD')
            ib.qualifyContracts(contract)

            start = time.time()
            bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr='5 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False
            )
            elapsed = time.time() - start
            print(f"  ✓ {symbol}: {len(bars)} bars in {elapsed:.2f}s")

            # Small delay between requests
            time.sleep(0.1)

        ib.disconnect()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False

def test_with_sleep():
    """Test using ib.sleep() instead of blocking"""
    print("\nTest 4: Using ib.sleep() for async handling...")
    ib = IB()

    try:
        ib.connect('127.0.0.1', 7497, clientId=203)

        contract = Stock('META', 'SMART', 'USD')
        ib.qualifyContracts(contract)

        # Start request
        req = ib.reqHistoricalDataAsync(
            contract,
            endDateTime='',
            durationStr='5 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False
        )

        # Wait for completion with timeout
        start = time.time()
        while not req.done() and time.time() - start < 5:
            ib.sleep(0.1)

        if req.done():
            bars = req.result()
            print(f"  ✓ Got {len(bars)} bars using async")
        else:
            print("  ✗ Request timed out")

        ib.disconnect()
        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False

if __name__ == "__main__":
    print("="*60)
    print("IBKR CONNECTION TESTS")
    print("="*60)

    results = []

    # Run tests
    results.append(("Basic connection", test_basic_connection()))
    time.sleep(1)

    results.append(("Thread with event loop", test_event_loop_in_thread()))
    time.sleep(1)

    results.append(("Multiple sequential", test_multiple_sequential()))
    time.sleep(1)

    results.append(("Async with ib.sleep", test_with_sleep()))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:30} {status}")

    all_pass = all(r[1] for r in results)
    print(f"\nOverall: {'✓ ALL TESTS PASSED' if all_pass else '✗ SOME TESTS FAILED'}")