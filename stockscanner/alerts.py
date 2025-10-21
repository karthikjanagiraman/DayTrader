#!/usr/bin/env python3
"""
Alert Module for PS60 Scanner
Monitors scanner results and generates alerts for resistance/support levels
"""

from ib_insync import *
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import time

class AlertManager:
    """Manages price alerts for scanner results"""

    def __init__(self, scanner_results_file=None):
        """
        Initialize alert manager

        Args:
            scanner_results_file: Path to scanner results JSON file
        """
        self.ib = None
        self.alerts = []
        self.scanner_results_file = scanner_results_file or "output/scanner_results.json"
        self.active_alerts = {}

    def connect(self, client_id=1010):
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

    def load_scanner_results(self):
        """Load scanner results from JSON file"""
        try:
            with open(self.scanner_results_file, 'r') as f:
                results = json.load(f)
            print(f"✓ Loaded {len(results)} stocks from {self.scanner_results_file}")
            return results
        except FileNotFoundError:
            print(f"✗ Scanner results file not found: {self.scanner_results_file}")
            return []
        except Exception as e:
            print(f"✗ Error loading scanner results: {e}")
            return []

    def create_alerts(self, threshold_pct=2.0):
        """
        Create alerts for all stocks in scanner results

        Args:
            threshold_pct: Alert when price is within this % of resistance/support
        """
        results = self.load_scanner_results()

        for stock in results:
            symbol = stock['symbol']
            resistance = stock.get('resistance')
            support = stock.get('support')
            current_price = stock.get('close')

            if resistance:
                # Alert when price approaches resistance (within threshold_pct)
                alert_price = resistance * (1 - threshold_pct / 100)
                self.alerts.append({
                    'symbol': symbol,
                    'type': 'RESISTANCE',
                    'trigger_price': alert_price,
                    'target_price': resistance,
                    'current_price': current_price,
                    'threshold_pct': threshold_pct,
                    'targets': {
                        'T1': stock.get('target1'),
                        'T2': stock.get('target2'),
                        'T3': stock.get('target3')
                    }
                })

            if support:
                # Alert when price approaches support (within threshold_pct)
                alert_price = support * (1 + threshold_pct / 100)
                self.alerts.append({
                    'symbol': symbol,
                    'type': 'SUPPORT',
                    'trigger_price': alert_price,
                    'target_price': support,
                    'current_price': current_price,
                    'threshold_pct': threshold_pct,
                    'downside': {
                        'D1': stock.get('downside1'),
                        'D2': stock.get('downside2')
                    }
                })

        print(f"✓ Created {len(self.alerts)} alerts ({len(self.alerts)//2} stocks)")
        return self.alerts

    def generate_tradingview_alerts(self, output_file="output/tradingview_alerts.txt"):
        """
        Generate TradingView-compatible alert messages

        Output format:
        SYMBOL: Alert when price crosses RESISTANCE_PRICE (resistance at XXX)
        """
        if not self.alerts:
            self.create_alerts()

        lines = []
        lines.append("=" * 80)
        lines.append("TRADINGVIEW PRICE ALERTS - PS60 Scanner")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Total Alerts: {len(self.alerts)}")
        lines.append("=" * 80)
        lines.append("")

        # Group by symbol
        symbols = sorted(set(a['symbol'] for a in self.alerts))

        for symbol in symbols:
            symbol_alerts = [a for a in self.alerts if a['symbol'] == symbol]

            lines.append(f"\n{'='*80}")
            lines.append(f"SYMBOL: {symbol}")
            lines.append('='*80)

            for alert in symbol_alerts:
                if alert['type'] == 'RESISTANCE':
                    lines.append(f"\n🔼 RESISTANCE ALERT:")
                    lines.append(f"   Alert Trigger: ${alert['trigger_price']:.2f} (within {alert['threshold_pct']}% of resistance)")
                    lines.append(f"   Resistance Level: ${alert['target_price']:.2f}")
                    lines.append(f"   Current Price: ${alert['current_price']:.2f}")
                    lines.append(f"   Distance: {((alert['target_price'] - alert['current_price']) / alert['current_price'] * 100):.2f}%")

                    if alert['targets']['T1']:
                        lines.append(f"\n   Breakout Targets:")
                        lines.append(f"      T1: ${alert['targets']['T1']:.2f}")
                        lines.append(f"      T2: ${alert['targets']['T2']:.2f}")
                        lines.append(f"      T3: ${alert['targets']['T3']:.2f}")

                    lines.append(f"\n   📝 TradingView Alert Setup:")
                    lines.append(f"      Condition: {symbol} price crosses above ${alert['trigger_price']:.2f}")
                    lines.append(f"      Message: {symbol} approaching resistance ${alert['target_price']:.2f} - prepare for breakout")

                else:  # SUPPORT
                    lines.append(f"\n🔽 SUPPORT ALERT:")
                    lines.append(f"   Alert Trigger: ${alert['trigger_price']:.2f} (within {alert['threshold_pct']}% of support)")
                    lines.append(f"   Support Level: ${alert['target_price']:.2f}")
                    lines.append(f"   Current Price: ${alert['current_price']:.2f}")
                    lines.append(f"   Distance: {((alert['current_price'] - alert['target_price']) / alert['current_price'] * 100):.2f}%")

                    if alert['downside']['D1']:
                        lines.append(f"\n   Breakdown Targets:")
                        lines.append(f"      D1: ${alert['downside']['D1']:.2f}")
                        lines.append(f"      D2: ${alert['downside']['D2']:.2f}")

                    lines.append(f"\n   📝 TradingView Alert Setup:")
                    lines.append(f"      Condition: {symbol} price crosses below ${alert['trigger_price']:.2f}")
                    lines.append(f"      Message: {symbol} approaching support ${alert['target_price']:.2f} - prepare for breakdown")

        # Write to file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"\n✓ TradingView alerts saved to: {output_file}")

        # Also print to console
        print('\n'.join(lines))

        return output_path

    def generate_alert_json(self, output_file="output/alerts.json"):
        """Generate JSON file with all alerts for API integration"""
        if not self.alerts:
            self.create_alerts()

        alert_data = {
            'generated_at': datetime.now().isoformat(),
            'total_alerts': len(self.alerts),
            'alerts': self.alerts
        }

        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(alert_data, f, indent=2)

        print(f"✓ Alert JSON saved to: {output_file}")
        return output_path

    def monitor_prices(self, check_interval=60):
        """
        Monitor real-time prices and trigger alerts

        Args:
            check_interval: Seconds between price checks
        """
        if not self.ib or not self.ib.isConnected():
            print("✗ Not connected to IBKR. Call connect() first.")
            return

        if not self.alerts:
            self.create_alerts()

        print(f"\n{'='*80}")
        print("🔔 STARTING PRICE MONITORING")
        print('='*80)
        print(f"Monitoring {len(set(a['symbol'] for a in self.alerts))} symbols")
        print(f"Check interval: {check_interval} seconds")
        print(f"Press Ctrl+C to stop")
        print('='*80)

        try:
            while True:
                triggered_alerts = self.check_alerts()

                if triggered_alerts:
                    print(f"\n⚠️  {len(triggered_alerts)} ALERTS TRIGGERED!")
                    for alert in triggered_alerts:
                        self.print_alert(alert)

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n✓ Monitoring stopped by user")

    def check_alerts(self):
        """Check current prices against alert triggers"""
        triggered = []

        for alert in self.alerts:
            symbol = alert['symbol']

            # Skip if already triggered
            alert_key = f"{symbol}_{alert['type']}"
            if alert_key in self.active_alerts:
                continue

            # Get current price
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            ticker = self.ib.reqMktData(contract)
            self.ib.sleep(1)  # Wait for data

            current_price = ticker.last if ticker.last else ticker.close

            if current_price:
                # Check if alert should trigger
                if alert['type'] == 'RESISTANCE':
                    if current_price >= alert['trigger_price']:
                        alert['triggered_price'] = current_price
                        alert['triggered_at'] = datetime.now().isoformat()
                        triggered.append(alert)
                        self.active_alerts[alert_key] = alert

                else:  # SUPPORT
                    if current_price <= alert['trigger_price']:
                        alert['triggered_price'] = current_price
                        alert['triggered_at'] = datetime.now().isoformat()
                        triggered.append(alert)
                        self.active_alerts[alert_key] = alert

            # Cancel market data subscription
            self.ib.cancelMktData(contract)

        return triggered

    def print_alert(self, alert):
        """Print formatted alert message"""
        print(f"\n{'='*80}")
        print(f"🚨 ALERT TRIGGERED: {alert['symbol']}")
        print('='*80)
        print(f"Type: {alert['type']}")
        print(f"Triggered Price: ${alert['triggered_price']:.2f}")
        print(f"Target Level: ${alert['target_price']:.2f}")
        print(f"Triggered At: {alert['triggered_at']}")

        if alert['type'] == 'RESISTANCE':
            print(f"\n🔼 Price approaching RESISTANCE at ${alert['target_price']:.2f}")
            print(f"   Watch for breakout above ${alert['target_price']:.2f}")
            if alert['targets']['T1']:
                print(f"   Breakout targets: T1=${alert['targets']['T1']:.2f}, T2=${alert['targets']['T2']:.2f}")
        else:
            print(f"\n🔽 Price approaching SUPPORT at ${alert['target_price']:.2f}")
            print(f"   Watch for breakdown below ${alert['target_price']:.2f}")
            if alert['downside']['D1']:
                print(f"   Breakdown targets: D1=${alert['downside']['D1']:.2f}, D2=${alert['downside']['D2']:.2f}")

        print('='*80)


