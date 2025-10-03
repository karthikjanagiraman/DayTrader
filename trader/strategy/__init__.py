"""
PS60 Trading Strategy Module

Shared trading logic used by both live trader and backtester.
This ensures consistency and single source of truth for strategy rules.
"""

from .ps60_strategy import PS60Strategy
from .position_manager import PositionManager

__all__ = ['PS60Strategy', 'PositionManager']
