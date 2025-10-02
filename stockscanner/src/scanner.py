"""
PS60 Pre-Market Scanner - Fixed Version
Scans for trading setups using IBKR data
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from ib_insync import IB, Stock, util
from loguru import logger
import yaml
import time
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.modules.data_processor import DataProcessor
from src.modules.filter_engine import PS60FilterEngine
from src.modules.watchlist_generator import WatchlistGenerator


class PS60Scanner:
    """Fixed PS60 scanner with proper event loop handling"""

    def __init__(self, config_path: str = None):
        """Initialize scanner with configuration"""
        self.config = self._load_config(config_path)
        self.ib = None
        self.processor = DataProcessor(self.config['scan_config'])
        self.filter_engine = PS60FilterEngine(self.config['scan_config'])
        self.output_generator = WatchlistGenerator(self.config['scan_config'])
        self._setup_logging()

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'scanner_config.yaml'

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _setup_logging(self):
        """Configure logging"""
        log_config = self.config['scan_config'].get('logging', {})
        log_level = log_config.get('level', 'INFO')
        logger.remove()
        logger.add(sys.stderr, level=log_level, format="{time:HH:mm:ss} | {level} | {message}")

    def connect(self) -> bool:
        """Connect to IBKR"""
        try:
            self.ib = IB()
            client_id = self.config['scan_config']['ibkr']['client_id']
            self.ib.connect(
                self.config['scan_config']['ibkr']['host'],
                self.config['scan_config']['ibkr']['port'],
                clientId=client_id
            )
            logger.info(f"Connected to IBKR (client_id: {client_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")

    def _get_stock_universe(self) -> List[str]:
        """Get list of stocks to scan"""
        universe_config = self.config['scan_config']['universe']

        # For tomorrow's setups, use a broader universe
        symbols = universe_config.get('custom_symbols', [])

        # Add major index components - top movers and liquid stocks
        major_stocks = [
            'SPY', 'QQQ', 'TSLA', 'NVDA', 'AMD', 'META', 'AAPL', 'MSFT', 'AMZN', 'GOOGL',
            'NFLX', 'COIN', 'PLTR', 'SOFI', 'HOOD', 'GME', 'AMC', 'PYPL', 'SQ', 'UBER'
        ]

        # Combine and remove duplicates
        all_symbols = list(set(symbols + major_stocks))

        # Apply max limit if configured
        max_symbols = universe_config.get('max_symbols', 100)
        if len(all_symbols) > max_symbols:
            logger.warning(f"Limiting to {max_symbols} symbols")
            all_symbols = all_symbols[:max_symbols]

        return all_symbols

    def scan_symbol(self, symbol: str, scan_date: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Scan a single symbol

        Args:
            symbol: Stock symbol
            scan_date: Date to scan (None for current date)

        Returns:
            Stock data dictionary or None
        """
        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')
            qualified = self.ib.qualifyContracts(contract)
            if not qualified:
                logger.warning(f"Could not qualify {symbol}")
                return None

            # Determine date range
            if scan_date:
                end_date = scan_date + timedelta(days=1)
                duration = "30 D"
            else:
                end_date = ''  # Current time
                duration = "30 D"

            # Get daily historical data
            daily_bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date if isinstance(end_date, str) else end_date.strftime('%Y%m%d %H:%M:%S'),
                durationStr=duration,
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1
            )

            if not daily_bars or len(daily_bars) < 20:
                logger.debug(f"Insufficient data for {symbol}")
                return None

            # Convert to DataFrame
            daily_df = util.df(daily_bars)
            daily_df['date'] = pd.to_datetime(daily_df['date'])
            daily_df.set_index('date', inplace=True)

            # Get the most recent trading day
            latest_idx = -1
            latest_day = daily_df.iloc[latest_idx]
            prev_day = daily_df.iloc[latest_idx - 1]

            # Calculate gap and RVOL
            gap_pct = ((latest_day['open'] - prev_day['close']) / prev_day['close']) * 100
            avg_volume = daily_df['volume'].iloc[-21:-1].mean()
            rvol = latest_day['volume'] / avg_volume if avg_volume > 0 else 0

            # Get intraday data for pivot points
            time.sleep(0.1)  # Rate limiting

            intraday_end = datetime.now() if not scan_date else scan_date.replace(hour=16)
            intraday_bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='' if not scan_date else intraday_end.strftime('%Y%m%d %H:%M:%S'),
                durationStr='1 D',
                barSizeSetting='1 hour',
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1
            )

            # Calculate pivots
            pivot_high = latest_day['high']
            pivot_low = latest_day['low']

            if intraday_bars and len(intraday_bars) >= 4:
                intraday_df = util.df(intraday_bars)
                # Use first 4 hours for pivots
                pivot_high = intraday_df.iloc[:4]['high'].max()
                pivot_low = intraday_df.iloc[:4]['low'].min()

            # Process data
            result = {
                'symbol': symbol,
                'valid': True,
                'current_price': float(latest_day['close']),
                'gap_pct': round(gap_pct, 2),
                'rvol': round(rvol, 2),
                'volume': int(latest_day['volume']),
                'pivot_high': float(pivot_high),
                'pivot_low': float(pivot_low),
                'prev_close': float(prev_day['close']),
                'open': float(latest_day['open']),
                'high': float(latest_day['high']),
                'low': float(latest_day['low']),
                'close': float(latest_day['close']),
                'dollar_volume': float(latest_day['volume'] * latest_day['close'] / 1e6),  # in millions
                'atr': float(daily_df['high'].iloc[-10:].max() - daily_df['low'].iloc[-10:].min()),
                'sma_20': float(daily_df['close'].iloc[-20:].mean()),
                'resistance': float(daily_df['high'].iloc[-20:].max()),
                'support': float(daily_df['low'].iloc[-20:].min())
            }

            # Calculate score
            score = 0
            if abs(gap_pct) >= 2.0: score += 30
            elif abs(gap_pct) >= 1.0: score += 15
            if rvol >= 2.0: score += 30
            elif rvol >= 1.5: score += 15
            result['score'] = score

            return result

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")
            return None

    def scan_for_setups(self, scan_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Scan all symbols for setups

        Args:
            scan_date: Date to scan (None for current date)

        Returns:
            Dictionary with scan results
        """
        start_time = time.time()

        if scan_date:
            logger.info(f"Scanning for {scan_date.date()}")
        else:
            logger.info("Scanning for current market conditions")

        # Connect to IBKR
        if not self.connect():
            return {'error': 'Failed to connect to IBKR'}

        try:
            # Get symbols
            symbols = self._get_stock_universe()
            logger.info(f"Scanning {len(symbols)} symbols...")

            # Scan each symbol
            all_stock_data = []
            failed_symbols = []

            for i, symbol in enumerate(symbols):
                # Progress update
                if (i + 1) % 10 == 0:
                    logger.info(f"Progress: {i+1}/{len(symbols)} symbols")

                # Scan symbol
                result = self.scan_symbol(symbol, scan_date)

                if result:
                    all_stock_data.append(result)

                    # Log significant movers
                    if abs(result['gap_pct']) >= 2.0 or result['rvol'] >= 2.0:
                        logger.success(f"  {symbol}: Gap {result['gap_pct']:+.1f}%, RVOL {result['rvol']:.1f}x")
                else:
                    failed_symbols.append(symbol)

                # Rate limiting
                time.sleep(0.2)

            # Apply filters
            long_candidates, short_candidates = self.filter_engine.filter_candidates(all_stock_data)

            # Sort by score
            long_candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
            short_candidates.sort(key=lambda x: x.get('score', 0), reverse=True)

            # Market context
            market_context = self.filter_engine.assess_market_context({}, long_candidates + short_candidates)

            # Prepare results
            results = {
                'scan_date': scan_date.isoformat() if scan_date else datetime.now().isoformat(),
                'market_context': market_context,
                'long_candidates': long_candidates[:20],  # Top 20
                'short_candidates': short_candidates[:20],
                'total_scanned': len(symbols),
                'failed_symbols': failed_symbols,
                'timestamp': datetime.now(),
                'scan_time_seconds': time.time() - start_time
            }

            # Save outputs
            self.output_generator.generate_all_outputs(results)

            # Display results
            self._display_results(results)

            return results

        finally:
            self.disconnect()

    def _display_results(self, results: Dict[str, Any]):
        """Display scan results"""
        print("\n" + "="*80)
        print("PS60 SCANNER RESULTS")
        print("="*80)
        print(f"Scan Date: {results['scan_date']}")
        print(f"Total Scanned: {results['total_scanned']} symbols in {results['scan_time_seconds']:.1f}s")
        print(f"Market Context: {results['market_context']['bias'].upper()}")

        if results['long_candidates']:
            print("\n📈 LONG CANDIDATES:")
            for c in results['long_candidates'][:5]:
                print(f"  {c['symbol']:6} Gap: {c['gap_pct']:+5.1f}%  RVOL: {c['rvol']:4.1f}x  Score: {c['score']:3}")

        if results['short_candidates']:
            print("\n📉 SHORT CANDIDATES:")
            for c in results['short_candidates'][:5]:
                print(f"  {c['symbol']:6} Gap: {c['gap_pct']:+5.1f}%  RVOL: {c['rvol']:4.1f}x  Score: {c['score']:3}")

        if not results['long_candidates'] and not results['short_candidates']:
            print("\n⚠️ No significant setups found")

        print(f"\nFailed symbols: {len(results['failed_symbols'])}")
        print("\nOutput files generated:")
        print("  ✓ output/watchlist.csv")
        print("  ✓ output/scan_results.json")
        print("  ✓ output/research.md")


def main():
    """Main entry point"""
    import click

    @click.command()
    @click.option('--date', type=click.DateTime(['%Y-%m-%d']), help='Historical date to scan')
    @click.option('--config', type=click.Path(exists=True), help='Configuration file path')
    def run_scanner(date, config):
        """Run PS60 scanner for trading setups"""
        scanner = PS60Scanner(config)
        scanner.scan_for_setups(date)

    run_scanner()


if __name__ == "__main__":
    main()