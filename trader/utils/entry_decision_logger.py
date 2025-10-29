"""
Entry Decision Logger for Backtest Validation (October 25, 2025)

This module captures comprehensive filter decision data for EVERY entry attempt
(both entered and blocked) to enable validation of backtest results.

Purpose:
- Validate if backtest missed any valid entries
- Analyze why entries were blocked
- Understand filter effectiveness
- Debug filter logic issues

Captures:
- All pivot checks
- Entry path determination (momentum/pullback/sustained)
- All filter values and results
- Final decision and reasoning
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class EntryDecisionLogger:
    """
    Logs comprehensive entry decision data for backtest validation.

    Captures ALL entry attempts (entered + blocked) with complete filter values.
    """

    def __init__(self, backtest_date: datetime):
        """
        Initialize entry decision logger.

        Args:
            backtest_date: Date being backtested
        """
        self.backtest_date = backtest_date
        self.attempts: List[Dict[str, Any]] = []

        # Statistics
        self.total_attempts = 0
        self.entered = 0
        self.blocked = 0
        self.blocks_by_filter: Dict[str, int] = {}
        self.blocks_by_symbol: Dict[str, int] = {}

    def log_entry_attempt(self,
                          timestamp: datetime,
                          symbol: str,
                          side: str,
                          bar_idx: int,
                          price: float,
                          pivot_data: Dict[str, Any],
                          pivot_checks: Dict[str, Any],
                          entry_path: Dict[str, Any],
                          filters: Dict[str, Any],
                          decision: str,
                          phase: str,
                          reason: str):
        """
        Log a single entry attempt with complete filter data.

        Args:
            timestamp: Bar timestamp
            symbol: Stock symbol
            side: 'LONG' or 'SHORT'
            bar_idx: Bar index
            price: Current price
            pivot_data: {resistance, support, through_pivot}
            pivot_checks: {price_vs_pivot, attempt_count, avoid_list, position_size}
            entry_path: {volume_ratio, candle_size_pct, path_chosen}
            filters: {choppy: {...}, room_to_run: {...}, stochastic: {...}, cvd: {...}}
            decision: 'ENTERED' or 'BLOCKED'
            phase: Entry phase/state
            reason: Final decision reason
        """
        self.total_attempts += 1

        if decision == 'ENTERED':
            self.entered += 1
        else:
            self.blocked += 1

            # Track which filter blocked
            blocking_filter = phase if phase else 'unknown'
            self.blocks_by_filter[blocking_filter] = self.blocks_by_filter.get(blocking_filter, 0) + 1
            self.blocks_by_symbol[symbol] = self.blocks_by_symbol.get(symbol, 0) + 1

        # Build attempt record
        attempt = {
            'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            'symbol': symbol,
            'side': side,
            'bar_idx': bar_idx,
            'price': price,
            'pivot': pivot_data,
            'pivot_checks': pivot_checks,
            'entry_path': entry_path,
            'filters': filters,
            'decision': decision,
            'phase': phase,
            'reason': reason
        }

        self.attempts.append(attempt)

    def save_to_json(self, output_dir: Path) -> Path:
        """
        Save all entry decisions to JSON file.

        Args:
            output_dir: Directory to save file

        Returns:
            Path to saved file
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = self.backtest_date.strftime('%Y%m%d')
        filename = output_dir / f'backtest_entry_decisions_{date_str}.json'

        # Build output structure
        output = {
            'backtest_date': self.backtest_date.strftime('%Y-%m-%d'),
            'total_attempts': self.total_attempts,
            'entered': self.entered,
            'blocked': self.blocked,
            'blocks_by_filter': dict(sorted(self.blocks_by_filter.items(),
                                           key=lambda x: x[1], reverse=True)),
            'blocks_by_symbol': dict(sorted(self.blocks_by_symbol.items(),
                                           key=lambda x: x[1], reverse=True)),
            'attempts': self.attempts
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)

        return filename

    def print_summary(self):
        """Print summary statistics."""
        print(f"\n{'='*80}")
        print(f"ENTRY DECISION SUMMARY")
        print(f"{'='*80}")
        print(f"Total Attempts: {self.total_attempts}")
        print(f"Entered: {self.entered} ({self.entered/self.total_attempts*100:.1f}%)")
        print(f"Blocked: {self.blocked} ({self.blocked/self.total_attempts*100:.1f}%)")

        if self.blocks_by_filter:
            print(f"\nBLOCKS BY FILTER:")
            for filter_name, count in sorted(self.blocks_by_filter.items(),
                                            key=lambda x: x[1], reverse=True):
                pct = count / self.blocked * 100 if self.blocked > 0 else 0
                print(f"  {filter_name}: {count} ({pct:.1f}%)")

        if self.blocks_by_symbol:
            print(f"\nTOP 10 SYMBOLS BLOCKED:")
            for i, (symbol, count) in enumerate(list(sorted(self.blocks_by_symbol.items(),
                                                           key=lambda x: x[1], reverse=True))[:10]):
                print(f"  {i+1}. {symbol}: {count} blocks")


