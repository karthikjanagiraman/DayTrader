#!/usr/bin/env python3
"""
Monthly Backtesting Script
Runs scanner + backtest for each trading day in a given month
"""

from ib_insync import *
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json
import pandas as pd
import time

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent / 'stockscanner'))

class HistoricalScanner:
    """Scanner that works with historical dates"""

    def __init__(self):
        self.ib = None

    def connect(self):
        """Connect to IBKR"""
        self.ib = IB()
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=3000)
            print(f"✓ Connected to IBKR")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()

    def get_symbols(self):
        """Get symbols to scan - same as main scanner"""
        core_symbols = {
            'indices': ['SPY', 'QQQ', 'IWM', 'DIA'],
            'mega_tech': ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'TSLA'],
            'semis': ['AMD', 'INTC', 'MU', 'QCOM', 'AVGO', 'AMAT', 'LRCX', 'ARM'],
            'high_vol': ['COIN', 'PLTR', 'SOFI', 'HOOD', 'ROKU', 'SNAP', 'PINS', 'RBLX'],
            'meme': ['GME', 'AMC', 'BB', 'BBBY', 'CLOV'],
            'finance': ['JPM', 'BAC', 'GS', 'MS', 'C', 'WFC'],
            'energy': ['XOM', 'CVX', 'OXY'],
            'china': ['BABA', 'JD', 'BIDU', 'NIO', 'LI', 'XPEV'],
            'other': ['NFLX', 'DIS', 'UBER', 'LYFT', 'PYPL', 'BA', 'F', 'GM', 'RIVN', 'LCID']
        }

        all_symbols = []
        for symbols in core_symbols.values():
            all_symbols.extend(symbols)
        return list(set(all_symbols))

    def scan_for_date(self, scan_date, category='all'):
        """
        Run scanner for a specific historical date

        CRITICAL: Avoid look-ahead bias!
        - Scanner runs BEFORE market open on scan_date
        - Should only use data from BEFORE scan_date
        - Use previous day's close as "current_price"
        - Calculate S/R using data up to day BEFORE scan_date
        """
        print(f"\n{'='*80}")
        print(f"Historical Scanner - {scan_date.strftime('%Y-%m-%d')}")
        print(f"{'='*80}")

        if not self.connect():
            return None

        results = []
        symbols = self.get_symbols()

        print(f"Scanning {len(symbols)} symbols for {scan_date.strftime('%Y-%m-%d')}...")

        for i, symbol in enumerate(symbols):
            try:
                # Get historical data UP TO the day BEFORE scan_date (NO LOOK-AHEAD BIAS)
                contract = Stock(symbol, 'SMART', 'USD')
                if not self.ib.qualifyContracts(contract):
                    continue

                # End date is the day BEFORE scan_date (scanner runs pre-market)
                day_before = scan_date - timedelta(days=1)
                end_date = day_before.strftime('%Y%m%d 23:59:59')

                bars = self.ib.reqHistoricalData(
                    contract,
                    endDateTime=end_date,
                    durationStr='30 D',
                    barSizeSetting='1 day',
                    whatToShow='TRADES',
                    useRTH=True,
                    formatDate=1
                )

                if not bars or len(bars) < 20:
                    continue

                # Convert to DataFrame
                df = util.df(bars)

                # "Today" is the last available day (day before scan_date)
                # "Yesterday" is the day before that
                today = df.iloc[-1]
                yesterday = df.iloc[-2]
                current_price = today['close']  # This is the previous day's close

                # Calculate key metrics
                change_pct = ((current_price - yesterday['close']) / yesterday['close']) * 100

                avg_volume = df['volume'].iloc[-21:-1].mean()
                rvol = today['volume'] / avg_volume if avg_volume > 0 else 0

                # ATR calculation
                tr_list = []
                for j in range(1, len(df)):
                    high_low = df.iloc[j]['high'] - df.iloc[j]['low']
                    high_close = abs(df.iloc[j]['high'] - df.iloc[j-1]['close'])
                    low_close = abs(df.iloc[j]['low'] - df.iloc[j-1]['close'])
                    tr_list.append(max(high_low, high_close, low_close))
                atr = pd.Series(tr_list).iloc[-14:].mean() if len(tr_list) >= 14 else 0
                atr_pct = (atr / current_price) * 100

                # Support/Resistance calculation
                resistance_5d_spike = df['high'].iloc[-5:].max()
                resistance_5d_close = df['close'].iloc[-5:].max()
                support_5d = df['low'].iloc[-5:].min()

                resistance_10d = df['high'].iloc[-10:].quantile(0.9)
                resistance_10d_close = df['close'].iloc[-10:].quantile(0.95)
                support_10d = df['low'].iloc[-10:].quantile(0.1)

                sma_10 = df['close'].iloc[-10:].mean()
                sma_20 = df['close'].iloc[-20:].mean()

                # Smart resistance selection
                if (resistance_5d_spike - resistance_5d_close) / resistance_5d_close > 0.01:
                    resistance = max(resistance_5d_close, resistance_10d_close)
                else:
                    resistance = resistance_5d_spike

                # Smart support selection
                if current_price > sma_10 and abs(current_price - sma_10) < current_price * 0.1:
                    support = sma_10
                elif abs(current_price - support_5d) / current_price < 0.1:
                    support = support_5d
                else:
                    support = support_10d

                # Calculate targets
                range_height = resistance - support
                target1 = resistance + (range_height * 0.5)
                target2 = resistance + (range_height * 1.0)

                # Downside targets (for shorts)
                downside1 = support - (range_height * 0.5)
                downside2 = support - (range_height * 1.0)

                # Risk/Reward
                potential_gain = ((target2 - current_price) / current_price) * 100
                risk_to_support = ((current_price - support) / current_price) * 100
                risk_reward = potential_gain / risk_to_support if risk_to_support > 0 else 0

                # Distance to levels
                dist_to_resistance = ((resistance - current_price) / current_price) * 100
                dist_to_support = ((current_price - support) / current_price) * 100

                # Scoring
                score = 0
                if abs(change_pct) >= 3:
                    score += 30
                elif abs(change_pct) >= 2:
                    score += 20
                elif abs(change_pct) >= 1:
                    score += 10

                if rvol >= 2.0:
                    score += 30
                elif rvol >= 1.5:
                    score += 20
                elif rvol >= 1.2:
                    score += 10

                if atr_pct >= 4:
                    score += 20
                elif atr_pct >= 3:
                    score += 15
                elif atr_pct >= 2:
                    score += 10

                if 0 < dist_to_resistance <= 2:
                    score += 25
                elif 2 < dist_to_resistance <= 3:
                    score += 15

                if risk_reward >= 3:
                    score += 20
                elif risk_reward >= 2:
                    score += 10

                result = {
                    'symbol': symbol,
                    'close': round(current_price, 2),
                    'change%': round(change_pct, 2),
                    'volume': int(today['volume']),
                    'rvol': round(rvol, 2),
                    'atr%': round(atr_pct, 2),
                    'resistance': round(resistance, 2),
                    'support': round(support, 2),
                    'dist_to_R%': round(dist_to_resistance, 2),
                    'dist_to_S%': round(dist_to_support, 2),
                    'target1': round(target1, 2),
                    'target2': round(target2, 2),
                    'downside1': round(downside1, 2),
                    'downside2': round(downside2, 2),
                    'risk_reward': round(risk_reward, 2),
                    'score': score,
                    'scan_date': scan_date.strftime('%Y-%m-%d')
                }

                results.append(result)
                print(f"[{i+1}/{len(symbols)}] {symbol}: ${current_price:.2f} Score:{score}")

            except Exception as e:
                print(f"[{i+1}/{len(symbols)}] {symbol}: Error - {e}")

            time.sleep(0.2)  # Rate limiting

        self.disconnect()
        return results


