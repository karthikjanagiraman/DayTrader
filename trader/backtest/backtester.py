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
import pytz
import logging

# Import shared strategy module
sys.path.append(str(Path(__file__).parent.parent))
from strategy import PS60Strategy, PositionManager
from data_processor import DataProcessor
from utils import EntryDecisionLogger, capture_filter_data

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

        # Initialize strategy WITHOUT IB connection (will be set after connect())
        # CRITICAL FIX (Oct 15, 2025): Don't pass IB connection until after connect()
        # SMACalculator requires connected IB instance, which isn't ready during __init__
        # For backtesting with 1-minute bars (Oct 22, 2025)
        self.strategy = PS60Strategy(self.config, ib_connection=None, bar_size_seconds=60)
        self.pm = PositionManager()

        # Track trades for backtest results
        self.trades = []

        # CVD Filter Analytics (Oct 19, 2025)
        self.cvd_analytics = {
            'total_blocks': 0,
            'long_blocks': 0,
            'short_blocks': 0,
            'blocks_by_reason': {},  # {'BULLISH trend blocking SHORT': count}
            'symbols_blocked': set()  # Track which symbols were blocked
        }

        # In-memory cache for bars (avoids re-reading from disk)
        self.bars_cache = {}

        # Cache for hourly momentum bars (Oct 7, 2025) - Performance optimization
        # Hourly bars don't change during backtest day, so fetch once and reuse
        self.hourly_bars_cache = {}

        # Cache for historical ticks (Oct 21, 2025) - CVD improvement
        # Stores tick data for CVD calculation: {(symbol, timestamp): [tick_list]}
        # Used for recent backtests (<60 days) to match live trading CVD accuracy
        self.tick_cache = {}
        self.use_tick_based_cvd = self.config.get('backtest', {}).get('use_tick_based_cvd', True)
        self.tick_cache_enabled = self.config.get('backtest', {}).get('tick_cache_enabled', True)

        # Cache for CVD-enriched bars (Oct 21, 2025) - Pre-built CVD data
        # Stores complete bar + CVD data: {symbol: cvd_enriched_bars_dict}
        # Allows backtesting without IBKR after initial build
        self.cvd_enriched_bars = {}

        # Direction filters (for testing scanner quality)
        self.enable_shorts = self.config['trading'].get('enable_shorts', True)
        self.enable_longs = self.config['trading'].get('enable_longs', True)

        # Entry Decision Logger (Oct 25, 2025)
        # Logs ALL entry attempts (entered + blocked) with complete filter data
        self.entry_logger = EntryDecisionLogger(self.test_date)

        # Slippage simulation (per requirements - use strategy config)
        self.entry_slippage = self.strategy.slippage_pct if self.strategy.slippage_enabled else 0.0
        self.stop_slippage = self.strategy.slippage_pct * 2 if self.strategy.slippage_enabled else 0.0  # Stops get worse fills
        self.exit_slippage = self.strategy.slippage_pct if self.strategy.slippage_enabled else 0.0

        # Commission costs (per requirements)
        self.commission_per_share = self.strategy.commission_per_share if self.strategy.commission_enabled else 0.0

        # Setup logging
        self._setup_logging()

        # CRITICAL FIX (Oct 14, 2025): Pass logger to strategy for filter visibility
        # Enables room-to-run and directional volume filter logging in backtest context
        self.strategy.logger = self.logger

        # Load scanner results
        print(f"\n{'='*80}")
        print(f"PS60 BACKTEST - {self.test_date}")
        print(f"{'='*80}")
        print(f"Scanner file: {scanner_file}")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"PS60 BACKTEST - {self.test_date}")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"Scanner file: {scanner_file}")

        # Check if it's enhanced scoring CSV or regular JSON
        if scanner_file.endswith('.csv'):
            print(f"✓ Detected enhanced scoring CSV")
            self.scanner_results = self._load_enhanced_scoring_csv(scanner_file)
            self.using_enhanced_scoring = True
        else:
            with open(scanner_file) as f:
                self.scanner_results = json.load(f)
            self.using_enhanced_scoring = False

        print(f"Loaded {len(self.scanner_results)} scanner results")

    def _load_enhanced_scoring_csv(self, csv_path):
        """Load enhanced scoring CSV for backtesting"""
        import csv

        results = []
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

                # Use 'symbol' field
                if 'symbol' in stock:
                    results.append(stock)

        return results

    def _setup_logging(self):
        """Setup logging to file and console with DEBUG level"""
        # Create logs directory
        logs_dir = Path(__file__).parent / 'logs'
        logs_dir.mkdir(exist_ok=True)

        # Create log filename with date
        date_str = self.test_date.strftime('%Y%m%d')
        timestamp = datetime.now().strftime('%H%M%S')
        log_file = logs_dir / f'backtest_{date_str}_{timestamp}.log'

        # Setup logger
        self.logger = logging.getLogger('PS60Backtester')
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self.logger.handlers.clear()

        # File handler (DEBUG level)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console handler (INFO level to avoid cluttering console)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        self.logger.info(f"Logging initialized: {log_file}")

    def connect(self):
        """Connect to IBKR"""
        try:
            # PERFORMANCE FIX (Oct 19, 2025): Use timestamp-based client ID to avoid conflicts
            import time
            client_id = 3000 + int(time.time() % 1000)  # 3000-3999 range
            self.ib.connect('127.0.0.1', 7497, clientId=client_id)
            print(f"✓ Connected to IBKR (Client ID: {client_id})")

            # CRITICAL FIX (Oct 15, 2025): Set IB connection on strategy AFTER connecting
            # This allows SMACalculator to initialize properly with connected instance
            self.strategy.ib = self.ib

            # Re-initialize SMA calculator now that IB is connected
            if self.strategy.use_sma_target_partials and self.strategy.sma_enabled:
                try:
                    from strategy.sma_calculator import SMACalculator
                    self.strategy.sma_calculator = SMACalculator(
                        self.ib,
                        cache_duration_sec=self.strategy.sma_cache_duration
                    )
                    print(f"✓ SMA calculator initialized (timeframe: {self.strategy.sma_timeframe}, periods: {self.strategy.sma_periods})")
                except Exception as e:
                    print(f"⚠️  Failed to initialize SMA calculator: {e}")
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
                    print(f"✓ Stochastic calculator initialized ({self.strategy.stochastic_k_period}, {self.strategy.stochastic_k_smooth}, {self.strategy.stochastic_d_smooth})")
                    print(f"  LONG: K={self.strategy.stochastic_long_min_k}-{self.strategy.stochastic_long_max_k}, SHORT: K={self.strategy.stochastic_short_min_k}-{self.strategy.stochastic_short_max_k}")
                except Exception as e:
                    print(f"⚠️  Failed to initialize stochastic calculator: {e}")
                    self.strategy.stochastic_calculator = None

            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("\n✓ Disconnected from IBKR")

        # Clear in-memory cache to free memory
        self.bars_cache.clear()
        self.hourly_bars_cache.clear()

    def prefetch_hourly_bars(self, watchlist):
        """
        Pre-fetch 1-hour bars for all watchlist stocks (Oct 7, 2025)

        Performance optimization: Hourly bars are static during backtest,
        so fetch once and cache for reuse in momentum indicator checks.

        Args:
            watchlist: List of stock dictionaries from scanner
        """
        from strategy.momentum_indicators import fetch_1hour_bars
        from ib_insync import Stock

        print("\n📊 Pre-fetching hourly bars for momentum indicators...")

        for stock in watchlist:
            symbol = stock['symbol']
            try:
                contract = Stock(symbol, 'SMART', 'USD')
                bars = fetch_1hour_bars(self.ib, contract, lookback_bars=50)

                if bars and len(bars) >= 26:  # Minimum for MACD (26 + 9 = 35)
                    self.hourly_bars_cache[symbol] = bars
                    print(f"  ✓ {symbol}: {len(bars)} hourly bars cached")
                else:
                    print(f"  ⚠️  {symbol}: Insufficient hourly data ({len(bars) if bars else 0} bars)")

            except Exception as e:
                print(f"  ✗ {symbol}: Error fetching hourly bars - {e}")

        print(f"✓ Cached hourly bars for {len(self.hourly_bars_cache)}/{len(watchlist)} stocks\n")

    def _check_all_data_cached(self):
        """
        Check if all required data is available in cache (Oct 19, 2025)
        Returns True if we can run backtest without connecting to IBKR
        """
        cache_dir = Path(__file__).parent / 'data'
        if not cache_dir.exists():
            return False

        date_str = self.test_date.strftime('%Y%m%d')

        # Get watchlist first (need to know which symbols to check)
        # Filter using strategy module
        if self.using_enhanced_scoring:
            watchlist = self.strategy.filter_enhanced_scanner_results(self.scanner_results)
        else:
            watchlist = self.strategy.filter_scanner_results(self.scanner_results)

        if not watchlist:
            return True  # No stocks to trade, can run without IBKR

        # Check if all symbols have cached CVD-enriched bars
        missing_symbols = []
        for stock in watchlist:
            symbol = stock['symbol']
            cache_file = cache_dir / 'cvd_bars' / f'{symbol}_{date_str}_cvd.json'
            if not cache_file.exists():
                missing_symbols.append(symbol)

        if missing_symbols:
            print(f"⚠️  Missing cache for {len(missing_symbols)} symbols: {', '.join(missing_symbols[:5])}")
            return False

        print(f"✓ Found cache for all {len(watchlist)} symbols")
        return True

    def run(self):
        """Run backtest with two-phase approach (Oct 21, 2025)

        PHASE 1: Build CVD-enriched bars (requires IBKR)
        PHASE 2: Backtest using cached CVD data (no IBKR needed after first run)
        """
        # Always connect to IBKR for CVD build phase
        if not self.connect():
            print("✗ IBKR connection failed - cannot build CVD data")
            return

        try:
            # Initialize Data Processor
            data_processor = DataProcessor(self.ib, self.config, self.logger)

            # Get symbols from scanner
            if self.using_enhanced_scoring:
                watchlist = self.strategy.filter_enhanced_scanner_results(self.scanner_results)
            else:
                watchlist = self.strategy.filter_scanner_results(self.scanner_results)

            symbols = [stock['symbol'] for stock in watchlist]

            # Prepare all data (tick data, 1-min bars, CVD-enriched bars)
            print(f"\n{'='*80}")
            print(f"DATA PROCESSOR - Checking/downloading data for {len(symbols)} symbols")
            print(f"{'='*80}")

            stats = data_processor.prepare_data_for_date(symbols, self.test_date)

            # Log summary
            print(f"\nData Processor Summary:")
            print(f"  Symbols processed: {stats['symbols_processed']}/{len(symbols)}")
            print(f"  Tick data downloaded: {stats['tick_data_downloaded']}")
            print(f"  1-minute bars downloaded: {stats['bars_downloaded']}")
            print(f"  CVD-enriched bars built: {stats['cvd_bars_built']}")
            print(f"  Already cached: {stats['already_cached']}")
            print(f"  Errors: {stats['errors']}")

            # PHASE 1: Build/load CVD-enriched bars for all symbols
            print(f"\n{'='*80}")
            print(f"PHASE 1: Loading CVD-Enriched Bars")
            print(f"{'='*80}")

            print(f"Processing {len(watchlist)} symbols from scanner...")

            for i, stock in enumerate(watchlist):
                symbol = stock['symbol']
                print(f"\n[{i+1}/{len(watchlist)}] {symbol}")

                # Try to load from cache first
                cvd_data = self.load_cvd_enriched_bars(symbol, self.test_date)

                if cvd_data:
                    print(f"  ✓ Loaded {cvd_data['total_bars']} CVD-enriched bars from cache")
                    self.cvd_enriched_bars[symbol] = cvd_data
                else:
                    # Build new CVD data
                    print(f"  Building CVD data from scratch...")
                    try:
                        cvd_data = self.build_cvd_enriched_bars(symbol, self.test_date)
                        self.cvd_enriched_bars[symbol] = cvd_data
                    except Exception as e:
                        print(f"  ✗ Failed to build CVD data: {e}")
                        continue

            print(f"\n{'='*80}")
            print(f"PHASE 1 COMPLETE: Built CVD data for {len(self.cvd_enriched_bars)} symbols")
            print(f"{'='*80}")

            # PHASE 2: Run backtest using CVD-enriched bars
            print(f"\n{'='*80}")
            print(f"PHASE 2: Running Backtest")
            print(f"{'='*80}")

            self.backtest_day()
            self.save_trades_to_json()
            self.print_results()

            # Entry Decision Logging (Oct 25, 2025)
            # Save comprehensive entry decision data for validation
            results_dir = Path(__file__).parent / 'results'
            decision_file = self.entry_logger.save_to_json(results_dir)
            print(f"\n💾 Saved entry decisions to: {decision_file}")
            self.entry_logger.print_summary()

        finally:
            self.disconnect()

    def build_cvd_enriched_bars(self, symbol, date):
        """
        Build CVD-enriched 1-minute bars for a symbol on a specific date

        This method pre-builds all the bar data + CVD data needed for backtesting,
        allowing subsequent backtests to run without IBKR connection.

        CRITICAL (Oct 21, 2025): Uses persistent CVDCalculator across all bars
        to maintain history for slope calculation.

        Args:
            symbol: Stock symbol
            date: Trading date (datetime object)

        Returns:
            dict with structure:
            {
                'symbol': 'SMCI',
                'date': '2025-10-21',
                'total_bars': 390,
                'bars': [
                    {
                        'minute': 1,
                        'timestamp': '2025-10-21T09:30:00-04:00',
                        'open': 54.50,
                        'high': 54.60,
                        'low': 54.40,
                        'close': 54.55,
                        'volume': 125000,
                        'tick_count': 1038,
                        'cvd': {
                            'value': 5200.0,
                            'slope': -400.0,
                            'trend': 'NEUTRAL',
                            'divergence': None,
                            'data_source': 'TICK',
                            'confidence': 1.0
                        }
                    },
                    ...
                ]
            }
        """
        from indicators.cvd_calculator import CVDCalculator

        print(f"\n{'='*80}")
        print(f"Building CVD-enriched bars: {symbol} on {date.strftime('%Y-%m-%d')}")
        print(f"{'='*80}")

        # Check IBKR connection
        if not self.ib or not self.ib.isConnected():
            raise ValueError("IBKR connection required to build CVD-enriched bars")

        # Fetch 1-minute bars for the trading day
        print(f"Fetching 1-minute bars from IBKR...")
        bars = self.get_bars(symbol)

        if not bars:
            raise ValueError(f"No bar data available for {symbol} on {date.strftime('%Y-%m-%d')}")

        print(f"✓ Fetched {len(bars)} 1-minute bars")

        # Create persistent CVD calculator (Oct 27, 2025 - Cleaned up deprecated parameters)
        # This calculator accumulates history across ALL bars
        cvd_config = self.config.get('confirmation', {}).get('cvd', {})
        cvd_calculator = CVDCalculator(
            slope_lookback=cvd_config.get('slope_lookback', 5),
            imbalance_threshold=cvd_config.get('imbalance_threshold', 10.0)
        )

        # Build enriched bars
        enriched_bars = []

        print(f"Building CVD for each bar...")
        for i, bar in enumerate(bars):
            bar_num = i + 1

            # Get timestamp from bar
            bar_timestamp = bar.date

            # Fetch tick data for this specific 1-minute window
            # This matches exactly what we do during backtesting
            ticks = self.get_historical_ticks(symbol, bar_timestamp, lookback_seconds=60)

            if not ticks:
                print(f"⚠️  Bar {bar_num}/{len(bars)}: No tick data available")
                # Skip this bar - we MUST have tick data for CVD
                continue

            # Calculate CVD using tick data (Oct 26, 2025 - Phase 2 Fix: Pass bar for price validation)
            try:
                cvd_result = cvd_calculator.calculate_from_ticks(ticks, bar=bar)

                # Log progress every 30 bars
                if bar_num % 30 == 0:
                    print(f"  Bar {bar_num}/{len(bars)}: CVD={cvd_result.cvd_value:.1f}, "
                          f"slope={cvd_result.cvd_slope:.1f}, trend={cvd_result.cvd_trend}")

                # Build enriched bar data (Oct 26, 2025 - Phase 2 Fix: Added price validation fields)
                enriched_bar = {
                    'minute': bar_num,
                    'timestamp': bar_timestamp.isoformat(),
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'tick_count': len(ticks),
                    'cvd': {
                        'value': cvd_result.cvd_value,
                        'slope': cvd_result.cvd_slope,  # DEPRECATED
                        'trend': cvd_result.cvd_trend,
                        'divergence': cvd_result.divergence,
                        'data_source': cvd_result.data_source,
                        'confidence': cvd_result.confidence,
                        # Phase 1 Fix (Oct 22, 2025)
                        'imbalance_pct': cvd_result.imbalance_pct,
                        'buy_volume': cvd_result.buy_volume,
                        'sell_volume': cvd_result.sell_volume,
                        # Phase 2 Fix (Oct 26, 2025) - Price validation
                        'price_direction': cvd_result.price_direction,
                        'price_change_pct': cvd_result.price_change_pct,
                        'signals_aligned': cvd_result.signals_aligned,
                        'validation_reason': cvd_result.validation_reason
                    }
                }

                enriched_bars.append(enriched_bar)

            except Exception as e:
                print(f"⚠️  Bar {bar_num}/{len(bars)}: CVD calculation failed - {str(e)}")
                continue

        # Build final structure
        enriched_data = {
            'symbol': symbol,
            'date': date.strftime('%Y-%m-%d'),
            'total_bars': len(enriched_bars),
            'bars': enriched_bars
        }

        print(f"\n{'='*80}")
        print(f"✓ Built {len(enriched_bars)} CVD-enriched bars for {symbol}")
        print(f"{'='*80}")

        # Save to cache
        cache_dir = Path(__file__).parent / 'data' / 'cvd_bars'
        cache_dir.mkdir(parents=True, exist_ok=True)

        date_str = date.strftime('%Y%m%d')
        cache_file = cache_dir / f'{symbol}_{date_str}_cvd.json'

        with open(cache_file, 'w') as f:
            json.dump(enriched_data, f, indent=2)

        print(f"✓ Saved CVD-enriched bars to: {cache_file}")

        return enriched_data

    def load_cvd_enriched_bars(self, symbol, date):
        """
        Load CVD-enriched bars from cache

        Args:
            symbol: Stock symbol
            date: Trading date (datetime object)

        Returns:
            dict with CVD-enriched bars data, or None if not cached
        """
        cache_dir = Path(__file__).parent / 'data' / 'cvd_bars'
        date_str = date.strftime('%Y%m%d')
        cache_file = cache_dir / f'{symbol}_{date_str}_cvd.json'

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            return data
        except Exception as e:
            self.logger.warning(f"Failed to load CVD cache for {symbol}: {e}")
            return None

    def backtest_day(self):
        """Backtest single trading day"""
        # DISABLED: Market trend detection (Oct 25, 2025)
        # Was causing SPY fetch timeouts and not used in trading logic
        # if self.ib and self.ib.isConnected():
        #     self.market_trend = self.detect_market_trend()
        # else:
        #     self.market_trend = 'NEUTRAL'
        self.market_trend = 'NEUTRAL'  # Always NEUTRAL (trend detection disabled)

        # Filter scanner using strategy module (score, R/R, distance)
        # Use enhanced filtering if enhanced scoring CSV was loaded
        if self.using_enhanced_scoring:
            watchlist = self.strategy.filter_enhanced_scanner_results(self.scanner_results)
            print(f"✓ Using ENHANCED SCORING filtering (tier-based)")
        else:
            watchlist = self.strategy.filter_scanner_results(self.scanner_results)
            print(f"⚠️  Using LEGACY scoring filtering")

        print(f"\n{'='*80}")
        print(f"MARKET TREND: {self.market_trend}")
        print(f"WATCHLIST: {len(watchlist)} tradeable setups (using strategy filters)")
        print(f"{'='*80}")

        # Pre-fetch hourly bars for all stocks ONCE (performance optimization)
        # Skip if no IBKR connection (stochastic/SMA will be unavailable)
        if watchlist and self.ib and self.ib.isConnected():
            self.prefetch_hourly_bars(watchlist)
        elif watchlist:
            print("⚠️  Skipping hourly bar prefetch (no IBKR connection) - Stochastic/SMA disabled")

        # Print tier breakdown if using enhanced scoring
        if self.using_enhanced_scoring and watchlist:
            from collections import Counter
            tiers = Counter(stock.get('tier', 'UNKNOWN') for stock in watchlist)
            print(f"\nTIER BREAKDOWN:")
            for tier in ['TIER 1', 'TIER 2', 'TIER 3']:
                count = tiers.get(tier, 0)
                if count > 0:
                    symbols = [s['symbol'] for s in watchlist if s.get('tier') == tier]
                    print(f"  {tier}: {count} stocks - {', '.join(symbols[:5])}")
            print()

        # Get opening prices for gap analysis (simulates 9:30 AM market open)
        opening_prices = self.get_opening_prices(watchlist)

        # Apply gap filter at market open
        gap_filtered_watchlist, gap_report = self.strategy.filter_scanner_for_gaps(
            watchlist,
            opening_prices
        )

        # Print gap analysis
        if gap_report and any(gap_report.values()):
            print(f"\n{'='*80}")
            print(f"GAP ANALYSIS AT MARKET OPEN (9:30 AM)")
            print(f"{'='*80}")

            # Process skipped stocks
            for item in gap_report.get('skipped', []):
                print(f"❌ {item['symbol']}: {item['reason']}")

            # Process adjusted stocks
            for item in gap_report.get('adjusted', []):
                print(f"⚠️  {item['symbol']}: {item['reason']}")

            # Process noted stocks
            for item in gap_report.get('noted', []):
                print(f"📊 {item['symbol']}: {item['reason']}")

        # Final watchlist after gap filtering
        if len(gap_filtered_watchlist) < len(watchlist):
            skipped_count = len(watchlist) - len(gap_filtered_watchlist)
            print(f"\n{'='*80}")
            print(f"FINAL WATCHLIST: {len(gap_filtered_watchlist)} setups ({skipped_count} removed by gap filter)")
            print(f"{'='*80}")

        # Backtest final watchlist
        for stock in gap_filtered_watchlist:
            print(f"\n[{stock['symbol']}] Testing setup...")
            print(f"  Resistance: ${stock['resistance']:.2f} | Support: ${stock['support']:.2f}")
            print(f"  Score: {stock['score']} | R/R: {stock['risk_reward']:.2f}:1")

            self.backtest_stock(stock)

    def get_opening_prices(self, watchlist):
        """
        Get opening prices for all stocks in watchlist

        Args:
            watchlist: List of stock dicts from scanner

        Returns:
            Dict of {symbol: opening_price}
        """
        opening_prices = {}

        for stock in watchlist:
            symbol = stock['symbol']

            # Get bars for this stock (will use cache if available)
            bars = self.get_bars(symbol)

            if bars and len(bars) > 0:
                # First bar of the day = opening price
                opening_prices[symbol] = bars[0].open

        return opening_prices

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

        # STATE MACHINE (Oct 9, 2025): Reset state for this symbol at start of day
        self.strategy.state_tracker.reset_state(symbol)

        self.logger.debug(f"\n{'='*80}")
        self.logger.debug(f"Starting backtest for {symbol}")
        self.logger.debug(f"Resistance: ${resistance:.2f}, Support: ${support:.2f}")
        self.logger.debug(f"{'='*80}")

        # Get 1-minute historical bars from IBKR
        bars = self.get_bars(symbol)

        if not bars:
            print(f"  ⚠️  No historical data available")
            self.logger.warning(f"{symbol}: No historical data available")
            return

        print(f"  ✓ Fetched {len(bars)} 1-minute bars")
        self.logger.info(f"{symbol}: Fetched {len(bars)} 1-minute bars")

        # Gap detection is now handled by strategy.should_enter_long/short() which calls _check_gap_filter()
        # This ensures consistent gap handling between backtesting and live trading

        # Report opening gap for visibility (optional diagnostic info)
        opening_bar = bars[0]
        opening_price = opening_bar.open
        prev_close = stock['close']
        gap_pct = ((opening_price - prev_close) / prev_close) * 100

        if abs(gap_pct) > 2.0:
            dist_to_r = abs(((opening_price - resistance) / opening_price) * 100)
            dist_to_s = abs(((opening_price - support) / opening_price) * 100)
            print(f"  📊 Overnight gap: {gap_pct:+.2f}% → Now {min(dist_to_r, dist_to_s):.2f}% from pivot")

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

            # Entry logic - check for setups (MAX 2 ATTEMPTS per type)
            # CRITICAL FIX (Oct 4, 2025): Prioritize BREAKOUT checks over BOUNCE/REJECTION
            # Previous bug: BOUNCE condition (price > support*0.99) blocked SHORT breakout checks
            if position is None and within_entry_window:
                # Check BREAKOUT long entry using strategy module (includes gap filter!)
                if long_attempts < max_attempts and self.enable_longs:
                    # Use strategy module's should_enter_long (checks pivot, attempts, gap filter, etc.)
                    should_enter, reason = self.strategy.should_enter_long(stock, price, long_attempts)

                    self.logger.debug(f"{symbol} Bar {bar_count} - LONG check: price=${price:.2f} vs resistance=${resistance:.2f}, should_enter={should_enter}, reason='{reason}'")

                    if should_enter:
                        # HYBRID Entry Strategy (Oct 4, 2025)
                        # Momentum breakout OR pullback/retest based on volume + candle strength
                        # Performance optimization: Pass cached hourly bars for RSI/MACD
                        cached_bars = self.hourly_bars_cache.get(stock['symbol'])

                        # PHASE 7 (Oct 13, 2025): Dynamic target selection - use highest available target
                        # Allows delayed momentum entries even after price passes target1
                        highest_target = stock.get('target3') or stock.get('target2') or stock.get('target1')

                        confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(
                            bars, bar_count - 1, resistance, side='LONG',
                            target_price=highest_target,  # Use highest available target
                            symbol=stock['symbol'],  # For RSI/MACD momentum check
                            cached_hourly_bars=cached_bars,  # Pre-fetched hourly bars
                            backtester=self  # Oct 21, 2025: For tick-based CVD
                        )

                        self.logger.debug(f"{symbol} Bar {bar_count} - LONG confirmation: confirmed={confirmed}, reason='{confirm_reason}', entry_state='{entry_state}'")

                        # ═══════════════════════════════════════════════════════════════
                        # ENTRY DECISION LOGGING (Oct 25, 2025)
                        # ═══════════════════════════════════════════════════════════════
                        # Log EVERY entry attempt (entered + blocked) with complete filter data
                        # This enables validation of backtest results:
                        #   - Find missed valid entries (all filters passed but didn't enter)
                        #   - Identify invalid breakouts (conflicting signals but entered anyway)
                        #   - Analyze filter effectiveness (which filters block most?)
                        #   - Optimize filter parameters (test different thresholds)
                        #
                        # Output: backtest/results/backtest_entry_decisions_YYYYMMDD.json
                        # ═══════════════════════════════════════════════════════════════

                        # Capture filter data at decision time
                        entry_path_data = {
                            'volume_ratio': entry_state.get('volume_ratio', 0),
                            'volume_threshold': self.strategy.momentum_volume_threshold,
                            'candle_size_pct': entry_state.get('candle_size_pct', 0),
                            'candle_threshold_pct': self.strategy.momentum_candle_min_pct,
                            'path_chosen': entry_state.get('phase', 'unknown')
                        }

                        # COMPREHENSIVE FILTER EVALUATION (Oct 26, 2025)
                        # If state machine provided comprehensive filter results, use those directly
                        # Otherwise fall back to old capture_filter_data() for backwards compatibility
                        if 'all_filters' in entry_state:
                            # Use comprehensive results from state machine
                            filters = entry_state['all_filters']
                        else:
                            # Fall back to old extraction method
                            filters = capture_filter_data(
                                self.strategy, bars, bar_count - 1, 'LONG',
                                entry_path_data, target_price=highest_target,
                                symbol=stock['symbol'],
                                entry_state=entry_state
                            )

                        # CRITICAL FIX (Oct 26, 2025): Prioritize actual filter blocking reasons
                        # Problem: confirm_reason shows "Breakout detected, waiting for candle close"
                        #          even when stochastic/CVD/other filters already blocked entry
                        # Solution: Check filters dict for BLOCK results, use their reason instead
                        actual_reason = confirm_reason  # Default to hybrid entry reason
                        if not confirmed and filters:
                            # Search for the first filter that blocked
                            for filter_name, filter_data in filters.items():
                                if isinstance(filter_data, dict) and filter_data.get('result') == 'BLOCK':
                                    filter_reason = filter_data.get('reason', 'Filter blocked')
                                    actual_reason = f"Breakout rejected: {filter_name.replace('_', ' ').title()} ({filter_reason})"
                                    break  # Use first blocking filter found

                        # Log this entry attempt
                        self.entry_logger.log_entry_attempt(
                            timestamp=timestamp,
                            symbol=stock['symbol'],
                            side='LONG',
                            bar_idx=bar_count,
                            price=price,
                            pivot_data={
                                'resistance': resistance,
                                'support': support,
                                'through_pivot': True  # Passed should_enter_long
                            },
                            pivot_checks={
                                'price_vs_pivot': 'PASS',
                                'attempt_count': f'{long_attempts}/{max_attempts}',
                                'avoid_list': 'PASS' if stock['symbol'] not in self.strategy.avoid_symbols else 'FAIL',
                                'position_size': 'PASS'  # Calculated in should_enter_long
                            },
                            entry_path=entry_path_data,
                            filters=filters,
                            decision='ENTERED' if confirmed else 'BLOCKED',
                            phase=entry_state.get('phase', 'unknown'),
                            reason=actual_reason  # Use actual blocking reason, not generic confirm_reason
                        )

                        # CVD Analytics (Oct 19, 2025): Track CVD filter blocks
                        if not confirmed and entry_state.get('phase') == 'cvd_filter':
                            self.cvd_analytics['total_blocks'] += 1
                            self.cvd_analytics['long_blocks'] += 1
                            self.cvd_analytics['symbols_blocked'].add(symbol)
                            # Track reason
                            reason_key = confirm_reason.split('(')[0].strip() if '(' in confirm_reason else confirm_reason
                            self.cvd_analytics['blocks_by_reason'][reason_key] = \
                                self.cvd_analytics['blocks_by_reason'].get(reason_key, 0) + 1
                            self.logger.info(f"[CVD ANALYTICS] {symbol} LONG blocked: {confirm_reason}")

                        if confirmed:
                            # PHASE 5 (Oct 12, 2025): Use adjusted stop if available (PULLBACK_RETEST entries)
                            # Otherwise use scanner resistance (MOMENTUM/SUSTAINED_BREAK entries)
                            adjusted_stop = entry_state.get('adjusted_stop')
                            pivot_for_stop = adjusted_stop if adjusted_stop is not None else resistance

                            # Use configured stop calculation from strategy (Oct 23, 2025)
                            # Supports both ATR-based and candle-based stops
                            # Create temporary position dict for stop calculation
                            temp_position = {
                                'entry_price': price,
                                'side': 'LONG',
                                'partials': 0,
                                'pivot': pivot_for_stop  # PHASE 5: May be adjusted for pullback retests
                            }
                            stop_price = self.strategy.calculate_stop_price(
                                temp_position,
                                price,
                                stock,
                                bars=bars,
                                entry_bar_idx=bar_count
                            )

                            if adjusted_stop is not None:
                                self.logger.info(f"{symbol} Bar {bar_count} - ENTERING LONG @ ${price:.2f}, stop=${stop_price:.2f} (adjusted from pullback low ${adjusted_stop:.2f}), attempts={long_attempts}/{max_attempts}")
                            else:
                                self.logger.info(f"{symbol} Bar {bar_count} - ENTERING LONG @ ${price:.2f}, stop=${stop_price:.2f} (ATR: {stock.get('atr%', 0):.1f}%), attempts={long_attempts}/{max_attempts}")
                            position = self.enter_long(stock, price, timestamp, bar_count, setup_type='BREAKOUT', stop_override=stop_price)
                            long_attempts += 1

                # Check BREAKOUT short entry using strategy module (includes gap filter!)
                # MOVED UP: Must check BEFORE bounce/rejection to prevent blocking
                if position is None and short_attempts < max_attempts and self.enable_shorts:
                    # Use strategy module's should_enter_short (checks pivot, attempts, gap filter, etc.)
                    should_enter, reason = self.strategy.should_enter_short(stock, price, short_attempts)

                    self.logger.debug(f"{symbol} Bar {bar_count} - SHORT check: price=${price:.2f} vs support=${support:.2f}, should_enter={should_enter}, reason='{reason}'")

                    if should_enter:
                        # HYBRID Entry Strategy (Oct 4, 2025)
                        # Momentum breakout OR pullback/retest based on volume + candle strength
                        # Performance optimization: Pass cached hourly bars for RSI/MACD
                        cached_bars = self.hourly_bars_cache.get(stock['symbol'])

                        # PHASE 7 (Oct 13, 2025): Dynamic target selection - use lowest available downside target
                        # Allows delayed momentum entries even after price passes downside1
                        lowest_downside = stock.get('downside2') or stock.get('downside1')

                        confirmed, confirm_reason, entry_state = self.strategy.check_hybrid_entry(
                            bars, bar_count - 1, support, side='SHORT',
                            target_price=lowest_downside,  # Use lowest available downside target
                            symbol=stock['symbol'],  # For RSI/MACD momentum check
                            cached_hourly_bars=cached_bars,  # Pre-fetched hourly bars
                            backtester=self  # Oct 21, 2025: For tick-based CVD
                        )

                        self.logger.debug(f"{symbol} Bar {bar_count} - SHORT confirmation: confirmed={confirmed}, reason='{confirm_reason}', entry_state='{entry_state}'")

                        # ═══════════════════════════════════════════════════════════════
                        # ENTRY DECISION LOGGING (Oct 25, 2025)
                        # ═══════════════════════════════════════════════════════════════
                        # Log EVERY entry attempt (entered + blocked) with complete filter data
                        # See LONG entry logging above for detailed explanation
                        # ═══════════════════════════════════════════════════════════════

                        # Capture filter data at decision time
                        entry_path_data = {
                            'volume_ratio': entry_state.get('volume_ratio', 0),
                            'volume_threshold': self.strategy.momentum_volume_threshold,
                            'candle_size_pct': entry_state.get('candle_size_pct', 0),
                            'candle_threshold_pct': self.strategy.momentum_candle_min_pct,
                            'path_chosen': entry_state.get('phase', 'unknown')
                        }

                        # COMPREHENSIVE FILTER EVALUATION (Oct 26, 2025)
                        # If state machine provided comprehensive filter results, use those directly
                        # Otherwise fall back to old capture_filter_data() for backwards compatibility
                        if 'all_filters' in entry_state:
                            # Use comprehensive results from state machine
                            filters = entry_state['all_filters']
                        else:
                            # Fall back to old extraction method
                            filters = capture_filter_data(
                                self.strategy, bars, bar_count - 1, 'SHORT',
                                entry_path_data, target_price=lowest_downside,
                                symbol=stock['symbol'],
                                entry_state=entry_state
                            )

                        # CRITICAL FIX (Oct 26, 2025): Prioritize actual filter blocking reasons
                        # Problem: confirm_reason shows "Breakout detected, waiting for candle close"
                        #          even when stochastic/CVD/other filters already blocked entry
                        # Solution: Check filters dict for BLOCK results, use their reason instead
                        actual_reason = confirm_reason  # Default to hybrid entry reason
                        if not confirmed and filters:
                            # Search for the first filter that blocked
                            for filter_name, filter_data in filters.items():
                                if isinstance(filter_data, dict) and filter_data.get('result') == 'BLOCK':
                                    filter_reason = filter_data.get('reason', 'Filter blocked')
                                    actual_reason = f"Breakout rejected: {filter_name.replace('_', ' ').title()} ({filter_reason})"
                                    break  # Use first blocking filter found

                        # Log this entry attempt
                        self.entry_logger.log_entry_attempt(
                            timestamp=timestamp,
                            symbol=stock['symbol'],
                            side='SHORT',
                            bar_idx=bar_count,
                            price=price,
                            pivot_data={
                                'resistance': resistance,
                                'support': support,
                                'through_pivot': True  # Passed should_enter_short
                            },
                            pivot_checks={
                                'price_vs_pivot': 'PASS',
                                'attempt_count': f'{short_attempts}/{max_attempts}',
                                'avoid_list': 'PASS' if stock['symbol'] not in self.strategy.avoid_symbols else 'FAIL',
                                'position_size': 'PASS'  # Calculated in should_enter_short
                            },
                            entry_path=entry_path_data,
                            filters=filters,
                            decision='ENTERED' if confirmed else 'BLOCKED',
                            phase=entry_state.get('phase', 'unknown'),
                            reason=actual_reason  # Use actual blocking reason, not generic confirm_reason
                        )

                        # CVD Analytics (Oct 19, 2025): Track CVD filter blocks
                        if not confirmed and entry_state.get('phase') == 'cvd_filter':
                            self.cvd_analytics['total_blocks'] += 1
                            self.cvd_analytics['short_blocks'] += 1
                            self.cvd_analytics['symbols_blocked'].add(symbol)
                            # Track reason
                            reason_key = confirm_reason.split('(')[0].strip() if '(' in confirm_reason else confirm_reason
                            self.cvd_analytics['blocks_by_reason'][reason_key] = \
                                self.cvd_analytics['blocks_by_reason'].get(reason_key, 0) + 1
                            self.logger.info(f"[CVD ANALYTICS] {symbol} SHORT blocked: {confirm_reason}")

                        if confirmed:
                            # PHASE 5 (Oct 12, 2025): Use adjusted stop if available (PULLBACK_RETEST entries)
                            # Otherwise use scanner support (MOMENTUM/SUSTAINED_BREAK entries)
                            adjusted_stop = entry_state.get('adjusted_stop')
                            pivot_for_stop = adjusted_stop if adjusted_stop is not None else support

                            # Use configured stop calculation from strategy (Oct 23, 2025)
                            # Supports both ATR-based and candle-based stops
                            # Create temporary position dict for stop calculation
                            temp_position = {
                                'entry_price': price,
                                'side': 'SHORT',
                                'partials': 0,
                                'pivot': pivot_for_stop  # PHASE 5: May be adjusted for pullback retests
                            }
                            stop_price = self.strategy.calculate_stop_price(
                                temp_position,
                                price,
                                stock,
                                bars=bars,
                                entry_bar_idx=bar_count
                            )

                            if adjusted_stop is not None:
                                self.logger.info(f"{symbol} Bar {bar_count} - ENTERING SHORT @ ${price:.2f}, stop=${stop_price:.2f} (adjusted from pullback high ${adjusted_stop:.2f}), attempts={short_attempts}/{max_attempts}")
                            else:
                                self.logger.info(f"{symbol} Bar {bar_count} - ENTERING SHORT @ ${price:.2f}, stop=${stop_price:.2f} (ATR: {stock.get('atr%', 0):.1f}%), attempts={short_attempts}/{max_attempts}")
                            position = self.enter_short(stock, price, timestamp, bar_count,
                                                      setup_type='BREAKOUT', stop_override=stop_price)
                            short_attempts += 1

                # Check BOUNCE long entry (pullback to support + reversal)
                # MOVED DOWN: After breakout checks to avoid blocking SHORT entries
                if position is None and long_attempts < max_attempts and price > support * 0.99 and self.enable_longs:
                    bounce_confirmed, bounce_reason = self.strategy.check_bounce_setup(
                        bars, bar_count, support, side='LONG'
                    )

                    if bounce_confirmed:
                        position = self.enter_long(stock, price, timestamp, bar_count, setup_type='BOUNCE')
                        long_attempts += 1

                # Check REJECTION short entry (failed breakout at resistance)
                # MOVED DOWN: After breakout checks
                if position is None and short_attempts < max_attempts and price < resistance * 1.01 and self.enable_shorts:
                    rejection_confirmed, rejection_reason = self.strategy.check_rejection_setup(
                        bars, bar_count, resistance, side='SHORT'
                    )

                    if rejection_confirmed:
                        position = self.enter_short(stock, price, timestamp, bar_count, setup_type='REJECTION')
                        short_attempts += 1

            # Exit logic - manage open position
            elif position is not None:
                position, closed_trade = self.manage_position(
                    position, price, timestamp, bar_count, bars
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
        """
        Fetch 1-minute bars from cache ONLY - NO IBKR fallback (Oct 23, 2025)

        IMPORTANT: Backtester now requires pre-downloaded tick data in data/ticks/
        This ensures consistent backtest results and avoids rate limits.
        """
        # Check in-memory cache first (fastest)
        if symbol in self.bars_cache:
            return self.bars_cache[symbol]

        # Check disk cache
        cache_dir = Path(__file__).parent / 'data'
        cache_dir.mkdir(exist_ok=True)

        date_str = self.test_date.strftime('%Y%m%d')
        cache_file = cache_dir / f'{symbol}_{date_str}_1min.json'

        # Load from cache if exists
        if cache_file.exists():
            print(f"  ✓ Loading from cache: {cache_file.name}")
            try:
                import json
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)

                # Reconstruct BarDataList from cached data
                from ib_insync import BarDataList, BarData
                from datetime import datetime

                bars = BarDataList()
                for bar_dict in cached_data:
                    bar = BarData(
                        date=datetime.fromisoformat(bar_dict['date']),
                        open=bar_dict['open'],
                        high=bar_dict['high'],
                        low=bar_dict['low'],
                        close=bar_dict['close'],
                        volume=bar_dict['volume'],
                        average=bar_dict.get('average', bar_dict['close']),
                        barCount=bar_dict.get('barCount', 0)
                    )
                    bars.append(bar)

                # Store in memory cache
                self.bars_cache[symbol] = bars
                return bars
            except Exception as e:
                print(f"  ⚠️  Cache read error: {e}")

        # Check if tick data exists before failing
        tick_dir = cache_dir / 'ticks'
        if tick_dir.exists():
            # Check if ANY tick files exist for this symbol/date
            tick_pattern = f"{symbol}_{date_str}_*_ticks.json"
            tick_files = list(tick_dir.glob(tick_pattern))

            if tick_files:
                print(f"  ❌ ERROR: Tick data exists ({len(tick_files)} files) but 1-minute bars not built")
                print(f"     Run: python3 build_bars_from_ticks.py --date {date_str} --symbol {symbol}")
                print(f"     Or rebuild CVD-enriched data to auto-generate 1-minute bars")
                return []

        # NO FALLBACK TO IBKR - Fail immediately
        print(f"  ❌ ERROR: No cached 1-minute bars found for {symbol} on {date_str}")
        print(f"     Expected file: {cache_file}")
        print(f"     Tick data directory: {tick_dir}")
        print(f"")
        print(f"  To fix this:")
        print(f"     1. Download tick data first:")
        print(f"        python3 download_tick_data.py --date {self.test_date.strftime('%Y-%m-%d')} --symbol {symbol}")
        print(f"     2. Then run backtest (it will auto-build bars from ticks)")
        print(f"")
        return []

    def get_historical_ticks(self, symbol, bar_timestamp, lookback_seconds=60):
        """
        Fetch historical tick data for CVD calculation (Oct 21, 2025)

        This method fetches tick-by-tick trade data from IBKR for a specific time window,
        allowing more accurate CVD calculation in backtesting (matches live trading methodology).

        Args:
            symbol: Stock symbol
            bar_timestamp: Timestamp of the bar being analyzed (datetime object)
            lookback_seconds: How many seconds of tick data to fetch (default: 60 seconds)

        Returns:
            List of tick objects with .price and .size attributes, or None if unavailable

        Note:
            - IBKR historical ticks only available for last ~60 days
            - Falls back to bar approximation for older dates
            - Uses disk caching to avoid repeated API calls
        """
        # Check if tick-based CVD is enabled
        if not self.use_tick_based_cvd:
            self.logger.debug(f"Tick-based CVD disabled for {symbol}")
            return None

        # Check if we're connected to IBKR (required for tick data)
        if not self.ib or not self.ib.isConnected():
            self.logger.debug(f"No IBKR connection for {symbol} tick fetch")
            return None

        # Log entry into tick fetching
        self.logger.info(f"🔍 Fetching historical ticks for {symbol} @ {bar_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        # Calculate time window
        end_time = bar_timestamp
        start_time = bar_timestamp - timedelta(seconds=lookback_seconds)

        # Create cache key
        cache_key = (symbol, bar_timestamp.isoformat())

        # Check in-memory cache first
        if self.tick_cache_enabled and cache_key in self.tick_cache:
            return self.tick_cache[cache_key]

        # Check disk cache
        cache_dir = Path(__file__).parent / 'data' / 'ticks'
        cache_dir.mkdir(parents=True, exist_ok=True)

        date_str = self.test_date.strftime('%Y%m%d')
        time_str = bar_timestamp.strftime('%H%M%S')
        cache_file = cache_dir / f'{symbol}_{date_str}_{time_str}_ticks.json'

        # Load from cache if exists
        if cache_file.exists() and self.tick_cache_enabled:
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)

                # Convert to tick objects (matching CVD calculator format)
                from dataclasses import dataclass

                @dataclass
                class TickData:
                    price: float
                    size: int

                tick_list = [TickData(price=t['price'], size=t['size']) for t in cached_data]

                # Store in memory cache
                self.tick_cache[cache_key] = tick_list
                self.logger.info(f"✅ Loaded {len(tick_list)} ticks from cache for {symbol}")
                return tick_list

            except Exception as e:
                self.logger.warning(f"Tick cache read error for {symbol}: {e}")

        # Fetch from IBKR
        try:
            contract = Stock(symbol, 'SMART', 'USD')

            # Request historical ticks
            # Note: IBKR limits to last ~60 days for tick data
            ticks = self.ib.reqHistoricalTicks(
                contract,
                startDateTime=start_time,
                endDateTime=end_time,
                numberOfTicks=1000,
                whatToShow='TRADES',
                useRth=True
            )

            if not ticks:
                self.logger.debug(f"No tick data available for {symbol} at {bar_timestamp}")
                return None

            # Convert to format CVD calculator expects
            from dataclasses import dataclass

            @dataclass
            class TickData:
                price: float
                size: int

            tick_list = [TickData(price=t.price, size=t.size) for t in ticks]

            # Cache to disk
            if self.tick_cache_enabled:
                cache_data = [{'price': t.price, 'size': t.size} for t in tick_list]
                with open(cache_file, 'w') as f:
                    json.dump(cache_data, f)

            # Store in memory cache
            self.tick_cache[cache_key] = tick_list

            # Add small delay to respect rate limits
            self.ib.sleep(0.5)

            self.logger.info(f"✅ Fetched {len(tick_list)} ticks from IBKR for {symbol}, cached to disk")
            return tick_list

        except Exception as e:
            # Historical ticks may not be available (>60 days old or other API error)
            # This is expected and not an error - will fall back to bar approximation
            self.logger.debug(f"Could not fetch historical ticks for {symbol}: {e}")
            return None

    def enter_long(self, stock, price, timestamp, bar_num, setup_type='BREAKOUT', stop_override=None):
        """Enter long position"""
        # Apply entry slippage (buy at slightly worse price)
        entry_price = price * (1 + self.entry_slippage)

        # Stop placement depends on setup type
        if stop_override is not None:
            # Use explicit stop override (e.g., from ATR calculation or retest confirmation)
            # Don't apply minimum stop logic - the override already accounts for volatility
            stop_price = stop_override
        elif setup_type == 'BOUNCE':
            # For bounce: stop below support
            base_stop = stock['support'] * 0.995  # Just below support
            # Apply minimum stop logic for non-override cases
            BOUNCE_MIN_STOP_PCT = 0.004
            min_stop_price = entry_price * (1 - BOUNCE_MIN_STOP_PCT)
            stop_price = min(base_stop, min_stop_price)
        else:  # BREAKOUT
            # For breakout: stop at resistance (pivot)
            base_stop = stock['resistance']
            # PHASE 1 FIX (Oct 9, 2025): Enforce minimum stop distances
            # Prevents getting stopped out by normal price noise
            MOMENTUM_MIN_STOP_PCT = 0.005  # 0.5% for momentum breakouts
            min_stop_price = entry_price * (1 - MOMENTUM_MIN_STOP_PCT)
            # Use the LOWER of base_stop or min_stop (provides more protection)
            stop_price = min(base_stop, min_stop_price)

        shares = self.calculate_position_size(entry_price, stop_price)

        # Create position using position manager
        position = self.pm.create_position(
            symbol=stock['symbol'],
            side='LONG',
            entry_price=entry_price,
            shares=shares,
            pivot=stock['resistance'],
            stop=stop_price,  # Use calculated ATR-based stop
            target1=stock['target1'],
            target2=stock['target2'],
            entry_time=timestamp,
            entry_bar=bar_num
        )
        position['setup_type'] = setup_type

        emoji = "🔄" if setup_type == 'BOUNCE' else "🟢"
        print(f"  {emoji} LONG {setup_type} @ ${entry_price:.2f} (bar {bar_num}, {timestamp.strftime('%H:%M')})")
        print(f"     Shares: {shares} | Stop: ${stop_price:.2f}")
        return position

    def enter_short(self, stock, price, timestamp, bar_num, setup_type='BREAKOUT', stop_override=None):
        """Enter short position"""
        # Apply entry slippage (sell at slightly worse price)
        entry_price = price * (1 - self.entry_slippage)

        # Stop placement depends on setup type
        if stop_override is not None:
            # Use explicit stop override (e.g., from ATR calculation or retest confirmation)
            # Don't apply minimum stop logic - the override already accounts for volatility
            stop_price = stop_override
        elif setup_type == 'REJECTION':
            # For rejection: stop above resistance
            base_stop = stock['resistance'] * 1.005  # Just above resistance
            # Apply minimum stop logic for non-override cases
            REJECTION_MIN_STOP_PCT = 0.004
            min_stop_price = entry_price * (1 + REJECTION_MIN_STOP_PCT)
            stop_price = max(base_stop, min_stop_price)
        else:  # BREAKOUT
            # For breakout: stop at support (pivot)
            base_stop = stock['support']
            # PHASE 1 FIX (Oct 9, 2025): Enforce minimum stop distances
            # Prevents getting stopped out by normal price noise
            MOMENTUM_MIN_STOP_PCT = 0.005  # 0.5% for momentum breakouts
            # Calculate minimum stop price (ABOVE entry for shorts)
            min_stop_price = entry_price * (1 + MOMENTUM_MIN_STOP_PCT)
            # Use the HIGHER of base_stop or min_stop (provides more protection for shorts)
            stop_price = max(base_stop, min_stop_price)

        shares = self.calculate_position_size(stop_price, entry_price)

        # Create position using position manager
        position = self.pm.create_position(
            symbol=stock['symbol'],
            side='SHORT',
            entry_price=entry_price,
            shares=shares,
            pivot=stock['support'],
            stop=stop_price,  # Use calculated ATR-based stop
            target1=stock.get('downside1', stock['support'] * 0.98),
            target2=stock.get('downside2', stock['support'] * 0.96),
            entry_time=timestamp,
            entry_bar=bar_num
        )
        position['setup_type'] = setup_type

        emoji = "⬇️" if setup_type == 'REJECTION' else "🔴"
        print(f"  {emoji} SHORT {setup_type} @ ${entry_price:.2f} (bar {bar_num}, {timestamp.strftime('%H:%M')})")
        print(f"     Shares: {shares} | Stop: ${stop_price:.2f}")
        return position

    def manage_position(self, pos, price, timestamp, bar_num, bars):
        """
        Manage open position per PS60 rules using strategy module:
        - 15-minute rule: Exit if no progress after 15 minutes
        - Take 50% profit on first move
        - Move stop to breakeven
        - Update trailing stop for runners
        - Exit at target or stop
        - Partial profit-taking at 1R and targets
        """
        # 7-MINUTE RULE (PS60 Core Rule - configurable threshold, default 7 min)
        # Use strategy module's check_fifteen_minute_rule method
        should_exit, reason = self.strategy.check_fifteen_minute_rule(pos, price, timestamp)
        self.logger.debug(f"{pos['symbol']} Bar {bar_num} - {self.strategy.fifteen_minute_threshold}-min rule check: should_exit={should_exit}, reason='{reason}'")
        if should_exit:
            exit_price = price  # No additional slippage, market exit
            print(f"     ⏱️  {reason} @ ${exit_price:.2f} ({timestamp.strftime('%H:%M')})")
            # Use actual threshold from strategy config (7 minutes, not 15)
            rule_name = f"{self.strategy.fifteen_minute_threshold}MIN_RULE"
            self.logger.info(f"{pos['symbol']} Bar {bar_num} - EXIT ({rule_name}) @ ${exit_price:.2f}, P&L=${(exit_price-pos['entry_price'])*pos['shares']*(1 if pos['side']=='SHORT' else -1):.2f}")
            return None, self.close_position(pos, exit_price, timestamp, rule_name, bar_num)

        # Check for partial profit using strategy module (now uses 1R-based logic)
        # Pass bars for SMA calculation in progressive partial system
        should_partial, pct, reason = self.strategy.should_take_partial(pos, price, bars=bars)
        if should_partial:
            # Record partial using position manager
            partial_record = self.pm.take_partial(pos['symbol'], price, pct, reason)
            print(f"     💰 PARTIAL {int(pct*100)}% @ ${price:.2f} "
                  f"(+${partial_record['gain']:.2f}, {timestamp.strftime('%H:%M')})")
            self.logger.info(f"{pos['symbol']} Bar {bar_num} - PARTIAL {int(pct*100)}% @ ${price:.2f}, gain=${partial_record['gain']:.2f}, reason='{reason}'")

            # Move stop to breakeven if configured
            if self.strategy.should_move_stop_to_breakeven(pos):
                pos['stop'] = pos['entry_price']
                self.logger.debug(f"{pos['symbol']} Bar {bar_num} - Stop moved to breakeven @ ${pos['stop']:.2f}")

        # ========================================================================
        # TARGET-HIT STALL DETECTION (Oct 21, 2025 - Phase 9)
        # ========================================================================
        # Check if price is stalling after hitting target1 (runner positions only)
        # Tighten trailing stop from 0.5% → 0.1% to exit quickly and free capital
        config_stall = self.config.get('trading', {}).get('exits', {}).get('target_hit_stall_detection', {})
        if config_stall.get('enabled', False):
            # Check for stall after target hit
            is_stalled, new_trail_pct = self.strategy.check_target_hit_stall(
                pos, price, timestamp
            )

            if is_stalled and new_trail_pct:
                # STALL DETECTED! Tighten trailing stop dramatically
                old_trail = pos.get('trailing_distance', self.config['trading']['exits']['trailing_stop']['percentage'])

                # Calculate new stop with tighter trail
                if pos['side'] == 'LONG':
                    new_stop = price * (1 - new_trail_pct)
                else:  # SHORT
                    new_stop = price * (1 + new_trail_pct)

                old_stop = pos['stop']
                pos['stop'] = new_stop
                pos['trailing_distance'] = new_trail_pct

                # Calculate gain for logging
                if pos['side'] == 'LONG':
                    gain_pct = ((price - pos['entry_price']) / pos['entry_price']) * 100
                else:
                    gain_pct = ((pos['entry_price'] - price) / pos['entry_price']) * 100

                # Calculate stall duration in minutes
                stall_duration_min = int((timestamp - pos['stall_window_start']).total_seconds() / 60)

                self.logger.info(f"\n⏸️  STALL DETECTED: {pos['symbol']}")
                self.logger.info(f"   Entry: ${pos['entry_price']:.2f}")
                self.logger.info(f"   Current: ${price:.2f} ({gain_pct:+.2f}%)")
                self.logger.info(f"   Target1: ${pos.get('target1', 0):.2f} (hit!)")
                self.logger.info(f"   Stall Range: {pos['stall_window_high']:.2f} - {pos['stall_window_low']:.2f}")
                self.logger.info(f"   Duration: {stall_duration_min} minutes")
                self.logger.info(f"   🔔 Tightening trail: {old_trail*100:.1f}% → {new_trail_pct*100:.1f}%")
                self.logger.info(f"   🛡️  New stop: ${old_stop:.2f} → ${new_stop:.2f}")

                print(f"     ⏸️  STALL @ bar {bar_num}: Tightened trail {old_trail*100:.1f}% → {new_trail_pct*100:.1f}% (stop ${old_stop:.2f} → ${new_stop:.2f})")

        # Update trailing stop for runners (per requirements)
        stop_updated, new_stop, trail_reason = self.strategy.update_trailing_stop(pos, price)
        if stop_updated:
            pos['stop'] = new_stop
            # Uncomment for detailed trail tracking:
            # print(f"     ⬆️  {trail_reason}")

        # Check trailing stop hit (for runners)
        trail_hit, trail_reason = self.strategy.check_trailing_stop_hit(pos, price)
        if trail_hit:
            # Apply stop slippage
            if pos['side'] == 'LONG':
                exit_price = price * (1 - self.stop_slippage)
            else:
                exit_price = price * (1 + self.stop_slippage)
            print(f"     🎯 {trail_reason} @ ${exit_price:.2f} ({timestamp.strftime('%H:%M')})")
            return None, self.close_position(pos, exit_price, timestamp, trail_reason.split()[0], bar_num)

        # Check regular stops
        if pos['side'] == 'LONG':
            # Stop hit - exit remaining (with slippage)
            if price <= pos['stop']:
                # Apply stop slippage (sell at worse price for longs)
                stop_exit_price = price * (1 - self.stop_slippage)
                print(f"     🛑 STOP remaining @ ${stop_exit_price:.2f} ({timestamp.strftime('%H:%M')})")
                self.logger.info(f"{pos['symbol']} Bar {bar_num} - EXIT (STOP) LONG @ ${stop_exit_price:.2f}, stop=${pos['stop']:.2f}, price=${price:.2f}")
                return None, self.close_position(pos, stop_exit_price, timestamp, 'STOP', bar_num)

        else:  # SHORT
            # Stop hit (with slippage)
            if price >= pos['stop']:
                # Apply stop slippage (buy back at worse price for shorts)
                stop_exit_price = price * (1 + self.stop_slippage)
                print(f"     🛑 STOP remaining @ ${stop_exit_price:.2f} ({timestamp.strftime('%H:%M')})")
                self.logger.info(f"{pos['symbol']} Bar {bar_num} - EXIT (STOP) SHORT @ ${stop_exit_price:.2f}, stop=${pos['stop']:.2f}, price=${price:.2f}")
                return None, self.close_position(pos, stop_exit_price, timestamp, 'STOP', bar_num)

        return pos, None

    def calculate_position_size(self, entry, stop):
        """
        Calculate shares based on 1% risk per trade

        Risk-based sizing:
        - Risk amount = account_size × risk_per_trade (1%)
        - Stop distance = abs(entry - stop)
        - Shares = risk_amount / stop_distance
        - Capped at min_shares and max_shares

        This matches live trader behavior and provides realistic backtest results.
        """
        # Calculate risk amount (1% of account)
        risk_amount = self.config['trading']['account_size'] * self.config['trading']['risk_per_trade']

        # Calculate stop distance
        stop_distance = abs(entry - stop)

        if stop_distance == 0:
            # Avoid division by zero - use min shares
            return self.config['trading']['position_sizing']['min_shares']

        # Calculate shares based on risk
        shares = int(risk_amount / stop_distance)

        # Apply min/max constraints
        min_shares = self.config['trading']['position_sizing']['min_shares']
        max_shares = self.config['trading']['position_sizing']['max_shares']

        shares = max(min_shares, min(shares, max_shares))

        return shares

    def close_position(self, pos, exit_price, timestamp, reason, bar_num):
        """Close position and record trade using position manager"""
        # Close position using position manager
        # FIX: Pass timestamp to get correct exit time instead of wall clock
        trade_record = self.pm.close_position(pos['symbol'], exit_price, reason, exit_time=timestamp)

        # Deduct commission costs (per requirements)
        commission_cost = pos['shares'] * self.commission_per_share * 2  # Entry + exit
        trade_record['pnl'] -= commission_cost

        # Add backtester-specific fields
        duration_min = (timestamp - pos['entry_time']).total_seconds() / 60
        pnl_per_share = trade_record['pnl'] / pos['shares']

        trade = {
            **trade_record,  # Include all PM fields (symbol, side, entry, exit, pnl, etc.)
            'pnl_per_share': pnl_per_share,
            'pnl_pct': (pnl_per_share / pos['entry_price']) * 100,
            'duration_min': duration_min,
            'entry_bar': pos.get('entry_bar', 0),
            'exit_bar': bar_num,
            'commission': commission_cost  # Track commissions paid
        }

        return trade

    def save_trades_to_json(self):
        """Save all trades to JSON file for analysis"""
        if not self.trades:
            return None

        # Create results directory if it doesn't exist
        results_dir = Path(__file__).parent / 'results'
        results_dir.mkdir(exist_ok=True)

        # Generate filename with date
        date_str = self.test_date.strftime('%Y%m%d')
        filename = results_dir / f'backtest_trades_{date_str}.json'

        # Convert trades to JSON-serializable format
        trades_json = []
        for trade in self.trades:
            trade_copy = trade.copy()
            # Convert datetime objects to ISO strings
            if isinstance(trade_copy.get('entry_time'), datetime):
                trade_copy['entry_time'] = trade_copy['entry_time'].isoformat()
            if isinstance(trade_copy.get('exit_time'), datetime):
                trade_copy['exit_time'] = trade_copy['exit_time'].isoformat()
            trades_json.append(trade_copy)

        # Save to JSON
        with open(filename, 'w') as f:
            json.dump(trades_json, f, indent=2)

        print(f"\n💾 Saved {len(trades_json)} trades to: {filename}")
        return filename

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

        # CVD FILTER ANALYTICS (Oct 19, 2025)
        if self.cvd_analytics['total_blocks'] > 0:
            print(f"\n🔬 CVD FILTER ANALYTICS:")
            print(f"  Total blocks: {self.cvd_analytics['total_blocks']}")
            print(f"  LONG blocks: {self.cvd_analytics['long_blocks']}")
            print(f"  SHORT blocks: {self.cvd_analytics['short_blocks']}")
            print(f"  Symbols blocked: {len(self.cvd_analytics['symbols_blocked'])}")
            if self.cvd_analytics['blocks_by_reason']:
                print(f"\n  Block reasons:")
                for reason, count in sorted(self.cvd_analytics['blocks_by_reason'].items(),
                                           key=lambda x: x[1], reverse=True):
                    print(f"    • {reason}: {count}")
        elif self.config.get('confirmation', {}).get('cvd', {}).get('enabled', False):
            print(f"\n🔬 CVD FILTER ANALYTICS:")
            print(f"  CVD enabled but no entries were blocked")
        else:
            print(f"\n🔬 CVD FILTER: DISABLED")

        print(f"\n{'='*80}")
        print(f"DETAILED TRADE LOG:")
        print(f"{'='*80}")

        for idx, trade in df.iterrows():
            sign = '+' if trade['pnl'] > 0 else ''
            # Convert times to Eastern Time for display
            entry_et = trade['entry_time'].astimezone(pytz.timezone('US/Eastern'))
            exit_et = trade['exit_time'].astimezone(pytz.timezone('US/Eastern'))
            print(f"\n{idx+1}. {trade['symbol']} {trade['side']}")
            print(f"   Entry: ${trade['entry_price']:.2f} @ {entry_et.strftime('%H:%M')}")
            print(f"   Exit:  ${trade['exit_price']:.2f} @ {exit_et.strftime('%H:%M')} ({trade['reason']})")
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
