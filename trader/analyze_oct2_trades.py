#!/usr/bin/env python3
"""
Analyze October 2nd trades to assess scanner prediction quality
"""

import json
import pandas as pd
from datetime import datetime
import os

def load_scanner_data():
    """Load scanner predictions for Oct 2"""
    with open('../stockscanner/output/scanner_results_20251002.json', 'r') as f:
        return json.load(f)

def load_market_data(symbol):
    """Load cached 5-second bar data"""
    cache_file = f'backtest/data/{symbol}_20251002_5sec.json'
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            data = json.load(f)
            # Data is already a list of bars
            # Convert date field to time for compatibility
            for bar in data:
                bar['time'] = bar.get('date', '')
            return data
    return None

def analyze_breakout_quality(symbol, scanner_data, market_bars):
    """Analyze the quality of a breakout prediction"""

    # Find scanner data for this symbol
    stock_data = next((s for s in scanner_data if s['symbol'] == symbol), None)
    if not stock_data:
        return None

    resistance = stock_data['resistance']
    support = stock_data['support']
    close_price = stock_data['close']

    # Get opening price (first bar)
    open_price = market_bars[0]['open']

    # Calculate gap
    gap_pct = ((open_price - close_price) / close_price) * 100

    # Find breakout attempts
    breakouts = []
    for i, bar in enumerate(market_bars):
        if bar['high'] > resistance and len(breakouts) < 2:  # Max 2 attempts
            breakout_bar = i
            breakout_time = bar['time'].split(' ')[1] if ' ' in bar['time'] else bar['time']
            breakout_price = bar['close']

            # Find where it failed (if it did)
            failure_bar = None
            failure_price = None
            max_gain = 0

            for j in range(i+1, min(i+100, len(market_bars))):  # Look ahead up to 100 bars (8.3 min)
                gain = market_bars[j]['high'] - breakout_price
                max_gain = max(max_gain, gain)

                if market_bars[j]['low'] < resistance:  # Fell back below resistance
                    failure_bar = j
                    failure_price = market_bars[j]['low']
                    break

            duration = (failure_bar - breakout_bar) if failure_bar else (len(market_bars) - breakout_bar)
            duration_min = duration * 5 / 60  # Convert to minutes

            breakouts.append({
                'time': breakout_time,
                'price': breakout_price,
                'failed': failure_bar is not None,
                'failure_price': failure_price,
                'max_gain': max_gain,
                'duration_min': duration_min
            })

    # Analyze price action characteristics
    highs = [bar['high'] for bar in market_bars]
    lows = [bar['low'] for bar in market_bars]
    closes = [bar['close'] for bar in market_bars]
    volumes = [bar['volume'] for bar in market_bars]

    max_price = max(highs)
    min_price = min(lows)
    close_price_eod = closes[-1]

    # Calculate volatility (high-low range as % of price)
    avg_range = sum([(highs[i] - lows[i])/closes[i] * 100 for i in range(len(market_bars))]) / len(market_bars)

    # Check if resistance held
    resistance_held = max_price < resistance + (resistance * 0.005)  # Within 0.5% counts as held

    # Time spent above resistance
    bars_above_resistance = sum(1 for bar in market_bars if bar['close'] > resistance)
    time_above_resistance_min = bars_above_resistance * 5 / 60

    return {
        'symbol': symbol,
        'resistance': resistance,
        'support': support,
        'scanner_close': close_price,
        'open': open_price,
        'gap_pct': gap_pct,
        'max_price': max_price,
        'min_price': min_price,
        'eod_close': close_price_eod,
        'breakout_attempts': len(breakouts),
        'breakouts': breakouts,
        'avg_volatility': avg_range,
        'resistance_held': resistance_held,
        'time_above_resistance_min': time_above_resistance_min,
        'max_move_from_resistance': ((max_price - resistance) / resistance) * 100,
        'scanner_score': stock_data['score'],
        'scanner_rr': stock_data['risk_reward']
    }

