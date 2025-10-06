"""
Position Manager - Position Tracking and P&L Calculation

Handles position state management, partial profits tracking, and P&L calculation.
Shared by both live trader and backtester.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pytz


class PositionManager:
    """
    Manages trading positions and their lifecycle

    Tracks:
    - Entry/exit prices and times
    - Partial profits taken
    - Current remaining position size
    - P&L calculations
    """

    def __init__(self):
        """Initialize position manager"""
        self.positions: Dict[str, dict] = {}
        self.trades_today: List[dict] = []
        self.daily_pnl = 0.0
        self.attempt_counts: Dict[str, int] = {}

    def create_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        shares: int,
        pivot: float,
        contract=None,
        **kwargs
    ) -> dict:
        """
        Create new position

        Args:
            symbol: Stock symbol
            side: 'LONG' or 'SHORT'
            entry_price: Entry price
            shares: Number of shares
            pivot: Pivot price (resistance for longs, support for shorts)
            contract: IBKR contract object (optional, for live trading)
            **kwargs: Additional position data (target1, target2, etc.)

        Returns:
            Position dict
        """
        position = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'entry_time': datetime.now(pytz.UTC),  # Timezone-aware UTC
            'shares': shares,
            'remaining': 1.0,  # 100% remaining
            'pivot': pivot,
            'stop': pivot,  # Initial stop at pivot
            'partials': [],
            'contract': contract,
            'highest_price': entry_price if side == 'LONG' else None,
            'lowest_price': entry_price if side == 'SHORT' else None,
        }

        # Add optional fields
        for key, value in kwargs.items():
            position[key] = value

        self.positions[symbol] = position

        # Track attempt count
        pivot_key = f"{symbol}_{pivot:.2f}"
        self.attempt_counts[pivot_key] = self.attempt_counts.get(pivot_key, 0) + 1

        return position

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position by symbol"""
        return self.positions.get(symbol)

    def has_position(self, symbol: str) -> bool:
        """Check if position exists"""
        return symbol in self.positions

    def get_attempt_count(self, symbol: str, pivot: float) -> int:
        """Get number of attempts on this pivot"""
        pivot_key = f"{symbol}_{pivot:.2f}"
        return self.attempt_counts.get(pivot_key, 0)

    def update_price_extremes(self, symbol: str, current_price: float):
        """
        Update highest/lowest price seen for position

        Used for trailing stop calculations
        """
        if symbol not in self.positions:
            return

        position = self.positions[symbol]

        if position['side'] == 'LONG':
            if position['highest_price'] is None or current_price > position['highest_price']:
                position['highest_price'] = current_price
        else:
            if position['lowest_price'] is None or current_price < position['lowest_price']:
                position['lowest_price'] = current_price

    def take_partial(
        self,
        symbol: str,
        price: float,
        pct: float,
        reason: str
    ) -> Optional[dict]:
        """
        Record partial profit taken

        Args:
            symbol: Stock symbol
            price: Exit price for partial
            pct: Percentage of position sold (e.g., 0.50 for 50%)
            reason: Reason for partial (e.g., 'FIRST_MOVE', 'TARGET1')

        Returns:
            Partial record dict
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # Calculate gain
        if position['side'] == 'LONG':
            gain = price - position['entry_price']
        else:
            gain = position['entry_price'] - price

        partial = {
            'time': datetime.now(pytz.UTC),  # Timezone-aware UTC
            'price': price,
            'pct': pct,
            'gain': gain,
            'reason': reason
        }

        position['partials'].append(partial)
        position['remaining'] -= pct

        return partial

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str,
        exit_time: datetime = None
    ) -> Optional[dict]:
        """
        Close position and record trade

        Args:
            symbol: Stock symbol
            exit_price: Exit price
            reason: Exit reason (e.g., 'STOP', 'TARGET', 'EOD')
            exit_time: Exit timestamp (uses current time if None)

        Returns:
            Trade record dict
        """
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # Calculate total P&L
        pnl = self.calculate_pnl(position, exit_price)

        # Use provided exit_time or current time
        # FIX: Accept exit_time parameter instead of always using datetime.now()
        if exit_time is None:
            exit_time = datetime.now(pytz.UTC)

        entry_time = position['entry_time']

        # Ensure both are UTC for consistent duration calculation
        if entry_time.tzinfo is None:
            entry_time = pytz.UTC.localize(entry_time)
        else:
            entry_time = entry_time.astimezone(pytz.UTC)

        if exit_time.tzinfo is None:
            exit_time = pytz.UTC.localize(exit_time)
        else:
            exit_time = exit_time.astimezone(pytz.UTC)

        duration_min = (exit_time - entry_time).total_seconds() / 60

        # Create trade record
        trade_record = {
            'symbol': symbol,
            'side': position['side'],
            'entry_price': position['entry_price'],
            'entry_time': position['entry_time'],
            'exit_price': exit_price,
            'exit_time': exit_time,
            'shares': position['shares'],
            'pnl': pnl,
            'reason': reason,
            'partials': len(position['partials']),
            'duration_min': duration_min
        }

        self.trades_today.append(trade_record)
        self.daily_pnl += pnl

        # Remove position
        del self.positions[symbol]

        return trade_record

    def calculate_pnl(self, position: dict, exit_price: float) -> float:
        """
        Calculate total P&L for position including partials

        Args:
            position: Position dict
            exit_price: Exit price for remaining shares

        Returns:
            Total P&L in dollars
        """
        total_pnl = 0.0

        # P&L from partials
        for partial in position['partials']:
            pnl_partial = partial['gain'] * position['shares'] * partial['pct']
            total_pnl += pnl_partial

        # P&L from remaining
        if position['side'] == 'LONG':
            remaining_pnl = (exit_price - position['entry_price']) * position['shares'] * position['remaining']
        else:
            remaining_pnl = (position['entry_price'] - exit_price) * position['shares'] * position['remaining']

        total_pnl += remaining_pnl

        return total_pnl

    def get_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        """
        Calculate unrealized P&L for open position

        Args:
            symbol: Stock symbol
            current_price: Current market price

        Returns:
            Unrealized P&L in dollars
        """
        if symbol not in self.positions:
            return 0.0

        position = self.positions[symbol]
        return self.calculate_pnl(position, current_price)

    def get_all_positions(self) -> List[dict]:
        """Get all open positions"""
        return list(self.positions.values())

    def get_position_count(self) -> int:
        """Get count of open positions"""
        return len(self.positions)

    def close_all_positions(self, current_prices: Dict[str, float], reason: str = 'EOD') -> List[dict]:
        """
        Close all open positions

        Args:
            current_prices: Dict of symbol -> current price
            reason: Exit reason

        Returns:
            List of trade records
        """
        trades = []

        for symbol in list(self.positions.keys()):
            price = current_prices.get(symbol)
            if price:
                trade = self.close_position(symbol, price, reason)
                if trade:
                    trades.append(trade)

        return trades

    def get_daily_summary(self) -> dict:
        """
        Get daily trading summary

        Returns:
            Summary dict with P&L, win rate, etc.
        """
        if not self.trades_today:
            return {
                'total_trades': 0,
                'daily_pnl': 0.0,
                'winners': 0,
                'losers': 0,
                'win_rate': 0.0,
                'avg_winner': 0.0,
                'avg_loser': 0.0,
            }

        winners = [t for t in self.trades_today if t['pnl'] > 0]
        losers = [t for t in self.trades_today if t['pnl'] < 0]

        return {
            'total_trades': len(self.trades_today),
            'daily_pnl': self.daily_pnl,
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': len(winners) / len(self.trades_today) * 100 if self.trades_today else 0,
            'avg_winner': sum(t['pnl'] for t in winners) / len(winners) if winners else 0,
            'avg_loser': sum(t['pnl'] for t in losers) / len(losers) if losers else 0,
        }

    def reset_daily(self):
        """Reset daily counters (for new trading day)"""
        self.trades_today = []
        self.daily_pnl = 0.0
        # Keep positions (in case overnight)
        # Keep attempt_counts (reset manually if needed)
