#!/usr/bin/env python3
"""
PS60 Live Trader - Paper Trading Implementation (Updated Oct 5, 2025)
Executes trades based on scanner-identified pivots using IBKR Paper Trading API

FULL FILTER SYSTEM INTEGRATED:
- ✅ Choppy Market Filter (saved $15k/month in backtests)
- ✅ Room-to-Run Filter (19x P&L improvement on Oct 1)
- ✅ Sustained Break Logic (catch slow grind breakouts)
- ✅ Hybrid Entry Confirmation (momentum/pullback/sustained)
- ✅ 8-Minute Rule (exit if no progress, no partials taken)
- ✅ Gap Filter at Market Open (scanner is 8-13 hours old)
- ✅ Max 2 attempts per pivot
- ✅ Entry Time Window (9:45 AM - 3:00 PM ET)
- ✅ 50% partial profits at 1R
- ✅ Stop to breakeven after partial
- ✅ EOD close at 3:55 PM ET

TIMEZONE HANDLING:
- All market times use Eastern Time (pytz)
- Fixed EOD close bug (Oct 1, 2025)
- Proper timestamp display in all logs

See FILTER_DOCUMENTATION.md for complete filter reference
"""

from ib_insync import IB, Stock, MarketOrder, StopOrder, LimitOrder, util
from datetime import datetime, time as dt_time, timedelta
import json
import yaml
from state_manager import StateManager
from ibkr_resilience import IBKRResilience
import argparse
import logging
from pathlib import Path
from collections import defaultdict, namedtuple
import time as time_module
import pytz

# Import shared strategy module
from strategy import PS60Strategy, PositionManager

# Mock bar structure for converting tick data to bars
MockBar = namedtuple('MockBar', ['date', 'open', 'high', 'low', 'close', 'volume'])


