#!/usr/bin/env python3
"""
Compare Enhanced Scoring Accuracy

Compares enhanced scores against actual validation outcomes
to measure predictive accuracy.
"""

import csv
import json
import sys

def load_validation_outcomes(validation_csv):
    """Load actual outcomes from validation"""
    outcomes = {}

    with open(validation_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row['Symbol']

            # Track LONG outcome
            if row['Long Breakout?'] == 'Yes':
                outcomes[f"{symbol}_LONG"] = {
                    'symbol': symbol,
                    'side': 'LONG',
                    'outcome': row['Long Outcome'],
                    'is_success': row['Long Outcome'] == 'SUCCESS',
                    'is_false': row['Long Outcome'] == 'FALSE_BREAKOUT'
                }

            # Track SHORT outcome
            if row['Short Breakout?'] == 'Yes':
                outcomes[f"{symbol}_SHORT"] = {
                    'symbol': symbol,
                    'side': 'SHORT',
                    'outcome': row['Short Outcome'],
                    'is_success': row['Short Outcome'] == 'SUCCESS',
                    'is_false': row['Short Outcome'] == 'FALSE_BREAKOUT'
                }

    return outcomes

def load_enhanced_scores(rescored_csv):
    """Load enhanced scores"""
    scores = {}

    with open(rescored_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row.get('symbol', row.get('Symbol', ''))

            scores[f"{symbol}_LONG"] = {
                'symbol': symbol,
                'side': 'LONG',
                'score': float(row['enhanced_long_score']),
                'recommendation': row['long_recommendation'],
                'pivot_width_pct': float(row['pivot_width_pct'])
            }

            scores[f"{symbol}_SHORT"] = {
                'symbol': symbol,
                'side': 'SHORT',
                'score': float(row['enhanced_short_score']),
                'recommendation': row['short_recommendation'],
                'pivot_width_pct': float(row['pivot_width_pct'])
            }

    return scores

def compare_accuracy(outcomes, scores):
    """Compare scoring accuracy"""
    print("="*80)
    print("ENHANCED SCORING ACCURACY ANALYSIS")
    print("="*80)

    # Match outcomes with scores
    matches = []

    for key, outcome in outcomes.items():
        if key in scores:
            matches.append({
                'symbol': outcome['symbol'],
                'side': outcome['side'],
                'outcome': outcome['outcome'],
                'is_success': outcome['is_success'],
                'is_false': outcome['is_false'],
                'score': scores[key]['score'],
                'recommendation': scores[key]['recommendation'],
                'pivot_width_pct': scores[key]['pivot_width_pct']
            })

    # Separate by outcome
    successes = [m for m in matches if m['is_success']]
    false_breakouts = [m for m in matches if m['is_false']]

    print(f"\nTotal Breakouts: {len(matches)}")
    print(f"  Successes: {len(successes)}")
    print(f"  False Breakouts: {len(false_breakouts)}")

    # Score distribution
    success_scores = [s['score'] for s in successes]
    false_scores = [f['score'] for f in false_breakouts]

    print(f"\nScore Distribution:")
    print(f"  Successes:")
    print(f"    Average: {sum(success_scores)/len(success_scores):.1f}")
    print(f"    Range: {min(success_scores):.0f} - {max(success_scores):.0f}")

    print(f"  False Breakouts:")
    print(f"    Average: {sum(false_scores)/len(false_scores):.1f}")
    print(f"    Range: {min(false_scores):.0f} - {max(false_scores):.0f}")

    # Check separation
    avg_success = sum(success_scores) / len(success_scores)
    avg_false = sum(false_scores) / len(false_scores)
    separation = avg_success - avg_false

    print(f"\n📊 Score Separation: {separation:+.1f} points")
    if separation > 10:
        print("   ✓ GOOD - Scoring distinguishes winners from false breakouts")
    elif separation > 5:
        print("   ≈ MODERATE - Some separation but room for improvement")
    else:
        print("   ⚠️  POOR - Scoring doesn't distinguish well")

    # Recommendation accuracy
    print(f"\n{'='*80}")
    print("RECOMMENDATION ACCURACY")
    print(f"{'='*80}")

    # Count by recommendation
    rec_categories = ['STRONG BUY', 'BUY', 'CONSIDER', 'NEUTRAL', 'AVOID']

    for rec in rec_categories:
        rec_matches = [m for m in matches if m['recommendation'] == rec]
        if not rec_matches:
            continue

        rec_successes = [m for m in rec_matches if m['is_success']]
        success_rate = len(rec_successes) / len(rec_matches) * 100

        print(f"\n{rec}: {len(rec_matches)} setups")
        print(f"  Success Rate: {success_rate:.1f}% ({len(rec_successes)}/{len(rec_matches)})")

    # Top-ranked accuracy
    print(f"\n{'='*80}")
    print("TOP-RANKED ACCURACY")
    print(f"{'='*80}")

    # Sort by score
    sorted_matches = sorted(matches, key=lambda x: x['score'], reverse=True)

    # Check top N
    for n in [5, 10, 15, 20]:
        if n > len(sorted_matches):
            continue

        top_n = sorted_matches[:n]
        top_successes = [m for m in top_n if m['is_success']]
        success_rate = len(top_successes) / n * 100

        print(f"\nTop {n} Ranked:")
        print(f"  Successes: {len(top_successes)}/{n} ({success_rate:.1f}%)")
        print(f"  Winners captured: {', '.join([m['symbol'] for m in top_successes])}")

    # Show comparison
    print(f"\n{'='*80}")
    print("SUCCESSES - RANKED BY ENHANCED SCORE")
    print(f"{'='*80}")

    sorted_successes = sorted(successes, key=lambda x: x['score'], reverse=True)
    for i, s in enumerate(sorted_successes, 1):
        print(f"{i:2}. {s['symbol']:6} {s['side']:5} - Score:{s['score']:3.0f} "
              f"Pivot:{s['pivot_width_pct']:.2f}% - {s['recommendation']}")

    print(f"\n{'='*80}")
    print("FALSE BREAKOUTS - RANKED BY ENHANCED SCORE")
    print(f"{'='*80}")

    sorted_false = sorted(false_breakouts, key=lambda x: x['score'], reverse=True)
    for i, f in enumerate(sorted_false, 1):
        print(f"{i:2}. {f['symbol']:6} {f['side']:5} - Score:{f['score']:3.0f} "
              f"Pivot:{f['pivot_width_pct']:.2f}% - {f['recommendation']}")

    # Pivot width analysis
    print(f"\n{'='*80}")
    print("PIVOT WIDTH CORRELATION")
    print(f"{'='*80}")

    success_pivots = [s['pivot_width_pct'] for s in successes]
    false_pivots = [f['pivot_width_pct'] for f in false_breakouts]

    print(f"\nPivot Width:")
    print(f"  Successes: {sum(success_pivots)/len(success_pivots):.2f}% avg")
    print(f"  False Breakouts: {sum(false_pivots)/len(false_pivots):.2f}% avg")
    print(f"  Difference: {sum(false_pivots)/len(false_pivots) - sum(success_pivots)/len(success_pivots):.2f}%")

def main():
    if len(sys.argv) < 3:
        print("Usage: python compare_scoring_accuracy.py <validation_csv> <rescored_csv>")
        print("Example: python compare_scoring_accuracy.py validation_20251006.csv rescored_20251006.csv")
        sys.exit(1)

    validation_csv = sys.argv[1]
    rescored_csv = sys.argv[2]

    print(f"Loading validation outcomes from {validation_csv}...")
    outcomes = load_validation_outcomes(validation_csv)
    print(f"✓ Loaded {len(outcomes)} outcomes\n")

    print(f"Loading enhanced scores from {rescored_csv}...")
    scores = load_enhanced_scores(rescored_csv)
    print(f"✓ Loaded {len(scores)} scores\n")

    compare_accuracy(outcomes, scores)

if __name__ == '__main__':
    main()
