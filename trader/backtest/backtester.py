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
import yaml

# Import shared strategy module
sys.path.append(str(Path(__file__).parent.parent))
from strategy import PS60Strategy, PositionManager

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

        # Load config and initialize strategy module
        config_path = Path(__file__).parent.parent / 'config' / 'trader_config.yaml'
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Initialize strategy and position manager
        self.strategy = PS60Strategy(self.config)
        self.pm = PositionManager()

        # Track trades for backtest results
        self.trades = []

        # Slippage simulation (realistic execution costs)
        self.entry_slippage = 0.0005  # 0.05% slippage on entries
        self.stop_slippage = 0.002    # 0.2% slippage on stops (worse execution)
        self.exit_slippage = 0.0005   # 0.05% slippage on normal exits

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
        # Detect market trend first
        self.market_trend = self.detect_market_trend()

        # Filter scanner using strategy module
        watchlist = self.strategy.filter_scanner_results(self.scanner_results)

        print(f"\n{'='*80}")
        print(f"MARKET TREND: {self.market_trend}")
        print(f"WATCHLIST: {len(watchlist)} tradeable setups (using strategy filters)")
        print(f"{'='*80}")

        for stock in watchlist:
            print(f"\n[{stock['symbol']}] Testing setup...")
            print(f"  Resistance: ${stock['resistance']:.2f} | Support: ${stock['support']:.2f}")
            print(f"  Score: {stock['score']} | R/R: {stock['risk_reward']:.2f}:1")

            self.backtest_stock(stock)

    def detect_market_trend(self):
        """
        Detect overall market trend using SPY
        Returns: 'BULLISH', 'BEARISH', or 'NEUTRAL'
        """
        try:
            from ib_insync import Stock
            spy = Stock('SPY', 'SMART', 'USD')

            # Get SPY bars for the day
            end_datetime = f'{self.test_date.strftime("%Y%m%d")} 16:00:00'
            bars = self.ib.reqHistoricalData(
                spy,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                return 'NEUTRAL'

            # Calculate % change from open to close
            day_bar = bars[-1]
            change_pct = ((day_bar.close - day_bar.open) / day_bar.open) * 100

            if change_pct > 0.5:
                return 'BULLISH'
            elif change_pct < -0.5:
                return 'BEARISH'
            else:
                return 'NEUTRAL'

        except Exception as e:
            print(f"  ⚠️  Could not detect market trend: {e}")
            return 'NEUTRAL'

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

        # Track last exit for re-entry confirmation
        last_exit_bar = None
        last_exit_side = None

        # Simulate tick-by-tick monitoring
        for bar in bars:
            bar_count += 1
            timestamp = bar.date
            price = bar.close

            # Check if within entry time window using strategy module
            within_entry_window = self.strategy.is_within_entry_window(timestamp)

            # Entry logic - check for pivot breaks (MAX 2 ATTEMPTS)
            if position is None and within_entry_window:
                # Long entry - only if we haven't exceeded max attempts
                if long_attempts < max_attempts and price > resistance:
                    # Check if this is counter-trend (long on bearish day)
                    counter_trend = (self.market_trend == 'BEARISH')

                    # Require stronger confirmation for counter-trend
                    if counter_trend:
                        # Counter-trend LONG: require 0.5% above resistance + high score
                        if price > resistance * 1.005 and stock['score'] >= 85:
                            position = self.enter_long(stock, price, timestamp, bar_count)
                            long_attempts += 1
                    else:
                        # Normal LONG entry
                        position = self.enter_long(stock, price, timestamp, bar_count)
                        long_attempts += 1

                # Short entry - only if we haven't exceeded max attempts
                elif short_attempts < max_attempts and price < support:
                    # Check if this is counter-trend (short on bullish day)
                    counter_trend = (self.market_trend == 'BULLISH')

                    # Require stronger confirmation for counter-trend
                    if counter_trend:
                        # Counter-trend SHORT: require 0.5% below support + high score
                        if price < support * 0.995 and stock['score'] >= 85:
                            position = self.enter_short(stock, price, timestamp, bar_count)
                            short_attempts += 1
                    else:
                        # Normal SHORT entry
                        position = self.enter_short(stock, price, timestamp, bar_count)
                        short_attempts += 1

            # Exit logic - manage open position
            elif position is not None:
                position, closed_trade = self.manage_position(
                    position, price, timestamp, bar_count
                )
                if closed_trade:
                    self.trades.append(closed_trade)
                    # Track exit for re-entry logic
                    last_exit_bar = bar_count
                    last_exit_side = closed_trade['side']
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
        # Apply entry slippage (buy at slightly worse price)
        entry_price = price * (1 + self.entry_slippage)

        # Use original tight stop (resistance level)
        stop_price = stock['resistance']

        shares = self.calculate_position_size(entry_price, stop_price)

        # Create position using position manager
        position = self.pm.create_position(
            symbol=stock['symbol'],
            side='LONG',
            entry_price=entry_price,
            shares=shares,
            pivot=stock['resistance'],
            target1=stock['target1'],
            target2=stock['target2'],
            entry_time=timestamp,
            entry_bar=bar_num
        )

        print(f"  🟢 LONG @ ${entry_price:.2f} (bar {bar_num}, {timestamp.strftime('%H:%M')})")
        print(f"     Shares: {shares} | Stop: ${stop_price:.2f}")
        return position

    def enter_short(self, stock, price, timestamp, bar_num):
        """Enter short position"""
        # Apply entry slippage (sell at slightly worse price)
        entry_price = price * (1 - self.entry_slippage)

        # Use original tight stop (support level)
        stop_price = stock['support']

        shares = self.calculate_position_size(stop_price, entry_price)

        # Create position using position manager
        position = self.pm.create_position(
            symbol=stock['symbol'],
            side='SHORT',
            entry_price=entry_price,
            shares=shares,
            pivot=stock['support'],
            target1=stock.get('downside1', stock['support'] * 0.98),
            target2=stock.get('downside2', stock['support'] * 0.96),
            entry_time=timestamp,
            entry_bar=bar_num
        )

        print(f"  🔴 SHORT @ ${entry_price:.2f} (bar {bar_num}, {timestamp.strftime('%H:%M')})")
        print(f"     Shares: {shares} | Stop: ${stop_price:.2f}")
        return position

    def manage_position(self, pos, price, timestamp, bar_num):
        """
        Manage open position per PS60 rules using strategy module:
        - Take 50% profit on first move
        - Move stop to breakeven
        - Exit at target or stop
        - 5-7 minute rule (FIXED - checks if stuck at pivot)
        """
        # Check 5-7 minute rule using strategy module (FIXED)
        should_exit, reason = self.strategy.check_five_minute_rule(pos, price, timestamp)
        if should_exit:
            print(f"     ⏱️  {reason} exit @ ${price:.2f} ({timestamp.strftime('%H:%M')})")
            return None, self.close_position(pos, price, timestamp, reason, bar_num)

        # Check for partial profit using strategy module
        should_partial, pct, reason = self.strategy.should_take_partial(pos, price)
        if should_partial:
            # Record partial using position manager
            partial_record = self.pm.take_partial(pos['symbol'], price, pct, reason)
            print(f"     💰 PARTIAL {int(pct*100)}% @ ${price:.2f} "
                  f"(+${partial_record['gain']:.2f}, {timestamp.strftime('%H:%M')})")

            # Move stop to breakeven if configured
            if self.strategy.should_move_stop_to_breakeven(pos):
                pos['stop'] = pos['entry_price']

        # Check stops
        if pos['side'] == 'LONG':
            # Stop hit - exit remaining (with slippage)
            if price <= pos['stop']:
                # Apply stop slippage (sell at worse price for longs)
                stop_exit_price = price * (1 - self.stop_slippage)
                print(f"     🛑 STOP remaining @ ${stop_exit_price:.2f} ({timestamp.strftime('%H:%M')})")
                return None, self.close_position(pos, stop_exit_price, timestamp, 'STOP', bar_num)

        else:  # SHORT
            # Stop hit (with slippage)
            if price >= pos['stop']:
                # Apply stop slippage (buy back at worse price for shorts)
                stop_exit_price = price * (1 + self.stop_slippage)
                print(f"     🛑 STOP remaining @ ${stop_exit_price:.2f} ({timestamp.strftime('%H:%M')})")
                return None, self.close_position(pos, stop_exit_price, timestamp, 'STOP', bar_num)

        return pos, None

    def calculate_position_size(self, entry, stop):
        """
        Calculate shares - CONSERVATIVE FIXED SIZING

        Note: While live trader uses 1% risk-based sizing, backtester uses
        fixed 1000 shares for consistency and to avoid over-concentration
        on tight-stop trades. Real trading will vary position sizes.
        """
        return 1000  # Fixed conservative position size

    def close_position(self, pos, exit_price, timestamp, reason, bar_num):
        """Close position and record trade using position manager"""
        # Close position using position manager
        trade_record = self.pm.close_position(pos['symbol'], exit_price, reason)

        # Add backtester-specific fields
        duration_min = (timestamp - pos['entry_time']).total_seconds() / 60
        pnl_per_share = trade_record['pnl'] / pos['shares']

        trade = {
            **trade_record,  # Include all PM fields (symbol, side, entry, exit, pnl, etc.)
            'pnl_per_share': pnl_per_share,
            'pnl_pct': (pnl_per_share / pos['entry_price']) * 100,
            'duration_min': duration_min,
            'entry_bar': pos.get('entry_bar', 0),
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
            print(f"   Entry: ${trade['entry_price']:.2f} @ {trade['entry_time'].strftime('%H:%M')}")
            print(f"   Exit:  ${trade['exit_price']:.2f} @ {trade['exit_time'].strftime('%H:%M')} ({trade['reason']})")
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
