#!/usr/bin/env python3
"""
Pivot Behavior Analysis Script

Analyzes scanner-identified pivots using IBKR historical data to understand:
1. Did price break through pivot?
2. Did it reach targets?
3. How many times did it retest the pivot?
4. What stop-loss buffer would have captured the full move?

Outputs detailed CSV for further analysis and optimization.
"""

import sys
import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Add trader directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ib_insync import IB, Stock, util
import pandas as pd


class PivotBehaviorAnalyzer:
    """Analyzes pivot behavior using IBKR historical data"""

    def __init__(self, date: str, account_size: float = 50000):
        self.date = date
        self.account_size = account_size
        self.ib = None
        self.cache_dir = Path(__file__).parent.parent / "backtest" / "data"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Buffer scenarios to test (percentages)
        self.stop_buffers = [0.0, 0.1, 0.25, 0.5, 1.0]

        # Results storage
        self.results = []

    def connect_ib(self):
        """Connect to IBKR"""
        self.ib = IB()
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=9000)
            print("✅ Connected to IBKR")
        except Exception as e:
            print(f"❌ IBKR connection failed: {e}")
            print("   Continuing with cached data only...")

    def disconnect_ib(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("✅ Disconnected from IBKR")

    def get_cached_bars(self, symbol: str) -> Optional[List]:
        """Load bars from cache if available"""
        # Try new format first: SYMBOL_YYYY-MM-DD_1min_bars.json
        cache_file = self.cache_dir / f"{symbol}_{self.date}_1min_bars.json"

        # Try existing backtest cache format: SYMBOL_YYYYMMDD_1min.json
        if not cache_file.exists():
            date_no_dashes = self.date.replace('-', '')
            cache_file = self.cache_dir / f"{symbol}_{date_no_dashes}_1min.json"

        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    bars_data = json.load(f)
                    print(f"  📦 Loaded {symbol} from cache ({len(bars_data)} bars)")
                    return bars_data
            except Exception as e:
                print(f"  ⚠️  Cache read error for {symbol}: {e}")

        return None

    def cache_bars(self, symbol: str, bars: List):
        """Save bars to cache"""
        cache_file = self.cache_dir / f"{symbol}_{self.date}_1min_bars.json"

        try:
            # Convert BarDataList to dict format
            bars_data = []
            for bar in bars:
                bars_data.append({
                    'date': bar.date.isoformat() if hasattr(bar.date, 'isoformat') else str(bar.date),
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume
                })

            with open(cache_file, 'w') as f:
                json.dump(bars_data, f, indent=2)

            print(f"  💾 Cached {symbol} ({len(bars_data)} bars)")
        except Exception as e:
            print(f"  ⚠️  Cache write error for {symbol}: {e}")

    def fetch_bars_from_ibkr(self, symbol: str) -> Optional[List]:
        """Fetch 1-minute bars from IBKR"""
        if not self.ib or not self.ib.isConnected():
            return None

        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Fetch 1-minute bars for entire trading day
            # IBKR requires format: YYYYMMDD HH:MM:SS (no dashes in date)
            date_formatted = self.date.replace('-', '')
            end_datetime = f"{date_formatted} 16:00:00"
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if bars:
                print(f"  📡 Fetched {symbol} from IBKR ({len(bars)} bars)")
                self.cache_bars(symbol, bars)

                # Convert to dict format
                bars_data = []
                for bar in bars:
                    bars_data.append({
                        'date': bar.date.isoformat() if hasattr(bar.date, 'isoformat') else str(bar.date),
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': bar.volume
                    })
                return bars_data

            return None

        except Exception as e:
            print(f"  ❌ IBKR fetch error for {symbol}: {e}")
            return None

    def get_bars(self, symbol: str) -> Optional[List]:
        """Get bars from cache or IBKR"""
        # Try cache first
        bars = self.get_cached_bars(symbol)
        if bars:
            return bars

        # Fetch from IBKR if not cached
        return self.fetch_bars_from_ibkr(symbol)

    def analyze_long_pivot(self, symbol: str, stock_data: Dict, bars: List) -> Dict:
        """Analyze LONG setup (resistance break)"""

        pivot = stock_data['resistance']
        target1 = stock_data.get('target1')
        target2 = stock_data.get('target2')
        target3 = stock_data.get('target3')

        result = {
            'symbol': symbol,
            'direction': 'LONG',
            'pivot_price': pivot,
            'target1': target1,
            'target2': target2,
            'target3': target3,
            'breakout_occurred': False,
            'breakout_time': None,
            'breakout_price': None,
            'target1_hit': False,
            'target1_hit_time': None,
            'target1_hit_price': None,
            'target2_hit': False,
            'target2_hit_time': None,
            'target2_hit_price': None,
            'target3_hit': False,
            'target3_hit_time': None,
            'target3_hit_price': None,
            'retest_count': 0,
            'retest_times': [],
            'retest_prices': [],
            'lowest_price_during_move': None,
            'false_breakout': False,
            'bars_above_pivot_before_reversal': 0,
            'max_excursion_pct': 0.0,
            'breakout_quality': 'N/A'
        }

        # Find initial breakout
        breakout_idx = None
        for idx, bar in enumerate(bars):
            if bar['close'] > pivot:
                result['breakout_occurred'] = True
                result['breakout_time'] = bar['date']
                result['breakout_price'] = bar['close']
                breakout_idx = idx
                break

        if not result['breakout_occurred']:
            # No breakout occurred
            return result

        # Track position after breakout
        above_pivot = True
        bars_above = 0
        lowest_during_move = result['breakout_price']
        max_price = result['breakout_price']
        target1_reached = False
        target2_reached = False
        target3_reached = False
        retests = []

        # Analyze bars after initial breakout
        for idx in range(breakout_idx + 1, len(bars)):
            bar = bars[idx]
            close = bar['close']
            low = bar['low']
            high = bar['high']

            # Track max price
            max_price = max(max_price, high)

            # Check target hits
            if target1 and not target1_reached and high >= target1:
                result['target1_hit'] = True
                result['target1_hit_time'] = bar['date']
                result['target1_hit_price'] = high
                target1_reached = True

            if target2 and not target2_reached and high >= target2:
                result['target2_hit'] = True
                result['target2_hit_time'] = bar['date']
                result['target2_hit_price'] = high
                target2_reached = True

            if target3 and not target3_reached and high >= target3:
                result['target3_hit'] = True
                result['target3_hit_time'] = bar['date']
                result['target3_hit_price'] = high
                target3_reached = True

            # Track retests (bar closes BELOW pivot)
            if close < pivot:
                if above_pivot:
                    # First time back below pivot after being above
                    retests.append({
                        'time': bar['date'],
                        'price': close
                    })
                    above_pivot = False
                bars_above = 0  # Reset counter
            else:
                # Still above pivot or back above
                if not above_pivot:
                    above_pivot = True  # Back above pivot
                bars_above += 1

                # Track lowest price while above pivot (for stop analysis)
                if above_pivot:
                    lowest_during_move = min(lowest_during_move, low)

        # Store retest data
        result['retest_count'] = len(retests)
        result['retest_times'] = [r['time'] for r in retests]
        result['retest_prices'] = [r['price'] for r in retests]
        result['lowest_price_during_move'] = lowest_during_move

        # Classify breakout quality
        if result['retest_count'] == 0:
            result['breakout_quality'] = 'CLEAN'
        elif result['retest_count'] <= 2:
            result['breakout_quality'] = 'MODERATE'
        else:
            result['breakout_quality'] = 'CHOPPY'

        # Detect false breakout
        if not target1_reached:
            result['false_breakout'] = True
            result['bars_above_pivot_before_reversal'] = bars_above

            # Calculate max excursion toward target
            if target1:
                move_to_target = target1 - pivot
                actual_move = max_price - pivot
                result['max_excursion_pct'] = (actual_move / move_to_target) * 100 if move_to_target > 0 else 0.0

        # Optimal stop analysis with different buffers
        for buffer_pct in self.stop_buffers:
            buffer_key = f"buffer_{buffer_pct:.1f}pct"

            # Calculate stop price
            stop_price = pivot * (1 - buffer_pct / 100)
            result[f'optimal_stop_{buffer_key}'] = stop_price

            # Check if this stop would have survived
            survived = lowest_during_move >= stop_price
            result[f'survived_with_{buffer_key}'] = survived

            # Calculate R/R ratio if reached target1
            if target1_reached and survived:
                risk = result['breakout_price'] - stop_price
                reward = target1 - result['breakout_price']
                rr_ratio = reward / risk if risk > 0 else 0.0
                result[f'rr_ratio_{buffer_key}'] = round(rr_ratio, 2)
            else:
                result[f'rr_ratio_{buffer_key}'] = None

        return result

    def analyze_short_pivot(self, symbol: str, stock_data: Dict, bars: List) -> Dict:
        """Analyze SHORT setup (support break)"""

        pivot = stock_data['support']
        target1 = stock_data.get('downside1')
        target2 = stock_data.get('downside2')

        result = {
            'symbol': symbol,
            'direction': 'SHORT',
            'pivot_price': pivot,
            'target1': target1,
            'target2': target2,
            'target3': None,  # Shorts typically have only 2 targets
            'breakout_occurred': False,
            'breakout_time': None,
            'breakout_price': None,
            'target1_hit': False,
            'target1_hit_time': None,
            'target1_hit_price': None,
            'target2_hit': False,
            'target2_hit_time': None,
            'target2_hit_price': None,
            'target3_hit': False,
            'target3_hit_time': None,
            'target3_hit_price': None,
            'retest_count': 0,
            'retest_times': [],
            'retest_prices': [],
            'highest_price_during_move': None,
            'false_breakout': False,
            'bars_below_pivot_before_reversal': 0,
            'max_excursion_pct': 0.0,
            'breakout_quality': 'N/A'
        }

        # Find initial breakout
        breakout_idx = None
        for idx, bar in enumerate(bars):
            if bar['close'] < pivot:
                result['breakout_occurred'] = True
                result['breakout_time'] = bar['date']
                result['breakout_price'] = bar['close']
                breakout_idx = idx
                break

        if not result['breakout_occurred']:
            return result

        # Track position after breakout
        below_pivot = True
        bars_below = 0
        highest_during_move = result['breakout_price']
        min_price = result['breakout_price']
        target1_reached = False
        target2_reached = False
        retests = []

        # Analyze bars after initial breakout
        for idx in range(breakout_idx + 1, len(bars)):
            bar = bars[idx]
            close = bar['close']
            low = bar['low']
            high = bar['high']

            # Track min price
            min_price = min(min_price, low)

            # Check target hits (for shorts, targets are below pivot)
            if target1 and not target1_reached and low <= target1:
                result['target1_hit'] = True
                result['target1_hit_time'] = bar['date']
                result['target1_hit_price'] = low
                target1_reached = True

            if target2 and not target2_reached and low <= target2:
                result['target2_hit'] = True
                result['target2_hit_time'] = bar['date']
                result['target2_hit_price'] = low
                target2_reached = True

            # Track retests (bar closes ABOVE pivot)
            if close > pivot:
                if below_pivot:
                    retests.append({
                        'time': bar['date'],
                        'price': close
                    })
                    below_pivot = False
                bars_below = 0
            else:
                if not below_pivot:
                    below_pivot = True
                bars_below += 1

                # Track highest price while below pivot (for stop analysis)
                if below_pivot:
                    highest_during_move = max(highest_during_move, high)

        # Store retest data
        result['retest_count'] = len(retests)
        result['retest_times'] = [r['time'] for r in retests]
        result['retest_prices'] = [r['price'] for r in retests]
        result['highest_price_during_move'] = highest_during_move

        # Classify breakout quality
        if result['retest_count'] == 0:
            result['breakout_quality'] = 'CLEAN'
        elif result['retest_count'] <= 2:
            result['breakout_quality'] = 'MODERATE'
        else:
            result['breakout_quality'] = 'CHOPPY'

        # Detect false breakout
        if not target1_reached:
            result['false_breakout'] = True
            result['bars_below_pivot_before_reversal'] = bars_below

            # Calculate max excursion toward target
            if target1:
                move_to_target = pivot - target1
                actual_move = pivot - min_price
                result['max_excursion_pct'] = (actual_move / move_to_target) * 100 if move_to_target > 0 else 0.0

        # Optimal stop analysis with different buffers
        for buffer_pct in self.stop_buffers:
            buffer_key = f"buffer_{buffer_pct:.1f}pct"

            # Calculate stop price (for shorts, stop is ABOVE pivot)
            stop_price = pivot * (1 + buffer_pct / 100)
            result[f'optimal_stop_{buffer_key}'] = stop_price

            # Check if this stop would have survived
            survived = highest_during_move <= stop_price
            result[f'survived_with_{buffer_key}'] = survived

            # Calculate R/R ratio if reached target1
            if target1_reached and survived:
                risk = stop_price - result['breakout_price']
                reward = result['breakout_price'] - target1
                rr_ratio = reward / risk if risk > 0 else 0.0
                result[f'rr_ratio_{buffer_key}'] = round(rr_ratio, 2)
            else:
                result[f'rr_ratio_{buffer_key}'] = None

        return result

    def analyze_stock(self, symbol: str, stock_data: Dict):
        """Analyze both LONG and SHORT pivots for a stock"""
        print(f"\n📊 Analyzing {symbol}...")

        # Get bars
        bars = self.get_bars(symbol)
        if not bars:
            print(f"  ⚠️  No data available for {symbol}")
            return

        # Analyze LONG (resistance break)
        if 'resistance' in stock_data and stock_data['resistance']:
            long_result = self.analyze_long_pivot(symbol, stock_data, bars)
            self.results.append(long_result)

            # Print summary
            if long_result['breakout_occurred']:
                emoji = "✅" if long_result['target1_hit'] else "❌"
                quality = long_result['breakout_quality']
                retests = long_result['retest_count']
                print(f"  {emoji} LONG: Broke ${long_result['pivot_price']:.2f} | "
                      f"Target1: {long_result['target1_hit']} | "
                      f"Retests: {retests} ({quality})")
            else:
                print(f"  ⚪ LONG: No breakout above ${stock_data['resistance']:.2f}")

        # Analyze SHORT (support break)
        if 'support' in stock_data and stock_data['support']:
            short_result = self.analyze_short_pivot(symbol, stock_data, bars)
            self.results.append(short_result)

            # Print summary
            if short_result['breakout_occurred']:
                emoji = "✅" if short_result['target1_hit'] else "❌"
                quality = short_result['breakout_quality']
                retests = short_result['retest_count']
                print(f"  {emoji} SHORT: Broke ${short_result['pivot_price']:.2f} | "
                      f"Target1: {short_result['target1_hit']} | "
                      f"Retests: {retests} ({quality})")
            else:
                print(f"  ⚪ SHORT: No breakout below ${stock_data['support']:.2f}")

    def save_to_csv(self, output_file: str):
        """Save results to CSV with all details"""
        print(f"\n💾 Saving results to {output_file}...")

        if not self.results:
            print("  ⚠️  No results to save")
            return

        # Define CSV columns
        fieldnames = [
            'symbol', 'direction', 'pivot_price', 'target1', 'target2', 'target3',
            'breakout_occurred', 'breakout_time', 'breakout_price',
            'target1_hit', 'target1_hit_time', 'target1_hit_price',
            'target2_hit', 'target2_hit_time', 'target2_hit_price',
            'target3_hit', 'target3_hit_time', 'target3_hit_price',
            'retest_count', 'retest_times', 'retest_prices',
            'lowest_price_during_move', 'highest_price_during_move',
            'breakout_quality', 'false_breakout',
            'bars_above_pivot_before_reversal', 'bars_below_pivot_before_reversal',
            'max_excursion_pct'
        ]

        # Add columns for each buffer scenario
        for buffer_pct in self.stop_buffers:
            buffer_key = f"buffer_{buffer_pct:.1f}pct"
            fieldnames.extend([
                f'optimal_stop_{buffer_key}',
                f'survived_with_{buffer_key}',
                f'rr_ratio_{buffer_key}'
            ])

        # Write CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in self.results:
                # Convert list fields to comma-separated strings
                row = result.copy()
                if 'retest_times' in row and row['retest_times']:
                    row['retest_times'] = '|'.join(str(t) for t in row['retest_times'])
                else:
                    row['retest_times'] = ''

                if 'retest_prices' in row and row['retest_prices']:
                    row['retest_prices'] = '|'.join(f"{p:.2f}" for p in row['retest_prices'])
                else:
                    row['retest_prices'] = ''

                writer.writerow(row)

        print(f"  ✅ Saved {len(self.results)} pivot analyses")

    def print_summary(self):
        """Print summary statistics"""
        if not self.results:
            print("\n⚠️  No results to summarize")
            return

        print("\n" + "=" * 80)
        print("PIVOT BEHAVIOR ANALYSIS SUMMARY")
        print("=" * 80)

        # Overall stats
        total = len(self.results)
        breakouts = sum(1 for r in self.results if r['breakout_occurred'])
        target1_hits = sum(1 for r in self.results if r['target1_hit'])
        false_breakouts = sum(1 for r in self.results if r['false_breakout'])

        print(f"\n📊 OVERALL STATISTICS:")
        print(f"  Total pivots analyzed: {total}")
        print(f"  Breakouts occurred: {breakouts} ({breakouts/total*100:.1f}%)")
        print(f"  Target1 reached: {target1_hits}/{breakouts} ({target1_hits/breakouts*100:.1f}% of breakouts)" if breakouts > 0 else "  Target1 reached: 0/0")
        print(f"  False breakouts: {false_breakouts}/{breakouts} ({false_breakouts/breakouts*100:.1f}% of breakouts)" if breakouts > 0 else "  False breakouts: 0/0")

        # Breakout quality
        if breakouts > 0:
            clean = sum(1 for r in self.results if r['breakout_occurred'] and r['breakout_quality'] == 'CLEAN')
            moderate = sum(1 for r in self.results if r['breakout_occurred'] and r['breakout_quality'] == 'MODERATE')
            choppy = sum(1 for r in self.results if r['breakout_occurred'] and r['breakout_quality'] == 'CHOPPY')

            print(f"\n🎯 BREAKOUT QUALITY:")
            print(f"  Clean (0 retests): {clean} ({clean/breakouts*100:.1f}%)")
            print(f"  Moderate (1-2 retests): {moderate} ({moderate/breakouts*100:.1f}%)")
            print(f"  Choppy (3+ retests): {choppy} ({choppy/breakouts*100:.1f}%)")

        # Stop optimization analysis
        if target1_hits > 0:
            print(f"\n🛡️  STOP OPTIMIZATION ANALYSIS:")

            for buffer_pct in self.stop_buffers:
                buffer_key = f"buffer_{buffer_pct:.1f}pct"

                # Count survivors among target1 winners
                survivors = sum(
                    1 for r in self.results
                    if r['target1_hit'] and r.get(f'survived_with_{buffer_key}', False)
                )

                # Average R/R for survivors
                rr_ratios = [
                    r[f'rr_ratio_{buffer_key}']
                    for r in self.results
                    if r['target1_hit'] and r.get(f'rr_ratio_{buffer_key}') is not None
                ]
                avg_rr = sum(rr_ratios) / len(rr_ratios) if rr_ratios else 0.0

                survival_rate = survivors / target1_hits * 100
                print(f"  Buffer {buffer_pct:.1f}%: "
                      f"{survivors}/{target1_hits} survived ({survival_rate:.1f}%) | "
                      f"Avg R/R: {avg_rr:.2f}:1")

        print("\n" + "=" * 80)

    def run(self, scanner_file: str, output_csv: str):
        """Main execution"""
        print("\n" + "=" * 80)
        print(f"PIVOT BEHAVIOR ANALYSIS - {self.date}")
        print("=" * 80)

        # Load scanner results
        print(f"\n📂 Loading scanner results from {scanner_file}...")
        try:
            with open(scanner_file, 'r') as f:
                scanner_data = json.load(f)
            print(f"  ✅ Loaded {len(scanner_data)} stocks")
        except Exception as e:
            print(f"  ❌ Error loading scanner file: {e}")
            return

        # Connect to IBKR
        self.connect_ib()

        # Analyze each stock
        for stock_data in scanner_data:
            symbol = stock_data['symbol']
            self.analyze_stock(symbol, stock_data)

        # Disconnect from IBKR
        self.disconnect_ib()

        # Save results
        self.save_to_csv(output_csv)

        # Print summary
        self.print_summary()

        print(f"\n✅ Analysis complete! Results saved to {output_csv}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze pivot behavior using IBKR historical data'
    )
    parser.add_argument(
        '--scanner',
        required=True,
        help='Scanner results file (JSON)'
    )
    parser.add_argument(
        '--date',
        required=True,
        help='Date to analyze (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--output',
        help='Output CSV file (default: pivot_behavior_YYYYMMDD.csv)'
    )
    parser.add_argument(
        '--account-size',
        type=float,
        default=50000,
        help='Account size (default: 50000)'
    )

    args = parser.parse_args()

    # Default output file
    if not args.output:
        date_str = args.date.replace('-', '')
        args.output = f"pivot_behavior_{date_str}.csv"

    # Create analyzer
    analyzer = PivotBehaviorAnalyzer(
        date=args.date,
        account_size=args.account_size
    )

    # Run analysis
    analyzer.run(args.scanner, args.output)


if __name__ == '__main__':
    main()
