#!/usr/bin/env python3
"""
Regenerate scanner results for a historical date
"""
import sys
from datetime import datetime
from scanner import PS60Scanner

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 rescan_historical.py YYYY-MM-DD")
        sys.exit(1)

    date_str = sys.argv[1]
    trading_date = datetime.strptime(date_str, '%Y-%m-%d').date()

    print(f"Regenerating scanner for {trading_date}...")

    from ib_insync import IB

    scanner = PS60Scanner()
    scanner.ib = IB()
    scanner.ib.connect('127.0.0.1', 7497, clientId=5000)  # Use unique client ID

    # Run scan with historical date
    scanner.run_scan(category='all', historical_date=trading_date)

    scanner.disconnect()

    print(f"\n✓ Scanner results saved to output/scanner_results_{trading_date.strftime('%Y%m%d')}.json")
