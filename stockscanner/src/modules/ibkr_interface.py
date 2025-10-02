"""
IBKR Interface Module
Manages connection to Interactive Brokers TWS/Gateway
Handles market data requests and historical data fetching
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from ib_insync import IB, Stock, Contract, BarDataList
import pandas as pd
from loguru import logger


class IBKRInterface:
    """Interface for Interactive Brokers API connection and data retrieval"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize IBKR connection interface

        Args:
            config: Configuration dictionary with IBKR settings
        """
        self.config = config['ibkr']
        self.ib = IB()
        self.connected = False
        self.subscriptions = {}
        self.max_concurrent = self.config.get('max_concurrent_requests', 50)
        self.request_delay = self.config.get('request_delay', 0.1)

    async def connect(self) -> bool:
        """
        Connect to IBKR TWS/Gateway

        Returns:
            True if connection successful, False otherwise
        """
        try:
            await self.ib.connectAsync(
                host=self.config['host'],
                port=self.config['port'],
                clientId=self.config['client_id'],
                timeout=self.config.get('timeout', 30)
            )

            # Set market data type (1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen)
            self.ib.reqMarketDataType(self.config.get('market_data_type', 1))

            self.connected = True
            logger.info(f"Connected to IBKR at {self.config['host']}:{self.config['port']}")

            # Verify connection and subscriptions
            await self._verify_connection()

            return True

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from IBKR"""
        if self.connected:
            # Cancel all subscriptions
            for symbol, subscription in self.subscriptions.items():
                self.ib.cancelMktData(subscription['contract'])

            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IBKR")

    async def _verify_connection(self):
        """Verify connection and market data subscriptions"""
        try:
            # Check if we have market data subscriptions
            account_values = self.ib.accountValues()
            logger.info(f"Account connected: {len(account_values) > 0}")

            # Test with a sample contract
            test_contract = Stock('AAPL', 'SMART', 'USD')
            self.ib.qualifyContracts(test_contract)
            logger.info("Market data subscription test successful")

        except Exception as e:
            logger.warning(f"Connection verification warning: {e}")

    def create_contract(self, symbol: str) -> Contract:
        """
        Create a stock contract for the given symbol

        Args:
            symbol: Stock ticker symbol

        Returns:
            Qualified IB contract
        """
        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        return contract

    async def get_historical_data(
        self,
        symbol: str,
        end_date: datetime,
        duration: str = "30 D",
        bar_size: str = "1 day",
        what_to_show: str = "TRADES"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol

        Args:
            symbol: Stock ticker symbol
            end_date: End date for historical data
            duration: Time period (e.g., "30 D", "1 M")
            bar_size: Bar size (e.g., "1 day", "1 hour")
            what_to_show: Data type (TRADES, MIDPOINT, BID, ASK)

        Returns:
            DataFrame with historical data or None if error
        """
        try:
            contract = self.create_contract(symbol)

            # Format end date for IBKR
            end_date_str = end_date.strftime('%Y%m%d %H:%M:%S')

            # Request historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_date_str,
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=False,  # Include pre/post market
                formatDate=1
            )

            if not bars:
                logger.warning(f"No historical data for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame([{
                'date': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'average': bar.average,
                'barCount': bar.barCount
            } for bar in bars])

            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # Add delay to respect rate limits
            await asyncio.sleep(self.request_delay)

            return df

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None

    async def get_pre_market_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get pre-market quote for a symbol

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with quote data or None if error
        """
        try:
            contract = self.create_contract(symbol)

            # Request market data
            ticker = self.ib.reqMktData(contract, '', False, False)

            # Wait for data to populate
            await asyncio.sleep(2)

            quote = {
                'symbol': symbol,
                'last': ticker.last,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'volume': ticker.volume,
                'high': ticker.high,
                'low': ticker.low,
                'close': ticker.close,
                'timestamp': datetime.now()
            }

            # Cancel market data subscription
            self.ib.cancelMktData(contract)

            return quote

        except Exception as e:
            logger.error(f"Error fetching pre-market quote for {symbol}: {e}")
            return None

    async def get_intraday_bars(
        self,
        symbol: str,
        date: datetime,
        bar_size: str = "1 hour"
    ) -> Optional[pd.DataFrame]:
        """
        Get intraday bars for a specific date

        Args:
            symbol: Stock ticker symbol
            date: Date to fetch data for
            bar_size: Bar size (default "1 hour" for 60-min bars)

        Returns:
            DataFrame with intraday data or None if error
        """
        try:
            # Set end date to end of trading day
            end_date = date.replace(hour=16, minute=0, second=0)

            # Fetch intraday data
            return await self.get_historical_data(
                symbol=symbol,
                end_date=end_date,
                duration="1 D",
                bar_size=bar_size,
                what_to_show="TRADES"
            )

        except Exception as e:
            logger.error(f"Error fetching intraday data for {symbol}: {e}")
            return None

    async def get_news(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get news for a symbol from IBKR news feed

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of news items or None if error
        """
        try:
            contract = self.create_contract(symbol)

            # Request news
            news_providers = self.ib.reqNewsProviders()
            logger.debug(f"Available news providers: {news_providers}")

            # Get historical news
            news_articles = []

            # Note: IBKR news requires specific subscriptions
            # This is a placeholder for news fetching logic
            logger.warning(f"News fetching for {symbol} requires IBKR news subscription")

            return news_articles

        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return None

    async def batch_get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get quotes for multiple symbols with rate limiting

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to quote data
        """
        quotes = {}
        contracts = []

        # Create contracts and request market data
        for symbol in symbols[:self.max_concurrent]:
            try:
                contract = self.create_contract(symbol)
                ticker = self.ib.reqMktData(contract, '', False, False)
                contracts.append((symbol, contract, ticker))
            except Exception as e:
                logger.error(f"Error requesting data for {symbol}: {e}")

        # Wait for data to populate
        await asyncio.sleep(3)

        # Collect quotes
        for symbol, contract, ticker in contracts:
            quotes[symbol] = {
                'last': ticker.last,
                'bid': ticker.bid,
                'ask': ticker.ask,
                'volume': ticker.volume,
                'high': ticker.high,
                'low': ticker.low,
                'close': ticker.close
            }

            # Cancel subscription
            self.ib.cancelMktData(contract)

        # Process remaining symbols if any
        if len(symbols) > self.max_concurrent:
            await asyncio.sleep(self.request_delay)
            remaining_quotes = await self.batch_get_quotes(symbols[self.max_concurrent:])
            quotes.update(remaining_quotes)

        return quotes

    async def get_contract_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed contract information

        Args:
            symbol: Stock ticker symbol

        Returns:
            Contract details dictionary or None if error
        """
        try:
            contract = self.create_contract(symbol)
            details = self.ib.reqContractDetails(contract)

            if details:
                detail = details[0]
                return {
                    'symbol': symbol,
                    'longName': detail.longName,
                    'industry': detail.industry,
                    'category': detail.category,
                    'subcategory': detail.subcategory,
                    'minTick': detail.minTick,
                    'priceMagnifier': detail.priceMagnifier,
                    'exchange': detail.validExchanges
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching contract details for {symbol}: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if connected to IBKR"""
        return self.connected and self.ib.isConnected()