"""
IBKR Thread-Local Connection Manager
Each thread creates and manages its own IBKR connection
"""

import threading
from typing import Optional, Dict, Any, List, Callable
import pandas as pd
from datetime import datetime
from loguru import logger
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

from src.modules.ibkr_sync_interface import IBKRSyncInterface


class ThreadLocalIBKR:
    """Thread-local IBKR connection manager"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize thread-local storage for IBKR connections

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self._local = threading.local()
        self._client_id_counter = 0
        self._lock = threading.Lock()

    def _get_next_client_id(self) -> int:
        """Get next available client ID"""
        with self._lock:
            client_id = self.config['ibkr']['client_id'] + self._client_id_counter
            self._client_id_counter += 1
            return client_id

    def _get_connection(self) -> IBKRSyncInterface:
        """
        Get or create connection for current thread

        Returns:
            IBKRSyncInterface instance for this thread
        """
        # Check if this thread already has a connection
        if not hasattr(self._local, 'connection'):
            # Create new connection for this thread
            thread_config = self.config.copy()
            thread_config['ibkr'] = self.config['ibkr'].copy()
            thread_config['ibkr']['client_id'] = self._get_next_client_id()

            # Create connection
            conn = IBKRSyncInterface(thread_config)

            # Connect
            if conn.connect():
                self._local.connection = conn
                logger.info(f"Thread {threading.current_thread().name} created IBKR connection with client_id {thread_config['ibkr']['client_id']}")
            else:
                raise Exception(f"Failed to connect to IBKR in thread {threading.current_thread().name}")

        return self._local.connection

    def get_historical_data(
        self,
        symbol: str,
        end_date: datetime,
        duration: str = "30 D",
        bar_size: str = "1 day"
    ) -> Optional[pd.DataFrame]:
        """
        Thread-safe historical data fetch

        Args:
            symbol: Stock ticker symbol
            end_date: End date for historical data
            duration: Time period
            bar_size: Bar size

        Returns:
            DataFrame with historical data or None
        """
        try:
            conn = self._get_connection()
            return conn.get_historical_data(symbol, end_date, duration, bar_size)
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None

    def get_intraday_bars(
        self,
        symbol: str,
        date: datetime,
        bar_size: str = "1 hour"
    ) -> Optional[pd.DataFrame]:
        """
        Thread-safe intraday bars fetch

        Args:
            symbol: Stock ticker symbol
            date: Date to fetch data for
            bar_size: Bar size

        Returns:
            DataFrame with intraday data or None
        """
        try:
            conn = self._get_connection()
            return conn.get_intraday_bars(symbol, date, bar_size)
        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return None

    def get_market_data(self, symbol: str, snapshot: bool = True) -> Optional[Dict[str, Any]]:
        """
        Thread-safe market data fetch

        Args:
            symbol: Stock ticker symbol
            snapshot: If True, get snapshot data

        Returns:
            Dictionary with market data or None
        """
        try:
            conn = self._get_connection()
            return conn.get_market_data(symbol, snapshot)
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    def cleanup(self):
        """Clean up all connections"""
        # Each thread will cleanup its own connection when done
        if hasattr(self._local, 'connection'):
            self._local.connection.disconnect()
            delattr(self._local, 'connection')


class MultithreadedIBKR:
    """Multithreaded IBKR data fetcher using thread-local connections"""

    def __init__(self, config: Dict[str, Any], max_workers: int = 5):
        """
        Initialize multithreaded IBKR interface

        Args:
            config: Configuration dictionary
            max_workers: Maximum number of worker threads
        """
        self.config = config
        self.max_workers = max_workers
        self.thread_local_mgr = ThreadLocalIBKR(config)

    def fetch_symbol_data(
        self,
        symbol: str,
        end_date: datetime,
        fetch_func: Callable
    ) -> tuple:
        """
        Fetch data for a single symbol

        Args:
            symbol: Stock ticker symbol
            end_date: End date for data
            fetch_func: Function to fetch data

        Returns:
            Tuple of (symbol, data)
        """
        try:
            data = fetch_func(symbol, end_date)
            return (symbol, data)
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            return (symbol, None)

    def fetch_all_historical(
        self,
        symbols: List[str],
        end_date: datetime,
        duration: str = "30 D",
        bar_size: str = "1 day"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical data for multiple symbols in parallel

        Args:
            symbols: List of ticker symbols
            end_date: End date for historical data
            duration: Time period
            bar_size: Bar size

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}

        def fetch_func(symbol, end_date):
            return self.thread_local_mgr.get_historical_data(
                symbol, end_date, duration, bar_size
            )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    self.fetch_symbol_data, symbol, end_date, fetch_func
                ): symbol
                for symbol in symbols
            }

            # Collect results as they complete
            for future in as_completed(futures):
                symbol, data = future.result()
                if data is not None:
                    results[symbol] = data
                else:
                    logger.warning(f"No data retrieved for {symbol}")

        return results

    def fetch_all_intraday(
        self,
        symbols: List[str],
        date: datetime,
        bar_size: str = "1 hour"
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch intraday data for multiple symbols in parallel

        Args:
            symbols: List of ticker symbols
            date: Date to fetch data for
            bar_size: Bar size

        Returns:
            Dictionary mapping symbols to DataFrames
        """
        results = {}

        def fetch_func(symbol, date):
            return self.thread_local_mgr.get_intraday_bars(
                symbol, date, bar_size
            )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    self.fetch_symbol_data, symbol, date, fetch_func
                ): symbol
                for symbol in symbols
            }

            # Collect results as they complete
            for future in as_completed(futures):
                symbol, data = future.result()
                if data is not None:
                    results[symbol] = data
                else:
                    logger.warning(f"No data retrieved for {symbol}")

        return results

    def fetch_all_market_data(
        self,
        symbols: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch market data for multiple symbols in parallel

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to market data
        """
        results = {}

        def fetch_func(symbol, _):
            return self.thread_local_mgr.get_market_data(symbol)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    self.fetch_symbol_data, symbol, None, fetch_func
                ): symbol
                for symbol in symbols
            }

            # Collect results as they complete
            for future in as_completed(futures):
                symbol, data = future.result()
                if data is not None:
                    results[symbol] = data
                else:
                    logger.warning(f"No market data retrieved for {symbol}")

        return results

    def cleanup(self):
        """Clean up all connections"""
        self.thread_local_mgr.cleanup()