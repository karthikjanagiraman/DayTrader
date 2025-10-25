#!/usr/bin/env python3
"""
Check if stocks on Oct 21, 2025 had actual resistance/support breakouts
"""
import json
import sys
from pathlib import Path

def analyze_breakouts(scanner_file, date):
    """Analyze if any stocks broke resistance or support"""

    # Load scanner results
    with open(scanner_file) as f:
        scanner = json.load(f)

    print(f"\n{'='*80}")
    print(f"RESISTANCE/SUPPORT BREAKOUT ANALYSIS - {date}")
    print(f"{'='*80}\n")

    breakout_summary = {
        'resistance_breaks': [],
        'support_breaks': [],
        'no_breaks': []
    }

    for stock in scanner:
        symbol = stock['symbol']
        resistance = stock.get('resistance', 0)
        support = stock.get('support', 0)
        side = stock.get('side', 'UNKNOWN')

        print(f"\n{symbol} ({side}):")
        print(f"  Resistance: ${resistance:.2f}")
        print(f"  Support: ${support:.2f}")

        # Load CVD enriched bars
        cvd_file = f"data/cvd_bars/{symbol}_{date}_cvd.json"
        try:
            with open(cvd_file) as f:
                data = json.load(f)

            bars = data.get('bars', [])

            if not bars:
                print(f"  ⚠️  No bar data found")
                breakout_summary['no_breaks'].append(symbol)
                continue

            # Check for resistance breaks (LONG breakouts)
            resistance_breaks = []
            support_breaks = []

            for i, bar in enumerate(bars):
                timestamp = bar.get('timestamp', '')
                open_price = bar.get('open', 0)
                high = bar.get('high', 0)
                low = bar.get('low', 0)
                close = bar.get('close', 0)

                # Check resistance break (LONG)
                if close > resistance:
                    resistance_breaks.append({
                        'bar': i,
                        'time': timestamp,
                        'close': close,
                        'high': high,
                        'pct_above': ((close - resistance) / resistance) * 100
                    })

                # Check support break (SHORT)
                if close < support:
                    support_breaks.append({
                        'bar': i,
                        'time': timestamp,
                        'close': close,
                        'low': low,
                        'pct_below': ((support - close) / support) * 100
                    })

            # Report findings
            if resistance_breaks:
                print(f"  ✅ RESISTANCE BREAKS: {len(resistance_breaks)} bars closed above ${resistance:.2f}")
                first_break = resistance_breaks[0]
                print(f"     First break: Bar {first_break['bar']} @ {first_break['time']}")
                print(f"     Close: ${first_break['close']:.2f} (+{first_break['pct_above']:.2f}%)")
                print(f"     High: ${first_break['high']:.2f}")
                breakout_summary['resistance_breaks'].append({
                    'symbol': symbol,
                    'side': side,
                    'breaks': len(resistance_breaks),
                    'first_bar': first_break['bar'],
                    'first_time': first_break['time']
                })
            else:
                print(f"  ❌ No resistance breaks (stayed below ${resistance:.2f})")

            if support_breaks:
                print(f"  ✅ SUPPORT BREAKS: {len(support_breaks)} bars closed below ${support:.2f}")
                first_break = support_breaks[0]
                print(f"     First break: Bar {first_break['bar']} @ {first_break['time']}")
                print(f"     Close: ${first_break['close']:.2f} (-{first_break['pct_below']:.2f}%)")
                print(f"     Low: ${first_break['low']:.2f}")
                breakout_summary['support_breaks'].append({
                    'symbol': symbol,
                    'side': side,
                    'breaks': len(support_breaks),
                    'first_bar': first_break['bar'],
                    'first_time': first_break['time']
                })
            else:
                print(f"  ❌ No support breaks (stayed above ${support:.2f})")

            if not resistance_breaks and not support_breaks:
                breakout_summary['no_breaks'].append(symbol)

        except FileNotFoundError:
            print(f"  ⚠️  CVD file not found: {cvd_file}")
            breakout_summary['no_breaks'].append(symbol)
        except Exception as e:
            print(f"  ⚠️  Error loading data: {e}")
            breakout_summary['no_breaks'].append(symbol)

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")

    print(f"📊 Stocks with RESISTANCE breaks (LONG setups): {len(breakout_summary['resistance_breaks'])}")
    for item in breakout_summary['resistance_breaks']:
        print(f"   - {item['symbol']} ({item['side']}): {item['breaks']} bars, first @ bar {item['first_bar']}")

    print(f"\n📊 Stocks with SUPPORT breaks (SHORT setups): {len(breakout_summary['support_breaks'])}")
    for item in breakout_summary['support_breaks']:
        print(f"   - {item['symbol']} ({item['side']}): {item['breaks']} bars, first @ bar {item['first_bar']}")

    print(f"\n📊 Stocks with NO breaks (consolidation): {len(breakout_summary['no_breaks'])}")
    for symbol in breakout_summary['no_breaks']:
        print(f"   - {symbol}")

    total_with_breaks = len(breakout_summary['resistance_breaks']) + len(breakout_summary['support_breaks'])
    total_stocks = len(scanner)

    print(f"\n{'='*80}")
    print(f"CONCLUSION: {total_with_breaks}/{total_stocks} stocks ({total_with_breaks/total_stocks*100:.1f}%) had actual breakouts")

    if total_with_breaks == 0:
        print("\n🎯 Oct 21, 2025 was a CONSOLIDATION DAY - no clean breakouts occurred")
        print("   Zero trades with new CVD thresholds (20%/40%) is CORRECT behavior")
    else:
        print(f"\n⚠️  {total_with_breaks} stocks had breakouts but weren't traded")
        print("   CVD + other filters (stochastic, room-to-run, choppy) blocked entries")

    print(f"{'='*80}\n")

if __name__ == "__main__":
    scanner_file = "/Users/karthik/projects/DayTrader/stockscanner/output/scanner_results_20251021.json"
    date = "20251021"
    analyze_breakouts(scanner_file, date)
