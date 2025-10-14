#!/usr/bin/env python3
"""
Market Data Validator

Validates scanner predictions against actual market movements:
- Which breakouts actually happened
- Which were false breakouts
- Which setups never triggered
- Quality of pivot predictions
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import sys
sys.path.append('..')

from ib_insync import IB, Stock, util
import pytz


class MarketDataValidator:
    """
    Validates scanner predictions against real market data

    Step 1 of EOD Analysis: Verify what actually happened in the market
    """

    def __init__(self, date_str, scanner_file=None):
        """
        Initialize validator

        Args:
            date_str: Date in YYYYMMDD format
            scanner_file: Path to scanner results (auto-detect if None)
        """
        self.date_str = date_str
        self.date = datetime.strptime(date_str, '%Y%m%d')

        # Auto-detect scanner file
        if scanner_file:
            self.scanner_file = Path(scanner_file)
        else:
            # Try enhanced scoring first
            enhanced = Path(f'../scanner_validation/rescored_{date_str}.csv')
            if enhanced.exists():
                self.scanner_file = enhanced
            else:
                self.scanner_file = Path(f'../stockscanner/output/scanner_results_{date_str}.json')

        # Load scanner predictions
        self.scanner_data = self._load_scanner()

        # IB connection for historical data
        self.ib = None

        # Analysis results
        self.breakout_analysis = {}
        self.validation_summary = {}

    def _load_scanner(self):
        """Load scanner predictions"""
        if not self.scanner_file.exists():
            print(f"⚠️  Scanner file not found: {self.scanner_file}")
            return []

        if self.scanner_file.suffix == '.csv':
            df = pd.read_csv(self.scanner_file)
            return df.to_dict('records')
        else:
            with open(self.scanner_file, 'r') as f:
                return json.load(f)

    def connect_ib(self, port=7497, client_id=3001):
        """Connect to IBKR for market data"""
        self.ib = IB()
        try:
            self.ib.connect('127.0.0.1', port, clientId=client_id)
            print(f"✓ Connected to IBKR on port {port}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to IBKR: {e}")
            return False

    def validate_all(self):
        """Run complete validation"""
        print(f"\n{'='*80}")
        print(f"MARKET DATA VALIDATION - {self.date_str}")
        print(f"{'='*80}")

        if not self.scanner_data:
            print("\n⚠️  No scanner data to validate")
            return

        if not self.connect_ib():
            print("\n⚠️  Cannot proceed without IBKR connection")
            return

        try:
            # Validate each scanner prediction
            for i, stock in enumerate(self.scanner_data[:20], 1):  # Limit to top 20
                print(f"\nValidating {i}/{min(20, len(self.scanner_data))}: {stock['symbol']}...")
                self.validate_stock(stock)
                self.ib.sleep(1)  # Rate limiting

            # Generate summary
            self.generate_summary()

        finally:
            if self.ib:
                self.ib.disconnect()
                print("\n✓ Disconnected from IBKR")

    def validate_stock(self, stock_data):
        """Validate individual stock prediction"""
        symbol = stock_data['symbol']
        resistance = stock_data.get('resistance', 0)
        support = stock_data.get('support', 0)
        close_price = stock_data.get('close', 0)

        # Get 5-minute bars for the trading day
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            # Request historical data
            eastern = pytz.timezone('US/Eastern')
            end_datetime = self.date.replace(hour=16, minute=0)

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='5 mins',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                print(f"  ⚠️  No data available for {symbol}")
                return

            # Convert to DataFrame for easier analysis
            df = util.df(bars)

            # Analyze breakout attempts
            analysis = self._analyze_breakout(df, resistance, support, close_price)

            self.breakout_analysis[symbol] = analysis

            # Print summary
            self._print_stock_summary(symbol, analysis)

        except Exception as e:
            print(f"  ❌ Error validating {symbol}: {e}")

    def _analyze_breakout(self, df, resistance, support, close_price):
        """Analyze breakout attempts from market data"""
        analysis = {
            'resistance': resistance,
            'support': support,
            'close_price': close_price,
            'open_price': df.iloc[0]['open'],
            'high': df['high'].max(),
            'low': df['low'].min(),
            'close_eod': df.iloc[-1]['close'],
            'volume': df['volume'].sum(),
            'breakouts': [],
            'false_breakouts': [],
            'gap_analysis': {},
            'pivot_quality': {}
        }

        # Gap analysis
        gap_pct = ((analysis['open_price'] - close_price) / close_price) * 100
        analysis['gap_analysis'] = {
            'gap_pct': gap_pct,
            'gapped_above_resistance': analysis['open_price'] > resistance,
            'gapped_below_support': analysis['open_price'] < support,
        }

        # Track breakout attempts
        above_resistance_bars = 0
        below_support_bars = 0
        resistance_breaks = []
        support_breaks = []

        for idx, row in df.iterrows():
            # Check resistance break
            if row['high'] > resistance:
                if not resistance_breaks or (idx - resistance_breaks[-1]['bar']) > 12:  # New attempt if >1 hour
                    resistance_breaks.append({
                        'bar': idx,
                        'time': row['date'],
                        'break_price': row['high'],
                        'volume': row['volume']
                    })
                above_resistance_bars += 1

            # Check support break
            if row['low'] < support:
                if not support_breaks or (idx - support_breaks[-1]['bar']) > 12:
                    support_breaks.append({
                        'bar': idx,
                        'time': row['date'],
                        'break_price': row['low'],
                        'volume': row['volume']
                    })
                below_support_bars += 1

        # Classify breakouts as true or false
        for breakout in resistance_breaks:
            # Check if price held above resistance for >30 minutes (6 bars)
            held = self._check_breakout_held(df, breakout['bar'], resistance, 'above', 6)

            if held:
                max_gain = df.iloc[breakout['bar']:]['high'].max() - resistance
                analysis['breakouts'].append({
                    'type': 'RESISTANCE',
                    'time': breakout['time'],
                    'price': breakout['break_price'],
                    'held': True,
                    'max_gain': max_gain,
                    'gain_pct': (max_gain / resistance) * 100
                })
            else:
                analysis['false_breakouts'].append({
                    'type': 'RESISTANCE',
                    'time': breakout['time'],
                    'price': breakout['break_price'],
                    'whipsaw_bars': self._count_whipsaw_bars(df, breakout['bar'], resistance)
                })

        for breakout in support_breaks:
            held = self._check_breakout_held(df, breakout['bar'], support, 'below', 6)

            if held:
                max_loss = support - df.iloc[breakout['bar']:]['low'].min()
                analysis['breakouts'].append({
                    'type': 'SUPPORT',
                    'time': breakout['time'],
                    'price': breakout['break_price'],
                    'held': True,
                    'max_loss': max_loss,
                    'loss_pct': (max_loss / support) * 100
                })
            else:
                analysis['false_breakouts'].append({
                    'type': 'SUPPORT',
                    'time': breakout['time'],
                    'price': breakout['break_price'],
                    'whipsaw_bars': self._count_whipsaw_bars(df, breakout['bar'], support)
                })

        # Pivot quality assessment
        analysis['pivot_quality'] = {
            'resistance_tested': len(resistance_breaks),
            'support_tested': len(support_breaks),
            'resistance_held': analysis['high'] < resistance * 1.005,  # Within 0.5%
            'support_held': analysis['low'] > support * 0.995,
            'time_above_resistance_pct': (above_resistance_bars / len(df)) * 100,
            'time_below_support_pct': (below_support_bars / len(df)) * 100,
        }

        return analysis

    def _check_breakout_held(self, df, start_bar, pivot, direction, min_bars):
        """Check if breakout held for minimum bars"""
        if start_bar + min_bars >= len(df):
            return False  # Not enough data

        for i in range(start_bar, min(start_bar + min_bars, len(df))):
            if direction == 'above':
                if df.iloc[i]['low'] < pivot:
                    return False  # Fell back below
            else:  # below
                if df.iloc[i]['high'] > pivot:
                    return False  # Rose back above

        return True

    def _count_whipsaw_bars(self, df, start_bar, pivot):
        """Count how many bars until price returned to pivot"""
        for i in range(start_bar + 1, len(df)):
            if abs(df.iloc[i]['close'] - pivot) / pivot < 0.002:  # Within 0.2%
                return i - start_bar
        return len(df) - start_bar  # Never returned

    def _print_stock_summary(self, symbol, analysis):
        """Print validation summary for stock"""
        print(f"\n  {symbol} Validation:")
        print(f"  {'='*50}")

        # Gap analysis
        gap = analysis['gap_analysis']
        if abs(gap['gap_pct']) > 1:
            print(f"  📊 Gap: {gap['gap_pct']:+.2f}%", end='')
            if gap['gapped_above_resistance']:
                print(" (Gapped ABOVE resistance)")
            elif gap['gapped_below_support']:
                print(" (Gapped BELOW support)")
            else:
                print()

        # Pivot levels
        print(f"  📍 Resistance: ${analysis['resistance']:.2f}")
        print(f"  📍 Support: ${analysis['support']:.2f}")
        print(f"  📈 Day Range: ${analysis['low']:.2f} - ${analysis['high']:.2f}")

        # Breakouts
        if analysis['breakouts']:
            print(f"\n  ✅ TRUE BREAKOUTS ({len(analysis['breakouts'])})")
            for b in analysis['breakouts']:
                if b['type'] == 'RESISTANCE':
                    print(f"    • {b['time'].strftime('%I:%M %p')}: Broke resistance, gained {b['gain_pct']:.2f}%")
                else:
                    print(f"    • {b['time'].strftime('%I:%M %p')}: Broke support, fell {b['loss_pct']:.2f}%")

        # False breakouts
        if analysis['false_breakouts']:
            print(f"\n  ❌ FALSE BREAKOUTS ({len(analysis['false_breakouts'])})")
            for fb in analysis['false_breakouts']:
                print(f"    • {fb['time'].strftime('%I:%M %p')}: Failed {fb['type'].lower()} break, whipsawed in {fb['whipsaw_bars']} bars")

        # Pivot quality
        quality = analysis['pivot_quality']
        if quality['resistance_held'] and quality['support_held']:
            print(f"\n  📊 Pivots HELD - Rangebound day")
        elif not quality['resistance_held']:
            print(f"\n  📊 Resistance BROKEN - Bullish day")
        elif not quality['support_held']:
            print(f"\n  📊 Support BROKEN - Bearish day")

    def generate_summary(self):
        """Generate overall validation summary"""
        print(f"\n{'='*80}")
        print(f"VALIDATION SUMMARY")
        print(f"{'='*80}")

        total_stocks = len(self.breakout_analysis)
        total_breakouts = sum(len(a['breakouts']) for a in self.breakout_analysis.values())
        total_false = sum(len(a['false_breakouts']) for a in self.breakout_analysis.values())

        print(f"\n📊 Overall Statistics:")
        print(f"  Stocks Analyzed: {total_stocks}")
        print(f"  True Breakouts: {total_breakouts}")
        print(f"  False Breakouts: {total_false}")

        if total_breakouts + total_false > 0:
            success_rate = (total_breakouts / (total_breakouts + total_false)) * 100
            print(f"  Breakout Success Rate: {success_rate:.1f}%")

        # Best breakouts
        best_breakouts = []
        for symbol, analysis in self.breakout_analysis.items():
            for b in analysis.get('breakouts', []):
                if b['type'] == 'RESISTANCE' and 'gain_pct' in b:
                    best_breakouts.append((symbol, b['gain_pct'], b['time']))

        if best_breakouts:
            best_breakouts.sort(key=lambda x: x[1], reverse=True)
            print(f"\n💰 Top 3 Breakouts:")
            for symbol, gain, time in best_breakouts[:3]:
                print(f"  {symbol}: +{gain:.2f}% at {time.strftime('%I:%M %p')}")

        # Biggest false breakouts
        false_breakouts = []
        for symbol, analysis in self.breakout_analysis.items():
            false_breakouts.extend([(symbol, fb) for fb in analysis.get('false_breakouts', [])])

        if false_breakouts:
            print(f"\n⚠️  Notable False Breakouts:")
            for symbol, fb in false_breakouts[:3]:
                print(f"  {symbol}: Failed {fb['type'].lower()} break at {fb['time'].strftime('%I:%M %p')}")

        # Gap analysis
        gap_ups = []
        gap_downs = []
        for symbol, analysis in self.breakout_analysis.items():
            gap_pct = analysis['gap_analysis']['gap_pct']
            if gap_pct > 2:
                gap_ups.append((symbol, gap_pct))
            elif gap_pct < -2:
                gap_downs.append((symbol, gap_pct))

        if gap_ups or gap_downs:
            print(f"\n📈 Significant Gaps:")
            for symbol, gap in sorted(gap_ups, key=lambda x: x[1], reverse=True)[:3]:
                print(f"  {symbol}: +{gap:.2f}% gap up")
            for symbol, gap in sorted(gap_downs, key=lambda x: x[1])[:3]:
                print(f"  {symbol}: {gap:.2f}% gap down")

        # Save results
        self.save_validation()

    def save_validation(self):
        """Save validation results to JSON"""
        output_file = Path(f'logs/market_validation_{self.date_str}.json')

        # Convert datetime objects to strings
        clean_data = {}
        for symbol, analysis in self.breakout_analysis.items():
            clean_analysis = analysis.copy()

            # Convert breakout times
            for b in clean_analysis.get('breakouts', []):
                if 'time' in b and hasattr(b['time'], 'strftime'):
                    b['time'] = b['time'].isoformat()

            for fb in clean_analysis.get('false_breakouts', []):
                if 'time' in fb and hasattr(fb['time'], 'strftime'):
                    fb['time'] = fb['time'].isoformat()

            clean_data[symbol] = clean_analysis

        with open(output_file, 'w') as f:
            json.dump(clean_data, f, indent=2, default=str)

        print(f"\n📄 Validation saved to: {output_file}")
        return output_file


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python market_validator.py YYYYMMDD")
        print("Example: python market_validator.py 20251007")
        sys.exit(1)

    date_str = sys.argv[1]

    validator = MarketDataValidator(date_str)
    validator.validate_all()