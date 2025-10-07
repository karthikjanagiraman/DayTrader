#!/usr/bin/env python3
"""
Scanner Validation Metrics Analyzer

Analyzes validation CSV to extract patterns and create improved scoring system.
This script learns from actual market outcomes to improve scanner predictions.

Usage:
    python analyze_validation_metrics.py validation_20251006.csv
"""

import csv
import json
import sys
from pathlib import Path
from collections import defaultdict
import statistics

class ValidationMetricsAnalyzer:
    """Analyzes validation results to improve scanner scoring"""

    def __init__(self, validation_csv):
        self.validation_csv = validation_csv
        self.data = []
        self.successes = []
        self.false_breakouts = []
        self.no_breakouts = []
        self.metrics = {}

    def load_validation_data(self):
        """Load validation CSV"""
        with open(self.validation_csv, 'r') as f:
            reader = csv.DictReader(f)
            self.data = list(reader)

        print(f"✓ Loaded {len(self.data)} validation records\n")

    def categorize_outcomes(self):
        """Categorize stocks by outcome"""
        for row in self.data:
            symbol = row['Symbol']

            # Process LONG outcomes
            if row.get('Long Breakout?') == 'Yes':
                outcome = row['Long Outcome']

                record = {
                    'symbol': symbol,
                    'side': 'LONG',
                    'resistance': float(row['Resistance']) if row['Resistance'] else None,
                    'support': float(row['Support']) if row['Support'] else None,
                    'day_high': float(row['Day High']) if row['Day High'] else None,
                    'day_low': float(row['Day Low']) if row['Day Low'] else None,
                    'day_close': float(row['Day Close']) if row['Day Close'] else None,
                    'outcome': outcome,
                    'reason': row.get('Long Reason', '')
                }

                # Calculate pivot width
                if record['resistance'] and record['support']:
                    record['pivot_width'] = record['resistance'] - record['support']
                    record['pivot_width_pct'] = (record['pivot_width'] / record['support']) * 100

                # Calculate actual move
                if record['resistance'] and record['day_high']:
                    record['move_pct'] = ((record['day_high'] - record['resistance']) / record['resistance']) * 100

                # Calculate reversal (if false breakout)
                if outcome == 'FALSE_BREAKOUT' and record['day_close'] and record['resistance']:
                    record['reversal_pct'] = ((record['resistance'] - record['day_close']) / record['resistance']) * 100

                if outcome == 'SUCCESS':
                    self.successes.append(record)
                elif outcome == 'FALSE_BREAKOUT':
                    self.false_breakouts.append(record)

            # Process SHORT outcomes
            if row.get('Short Breakout?') == 'Yes':
                outcome = row['Short Outcome']

                record = {
                    'symbol': symbol,
                    'side': 'SHORT',
                    'resistance': float(row['Resistance']) if row['Resistance'] else None,
                    'support': float(row['Support']) if row['Support'] else None,
                    'day_high': float(row['Day High']) if row['Day High'] else None,
                    'day_low': float(row['Day Low']) if row['Day Low'] else None,
                    'day_close': float(row['Day Close']) if row['Day Close'] else None,
                    'outcome': outcome,
                    'reason': row.get('Short Reason', '')
                }

                # Calculate pivot width
                if record['resistance'] and record['support']:
                    record['pivot_width'] = record['resistance'] - record['support']
                    record['pivot_width_pct'] = (record['pivot_width'] / record['support']) * 100

                # Calculate actual move
                if record['support'] and record['day_low']:
                    record['move_pct'] = ((record['support'] - record['day_low']) / record['support']) * 100

                # Calculate reversal (if false breakout)
                if outcome == 'FALSE_BREAKOUT' and record['day_close'] and record['support']:
                    record['reversal_pct'] = ((record['day_close'] - record['support']) / record['support']) * 100

                if outcome == 'SUCCESS':
                    self.successes.append(record)
                elif outcome == 'FALSE_BREAKOUT':
                    self.false_breakouts.append(record)

            # Track stocks that didn't break out
            if row.get('Long Breakout?') == 'No' and row.get('Short Breakout?') == 'No':
                self.no_breakouts.append({
                    'symbol': symbol,
                    'resistance': float(row['Resistance']) if row['Resistance'] else None,
                    'support': float(row['Support']) if row['Support'] else None,
                })

        print(f"Categorized outcomes:")
        print(f"  Successes: {len(self.successes)}")
        print(f"  False Breakouts: {len(self.false_breakouts)}")
        print(f"  No Breakouts: {len(self.no_breakouts)}\n")

    def analyze_success_patterns(self):
        """Analyze what makes a successful setup"""
        print("="*80)
        print("SUCCESS PATTERN ANALYSIS")
        print("="*80)

        if not self.successes:
            print("No successful setups to analyze\n")
            return

        # Analyze pivot width
        pivot_widths = [s['pivot_width_pct'] for s in self.successes if 'pivot_width_pct' in s]
        if pivot_widths:
            print(f"\nPivot Width (R-S as % of price):")
            print(f"  Average: {statistics.mean(pivot_widths):.2f}%")
            print(f"  Median: {statistics.median(pivot_widths):.2f}%")
            print(f"  Range: {min(pivot_widths):.2f}% - {max(pivot_widths):.2f}%")

        # Analyze move size
        moves = [s['move_pct'] for s in self.successes if 'move_pct' in s]
        if moves:
            print(f"\nActual Move Size (beyond pivot):")
            print(f"  Average: {statistics.mean(moves):.2f}%")
            print(f"  Median: {statistics.median(moves):.2f}%")
            print(f"  Best: {max(moves):.2f}% ({[s['symbol'] for s in self.successes if s.get('move_pct') == max(moves)][0]})")
            print(f"  Smallest: {min(moves):.2f}%")

        # Analyze by side
        long_successes = [s for s in self.successes if s['side'] == 'LONG']
        short_successes = [s for s in self.successes if s['side'] == 'SHORT']

        print(f"\nBy Direction:")
        print(f"  LONG: {len(long_successes)} ({len(long_successes)/len(self.successes)*100:.1f}%)")
        print(f"  SHORT: {len(short_successes)} ({len(short_successes)/len(self.successes)*100:.1f}%)")

        # Show best performers
        print(f"\nBest Performers (by move %):")
        sorted_successes = sorted([s for s in self.successes if 'move_pct' in s],
                                  key=lambda x: x['move_pct'], reverse=True)[:5]
        for s in sorted_successes:
            print(f"  {s['symbol']:6} {s['side']:5} - {s['move_pct']:+.2f}%")

    def analyze_false_breakout_patterns(self):
        """Analyze what causes false breakouts"""
        print("\n" + "="*80)
        print("FALSE BREAKOUT PATTERN ANALYSIS")
        print("="*80)

        if not self.false_breakouts:
            print("No false breakouts to analyze\n")
            return

        # Analyze pivot width for false breakouts
        pivot_widths = [s['pivot_width_pct'] for s in self.false_breakouts if 'pivot_width_pct' in s]
        if pivot_widths:
            print(f"\nPivot Width (R-S as % of price):")
            print(f"  Average: {statistics.mean(pivot_widths):.2f}%")
            print(f"  Median: {statistics.median(pivot_widths):.2f}%")
            print(f"  Range: {min(pivot_widths):.2f}% - {max(pivot_widths):.2f}%")

        # Analyze reversal magnitude
        reversals = [s['reversal_pct'] for s in self.false_breakouts if 'reversal_pct' in s]
        if reversals:
            print(f"\nReversal Magnitude (back through pivot):")
            print(f"  Average: {statistics.mean(reversals):.2f}%")
            print(f"  Median: {statistics.median(reversals):.2f}%")
            print(f"  Worst: {max(reversals):.2f}%")

        # Identify common symbols (indices, high-vol stocks)
        index_symbols = ['SPY', 'QQQ', 'DIA', 'IWM']
        high_vol_symbols = ['TSLA', 'NVDA', 'COIN', 'AMC', 'GME']

        index_false = [s for s in self.false_breakouts if s['symbol'] in index_symbols]
        high_vol_false = [s for s in self.false_breakouts if s['symbol'] in high_vol_symbols]

        print(f"\nCommon Culprits:")
        print(f"  Index ETFs (SPY, QQQ, etc.): {len(index_false)} / {len(self.false_breakouts)} ({len(index_false)/len(self.false_breakouts)*100:.1f}%)")
        print(f"  High-vol stocks (TSLA, COIN, etc.): {len(high_vol_false)} / {len(self.false_breakouts)} ({len(high_vol_false)/len(self.false_breakouts)*100:.1f}%)")

        # Show worst false breakouts
        print(f"\nWorst False Breakouts (by reversal):")
        sorted_false = sorted([s for s in self.false_breakouts if 'reversal_pct' in s],
                             key=lambda x: x['reversal_pct'], reverse=True)[:5]
        for s in sorted_false:
            print(f"  {s['symbol']:6} {s['side']:5} - Reversed {s['reversal_pct']:.2f}%")

    def compare_success_vs_false(self):
        """Compare characteristics of successes vs false breakouts"""
        print("\n" + "="*80)
        print("SUCCESS vs FALSE BREAKOUT COMPARISON")
        print("="*80)

        success_pivot_widths = [s['pivot_width_pct'] for s in self.successes if 'pivot_width_pct' in s]
        false_pivot_widths = [s['pivot_width_pct'] for s in self.false_breakouts if 'pivot_width_pct' in s]

        print(f"\nPivot Width Comparison:")
        if success_pivot_widths:
            print(f"  Successes: {statistics.mean(success_pivot_widths):.2f}% avg (median {statistics.median(success_pivot_widths):.2f}%)")
        if false_pivot_widths:
            print(f"  False Breakouts: {statistics.mean(false_pivot_widths):.2f}% avg (median {statistics.median(false_pivot_widths):.2f}%)")

        # Key insight
        if success_pivot_widths and false_pivot_widths:
            if statistics.mean(false_pivot_widths) < statistics.mean(success_pivot_widths):
                print(f"\n  ⚠️  KEY INSIGHT: False breakouts have TIGHTER pivot ranges!")
                print(f"     Avoid setups with pivot width < {statistics.mean(false_pivot_widths):.2f}%")
            elif statistics.mean(false_pivot_widths) > statistics.mean(success_pivot_widths):
                print(f"\n  ⚠️  KEY INSIGHT: False breakouts have WIDER pivot ranges!")
                print(f"     Prefer setups with pivot width < {statistics.mean(success_pivot_widths):.2f}%")

    def generate_scoring_recommendations(self):
        """Generate scoring recommendations based on validation data"""
        print("\n" + "="*80)
        print("SCORING RECOMMENDATIONS")
        print("="*80)

        recommendations = []

        # 1. Success rate by direction
        long_success_count = len([s for s in self.successes if s['side'] == 'LONG'])
        long_total = long_success_count + len([s for s in self.false_breakouts if s['side'] == 'LONG'])

        short_success_count = len([s for s in self.successes if s['side'] == 'SHORT'])
        short_total = short_success_count + len([s for s in self.false_breakouts if s['side'] == 'SHORT'])

        if long_total > 0:
            long_success_rate = long_success_count / long_total
            print(f"\n1. LONG Success Rate: {long_success_rate*100:.1f}% ({long_success_count}/{long_total})")
            if long_success_rate < 0.30:
                recommendations.append({
                    'rule': 'REDUCE LONG SCORING',
                    'reason': f'LONG success rate only {long_success_rate*100:.1f}%',
                    'action': 'Reduce LONG setup scores by 20 points'
                })
            elif long_success_rate > 0.45:
                recommendations.append({
                    'rule': 'INCREASE LONG SCORING',
                    'reason': f'LONG success rate {long_success_rate*100:.1f}%',
                    'action': 'Increase LONG setup scores by 10 points'
                })

        if short_total > 0:
            short_success_rate = short_success_count / short_total
            print(f"2. SHORT Success Rate: {short_success_rate*100:.1f}% ({short_success_count}/{short_total})")
            if short_success_rate < 0.25:
                recommendations.append({
                    'rule': 'REDUCE SHORT SCORING',
                    'reason': f'SHORT success rate only {short_success_rate*100:.1f}%',
                    'action': 'Reduce SHORT setup scores by 30 points or DISABLE SHORTS'
                })

        # 2. Pivot width recommendations
        success_pivot_widths = [s['pivot_width_pct'] for s in self.successes if 'pivot_width_pct' in s]
        false_pivot_widths = [s['pivot_width_pct'] for s in self.false_breakouts if 'pivot_width_pct' in s]

        if success_pivot_widths and false_pivot_widths:
            success_median = statistics.median(success_pivot_widths)
            false_median = statistics.median(false_pivot_widths)

            print(f"\n3. Pivot Width:")
            print(f"   Successes: {success_median:.2f}% median")
            print(f"   False Breakouts: {false_median:.2f}% median")

            if false_median < success_median * 0.7:
                # False breakouts have much tighter pivots
                recommendations.append({
                    'rule': 'PENALIZE TIGHT PIVOTS',
                    'reason': f'Tight pivots (<{false_median:.2f}%) correlate with false breakouts',
                    'action': f'Reduce score by 20 points if pivot_width_pct < {false_median:.2f}%'
                })
            elif false_median > success_median * 1.3:
                # False breakouts have much wider pivots
                recommendations.append({
                    'rule': 'PENALIZE WIDE PIVOTS',
                    'reason': f'Wide pivots (>{false_median:.2f}%) correlate with false breakouts',
                    'action': f'Reduce score by 15 points if pivot_width_pct > {false_median:.2f}%'
                })

        # 3. Index ETF recommendation
        index_false = len([s for s in self.false_breakouts if s['symbol'] in ['SPY', 'QQQ', 'DIA', 'IWM']])
        index_success = len([s for s in self.successes if s['symbol'] in ['SPY', 'QQQ', 'DIA', 'IWM']])

        if index_false > 0 and index_success == 0:
            print(f"\n4. Index ETFs: {index_false} false breakouts, {index_success} successes")
            recommendations.append({
                'rule': 'PENALIZE INDEX ETFS',
                'reason': 'Index ETFs had 100% false breakout rate',
                'action': 'Reduce score by 40 points for SPY, QQQ, DIA, IWM'
            })

        # 4. High-volatility stocks
        high_vol = ['TSLA', 'NVDA', 'COIN', 'AMC', 'GME', 'HOOD']
        highvol_false = len([s for s in self.false_breakouts if s['symbol'] in high_vol])
        highvol_success = len([s for s in self.successes if s['symbol'] in high_vol])

        if highvol_false > highvol_success:
            print(f"\n5. High-Vol Stocks: {highvol_false} false breakouts, {highvol_success} successes")
            recommendations.append({
                'rule': 'PENALIZE HIGH-VOL STOCKS',
                'reason': f'High-vol stocks (TSLA, COIN, etc.) had {highvol_false} false breakouts vs {highvol_success} successes',
                'action': 'Reduce score by 25 points for known high-vol tickers'
            })

        # Print all recommendations
        print("\n" + "="*80)
        print("RECOMMENDED SCORING CHANGES:")
        print("="*80)

        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['rule']}")
            print(f"   Reason: {rec['reason']}")
            print(f"   Action: {rec['action']}")

        return recommendations

    def generate_summary_report(self):
        """Generate comprehensive summary"""
        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)

        total_breakouts = len(self.successes) + len(self.false_breakouts)

        print(f"\nTotal Stocks Validated: {len(self.data)}")
        print(f"  Breakouts Occurred: {total_breakouts}")
        print(f"  No Breakouts: {len(self.no_breakouts)}")
        print(f"  Breakout Rate: {total_breakouts/len(self.data)*100:.1f}%")

        if total_breakouts > 0:
            print(f"\nBreakout Outcomes:")
            print(f"  SUCCESS: {len(self.successes)} ({len(self.successes)/total_breakouts*100:.1f}%)")
            print(f"  FALSE BREAKOUT: {len(self.false_breakouts)} ({len(self.false_breakouts)/total_breakouts*100:.1f}%)")

        # Overall success rate
        if total_breakouts > 0:
            success_rate = len(self.successes) / total_breakouts
            print(f"\n{'='*80}")
            print(f"OVERALL SUCCESS RATE: {success_rate*100:.1f}%")
            print(f"{'='*80}")

            if success_rate >= 0.35:
                print("\n✓ EXCELLENT - Scanner is performing well!")
            elif success_rate >= 0.25:
                print("\n≈ GOOD - Scanner is acceptable, room for improvement")
            else:
                print("\n⚠️  NEEDS IMPROVEMENT - Success rate below 25%")

        # Save metrics for programmatic use
        self.metrics = {
            'total_stocks': len(self.data),
            'total_breakouts': total_breakouts,
            'successes': len(self.successes),
            'false_breakouts': len(self.false_breakouts),
            'success_rate': len(self.successes) / total_breakouts if total_breakouts > 0 else 0,
            'long_success_rate': len([s for s in self.successes if s['side'] == 'LONG']) / len([s for s in self.successes + self.false_breakouts if s['side'] == 'LONG']) if len([s for s in self.successes + self.false_breakouts if s['side'] == 'LONG']) > 0 else 0,
            'short_success_rate': len([s for s in self.successes if s['side'] == 'SHORT']) / len([s for s in self.successes + self.false_breakouts if s['side'] == 'SHORT']) if len([s for s in self.successes + self.false_breakouts if s['side'] == 'SHORT']) > 0 else 0,
        }

    def save_metrics_json(self, output_file='validation_metrics.json'):
        """Save metrics to JSON for use by scanner"""
        output = {
            'date': Path(self.validation_csv).stem.replace('validation_', ''),
            'metrics': self.metrics,
            'successes': self.successes,
            'false_breakouts': self.false_breakouts,
        }

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2, default=str)

        print(f"\n✓ Metrics saved to: {output_file}")

    def run_full_analysis(self):
        """Run complete analysis"""
        self.load_validation_data()
        self.categorize_outcomes()
        self.analyze_success_patterns()
        self.analyze_false_breakout_patterns()
        self.compare_success_vs_false()
        recommendations = self.generate_scoring_recommendations()
        self.generate_summary_report()
        self.save_metrics_json()

        return recommendations

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_validation_metrics.py <validation_csv>")
        print("Example: python analyze_validation_metrics.py validation_20251006.csv")
        sys.exit(1)

    validation_csv = sys.argv[1]

    analyzer = ValidationMetricsAnalyzer(validation_csv)
    analyzer.run_full_analysis()

if __name__ == '__main__':
    main()
