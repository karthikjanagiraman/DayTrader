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

class PS60Trader:
    """Live trader implementing PS60 strategy with scanner-identified pivots"""

    def __init__(self, config_path='config/trader_config.yaml'):
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Setup logging
        self.setup_logging()

        # Initialize IBKR connection
        self.ib = IB()

        # Trading state
        self.watchlist = []
        self.positions = {}  # symbol -> position dict
        self.attempted_pivots = defaultdict(lambda: {'long': 0, 'short': 0})
        self.daily_pnl = 0.0
        self.trade_count = 0
        self.trades_today = []

        # Account info
        self.account_size = self.config['trading']['account_size']
        self.max_positions = self.config['trading']['max_positions']

        # Filters
        self.avoid_symbols = set(self.config['filters'].get('avoid_symbols', []))
        self.avoid_index_shorts = self.config['filters']['avoid_index_shorts']

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
        """Load today's scanner results"""
        scanner_dir = Path(self.config['scanner']['output_dir'])
        scanner_file = self.config['scanner']['results_file']
        scanner_path = scanner_dir / scanner_file

        try:
            with open(scanner_path, 'r') as f:
                all_results = json.load(f)

            # Filter based on configuration
            min_score = self.config['filters']['min_score']
            min_rr = self.config['filters']['min_risk_reward']

            self.watchlist = [
                stock for stock in all_results
                if stock['score'] >= min_score
                and stock['risk_reward'] >= min_rr
                and stock['symbol'] not in self.avoid_symbols
            ]

            self.logger.info(f"✓ Loaded {len(self.watchlist)} setups from scanner")
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
        import pytz
        # Get current time in Eastern Time (market timezone)
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)
        now = now_et.time()

        # Market hours: 9:30 AM - 4:00 PM ET
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)

        # Entry window
        min_entry = datetime.strptime(
            self.config['trading']['entry']['min_entry_time'], '%H:%M'
        ).time()
        max_entry = datetime.strptime(
            self.config['trading']['entry']['max_entry_time'], '%H:%M'
        ).time()

        in_market_hours = market_open <= now <= market_close
        in_entry_window = min_entry <= now <= max_entry

        return in_market_hours, in_entry_window

    def check_pivot_break(self, stock_data, current_price):
        """Check if current price breaks pivot levels"""
        symbol = stock_data['symbol']
        resistance = stock_data['resistance']
        support = stock_data['support']

        max_attempts = self.config['trading']['attempts']['max_attempts_per_pivot']

        # Check long pivot break
        if current_price > resistance:
            if self.attempted_pivots[symbol]['long'] < max_attempts:
                return 'LONG', resistance

        # Check short pivot break
        elif current_price < support:
            # Skip if avoiding index shorts
            if self.avoid_index_shorts and symbol in ['SPY', 'QQQ', 'DIA', 'IWM']:
                self.logger.debug(f"Skipping {symbol} SHORT (index short filter)")
                return None, None

            if self.attempted_pivots[symbol]['short'] < max_attempts:
                return 'SHORT', support

        return None, None

    def calculate_position_size(self, entry_price, stop_price):
        """Calculate position size based on 1% risk"""
        risk_per_trade = self.account_size * self.config['trading']['risk_per_trade']
        stop_distance = abs(entry_price - stop_price)

        if stop_distance == 0:
            return self.config['trading']['position_sizing']['min_shares']

        shares = int(risk_per_trade / stop_distance)

        # Apply min/max constraints
        min_shares = self.config['trading']['position_sizing']['min_shares']
        max_shares = self.config['trading']['position_sizing']['max_shares']

        shares = max(min_shares, min(shares, max_shares))

        return shares

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

        # Create position record
        position = {
            'symbol': symbol,
            'side': 'LONG',
            'entry_price': fill_price,
            'entry_time': datetime.now(),
            'shares': shares,
            'stop': resistance,
            'target1': stock_data['target1'],
            'target2': stock_data['target2'],
            'remaining': 1.0,  # 100%
            'partials': [],
            'contract': contract
        }

        self.positions[symbol] = position
        self.attempted_pivots[symbol]['long'] += 1
        self.trade_count += 1

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

        # Create position record
        position = {
            'symbol': symbol,
            'side': 'SHORT',
            'entry_price': fill_price,
            'entry_time': datetime.now(),
            'shares': shares,
            'stop': support,
            'target1': stock_data.get('downside1', support * 0.98),
            'target2': stock_data.get('downside2', support * 0.96),
            'remaining': 1.0,
            'partials': [],
            'contract': contract
        }

        self.positions[symbol] = position
        self.attempted_pivots[symbol]['short'] += 1
        self.trade_count += 1

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

            # Check time in trade
            time_in_trade = (datetime.now() - position['entry_time']).total_seconds() / 60

            if position['side'] == 'LONG':
                gain = current_price - position['entry_price']

                # Take 50% partial on first move
                if position['remaining'] == 1.0 and gain >= 0.25:
                    self.take_partial(position, current_price, 0.50, 'FIRST_MOVE')
                    # Move stop to breakeven
                    position['stop'] = position['entry_price']

                # Hit target1
                elif position['remaining'] > 0.25 and current_price >= position['target1']:
                    self.take_partial(position, current_price, 0.25, 'TARGET1')

                # 5-7 minute rule
                elif time_in_trade >= 7 and position['remaining'] == 1.0 and gain < 0.10:
                    self.logger.info(f"  ⏱️  5-MIN RULE: Exiting {symbol}")
                    self.close_position(position, current_price, '5MIN_RULE')

            else:  # SHORT
                gain = position['entry_price'] - current_price

                # Similar logic for shorts
                if position['remaining'] == 1.0 and gain >= 0.25:
                    self.take_partial(position, current_price, 0.50, 'FIRST_MOVE')
                    position['stop'] = position['entry_price']

                elif position['remaining'] > 0.25 and current_price <= position['target1']:
                    self.take_partial(position, current_price, 0.25, 'TARGET1')

                elif time_in_trade >= 7 and position['remaining'] == 1.0 and gain < 0.10:
                    self.logger.info(f"  ⏱️  5-MIN RULE: Exiting {symbol}")
                    self.close_position(position, current_price, '5MIN_RULE')

    def take_partial(self, position, price, pct, reason):
        """Take partial profit"""
        symbol = position['symbol']
        shares_to_sell = int(position['shares'] * pct)

        if position['side'] == 'LONG':
            action = 'SELL'
            gain = price - position['entry_price']
        else:
            action = 'BUY'
            gain = position['entry_price'] - price

        # Place market order for partial
        order = MarketOrder(action, shares_to_sell)
        trade = self.ib.placeOrder(position['contract'], order)

        position['remaining'] -= pct
        position['partials'].append({
            'pct': pct,
            'price': price,
            'gain': gain,
            'reason': reason,
            'time': datetime.now()
        })

        self.logger.info(f"  💰 PARTIAL {int(pct*100)}% {symbol} @ ${price:.2f} "
                        f"(+${gain:.2f}, {reason})")

    def close_position(self, position, price, reason):
        """Close entire position"""
        symbol = position['symbol']
        shares = int(position['shares'] * position['remaining'])

        if shares == 0:
            del self.positions[symbol]
            return

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Place market order
        order = MarketOrder(action, shares)
        trade = self.ib.placeOrder(position['contract'], order)

        # Calculate P&L
        pnl = self.calculate_pnl(position, price)

        self.logger.info(f"  🛑 CLOSE {symbol} @ ${price:.2f} ({reason})")
        self.logger.info(f"     P&L: ${pnl:.2f}")

        # Record trade
        self.record_trade(position, price, reason, pnl)

        # Remove position
        del self.positions[symbol]

    def calculate_pnl(self, position, exit_price):
        """Calculate total P&L including partials"""
        total_pnl = 0

        # P&L from partials
        for partial in position['partials']:
            pnl_partial = partial['gain'] * position['shares'] * partial['pct']
            total_pnl += pnl_partial

        # P&L from remaining
        if position['side'] == 'LONG':
            remaining_pnl = (exit_price - position['entry_price']) * position['shares'] * position['remaining']
        else:
            remaining_pnl = (position['entry_price'] - exit_price) * position['shares'] * position['remaining']

        total_pnl += remaining_pnl

        return total_pnl

    def record_trade(self, position, exit_price, reason, pnl):
        """Record completed trade"""
        trade_record = {
            'symbol': position['symbol'],
            'side': position['side'],
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'shares': position['shares'],
            'pnl': pnl,
            'entry_time': position['entry_time'].isoformat(),
            'exit_time': datetime.now().isoformat(),
            'reason': reason,
            'partials': len(position['partials'])
        }

        self.trades_today.append(trade_record)
        self.daily_pnl += pnl

    def close_all_positions(self, reason='EOD'):
        """Close all open positions"""
        self.logger.info(f"Closing all positions ({reason})...")

        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            stock_data = next((s for s in self.watchlist if s['symbol'] == symbol), None)

            if stock_data and stock_data['ticker'].last:
                current_price = float(stock_data['ticker'].last)
                self.close_position(position, current_price, reason)

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

                # Check for EOD close
                import pytz
                eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(pytz.UTC).astimezone(eastern)
                now = now_et.time()
                eod_time = datetime.strptime(
                    self.config['trading']['exits']['eod_close_time'], '%H:%M'
                ).time()

                if now >= eod_time:
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
        self.logger.info("\n" + "="*80)
        self.logger.info("DAILY SUMMARY")
        self.logger.info("="*80)

        self.logger.info(f"Total Trades: {len(self.trades_today)}")
        self.logger.info(f"Daily P&L: ${self.daily_pnl:.2f}")

        if self.trades_today:
            winners = [t for t in self.trades_today if t['pnl'] > 0]
            losers = [t for t in self.trades_today if t['pnl'] <= 0]

            self.logger.info(f"Winners: {len(winners)} ({len(winners)/len(self.trades_today)*100:.1f}%)")
            self.logger.info(f"Losers: {len(losers)}")

            if winners:
                avg_winner = sum(t['pnl'] for t in winners) / len(winners)
                self.logger.info(f"Avg Winner: ${avg_winner:.2f}")

            if losers:
                avg_loser = sum(t['pnl'] for t in losers) / len(losers)
                self.logger.info(f"Avg Loser: ${avg_loser:.2f}")

        # Save trades to file
        if self.trades_today:
            log_dir = Path(self.config['logging']['log_dir'])
            trade_file = log_dir / f'trades_{datetime.now().strftime("%Y%m%d")}.json'

            with open(trade_file, 'w') as f:
                json.dump(self.trades_today, f, indent=2)

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
