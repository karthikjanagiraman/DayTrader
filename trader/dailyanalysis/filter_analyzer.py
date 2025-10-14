#!/usr/bin/env python3
"""
Filter Effectiveness Analyzer

Analyzes why trades were blocked and whether filters are working correctly.
Helps optimize filter thresholds and identify over-filtering.
"""

import re
from pathlib import Path
from collections import defaultdict


class FilterEffectivenessAnalyzer:
    """
    Analyzes filter blocking patterns to optimize entry criteria

    Questions answered:
    - Which filters block the most trades?
    - Are filters blocking good setups or bad ones?
    - Should filter thresholds be adjusted?
    """

    def __init__(self, log_file):
        """
        Initialize analyzer with log file

        Args:
            log_file: Path to trader_YYYYMMDD.log
        """
        self.log_file = Path(log_file)
        self.log_lines = self._load_log()

        # Parsed data
        self.filter_blocks = defaultdict(int)
        self.blocked_symbols = defaultdict(list)
        self.filter_details = defaultdict(list)

    def _load_log(self):
        """Load log file"""
        if not self.log_file.exists():
            print(f"⚠️  Log file not found: {self.log_file}")
            return []

        with open(self.log_file, 'r') as f:
            return f.readlines()

    def analyze(self):
        """Run filter analysis"""
        print(f"\n{'='*80}")
        print(f"FILTER EFFECTIVENESS ANALYSIS")
        print(f"{'='*80}")

        self._parse_blocks()
        self._analyze_block_patterns()
        self._analyze_by_symbol()
        self._recommend_adjustments()

    def _parse_blocks(self):
        """Parse all blocked trades from log"""
        for i, line in enumerate(self.log_lines):
            if '❌' in line and 'blocked' in line.lower():
                # Extract symbol
                symbol_match = re.search(r'([A-Z]{1,5}):', line)
                symbol = symbol_match.group(1) if symbol_match else 'UNKNOWN'

                # Extract block reason
                if ' - ' in line:
                    parts = line.split(' - ')
                    reason = parts[1].strip() if len(parts) > 1 else 'UNKNOWN'

                    # Clean up reason
                    reason = reason.split('(')[0].strip()

                    # Store
                    self.filter_blocks[reason] += 1
                    self.blocked_symbols[symbol].append(reason)
                    self.filter_details[reason].append({
                        'symbol': symbol,
                        'line_num': i,
                        'full_line': line.strip()
                    })

    def _analyze_block_patterns(self):
        """Analyze overall blocking patterns"""
        print(f"\n🎯 FILTER BLOCKING SUMMARY")
        print(f"{'-'*80}")

        if not self.filter_blocks:
            print("⚠️  No filter blocks detected")
            print("   This is unusual - verify filters are configured correctly")
            return

        total_blocks = sum(self.filter_blocks.values())
        print(f"Total Blocks: {total_blocks}\n")

        print(f"{'Filter Reason':<50} {'Count':>8} {'%':>7} {'Action'}")
        print(f"{'-'*80}")

        for reason, count in sorted(self.filter_blocks.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total_blocks) * 100

            # Determine if filter is working correctly
            action = self._get_filter_action(reason, count, total_blocks)

            print(f"{reason[:48]:<50} {count:>8} {pct:>6.1f}% {action}")

    def _get_filter_action(self, reason, count, total):
        """Determine recommended action for filter"""
        pct = (count / total) * 100

        # High-frequency blocks (>30%)
        if pct > 30:
            if 'Max attempts' in reason:
                return "✓ GOOD"
            elif 'choppy' in reason.lower():
                return "✓ GOOD"
            elif 'Position too large' in reason:
                return "⚠️  FIX SIZING"
            elif 'Waiting' in reason:
                return "⚠️  TOO STRICT?"
            else:
                return "⚠️  REVIEW"

        # Medium-frequency blocks (10-30%)
        elif pct > 10:
            if any(x in reason.lower() for x in ['gap', 'room', 'choppy']):
                return "✓ GOOD"
            else:
                return "→ MONITOR"

        # Low-frequency blocks (<10%)
        else:
            return "→ OK"

    def _analyze_by_symbol(self):
        """Analyze which symbols get blocked most"""
        print(f"\n📊 MOST BLOCKED SYMBOLS")
        print(f"{'-'*80}")

        # Count blocks per symbol
        symbol_counts = {sym: len(reasons) for sym, reasons in self.blocked_symbols.items()}

        # Sort by count
        sorted_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        print(f"\n{'Symbol':<8} {'Blocks':>8} {'Top Reason'}")
        print(f"{'-'*50}")

        for symbol, count in sorted_symbols:
            # Find most common reason for this symbol
            reason_counts = defaultdict(int)
            for reason in self.blocked_symbols[symbol]:
                reason_counts[reason] += 1

            top_reason = max(reason_counts.items(), key=lambda x: x[1])[0]
            top_reason_short = top_reason[:30] + '...' if len(top_reason) > 30 else top_reason

            print(f"{symbol:<8} {count:>8} {top_reason_short}")

    def _recommend_adjustments(self):
        """Recommend filter threshold adjustments"""
        print(f"\n💡 RECOMMENDED ADJUSTMENTS")
        print(f"{'-'*80}")

        recommendations = []

        # Check for over-filtering
        total_blocks = sum(self.filter_blocks.values())

        for reason, count in self.filter_blocks.items():
            pct = (count / total_blocks) * 100

            # Position too large
            if 'Position too large' in reason and pct > 10:
                recommendations.append({
                    'priority': 'HIGH',
                    'filter': 'Position Sizing',
                    'issue': f'{count} trades blocked ({pct:.1f}%)',
                    'action': 'Implement adaptive position sizing (max_position_value)',
                    'impact': f'Could capture ${count * 50:.0f} - ${count * 150:.0f} additional profit'
                })

            # Choppy market filter blocking too much
            if 'choppy' in reason.lower() and pct > 40:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'filter': 'Choppy Market Filter',
                    'issue': f'{count} trades blocked ({pct:.1f}%)',
                    'action': 'Consider lowering choppy_atr_multiplier from 0.5 to 0.4',
                    'impact': 'Allow more trades in moderate consolidation'
                })

            # Waiting for confirmation
            if 'Waiting' in reason and pct > 25:
                recommendations.append({
                    'priority': 'LOW',
                    'filter': 'Confirmation Logic',
                    'issue': f'{count} confirmations pending ({pct:.1f}%)',
                    'action': 'This is normal - confirmation logic is working',
                    'impact': 'Protects from false breakouts'
                })

            # Room to target
            if 'room' in reason.lower() and pct > 20:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'filter': 'Room to Target',
                    'issue': f'{count} trades blocked ({pct:.1f}%)',
                    'action': 'Consider lowering min_room_to_target_pct from 1.5% to 1.0%',
                    'impact': 'Allow trades with smaller targets'
                })

            # Max attempts
            if 'Max attempts' in reason and pct > 35:
                recommendations.append({
                    'priority': 'LOW',
                    'filter': 'Max Attempts',
                    'issue': f'{count} stocks whipsawed ({pct:.1f}%)',
                    'action': 'No change needed - filter preventing losses',
                    'impact': f'Saved ~${count * 100:.0f} in whipsaw losses'
                })

        # Print recommendations
        if not recommendations:
            print("\n✓ No adjustments recommended - filters working as expected")
            return

        recommendations.sort(key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}[x['priority']])

        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. [{rec['priority']}] {rec['filter']}")
            print(f"   Issue: {rec['issue']}")
            print(f"   Action: {rec['action']}")
            print(f"   Impact: {rec['impact']}")

    def get_blocked_trades(self, filter_name):
        """Get list of all trades blocked by specific filter"""
        return self.filter_details.get(filter_name, [])


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python filter_analyzer.py trader_YYYYMMDD.log")
        print("Example: python filter_analyzer.py logs/trader_20251007.log")
        sys.exit(1)

    log_file = sys.argv[1]

    analyzer = FilterEffectivenessAnalyzer(log_file)
    analyzer.analyze()