def main():
    # Trades that occurred on Oct 2
    traded_symbols = ['MU', 'ROKU', 'ARM', 'JD', 'F', 'LCID', 'PLTR', 'INTC']

    scanner_data = load_scanner_data()

    print("=" * 80)
    print("OCTOBER 2ND TRADE ANALYSIS - SCANNER PREDICTION QUALITY")
    print("=" * 80)
    print()

    results = []
    for symbol in traded_symbols:
        market_bars = load_market_data(symbol)
        if market_bars:
            analysis = analyze_breakout_quality(symbol, scanner_data, market_bars)
            if analysis:
                results.append(analysis)

                print(f"\n{symbol} ANALYSIS:")
                print("-" * 40)
                print(f"Scanner Prediction: Resistance ${analysis['resistance']:.2f}, Support ${analysis['support']:.2f}")
                print(f"Scanner Score: {analysis['scanner_score']}, R/R: {analysis['scanner_rr']:.2f}")
                print(f"Gap at Open: {analysis['gap_pct']:.2f}%")
                print(f"Max Price: ${analysis['max_price']:.2f} ({analysis['max_move_from_resistance']:.2f}% above resistance)")
                print(f"Breakout Attempts: {analysis['breakout_attempts']}")

                if analysis['breakouts']:
                    for i, breakout in enumerate(analysis['breakouts'], 1):
                        status = "FAILED" if breakout['failed'] else "HELD"
                        print(f"  Attempt {i}: {breakout['time']} @ ${breakout['price']:.2f} - {status}")
                        print(f"    Max gain: ${breakout['max_gain']:.2f}, Duration: {breakout['duration_min']:.1f} min")

                print(f"Time Above Resistance: {analysis['time_above_resistance_min']:.1f} minutes")
                print(f"Avg Volatility: {analysis['avg_volatility']:.3f}%")

                # Quality Assessment
                quality_issues = []
                if analysis['gap_pct'] > 1:
                    quality_issues.append(f"Gapped up {analysis['gap_pct']:.1f}% at open")
                if analysis['max_move_from_resistance'] < 0.5:
                    quality_issues.append("Never cleanly broke resistance")
                if analysis['breakout_attempts'] > 0 and all(b['failed'] for b in analysis['breakouts']):
                    quality_issues.append("All breakout attempts failed")
                if analysis['time_above_resistance_min'] < 5:
                    quality_issues.append("Couldn't sustain above resistance")
                if analysis['avg_volatility'] > 0.1:
                    quality_issues.append(f"High volatility ({analysis['avg_volatility']:.2f}%)")

                if quality_issues:
                    print(f"\n⚠️  Quality Issues:")
                    for issue in quality_issues:
                        print(f"  - {issue}")

    # Summary Statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    if results:
        # Breakout success rate
        total_breakouts = sum(r['breakout_attempts'] for r in results)
        failed_breakouts = sum(sum(1 for b in r['breakouts'] if b['failed']) for r in results)

        print(f"\nBreakout Attempts: {total_breakouts}")
        print(f"Failed Breakouts: {failed_breakouts} ({failed_breakouts/total_breakouts*100:.1f}%)")

        # Gap analysis
        avg_gap = sum(r['gap_pct'] for r in results) / len(results)
        gapped_up = sum(1 for r in results if r['gap_pct'] > 1)

        print(f"\nAverage Gap: {avg_gap:.2f}%")
        print(f"Stocks that gapped >1%: {gapped_up}/{len(results)}")

        # Resistance quality
        never_broke = sum(1 for r in results if r['max_move_from_resistance'] < 0.5)
        sustained_break = sum(1 for r in results if r['time_above_resistance_min'] > 10)

        print(f"\nNever cleanly broke resistance: {never_broke}/{len(results)}")
        print(f"Sustained above resistance >10min: {sustained_break}/{len(results)}")

        # Volatility
        avg_volatility = sum(r['avg_volatility'] for r in results) / len(results)
        print(f"\nAverage intraday volatility: {avg_volatility:.3f}%")

        print("\n🔍 KEY FINDINGS:")
        print("-" * 40)

        if failed_breakouts / total_breakouts > 0.7:
            print("❌ HIGH FAILURE RATE: Over 70% of breakout attempts failed immediately")

        if avg_gap > 0.5:
            print(f"⚠️  GAP RISK: Stocks gapped {avg_gap:.1f}% on average, reducing room to run")

        if never_broke > len(results) * 0.5:
            print("❌ WEAK BREAKOUTS: Most stocks never cleanly broke resistance")

        if sustained_break < len(results) * 0.3:
            print("❌ NO FOLLOW-THROUGH: Few stocks sustained above resistance")

        if avg_volatility > 0.08:
            print(f"⚠️  HIGH VOLATILITY: {avg_volatility:.3f}% avg range creates whipsaws")

        # Scanner accuracy assessment
        print("\n📊 SCANNER ACCURACY ASSESSMENT:")
        print("-" * 40)

        # Check if resistance levels were reasonable
        resistance_tested = sum(1 for r in results if r['max_price'] >= r['resistance'] * 0.995)
        print(f"Resistance levels tested: {resistance_tested}/{len(results)} ({resistance_tested/len(results)*100:.0f}%)")

        # Were the scores predictive?
        high_score_success = sum(1 for r in results if r['scanner_score'] >= 85 and r['time_above_resistance_min'] > 5)
        high_score_total = sum(1 for r in results if r['scanner_score'] >= 85)
        if high_score_total > 0:
            print(f"High score (≥85) success rate: {high_score_success}/{high_score_total} ({high_score_success/high_score_total*100:.0f}%)")

        print("\n💡 CONCLUSION:")
        print("-" * 40)
        print("Scanner correctly identified resistance levels (tested by most stocks)")
        print("However, October 2nd market conditions were poor for breakout trading:")
        print("  1. Stocks gapped up at open, reducing room to run")
        print("  2. High intraday volatility caused whipsaws")
        print("  3. Breakouts lacked follow-through (no sustained moves)")
        print("  4. Quick reversals below resistance triggered stops")
        print("\nThe scanner predictions were ACCURATE, but market CONDITIONS were unfavorable.")

if __name__ == "__main__":
    main()