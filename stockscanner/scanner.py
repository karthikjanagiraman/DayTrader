#!/usr/bin/env python3
"""
PS60 Trading Scanner - Unified Version
Finds high-probability breakout setups with detailed analysis
"""

from ib_insync import *
from datetime import datetime, timedelta
import pandas as pd
import time
import json
from pathlib import Path
from tabulate import tabulate
import argparse
import pytz

class PS60Scanner:
    """Main scanner for PS60 trading setups"""

    def __init__(self, port=7497, client_id=None, scan_timestamp=None):
        """
        Initialize scanner

        Args:
            port: IBKR port (7497 for paper, 7496 for live)
            client_id: IBKR client ID (auto-assigned if None)
            scan_timestamp: Datetime object for historical scans (uses 8 AM ET if only date provided)
        """
        self.ib = None
        self.results = []
        self.failed = []
        self.port = port
        self.client_id = client_id
        self.scan_timestamp = scan_timestamp
        self.scan_date = None  # Track the date being scanned (for backward compatibility)

    def connect(self, client_id=None):
        """Connect to IBKR TWS"""
        self.ib = IB()

        # Use provided client_id, or self.client_id, or default
        if client_id is None:
            client_id = self.client_id if self.client_id is not None else 1001

        try:
            self.ib.connect('127.0.0.1', self.port, clientId=client_id)
            print(f"✓ Connected to IBKR (Port: {self.port}, Client ID: {client_id})")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    def get_symbols(self, category='all'):
        """Get symbols to scan based on category"""

        core_symbols = {
            'indices': ['SPY', 'QQQ', 'IWM', 'DIA'],
            'mega_tech': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA'],
            'semis': ['AMD', 'INTC', 'MU', 'QCOM', 'AVGO', 'AMAT', 'LRCX', 'ARM'],
            'high_vol': ['COIN', 'PLTR', 'SOFI', 'HOOD', 'ROKU', 'SNAP', 'PINS', 'RBLX'],
            'meme': ['GME', 'AMC', 'BB', 'BBBY', 'CLOV'],
            'finance': ['JPM', 'BAC', 'GS', 'MS', 'C', 'WFC'],
            'energy': ['XOM', 'CVX', 'OXY'],
            'china': ['BABA', 'JD', 'BIDU', 'NIO', 'LI', 'XPEV'],
            'other': ['NFLX', 'DIS', 'UBER', 'LYFT', 'PYPL', 'BA', 'F', 'GM', 'RIVN', 'LCID']
        }

        if category == 'quick':
            # Top movers for quick scan
            return ['QQQ', 'TSLA', 'NVDA', 'AMD', 'PLTR', 'SOFI', 'HOOD', 'SMCI', 'PATH', 'SNOW', 'CELH', 'AMZN', 'ELF', 'QCOM', 'TEAM', 'TTD', 'CAVA', 'HIMS', 'JOBY', 'ACHR']
        elif category == 'all':
            # All symbols
            all_symbols = []
            for symbols in core_symbols.values():
                all_symbols.extend(symbols)
            return list(set(all_symbols))  # Remove duplicates
        else:
            return core_symbols.get(category, [])

    def _is_bounce_high(self, df_hourly, todays_high, today):
        """
        Detect if today's high is a bounce high (recovery after pullback)
        vs. a tested resistance level.

        Returns:
            dict: {
                'is_bounce': bool,
                'penalty': float (weight penalty to apply),
                'bounce_pct': float (how far bounced from recent lows)
            }
        """
        try:
            # Get last 3 days of data
            df_hourly = df_hourly.copy()
            df_hourly['date'] = pd.to_datetime(df_hourly['date']).dt.date
            dates = df_hourly['date'].unique()

            if len(dates) < 3:
                return {'is_bounce': False, 'penalty': 0.0, 'bounce_pct': 0.0}

            # Get bars from 1-3 days ago
            recent_dates = [d for d in dates if d < today][-3:]
            recent_bars = df_hourly[df_hourly['date'].isin(recent_dates)]

            if len(recent_bars) == 0:
                return {'is_bounce': False, 'penalty': 0.0, 'bounce_pct': 0.0}

            # Find lowest low in recent 1-3 days
            recent_low = recent_bars['low'].min()

            # Calculate bounce percentage
            bounce_pct = ((todays_high - recent_low) / recent_low) * 100

            # Classify as bounce if today's high is >2% above recent lows
            if bounce_pct >= 2.0:
                # Apply graduated penalty based on bounce size
                if bounce_pct >= 5.0:
                    penalty = 1.5  # Large bounce, strong penalty
                elif bounce_pct >= 3.5:
                    penalty = 1.0  # Medium bounce
                else:
                    penalty = 0.5  # Small bounce

                return {
                    'is_bounce': True,
                    'penalty': penalty,
                    'bounce_pct': bounce_pct,
                    'recent_low': recent_low
                }

            return {'is_bounce': False, 'penalty': 0.0, 'bounce_pct': bounce_pct}

        except Exception as e:
            return {'is_bounce': False, 'penalty': 0.0, 'bounce_pct': 0.0}

    def _check_higher_resistance_nearby(self, all_resistances, current_resistance, proximity_pct=1.5):
        """
        Check if there's a higher resistance level within proximity_pct (default 1.5%)
        If found and it has decent weight, use that instead.

        Args:
            all_resistances: list of dicts with 'level', 'weight', 'test_count'
            current_resistance: float - currently selected resistance
            proximity_pct: float - max distance to consider (default 1.5%)

        Returns:
            dict: {
                'use_higher': bool,
                'higher_level': float or None,
                'reason': str
            }
        """
        try:
            # Find all resistances higher than current
            higher_resistances = [
                r for r in all_resistances
                if r['level'] > current_resistance
            ]

            if not higher_resistances:
                return {'use_higher': False, 'higher_level': None, 'reason': 'No higher resistance found'}

            # Sort by level (ascending)
            higher_resistances = sorted(higher_resistances, key=lambda x: x['level'])

            # Check closest higher resistance
            closest_higher = higher_resistances[0]
            distance_pct = ((closest_higher['level'] - current_resistance) / current_resistance) * 100

            # If within proximity threshold
            if distance_pct <= proximity_pct:
                # Use higher level if it has decent weight (>= 2.0) OR multiple tests (>= 2)
                if closest_higher['weight'] >= 2.0 or closest_higher['test_count'] >= 2:
                    return {
                        'use_higher': True,
                        'higher_level': closest_higher['level'],
                        'reason': f'Higher resistance ${closest_higher["level"]:.2f} only {distance_pct:.1f}% away (weight={closest_higher["weight"]:.1f}, tests={closest_higher["test_count"]})',
                        'distance_pct': distance_pct
                    }

            return {
                'use_higher': False,
                'higher_level': None,
                'reason': f'Higher resistance too far ({distance_pct:.1f}%) or weak weight'
            }

        except Exception as e:
            return {'use_higher': False, 'higher_level': None, 'reason': f'Error: {str(e)}'}

    def _detect_recency_weighted_resistance(self, df_hourly, current_price):
        """
        Detect resistance using recency-weighted pattern detection
        Prioritizes what price is testing NOW (last 1-2 days)
        ENHANCED with bounce high detection and proximity check
        """
        try:
            # Step 1: Identify TODAY's high and recent pattern
            df_hourly['date'] = pd.to_datetime(df_hourly['date']).dt.date
            today = df_hourly['date'].iloc[-1]
            yesterday = df_hourly['date'].iloc[-2] if len(df_hourly) >= 2 else today

            today_bars = df_hourly[df_hourly['date'] == today]
            yesterday_bars = df_hourly[df_hourly['date'] == yesterday]
            recent_bars = pd.concat([yesterday_bars, today_bars])

            # Get TODAY's high (most immediate level)
            todays_high = today_bars['high'].max() if len(today_bars) > 0 else None
            if todays_high is None:
                return {'activated': False}

            # NEW: Check if today's high is a bounce high
            bounce_info = self._is_bounce_high(df_hourly, todays_high, today)

            # Step 2: Check last 7 days pattern - NEW RANGE or RECOVERY?
            last_7days = df_hourly.iloc[-28:] if len(df_hourly) >= 28 else df_hourly
            last_7days_dates = last_7days['date'].unique()

            # Get daily highs for last 7 days
            daily_highs_7d = []
            for date in last_7days_dates[-7:]:
                date_bars = last_7days[last_7days['date'] == date]
                if len(date_bars) > 0:
                    daily_highs_7d.append({
                        'date': date,
                        'high': date_bars['high'].max(),
                        'days_ago': len(last_7days_dates) - list(last_7days_dates).index(date) - 1
                    })

            # Step 3: Determine pattern type and resistance level
            pattern_type = "CURRENT_TEST"
            resistance_level = todays_high  # Default: use today's high

            if len(daily_highs_7d) >= 3:
                # Check if recent 3+ days forming NEW RANGE below old highs
                recent_3_highs = [h['high'] for h in daily_highs_7d if h['days_ago'] <= 2]
                old_highs = [h['high'] for h in daily_highs_7d if h['days_ago'] >= 3]

                if len(recent_3_highs) >= 3 and len(old_highs) > 0:
                    recent_max = max(recent_3_highs)
                    old_max = max(old_highs)

                    # New range = recent 3+ days stuck below old highs by >2%
                    if recent_max < old_max * 0.98:
                        pattern_type = "NEW_RANGE"
                        resistance_level = recent_max
                    else:
                        pattern_type = "RECOVERY"
                        # Use highest level being tested now
                        resistance_level = max(todays_high, old_max if old_max < todays_high * 1.05 else todays_high)

            # NEW: Collect ALL potential resistance levels (not just one)
            all_resistance_candidates = []

            # Candidate 1: TODAY's high
            all_resistance_candidates.append({
                'level': todays_high,
                'source': 'today_high',
                'days_ago': 0
            })

            # Candidate 2-N: Daily highs from last 7 days
            for dh in daily_highs_7d:
                if dh['high'] >= current_price:  # Only above current price
                    all_resistance_candidates.append({
                        'level': dh['high'],
                        'source': f'daily_high_{dh["days_ago"]}d_ago',
                        'days_ago': dh['days_ago']
                    })

            # Step 4: Find all tests of the resistance level (±1% tolerance)
            zone_tolerance = resistance_level * 0.01
            tests = []

            for idx, bar in df_hourly.iterrows():
                if abs(bar['high'] - resistance_level) <= zone_tolerance:
                    # Determine days ago
                    if bar['date'] in list(last_7days_dates):
                        days_ago = len(last_7days_dates) - list(last_7days_dates).index(bar['date']) - 1
                    else:
                        days_ago = len(df_hourly) - idx // 4

                    tests.append({
                        'high': bar['high'],
                        'close': bar['close'],
                        'days_ago': days_ago,
                        'date': bar['date']
                    })

            # Step 5: Apply recency weighting
            weighted_tests = []
            for test in tests:
                if test['days_ago'] == 0:
                    weight = 3.0  # TODAY
                elif test['days_ago'] == 1:
                    weight = 2.0  # Yesterday
                elif test['days_ago'] == 2:
                    weight = 1.5  # 2 days ago
                elif test['days_ago'] == 3:
                    weight = 1.0  # 3 days ago
                else:
                    weight = 0.5  # 4+ days ago

                weighted_tests.append({'test': test, 'weight': weight})

            total_weight = sum(t['weight'] for t in weighted_tests)

            # NEW: Apply bounce high penalty
            if bounce_info['is_bounce'] and resistance_level == todays_high:
                total_weight -= bounce_info['penalty']
                pattern_type += "_BOUNCE"

            # NEW: Calculate weights for ALL resistance candidates
            all_resistance_weights = []
            for candidate in all_resistance_candidates:
                # Find tests for this level
                level_zone = candidate['level'] * 0.01
                level_tests = [
                    t for t in weighted_tests
                    if abs(t['test']['high'] - candidate['level']) <= level_zone
                ]

                if level_tests:
                    level_weight = sum(t['weight'] for t in level_tests)
                    all_resistance_weights.append({
                        'level': candidate['level'],
                        'weight': level_weight,
                        'test_count': len(level_tests),
                        'days_ago': candidate['days_ago']
                    })

            # NEW: Check for higher resistance nearby (Enhancement #3)
            proximity_check = self._check_higher_resistance_nearby(
                all_resistance_weights,
                resistance_level,
                proximity_pct=1.5  # 1.5% threshold
            )

            if proximity_check['use_higher']:
                # Override with higher resistance
                resistance_level = proximity_check['higher_level']

                # Recalculate tests for this level
                zone_tolerance = resistance_level * 0.01
                tests = [
                    t['test'] for t in weighted_tests
                    if abs(t['test']['high'] - resistance_level) <= zone_tolerance
                ]
                total_weight = sum(
                    t['weight'] for t in weighted_tests
                    if abs(t['test']['high'] - resistance_level) <= zone_tolerance
                )
                pattern_type = "PROXIMITY_ADJUSTED"

            # Activate if weighted count >= 3.0
            if total_weight >= 3.0:
                num_tests = len(tests)

                reason_parts = [f'Tested {num_tests}x']
                if bounce_info['is_bounce'] and todays_high in [t['test']['high'] for t in weighted_tests[:5]]:
                    reason_parts.append(f'bounce from ${bounce_info["recent_low"]:.2f}')
                if proximity_check['use_higher']:
                    reason_parts.append(f'adjusted to higher level')

                reason = ' | '.join(reason_parts)

                return {
                    'activated': True,
                    'level': resistance_level,
                    'reason': reason,
                    'confidence': 'HIGH' if total_weight >= 5.0 else 'MEDIUM',
                    'touches': num_tests,
                    'test_count': num_tests,  # For Phase 1 output
                    'pattern_type': pattern_type,  # For Phase 2 output
                    'bounce_detected': bounce_info['is_bounce'],
                    'proximity_adjusted': proximity_check['use_higher']
                }

            return {'activated': False}

        except Exception as e:
            return {'activated': False}

    def _is_bounce_low(self, df_hourly, todays_low, today):
        """
        Detect if today's low is a selloff low (decline from recent highs)
        vs. a tested support level.

        Returns:
            dict: {
                'is_selloff': bool,
                'penalty': float (weight penalty to apply),
                'selloff_pct': float (how far declined from recent highs)
            }
        """
        try:
            # Get last 3 days of data
            df_hourly = df_hourly.copy()
            df_hourly['date'] = pd.to_datetime(df_hourly['date']).dt.date
            dates = df_hourly['date'].unique()

            if len(dates) < 3:
                return {'is_selloff': False, 'penalty': 0.0, 'selloff_pct': 0.0}

            # Get bars from 1-3 days ago
            recent_dates = [d for d in dates if d < today][-3:]
            recent_bars = df_hourly[df_hourly['date'].isin(recent_dates)]

            if len(recent_bars) == 0:
                return {'is_selloff': False, 'penalty': 0.0, 'selloff_pct': 0.0}

            # Find highest high in recent 1-3 days
            recent_high = recent_bars['high'].max()

            # Calculate selloff percentage
            selloff_pct = ((recent_high - todays_low) / recent_high) * 100

            # Classify as selloff if today's low is >2% below recent highs
            if selloff_pct >= 2.0:
                # Apply graduated penalty based on selloff size
                if selloff_pct >= 5.0:
                    penalty = 1.5  # Large selloff, strong penalty
                elif selloff_pct >= 3.5:
                    penalty = 1.0  # Medium selloff
                else:
                    penalty = 0.5  # Small selloff

                return {
                    'is_selloff': True,
                    'penalty': penalty,
                    'selloff_pct': selloff_pct,
                    'recent_high': recent_high
                }

            return {'is_selloff': False, 'penalty': 0.0, 'selloff_pct': selloff_pct}

        except Exception as e:
            return {'is_selloff': False, 'penalty': 0.0, 'selloff_pct': 0.0}

    def _check_lower_support_nearby(self, all_supports, current_support, proximity_pct=1.5):
        """
        Check if there's a lower support level within proximity_pct (default 1.5%)
        If found and it has decent weight, use that instead.

        Args:
            all_supports: list of dicts with 'level', 'weight', 'test_count'
            current_support: float - currently selected support
            proximity_pct: float - max distance to consider (default 1.5%)

        Returns:
            dict: {
                'use_lower': bool,
                'lower_level': float or None,
                'reason': str
            }
        """
        try:
            # Find all supports lower than current
            lower_supports = [
                s for s in all_supports
                if s['level'] < current_support
            ]

            if not lower_supports:
                return {'use_lower': False, 'lower_level': None, 'reason': 'No lower support found'}

            # Sort by level (descending - highest of the lower levels)
            lower_supports = sorted(lower_supports, key=lambda x: x['level'], reverse=True)

            # Check closest lower support
            closest_lower = lower_supports[0]
            distance_pct = ((current_support - closest_lower['level']) / current_support) * 100

            # If within proximity threshold
            if distance_pct <= proximity_pct:
                # Use lower level if it has decent weight (>= 2.0) OR multiple tests (>= 2)
                if closest_lower['weight'] >= 2.0 or closest_lower['test_count'] >= 2:
                    return {
                        'use_lower': True,
                        'lower_level': closest_lower['level'],
                        'reason': f'Lower support ${closest_lower["level"]:.2f} only {distance_pct:.1f}% away (weight={closest_lower["weight"]:.1f}, tests={closest_lower["test_count"]})',
                        'distance_pct': distance_pct
                    }

            return {
                'use_lower': False,
                'lower_level': None,
                'reason': f'Lower support too far ({distance_pct:.1f}%) or weak weight'
            }

        except Exception as e:
            return {'use_lower': False, 'lower_level': None, 'reason': f'Error: {str(e)}'}

    def _detect_recency_weighted_support(self, df_hourly, current_price):
        """
        Detect support using recency-weighted pattern detection
        Prioritizes what price is testing NOW (last 1-2 days)
        ENHANCED with bounce low detection and proximity check
        """
        try:
            # Step 1: Identify TODAY's low and recent pattern
            df_hourly['date'] = pd.to_datetime(df_hourly['date']).dt.date
            today = df_hourly['date'].iloc[-1]
            yesterday = df_hourly['date'].iloc[-2] if len(df_hourly) >= 2 else today

            today_bars = df_hourly[df_hourly['date'] == today]
            yesterday_bars = df_hourly[df_hourly['date'] == yesterday]
            recent_bars = pd.concat([yesterday_bars, today_bars])

            # Get TODAY's low (most immediate level)
            todays_low = today_bars['low'].min() if len(today_bars) > 0 else None
            if todays_low is None:
                return {'activated': False}

            # NEW: Check if today's low is a selloff low
            selloff_info = self._is_bounce_low(df_hourly, todays_low, today)

            # Step 2: Check last 7 days pattern - NEW RANGE or RECOVERY?
            last_7days = df_hourly.iloc[-28:] if len(df_hourly) >= 28 else df_hourly
            last_7days_dates = last_7days['date'].unique()

            # Get daily lows for last 7 days
            daily_lows_7d = []
            for date in last_7days_dates[-7:]:
                date_bars = last_7days[last_7days['date'] == date]
                if len(date_bars) > 0:
                    daily_lows_7d.append({
                        'date': date,
                        'low': date_bars['low'].min(),
                        'days_ago': len(last_7days_dates) - list(last_7days_dates).index(date) - 1
                    })

            # Step 3: Determine pattern type and support level
            pattern_type = "CURRENT_TEST"
            support_level = todays_low  # Default: use today's low

            if len(daily_lows_7d) >= 3:
                # Check if recent 3+ days forming NEW RANGE above old lows
                recent_3_lows = [h['low'] for h in daily_lows_7d if h['days_ago'] <= 2]
                old_lows = [h['low'] for h in daily_lows_7d if h['days_ago'] >= 3]

                if len(recent_3_lows) >= 3 and len(old_lows) > 0:
                    recent_min = min(recent_3_lows)
                    old_min = min(old_lows)

                    # New range = recent 3+ days held above old lows by >2%
                    if recent_min > old_min * 1.02:
                        pattern_type = "NEW_RANGE"
                        support_level = recent_min
                    else:
                        pattern_type = "RECOVERY"
                        # Use lowest level being tested now
                        support_level = min(todays_low, old_min if old_min > todays_low * 0.95 else todays_low)

            # NEW: Collect ALL potential support levels (not just one)
            all_support_candidates = []

            # Candidate 1: TODAY's low
            all_support_candidates.append({
                'level': todays_low,
                'source': 'today_low',
                'days_ago': 0
            })

            # Candidate 2-N: Daily lows from last 7 days
            for dl in daily_lows_7d:
                if dl['low'] <= current_price:  # Only below current price
                    all_support_candidates.append({
                        'level': dl['low'],
                        'source': f'daily_low_{dl["days_ago"]}d_ago',
                        'days_ago': dl['days_ago']
                    })

            # Step 4: Find all tests of the support level (±1% tolerance)
            zone_tolerance = support_level * 0.01
            tests = []

            for idx, bar in df_hourly.iterrows():
                if abs(bar['low'] - support_level) <= zone_tolerance:
                    # Determine days ago
                    if bar['date'] in list(last_7days_dates):  # FIXED: was last_5days_dates
                        days_ago = len(last_7days_dates) - list(last_7days_dates).index(bar['date']) - 1
                    else:
                        days_ago = len(df_hourly) - idx // 4

                    tests.append({
                        'low': bar['low'],
                        'close': bar['close'],
                        'days_ago': days_ago,
                        'date': bar['date']
                    })

            # Step 5: Apply recency weighting
            weighted_tests = []
            for test in tests:
                if test['days_ago'] == 0:
                    weight = 3.0  # TODAY
                elif test['days_ago'] == 1:
                    weight = 2.0  # Yesterday
                elif test['days_ago'] == 2:
                    weight = 1.5  # 2 days ago
                elif test['days_ago'] == 3:
                    weight = 1.0  # 3 days ago
                else:
                    weight = 0.5  # 4+ days ago

                weighted_tests.append({'test': test, 'weight': weight})

            total_weight = sum(t['weight'] for t in weighted_tests)

            # NEW: Apply selloff low penalty
            if selloff_info['is_selloff'] and support_level == todays_low:
                total_weight -= selloff_info['penalty']
                pattern_type += "_SELLOFF"

            # NEW: Calculate weights for ALL support candidates
            all_support_weights = []
            for candidate in all_support_candidates:
                # Find tests for this level
                level_zone = candidate['level'] * 0.01
                level_tests = [
                    t for t in weighted_tests
                    if abs(t['test']['low'] - candidate['level']) <= level_zone
                ]

                if level_tests:
                    level_weight = sum(t['weight'] for t in level_tests)
                    all_support_weights.append({
                        'level': candidate['level'],
                        'weight': level_weight,
                        'test_count': len(level_tests),
                        'days_ago': candidate['days_ago']
                    })

            # NEW: Check for lower support nearby (Enhancement #4)
            proximity_check = self._check_lower_support_nearby(
                all_support_weights,
                support_level,
                proximity_pct=1.5  # 1.5% threshold
            )

            if proximity_check['use_lower']:
                # Override with lower support
                support_level = proximity_check['lower_level']

                # Recalculate tests for this level
                zone_tolerance = support_level * 0.01
                tests = [
                    t['test'] for t in weighted_tests
                    if abs(t['test']['low'] - support_level) <= zone_tolerance
                ]
                total_weight = sum(
                    t['weight'] for t in weighted_tests
                    if abs(t['test']['low'] - support_level) <= zone_tolerance
                )
                pattern_type = "PROXIMITY_ADJUSTED"

            # Activate if weighted count >= 3.0
            if total_weight >= 3.0:
                num_tests = len(tests)

                reason_parts = [f'Tested {num_tests}x']
                if selloff_info['is_selloff'] and todays_low in [t['test']['low'] for t in weighted_tests[:5]]:
                    reason_parts.append(f'selloff from ${selloff_info["recent_high"]:.2f}')
                if proximity_check['use_lower']:
                    reason_parts.append(f'adjusted to lower level')

                reason = ' | '.join(reason_parts)

                return {
                    'activated': True,
                    'level': support_level,
                    'reason': reason,
                    'confidence': 'HIGH' if total_weight >= 5.0 else 'MEDIUM',
                    'touches': num_tests,
                    'test_count': num_tests,  # For Phase 1 output
                    'pattern_type': pattern_type,  # For Phase 2 output
                    'selloff_detected': selloff_info['is_selloff'],
                    'proximity_adjusted': proximity_check['use_lower']
                }

            return {'activated': False}

        except Exception as e:
            return {'activated': False}

    def analyze_breakout_levels(self, df, resistance, support, current_price):
        """Analyze why a level is significant and calculate targets"""
        reasons = []

        # Check if resistance is a spike or consolidation
        spike_high_5d = df['high'].iloc[-5:].max()
        close_high_5d = df['close'].iloc[-5:].max()
        if abs(spike_high_5d - resistance) < 1:  # If resistance is near spike high
            if (spike_high_5d - close_high_5d) / close_high_5d > 0.01:
                reasons.append(f"Consolidation zone (spike to ${spike_high_5d:.2f})")

        # Count resistance touches
        touches = 0
        for i in range(-20, 0):
            if abs(df.iloc[i]['high'] - resistance) / resistance < 0.015:
                touches += 1

        if touches >= 3:
            reasons.append(f"Tested {touches}x")
        elif touches >= 2:
            reasons.append("Double-tested")

        # Check for psychological levels
        if resistance % 10 == 0:
            reasons.append(f"Round ${resistance:.0f}")
        elif resistance % 5 == 0:
            reasons.append(f"${resistance:.0f} level")

        # Historical significance - check both highs and closes
        high_20d = df['high'].iloc[-20:].max()
        high_10d = df['high'].iloc[-10:].max()
        high_5d = df['high'].iloc[-5:].max()
        close_5d = df['close'].iloc[-5:].max()

        if abs(resistance - high_20d) < 1:
            reasons.append("20-day high")
        elif abs(resistance - high_10d) < 1:
            reasons.append("10-day high")
        elif abs(resistance - high_5d) < 1:
            reasons.append("5-day high")
        elif abs(resistance - close_5d) < 1:
            reasons.append("5-day closing high")

        # Pattern detection
        recent_range = df['high'].iloc[-5:].max() - df['low'].iloc[-5:].min()
        avg_range = (df['high'] - df['low']).iloc[-20:].mean()
        if recent_range < avg_range * 0.7:
            reasons.append("Tight consolidation")

        # Calculate targets using measured moves
        range_height = resistance - support

        # Upside targets
        target1 = resistance + (range_height * 0.5)   # Conservative
        target2 = resistance + (range_height * 1.0)   # Standard
        target3 = resistance + (range_height * 1.618) # Fibonacci

        # Downside targets
        downside1 = support - (range_height * 0.5)
        downside2 = support - (range_height * 1.0)

        # Risk/Reward calculation
        potential_gain = ((target2 - current_price) / current_price) * 100
        risk_to_support = ((current_price - support) / current_price) * 100
        risk_reward = potential_gain / risk_to_support if risk_to_support > 0 else 0

        return {
            'reasoning': ' | '.join(reasons) if reasons else 'Technical level',
            'target1': round(target1, 2),
            'target2': round(target2, 2),
            'target3': round(target3, 2),
            'downside1': round(downside1, 2),
            'downside2': round(downside2, 2),
            'potential_gain%': round(potential_gain, 2),
            'risk%': round(risk_to_support, 2),
            'risk_reward': round(risk_reward, 2)
        }

    def scan_symbol(self, symbol, historical_date=None):
        """
        Scan a single symbol

        Args:
            symbol: Stock symbol to scan
            historical_date: Optional date (datetime.date) to scan FOR that trading day
                           Uses data UP TO (but not including) this date (no look-ahead bias)
                           Example: --date 2025-10-10 uses data through Oct 9 close
        """
        try:
            # Create and qualify contract
            contract = Stock(symbol, 'SMART', 'USD')
            if not self.ib.qualifyContracts(contract):
                return None

            # Set end date for historical data
            if self.scan_timestamp:
                # CRITICAL FIX: For pre-market scans (8 AM), use PREVIOUS day's close
                # IBKR daily bars include the ENTIRE day even if you specify 8 AM
                # So to simulate 8 AM pre-market, we need data from the day BEFORE
                previous_day = self.scan_timestamp.date() - timedelta(days=1)
                end_datetime = previous_day.strftime('%Y%m%d 23:59:59')
            elif historical_date:
                # BACKWARD COMPATIBILITY: To scan FOR a trading day, use data from PREVIOUS day
                # Scanner runs pre-market, so can't see same-day data yet
                previous_day = historical_date - timedelta(days=1)
                end_datetime = previous_day.strftime('%Y%m%d 23:59:59')
            else:
                # Current/live data
                end_datetime = ''

            # Get historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='30 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1
            )

            if not bars or len(bars) < 20:
                return None

            # Convert to DataFrame
            df = util.df(bars)

            # Get current and previous day
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            current_price = today['close']

            # Calculate key metrics
            # 1. Price change
            change_pct = ((current_price - yesterday['close']) / yesterday['close']) * 100

            # 2. Volume analysis
            avg_volume = df['volume'].iloc[-21:-1].mean()
            rvol = today['volume'] / avg_volume if avg_volume > 0 else 0

            # 3. ATR (volatility)
            tr_list = []
            for i in range(1, len(df)):
                high_low = df.iloc[i]['high'] - df.iloc[i]['low']
                high_close = abs(df.iloc[i]['high'] - df.iloc[i-1]['close'])
                low_close = abs(df.iloc[i]['low'] - df.iloc[i-1]['close'])
                tr_list.append(max(high_low, high_close, low_close))
            atr = pd.Series(tr_list).iloc[-14:].mean() if len(tr_list) >= 14 else 0
            atr_pct = (atr / current_price) * 100

            # 4. Smart support/resistance calculation using recency-weighted hourly analysis

            # Moving averages
            sma_10 = df['close'].iloc[-10:].mean()
            sma_20 = df['close'].iloc[-20:].mean()

            # Try hourly recency-weighted analysis first (5-day lookback)
            resistance = None
            support = None
            resistance_reason = None
            support_reason = None
            resistance_result = None  # Initialize for later access
            support_result = None     # Initialize for later access
            df_hourly = None          # Initialize for later access

            try:
                # Fetch 7 days of hourly bars for precision analysis
                hourly_bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=end_datetime,
                    durationStr='7 D',
                    barSizeSetting='1 hour',
                    whatToShow='TRADES',
                    useRTH=True,  # Regular trading hours only
                    formatDate=1
                )

                if hourly_bars and len(hourly_bars) >= 5:
                    df_hourly = util.df(hourly_bars)

                    # RECENCY-WEIGHTED RESISTANCE DETECTION
                    resistance_result = self._detect_recency_weighted_resistance(df_hourly, current_price)
                    if resistance_result['activated']:
                        resistance = resistance_result['level']
                        resistance_reason = resistance_result['reason']

                    # RECENCY-WEIGHTED SUPPORT DETECTION
                    support_result = self._detect_recency_weighted_support(df_hourly, current_price)
                    if support_result['activated']:
                        support = support_result['level']
                        support_reason = support_result['reason']

            except Exception as e:
                print(f"Hourly analysis failed for {symbol}: {e}")

            # Fallback to daily-based calculation if hourly failed
            if resistance is None:
                resistance_5d_spike = df['high'].iloc[-5:].max()
                resistance_5d_close = df['close'].iloc[-5:].max()
                resistance_10d_close = df['close'].iloc[-10:].quantile(0.95)

                if (resistance_5d_spike - resistance_5d_close) / resistance_5d_close > 0.01:
                    resistance = max(resistance_5d_close, resistance_10d_close)
                else:
                    resistance = resistance_5d_spike
                resistance_reason = "Daily calculation (hourly unavailable)"

            if support is None:
                support_5d = df['low'].iloc[-5:].min()
                support_10d = df['low'].iloc[-10:].quantile(0.1)

                if current_price > sma_10 and abs(current_price - sma_10) < current_price * 0.1:
                    support = sma_10
                elif abs(current_price - support_5d) / current_price < 0.1:
                    support = support_5d
                else:
                    support = support_10d
                support_reason = "Daily calculation (hourly unavailable)"

            # Get detailed breakout analysis
            analysis = self.analyze_breakout_levels(df, resistance, support, current_price)

            # Calculate distances
            dist_to_resistance = ((resistance - current_price) / current_price) * 100
            dist_to_support = ((current_price - support) / current_price) * 100

            # ========== PHASE 1 & 2: CALCULATE ENHANCED FIELDS ==========

            # Phase 1: Intraday Price Context
            open_price = today['open']
            high_price = today['high']
            low_price = today['low']
            prev_close = yesterday['close']
            gap_pct = ((open_price - prev_close) / prev_close) * 100

            # Phase 1: Resistance/Support Test Metadata
            # Extract from recency-weighted detection results
            resistance_test_count = 0
            resistance_last_test = None
            support_test_count = 0
            support_last_test = None

            # Try to extract test counts from hourly analysis
            try:
                if resistance_result and 'test_count' in resistance_result:
                    resistance_test_count = resistance_result.get('test_count', 0)
                if support_result and 'test_count' in support_result:
                    support_test_count = support_result.get('test_count', 0)

                # Find last test timestamps from hourly bars
                if df_hourly is not None and len(df_hourly) > 0:
                    # Find most recent bar that tested resistance (within 1%)
                    resistance_zone_upper = resistance * 1.01
                    resistance_zone_lower = resistance * 0.99
                    recent_resistance_tests = df_hourly[
                        (df_hourly['high'] >= resistance_zone_lower) &
                        (df_hourly['high'] <= resistance_zone_upper)
                    ]
                    if len(recent_resistance_tests) > 0:
                        resistance_last_test = recent_resistance_tests.iloc[-1]['date']
                        if hasattr(resistance_last_test, 'isoformat'):
                            resistance_last_test = resistance_last_test.isoformat()

                    # Find most recent bar that tested support (within 1%)
                    support_zone_upper = support * 1.01
                    support_zone_lower = support * 0.99
                    recent_support_tests = df_hourly[
                        (df_hourly['low'] >= support_zone_lower) &
                        (df_hourly['low'] <= support_zone_upper)
                    ]
                    if len(recent_support_tests) > 0:
                        support_last_test = recent_support_tests.iloc[-1]['date']
                        if hasattr(support_last_test, 'isoformat'):
                            support_last_test = support_last_test.isoformat()
            except Exception as e:
                pass  # Use defaults if extraction fails

            # Phase 1: Volume Distribution
            # Calculate volume trend (last 5 days)
            volume_trend = "flat"
            try:
                volumes_last_5 = df['volume'].iloc[-5:].values
                if len(volumes_last_5) >= 3:
                    recent_avg = volumes_last_5[-2:].mean()
                    older_avg = volumes_last_5[:-2].mean()
                    if recent_avg > older_avg * 1.2:
                        volume_trend = "increasing"
                    elif recent_avg < older_avg * 0.8:
                        volume_trend = "decreasing"
            except:
                pass

            volume_vs_prev_day = today['volume'] / yesterday['volume'] if yesterday['volume'] > 0 else 0
            avg_volume_20d = avg_volume  # Already calculated earlier (line 746)

            # Phase 2: Moving Average Distances
            sma_50 = df['close'].iloc[-50:].mean() if len(df) >= 50 else None
            dist_to_sma10 = ((current_price - sma_10) / sma_10) * 100
            dist_to_sma20 = ((current_price - sma_20) / sma_20) * 100
            dist_to_sma50 = ((current_price - sma_50) / sma_50) * 100 if sma_50 else None

            # Phase 2: Pattern Classification
            pattern_type = None
            consolidation_days = None
            try:
                # Extract pattern type from resistance detection if available
                if resistance_result and 'pattern_type' in resistance_result:
                    pattern_type = resistance_result['pattern_type']

                # Detect consolidation (tight range for 3+ days)
                recent_5_days = df.iloc[-5:]
                ranges = (recent_5_days['high'] - recent_5_days['low']) / recent_5_days['low']
                if ranges.mean() < 0.03:  # Average range < 3%
                    consolidation_days = 5
                    if pattern_type is None:
                        pattern_type = "CONSOLIDATION"
            except:
                pass

            # Phase 2: Time-Based Metrics
            session_range_pct = ((high_price - low_price) / low_price) * 100 if low_price > 0 else 0

            # Hourly trend (last 3 hours vs previous 3 hours)
            hourly_trend = "neutral"
            try:
                if df_hourly is not None and len(df_hourly) >= 6:
                    recent_3h = df_hourly.iloc[-3:]['close'].mean()
                    prev_3h = df_hourly.iloc[-6:-3]['close'].mean()
                    if recent_3h > prev_3h * 1.01:
                        hourly_trend = "bullish"
                    elif recent_3h < prev_3h * 0.99:
                        hourly_trend = "bearish"
            except:
                pass

            # Daily trend (last 5 days vs previous 5 days)
            daily_trend = "neutral"
            try:
                if len(df) >= 10:
                    recent_5d = df.iloc[-5:]['close'].mean()
                    prev_5d = df.iloc[-10:-5]['close'].mean()
                    if recent_5d > prev_5d * 1.02:
                        daily_trend = "bullish"
                    elif recent_5d < prev_5d * 0.98:
                        daily_trend = "bearish"
            except:
                pass

            # ========== END ENHANCED FIELDS CALCULATION ==========

            # Score the setup
            score = 0
            setup_factors = []

            # Momentum scoring
            if abs(change_pct) >= 3:
                score += 30
                setup_factors.append(f"Strong {'up' if change_pct > 0 else 'down'} {change_pct:+.1f}%")
            elif abs(change_pct) >= 2:
                score += 20
                setup_factors.append(f"Moderate move {change_pct:+.1f}%")
            elif abs(change_pct) >= 1:
                score += 10

            # Volume scoring
            if rvol >= 2.0:
                score += 30
                setup_factors.append(f"High volume {rvol:.1f}x")
            elif rvol >= 1.5:
                score += 20
                setup_factors.append(f"Elevated volume {rvol:.1f}x")
            elif rvol >= 1.2:
                score += 10

            # Volatility scoring
            if atr_pct >= 4:
                score += 20
                setup_factors.append(f"High volatility {atr_pct:.1f}%")
            elif atr_pct >= 3:
                score += 15
                setup_factors.append(f"Good volatility {atr_pct:.1f}%")
            elif atr_pct >= 2:
                score += 10

            # Breakout proximity scoring
            if 0 < dist_to_resistance <= 2:
                score += 25
                setup_factors.append(f"Near breakout ({dist_to_resistance:.1f}%)")
            elif 2 < dist_to_resistance <= 3:
                score += 15
                setup_factors.append(f"Approaching breakout")

            # Already breaking out
            if current_price > resistance and rvol >= 1.2:
                score += 30
                setup_factors.append("BREAKING OUT")

            # Risk/Reward bonus
            if analysis['risk_reward'] >= 3:
                score += 20
                setup_factors.append(f"Excellent R/R {analysis['risk_reward']:.1f}:1")
            elif analysis['risk_reward'] >= 2:
                score += 10
                setup_factors.append(f"Good R/R {analysis['risk_reward']:.1f}:1")

            # Trend alignment
            if current_price > sma_10 > sma_20:
                score += 10
                setup_factors.append("Uptrend")

            return {
                # Core identification
                'symbol': symbol,

                # Current price data
                'close': round(current_price, 2),
                'open': round(open_price, 2),
                'high': round(high_price, 2),
                'low': round(low_price, 2),
                'prev_close': round(prev_close, 2),
                'change%': round(change_pct, 2),
                'gap%': round(gap_pct, 2),

                # Volume metrics
                'volume': int(today['volume']),
                'volume_M': round(today['volume'] / 1e6, 1),
                'rvol': round(rvol, 2),
                'volume_trend': volume_trend,
                'volume_vs_prev_day': round(volume_vs_prev_day, 2),
                'avg_volume_20d': int(avg_volume_20d),

                # Volatility
                'atr%': round(atr_pct, 2),
                'session_range%': round(session_range_pct, 2),

                # Key levels
                'resistance': round(resistance, 2),
                'support': round(support, 2),
                'resistance_test_count': resistance_test_count,
                'resistance_last_test': resistance_last_test,
                'support_test_count': support_test_count,
                'support_last_test': support_last_test,

                # Targets and risk
                'breakout_reason': analysis['reasoning'],
                'target1': analysis['target1'],
                'target2': analysis['target2'],
                'target3': analysis['target3'],
                'downside1': analysis['downside1'],
                'downside2': analysis['downside2'],
                'potential_gain%': analysis['potential_gain%'],
                'risk%': analysis['risk%'],
                'risk_reward': analysis['risk_reward'],

                # Moving averages and distances
                'sma10': round(sma_10, 2),
                'sma20': round(sma_20, 2),
                'sma50': round(sma_50, 2) if sma_50 else None,
                'dist_to_sma10': round(dist_to_sma10, 2),
                'dist_to_sma20': round(dist_to_sma20, 2),
                'dist_to_sma50': round(dist_to_sma50, 2) if dist_to_sma50 else None,

                # Pattern and trend
                'pattern_type': pattern_type,
                'consolidation_days': consolidation_days,
                'hourly_trend': hourly_trend,
                'daily_trend': daily_trend,

                # Scoring
                'score': score,
                'setup': ' | '.join(setup_factors) if setup_factors else 'No setup'
            }

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            return None

    def run_scan(self, symbols=None, category='all', historical_date=None):
        """
        Run the full scan

        Args:
            symbols: List of symbols to scan (optional)
            category: Category to scan if symbols not provided
            historical_date: Optional date (datetime.date) to scan as of that date
        """
        # Store the scan date for later use in save_results()
        # Use scan_timestamp date if available, otherwise use historical_date
        if self.scan_timestamp:
            self.scan_date = self.scan_timestamp.date()
        else:
            self.scan_date = historical_date

        print("\n" + "="*80)
        if self.scan_timestamp:
            print(f"PS60 BREAKOUT SCANNER - HISTORICAL ({self.scan_timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')})")
        elif historical_date:
            print(f"PS60 BREAKOUT SCANNER - HISTORICAL ({historical_date.strftime('%Y-%m-%d')})")
        else:
            print("PS60 BREAKOUT SCANNER - TOMORROW'S TRADING SETUPS")
        print("="*80)
        print(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*80)

        if not self.connect():
            return False

        try:
            # Get symbols
            if symbols:
                scan_symbols = symbols
            else:
                scan_symbols = self.get_symbols(category)

            print(f"\nScanning {len(scan_symbols)} symbols...")
            print("-"*80)

            # Scan each symbol
            for i, symbol in enumerate(scan_symbols):
                print(f"[{i+1}/{len(scan_symbols)}] {symbol}...", end=' ')

                result = self.scan_symbol(symbol, historical_date=historical_date)

                if result:
                    self.results.append(result)

                    # Status indicator
                    if result['score'] >= 60:
                        status = "🚀"
                    elif result['score'] >= 40:
                        status = "⭐"
                    else:
                        status = "✓"

                    print(f"{status} ${result['close']} ({result['change%']:+.1f}%) Score:{result['score']}")
                else:
                    self.failed.append(symbol)
                    print("✗ Failed")

                # Rate limiting
                time.sleep(0.2)

                # Progress update
                if (i + 1) % 10 == 0:
                    print(f"\nProgress: {i+1}/{len(scan_symbols)} completed\n")

            # Process and display results
            self.display_results()
            self.save_results()

            return True

        except Exception as e:
            print(f"\nScan error: {e}")
            return False

        finally:
            self.disconnect()

    def display_results(self):
        """Display scan results with analysis"""
        if not self.results:
            print("\nNo results to display")
            return

        # Sort by score and breakout proximity
        # Calculate dist_to_R% inline: (resistance - close) / close * 100
        self.results.sort(key=lambda x: (-x['score'], ((x['resistance'] - x['close']) / x['close'] * 100) if x['close'] > 0 else 999))

        print("\n" + "="*80)
        print("🎯 TOP BREAKOUT CANDIDATES (DETAILED ANALYSIS)")
        print("="*80)

        # Top candidates with full analysis
        top_candidates = [r for r in self.results if r['score'] >= 40][:5]

        for r in top_candidates:
            print(f"\n{'='*60}")
            print(f"📊 {r['symbol']} - Score: {r['score']}")
            print(f"{'='*60}")

            print(f"\n📈 CURRENT STATUS:")
            print(f"  Price: ${r['close']} ({r['change%']:+.2f}% today)")
            print(f"  Volume: {r['volume_M']:.1f}M (RVOL: {r['rvol']:.1f}x)")
            print(f"  Volatility: {r['atr%']:.1f}% ATR")

            print(f"\n🎯 KEY LEVELS:")
            # Calculate distances inline
            dist_to_R = ((r['resistance'] - r['close']) / r['close'] * 100)
            dist_to_S = ((r['close'] - r['support']) / r['close'] * 100)
            print(f"  Resistance: ${r['resistance']} ({dist_to_R:+.1f}% away)")
            print(f"  Support: ${r['support']} ({dist_to_S:.1f}% below)")
            print(f"  Why ${r['resistance']}? {r['breakout_reason']}")

            print(f"\n🚀 ROOM TO RUN (if breaks ${r['resistance']}):")
            print(f"  Target 1: ${r['target1']} (+{((r['target1']-r['close'])/r['close']*100):.1f}%)")
            print(f"  Target 2: ${r['target2']} (+{((r['target2']-r['close'])/r['close']*100):.1f}%)")
            print(f"  Target 3: ${r['target3']} (+{((r['target3']-r['close'])/r['close']*100):.1f}%)")

            print(f"\n⚖️ RISK/REWARD:")
            print(f"  Potential Gain: {r['potential_gain%']:.1f}%")
            print(f"  Risk to Support: {r['risk%']:.1f}%")
            print(f"  Risk/Reward Ratio: {r['risk_reward']:.1f}:1")

            print(f"\n💡 SETUP FACTORS:")
            print(f"  {r['setup']}")

        # Summary table
        print("\n" + "="*80)
        print("SUMMARY TABLE - ALL HIGH-SCORE SETUPS (Score ≥30)")
        print("="*80)

        high_score = [r for r in self.results if r['score'] >= 30]
        if high_score:
            df_display = pd.DataFrame(high_score)
            # Calculate dist_to_R% as a new column
            df_display['dist_to_R%'] = ((df_display['resistance'] - df_display['close']) / df_display['close'] * 100)
            df_display = df_display[
                ['symbol', 'close', 'change%', 'dist_to_R%', 'target2', 'risk_reward', 'score']
            ].head(20)
            print(tabulate(df_display, headers='keys', tablefmt='grid', showindex=False))

        # Market overview
        print("\n" + "="*80)
        print("MARKET OVERVIEW")
        print("="*80)

        df = pd.DataFrame(self.results)
        up = len(df[df['change%'] > 0])
        down = len(df[df['change%'] < 0])

        print(f"Market Breadth: {up} up / {down} down")
        print(f"High Scores (≥40): {len([r for r in self.results if r['score'] >= 40])} stocks")
        # Calculate dist_to_R% inline for breakout proximity check
        print(f"Near Breakout (<3% from R): {len([r for r in self.results if 0 < ((r['resistance'] - r['close']) / r['close'] * 100) <= 3])} stocks")
        print(f"High Volatility (≥3% ATR): {len([r for r in self.results if r['atr%'] >= 3])} stocks")
        print(f"Average Risk/Reward: {df['risk_reward'].mean():.2f}:1")

        if self.failed:
            print(f"\nFailed to scan: {', '.join(self.failed)}")

    def get_next_trading_date(self):
        """
        Determine the trading date for this scan based on current time.

        Logic:
        - Before 4:00 PM ET: Use today's date (scan for today's session)
        - After 4:00 PM ET: Use next weekday's date (scan for next session)
        - Weekends: Use next Monday's date
        """
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)

        # Market close time (4:00 PM ET)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

        # If it's a weekend, use next Monday
        if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
            days_until_monday = 7 - now_et.weekday()
            trading_date = now_et + timedelta(days=days_until_monday)
        # If before market close, use today
        elif now_et < market_close:
            trading_date = now_et
        # If after market close, use next trading day
        else:
            # If Friday after close, use Monday
            if now_et.weekday() == 4:  # Friday
                trading_date = now_et + timedelta(days=3)
            else:
                trading_date = now_et + timedelta(days=1)

        return trading_date.strftime('%Y%m%d')

    def save_results(self):
        """Save results to files"""
        if not self.results:
            return

        # Create output directory
        Path('output').mkdir(exist_ok=True)

        # Save to CSV
        df = pd.DataFrame(self.results)

        # Get the trading date this scan is for
        # If historical scan, use the historical date; otherwise use next trading date
        if self.scan_date:
            trading_date = self.scan_date.strftime('%Y%m%d')
        else:
            trading_date = self.get_next_trading_date()

        csv_filename = f'output/scanner_results_{trading_date}.csv'
        json_filename = f'output/scanner_results_{trading_date}.json'

        # Save with dated filenames
        df.to_csv(csv_filename, index=False)
        with open(json_filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        # Also save as latest (for backward compatibility)
        df.to_csv('output/scanner_results.csv', index=False)
        with open('output/scanner_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n✅ Results saved to:")
        print(f"   - {csv_filename}")
        print(f"   - {json_filename}")
        print(f"   - output/scanner_results.csv (latest)")
        print(f"   - output/scanner_results.json (latest)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='PS60 Breakout Scanner')
    parser.add_argument('--symbols', nargs='+', help='Specific symbols to scan')
    parser.add_argument('--category', default='all',
                       choices=['all', 'quick', 'indices', 'mega_tech', 'semis',
                               'high_vol', 'meme', 'finance', 'energy', 'china'],
                       help='Category of symbols to scan')
    parser.add_argument('--client-id', type=int, default=1001, help='TWS client ID')
    parser.add_argument('--date', type=str, help='Historical date to scan (format: YYYY-MM-DD)')

    args = parser.parse_args()

    # Parse historical date if provided
    historical_date = None
    if args.date:
        try:
            historical_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD format.")
            return 1

    scanner = PS60Scanner()
    success = scanner.run_scan(symbols=args.symbols, category=args.category, historical_date=historical_date)

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())