#!/usr/bin/env python3
"""
PS60 Backtester - Uses 1-minute historical bars from IBKR
Simulates tick-by-tick monitoring of scanner-identified pivots
"""

from ib_insync import IB, Stock
from datetime import datetime, timedelta
import json
import pandas as pd
import sys
import argparse
from pathlib import Path

class PS60Backtester:
    """
    Backtest PS60 strategy using 1-minute historical bars from IBKR
    Simulates tick-by-tick monitoring of scanner-identified pivots
    """

    def __init__(self, scanner_file=None, test_date=None, account_size=100000,
                 scanner_results_path=None):
        """
        Initialize backtester

        Args:
            scanner_file: Path to scanner results (old parameter name)
            test_date: Date to backtest (can be string or datetime)
            account_size: Account size for position sizing
            scanner_results_path: Path to scanner results (new parameter name)
        """
        self.ib = IB()

        # Support both old and new parameter names
        if scanner_results_path is not None:
            scanner_file = scanner_results_path
        elif scanner_file is None:
            raise ValueError("Must provide scanner_file or scanner_results_path")

        self.scanner_file = scanner_file

        # Convert test_date to datetime if string
        if isinstance(test_date, str):
            self.test_date = datetime.strptime(test_date, '%Y-%m-%d')
        else:
            self.test_date = test_date

        self.account_size = account_size
        self.trades = []
        self.positions = {}

        # Load scanner results
        print(f"\n{'='*80}")
        print(f"PS60 BACKTEST - {self.test_date}")
        print(f"{'='*80}")
        print(f"Scanner file: {scanner_file}")

        with open(scanner_file) as f:
            self.scanner_results = json.load(f)

        print(f"Loaded {len(self.scanner_results)} scanner results")

    def connect(self):
        """Connect to IBKR"""
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=3000)
            print(f"✓ Connected to IBKR (Client ID: 3000)")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("\n✓ Disconnected from IBKR")

    def run(self):
        """Run backtest"""
        if not self.connect():
            return

        try:
            self.backtest_day()
            self.print_results()
        finally:
            self.disconnect()

    def backtest_day(self):
        """Backtest single trading day"""
        # Filter scanner for tradeable setups (UPDATED: R/R >= 1.5, Score >= 75)
        watchlist = [s for s in self.scanner_results
                     if s['score'] >= 75 and s['risk_reward'] >= 1.5]

        print(f"\n{'='*80}")
        print(f"WATCHLIST: {len(watchlist)} tradeable setups (score≥75, R/R≥1.5)")
        print(f"{'='*80}")

        for stock in watchlist:
            print(f"\n[{stock['symbol']}] Testing setup...")
            print(f"  Resistance: ${stock['resistance']:.2f} | Support: ${stock['support']:.2f}")
            print(f"  Score: {stock['score']} | R/R: {stock['risk_reward']:.2f}:1")

            self.backtest_stock(stock)

    def backtest_stock(self, stock):
        """Backtest single stock for the day"""
        symbol = stock['symbol']
        resistance = stock['resistance']
        support = stock['support']

        # Get 1-minute historical bars from IBKR
        bars = self.get_bars(symbol)

        if not bars:
            print(f"  ⚠️  No historical data available")
            return

        print(f"  ✓ Fetched {len(bars)} 1-minute bars")

        position = None
        bar_count = 0

        # Track attempts for each pivot (MAX 2 ATTEMPTS PER PIVOT)
        long_attempts = 0
        short_attempts = 0
        max_attempts = 2

        # Simulate tick-by-tick monitoring
        for bar in bars:
            bar_count += 1
            timestamp = bar.date
            price = bar.close

            # No new entries in last hour (after 3:00 PM / 15:00)
            hour = timestamp.hour
            minute = timestamp.minute
            time_cutoff = (hour >= 15)  # 3:00 PM or later

            # Entry logic - check for pivot breaks (MAX 2 ATTEMPTS)
            if position is None and not time_cutoff:
                # Long entry - only if we haven't exceeded max attempts
                if long_attempts < max_attempts and price > resistance:
                    position = self.enter_long(stock, price, timestamp, bar_count)
                    long_attempts += 1  # Increment attempt counter

                # Short entry - only if we haven't exceeded max attempts
                elif short_attempts < max_attempts and price < support:
                    position = self.enter_short(stock, price, timestamp, bar_count)
                    short_attempts += 1  # Increment attempt counter

            # Exit logic - manage open position
            elif position is not None:
                position, closed_trade = self.manage_position(
                    position, price, timestamp, bar_count
                )
                if closed_trade:
                    self.trades.append(closed_trade)
                    position = None
                    # Attempts NOT reset - max 2 tries per pivot per day

        # Close any remaining position at EOD
        if position:
            print(f"  💼 EOD close remaining position @ ${price:.2f}")
            closed_trade = self.close_position(
                position, price, timestamp, 'EOD', bar_count
            )
            self.trades.append(closed_trade)

    def get_bars(self, symbol):
        """Fetch 1-minute bars from IBKR"""
        contract = Stock(symbol, 'SMART', 'USD')

        try:
            # Request historical 1-minute bars for the day
            end_datetime = f'{self.test_date.strftime("%Y%m%d")} 16:00:00'

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,  # Regular trading hours only
                formatDate=1
            )

            # Add small delay to respect rate limits
            self.ib.sleep(0.5)

            return bars

        except Exception as e:
            print(f"  ✗ Error fetching data: {e}")
            return []

    def enter_long(self, stock, price, timestamp, bar_num):
        """Enter long position"""
        shares = self.calculate_position_size(price, stock['resistance'])

        position = {
            'symbol': stock['symbol'],
            'side': 'LONG',
            'entry_price': price,
            'entry_time': timestamp,
            'entry_bar': bar_num,
            'stop': stock['resistance'],  # Initial stop at pivot
            'target1': stock['target1'],
            'target2': stock['target2'],
            'shares': shares,
            'remaining': 1.0,  # 100% of position
            'partials': []
        }

        print(f"  🟢 LONG @ ${price:.2f} (bar {bar_num}, {timestamp.strftime('%H:%M')})")
        print(f"     Shares: {shares} | Stop: ${stock['resistance']:.2f}")
        return position

    def enter_short(self, stock, price, timestamp, bar_num):
        """Enter short position"""
        shares = self.calculate_position_size(stock['support'], price)

        position = {
            'symbol': stock['symbol'],
            'side': 'SHORT',
            'entry_price': price,
            'entry_time': timestamp,
            'entry_bar': bar_num,
            'stop': stock['support'],  # Initial stop at pivot
            'target1': stock['downside1'],
            'target2': stock['downside2'],
            'shares': shares,
            'remaining': 1.0,
            'partials': []
        }

        print(f"  🔴 SHORT @ ${price:.2f} (bar {bar_num}, {timestamp.strftime('%H:%M')})")
        print(f"     Shares: {shares} | Stop: ${stock['support']:.2f}")
        return position

    def manage_position(self, pos, price, timestamp, bar_num):
        """
        Manage open position per PS60 rules:
        - Take 50% profit on first move
        - Move stop to breakeven
        - Exit at target or stop
        - 5-7 minute rule
        """
        time_in_trade = (timestamp - pos['entry_time']).total_seconds() / 60

        if pos['side'] == 'LONG':
            gain = price - pos['entry_price']

            # Take 50% profit on first favorable move (0.25-0.75)
            if pos['remaining'] == 1.0 and gain >= 0.25:
                print(f"     💰 PARTIAL 50% @ ${price:.2f} (+${gain:.2f}, {timestamp.strftime('%H:%M')})")
                pos['remaining'] = 0.5
                pos['stop'] = pos['entry_price']  # Move to breakeven
                pos['partials'].append({'pct': 0.5, 'price': price, 'gain': gain})

            # Hit target1 - take another 25%
            elif pos['remaining'] > 0.25 and price >= pos['target1']:
                gain_t1 = price - pos['entry_price']
                print(f"     🎯 TARGET1 25% @ ${price:.2f} (+${gain_t1:.2f}, {timestamp.strftime('%H:%M')})")
                pos['remaining'] = 0.25
                pos['partials'].append({'pct': 0.25, 'price': price, 'gain': gain_t1})

            # Stop hit - exit remaining
            elif price <= pos['stop']:
                print(f"     🛑 STOP remaining @ ${price:.2f} ({timestamp.strftime('%H:%M')})")
                return None, self.close_position(pos, price, timestamp, 'STOP', bar_num)

            # 5-7 minute rule - no movement
            elif time_in_trade >= 7 and pos['remaining'] == 1.0 and gain < 0.10:
                print(f"     ⏱️  5-MIN RULE exit @ ${price:.2f} (no movement in 7 min)")
                return None, self.close_position(pos, price, timestamp, '5MIN_RULE', bar_num)

        else:  # SHORT
            gain = pos['entry_price'] - price

            # Take 50% profit on first favorable move
            if pos['remaining'] == 1.0 and gain >= 0.25:
                print(f"     💰 PARTIAL 50% @ ${price:.2f} (+${gain:.2f}, {timestamp.strftime('%H:%M')})")
                pos['remaining'] = 0.5
                pos['stop'] = pos['entry_price']  # Move to breakeven
                pos['partials'].append({'pct': 0.5, 'price': price, 'gain': gain})

            # Hit target1
            elif pos['remaining'] > 0.25 and price <= pos['target1']:
                gain_t1 = pos['entry_price'] - price
                print(f"     🎯 TARGET1 25% @ ${price:.2f} (+${gain_t1:.2f}, {timestamp.strftime('%H:%M')})")
                pos['remaining'] = 0.25
                pos['partials'].append({'pct': 0.25, 'price': price, 'gain': gain_t1})

            # Stop hit
            elif price >= pos['stop']:
                print(f"     🛑 STOP remaining @ ${price:.2f} ({timestamp.strftime('%H:%M')})")
                return None, self.close_position(pos, price, timestamp, 'STOP', bar_num)

            # 5-7 minute rule
            elif time_in_trade >= 7 and pos['remaining'] == 1.0 and gain < 0.10:
                print(f"     ⏱️  5-MIN RULE exit @ ${price:.2f}")
                return None, self.close_position(pos, price, timestamp, '5MIN_RULE', bar_num)

        return pos, None

    def calculate_position_size(self, entry, stop):
        """Calculate shares based on 1% risk"""
        risk_per_trade = self.account_size * 0.01
        stop_distance = abs(entry - stop)

        if stop_distance == 0:
            return 100  # Fallback

        shares = int(risk_per_trade / stop_distance)
        return min(max(shares, 10), 1000)  # Between 10-1000 shares

    def close_position(self, pos, exit_price, timestamp, reason, bar_num):
        """Close position and record trade"""
        # Calculate P&L including partials
        total_pnl = 0

        # P&L from partials
        for partial in pos['partials']:
            pnl_partial = partial['gain'] * pos['shares'] * partial['pct']
            total_pnl += pnl_partial

        # P&L from remaining position
        if pos['side'] == 'LONG':
            remaining_pnl_per_share = exit_price - pos['entry_price']
        else:
            remaining_pnl_per_share = pos['entry_price'] - exit_price

        remaining_pnl = remaining_pnl_per_share * pos['shares'] * pos['remaining']
        total_pnl += remaining_pnl

        # Overall P&L per share
        pnl_per_share = total_pnl / pos['shares']

        duration_min = (timestamp - pos['entry_time']).total_seconds() / 60

        trade = {
            'symbol': pos['symbol'],
            'side': pos['side'],
            'entry': pos['entry_price'],
            'exit': exit_price,
            'shares': pos['shares'],
            'pnl': total_pnl,
            'pnl_per_share': pnl_per_share,
            'pnl_pct': (pnl_per_share / pos['entry_price']) * 100,
            'entry_time': pos['entry_time'],
            'exit_time': timestamp,
            'duration_min': duration_min,
            'reason': reason,
            'partials': len(pos['partials']),
            'entry_bar': pos['entry_bar'],
            'exit_bar': bar_num
        }

        return trade

    def print_results(self):
        """Print backtest performance metrics"""
        print(f"\n{'='*80}")
        print(f"BACKTEST RESULTS")
        print(f"{'='*80}")

        if not self.trades:
            print("❌ No trades executed")
            return

        df = pd.DataFrame(self.trades)

        winners = df[df['pnl'] > 0]
        losers = df[df['pnl'] <= 0]

        print(f"\n📊 TRADE SUMMARY:")
        print(f"  Total trades: {len(df)}")
        print(f"  Winners: {len(winners)} ({len(winners)/len(df)*100:.1f}%)")
        print(f"  Losers: {len(losers)} ({len(losers)/len(df)*100:.1f}%)")

        print(f"\n💰 P&L ANALYSIS:")
        print(f"  Total P&L: ${df['pnl'].sum():.2f}")
        print(f"  Avg trade: ${df['pnl'].mean():.2f}")

        if len(winners) > 0:
            print(f"  Avg winner: ${winners['pnl'].mean():.2f}")
        if len(losers) > 0:
            print(f"  Avg loser: ${losers['pnl'].mean():.2f}")

        if len(winners) > 0 and len(losers) > 0:
            profit_factor = winners['pnl'].sum() / abs(losers['pnl'].sum())
            print(f"  Profit factor: {profit_factor:.2f}")

        print(f"\n⏱️  TRADE DURATION:")
        print(f"  Avg duration: {df['duration_min'].mean():.1f} minutes")

        print(f"\n🎯 EXIT REASONS:")
        for reason in df['reason'].unique():
            count = len(df[df['reason'] == reason])
            print(f"  {reason}: {count} trades")

        print(f"\n{'='*80}")
        print(f"DETAILED TRADE LOG:")
        print(f"{'='*80}")

        for idx, trade in df.iterrows():
            sign = '+' if trade['pnl'] > 0 else ''
            print(f"\n{idx+1}. {trade['symbol']} {trade['side']}")
            print(f"   Entry: ${trade['entry']:.2f} @ {trade['entry_time'].strftime('%H:%M')}")
            print(f"   Exit:  ${trade['exit']:.2f} @ {trade['exit_time'].strftime('%H:%M')} ({trade['reason']})")
            print(f"   P&L:   {sign}${trade['pnl']:.2f} ({sign}{trade['pnl_pct']:.2f}%) | Duration: {trade['duration_min']:.0f} min")
            print(f"   Partials: {trade['partials']}")


def main():
    parser = argparse.ArgumentParser(description='PS60 Backtester')
    parser.add_argument('--scanner', required=True, help='Path to scanner results JSON')
    parser.add_argument('--date', required=True, help='Test date (YYYY-MM-DD)')
    parser.add_argument('--account-size', type=float, default=100000, help='Account size for position sizing')

    args = parser.parse_args()

    # Parse date
    test_date = datetime.strptime(args.date, '%Y-%m-%d')

    # Run backtest
    backtester = PS60Backtester(args.scanner, test_date, args.account_size)
    backtester.run()


if __name__ == '__main__':
    main()
