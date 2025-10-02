"""
IBKR Connection Pool for Multithreaded Access
Manages multiple IBKR connections for concurrent data fetching
"""

import threading
from queue import Queue
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime
from loguru import logger
import time

from src.modules.ibkr_sync_interface import IBKRSyncInterface


class IBKRConnectionPool:
    """Thread-safe connection pool for IBKR"""

    def __init__(self, config: Dict[str, Any], pool_size: int = 5):
        """
        Initialize connection pool

        Args:
            config: Configuration dictionary
            pool_size: Number of connections to maintain
        """
        self.config = config
        self.pool_size = pool_size
        self.connections = Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        self.initialized = False

    def initialize(self) -> bool:
        """
        Initialize all connections in the pool

        Returns:
            True if all connections initialized successfully
        """
        with self.lock:
            if self.initialized:
                return True

            logger.info(f"Initializing IBKR connection pool with {self.pool_size} connections")

            for i in range(self.pool_size):
                # Create a new config with unique client_id
                conn_config = self.config.copy()
                conn_config['ibkr'] = self.config['ibkr'].copy()
                conn_config['ibkr']['client_id'] = self.config['ibkr']['client_id'] + i

                conn = IBKRSyncInterface(conn_config)

                if conn.connect():
                    self.connections.put(conn)
                    logger.info(f"Connection {i+1}/{self.pool_size} established with client_id {conn_config['ibkr']['client_id']}")
                else:
                    logger.error(f"Failed to establish connection {i+1}")
                    # Clean up any established connections
                    while not self.connections.empty():
                        c = self.connections.get()
                        c.disconnect()
                    return False

                # Small delay between connections
                if i < self.pool_size - 1:
                    time.sleep(0.5)

            self.initialized = True
            logger.info("Connection pool initialized successfully")
            return True

    def get_connection(self, timeout: float = 10) -> Optional[IBKRSyncInterface]:
        """
        Get a connection from the pool

        Args:
            timeout: Maximum time to wait for a connection

        Returns:
            IBKR connection or None if timeout
        """
        try:
            return self.connections.get(timeout=timeout)
        except:
            logger.warning("Timeout waiting for available connection")
            return None

    def return_connection(self, conn: IBKRSyncInterface):
        """
        Return a connection to the pool

        Args:
            conn: Connection to return
        """
        if conn:
            self.connections.put(conn)

    def execute_with_connection(self, func, *args, **kwargs):
        """
        Execute a function with a connection from the pool

        Args:
            func: Function to execute
            *args, **kwargs: Arguments for the function

        Returns:
            Result of the function
        """
        conn = self.get_connection()
        if not conn:
            raise Exception("No available connections")

        try:
            return func(conn, *args, **kwargs)
        finally:
            self.return_connection(conn)

    def shutdown(self):
        """Shutdown all connections in the pool"""
        with self.lock:
            if not self.initialized:
                return

            logger.info("Shutting down connection pool")

            while not self.connections.empty():
                conn = self.connections.get()
                conn.disconnect()

            self.initialized = False
            logger.info("Connection pool shutdown complete")


class ThreadSafeIBKR:
    """Thread-safe wrapper for IBKR operations using connection pool"""

    def __init__(self, config: Dict[str, Any], pool_size: int = 5):
        """
        Initialize thread-safe IBKR interface

        Args:
            config: Configuration dictionary
            pool_size: Size of connection pool
        """
        self.pool = IBKRConnectionPool(config, pool_size)
        self.config = config

    def connect(self) -> bool:
        """Initialize connection pool"""
        return self.pool.initialize()

    def disconnect(self):
        """Shutdown connection pool"""
        self.pool.shutdown()

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
        def fetch_data(conn, symbol, end_date, duration, bar_size):
            return conn.get_historical_data(symbol, end_date, duration, bar_size)

        try:
            return self.pool.execute_with_connection(
                fetch_data, symbol, end_date, duration, bar_size
            )
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
        def fetch_intraday(conn, symbol, date, bar_size):
            return conn.get_intraday_bars(symbol, date, bar_size)

        try:
            return self.pool.execute_with_connection(
                fetch_intraday, symbol, date, bar_size
            )
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
        def fetch_market_data(conn, symbol, snapshot):
            return conn.get_market_data(symbol, snapshot)

        try:
            return self.pool.execute_with_connection(
                fetch_market_data, symbol, snapshot
            )
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if pool is initialized"""
        return self.pool.initialized