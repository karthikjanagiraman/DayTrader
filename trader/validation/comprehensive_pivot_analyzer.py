#!/usr/bin/env python3
"""
Comprehensive Pivot Behavior & Strategy Analysis Tool

Analyzes scanner-identified pivots with complete PS60 strategy simulation including:
- Full state machine tracking
- All filter calculations
- Multi-bar confirmation sequences
- Market context analysis
- Gap detection and handling
- Entry quality scoring
- Complete decision engine simulation

Author: DayTrader System
Date: October 30, 2025
Version: 1.0
"""

import sys
import os
import json
import yaml
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import csv
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# Add trader directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import IBKR
from ib_insync import IB, Stock, util

# For technical indicators
import pandas as pd
import numpy as np


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class State(Enum):
    """Trading state machine states"""
    INIT = "INIT"
    MONITORING_BREAKOUT = "MONITORING_BREAKOUT"
    WAITING_FOR_CANDLE_CLOSE = "WAITING_FOR_CANDLE_CLOSE"
    MOMENTUM_BREAKOUT_DETECTED = "MOMENTUM_BREAKOUT_DETECTED"
    WEAK_BREAKOUT_TRACKING = "WEAK_BREAKOUT_TRACKING"
    PULLBACK_TRACKING = "PULLBACK_TRACKING"
    WAITING_FOR_PULLBACK = "WAITING_FOR_PULLBACK"
    CVD_MONITORING = "CVD_MONITORING"
    SUSTAINED_BREAK_TRACKING = "SUSTAINED_BREAK_TRACKING"
    ENTERING_POSITION = "ENTERING_POSITION"
    POSITION_ACTIVE = "POSITION_ACTIVE"
    BLOCKED = "BLOCKED"


class EntryPath(Enum):
    """Entry path types"""
    MOMENTUM_BREAKOUT = "MOMENTUM_BREAKOUT"
    PULLBACK_RETEST = "PULLBACK_RETEST"
    SUSTAINED_BREAK = "SUSTAINED_BREAK"
    CVD_MONITORING = "CVD_MONITORING"
    NONE = "NONE"


class Decision(Enum):
    """Strategy decisions"""
    ENTER = "ENTER"
    BLOCK = "BLOCK"
    WAIT = "WAIT"
    MONITOR = "MONITOR"


class Outcome(Enum):
    """Trade outcomes"""
    WINNER = "WINNER"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"
    STOPPED_OUT = "STOPPED_OUT"
    NO_BREAKOUT = "NO_BREAKOUT"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Bar:
    """Single bar data"""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_pct(self) -> float:
        return (self.body / self.close) * 100 if self.close > 0 else 0

    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low


@dataclass
class BreakoutData:
    """Breakout information"""
    symbol: str
    direction: str  # LONG or SHORT
    pivot_price: float
    breakout_time: datetime
    breakout_bar_idx: int
    breakout_price: float
    bars_since_open: int
    opening_price: float
    previous_close: float
    target1: float
    target2: Optional[float] = None
    target3: Optional[float] = None


@dataclass
class FilterResult:
    """Individual filter result"""
    enabled: bool
    result: str  # PASS or BLOCK
    value: float
    threshold: float
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StateTransition:
    """State machine transition"""
    bar_idx: int
    time: datetime
    from_state: State
    to_state: State
    trigger: str
    details: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# MAIN ANALYZER CLASS
# ============================================================================

