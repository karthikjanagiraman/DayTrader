#!/usr/bin/env python3
"""
Scanner Validation Script
Validates daily scanner output by checking actual market performance

Per Requirements Document: Daily Stock Breakout Validation Script
- Loads scanner output for a given date
- Fetches intraday data for next trading day
- Validates which stocks broke out (long/short)
- Determines if breakouts hit targets or were false
- Does NOT skip any stocks (handles all symbols)
"""

import json
import csv
from pathlib import Path
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util
import time
import pandas as pd

class ScannerValidator:
    """Validates scanner predictions against actual market data"""

    def __init__(self, scanner_date, scanner_file, ibkr_host='127.0.0.1', ibkr_port=7497):
        """
        Initialize validator

        Args:
            scanner_date: Date scanner was run FOR (e.g., '2025-10-01' means trading day Oct 1)
            scanner_file: Path to scanner output CSV/JSON
            ibkr_host: IBKR TWS/Gateway host
            ibkr_port: IBKR port (7497 for paper, 7496 for live)
        """
        self.scanner_date = datetime.strptime(scanner_date, '%Y-%m-%d')
        self.scanner_file = Path(scanner_file)
        self.ibkr_host = ibkr_host
        self.ibkr_port = ibkr_port

        # Trading date is SAME as scanner date (scanner predicts for that day)
        self.trading_date = self.scanner_date

        # Results storage
        self.results = []
        self.errors = []

        # IBKR connection
        self.ib = None

    def load_scanner_data(self):
        """
        Load scanner output file (CSV or JSON)

        Returns:
            list of dicts with stock data
        """
        if self.scanner_file.suffix == '.json':
            with open(self.scanner_file) as f:
                data = json.load(f)
        elif self.scanner_file.suffix == '.csv':
            data = []
            with open(self.scanner_file) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    for key in ['close', 'resistance', 'support', 'target1', 'target2', 'target3',
                                'downside1', 'downside2']:
                        if key in row and row[key]:
                            try:
                                row[key] = float(row[key])
                            except:
                                pass
                    data.append(row)
        else:
            raise ValueError(f"Unsupported file format: {self.scanner_file.suffix}")

        print(f"✓ Loaded {len(data)} stocks from scanner")
        return data

    def connect_ibkr(self):
        """Connect to IBKR"""
        print(f"\nConnecting to IBKR ({self.ibkr_host}:{self.ibkr_port})...")
        self.ib = IB()
        self.ib.connect(self.ibkr_host, self.ibkr_port, clientId=6000)
        print("✓ Connected to IBKR")

    def disconnect_ibkr(self):
        """Disconnect from IBKR"""
        if self.ib:
            self.ib.disconnect()
            print("\n✓ Disconnected from IBKR")

    def validate_stock(self, stock):
        """
        Validate a single stock

        Args:
            stock: Dict with scanner data (symbol, resistance, support, targets, etc.)

        Returns:
            Dict with validation results
        """
        symbol = stock['symbol']
        resistance = stock.get('resistance', None)
        support = stock.get('support', None)
        target1 = stock.get('target1', None)
        downside1 = stock.get('downside1', None)

        print(f"  {symbol}: R=${resistance:.2f}, S=${support:.2f}", end=' ')

        # Fetch intraday data
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=self.trading_date.strftime('%Y%m%d 16:00:00'),
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars or len(bars) < 10:
                print("⚠️  No data")
                return {
                    'symbol': symbol,
                    'error': 'Insufficient data',
                    'long_breakout': {'occurred': False, 'outcome': 'NO_DATA'},
                    'short_breakout': {'occurred': False, 'outcome': 'NO_DATA'}
                }

            # Get day's high/low
            day_high = max(b.high for b in bars)
            day_low = min(b.low for b in bars)
            day_close = bars[-1].close

            # Validate LONG breakout
            long_result = self._validate_long(
                bars, resistance, target1, day_high, day_low, day_close
            )

            # Validate SHORT breakout
            short_result = self._validate_short(
                bars, support, downside1, day_high, day_low, day_close
            )

            # Print summary
            long_status = self._format_outcome(long_result)
            short_status = self._format_outcome(short_result)
            print(f"→ L:{long_status} S:{short_status}")

            return {
                'symbol': symbol,
                'date': self.trading_date.strftime('%Y-%m-%d'),
                'resistance': resistance,
                'support': support,
                'target1': target1,
                'downside1': downside1,
                'day_high': day_high,
                'day_low': day_low,
                'day_close': day_close,
                'long_breakout': long_result,
                'short_breakout': short_result,
                'error': None
            }

        except Exception as e:
            print(f"⚠️  Error: {str(e)[:50]}")
            self.errors.append({'symbol': symbol, 'error': str(e)})

            return {
                'symbol': symbol,
                'error': str(e),
                'long_breakout': {'occurred': False, 'outcome': 'ERROR'},
                'short_breakout': {'occurred': False, 'outcome': 'ERROR'}
            }

    def _validate_long(self, bars, resistance, target1, day_high, day_low, day_close):
        """
        Validate long (upward) breakout

        Returns:
            dict with outcome
        """
        if resistance is None or target1 is None:
            return {'occurred': False, 'reason': 'No resistance/target defined'}

        # Check if price broke above resistance
        if day_high < resistance:
            return {
                'occurred': False,
                'outcome': 'NO_BREAKOUT',
                'reason': f'Stayed below ${resistance:.2f}'
            }

        # Breakout occurred - find when
        breakout_time = None
        breakout_bar = None

        for bar in bars:
            if bar.high >= resistance:
                breakout_time = bar.date
                breakout_bar = bar
                break

        # Check if target was hit
        if day_high >= target1:
            return {
                'occurred': True,
                'outcome': 'SUCCESS',
                'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
                'breakout_price': resistance,
                'max_price': day_high,
                'target': target1,
                'target_hit': True,
                'reason': f'Hit ${target1:.2f} (max ${day_high:.2f})'
            }

        # Check if came close to target (within 0.5%)
        target_distance = abs(target1 - resistance)
        achieved_distance = day_high - resistance
        pct_to_target = (achieved_distance / target_distance * 100) if target_distance > 0 else 0

        if pct_to_target >= 95:
            return {
                'occurred': True,
                'outcome': 'NEAR_SUCCESS',
                'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
                'breakout_price': resistance,
                'max_price': day_high,
                'target': target1,
                'target_hit': False,
                'pct_to_target': pct_to_target,
                'reason': f'Reached {pct_to_target:.1f}% to target'
            }

        # Didn't reach target - check if fell back below resistance (false breakout)
        if day_close < resistance:
            return {
                'occurred': True,
                'outcome': 'FALSE_BREAKOUT',
                'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
                'breakout_price': resistance,
                'max_price': day_high,
                'target': target1,
                'target_hit': False,
                'close_price': day_close,
                'reason': f'Reversed below ${resistance:.2f} (closed ${day_close:.2f})'
            }

        # Broke out, held above resistance, but didn't reach target
        return {
            'occurred': True,
            'outcome': 'UNCONFIRMED',
            'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
            'breakout_price': resistance,
            'max_price': day_high,
            'target': target1,
            'target_hit': False,
            'close_price': day_close,
            'pct_to_target': pct_to_target,
            'reason': f'Held above but only {pct_to_target:.1f}% to target'
        }

    def _validate_short(self, bars, support, downside1, day_high, day_low, day_close):
        """
        Validate short (downward) breakout

        Returns:
            dict with outcome
        """
        if support is None or downside1 is None:
            return {'occurred': False, 'reason': 'No support/target defined'}

        # Check if price broke below support
        if day_low > support:
            return {
                'occurred': False,
                'outcome': 'NO_BREAKOUT',
                'reason': f'Stayed above ${support:.2f}'
            }

        # Breakdown occurred - find when
        breakout_time = None
        breakout_bar = None

        for bar in bars:
            if bar.low <= support:
                breakout_time = bar.date
                breakout_bar = bar
                break

        # Check if downside target was hit
        if day_low <= downside1:
            return {
                'occurred': True,
                'outcome': 'SUCCESS',
                'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
                'breakout_price': support,
                'min_price': day_low,
                'target': downside1,
                'target_hit': True,
                'reason': f'Hit ${downside1:.2f} (min ${day_low:.2f})'
            }

        # Check if came close to target (within 0.5%)
        target_distance = abs(support - downside1)
        achieved_distance = support - day_low
        pct_to_target = (achieved_distance / target_distance * 100) if target_distance > 0 else 0

        if pct_to_target >= 95:
            return {
                'occurred': True,
                'outcome': 'NEAR_SUCCESS',
                'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
                'breakout_price': support,
                'min_price': day_low,
                'target': downside1,
                'target_hit': False,
                'pct_to_target': pct_to_target,
                'reason': f'Reached {pct_to_target:.1f}% to target'
            }

        # Didn't reach target - check if bounced back above support (false breakdown)
        if day_close > support:
            return {
                'occurred': True,
                'outcome': 'FALSE_BREAKOUT',
                'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
                'breakout_price': support,
                'min_price': day_low,
                'target': downside1,
                'target_hit': False,
                'close_price': day_close,
                'reason': f'Reversed above ${support:.2f} (closed ${day_close:.2f})'
            }

        # Broke down, stayed below support, but didn't reach target
        return {
            'occurred': True,
            'outcome': 'UNCONFIRMED',
            'breakout_time': breakout_time.strftime('%H:%M') if breakout_time else None,
            'breakout_price': support,
            'min_price': day_low,
            'target': downside1,
            'target_hit': False,
            'close_price': day_close,
            'pct_to_target': pct_to_target,
            'reason': f'Held below but only {pct_to_target:.1f}% to target'
        }

    def _format_outcome(self, result):
        """Format outcome for console display"""
        if not result or not result.get('occurred'):
            return "⊗"  # No breakout

        outcome = result.get('outcome')
        if outcome == 'SUCCESS':
            return "✓"
        elif outcome == 'NEAR_SUCCESS':
            return "≈"
        elif outcome == 'FALSE_BREAKOUT':
            return "✗"
        elif outcome == 'UNCONFIRMED':
            return "?"
        else:
            return "-"

    def validate_all(self):
        """
        Validate all stocks from scanner

        Returns:
            list of validation results
        """
        print(f"\n{'='*80}")
        print(f"SCANNER VALIDATION - {self.scanner_date.strftime('%Y-%m-%d')}")
        print(f"Trading Day: {self.trading_date.strftime('%Y-%m-%d')}")
        print(f"{'='*80}")

        # Load scanner data
        scanner_data = self.load_scanner_data()

        # Connect to IBKR
        self.connect_ibkr()

        # Validate each stock
        print(f"\nValidating {len(scanner_data)} stocks:")
        print(f"{'='*80}")

        for i, stock in enumerate(scanner_data, 1):
            print(f"[{i}/{len(scanner_data)}]", end=' ')

            result = self.validate_stock(stock)
            self.results.append(result)

            # Rate limit (0.5s between requests)
            time.sleep(0.5)

        # Disconnect
        self.disconnect_ibkr()

        return self.results

    def generate_report(self, output_file=None):
        """
        Generate validation report

        Args:
            output_file: Optional path to save CSV report
        """
        if not self.results:
            print("\n⚠️  No results to report")
            return

        print(f"\n{'='*80}")
        print("VALIDATION REPORT")
        print(f"{'='*80}")

        # Calculate statistics
        total = len(self.results)
        errors = len([r for r in self.results if r.get('error')])
        validated = total - errors

        long_breakouts = sum(1 for r in self.results if r.get('long_breakout', {}).get('occurred'))
        short_breakouts = sum(1 for r in self.results if r.get('short_breakout', {}).get('occurred'))

        long_success = sum(1 for r in self.results
                          if r.get('long_breakout', {}).get('outcome') == 'SUCCESS')
        short_success = sum(1 for r in self.results
                           if r.get('short_breakout', {}).get('outcome') == 'SUCCESS')

        long_false = sum(1 for r in self.results
                        if r.get('long_breakout', {}).get('outcome') == 'FALSE_BREAKOUT')
        short_false = sum(1 for r in self.results
                         if r.get('short_breakout', {}).get('outcome') == 'FALSE_BREAKOUT')

        print(f"\nTotal stocks: {total}")
        print(f"  Validated: {validated}")
        print(f"  Errors: {errors}")

        print(f"\nLONG Breakouts:")
        print(f"  Occurred: {long_breakouts}")
        print(f"  Success (hit target): {long_success}")
        print(f"  False breakouts: {long_false}")
        if long_breakouts > 0:
            print(f"  Success rate: {long_success/long_breakouts*100:.1f}%")

        print(f"\nSHORT Breakouts:")
        print(f"  Occurred: {short_breakouts}")
        print(f"  Success (hit target): {short_success}")
        print(f"  False breakouts: {short_false}")
        if short_breakouts > 0:
            print(f"  Success rate: {short_success/short_breakouts*100:.1f}%")

        # Show successful breakouts
        print(f"\n{'-'*80}")
        print("SUCCESSFUL BREAKOUTS:")
        print(f"{'-'*80}")

        for r in self.results:
            symbol = r['symbol']

            long_result = r.get('long_breakout', {})
            if long_result.get('outcome') == 'SUCCESS':
                print(f"  ✓ {symbol} LONG: {long_result.get('reason')}")

            short_result = r.get('short_breakout', {})
            if short_result.get('outcome') == 'SUCCESS':
                print(f"  ✓ {symbol} SHORT: {short_result.get('reason')}")

        # Show false breakouts
        print(f"\n{'-'*80}")
        print("FALSE BREAKOUTS:")
        print(f"{'-'*80}")

        for r in self.results:
            symbol = r['symbol']

            long_result = r.get('long_breakout', {})
            if long_result.get('outcome') == 'FALSE_BREAKOUT':
                print(f"  ✗ {symbol} LONG: {long_result.get('reason')}")

            short_result = r.get('short_breakout', {})
            if short_result.get('outcome') == 'FALSE_BREAKOUT':
                print(f"  ✗ {symbol} SHORT: {short_result.get('reason')}")

        # Save CSV if requested
        if output_file:
            self._save_csv(output_file)
            print(f"\n✓ Report saved: {output_file}")

    def _save_csv(self, output_file):
        """Save results to CSV"""
        rows = []

        for r in self.results:
            long_result = r.get('long_breakout', {}) or {}
            short_result = r.get('short_breakout', {}) or {}

            row = {
                'Symbol': r['symbol'],
                'Date': r.get('date', ''),
                'Resistance': r.get('resistance', ''),
                'Support': r.get('support', ''),
                'Day High': r.get('day_high', ''),
                'Day Low': r.get('day_low', ''),
                'Day Close': r.get('day_close', ''),

                'Long Breakout?': 'Yes' if long_result.get('occurred') else 'No',
                'Long Outcome': long_result.get('outcome', 'N/A'),
                'Long Reason': long_result.get('reason', ''),

                'Short Breakout?': 'Yes' if short_result.get('occurred') else 'No',
                'Short Outcome': short_result.get('outcome', 'N/A'),
                'Short Reason': short_result.get('reason', ''),

                'Error': r.get('error', '')
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False)

def main():
    """Main entry point"""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python validate_scanner.py <scanner_date> <scanner_file>")
        print("Example: python validate_scanner.py 2025-10-01 scanner_results_20251001.json")
        sys.exit(1)

    scanner_date = sys.argv[1]
    scanner_file = sys.argv[2]

    # Optional output file
    output_file = sys.argv[3] if len(sys.argv) > 3 else None

    # Create validator
    validator = ScannerValidator(scanner_date, scanner_file)

    # Run validation
    validator.validate_all()

    # Generate report
    if output_file:
        validator.generate_report(output_file)
    else:
        # Auto-generate output filename
        output_file = f"validation_{scanner_date.replace('-', '')}.csv"
        validator.generate_report(output_file)

if __name__ == "__main__":
    main()
