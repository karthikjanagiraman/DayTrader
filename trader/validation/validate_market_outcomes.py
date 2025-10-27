"""
Market Outcome Validator - Validates entry decisions against actual market outcomes

Author: Auto-generated
Date: October 25, 2025

PURPOSE:
--------
This validator analyzes what ACTUALLY happened in the market after each breakout
and validates whether our entry decisions (ENTERED or BLOCKED) were correct in hindsight.

KEY FEATURES (Oct 25, 2025 Final Spec):
---------------------------------------
1. Profit-taking checkpoints: Track price at 25%, 50%, 75%, 100% toward target1
2. 5-star rating system: ⭐ to ⭐⭐⭐⭐⭐ based on checkpoints reached
3. Full day analysis: Watch until market close (16:00 ET), not just 30 minutes
4. Missing bars handling: Download from IBKR + report CRITICAL ERROR
5. Overwrite behavior: Always overwrite previous reports (no duplicates)
6. Stop loss logic: Use backtester's actual stop calculation (not hardcoded)

DOCUMENTATION:
--------------
- DETAILED_REQUIREMENTS.md: Complete specifications with final decisions
- OPEN_QUESTIONS_EXPLAINED.md: Design decisions explained with examples
- IMPLEMENTATION_GUIDE.md: Step-by-step algorithm breakdown
- IMPLEMENTATION_STATUS.md: Progress tracking

USAGE:
------
python3 validate_market_outcomes.py \
    --scanner ../stockscanner/output/scanner_results_20251021.json \
    --entry-log ../backtest/results/backtest_entry_decisions_20251021.json \
    --date 2025-10-21 \
    --account-size 50000
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import argparse
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import IBKR connection for downloading missing bars
try:
    from ib_insync import IB, Stock, util
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    print("⚠️  WARNING: ib_insync not available - cannot download missing bars")

# Import PS60Strategy for accurate stop level calculation
# CRITICAL FIX (Oct 25, 2025): Use actual backtester stop logic, not simple pivot stops
try:
    from strategy.ps60_strategy import PS60Strategy
    import yaml
    STRATEGY_AVAILABLE = True
except ImportError as e:
    STRATEGY_AVAILABLE = False
    print(f"⚠️  WARNING: Cannot import PS60Strategy - will use simple pivot stops: {e}")

# ================================================================================
# LOGGING SETUP
# ================================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ================================================================================
# MARKET OUTCOME VALIDATOR CLASS
# ================================================================================
class MarketOutcomeValidator:
    """
    Validates entry decisions against actual market outcomes

    This class implements market outcome-based validation:
    - Identifies ALL breakouts from 1-min bar data
    - Classifies outcomes with 5-star rating system
    - Matches to entry decision log
    - Validates decisions (were they correct in hindsight?)
    - Generates comprehensive reports
    """

    def __init__(self, scanner_file: str, entry_log_file: str, date: str, account_size: float = 50000):
        """
        Initialize validator

        Args:
            scanner_file: Path to scanner results JSON
            entry_log_file: Path to entry decision log JSON
            date: Trading date (YYYY-MM-DD format)
            account_size: Account size for position sizing (default: 50000)
        """
        # ========================================
        # PARSE DATE
        # ========================================
        self.date = datetime.strptime(date, '%Y-%m-%d')
        self.date_str = date
        self.account_size = account_size

        # ========================================
        # LOAD SCANNER RESULTS
        # ========================================
        # Scanner provides resistance/support levels and targets
        logger.info(f"Loading scanner results from {scanner_file}...")
        with open(scanner_file) as f:
            self.scanner_data = json.load(f)
        logger.info(f"✓ Loaded {len(self.scanner_data)} stocks from scanner")

        # ========================================
        # LOAD ENTRY DECISION LOG
        # ========================================
        # Contains ALL entry attempts (ENTERED + BLOCKED) with filter data
        logger.info(f"Loading entry decision log from {entry_log_file}...")
        with open(entry_log_file) as f:
            self.entry_log = json.load(f)
        logger.info(f"✓ Loaded {self.entry_log['total_attempts']} entry attempts")
        logger.info(f"  Entered: {self.entry_log['entered']}")
        logger.info(f"  Blocked: {self.entry_log['blocked']}")

        # ========================================
        # INITIALIZE PS60 STRATEGY (FOR ACCURATE STOP CALCULATION)
        # ========================================
        # CRITICAL FIX (Oct 25, 2025): Load strategy to use actual stop logic
        self.strategy = None
        if STRATEGY_AVAILABLE:
            try:
                # Load trader config for strategy initialization
                config_path = Path(__file__).parent.parent / 'config' / 'trader_config.yaml'
                with open(config_path) as f:
                    config = yaml.safe_load(f)

                self.strategy = PS60Strategy(config)
                logger.info("✓ Loaded PS60Strategy for accurate stop calculation")
            except Exception as e:
                logger.warning(f"⚠️  Could not load PS60Strategy: {e}")
                logger.warning("⚠️  Will use simple pivot-level stops (less accurate)")

        # ========================================
        # INITIALIZE IBKR CONNECTION (FOR MISSING BARS)
        # ========================================
        self.ib = None
        if IBKR_AVAILABLE:
            try:
                self.ib = IB()
                self.ib.connect('127.0.0.1', 7497, clientId=9000)
                logger.info("✓ Connected to IBKR for emergency bar downloads")
            except Exception as e:
                logger.warning(f"⚠️  Could not connect to IBKR: {e}")

        # ========================================
        # INITIALIZE TRACKING VARIABLES
        # ========================================
        self.missing_bars_symbols = []  # Track missing bars (CRITICAL ERROR)
        self.all_breakouts = []  # All breakout events with outcomes

        # Validation statistics
        self.validation_results = {
            'good_entries': 0,      # Entered winners
            'good_blocks': 0,       # Blocked losers
            'bad_entries': 0,       # Entered losers
            'missed_winners': 0,    # Blocked winners
            'missed_detections': 0, # Breakouts not logged
            'early_exits': 0        # Stopped out but was winner
        }

        logger.info("")
        logger.info("="*80)
        logger.info(f"VALIDATION STARTED - {date}")
        logger.info("="*80)
        logger.info("")

    # ================================================================================
    # METHOD 1: LOAD SAVED BARS (WITH CRITICAL ERROR HANDLING)
    # ================================================================================
    def load_saved_bars(self, symbol: str) -> Optional[List[Dict]]:
        """
        Load cached 1-min bars from backtest data directory

        CRITICAL REQUIREMENT (Oct 25, 2025):
        - Bars should be cached by backtest at backtest/data/SYMBOL_YYYYMMDD_1min.json
        - If missing = CRITICAL ERROR (backtest didn't run properly)
        - Attempt emergency download from IBKR
        - Report missing bars in final summary

        Args:
            symbol: Stock ticker

        Returns:
            List of bar dicts or None if cannot load
        """
        # Construct file path
        bars_dir = Path(__file__).parent.parent / 'backtest' / 'data'
        bars_file = bars_dir / f"{symbol}_{self.date.strftime('%Y%m%d')}_1min.json"

        # Check if file exists
        if not bars_file.exists():
            # CRITICAL ERROR - bars should be cached
            logger.critical("")
            logger.critical("="*80)
            logger.critical(f"⚠️⚠️  CRITICAL ERROR: Bars missing for {symbol}")
            logger.critical("="*80)
            logger.critical(f"  Expected: {bars_file}")
            logger.critical(f"  Backtest should have cached all bars!")
            logger.critical("")

            self.missing_bars_symbols.append(symbol)

            # Attempt emergency download
            if self.ib and self.ib.isConnected():
                logger.info(f"  Attempting emergency download...")
                try:
                    bars = self.download_bars_from_ibkr(symbol)
                    if bars:
                        self.save_bars(bars, bars_file)
                        logger.warning(f"  ⚠️  Downloaded {len(bars)} bars")
                        logger.warning(f"  ⚠️  But backtest should have done this!")
                        return bars
                except Exception as e:
                    logger.error(f"  ✗ Download failed: {e}")
                    return None
            else:
                logger.error(f"  ✗ Cannot download (IBKR not connected)")
                return None

        # Load cached bars
        try:
            with open(bars_file) as f:
                bars = json.load(f)
            logger.debug(f"  ✓ Loaded {len(bars)} bars for {symbol}")
            return bars
        except Exception as e:
            logger.error(f"  ✗ Error loading {bars_file}: {e}")
            return None

    def download_bars_from_ibkr(self, symbol: str) -> Optional[List[Dict]]:
        """Emergency download of 1-min bars from IBKR"""
        if not self.ib or not self.ib.isConnected():
            return None

        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            end_datetime = self.date.replace(hour=16, minute=0)
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                return None

            bars_list = []
            for bar in bars:
                bars_list.append({
                    'date': bar.date.isoformat(),
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'average': bar.average,
                    'barCount': bar.barCount
                })

            return bars_list

        except Exception as e:
            logger.error(f"    IBKR download error: {e}")
            return None

    def save_bars(self, bars: List[Dict], file_path: Path):
        """Save downloaded bars to cache"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(bars, f, indent=2)
            logger.info(f"    ✓ Saved to {file_path}")
        except Exception as e:
            logger.error(f"    ✗ Failed to save: {e}")

    # ================================================================================
    # METHOD 2: IDENTIFY BREAKOUTS
    # ================================================================================
    def identify_breakouts(self, bars: List[Dict], resistance: float, support: float) -> List[Dict]:
        """
        Find ALL times price broke resistance or support

        Breakout Detection Rules:
        - LONG breakout: Current bar close > resistance AND previous bar close <= resistance
        - SHORT breakout: Current bar close < support AND previous bar close >= support
        - Re-breaks count as separate breakouts
        - Use bar CLOSE price (matches backtester logic)

        Args:
            bars: List of 1-min bar dicts
            resistance: Resistance level from scanner
            support: Support level from scanner

        Returns:
            List of breakout event dicts with:
            - timestamp: ISO datetime string
            - type: 'LONG' or 'SHORT'
            - price: Close price at breakout
            - bar_index: Index in bars list
            - broke_level: resistance or support level
        """
        breakouts = []

        # FIX #10 (Oct 25, 2025): Add deduplication to prevent flagging
        # multiple crosses of same level within 5 minutes as separate breakouts
        last_long_time = None
        last_short_time = None
        min_gap_seconds = 300  # 5 minutes

        # ========================================
        # LOOP THROUGH BARS (START AT INDEX 1)
        # ========================================
        # We need previous bar for comparison, so start at index 1
        for i in range(1, len(bars)):
            curr_bar = bars[i]
            prev_bar = bars[i-1]
            curr_time = self._parse_timestamp(curr_bar['date'])

            # ========================================
            # LONG BREAKOUT DETECTION
            # ========================================
            # Price crosses ABOVE resistance
            # Previous bar was at/below resistance, current bar is above
            if curr_bar['close'] > resistance and prev_bar['close'] <= resistance:
                # Only flag if at least 5 minutes since last LONG breakout
                if not last_long_time or (curr_time - last_long_time).total_seconds() >= min_gap_seconds:
                    breakouts.append({
                        'timestamp': curr_bar['date'],
                        'type': 'LONG',
                        'price': curr_bar['close'],
                        'bar_index': i,
                        'broke_level': resistance
                    })
                    last_long_time = curr_time

            # ========================================
            # SHORT BREAKOUT DETECTION
            # ========================================
            # Price crosses BELOW support
            # Previous bar was at/above support, current bar is below
            elif curr_bar['close'] < support and prev_bar['close'] >= support:
                # Only flag if at least 5 minutes since last SHORT breakout
                if not last_short_time or (curr_time - last_short_time).total_seconds() >= min_gap_seconds:
                    breakouts.append({
                        'timestamp': curr_bar['date'],
                        'type': 'SHORT',
                        'price': curr_bar['close'],
                        'bar_index': i,
                        'broke_level': support
                    })
                    last_short_time = curr_time

        return breakouts

    # ================================================================================
    # METHOD 3: CLASSIFY OUTCOME (WITH 5-STAR RATING SYSTEM)
    # ================================================================================
    def classify_outcome(self, bars: List[Dict], breakout: Dict, target1: float,
                        stop_level: float) -> Dict:
        """
        Analyze what happened after breakout with profit-taking checkpoints

        NEW FEATURES (Oct 25, 2025 Final Spec):
        ---------------------------------------
        - Profit-taking checkpoints: 25%, 50%, 75%, 100% toward target1
        - 5-star rating: ⭐ (1 star) to ⭐⭐⭐⭐⭐ (5 stars)
        - Full day analysis: Until market close (16:00 ET), not just 30 min
        - stopped_out_early flag: Hit stop BUT checkpoints were reached

        Classification Rules:
        - WINNER: Hit target1 (100% checkpoint) or any checkpoint
        - STOPPED_OUT: Hit stop loss
        - FALSE_BREAKOUT: Max gain < 0.1%
        - CHOPPY: Max gain < 0.3%
        - RUNNER: Made progress >= 0.5% but didn't hit checkpoints

        Star Rating:
        - 5 stars ⭐⭐⭐⭐⭐: Hit target1 (100%)
        - 4 stars ⭐⭐⭐⭐: Hit 75% checkpoint
        - 3 stars ⭐⭐⭐: Hit 50% checkpoint
        - 2 stars ⭐⭐: Hit 25% checkpoint
        - 1 star ⭐: Positive move but no checkpoints
        - 0 stars: No progress

        Args:
            bars: List of 1-min bars
            breakout: Breakout event dict
            target1: Target price from scanner
            stop_level: Stop loss price (from backtester logic)

        Returns:
            Dict with outcome classification, star rating, and comprehensive metrics
        """
        start_idx = breakout['bar_index']
        entry_price = breakout['price']
        side = breakout['type']

        # ========================================
        # CALCULATE PROFIT-TAKING CHECKPOINTS
        # ========================================
        # Distance from entry to target1
        # For LONG: target1 is above entry
        # For SHORT: target1 is below entry
        if side == 'LONG':
            distance = target1 - entry_price
        else:  # SHORT
            distance = entry_price - target1

        # FIX #3: Handle edge case where target1 == entry_price (zero distance)
        # This can happen if breakout occurs exactly at target1 or data quality issue
        if abs(distance) < 0.01:  # Less than 1 cent
            logger.warning(f"  Skipping checkpoint analysis - target1 too close to entry")
            logger.warning(f"    Entry: ${entry_price:.2f}, Target1: ${target1:.2f}, Distance: ${distance:.2f}")
            # Return simplified outcome without checkpoints
            return {
                'classification': 'INSUFFICIENT_DATA',
                'star_rating': 0,
                'max_gain_pct': 0.0,
                'max_loss_pct': 0.0,
                'checkpoints': {},
                'checkpoints_hit': {'25%': False, '50%': False, '75%': False, '100%': False},
                'checkpoint_times': {},
                'num_checkpoints_hit': 0,
                'hit_stop': False,
                'time_to_stop': None,
                'stopped_out_early': False,
                'analysis_duration_minutes': 0,
                'entry_price': entry_price,
                'stop_level': stop_level,
                'target1': target1
            }

        # Calculate checkpoint prices (every 25% of distance)
        if side == 'LONG':
            checkpoints = {
                '25%': entry_price + (distance * 0.25),
                '50%': entry_price + (distance * 0.50),
                '75%': entry_price + (distance * 0.75),
                '100%': target1  # 100% = target1
            }
        else:  # SHORT
            # For shorts, checkpoints are BELOW entry
            checkpoints = {
                '25%': entry_price - (distance * 0.25),
                '50%': entry_price - (distance * 0.50),
                '75%': entry_price - (distance * 0.75),
                '100%': target1  # 100% = target1
            }

        # Track which checkpoints were hit
        checkpoints_hit = {
            '25%': False,
            '50%': False,
            '75%': False,
            '100%': False
        }
        checkpoint_times = {}  # Track time to each checkpoint (in minutes)

        # ========================================
        # ANALYZE PRICE MOVEMENT UNTIL EOD
        # ========================================
        # FIX #6: Initialize to extreme values to handle all cases correctly
        max_gain = float('-inf')
        max_loss = float('inf')
        hit_stop = False
        time_to_stop = None

        # Analyze ALL bars until end of day (not just 30 minutes)
        # This implements Oct 25 spec: "Watch until 16:00 ET"
        analyze_bars = len(bars) - start_idx - 1

        # FIX #4: Handle edge case where breakout occurs on last bar
        # If breakout at last bar, no post-breakout data available
        if analyze_bars <= 0:
            logger.debug(f"  Breakout at last bar - no post-breakout data to analyze")
            return {
                'classification': 'INSUFFICIENT_DATA',
                'star_rating': 0,
                'max_gain_pct': 0.0,
                'max_loss_pct': 0.0,
                'checkpoints': checkpoints,
                'checkpoints_hit': {'25%': False, '50%': False, '75%': False, '100%': False},
                'checkpoint_times': {},
                'num_checkpoints_hit': 0,
                'hit_stop': False,
                'time_to_stop': None,
                'stopped_out_early': False,
                'analysis_duration_minutes': 0,
                'entry_price': entry_price,
                'stop_level': stop_level,
                'target1': target1
            }

        for i in range(1, analyze_bars + 1):
            bar = bars[start_idx + i]
            minutes_elapsed = i

            if side == 'LONG':
                # ========================================
                # LONG POSITION ANALYSIS
                # ========================================

                # Calculate gain/loss (percentage)
                gain = (bar['high'] - entry_price) / entry_price
                loss = (bar['low'] - entry_price) / entry_price

                max_gain = max(max_gain, gain)
                max_loss = min(max_loss, loss)

                # Check each checkpoint (in order from lowest to highest)
                # Track TIME when each checkpoint hit
                if not checkpoints_hit['25%'] and bar['high'] >= checkpoints['25%']:
                    checkpoints_hit['25%'] = True
                    checkpoint_times['25%'] = minutes_elapsed

                if not checkpoints_hit['50%'] and bar['high'] >= checkpoints['50%']:
                    checkpoints_hit['50%'] = True
                    checkpoint_times['50%'] = minutes_elapsed

                if not checkpoints_hit['75%'] and bar['high'] >= checkpoints['75%']:
                    checkpoints_hit['75%'] = True
                    checkpoint_times['75%'] = minutes_elapsed

                if not checkpoints_hit['100%'] and bar['high'] >= checkpoints['100%']:
                    checkpoints_hit['100%'] = True
                    checkpoint_times['100%'] = minutes_elapsed

                # Check if stop hit
                if bar['low'] <= stop_level and not hit_stop:
                    hit_stop = True
                    time_to_stop = minutes_elapsed

            else:  # SHORT
                # ========================================
                # SHORT POSITION ANALYSIS
                # ========================================

                # For shorts, gain is when price goes DOWN
                gain = (entry_price - bar['low']) / entry_price
                loss = (entry_price - bar['high']) / entry_price

                max_gain = max(max_gain, gain)
                max_loss = min(max_loss, loss)

                # Check each checkpoint (price going DOWN for shorts)
                if not checkpoints_hit['25%'] and bar['low'] <= checkpoints['25%']:
                    checkpoints_hit['25%'] = True
                    checkpoint_times['25%'] = minutes_elapsed

                if not checkpoints_hit['50%'] and bar['low'] <= checkpoints['50%']:
                    checkpoints_hit['50%'] = True
                    checkpoint_times['50%'] = minutes_elapsed

                if not checkpoints_hit['75%'] and bar['low'] <= checkpoints['75%']:
                    checkpoints_hit['75%'] = True
                    checkpoint_times['75%'] = minutes_elapsed

                if not checkpoints_hit['100%'] and bar['low'] <= checkpoints['100%']:
                    checkpoints_hit['100%'] = True
                    checkpoint_times['100%'] = minutes_elapsed

                # Check if stop hit (price goes UP for shorts)
                if bar['high'] >= stop_level and not hit_stop:
                    hit_stop = True
                    time_to_stop = minutes_elapsed

        # ========================================
        # CALCULATE STAR RATING
        # ========================================
        # FIX #6: Handle extreme value initialization (convert back to 0 if no movement)
        if max_gain == float('-inf'):
            max_gain = 0.0
        if max_loss == float('inf'):
            max_loss = 0.0

        # Count how many checkpoints were hit
        num_checkpoints = sum(checkpoints_hit.values())

        if num_checkpoints == 4:
            star_rating = 5  # ⭐⭐⭐⭐⭐ Hit target1 (100%)
        elif num_checkpoints == 3:
            star_rating = 4  # ⭐⭐⭐⭐ Hit 75%
        elif num_checkpoints == 2:
            star_rating = 3  # ⭐⭐⭐ Hit 50%
        elif num_checkpoints == 1:
            star_rating = 2  # ⭐⭐ Hit 25%
        elif max_gain > 0:
            star_rating = 1  # ⭐ Positive move but no checkpoints
        else:
            star_rating = 0  # No progress

        # ========================================
        # CLASSIFY OUTCOME
        # ========================================
        # Determine overall classification based on what happened

        if checkpoints_hit['100%']:
            # Hit target1 = definite WINNER
            classification = 'WINNER'

        elif hit_stop:
            # Hit stop loss
            classification = 'STOPPED_OUT'

        elif max_gain < 0.001:  # Less than 0.1% gain
            # Immediate reversal = false breakout
            classification = 'FALSE_BREAKOUT'

        elif max_gain < 0.003:  # Less than 0.3% gain
            # Minimal movement = choppy
            classification = 'CHOPPY'

        elif any(checkpoints_hit.values()):
            # Hit at least one checkpoint = partial winner
            classification = 'WINNER'

        elif max_gain >= 0.005:  # At least 0.5% gain
            # Made progress but didn't hit checkpoints = runner
            classification = 'RUNNER'

        else:
            classification = 'UNCLEAR'

        # ========================================
        # CHECK FOR EARLY EXIT (STOPPED OUT BUT WAS WINNER)
        # ========================================
        # This is a special case that indicates stop was too tight
        # We got stopped out BUT price eventually reached checkpoints
        # Indicates potential EARLY_EXIT validation flag
        stopped_out_early = (hit_stop and any(checkpoints_hit.values()))

        # ========================================
        # RETURN COMPREHENSIVE OUTCOME DATA
        # ========================================
        return {
            'classification': classification,
            'star_rating': star_rating,  # 0-5 stars

            # Price movement metrics
            'max_gain_pct': max_gain * 100,
            'max_loss_pct': max_loss * 100,

            # Checkpoint data
            'checkpoints': checkpoints,  # Price levels for each checkpoint
            'checkpoints_hit': checkpoints_hit,  # Which checkpoints hit
            'checkpoint_times': checkpoint_times,  # When they hit (minutes)
            'num_checkpoints_hit': num_checkpoints,

            # Stop data
            'hit_stop': hit_stop,
            'time_to_stop': time_to_stop,
            'stopped_out_early': stopped_out_early,  # Special flag

            # Analysis metadata
            'analysis_duration_minutes': analyze_bars,
            'entry_price': entry_price,
            'stop_level': stop_level,
            'target1': target1
        }

    # ================================================================================
    # HELPER: ROBUST TIMESTAMP PARSING
    # ================================================================================
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Robust timestamp parsing that handles multiple formats

        FIX #5 (Oct 25, 2025): Handle different ISO formats gracefully
        FIX #7 (Oct 25, 2025): Always return timezone-aware datetimes

        Args:
            timestamp_str: Timestamp string in various ISO formats

        Returns:
            datetime object (always timezone-aware, assumes UTC if not specified)

        Raises:
            ValueError: If timestamp cannot be parsed
        """
        import pytz

        try:
            # Handle 'Z' suffix (UTC)
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'

            # Try standard fromisoformat
            dt = datetime.fromisoformat(timestamp_str)

            # If timezone-naive, assume UTC
            if dt.tzinfo is None:
                dt = pytz.UTC.localize(dt)

            return dt

        except ValueError:
            # Fallback: Try dateutil parser if available
            try:
                from dateutil import parser as date_parser
                dt = date_parser.parse(timestamp_str)

                # If timezone-naive, assume UTC
                if dt.tzinfo is None:
                    dt = pytz.UTC.localize(dt)

                return dt
            except ImportError:
                # dateutil not available, re-raise original error
                raise ValueError(f"Cannot parse timestamp: {timestamp_str}")

    # ================================================================================
    # METHOD 4: MATCH TO ENTRY DECISION LOG
    # ================================================================================
    def match_to_log(self, symbol: str, timestamp: str, side: str) -> Optional[Dict]:
        """
        Find matching entry attempt in decision log

        Matching Rules:
        - Same symbol
        - Same side (LONG/SHORT)
        - Timestamp within ±60 seconds (1-min bar tolerance)

        Args:
            symbol: Stock ticker
            timestamp: ISO datetime string of breakout
            side: 'LONG' or 'SHORT'

        Returns:
            Matching attempt dict from entry log or None if not found
            None indicates MISSED_DETECTION (breakout not logged = BUG)
        """
        # FIX #5: Use robust timestamp parsing
        breakout_time = self._parse_timestamp(timestamp)

        # ========================================
        # SEARCH ENTRY LOG FOR MATCH
        # ========================================
        for attempt in self.entry_log['attempts']:
            # Check symbol match
            if attempt['symbol'] != symbol:
                continue

            # Check side match (LONG/SHORT)
            if attempt['side'] != side:
                continue

            # Check timestamp match (within ±60 seconds)
            # This accounts for 1-min bar resolution
            # FIX #5: Use robust timestamp parsing
            log_time = self._parse_timestamp(attempt['timestamp'])
            time_diff = abs((breakout_time - log_time).total_seconds())

            if time_diff <= 60:  # Within 1 minute
                return attempt

        # ========================================
        # NOT FOUND = MISSED DETECTION (BUG)
        # ========================================
        # If we get here, breakout occurred but wasn't logged
        # This indicates a bug in the entry detection logic
        return None

    # ================================================================================
    # METHOD 5: VALIDATE DECISION
    # ================================================================================
    def validate_decision(self, decision: str, outcome_data: Dict,
                         reason: Optional[str], filters: Optional[Dict],
                         symbol: str = None, timestamp: str = None,
                         breakout_type: str = None) -> Dict:
        """
        Validate if our decision was correct in hindsight

        Decision Matrix (8 cases):
        1. ENTERED + WINNER → GOOD_ENTRY ✅
        2. ENTERED + STOPPED_OUT (early exit) → EARLY_EXIT ⚠️
        3. ENTERED + STOPPED_OUT (truly bad) → BAD_ENTRY ⚠️
        4. ENTERED + FALSE_BREAKOUT/CHOPPY → BAD_ENTRY ⚠️
        5. BLOCKED + WINNER → MISSED_WINNER ⚠️
        6. BLOCKED + LOSER → GOOD_BLOCK ✅
        7. MISSED + WINNER → CRITICAL_MISS ⚠️⚠️
        8. MISSED + other → OK 🟡

        ENHANCED (Oct 26, 2025): Now accepts symbol and timestamp for sequence scanning.

        Args:
            decision: 'ENTERED', 'BLOCKED', or 'MISSED'
            outcome_data: Result from classify_outcome()
            reason: Why decision was made (from log)
            filters: Filter results (from log)
            symbol: Stock symbol (for sequence lookup)
            timestamp: Timestamp of attempt (for sequence lookup)

        Returns:
            Validation result dict with:
            - result: Validation classification
            - emoji: Visual indicator
            - analysis: Human-readable explanation
            - impact: What this means
            - action: Recommended next step
        """
        outcome = outcome_data['classification']
        star_rating = outcome_data['star_rating']

        # ========================================
        # CASE 1-4: ENTERED TRADE
        # ========================================
        if decision == 'ENTERED':

            # ----------------------------------------
            # CASE 1: ENTERED + WINNER → GOOD_ENTRY ✅
            # ----------------------------------------
            if outcome == 'WINNER':
                stars = '⭐' * star_rating
                return {
                    'result': 'GOOD_ENTRY',
                    'emoji': '✅',
                    'analysis': f'Correctly entered a winning breakout {stars}',
                    'impact': f'Profit captured ({outcome_data["num_checkpoints_hit"]} checkpoints)',
                    'action': None  # No action needed - good trade
                }

            # ----------------------------------------
            # CASE 2-3: ENTERED + STOPPED_OUT
            # ----------------------------------------
            elif outcome == 'STOPPED_OUT':
                # Check if this was an early exit
                # (stopped out but checkpoints were eventually hit)
                if outcome_data.get('stopped_out_early'):
                    # CASE 2: EARLY_EXIT ⚠️
                    return {
                        'result': 'EARLY_EXIT',
                        'emoji': '⚠️',
                        'analysis': 'Stopped out but target was eventually hit',
                        'impact': 'Missed profit due to tight stop',
                        'action': 'Consider widening stop or using trailing stop'
                    }
                else:
                    # CASE 3: BAD_ENTRY ⚠️
                    return {
                        'result': 'BAD_ENTRY',
                        'emoji': '⚠️',
                        'analysis': 'Entered a losing trade (stopped out)',
                        'impact': 'Loss incurred',
                        'action': 'Review filters - should have blocked this'
                    }

            # ----------------------------------------
            # CASE 4: ENTERED + FALSE_BREAKOUT/CHOPPY
            # ----------------------------------------
            elif outcome in ['FALSE_BREAKOUT', 'CHOPPY']:
                return {
                    'result': 'BAD_ENTRY',
                    'emoji': '⚠️',
                    'analysis': f'Entered a {outcome.lower()}',
                    'impact': 'Loss or minimal gain',
                    'action': f'Tighten filters (choppy/CVD) to avoid {outcome.lower()}'
                }

            else:
                return {
                    'result': 'NEUTRAL',
                    'emoji': '🟡',
                    'analysis': f'Unclear outcome: {outcome}',
                    'impact': 'Monitor',
                    'action': None
                }

        # ========================================
        # CASE 5-6: BLOCKED TRADE
        # ========================================
        elif decision == 'BLOCKED':

            # ----------------------------------------
            # CASE 5: BLOCKED + WINNER → MISSED_WINNER ⚠️
            # ----------------------------------------
            if outcome == 'WINNER':
                stars = '⭐' * star_rating
                # Find which filter blocked it (with details)
                blocking_filter = self.find_blocking_filter(filters) if filters else 'unknown'

                # FIX (Oct 26, 2025): Use confirmation sequence for JSON analysis (same as terminal display)
                # Search for nearby blocked attempts to get complete confirmation flow
                nearby_attempt = self.find_nearby_blocked_attempts(
                    symbol,
                    timestamp,
                    breakout_type  # Will need to pass this from caller
                )

                if nearby_attempt:
                    confirmation_sequence = nearby_attempt.get('confirmation_sequence', [])
                    total_attempts = nearby_attempt.get('total_attempts', 1)

                    # Build detailed confirmation sequence (same logic as terminal display)
                    if confirmation_sequence and len(confirmation_sequence) > 1:
                        sequence_details = []
                        for idx, step in enumerate(confirmation_sequence):
                            step_type = "State Init" if step['is_state_init'] else "Filter Result"
                            reason_text = step['reason'][:60] + "..." if len(step['reason']) > 60 else step['reason']
                            sequence_details.append(
                                f"  Attempt {idx+1} [{step_type}]: {reason_text}"
                            )

                        filter_details = (
                            f"Entry confirmation sequence ({total_attempts} attempts):\n"
                            + "\n".join(sequence_details)
                        )
                    else:
                        # Single attempt - use format_filter_details as before
                        filter_details = self.format_filter_details(filters, symbol, timestamp, self.entry_log) if filters else 'No filter details'
                else:
                    # No nearby attempt found - use format_filter_details as before
                    filter_details = self.format_filter_details(filters, symbol, timestamp, self.entry_log) if filters else 'No filter details'

                return {
                    'result': 'MISSED_WINNER',
                    'emoji': '⚠️',
                    'analysis': f'Blocked a winning breakout {stars}. {filter_details}',
                    'impact': f'Opportunity lost ({outcome_data["num_checkpoints_hit"]} checkpoints)',
                    'action': f'Consider loosening {blocking_filter} filter'
                }

            # ----------------------------------------
            # CASE 6: BLOCKED + LOSER → GOOD_BLOCK ✅
            # ----------------------------------------
            elif outcome in ['STOPPED_OUT', 'FALSE_BREAKOUT', 'CHOPPY']:
                blocking_filter = self.find_blocking_filter(filters) if filters else 'unknown'

                # FIX (Oct 26, 2025): Use confirmation sequence for JSON analysis (same as terminal display)
                # Search for nearby blocked attempts to get complete confirmation flow
                nearby_attempt = self.find_nearby_blocked_attempts(
                    symbol,
                    timestamp,
                    breakout_type
                )

                if nearby_attempt:
                    confirmation_sequence = nearby_attempt.get('confirmation_sequence', [])
                    total_attempts = nearby_attempt.get('total_attempts', 1)

                    # Build detailed confirmation sequence (same logic as terminal display)
                    if confirmation_sequence and len(confirmation_sequence) > 1:
                        sequence_details = []
                        for idx, step in enumerate(confirmation_sequence):
                            step_type = "State Init" if step['is_state_init'] else "Filter Result"
                            reason_text = step['reason'][:60] + "..." if len(step['reason']) > 60 else step['reason']
                            sequence_details.append(
                                f"  Attempt {idx+1} [{step_type}]: {reason_text}"
                            )

                        filter_details = (
                            f"Entry confirmation sequence ({total_attempts} attempts):\n"
                            + "\n".join(sequence_details)
                        )
                    else:
                        # Single attempt - use format_filter_details as before
                        filter_details = self.format_filter_details(filters, symbol, timestamp, self.entry_log) if filters else 'No filter details'
                else:
                    # No nearby attempt found - use format_filter_details as before
                    filter_details = self.format_filter_details(filters, symbol, timestamp, self.entry_log) if filters else 'No filter details'

                return {
                    'result': 'GOOD_BLOCK',
                    'emoji': '✅',
                    'analysis': f'Correctly blocked {outcome.lower()}. {filter_details}',
                    'impact': 'Loss avoided',
                    'action': f'Keep {blocking_filter} filter enabled'
                }

            else:
                return {
                    'result': 'NEUTRAL',
                    'emoji': '🟡',
                    'analysis': f'Blocked {outcome}',
                    'impact': 'Monitor',
                    'action': None
                }

        # ========================================
        # CASE 7-8: MISSED DETECTION (NOT LOGGED)
        # ========================================
        else:  # decision == 'MISSED'

            # FIX #9 (Oct 25, 2025): Enhanced analysis with filter details
            # When breakout is MISSED, search for nearby blocked attempts
            # to explain WHY it was not detected

            # Try to find nearby blocked attempts (within ±5 minutes)
            # This provides context on what filters may have blocked entry
            # Note: We need symbol and side information from the calling context
            # These will be passed via additional parameters if available

            # ----------------------------------------
            # CASE 7: MISSED + WINNER → CRITICAL_MISS ⚠️⚠️
            # ----------------------------------------
            if outcome == 'WINNER':
                stars = '⭐' * star_rating

                # Build detailed analysis based on reason if available
                if reason:
                    # Have some context from nearby attempt
                    analysis = f'Breakout not detected. {reason}. Would have been {stars}'
                else:
                    # No context - pure detection bug
                    analysis = f'Breakout not detected by backtester - detection logic did not trigger. Would have been {stars}'

                return {
                    'result': 'CRITICAL_MISS',
                    'emoji': '⚠️⚠️',
                    'analysis': analysis,
                    'impact': 'Major opportunity lost',
                    'action': 'Fix breakout detection logic or review filter thresholds'
                }

            # ----------------------------------------
            # CASE 8: MISSED + OTHER → OK 🟡
            # ----------------------------------------
            else:
                # Build detailed analysis based on reason if available
                if reason:
                    analysis = f'Breakout not detected. {reason}. Outcome was {outcome.lower()}'
                else:
                    analysis = f'Breakout not detected, but was {outcome.lower()}'

                return {
                    'result': 'MISSED_OK',
                    'emoji': '🟡',
                    'analysis': analysis,
                    'impact': 'No harm (would have lost/broken even)',
                    'action': 'Monitor detection coverage'
                }

    def find_blocking_filter(self, filters: Optional[Dict]) -> str:
        """
        Find which filter blocked the entry

        Args:
            filters: Filter results dict from entry log

        Returns:
            Name of blocking filter or 'unknown'
        """
        if not filters:
            return 'unknown'

        for filter_name, filter_data in filters.items():
            if isinstance(filter_data, dict):
                if filter_data.get('enabled') and filter_data.get('result') == 'BLOCK':
                    return filter_name

        return 'unknown'

    def find_nearby_blocked_attempts(self, symbol: str, timestamp: str, side: str) -> Optional[Dict]:
        """
        Find nearby blocked entry attempts (within ±5 minutes) for a missed breakout

        ENHANCED (Oct 26, 2025): Now shows complete entry confirmation flow
        - Detects "waiting for candle close" state transitions
        - Follows through to actual filter results
        - Reports ALL retry attempts and their outcomes

        This helps explain WHY a breakout was missed by finding the closest
        entry attempt that was blocked by filters.

        Args:
            symbol: Stock ticker
            timestamp: ISO datetime string of breakout
            side: 'LONG' or 'SHORT'

        Returns:
            Dict with 'closest_attempt' and 'confirmation_sequence' or None
        """
        breakout_time = self._parse_timestamp(timestamp)

        nearby_attempts = []
        confirmation_sequence = []

        # Search for attempts near this breakout
        for attempt in self.entry_log['attempts']:
            # Check symbol match
            if attempt['symbol'] != symbol:
                continue

            # Check side match (or either side if unknown)
            if attempt['side'] != side:
                continue

            # Check if BLOCKED
            if attempt['decision'] != 'BLOCKED':
                continue

            # Check timestamp within ±5 minutes (wider window)
            log_time = self._parse_timestamp(attempt['timestamp'])
            time_diff = abs((breakout_time - log_time).total_seconds())

            if time_diff <= 300:  # Within 5 minutes
                nearby_attempts.append((time_diff, attempt))

                # Track confirmation sequences
                reason = attempt.get('reason', '')
                phase = attempt.get('phase', 'unknown')

                # Check if this is state transition or actual filter result
                is_state_init = 'waiting for candle close' in reason

                confirmation_sequence.append({
                    'timestamp': attempt['timestamp'],
                    'time_offset': time_diff,
                    'is_state_init': is_state_init,
                    'phase': phase,
                    'reason': reason,
                    'filters': attempt.get('filters', {})
                })

        # Return closest attempt plus complete sequence
        if nearby_attempts:
            # Sort by time difference (closest first)
            nearby_attempts.sort(key=lambda x: x[0])
            confirmation_sequence.sort(key=lambda x: x['time_offset'])

            return {
                'closest_attempt': nearby_attempts[0][1],
                'confirmation_sequence': confirmation_sequence,
                'total_attempts': len(confirmation_sequence)
            }

        return None

    def find_volume_rejections_from_logs(self, symbol: str, timestamp: str, side: str, backtest_log_path: str = None) -> List[Dict]:
        """
        Parse backtest DEBUG logs to find volume filter rejections

        The entry decision JSON only contains attempts that reached filter evaluation.
        Volume rejections happen earlier and are only in DEBUG logs.

        Args:
            symbol: Stock ticker
            timestamp: ISO datetime string of breakout
            side: 'LONG' or 'SHORT'
            backtest_log_path: Path to backtest log file (auto-detect if None)

        Returns:
            List of volume rejection dicts with time, volume, and reason
        """
        breakout_time = self._parse_timestamp(timestamp)

        # Auto-detect log file if not provided
        if not backtest_log_path:
            date_str = self.date_str.replace('-', '')
            log_dir = Path(__file__).parent.parent / 'backtest' / 'logs'

            # Find most recent log for this date
            log_files = sorted(log_dir.glob(f'backtest_{date_str}_*.log'))
            if not log_files:
                logger.warning(f"No backtest log found for {self.date}")
                return []

            backtest_log_path = log_files[-1]  # Most recent

        if not Path(backtest_log_path).exists():
            logger.warning(f"Backtest log not found: {backtest_log_path}")
            return []

        rejections = []

        try:
            with open(backtest_log_path, 'r') as f:
                for line in f:
                    # Look for volume rejection lines
                    # Example: "SMCI Bar 27 - SHORT confirmation: confirmed=False, reason='Breakout rejected: Sub-average volume (0.80x)'"
                    if symbol in line and side in line and 'Sub-average volume' in line:
                        # Extract details
                        import re

                        # Extract bar number
                        bar_match = re.search(rf'{symbol} Bar (\d+)', line)
                        if not bar_match:
                            continue
                        bar_num = int(bar_match.group(1))

                        # Extract volume ratio
                        vol_match = re.search(r'Sub-average volume \(([0-9.]+)x\)', line)
                        if not vol_match:
                            continue
                        volume_ratio = float(vol_match.group(1))

                        # Extract timestamp from log line
                        time_match = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        if not time_match:
                            continue
                        log_time_str = time_match.group(1)

                        rejections.append({
                            'bar': bar_num,
                            'volume_ratio': volume_ratio,
                            'log_time': log_time_str,
                            'reason': f'Sub-average volume ({volume_ratio}x < 1.0x required)'
                        })

        except Exception as e:
            logger.error(f"Error parsing backtest log: {e}")
            return []

        return rejections

    def format_filter_details(self, filters: Optional[Dict], symbol: str = None, timestamp: str = None, entry_log: List[Dict] = None) -> str:
        """
        Format filter details into human-readable explanation

        ENHANCED (Oct 26, 2025): Uses enhanced entry decision logging that includes
        detailed blocking reasons directly in the 'reason' field. Much simpler now!

        Args:
            filters: Filter results dict from entry log
            symbol: Stock symbol (for attempt lookup)
            timestamp: Timestamp of current attempt (for attempt lookup)
            entry_log: Full entry log for extracting detailed reason

        Returns:
            Formatted string explaining which filters blocked and why
        """
        if not filters:
            return "No filter information available"

        # ENHANCEMENT: Extract detailed blocking reason from entry log
        # The enhanced logging (Oct 26) now includes specific filter values in 'reason' field
        if symbol and timestamp and entry_log and isinstance(entry_log, list):
            # Find this attempt in the log by timestamp
            attempt_idx = None
            for idx, attempt in enumerate(entry_log):
                if not isinstance(attempt, dict):
                    continue

                if attempt.get('symbol') == symbol and attempt.get('timestamp') == timestamp:
                    attempt_idx = idx
                    reason = attempt.get('reason', '')
                    phase = attempt.get('phase', 'unknown')

                    # If we have a detailed blocking reason, return it directly
                    # Example: "Breakout rejected: Sub-average volume (0.72x)"
                    if reason and reason != "Breakout detected, waiting for candle close":
                        return reason

                    # If this is the initial detection message, check subsequent bars for same symbol
                    if reason == "Breakout detected, waiting for candle close":
                        # Search forward in the log for next attempt with this symbol
                        found_subsequent = False
                        for next_idx in range(idx + 1, min(idx + 20, len(entry_log))):  # Check up to 20 bars ahead
                            next_attempt = entry_log[next_idx]
                            if not isinstance(next_attempt, dict):
                                continue

                            if next_attempt.get('symbol') == symbol:
                                next_reason = next_attempt.get('reason', '')
                                # Skip other "waiting for candle close" messages
                                if next_reason and next_reason != "Breakout detected, waiting for candle close":
                                    return next_reason
                                found_subsequent = True
                                # If we hit another symbol's attempt, stop searching
                                break

                        # If no subsequent attempt found, return informative message
                        if not found_subsequent:
                            return "Initial detection only - no subsequent filter checks logged (backtester bug)"

                    # Fallback: use phase
                    return f"{phase} filter (check entry log for details)"

        blocking_filters = []

        for filter_name, filter_data in filters.items():
            if not isinstance(filter_data, dict):
                continue

            if filter_data.get('enabled') and filter_data.get('result') == 'BLOCK':
                # Extract filter-specific details
                reason = filter_data.get('reason', 'No reason provided')

                # Build detailed explanation based on filter type
                if filter_name == 'room_to_run':
                    room_pct = filter_data.get('room_pct', 0) * 100
                    threshold = filter_data.get('threshold', 0) * 100
                    blocking_filters.append(
                        f"room_to_run filter (room: {room_pct:.2f}% < {threshold:.2f}% threshold)"
                    )

                elif filter_name == 'choppy':
                    range_pct = filter_data.get('range_pct', 0) * 100
                    threshold = filter_data.get('threshold', 0) * 100
                    blocking_filters.append(
                        f"choppy filter (range: {range_pct:.2f}% < {threshold:.2f}% threshold)"
                    )

                elif filter_name == 'cvd':
                    cvd_state = filter_data.get('cvd_state', 'UNKNOWN')
                    blocking_filters.append(
                        f"CVD filter ({cvd_state} trend blocking entry)"
                    )

                elif filter_name == 'stochastic':
                    stoch_state = filter_data.get('stochastic_state', 'UNKNOWN')
                    blocking_filters.append(
                        f"stochastic filter ({stoch_state})"
                    )

                elif filter_name == 'directional_volume':
                    blocking_filters.append(
                        f"directional_volume filter ({reason})"
                    )

                else:
                    # Generic format for unknown filters
                    blocking_filters.append(f"{filter_name} filter ({reason})")

        if blocking_filters:
            return "Blocked by: " + ", ".join(blocking_filters)
        else:
            return "No blocking filters detected"

    # ================================================================================
    # METHOD 6: RUN - MAIN VALIDATION WORKFLOW
    # ================================================================================
    def run(self):
        """
        Main validation workflow

        Steps:
        1. Loop through each stock in scanner
        2. Load cached 1-min bars (skip if missing)
        3. Identify all breakouts (resistance + support)
        4. Classify each breakout outcome (with 5-star rating)
        5. Match breakout to entry decision log
        6. Validate decision (was it correct?)
        7. Track statistics
        8. Generate comprehensive reports
        """
        logger.info("Starting validation workflow...")
        logger.info("")

        # ========================================
        # LOOP THROUGH EACH STOCK
        # ========================================
        for idx, stock in enumerate(self.scanner_data, 1):
            symbol = stock['symbol']

            logger.info(f"[{idx}/{len(self.scanner_data)}] Processing {symbol}...")

            # ========================================
            # STEP 1: LOAD CACHED 1-MIN BARS
            # ========================================
            bars = self.load_saved_bars(symbol)
            if not bars:
                logger.warning(f"  ⚠️  Skipping {symbol} (bars not available)")
                continue

            # ========================================
            # STEP 2: IDENTIFY ALL BREAKOUTS
            # ========================================
            breakouts = self.identify_breakouts(
                bars,
                stock['resistance'],
                stock['support']
            )

            logger.info(f"  Found {len(breakouts)} breakouts")

            # If no breakouts, move to next stock
            if not breakouts:
                continue

            # ========================================
            # STEP 3-6: PROCESS EACH BREAKOUT
            # ========================================
            for breakout in breakouts:
                # ----------------------------------------
                # STEP 3: CLASSIFY OUTCOME (5-STAR RATING)
                # ----------------------------------------
                # CRITICAL FIX (Oct 25, 2025): Use actual backtester stop logic
                # Calculate stop level using PS60Strategy (if available)
                if self.strategy:
                    # Create temporary position dict (as backtester does)
                    temp_position = {
                        'entry_price': breakout['price'],
                        'side': breakout['type'],
                        'partials': 0,
                        'pivot': stock['resistance'] if breakout['type'] == 'LONG' else stock['support']
                    }
                    # Use actual strategy stop calculation
                    stop_level = self.strategy.calculate_stop_price(
                        position=temp_position,
                        current_price=breakout['price'],
                        stock_data=stock
                    )
                else:
                    # Fallback: Simple pivot-level stop
                    # This is less accurate but better than crashing
                    if breakout['type'] == 'LONG':
                        stop_level = stock['resistance']
                    else:
                        stop_level = stock['support']

                # FIX #2 & #11 (Oct 25, 2025): Use correct target based on direction
                # LONG trades: Use target1 (above entry price)
                # SHORT trades: Use downside1 (below entry price)
                if breakout['type'] == 'LONG':
                    target1 = stock.get('target1')
                    if not target1:
                        logger.warning(f"  Skipping breakout - missing target1 for {symbol}")
                        continue
                else:  # SHORT
                    target1 = stock.get('downside1')
                    if not target1:
                        logger.warning(f"  Skipping breakout - missing downside1 for {symbol}")
                        continue

                outcome = self.classify_outcome(
                    bars,
                    breakout,
                    target1,
                    stop_level
                )

                # ----------------------------------------
                # STEP 4: MATCH TO ENTRY DECISION LOG
                # ----------------------------------------
                log_entry = self.match_to_log(
                    symbol,
                    breakout['timestamp'],
                    breakout['type']
                )

                # Determine decision type
                if log_entry:
                    decision = log_entry['decision']  # 'ENTERED' or 'BLOCKED'
                    reason = log_entry.get('reason')
                    filters = log_entry.get('filters')

                    # ENHANCED (Oct 26, 2025): Also show confirmation sequences for BLOCKED entries
                    if decision == 'BLOCKED':
                        nearby_attempt = self.find_nearby_blocked_attempts(
                            symbol,
                            breakout['timestamp'],
                            breakout['type']
                        )

                        if nearby_attempt:
                            confirmation_sequence = nearby_attempt.get('confirmation_sequence', [])
                            total_attempts = nearby_attempt.get('total_attempts', 1)

                            # Enhance reason with confirmation sequence if multiple attempts
                            if confirmation_sequence and len(confirmation_sequence) > 1:
                                sequence_details = []
                                for idx, step in enumerate(confirmation_sequence):
                                    step_type = "State Init" if step['is_state_init'] else "Filter Result"
                                    reason_text = step['reason'][:60] + "..." if len(step['reason']) > 60 else step['reason']
                                    sequence_details.append(
                                        f"  Attempt {idx+1} [{step_type}]: {reason_text}"
                                    )

                                # Replace simple reason with detailed sequence
                                reason = (
                                    f"Entry confirmation sequence ({total_attempts} attempts):\n"
                                    + "\n".join(sequence_details)
                                )
                else:
                    # MISSED detection - search for nearby blocked attempts
                    # FIX #9 (Oct 25, 2025): Provide detailed WHY analysis
                    decision = 'MISSED'

                    # Search for nearby blocked attempts (within ±5 minutes)
                    nearby_attempt = self.find_nearby_blocked_attempts(
                        symbol,
                        breakout['timestamp'],
                        breakout['type']
                    )

                    if nearby_attempt:
                        # ENHANCED (Oct 26, 2025): Extract confirmation sequence to show complete retry flow
                        closest_attempt = nearby_attempt.get('closest_attempt', nearby_attempt)
                        confirmation_sequence = nearby_attempt.get('confirmation_sequence', [])
                        total_attempts = nearby_attempt.get('total_attempts', 1)

                        # Found a nearby blocked attempt - extract filter details
                        nearby_filters = closest_attempt.get('filters')
                        filter_explanation = self.format_filter_details(
                            nearby_filters,
                            closest_attempt.get('symbol'),
                            closest_attempt.get('timestamp'),
                            self.entry_log
                        )

                        # Calculate time offset
                        breakout_time = self._parse_timestamp(breakout['timestamp'])
                        attempt_time = self._parse_timestamp(closest_attempt['timestamp'])
                        time_diff = int(abs((breakout_time - attempt_time).total_seconds()))

                        # Build detailed reason with confirmation sequence
                        if confirmation_sequence and len(confirmation_sequence) > 1:
                            # Show complete retry flow
                            sequence_details = []
                            for idx, step in enumerate(confirmation_sequence):
                                step_type = "State Init" if step['is_state_init'] else "Filter Result"
                                reason_text = step['reason'][:60] + "..." if len(step['reason']) > 60 else step['reason']
                                sequence_details.append(
                                    f"  Attempt {idx+1} [{step_type}]: {reason_text}"
                                )

                            reason = (
                                f"Entry confirmation sequence ({total_attempts} attempts within {time_diff}s):\n"
                                + "\n".join(sequence_details) + "\n"
                                + f"Final result: BLOCKED. {filter_explanation}"
                            )
                        else:
                            # Single attempt (backward compatibility)
                            reason = (
                                f"Nearby entry attempt found at {closest_attempt['timestamp']} "
                                f"({time_diff}s away) was BLOCKED. {filter_explanation}"
                            )
                        filters = nearby_filters
                    else:
                        # No nearby attempts found in entry log - check DEBUG logs for volume rejections
                        volume_rejections = self.find_volume_rejections_from_logs(
                            symbol,
                            breakout['timestamp'],
                            breakout['type']
                        )

                        if volume_rejections:
                            # ENHANCED (Oct 26, 2025): Build confirmation sequence from volume rejections
                            # Each rejection implies: State Init → Filter Result pattern
                            confirmation_sequence = []
                            for idx, rejection in enumerate(volume_rejections):
                                # Add State Init (waiting for candle close)
                                confirmation_sequence.append({
                                    'timestamp': f"Bar {rejection['bar']}",
                                    'is_state_init': True,
                                    'phase': 'unknown',
                                    'reason': 'Breakout detected, waiting for candle close'
                                })

                                # Add Filter Result (volume rejection)
                                confirmation_sequence.append({
                                    'timestamp': f"Bar {rejection['bar']}",
                                    'is_state_init': False,
                                    'phase': 'volume_filter',
                                    'reason': f"Sub-average volume ({rejection['volume_ratio']:.2f}x < 1.0x required)"
                                })

                            # Display detailed confirmation sequence
                            if len(confirmation_sequence) > 1:
                                sequence_details = []
                                for idx, step in enumerate(confirmation_sequence):
                                    step_type = "State Init" if step['is_state_init'] else "Filter Result"
                                    sequence_details.append(
                                        f"  Attempt {idx+1} [{step_type}]: {step['reason']}"
                                    )

                                reason = (
                                    f"Entry confirmation sequence ({len(volume_rejections)} retries):\n"
                                    + "\n".join(sequence_details) + "\n"
                                    + "Final result: BLOCKED by volume filter. Entry occurred later when volume surged."
                                )
                            else:
                                # Fallback to condensed format
                                rejection_details = []
                                for rejection in volume_rejections:
                                    rejection_details.append(
                                        f"Bar {rejection['bar']}: volume {rejection['volume_ratio']:.2f}x (< 1.0x required)"
                                    )

                                reason = (
                                    f"Breakout detected but rejected by volume filter. "
                                    f"Attempts: {', '.join(rejection_details)}. "
                                    f"Entry occurred later when volume surged."
                                )

                            filters = {'volume_filter': {
                                'enabled': True,
                                'result': 'BLOCK',
                                'rejections': volume_rejections
                            }}
                        else:
                            # No nearby attempts and no volume rejections - pure detection bug
                            reason = "No entry attempts logged near this breakout time - breakout detection logic did not trigger"
                            filters = None

                # ----------------------------------------
                # STEP 5: VALIDATE DECISION
                # ----------------------------------------
                validation = self.validate_decision(
                    decision,
                    outcome,
                    reason,
                    filters,
                    symbol,
                    breakout['timestamp'],
                    breakout['type']  # FIX (Oct 26, 2025): Pass breakout_type for nearby attempt search
                )

                # ----------------------------------------
                # STEP 6: TRACK RESULTS
                # ----------------------------------------
                # Store for reporting
                self.all_breakouts.append({
                    'symbol': symbol,
                    'breakout': breakout,
                    'outcome': outcome,
                    'decision': decision,
                    'log_entry': log_entry,
                    'validation': validation
                })

                # Update statistics
                result = validation['result']
                if result == 'GOOD_ENTRY':
                    self.validation_results['good_entries'] += 1
                elif result == 'GOOD_BLOCK':
                    self.validation_results['good_blocks'] += 1
                elif result == 'BAD_ENTRY':
                    self.validation_results['bad_entries'] += 1
                elif result == 'MISSED_WINNER':
                    self.validation_results['missed_winners'] += 1
                elif result == 'EARLY_EXIT':
                    self.validation_results['early_exits'] += 1
                elif result == 'CRITICAL_MISS':
                    self.validation_results['missed_detections'] += 1

        # ========================================
        # STEP 7: GENERATE REPORTS
        # ========================================
        logger.info("")
        logger.info("="*80)
        logger.info("GENERATING REPORTS")
        logger.info("="*80)
        logger.info("")

        self.generate_reports()

    # ================================================================================
    # METHOD 7: GENERATE REPORTS
    # ================================================================================
    def generate_reports(self):
        """
        Generate comprehensive validation reports

        Outputs:
        1. Console: Per-stock detailed analysis
        2. Console: Daily summary with statistics
        3. JSON: Machine-readable results (always overwrite)
        """
        # ========================================
        # PART 1: PER-STOCK CONSOLE REPORTS
        # ========================================
        # Group breakouts by stock
        by_stock = {}
        for item in self.all_breakouts:
            symbol = item['symbol']
            if symbol not in by_stock:
                by_stock[symbol] = []
            by_stock[symbol].append(item)

        # Print per-stock analysis
        for symbol in sorted(by_stock.keys()):
            items = by_stock[symbol]

            print("")
            print("="*80)
            print(f"{symbol} - {self.date_str}")
            print("="*80)

            for i, item in enumerate(items, 1):
                breakout = item['breakout']
                outcome = item['outcome']
                validation = item['validation']

                # Show star rating
                stars = '⭐' * outcome['star_rating']

                print(f"\nBREAKOUT #{i} - {breakout['type']} @ {breakout['timestamp']}")
                print(f"  Price: ${breakout['price']:.2f}")
                print("")
                print(f"  OUTCOME:")
                print(f"    Classification: {outcome['classification']} {stars}")
                print(f"    Max Gain: +{outcome['max_gain_pct']:.2f}%")
                print(f"    Max Loss: {outcome['max_loss_pct']:.2f}%")
                print(f"    Checkpoints Hit: {outcome['num_checkpoints_hit']}/4")
                if outcome['checkpoints_hit']['25%']:
                    print(f"      ✓ 25% @ {outcome['checkpoint_times'].get('25%', '?')} min")
                if outcome['checkpoints_hit']['50%']:
                    print(f"      ✓ 50% @ {outcome['checkpoint_times'].get('50%', '?')} min")
                if outcome['checkpoints_hit']['75%']:
                    print(f"      ✓ 75% @ {outcome['checkpoint_times'].get('75%', '?')} min")
                if outcome['checkpoints_hit']['100%']:
                    print(f"      ✓ 100% (target1) @ {outcome['checkpoint_times'].get('100%', '?')} min")

                print("")
                print(f"  DECISION:")
                print(f"    Type: {item['decision']}")
                if item['log_entry']:
                    print(f"    Reason: {item['log_entry'].get('reason', 'N/A')}")

                print("")
                print(f"  VALIDATION:")
                print(f"    Result: {validation['emoji']} {validation['result']}")
                print(f"    Analysis: {validation['analysis']}")
                print(f"    Impact: {validation['impact']}")
                if validation['action']:
                    print(f"    Action: {validation['action']}")

        # ========================================
        # PART 2: DAILY SUMMARY CONSOLE REPORT
        # ========================================
        print("")
        print("="*80)
        print(f"VALIDATION SUMMARY - {self.date_str}")
        print("="*80)
        print("")

        print(f"BREAKOUT ANALYSIS:")
        print(f"  Total breakouts: {len(self.all_breakouts)}")

        # Count by type
        long_count = sum(1 for item in self.all_breakouts if item['breakout']['type'] == 'LONG')
        short_count = sum(1 for item in self.all_breakouts if item['breakout']['type'] == 'SHORT')
        print(f"  - LONG breakouts: {long_count}")
        print(f"  - SHORT breakouts: {short_count}")
        print("")

        print(f"DECISION QUALITY:")
        print(f"  ✅ Good entries: {self.validation_results['good_entries']}")
        print(f"  ✅ Good blocks: {self.validation_results['good_blocks']}")
        print(f"  ⚠️  Bad entries: {self.validation_results['bad_entries']}")
        print(f"  ⚠️  Missed winners: {self.validation_results['missed_winners']}")
        print(f"  ⚠️  Early exits: {self.validation_results['early_exits']}")
        print(f"  ⚠️⚠️  Missed detections: {self.validation_results['missed_detections']}")
        print("")

        # Calculate accuracy
        total_decisions = len([item for item in self.all_breakouts if item['decision'] != 'MISSED'])
        good_decisions = self.validation_results['good_entries'] + self.validation_results['good_blocks']
        if total_decisions > 0:
            accuracy = (good_decisions / total_decisions) * 100
            print(f"DECISION ACCURACY: {accuracy:.1f}% ({good_decisions}/{total_decisions})")

        # ========================================
        # PART 3: SAVE JSON REPORT
        # ========================================
        # Always overwrite (Oct 25 spec: no duplicates)
        reports_dir = Path(__file__).parent / 'reports'
        reports_dir.mkdir(exist_ok=True)

        json_file = reports_dir / f"validation_results_{self.date.strftime('%Y%m%d')}.json"

        # Prepare JSON data
        json_data = {
            'generated_at': datetime.now().isoformat(),
            'validation_date': self.date_str,
            'total_breakouts': len(self.all_breakouts),
            'long_breakouts': long_count,
            'short_breakouts': short_count,
            'validation_results': self.validation_results,
            'breakouts': []
        }

        # Add all breakout details
        for item in self.all_breakouts:
            json_data['breakouts'].append({
                'symbol': item['symbol'],
                'timestamp': item['breakout']['timestamp'],
                'type': item['breakout']['type'],
                'price': item['breakout']['price'],
                'outcome': {
                    'classification': item['outcome']['classification'],
                    'star_rating': item['outcome']['star_rating'],
                    'max_gain_pct': item['outcome']['max_gain_pct'],
                    'checkpoints_hit': item['outcome']['checkpoints_hit'],
                    'num_checkpoints_hit': item['outcome']['num_checkpoints_hit']
                },
                'decision': item['decision'],
                'validation': {
                    'result': item['validation']['result'],
                    'analysis': item['validation']['analysis'],
                    'impact': item['validation']['impact'],
                    'action': item['validation']['action']
                }
            })

        # Save JSON (always overwrite)
        with open(json_file, 'w') as f:
            json.dump(json_data, f, indent=2)

        print("")
        print(f"💾 JSON report saved to: {json_file}")

        # ========================================
        # PART 4: CRITICAL ERRORS SUMMARY
        # ========================================
        if self.missing_bars_symbols:
            print("")
            print("="*80)
            print("⚠️⚠️  CRITICAL ERRORS DETECTED")
            print("="*80)
            print(f"Missing bars for {len(self.missing_bars_symbols)} stocks:")
            for symbol in self.missing_bars_symbols:
                print(f"  - {symbol}")
            print("")
            print("ACTION REQUIRED:")
            print(f"  Re-run backtest for {self.date_str}")
            print(f"  Ensure all stocks have cached bars")
            print("="*80)


# ================================================================================
# MAIN ENTRY POINT
# ================================================================================
def main():
    """Command-line entry point for market outcome validator"""
    parser = argparse.ArgumentParser(
        description='Validate entry decisions against actual market outcomes'
    )

    parser.add_argument(
        '--scanner',
        required=True,
        help='Path to scanner results JSON'
    )

    parser.add_argument(
        '--entry-log',
        required=True,
        help='Path to entry decision log JSON'
    )

    parser.add_argument(
        '--date',
        required=True,
        help='Trading date (YYYY-MM-DD)'
    )

    parser.add_argument(
        '--account-size',
        type=float,
        default=50000,
        help='Account size (default: 50000)'
    )

    args = parser.parse_args()

    try:
        validator = MarketOutcomeValidator(
            scanner_file=args.scanner,
            entry_log_file=args.entry_log,
            date=args.date,
            account_size=args.account_size
        )

        validator.run()

    except FileNotFoundError as e:
        logger.error(f"✗ File not found: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"✗ Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"✗ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
