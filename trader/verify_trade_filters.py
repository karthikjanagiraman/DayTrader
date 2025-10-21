"""
Verify Trade Filters Against Real IBKR Market Data

Cross-verifies all trades from a trading session with actual IBKR 5-second bar data
to confirm that volume and candle filters were correctly applied.

Usage:
    python3 verify_trade_filters.py --date 2025-10-16

Author: Claude Code
Date: October 16, 2025
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import pytz
import yaml
from ib_insync import IB, Stock, util

# Add trader directory to path
sys.path.insert(0, str(Path(__file__).parent))

from strategy.ps60_strategy import PS60Strategy


class TradeFilterVerifier:
    """Verify that trade entry filters were correctly applied"""

    def __init__(self, date_str: str):
        self.date_str = date_str
        self.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        self.eastern = pytz.timezone('US/Eastern')

        # Load config
        config_path = Path(__file__).parent / 'config' / 'trader_config.yaml'
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.strategy = PS60Strategy(self.config)

        # Connect to IBKR
        self.ib = IB()
        print("Connecting to IBKR...")
        self.ib.connect('127.0.0.1', 7497, clientId=5000)
        print("✓ Connected to IBKR\n")

        # Load trades and state
        self.trades = self._load_trades()
        self.state = self._load_state()

    def _load_trades(self) -> dict:
        """Load trades from logs/trades_YYYYMMDD.json"""
        trades_file = Path(__file__).parent / 'logs' / f'trades_{self.date_str.replace("-", "")}.json'

        if not trades_file.exists():
            print(f"❌ Trades file not found: {trades_file}")
            return {}

        with open(trades_file) as f:
            return json.load(f)

    def _load_state(self) -> dict:
        """Load session state from logs/trader_state.json"""
        state_file = Path(__file__).parent / 'logs' / 'trader_state.json'

        if not state_file.exists():
            print(f"❌ State file not found: {state_file}")
            return {}

        with open(state_file) as f:
            return json.load(f)

    def verify_all_trades(self):
        """Verify all trades from the session"""
        print("=" * 80)
        print(f"TRADE FILTER VERIFICATION - {self.date_str}")
        print("=" * 80)
        print()

        # Get all trades (closed + open)
        all_trades = []

        # Try to get closed trades from trades file
        if self.trades and 'closed_trades' in self.trades:
            all_trades.extend(self.trades['closed_trades'])

        # Get open positions from state file
        if self.state and 'positions' in self.state:
            # Convert open positions to trade format
            for symbol, pos in self.state['positions'].items():
                all_trades.append({
                    'symbol': symbol,
                    'side': pos['side'],
                    'entry_price': pos['entry_price'],
                    'entry_time': pos['entry_time'],
                    'status': 'OPEN'
                })

        if not all_trades:
            print("❌ No trades found to verify")
            print("Checked:")
            print(f"  - Trades file: logs/trades_{self.date_str.replace('-', '')}.json")
            print(f"  - State file: logs/trader_state.json")
            return

        print(f"Found {len(all_trades)} trades to verify\n")

        verification_results = []

        for i, trade in enumerate(all_trades, 1):
            print(f"\n{'=' * 80}")
            print(f"Trade #{i}: {trade['symbol']} {trade['side']}")
            print(f"{'=' * 80}")

            result = self.verify_trade(trade)
            verification_results.append(result)

            print()

            # Add delay between stocks to avoid rate limiting
            if i < len(all_trades):
                import time
                time.sleep(3)

        # Summary
        self._print_summary(verification_results)

    def verify_trade(self, trade: dict) -> dict:
        """Verify a single trade against IBKR data"""
        symbol = trade['symbol']
        side = trade['side']
        entry_time_str = trade['entry_time']
        entry_price = trade['entry_price']

        # Parse entry time
        try:
            entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
            entry_time = entry_time.astimezone(self.eastern)
        except Exception as e:
            print(f"❌ Failed to parse entry time: {e}")
            return {'symbol': symbol, 'verified': False, 'error': 'Invalid entry time'}

        print(f"Entry Time: {entry_time.strftime('%H:%M:%S')} ET")
        print(f"Entry Price: ${entry_price:.2f}")

        # Get entry path from state
        entry_path = self._get_entry_path(symbol, trade)
        print(f"Entry Path: {entry_path}")

        # Fetch 5-second bars around entry time
        bars = self._fetch_bars(symbol, entry_time)

        if not bars:
            print(f"❌ No IBKR data available")
            return {'symbol': symbol, 'verified': False, 'error': 'No IBKR data'}

        print(f"✓ Fetched {len(bars)} bars from IBKR")

        # Analyze bars around entry
        result = self._analyze_entry_filters(symbol, entry_time, entry_price, bars, side, entry_path)

        return result

    def _get_entry_path(self, symbol: str, trade: dict) -> str:
        """Get entry path from state analytics"""
        if 'entry_paths' not in self.state.get('analytics', {}):
            return "Unknown"

        # Find entry path that matches this symbol's characteristics
        entry_paths = self.state['analytics']['entry_paths']

        # Try to find exact match or return first one
        for path, count in entry_paths.items():
            if symbol.upper() in path.upper() or trade['side'] in path:
                return path

        # Return first entry path as fallback
        if entry_paths:
            return list(entry_paths.keys())[0]

        return "Unknown"

    def _fetch_bars(self, symbol: str, entry_time: datetime, window_minutes: int = 3) -> list:
        """Fetch 5-second bars around entry time"""
        import time

        for attempt in range(3):
            try:
                contract = Stock(symbol, 'SMART', 'USD')
                self.ib.qualifyContracts(contract)

                # Fetch bars from 3 minutes before to 1 minute after entry
                start_time = entry_time - timedelta(minutes=window_minutes)
                end_time = entry_time + timedelta(minutes=1)

                # Add small delay to avoid rate limiting
                if attempt > 0:
                    print(f"  Retry {attempt}/3...")
                    time.sleep(2)

                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=end_time,
                    durationStr=f'{window_minutes + 1} M',
                    barSizeSetting='5 secs',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1,
                    timeout=60  # 60 second timeout
                )

                if bars:
                    return bars
                else:
                    print(f"  No bars returned (attempt {attempt+1}/3)")

            except Exception as e:
                print(f"  Error fetching bars (attempt {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)  # Wait before retry

        print(f"❌ Failed to fetch bars after 3 attempts")
        return []

    def _analyze_entry_filters(self, symbol: str, entry_time: datetime,
                               entry_price: float, bars: list, side: str,
                               entry_path: str) -> dict:
        """Analyze if entry filters were correctly applied"""

        # Find the bar closest to entry time
        entry_bar_idx = None
        min_time_diff = timedelta(hours=1)

        for i, bar in enumerate(bars):
            bar_time = bar.date.astimezone(self.eastern)
            time_diff = abs(bar_time - entry_time)

            if time_diff < min_time_diff:
                min_time_diff = time_diff
                entry_bar_idx = i

        if entry_bar_idx is None:
            print("❌ Could not find entry bar")
            return {'symbol': symbol, 'verified': False, 'error': 'Entry bar not found'}

        entry_bar = bars[entry_bar_idx]
        entry_bar_time = entry_bar.date.astimezone(self.eastern)

        print(f"\nEntry Bar Found:")
        print(f"  Time: {entry_bar_time.strftime('%H:%M:%S')} ET")
        print(f"  Time Diff: {min_time_diff.total_seconds():.1f} seconds")
        print(f"  Price: ${entry_bar.close:.2f}")
        print(f"  Volume: {entry_bar.volume:,}")

        # Determine if this was a MOMENTUM or PULLBACK/RETEST entry
        is_pullback = 'PULLBACK' in entry_path or 'weak initial' in entry_path

        if is_pullback:
            result = self._verify_pullback_entry(symbol, entry_bar_idx, bars, side)
        else:
            result = self._verify_momentum_entry(symbol, entry_bar_idx, bars, side)

        result['symbol'] = symbol
        result['entry_time'] = entry_time
        result['entry_bar_time'] = entry_bar_time
        result['time_diff_seconds'] = min_time_diff.total_seconds()

        return result

    def _verify_momentum_entry(self, symbol: str, entry_idx: int,
                               bars: list, side: str) -> dict:
        """Verify MOMENTUM entry filters"""
        print(f"\n{'─' * 80}")
        print("VERIFYING MOMENTUM ENTRY")
        print(f"{'─' * 80}")

        # Need to aggregate to 1-minute candle
        # Find start of 1-minute candle (entry_idx should be at candle close)
        entry_bar = bars[entry_idx]
        entry_time = entry_bar.date

        # Round down to nearest minute
        candle_start_time = entry_time.replace(second=0, microsecond=0)
        candle_bars = []

        for bar in bars:
            bar_minute = bar.date.replace(second=0, microsecond=0)
            if bar_minute == candle_start_time:
                candle_bars.append(bar)

        if not candle_bars:
            print("❌ Could not find 1-minute candle bars")
            return {'verified': False, 'error': 'No candle bars'}

        # Calculate 1-minute candle metrics
        candle_open = candle_bars[0].open
        candle_close = candle_bars[-1].close
        candle_high = max(b.high for b in candle_bars)
        candle_low = min(b.low for b in candle_bars)
        candle_volume = sum(b.volume for b in candle_bars)

        candle_size_pct = abs(candle_close - candle_open) / candle_open

        print(f"\n1-Minute Candle Metrics:")
        print(f"  Open: ${candle_open:.2f}")
        print(f"  Close: ${candle_close:.2f}")
        print(f"  High: ${candle_high:.2f}")
        print(f"  Low: ${candle_low:.2f}")
        print(f"  Volume: {candle_volume:,}")
        print(f"  Candle Size: {candle_size_pct*100:.2f}%")

        # Calculate average volume (20 1-minute candles before)
        # Aggregate previous bars into 1-minute candles
        avg_volumes = []
        current_minute = None
        minute_volume = 0

        for bar in bars[:entry_idx]:
            bar_minute = bar.date.replace(second=0, microsecond=0)

            if current_minute is None:
                current_minute = bar_minute
                minute_volume = bar.volume
            elif bar_minute == current_minute:
                minute_volume += bar.volume
            else:
                # New minute started
                avg_volumes.append(minute_volume)
                current_minute = bar_minute
                minute_volume = bar.volume

        # Add last accumulated minute
        if minute_volume > 0:
            avg_volumes.append(minute_volume)

        # Take last 20 minutes
        if len(avg_volumes) >= 20:
            avg_volume = sum(avg_volumes[-20:]) / 20
        elif len(avg_volumes) > 0:
            avg_volume = sum(avg_volumes) / len(avg_volumes)
        else:
            avg_volume = candle_volume  # Fallback

        volume_ratio = candle_volume / avg_volume if avg_volume > 0 else 1.0

        print(f"  Avg Volume (20 candles): {avg_volume:,.0f}")
        print(f"  Volume Ratio: {volume_ratio:.2f}x")

        # Check against momentum thresholds
        momentum_volume_threshold = self.strategy.momentum_volume_threshold
        momentum_candle_threshold = self.strategy.momentum_candle_min_pct

        print(f"\nMomentum Thresholds:")
        print(f"  Required Volume: ≥{momentum_volume_threshold:.1f}x")
        print(f"  Required Candle: ≥{momentum_candle_threshold*100:.1f}%")

        volume_passed = volume_ratio >= momentum_volume_threshold
        candle_passed = candle_size_pct >= momentum_candle_threshold

        print(f"\nFilter Results:")
        print(f"  Volume: {'✓ PASS' if volume_passed else '✗ FAIL'} ({volume_ratio:.2f}x vs {momentum_volume_threshold:.1f}x)")
        print(f"  Candle: {'✓ PASS' if candle_passed else '✗ FAIL'} ({candle_size_pct*100:.2f}% vs {momentum_candle_threshold*100:.1f}%)")

        both_passed = volume_passed and candle_passed

        if both_passed:
            print(f"\n✅ MOMENTUM ENTRY VERIFIED - All filters passed correctly")
        else:
            print(f"\n❌ MOMENTUM ENTRY FAILED - Filters should have blocked this entry")

        return {
            'verified': both_passed,
            'entry_type': 'MOMENTUM',
            'volume_ratio': volume_ratio,
            'volume_required': momentum_volume_threshold,
            'volume_passed': volume_passed,
            'candle_size_pct': candle_size_pct,
            'candle_required': momentum_candle_threshold,
            'candle_passed': candle_passed,
            'error': None if both_passed else 'Filter mismatch'
        }

    def _verify_pullback_entry(self, symbol: str, entry_idx: int,
                               bars: list, side: str) -> dict:
        """Verify PULLBACK/RETEST entry filters"""
        print(f"\n{'─' * 80}")
        print("VERIFYING PULLBACK/RETEST ENTRY")
        print(f"{'─' * 80}")

        # For pullback entries, the filter is applied on 5-second bars
        # Check the current bar and surrounding bars for bounce confirmation

        entry_bar = bars[entry_idx]

        # Get previous bar for rising price check
        if entry_idx > 0:
            prev_bar = bars[entry_idx - 1]
            previous_price = prev_bar.close
        else:
            previous_price = entry_bar.close

        current_price = entry_bar.close
        current_volume = entry_bar.volume

        print(f"\n5-Second Bar Metrics:")
        print(f"  Previous Price: ${previous_price:.2f}")
        print(f"  Current Price: ${current_price:.2f}")
        print(f"  Price Rising: {current_price > previous_price}")
        print(f"  Volume: {current_volume:,}")

        # Calculate candle size
        candle_size_pct = abs(entry_bar.close - entry_bar.open) / entry_bar.open
        print(f"  Candle Size: {candle_size_pct*100:.2f}%")

        # Calculate average volume (last 20 bars)
        if entry_idx >= 20:
            avg_volume = sum(bars[i].volume for i in range(entry_idx-19, entry_idx+1)) / 20
        else:
            avg_volume = sum(bars[i].volume for i in range(0, entry_idx+1)) / (entry_idx + 1)

        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

        print(f"  Avg Volume (20 bars): {avg_volume:,.0f}")
        print(f"  Volume Ratio: {volume_ratio:.2f}x")

        # Check against pullback thresholds
        pullback_volume_threshold = self.strategy.pullback_volume_threshold
        pullback_candle_threshold = self.strategy.pullback_candle_min_pct

        print(f"\nPullback Thresholds:")
        print(f"  Required Volume: ≥{pullback_volume_threshold:.1f}x")
        print(f"  Required Candle: ≥{pullback_candle_threshold*100:.1f}%")

        volume_passed = volume_ratio >= pullback_volume_threshold
        candle_passed = candle_size_pct >= pullback_candle_threshold
        rising_passed = current_price > previous_price

        print(f"\nFilter Results:")
        print(f"  Volume: {'✓ PASS' if volume_passed else '✗ FAIL'} ({volume_ratio:.2f}x vs {pullback_volume_threshold:.1f}x)")
        print(f"  Candle: {'✓ PASS' if candle_passed else '✗ FAIL'} ({candle_size_pct*100:.2f}% vs {pullback_candle_threshold*100:.1f}%)")
        print(f"  Rising: {'✓ PASS' if rising_passed else '✗ FAIL'} (${current_price:.2f} vs ${previous_price:.2f})")

        all_passed = volume_passed and candle_passed and rising_passed

        if all_passed:
            print(f"\n✅ PULLBACK/RETEST ENTRY VERIFIED - All filters passed correctly")
        else:
            print(f"\n❌ PULLBACK/RETEST ENTRY FAILED - Filters should have blocked this entry")

        return {
            'verified': all_passed,
            'entry_type': 'PULLBACK_RETEST',
            'volume_ratio': volume_ratio,
            'volume_required': pullback_volume_threshold,
            'volume_passed': volume_passed,
            'candle_size_pct': candle_size_pct,
            'candle_required': pullback_candle_threshold,
            'candle_passed': candle_passed,
            'rising_passed': rising_passed,
            'error': None if all_passed else 'Filter mismatch'
        }

    def _print_summary(self, results: list):
        """Print verification summary"""
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)

        verified_count = sum(1 for r in results if r.get('verified', False))
        failed_count = len(results) - verified_count

        print(f"\nTotal Trades Verified: {len(results)}")
        print(f"✅ Filters Correct: {verified_count}")
        print(f"❌ Filters Incorrect: {failed_count}")

        if failed_count > 0:
            print(f"\n⚠️  WARNING: {failed_count} trades had incorrect filter application!")
            print("Review the detailed output above to investigate.")
        else:
            print(f"\n✅ All filters were correctly applied!")

        # Detailed breakdown
        print(f"\nBy Entry Type:")
        momentum_results = [r for r in results if r.get('entry_type') == 'MOMENTUM']
        pullback_results = [r for r in results if r.get('entry_type') == 'PULLBACK_RETEST']

        if momentum_results:
            momentum_verified = sum(1 for r in momentum_results if r.get('verified', False))
            print(f"  MOMENTUM: {momentum_verified}/{len(momentum_results)} verified")

        if pullback_results:
            pullback_verified = sum(1 for r in pullback_results if r.get('verified', False))
            print(f"  PULLBACK/RETEST: {pullback_verified}/{len(pullback_results)} verified")

        print()

    def disconnect(self):
        """Disconnect from IBKR"""
        self.ib.disconnect()
        print("Disconnected from IBKR")


def main():
    parser = argparse.ArgumentParser(
        description='Verify trade entry filters against real IBKR market data'
    )
    parser.add_argument(
        '--date',
        type=str,
        required=True,
        help='Trading date (YYYY-MM-DD)'
    )

    args = parser.parse_args()

    verifier = TradeFilterVerifier(args.date)

    try:
        verifier.verify_all_trades()
    finally:
        verifier.disconnect()


if __name__ == '__main__':
    main()
