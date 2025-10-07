#!/usr/bin/env python3
"""
State Manager - Persistent State for Crash Recovery

CRITICAL: Ensures live trader can recover from crashes/restarts

Features:
- Save trading state every 10 seconds
- Load state on startup
- Query IBKR portfolio for validation
- Reconcile state file with broker reality
- Atomic file writes (no corruption)

Usage:
    sm = StateManager(trader)
    sm.recover_full_state()  # On startup
    sm.save_state()          # Every 10 seconds in main loop
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import pytz


class StateManager:
    """
    Manage persistent state for crash recovery

    CRITICAL: Without this, trader loses all context on restart
    """

    def __init__(self, trader):
        """
        Initialize state manager

        Args:
            trader: PS60Trader instance
        """
        self.trader = trader
        self.logger = logging.getLogger('StateManager')

        # State file location
        self.state_dir = Path(trader.config['logging']['log_dir'])
        self.state_dir.mkdir(exist_ok=True)

        self.state_file = self.state_dir / 'trader_state.json'
        self.backup_file = self.state_dir / 'trader_state_backup.json'

    def save_state(self):
        """
        Save current trading state to file

        CRITICAL: Call this every 10 seconds to minimize data loss

        Saves:
        - Open positions (with metadata)
        - Attempt counts (whipsaw protection)
        - Analytics (daily P&L, filter blocks)
        - Session info (start time, watchlist)
        """
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)

        try:
            # Build state snapshot
            state = {
                'timestamp': now_et.isoformat(),
                'date': now_et.strftime('%Y-%m-%d'),
                'positions': self._serialize_positions(),
                'attempt_counts': self._serialize_attempt_counts(),
                'analytics': self._serialize_analytics(),
                'session': {
                    'start_time': self.trader.analytics['session_start'].isoformat() if self.trader.analytics['session_start'] else None,
                    'watchlist_count': len(self.trader.watchlist),
                }
            }

            # Atomic write: write to temp file, then rename
            temp_file = self.state_file.with_suffix('.tmp')

            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)

            # Backup previous state (safety)
            if self.state_file.exists():
                self.state_file.replace(self.backup_file)

            # Move temp to actual state file
            temp_file.replace(self.state_file)

            # Log save (DEBUG only to avoid spam)
            self.logger.debug(f"State saved: {len(state['positions'])} positions, "
                            f"${state['analytics']['daily_pnl']:.2f} P&L")

        except Exception as e:
            self.logger.error(f"Failed to save state: {e}", exc_info=True)

    def load_state(self):
        """
        Load trading state from file

        CRITICAL: Validates state is from today before loading

        Returns:
            dict: State data, or None if not found/invalid
        """
        if not self.state_file.exists():
            self.logger.info("No previous state found (clean start)")
            return None

        try:
            with open(self.state_file) as f:
                state = json.load(f)

            # Validate state is from today
            eastern = pytz.timezone('US/Eastern')
            now_et = datetime.now(pytz.UTC).astimezone(eastern)
            state_date = state.get('date')

            if state_date != now_et.strftime('%Y-%m-%d'):
                self.logger.warning(f"State file is from {state_date}, today is {now_et.strftime('%Y-%m-%d')} - ignoring")
                return None

            self.logger.info(f"📂 Loaded state file from {state.get('timestamp')}")
            self.logger.info(f"   Positions: {len(state.get('positions', {}))}")
            self.logger.info(f"   Daily P&L: ${state.get('analytics', {}).get('daily_pnl', 0):.2f}")

            return state

        except json.JSONDecodeError as e:
            self.logger.error(f"State file corrupted: {e}")
            # Try backup
            if self.backup_file.exists():
                self.logger.warning("Attempting to load backup state file...")
                try:
                    with open(self.backup_file) as f:
                        state = json.load(f)
                    self.logger.info("✓ Backup state file loaded successfully")
                    return state
                except Exception:
                    pass

            self.logger.error("Cannot load state - starting fresh")
            return None

        except Exception as e:
            self.logger.error(f"Failed to load state: {e}", exc_info=True)
            return None

    def recover_from_ibkr(self):
        """
        Recover open positions from IBKR portfolio

        CRITICAL: IBKR is source of truth for actual positions

        Returns:
            dict: {symbol: ibkr_position}
        """
        try:
            # Get all open positions from IBKR
            positions = self.trader.ib.positions()

            ibkr_positions = {}

            for pos in positions:
                symbol = pos.contract.symbol

                # Only track positions in today's watchlist
                watchlist_symbols = [s['symbol'] for s in self.trader.watchlist]

                if symbol in watchlist_symbols:
                    ibkr_positions[symbol] = {
                        'shares': abs(pos.position),  # abs() handles both LONG/SHORT
                        'avg_cost': pos.avgCost,
                        'side': 'LONG' if pos.position > 0 else 'SHORT',
                        'contract': pos.contract
                    }

                    self.logger.info(f"🔄 IBKR POSITION: {symbol} {pos.position} shares @ avg ${pos.avgCost:.2f}")

            return ibkr_positions

        except Exception as e:
            self.logger.error(f"Failed to query IBKR positions: {e}", exc_info=True)
            return {}

    def recover_open_orders(self):
        """
        Recover open orders (stops) from IBKR

        Returns:
            dict: {symbol: {order_id, stop_price}}
        """
        try:
            orders = self.trader.ib.openOrders()

            open_stops = {}

            for order in orders:
                symbol = order.contract.symbol

                # Only track stop orders for our positions
                if symbol in self.trader.positions:
                    open_stops[symbol] = {
                        'order_id': order.orderId,
                        'stop_price': order.auxPrice if hasattr(order, 'auxPrice') else order.lmtPrice,
                        'shares': order.totalQuantity
                    }

                    stop_price = order.auxPrice if hasattr(order, 'auxPrice') else order.lmtPrice
                    self.logger.info(f"🔄 IBKR STOP ORDER: {symbol} @ ${stop_price:.2f}")

            return open_stops

        except Exception as e:
            self.logger.error(f"Failed to query IBKR orders: {e}", exc_info=True)
            return {}

    def recover_full_state(self):
        """
        HYBRID RECOVERY: Load state file + validate with IBKR

        CRITICAL: Best of both worlds
        - State file: metadata, attempt counts, analytics
        - IBKR: source of truth for actual positions

        This is called on trader startup (after connecting to IBKR)
        """
        self.logger.info("\n" + "="*80)
        self.logger.info("🔄 RECOVERING STATE FROM PREVIOUS SESSION...")
        self.logger.info("="*80)

        # Step 1: Load state file (metadata)
        state = self.load_state()

        # Step 2: Query IBKR (source of truth)
        ibkr_positions = self.recover_from_ibkr()
        ibkr_orders = self.recover_open_orders()

        if not state and not ibkr_positions:
            self.logger.info("No state to recover (clean start)")
            return

        # Step 3: Reconcile state file with IBKR
        if state and state.get('positions'):
            self._reconcile_positions(state['positions'], ibkr_positions, ibkr_orders)

        # Step 4: Restore attempt counts
        if state and state.get('attempt_counts'):
            self._restore_attempt_counts(state['attempt_counts'])

        # Step 5: Restore analytics
        if state and state.get('analytics'):
            self._restore_analytics(state['analytics'])

        # Step 6: Check for IBKR positions NOT in state file
        self._check_untracked_positions(ibkr_positions, state)

        self.logger.info("\n" + "="*80)
        self.logger.info("✓ STATE RECOVERY COMPLETE")
        self.logger.info(f"  Recovered Positions: {len(self.trader.positions)}")
        if self.trader.positions:
            for symbol in self.trader.positions:
                pos = self.trader.positions[symbol]
                self.logger.info(f"    {symbol}: {pos['side']} {pos['shares']} shares @ ${pos['entry_price']:.2f}")
        self.logger.info("="*80 + "\n")

    def _serialize_positions(self):
        """Serialize positions to JSON-compatible dict"""
        positions = {}

        for symbol, pos in self.trader.positions.items():
            # Convert entry_time to ISO string for JSON serialization
            entry_time = pos['entry_time']
            if isinstance(entry_time, datetime):
                entry_time = entry_time.isoformat()

            positions[symbol] = {
                'symbol': symbol,
                'side': pos['side'],
                'entry_price': pos['entry_price'],
                'entry_time': entry_time,
                'shares': pos['shares'],
                'remaining': pos['remaining'],
                'pivot': pos['pivot'],
                'target1': pos['target1'],
                'target2': pos['target2'],
                'stop_price': pos.get('stop_price'),
                'stop_order_id': pos.get('stop_order_id'),
                'partials_taken': pos.get('partials_taken', [])
            }

        return positions

    def _serialize_attempt_counts(self):
        """Serialize attempt counts from position manager"""
        # Get attempt counts from position manager
        attempt_counts = {}

        for symbol in [s['symbol'] for s in self.trader.watchlist]:
            resistance = next((s['resistance'] for s in self.trader.watchlist if s['symbol'] == symbol), None)
            support = next((s['support'] for s in self.trader.watchlist if s['symbol'] == symbol), None)

            if resistance:
                long_attempts = self.trader.pm.get_attempt_count(symbol, resistance)
                if long_attempts > 0:
                    if symbol not in attempt_counts:
                        attempt_counts[symbol] = {}
                    attempt_counts[symbol]['long_attempts'] = long_attempts
                    attempt_counts[symbol]['resistance'] = resistance

            if support:
                short_attempts = self.trader.pm.get_attempt_count(symbol, support)
                if short_attempts > 0:
                    if symbol not in attempt_counts:
                        attempt_counts[symbol] = {}
                    attempt_counts[symbol]['short_attempts'] = short_attempts
                    attempt_counts[symbol]['support'] = support

        return attempt_counts

    def _serialize_analytics(self):
        """Serialize analytics data"""
        summary = self.trader.pm.get_daily_summary()

        return {
            'daily_pnl': summary['daily_pnl'],
            'total_trades': summary['total_trades'],
            'winners': summary['winners'],
            'losers': summary['losers'],
            'filter_blocks': dict(self.trader.analytics['filter_blocks']),
            'entry_paths': dict(self.trader.analytics['entry_paths']),
            'pivot_checks': dict(self.trader.analytics['pivot_checks'])
        }

    def _reconcile_positions(self, state_positions, ibkr_positions, ibkr_orders):
        """
        Reconcile state file positions with IBKR reality

        CRITICAL: IBKR share count is source of truth
        """
        self.logger.info("\n🔄 VALIDATING POSITIONS WITH IBKR PORTFOLIO...")

        for symbol, pos_data in state_positions.items():
            if symbol in ibkr_positions:
                # ✓ IBKR confirms position exists
                ibkr_pos = ibkr_positions[symbol]

                # Validate shares match (within 0.1 for rounding)
                if abs(ibkr_pos['shares'] - pos_data['shares']) > 0.1:
                    self.logger.warning(f"⚠️  {symbol}: State file shows {pos_data['shares']} shares, "
                                      f"IBKR shows {ibkr_pos['shares']} shares")
                    self.logger.warning(f"    Using IBKR value (source of truth)")
                    pos_data['shares'] = ibkr_pos['shares']

                # Restore position with metadata from state file
                stock_data = next((s for s in self.trader.watchlist if s['symbol'] == symbol), None)

                if stock_data:
                    # Create position using position manager
                    position = self.trader.pm.create_position(
                        symbol=symbol,
                        side=pos_data['side'],
                        entry_price=pos_data['entry_price'],
                        shares=pos_data['shares'],
                        pivot=pos_data['pivot'],
                        contract=ibkr_pos['contract'],
                        target1=pos_data['target1'],
                        target2=pos_data['target2']
                    )

                    # Restore additional metadata
                    # CRITICAL: Convert entry_time string to datetime object
                    if isinstance(pos_data['entry_time'], str):
                        position['entry_time'] = datetime.fromisoformat(pos_data['entry_time'])
                    else:
                        position['entry_time'] = pos_data['entry_time']
                    position['remaining'] = pos_data['remaining']
                    position['stop_price'] = pos_data.get('stop_price')
                    position['partials_taken'] = pos_data.get('partials_taken', [])

                    # Restore stop order ID if exists
                    if symbol in ibkr_orders:
                        position['stop_order_id'] = ibkr_orders[symbol]['order_id']

                    self.trader.positions[symbol] = position

                    self.logger.info(f"✓ RECOVERED: {symbol} {pos_data['side']} {pos_data['shares']} shares "
                                   f"(state + IBKR validated)")
                else:
                    self.logger.warning(f"⚠️  {symbol}: Position exists but NOT in today's watchlist - skipping")

            else:
                # State file shows position but IBKR doesn't
                self.logger.warning(f"⚠️  {symbol}: State file shows position but NOT in IBKR portfolio")
                self.logger.warning(f"    Possible: closed by broker, or filled during downtime")
                self.logger.warning(f"    NOT restoring this position")

    def _restore_attempt_counts(self, attempt_counts):
        """Restore attempt counts to position manager"""
        self.logger.info("\n🔄 RESTORING ATTEMPT COUNTS...")

        # TODO: Implement record_attempt method in PositionManager
        # For now, skip attempt count restoration - not critical for trading
        self.logger.warning("⚠️  Attempt count restoration skipped (record_attempt method not implemented)")
        return

        # for symbol, counts in attempt_counts.items():
        #     if 'long_attempts' in counts:
        #         resistance = counts['resistance']
        #         for _ in range(counts['long_attempts']):
        #             self.trader.pm.record_attempt(symbol, resistance)
        #         self.logger.info(f"  {symbol}: {counts['long_attempts']} long attempts at ${resistance:.2f}")
        #
        #     if 'short_attempts' in counts:
        #         support = counts['support']
        #         for _ in range(counts['short_attempts']):
        #             self.trader.pm.record_attempt(symbol, support)
        #         self.logger.info(f"  {symbol}: {counts['short_attempts']} short attempts at ${support:.2f}")

    def _restore_analytics(self, analytics):
        """Restore analytics data"""
        self.logger.info("\n🔄 RESTORING ANALYTICS...")
        self.logger.info(f"  Daily P&L: ${analytics.get('daily_pnl', 0):.2f}")
        self.logger.info(f"  Trades Today: {analytics.get('total_trades', 0)}")
        self.logger.info(f"  Win Rate: {analytics.get('winners', 0)}/{analytics.get('total_trades', 0)}")

        # Restore filter blocks and entry paths
        self.trader.analytics['filter_blocks'] = defaultdict(int, analytics.get('filter_blocks', {}))
        self.trader.analytics['entry_paths'] = defaultdict(int, analytics.get('entry_paths', {}))
        self.trader.analytics['pivot_checks'] = defaultdict(int, analytics.get('pivot_checks', {}))

    def _check_untracked_positions(self, ibkr_positions, state):
        """
        Check for positions in IBKR but not in state file

        CRITICAL: Detect positions opened outside trader (or state file lost)
        """
        if not ibkr_positions:
            return

        state_symbols = set(state['positions'].keys()) if state and state.get('positions') else set()

        for symbol, ibkr_pos in ibkr_positions.items():
            if symbol not in state_symbols:
                self.logger.warning(f"\n⚠️  {symbol}: In IBKR portfolio but NOT in state file")
                self.logger.warning(f"    {ibkr_pos['shares']} shares @ ${ibkr_pos['avg_cost']:.2f}")
                self.logger.warning(f"    Possible: opened manually, or state file lost")
                self.logger.warning(f"    Creating minimal position (metadata unknown)")

                # Create minimal position from IBKR data
                stock_data = next((s for s in self.trader.watchlist if s['symbol'] == symbol), None)

                if stock_data:
                    position = self.trader.pm.create_position(
                        symbol=symbol,
                        side=ibkr_pos['side'],
                        entry_price=ibkr_pos['avg_cost'],
                        shares=ibkr_pos['shares'],
                        pivot=stock_data['resistance'] if ibkr_pos['side'] == 'LONG' else stock_data['support'],
                        contract=ibkr_pos['contract'],
                        target1=stock_data['target1'],
                        target2=stock_data.get('target2', stock_data['target1'] * 1.02)
                    )

                    # Mark as recovered with incomplete data
                    eastern = pytz.timezone('US/Eastern')
                    # CRITICAL: Use datetime object, not string
                    position['entry_time'] = datetime.now(pytz.UTC).astimezone(eastern)
                    position['remaining'] = 1.0  # Assume no partials
                    position['recovered_incomplete'] = True

                    self.trader.positions[symbol] = position

                    self.logger.warning(f"    ⚠️  Position created with ESTIMATED metadata - manage carefully")
