#!/usr/bin/env python3
"""
Test script for retry mechanism
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timedelta
from src.modules.ibkr_sync_interface import IBKRSyncInterface
from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

def test_retry_mechanism():
    """Test the retry mechanism with a small set of symbols"""

    # Configuration
    config = {
        'ibkr': {
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 1,
            'market_data_type': 1,
            'timeout': 30,
            'max_concurrent_requests': 50,
            'request_delay': 0.1,
            'retry_count': 3,
            'retry_delay': 1.0,
            'max_requests_per_second': 10
        }
    }

    # Create interface
    ibkr = IBKRSyncInterface(config)

    logger.info("Testing retry mechanism...")
    logger.info(f"Retry count: {ibkr.retry_count}")
    logger.info(f"Retry delay: {ibkr.retry_delay}")

    # Connect
    if not ibkr.connect():
        logger.error("Failed to connect to IBKR")
        return False

    try:
        # Test with a few symbols
        test_symbols = ['AAPL', 'INVALID_SYMBOL', 'TSLA']
        end_date = datetime(2025, 9, 25) + timedelta(days=1)

        for symbol in test_symbols:
            logger.info(f"\nTesting {symbol}...")

            # Try to fetch historical data
            data = ibkr.get_historical_data(
                symbol=symbol,
                end_date=end_date,
                duration="5 D",
                bar_size="1 day"
            )

            if data is not None:
                logger.success(f"✓ Got data for {symbol}: {len(data)} bars")
                logger.info(f"  Adaptive delay: {ibkr.adaptive_delay:.2f}s")
                logger.info(f"  Connection health: {ibkr.connection_mgr.get_status()['health_score']:.1f}%")
            else:
                logger.warning(f"✗ No data for {symbol}")
                status = ibkr.connection_mgr.get_status()
                logger.info(f"  Errors: {status['error_count']}, Rate violations: {status['rate_violations']}")

        # Print final status
        final_status = ibkr.connection_mgr.get_status()
        logger.info("\n" + "="*50)
        logger.info("Final Connection Status:")
        logger.info(f"  Health Score: {final_status['health_score']:.1f}%")
        logger.info(f"  Success Count: {final_status['success_count']}")
        logger.info(f"  Error Count: {final_status['error_count']}")
        logger.info(f"  Avg Response Time: {final_status['avg_response_time']:.2f}s")
        logger.info(f"  Current Rate Limit: {final_status['current_rate_limit']:.1f} req/s")
        logger.info(f"  Rate Violations: {final_status['rate_violations']}")

        return True

    finally:
        ibkr.disconnect()
        logger.info("Disconnected from IBKR")


if __name__ == "__main__":
    success = test_retry_mechanism()
    sys.exit(0 if success else 1)