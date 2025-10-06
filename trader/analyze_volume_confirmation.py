#!/usr/bin/env python3
"""
Analyze October 2nd trades to check if volume confirmation would have helped
identify false breakouts and prevent losses.

Uses cached 5-second bar data from backtest.
"""

import json
import os

def load_cached_bars(symbol, date='20251002'):
    """Load cached 5-second bars from backtest data directory"""
    cache_file = f'backtest/data/{symbol}_{date}_5sec.json'

    if not os.path.exists(cache_file):
        return None

    with open(cache_file) as f:
        data = json.load(f)

    # Convert to simple bar objects
    class Bar:
        def __init__(self, d):
            self.date = d['date']
            self.open = d['open']
            self.high = d['high']
            self.low = d['low']
            self.close = d['close']
            self.volume = d['volume']

    return [Bar(d) for d in data]

def analyze_volume_at_breakout(symbol, entry_bar, bars):
    """
    Analyze volume at breakout bar compared to average

    Returns:
        dict with volume analysis
    """
    if entry_bar >= len(bars):
        return None

    breakout_bar = bars[entry_bar]

    # Calculate average volume from 20 bars before breakout
    start_idx = max(0, entry_bar - 20)
    recent_bars = bars[start_idx:entry_bar]

    if len(recent_bars) < 5:
        return {
            'has_volume_surge': False,
            'reason': 'Insufficient history',
            'breakout_volume': breakout_bar.volume,
            'avg_volume': 0,
            'volume_ratio': 0
        }

    avg_volume = sum(bar.volume for bar in recent_bars) / len(recent_bars)
    volume_ratio = breakout_bar.volume / avg_volume if avg_volume > 0 else 0
    required_volume = avg_volume * 1.5

    has_surge = breakout_bar.volume >= required_volume

    # Also check if ANY of the next 5 bars had volume surge (for strong moves)
    next_bars = bars[entry_bar:min(entry_bar + 5, len(bars))]
    max_volume_ratio = max((bar.volume / avg_volume for bar in next_bars), default=0) if avg_volume > 0 else 0
    has_surge_in_move = max_volume_ratio >= 1.5

    return {
        'has_volume_surge': has_surge,
        'has_surge_in_move': has_surge_in_move,
        'breakout_volume': int(breakout_bar.volume),
        'avg_volume': int(avg_volume),
        'required_volume': int(required_volume),
        'volume_ratio': round(volume_ratio, 2),
        'max_volume_ratio_in_move': round(max_volume_ratio, 2)
    }

