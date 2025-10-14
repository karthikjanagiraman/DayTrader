#!/usr/bin/env python3
"""
Test IBKR connection for Nifty Fifty stocks (Indian NSE market)
"""

from ib_insync import *
import time

def test_indian_stocks():
    """Test if IBKR supports Indian market stocks"""

    print("="*80)
    print("TESTING IBKR SUPPORT FOR NIFTY FIFTY (NSE INDIA)")
    print("="*80)

    # Sample Nifty 50 symbols to test
    test_symbols = [
        'RELIANCE',   # Reliance Industries
        'TCS',        # Tata Consultancy Services
        'HDFCBANK',   # HDFC Bank
        'INFY',       # Infosys
        'ICICIBANK',  # ICICI Bank
        'HINDUNILVR', # Hindustan Unilever
        'ITC',        # ITC Limited
        'BHARTIARTL', # Bharti Airtel
        'SBIN',       # State Bank of India
        'LT'          # Larsen & Toubro
    ]

    # Connect to IBKR
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1010)
        print(f"✓ Connected to IBKR TWS\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print("\nMake sure TWS/Gateway is running on port 7497")
        return False

    results = {
        'supported': [],
        'not_supported': [],
        'errors': []
    }

    print("Testing stock contracts...\n")
    print("-"*80)

    for symbol in test_symbols:
        print(f"Testing {symbol}...", end=' ')

        try:
            # Try NSE exchange (National Stock Exchange of India)
            contract_nse = Stock(symbol, 'NSE', 'INR')
            qualified_nse = ib.qualifyContracts(contract_nse)

            if qualified_nse:
                print(f"✓ SUPPORTED on NSE")
                results['supported'].append(f"{symbol} (NSE)")

                # Try to get a quote
                time.sleep(0.5)
                ticker = ib.reqMktData(contract_nse)
                time.sleep(1)

                if ticker.last and ticker.last > 0:
                    print(f"   └─ Live quote: ₹{ticker.last:.2f}")
                else:
                    print(f"   └─ No live quote (may need market data subscription)")

                ib.cancelMktData(contract_nse)
                continue

        except Exception as e:
            # NSE failed, try SMART routing
            pass

        try:
            # Try SMART routing
            contract_smart = Stock(symbol, 'SMART', 'INR')
            qualified_smart = ib.qualifyContracts(contract_smart)

            if qualified_smart:
                print(f"✓ SUPPORTED on SMART routing")
                results['supported'].append(f"{symbol} (SMART)")
                continue

        except Exception as e:
            pass

        # Not found
        print(f"✗ NOT SUPPORTED")
        results['not_supported'].append(symbol)

        time.sleep(0.3)  # Rate limiting

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✓ Supported: {len(results['supported'])} stocks")
    print(f"✗ Not Supported: {len(results['not_supported'])} stocks")

    if results['supported']:
        print("\n✓ SUPPORTED STOCKS:")
        for stock in results['supported']:
            print(f"  - {stock}")

    if results['not_supported']:
        print("\n✗ NOT SUPPORTED STOCKS:")
        for stock in results['not_supported']:
            print(f"  - {stock}")

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)

    if len(results['supported']) > 0:
        print("✓ IBKR SUPPORTS INDIAN STOCKS (NSE)")
        print("\nTo scan Nifty Fifty, you need:")
        print("1. IBKR account with Indian market data subscription")
        print("2. NSE market data permissions enabled")
        print("3. Currency should be INR (Indian Rupee)")
        return True
    else:
        print("✗ IBKR DOES NOT SUPPORT INDIAN STOCKS")
        print("\nPossible reasons:")
        print("1. Your IBKR account doesn't have Indian market access")
        print("2. NSE market data subscription is not active")
        print("3. Indian market permissions not enabled")
        print("\nTo enable:")
        print("1. Log in to IBKR Account Management")
        print("2. Go to Settings > Market Data Subscriptions")
        print("3. Add 'Indian Stock Exchange (NSE)' subscription")
        return False

    ib.disconnect()

if __name__ == "__main__":
    test_indian_stocks()