class ComprehensivePivotAnalyzer:
    """Complete pivot behavior and strategy analyzer"""

    def __init__(self, date: str, config_file: Optional[str] = None):
        self.date = date
        self.ib = None
        self.config = self._load_config(config_file)
        self.cache_dir = Path(__file__).parent.parent / "backtest" / "data"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Results storage
        self.results = []
        self.debug_data = defaultdict(list)

        # Market data cache
        self.spy_data = None
        self.vix_data = None

    def _load_config(self, config_file: Optional[str]) -> Dict:
        """Load configuration from trader_config.yaml"""
        if config_file and Path(config_file).exists():
            config_path = Path(config_file)
        else:
            # Try default location
            config_path = Path(__file__).parent.parent / "config" / "trader_config.yaml"

        config = {}
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        else:
            print(f"⚠️  Config file not found at {config_path}, using defaults")

        # Merge with defaults to ensure all required fields exist
        default_config = self._get_default_config()

        # Deep merge config with defaults
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
            elif isinstance(value, dict) and isinstance(config.get(key), dict):
                # Recursively merge nested dicts
                for subkey, subvalue in value.items():
                    if subkey not in config[key]:
                        config[key][subkey] = subvalue

        return config

    def _get_default_config(self) -> Dict:
        """Get default configuration values"""
        return {
            'filters': {
                'enable_choppy_filter': True,
                'choppy_range_threshold': 0.5,
                'enable_room_to_run_filter': True,
                'room_to_run_threshold': 0.015,
                'enable_stochastic_filter': False,
                'stochastic_overbought': 80,
                'stochastic_oversold': 20,
                'enable_cvd_filter': True,
                'cvd_imbalance_threshold': 10.0,
                'enable_volume_filter': True,
                'volume_threshold': 1.0,
                'enable_directional_volume_filter': False,
                'directional_volume_threshold': 1.5,
                'avoid_index_shorts': True,
                'enable_gap_filter': True,
                'max_gap_through_pivot': 1.0,
                'min_room_to_target_after_gap': 3.0
            },
            'confirmation': {
                'momentum_volume_threshold': 2.0,
                'momentum_candle_size_pct': 1.5,
                'momentum_atr_multiplier': 2.0,
                'pullback_zone_pct': 0.3,
                'pullback_retest_volume': 1.2,
                'sustained_break_bars': 2,
                'sustained_break_volume': 0.8,
                'cvd': {
                    'imbalance_threshold': 10.0,
                    'confirmation_bars': 3
                }
            },
            'timing': {
                'no_entry_before': "09:45:00",
                'no_entry_after': "15:00:00"
            },
            'risk': {
                'max_attempts_per_pivot': 2,
                'attempt_cooldown_minutes': 5
            }
        }

    # ==========================================================================
    # DATA LOADING
    # ==========================================================================

    def connect_ib(self):
        """Connect to IBKR"""
        self.ib = IB()
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=9001)
            print("✅ Connected to IBKR")
            return True
        except Exception as e:
            print(f"⚠️  IBKR connection failed: {e}")
            print("   Continuing with cached data only...")
            return False

    def disconnect_ib(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("✅ Disconnected from IBKR")

    def get_bars(self, symbol: str, bar_size: str = "1min") -> Optional[List[Bar]]:
        """Get bars from cache or IBKR"""
        # Try cache first
        bars_data = self._get_cached_bars(symbol, bar_size)
        if bars_data:
            return [self._dict_to_bar(b) for b in bars_data]

        # Fetch from IBKR if connected
        if self.ib and self.ib.isConnected():
            bars_data = self._fetch_bars_from_ibkr(symbol, bar_size)
            if bars_data:
                return [self._dict_to_bar(b) for b in bars_data]

        return None

    def _get_cached_bars(self, symbol: str, bar_size: str = "1min") -> Optional[List[Dict]]:
        """Load bars from cache"""
        # Try different cache formats
        date_no_dashes = self.date.replace('-', '')

        if bar_size == "1min":
            cache_files = [
                self.cache_dir / f"{symbol}_{self.date}_1min_bars.json",
                self.cache_dir / f"{symbol}_{date_no_dashes}_1min.json",
                self.cache_dir / f"{symbol}_{date_no_dashes}_1min_bars.json"
            ]
        else:  # 5sec
            cache_files = [
                self.cache_dir / "cvd_bars" / f"{symbol}_{date_no_dashes}_5sec_bars.json"
            ]

        for cache_file in cache_files:
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        bars_data = json.load(f)
                        print(f"  📦 Loaded {symbol} from cache ({len(bars_data)} {bar_size} bars)")
                        return bars_data
                except Exception as e:
                    print(f"  ⚠️  Cache read error for {symbol}: {e}")

        return None

    def _fetch_bars_from_ibkr(self, symbol: str, bar_size: str = "1min") -> Optional[List[Dict]]:
        """Fetch bars from IBKR"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Format date for IBKR
            date_formatted = self.date.replace('-', '')
            end_datetime = f"{date_formatted} 16:00:00"

            # Determine bar size setting
            if bar_size == "1min":
                bar_size_setting = '1 min'
                duration = '1 D'
            else:  # 5sec
                bar_size_setting = '5 secs'
                duration = '1800 S'  # 30 minutes of 5-sec bars

            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr=duration,
                barSizeSetting=bar_size_setting,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if bars:
                print(f"  📡 Fetched {symbol} from IBKR ({len(bars)} {bar_size} bars)")
                bars_data = []
                for bar in bars:
                    bars_data.append({
                        'date': bar.date.isoformat() if hasattr(bar.date, 'isoformat') else str(bar.date),
                        'open': bar.open,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': bar.volume
                    })
                # Cache for future use
                self._cache_bars(symbol, bars_data, bar_size)
                return bars_data

        except Exception as e:
            print(f"  ❌ IBKR fetch error for {symbol}: {e}")

        return None

    def _cache_bars(self, symbol: str, bars_data: List[Dict], bar_size: str = "1min"):
        """Cache bars for future use"""
        date_no_dashes = self.date.replace('-', '')

        if bar_size == "1min":
            cache_file = self.cache_dir / f"{symbol}_{self.date}_1min_bars.json"
        else:
            cache_dir = self.cache_dir / "cvd_bars"
            cache_dir.mkdir(exist_ok=True)
            cache_file = cache_dir / f"{symbol}_{date_no_dashes}_5sec_bars.json"

        try:
            with open(cache_file, 'w') as f:
                json.dump(bars_data, f, indent=2)
            print(f"  💾 Cached {symbol} ({len(bars_data)} {bar_size} bars)")
        except Exception as e:
            print(f"  ⚠️  Cache write error: {e}")

    def _dict_to_bar(self, bar_dict: Dict) -> Bar:
        """Convert dictionary to Bar object"""
        # Handle different date formats
        date_str = bar_dict['date']
        if isinstance(date_str, str):
            # Try different date formats
            for fmt in ['%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                try:
                    dt = datetime.strptime(date_str.split('.')[0].replace('-04:00', ''), fmt)
                    break
                except:
                    continue
            else:
                dt = datetime.now()  # Fallback
        else:
            dt = date_str

        return Bar(
            date=dt,
            open=bar_dict['open'],
            high=bar_dict['high'],
            low=bar_dict['low'],
            close=bar_dict['close'],
            volume=bar_dict.get('volume', 0)
        )

    # ==========================================================================
    # MARKET CONTEXT
    # ==========================================================================

    def load_market_context(self):
        """Load SPY and VIX data for market context"""
        print("📊 Loading market context data...")

        # Load SPY data
        self.spy_data = self.get_bars('SPY', '1min')
        if self.spy_data:
            print(f"  ✅ Loaded SPY data ({len(self.spy_data)} bars)")
        else:
            print("  ⚠️  No SPY data available")

        # For now, skip VIX as it requires daily bars
        # Could be enhanced to fetch from a different source

    def get_market_context_at_time(self, bar_idx: int) -> Dict:
        """Get market context at specific bar"""
        context = {
            'spy_trend': 'UNKNOWN',
            'spy_strength': 0.0,
            'spy_volume': 'NORMAL',
            'market_regime': 'UNKNOWN',
            'vix_level': None,
            'risk_regime': 'NORMAL'
        }

        if self.spy_data and bar_idx < len(self.spy_data):
            # Calculate SPY trend
            if bar_idx >= 20:
                spy_close = self.spy_data[bar_idx].close
                spy_open = self.spy_data[max(0, bar_idx-20)].close
                spy_change_pct = ((spy_close - spy_open) / spy_open) * 100

                if spy_change_pct > 0.2:
                    context['spy_trend'] = 'UP'
                elif spy_change_pct < -0.2:
                    context['spy_trend'] = 'DOWN'
                else:
                    context['spy_trend'] = 'FLAT'

                context['spy_strength'] = abs(spy_change_pct)

                # Determine market regime
                if abs(spy_change_pct) > 0.5:
                    context['market_regime'] = 'TRENDING'
                else:
                    context['market_regime'] = 'CHOPPY'

        return context

    # ==========================================================================
    # BREAKOUT DETECTION
    # ==========================================================================

    def detect_breakouts(self, symbol: str, stock_data: Dict, bars: List[Bar]) -> List[BreakoutData]:
        """Detect all breakouts for a symbol"""
        breakouts = []

        resistance = stock_data.get('resistance')
        support = stock_data.get('support')
        target1 = stock_data.get('target1')
        target2 = stock_data.get('target2')
        target3 = stock_data.get('target3')
        downside1 = stock_data.get('downside1')
        downside2 = stock_data.get('downside2')

        # Get opening price (first bar)
        opening_price = bars[0].open if bars else 0

        # Get previous close (would need previous day data, approximate with first bar)
        previous_close = stock_data.get('close', opening_price)

        # Track if breakout already detected
        long_breakout_detected = False
        short_breakout_detected = False

        # Market open is typically bar index 0 (9:30 AM)
        market_open_idx = 0

        for idx, bar in enumerate(bars):
            bars_since_open = idx - market_open_idx

            # LONG breakout detection
            if resistance and not long_breakout_detected:
                if bar.close > resistance:
                    breakout = BreakoutData(
                        symbol=symbol,
                        direction='LONG',
                        pivot_price=resistance,
                        breakout_time=bar.date,
                        breakout_bar_idx=idx,
                        breakout_price=bar.close,
                        bars_since_open=bars_since_open,
                        opening_price=opening_price,
                        previous_close=previous_close,
                        target1=target1 if target1 else resistance * 1.02,
                        target2=target2,
                        target3=target3
                    )
                    breakouts.append(breakout)
                    long_breakout_detected = True

            # SHORT breakout detection
            if support and not short_breakout_detected:
                if bar.close < support:
                    breakout = BreakoutData(
                        symbol=symbol,
                        direction='SHORT',
                        pivot_price=support,
                        breakout_time=bar.date,
                        breakout_bar_idx=idx,
                        breakout_price=bar.close,
                        bars_since_open=bars_since_open,
                        opening_price=opening_price,
                        previous_close=previous_close,
                        target1=downside1 if downside1 else support * 0.98,
                        target2=downside2,
                        target3=None  # Shorts typically only have 2 targets
                    )
                    breakouts.append(breakout)
                    short_breakout_detected = True

            # Stop if both detected
            if long_breakout_detected and short_breakout_detected:
                break

        return breakouts

    # ==========================================================================
    # GAP ANALYSIS
    # ==========================================================================

    def analyze_gap(self, breakout: BreakoutData) -> Dict:
        """Analyze gap at market open"""
        gap_analysis = {
            'has_gap': False,
            'gap_type': 'NONE',
            'gap_size_pct': 0.0,
            'gap_through_pivot': False,
            'room_after_gap': 0.0,
            'gap_invalidates_setup': False
        }

        # Calculate gap
        gap_pct = ((breakout.opening_price - breakout.previous_close) / breakout.previous_close) * 100

        if abs(gap_pct) < 0.5:
            gap_analysis['gap_type'] = 'NO_GAP'
        elif breakout.direction == 'LONG':
            # Check if gapped through resistance
            if breakout.previous_close < breakout.pivot_price <= breakout.opening_price:
                gap_analysis['has_gap'] = True
                gap_analysis['gap_through_pivot'] = True
                gap_size_through = ((breakout.opening_price - breakout.pivot_price) / breakout.pivot_price) * 100
                gap_analysis['gap_size_pct'] = gap_size_through

                # Calculate room remaining to target
                room_to_target = ((breakout.target1 - breakout.opening_price) / breakout.opening_price) * 100
                gap_analysis['room_after_gap'] = room_to_target

                if gap_size_through < 1.0:
                    gap_analysis['gap_type'] = 'SMALL_GAP'
                else:
                    gap_analysis['gap_type'] = 'LARGE_GAP'
                    if room_to_target < self.config['filters'].get('min_room_to_target_after_gap', 3.0):
                        gap_analysis['gap_invalidates_setup'] = True

        elif breakout.direction == 'SHORT':
            # Check if gapped through support
            if breakout.previous_close > breakout.pivot_price >= breakout.opening_price:
                gap_analysis['has_gap'] = True
                gap_analysis['gap_through_pivot'] = True
                gap_size_through = ((breakout.pivot_price - breakout.opening_price) / breakout.pivot_price) * 100
                gap_analysis['gap_size_pct'] = gap_size_through

                # Calculate room remaining to target
                room_to_target = ((breakout.opening_price - breakout.target1) / breakout.opening_price) * 100
                gap_analysis['room_after_gap'] = room_to_target

                if gap_size_through < 1.0:
                    gap_analysis['gap_type'] = 'SMALL_GAP'
                else:
                    gap_analysis['gap_type'] = 'LARGE_GAP'
                    if room_to_target < self.config['filters'].get('min_room_to_target_after_gap', 3.0):
                        gap_analysis['gap_invalidates_setup'] = True

        return gap_analysis

    # ==========================================================================
    # TIMING VALIDATION
    # ==========================================================================

    def validate_timing(self, breakout: BreakoutData) -> Dict:
        """Validate if breakout is in valid entry window"""
        timing = {
            'in_entry_window': False,
            'minutes_from_open': 0,
            'minutes_to_close': 0,
            'time_zone': 'UNKNOWN',
            'optimal_time': False,
            'too_early': False,
            'too_late': False
        }

        # Calculate minutes from market open (9:30 AM)
        market_open = breakout.breakout_time.replace(hour=9, minute=30, second=0)
        market_close = breakout.breakout_time.replace(hour=16, minute=0, second=0)

        minutes_from_open = (breakout.breakout_time - market_open).total_seconds() / 60
        minutes_to_close = (market_close - breakout.breakout_time).total_seconds() / 60

        timing['minutes_from_open'] = int(minutes_from_open)
        timing['minutes_to_close'] = int(minutes_to_close)

        # Parse config times
        no_entry_before = self.config['timing'].get('no_entry_before', '09:45:00')
        no_entry_after = self.config['timing'].get('no_entry_after', '15:00:00')

        before_hour, before_min, before_sec = map(int, no_entry_before.split(':'))
        after_hour, after_min, after_sec = map(int, no_entry_after.split(':'))

        earliest_entry = market_open.replace(hour=before_hour, minute=before_min, second=before_sec)
        latest_entry = market_open.replace(hour=after_hour, minute=after_min, second=after_sec)

        # Check if in valid window
        if earliest_entry <= breakout.breakout_time <= latest_entry:
            timing['in_entry_window'] = True
        elif breakout.breakout_time < earliest_entry:
            timing['too_early'] = True
        else:
            timing['too_late'] = True

        # Determine time zone
        if minutes_from_open < 30:
            timing['time_zone'] = 'EARLY'
        elif minutes_from_open < 120:
            timing['time_zone'] = 'MORNING'
        elif minutes_from_open < 240:
            timing['time_zone'] = 'MIDDAY'
        else:
            timing['time_zone'] = 'LATE'

        # Check if optimal time (first 45 min or last 90 min)
        if (15 <= minutes_from_open <= 60) or (300 <= minutes_from_open <= 390):
            timing['optimal_time'] = True

        return timing

    # ==========================================================================
    # TECHNICAL INDICATORS
    # ==========================================================================

    def calculate_atr(self, bars: List[Bar], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(bars) < period:
            return 0.0

        true_ranges = []
        for i in range(1, len(bars)):
            tr = max(
                bars[i].high - bars[i].low,
                abs(bars[i].high - bars[i-1].close),
                abs(bars[i].low - bars[i-1].close)
            )
            true_ranges.append(tr)

        if len(true_ranges) >= period:
            return sum(true_ranges[-period:]) / period
        return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0

    def calculate_stochastic(self, bars: List[Bar], idx: int, period: int = 14) -> Tuple[float, float]:
        """Calculate Stochastic oscillator %K and %D"""
        if idx < period:
            return 50.0, 50.0  # Default neutral values

        # Get last 'period' bars
        period_bars = bars[max(0, idx-period+1):idx+1]

        # Find highest high and lowest low
        highest = max(bar.high for bar in period_bars)
        lowest = min(bar.low for bar in period_bars)

        # Calculate %K
        current_close = bars[idx].close
        if highest != lowest:
            k_value = ((current_close - lowest) / (highest - lowest)) * 100
        else:
            k_value = 50.0

        # Calculate %D (3-period SMA of %K)
        # Simplified: just return %K for now
        d_value = k_value

        return k_value, d_value

    def calculate_volume_ratio(self, bars: List[Bar], idx: int, period: int = 20) -> float:
        """Calculate volume ratio vs average"""
        if idx < period:
            period = max(1, idx)

        # Get average volume
        period_bars = bars[max(0, idx-period):idx]
        if not period_bars:
            return 1.0

        avg_volume = sum(bar.volume for bar in period_bars) / len(period_bars)
        current_volume = bars[idx].volume

        if avg_volume > 0:
            return current_volume / avg_volume
        return 1.0

    def calculate_cvd(self, bars: List[Bar], idx: int, lookback: int = 20) -> Dict:
        """Calculate Cumulative Volume Delta (approximated from 1-min bars)"""
        cvd_data = {
            'buy_volume': 0,
            'sell_volume': 0,
            'net_delta': 0,
            'imbalance_pct': 0.0,
            'trend': 'NEUTRAL'
        }

        if idx < lookback:
            lookback = max(1, idx)

        # Approximate buy/sell volume from price action
        for i in range(max(0, idx-lookback+1), idx+1):
            bar = bars[i]
            # Simple approximation: if close > open, more buying
            # Use (close - open) / range as buy percentage
            if bar.range > 0:
                buy_pct = (bar.close - bar.low) / bar.range
                buy_vol = bar.volume * buy_pct
                sell_vol = bar.volume * (1 - buy_pct)
            else:
                buy_vol = bar.volume * 0.5
                sell_vol = bar.volume * 0.5

            cvd_data['buy_volume'] += buy_vol
            cvd_data['sell_volume'] += sell_vol

        cvd_data['net_delta'] = cvd_data['buy_volume'] - cvd_data['sell_volume']

        # Calculate imbalance
        total_volume = cvd_data['buy_volume'] + cvd_data['sell_volume']
        if total_volume > 0:
            cvd_data['imbalance_pct'] = (abs(cvd_data['net_delta']) / total_volume) * 100

        # Determine trend
        if cvd_data['net_delta'] > 0 and cvd_data['imbalance_pct'] > 5:
            cvd_data['trend'] = 'BULLISH'
        elif cvd_data['net_delta'] < 0 and cvd_data['imbalance_pct'] > 5:
            cvd_data['trend'] = 'BEARISH'
        else:
            cvd_data['trend'] = 'NEUTRAL'

        return cvd_data

    # ==========================================================================
    # FILTER CALCULATIONS
    # ==========================================================================

    def calculate_choppy_filter(self, bars: List[Bar], idx: int) -> FilterResult:
        """Calculate choppy market filter"""
        config = self.config['filters']

        if not config.get('enable_choppy_filter', True):
            return FilterResult(
                enabled=False,
                result='DISABLED',
                value=0.0,
                threshold=0.0,
                reason='Filter disabled'
            )

        # Look back 60 bars (1 hour)
        lookback = 60
        if idx < lookback:
            lookback = max(1, idx)

        period_bars = bars[max(0, idx-lookback+1):idx+1]

        # Calculate range
        highest = max(bar.high for bar in period_bars)
        lowest = min(bar.low for bar in period_bars)
        range_val = highest - lowest
        range_pct = (range_val / lowest) * 100 if lowest > 0 else 0

        # Calculate ATR
        atr = self.calculate_atr(bars[:idx+1])
        atr_ratio = range_val / atr if atr > 0 else 0

        # Get threshold
        threshold = config.get('choppy_range_threshold', 0.5)

        # Determine result
        if range_pct >= threshold:
            result = 'PASS'
            reason = f'Range {range_pct:.2f}% >= {threshold}% threshold'
        else:
            result = 'BLOCK'
            reason = f'Range {range_pct:.2f}% < {threshold}% threshold (too choppy)'

        return FilterResult(
            enabled=True,
            result=result,
            value=range_pct,
            threshold=threshold,
            reason=reason,
            details={'atr_ratio': atr_ratio, 'bars_checked': lookback}
        )

    def calculate_room_to_run_filter(self, breakout: BreakoutData, current_price: float) -> FilterResult:
        """Calculate room to run filter"""
        config = self.config['filters']

        if not config.get('enable_room_to_run_filter', True):
            return FilterResult(
                enabled=False,
                result='DISABLED',
                value=0.0,
                threshold=0.0,
                reason='Filter disabled'
            )

        # Calculate room to target
        if breakout.direction == 'LONG':
            room_pct = ((breakout.target1 - current_price) / current_price) * 100
        else:  # SHORT
            room_pct = ((current_price - breakout.target1) / current_price) * 100

        # Get threshold
        threshold = config.get('room_to_run_threshold', 1.5) * 100  # Convert to percentage

        # Determine result
        if room_pct >= threshold:
            result = 'PASS'
            reason = f'Room {room_pct:.2f}% >= {threshold:.1f}% threshold'
        else:
            result = 'BLOCK'
            reason = f'Room {room_pct:.2f}% < {threshold:.1f}% threshold (insufficient room)'

        return FilterResult(
            enabled=True,
            result=result,
            value=room_pct,
            threshold=threshold,
            reason=reason,
            details={'target_price': breakout.target1}
        )

    def calculate_stochastic_filter(self, bars: List[Bar], idx: int, direction: str) -> FilterResult:
        """Calculate stochastic filter"""
        config = self.config['filters']

        if not config.get('enable_stochastic_filter', False):
            return FilterResult(
                enabled=False,
                result='DISABLED',
                value=0.0,
                threshold=0.0,
                reason='Filter disabled'
            )

        # Calculate stochastic
        k_value, d_value = self.calculate_stochastic(bars, idx)

        # Get thresholds
        overbought = config.get('stochastic_overbought', 80)
        oversold = config.get('stochastic_oversold', 20)

        # Determine result based on direction
        if direction == 'LONG':
            if k_value > overbought:
                result = 'BLOCK'
                reason = f'Stochastic {k_value:.1f} > {overbought} (overbought)'
            else:
                result = 'PASS'
                reason = f'Stochastic {k_value:.1f} <= {overbought}'
            threshold = overbought
        else:  # SHORT
            if k_value < oversold:
                result = 'BLOCK'
                reason = f'Stochastic {k_value:.1f} < {oversold} (oversold)'
            else:
                result = 'PASS'
                reason = f'Stochastic {k_value:.1f} >= {oversold}'
            threshold = oversold

        return FilterResult(
            enabled=True,
            result=result,
            value=k_value,
            threshold=threshold,
            reason=reason,
            details={'k_value': k_value, 'd_value': d_value}
        )

    def calculate_cvd_filter(self, bars: List[Bar], idx: int, direction: str) -> FilterResult:
        """Calculate CVD filter"""
        config = self.config['filters']

        if not config.get('enable_cvd_filter', True):
            return FilterResult(
                enabled=False,
                result='DISABLED',
                value=0.0,
                threshold=0.0,
                reason='Filter disabled'
            )

        # Calculate CVD
        cvd_data = self.calculate_cvd(bars, idx)

        # Get threshold
        threshold = config.get('cvd_imbalance_threshold', 10.0)

        # Check alignment with direction
        alignment = False
        if direction == 'LONG' and cvd_data['trend'] == 'BULLISH':
            alignment = True
        elif direction == 'SHORT' and cvd_data['trend'] == 'BEARISH':
            alignment = True

        # Determine result
        if cvd_data['imbalance_pct'] < threshold:
            result = 'PASS'
            reason = f'CVD imbalance {cvd_data["imbalance_pct"]:.1f}% < {threshold}% (no strong imbalance)'
        elif not alignment:
            result = 'BLOCK'
            reason = f'CVD {cvd_data["trend"]} contradicts {direction} direction'
        else:
            result = 'PASS'
            reason = f'CVD {cvd_data["trend"]} aligns with {direction}'

        return FilterResult(
            enabled=True,
            result=result,
            value=cvd_data['imbalance_pct'],
            threshold=threshold,
            reason=reason,
            details=cvd_data
        )

    def calculate_volume_filter(self, bars: List[Bar], idx: int) -> FilterResult:
        """Calculate volume confirmation filter"""
        config = self.config['filters']

        if not config.get('enable_volume_filter', True):
            return FilterResult(
                enabled=False,
                result='DISABLED',
                value=0.0,
                threshold=0.0,
                reason='Filter disabled'
            )

        # Calculate volume ratio
        volume_ratio = self.calculate_volume_ratio(bars, idx)

        # Get threshold
        threshold = config.get('volume_threshold', 1.0)

        # Determine result
        if volume_ratio >= threshold:
            result = 'PASS'
            reason = f'Volume {volume_ratio:.2f}x >= {threshold}x threshold'
        else:
            result = 'BLOCK'
            reason = f'Volume {volume_ratio:.2f}x < {threshold}x threshold'

        return FilterResult(
            enabled=True,
            result=result,
            value=volume_ratio,
            threshold=threshold,
            reason=reason,
            details={'current_volume': bars[idx].volume if idx < len(bars) else 0}
        )

    def calculate_index_filter(self, symbol: str, direction: str) -> FilterResult:
        """Calculate index ETF filter"""
        config = self.config['filters']

        # Index ETFs to check
        index_etfs = ['SPY', 'QQQ', 'DIA', 'IWM', 'TLT', 'GLD']
        is_index = symbol.upper() in index_etfs

        avoid_index_shorts = config.get('avoid_index_shorts', True)

        if is_index and direction == 'SHORT' and avoid_index_shorts:
            result = 'BLOCK'
            reason = f'Avoiding short on index ETF {symbol}'
        else:
            result = 'PASS'
            reason = 'Not an index ETF short' if not is_index else 'Index longs allowed'

        return FilterResult(
            enabled=avoid_index_shorts,
            result=result,
            value=1.0 if is_index else 0.0,
            threshold=0.0,
            reason=reason,
            details={'is_index': is_index}
        )

    # ==========================================================================
    # STATE MACHINE SIMULATION
    # ==========================================================================

    def simulate_state_machine(self, breakout: BreakoutData, bars: List[Bar]) -> Dict:
        """Simulate complete state machine progression"""
        state_data = {
            'states_visited': [],
            'state_transitions': [],
            'bars_in_each_state': defaultdict(int),
            'final_state': State.INIT,
            'total_bars_to_decision': 0,
            'decision_bar_idx': None,
            'confirmation_sequence': []
        }

        # Start from breakout bar
        current_state = State.INIT
        bar_idx = breakout.breakout_bar_idx

        # Track attempts
        attempt_number = 0
        last_attempt_bar = -100

        # Simulate for up to 30 bars after breakout
        max_bars = min(bar_idx + 30, len(bars))

        for idx in range(bar_idx, max_bars):
            bar = bars[idx]
            prev_state = current_state

            # Record bar in current state
            state_data['bars_in_each_state'][current_state.value] += 1

            # State machine logic
            if current_state == State.INIT:
                # Breakout detected, start monitoring
                current_state = State.MONITORING_BREAKOUT

            elif current_state == State.MONITORING_BREAKOUT:
                # Check if this is a new attempt
                if idx - last_attempt_bar >= 5:  # Cooldown period
                    attempt_number += 1
                    last_attempt_bar = idx

                # Determine entry path
                volume_ratio = self.calculate_volume_ratio(bars, idx)
                candle_size_pct = bar.body_pct
                atr = self.calculate_atr(bars[:idx+1])

                # Check momentum criteria
                momentum_vol_threshold = self.config['confirmation']['momentum_volume_threshold']
                momentum_candle_threshold = self.config['confirmation']['momentum_candle_size_pct']

                if volume_ratio >= momentum_vol_threshold and candle_size_pct >= momentum_candle_threshold:
                    current_state = State.MOMENTUM_BREAKOUT_DETECTED
                else:
                    current_state = State.WEAK_BREAKOUT_TRACKING

            elif current_state == State.MOMENTUM_BREAKOUT_DETECTED:
                # Strong breakout, check filters immediately
                current_state = State.WAITING_FOR_CANDLE_CLOSE

            elif current_state == State.WEAK_BREAKOUT_TRACKING:
                # Wait for pullback or sustained break
                if idx - bar_idx >= 2:  # After 2 bars
                    current_state = State.PULLBACK_TRACKING

            elif current_state == State.PULLBACK_TRACKING:
                # Check if pulled back to pivot zone
                pullback_zone = self.config['confirmation']['pullback_zone_pct'] / 100

                if breakout.direction == 'LONG':
                    if abs(bar.low - breakout.pivot_price) / breakout.pivot_price <= pullback_zone:
                        current_state = State.WAITING_FOR_PULLBACK
                else:  # SHORT
                    if abs(bar.high - breakout.pivot_price) / breakout.pivot_price <= pullback_zone:
                        current_state = State.WAITING_FOR_PULLBACK

            elif current_state == State.WAITING_FOR_PULLBACK:
                # Check for re-break with volume
                volume_ratio = self.calculate_volume_ratio(bars, idx)
                retest_vol = self.config['confirmation']['pullback_retest_volume']

                if volume_ratio >= retest_vol:
                    if breakout.direction == 'LONG' and bar.close > breakout.pivot_price:
                        current_state = State.WAITING_FOR_CANDLE_CLOSE
                    elif breakout.direction == 'SHORT' and bar.close < breakout.pivot_price:
                        current_state = State.WAITING_FOR_CANDLE_CLOSE

            elif current_state == State.WAITING_FOR_CANDLE_CLOSE:
                # Run all filters
                all_filters_pass = True  # Would run filters here

                if all_filters_pass and attempt_number <= self.config['risk']['max_attempts_per_pivot']:
                    current_state = State.ENTERING_POSITION
                    state_data['decision_bar_idx'] = idx
                else:
                    current_state = State.BLOCKED
                    state_data['decision_bar_idx'] = idx

            elif current_state in [State.ENTERING_POSITION, State.BLOCKED]:
                # Terminal states
                break

            # Record state transition
            if current_state != prev_state:
                transition = StateTransition(
                    bar_idx=idx,
                    time=bar.date,
                    from_state=prev_state,
                    to_state=current_state,
                    trigger=f'Bar {idx}',
                    details={'volume_ratio': self.calculate_volume_ratio(bars, idx)}
                )
                state_data['state_transitions'].append(transition)

            # Record confirmation sequence
            state_data['confirmation_sequence'].append({
                'bar_idx': idx,
                'time': str(bar.date),
                'state': current_state.value,
                'price': bar.close,
                'volume': bar.volume,
                'action': 'MONITORING'
            })

            # Record unique states visited
            if current_state.value not in state_data['states_visited']:
                state_data['states_visited'].append(current_state.value)

        state_data['final_state'] = current_state.value
        state_data['total_bars_to_decision'] = len(state_data['confirmation_sequence'])

        return state_data

    # ==========================================================================
    # ENTRY PATH DETERMINATION
    # ==========================================================================

    def determine_entry_path(self, breakout: BreakoutData, bars: List[Bar]) -> Dict:
        """Determine which entry path was taken"""
        idx = breakout.breakout_bar_idx
        bar = bars[idx] if idx < len(bars) else None

        if not bar:
            return {
                'path': EntryPath.NONE.value,
                'volume_ratio': 0.0,
                'candle_size_pct': 0.0,
                'atr_ratio': 0.0,
                'details': {}
            }

        # Calculate metrics
        volume_ratio = self.calculate_volume_ratio(bars, idx)
        candle_size_pct = bar.body_pct
        atr = self.calculate_atr(bars[:idx+1])
        atr_ratio = bar.range / atr if atr > 0 else 0

        # Get thresholds
        momentum_vol = self.config['confirmation']['momentum_volume_threshold']
        momentum_candle = self.config['confirmation']['momentum_candle_size_pct']
        momentum_atr = self.config['confirmation']['momentum_atr_multiplier']

        # Determine path
        if volume_ratio >= momentum_vol and (candle_size_pct >= momentum_candle or atr_ratio >= momentum_atr):
            path = EntryPath.MOMENTUM_BREAKOUT
        elif volume_ratio < 1.0:
            path = EntryPath.PULLBACK_RETEST
        else:
            path = EntryPath.SUSTAINED_BREAK

        return {
            'path': path.value,
            'volume_ratio': volume_ratio,
            'candle_size_pct': candle_size_pct,
            'atr_ratio': atr_ratio,
            'details': {
                'momentum_criteria_met': path == EntryPath.MOMENTUM_BREAKOUT,
                'thresholds': {
                    'volume': momentum_vol,
                    'candle': momentum_candle,
                    'atr': momentum_atr
                }
            }
        }

    # ==========================================================================
    # COMPLETE ANALYSIS
    # ==========================================================================

    def analyze_breakout(self, breakout: BreakoutData, stock_data: Dict, bars: List[Bar]) -> Dict:
        """Complete analysis of a single breakout"""

        print(f"    Analyzing {breakout.direction} breakout at {breakout.breakout_time}")

        # Initialize complete analysis structure
        analysis = {
            'id': f"{breakout.symbol}_{breakout.direction}_{breakout.breakout_time}",
            'symbol': breakout.symbol,
            'direction': breakout.direction,
            'date': self.date,

            # Breakout details
            'breakout': {
                'pivot_price': breakout.pivot_price,
                'breakout_time': str(breakout.breakout_time),
                'breakout_price': breakout.breakout_price,
                'breakout_bar_idx': breakout.breakout_bar_idx,
                'breakout_strength_pct': ((breakout.breakout_price - breakout.pivot_price) / breakout.pivot_price) * 100,
                'bars_since_open': breakout.bars_since_open
            },

            # Gap analysis
            'gap': self.analyze_gap(breakout),

            # Timing
            'timing': self.validate_timing(breakout),

            # State machine
            'state_machine': self.simulate_state_machine(breakout, bars),

            # Entry path
            'entry_path': self.determine_entry_path(breakout, bars),

            # Market context
            'market': self.get_market_context_at_time(breakout.breakout_bar_idx),

            # Scanner context
            'scanner': {
                'score': stock_data.get('score', 0),
                'setup_type': stock_data.get('setup', 'UNKNOWN'),
                'risk_reward': stock_data.get('risk_reward', 0),
                'atr_pct': stock_data.get('atr_pct', 0)
            }
        }

        # Calculate all filters
        idx = breakout.breakout_bar_idx

        analysis['filters'] = {
            'choppy': self.calculate_choppy_filter(bars, idx),
            'room_to_run': self.calculate_room_to_run_filter(breakout, breakout.breakout_price),
            'stochastic': self.calculate_stochastic_filter(bars, idx, breakout.direction),
            'cvd': self.calculate_cvd_filter(bars, idx, breakout.direction),
            'volume': self.calculate_volume_filter(bars, idx),
            'index': self.calculate_index_filter(breakout.symbol, breakout.direction)
        }

        # Strategy decision
        analysis['strategy_decision'] = self.make_strategy_decision(analysis)

        # Calculate outcome
        analysis['outcome'] = self.calculate_outcome(breakout, bars)

        # Classify decision accuracy
        analysis['accuracy'] = self.classify_decision_accuracy(
            analysis['strategy_decision'],
            analysis['outcome']
        )

        return analysis

    def make_strategy_decision(self, analysis: Dict) -> Dict:
        """Make final strategy decision based on all factors"""
        decision_data = {
            'final_decision': Decision.BLOCK.value,
            'confidence_score': 0.0,
            'primary_reason': '',
            'filters_passed': [],
            'filters_failed': [],
            'blocking_filters': []
        }

        # Check gap filter first
        if analysis['gap']['gap_invalidates_setup']:
            decision_data['final_decision'] = Decision.BLOCK.value
            decision_data['primary_reason'] = 'Gap invalidated setup'
            decision_data['blocking_filters'].append('gap_filter')
            return decision_data

        # Check timing
        if not analysis['timing']['in_entry_window']:
            decision_data['final_decision'] = Decision.BLOCK.value
            if analysis['timing']['too_early']:
                decision_data['primary_reason'] = 'Too early (before entry window)'
            else:
                decision_data['primary_reason'] = 'Too late (after entry window)'
            decision_data['blocking_filters'].append('timing_filter')
            return decision_data

        # Check all filters
        for filter_name, filter_result in analysis['filters'].items():
            if isinstance(filter_result, FilterResult):
                if filter_result.enabled:
                    if filter_result.result == 'PASS':
                        decision_data['filters_passed'].append(filter_name)
                    else:
                        decision_data['filters_failed'].append(filter_name)
                        decision_data['blocking_filters'].append(filter_name)

        # Make decision
        if not decision_data['blocking_filters']:
            decision_data['final_decision'] = Decision.ENTER.value
            decision_data['primary_reason'] = 'All filters passed'
            decision_data['confidence_score'] = 80.0  # Base confidence

            # Adjust confidence based on quality
            if analysis['entry_path']['path'] == EntryPath.MOMENTUM_BREAKOUT.value:
                decision_data['confidence_score'] += 10
            if analysis['scanner']['score'] > 70:
                decision_data['confidence_score'] += 5
            if analysis['market']['spy_trend'] == 'UP' and analysis['direction'] == 'LONG':
                decision_data['confidence_score'] += 5

        else:
            decision_data['final_decision'] = Decision.BLOCK.value
            decision_data['primary_reason'] = f"Blocked by {decision_data['blocking_filters'][0]}"
            decision_data['confidence_score'] = 20.0

        return decision_data

    def calculate_outcome(self, breakout: BreakoutData, bars: List[Bar]) -> Dict:
        """Calculate actual outcome of breakout"""
        outcome_data = {
            'result': Outcome.FALSE_BREAKOUT.value,
            'target1_hit': False,
            'target2_hit': False,
            'target3_hit': False,
            'max_favorable_excursion': 0.0,
            'max_adverse_excursion': 0.0,
            'bars_to_target': None,
            'bars_to_stop': None,
            'exit_reason': 'UNKNOWN',
            'profit_loss_pct': 0.0
        }

        # Track from breakout bar forward
        start_idx = breakout.breakout_bar_idx
        entry_price = breakout.breakout_price

        if breakout.direction == 'LONG':
            max_price = entry_price
            min_price = entry_price

            for i, bar in enumerate(bars[start_idx:], start=start_idx):
                # Update extremes
                max_price = max(max_price, bar.high)
                min_price = min(min_price, bar.low)

                # Check target hits
                if breakout.target1 and not outcome_data['target1_hit']:
                    if bar.high >= breakout.target1:
                        outcome_data['target1_hit'] = True
                        outcome_data['bars_to_target'] = i - start_idx
                        outcome_data['result'] = Outcome.WINNER.value

                if breakout.target2 and not outcome_data['target2_hit']:
                    if bar.high >= breakout.target2:
                        outcome_data['target2_hit'] = True

                if breakout.target3 and not outcome_data['target3_hit']:
                    if bar.high >= breakout.target3:
                        outcome_data['target3_hit'] = True

            outcome_data['max_favorable_excursion'] = ((max_price - entry_price) / entry_price) * 100
            outcome_data['max_adverse_excursion'] = ((entry_price - min_price) / entry_price) * 100

        else:  # SHORT
            max_price = entry_price
            min_price = entry_price

            for i, bar in enumerate(bars[start_idx:], start=start_idx):
                # Update extremes
                max_price = max(max_price, bar.high)
                min_price = min(min_price, bar.low)

                # Check target hits
                if breakout.target1 and not outcome_data['target1_hit']:
                    if bar.low <= breakout.target1:
                        outcome_data['target1_hit'] = True
                        outcome_data['bars_to_target'] = i - start_idx
                        outcome_data['result'] = Outcome.WINNER.value

                if breakout.target2 and not outcome_data['target2_hit']:
                    if bar.low <= breakout.target2:
                        outcome_data['target2_hit'] = True

            outcome_data['max_favorable_excursion'] = ((entry_price - min_price) / entry_price) * 100
            outcome_data['max_adverse_excursion'] = ((max_price - entry_price) / entry_price) * 100

        # Calculate profit/loss
        if outcome_data['target1_hit']:
            outcome_data['profit_loss_pct'] = outcome_data['max_favorable_excursion']
            outcome_data['exit_reason'] = 'TARGET'
        elif outcome_data['max_adverse_excursion'] > 1.0:
            outcome_data['profit_loss_pct'] = -outcome_data['max_adverse_excursion']
            outcome_data['exit_reason'] = 'STOP'
            outcome_data['result'] = Outcome.STOPPED_OUT.value
        else:
            outcome_data['profit_loss_pct'] = 0.0
            outcome_data['exit_reason'] = 'FLAT'

        return outcome_data

    def classify_decision_accuracy(self, decision: Dict, outcome: Dict) -> Dict:
        """Classify decision accuracy"""
        classification = {
            'classification': '',
            'correct_decision': False,
            'opportunity_cost': 0.0
        }

        if decision['final_decision'] == Decision.ENTER.value:
            if outcome['result'] == Outcome.WINNER.value:
                classification['classification'] = 'CORRECT_ENTRY'
                classification['correct_decision'] = True
            else:
                classification['classification'] = 'BAD_ENTRY'
                classification['opportunity_cost'] = abs(outcome['profit_loss_pct']) * 100  # Simplified
        else:  # BLOCK
            if outcome['result'] == Outcome.WINNER.value:
                classification['classification'] = 'MISSED_WINNER'
                classification['opportunity_cost'] = outcome['profit_loss_pct'] * 100
            else:
                classification['classification'] = 'CORRECT_BLOCK'
                classification['correct_decision'] = True
                classification['opportunity_cost'] = abs(outcome['profit_loss_pct']) * 100  # Saved

        return classification

    # ==========================================================================
    # MAIN ANALYSIS FLOW
    # ==========================================================================

    def analyze_stock(self, symbol: str, stock_data: Dict):
        """Analyze all breakouts for a stock"""
        print(f"\n📊 Analyzing {symbol}...")

        # Get bars
        bars = self.get_bars(symbol, '1min')
        if not bars:
            print(f"  ⚠️  No data available for {symbol}")
            return

        # Detect breakouts
        breakouts = self.detect_breakouts(symbol, stock_data, bars)

        if not breakouts:
            print(f"  ⚪ No breakouts detected")
            return

        # Analyze each breakout
        for breakout in breakouts:
            analysis = self.analyze_breakout(breakout, stock_data, bars)
            self.results.append(analysis)

            # Print summary
            decision = analysis['strategy_decision']['final_decision']
            outcome = analysis['outcome']['result']
            accuracy = analysis['accuracy']['classification']

            emoji = "✅" if analysis['accuracy']['correct_decision'] else "❌"

            print(f"  {emoji} {breakout.direction}: {decision} vs {outcome} = {accuracy}")

    def generate_csv_row(self, analysis: Dict) -> OrderedDict:
        """Generate CSV row from analysis"""
        row = OrderedDict()

        # Identification
        row['symbol'] = analysis['symbol']
        row['direction'] = analysis['direction']
        row['date'] = analysis['date']
        row['breakout_time'] = analysis['breakout']['breakout_time']

        # Breakout details
        row['pivot_price'] = analysis['breakout']['pivot_price']
        row['breakout_price'] = analysis['breakout']['breakout_price']
        row['breakout_strength_pct'] = analysis['breakout']['breakout_strength_pct']

        # Gap analysis
        row['has_gap'] = analysis['gap']['has_gap']
        row['gap_type'] = analysis['gap']['gap_type']
        row['gap_size_pct'] = analysis['gap']['gap_size_pct']
        row['gap_through_pivot'] = analysis['gap']['gap_through_pivot']
        row['room_after_gap'] = analysis['gap']['room_after_gap']

        # Timing
        row['in_entry_window'] = analysis['timing']['in_entry_window']
        row['minutes_from_open'] = analysis['timing']['minutes_from_open']
        row['time_zone'] = analysis['timing']['time_zone']

        # State machine
        row['states_visited'] = '|'.join(analysis['state_machine']['states_visited'])
        row['state_transitions'] = len(analysis['state_machine']['state_transitions'])
        row['final_state'] = analysis['state_machine']['final_state']
        row['bars_to_decision'] = analysis['state_machine']['total_bars_to_decision']

        # Entry path
        row['entry_path'] = analysis['entry_path']['path']
        row['path_volume_ratio'] = analysis['entry_path']['volume_ratio']
        row['path_candle_size'] = analysis['entry_path']['candle_size_pct']

        # Filters
        for filter_name, filter_result in analysis['filters'].items():
            if isinstance(filter_result, FilterResult):
                row[f'{filter_name}_enabled'] = filter_result.enabled
                row[f'{filter_name}_result'] = filter_result.result
                row[f'{filter_name}_value'] = filter_result.value
                row[f'{filter_name}_threshold'] = filter_result.threshold

        # Market context
        row['spy_trend'] = analysis['market']['spy_trend']
        row['spy_strength'] = analysis['market']['spy_strength']
        row['market_regime'] = analysis['market']['market_regime']

        # Scanner context
        row['scanner_score'] = analysis['scanner']['score']
        row['setup_type'] = analysis['scanner']['setup_type']
        row['risk_reward'] = analysis['scanner']['risk_reward']

        # Decision
        row['FINAL_DECISION'] = analysis['strategy_decision']['final_decision']
        row['confidence_score'] = analysis['strategy_decision']['confidence_score']
        row['primary_reason'] = analysis['strategy_decision']['primary_reason']
        row['filters_passed'] = '|'.join(analysis['strategy_decision']['filters_passed'])
        row['filters_failed'] = '|'.join(analysis['strategy_decision']['filters_failed'])
        row['blocking_filters'] = '|'.join(analysis['strategy_decision']['blocking_filters'])

        # Outcome
        row['actual_outcome'] = analysis['outcome']['result']
        row['target1_hit'] = analysis['outcome']['target1_hit']
        row['max_favorable_excursion'] = analysis['outcome']['max_favorable_excursion']
        row['max_adverse_excursion'] = analysis['outcome']['max_adverse_excursion']
        row['profit_loss_pct'] = analysis['outcome']['profit_loss_pct']

        # Classification
        row['decision_classification'] = analysis['accuracy']['classification']
        row['correct_decision'] = analysis['accuracy']['correct_decision']
        row['opportunity_cost'] = analysis['accuracy']['opportunity_cost']

        return row

    def save_to_csv(self, output_file: str):
        """Save results to comprehensive CSV"""
        if not self.results:
            print("⚠️  No results to save")
            return

        print(f"\n💾 Saving comprehensive results to {output_file}...")

        # Generate rows
        rows = [self.generate_csv_row(analysis) for analysis in self.results]

        # Write CSV
        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False)

        print(f"  ✅ Saved {len(rows)} breakout analyses ({len(df.columns)} columns)")

    def generate_report(self, report_file: str):
        """Generate comprehensive markdown report"""
        print(f"\n📝 Generating report to {report_file}...")

        with open(report_file, 'w') as f:
            f.write("# Comprehensive Pivot Behavior & Strategy Analysis Report\n\n")
            f.write(f"**Date**: {self.date}\n")
            f.write(f"**Total Breakouts Analyzed**: {len(self.results)}\n\n")

            # Calculate summary statistics
            if self.results:
                total = len(self.results)
                would_enter = sum(1 for r in self.results if r['strategy_decision']['final_decision'] == Decision.ENTER.value)
                would_block = total - would_enter

                correct_entries = sum(1 for r in self.results if r['accuracy']['classification'] == 'CORRECT_ENTRY')
                bad_entries = sum(1 for r in self.results if r['accuracy']['classification'] == 'BAD_ENTRY')
                correct_blocks = sum(1 for r in self.results if r['accuracy']['classification'] == 'CORRECT_BLOCK')
                missed_winners = sum(1 for r in self.results if r['accuracy']['classification'] == 'MISSED_WINNER')

                accuracy = (correct_entries + correct_blocks) / total * 100 if total > 0 else 0

                f.write("## Summary Statistics\n\n")
                f.write(f"- **Strategy Would Enter**: {would_enter}/{total} ({would_enter/total*100:.1f}%)\n")
                f.write(f"- **Strategy Would Block**: {would_block}/{total} ({would_block/total*100:.1f}%)\n\n")

                f.write("### Decision Accuracy\n\n")
                f.write(f"- ✅ **Correct Entries**: {correct_entries}\n")
                f.write(f"- ❌ **Bad Entries**: {bad_entries}\n")
                f.write(f"- ✅ **Correct Blocks**: {correct_blocks}\n")
                f.write(f"- ❌ **Missed Winners**: {missed_winners}\n")
                f.write(f"- **Overall Accuracy**: {accuracy:.1f}%\n\n")

                # Filter effectiveness
                f.write("## Filter Effectiveness\n\n")
                filter_blocks = defaultdict(int)
                for result in self.results:
                    for filter_name in result['strategy_decision']['blocking_filters']:
                        filter_blocks[filter_name] += 1

                f.write("| Filter | Blocks | Percentage |\n")
                f.write("|--------|--------|------------|\n")
                for filter_name, count in sorted(filter_blocks.items(), key=lambda x: x[1], reverse=True):
                    pct = count / total * 100 if total > 0 else 0
                    f.write(f"| {filter_name} | {count} | {pct:.1f}% |\n")
                f.write("\n")

                # Detailed breakout analysis
                f.write("## Detailed Breakout Analysis\n\n")
                for result in self.results:
                    symbol = result['symbol']
                    direction = result['direction']
                    decision = result['strategy_decision']['final_decision']
                    outcome = result['outcome']['result']
                    classification = result['accuracy']['classification']

                    emoji = "✅" if result['accuracy']['correct_decision'] else "❌"

                    f.write(f"### {emoji} {symbol} {direction}\n\n")
                    f.write(f"- **Decision**: {decision}\n")
                    f.write(f"- **Outcome**: {outcome}\n")
                    f.write(f"- **Classification**: {classification}\n")
                    f.write(f"- **Entry Path**: {result['entry_path']['path']}\n")
                    f.write(f"- **Blocking Filters**: {', '.join(result['strategy_decision']['blocking_filters']) if result['strategy_decision']['blocking_filters'] else 'None'}\n")
                    f.write(f"- **Max Favorable Excursion**: {result['outcome']['max_favorable_excursion']:.2f}%\n")
                    f.write(f"- **Max Adverse Excursion**: {result['outcome']['max_adverse_excursion']:.2f}%\n")
                    f.write("\n")

        print(f"  ✅ Report saved")

    def run(self, scanner_file: str, output_csv: str, report_file: Optional[str] = None):
        """Run complete analysis"""
        print("\n" + "=" * 80)
        print(f"COMPREHENSIVE PIVOT BEHAVIOR & STRATEGY ANALYSIS")
        print(f"Date: {self.date}")
        print("=" * 80)

        # Load scanner results
        print(f"\n📂 Loading scanner results from {scanner_file}...")
        try:
            with open(scanner_file, 'r') as f:
                scanner_data = json.load(f)
            print(f"  ✅ Loaded {len(scanner_data)} stocks")
        except Exception as e:
            print(f"  ❌ Error loading scanner file: {e}")
            return

        # Connect to IBKR
        self.connect_ib()

        # Load market context
        self.load_market_context()

        # Analyze each stock
        for stock_data in scanner_data:
            symbol = stock_data['symbol']
            self.analyze_stock(symbol, stock_data)

        # Disconnect
        self.disconnect_ib()

        # Save results
        self.save_to_csv(output_csv)

        # Generate report
        if report_file:
            self.generate_report(report_file)

        # Print summary
        self.print_summary()

        print(f"\n✅ Analysis complete!")

    def print_summary(self):
        """Print analysis summary to terminal"""
        if not self.results:
            print("\n⚠️  No results to summarize")
            return

        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)

        total = len(self.results)

        # Decision breakdown
        decisions = defaultdict(int)
        for r in self.results:
            decisions[r['strategy_decision']['final_decision']] += 1

        print(f"\n📊 Strategy Decisions:")
        for decision, count in decisions.items():
            print(f"  {decision}: {count} ({count/total*100:.1f}%)")

        # Accuracy breakdown
        classifications = defaultdict(int)
        for r in self.results:
            classifications[r['accuracy']['classification']] += 1

        print(f"\n🎯 Decision Accuracy:")
        for classification, count in classifications.items():
            emoji = "✅" if "CORRECT" in classification else "❌"
            print(f"  {emoji} {classification}: {count}")

        # Calculate overall accuracy
        correct = sum(1 for r in self.results if r['accuracy']['correct_decision'])
        accuracy = correct / total * 100 if total > 0 else 0
        print(f"\n  Overall Accuracy: {accuracy:.1f}%")

        print("\n" + "=" * 80)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive Pivot Behavior & Strategy Analysis'
    )
    parser.add_argument(
        '--scanner',
        required=True,
        help='Scanner results file (JSON)'
    )
    parser.add_argument(
        '--date',
        required=True,
        help='Date to analyze (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--config',
        help='Configuration file (trader_config.yaml)'
    )
    parser.add_argument(
        '--output',
        help='Output CSV file (default: comprehensive_pivot_analysis_YYYYMMDD.csv)'
    )
    parser.add_argument(
        '--report',
        help='Output report file (default: pivot_analysis_report_YYYYMMDD.md)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Save debug data'
    )

    args = parser.parse_args()

    # Default output files
    date_str = args.date.replace('-', '')
    if not args.output:
        args.output = f"comprehensive_pivot_analysis_{date_str}.csv"
    if not args.report:
        args.report = f"pivot_analysis_report_{date_str}.md"

    # Create analyzer
    analyzer = ComprehensivePivotAnalyzer(
        date=args.date,
        config_file=args.config
    )

    # Run analysis
    analyzer.run(args.scanner, args.output, args.report)


if __name__ == '__main__':
    main()