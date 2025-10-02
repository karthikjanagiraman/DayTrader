"""
PS60 Pre-Market Scanner - Main Scanner
Single consolidated scanner with all functionality
Uses synchronous IBKR interface to fetch real market data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import click
import yaml
import pandas as pd
from loguru import logger
from tabulate import tabulate
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.ibkr_sync_interface import IBKRSyncInterface
from src.modules.ibkr_thread_pool_v2 import MultithreadedIBKR
from src.modules.data_processor import DataProcessor
from src.modules.filter_engine import PS60FilterEngine
from src.modules.advanced_pattern_detector import AdvancedPatternDetector
from src.modules.watchlist_generator import WatchlistGenerator


class PS60Scanner:
    """Main PS60 scanner with all functionality consolidated"""

    def __init__(self, config_path: str = None, use_advanced_patterns: bool = False, max_workers: int = 5):
        """
        Initialize scanner with configuration

        Args:
            config_path: Path to configuration file
            use_advanced_patterns: Enable advanced pattern detection
            max_workers: Maximum number of concurrent threads for processing
        """
        # Load configuration
        self.config = self._load_config(config_path)
        self.use_advanced_patterns = use_advanced_patterns
        self.max_workers = max_workers

        # Initialize IBKR connection (thread-safe for multithreading)
        self.use_multithreaded = max_workers > 1
        if self.use_multithreaded:
            # Use thread-local connections for multithreaded access
            self.ibkr_mt = MultithreadedIBKR(self.config['scan_config'], max_workers=max_workers)
        else:
            # Use single connection for single-threaded access
            self.ibkr = IBKRSyncInterface(self.config['scan_config'])

        # Initialize processing modules (thread-safe)
        self.processor = DataProcessor(self.config['scan_config'])
        self.filter_engine = PS60FilterEngine(self.config['scan_config'])
        self.output_generator = WatchlistGenerator(self.config['scan_config'])

        # Initialize advanced pattern detector if enabled
        if use_advanced_patterns:
            self.pattern_detector = AdvancedPatternDetector(lookback_days=15)

        # Thread safety
        self.data_lock = threading.Lock()
        self.progress_lock = threading.Lock()
        self.processed_count = 0

        # Setup logging
        self._setup_logging()

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_path is None:
            # Try to determine best config based on context
            config_path = Path(__file__).parent.parent / 'config' / 'scanner_config.yaml'

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        return config

    def _setup_logging(self):
        """Configure logging"""
        log_config = self.config['scan_config'].get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('log_file', './logs/scanner.log')

        # Ensure log directory exists
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            level=log_level,
            rotation=log_config.get('max_file_size', '10MB'),
            retention=log_config.get('backup_count', 5)
        )

    def _get_stock_universe(self) -> List[str]:
        """
        Get list of stocks to scan based on configuration

        Returns:
            List of ticker symbols
        """
        universe_config = self.config['scan_config']['universe']

        # Start with custom symbols
        symbols = universe_config.get('custom_symbols', [])

        # Add volatile stocks for better historical results
        volatile_stocks = [
            'TSLA', 'NVDA', 'AMD', 'META', 'AMZN', 'GOOGL', 'AAPL', 'MSFT',
            'NFLX', 'ROKU', 'PYPL', 'SHOP', 'SNAP', 'UBER', 'LYFT', 'DOCU',
            'ZM', 'HOOD', 'COIN', 'PLTR', 'SOFI', 'RIVN', 'LCID', 'NIO'
        ]

        # Add index components
        indexes = universe_config.get('indexes', [])
        if 'NASDAQ100' in indexes:
            symbols.extend([
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
                'AVGO', 'PEP', 'COST', 'ADBE', 'CSCO', 'CMCSA', 'NFLX',
                'AMD', 'INTC', 'TMUS', 'TXN', 'QCOM', 'AMGN'
            ])

        if 'SP500' in indexes:
            symbols.extend([
                'JPM', 'JNJ', 'V', 'PG', 'UNH', 'HD', 'MA',
                'DIS', 'BAC', 'XOM', 'CVX', 'ABBV', 'KO', 'WMT'
            ])

        # Add volatile stocks if historical mode
        mode = self.config['scan_config'].get('mode', 'live')
        if mode == 'historical' or mode == 'backtest':
            symbols.extend(volatile_stocks)

        # Remove duplicates
        symbols = list(set(symbols))

        # Remove problematic symbols
        problematic = ['BRK.B', 'BRK.A', 'TWTR', 'PELOTON', 'SQ']
        symbols = [s for s in symbols if s not in problematic]

        # Apply max symbols limit
        max_symbols = universe_config.get('max_symbols', 100)
        if len(symbols) > max_symbols:
            logger.warning(f"Limiting to {max_symbols} symbols")
            symbols = symbols[:max_symbols]

        return symbols

    def _fetch_and_process_symbol(
        self,
        symbol: str,
        scan_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch and process a single symbol (thread-safe)

        Args:
            symbol: Stock symbol
            scan_date: Date to scan

        Returns:
            Processed stock data or None
        """
        try:
            # Fetch historical data
            daily_df = self.ibkr.get_historical_data(
                symbol=symbol,
                end_date=scan_date + timedelta(days=1),
                duration="30 D",
                bar_size="1 day"
            )

            if daily_df is None or len(daily_df) < 20:
                return None

            # Find scan date index
            scan_date_only = scan_date.date()
            scan_day_idx = None

            for idx in range(len(daily_df)):
                if daily_df.index[idx].date() == scan_date_only:
                    scan_day_idx = idx
                    break

            if scan_day_idx is None:
                scan_day_idx = len(daily_df) - 1

            if scan_day_idx < 1:
                return None

            # Process the symbol
            return self._process_symbol(symbol, scan_date, scan_day_idx, daily_df)

        except Exception as e:
            logger.error(f"Error fetching/processing {symbol}: {e}")
            return None

    def _process_symbol(
        self,
        symbol: str,
        scan_date: datetime,
        scan_day_idx: int,
        daily_df: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single symbol

        Args:
            symbol: Stock symbol
            scan_date: Date to scan
            scan_day_idx: Index of scan date in dataframe
            daily_df: Daily OHLCV data

        Returns:
            Processed stock data or None
        """
        try:
            scan_day = daily_df.iloc[scan_day_idx]
            prev_day = daily_df.iloc[scan_day_idx - 1]

            # Quick pre-filter based on gap
            gap_pct = ((scan_day['open'] - prev_day['close']) / prev_day['close']) * 100
            gap_threshold = self.config['scan_config']['filters'].get('gap_threshold', 2.0)

            # For historical mode, be more lenient
            mode = self.config['scan_config'].get('mode', 'live')
            if mode in ['historical', 'backtest']:
                gap_threshold = self.config['scan_config']['filters'].get('gap_threshold', 1.0)

            # Calculate daily RVOL for filtering
            avg_volume = daily_df['volume'].iloc[max(0, scan_day_idx-20):scan_day_idx].mean()
            daily_rvol = scan_day['volume'] / avg_volume if avg_volume > 0 else 0

            # For historical mode, check daily RVOL as proxy
            use_daily_fallback = self.config['scan_config']['filters'].get('use_daily_rvol_fallback', False)
            daily_rvol_threshold = self.config['scan_config']['filters'].get('daily_rvol_threshold', 1.2)

            if use_daily_fallback:
                if daily_rvol < daily_rvol_threshold and abs(gap_pct) < gap_threshold:
                    return None

            # Fetch intraday data
            if self.use_multithreaded:
                # Use thread-local connection
                intraday_df = self.ibkr_mt.thread_local_mgr.get_intraday_bars(
                    symbol=symbol,
                    date=scan_date,
                    bar_size="1 hour"
                )
            else:
                # Use single connection
                intraday_df = self.ibkr.get_intraday_bars(
                    symbol=symbol,
                    date=scan_date,
                    bar_size="1 hour"
                )

            # Create quote for processing
            historical_volume_factor = self.config['scan_config']['filters'].get('historical_volume_factor', 0.3)
            quote = {
                'symbol': symbol,
                'last': scan_day['open'],
                'volume': int(scan_day['volume'] * historical_volume_factor),
                'high': scan_day['high'],
                'low': scan_day['low'],
                'close': prev_day['close']
            }

            # Process with data processor
            processed = self.processor.process_stock_data(
                symbol=symbol,
                daily_df=daily_df.iloc[:scan_day_idx + 1],
                intraday_df=intraday_df,
                quote=quote
            )

            if processed.get('valid', False):
                processed['daily_rvol'] = daily_rvol
                processed['scan_day_volume'] = scan_day['volume']

                # Add advanced pattern analysis if enabled
                if self.use_advanced_patterns and scan_day_idx >= 15:
                    analysis_df = daily_df.iloc[scan_day_idx-15:scan_day_idx]
                    setup_analysis = self.pattern_detector.analyze_setup(
                        analysis_df,
                        scan_day['open']
                    )
                    processed['pattern_analysis'] = setup_analysis
                    processed['pattern_score'] = setup_analysis['setup_score']

                return processed

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

        return None

    def _scan_multithreaded(
        self,
        symbols: List[str],
        scan_date: datetime,
        all_stock_data: List[Dict],
        failed_symbols: List[str],
        total_symbols: int
    ):
        """
        Scan symbols using multithreaded approach with thread-local connections

        Args:
            symbols: List of symbols to scan
            scan_date: Date to scan for
            all_stock_data: List to store processed data
            failed_symbols: List to store failed symbols
            total_symbols: Total number of symbols for progress
        """
        # Process each symbol in a worker thread with its own connection
        def process_symbol_mt(symbol: str) -> Optional[Dict[str, Any]]:
            """Process symbol with thread-local connection"""
            try:
                # Fetch daily data (15 days lookback)
                end_date = scan_date + timedelta(days=1)
                daily_df = self.ibkr_mt.thread_local_mgr.get_historical_data(
                    symbol=symbol,
                    end_date=end_date,
                    duration="30 D",
                    bar_size="1 day"
                )

                if daily_df is None or daily_df.empty:
                    logger.warning(f"No daily data for {symbol}")
                    return None

                # Find the scan date in daily data
                daily_df = daily_df.sort_index()
                scan_date_str = scan_date.strftime('%Y-%m-%d')
                scan_day_idx = None

                for idx, date in enumerate(daily_df.index):
                    if date.strftime('%Y-%m-%d') == scan_date_str:
                        scan_day_idx = idx
                        break

                if scan_day_idx is None or scan_day_idx < 1:
                    logger.warning(f"Scan date {scan_date_str} not found in data for {symbol}")
                    return None

                # Process the symbol
                result = self._process_symbol(symbol, scan_date, scan_day_idx, daily_df)

                # Update progress
                with self.progress_lock:
                    self.processed_count += 1
                    if self.processed_count % 10 == 0 or self.processed_count == total_symbols:
                        progress_pct = (self.processed_count / total_symbols) * 100
                        print(f"Progress: {self.processed_count}/{total_symbols} symbols ({progress_pct:.0f}%)")

                return result

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                return None

        # Use ThreadPoolExecutor to process symbols
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_symbol = {
                executor.submit(process_symbol_mt, symbol): symbol
                for symbol in symbols
            }

            # Collect results
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result(timeout=15)
                    if result:
                        with self.data_lock:
                            all_stock_data.append(result)
                    else:
                        with self.data_lock:
                            failed_symbols.append(symbol)
                except Exception as e:
                    logger.error(f"Error getting result for {symbol}: {e}")
                    with self.data_lock:
                        failed_symbols.append(symbol)

    def scan_historical_date(self, scan_date: datetime) -> Dict[str, Any]:
        """
        Scan stocks for a historical date using multithreading

        Args:
            scan_date: Date to scan for

        Returns:
            Dictionary with scan results
        """
        start_time = time.time()
        logger.info(f"Starting multithreaded scan for {scan_date.date()}")
        logger.info(f"Advanced patterns: {'Enabled' if self.use_advanced_patterns else 'Disabled'}")
        logger.info(f"Max workers: {self.max_workers}")

        # Connect to IBKR (only for single-threaded mode)
        if not self.use_multithreaded:
            if not self.ibkr.connect():
                logger.error("Failed to connect to IBKR TWS/Gateway")
                logger.error("Please ensure TWS or IB Gateway is running on port 7497 (paper) or 7496 (live)")
                return {'error': 'Connection failed - TWS/Gateway not available'}

        try:
            # Get stock universe
            symbols = self._get_stock_universe()
            total_symbols = len(symbols)
            logger.info(f"Scanning {total_symbols} symbols using {self.max_workers} threads")

            # Reset progress counter
            self.processed_count = 0

            # Process symbols concurrently
            all_stock_data = []
            failed_symbols = []

            if self.use_multithreaded:
                # Use multithreaded fetching with thread-local connections
                self._scan_multithreaded(symbols, scan_date, all_stock_data, failed_symbols, total_symbols)
            else:
                # Use single-threaded processing without ThreadPoolExecutor
                for i, symbol in enumerate(symbols):
                    try:
                        result = self._fetch_and_process_symbol(symbol, scan_date)

                        # Update progress
                        self.processed_count = i + 1
                        if self.processed_count % 10 == 0 or self.processed_count == total_symbols:
                            progress_pct = (self.processed_count / total_symbols) * 100
                            print(f"Progress: {self.processed_count}/{total_symbols} symbols ({progress_pct:.0f}%)")
                            logger.info(f"Processed {self.processed_count}/{total_symbols} symbols")

                        # Store result
                        if result:
                            all_stock_data.append(result)
                        else:
                            failed_symbols.append(symbol)

                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        failed_symbols.append(symbol)

            logger.info(f"Processed {len(all_stock_data)} valid stocks in {time.time()-start_time:.1f}s")

            # Log connection status if available
            if not self.use_multithreaded and hasattr(self.ibkr, 'connection_mgr'):
                status = self.ibkr.connection_mgr.get_status()
                logger.info(f"Connection health: {status['health_score']:.1f}%, "
                          f"Success: {status['success_count']}, "
                          f"Errors: {status['error_count']}, "
                          f"Rate: {status['current_rate_limit']:.1f} req/s")

            # Apply filters
            long_candidates, short_candidates = self.filter_engine.filter_candidates(all_stock_data)

            # Sort by score
            if self.use_advanced_patterns:
                # Sort by pattern score if available
                long_candidates.sort(key=lambda x: x.get('pattern_score', x.get('score', 0)), reverse=True)
                short_candidates.sort(key=lambda x: x.get('pattern_score', x.get('score', 0)), reverse=True)
            else:
                long_candidates.sort(key=lambda x: x['score'], reverse=True)
                short_candidates.sort(key=lambda x: x['score'], reverse=True)

            # Limit candidates
            max_candidates = self.config['scan_config']['output'].get('max_candidates', 20)
            long_candidates = long_candidates[:max_candidates]
            short_candidates = short_candidates[:max_candidates]

            # Assess market context
            market_context = self.filter_engine.assess_market_context(
                {},
                long_candidates + short_candidates
            )

            # Generate outputs
            results = {
                'scan_date': scan_date,
                'long_candidates': long_candidates,
                'short_candidates': short_candidates,
                'market_context': market_context,
                'total_scanned': len(symbols),
                'failed_symbols': failed_symbols,
                'timestamp': datetime.now(),
                'scan_time_seconds': time.time() - start_time
            }

            # Save outputs
            self.output_generator.generate_all_outputs(results)

            return results

        finally:
            # Disconnect
            if self.use_multithreaded:
                # Cleanup thread-local connections
                self.ibkr_mt.cleanup()
            else:
                # Disconnect single connection
                self.ibkr.disconnect()

    def scan_pre_market(self) -> Dict[str, Any]:
        """
        Run live pre-market scan

        Returns:
            Dictionary with scan results
        """
        return self.scan_historical_date(datetime.now())

    def display_results(self, results: Dict[str, Any]):
        """Display scan results in terminal"""

        print("\n" + "="*80)
        print(f"PS60 PRE-MARKET SCANNER RESULTS")
        print(f"Scan Date: {results['scan_date']}")
        print(f"Total Scanned: {results['total_scanned']} ({results.get('scan_time_seconds', 0):.1f}s)")
        print("="*80)

        # Market Context
        context = results['market_context']
        print(f"\nMARKET CONTEXT:")
        print(f"Bias: {context['bias'].upper()}")
        print(f"Summary: {context['summary']}")

        # Long Candidates
        print(f"\nLONG CANDIDATES ({len(results['long_candidates'])}):")
        if results['long_candidates']:
            long_table = []
            for c in results['long_candidates'][:10]:
                score = c.get('pattern_score', c.get('score', 0))
                long_table.append([
                    c['symbol'],
                    f"${c['current_price']:.2f}",
                    f"{c['gap_pct']:+.2f}%",
                    f"{c['rvol']:.1f}x",
                    f"{c['rr_ratio']:.1f}:1",
                    f"{score:.0f}",
                    c['rationale'][:40] + "..." if len(c['rationale']) > 40 else c['rationale']
                ])

            print(tabulate(
                long_table,
                headers=['Symbol', 'Price', 'Gap%', 'RVOL', 'R:R', 'Score', 'Rationale'],
                tablefmt='grid'
            ))
        else:
            print("No long candidates found")

        # Short Candidates
        print(f"\nSHORT CANDIDATES ({len(results['short_candidates'])}):")
        if results['short_candidates']:
            short_table = []
            for c in results['short_candidates'][:10]:
                score = c.get('pattern_score', c.get('score', 0))
                short_table.append([
                    c['symbol'],
                    f"${c['current_price']:.2f}",
                    f"{c['gap_pct']:+.2f}%",
                    f"{c['rvol']:.1f}x",
                    f"{c['rr_ratio']:.1f}:1",
                    f"{score:.0f}",
                    c['rationale'][:40] + "..." if len(c['rationale']) > 40 else c['rationale']
                ])

            print(tabulate(
                short_table,
                headers=['Symbol', 'Price', 'Gap%', 'RVOL', 'R:R', 'Score', 'Rationale'],
                tablefmt='grid'
            ))
        else:
            print("No short candidates found")

        # Failed symbols (if any)
        if 'failed_symbols' in results and results['failed_symbols']:
            print(f"\nFailed to process: {', '.join(results['failed_symbols'][:10])}")
            if len(results['failed_symbols']) > 10:
                print(f"... and {len(results['failed_symbols']) - 10} more")

        print("\n" + "="*80)


@click.command()
@click.option(
    '--date',
    help='Historical date to scan (YYYY-MM-DD format)',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None
)
@click.option(
    '--config',
    help='Path to configuration file',
    type=click.Path(exists=True),
    default=None
)
@click.option(
    '--live',
    help='Run live pre-market scan',
    is_flag=True,
    default=False
)
@click.option(
    '--advanced',
    help='Enable advanced pattern detection',
    is_flag=True,
    default=False
)
@click.option(
    '--threads',
    help='Number of threads for parallel processing (default: 5)',
    type=int,
    default=5
)
def main(date, config, live, advanced, threads):
    """PS60 Pre-Market Scanner - Multithreaded Version"""

    # Determine config file
    if config is None:
        if date or not live:
            # Use backtest config for historical scans
            config = Path(__file__).parent.parent / 'config' / 'scanner_config_backtest.yaml'
        else:
            # Use regular config for live scans
            config = Path(__file__).parent.parent / 'config' / 'scanner_config.yaml'

    scanner = PS60Scanner(config, use_advanced_patterns=advanced, max_workers=threads)

    if live:
        # Run live pre-market scan
        results = scanner.scan_pre_market()
    elif date:
        # Run historical scan for specified date
        results = scanner.scan_historical_date(date)
    else:
        # Default to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        results = scanner.scan_historical_date(yesterday)

    # Display results
    if 'error' not in results:
        scanner.display_results(results)
        print(f"\nOutput files generated:")
        print(f"  ✓ output/watchlist.csv")
        print(f"  ✓ output/scan_results.json")
        print(f"  ✓ output/research.md")
    else:
        logger.error(f"Scan failed: {results['error']}")
        print(f"\n❌ ERROR: {results['error']}")
        print("\nPlease ensure:")
        print("  1. TWS or IB Gateway is running")
        print("  2. API is enabled in TWS/Gateway settings")
        print("  3. Port 7497 (paper) or 7496 (live) is correct")
        print("  4. You are logged in to TWS/Gateway")


if __name__ == "__main__":
    main()