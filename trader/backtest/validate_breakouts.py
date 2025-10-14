#!/usr/bin/env python3
"""
Breakout Validation Script

Analyzes actual price action of trades to determine:
1. TRUE vs FALSE breakouts
2. Whipsaws (stops too tight?)
3. Re-entry opportunities
4. Entry timing analysis
5. Confirmation logic analysis from logs

Uses 1-minute historical bars from IBKR to validate breakout quality.
"""

import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util
import pandas as pd
import time
import re


class BreakoutValidator:
    """Validates breakout quality using 1-minute price action"""

    def __init__(self, date, scanner_file, trades_file, log_file=None):
        """
        Initialize validator

        Args:
            date: Trading date (YYYY-MM-DD)
            scanner_file: Path to scanner results JSON
            trades_file: Path to backtest trades JSON
            log_file: Optional path to backtester log file for detailed analysis
        """
        self.date = datetime.strptime(date, '%Y-%m-%d').date()

        # Load scanner results
        with open(scanner_file) as f:
            self.scanner_data = {s['symbol']: s for s in json.load(f)}

        # Load trade results
        with open(trades_file) as f:
            self.trades = json.load(f)

        # Parse log file if provided
        self.log_data = {}
        if log_file and Path(log_file).exists():
            self.log_data = self._parse_log_file(log_file)

        # IBKR connection
        self.ib = IB()

        # Results storage
        self.bar_data = {}  # {symbol: bars}
        self.analyses = []  # List of trade analyses

    def _parse_log_file(self, log_file):
        """
        Parse backtester log file to extract entry decisions

        Returns:
            dict: {symbol: {entries: [...], confirmations: [...], checks: [...]}}
        """
        print(f"\n📋 Parsing log file: {log_file}")
        log_data = {}

        try:
            with open(log_file, 'r') as f:
                for line in f:
                    # Parse ENTERING lines
                    if 'ENTERING' in line:
                        match = re.search(r'(\w+) Bar (\d+) - ENTERING (LONG|SHORT) @ \$([0-9.]+), stop=\$([0-9.]+), attempts=(\d+)/(\d+)', line)
                        if match:
                            symbol, bar, side, entry, stop, attempt, max_attempts = match.groups()
                            if symbol not in log_data:
                                log_data[symbol] = {'entries': [], 'confirmations': [], 'checks': []}
                            log_data[symbol]['entries'].append({
                                'bar': int(bar),
                                'side': side,
                                'entry_price': float(entry),
                                'stop_price': float(stop),
                                'attempt': int(attempt),
                                'max_attempts': int(max_attempts)
                            })

                    # Parse confirmation lines
                    elif 'confirmation:' in line:
                        match = re.search(r'(\w+) Bar (\d+) - (LONG|SHORT) confirmation: confirmed=(True|False), reason=\'([^\']+)\', entry_state=', line)
                        if match:
                            symbol, bar, side, confirmed, reason = match.groups()
                            if symbol not in log_data:
                                log_data[symbol] = {'entries': [], 'confirmations': [], 'checks': []}
                            log_data[symbol]['confirmations'].append({
                                'bar': int(bar),
                                'side': side,
                                'confirmed': confirmed == 'True',
                                'reason': reason
                            })

                    # Parse check lines (for failed entries)
                    elif 'check:' in line and 'should_enter=' in line:
                        match = re.search(r'(\w+) Bar (\d+) - (LONG|SHORT) check: .* should_enter=(True|False), reason=\'([^\']+)\'', line)
                        if match:
                            symbol, bar, side, should_enter, reason = match.groups()
                            if symbol not in log_data:
                                log_data[symbol] = {'entries': [], 'confirmations': [], 'checks': []}
                            # Only keep True checks (potential entries)
                            if should_enter == 'True':
                                log_data[symbol]['checks'].append({
                                    'bar': int(bar),
                                    'side': side,
                                    'should_enter': True,
                                    'reason': reason
                                })

            print(f"  ✅ Parsed log data for {len(log_data)} symbols")
            return log_data

        except Exception as e:
            print(f"  ⚠️  Error parsing log: {e}")
            return {}

    def connect(self):
        """Connect to IBKR"""
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=4000)
            print("✅ Connected to IBKR")
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib.isConnected():
            self.ib.disconnect()

    def fetch_1min_bars(self, symbols):
        """
        Fetch 1-minute bars for all symbols

        Args:
            symbols: List of stock symbols
        """
        print(f"\n📊 Fetching 1-minute bars for {len(symbols)} symbols...")

        for i, symbol in enumerate(symbols, 1):
            print(f"  [{i}/{len(symbols)}] {symbol}...", end=' ')

            try:
                contract = Stock(symbol, 'SMART', 'USD')
                self.ib.qualifyContracts(contract)

                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=f'{self.date.strftime("%Y%m%d")} 16:00:00',
                    durationStr='1 D',
                    barSizeSetting='1 min',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )

                if bars:
                    self.bar_data[symbol] = bars
                    print(f"✅ {len(bars)} bars")
                else:
                    print("⚠️  No data")

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                print(f"❌ Error: {e}")

    def analyze_breakout_timeline(self, symbol, bars, pivot, side, our_entry_time, our_entry_price, our_exit_time, our_exit_price, our_stop_price):
        """
        Analyze breakout timeline for a single trade

        Returns:
            dict: Timeline analysis with breakout details
        """
        if not bars:
            return None

        analysis = {
            'symbol': symbol,
            'side': side,
            'pivot': pivot,
            'our_entry_time': our_entry_time,
            'our_entry_price': our_entry_price,
            'our_exit_time': our_exit_time,
            'our_exit_price': our_exit_price,
            'our_stop_price': our_stop_price,
        }

        # Find first breakout
        breakout_bar = None
        breakout_idx = None

        for i, bar in enumerate(bars):
            if side == 'LONG':
                if bar.close > pivot:
                    breakout_bar = bar
                    breakout_idx = i
                    break
            else:  # SHORT
                if bar.close < pivot:
                    breakout_bar = bar
                    breakout_idx = i
                    break

        if not breakout_bar:
            analysis['breakout_found'] = False
            analysis['classification'] = 'NO_BREAKOUT'
            return analysis

        analysis['breakout_found'] = True
        analysis['breakout_time'] = breakout_bar.date
        analysis['breakout_price'] = breakout_bar.close
        analysis['breakout_volume'] = breakout_bar.volume

        # Calculate follow-through (max move in first 5 minutes)
        follow_through_bars = bars[breakout_idx:min(breakout_idx+5, len(bars))]
        if side == 'LONG':
            max_price = max(b.high for b in follow_through_bars)
            follow_through = ((max_price - pivot) / pivot) * 100
        else:
            min_price = min(b.low for b in follow_through_bars)
            follow_through = ((pivot - min_price) / pivot) * 100

        analysis['follow_through_pct'] = follow_through

        # Find when WE entered
        our_entry_dt = datetime.fromisoformat(our_entry_time)
        entry_delay_bars = 0
        for i in range(breakout_idx, len(bars)):
            if bars[i].date >= our_entry_dt:
                entry_delay_bars = i - breakout_idx
                break

        analysis['entry_delay_bars'] = entry_delay_bars

        # Calculate where in the range we entered
        if side == 'LONG':
            move_at_entry = our_entry_price - pivot
            if follow_through > 0:
                entry_position_pct = (move_at_entry / (max_price - pivot)) * 100
            else:
                entry_position_pct = 100  # Entered at peak
        else:
            move_at_entry = pivot - our_entry_price
            if follow_through > 0:
                entry_position_pct = (move_at_entry / (pivot - min_price)) * 100
            else:
                entry_position_pct = 100

        analysis['entry_position_pct'] = min(entry_position_pct, 100)

        # Check what happened after our stop hit
        our_exit_dt = datetime.fromisoformat(our_exit_time)
        exit_idx = None
        for i, bar in enumerate(bars):
            if bar.date >= our_exit_dt:
                exit_idx = i
                break

        if exit_idx and exit_idx < len(bars) - 1:
            # Look at next 2 hours (120 bars)
            post_exit_bars = bars[exit_idx:min(exit_idx+120, len(bars))]

            if side == 'LONG':
                # Did it reverse UP after stop?
                max_after_stop = max(b.high for b in post_exit_bars)
                reversal_to_profit = max_after_stop > our_entry_price
                max_move_after_stop = ((max_after_stop - our_exit_price) / our_exit_price) * 100
            else:
                # Did it reverse DOWN after stop?
                min_after_stop = min(b.low for b in post_exit_bars)
                reversal_to_profit = min_after_stop < our_entry_price
                max_move_after_stop = ((our_exit_price - min_after_stop) / our_exit_price) * 100

            analysis['reversal_to_profit'] = reversal_to_profit
            analysis['max_move_after_stop_pct'] = max_move_after_stop
        else:
            analysis['reversal_to_profit'] = False
            analysis['max_move_after_stop_pct'] = 0

        # Classify breakout
        analysis['classification'] = self._classify_breakout(analysis, side)

        return analysis

    def _classify_breakout(self, analysis, side):
        """
        Classify breakout into one of 6 categories:
        1. TRUE BREAKOUT - Clean Winner
        2. TRUE BREAKOUT - Stop Too Tight (whipsaw)
        3. FALSE BREAKOUT - Immediate Reversal
        4. FALSE BREAKOUT - Failed After Move
        5. CHOPPY/INDECISION
        6. RE-ENTRY WINNER
        """
        follow_through = analysis['follow_through_pct']
        reversal = analysis['reversal_to_profit']
        entry_delay = analysis['entry_delay_bars']

        # Category 1: Clean Winner (good P&L from our trade)
        # (This will be determined by actual P&L, marked later)

        # Category 2: Whipsaw (stop hit, then reversed to profit)
        if reversal and analysis['max_move_after_stop_pct'] > 0.5:
            return 'WHIPSAW'

        # Category 3: Immediate Reversal (<= 2 bars follow-through)
        if follow_through < 0.2 and entry_delay <= 2:
            return 'FALSE_IMMEDIATE'

        # Category 4: Failed After Move (some follow-through, but still failed)
        if follow_through >= 0.2 and follow_through < 1.0:
            return 'FALSE_AFTER_MOVE'

        # Category 5: Choppy (multiple small moves)
        if 0.2 <= follow_through <= 0.5:
            return 'CHOPPY'

        # Default: True breakout (will be refined with P&L)
        return 'TRUE_BREAKOUT'

    def detect_whipsaws(self, symbol, bars, side, entry_price, stop_price, exit_reason):
        """
        Test if wider stops would have saved the trade

        Tests: +0.5% and +1.0% wider stops

        Returns:
            dict: Whipsaw test results
        """
        if exit_reason != 'STOP':
            return {'was_stopped': False}

        results = {
            'was_stopped': True,
            'original_stop': stop_price,
            'wider_0_5_pct': None,
            'wider_1_0_pct': None
        }

        if not bars:
            return results

        # Calculate wider stops
        if side == 'LONG':
            stop_0_5 = stop_price * (1 - 0.005)  # 0.5% below
            stop_1_0 = stop_price * (1 - 0.010)  # 1.0% below
        else:
            stop_0_5 = stop_price * (1 + 0.005)  # 0.5% above
            stop_1_0 = stop_price * (1 + 0.010)  # 1.0% above

        # Test each stop level
        for bar in bars:
            # Test 0.5% wider
            if results['wider_0_5_pct'] is None:
                if side == 'LONG':
                    if bar.low <= stop_0_5:
                        results['wider_0_5_pct'] = 'STOPPED'
                else:
                    if bar.high >= stop_0_5:
                        results['wider_0_5_pct'] = 'STOPPED'

            # Test 1.0% wider
            if results['wider_1_0_pct'] is None:
                if side == 'LONG':
                    if bar.low <= stop_1_0:
                        results['wider_1_0_pct'] = 'STOPPED'
                else:
                    if bar.high >= stop_1_0:
                        results['wider_1_0_pct'] = 'STOPPED'

        # If never stopped, would have been saved
        if results['wider_0_5_pct'] is None:
            results['wider_0_5_pct'] = 'SAVED'
        if results['wider_1_0_pct'] is None:
            results['wider_1_0_pct'] = 'SAVED'

        return results

    def analyze_all_trades(self):
        """Analyze all trades"""
        print(f"\n🔍 Analyzing {len(self.trades)} trades...")

        for i, trade in enumerate(self.trades, 1):
            symbol = trade['symbol']
            print(f"\n[{i}/{len(self.trades)}] {symbol} {trade['side']}...")

            if symbol not in self.bar_data:
                print(f"  ⚠️  No bar data for {symbol}")
                continue

            if symbol not in self.scanner_data:
                print(f"  ⚠️  No scanner data for {symbol}")
                continue

            # Get pivot from scanner
            scanner = self.scanner_data[symbol]
            side = trade['side']
            pivot = scanner['resistance'] if side == 'LONG' else scanner['support']

            # Analyze breakout timeline
            timeline = self.analyze_breakout_timeline(
                symbol,
                self.bar_data[symbol],
                pivot,
                side,
                trade['entry_time'],
                trade['entry_price'],
                trade['exit_time'],
                trade['exit_price'],
                trade.get('stop_price', pivot)
            )

            if timeline:
                # Add trade P&L info
                timeline['actual_pnl'] = trade['pnl']
                timeline['actual_exit_reason'] = trade['reason']

                # Add log data if available
                if symbol in self.log_data:
                    timeline['log_entries'] = self.log_data[symbol].get('entries', [])
                    timeline['log_confirmations'] = self.log_data[symbol].get('confirmations', [])
                    timeline['log_checks'] = self.log_data[symbol].get('checks', [])

                    # Count failed confirmations (should_enter=True but confirmed=False)
                    failed_confirmations = [c for c in self.log_data[symbol].get('confirmations', [])
                                          if not c['confirmed'] and c['side'] == side]
                    timeline['failed_confirmations_count'] = len(failed_confirmations)
                    if failed_confirmations:
                        timeline['failed_confirmation_reasons'] = [c['reason'] for c in failed_confirmations[:5]]  # First 5

                # Refine classification based on P&L
                if trade['pnl'] > 50:  # Winner
                    if timeline['classification'] in ['TRUE_BREAKOUT', 'CHOPPY']:
                        timeline['classification'] = 'TRUE_BREAKOUT_WINNER'

                # Whipsaw analysis
                whipsaw_results = self.detect_whipsaws(
                    symbol,
                    self.bar_data[symbol],
                    side,
                    trade['entry_price'],
                    trade.get('stop_price', pivot),
                    trade['reason']
                )
                timeline['whipsaw_test'] = whipsaw_results

                self.analyses.append(timeline)

                # Print summary
                print(f"  Breakout: {timeline.get('breakout_time', 'N/A')}")
                print(f"  Follow-through: {timeline.get('follow_through_pct', 0):.2f}%")
                print(f"  Entry delay: {timeline.get('entry_delay_bars', 0)} bars")
                print(f"  Entry position: {timeline.get('entry_position_pct', 0):.1f}% of range")
                print(f"  Classification: {timeline.get('classification', 'UNKNOWN')}")
                if whipsaw_results['was_stopped']:
                    print(f"  Whipsaw 0.5%: {whipsaw_results['wider_0_5_pct']}")
                    print(f"  Whipsaw 1.0%: {whipsaw_results['wider_1_0_pct']}")

    def generate_summary(self):
        """Generate summary statistics"""
        if not self.analyses:
            print("\n⚠️  No analyses to summarize")
            return

        print("\n" + "="*80)
        print("BREAKOUT VALIDATION SUMMARY")
        print("="*80)

        # Classification distribution
        classifications = {}
        for a in self.analyses:
            c = a['classification']
            classifications[c] = classifications.get(c, 0) + 1

        print("\n📊 BREAKOUT CLASSIFICATIONS:")
        total = len(self.analyses)
        for c, count in sorted(classifications.items()):
            pct = (count / total) * 100
            print(f"  {c:30s}: {count:3d} ({pct:5.1f}%)")

        # Entry timing stats
        winners = [a for a in self.analyses if a['actual_pnl'] > 0]
        losers = [a for a in self.analyses if a['actual_pnl'] <= 0]

        print(f"\n⏱️  ENTRY TIMING:")
        if winners:
            avg_delay_winners = sum(a['entry_delay_bars'] for a in winners) / len(winners)
            avg_pos_winners = sum(a['entry_position_pct'] for a in winners) / len(winners)
            print(f"  Winners avg delay: {avg_delay_winners:.1f} bars")
            print(f"  Winners avg position: {avg_pos_winners:.1f}% of range")

        if losers:
            avg_delay_losers = sum(a['entry_delay_bars'] for a in losers) / len(losers)
            avg_pos_losers = sum(a['entry_position_pct'] for a in losers) / len(losers)
            print(f"  Losers avg delay: {avg_delay_losers:.1f} bars")
            print(f"  Losers avg position: {avg_pos_losers:.1f}% of range")

        # Whipsaw analysis
        stopped_trades = [a for a in self.analyses if a['whipsaw_test']['was_stopped']]
        if stopped_trades:
            saved_0_5 = sum(1 for a in stopped_trades if a['whipsaw_test']['wider_0_5_pct'] == 'SAVED')
            saved_1_0 = sum(1 for a in stopped_trades if a['whipsaw_test']['wider_1_0_pct'] == 'SAVED')

            print(f"\n🔄 WHIPSAW ANALYSIS:")
            print(f"  Total stopped trades: {len(stopped_trades)}")
            print(f"  Saved with +0.5% wider stop: {saved_0_5} ({(saved_0_5/len(stopped_trades)*100):.1f}%)")
            print(f"  Saved with +1.0% wider stop: {saved_1_0} ({(saved_1_0/len(stopped_trades)*100):.1f}%)")

            # Estimate P&L improvement
            avg_loss = sum(a['actual_pnl'] for a in stopped_trades) / len(stopped_trades)
            estimated_improvement_0_5 = saved_0_5 * abs(avg_loss)
            estimated_improvement_1_0 = saved_1_0 * abs(avg_loss)
            print(f"  Est. P&L improvement +0.5%: ${estimated_improvement_0_5:,.0f}")
            print(f"  Est. P&L improvement +1.0%: ${estimated_improvement_1_0:,.0f}")

        # Reversal analysis
        reversals = [a for a in self.analyses if a.get('reversal_to_profit', False)]
        print(f"\n🔁 REVERSAL TO PROFIT:")
        print(f"  Trades that reversed to profit after stop: {len(reversals)} ({(len(reversals)/total*100):.1f}%)")

        if reversals:
            avg_move = sum(a['max_move_after_stop_pct'] for a in reversals) / len(reversals)
            print(f"  Avg move after stop hit: {avg_move:.2f}%")

        print("\n" + "="*80)

    def save_detailed_report(self, output_file):
        """Save detailed trade-by-trade report"""
        with open(output_file, 'w') as f:
            f.write("BREAKOUT VALIDATION - DETAILED REPORT\n")
            f.write("=" * 100 + "\n\n")

            for i, a in enumerate(self.analyses, 1):
                f.write(f"\nTRADE #{i}: {a['symbol']} {a['side']}\n")
                f.write("-" * 100 + "\n")
                f.write(f"Pivot: ${a['pivot']:.2f}\n")

                if a['breakout_found']:
                    f.write(f"Breakout: {a['breakout_time']} @ ${a['breakout_price']:.2f}\n")
                    f.write(f"Follow-through: {a['follow_through_pct']:.2f}%\n")
                    f.write(f"Our Entry: {a['our_entry_time']} @ ${a['our_entry_price']:.2f}\n")
                    f.write(f"Entry Delay: {a['entry_delay_bars']} bars after breakout\n")
                    f.write(f"Entry Position: {a['entry_position_pct']:.1f}% of range\n")
                else:
                    f.write("⚠️  NO BREAKOUT FOUND\n")

                f.write(f"Exit: {a['our_exit_time']} @ ${a['our_exit_price']:.2f}\n")
                f.write(f"P&L: ${a['actual_pnl']:.2f}\n")
                f.write(f"Exit Reason: {a['actual_exit_reason']}\n")
                f.write(f"\nCLASSIFICATION: {a['classification']}\n")

                if a.get('reversal_to_profit'):
                    f.write(f"⚠️  REVERSAL: Price moved {a['max_move_after_stop_pct']:.2f}% in profit direction after stop!\n")

                if a['whipsaw_test']['was_stopped']:
                    f.write(f"\nWhipsaw Test:\n")
                    f.write(f"  +0.5% wider: {a['whipsaw_test']['wider_0_5_pct']}\n")
                    f.write(f"  +1.0% wider: {a['whipsaw_test']['wider_1_0_pct']}\n")

                # Add log analysis if available
                if a.get('failed_confirmations_count', 0) > 0:
                    f.write(f"\n⚠️  CONFIRMATION FAILURES: {a['failed_confirmations_count']} failed attempts\n")
                    if 'failed_confirmation_reasons' in a:
                        f.write(f"   Reasons: {', '.join(a['failed_confirmation_reasons'])}\n")

                if a.get('log_entries'):
                    f.write(f"\nLog Data:\n")
                    f.write(f"  Entries attempted: {len(a['log_entries'])}\n")
                    for entry in a['log_entries']:
                        f.write(f"    Bar {entry['bar']}: {entry['side']} @ ${entry['entry_price']:.2f} (attempt {entry['attempt']+1})\n")

                f.write("\n")

        print(f"\n💾 Detailed report saved to: {output_file}")

    def save_csv(self, output_file):
        """Save analysis data to CSV"""
        if not self.analyses:
            return

        df = pd.DataFrame(self.analyses)

        # Flatten nested whipsaw_test dict
        df['whipsaw_wider_0_5'] = df['whipsaw_test'].apply(lambda x: x.get('wider_0_5_pct', 'N/A'))
        df['whipsaw_wider_1_0'] = df['whipsaw_test'].apply(lambda x: x.get('wider_1_0_pct', 'N/A'))
        df = df.drop('whipsaw_test', axis=1)

        df.to_csv(output_file, index=False)
        print(f"💾 CSV data saved to: {output_file}")

    def run(self):
        """Run full validation analysis"""
        if not self.connect():
            return

        try:
            # Get list of traded symbols
            symbols = list(set(t['symbol'] for t in self.trades))

            # Fetch 1-minute bars
            self.fetch_1min_bars(symbols)

            # Analyze all trades
            self.analyze_all_trades()

            # Generate summary
            self.generate_summary()

            # Save reports
            date_str = self.date.strftime('%Y%m%d')
            results_dir = Path(__file__).parent / 'results'
            results_dir.mkdir(exist_ok=True)

            detailed_file = results_dir / f'breakout_validation_{date_str}.txt'
            csv_file = results_dir / f'breakout_validation_{date_str}.csv'

            self.save_detailed_report(detailed_file)
            self.save_csv(csv_file)

        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description='Validate breakout quality using 1-minute bars')
    parser.add_argument('--date', required=True, help='Trading date (YYYY-MM-DD)')
    parser.add_argument('--scanner', required=True, help='Path to scanner results JSON')
    parser.add_argument('--trades', required=True, help='Path to backtest trades JSON')
    parser.add_argument('--log', help='Optional path to backtester log file for detailed analysis')

    args = parser.parse_args()

    validator = BreakoutValidator(args.date, args.scanner, args.trades, args.log)
    validator.run()


if __name__ == '__main__':
    main()
