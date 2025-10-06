#!/usr/bin/env python3
"""
PS60 Trading Scanner - Unified Version
Finds high-probability breakout setups with detailed analysis
"""

from ib_insync import *
from datetime import datetime, timedelta
import pandas as pd
import time
import json
from pathlib import Path
from tabulate import tabulate
import argparse
import pytz

class PS60Scanner:
    """Main scanner for PS60 trading setups"""

    def __init__(self):
        self.ib = None
        self.results = []
        self.failed = []

    def connect(self, client_id=1001):
        """Connect to IBKR TWS"""
        self.ib = IB()
        try:
            self.ib.connect('127.0.0.1', 7497, clientId=client_id)
            print(f"✓ Connected to IBKR (Client ID: {client_id})")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR"""
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
            print("✓ Disconnected from IBKR")

    def get_symbols(self, category='all'):
        """Get symbols to scan based on category"""

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

        if category == 'quick':
            # Top movers for quick scan
            return ['SPY', 'QQQ', 'TSLA', 'NVDA', 'AMD', 'GME', 'COIN', 'PLTR']
        elif category == 'all':
            # All symbols
            all_symbols = []
            for symbols in core_symbols.values():
                all_symbols.extend(symbols)
            return list(set(all_symbols))  # Remove duplicates
        else:
            return core_symbols.get(category, [])

    def analyze_breakout_levels(self, df, resistance, support, current_price):
        """Analyze why a level is significant and calculate targets"""
        reasons = []

        # Check if resistance is a spike or consolidation
        spike_high_5d = df['high'].iloc[-5:].max()
        close_high_5d = df['close'].iloc[-5:].max()
        if abs(spike_high_5d - resistance) < 1:  # If resistance is near spike high
            if (spike_high_5d - close_high_5d) / close_high_5d > 0.01:
                reasons.append(f"Consolidation zone (spike to ${spike_high_5d:.2f})")

        # Count resistance touches
        touches = 0
        for i in range(-20, 0):
            if abs(df.iloc[i]['high'] - resistance) / resistance < 0.015:
                touches += 1

        if touches >= 3:
            reasons.append(f"Tested {touches}x")
        elif touches >= 2:
            reasons.append("Double-tested")

        # Check for psychological levels
        if resistance % 10 == 0:
            reasons.append(f"Round ${resistance:.0f}")
        elif resistance % 5 == 0:
            reasons.append(f"${resistance:.0f} level")

        # Historical significance - check both highs and closes
        high_20d = df['high'].iloc[-20:].max()
        high_10d = df['high'].iloc[-10:].max()
        high_5d = df['high'].iloc[-5:].max()
        close_5d = df['close'].iloc[-5:].max()

        if abs(resistance - high_20d) < 1:
            reasons.append("20-day high")
        elif abs(resistance - high_10d) < 1:
            reasons.append("10-day high")
        elif abs(resistance - high_5d) < 1:
            reasons.append("5-day high")
        elif abs(resistance - close_5d) < 1:
            reasons.append("5-day closing high")

        # Pattern detection
        recent_range = df['high'].iloc[-5:].max() - df['low'].iloc[-5:].min()
        avg_range = (df['high'] - df['low']).iloc[-20:].mean()
        if recent_range < avg_range * 0.7:
            reasons.append("Tight consolidation")

        # Calculate targets using measured moves
        range_height = resistance - support

        # Upside targets
        target1 = resistance + (range_height * 0.5)   # Conservative
        target2 = resistance + (range_height * 1.0)   # Standard
        target3 = resistance + (range_height * 1.618) # Fibonacci

        # Downside targets
        downside1 = support - (range_height * 0.5)
        downside2 = support - (range_height * 1.0)

        # Risk/Reward calculation
        potential_gain = ((target2 - current_price) / current_price) * 100
        risk_to_support = ((current_price - support) / current_price) * 100
        risk_reward = potential_gain / risk_to_support if risk_to_support > 0 else 0

        return {
            'reasoning': ' | '.join(reasons) if reasons else 'Technical level',
            'target1': round(target1, 2),
            'target2': round(target2, 2),
            'target3': round(target3, 2),
            'downside1': round(downside1, 2),
            'downside2': round(downside2, 2),
            'potential_gain%': round(potential_gain, 2),
            'risk%': round(risk_to_support, 2),
            'risk_reward': round(risk_reward, 2)
        }

    def scan_symbol(self, symbol, historical_date=None):
        """
        Scan a single symbol

        Args:
            symbol: Stock symbol to scan
            historical_date: Optional date (datetime.date) to scan as of that date
                           Uses data UP TO this date (no look-ahead bias)
        """
        try:
            # Create and qualify contract
            contract = Stock(symbol, 'SMART', 'USD')
            if not self.ib.qualifyContracts(contract):
                return None

            # Set end date for historical data
            if historical_date:
                # Use end of day for the historical date
                end_datetime = historical_date.strftime('%Y%m%d 23:59:59')
            else:
                # Current/live data
                end_datetime = ''

            # Get historical data
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime=end_datetime,
                durationStr='30 D',
                barSizeSetting='1 day',
                whatToShow='TRADES',
                useRTH=False,
                formatDate=1
            )

            if not bars or len(bars) < 20:
                return None

            # Convert to DataFrame
            df = util.df(bars)

            # Get current and previous day
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            current_price = today['close']

            # Calculate key metrics
            # 1. Price change
            change_pct = ((current_price - yesterday['close']) / yesterday['close']) * 100

            # 2. Volume analysis
            avg_volume = df['volume'].iloc[-21:-1].mean()
            rvol = today['volume'] / avg_volume if avg_volume > 0 else 0

            # 3. ATR (volatility)
            tr_list = []
            for i in range(1, len(df)):
                high_low = df.iloc[i]['high'] - df.iloc[i]['low']
                high_close = abs(df.iloc[i]['high'] - df.iloc[i-1]['close'])
                low_close = abs(df.iloc[i]['low'] - df.iloc[i-1]['close'])
                tr_list.append(max(high_low, high_close, low_close))
            atr = pd.Series(tr_list).iloc[-14:].mean() if len(tr_list) >= 14 else 0
            atr_pct = (atr / current_price) * 100

            # 4. Smart support/resistance calculation
            # Near-term levels (5-day)
            resistance_5d_spike = df['high'].iloc[-5:].max()  # Spike high
            resistance_5d_close = df['close'].iloc[-5:].max()  # Closing high (more reliable)
            support_5d = df['low'].iloc[-5:].min()

            # Filter outliers using quantiles (10-day)
            resistance_10d = df['high'].iloc[-10:].quantile(0.9)
            resistance_10d_close = df['close'].iloc[-10:].quantile(0.95)  # Where price actually closed
            support_10d = df['low'].iloc[-10:].quantile(0.1)

            # Moving averages
            sma_10 = df['close'].iloc[-10:].mean()
            sma_20 = df['close'].iloc[-20:].mean()

            # Smart resistance selection - prefer consolidation zones over spike highs
            # If spike high is >1% above closing high, use closing high as true resistance
            if (resistance_5d_spike - resistance_5d_close) / resistance_5d_close > 0.01:
                # Spike detected - use closing high or 90th percentile
                resistance = max(resistance_5d_close, resistance_10d_close)
            else:
                # No significant spike - use the actual high
                resistance = resistance_5d_spike

            # Smart support selection
            if current_price > sma_10 and abs(current_price - sma_10) < current_price * 0.1:
                support = sma_10
            elif abs(current_price - support_5d) / current_price < 0.1:
                support = support_5d
            else:
                support = support_10d

            # Get detailed breakout analysis
            analysis = self.analyze_breakout_levels(df, resistance, support, current_price)

            # Calculate distances
            dist_to_resistance = ((resistance - current_price) / current_price) * 100
            dist_to_support = ((current_price - support) / current_price) * 100

            # Score the setup
            score = 0
            setup_factors = []

            # Momentum scoring
            if abs(change_pct) >= 3:
                score += 30
                setup_factors.append(f"Strong {'up' if change_pct > 0 else 'down'} {change_pct:+.1f}%")
            elif abs(change_pct) >= 2:
                score += 20
                setup_factors.append(f"Moderate move {change_pct:+.1f}%")
            elif abs(change_pct) >= 1:
                score += 10

            # Volume scoring
            if rvol >= 2.0:
                score += 30
                setup_factors.append(f"High volume {rvol:.1f}x")
            elif rvol >= 1.5:
                score += 20
                setup_factors.append(f"Elevated volume {rvol:.1f}x")
            elif rvol >= 1.2:
                score += 10

            # Volatility scoring
            if atr_pct >= 4:
                score += 20
                setup_factors.append(f"High volatility {atr_pct:.1f}%")
            elif atr_pct >= 3:
                score += 15
                setup_factors.append(f"Good volatility {atr_pct:.1f}%")
            elif atr_pct >= 2:
                score += 10

            # Breakout proximity scoring
            if 0 < dist_to_resistance <= 2:
                score += 25
                setup_factors.append(f"Near breakout ({dist_to_resistance:.1f}%)")
            elif 2 < dist_to_resistance <= 3:
                score += 15
                setup_factors.append(f"Approaching breakout")

            # Already breaking out
            if current_price > resistance and rvol >= 1.2:
                score += 30
                setup_factors.append("BREAKING OUT")

            # Risk/Reward bonus
            if analysis['risk_reward'] >= 3:
                score += 20
                setup_factors.append(f"Excellent R/R {analysis['risk_reward']:.1f}:1")
            elif analysis['risk_reward'] >= 2:
                score += 10
                setup_factors.append(f"Good R/R {analysis['risk_reward']:.1f}:1")

            # Trend alignment
            if current_price > sma_10 > sma_20:
                score += 10
                setup_factors.append("Uptrend")

            return {
                'symbol': symbol,
                'close': round(current_price, 2),
                'change%': round(change_pct, 2),
                'volume': int(today['volume']),
                'volume_M': round(today['volume'] / 1e6, 1),
                'rvol': round(rvol, 2),
                'atr%': round(atr_pct, 2),
                'resistance': round(resistance, 2),
                'support': round(support, 2),
                'dist_to_R%': round(dist_to_resistance, 2),
                'dist_to_S%': round(dist_to_support, 2),
                'breakout_reason': analysis['reasoning'],
                'target1': analysis['target1'],
                'target2': analysis['target2'],
                'target3': analysis['target3'],
                'downside1': analysis['downside1'],
                'downside2': analysis['downside2'],
                'potential_gain%': analysis['potential_gain%'],
                'risk%': analysis['risk%'],
                'risk_reward': analysis['risk_reward'],
                'sma10': round(sma_10, 2),
                'sma20': round(sma_20, 2),
                'score': score,
                'setup': ' | '.join(setup_factors) if setup_factors else 'No setup'
            }

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            return None

    def run_scan(self, symbols=None, category='all', historical_date=None):
        """
        Run the full scan

        Args:
            symbols: List of symbols to scan (optional)
            category: Category to scan if symbols not provided
            historical_date: Optional date (datetime.date) to scan as of that date
        """
        print("\n" + "="*80)
        if historical_date:
            print(f"PS60 BREAKOUT SCANNER - HISTORICAL ({historical_date.strftime('%Y-%m-%d')})")
        else:
            print("PS60 BREAKOUT SCANNER - TOMORROW'S TRADING SETUPS")
        print("="*80)
        print(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*80)

        if not self.connect():
            return False

        try:
            # Get symbols
            if symbols:
                scan_symbols = symbols
            else:
                scan_symbols = self.get_symbols(category)

            print(f"\nScanning {len(scan_symbols)} symbols...")
            print("-"*80)

            # Scan each symbol
            for i, symbol in enumerate(scan_symbols):
                print(f"[{i+1}/{len(scan_symbols)}] {symbol}...", end=' ')

                result = self.scan_symbol(symbol, historical_date=historical_date)

                if result:
                    self.results.append(result)

                    # Status indicator
                    if result['score'] >= 60:
                        status = "🚀"
                    elif result['score'] >= 40:
                        status = "⭐"
                    else:
                        status = "✓"

                    print(f"{status} ${result['close']} ({result['change%']:+.1f}%) Score:{result['score']}")
                else:
                    self.failed.append(symbol)
                    print("✗ Failed")

                # Rate limiting
                time.sleep(0.2)

                # Progress update
                if (i + 1) % 10 == 0:
                    print(f"\nProgress: {i+1}/{len(scan_symbols)} completed\n")

            # Process and display results
            self.display_results()
            self.save_results()

            return True

        except Exception as e:
            print(f"\nScan error: {e}")
            return False

        finally:
            self.disconnect()

    def display_results(self):
        """Display scan results with analysis"""
        if not self.results:
            print("\nNo results to display")
            return

        # Sort by score and breakout proximity
        self.results.sort(key=lambda x: (-x['score'], x['dist_to_R%'] if x['dist_to_R%'] > 0 else 999))

        print("\n" + "="*80)
        print("🎯 TOP BREAKOUT CANDIDATES (DETAILED ANALYSIS)")
        print("="*80)

        # Top candidates with full analysis
        top_candidates = [r for r in self.results if r['score'] >= 40][:5]

        for r in top_candidates:
            print(f"\n{'='*60}")
            print(f"📊 {r['symbol']} - Score: {r['score']}")
            print(f"{'='*60}")

            print(f"\n📈 CURRENT STATUS:")
            print(f"  Price: ${r['close']} ({r['change%']:+.2f}% today)")
            print(f"  Volume: {r['volume_M']:.1f}M (RVOL: {r['rvol']:.1f}x)")
            print(f"  Volatility: {r['atr%']:.1f}% ATR")

            print(f"\n🎯 KEY LEVELS:")
            print(f"  Resistance: ${r['resistance']} ({r['dist_to_R%']:+.1f}% away)")
            print(f"  Support: ${r['support']} ({r['dist_to_S%']:.1f}% below)")
            print(f"  Why ${r['resistance']}? {r['breakout_reason']}")

            print(f"\n🚀 ROOM TO RUN (if breaks ${r['resistance']}):")
            print(f"  Target 1: ${r['target1']} (+{((r['target1']-r['close'])/r['close']*100):.1f}%)")
            print(f"  Target 2: ${r['target2']} (+{((r['target2']-r['close'])/r['close']*100):.1f}%)")
            print(f"  Target 3: ${r['target3']} (+{((r['target3']-r['close'])/r['close']*100):.1f}%)")

            print(f"\n⚖️ RISK/REWARD:")
            print(f"  Potential Gain: {r['potential_gain%']:.1f}%")
            print(f"  Risk to Support: {r['risk%']:.1f}%")
            print(f"  Risk/Reward Ratio: {r['risk_reward']:.1f}:1")

            print(f"\n💡 SETUP FACTORS:")
            print(f"  {r['setup']}")

        # Summary table
        print("\n" + "="*80)
        print("SUMMARY TABLE - ALL HIGH-SCORE SETUPS (Score ≥30)")
        print("="*80)

        high_score = [r for r in self.results if r['score'] >= 30]
        if high_score:
            df_display = pd.DataFrame(high_score)[
                ['symbol', 'close', 'change%', 'dist_to_R%', 'target2', 'risk_reward', 'score']
            ].head(20)
            print(tabulate(df_display, headers='keys', tablefmt='grid', showindex=False))

        # Market overview
        print("\n" + "="*80)
        print("MARKET OVERVIEW")
        print("="*80)

        df = pd.DataFrame(self.results)
        up = len(df[df['change%'] > 0])
        down = len(df[df['change%'] < 0])

        print(f"Market Breadth: {up} up / {down} down")
        print(f"High Scores (≥40): {len([r for r in self.results if r['score'] >= 40])} stocks")
        print(f"Near Breakout (<3% from R): {len([r for r in self.results if 0 < r['dist_to_R%'] <= 3])} stocks")
        print(f"High Volatility (≥3% ATR): {len([r for r in self.results if r['atr%'] >= 3])} stocks")
        print(f"Average Risk/Reward: {df['risk_reward'].mean():.2f}:1")

        if self.failed:
            print(f"\nFailed to scan: {', '.join(self.failed)}")

    def get_next_trading_date(self):
        """
        Determine the trading date for this scan based on current time.

        Logic:
        - Before 4:00 PM ET: Use today's date (scan for today's session)
        - After 4:00 PM ET: Use next weekday's date (scan for next session)
        - Weekends: Use next Monday's date
        """
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(pytz.UTC).astimezone(eastern)

        # Market close time (4:00 PM ET)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

        # If it's a weekend, use next Monday
        if now_et.weekday() >= 5:  # Saturday = 5, Sunday = 6
            days_until_monday = 7 - now_et.weekday()
            trading_date = now_et + timedelta(days=days_until_monday)
        # If before market close, use today
        elif now_et < market_close:
            trading_date = now_et
        # If after market close, use next trading day
        else:
            # If Friday after close, use Monday
            if now_et.weekday() == 4:  # Friday
                trading_date = now_et + timedelta(days=3)
            else:
                trading_date = now_et + timedelta(days=1)

        return trading_date.strftime('%Y%m%d')

    def save_results(self):
        """Save results to files"""
        if not self.results:
            return

        # Create output directory
        Path('output').mkdir(exist_ok=True)

        # Save to CSV
        df = pd.DataFrame(self.results)

        # Get the trading date this scan is for
        trading_date = self.get_next_trading_date()
        csv_filename = f'output/scanner_results_{trading_date}.csv'
        json_filename = f'output/scanner_results_{trading_date}.json'

        # Save with dated filenames
        df.to_csv(csv_filename, index=False)
        with open(json_filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        # Also save as latest (for backward compatibility)
        df.to_csv('output/scanner_results.csv', index=False)
        with open('output/scanner_results.json', 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"\n✅ Results saved to:")
        print(f"   - {csv_filename}")
        print(f"   - {json_filename}")
        print(f"   - output/scanner_results.csv (latest)")
        print(f"   - output/scanner_results.json (latest)")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='PS60 Breakout Scanner')
    parser.add_argument('--symbols', nargs='+', help='Specific symbols to scan')
    parser.add_argument('--category', default='all',
                       choices=['all', 'quick', 'indices', 'mega_tech', 'semis',
                               'high_vol', 'meme', 'finance', 'energy', 'china'],
                       help='Category of symbols to scan')
    parser.add_argument('--client-id', type=int, default=1001, help='TWS client ID')

    args = parser.parse_args()

    scanner = PS60Scanner()
    success = scanner.run_scan(symbols=args.symbols, category=args.category)

    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())