def capture_filter_data(strategy, bars, current_idx, side,
                        entry_path_data: Dict[str, Any],
                        target_price: Optional[float] = None,
                        symbol: Optional[str] = None,
                        entry_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Capture all filter data at decision time.

    This function extracts current values from all enabled filters
    to enable validation analysis.

    Args:
        strategy: PS60Strategy instance
        bars: Bar list
        current_idx: Current bar index
        side: 'LONG' or 'SHORT'
        entry_path_data: Entry path info (volume_ratio, candle_size, etc.)
        target_price: Target price for room-to-run filter
        symbol: Stock symbol for stochastic/CVD filters
        entry_state: Entry state machine data (includes CVD, directional volume results)

    Returns:
        Dict with all filter data:
        {
            'choppy': {...},
            'room_to_run': {...},
            'stochastic': {...},
            'cvd': {...},
            'directional_volume': {...}
        }
    """
    filters = {}

    # --- CHOPPY FILTER ---
    choppy_enabled = strategy.enable_choppy_filter
    if choppy_enabled and current_idx >= strategy.atr_period:
        lookback_start = max(0, current_idx - strategy.choppy_lookback_bars)
        recent_bars = bars[lookback_start:current_idx + 1]

        if len(recent_bars) >= strategy.atr_period:
            recent_high = max(b.high for b in recent_bars)
            recent_low = min(b.low for b in recent_bars)
            recent_range = recent_high - recent_low
            atr = strategy._calculate_atr(bars, current_idx)
            ratio = recent_range / atr if atr > 0 else 0

            filters['choppy'] = {
                'enabled': True,
                'range_5min': round(recent_range, 2),
                'atr': round(atr, 2),
                'ratio': round(ratio, 2),
                'threshold': strategy.choppy_atr_multiplier,
                'result': 'BLOCK' if ratio < strategy.choppy_atr_multiplier else 'PASS',
                'reason': f"Choppy: {ratio:.2f}× ATR < {strategy.choppy_atr_multiplier}×" if ratio < strategy.choppy_atr_multiplier else None
            }
        else:
            filters['choppy'] = {'enabled': True, 'result': 'SKIP', 'reason': 'Insufficient bars for ATR'}
    else:
        filters['choppy'] = {'enabled': False, 'result': 'DISABLED'}

    # --- ROOM-TO-RUN FILTER ---
    room_enabled = strategy.enable_room_to_run_filter
    if room_enabled and target_price is not None:
        current_price = bars[current_idx].close
        if side == 'LONG':
            room_pct = ((target_price - current_price) / current_price) * 100
        else:  # SHORT
            room_pct = ((current_price - target_price) / current_price) * 100

        filters['room_to_run'] = {
            'enabled': True,
            'entry': round(current_price, 2),
            'target': round(target_price, 2),
            'room_pct': round(room_pct, 2),
            'threshold': strategy.min_room_to_target_pct,
            'result': 'BLOCK' if room_pct < strategy.min_room_to_target_pct else 'PASS',
            'reason': f"Room {room_pct:.2f}% < {strategy.min_room_to_target_pct:.1f}% min" if room_pct < strategy.min_room_to_target_pct else None
        }
    elif room_enabled:
        filters['room_to_run'] = {'enabled': True, 'result': 'SKIP', 'reason': 'No target price'}
    else:
        filters['room_to_run'] = {'enabled': False, 'result': 'DISABLED'}

    # --- STOCHASTIC FILTER ---
    stoch_enabled = strategy.stochastic_enabled
    if stoch_enabled and symbol and strategy.stochastic_calculator:
        try:
            stoch = strategy.stochastic_calculator.get_stochastic(symbol)
            if stoch:
                k = stoch['%K']
                d = stoch['%D']

                if side == 'LONG':
                    min_k = strategy.stochastic_long_min_k
                    max_k = strategy.stochastic_long_max_k
                    in_range = min_k <= k <= max_k
                else:  # SHORT
                    min_k = strategy.stochastic_short_min_k
                    max_k = strategy.stochastic_short_max_k
                    in_range = min_k <= k <= max_k

                filters['stochastic'] = {
                    'enabled': True,
                    'k_value': round(k, 1),
                    'd_value': round(d, 1),
                    'min_k': min_k,
                    'max_k': max_k,
                    'result': 'PASS' if in_range else 'BLOCK',
                    'reason': f"%K {k:.1f} not in range [{min_k}-{max_k}]" if not in_range else None
                }
            else:
                filters['stochastic'] = {'enabled': True, 'result': 'SKIP', 'reason': 'Calculation failed'}
        except Exception as e:
            filters['stochastic'] = {'enabled': True, 'result': 'ERROR', 'reason': str(e)}
    else:
        filters['stochastic'] = {'enabled': False, 'result': 'DISABLED'}

    # --- CVD FILTER ---
    # Extract CVD results from entry_state if available
    if entry_state and 'cvd_data' in entry_state:
        cvd_data = entry_state['cvd_data']
        filters['cvd'] = {
            'enabled': True,
            'buy_volume': cvd_data.get('buy_volume', 0),
            'sell_volume': cvd_data.get('sell_volume', 0),
            'imbalance_pct': round(cvd_data.get('imbalance_pct', 0), 1),
            'threshold': cvd_data.get('threshold', 0),
            'result': cvd_data.get('result', 'UNKNOWN'),
            'reason': cvd_data.get('reason')
        }
    elif entry_state and entry_state.get('phase') in ['CVD_MONITORING', 'cvd_filter']:
        # CVD was being checked but no data captured yet
        filters['cvd'] = {
            'enabled': True,
            'result': 'CHECKING',
            'reason': 'CVD monitoring active, waiting for signal'
        }
    else:
        # CVD not enabled or not applicable for this entry path
        cvd_enabled = getattr(strategy, 'cvd_enabled', False)
        filters['cvd'] = {'enabled': cvd_enabled, 'result': 'DISABLED' if not cvd_enabled else 'SKIP'}

    # --- DIRECTIONAL VOLUME FILTER ---
    # Extract directional volume results from entry_state if available
    if entry_state and 'directional_volume_data' in entry_state:
        dv_data = entry_state['directional_volume_data']
        filters['directional_volume'] = {
            'enabled': True,
            'volume_ratio': round(dv_data.get('volume_ratio', 0), 2),
            'threshold': dv_data.get('threshold', 1.0),
            'result': dv_data.get('result', 'UNKNOWN'),
            'reason': dv_data.get('reason')
        }
    elif entry_state and 'volume_ratio' in entry_state and entry_state.get('volume_ratio') is not None:
        # We have volume ratio from breakout detection
        vol_ratio = entry_state.get('volume_ratio', 0)
        vol_threshold = entry_path_data.get('volume_threshold', 1.0)
        is_pass = vol_ratio >= vol_threshold
        filters['directional_volume'] = {
            'enabled': True,
            'volume_ratio': round(vol_ratio, 2),
            'threshold': vol_threshold,
            'result': 'PASS' if is_pass else 'BLOCK',
            'reason': None if is_pass else f"Volume {vol_ratio:.2f}x < {vol_threshold:.1f}x required"
        }
    else:
        # Directional volume not checked
        filters['directional_volume'] = {'enabled': False, 'result': 'DISABLED'}

    return filters
