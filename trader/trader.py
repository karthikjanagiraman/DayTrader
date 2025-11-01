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
import signal
import sys

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

    CRITICAL FIX (Oct 20, 2025): Track ABSOLUTE bar count, not array index
    - State machine uses absolute bar numbers (0, 1, 2, ... 1400, 1401...)
    - Array only stores last N bars (sliding window)
    - Must map absolute bar numbers to array indices
    """

    def __init__(self, symbol, bar_size_seconds=5):
        self.symbol = symbol
        self.bar_size = bar_size_seconds
        self.current_bar = None
        self.bars = []  # Sliding window of recent bars
        self.max_bars = 240  # INCREASED: 240 bars = 20 minutes (was 120 = 10 min)
        self.total_bar_count = 0  # NEW: Absolute bar counter (increments forever)

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
                self.total_bar_count += 1  # NEW: Increment absolute counter

                # Keep only last max_bars (sliding window)
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
        """
        Get ABSOLUTE bar index (not array index)

        CRITICAL FIX (Oct 20, 2025):
        - Returns absolute bar count (0, 1, 2, ... 1400, 1401...)
        - NOT array index (which caps at max_bars - 1)
        - State machine uses absolute indices for tracking

        Returns:
            int: Absolute bar count since session start
        """
        return self.total_bar_count

    def get_current_array_index(self):
        """
        Get ARRAY index for direct bar data access

        CRITICAL FIX PART 2 (Oct 20, 2025):
        - Returns array position (0 to max_bars-1)
        - Use this for accessing bars[] directly
        - Strategy code uses this, state machine uses get_current_bar_index()

        Returns:
            int: Array index (0-239), or -1 if no bars
        """
        bars = self.get_bars_for_strategy()
        return len(bars) - 1 if bars else -1

    def get_oldest_bar_absolute_index(self):
        """
        Get absolute index of oldest bar in buffer

        Example:
        - total_bar_count = 500 (current bar)
        - len(bars) = 240 (buffer full)
        - oldest bar = 500 - 240 + 1 = 261

        Returns:
            int: Absolute index of oldest bar, or 0 if buffer not full
        """
        if not self.bars:
            return 0
        return max(0, self.total_bar_count - len(self.bars) + 1)

    def map_absolute_to_array_index(self, absolute_idx):
        """
        Map absolute bar index to array index

        Args:
            absolute_idx: Absolute bar number (e.g., 500)

        Returns:
            int: Array index (0-239), or None if bar not in buffer

        Example:
        - total_bar_count = 500
        - bars array size = 240
        - oldest_bar_absolute = 261
        - To access absolute bar 400:
          array_idx = 400 - 261 = 139
        """
        oldest_abs = self.get_oldest_bar_absolute_index()

        if absolute_idx < oldest_abs:
            # Bar has been dropped from buffer
            return None

        if absolute_idx > self.total_bar_count:
            # Future bar (doesn't exist yet)
            return None

        array_idx = absolute_idx - oldest_abs

        # Validate it's within array bounds
        if array_idx < 0 or array_idx >= len(self.bars):
            return None

        return array_idx

    def get_bars_by_absolute_range(self, start_abs, end_abs):
        """
        Get bars using ABSOLUTE bar indices (not array indices)

        Args:
            start_abs: Starting absolute bar index (inclusive)
            end_abs: Ending absolute bar index (exclusive, like Python slicing)

        Returns:
            list: MockBar objects in range, or empty list if not available

        Example:
        - Request bars 400-412 (12 bars for 1-minute candle)
        - Maps to array indices and returns those bars
        """
        # Map absolute indices to array indices
        start_array_idx = self.map_absolute_to_array_index(start_abs)
        end_array_idx = self.map_absolute_to_array_index(end_abs - 1)  # -1 because end is exclusive

        if start_array_idx is None or end_array_idx is None:
            # Requested bars not in buffer
            return []

        # Get all bars in strategy format
        all_bars = self.get_bars_for_strategy()

        # Return the requested range (end_array_idx + 1 because we want inclusive)
        return all_bars[start_array_idx:end_array_idx + 1]

    def validate_bars_available(self, start_abs, end_abs):
        """
        Check if requested bars are still in buffer

        Args:
            start_abs: Starting absolute bar index
            end_abs: Ending absolute bar index (exclusive)

        Returns:
            tuple: (available, reason)
        """
        oldest_abs = self.get_oldest_bar_absolute_index()

        if start_abs < oldest_abs:
            return False, f"Bar {start_abs} dropped from buffer (oldest={oldest_abs})"

        if end_abs > self.total_bar_count + 1:
            return False, f"Bar {end_abs} doesn't exist yet (current={self.total_bar_count})"

        return True, None

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

        # FIX GAP #7: Register graceful shutdown handler (Oct 13, 2025)
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        self.shutdown_requested = False

    def setup_logging(self):
        """Setup logging configuration - FIX GAP #10: Text-only logging (Oct 13, 2025)"""
        log_dir = Path(self.config['logging']['log_dir'])
        log_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d')
        log_file = log_dir / f'trader_{timestamp}.log'

        # FIX GAP #10: Ensure text-only logging (no binary data)
        logging.basicConfig(
            level=getattr(logging, self.config['logging']['log_level']),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', errors='replace'),  # Force UTF-8, replace bad chars
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('PS60Trader')

    def handle_shutdown(self, signum, frame):
        """
        FIX GAP #7: Graceful shutdown handler (Oct 13, 2025)
        Handle Ctrl+C and termination signals gracefully
        """
        signal_name = 'SIGINT' if signum == signal.SIGINT else 'SIGTERM'
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"🛑 SHUTDOWN SIGNAL RECEIVED ({signal_name})")
        self.logger.info(f"{'='*80}")
        self.logger.info("Closing all positions gracefully...")

        self.shutdown_requested = True

        # Close all open positions at market prices
        if self.positions:
            self.close_all_positions('SHUTDOWN')

        # Save final state
        self.save_session_report()

        self.logger.info("✓ Shutdown complete - exiting")
        sys.exit(0)

    def validate_startup(self):
        """
        FIX GAP #6: Startup validation checklist (Oct 13, 2025)
        Validates all prerequisites before starting trading

        Returns:
            (bool, str) - (success, error_message)
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("🔍 STARTUP VALIDATION CHECKLIST")
        self.logger.info("="*80)

        checks_passed = []
        checks_failed = []

        # CHECK 1: IBKR Connection
        if self.ib.isConnected():
            checks_passed.append("✓ IBKR Connection: Active")
        else:
            checks_failed.append("✗ IBKR Connection: NOT CONNECTED")

        # CHECK 2: Scanner File Exists
        scanner_file = Path(self.scanner_results_file)
        if scanner_file.exists():
            checks_passed.append(f"✓ Scanner File: {scanner_file.name}")

            # CHECK 3: Scanner File Age (should be recent)
            import time
            file_age_hours = (time.time() - scanner_file.stat().st_mtime) / 3600
            if file_age_hours < 24:
                checks_passed.append(f"✓ Scanner Age: {file_age_hours:.1f} hours (fresh)")
            else:
                checks_failed.append(f"⚠️  Scanner Age: {file_age_hours:.1f} hours (stale)")
        else:
            checks_failed.append(f"✗ Scanner File: NOT FOUND ({scanner_file})")

        # CHECK 4: FIX GAP #3 - Account Size Validation
        if self.account_size >= 10000:  # Minimum $10k
            checks_passed.append(f"✓ Account Size: ${self.account_size:,.0f}")
        else:
            checks_failed.append(f"✗ Account Size: ${self.account_size:,.0f} (too small)")

        # CHECK 5: Watchlist has valid symbols
        if self.watchlist and len(self.watchlist) > 0:
            checks_passed.append(f"✓ Watchlist: {len(self.watchlist)} symbols loaded")
        else:
            checks_failed.append("✗ Watchlist: EMPTY")

        # CHECK 6: Market hours
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)
        market_open = dt_time(9, 30)
        market_close = dt_time(16, 0)
        current_time = now_et.time()

        if market_open <= current_time < market_close:
            checks_passed.append(f"✓ Market Hours: {now_et.strftime('%I:%M %p')} ET (OPEN)")
        else:
            checks_failed.append(f"⚠️  Market Hours: {now_et.strftime('%I:%M %p')} ET (CLOSED)")

        # CHECK 7: No open positions from previous session
        portfolio = self.ib.portfolio()
        if len(portfolio) == 0:
            checks_passed.append("✓ Portfolio: Clean (no open positions)")
        else:
            checks_failed.append(f"⚠️  Portfolio: {len(portfolio)} open positions (cleanup needed)")

        # Print results
        for check in checks_passed:
            self.logger.info(f"  {check}")
        for check in checks_failed:
            self.logger.warning(f"  {check}")

        self.logger.info("="*80)

        # Determine if we can proceed
        critical_failures = [f for f in checks_failed if f.startswith("✗")]

        if critical_failures:
            self.logger.error(f"❌ STARTUP VALIDATION FAILED: {len(critical_failures)} critical issue(s)")
            return False, "\n".join(critical_failures)
        elif checks_failed:
            self.logger.warning(f"⚠️  STARTUP VALIDATION PASSED WITH WARNINGS: {len(checks_failed)} warning(s)")
            return True, "Warnings present but can proceed"
        else:
            self.logger.info(f"✅ STARTUP VALIDATION PASSED: All {len(checks_passed)} checks OK")
            return True, "All checks passed"

    def connect(self):
        """Connect to IBKR with retry logic"""
        host = self.config['ibkr']['host']
        port = self.config['ibkr']['port']
        client_id = self.config['ibkr']['client_id']

        # Use resilience layer for connection with retry
        return self.resilience.connect_with_retry(host, port, client_id)

    def cleanup_session(self):
        """
        Clean up at startup - close all open positions and cancel all orders
        Ensures we start fresh each session (Oct 13, 2025)
        """
        if not self.ib.isConnected():
            self.logger.warning("Cannot cleanup - not connected to IBKR")
            return

        self.logger.info("=" * 80)
        self.logger.info("🧹 SESSION CLEANUP - Preparing for fresh start...")
        self.logger.info("=" * 80)

        # 1. Cancel all open orders
        open_orders = self.ib.openOrders()
        if open_orders:
            self.logger.info(f"📋 Found {len(open_orders)} open orders - cancelling...")
            for order in open_orders:
                try:
                    self.ib.cancelOrder(order)
                    self.logger.info(f"   ✓ Cancelled order {order.orderId} for {order.contract.symbol}")
                except Exception as e:
                    self.logger.error(f"   ✗ Failed to cancel order {order.orderId}: {e}")

            # Wait for cancellations to process
            self.ib.sleep(2)
        else:
            self.logger.info("✓ No open orders to cancel")

        # 2. Close all open positions
        positions = self.ib.positions()
        active_positions = [p for p in positions if p.position != 0]

        if active_positions:
            self.logger.info(f"📊 Found {len(active_positions)} open positions - closing...")
            for position in active_positions:
                symbol = position.contract.symbol
                shares = abs(position.position)
                side = 'SHORT' if position.position < 0 else 'LONG'

                self.logger.info(f"   Closing {side} {symbol}: {shares} shares @ avg ${position.avgCost:.2f}")

                # Create closing order (opposite side)
                action = 'BUY' if position.position < 0 else 'SELL'
                contract = Stock(symbol, 'SMART', 'USD')
                order = MarketOrder(action, shares)

                try:
                    trade = self.ib.placeOrder(contract, order)
                    self.ib.sleep(1)  # Wait for fill

                    if trade.orderStatus.status in ['Filled', 'PreSubmitted']:
                        self.logger.info(f"   ✓ Closed {symbol}")
                    else:
                        self.logger.warning(f"   ⚠️  {symbol} order status: {trade.orderStatus.status}")
                except Exception as e:
                    self.logger.error(f"   ✗ Failed to close {symbol}: {e}")

            # Wait for all closes to complete
            self.ib.sleep(3)
        else:
            self.logger.info("✓ No open positions to close")

        # 3. Verify cleanup
        final_positions = [p for p in self.ib.positions() if p.position != 0]
        final_orders = self.ib.openOrders()

        if not final_positions and not final_orders:
            self.logger.info("=" * 80)
            self.logger.info("✅ SESSION CLEANUP COMPLETE - Starting fresh!")
            self.logger.info("=" * 80)
        else:
            self.logger.warning("=" * 80)
            self.logger.warning(f"⚠️  CLEANUP INCOMPLETE - {len(final_positions)} positions, {len(final_orders)} orders remain")
            self.logger.warning("=" * 80)

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            self.logger.info("✓ Disconnected from IBKR")

    def load_scanner_results(self):
        """
        Load today's scanner results (auto-detects correct date file)

        ENHANCED SCORING SUPPORT (Oct 6, 2025):
        - First tries to load enhanced scoring CSV (rescored_YYYYMMDD.csv)
        - Falls back to regular scanner JSON if enhanced scoring not found
        - Enhanced scoring provides tier classification and improved predictions
        """
        scanner_dir = Path(self.config['scanner']['output_dir'])

        # Check if we should use enhanced scoring from scanner_validation/
        enhanced_scoring_dir = Path(self.config['scanner'].get('enhanced_scoring_dir',
                                                                '../scanner_validation/'))

        today = datetime.now().strftime('%Y%m%d')

        # Try enhanced scoring first
        enhanced_file = f"rescored_{today}_v2.csv"  # v2 includes test count bonus
        enhanced_path = enhanced_scoring_dir / enhanced_file

        if enhanced_path.exists():
            self.logger.info(f"✓ Found enhanced scoring: {enhanced_file}")
            return self._load_enhanced_scoring(enhanced_path)

        # Try v1 enhanced scoring (without test count bonus)
        enhanced_file_v1 = f"rescored_{today}.csv"
        enhanced_path_v1 = enhanced_scoring_dir / enhanced_file_v1

        if enhanced_path_v1.exists():
            self.logger.info(f"✓ Found enhanced scoring (v1): {enhanced_file_v1}")
            return self._load_enhanced_scoring(enhanced_path_v1)

        # Fall back to regular scanner output
        self.logger.info(f"⚠️  Enhanced scoring not found, using regular scanner output")
        scanner_file = f"scanner_results_{today}.json"
        scanner_path = scanner_dir / scanner_file

        try:
            with open(scanner_path, 'r') as f:
                all_results = json.load(f)

            # Filter using strategy module
            self.watchlist = self.strategy.filter_scanner_results(all_results)

            # Store scanner file path for validation (FIX: Oct 14, 2025)
            self.scanner_results_file = str(scanner_path)

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

    def _load_enhanced_scoring(self, csv_path):
        """Load enhanced scoring CSV and apply tier-based filtering"""
        import csv

        try:
            all_results = []
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    stock = {}
                    for key, value in row.items():
                        if key in ['close', 'resistance', 'support', 'target1', 'target2', 'target3',
                                   'downside1', 'downside2', 'risk_reward', 'dist_to_R%', 'dist_to_S%',
                                   'rvol', 'atr%', 'score', 'enhanced_long_score', 'enhanced_short_score',
                                   'best_enhanced_score', 'pivot_width_pct', 'change%', 'volume',
                                   'volume_M', 'potential_gain%', 'risk%']:
                            try:
                                stock[key] = float(value) if value else 0.0
                            except ValueError:
                                stock[key] = 0.0
                        else:
                            stock[key] = value

                    # Use 'symbol' field (not 'Symbol')
                    if 'symbol' in stock:
                        all_results.append(stock)

            self.logger.info(f"✓ Loaded {len(all_results)} stocks from enhanced scoring")

            # Apply tier-based filtering
            self.watchlist = self.strategy.filter_enhanced_scanner_results(all_results)

            # Store scanner file path for validation (FIX: Oct 14, 2025)
            self.scanner_results_file = str(csv_path)

            self.logger.info(f"✓ Filtered to {len(self.watchlist)} setups after tier filtering")

            # Log watchlist with tier information
            for stock in self.watchlist:
                tier = self._classify_tier(stock)
                long_score = stock.get('enhanced_long_score', stock.get('score', 0))
                short_score = stock.get('enhanced_short_score', stock.get('score', 0))
                pivot_width = stock.get('pivot_width_pct', 0)

                self.logger.info(f"  [{stock['symbol']}] {tier} - "
                               f"LONG:{long_score:.0f} SHORT:{short_score:.0f} "
                               f"Pivot:{pivot_width:.2f}% "
                               f"R/R:{stock.get('risk_reward', 0):.2f}")

            return True

        except Exception as e:
            self.logger.error(f"✗ Error loading enhanced scoring: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    def _classify_tier(self, stock):
        """Classify stock into tiers based on enhanced scoring criteria"""
        pivot_width = stock.get('pivot_width_pct', 100)

        # Extract test count from breakout_reason
        import re
        breakout_reason = stock.get('breakout_reason', '')
        match = re.search(r'Tested (\d+)x', breakout_reason)
        test_count = int(match.group(1)) if match else 0

        # TIER 1: Tight pivot + heavy testing
        if pivot_width <= 2.5 and test_count >= 10:
            return "TIER 1 ⭐⭐⭐"

        # TIER 2: Good on one factor
        elif pivot_width <= 3.5 or test_count >= 5:
            return "TIER 2 ⭐⭐"

        # TIER 3: Weaker on both
        elif pivot_width <= 5.0:
            return "TIER 3 ⭐"

        # AVOID: Too wide
        else:
            return "AVOID ❌"

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
            return None, None, None

        # Get bars from buffer for strategy module
        bars = self.bar_buffers[symbol].get_bars_for_strategy()

        # CRITICAL FIX PART 2 (Oct 20, 2025):
        # Get BOTH absolute index (for state machine) and array index (for bar access)
        absolute_idx = self.bar_buffers[symbol].get_current_bar_index()  # For state tracking
        array_idx = self.bar_buffers[symbol].get_current_array_index()  # For bars[] access

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
        # Pass array_idx for bar access, absolute_idx for state machine
        # CRITICAL FIX PART 3 (Oct 20, 2025): Pass bar_buffer for candle mapping
        should_long, reason = self.strategy.should_enter_long(
            stock_data, current_price, long_attempts, bars=bars, current_idx=array_idx,
            absolute_idx=absolute_idx, bar_buffer=self.bar_buffers[symbol]
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
            # CRITICAL: reason can be a string or dict from check_hybrid_entry
            if isinstance(reason, dict):
                filter_name = reason.get('phase', 'unknown')
                reason_str = str(reason)
            else:
                filter_name = reason.split(':')[0] if ':' in reason else reason
                reason_str = reason
            self.analytics['filter_blocks'][filter_name] += 1

            # CRITICAL: Log filter blocks at INFO level when price is close to pivot
            # This helps understand why we DIDN'T enter a trade
            if abs(distance_to_resistance) < 1.0:  # Within 1% of pivot
                self.logger.info(f"  ❌ {symbol}: LONG blocked @ ${current_price:.2f} - {reason_str}")
            else:
                self.logger.debug(f"  {symbol}: LONG blocked - {reason_str}")

        # Check short pivot break using strategy module WITH ALL FILTERS
        # Pass array_idx for bar access, absolute_idx for state machine
        # CRITICAL FIX PART 3 (Oct 20, 2025): Pass bar_buffer for candle mapping
        should_short, reason = self.strategy.should_enter_short(
            stock_data, current_price, short_attempts, bars=bars, current_idx=array_idx,
            absolute_idx=absolute_idx, bar_buffer=self.bar_buffers[symbol]
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
            # CRITICAL: reason can be a string or dict from check_hybrid_entry
            if isinstance(reason, dict):
                filter_name = reason.get('phase', 'unknown')
                reason_str = str(reason)
            else:
                filter_name = reason.split(':')[0] if ':' in reason else reason
                reason_str = reason
            self.analytics['filter_blocks'][filter_name] += 1

            # CRITICAL: Log filter blocks at INFO level when price is close to pivot
            # This helps understand why we DIDN'T enter a trade
            if abs(distance_to_support) < 1.0:  # Within 1% of pivot
                self.logger.info(f"  ❌ {symbol}: SHORT blocked @ ${current_price:.2f} - {reason_str}")
            else:
                self.logger.debug(f"  {symbol}: SHORT blocked - {reason_str}")

        # Check BOUNCE long entry (pullback to support + reversal) - FEATURE #1 (Oct 9, 2025)
        # Only check if price near support (within 1%) and not already in position
        if symbol not in self.positions and long_attempts < self.strategy.max_attempts_per_pivot:
            if current_price > support * 0.99 and current_price < support * 1.01:
                bounce_confirmed, bounce_reason = self.strategy.check_bounce_setup(
                    bars, array_idx, support, side='LONG'
                )

                if bounce_confirmed:
                    self.logger.info(f"\n🔄 {symbol}: BOUNCE SIGNAL @ ${current_price:.2f}")
                    self.logger.info(f"   Bouncing off support: ${support:.2f}")
                    self.logger.info(f"   Attempt: {long_attempts + 1}/{self.strategy.max_attempts_per_pivot}")
                    self.logger.info(f"   Entry Path: {bounce_reason}")

                    # Track entry path
                    self.analytics['entry_paths'][bounce_reason] += 1

                    return 'LONG', support, bounce_reason

        # Check REJECTION short entry (failed breakout at resistance) - FEATURE #2 (Oct 9, 2025)
        # Only check if price near resistance (within 1%) and not already in position
        if symbol not in self.positions and short_attempts < self.strategy.max_attempts_per_pivot:
            if current_price < resistance * 1.01 and current_price > resistance * 0.99:
                rejection_confirmed, rejection_reason = self.strategy.check_rejection_setup(
                    bars, array_idx, resistance, side='SHORT'
                )

                if rejection_confirmed:
                    self.logger.info(f"\n⬇️  {symbol}: REJECTION SIGNAL @ ${current_price:.2f}")
                    self.logger.info(f"   Rejected at resistance: ${resistance:.2f}")
                    self.logger.info(f"   Attempt: {short_attempts + 1}/{self.strategy.max_attempts_per_pivot}")
                    self.logger.info(f"   Entry Path: {rejection_reason}")

                    # Track entry path
                    self.analytics['entry_paths'][rejection_reason] += 1

                    return 'SHORT', resistance, rejection_reason

        return None, None, None

    def calculate_position_size(self, entry_price, stop_price):
        """Calculate position size based on 1% risk"""
        return self.strategy.calculate_position_size(
            self.account_size,
            entry_price,
            stop_price
        )

    def check_margin_available(self, symbol, shares, price):
        """
        Check if sufficient margin available for trade

        CRITICAL FIX (Oct 10, 2025): Prevents IBKR Error 201 rejections

        Args:
            symbol: Stock symbol
            shares: Number of shares to buy/sell
            price: Entry price

        Returns:
            tuple: (is_available: bool, message: str)
        """
        try:
            # Query IBKR account summary for buying power
            account_values = self.ib.accountSummary()

            # Get buying power (available funds for new positions)
            buying_power = next((float(v.value) for v in account_values
                               if v.tag == 'BuyingPower'), None)

            if buying_power is None:
                self.logger.warning(f"  ⚠️  Could not query buying power - allowing trade (fail-open)")
                return True, "Unknown buying power"

            # Calculate required margin for this trade
            required_margin = shares * price

            # Check if sufficient margin available
            if required_margin > buying_power:
                return False, f"Insufficient margin: ${buying_power:,.2f} available, ${required_margin:,.2f} required (${required_margin - buying_power:,.2f} short)"

            # Sufficient margin available
            return True, f"${buying_power:,.2f} available, ${required_margin:,.2f} required"

        except Exception as e:
            self.logger.error(f"  ✗ Error checking margin: {e}")
            # On error, allow trade (fail-open to avoid blocking legitimate trades)
            return True, f"Error checking margin: {e}"

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

        # CRITICAL FIX (Oct 10, 2025): Check margin before placing order
        # Prevents IBKR Error 201 rejections that occurred on 3 trades today
        margin_ok, margin_msg = self.check_margin_available(symbol, shares, current_price)
        if not margin_ok:
            self.logger.warning(f"\n❌ {symbol} LONG REJECTED - {margin_msg}")
            return None

        self.logger.debug(f"  ✓ Margin check passed: {margin_msg}")

        # Create market order
        order = MarketOrder('BUY', shares)
        # Bypass IBKR direct routing warning (10311)
        order.outsideRth = False  # Only trade during regular hours

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

        # Get bars history from bar buffer (for candle-based stops - Oct 23, 2025)
        bars = self.bar_buffers[symbol].get_bars_for_strategy()
        entry_bar_idx = self.bar_buffers[symbol].get_current_array_index()

        # Create temporary position dict for stop calculation
        temp_position = {
            'entry_price': fill_price,
            'side': 'LONG',
            'partials': 0,
            'pivot': resistance  # Fallback pivot
        }

        # Calculate stop price using strategy module (supports both ATR and candle-based)
        # Oct 23, 2025: Now supports candle-based stops via config
        stop_price = self.strategy.calculate_stop_price(
            position=temp_position,
            current_price=fill_price,
            stock_data=stock_data,
            bars=bars,
            entry_bar_idx=entry_bar_idx
        )

        # Create position using position manager
        position = self.pm.create_position(
            symbol=symbol,
            side='LONG',
            entry_price=fill_price,
            shares=shares,
            pivot=stop_price,  # Use calculated stop (ATR or candle-based)
            contract=contract,
            target1=stock_data['target1'],
            target2=stock_data['target2']
        )

        # Add to local positions dict
        self.positions[symbol] = position

        # Calculate risk and room to target
        risk = fill_price - stop_price  # Use widened stop for risk calc
        room_to_target = stock_data['target1'] - fill_price
        room_pct = (room_to_target / fill_price) * 100

        self.logger.info(f"\n🟢 LONG {symbol} @ ${fill_price:.2f} ({now_et.strftime('%I:%M:%S %p')} ET)")
        self.logger.info(f"   Entry Path: {entry_reason}")
        self.logger.info(f"   Shares: {shares} | Risk: ${risk:.2f} | Room: {room_pct:.2f}%")
        self.logger.info(f"   Stop: ${stop_price:.2f} (pivot: ${resistance:.2f}) | Target1: ${stock_data['target1']:.2f}")

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

        # CRITICAL FIX (Oct 10, 2025): Check margin before placing order
        # Prevents IBKR Error 201 rejections that occurred on 3 trades today
        margin_ok, margin_msg = self.check_margin_available(symbol, shares, current_price)
        if not margin_ok:
            self.logger.warning(f"\n❌ {symbol} SHORT REJECTED - {margin_msg}")
            return None

        self.logger.debug(f"  ✓ Margin check passed: {margin_msg}")

        # Create market order
        order = MarketOrder('SELL', shares)
        # Bypass IBKR direct routing warning (10311)
        order.outsideRth = False  # Only trade during regular hours

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

        # Get bars history from bar buffer (for candle-based stops - Oct 23, 2025)
        bars = self.bar_buffers[symbol].get_bars_for_strategy()
        entry_bar_idx = self.bar_buffers[symbol].get_current_array_index()

        # Create temporary position dict for stop calculation
        temp_position = {
            'entry_price': fill_price,
            'side': 'SHORT',
            'partials': 0,
            'pivot': support  # Fallback pivot
        }

        # Calculate stop price using strategy module (supports both ATR and candle-based)
        # Oct 23, 2025: Now supports candle-based stops via config
        stop_price = self.strategy.calculate_stop_price(
            position=temp_position,
            current_price=fill_price,
            stock_data=stock_data,
            bars=bars,
            entry_bar_idx=entry_bar_idx
        )

        # Create position using position manager
        position = self.pm.create_position(
            symbol=symbol,
            side='SHORT',
            entry_price=fill_price,
            shares=shares,
            pivot=stop_price,  # Use calculated stop (ATR or candle-based)
            contract=contract,
            target1=stock_data.get('downside1', support * 0.98),
            target2=stock_data.get('downside2', support * 0.96)
        )

        # Add to local positions dict
        self.positions[symbol] = position

        # Calculate risk and room to target
        risk = stop_price - fill_price  # Use widened stop for risk calc
        room_to_target = fill_price - stock_data.get('downside1', support * 0.98)
        room_pct = (room_to_target / fill_price) * 100

        self.logger.info(f"\n🔴 SHORT {symbol} @ ${fill_price:.2f} ({now_et.strftime('%I:%M:%S %p')} ET)")
        self.logger.info(f"   Entry Path: {entry_reason}")
        self.logger.info(f"   Shares: {shares} | Risk: ${risk:.2f} | Room: {room_pct:.2f}%")
        self.logger.info(f"   Stop: ${stop_price:.2f} (pivot: ${support:.2f}) | Target1: ${stock_data.get('downside1', support * 0.98):.2f}")

        # Place stop order
        self.place_stop_order(position)

        return position

    def place_stop_order(self, position):
        """Place stop loss order with error handling"""
        symbol = position['symbol']
        # FIX (Oct 10, 2025): Round stop price to minimum tick size ($0.01 for stocks)
        # Prevents IBKR Warning 110: "price does not conform to minimum price variation"
        stop_price = round(position['stop'], 2)
        shares = int(position['shares'] * position['remaining'])

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Create stop order
        stop_order = StopOrder(action, shares, stop_price)

        # CRITICAL: Use SMART routing to avoid direct routing restrictions
        smart_contract = self.get_smart_contract(position['contract'])

        # Place order with error handling
        trade = self.resilience.safe_place_order(smart_contract, stop_order, f"{symbol} STOP")

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
        if not self.positions:
            return  # No positions to manage

        # Log that we're managing positions (INFO level for visibility)
        self.logger.debug(f"🔄 Managing {len(self.positions)} position(s)...")

        # FIX (Oct 10, 2025): Query IBKR portfolio once for all position validations
        # This prevents checking portfolio separately for each position (more efficient)
        try:
            portfolio = self.ib.portfolio()
            ibkr_symbols = {p.contract.symbol for p in portfolio}
        except Exception as e:
            self.logger.warning(f"  Could not query IBKR portfolio: {e}")
            ibkr_symbols = set()  # Empty set - won't trigger broker close detection

        for symbol in list(self.positions.keys()):
            position = self.positions[symbol]
            self.logger.debug(f"  Checking {symbol} {position['side']}...")

            # CRITICAL FIX (Oct 10, 2025): Detect broker-initiated closes
            # If position exists in our tracking but NOT in IBKR portfolio,
            # broker closed it (stop fill, margin call, liquidation, etc.)
            if ibkr_symbols and symbol not in ibkr_symbols:
                self.logger.warning(f"  ⚠️  {symbol}: NOT in IBKR portfolio - closed by broker")
                self.logger.warning(f"     Removing from tracking (already closed externally)")
                # Get current price for approximate P&L calculation
                stock_data = next((s for s in self.watchlist if s['symbol'] == symbol), None)
                current_price = float(stock_data['ticker'].last) if stock_data and stock_data['ticker'].last else position['entry_price']
                # Record trade with approximate exit price
                trade_record = self.pm.close_position(
                    symbol,
                    current_price,
                    'BROKER_CLOSE'
                )
                continue

            # Get current price
            stock_data = next((s for s in self.watchlist if s['symbol'] == symbol), None)
            if not stock_data:
                self.logger.warning(f"  ⚠️  {symbol}: No stock data in watchlist - skipping")
                continue

            if not stock_data['ticker'].last:
                self.logger.debug(f"  {symbol}: No price data yet - skipping")
                continue

            current_price = float(stock_data['ticker'].last)
            self.logger.debug(f"  {symbol}: Current price ${current_price:.2f}")

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

            # Log position state every 30 seconds at INFO level (changed from DEBUG every minute)
            # This gives us visibility without flooding logs
            if int(time_in_trade * 2) % 30 == 0:  # Every 30 seconds
                self.logger.info(f"  [{symbol}] {position['side']} @ ${position['entry_price']:.2f} | "
                                f"Current: ${current_price:.2f} ({gain_pct:+.2f}%) | "
                                f"Time: {int(time_in_trade)}m | "
                                f"Remaining: {int(position['remaining']*100)}% | "
                                f"P&L: ${unrealized_pnl:+.2f}")

            # ========================================================================
            # DYNAMIC RESISTANCE EXITS (Oct 15, 2025)
            # ========================================================================
            # Purpose: Take partials when price approaches technical resistance levels
            #          instead of waiting for arbitrary 1% or 2% profit targets
            #
            # Why: Stocks often stall/reverse at technical levels (SMAs, BB, LR)
            #      Taking partials BEFORE resistance locks profits
            #      Much smarter than fixed percentage targets
            #
            # How: Check hourly SMAs, Bollinger Bands, Linear Regression channels
            #      If resistance within 0.5% detected → take 25% partial
            #      Then activate trailing stop on remainder to capture further move
            #
            # Example: SOFI Oct 15, 2025
            #   - Entry: $28.55, Exit: $28.58 (15-min rule) = $10.50 profit ❌
            #   - WITH this feature:
            #     - Price $28.83, SMA50 @ $28.85 (0.07% away) = RESISTANCE!
            #     - Take 25% partial @ $28.83 = +$98 locked
            #     - Trail remainder @ 0.5% → capture move to $28.77 = +$231
            #     - Total: $329 profit (31x improvement!) ✅
            # ========================================================================

            config = self.config.get('trading', {}).get('exits', {}).get('dynamic_resistance_exits', {})
            if config.get('enabled', False):
                # Guard #1: Only check if position still has >25% remaining
                # Rationale: Don't check on final runner (let trailing stop handle it)
                if position.get('remaining', 1.0) > 0.25:
                    # Guard #2: Only check if we have minimum profit (default 0.5%)
                    # Rationale: Avoid checking on tiny moves that won't reach resistance
                    min_gain = config.get('min_gain_before_check', 0.005)  # 0.5%
                    if gain_pct / 100.0 >= min_gain:
                        self.logger.debug(f"  {symbol}: Checking overhead resistance (gain {gain_pct:.2f}%, remaining {position.get('remaining', 1.0)*100:.0f}%)...")

                        # Check for nearby resistance (SMAs, BB, LR on hourly bars)
                        has_resistance, resistance_level = self.strategy.check_overhead_resistance(
                            symbol, current_price
                        )

                        if has_resistance:
                            # Resistance detected! Extract details
                            level_price = resistance_level['price']
                            level_type = resistance_level['type']
                            distance_pct = resistance_level['distance_pct'] * 100

                            # Log detailed resistance detection
                            self.logger.info(f"\n🎯 RESISTANCE DETECTED: {symbol}")
                            self.logger.info(f"   Entry: ${position['entry_price']:.2f}")
                            self.logger.info(f"   Current: ${current_price:.2f} ({gain_pct:+.2f}%)")
                            self.logger.info(f"   {level_type}: ${level_price:.2f} (only {distance_pct:.2f}% away!)")
                            self.logger.info(f"   Remaining: {int(position.get('remaining', 1.0)*100)}%")

                            # ACTION 1: Take partial at resistance (default 25%)
                            partial_size = config.get('partial_size', 0.25)
                            self.logger.info(f"   💰 Taking {int(partial_size*100)}% partial to lock profits")
                            self.take_partial(position, current_price, partial_size, f'RESISTANCE_{level_type}')

                            # ACTION 2: Activate trailing stop on remainder if not already active
                            # Rationale: Let remainder capture additional move, but protect with trail
                            if not position.get('trailing_stop_active'):
                                trail_distance = config.get('trailing_distance_pct', 0.005)  # 0.5%

                                # Calculate new stop based on side
                                if position['side'] == 'LONG':
                                    new_stop = current_price * (1 - trail_distance)
                                else:  # SHORT
                                    new_stop = current_price * (1 + trail_distance)

                                # Update position tracking
                                position['stop'] = new_stop
                                position['trailing_stop_active'] = True
                                position['trailing_high'] = current_price  # Track high water mark

                                self.logger.info(f"   🔔 Trailing stop activated @ ${new_stop:.2f} ({trail_distance*100:.1f}% trail)")

                                # ACTION 3: Update stop order in IBKR with new quantity
                                # Important: After taking partial, remaining shares changed
                                try:
                                    # Cancel old stop order (has wrong quantity)
                                    if 'stop_order' in position and position['stop_order']:
                                        old_order = position['stop_order']
                                        self.ib.cancelOrder(old_order.order)
                                        self.ib.sleep(0.5)  # Wait for cancellation

                                    # Place new stop order with updated quantity and trail stop price
                                    self.place_stop_order(position)
                                    self.logger.info(f"   ✓ Updated stop order in IBKR (new qty: {int(position['shares'] * position['remaining'])} shares)")
                                except Exception as e:
                                    self.logger.error(f"   ✗ CRITICAL: Failed to update stop order: {e}")
                                    self.logger.error(f"      Position may be unprotected - MANUAL CHECK REQUIRED")
                            else:
                                self.logger.debug(f"  {symbol}: Trailing stop already active, skipping activation")

            # ========================================================================
            # TARGET-HIT STALL DETECTION (Oct 21, 2025 - Phase 9)
            # ========================================================================
            # Purpose: Detect when price stalls after hitting target1, tighten trail quickly
            #
            # Problem: After target hit, price often ranges for extended periods
            #          Example: PATH hit target1 $16.42, ranged for 86 min → $3 on runner
            #
            # Solution: Detect stall (0.2% range for 5+ min) → tighten trail 0.5% → 0.1%
            #          PATH example: Exit at $16.40 after 5 min vs $16.34 after 86 min
            #          Result: +$21 vs +$3 = 7x better on runner
            # ========================================================================

            config_stall = self.config.get('trading', {}).get('exits', {}).get('target_hit_stall_detection', {})
            if config_stall.get('enabled', False):
                # Check for stall after target hit
                is_stalled, new_trail_pct = self.strategy.check_target_hit_stall(
                    position, current_price, current_time
                )

                if is_stalled and new_trail_pct:
                    # STALL DETECTED! Tighten trailing stop dramatically
                    old_trail = position.get('trailing_distance', self.config['trading']['exits']['trailing_stop']['percentage'])

                    # Calculate new stop with tighter trail
                    if position['side'] == 'LONG':
                        new_stop = current_price * (1 - new_trail_pct)
                    else:  # SHORT
                        new_stop = current_price * (1 + new_trail_pct)

                    old_stop = position['stop']
                    position['stop'] = new_stop
                    position['trailing_distance'] = new_trail_pct

                    self.logger.info(f"\n⏸️  STALL DETECTED: {symbol}")
                    self.logger.info(f"   Entry: ${position['entry_price']:.2f}")
                    self.logger.info(f"   Current: ${current_price:.2f} ({gain_pct:+.2f}%)")
                    self.logger.info(f"   Target1: ${position.get('target1', 0):.2f} (hit!)")
                    self.logger.info(f"   Stall Range: {position['stall_window_high']:.2f} - {position['stall_window_low']:.2f}")
                    self.logger.info(f"   Duration: {int((current_time - position['stall_window_start']).total_seconds() / 60)} minutes")
                    self.logger.info(f"   🔔 Tightening trail: {old_trail*100:.1f}% → {new_trail_pct*100:.1f}%")
                    self.logger.info(f"   🛡️  New stop: ${old_stop:.2f} → ${new_stop:.2f}")

                    # Update IBKR stop order with tighter stop
                    stop_canceled = False
                    if 'stop_order' in position and position['stop_order']:
                        try:
                            old_order = position['stop_order']
                            self.ib.cancelOrder(old_order.order)
                            self.ib.sleep(0.5)
                            self.logger.info(f"   ✓ Cancelled old stop order")
                            stop_canceled = True
                        except Exception as e:
                            self.logger.error(f"   ✗ Could not cancel old stop order: {e}")

                    # Place new stop order with tightened trail
                    if stop_canceled or not ('stop_order' in position and position['stop_order']):
                        success = self.place_stop_order(position)
                        if success:
                            self.logger.info(f"   ✓ Placed tightened stop order @ ${new_stop:.2f}")
                        else:
                            self.logger.error(f"   ✗ CRITICAL: Failed to place tightened stop order")

            # Check 15-minute rule (PS60 methodology - exit stuck positions)
            self.logger.debug(f"  {symbol}: Checking 15-minute rule (time in trade: {int(time_in_trade)}m)...")
            should_exit, reason = self.strategy.check_fifteen_minute_rule(
                position, current_price, current_time
            )
            self.logger.debug(f"  {symbol}: 15-min rule result: {should_exit}, reason: {reason}")
            if should_exit:
                # NEW (Oct 31, 2025): Instead of exiting, tighten stop to 2 ticks above entry
                # This gives position more time while protecting against reversals
                if not position.get('seven_min_stop_tightened', False):
                    tick_size = 0.01  # Standard US stock tick
                    ticks_buffer = 2

                    if position['side'] == 'LONG':
                        # Move stop 2 ticks above entry (near breakeven)
                        new_stop = position['entry_price'] + (tick_size * ticks_buffer)
                    else:  # SHORT
                        # Move stop 2 ticks below entry (near breakeven)
                        new_stop = position['entry_price'] - (tick_size * ticks_buffer)

                    old_stop = position['stop']
                    position['stop'] = new_stop
                    position['seven_min_stop_tightened'] = True  # Mark as triggered

                    self.logger.info(f"\n⏱️  7-MINUTE RULE TRIGGERED: {symbol}")
                    self.logger.info(f"   Entry: ${position['entry_price']:.2f} @ {position['entry_time'].strftime('%I:%M:%S %p')} ET")
                    self.logger.info(f"   Current: ${current_price:.2f} ({gain_pct:+.2f}%) after {int(time_in_trade)} minutes")
                    self.logger.info(f"   Reason: {reason}")
                    self.logger.info(f"   Action: TIGHTENED STOP ${old_stop:.2f} → ${new_stop:.2f} ({ticks_buffer} ticks from entry)")

                    # Update IBKR stop order (if live trading)
                    if hasattr(self, 'ib') and self.ib.isConnected():
                        self.cancel_and_replace_stop_order(position)

                    continue
                # If stop was already tightened and still no progress, let normal stop logic handle it

            # Check for partial profit
            self.logger.debug(f"  {symbol}: Checking for partial profit...")
            should_partial, pct, reason = self.strategy.should_take_partial(
                position, current_price
            )
            self.logger.debug(f"  {symbol}: Partial check result: {should_partial}, pct: {pct}, reason: {reason}")
            if should_partial:
                self.logger.info(f"  💰 {symbol}: Taking {int(pct*100)}% partial - {reason}")
                self.take_partial(position, current_price, pct, reason)

                # ═══════════════════════════════════════════════════════════════════════════
                # DYNAMIC PIVOT UPDATES - STEP 2: Target Progression (Oct 28, 2025)
                # ═══════════════════════════════════════════════════════════════════════════
                # Check if Target1 was hit and update pivot to Target1 for Target2 run
                if self.strategy.check_target_progression_pivot(position, current_price):
                    self.logger.info(f"📊 {symbol}: Pivot updated to Target1 after hit")

                # Move stop to breakeven after partial (if configured)
                if self.strategy.should_move_stop_to_breakeven(position):
                    old_stop = position['stop']
                    position['stop'] = position['entry_price']

                    # CRITICAL: Cancel old stop order and place new one with updated quantity
                    stop_canceled = False
                    if 'stop_order' in position and position['stop_order']:
                        try:
                            old_order = position['stop_order']
                            self.ib.cancelOrder(old_order.order)
                            # Wait for cancellation confirmation
                            self.ib.sleep(0.5)
                            self.logger.info(f"  ✓ Cancelled old stop order for {symbol} (Order ID: {old_order.order.orderId})")
                            stop_canceled = True
                        except Exception as e:
                            self.logger.error(f"  ✗ CRITICAL: Could not cancel old stop order for {symbol}: {e}")
                            self.logger.error(f"    Old stop may still be active - MANUAL CHECK REQUIRED")
                    else:
                        self.logger.warning(f"  ⚠️  No stop order found in position for {symbol} - cannot cancel")

                    # Place new stop order with correct remaining shares
                    if stop_canceled or not ('stop_order' in position and position['stop_order']):
                        success = self.place_stop_order(position)
                        if success:
                            self.logger.info(f"  🛡️  {symbol}: Stop moved ${old_stop:.2f} → ${position['stop']:.2f} (breakeven)")
                        else:
                            self.logger.error(f"  ✗ CRITICAL: Failed to place new stop order for {symbol} at breakeven")
                    else:
                        self.logger.error(f"  ✗ CRITICAL: Skipping new stop placement - old stop not canceled for {symbol}")

            # Update trailing stop for runners (CRITICAL FEATURE #3 - Oct 9, 2025)
            self.logger.debug(f"  {symbol}: Checking trailing stop update...")
            stop_updated, new_stop, trail_reason = self.strategy.update_trailing_stop(
                position, current_price
            )
            self.logger.debug(f"  {symbol}: Trailing stop update result: {stop_updated}")
            if stop_updated:
                old_stop = position['stop']
                position['stop'] = new_stop
                self.logger.info(f"   ⬆️  {symbol}: {trail_reason}")

                # Update stop order with IBKR
                stop_canceled = False
                if 'stop_order' in position and position['stop_order']:
                    try:
                        old_order = position['stop_order']
                        self.ib.cancelOrder(old_order.order)
                        self.ib.sleep(0.5)
                        self.logger.debug(f"  ✓ Cancelled old stop order for {symbol} (trailing)")
                        stop_canceled = True
                    except Exception as e:
                        self.logger.error(f"  ✗ Could not cancel old stop order for {symbol}: {e}")

                # Place new stop order with trailing stop price
                if stop_canceled or not ('stop_order' in position and position['stop_order']):
                    success = self.place_stop_order(position)
                    if success:
                        self.logger.info(f"  🛡️  {symbol}: Trailing stop updated ${old_stop:.2f} → ${new_stop:.2f}")
                    else:
                        self.logger.error(f"  ✗ Failed to place new trailing stop order for {symbol}")

            # Check trailing stop hit (CRITICAL FEATURE #3 - Oct 9, 2025)
            self.logger.debug(f"  {symbol}: Checking if trailing stop hit...")
            trail_hit, trail_reason = self.strategy.check_trailing_stop_hit(
                position, current_price
            )
            self.logger.debug(f"  {symbol}: Trailing stop hit result: {trail_hit}")
            if trail_hit:
                self.logger.info(f"   🎯 {symbol}: {trail_reason} - closing runner")
                trade = self.close_position(position, current_price, trail_reason)
                continue

            # CRITICAL: Check if stop order was filled by IBKR (Oct 10, 2025)
            # This was missing - stops would fill but position wouldn't be removed
            if 'stop_order' in position and position['stop_order']:
                stop_order = position['stop_order']
                if stop_order.orderStatus.status == 'Filled':
                    self.logger.info(f"   🛑 {symbol}: Stop order FILLED by IBKR @ ${stop_order.orderStatus.avgFillPrice:.2f}")
                    self.logger.info(f"      Position was stopped out - removing from tracker")
                    # Close position in our tracking (already closed by IBKR)
                    trade = self.close_position(position, stop_order.orderStatus.avgFillPrice, 'STOP_HIT')
                    continue

    def get_smart_contract(self, contract):
        """
        Convert contract to use SMART routing

        CRITICAL: IBKR returns contracts with actual exchange (NYSE, NASDAQ, etc)
        but we need SMART routing to avoid direct routing restrictions
        """
        return Stock(contract.symbol, 'SMART', 'USD')

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
        # Bypass IBKR direct routing warning (10311)
        order.outsideRth = False  # Only trade during regular hours

        # CRITICAL: Use SMART routing to avoid direct routing restrictions
        smart_contract = self.get_smart_contract(position['contract'])
        trade = self.ib.placeOrder(smart_contract, order)

        # Record partial using position manager
        partial_record = self.pm.take_partial(symbol, price, pct, reason)

        self.logger.info(f"  💰 PARTIAL {int(pct*100)}% {symbol} @ ${price:.2f} "
                        f"(+${partial_record['gain']:.2f}, {reason})")

        # FIX (Oct 10, 2025): Remove position if fully closed via partials
        # Before this fix, positions with remaining=0.0 stayed in tracking indefinitely
        if position['remaining'] <= 0:
            self.logger.info(f"  ✓ {symbol}: Position fully closed via partials (remaining={position['remaining']})")
            # Record final trade closure
            trade_record = self.pm.close_position(symbol, price, 'FULL_PARTIALS')
            # Remove from local tracking
            if symbol in self.positions:
                del self.positions[symbol]
            self.logger.info(f"  ✓ {symbol}: Removed from position tracking")

    def close_position(self, position, price, reason):
        """Close entire position and return trade object with error handling"""
        symbol = position['symbol']
        shares = int(position['shares'] * position['remaining'])

        if shares == 0:
            del self.positions[symbol]
            return None

        # CRITICAL FIX (Oct 14, 2025): Cancel stop-loss order BEFORE closing position
        # Prevents orphaned stops from triggering after position is closed
        if 'stop_order' in position and position['stop_order']:
            try:
                stop_order = position['stop_order']
                self.ib.cancelOrder(stop_order.order)
                self.ib.sleep(0.5)  # Wait for cancellation
                self.logger.info(f"  ✓ Cancelled stop order for {symbol} (Order ID: {stop_order.order.orderId})")
            except Exception as e:
                self.logger.error(f"  ✗ CRITICAL: Failed to cancel stop order for {symbol}: {e}")
                self.logger.error(f"    Stop may still be active - MANUAL CHECK REQUIRED")

        if position['side'] == 'LONG':
            action = 'SELL'
        else:
            action = 'BUY'

        # Place market order with error handling
        order = MarketOrder(action, shares)
        # Bypass IBKR direct routing warning (10311)
        order.outsideRth = False  # Only trade during regular hours

        # CRITICAL: Use SMART routing to avoid direct routing restrictions
        smart_contract = self.get_smart_contract(position['contract'])
        trade = self.resilience.safe_place_order(smart_contract, order, f"{symbol} CLOSE")

        if not trade:
            self.logger.error(f"✗ Failed to close {symbol} position")
            self.logger.error(f"  ⚠️  Manual intervention required to close {shares} shares")
            # Don't remove from positions - will retry on next iteration
            return None

        # Close position and record trade using position manager
        trade_record = self.pm.close_position(symbol, price, reason)

        self.logger.info(f"  🛑 CLOSE {symbol} @ ${price:.2f} ({reason})")

        # ═══════════════════════════════════════════════════════════════════════════
        # DYNAMIC PIVOT UPDATES - STEP 3: Failure Update (Oct 28, 2025)
        # ═══════════════════════════════════════════════════════════════════════════
        # Check if trade failed and update pivot to session high for retry
        stock = next((s for s in self.watchlist if s['symbol'] == symbol), None)
        if stock and self.strategy.check_failure_and_update_pivot(stock, price, reason):
            self.logger.info(f"📊 {symbol}: Pivot updated after failure, attempts reset")

        # Check if trade_record is valid before accessing
        if trade_record:
            self.logger.info(f"     P&L: ${trade_record['pnl']:.2f}")
        else:
            self.logger.warning(f"     ⚠️  Trade record not available for {symbol}")

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

    def reconcile_portfolio(self):
        """
        Check for orphaned positions in IBKR that aren't being tracked.

        Orphaned positions occur when:
        - Stop orders get filled but position tracking fails
        - Manual trades are placed
        - Trader restarts and recovery fails

        These positions are CLOSED IMMEDIATELY to prevent unmanaged risk.
        """
        try:
            # Get all non-zero positions from IBKR
            ibkr_portfolio = {
                item.contract.symbol: item
                for item in self.ib.portfolio()
                if item.position != 0
            }

            # Find positions in IBKR but not in our tracking
            orphaned = []
            for symbol, portfolio_item in ibkr_portfolio.items():
                if symbol not in self.positions:
                    orphaned.append((symbol, portfolio_item))

            if not orphaned:
                return  # All good

            # Log and close orphaned positions
            self.logger.warning("")
            self.logger.warning("="*80)
            self.logger.warning("⚠️  ORPHANED POSITIONS DETECTED")
            self.logger.warning("="*80)

            for symbol, portfolio_item in orphaned:
                position = portfolio_item.position
                avg_cost = portfolio_item.averageCost
                market_price = portfolio_item.marketPrice
                unrealized_pnl = portfolio_item.unrealizedPNL

                side = "LONG" if position > 0 else "SHORT"
                shares = abs(position)

                self.logger.warning(f"")
                self.logger.warning(f"📍 {symbol}: {side} {shares} shares @ ${avg_cost:.2f}")
                self.logger.warning(f"   Current Price: ${market_price:.2f}")
                self.logger.warning(f"   Unrealized P&L: ${unrealized_pnl:+.2f}")
                self.logger.warning(f"   ⚠️  This position is NOT being managed by current session")
                self.logger.warning(f"   🛑 CLOSING IMMEDIATELY to prevent unmanaged risk")

                # Close the orphaned position
                try:
                    contract = self.get_smart_contract(portfolio_item.contract)
                    action = 'SELL' if position > 0 else 'BUY'
                    order = MarketOrder(action, shares)

                    trade = self.resilience.safe_place_order(
                        contract, order, f"{symbol} ORPHAN_CLOSE"
                    )

                    if trade:
                        self.logger.warning(f"   ✓ Orphan close order placed: {action} {shares} {symbol}")
                    else:
                        self.logger.error(f"   ✗ Failed to close orphaned {symbol} position")
                        self.logger.error(f"   ⚠️  MANUAL INTERVENTION REQUIRED")

                except Exception as e:
                    self.logger.error(f"   ✗ Error closing orphaned {symbol}: {e}")
                    self.logger.error(f"   ⚠️  MANUAL INTERVENTION REQUIRED")

            self.logger.warning("="*80)
            self.logger.warning("")

        except Exception as e:
            self.logger.error(f"Error during portfolio reconciliation: {e}")
            self.logger.exception("Full traceback:")

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

        # CRITICAL FIX (Oct 15, 2025): Set IB connection on strategy AFTER connecting
        # This allows SMACalculator and StochasticCalculator to initialize properly
        self.strategy.ib = self.ib

        # Re-initialize SMA calculator now that IB is connected
        if self.strategy.use_sma_target_partials and self.strategy.sma_enabled:
            try:
                from strategy.sma_calculator import SMACalculator
                self.strategy.sma_calculator = SMACalculator(
                    self.ib,
                    cache_duration_sec=self.strategy.sma_cache_duration
                )
                self.logger.info(f"✓ SMA calculator initialized (timeframe: {self.strategy.sma_timeframe}, periods: {self.strategy.sma_periods})")
            except Exception as e:
                self.logger.warning(f"⚠️  Failed to initialize SMA calculator: {e}")
                self.strategy.sma_calculator = None

        # Re-initialize Stochastic calculator now that IB is connected (Oct 15, 2025)
        if self.strategy.stochastic_enabled:
            try:
                from strategy.stochastic_calculator import StochasticCalculator
                self.strategy.stochastic_calculator = StochasticCalculator(
                    self.ib,
                    k_period=self.strategy.stochastic_k_period,
                    k_smooth=self.strategy.stochastic_k_smooth,
                    d_smooth=self.strategy.stochastic_d_smooth,
                    cache_duration_sec=self.strategy.stochastic_cache_duration
                )
                self.logger.info(f"✓ Stochastic calculator initialized ({self.strategy.stochastic_k_period}, {self.strategy.stochastic_k_smooth}, {self.strategy.stochastic_d_smooth})")
                self.logger.info(f"  LONG: K={self.strategy.stochastic_long_min_k}-{self.strategy.stochastic_long_max_k}, SHORT: K={self.strategy.stochastic_short_min_k}-{self.strategy.stochastic_short_max_k}")
            except Exception as e:
                self.logger.warning(f"⚠️  Failed to initialize stochastic calculator: {e}")
                self.strategy.stochastic_calculator = None

        # CRITICAL: Clean up any existing positions/orders before starting (Oct 13, 2025)
        self.cleanup_session()

        # Load scanner results
        if not self.load_scanner_results():
            self.disconnect()
            return

        # Subscribe to market data
        self.subscribe_market_data()

        # CRITICAL: Recover state from previous session (crash recovery)
        # This must happen AFTER connecting to IBKR and subscribing to data
        self.state_manager.recover_full_state()

        # FIX GAP #6: Run startup validation (Oct 13, 2025)
        validation_ok, validation_msg = self.validate_startup()
        if not validation_ok:
            self.logger.error("\n❌ STARTUP VALIDATION FAILED")
            self.logger.error(validation_msg)
            self.logger.error("\n🛑 Cannot start trading - fix issues above and restart")
            self.disconnect()
            return

        # Wait for market open if before 9:30 AM ET
        market_open_time = dt_time(9, 30)
        while now_et.time() < market_open_time:
            try:
                # Create timezone-aware market open time
                market_open_dt = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
                wait_seconds = (market_open_dt - now_et).total_seconds()
                self.logger.info(f"Waiting for market open... ({int(wait_seconds/60)} minutes)")

                # Check IBKR connection health every 5 minutes
                if int(wait_seconds/60) % 5 == 0:
                    if not self.ib.isConnected():
                        self.logger.error("IBKR connection lost during wait! Attempting reconnect...")
                        if not self.connect():
                            self.logger.error("Reconnection failed. Exiting.")
                            return
                        self.logger.info("✓ Reconnected to IBKR")
                    else:
                        self.logger.info(f"✓ IBKR connection healthy (waiting for market open)")

                time_module.sleep(min(60, wait_seconds))
                now_et = datetime.now(pytz.UTC).astimezone(eastern)
            except Exception as e:
                self.logger.error(f"Error during market open wait: {e}")
                self.logger.exception("Full traceback:")
                return

        # Check gap filter at market open (CRITICAL - Oct 5, 2025)
        self.check_gap_filter_at_open()

        # ═══════════════════════════════════════════════════════════════════════════
        # DYNAMIC PIVOT UPDATES - STEP 1: Gap Detection at Initialization (Oct 28, 2025)
        # ═══════════════════════════════════════════════════════════════════════════
        # Check if stocks gapped above pivot and update to session high
        # This runs when TRADER INITIALIZES (not just at 9:30 AM market open)
        # So if you start trader at 10 AM and stock gapped, it still detects it
        pivot_updates_count = 0
        for stock in self.watchlist:
            # Get current price from ticker
            current_price = float(stock['ticker'].last) if stock['ticker'].last else stock['resistance']

            # Check gap and update pivot if needed
            if self.strategy.check_gap_and_update_pivot(stock, current_price, now_et):
                pivot_updates_count += 1

        if pivot_updates_count > 0:
            self.logger.info(f"\n📊 Dynamic Pivots: Updated {pivot_updates_count} stocks (gap condition detected)")

        # Record session start
        self.analytics['session_start'] = datetime.now(pytz.UTC).astimezone(eastern)

        self.logger.info("\n" + "="*80)
        self.logger.info("MONITORING STARTED - ALL FILTERS ACTIVE")
        self.logger.info("="*80)
        self.logger.info("Active Filters:")
        self.logger.info(f"  ✓ Choppy Market Filter: {self.strategy.enable_choppy_filter}")
        self.logger.info(f"  ✓ Room-to-Run Filter: {self.strategy.enable_room_to_run_filter}")
        self.logger.info(f"  ✓ Sustained Break Logic: {self.strategy.sustained_break_enabled}")
        self.logger.info(f"  ✓ Stochastic Filter: {self.strategy.stochastic_enabled}")
        if self.strategy.stochastic_enabled:
            self.logger.info(f"    - LONG: K={self.strategy.stochastic_long_min_k}-{self.strategy.stochastic_long_max_k}")
            self.logger.info(f"    - SHORT: K={self.strategy.stochastic_short_min_k}-{self.strategy.stochastic_short_max_k}")
        self.logger.info(f"  ✓ 8-Minute Rule: Active")
        self.logger.info(f"  ✓ Max Attempts: {self.strategy.max_attempts_per_pivot}")
        self.logger.info(f"  ✓ Entry Window: {self.strategy.min_entry_time} - {self.strategy.max_entry_time}")
        self.logger.info("="*80)
        self.logger.info(f"\n💡 TIP: Set log level to DEBUG to see all filter decisions")
        self.logger.info(f"    Edit config: logging.log_level = 'DEBUG'")
        self.logger.info("="*80)

        try:
            while True:
                # FIX GAP #7: Check for shutdown signal (Oct 13, 2025)
                if self.shutdown_requested:
                    self.logger.info("Shutdown signal detected in main loop")
                    break

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

                # CRITICAL: Check for orphaned positions every 60 seconds
                if self.analytics['price_updates'] % 60 == 0:  # Every 60 seconds
                    self.reconcile_portfolio()

                # Log market activity every 5 minutes
                if self.analytics['price_updates'] % 300 == 0:  # Every 5 minutes (at 1 update/sec)
                    eastern = pytz.timezone('US/Eastern')
                    now_et = datetime.now(pytz.UTC).astimezone(eastern)
                    self.logger.info(f"\n⏰ {now_et.strftime('%I:%M %p')} ET - Market Activity Check:")
                    self.logger.info(f"   Open Positions: {len(self.positions)}")
                    self.logger.info(f"   Monitoring: {len(self.watchlist)} symbols")
                    if self.positions:
                        for symbol, pos in self.positions.items():
                            # Get current price from position's stock data
                            stock_data = pos.get('stock_data')
                            if stock_data and stock_data['ticker'].last:
                                current_price = float(stock_data['ticker'].last)
                                if pos['side'] == 'LONG':
                                    gain = ((current_price - pos['entry_price']) / pos['entry_price']) * 100
                                else:
                                    gain = ((pos['entry_price'] - current_price) / pos['entry_price']) * 100
                                self.logger.info(f"   {symbol}: {pos['side']} @ ${pos['entry_price']:.2f} -> ${current_price:.2f} ({gain:+.2f}%)")

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
                if self.positions:
                    # Only log if we have positions (avoid spam)
                    if self.analytics['price_updates'] % 10 == 0:  # Every 10 seconds
                        eastern = pytz.timezone('US/Eastern')
                        now_et = datetime.now(pytz.UTC).astimezone(eastern)
                        self.logger.debug(f"[{now_et.strftime('%I:%M:%S %p')}] Calling manage_positions() for {len(self.positions)} position(s)")
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
                # Handle both string and datetime objects
                entry_time = trade['entry_time']
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)

                exit_time = trade['exit_time']
                if isinstance(exit_time, str):
                    exit_time = datetime.fromisoformat(exit_time)

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
            # FIX GAP #8: Calculate session duration (Oct 13, 2025)
            duration_seconds = 0
            if self.analytics['session_start'] and self.analytics['session_end']:
                duration_seconds = (self.analytics['session_end'] - self.analytics['session_start']).total_seconds()

            save_data = {
                'summary': summary,
                'analytics': {
                    'session_start': self.analytics['session_start'].isoformat() if self.analytics['session_start'] else None,
                    'session_end': self.analytics['session_end'].isoformat() if self.analytics['session_end'] else None,
                    'duration_seconds': duration_seconds,
                    'duration_minutes': round(duration_seconds / 60, 2),
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

            # Convert datetime objects to strings for JSON serialization
            def serialize_datetimes(obj):
                if isinstance(obj, dict):
                    return {k: serialize_datetimes(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [serialize_datetimes(item) for item in obj]
                elif isinstance(obj, datetime):
                    return obj.isoformat()
                else:
                    return obj

            serialized_data = serialize_datetimes(save_data)

            with open(trade_file, 'w') as f:
                json.dump(serialized_data, f, indent=2)

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


# Global trader instance for signal handlers
trader_instance = None

def graceful_shutdown(signum, frame):
    """
    Graceful shutdown handler for SIGINT (Ctrl+C) and SIGTERM
    Closes all positions, saves state, and exits cleanly (Oct 13, 2025)
    """
    global trader_instance

    if trader_instance is None:
        print("\n⚠️  No active trader session to shut down")
        sys.exit(0)

    print("\n" + "="*80)
    print("🛑 GRACEFUL SHUTDOWN INITIATED")
    print("="*80)

    try:
        # 1. Close all open positions
        if trader_instance.positions:
            trader_instance.logger.info(f"📊 Closing {len(trader_instance.positions)} open positions...")
            trader_instance.close_all_positions('SHUTDOWN')

        # 2. Save current state
        trader_instance.logger.info("💾 Saving session state...")
        trader_instance.state_manager.save_state()

        # 3. Generate final report
        trader_instance.logger.info("📊 Generating final report...")
        trader_instance.print_session_summary()

        # 4. Disconnect from IBKR
        trader_instance.logger.info("🔌 Disconnecting from IBKR...")
        trader_instance.disconnect()

        print("="*80)
        print("✅ GRACEFUL SHUTDOWN COMPLETE")
        print("   Session state saved for potential restart")
        print("="*80)

    except Exception as e:
        print(f"❌ Error during shutdown: {e}")
        import traceback
        traceback.print_exc()
    finally:
        sys.exit(0)


def main():
    global trader_instance

    parser = argparse.ArgumentParser(description='PS60 Live Trader')
    parser.add_argument('--config', default='config/trader_config.yaml',
                       help='Path to configuration file')

    args = parser.parse_args()

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl+C
    signal.signal(signal.SIGTERM, graceful_shutdown)  # kill command

    try:
        trader_instance = PS60Trader(args.config)
        trader_instance.run()
    except KeyboardInterrupt:
        # This shouldn't normally be reached due to signal handler
        graceful_shutdown(None, None)
    except Exception as e:
        if trader_instance:
            trader_instance.logger.error(f"Fatal error in main: {e}")
            trader_instance.logger.exception("Full traceback:")
            # Try to save state even on error
            try:
                trader_instance.state_manager.save_state()
            except:
                pass
        raise


if __name__ == '__main__':
    main()
