#!/usr/bin/env python3
"""
Analyze price movements after stop-outs to verify if relaxed stops would have worked.
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from ib_insync import IB, Stock, util
import time
import pytz

def analyze_stop_recovery():
    """Check if price recovered after stop-outs"""

    # Load all trade data
    trades_by_date = {
        '2025-10-07': 'results/backtest_trades_20251007.json',
        '2025-10-08': 'results/backtest_trades_20251008.json',
        '2025-10-09': 'results/backtest_trades_20251009.json'
    }

    # Load scanner data for ATR
    scanner_by_date = {
        '2025-10-07': '../../stockscanner/output/scanner_results_20251007.json',
        '2025-10-08': '../../stockscanner/output/scanner_results_20251008.json',
        '2025-10-09': '../../stockscanner/output/scanner_results_20251009.json'
    }

    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=6000)
        time.sleep(1)
    except Exception as e:
        print(f"Error connecting to IBKR: {e}")
        return

    results = []

    for date_str, trades_file in trades_by_date.items():
        print(f"\n{'='*80}")
        print(f"Analyzing {date_str}")
        print('='*80)

        # Load trades
        try:
            with open(trades_file, 'r') as f:
                trades = json.load(f)
        except:
            print(f"No trades file for {date_str}")
            continue

        # Load scanner data
        try:
            with open(scanner_by_date[date_str], 'r') as f:
                scanner_data = json.load(f)
            scanner_dict = {s['symbol']: s for s in scanner_data}
        except:
            scanner_dict = {}

        # Filter for stopped trades
        stopped_trades = [t for t in trades if t['reason'] == 'STOP' and t['duration_min'] < 15]

        for trade in stopped_trades:
            symbol = trade['symbol']
            side = trade['side']
            entry_price = trade['entry_price']
            exit_price = trade['exit_price']
            entry_time = pd.to_datetime(trade['entry_time'])
            exit_time = pd.to_datetime(trade['exit_time'])
            duration_min = trade['duration_min']

            # Get ATR from scanner
            atr_pct = scanner_dict.get(symbol, {}).get('atr%', 5.0)

            # Calculate stop width
            if side == 'LONG':
                stop_width_pct = ((entry_price - exit_price) / entry_price) * 100
            else:
                stop_width_pct = ((exit_price - entry_price) / entry_price) * 100

            # Calculate recommended stop based on ATR
            if atr_pct < 2.0:
                recommended_stop_pct = 0.7
            elif atr_pct < 4.0:
                recommended_stop_pct = 1.2
            elif atr_pct < 6.0:
                recommended_stop_pct = 1.8
            else:
                recommended_stop_pct = 2.5

            print(f"\n{symbol} {side}:")
            print(f"  Entry: ${entry_price:.2f} at {entry_time.strftime('%H:%M:%S')}")
            print(f"  Stop Hit: ${exit_price:.2f} at {exit_time.strftime('%H:%M:%S')} ({duration_min:.1f} min)")
            print(f"  Stop Width: {stop_width_pct:.2f}% (ATR: {atr_pct:.1f}%)")
            print(f"  Recommended Stop: {recommended_stop_pct:.1f}%")

            # Fetch bars after stop-out
            contract = Stock(symbol, 'SMART', 'USD')

            try:
                # Get 30 minutes of data after stop
                # Need to adjust for timezone - IBKR expects US/Eastern
                eastern = pytz.timezone('US/Eastern')

                # Convert exit_time to Eastern if needed
                if exit_time.tzinfo is None:
                    # Assume it's already Eastern
                    exit_time_et = eastern.localize(exit_time.replace(tzinfo=None))
                else:
                    exit_time_et = exit_time.astimezone(eastern)

                end_time_et = exit_time_et + timedelta(minutes=30)

                # Format for IBKR - needs specific format
                end_datetime_str = end_time_et.strftime('%Y%m%d %H:%M:%S') + ' US/Eastern'

                bars = ib.reqHistoricalData(
                    contract,
                    endDateTime=end_datetime_str,
                    durationStr='1800 S',  # 30 minutes in seconds
                    barSizeSetting='5 secs',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )

                if bars:
                    # Find highest/lowest price in next 30 minutes
                    post_stop_bars = [b for b in bars if pd.to_datetime(b.date) > exit_time]

                    if post_stop_bars:
                        high_after = max(b.high for b in post_stop_bars[:60])  # Next 5 minutes
                        low_after = min(b.low for b in post_stop_bars[:60])

                        high_30min = max(b.high for b in post_stop_bars)  # Next 30 minutes
                        low_30min = min(b.low for b in post_stop_bars)

                        if side == 'LONG':
                            # For longs, check if price went back above entry
                            recovery_5min = high_after > entry_price
                            recovery_30min = high_30min > entry_price

                            # Check if relaxed stop would have held
                            relaxed_stop = entry_price * (1 - recommended_stop_pct/100)
                            would_hold = low_after > relaxed_stop

                            potential_profit = high_30min - entry_price

                            print(f"  Next 5 min: High ${high_after:.2f} (Recovery: {recovery_5min})")
                            print(f"  Next 30 min: High ${high_30min:.2f} (Recovery: {recovery_30min})")
                            print(f"  Relaxed Stop ${relaxed_stop:.2f} would have held: {would_hold}")
                            if recovery_30min:
                                print(f"  Potential Profit: ${potential_profit:.2f} ({(potential_profit/entry_price)*100:.1f}%)")

                        else:  # SHORT
                            # For shorts, check if price went back below entry
                            recovery_5min = low_after < entry_price
                            recovery_30min = low_30min < entry_price

                            # Check if relaxed stop would have held
                            relaxed_stop = entry_price * (1 + recommended_stop_pct/100)
                            would_hold = high_after < relaxed_stop

                            potential_profit = entry_price - low_30min

                            print(f"  Next 5 min: Low ${low_after:.2f} (Recovery: {recovery_5min})")
                            print(f"  Next 30 min: Low ${low_30min:.2f} (Recovery: {recovery_30min})")
                            print(f"  Relaxed Stop ${relaxed_stop:.2f} would have held: {would_hold}")
                            if recovery_30min:
                                print(f"  Potential Profit: ${potential_profit:.2f} ({(potential_profit/entry_price)*100:.1f}%)")

                        results.append({
                            'date': date_str,
                            'symbol': symbol,
                            'side': side,
                            'entry': entry_price,
                            'stop_hit': exit_price,
                            'stop_width%': stop_width_pct,
                            'atr%': atr_pct,
                            'recommended_stop%': recommended_stop_pct,
                            'relaxed_stop': relaxed_stop,
                            'would_hold_relaxed': would_hold,
                            'recovered_5min': recovery_5min,
                            'recovered_30min': recovery_30min,
                            'potential_profit': potential_profit if recovery_30min else 0
                        })

                time.sleep(0.5)  # Rate limit

            except Exception as e:
                print(f"  Error fetching data: {e}")

    ib.disconnect()

    # Summary
    if results:
        df = pd.DataFrame(results)

        print("\n" + "="*80)
        print("SUMMARY: Would Relaxed Stops Have Helped?")
        print("="*80)

        total = len(df)
        would_hold = len(df[df['would_hold_relaxed']])
        recovered_5min = len(df[df['recovered_5min']])
        recovered_30min = len(df[df['recovered_30min']])

        print(f"\nTotal Stopped Trades Analyzed: {total}")
        print(f"Would Hold with Relaxed Stop: {would_hold} ({would_hold/total*100:.1f}%)")
        print(f"Price Recovered in 5 min: {recovered_5min} ({recovered_5min/total*100:.1f}%)")
        print(f"Price Recovered in 30 min: {recovered_30min} ({recovered_30min/total*100:.1f}%)")

        if df['potential_profit'].sum() > 0:
            print(f"\nTotal Potential Profit Missed: ${df['potential_profit'].sum():.2f}")

        # Save detailed results
        output_file = 'STOP_RECOVERY_ANALYSIS.csv'
        df.to_csv(output_file, index=False)
        print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    analyze_stop_recovery()