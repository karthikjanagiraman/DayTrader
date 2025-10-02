"""
Advanced Pattern Detection Module
Implements sophisticated multi-day pattern recognition for pre-market setups
Based on VCP, ATR contraction, volume patterns, and consolidation detection
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
from loguru import logger


class AdvancedPatternDetector:
    """Detects advanced trading patterns using multi-day analysis"""

    def __init__(self, lookback_days: int = 15):
        """
        Initialize pattern detector

        Args:
            lookback_days: Number of days to analyze for patterns (default 15)
        """
        self.lookback_days = lookback_days

    def detect_vcp_pattern(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect Volatility Contraction Pattern (VCP)
        Looks for progressively tighter price contractions

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with VCP analysis
        """
        if len(df) < self.lookback_days:
            return {'vcp_detected': False}

        recent_data = df.tail(self.lookback_days)

        # Calculate contractions (high-low ranges)
        contractions = []
        for i in range(len(recent_data)):
            day_range = (recent_data.iloc[i]['high'] - recent_data.iloc[i]['low']) / recent_data.iloc[i]['close'] * 100
            contractions.append(day_range)

        # Find contraction periods (local minima in range)
        contraction_points = []
        for i in range(1, len(contractions) - 1):
            if contractions[i] < contractions[i-1] and contractions[i] < contractions[i+1]:
                contraction_points.append((i, contractions[i]))

        # Check if contractions are getting progressively tighter
        vcp_detected = False
        contraction_ratio = 0

        if len(contraction_points) >= 2:
            # Each contraction should be 40-60% smaller than previous
            ratios = []
            for i in range(1, len(contraction_points)):
                ratio = contraction_points[i][1] / contraction_points[i-1][1]
                ratios.append(ratio)

            # VCP is valid if contractions are getting smaller
            if ratios and all(r < 0.8 for r in ratios):  # Each at least 20% smaller
                vcp_detected = True
                contraction_ratio = np.mean(ratios)

        return {
            'vcp_detected': vcp_detected,
            'num_contractions': len(contraction_points),
            'contraction_ratio': contraction_ratio,
            'latest_range_pct': contractions[-1] if contractions else 0,
            'pattern_description': f"VCP with {len(contraction_points)} contractions" if vcp_detected else ""
        }

    def detect_atr_contraction(self, df: pd.DataFrame, threshold_pct: float = 20) -> Dict[str, Any]:
        """
        Detect ATR (Average True Range) contraction

        Args:
            df: DataFrame with OHLCV data
            threshold_pct: Minimum % reduction in ATR to qualify

        Returns:
            Dictionary with ATR contraction analysis
        """
        if len(df) < self.lookback_days:
            return {'atr_contraction': False}

        # Calculate ATR manually
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean()

        if atr is None or len(atr) < self.lookback_days:
            return {'atr_contraction': False}

        recent_atr = atr.tail(self.lookback_days)

        # Compare current ATR to peak ATR in period
        current_atr = recent_atr.iloc[-1]
        peak_atr = recent_atr.max()
        atr_reduction_pct = ((peak_atr - current_atr) / peak_atr) * 100 if peak_atr > 0 else 0

        # Check if ATR is contracting
        atr_contraction = atr_reduction_pct >= threshold_pct

        # Check if ATR is in lower quartile (tight range)
        atr_percentile = (recent_atr < current_atr).sum() / len(recent_atr) * 100

        return {
            'atr_contraction': atr_contraction,
            'atr_reduction_pct': atr_reduction_pct,
            'current_atr': current_atr,
            'peak_atr': peak_atr,
            'atr_percentile': atr_percentile,
            'tight_range': atr_percentile < 25  # In bottom 25% of recent range
        }

    def detect_volume_pattern(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect volume patterns (declining volume during consolidation)

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with volume pattern analysis
        """
        if len(df) < self.lookback_days:
            return {'volume_declining': False}

        recent_data = df.tail(self.lookback_days)

        # Calculate average volumes
        first_half_avg = recent_data['volume'].iloc[:len(recent_data)//2].mean()
        second_half_avg = recent_data['volume'].iloc[len(recent_data)//2:].mean()

        # Volume should be declining during consolidation
        volume_reduction_pct = ((first_half_avg - second_half_avg) / first_half_avg) * 100 if first_half_avg > 0 else 0

        # Calculate relative volume trend
        volume_ma = recent_data['volume'].rolling(window=5).mean()
        volume_declining = volume_reduction_pct > 20  # At least 20% reduction

        # Check for volume dry-up (very low recent volume)
        avg_volume = df['volume'].tail(20).mean()
        recent_volume = recent_data['volume'].tail(3).mean()
        volume_dryup = (recent_volume / avg_volume < 0.7) if avg_volume > 0 else False

        return {
            'volume_declining': volume_declining,
            'volume_reduction_pct': volume_reduction_pct,
            'volume_dryup': volume_dryup,
            'recent_volume_ratio': recent_volume / avg_volume if avg_volume > 0 else 0,
            'pattern_description': "Volume dry-up detected" if volume_dryup else ""
        }

    def detect_support_levels(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect key support levels and moving average support

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with support level analysis
        """
        if len(df) < 20:
            return {'riding_support': False}

        # Calculate moving averages
        ma_10 = df['close'].rolling(window=10).mean()
        ma_20 = df['close'].rolling(window=20).mean()
        ma_50 = df['close'].rolling(window=50).mean() if len(df) >= 50 else None

        current_price = df['close'].iloc[-1]
        recent_low = df['low'].tail(10).min()

        # Check if price is "riding" moving averages
        riding_10ma = False
        riding_20ma = False

        if ma_10 is not None and len(ma_10) > 0:
            ma_10_current = ma_10.iloc[-1]
            # Price should be within 2% of MA
            riding_10ma = abs((current_price - ma_10_current) / ma_10_current) < 0.02 if ma_10_current > 0 else False

        if ma_20 is not None and len(ma_20) > 0:
            ma_20_current = ma_20.iloc[-1]
            riding_20ma = abs((current_price - ma_20_current) / ma_20_current) < 0.02 if ma_20_current > 0 else False

        # Check if MAs are acting as support (price bouncing off)
        support_bounces = 0
        if len(df) >= 10:
            for i in range(-10, -1):
                if ma_10 is not None and len(ma_10) > abs(i):
                    if df['low'].iloc[i] <= ma_10.iloc[i] <= df['high'].iloc[i]:
                        support_bounces += 1

        return {
            'riding_support': riding_10ma or riding_20ma,
            'riding_10ma': riding_10ma,
            'riding_20ma': riding_20ma,
            'support_bounces': support_bounces,
            'ma_10': ma_10.iloc[-1] if ma_10 is not None and len(ma_10) > 0 else None,
            'ma_20': ma_20.iloc[-1] if ma_20 is not None and len(ma_20) > 0 else None,
            'recent_low': recent_low
        }

    def detect_flag_pattern(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect flag and pennant patterns

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Dictionary with flag pattern analysis
        """
        if len(df) < 10:
            return {'flag_detected': False}

        # Look for strong move followed by consolidation
        recent_data = df.tail(10)

        # Calculate the "pole" (strong move)
        pole_start = recent_data.iloc[0]['close']
        pole_peak = recent_data['high'].max()
        pole_move_pct = ((pole_peak - pole_start) / pole_start) * 100 if pole_start > 0 else 0

        # Check for consolidation after move (flag)
        consolidation_data = recent_data.tail(5)
        consolidation_range = consolidation_data['high'].max() - consolidation_data['low'].min()
        avg_price = consolidation_data['close'].mean()
        consolidation_pct = (consolidation_range / avg_price) * 100 if avg_price > 0 else 0

        # Bull flag: Strong up move (>5%) followed by tight consolidation (<3%)
        bull_flag = pole_move_pct > 5 and consolidation_pct < 3

        # High tight flag: Extreme move (>20%) with very tight consolidation (<2%)
        high_tight_flag = pole_move_pct > 20 and consolidation_pct < 2

        return {
            'flag_detected': bull_flag or high_tight_flag,
            'bull_flag': bull_flag,
            'high_tight_flag': high_tight_flag,
            'pole_move_pct': pole_move_pct,
            'consolidation_pct': consolidation_pct,
            'pattern_description': "High tight flag" if high_tight_flag else "Bull flag" if bull_flag else ""
        }

    def detect_consolidation_breakout(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Detect if stock is breaking out of consolidation

        Args:
            df: DataFrame with OHLCV data
            current_price: Current pre-market price

        Returns:
            Dictionary with breakout analysis
        """
        if len(df) < 10:
            return {'breakout_detected': False}

        # Get consolidation range from recent data
        recent_data = df.tail(10)
        resistance = recent_data['high'].max()
        support = recent_data['low'].min()
        range_size = resistance - support
        range_midpoint = (resistance + support) / 2

        # Check if current price is breaking out
        breakout_up = current_price > resistance
        breakout_pct = ((current_price - resistance) / resistance) * 100 if resistance > 0 else 0

        # Check if consolidation was tight enough (< 5% range)
        range_pct = (range_size / range_midpoint) * 100 if range_midpoint > 0 else 0
        tight_consolidation = range_pct < 5

        # Valid breakout: Breaking resistance from tight consolidation
        valid_breakout = breakout_up and tight_consolidation and breakout_pct > 0.5

        return {
            'breakout_detected': valid_breakout,
            'resistance': resistance,
            'support': support,
            'range_pct': range_pct,
            'breakout_pct': breakout_pct,
            'tight_consolidation': tight_consolidation,
            'pattern_description': f"Breaking out {breakout_pct:.1f}% above resistance" if valid_breakout else ""
        }

    def calculate_setup_score(self, patterns: Dict[str, Any]) -> float:
        """
        Calculate overall setup score based on multiple patterns

        Args:
            patterns: Dictionary with all pattern detection results

        Returns:
            Setup score (0-100)
        """
        score = 0

        # VCP pattern (25 points)
        if patterns.get('vcp', {}).get('vcp_detected'):
            score += 25

        # ATR contraction (20 points)
        if patterns.get('atr', {}).get('atr_contraction'):
            score += 20
            if patterns.get('atr', {}).get('tight_range'):
                score += 5

        # Volume pattern (15 points)
        if patterns.get('volume', {}).get('volume_declining'):
            score += 10
        if patterns.get('volume', {}).get('volume_dryup'):
            score += 5

        # Support levels (15 points)
        if patterns.get('support', {}).get('riding_support'):
            score += 15

        # Flag patterns (15 points)
        if patterns.get('flag', {}).get('bull_flag'):
            score += 10
        if patterns.get('flag', {}).get('high_tight_flag'):
            score += 15

        # Consolidation breakout (10 points)
        if patterns.get('breakout', {}).get('breakout_detected'):
            score += 10

        return min(score, 100)

    def analyze_setup(self, df: pd.DataFrame, current_price: float) -> Dict[str, Any]:
        """
        Complete setup analysis using all pattern detection methods

        Args:
            df: DataFrame with OHLCV data
            current_price: Current pre-market price

        Returns:
            Complete setup analysis
        """
        patterns = {
            'vcp': self.detect_vcp_pattern(df),
            'atr': self.detect_atr_contraction(df),
            'volume': self.detect_volume_pattern(df),
            'support': self.detect_support_levels(df),
            'flag': self.detect_flag_pattern(df),
            'breakout': self.detect_consolidation_breakout(df, current_price)
        }

        # Calculate overall score
        setup_score = self.calculate_setup_score(patterns)

        # Generate setup description
        setup_descriptions = []
        for pattern_type, pattern_data in patterns.items():
            if pattern_data.get('pattern_description'):
                setup_descriptions.append(pattern_data['pattern_description'])

        return {
            'patterns': patterns,
            'setup_score': setup_score,
            'setup_quality': 'Excellent' if setup_score >= 70 else 'Good' if setup_score >= 50 else 'Fair' if setup_score >= 30 else 'Poor',
            'setup_description': '. '.join(setup_descriptions) if setup_descriptions else 'No significant patterns detected',
            'recommendation': 'Strong Buy' if setup_score >= 70 else 'Buy' if setup_score >= 50 else 'Watch' if setup_score >= 30 else 'Pass'
        }