"""
IBKR Synchronous Interface Module
Handles TWS/Gateway connection using ib_insync with proper event loop management
Fetches real market data from Interactive Brokers
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from ib_insync import IB, Stock, Contract, util
from loguru import logger
import time
import asyncio
import threading
import random
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.modules.connection_manager import ConnectionManager


class IBKRSyncInterface:
    """Synchronous interface for Interactive Brokers TWS API"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize IBKR connection interface

        Args:
            config: Configuration dictionary with IBKR settings
        """
        self.config = config['ibkr']
        self.ib = None
        self.connected = False
        self.max_concurrent = self.config.get('max_concurrent_requests', 50)
        self.request_delay = self.config.get('request_delay', 0.1)
        self._loop = None
        self._thread_local = threading.local()
        self.retry_count = self.config.get('retry_count', 3)
        self.retry_delay = self.config.get('retry_delay', 1.0)
        self.error_count = 0
        self.last_error_time = None
        self.adaptive_delay = self.request_delay
        # Initialize connection manager
        self.connection_mgr = ConnectionManager({
            'max_requests_per_second': self.config.get('max_requests_per_second', 10),
            'auto_recovery': True
        })

    def _ensure_event_loop(self):
        """Ensure an event loop exists in the current thread"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
        return loop

    def connect(self) -> bool:
        """
        Connect to IBKR TWS/Gateway

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Ensure event loop exists for this thread
            self._ensure_event_loop()

            # Create IB instance for this connection
            self.ib = IB()

            # Connect to TWS/Gateway
            self.ib.connect(
                host=self.config['host'],
                port=self.config['port'],
                clientId=self.config['client_id'],
                timeout=self.config.get('timeout', 30),
                readonly=False
            )

            # Set market data type (1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen)
            self.ib.reqMarketDataType(self.config.get('market_data_type', 1))

            self.connected = True
            logger.info(f"Connected to IBKR at {self.config['host']}:{self.config['port']} (client_id: {self.config['client_id']})")

            # Verify connection
            self._verify_connection()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.connected and self.ib:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")

        # Clean up event loop if we created one
        if self._loop and not self._loop.is_closed():
            self._loop.close()

    def _verify_connection(self):
        """Verify connection and market data subscriptions"""
        try:
            # Check account values
            account_values = self.ib.accountValues()
            if account_values:
                logger.info(f"Account connected with {len(account_values)} values")
            else:
                logger.warning("No account values received - check TWS login")

            # Test with a sample contract
            test_contract = Stock('AAPL', 'SMART', 'USD')
            qualified = self.ib.qualifyContracts(test_contract)
            if qualified:
                logger.info("Contract qualification test successful")
            else:
                logger.warning("Contract qualification failed - check permissions")

        except Exception as e:
            logger.warning(f"Connection verification warning: {e}")

    def create_contract(self, symbol: str) -> Optional[Contract]:
        """
        Create and qualify a stock contract with retry logic

        Args:
            symbol: Stock ticker symbol

        Returns:
            Qualified IB contract or None
        """
        for attempt in range(self.retry_count):
            try:
                contract = Stock(symbol, 'SMART', 'USD')
                qualified = self.ib.qualifyContracts(contract)
                if qualified:
                    # Reset error tracking on success
                    if self.error_count > 0:
                        self.error_count = max(0, self.error_count - 1)
                        self.adaptive_delay = max(self.request_delay, self.adaptive_delay * 0.9)
                    return qualified[0]
                else:
                    logger.warning(f"Could not qualify contract for {symbol}")
                    if attempt < self.retry_count - 1:
                        time.sleep(self.retry_delay * (attempt + 1))
                    else:
                        return None
            except Exception as e:
                self._handle_error(f"Error creating contract for {symbol}", e)
                if attempt < self.retry_count - 1:
                    wait_time = self.retry_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"Retrying contract creation for {symbol} in {wait_time:.1f}s (attempt {attempt + 1}/{self.retry_count})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to create contract for {symbol} after {self.retry_count} attempts")
                    return None
        return None

    def get_historical_data(
        self,
        symbol: str,
        end_date: datetime,
        duration: str = "30 D",
        bar_size: str = "1 day"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol with retry logic

        Args:
            symbol: Stock ticker symbol
            end_date: End date for historical data
            duration: Time period (e.g., "30 D", "1 M")
            bar_size: Bar size (e.g., "1 day", "1 hour")

        Returns:
            DataFrame with historical data or None if error
        """
        for attempt in range(self.retry_count):
            try:
                contract = self.create_contract(symbol)
                if not contract:
                    return None

                # Format end date for IBKR
                end_date_str = end_date.strftime('%Y%m%d %H:%M:%S')

                # Rate limiting and health check
                self.connection_mgr.before_request()
                start_time = time.time()

                # Request historical data
                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=end_date_str,
                    durationStr=duration,
                    barSizeSetting=bar_size,
                    whatToShow='TRADES',
                    useRTH=False,  # Include pre/post market
                    formatDate=1,
                    keepUpToDate=False
                )

                if not bars:
                    if attempt < self.retry_count - 1:
                        logger.warning(f"No historical data for {symbol}, retrying...")
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    else:
                        logger.warning(f"No historical data for {symbol} after {self.retry_count} attempts")
                        return None

                # Convert to DataFrame
                df = util.df(bars)
                if df.empty:
                    return None

                # Rename columns to match expected format
                df = df.rename(columns={
                    'date': 'date',
                    'open': 'open',
                    'high': 'high',
                    'low': 'low',
                    'close': 'close',
                    'volume': 'volume',
                    'average': 'average',
                    'barCount': 'barCount'
                })

                # Ensure date is datetime
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)

                # Add adaptive delay to respect rate limits
                time.sleep(self.adaptive_delay)

                # Success - reduce error count
                if self.error_count > 0:
                    self.error_count = max(0, self.error_count - 1)
                    self.adaptive_delay = max(self.request_delay, self.adaptive_delay * 0.95)

                # Record success
                response_time = time.time() - start_time
                self.connection_mgr.after_request(True, response_time)

                return df

            except Exception as e:
                self._handle_error(f"Error fetching historical data for {symbol}", e)
                self.connection_mgr.after_request(False, error=str(e))

                if attempt < self.retry_count - 1:
                    # Exponential backoff with jitter
                    wait_time = self.retry_delay * (2 ** attempt) + random.uniform(0, 2)
                    logger.info(f"Retrying historical data for {symbol} in {wait_time:.1f}s (attempt {attempt + 1}/{self.retry_count})")
                    time.sleep(wait_time)

                    # Check if we need to reconnect
                    if not self.is_connected():
                        logger.warning("Connection lost, attempting to reconnect...")
                        if not self.reconnect():
                            logger.error("Failed to reconnect")
                            return None
                else:
                    logger.error(f"Failed to fetch historical data for {symbol} after {self.retry_count} attempts")
                    return None

        return None

    def get_market_data(self, symbol: str, snapshot: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get current market data for a symbol

        Args:
            symbol: Stock ticker symbol
            snapshot: If True, get snapshot data; if False, stream data

        Returns:
            Dictionary with market data or None
        """
        try:
            contract = self.create_contract(symbol)
            if not contract:
                return None

            if snapshot:
                # Request snapshot data
                tickers = self.ib.reqTickers(contract)
                if tickers:
                    ticker = tickers[0]
                else:
                    # Try market data subscription
                    self.ib.reqMktData(contract, '', snapshot, False)
                    self.ib.sleep(2)  # Wait for data
                    ticker = self.ib.ticker(contract)

                if ticker:
                    return {
                        'symbol': symbol,
                        'last': ticker.last if not util.isNan(ticker.last) else ticker.close,
                        'bid': ticker.bid if not util.isNan(ticker.bid) else 0,
                        'ask': ticker.ask if not util.isNan(ticker.ask) else 0,
                        'volume': ticker.volume if not util.isNan(ticker.volume) else 0,
                        'high': ticker.high if not util.isNan(ticker.high) else 0,
                        'low': ticker.low if not util.isNan(ticker.low) else 0,
                        'close': ticker.close if not util.isNan(ticker.close) else 0,
                        'timestamp': datetime.now()
                    }

            return None

        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
        finally:
            # Cancel market data subscription if streaming
            if not snapshot and contract:
                self.ib.cancelMktData(contract)

    def get_pre_market_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get pre-market quote for a symbol
        Uses snapshot data which includes pre-market prices

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with quote data or None
        """
        return self.get_market_data(symbol, snapshot=True)

    def batch_get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get quotes for multiple symbols with rate limiting

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to quote data
        """
        quotes = {}

        for i, symbol in enumerate(symbols):
            if i > 0 and i % 10 == 0:
                # Pause every 10 symbols to respect rate limits
                time.sleep(1)

            quote = self.get_market_data(symbol, snapshot=True)
            if quote:
                quotes[symbol] = quote
            else:
                logger.warning(f"No quote data for {symbol}")

            # Small delay between requests
            time.sleep(self.request_delay)

        return quotes

    def get_intraday_bars(
        self,
        symbol: str,
        date: datetime,
        bar_size: str = "1 hour"
    ) -> Optional[pd.DataFrame]:
        """
        Get intraday bars for a specific date with retry logic

        Args:
            symbol: Stock ticker symbol
            date: Date to fetch data for
            bar_size: Bar size (default "1 hour" for 60-min bars)

        Returns:
            DataFrame with intraday data or None if error
        """
        for attempt in range(self.retry_count):
            try:
                # Set end date to end of trading day
                end_date = date.replace(hour=16, minute=0, second=0)

                # Fetch intraday data (already has retry logic)
                result = self.get_historical_data(
                    symbol=symbol,
                    end_date=end_date,
                    duration="1 D",
                    bar_size=bar_size
                )

                if result is not None or attempt == self.retry_count - 1:
                    return result

                # If None returned, wait before retry
                wait_time = self.retry_delay * (attempt + 1)
                logger.info(f"Retrying intraday data for {symbol} in {wait_time:.1f}s")
                time.sleep(wait_time)

            except Exception as e:
                self._handle_error(f"Error fetching intraday data for {symbol}", e)
                if attempt < self.retry_count - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                else:
                    return None

        return None

    def get_contract_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed contract information

        Args:
            symbol: Stock ticker symbol

        Returns:
            Contract details dictionary or None
        """
        try:
            contract = self.create_contract(symbol)
            if not contract:
                return None

            details_list = self.ib.reqContractDetails(contract)

            if details_list:
                detail = details_list[0]
                return {
                    'symbol': symbol,
                    'longName': detail.longName,
                    'industry': detail.industry,
                    'category': detail.category,
                    'subcategory': detail.subcategory,
                    'minTick': detail.minTick,
                    'exchange': detail.validExchanges
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching contract details for {symbol}: {e}")
            return None

    def _handle_error(self, context: str, error: Exception):
        """Handle errors and adjust rate limiting"""
        self.error_count += 1
        self.last_error_time = time.time()

        # Increase delay if getting too many errors
        if self.error_count > 5:
            self.adaptive_delay = min(5.0, self.adaptive_delay * 1.5)
            logger.warning(f"Increased adaptive delay to {self.adaptive_delay:.2f}s due to errors")

        error_str = str(error)
        if 'pacing violation' in error_str.lower() or 'rate' in error_str.lower():
            # Rate limit error - back off more aggressively
            self.adaptive_delay = min(10.0, self.adaptive_delay * 2)
            logger.warning(f"Rate limit detected, increasing delay to {self.adaptive_delay:.2f}s")
        elif 'not connected' in error_str.lower() or 'connection' in error_str.lower():
            # Connection issue - might need to reconnect
            logger.error(f"{context}: Connection issue - {error}")
            if not self.is_connected():
                logger.info("Attempting to reconnect...")
                self.reconnect()
        else:
            logger.error(f"{context}: {error}")

    def reconnect(self) -> bool:
        """Attempt to reconnect to IBKR"""
        try:
            if self.ib and self.ib.isConnected():
                self.ib.disconnect()
            time.sleep(2)
            return self.connect()
        except Exception as e:
            logger.error(f"Failed to reconnect: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to IBKR"""
        return self.connected and self.ib and self.ib.isConnected()