def main():
    # Load October 2nd trades
    with open('backtest/monthly_results/all_trades_202510.json') as f:
        trades = json.load(f)

    print("="*80)
    print("VOLUME CONFIRMATION ANALYSIS - October 2nd Trades")
    print("="*80)
    print()

    results = []
    symbols_processed = set()

    for i, trade in enumerate(trades, 1):
        symbol = trade['symbol']
        side = trade['side']
        entry_bar = trade['entry_bar']
        pnl = trade['pnl']
        result = 'WIN' if pnl > 0 else 'LOSS'

        # Skip if we already analyzed this symbol
        if symbol in symbols_processed:
            continue
        symbols_processed.add(symbol)

        print(f"[{i}] {symbol} {side}")
        print(f"    Result: {result} (P&L: ${pnl:.2f})")
        print(f"    Entry bar: {entry_bar}")

        # Load cached bars
        bars = load_cached_bars(symbol)

        if not bars:
            print("    ⚠️  No cached bar data available")
            print()
            continue

        # Analyze volume at breakout
        volume_analysis = analyze_volume_at_breakout(symbol, entry_bar, bars)

        if volume_analysis:
            has_surge = volume_analysis['has_volume_surge']
            has_surge_move = volume_analysis['has_surge_in_move']

            print(f"    Breakout Volume: {volume_analysis['breakout_volume']:,}")
            print(f"    Avg Volume (20 bars): {volume_analysis['avg_volume']:,}")
            print(f"    Volume Ratio: {volume_analysis['volume_ratio']}x (need 1.5x)")
            print(f"    Max Volume in Move: {volume_analysis['max_volume_ratio_in_move']}x")

            if has_surge or has_surge_move:
                print(f"    ✅ HAS VOLUME SURGE - Trade would be TAKEN")
            else:
                print(f"    ❌ NO VOLUME SURGE - Trade would be SKIPPED")

            results.append({
                'symbol': symbol,
                'side': side,
                'result': result,
                'pnl': pnl,
                'has_volume': has_surge or has_surge_move,
                'volume_ratio': volume_analysis['volume_ratio'],
                'max_volume_ratio': volume_analysis['max_volume_ratio_in_move']
            })

        print()

    # Summary analysis
    print("="*80)
    print("SUMMARY: Would Volume Filter Have Helped?")
    print("="*80)
    print()

    # Categorize trades
    losers_with_volume = [r for r in results if r['result'] == 'LOSS' and r['has_volume']]
    losers_without_volume = [r for r in results if r['result'] == 'LOSS' and not r['has_volume']]
    winners_with_volume = [r for r in results if r['result'] == 'WIN' and r['has_volume']]
    winners_without_volume = [r for r in results if r['result'] == 'WIN' and not r['has_volume']]

    print(f"Total trades analyzed: {len(results)}")
    print()

    print("LOSERS:")
    print(f"  With volume: {len(losers_with_volume)} trades")
    if losers_with_volume:
        total_loss = sum(r['pnl'] for r in losers_with_volume)
        print(f"    Symbols: {', '.join(r['symbol'] for r in losers_with_volume)}")
        print(f"    Total loss: ${total_loss:.2f}")

    print(f"  Without volume: {len(losers_without_volume)} trades")
    if losers_without_volume:
        total_saved = sum(abs(r['pnl']) for r in losers_without_volume)
        print(f"    Symbols: {', '.join(r['symbol'] for r in losers_without_volume)}")
        print(f"    Would have SAVED: ${total_saved:.2f}")

    print()
    print("WINNERS:")
    print(f"  With volume: {len(winners_with_volume)} trades")
    if winners_with_volume:
        total_profit = sum(r['pnl'] for r in winners_with_volume)
        print(f"    Symbols: {', '.join(r['symbol'] for r in winners_with_volume)}")
        print(f"    Total profit: ${total_profit:.2f}")

    print(f"  Without volume: {len(winners_without_volume)} trades")
    if winners_without_volume:
        total_missed = sum(r['pnl'] for r in winners_without_volume)
        print(f"    Symbols: {', '.join(r['symbol'] for r in winners_without_volume)}")
        print(f"    Would have MISSED: ${total_missed:.2f}")

    print()
    print("NET IMPACT:")
    saved = sum(abs(r['pnl']) for r in losers_without_volume)
    missed = sum(r['pnl'] for r in winners_without_volume)
    net_benefit = saved - missed

    print(f"  Losses avoided: ${saved:.2f}")
    print(f"  Profits missed: ${missed:.2f}")
    print(f"  NET BENEFIT: ${net_benefit:.2f}")

    if net_benefit > 0:
        print(f"  ✅ Volume filter would have IMPROVED results by ${net_benefit:.2f}")
    else:
        print(f"  ❌ Volume filter would have HURT results by ${abs(net_benefit):.2f}")

    # Calculate new performance
    print()
    print("PERFORMANCE WITH VOLUME FILTER:")
    trades_with_volume = [r for r in results if r['has_volume']]
    if trades_with_volume:
        total_pnl = sum(r['pnl'] for r in trades_with_volume)
        winners = len([r for r in trades_with_volume if r['result'] == 'WIN'])
        win_rate = (winners / len(trades_with_volume) * 100) if trades_with_volume else 0

        print(f"  Trades taken: {len(trades_with_volume)} (vs {len(results)} originally)")
        print(f"  Win rate: {win_rate:.1f}%")
        print(f"  Total P&L: ${total_pnl:.2f}")
        print(f"  Avg P&L per trade: ${total_pnl / len(trades_with_volume):.2f}")

    # Save detailed results
    with open('volume_confirmation_analysis.json', 'w') as f:
        json.dump({
            'trades': results,
            'summary': {
                'total_trades': len(results),
                'losers_with_volume': len(losers_with_volume),
                'losers_without_volume': len(losers_without_volume),
                'winners_with_volume': len(winners_with_volume),
                'winners_without_volume': len(winners_without_volume),
                'losses_avoided': saved,
                'profits_missed': missed,
                'net_benefit': net_benefit
            }
        }, f, indent=2)

    print()
    print(f"✓ Detailed results saved to volume_confirmation_analysis.json")

if __name__ == '__main__':
    main()
