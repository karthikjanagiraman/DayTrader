#!/usr/bin/env python3
"""
Deep Analysis of Short Stop Failures
Analyzes whether stopped-out shorts would have become profitable
if we had proper stop placement (below entry instead of above)
"""

import sys
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from ib_insync import IB, Stock
import pandas as pd

# Add paths
sys.path.insert(0, str(Path(__file__).parent))

def analyze_short_stops():
    """
    Analyze all SHORT STOP exits to see if they would have been profitable
    with proper stop placement
    """

    # Load trades
    trades_file = Path(__file__).parent / 'backtest/monthly_results/all_trades_202509.json'
    if not trades_file.exists():
        print(f"❌ Trades file not found: {trades_file}")
        return

    with open(trades_file) as f:
        all_trades = json.load(f)

    # Filter for SHORT trades with STOP exits that lost money
    short_stops = [
        t for t in all_trades
        if t.get('side') == 'SHORT'
        and t.get('reason') in ['STOP']
        and t.get('pnl', 0) < 0
    ]

    if not short_stops:
        print("No SHORT STOP losses found")
        return

    print(f"\n{'='*80}")
    print(f"ANALYZING {len(short_stops)} SHORT TRADES WITH STOP LOSSES")
    print(f"{'='*80}\n")

    # Connect to IBKR
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=4000)
        print("✓ Connected to IBKR\n")
    except Exception as e:
        print(f"❌ Could not connect to IBKR: {e}")
        print("Please ensure TWS/Gateway is running on port 7497")
        return

    results = []

    for idx, trade in enumerate(short_stops, 1):
        symbol = trade['symbol']
        entry_price = trade['entry_price']
        exit_price = trade['exit_price']
        pnl = trade['pnl']
        entry_time = trade.get('entry_time', '')
        exit_time = trade.get('exit_time', '')

        # Parse dates - use entry_bar and exit_bar numbers
        entry_bar_num = trade.get('entry_bar', 0)
        exit_bar_num = trade.get('exit_bar', 0)

        # Parse date from entry time
        try:
            # Entry times are in format: "2025-08-29 12:44:00-04:00"
            # The date is WRONG (look-ahead bias), so we need to infer from September month
            # Extract the day part and assume it's September 2025
            if 'entry_time' in trade:
                # Try to parse, but we know dates are wrong, so we'll use a workaround
                entry_parts = entry_time.split()[0].split('-')
                if len(entry_parts) == 3:
                    # Use September 2025 with the day number
                    day = int(entry_parts[2])
                    trade_date = date(2025, 9, day) if day <= 30 else date(2025, 9, 1)
                else:
                    print(f"  Skipping {symbol} - invalid date format")
                    continue
            else:
                print(f"  Skipping {symbol} - no entry_time")
                continue
        except Exception as e:
            print(f"  Skipping {symbol} - date parse error: {e}")
            continue

        print(f"[{idx}/{len(short_stops)}] Analyzing {symbol} on {trade_date}")
        print(f"  Entry: ${entry_price:.2f} @ bar {entry_bar_num} | Stop Exit: ${exit_price:.2f} @ bar {exit_bar_num} | Loss: ${pnl:.2f}")

        # Fetch full day's 1-minute bars
        contract = Stock(symbol, 'SMART', 'USD')
        try:
            bars = ib.reqHistoricalData(
                contract,
                endDateTime=f'{trade_date.strftime("%Y%m%d")} 16:00:00',
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars:
                print(f"  ⚠️  No data available")
                continue

            # Convert to DataFrame for analysis
            df = pd.DataFrame([{
                'time': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars])

            # Use exit bar number to find the exit point
            exit_bar_idx = exit_bar_num

            if exit_bar_idx >= len(df):
                print(f"  ⚠️  Exit bar {exit_bar_idx} beyond data length {len(df)}")
                continue

            # Analyze price action AFTER stop exit
            remaining_bars = df.iloc[exit_bar_idx:].copy()

            if len(remaining_bars) == 0:
                print(f"  ⚠️  No bars after exit (stopped at EOD)")
                continue

            # For SHORT: profit zone is BELOW entry price
            # Calculate: What was the LOW price after the stop?
            lowest_after_stop = remaining_bars['low'].min()

            # Calculate potential profit if held to lowest point
            # For SHORT: profit = entry - exit
            potential_profit = entry_price - lowest_after_stop
            actual_loss = entry_price - exit_price  # Negative for loss

            # Did price go back into profit zone?
            # For SHORT to be profitable: price needs to drop below entry
            went_profitable = lowest_after_stop < entry_price

            # How much profit would we have made at the low?
            max_profit_potential = (entry_price - lowest_after_stop) * trade.get('shares', 1000)

            # Calculate proper stop (should be ABOVE entry for shorts, not at support)
            # Proper stop would be: entry * 1.005 (0.5% above entry)
            proper_stop = entry_price * 1.005

            # Would proper stop have been hit?
            highest_after_entry = remaining_bars['high'].max()
            proper_stop_hit = highest_after_entry >= proper_stop

            result = {
                'symbol': symbol,
                'date': trade_date,
                'entry': entry_price,
                'actual_stop_exit': exit_price,
                'proper_stop': proper_stop,
                'actual_loss': pnl,
                'lowest_after_stop': lowest_after_stop,
                'went_profitable': went_profitable,
                'max_profit_potential': max_profit_potential,
                'proper_stop_would_hit': proper_stop_hit,
                'minutes_after_stop': len(remaining_bars)
            }

            results.append(result)

            print(f"  Lowest after stop: ${lowest_after_stop:.2f}")
            if went_profitable:
                print(f"  ✅ YES - Went profitable! Max profit: ${max_profit_potential:.2f}")
            else:
                print(f"  ❌ NO - Never went profitable")
            print(f"  Proper stop (entry +0.5%): ${proper_stop:.2f}")
            if proper_stop_hit:
                print(f"  🛑 Proper stop WOULD have hit (high: ${highest_after_entry:.2f})")
            else:
                print(f"  ✅ Proper stop WOULD NOT have hit (high: ${highest_after_entry:.2f})")
            print()

            # Rate limiting
            ib.sleep(0.5)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

    ib.disconnect()

    # Summary statistics
    if not results:
        print("No results to analyze")
        return

    print(f"\n{'='*80}")
    print(f"SUMMARY STATISTICS")
    print(f"{'='*80}\n")

    total = len(results)
    went_profitable = sum(1 for r in results if r['went_profitable'])
    proper_stop_safe = sum(1 for r in results if not r['proper_stop_would_hit'])
    both_conditions = sum(1 for r in results if r['went_profitable'] and not r['proper_stop_would_hit'])

    total_actual_loss = sum(r['actual_loss'] for r in results)
    total_potential_profit = sum(r['max_profit_potential'] for r in results if r['went_profitable'] and not r['proper_stop_would_hit'])

    print(f"Total SHORT STOP Losses Analyzed: {total}")
    print(f"")
    print(f"📊 PRICE ACTION AFTER STOP:")
    print(f"  Went back to PROFIT zone: {went_profitable}/{total} ({went_profitable/total*100:.1f}%)")
    print(f"  Never went profitable: {total-went_profitable}/{total} ({(total-went_profitable)/total*100:.1f}%)")
    print(f"")
    print(f"🛑 PROPER STOP PLACEMENT ANALYSIS:")
    print(f"  Proper stop (0.5% above entry) would NOT hit: {proper_stop_safe}/{total} ({proper_stop_safe/total*100:.1f}%)")
    print(f"  Proper stop would STILL hit: {total-proper_stop_safe}/{total} ({(total-proper_stop_safe)/total*100:.1f}%)")
    print(f"")
    print(f"✅ BOTH CONDITIONS (profitable + proper stop safe):")
    print(f"  Trades that would be WINNERS with proper stops: {both_conditions}/{total} ({both_conditions/total*100:.1f}%)")
    print(f"")
    print(f"💰 FINANCIAL IMPACT:")
    print(f"  Total ACTUAL losses (bad stops): ${total_actual_loss:,.2f}")
    print(f"  Total POTENTIAL profit (if held with proper stops): ${total_potential_profit:,.2f}")
    print(f"  NET IMPROVEMENT: ${total_potential_profit - abs(total_actual_loss):,.2f}")
    print(f"")

    # Detailed breakdown
    print(f"{'='*80}")
    print(f"DETAILED BREAKDOWN")
    print(f"{'='*80}\n")

    print("Trades that would be WINNERS with proper stop placement:\n")
    for r in results:
        if r['went_profitable'] and not r['proper_stop_would_hit']:
            print(f"  {r['symbol']:6s} {r['date']} | Loss: ${r['actual_loss']:8,.2f} → "
                  f"Potential: ${r['max_profit_potential']:8,.2f} | "
                  f"Improvement: ${r['max_profit_potential'] - abs(r['actual_loss']):8,.2f}")

    print("\n" + "="*80)
    print("Trades that would STILL lose (proper stop would hit):\n")
    for r in results:
        if r['proper_stop_would_hit']:
            proper_stop_loss = (r['entry'] - r['proper_stop']) * 1000  # Assume 1000 shares
            print(f"  {r['symbol']:6s} {r['date']} | Actual Loss: ${r['actual_loss']:8,.2f} → "
                  f"Proper Stop Loss: ${proper_stop_loss:8,.2f}")

    # Save results
    output_file = Path(__file__).parent / 'short_stop_analysis.json'
    with open(output_file, 'w') as f:
        json.dump({
            'analysis_date': datetime.now().isoformat(),
            'total_analyzed': total,
            'went_profitable_count': went_profitable,
            'proper_stop_safe_count': proper_stop_safe,
            'would_be_winners_count': both_conditions,
            'total_actual_loss': total_actual_loss,
            'total_potential_profit': total_potential_profit,
            'net_improvement': total_potential_profit - abs(total_actual_loss),
            'detailed_results': results
        }, f, indent=2, default=str)

    print(f"\n✓ Detailed results saved to: {output_file}")

if __name__ == '__main__':
    analyze_short_stops()