def run_monthly_backtest(year, month, account_size=100000):
    """Run scanner + backtest for each trading day in the month"""

    print(f"\n{'='*80}")
    print(f"MONTHLY BACKTEST: {year}-{month:02d}")
    print(f"{'='*80}\n")

    # Create output directory
    output_dir = Path(__file__).parent / 'monthly_results'
    output_dir.mkdir(exist_ok=True)

    # Import backtester
    sys.path.append(str(Path(__file__).parent))
    from backtester import PS60Backtester

    # Initialize scanner
    scanner = HistoricalScanner()

    # Get all days in the month
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    current_date = start_date
    all_results = []
    daily_results = []

    while current_date <= end_date:
        # Skip weekends
        if current_date.weekday() >= 5:  # Saturday=5, Sunday=6
            current_date += timedelta(days=1)
            continue

        date_str = current_date.strftime('%Y%m%d')
        print(f"\n{'='*80}")
        print(f"Processing {current_date.strftime('%Y-%m-%d')} ({current_date.strftime('%A')})")
        print(f"{'='*80}")

        try:
            # Step 1: Run scanner for this date
            print(f"\n[1/2] Running scanner...")
            scanner_results = scanner.scan_for_date(current_date)

            if not scanner_results or len(scanner_results) == 0:
                print(f"No scanner results for {date_str}, skipping...")
                current_date += timedelta(days=1)
                continue

            # Save scanner results
            scanner_file = output_dir / f'scanner_{date_str}.json'
            with open(scanner_file, 'w') as f:
                json.dump(scanner_results, f, indent=2)
            print(f"✓ Scanner found {len(scanner_results)} setups")
            print(f"✓ Saved to {scanner_file}")

            # Step 2: Run backtest using scanner results
            print(f"\n[2/2] Running backtest...")
            backtester = PS60Backtester(
                scanner_results_path=str(scanner_file),
                test_date=current_date,
                account_size=account_size
            )

            # Run backtest (it modifies backtester.trades internally)
            backtester.run()
            trades = backtester.trades

            if trades:
                # Calculate daily P&L
                total_pnl = sum(t['pnl'] for t in trades)
                winners = [t for t in trades if t['pnl'] > 0]
                losers = [t for t in trades if t['pnl'] < 0]
                win_rate = (len(winners) / len(trades) * 100) if trades else 0

                daily_summary = {
                    'date': current_date.strftime('%Y-%m-%d'),
                    'trades': len(trades),
                    'winners': len(winners),
                    'losers': len(losers),
                    'win_rate': round(win_rate, 1),
                    'total_pnl': round(total_pnl, 2),
                    'avg_pnl': round(total_pnl / len(trades), 2) if trades else 0
                }

                daily_results.append(daily_summary)
                all_results.extend(trades)

                print(f"\n✓ Backtest complete: {len(trades)} trades, ${total_pnl:,.2f} P&L")
            else:
                print(f"✓ Backtest complete: No trades")

        except Exception as e:
            print(f"✗ Error processing {date_str}: {e}")
            import traceback
            traceback.print_exc()

        current_date += timedelta(days=1)
        time.sleep(1)  # Small delay between days

    # Generate monthly summary
    if daily_results:
        print(f"\n{'='*80}")
        print(f"MONTHLY SUMMARY: {year}-{month:02d}")
        print(f"{'='*80}\n")

        df = pd.DataFrame(daily_results)
        print(df.to_string(index=False))

        total_trades = df['trades'].sum()
        total_pnl = df['total_pnl'].sum()
        avg_daily_pnl = df['total_pnl'].mean()
        winning_days = len(df[df['total_pnl'] > 0])
        losing_days = len(df[df['total_pnl'] < 0])
        overall_win_rate = (df['winners'].sum() / df['trades'].sum() * 100) if total_trades > 0 else 0

        print(f"\n{'='*80}")
        print(f"OVERALL STATISTICS")
        print(f"{'='*80}")
        print(f"Trading Days: {len(daily_results)}")
        print(f"Total Trades: {total_trades}")
        print(f"Total P&L: ${total_pnl:,.2f}")
        print(f"Avg Daily P&L: ${avg_daily_pnl:,.2f}")
        print(f"Win Rate: {overall_win_rate:.1f}%")
        print(f"Winning Days: {winning_days}/{len(daily_results)} ({winning_days/len(daily_results)*100:.1f}%)")
        print(f"Losing Days: {losing_days}/{len(daily_results)}")
        print(f"Monthly Return: {(total_pnl/account_size)*100:.2f}%")

        # Save results
        summary_file = output_dir / f'monthly_summary_{year}{month:02d}.json'
        with open(summary_file, 'w') as f:
            json.dump({
                'month': f'{year}-{month:02d}',
                'daily_results': daily_results,
                'summary': {
                    'trading_days': len(daily_results),
                    'total_trades': int(total_trades),
                    'total_pnl': round(total_pnl, 2),
                    'avg_daily_pnl': round(avg_daily_pnl, 2),
                    'win_rate': round(overall_win_rate, 1),
                    'winning_days': winning_days,
                    'losing_days': losing_days,
                    'monthly_return_pct': round((total_pnl/account_size)*100, 2)
                }
            }, f, indent=2)
        print(f"\n✓ Results saved to {summary_file}")

        # Save all trades
        trades_file = output_dir / f'all_trades_{year}{month:02d}.json'
        with open(trades_file, 'w') as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"✓ All trades saved to {trades_file}")
    else:
        print(f"\nNo trading days processed for {year}-{month:02d}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Run monthly backtest')
    parser.add_argument('--year', type=int, default=2025, help='Year')
    parser.add_argument('--month', type=int, default=9, help='Month (1-12)')
    parser.add_argument('--account-size', type=int, default=100000, help='Account size')

    args = parser.parse_args()

    run_monthly_backtest(args.year, args.month, args.account_size)
