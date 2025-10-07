#!/usr/bin/env python3
"""
IBKR Verification Script for Scanner Validation

This script double-checks the scanner validation results by fetching actual
historical data from IBKR for the trading day and verifying:
1. Did the breakout actually occur?
2. Did it hit the target price?
3. What was the intraday high/low?
4. Was it a true breakout or false signal?

Usage:
    python verify_with_ibkr.py <date> <validation_csv>

Example:
    python verify_with_ibkr.py 2025-10-06 validation_20251006.csv
"""

import sys
import csv
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util
import time

class IBKRVerifier:
    def __init__(self):
        self.ib = IB()
        self.verified = []
        self.errors = []

    def connect(self):
        """Connect to IBKR"""
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=3001)
            print("✓ Connected to IBKR")
            return True
        except Exception as e:
            print(f"✗ IBKR connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    def get_historical_bars(self, symbol, date):
        """
        Fetch 1-minute historical bars for the trading day

        Args:
            symbol: Stock symbol
            date: Trading date (datetime object)

        Returns:
            List of BarData objects or None if error
        """
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Request 1-minute bars for the entire trading day
            end_datetime = date.replace(hour=16, minute=0, second=0)
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime.strftime('%Y%m%d %H:%M:%S'),
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )

            # Respect IBKR pacing
            time.sleep(0.5)

            return bars

        except Exception as e:
            print(f"  ✗ Error fetching {symbol}: {e}")
            return None

    def verify_breakout(self, symbol, side, pivot, target, date):
        """
        Verify if breakout occurred and hit target

        Args:
            symbol: Stock symbol
            side: 'LONG' or 'SHORT'
            pivot: Pivot price (resistance for long, support for short)
            target: Target price
            date: Trading date

        Returns:
            dict with verification results
        """
        bars = self.get_historical_bars(symbol, date)

        if not bars or len(bars) == 0:
            return {
                'symbol': symbol,
                'side': side,
                'verified': False,
                'error': 'No data available'
            }

        # Find when/if pivot was broken
        breakout_bar = None
        breakout_time = None

        for i, bar in enumerate(bars):
            if side == 'LONG':
                if bar.close > pivot:
                    breakout_bar = bar
                    breakout_time = bar.date
                    break
            else:  # SHORT
                if bar.close < pivot:
                    breakout_bar = bar
                    breakout_time = bar.date
                    break

        if not breakout_bar:
            return {
                'symbol': symbol,
                'side': side,
                'verified': True,
                'breakout_occurred': False,
                'pivot': pivot,
                'day_high': max(b.high for b in bars),
                'day_low': min(b.low for b in bars),
            }

        # Check if target was hit after breakout
        target_hit = False
        target_time = None
        max_favorable = breakout_bar.close

        for bar in bars[bars.index(breakout_bar):]:
            if side == 'LONG':
                max_favorable = max(max_favorable, bar.high)
                if bar.high >= target:
                    target_hit = True
                    target_time = bar.date
                    break
            else:  # SHORT
                max_favorable = min(max_favorable, bar.low)
                if bar.low <= target:
                    target_hit = True
                    target_time = bar.date
                    break

        # Check for reversal (false breakout)
        close_price = bars[-1].close
        reversed = False

        if side == 'LONG':
            if close_price < pivot:
                reversed = True
        else:
            if close_price > pivot:
                reversed = True

        return {
            'symbol': symbol,
            'side': side,
            'verified': True,
            'breakout_occurred': True,
            'breakout_time': breakout_time,
            'target_hit': target_hit,
            'target_time': target_time if target_hit else None,
            'max_favorable': max_favorable,
            'close_price': close_price,
            'reversed': reversed,
            'pivot': pivot,
            'target': target,
            'day_high': max(b.high for b in bars),
            'day_low': min(b.low for b in bars),
        }

    def verify_validation_file(self, validation_csv, date):
        """
        Verify all entries in validation CSV using IBKR data

        Args:
            validation_csv: Path to validation CSV file
            date: Trading date (datetime object)
        """
        print(f"\n{'='*80}")
        print(f"IBKR VERIFICATION - {date.strftime('%Y-%m-%d')}")
        print(f"{'='*80}\n")

        # Read validation results
        with open(validation_csv, 'r') as f:
            reader = csv.DictReader(f)
            entries = list(reader)

        print(f"Loaded {len(entries)} entries from validation file\n")

        verified_count = 0
        match_count = 0
        mismatch_count = 0

        for i, entry in enumerate(entries, 1):
            symbol = entry['Symbol']

            # Verify LONG if it occurred
            if entry['Long Breakout?'] == 'Yes':
                print(f"[{i}/{len(entries)}] Verifying {symbol} LONG...")

                resistance = float(entry['Resistance'])
                # Assume target is +2% (can be adjusted based on scanner data)
                target = resistance * 1.02

                result = self.verify_breakout(symbol, 'LONG', resistance, target, date)

                if result.get('verified'):
                    verified_count += 1

                    # Compare with validation results
                    validation_success = entry['Long Outcome'] == 'SUCCESS'
                    ibkr_success = result.get('target_hit', False)

                    if validation_success == ibkr_success:
                        match_count += 1
                        print(f"  ✓ MATCH - Both show {'SUCCESS' if ibkr_success else 'FAILURE'}")
                    else:
                        mismatch_count += 1
                        print(f"  ⚠ MISMATCH - Validation: {validation_success}, IBKR: {ibkr_success}")

                    if result.get('breakout_occurred'):
                        print(f"    Breakout: {result['breakout_time'].strftime('%H:%M')}")
                        print(f"    Max: ${result['max_favorable']:.2f}")
                        print(f"    Close: ${result['close_price']:.2f}")
                        if result['reversed']:
                            print(f"    ⚠ False breakout (reversed)")
                else:
                    self.errors.append(result)

            # Verify SHORT if it occurred
            if entry['Short Breakout?'] == 'Yes':
                print(f"[{i}/{len(entries)}] Verifying {symbol} SHORT...")

                support = float(entry['Support'])
                target = support * 0.98

                result = self.verify_breakout(symbol, 'SHORT', support, target, date)

                if result.get('verified'):
                    verified_count += 1

                    validation_success = entry['Short Outcome'] == 'SUCCESS'
                    ibkr_success = result.get('target_hit', False)

                    if validation_success == ibkr_success:
                        match_count += 1
                        print(f"  ✓ MATCH - Both show {'SUCCESS' if ibkr_success else 'FAILURE'}")
                    else:
                        mismatch_count += 1
                        print(f"  ⚠ MISMATCH - Validation: {validation_success}, IBKR: {ibkr_success}")

                    if result.get('breakout_occurred'):
                        print(f"    Breakout: {result['breakout_time'].strftime('%H:%M')}")
                        print(f"    Max: ${result['max_favorable']:.2f}")
                        print(f"    Close: ${result['close_price']:.2f}")
                        if result['reversed']:
                            print(f"    ⚠ False breakout (reversed)")
                else:
                    self.errors.append(result)

        # Summary
        print(f"\n{'='*80}")
        print("VERIFICATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total verifications: {verified_count}")
        print(f"Matches: {match_count} ({match_count/verified_count*100:.1f}%)")
        print(f"Mismatches: {mismatch_count} ({mismatch_count/verified_count*100:.1f}%)")
        print(f"Errors: {len(self.errors)}")

        if match_count / verified_count >= 0.95:
            print("\n✓ VALIDATION ACCURACY: EXCELLENT (≥95% match)")
        elif match_count / verified_count >= 0.90:
            print("\n✓ VALIDATION ACCURACY: GOOD (≥90% match)")
        else:
            print("\n⚠ VALIDATION ACCURACY: NEEDS REVIEW (<90% match)")

def main():
    if len(sys.argv) < 3:
        print("Usage: python verify_with_ibkr.py <date> <validation_csv>")
        print("Example: python verify_with_ibkr.py 2025-10-06 validation_20251006.csv")
        sys.exit(1)

    date_str = sys.argv[1]
    validation_csv = sys.argv[2]

    # Parse date
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"✗ Invalid date format: {date_str}")
        print("Use YYYY-MM-DD format")
        sys.exit(1)

    # Verify file exists
    try:
        with open(validation_csv, 'r'):
            pass
    except FileNotFoundError:
        print(f"✗ File not found: {validation_csv}")
        sys.exit(1)

    # Run verification
    verifier = IBKRVerifier()

    if not verifier.connect():
        sys.exit(1)

    try:
        verifier.verify_validation_file(validation_csv, date)
    finally:
        verifier.disconnect()

if __name__ == '__main__':
    main()
