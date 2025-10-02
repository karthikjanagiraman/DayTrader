"""
IBKR Web API Interface Module
Uses Interactive Brokers Client Portal Web API
REST API with WebSocket support for real-time data
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from loguru import logger
import ssl
import certifi


class IBKRWebInterface:
    """Interface for Interactive Brokers Web API (Client Portal API)"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize IBKR Web API connection

        Args:
            config: Configuration dictionary with Web API settings
        """
        self.config = config['ibkr']
        self.base_url = self.config.get('web_api_url', 'https://localhost:5000/v1/api')
        self.session = None
        self.authenticated = False
        self.account_id = None

        # SSL context for self-signed certificates
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    async def connect(self) -> bool:
        """
        Connect and authenticate with IBKR Web API

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Create aiohttp session
            connector = aiohttp.TCPConnector(ssl=self.ssl_context)
            self.session = aiohttp.ClientSession(connector=connector)

            # Check if gateway is running
            async with self.session.get(f"{self.base_url}/portal/iserver/auth/status") as resp:
                if resp.status != 200:
                    logger.error(f"IBKR Client Portal not accessible at {self.base_url}")
                    return False

                status = await resp.json()
                self.authenticated = status.get('authenticated', False)

                if not self.authenticated:
                    # Attempt reauthentication
                    await self._reauthenticate()

                if self.authenticated:
                    # Get account info
                    await self._get_account_info()
                    logger.info(f"Connected to IBKR Web API. Account: {self.account_id}")
                    return True
                else:
                    logger.error("Failed to authenticate with IBKR Web API")
                    return False

        except Exception as e:
            logger.error(f"Failed to connect to IBKR Web API: {e}")
            logger.error("Make sure IBKR Client Portal Gateway is running on localhost:5000")
            return False

    async def _reauthenticate(self):
        """Reauthenticate with the API"""
        try:
            async with self.session.post(f"{self.base_url}/portal/iserver/reauthenticate") as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.authenticated = result.get('message') == 'ok'
        except Exception as e:
            logger.error(f"Reauthentication failed: {e}")

    async def _get_account_info(self):
        """Get account information"""
        try:
            async with self.session.get(f"{self.base_url}/portal/iserver/accounts") as resp:
                if resp.status == 200:
                    accounts = await resp.json()
                    if accounts and 'accounts' in accounts:
                        self.account_id = accounts['accounts'][0]
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")

    async def disconnect(self):
        """Disconnect from IBKR Web API"""
        if self.session:
            await self.session.close()
            self.authenticated = False
            logger.info("Disconnected from IBKR Web API")

    async def search_contract(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Search for a stock contract

        Args:
            symbol: Stock ticker symbol

        Returns:
            Contract details or None
        """
        try:
            params = {
                'symbol': symbol,
                'name': False,
                'secType': 'STK'
            }

            async with self.session.get(
                f"{self.base_url}/portal/iserver/secdef/search",
                params=params
            ) as resp:
                if resp.status == 200:
                    results = await resp.json()
                    if results and len(results) > 0:
                        # Return first US stock match
                        for contract in results:
                            if contract.get('description', '').endswith('NASDAQ') or \
                               contract.get('description', '').endswith('NYSE'):
                                return contract
                        return results[0]

            return None

        except Exception as e:
            logger.error(f"Error searching contract for {symbol}: {e}")
            return None

    async def get_historical_data(
        self,
        symbol: str,
        end_date: datetime,
        duration: str = "30d",
        bar_size: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        Fetch historical data for a symbol

        Args:
            symbol: Stock ticker symbol
            end_date: End date for historical data
            duration: Time period (e.g., "30d", "1m", "1y")
            bar_size: Bar size (e.g., "1d", "1h", "5min")

        Returns:
            DataFrame with historical data or None if error
        """
        try:
            # Search for contract
            contract = await self.search_contract(symbol)
            if not contract:
                logger.warning(f"Contract not found for {symbol}")
                return None

            conid = contract['conid']

            # Convert bar size to API format
            bar_size_map = {
                "1 day": "1d",
                "1 hour": "1h",
                "30 min": "30min",
                "15 min": "15min",
                "5 min": "5min",
                "1 min": "1min"
            }

            api_bar_size = bar_size_map.get(bar_size, bar_size)

            # Make historical data request
            params = {
                'conid': conid,
                'exchange': contract.get('exchange', ''),
                'period': duration,
                'bar': api_bar_size,
                'outsideRth': True  # Include pre/post market
            }

            async with self.session.get(
                f"{self.base_url}/portal/iserver/marketdata/history",
                params=params
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if 'data' in data:
                        # Convert to DataFrame
                        df_data = []
                        for point in data['data']:
                            df_data.append({
                                'date': datetime.fromtimestamp(point['t'] / 1000),
                                'open': point.get('o', 0),
                                'high': point.get('h', 0),
                                'low': point.get('l', 0),
                                'close': point.get('c', 0),
                                'volume': point.get('v', 0)
                            })

                        df = pd.DataFrame(df_data)
                        df.set_index('date', inplace=True)
                        return df

            logger.warning(f"No historical data received for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None

    async def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current market data for a symbol

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with market data or None
        """
        try:
            # Search for contract
            contract = await self.search_contract(symbol)
            if not contract:
                return None

            conid = contract['conid']

            # Subscribe to market data
            fields = "31,84,85,86,87,88,7295,7296"  # Last, bid, ask, high, low, volume, etc.

            async with self.session.get(
                f"{self.base_url}/portal/iserver/marketdata/snapshot",
                params={'conids': conid, 'fields': fields}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if data and len(data) > 0:
                        snapshot = data[0]

                        # Parse the snapshot data
                        market_data = {
                            'symbol': symbol,
                            'last': snapshot.get('31', 0),
                            'bid': snapshot.get('84', 0),
                            'ask': snapshot.get('85', 0),
                            'high': snapshot.get('87', 0),
                            'low': snapshot.get('88', 0),
                            'volume': snapshot.get('7762', 0),
                            'close': snapshot.get('31', 0),  # Previous close
                            'timestamp': datetime.now()
                        }

                        return market_data

            return None

        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None

    async def get_pre_market_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get pre-market quote for a symbol

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with pre-market quote data or None
        """
        # Use market data snapshot which includes pre-market
        return await self.get_market_data(symbol)

    async def batch_get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get quotes for multiple symbols

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to quote data
        """
        quotes = {}

        # Process in batches to avoid overwhelming the API
        batch_size = 10
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i + batch_size]

            # Get contracts for batch
            conids = []
            symbol_to_conid = {}

            for symbol in batch:
                contract = await self.search_contract(symbol)
                if contract:
                    conids.append(str(contract['conid']))
                    symbol_to_conid[contract['conid']] = symbol

            if conids:
                # Get market data for batch
                fields = "31,84,85,86,87,88,7762"
                conids_str = ','.join(conids)

                try:
                    async with self.session.get(
                        f"{self.base_url}/portal/iserver/marketdata/snapshot",
                        params={'conids': conids_str, 'fields': fields}
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            for snapshot in data:
                                conid = snapshot.get('conid')
                                if conid in symbol_to_conid:
                                    symbol = symbol_to_conid[conid]
                                    quotes[symbol] = {
                                        'last': snapshot.get('31', 0),
                                        'bid': snapshot.get('84', 0),
                                        'ask': snapshot.get('85', 0),
                                        'high': snapshot.get('87', 0),
                                        'low': snapshot.get('88', 0),
                                        'volume': snapshot.get('7762', 0)
                                    }

                except Exception as e:
                    logger.error(f"Error in batch quote request: {e}")

            # Rate limiting
            await asyncio.sleep(0.5)

        return quotes

    async def get_news(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get news for a symbol

        Args:
            symbol: Stock ticker symbol

        Returns:
            List of news items or None
        """
        try:
            # Search for contract
            contract = await self.search_contract(symbol)
            if not contract:
                return None

            conid = contract['conid']

            # Get news
            params = {
                'conid': conid,
                'limit': 10
            }

            async with self.session.get(
                f"{self.base_url}/portal/iserver/marketdata/news",
                params=params
            ) as resp:
                if resp.status == 200:
                    news_data = await resp.json()

                    news_items = []
                    for item in news_data:
                        news_items.append({
                            'headline': item.get('headline', ''),
                            'summary': item.get('summary', ''),
                            'source': item.get('source', ''),
                            'timestamp': item.get('datetime', '')
                        })

                    return news_items

            return []

        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return None

    def is_connected(self) -> bool:
        """Check if connected and authenticated"""
        return self.authenticated and self.session is not None