#!/usr/bin/env python3
"""
Scanner Quality Analyzer

Compares scanner predictions vs actual market outcomes:
- Did predicted breakouts actually break?
- Which scanner scores correlate with success?
- Pivot width vs success rate
- Test count impact on reliability
"""

import json
import pandas as pd
from pathlib import Path
from collections import defaultdict


class ScannerQualityAnalyzer:
    """
    Analyzes scanner prediction accuracy

    Validates:
    - Resistance/support predictions
    - Enhanced scoring effectiveness
    - Tier classification accuracy
    - Pivot quality metrics
    """

    def __init__(self, scanner_file, trades_file, log_file=None):
        """
        Initialize analyzer

        Args:
            scanner_file: Path to scanner results JSON or enhanced scoring CSV
            trades_file: Path to trades JSON
            log_file: Optional log file for additional context
        """
        self.scanner_file = Path(scanner_file)
        self.trades_file = Path(trades_file)
        self.log_file = Path(log_file) if log_file else None

        # Load data
        self.scanner_data = self._load_scanner()
        self.trades = self._load_trades()

    def _load_scanner(self):
        """Load scanner results"""
        if not self.scanner_file.exists():
            print(f"⚠️  Scanner file not found: {self.scanner_file}")
            return []

        # Check if CSV (enhanced scoring) or JSON (standard scanner)
        if self.scanner_file.suffix == '.csv':
            df = pd.read_csv(self.scanner_file)
            return df.to_dict('records')
        else:
            with open(self.scanner_file, 'r') as f:
                return json.load(f)

    def _load_trades(self):
        """Load trades"""
        if not self.trades_file.exists():
            print(f"⚠️  Trades file not found: {self.trades_file}")
            return []

        with open(self.trades_file, 'r') as f:
            return json.load(f)

    def analyze(self):
        """Run scanner quality analysis"""
        print(f"\n{'='*80}")
        print(f"SCANNER PREDICTION QUALITY ANALYSIS")
        print(f"{'='*80}")

        if not self.scanner_data:
            print("\n⚠️  No scanner data to analyze")
            return

        self._analyze_traded_symbols()
        self._analyze_tier_performance()
        self._analyze_pivot_width()
        self._analyze_scoring_correlation()

    def _analyze_traded_symbols(self):
        """Analyze which scanner symbols were traded"""
        print(f"\n📊 SCANNER COVERAGE ANALYSIS")
        print(f"{'-'*80}")

        total_scanned = len(self.scanner_data)
        traded_symbols = set(t['symbol'] for t in self.trades)

        # Find which scanned symbols were traded
        scanned_symbols = set(s['symbol'] for s in self.scanner_data)
        traded_from_scanner = traded_symbols & scanned_symbols

        coverage_pct = (len(traded_from_scanner) / total_scanned * 100) if total_scanned > 0 else 0

        print(f"Total Scanned Symbols: {total_scanned}")
        print(f"Symbols Traded: {len(traded_symbols)}")
        print(f"Traded from Scanner: {len(traded_from_scanner)} ({coverage_pct:.1f}% coverage)")

        # Symbols traded but not in scanner
        not_in_scanner = traded_symbols - scanned_symbols
        if not_in_scanner:
            print(f"\n⚠️  Symbols traded but NOT in scanner: {', '.join(sorted(not_in_scanner))}")
            print(f"   → These should not have been traded (watchlist issue?)")

        # Top scanner symbols that were NOT traded
        print(f"\nTop 10 Scanner Symbols NOT Traded:")

        # Sort by score or enhanced_score
        score_key = 'enhanced_score' if 'enhanced_score' in self.scanner_data[0] else 'score'

        untapped = [s for s in self.scanner_data if s['symbol'] not in traded_symbols]
        untapped_sorted = sorted(untapped, key=lambda x: x.get(score_key, 0), reverse=True)[:10]

        for stock in untapped_sorted:
            symbol = stock['symbol']
            score = stock.get(score_key, 0)
            tier = stock.get('tier', 'N/A')
            reason = stock.get('notes', 'Unknown')

            print(f"  {symbol:<6} (Score: {score:>3}, Tier: {tier}) - {reason[:40]}")

    def _analyze_tier_performance(self):
        """Analyze performance by scanner tier"""
        print(f"\n🎯 TIER PERFORMANCE ANALYSIS")
        print(f"{'-'*80}")

        # Check if enhanced scoring data exists
        if 'tier' not in self.scanner_data[0]:
            print("⚠️  No tier data in scanner results (using standard scanner)")
            return

        # Build tier -> trades mapping
        tier_trades = defaultdict(list)

        for trade in self.trades:
            symbol = trade['symbol']

            # Find scanner data for this symbol
            scanner_match = next((s for s in self.scanner_data if s['symbol'] == symbol), None)

            if scanner_match:
                tier = scanner_match.get('tier', 'UNKNOWN')
                tier_trades[tier].append(trade)

        # Calculate stats per tier
        print(f"\n{'Tier':<10} {'Trades':>7} {'Win%':>6} {'Avg P&L':>10} {'Total P&L':>12}")
        print(f"{'-'*50}")

        for tier in ['TIER 1', 'TIER 2', 'TIER 3', 'AVOID', 'UNKNOWN']:
            if tier not in tier_trades:
                continue

            trades = tier_trades[tier]
            count = len(trades)
            winners = sum(1 for t in trades if t['pnl'] > 0)
            win_rate = (winners / count * 100) if count > 0 else 0
            avg_pnl = sum(t['pnl'] for t in trades) / count if count > 0 else 0
            total_pnl = sum(t['pnl'] for t in trades)

            print(f"{tier:<10} {count:>7} {win_rate:>5.1f}% ${avg_pnl:>8.2f} ${total_pnl:>10.2f}")

        # Validation
        tier1_trades = tier_trades.get('TIER 1', [])
        if tier1_trades:
            tier1_winners = sum(1 for t in tier1_trades if t['pnl'] > 0)
            tier1_win_rate = (tier1_winners / len(tier1_trades) * 100)

            print(f"\n📈 TIER 1 Validation:")
            print(f"   Expected: 70-80% win rate")
            print(f"   Actual: {tier1_win_rate:.1f}%")

            if tier1_win_rate >= 70:
                print(f"   ✓ TIER 1 classification is ACCURATE")
            elif tier1_win_rate >= 60:
                print(f"   → TIER 1 classification is ACCEPTABLE (close to target)")
            else:
                print(f"   ⚠️  TIER 1 classification needs IMPROVEMENT")

    def _analyze_pivot_width(self):
        """Analyze correlation between pivot width and success"""
        print(f"\n📏 PIVOT WIDTH ANALYSIS")
        print(f"{'-'*80}")

        # Check if pivot width data exists
        if 'pivot_width_pct' not in self.scanner_data[0]:
            print("⚠️  No pivot width data in scanner results")
            return

        # Bucket pivot widths
        buckets = [0, 1.0, 2.0, 3.0, 5.0, 10.0, 100.0]
        labels = ['<1%', '1-2%', '2-3%', '3-5%', '5-10%', '>10%']

        # Map trades to pivot widths
        trades_with_width = []

        for trade in self.trades:
            symbol = trade['symbol']
            scanner_match = next((s for s in self.scanner_data if s['symbol'] == symbol), None)

            if scanner_match and 'pivot_width_pct' in scanner_match:
                width = scanner_match['pivot_width_pct']
                trades_with_width.append({
                    'symbol': symbol,
                    'width': width,
                    'pnl': trade['pnl'],
                    'winner': trade['pnl'] > 0
                })

        if not trades_with_width:
            print("No trades with pivot width data")
            return

        df = pd.DataFrame(trades_with_width)
        df['width_bucket'] = pd.cut(df['width'], bins=buckets, labels=labels, include_lowest=True)

        # Stats by bucket
        bucket_stats = df.groupby('width_bucket', observed=True).agg({
            'pnl': ['count', 'mean'],
            'winner': 'mean'
        })

        print(f"\n{'Pivot Width':<12} {'Trades':>7} {'Win%':>6} {'Avg P&L':>10}")
        print(f"{'-'*40}")

        for bucket in bucket_stats.index:
            count = int(bucket_stats.loc[bucket, ('pnl', 'count')])
            avg_pnl = bucket_stats.loc[bucket, ('pnl', 'mean')]
            win_rate = bucket_stats.loc[bucket, ('winner', 'mean')] * 100

            print(f"{bucket:<12} {count:>7} {win_rate:>5.1f}% ${avg_pnl:>8.2f}")

        # Key finding
        narrow_pivots = df[df['width'] <= 2.5]
        wide_pivots = df[df['width'] > 2.5]

        if len(narrow_pivots) > 0 and len(wide_pivots) > 0:
            narrow_win = (narrow_pivots['winner'].sum() / len(narrow_pivots)) * 100
            wide_win = (wide_pivots['winner'].sum() / len(wide_pivots)) * 100

            print(f"\n📊 Key Finding:")
            print(f"   Tight Pivots (≤2.5%): {narrow_win:.1f}% win rate")
            print(f"   Wide Pivots (>2.5%): {wide_win:.1f}% win rate")

            if narrow_win > wide_win + 15:
                print(f"   ✓ Pivot width filter is EFFECTIVE - keep max at 5%")
            else:
                print(f"   → Pivot width impact is MODERATE")

    def _analyze_scoring_correlation(self):
        """Analyze correlation between score and outcomes"""
        print(f"\n🎯 SCORING CORRELATION ANALYSIS")
        print(f"{'-'*80}")

        # Check which scoring system exists
        score_key = 'enhanced_score' if 'enhanced_score' in self.scanner_data[0] else 'score'

        # Map trades to scores
        trades_with_scores = []

        for trade in self.trades:
            symbol = trade['symbol']
            scanner_match = next((s for s in self.scanner_data if s['symbol'] == symbol), None)

            if scanner_match and score_key in scanner_match:
                score = scanner_match[score_key]
                trades_with_scores.append({
                    'symbol': symbol,
                    'score': score,
                    'pnl': trade['pnl'],
                    'winner': trade['pnl'] > 0
                })

        if not trades_with_scores:
            print("No trades with scoring data")
            return

        df = pd.DataFrame(trades_with_scores)

        # Bucket by score
        if score_key == 'enhanced_score':
            buckets = [0, 70, 85, 100, 150]
            labels = ['<70', '70-85', '85-100', '>100']
        else:
            buckets = [0, 50, 70, 85, 100]
            labels = ['<50', '50-70', '70-85', '>85']

        df['score_bucket'] = pd.cut(df['score'], bins=buckets, labels=labels, include_lowest=True)

        # Stats by bucket
        bucket_stats = df.groupby('score_bucket', observed=True).agg({
            'pnl': ['count', 'mean'],
            'winner': 'mean'
        })

        print(f"\n{'Score Range':<12} {'Trades':>7} {'Win%':>6} {'Avg P&L':>10}")
        print(f"{'-'*40}")

        for bucket in bucket_stats.index:
            count = int(bucket_stats.loc[bucket, ('pnl', 'count')])
            avg_pnl = bucket_stats.loc[bucket, ('pnl', 'mean')]
            win_rate = bucket_stats.loc[bucket, ('winner', 'mean')] * 100

            print(f"{bucket:<12} {count:>7} {win_rate:>5.1f}% ${avg_pnl:>8.2f}")

        # Correlation check
        correlation = df['score'].corr(df['pnl'])

        print(f"\n📊 Score-P&L Correlation: {correlation:.3f}")

        if correlation > 0.3:
            print(f"   ✓ STRONG positive correlation - scoring system is WORKING")
        elif correlation > 0.1:
            print(f"   → MODERATE correlation - scoring system has some value")
        else:
            print(f"   ⚠️  WEAK correlation - scoring system needs improvement")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("Usage: python scanner_analyzer.py scanner_results.json trades_YYYYMMDD.json")
        print("Example: python scanner_analyzer.py ../stockscanner/output/rescored_20251007.csv logs/trades_20251007.json")
        sys.exit(1)

    scanner_file = sys.argv[1]
    trades_file = sys.argv[2]

    analyzer = ScannerQualityAnalyzer(scanner_file, trades_file)
    analyzer.analyze()