def main():
    """Main function for running alerts"""
    import argparse

    parser = argparse.ArgumentParser(description='PS60 Scanner Alert System')
    parser.add_argument('--scanner-file', default='output/scanner_results.json',
                       help='Scanner results JSON file')
    parser.add_argument('--threshold', type=float, default=2.0,
                       help='Alert threshold percentage (default: 2.0%)')
    parser.add_argument('--monitor', action='store_true',
                       help='Monitor prices in real-time')
    parser.add_argument('--interval', type=int, default=60,
                       help='Price check interval in seconds (default: 60)')
    parser.add_argument('--tradingview', action='store_true',
                       help='Generate TradingView alert instructions')
    parser.add_argument('--json', action='store_true',
                       help='Generate JSON alert file')

    args = parser.parse_args()

    # Initialize alert manager
    manager = AlertManager(scanner_results_file=args.scanner_file)

    # Create alerts
    manager.create_alerts(threshold_pct=args.threshold)

    # Generate TradingView alerts
    if args.tradingview:
        manager.generate_tradingview_alerts()

    # Generate JSON
    if args.json:
        manager.generate_alert_json()

    # Monitor prices
    if args.monitor:
        if manager.connect():
            manager.monitor_prices(check_interval=args.interval)
            manager.disconnect()

    # If no specific action, generate TradingView by default
    if not (args.monitor or args.tradingview or args.json):
        manager.generate_tradingview_alerts()


if __name__ == '__main__':
    main()
