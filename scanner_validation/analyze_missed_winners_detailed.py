#!/usr/bin/env python3
"""
Detailed Analysis of Missed Winners with Exact Timestamps

This script performs ultra-detailed analysis of each missed winner:
1. Exact breakout timestamp (when pivot broke)
2. Entry price at breakout
3. Target achievement timestamp
4. Exit price and timing
5. Trader state at breakout time
6. Filter blocks at critical moments
7. Simulated P&L if entered
8. Timeline visualization

Usage:
    python analyze_missed_winners_detailed.py 2025-10-06 validation_20251006.csv trader_log.txt
"""

import sys
import csv
import re
from datetime import datetime, timedelta
from ib_insync import IB, Stock
import time
import pytz

class DetailedWinnerAnalyzer:
    def __init__(self, validation_csv, trader_log):
        self.ib = IB()
        self.validation_csv = validation_csv
        self.trader_log = trader_log
        self.winners = []
        self.trader_log_content = None

    def connect(self):
        """Connect to IBKR"""
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=3005)
            print("✓ Connected to IBKR\n")
            return True
        except Exception as e:
            print(f"✗ IBKR connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib.isConnected():
            self.ib.disconnect()

    def load_winners(self):
        """Load winning setups from validation CSV"""
        with open(self.validation_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Check for LONG winners
                if row['Long Outcome'] == 'SUCCESS':
                    self.winners.append({
                        'symbol': row['Symbol'],
                        'side': 'LONG',
                        'pivot': float(row['Resistance']),
                        'day_high': float(row['Day High']),
                        'day_low': float(row['Day Low']),
                        'day_close': float(row['Day Close']),
                        'reason': row['Long Reason']
                    })

                # Check for SHORT winners
                if row['Short Outcome'] == 'SUCCESS':
                    self.winners.append({
                        'symbol': row['Symbol'],
                        'side': 'SHORT',
                        'pivot': float(row['Support']),
                        'day_high': float(row['Day High']),
                        'day_low': float(row['Day Low']),
                        'day_close': float(row['Day Close']),
                        'reason': row['Short Reason']
                    })

        print(f"Loaded {len(self.winners)} winning setups\n")
        return self.winners

    def load_trader_log(self):
        """Load trader log content"""
        with open(self.trader_log, 'r') as f:
            self.trader_log_content = f.read()

    def get_historical_bars(self, symbol, date):
        """Fetch 1-minute historical bars from IBKR"""
        try:
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Request 1-minute bars for the entire trading day
            end_datetime = date.replace(hour=16, minute=0, second=0)
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime.strftime('%Y%m%d %H:%M:%S'),
                durationStr='1 D',
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            time.sleep(0.5)  # Respect IBKR pacing
            return bars

        except Exception as e:
            print(f"  ✗ Error fetching {symbol}: {e}")
            return None

    def find_trader_state_at_time(self, symbol, timestamp):
        """Find what trader was doing at specific timestamp"""
        if not self.trader_log_content:
            return "Log not loaded"

        # Convert timestamp to string format used in logs
        time_str = timestamp.strftime('%H:%M:%S')

        # Search for log entries near this time for this symbol
        pattern = rf'({time_str}.*?{symbol}.*?)(?=\n\d{{2}}:\d{{2}}:\d{{2}}|\Z)'
        matches = re.findall(pattern, self.trader_log_content, re.DOTALL)

        if matches:
            return matches[0][:200]  # First 200 chars

        # If no exact match, find closest entry within 1 minute
        time_obj = datetime.strptime(time_str, '%H:%M:%S').time()
        for delta in [1, 2, 3, 5]:
            before = (datetime.combine(datetime.today(), time_obj) - timedelta(minutes=delta)).time()
            after = (datetime.combine(datetime.today(), time_obj) + timedelta(minutes=delta)).time()

            pattern = rf'({before.strftime("%H:%M")}.*?{symbol}.*?)(?=\n\d{{2}}:\d{{2}}:\d{{2}}|\Z)'
            matches = re.findall(pattern, self.trader_log_content, re.DOTALL)
            if matches:
                return f"[~{delta}min before] " + matches[0][:200]

        return "Trader not monitoring this stock at this time"

    def analyze_winner(self, winner, date):
        """Perform detailed analysis of single winner"""
        symbol = winner['symbol']
        side = winner['side']
        pivot = winner['pivot']

        print(f"\n{'='*100}")
        print(f"{symbol} {side} - DETAILED TIMELINE ANALYSIS")
        print(f"{'='*100}")
        print(f"Pivot: ${pivot:.2f}")
        print(f"Day High: ${winner['day_high']:.2f} | Day Low: ${winner['day_low']:.2f} | Close: ${winner['day_close']:.2f}")
        print(f"Validation Reason: {winner['reason']}\n")

        # Get 1-minute bars
        bars = self.get_historical_bars(symbol, date)
        if not bars or len(bars) == 0:
            print("✗ No historical data available\n")
            return None

        # Find breakout bar
        breakout_bar = None
        breakout_idx = None

        for i, bar in enumerate(bars):
            if side == 'LONG':
                if bar.close > pivot:
                    breakout_bar = bar
                    breakout_idx = i
                    break
            else:  # SHORT
                if bar.close < pivot:
                    breakout_bar = bar
                    breakout_idx = i
                    break

        if not breakout_bar:
            print("⚠️  No breakout detected (pivot never broken)\n")
            return None

        # Calculate target (assume 2% move)
        if side == 'LONG':
            target = pivot * 1.02
        else:
            target = pivot * 0.98

        # Find target hit bar
        target_bar = None
        target_idx = None
        max_favorable = breakout_bar.close

        for i in range(breakout_idx, len(bars)):
            bar = bars[i]
            if side == 'LONG':
                max_favorable = max(max_favorable, bar.high)
                if bar.high >= target:
                    target_bar = bar
                    target_idx = i
                    break
            else:
                max_favorable = min(max_favorable, bar.low)
                if bar.low <= target:
                    target_bar = bar
                    target_idx = i
                    break

        # Print timeline
        eastern = pytz.timezone('US/Eastern')

        print("📊 TIMELINE OF EVENTS:")
        print("-" * 100)

        # Market open
        market_open = bars[0].date
        print(f"09:30 AM - Market opens at ${bars[0].open:.2f}")

        # Breakout
        breakout_time = breakout_bar.date
        if hasattr(breakout_time, 'astimezone'):
            breakout_time_et = breakout_time.astimezone(eastern)
        else:
            breakout_time_et = breakout_time

        print(f"\n🚨 BREAKOUT @ {breakout_time_et.strftime('%H:%M:%S')} ET")
        print(f"   Price: ${breakout_bar.close:.2f} (broke ${pivot:.2f})")
        print(f"   Bar #{breakout_idx + 1} of day")
        print(f"   High: ${breakout_bar.high:.2f} | Low: ${breakout_bar.low:.2f}")

        # What was trader doing?
        trader_state = self.find_trader_state_at_time(symbol, breakout_time_et)
        print(f"\n   🤖 TRADER STATE AT BREAKOUT:")
        print(f"   {trader_state}")

        # Target hit
        if target_bar:
            target_time = target_bar.date
            if hasattr(target_time, 'astimezone'):
                target_time_et = target_time.astimezone(eastern)
            else:
                target_time_et = target_time

            minutes_to_target = (target_idx - breakout_idx)

            print(f"\n🎯 TARGET HIT @ {target_time_et.strftime('%H:%M:%S')} ET")
            print(f"   Price: ${target_bar.close:.2f} (target ${target:.2f})")
            print(f"   Time to target: {minutes_to_target} minutes")
            print(f"   Max favorable: ${max_favorable:.2f}")

            trader_state = self.find_trader_state_at_time(symbol, target_time_et)
            print(f"\n   🤖 TRADER STATE AT TARGET:")
            print(f"   {trader_state}")
        else:
            print(f"\n⚠️  Target ${target:.2f} was NOT hit")
            print(f"   Max favorable: ${max_favorable:.2f}")

        # Closing price
        close_bar = bars[-1]
        close_time = close_bar.date
        if hasattr(close_time, 'astimezone'):
            close_time_et = close_time.astimezone(eastern)
        else:
            close_time_et = close_time

        print(f"\n🔔 MARKET CLOSE @ {close_time_et.strftime('%H:%M:%S')} ET")
        print(f"   Close: ${winner['day_close']:.2f}")

        # Calculate simulated P&L
        print(f"\n💰 SIMULATED P&L IF ENTERED:")
        print("-" * 100)

        entry_price = breakout_bar.close
        stop_price = pivot
        stop_distance = abs(entry_price - stop_price)

        # Position size: 1% risk
        account_size = 100000
        risk_amount = account_size * 0.01
        shares = int(risk_amount / stop_distance)
        shares = min(shares, 1000)  # Cap at 1000

        print(f"Entry: ${entry_price:.2f} @ {breakout_time_et.strftime('%H:%M:%S')}")
        print(f"Stop: ${stop_price:.2f} (${stop_distance:.2f} away)")
        print(f"Shares: {shares} (1% risk = ${risk_amount:.2f})")
        print(f"Position size: ${shares * entry_price:.2f}")

        # Partial exits per PS60
        if target_bar:
            # 50% partial on first move (assume 0.25-0.50 gain)
            if side == 'LONG':
                partial1_price = entry_price + 0.35
            else:
                partial1_price = entry_price - 0.35

            # Find when we would have taken partial
            partial1_bar = None
            for i in range(breakout_idx, len(bars)):
                bar = bars[i]
                if side == 'LONG' and bar.high >= partial1_price:
                    partial1_bar = bar
                    break
                elif side == 'SHORT' and bar.low <= partial1_price:
                    partial1_bar = bar
                    break

            if partial1_bar:
                partial1_gain = (partial1_price - entry_price) if side == 'LONG' else (entry_price - partial1_price)
                partial1_pnl = partial1_gain * (shares * 0.5)
                print(f"\n50% Partial @ ${partial1_price:.2f}: +${partial1_pnl:.2f}")

                # 25% at target
                if side == 'LONG':
                    target_gain = target - entry_price
                else:
                    target_gain = entry_price - target
                target_pnl = target_gain * (shares * 0.25)
                print(f"25% at Target @ ${target:.2f}: +${target_pnl:.2f}")

                # 25% at close (trailing stop)
                close_gain = (winner['day_close'] - entry_price) if side == 'LONG' else (entry_price - winner['day_close'])
                close_pnl = close_gain * (shares * 0.25)
                print(f"25% Runner @ ${winner['day_close']:.2f}: ${close_pnl:+.2f}")

                total_pnl = partial1_pnl + target_pnl + close_pnl
                print(f"\n{'='*50}")
                print(f"TOTAL P&L: ${total_pnl:+.2f}")
                print(f"{'='*50}")

                return {
                    'symbol': symbol,
                    'side': side,
                    'breakout_time': breakout_time_et,
                    'entry_price': entry_price,
                    'target_time': target_time_et if target_bar else None,
                    'total_pnl': total_pnl,
                    'shares': shares
                }

        return None

    def run_analysis(self, date, max_stocks=5):
        """Run detailed analysis for all winners"""
        print(f"{'='*100}")
        print(f"DETAILED MISSED OPPORTUNITIES ANALYSIS - {date.strftime('%Y-%m-%d')}")
        print(f"{'='*100}\n")

        self.load_winners()
        self.load_trader_log()

        # Limit to first max_stocks to avoid timeout
        winners_to_analyze = self.winners[:max_stocks]
        print(f"Analyzing first {len(winners_to_analyze)} winners (out of {len(self.winners)} total)\n")

        results = []
        total_missed_pnl = 0

        for i, winner in enumerate(winners_to_analyze, 1):
            print(f"\n[{i}/{len(winners_to_analyze)}] Analyzing {winner['symbol']} {winner['side']}...")
            try:
                result = self.analyze_winner(winner, date)
                if result:
                    results.append(result)
                    total_missed_pnl += result['total_pnl']
            except Exception as e:
                print(f"  ✗ Error analyzing {winner['symbol']}: {e}")

        # Final summary
        print(f"\n\n{'='*100}")
        print("SUMMARY OF MISSED OPPORTUNITIES")
        print(f"{'='*100}\n")

        print(f"Total Winners Analyzed: {len(results)}/{len(self.winners)} (showing first {max_stocks})")
        print(f"Total Missed P&L (from analyzed): ${total_missed_pnl:+.2f}")
        if len(results) < len(self.winners):
            estimated_total = (total_missed_pnl / len(results)) * len(self.winners) if results else 0
            print(f"Estimated Total Missed P&L (all {len(self.winners)} winners): ${estimated_total:+.2f}\n")
        else:
            print()

        if results:
            print("Breakdown by Stock:")
            print("-" * 100)
            for r in sorted(results, key=lambda x: x['total_pnl'], reverse=True):
                print(f"{r['symbol']:6} {r['side']:5} - Breakout @ {r['breakout_time'].strftime('%H:%M')} - "
                      f"Entry ${r['entry_price']:.2f} - P&L: ${r['total_pnl']:+8.2f}")

        print("\n" + "="*100)

def main():
    if len(sys.argv) < 4:
        print("Usage: python analyze_missed_winners_detailed.py <date> <validation_csv> <trader_log>")
        print("Example: python analyze_missed_winners_detailed.py 2025-10-06 validation_20251006.csv trader.log")
        sys.exit(1)

    date_str = sys.argv[1]
    validation_csv = sys.argv[2]
    trader_log = sys.argv[3]

    # Parse date
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"✗ Invalid date format: {date_str}")
        sys.exit(1)

    # Run analysis
    analyzer = DetailedWinnerAnalyzer(validation_csv, trader_log)

    if not analyzer.connect():
        sys.exit(1)

    try:
        analyzer.run_analysis(date)
    finally:
        analyzer.disconnect()

if __name__ == '__main__':
    main()
