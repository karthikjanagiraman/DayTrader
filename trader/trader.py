#!/usr/bin/env python3
"""
PS60 Live Trader - Paper Trading Implementation
Executes trades based on scanner-identified pivots using IBKR Paper Trading API

Based on backtest results:
- Max 2 attempts per pivot
- Min R/R 2.0
- No trading after 3:00 PM
- 50% partial profits
- Tight stops at pivot
"""

from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder, util
from datetime import datetime, time as dt_time
import json
import yaml
import argparse
import logging
from pathlib import Path
from collections import defaultdict
import time as time_module
import pytz

# Import shared strategy module
from strategy import PS60Strategy, PositionManager

class PS60Trader:
    """Live trader implementing PS60 strategy with scanner-identified pivots"""

    def __init__(self, config_path='config/trader_config.yaml'):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        self.setup_logging()

        # Initialize strategy and position manager
        self.strategy = PS60Strategy(self.config)
        self.pm = PositionManager()

        # Initialize IBKR connection
        self.ib = IB()

        # Trading state
        self.watchlist = []
        self.positions = {}  # Local dict for IBKR-specific data (contracts, stop orders)

        # Account info
        self.account_size = self.config['trading']['account_size']
        self.max_positions = self.config['trading']['max_positions']

        self.logger.info("PS60 Trader initialized")
        self.logger.info(f"Paper Trading: {self.config['paper_trading']}")
        self.logger.info(f"Account Size: ${self.account_size:,.0f}")

    def setup_logging(self):
        """Setup logging configuration"""
        log_dir = Path(self.config['logging']['log_dir'])
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d')
        log_file = log_dir / f'trader_{timestamp}.log'

        logging.basicConfig(
            level=getattr(logging, self.config['logging']['log_level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('PS60Trader')

    def connect(self):
        """Connect to IBKR"""
        host = self.config['ibkr']['host']
        port = self.config['ibkr']['port']
        client_id = self.config['ibkr']['client_id']

        try:
            self.ib.connect(host, port, clientId=client_id)
            self.logger.info(f"✓ Connected to IBKR (Paper: Port {port}, Client ID: {client_id})")
            return True
        except Exception as e:
            self.logger.error(f"✗ Failed to connect to IBKR: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.logger.info("✓ Disconnected from IBKR")

    def load_scanner_results(self):
        """Load today's scanner results (auto-detects correct date file)"""
        scanner_dir = Path(self.config['scanner']['output_dir'])

        # Find today's scanner results file
        today = datetime.now().strftime('%Y%m%d')
        scanner_file = f"scanner_results_{today}.json"
        scanner_path = scanner_dir / scanner_file

        try:
            with open(scanner_path, 'r') as f:
                all_results = json.load(f)

            # Filter using strategy module
            self.watchlist = self.strategy.filter_scanner_results(all_results)

            self.logger.info(f"✓ Loaded {len(self.watchlist)} setups from {scanner_file}")
            self.logger.info(f"  Filtered from {len(all_results)} total results")

            # Log watchlist
            for stock in self.watchlist:
                self.logger.info(f"  [{stock['symbol']}] Score: {stock['score']}, "
                               f"R/R: {stock['risk_reward']:.2f}, "
                               f"Resistance: ${stock['resistance']:.2f}, "
                               f"Support: ${stock['support']:.2f}")

            return True

        except FileNotFoundError:
            self.logger.error(f"✗ Scanner results not found: {scanner_path}")
            self.logger.error(f"  Expected file: {scanner_file}")
            self.logger.error(f"  Please run the scanner first: cd ../stockscanner && python scanner.py")
            return False
        except Exception as e:
            self.logger.error(f"✗ Error loading scanner results: {e}")
            return False

    def subscribe_market_data(self):
        """Subscribe to real-time market data for watchlist"""
        self.logger.info("Subscribing to market data...")

        for stock_data in self.watchlist:
            symbol = stock_data['symbol']
            contract = Stock(symbol, 'SMART', 'USD')

            # Qualify contract
            self.ib.qualifyContracts(contract)

            # Subscribe to market data
            ticker = self.ib.reqMktData(contract, '', False, False)

            # Store ticker reference
            stock_data['contract'] = contract
            stock_data['ticker'] = ticker

            self.logger.debug(f"  Subscribed: {symbol}")

        self.logger.info(f"✓ Subscribed to {len(self.watchlist)} symbols")

    def is_trading_hours(self):
        """Check if within trading hours"""
        # Get current time in Eastern Time (market timezone)
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)
        now = now_et.time()

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)

        in_market_hours = market_open <= now <= market_close

        # Use strategy module for entry window check
        in_entry_window = self.strategy.is_within_entry_window(now_et)

        return in_market_hours, in_entry_window

    def check_pivot_break(self, stock_data, current_price):
        """Check if current price breaks pivot levels"""
        symbol = stock_data['symbol']
        resistance = stock_data['resistance']
        support = stock_data['support']

        # Get attempt count from position manager
        long_attempts = self.pm.get_attempt_count(symbol, resistance)
        short_attempts = self.pm.get_attempt_count(symbol, support)

        # Check long pivot break using strategy module
        should_long, reason = self.strategy.should_enter_long(
            stock_data, current_price, long_attempts
        )
        if should_long:
            return 'LONG', resistance

        # Check short pivot break using strategy module
        should_short, reason = self.strategy.should_enter_short(
            stock_data, current_price, short_attempts
        )
        if should_short:
            return 'SHORT', support

        return None, None

    def calculate_position_size(self, entry_price, stop_price):
        """Calculate position size based on 1% risk"""
        return self.strategy.calculate_position_size(
            self.account_size,
            entry_price,
            stop_price
        )

    def enter_long(self, stock_data, current_price):
        """Enter long position"""
        symbol = stock_data['symbol']
        resistance = stock_data['resistance']
        contract = stock_data['contract']

        # Calculate position size
        shares = self.calculate_position_size(current_price, resistance)

        # Create market order
        order = MarketOrder('BUY', shares)

        # Place order
        trade = self.ib.placeOrder(contract, order)

        # Wait for fill
        self.ib.sleep(1)

        # Get fill price
        fill_price = current_price  # Approximate for now
        if trade.orderStatus.filled > 0:
            fill_price = trade.orderStatus.avgFillPrice

        # Create position using position manager
        position = self.pm.create_position(
            symbol=symbol,
            side='LONG',
            entry_price=fill_price,
            shares=shares,
            pivot=resistance,
            contract=contract,
            target1=stock_data['target1'],
            target2=stock_data['target2']
        )

        # Add to local positions dict
        self.positions[symbol] = position

        self.logger.info(f"🟢 LONG {symbol} @ ${fill_price:.2f}")
        self.logger.info(f"   Shares: {shares} | Stop: ${resistance:.2f} | "
                        f"Target1: ${stock_data['target1']:.2f}")

        # Place stop order
        self.place_stop_order(position)

        return position

    def enter_short(self, stock_data, current_price):
        """Enter short position"""
        symbol = stock_data['symbol']
        support = stock_data['support']
        contract = stock_data['contract']

        # Calculate position size
        shares = self.calculate_position_size(support, current_price)

        # Create market order
        order = MarketOrder('SELL', shares)

        # Place order
        trade = self.ib.placeOrder(contract, order)

        # Wait for fill
        self.ib.sleep(1)

        # Get fill price
        fill_price = current_price
        if trade.orderStatus.filled > 0:
            fill_price = trade.orderStatus.avgFillPrice

        # Create position using position manager
        position = self.pm.create_position(
            symbol=symbol,
            side='SHORT',
            entry_price=fill_price,
            shares=shares,
            pivot=support,
            contract=contract,
            target1=stock_data.get('downside1', support * 0.98),
            target2=stock_data.get('downside2', support * 0.96)
        )

        # Add to local positions dict
        self.positions[symbol] = position

        self.logger.info(f"🔴 SHORT {symbol} @ ${fill_price:.2f}")
        self.logger.info(f"   Shares: {shares} | Stop: ${support:.2f}")

        # Place stop order
        self.place_stop_order(position)

        return position

    def place_stop_order(self, position):
        """Place stop loss order"""
        symbol = position['symbol']
        contract = position['contract']
        stop_price = position['stop']
        shares = int(position['shares'] * position['remaining'])

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        stop_order = StopOrder(action, shares, stop_price)
        trade = self.ib.placeOrder(contract, stop_order)

        position['stop_order'] = trade

        self.logger.debug(f"  Stop order placed: {action} {shares} @ ${stop_price:.2f}")

    def manage_positions(self):
        """Manage open positions - check for partials, stops, targets"""
        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]

            # Get current price
            stock_data = next((s for s in self.watchlist if s['symbol'] == symbol), None)
            if not stock_data or not stock_data['ticker'].last:
                continue

            current_price = float(stock_data['ticker'].last)

            # Get current time in Eastern
            eastern = pytz.timezone('US/Eastern')
            current_time = datetime.now(pytz.UTC).astimezone(eastern)

            # Check 5-7 minute rule (FIXED - checks if stuck at pivot)
            should_exit, reason = self.strategy.check_five_minute_rule(
                position, current_price, current_time
            )
            if should_exit:
                self.logger.info(f"  ⏱️  {reason}: Exiting {symbol}")
                self.close_position(position, current_price, reason)
                continue

            # Check for partial profit
            should_partial, pct, reason = self.strategy.should_take_partial(
                position, current_price
            )
            if should_partial:
                self.take_partial(position, current_price, pct, reason)

                # Move stop to breakeven after partial (if configured)
                if self.strategy.should_move_stop_to_breakeven(position):
                    old_stop = position['stop']
                    position['stop'] = position['entry_price']
                    self.logger.info(f"  🛡️  {symbol}: Stop moved to breakeven ${position['stop']:.2f}")

    def take_partial(self, position, price, pct, reason):
        """Take partial profit"""
        symbol = position['symbol']
        shares_to_sell = int(position['shares'] * pct)

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Place market order for partial
        order = MarketOrder(action, shares_to_sell)
        trade = self.ib.placeOrder(position['contract'], order)

        # Record partial using position manager
        partial_record = self.pm.take_partial(symbol, price, pct, reason)

        self.logger.info(f"  💰 PARTIAL {int(pct*100)}% {symbol} @ ${price:.2f} "
                        f"(+${partial_record['gain']:.2f}, {reason})")

    def close_position(self, position, price, reason):
        """Close entire position and return trade object"""
        symbol = position['symbol']
        shares = int(position['shares'] * position['remaining'])

        if shares == 0:
            del self.positions[symbol]
            return None

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Place market order
        order = MarketOrder(action, shares)
        trade = self.ib.placeOrder(position['contract'], order)

        # Close position and record trade using position manager
        trade_record = self.pm.close_position(symbol, price, reason)

        self.logger.info(f"  🛑 CLOSE {symbol} @ ${price:.2f} ({reason})")
        self.logger.info(f"     P&L: ${trade_record['pnl']:.2f}")

        # Remove from local positions dict
        del self.positions[symbol]

        return trade

    def close_all_positions(self, reason='EOD'):
        """Close all open positions and wait for fills"""
        self.logger.info(f"Closing all positions ({reason})...")

        # Collect all trades placed
        trades_to_monitor = []

        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            stock_data = next((s for s in self.watchlist if s['symbol'] == symbol), None)

            if stock_data and stock_data['ticker'].last:
                current_price = float(stock_data['ticker'].last)
                trade = self.close_position(position, current_price, reason)
                if trade:
                    trades_to_monitor.append(trade)

        # Wait for all orders to fill (max 30 seconds)
        if trades_to_monitor:
            self.logger.info(f"Waiting for {len(trades_to_monitor)} orders to fill...")
            max_wait = 30
            start_time = time_module.time()

            while time_module.time() - start_time < max_wait:
                all_filled = all(
                    trade.orderStatus.status in ['Filled', 'Cancelled']
                    for trade in trades_to_monitor
                )

                if all_filled:
                    filled_count = sum(1 for t in trades_to_monitor if t.orderStatus.status == 'Filled')
                    self.logger.info(f"All orders completed: {filled_count}/{len(trades_to_monitor)} filled")
                    break

                self.ib.sleep(0.5)

            # Log any unfilled orders
            for trade in trades_to_monitor:
                if trade.orderStatus.status not in ['Filled', 'Cancelled']:
                    self.logger.warning(
                        f"Order {trade.order.orderId} for {trade.contract.symbol} "
                        f"not filled (status: {trade.orderStatus.status})"
                    )

    def run(self):
        """Main trading loop"""
        self.logger.info("="*80)
        self.logger.info("PS60 LIVE TRADER - PAPER TRADING SESSION")
        self.logger.info("="*80)

        # Connect to IBKR
        if not self.connect():
            return

        # Load scanner results
        if not self.load_scanner_results():
            self.disconnect()
            return

        # Subscribe to market data
        self.subscribe_market_data()

        self.logger.info("\n" + "="*80)
        self.logger.info("MONITORING STARTED")
        self.logger.info("="*80)

        try:
            while True:
                # Check if within trading hours
                in_market, in_entry = self.is_trading_hours()

                if not in_market:
                    self.logger.info("Market closed. Exiting...")
                    break

                # Check for EOD close using strategy module
                import pytz
                eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(pytz.UTC).astimezone(eastern)

                if self.strategy.is_near_eod(now_et):
                    self.close_all_positions('EOD')
                    break

                # Update all tickers
                self.ib.sleep(0.1)

                # Check for new entry signals (if in entry window)
                if in_entry and len(self.positions) < self.max_positions:
                    for stock_data in self.watchlist:
                        symbol = stock_data['symbol']

                        # Skip if already in position
                        if symbol in self.positions:
                            continue

                        # Get current price
                        if not stock_data['ticker'].last:
                            continue

                        current_price = float(stock_data['ticker'].last)

                        # Check for pivot break
                        direction, pivot = self.check_pivot_break(stock_data, current_price)

                        if direction == 'LONG':
                            self.enter_long(stock_data, current_price)
                        elif direction == 'SHORT':
                            self.enter_short(stock_data, current_price)

                # Manage existing positions
                self.manage_positions()

                # Small delay
                time_module.sleep(1)

        except KeyboardInterrupt:
            self.logger.info("\n\nTrading interrupted by user")
            self.close_all_positions('USER_INTERRUPT')

        except Exception as e:
            self.logger.error(f"Error in trading loop: {e}", exc_info=True)
            self.close_all_positions('ERROR')

        finally:
            # Print daily summary
            self.print_daily_summary()

            # Disconnect
            self.disconnect()

    def print_daily_summary(self):
        """Print end-of-day summary"""
        # Get summary from position manager
        summary = self.pm.get_daily_summary()

        self.logger.info("\n" + "="*80)
        self.logger.info("DAILY SUMMARY")
        self.logger.info("="*80)

        self.logger.info(f"Total Trades: {summary['total_trades']}")
        self.logger.info(f"Daily P&L: ${summary['daily_pnl']:.2f}")

        if summary['total_trades'] > 0:
            self.logger.info(f"Winners: {summary['winners']} ({summary['win_rate']:.1f}%)")
            self.logger.info(f"Losers: {summary['losers']}")

            if summary['avg_winner']:
                self.logger.info(f"Avg Winner: ${summary['avg_winner']:.2f}")

            if summary['avg_loser']:
                self.logger.info(f"Avg Loser: ${summary['avg_loser']:.2f}")

        # Save trades to file
        if summary['trades']:
            log_dir = Path(self.config['logging']['log_dir'])
            trade_file = log_dir / f'trades_{datetime.now().strftime("%Y%m%d")}.json'

            with open(trade_file, 'w') as f:
                json.dump(summary['trades'], f, indent=2)

            self.logger.info(f"\nTrades saved to: {trade_file}")


def main():
    parser = argparse.ArgumentParser(description='PS60 Live Trader')
    parser.add_argument('--config', default='config/trader_config.yaml',
                       help='Path to configuration file')

    args = parser.parse_args()

    trader = PS60Trader(args.config)
    trader.run()


if __name__ == '__main__':
    main()
