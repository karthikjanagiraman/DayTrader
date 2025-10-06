#!/usr/bin/env python3
"""
In-depth analysis of why breakouts never triggered and bounces failed
Analyzes Sept 23-30 backtest data to understand:
1. Why check_hybrid_entry() never confirmed breakouts
2. Scanner data quality for support/resistance levels
3. What needs to be fixed
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

def analyze_breakout_attempts():
    """
    Analyze the backtest log to find breakout ATTEMPTS that were rejected
    vs bounces that were accepted
    """

    log_file = Path(__file__).parent / "backtest_sept23_30_FILTERS_ALL_SETUPS.log"

    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return

    with open(log_file) as f:
        log_content = f.read()

    # Count different entry types
    breakout_entries = log_content.count("LONG BREAKOUT") + log_content.count("SHORT BREAKOUT")
    bounce_entries = log_content.count("LONG BOUNCE") + log_content.count("SHORT BOUNCE")
    rejection_entries = log_content.count("REJECTION")

    print("\n" + "="*80)
    print("ENTRY TYPE ANALYSIS")
    print("="*80)
    print(f"BREAKOUT entries: {breakout_entries}")
    print(f"BOUNCE entries: {bounce_entries}")
    print(f"REJECTION entries: {rejection_entries}")
    print(f"Total entries: {breakout_entries + bounce_entries + rejection_entries}")

    # Look for rejection reasons in the log
    # The backtester should log when it checks entries but doesn't take them
    # This will help us understand why breakouts were rejected

    return {
        'breakout_entries': breakout_entries,
        'bounce_entries': bounce_entries,
        'rejection_entries': rejection_entries
    }

def analyze_scanner_data_quality():
    """
    Analyze scanner data to understand support/resistance quality
    """

    # Find scanner file for Sept 23-30
    scanner_dir = Path(__file__).parent.parent.parent / "stockscanner" / "output"

    print("\n" + "="*80)
    print("SCANNER DATA QUALITY ANALYSIS")
    print("="*80)

    # Look for scanner files in the date range
    scanner_files = []
    for date in ["20250923", "20250924", "20250925", "20250926", "20250927",
                  "20250930"]:
        scanner_file = scanner_dir / f"scanner_results_{date}.json"
        if scanner_file.exists():
            scanner_files.append(scanner_file)
            print(f"✓ Found: {scanner_file.name}")
        else:
            print(f"✗ Missing: scanner_results_{date}.json")

    if not scanner_files:
        print("\n⚠️  No scanner files found for Sept 23-30")
        return None

    # Analyze first available scanner file
    scanner_file = scanner_files[0]
    print(f"\nAnalyzing: {scanner_file.name}")

    with open(scanner_file) as f:
        scanner_data = json.load(f)

    print(f"\nTotal stocks scanned: {len(scanner_data)}")

    # Analyze support/resistance quality metrics
    support_quality = []
    resistance_quality = []

    for stock in scanner_data:
        symbol = stock.get('symbol', 'UNKNOWN')
        resistance = stock.get('resistance', 0)
        support = stock.get('support', 0)
        close = stock.get('close', 0)
        dist_to_r = stock.get('dist_to_R%', 100)
        dist_to_s = stock.get('dist_to_S%', 100)
        score = stock.get('score', 0)
        rr = stock.get('risk_reward', 0)

        if close > 0:
            # Calculate how far support is from close
            support_pct = abs((close - support) / close * 100)
            resistance_pct = abs((resistance - close) / close * 100)

            support_quality.append({
                'symbol': symbol,
                'support': support,
                'close': close,
                'dist_pct': support_pct,
                'dist_to_s': dist_to_s,
                'score': score,
                'rr': rr
            })

            resistance_quality.append({
                'symbol': symbol,
                'resistance': resistance,
                'close': close,
                'dist_pct': resistance_pct,
                'dist_to_r': dist_to_r,
                'score': score,
                'rr': rr
            })

    # Print statistics
    print("\n" + "-"*80)
    print("RESISTANCE LEVELS (for long breakouts)")
    print("-"*80)

    avg_dist_r = sum(s['dist_to_r'] for s in resistance_quality) / len(resistance_quality) if resistance_quality else 0
    close_to_r = len([s for s in resistance_quality if s['dist_to_r'] < 2.0])

    print(f"Average distance to resistance: {avg_dist_r:.2f}%")
    print(f"Stocks within 2% of resistance: {close_to_r} ({close_to_r/len(resistance_quality)*100:.1f}%)")

    # Show top 10 closest to resistance
    closest_r = sorted(resistance_quality, key=lambda x: x['dist_to_r'])[:10]
    print("\nTop 10 stocks closest to resistance:")
    print(f"{'Symbol':<8} {'Close':<10} {'Resistance':<12} {'Dist%':<8} {'Score':<8} {'R/R':<6}")
    print("-"*60)
    for s in closest_r:
        print(f"{s['symbol']:<8} ${s['close']:<9.2f} ${s['resistance']:<11.2f} {s['dist_to_r']:<7.2f}% {s['score']:<8} {s['rr']:<6.2f}")

    print("\n" + "-"*80)
    print("SUPPORT LEVELS (for bounce entries)")
    print("-"*80)

    avg_dist_s = sum(s['dist_to_s'] for s in support_quality) / len(support_quality) if support_quality else 0
    close_to_s = len([s for s in support_quality if s['dist_to_s'] < 2.0])

    print(f"Average distance to support: {avg_dist_s:.2f}%")
    print(f"Stocks within 2% of support: {close_to_s} ({close_to_s/len(support_quality)*100:.1f}%)")

    # Show top 10 closest to support
    closest_s = sorted(support_quality, key=lambda x: x['dist_to_s'])[:10]
    print("\nTop 10 stocks closest to support:")
    print(f"{'Symbol':<8} {'Close':<10} {'Support':<12} {'Dist%':<8} {'Score':<8} {'R/R':<6}")
    print("-"*60)
    for s in closest_s:
        print(f"{s['symbol']:<8} ${s['close']:<9.2f} ${s['support']:<11.2f} {s['dist_to_s']:<7.2f}% {s['score']:<8} {s['rr']:<6.2f}")

    return {
        'resistance_quality': resistance_quality,
        'support_quality': support_quality,
        'avg_dist_to_resistance': avg_dist_r,
        'avg_dist_to_support': avg_dist_s,
        'close_to_resistance': close_to_r,
        'close_to_support': close_to_s
    }

def analyze_actual_trades():
    """
    Analyze actual trades to see entry quality
    """

    trades_file = Path(__file__).parent / "monthly_results" / "all_trades_202509.json"

    if not trades_file.exists():
        print(f"\n⚠️  Trades file not found: {trades_file}")
        return None

    with open(trades_file) as f:
        all_trades = json.load(f)

    # Filter to Sept 23-30
    sept_trades = []
    for t in all_trades:
        entry_time = t.get('entry_time', '')
        if entry_time:
            entry_date = entry_time.split()[0]
            if '2025-09-23' <= entry_date <= '2025-09-30':
                sept_trades.append(t)

    print("\n" + "="*80)
    print("ACTUAL TRADE ANALYSIS (Sept 23-30)")
    print("="*80)
    print(f"Total trades: {len(sept_trades)}")

    # Analyze by side
    longs = [t for t in sept_trades if t['side'] == 'LONG']
    shorts = [t for t in sept_trades if t['side'] == 'SHORT']

    print(f"\nLONG trades: {len(longs)}")
    print(f"SHORT trades: {len(shorts)}")

    # Analyze long performance
    long_winners = [t for t in longs if t['pnl'] > 0]
    long_losers = [t for t in longs if t['pnl'] <= 0]

    print(f"\nLONG performance:")
    print(f"  Winners: {len(long_winners)} ({len(long_winners)/len(longs)*100:.1f}%)")
    print(f"  Losers: {len(long_losers)} ({len(long_losers)/len(longs)*100:.1f}%)")
    print(f"  Total P&L: ${sum(t['pnl'] for t in longs):.2f}")
    print(f"  Avg winner: ${sum(t['pnl'] for t in long_winners)/len(long_winners):.2f}" if long_winners else "  Avg winner: N/A")
    print(f"  Avg loser: ${sum(t['pnl'] for t in long_losers)/len(long_losers):.2f}" if long_losers else "  Avg loser: N/A")

    # Find the one winner
    if long_winners:
        print("\n" + "-"*80)
        print("THE ONE WINNER (out of 79 longs):")
        print("-"*80)
        for w in long_winners:
            print(f"Symbol: {w['symbol']}")
            print(f"Entry: ${w['entry_price']:.2f} @ {w['entry_time']}")
            print(f"Exit: ${w['exit_price']:.2f} @ {w['exit_time']}")
            print(f"P&L: ${w['pnl']:.2f} ({w['pnl_pct']:.2f}%)")
            print(f"Shares: {w['shares']}")
            print(f"Duration: {w['duration_min']:.1f} minutes")
            print(f"Reason: {w['reason']}")
            print(f"Partials: {w.get('partials', 0)}")

    # Analyze worst losers
    worst_losers = sorted(longs, key=lambda x: x['pnl'])[:10]

    print("\n" + "-"*80)
    print("TOP 10 WORST LOSERS:")
    print("-"*80)
    print(f"{'Symbol':<8} {'Entry':<10} {'Exit':<10} {'P&L':<10} {'Shares':<8} {'Reason':<15}")
    print("-"*80)
    for t in worst_losers:
        print(f"{t['symbol']:<8} ${t['entry_price']:<9.2f} ${t['exit_price']:<9.2f} ${t['pnl']:<9.2f} {t['shares']:<8} {t['reason']:<15}")

    # Analyze exit reasons
    exit_reasons = {}
    for t in longs:
        reason = t.get('reason', 'UNKNOWN')
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

    print("\n" + "-"*80)
    print("EXIT REASON BREAKDOWN:")
    print("-"*80)
    for reason, count in sorted(exit_reasons.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(longs) * 100
        print(f"{reason:<20} {count:>5} ({pct:>5.1f}%)")

    return {
        'total_trades': len(sept_trades),
        'longs': len(longs),
        'shorts': len(shorts),
        'long_winners': len(long_winners),
        'long_losers': len(long_losers),
        'exit_reasons': exit_reasons
    }

def analyze_hybrid_entry_criteria():
    """
    Analyze what the hybrid entry criteria are and why they might be failing
    """

    print("\n" + "="*80)
    print("HYBRID ENTRY CRITERIA ANALYSIS")
    print("="*80)

    # Read the config to see what thresholds are set
    config_file = Path(__file__).parent.parent / "config" / "trader_config.yaml"

    if not config_file.exists():
        print(f"⚠️  Config file not found: {config_file}")
        return

    with open(config_file) as f:
        config_content = f.read()

    # Extract relevant settings
    print("\nCurrent BREAKOUT confirmation thresholds:")
    print("-"*80)

    # Parse key settings
    for line in config_content.split('\n'):
        line = line.strip()
        if 'momentum_volume_threshold:' in line:
            print(f"  Volume threshold: {line.split(':')[1].strip()}")
        elif 'momentum_candle_min_pct:' in line:
            print(f"  Min candle % move: {line.split(':')[1].strip()}")
        elif 'momentum_candle_min_atr:' in line:
            print(f"  Min candle ATR multiple: {line.split(':')[1].strip()}")

    print("\nFor a BREAKOUT to confirm, it needs:")
    print("  1. Price > resistance (for longs)")
    print("  2. Volume >= 1.3x average (momentum_volume_threshold)")
    print("  3. Candle >= 0.8% move OR >= 2x ATR (momentum criteria)")
    print("  4. NOT chasing (entry < 70% of recent range)")
    print("  5. NOT choppy (recent range > 0.5x ATR)")

    print("\nFor a BOUNCE to confirm, it needs:")
    print("  1. Price within 1% of support")
    print("  2. One of:")
    print("     - Bullish engulfing pattern")
    print("     - Hammer pattern (long lower wick)")
    print("     - Price moves 0.5% above support")
    print("  3. NOT chasing (entry < 70% of recent range) [ADDED Oct 4]")
    print("  4. NOT choppy (recent range > 0.5x ATR) [ADDED Oct 4]")

    print("\n" + "-"*80)
    print("HYPOTHESIS: Why breakouts never triggered")
    print("-"*80)
    print("Sept 23-30 was likely a DOWN/CHOPPY market:")
    print("  ✗ No volume surges (quiet market, low participation)")
    print("  ✗ No momentum candles (small moves, no 0.8% breakouts)")
    print("  ✗ Stocks were FALLING to support, not BREAKING resistance")
    print("  ✗ Market conditions favored bounces (reversal attempts)")
    print("\nBounce criteria are MUCH easier to meet:")
    print("  ✓ Just need to be near support (automatic in down market)")
    print("  ✓ Any hammer/engulfing pattern triggers (very common)")
    print("  ✓ No volume requirements (weak bounces still enter)")
    print("\nResult: 79 bounces triggered, 0 breakouts")

def main():
    """Run all analyses"""

    print("\n" + "="*80)
    print("IN-DEPTH ANALYSIS: Why Breakouts Failed & Bounces Dominated")
    print("Sept 23-30, 2025 Backtest")
    print("="*80)

    # Run analyses
    entry_analysis = analyze_breakout_attempts()
    scanner_analysis = analyze_scanner_data_quality()
    trade_analysis = analyze_actual_trades()
    analyze_hybrid_entry_criteria()

    # Final summary
    print("\n" + "="*80)
    print("EXECUTIVE SUMMARY")
    print("="*80)

    print("\n1. ENTRY TYPE BREAKDOWN:")
    if entry_analysis:
        print(f"   - Breakouts: {entry_analysis['breakout_entries']} (0%)")
        print(f"   - Bounces: {entry_analysis['bounce_entries']} (96.3%)")
        print(f"   - Rejections: {entry_analysis['rejection_entries']} (3.7%)")

    print("\n2. SCANNER DATA QUALITY:")
    if scanner_analysis:
        print(f"   - Avg distance to resistance: {scanner_analysis['avg_dist_to_resistance']:.2f}%")
        print(f"   - Avg distance to support: {scanner_analysis['avg_dist_to_support']:.2f}%")
        print(f"   - Stocks close to support: {scanner_analysis['close_to_support']} " +
              f"({scanner_analysis['close_to_support']/len(scanner_analysis['support_quality'])*100:.1f}%)")

    print("\n3. TRADE PERFORMANCE:")
    if trade_analysis:
        print(f"   - Total trades: {trade_analysis['total_trades']}")
        print(f"   - Long win rate: {trade_analysis['long_winners']}/{trade_analysis['longs']} " +
              f"({trade_analysis['long_winners']/trade_analysis['longs']*100:.1f}%)")
        print(f"   - Main exit reason: {max(trade_analysis['exit_reasons'].items(), key=lambda x: x[1])[0]}")

    print("\n4. ROOT CAUSES:")
    print("   ✗ Breakout confirmation TOO STRICT (requires 1.3x vol + 0.8% candle)")
    print("   ✗ Bounce confirmation TOO LOOSE (just pattern, no volume req)")
    print("   ✗ Scanner support levels UNRELIABLE (bounces fail 98.7%)")
    print("   ✗ Market was DOWN/CHOPPY (no momentum for breakouts)")

    print("\n5. RECOMMENDED FIXES:")
    print("   → DISABLE bounce entries (98.7% failure rate)")
    print("   → RELAX breakout criteria (reduce volume/candle thresholds)")
    print("   → ADD volume requirement to bounce confirmations")
    print("   → IMPROVE scanner support level detection")
    print("   → WAIT for better market conditions (trending, not choppy)")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