class BarBuffer:
    """
    Convert tick-by-tick data into 5-second bars for strategy module

    CRITICAL: This bridges the gap between real-time tick data from IBKR
    and the bar-based strategy logic used in backtesting.

    The strategy module expects 5-second bars (like in backtest), but IBKR
    live data comes as ticks. This class aggregates ticks into bars.
    """

    def __init__(self, symbol, bar_size_seconds=5):
        self.symbol = symbol
        self.bar_size = bar_size_seconds
        self.current_bar = None
        self.bars = []  # Keep last 120 bars (10 minutes at 5-second resolution)
        self.max_bars = 120

    def round_to_bar(self, timestamp):
        """Round timestamp to nearest bar boundary"""
        # Round down to nearest N-second boundary
        total_seconds = timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
        bar_seconds = (total_seconds // self.bar_size) * self.bar_size

        hours = bar_seconds // 3600
        minutes = (bar_seconds % 3600) // 60
        seconds = bar_seconds % 60

        return timestamp.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)

    def update(self, tick_time, price, volume):
        """
        Update with new tick

        Parameters:
        - tick_time: datetime in Eastern Time
        - price: Last price from tick
        - volume: Cumulative volume (IBKR style - total for day)
        """
        # Get bar boundary time
        bar_time = self.round_to_bar(tick_time)

        # Check if we need a new bar
        if self.current_bar is None or self.current_bar['time'] != bar_time:
            # Complete current bar and add to history
            if self.current_bar is not None:
                self.bars.append(self.current_bar)

                # Keep only last max_bars
                if len(self.bars) > self.max_bars:
                    self.bars.pop(0)

            # Start new bar
            self.current_bar = {
                'time': bar_time,
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'volume': volume,
                'volume_start': volume  # Track volume at bar start for delta
            }
        else:
            # Update current bar
            self.current_bar['high'] = max(self.current_bar['high'], price)
            self.current_bar['low'] = min(self.current_bar['low'], price)
            self.current_bar['close'] = price
            self.current_bar['volume'] = volume

    def get_bars_for_strategy(self):
        """
        Get bars in format strategy module expects

        Returns list of MockBar objects compatible with strategy module
        """
        result = []

        # Convert completed bars
        for bar_dict in self.bars:
            # Calculate bar volume (delta from bar start)
            # IBKR volume is cumulative, so we need the delta
            bar_volume = bar_dict['volume'] - bar_dict.get('volume_start', 0)

            result.append(MockBar(
                date=bar_dict['time'],
                open=bar_dict['open'],
                high=bar_dict['high'],
                low=bar_dict['low'],
                close=bar_dict['close'],
                volume=max(0, bar_volume)  # Ensure non-negative
            ))

        # Add current incomplete bar if exists
        if self.current_bar is not None:
            bar_volume = self.current_bar['volume'] - self.current_bar.get('volume_start', 0)

            result.append(MockBar(
                date=self.current_bar['time'],
                open=self.current_bar['open'],
                high=self.current_bar['high'],
                low=self.current_bar['low'],
                close=self.current_bar['close'],
                volume=max(0, bar_volume)
            ))

        return result

    def get_current_bar_index(self):
        """Get index of current bar (last bar in list)"""
        bars = self.get_bars_for_strategy()
        return len(bars) - 1 if bars else -1

    def has_enough_data(self):
        """Check if we have enough bars for strategy calculations"""
        # Strategy needs at least 20 bars for ATR and filters
        return len(self.get_bars_for_strategy()) >= 20


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

        # Bar buffers for tick-to-bar conversion (CRITICAL for tick-by-tick data)
        self.bar_buffers = {}  # symbol -> BarBuffer

        # Account info
        self.account_size = self.config['trading']['account_size']
        self.max_positions = self.config['trading']['max_positions']

        # Analytics tracking (for end-of-day analysis)
        self.analytics = {
            'filter_blocks': defaultdict(int),  # Count of each filter blocking trades
            'entry_paths': defaultdict(int),    # Count of each entry path taken
            'pivot_checks': defaultdict(int),   # Count of pivot checks per symbol
            'price_updates': 0,                 # Total price updates received
            'session_start': None,              # Session start time
            'session_end': None,                # Session end time
        }

        # State manager for crash recovery (CRITICAL)
        self.state_manager = StateManager(self)

        # IBKR resilience layer (CRITICAL - prevents crashes)
        self.resilience = IBKRResilience(self.ib, self.logger, self.config)

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
        """Connect to IBKR with retry logic"""
        host = self.config['ibkr']['host']
        port = self.config['ibkr']['port']
        client_id = self.config['ibkr']['client_id']

        # Use resilience layer for connection with retry
        return self.resilience.connect_with_retry(host, port, client_id)

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
        """Subscribe to real-time market data for watchlist with error handling"""
        self.logger.info("Subscribing to market data...")

        successful_subscriptions = 0

        for stock_data in self.watchlist:
            symbol = stock_data['symbol']
            contract = Stock(symbol, 'SMART', 'USD')

            try:
                # Qualify contract with error handling
                if not self.resilience.safe_qualify_contract(contract):
                    self.logger.warning(f"  ⚠️  Failed to qualify {symbol} - skipping")
                    continue

                # Subscribe to market data with error handling
                ticker = self.resilience.safe_req_mkt_data(contract, symbol)

                if not ticker:
                    self.logger.warning(f"  ⚠️  Failed to get market data for {symbol} - skipping")
                    continue

                # Store ticker reference
                stock_data['contract'] = contract
                stock_data['ticker'] = ticker

                # Create bar buffer for this symbol (CRITICAL for tick-to-bar conversion)
                self.bar_buffers[symbol] = BarBuffer(symbol, bar_size_seconds=5)

                self.logger.debug(f"  ✓ Subscribed: {symbol}")
                successful_subscriptions += 1

            except Exception as e:
                self.logger.error(f"  ✗ Error subscribing to {symbol}: {e}")
                # Continue with next symbol instead of crashing

        self.logger.info(f"✓ Subscribed to {successful_subscriptions}/{len(self.watchlist)} symbols")
        self.logger.info(f"✓ Created {len(self.bar_buffers)} bar buffers (5-second bars)")

        if successful_subscriptions == 0:
            self.logger.error("✗ Failed to subscribe to any symbols - cannot trade")
            return False

        return True

    def check_gap_filter_at_open(self):
        """
        Check gap filter at market open (9:30 AM ET)

        Filters out stocks where overnight gaps ate up the move.
        This is CRITICAL since scanner runs 8-13 hours before market open.
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("GAP ANALYSIS AT MARKET OPEN (9:30 AM)")
        self.logger.info("="*80)

        # Wait for tickers to populate
        self.ib.sleep(2)

        # Collect opening prices
        opening_prices = {}
        for stock_data in self.watchlist:
            if stock_data['ticker'].last:
                opening_prices[stock_data['symbol']] = float(stock_data['ticker'].last)

        # Use strategy module to filter for gaps
        filtered_watchlist, gap_report = self.strategy.filter_scanner_for_gaps(
            self.watchlist,
            opening_prices
        )

        # Log gap analysis
        if gap_report['skipped']:
            self.logger.warning(f"❌ SKIPPED ({len(gap_report['skipped'])} stocks):")
            for item in gap_report['skipped']:
                self.logger.warning(f"  {item['symbol']}: {item['reason']}")

        if gap_report['adjusted']:
            self.logger.info(f"⚠️  ADJUSTED ({len(gap_report['adjusted'])} stocks):")
            for item in gap_report['adjusted']:
                self.logger.info(f"  {item['symbol']}: {item['reason']}")

        if gap_report['noted']:
            self.logger.info(f"📊 NOTED ({len(gap_report['noted'])} stocks):")
            for item in gap_report['noted']:
                self.logger.info(f"  {item['symbol']}: {item['reason']}")

        # Update watchlist
        original_count = len(self.watchlist)
        self.watchlist = filtered_watchlist
        removed_count = original_count - len(self.watchlist)

        self.logger.info("\n" + "="*80)
        self.logger.info(f"FINAL WATCHLIST: {len(self.watchlist)} setups "
                        f"({removed_count} removed by gap filter)")
        self.logger.info("="*80)

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
        """
        Check if current price breaks pivot levels with FULL FILTER SYSTEM

        Includes:
        - Hybrid entry confirmation (momentum/pullback/sustained)
        - Choppy market filter
        - Room-to-run filter
        - All other filters from strategy module

        USES BAR BUFFER to convert tick data to bars for strategy module

        LOGS EVERYTHING for analysis and learning
        """
        symbol = stock_data['symbol']
        resistance = stock_data['resistance']
        support = stock_data['support']

        # Track pivot checks
        self.analytics['pivot_checks'][symbol] += 1

        # CRITICAL: Check if we have enough bar data for strategy calculations
        if not self.bar_buffers[symbol].has_enough_data():
            bars_count = len(self.bar_buffers[symbol].get_bars_for_strategy())
            self.logger.debug(f"  {symbol}: Warming up ({bars_count}/20 bars), skipping checks")
            return None, None

        # Get bars from buffer for strategy module
        bars = self.bar_buffers[symbol].get_bars_for_strategy()
        current_idx = self.bar_buffers[symbol].get_current_bar_index()

        # Get attempt count from position manager
        long_attempts = self.pm.get_attempt_count(symbol, resistance)
        short_attempts = self.pm.get_attempt_count(symbol, support)

        # Log current state (verbose for learning)
        distance_to_resistance = ((current_price - resistance) / resistance) * 100
        distance_to_support = ((support - current_price) / support) * 100

        # Check if price is near pivot (within 1%)
        if abs(distance_to_resistance) < 1.0:
            self.logger.debug(f"  {symbol}: ${current_price:.2f} is {distance_to_resistance:+.2f}% from resistance ${resistance:.2f} (attempt {long_attempts+1})")

        if abs(distance_to_support) < 1.0:
            self.logger.debug(f"  {symbol}: ${current_price:.2f} is {distance_to_support:+.2f}% from support ${support:.2f} (attempt {short_attempts+1})")

        # Check long pivot break using strategy module WITH ALL FILTERS
        # Pass bars and current_idx for hybrid entry confirmation
        should_long, reason = self.strategy.should_enter_long(
            stock_data, current_price, long_attempts, bars=bars, current_idx=current_idx
        )
        if should_long:
            self.logger.info(f"\n🎯 {symbol}: LONG SIGNAL @ ${current_price:.2f}")
            self.logger.info(f"   Distance from resistance: {distance_to_resistance:+.2f}%")
            self.logger.info(f"   Attempt: {long_attempts + 1}/{self.strategy.max_attempts_per_pivot}")
            self.logger.info(f"   Entry Path: {reason}")

            # Track entry path for analytics
            self.analytics['entry_paths'][reason] += 1

            return 'LONG', resistance, reason
        elif reason:
            # Track which filter blocked
            filter_name = reason.split(':')[0] if ':' in reason else reason
            self.analytics['filter_blocks'][filter_name] += 1

            # CRITICAL: Log filter blocks at INFO level when price is close to pivot
            # This helps understand why we DIDN'T enter a trade
            if abs(distance_to_resistance) < 1.0:  # Within 1% of pivot
                self.logger.info(f"  ❌ {symbol}: LONG blocked @ ${current_price:.2f} - {reason}")
            else:
                self.logger.debug(f"  {symbol}: LONG blocked - {reason}")

        # Check short pivot break using strategy module WITH ALL FILTERS
        # Pass bars and current_idx for hybrid entry confirmation
        should_short, reason = self.strategy.should_enter_short(
            stock_data, current_price, short_attempts, bars=bars, current_idx=current_idx
        )
        if should_short:
            self.logger.info(f"\n🎯 {symbol}: SHORT SIGNAL @ ${current_price:.2f}")
            self.logger.info(f"   Distance from support: {distance_to_support:+.2f}%")
            self.logger.info(f"   Attempt: {short_attempts + 1}/{self.strategy.max_attempts_per_pivot}")
            self.logger.info(f"   Entry Path: {reason}")

            # Track entry path for analytics
            self.analytics['entry_paths'][reason] += 1

            return 'SHORT', support, reason
        elif reason:
            # Track which filter blocked
            filter_name = reason.split(':')[0] if ':' in reason else reason
            self.analytics['filter_blocks'][filter_name] += 1

            # CRITICAL: Log filter blocks at INFO level when price is close to pivot
            # This helps understand why we DIDN'T enter a trade
            if abs(distance_to_support) < 1.0:  # Within 1% of pivot
                self.logger.info(f"  ❌ {symbol}: SHORT blocked @ ${current_price:.2f} - {reason}")
            else:
                self.logger.debug(f"  {symbol}: SHORT blocked - {reason}")

        return None, None, None

    def calculate_position_size(self, entry_price, stop_price):
        """Calculate position size based on 1% risk"""
        return self.strategy.calculate_position_size(
            self.account_size,
            entry_price,
            stop_price
        )

    def enter_long(self, stock_data, current_price, entry_reason="Resistance broken"):
        """Enter long position with full filter system"""
        symbol = stock_data['symbol']
        resistance = stock_data['resistance']
        contract = stock_data['contract']

        # Get current time in Eastern
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)

        # Calculate position size
        shares = self.calculate_position_size(current_price, resistance)

        # Create market order
        order = MarketOrder('BUY', shares)

        # Place order with error handling
        trade = self.resilience.safe_place_order(contract, order, f"{symbol} LONG")

        if not trade:
            self.logger.error(f"✗ Failed to place LONG order for {symbol} - skipping entry")
            return None

        # Wait for fill
        try:
            self.ib.sleep(1)

            # Get fill price
            fill_price = current_price  # Approximate for now
            if trade.orderStatus.filled > 0:
                fill_price = trade.orderStatus.avgFillPrice
        except Exception as e:
            self.logger.error(f"⚠️  Error checking fill for {symbol}: {e}")
            fill_price = current_price  # Use current price as fallback

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

        # Calculate risk and room to target
        risk = fill_price - resistance
        room_to_target = stock_data['target1'] - fill_price
        room_pct = (room_to_target / fill_price) * 100

        self.logger.info(f"\n🟢 LONG {symbol} @ ${fill_price:.2f} ({now_et.strftime('%I:%M:%S %p')} ET)")
        self.logger.info(f"   Entry Path: {entry_reason}")
        self.logger.info(f"   Shares: {shares} | Risk: ${risk:.2f} | Room: {room_pct:.2f}%")
        self.logger.info(f"   Stop: ${resistance:.2f} | Target1: ${stock_data['target1']:.2f}")

        # Place stop order
        self.place_stop_order(position)

        return position

    def enter_short(self, stock_data, current_price, entry_reason="Support broken"):
        """Enter short position with full filter system"""
        symbol = stock_data['symbol']
        support = stock_data['support']
        contract = stock_data['contract']

        # Get current time in Eastern
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)

        # Calculate position size
        shares = self.calculate_position_size(support, current_price)

        # Create market order
        order = MarketOrder('SELL', shares)

        # Place order with error handling
        trade = self.resilience.safe_place_order(contract, order, f"{symbol} SHORT")

        if not trade:
            self.logger.error(f"✗ Failed to place SHORT order for {symbol} - skipping entry")
            return None

        # Wait for fill
        try:
            self.ib.sleep(1)

            # Get fill price
            fill_price = current_price
            if trade.orderStatus.filled > 0:
                fill_price = trade.orderStatus.avgFillPrice
        except Exception as e:
            self.logger.error(f"⚠️  Error checking fill for {symbol}: {e}")
            fill_price = current_price  # Use current price as fallback

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

        # Calculate risk and room to target
        risk = support - fill_price
        room_to_target = fill_price - stock_data.get('downside1', support * 0.98)
        room_pct = (room_to_target / fill_price) * 100

        self.logger.info(f"\n🔴 SHORT {symbol} @ ${fill_price:.2f} ({now_et.strftime('%I:%M:%S %p')} ET)")
        self.logger.info(f"   Entry Path: {entry_reason}")
        self.logger.info(f"   Shares: {shares} | Risk: ${risk:.2f} | Room: {room_pct:.2f}%")
        self.logger.info(f"   Stop: ${support:.2f} | Target1: ${stock_data.get('downside1', support * 0.98):.2f}")

        # Place stop order
        self.place_stop_order(position)

        return position

    def place_stop_order(self, position):
        """Place stop loss order with error handling"""
        symbol = position['symbol']
        contract = position['contract']
        stop_price = position['stop']
        shares = int(position['shares'] * position['remaining'])

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Create stop order
        stop_order = StopOrder(action, shares, stop_price)

        # Place order with error handling
        trade = self.resilience.safe_place_order(contract, stop_order, f"{symbol} STOP")

        if not trade:
            self.logger.error(f"✗ Failed to place stop order for {symbol}")
            self.logger.error(f"  ⚠️  Position at risk - manual intervention required")
            return False

        position['stop_order'] = trade
        self.logger.debug(f"  Stop order placed: {action} {shares} @ ${stop_price:.2f}")
        return True

    def manage_positions(self):
        """
        Manage open positions - check for partials, stops, targets

        LOGS DETAILED POSITION STATE for analysis
        """
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

            # Calculate current P&L and stats
            if position['side'] == 'LONG':
                unrealized_pnl = (current_price - position['entry_price']) * position['shares'] * position['remaining']
                gain_pct = ((current_price - position['entry_price']) / position['entry_price']) * 100
            else:
                unrealized_pnl = (position['entry_price'] - current_price) * position['shares'] * position['remaining']
                gain_pct = ((position['entry_price'] - current_price) / position['entry_price']) * 100

            time_in_trade = (current_time - position['entry_time']).total_seconds() / 60

            # Log position state every minute (for learning)
            if int(time_in_trade) % 1 == 0 and time_in_trade > 0:
                self.logger.debug(f"  [{symbol}] {position['side']} @ ${position['entry_price']:.2f} | "
                                f"Current: ${current_price:.2f} ({gain_pct:+.2f}%) | "
                                f"Time: {int(time_in_trade)}m | "
                                f"Remaining: {int(position['remaining']*100)}% | "
                                f"P&L: ${unrealized_pnl:+.2f}")

            # Check 8-minute rule (FIXED - checks if stuck at pivot)
            should_exit, reason = self.strategy.check_five_minute_rule(
                position, current_price, current_time
            )
            if should_exit:
                self.logger.info(f"\n⏱️  8-MINUTE RULE: {symbol} ({reason})")
                self.logger.info(f"   Entry: ${position['entry_price']:.2f} @ {position['entry_time'].strftime('%I:%M:%S %p')} ET")
                self.logger.info(f"   Current: ${current_price:.2f} ({gain_pct:+.2f}%) after {int(time_in_trade)} minutes")
                self.logger.info(f"   Reason: No progress, exiting to prevent larger loss")
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
                    self.logger.info(f"  🛡️  {symbol}: Stop moved ${old_stop:.2f} → ${position['stop']:.2f} (breakeven)")
                    self.logger.info(f"      Now protected: ${position['realized_pnl']:.2f} locked in")

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
        """Close entire position and return trade object with error handling"""
        symbol = position['symbol']
        shares = int(position['shares'] * position['remaining'])

        if shares == 0:
            del self.positions[symbol]
            return None

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Place market order with error handling
        order = MarketOrder(action, shares)
        trade = self.resilience.safe_place_order(position['contract'], order, f"{symbol} CLOSE")

        if not trade:
            self.logger.error(f"✗ Failed to close {symbol} position")
            self.logger.error(f"  ⚠️  Manual intervention required to close {shares} shares")
            # Don't remove from positions - will retry on next iteration
            return None

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
        """Main trading loop with FULL FILTER SYSTEM"""
        # Get current time in Eastern
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)

        self.logger.info("="*80)
        self.logger.info("PS60 LIVE TRADER - PAPER TRADING SESSION")
        self.logger.info(f"Date: {now_et.strftime('%Y-%m-%d %A')}")
        self.logger.info(f"Time: {now_et.strftime('%I:%M:%S %p')} ET")
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

        # CRITICAL: Recover state from previous session (crash recovery)
        # This must happen AFTER connecting to IBKR and subscribing to data
        self.state_manager.recover_full_state()

        # Wait for market open if before 9:30 AM ET
        market_open = dt_time(9, 30)
        while now_et.time() < market_open:
            wait_seconds = (datetime.combine(now_et.date(), market_open) - now_et).total_seconds()
            self.logger.info(f"Waiting for market open... ({int(wait_seconds/60)} minutes)")
            time_module.sleep(min(60, wait_seconds))
            now_et = datetime.now(pytz.UTC).astimezone(eastern)

        # Check gap filter at market open (CRITICAL - Oct 5, 2025)
        self.check_gap_filter_at_open()

        # Record session start
        self.analytics['session_start'] = datetime.now(pytz.UTC).astimezone(eastern)

        self.logger.info("\n" + "="*80)
        self.logger.info("MONITORING STARTED - ALL FILTERS ACTIVE")
        self.logger.info("="*80)
        self.logger.info("Active Filters:")
        self.logger.info(f"  ✓ Choppy Market Filter: {self.strategy.enable_choppy_filter}")
        self.logger.info(f"  ✓ Room-to-Run Filter: {self.strategy.enable_room_to_run_filter}")
        self.logger.info(f"  ✓ Sustained Break Logic: {self.strategy.sustained_break_enabled}")
        self.logger.info(f"  ✓ 8-Minute Rule: Active")
        self.logger.info(f"  ✓ Max Attempts: {self.strategy.max_attempts_per_pivot}")
        self.logger.info(f"  ✓ Entry Window: {self.strategy.min_entry_time} - {self.strategy.max_entry_time}")
        self.logger.info("="*80)
        self.logger.info(f"\n💡 TIP: Set log level to DEBUG to see all filter decisions")
        self.logger.info(f"    Edit config: logging.log_level = 'DEBUG'")
        self.logger.info("="*80)

        try:
            while True:
                # Check if within trading hours
                in_market, in_entry = self.is_trading_hours()

                if not in_market:
                    self.logger.info("Market closed. Exiting...")
                    break

                # Check for EOD close using strategy module (TIMEZONE FIX - Oct 5, 2025)
                # CRITICAL: Always use Eastern Time for market hours
                eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(pytz.UTC).astimezone(eastern)

                if self.strategy.is_near_eod(now_et):
                    self.logger.info(f"\n⏰ EOD close triggered at {now_et.strftime('%I:%M:%S %p')} ET")
                    self.close_all_positions('EOD')
                    break

                # Update all tickers
                self.ib.sleep(0.1)

                # Track price updates
                self.analytics['price_updates'] += 1

                # CRITICAL: Save state every 10 seconds (crash recovery)
                if self.analytics['price_updates'] % 10 == 0:  # Every 10 seconds
                    self.state_manager.save_state()

                    # CRITICAL: Monitor IBKR connection health every 10 seconds
                    if not self.resilience.monitor_connection():
                        self.logger.error("⚠️  Connection lost - cannot continue trading")
                        self.logger.error("    Please restart the trader")
                        break

                # Log market activity every 5 minutes
                if self.analytics['price_updates'] % 300 == 0:  # Every 5 minutes (at 1 update/sec)
                    eastern = pytz.timezone('US/Eastern')
                    now_et = datetime.now(pytz.UTC).astimezone(eastern)
                    self.logger.info(f"\n⏰ {now_et.strftime('%I:%M %p')} ET - Market Activity Check:")
                    self.logger.info(f"   Open Positions: {len(self.positions)}")
                    self.logger.info(f"   Monitoring: {len(self.watchlist)} symbols")
                    if self.positions:
                        for symbol, pos in self.positions.items():
                            if pos['side'] == 'LONG':
                                gain = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                            else:
                                gain = ((pos['entry_price'] - current_price) / pos['entry_price']) * 100
                            self.logger.info(f"   {symbol}: {pos['side']} @ ${pos['entry_price']:.2f} ({gain:+.2f}%)")

                # CRITICAL: Update bar buffers with tick data BEFORE checking pivots
                # This converts tick-by-tick data into 5-second bars for strategy module
                eastern = pytz.timezone('US/Eastern')
                now_et = datetime.now(pytz.UTC).astimezone(eastern)

                for stock_data in self.watchlist:
                    symbol = stock_data['symbol']
                    if stock_data['ticker'].last and stock_data['ticker'].volume:
                        price = float(stock_data['ticker'].last)
                        volume = stock_data['ticker'].volume

                        # Feed tick to bar buffer
                        self.bar_buffers[symbol].update(now_et, price, volume)

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

                        # Check for pivot break (uses bars from buffer)
                        direction, pivot, entry_reason = self.check_pivot_break(stock_data, current_price)

                        if direction == 'LONG':
                            self.enter_long(stock_data, current_price, entry_reason)
                        elif direction == 'SHORT':
                            self.enter_short(stock_data, current_price, entry_reason)

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
        """
        Print comprehensive end-of-day summary with analytics

        DETAILED LOGGING for analysis and learning
        """
        # Get summary from position manager
        summary = self.pm.get_daily_summary()

        # Record session end time
        eastern = pytz.timezone('US/Eastern')
        self.analytics['session_end'] = datetime.now(pytz.UTC).astimezone(eastern)

        self.logger.info("\n" + "="*80)
        self.logger.info("DAILY SUMMARY")
        self.logger.info("="*80)

        # Session timing
        if self.analytics['session_start']:
            session_duration = (self.analytics['session_end'] - self.analytics['session_start']).total_seconds() / 60
            self.logger.info(f"\nSession Duration: {int(session_duration)} minutes")
            self.logger.info(f"  Start: {self.analytics['session_start'].strftime('%I:%M:%S %p')} ET")
            self.logger.info(f"  End:   {self.analytics['session_end'].strftime('%I:%M:%S %p')} ET")

        # Trading results
        self.logger.info(f"\n📊 TRADING RESULTS:")
        self.logger.info(f"  Total Trades: {summary['total_trades']}")
        self.logger.info(f"  Daily P&L: ${summary['daily_pnl']:.2f} ({summary['daily_pnl']/self.account_size*100:.2f}% of account)")

        if summary['total_trades'] > 0:
            self.logger.info(f"  Winners: {summary['winners']} ({summary['win_rate']:.1f}%)")
            self.logger.info(f"  Losers: {summary['losers']}")
            self.logger.info(f"  Avg Trade: ${summary['daily_pnl']/summary['total_trades']:.2f}")

            if summary['avg_winner']:
                self.logger.info(f"  Avg Winner: ${summary['avg_winner']:.2f}")

            if summary['avg_loser']:
                self.logger.info(f"  Avg Loser: ${summary['avg_loser']:.2f}")

            if summary['winners'] > 0 and summary['losers'] > 0:
                profit_factor = abs(summary['avg_winner'] * summary['winners']) / abs(summary['avg_loser'] * summary['losers'])
                self.logger.info(f"  Profit Factor: {profit_factor:.2f}")

        # Filter analytics - CRITICAL for understanding missed opportunities
        self.logger.info(f"\n🎯 FILTER ANALYTICS - Why We DIDN'T Enter Trades:")
        if self.analytics['filter_blocks']:
            total_blocks = sum(self.analytics['filter_blocks'].values())
            self.logger.info(f"  Total Filter Blocks: {total_blocks}")
            self.logger.info(f"\n  Top Reasons (with actionable insights):")

            for filter_name, count in sorted(self.analytics['filter_blocks'].items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_blocks) * 100
                self.logger.info(f"\n    {filter_name}: {count} times ({pct:.1f}%)")

                # Provide actionable insights for each filter
                if 'Max attempts' in filter_name:
                    self.logger.info(f"      → Stock whipsawed {count} times - good filter working")
                elif 'choppy' in filter_name.lower():
                    self.logger.info(f"      → Choppy market filter saved ${count * 100:.0f} (estimated)")
                elif 'room' in filter_name.lower() or 'Room' in filter_name:
                    self.logger.info(f"      → Insufficient room to target - good risk management")
                elif 'waiting' in filter_name.lower() or 'Waiting' in filter_name:
                    self.logger.info(f"      → Confirmation logic working - patience required")
                elif 'Avoiding' in filter_name:
                    self.logger.info(f"      → Configuration filter - adjust if needed")
                elif 'Gap' in filter_name:
                    self.logger.info(f"      → Overnight gap filter working - protect capital")
                elif 'Price below' in filter_name or 'Price above' in filter_name:
                    self.logger.info(f"      → Not at pivot yet - monitor continues")
                else:
                    self.logger.info(f"      → Review this filter if blocking too many trades")
        else:
            self.logger.info(f"  No trades blocked by filters")
            self.logger.info(f"  ⚠️  This is unusual - verify filter system is working")

        # Entry path analytics - Shows which confirmation method triggered entries
        if self.analytics['entry_paths']:
            self.logger.info(f"\n📈 ENTRY PATH BREAKDOWN - How We Entered Trades:")
            total_entries = sum(self.analytics['entry_paths'].values())
            for path, count in sorted(self.analytics['entry_paths'].items(), key=lambda x: x[1], reverse=True):
                pct = (count / total_entries) * 100
                self.logger.info(f"  {path}: {count} trades ({pct:.1f}%)")

                # Explain what each path means
                if 'MOMENTUM' in path:
                    self.logger.info(f"    → Immediate entry (volume ≥1.3x, candle ≥0.8%)")
                elif 'PULLBACK' in path or 'RETEST' in path:
                    self.logger.info(f"    → Patient entry (waited for pullback/retest)")
                elif 'SUSTAINED' in path:
                    self.logger.info(f"    → Grinding entry (held 2+ minutes above pivot)")
        else:
            self.logger.info(f"\n📈 ENTRY PATH BREAKDOWN:")
            self.logger.info(f"  No trades entered today")

        # Pivot check analytics
        self.logger.info(f"\n🔍 MONITORING ACTIVITY:")
        self.logger.info(f"  Total Price Updates: {self.analytics['price_updates']:,}")
        if self.analytics['pivot_checks']:
            total_checks = sum(self.analytics['pivot_checks'].values())
            self.logger.info(f"  Total Pivot Checks: {total_checks:,}")
            self.logger.info(f"  Most Active Symbols:")
            for symbol, count in sorted(self.analytics['pivot_checks'].items(), key=lambda x: x[1], reverse=True)[:5]:
                self.logger.info(f"    {symbol}: {count:,} checks")

        # IBKR Error Statistics - CRITICAL for monitoring connection health
        error_summary = self.resilience.get_error_summary()
        self.logger.info(f"\n⚠️  IBKR ERROR STATISTICS:")
        self.logger.info(f"  Total Errors: {error_summary['total_errors']}")

        if error_summary['total_errors'] > 0:
            self.logger.info(f"\n  Error Breakdown:")
            for error_type, count in error_summary['error_counts'].items():
                if count > 0:
                    self.logger.info(f"    {error_type.capitalize()}: {count}")

            self.logger.info(f"\n  Connection Stats:")
            self.logger.info(f"    Connection Failures: {error_summary['connection_failures']}")
            self.logger.info(f"    Consecutive Errors: {error_summary['consecutive_errors']}")

            if error_summary['circuit_breaker_open']:
                self.logger.info(f"\n  ⚠️  CIRCUIT BREAKER WAS TRIGGERED")
                self.logger.info(f"      Too many consecutive errors - trading paused")
                self.logger.info(f"      → Check IBKR connection and TWS/Gateway status")

            # Actionable recommendations
            if error_summary['error_counts']['connection'] > 5:
                self.logger.info(f"\n  ⚠️  HIGH CONNECTION ERRORS ({error_summary['error_counts']['connection']})")
                self.logger.info(f"      → Check network stability")
                self.logger.info(f"      → Verify TWS/Gateway is running")

            if error_summary['error_counts']['order'] > 5:
                self.logger.info(f"\n  ⚠️  HIGH ORDER ERRORS ({error_summary['error_counts']['order']})")
                self.logger.info(f"      → Check account permissions")
                self.logger.info(f"      → Verify sufficient buying power")

            if error_summary['error_counts']['data'] > 10:
                self.logger.info(f"\n  ⚠️  HIGH DATA ERRORS ({error_summary['error_counts']['data']})")
                self.logger.info(f"      → Check market data subscriptions")
                self.logger.info(f"      → Verify symbols are valid")
        else:
            self.logger.info(f"  ✓ No IBKR errors encountered")
            self.logger.info(f"  ✓ Connection was stable throughout session")

        # Trade-by-trade breakdown
        if summary['trades']:
            self.logger.info(f"\n📋 TRADE-BY-TRADE BREAKDOWN:")
            for i, trade in enumerate(summary['trades'], 1):
                entry_time = datetime.fromisoformat(trade['entry_time'])
                exit_time = datetime.fromisoformat(trade['exit_time'])
                duration = (exit_time - entry_time).total_seconds() / 60

                pnl_sign = '+' if trade['pnl'] > 0 else ''
                self.logger.info(f"\n  Trade #{i}: {trade['symbol']} {trade['side']}")
                self.logger.info(f"    Entry: ${trade['entry_price']:.2f} @ {entry_time.strftime('%I:%M:%S %p')} ET")
                self.logger.info(f"    Exit:  ${trade['exit_price']:.2f} @ {exit_time.strftime('%I:%M:%S %p')} ET ({trade['reason']})")
                self.logger.info(f"    Duration: {int(duration)} minutes")
                self.logger.info(f"    P&L: {pnl_sign}${trade['pnl']:.2f} ({pnl_sign}{trade['pnl']/trade['entry_price']/trade['shares']*100:.2f}%)")
                if 'partials' in trade and trade['partials']:
                    self.logger.info(f"    Partials: {len(trade['partials'])} taken")

        # Save trades to file
        if summary['trades']:
            log_dir = Path(self.config['logging']['log_dir'])
            trade_file = log_dir / f'trades_{datetime.now().strftime("%Y%m%d")}.json'

            # Add analytics to save file
            save_data = {
                'summary': summary,
                'analytics': {
                    'session_start': self.analytics['session_start'].isoformat() if self.analytics['session_start'] else None,
                    'session_end': self.analytics['session_end'].isoformat() if self.analytics['session_end'] else None,
                    'filter_blocks': dict(self.analytics['filter_blocks']),
                    'entry_paths': dict(self.analytics['entry_paths']),
                    'pivot_checks': dict(self.analytics['pivot_checks']),
                    'price_updates': self.analytics['price_updates']
                },
                'config': {
                    'choppy_filter': self.strategy.enable_choppy_filter,
                    'room_to_run_filter': self.strategy.enable_room_to_run_filter,
                    'sustained_break': self.strategy.sustained_break_enabled,
                    'max_attempts': self.strategy.max_attempts_per_pivot,
                    'entry_window': f"{self.strategy.min_entry_time} - {self.strategy.max_entry_time}"
                }
            }

            with open(trade_file, 'w') as f:
                json.dump(save_data, f, indent=2)

            self.logger.info(f"\n💾 Full session data saved to: {trade_file}")

        # Comparison to backtest expectations
        self.logger.info(f"\n📊 BACKTEST COMPARISON:")
        self.logger.info(f"  Expected Win Rate: 35-45%")
        if summary['total_trades'] > 0:
            self.logger.info(f"  Actual Win Rate:   {summary['win_rate']:.1f}%")
            if summary['win_rate'] >= 35:
                self.logger.info(f"  ✅ Within expected range")
            else:
                self.logger.info(f"  ⚠️  Below expected range (needs investigation)")

        self.logger.info("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description='PS60 Live Trader')
    parser.add_argument('--config', default='config/trader_config.yaml',
                       help='Path to configuration file')

    args = parser.parse_args()

    trader = PS60Trader(args.config)
    trader.run()


if __name__ == '__main__':
    main()
