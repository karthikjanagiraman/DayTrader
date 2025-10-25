#!/usr/bin/env python3
"""
Analyze trading session for October 23, 2025
Generates comprehensive session analysis report per requirements document
"""

import re
from datetime import datetime
from collections import defaultdict
import json

LOG_FILE = "logs/trader_20251023.log"
OUTPUT_FILE = "analysis/TRADING_SESSION_ANALYSIS_20251023.md"

# Data structures
trades = []
blocked_entries = []
cvd_events = []
filter_stats = defaultdict(lambda: {"checks": 0, "blocks": 0})

def parse_log():
    """Parse the log file and extract all relevant data"""

    with open(LOG_FILE, 'r') as f:
        lines = f.readlines()

    # Track current trade
    current_trade = None

    for i, line in enumerate(lines):
        # Extract timestamp
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if not match:
            continue
        timestamp = match.group(1)

        # Find trade entries (look for CVD monitoring entering trades)
        if "⚡ STRONG" in line and "ENTER!" in line:
            symbol_match = re.search(r'\[CVD_MONITORING\] (\w+):', line)
            if symbol_match:
                symbol = symbol_match.group(1)
                # Determine side
                if "SELLING PRESSURE" in line:
                    side = "SHORT"
                elif "BUYING PRESSURE" in line:
                    side = "LONG"
                else:
                    side = "UNKNOWN"

                # Extract imbalance
                imb_match = re.search(r'([-\d.]+)%', line)
                imbalance = imb_match.group(1) if imb_match else "N/A"

                print(f"Found potential entry: {symbol} {side} at {timestamp}, imbalance {imbalance}%")

        # Find partials
        if "💰 PARTIAL" in line:
            match = re.search(r'PARTIAL (\d+)% (\w+) @ \$([\\d.]+) \(([+-\$\\d.]+)', line)
            if match:
                pct, symbol, price, pnl = match.groups()
                print(f"Found partial: {symbol} {pct}% @ ${price}, P&L: {pnl}")

        # Find exits
        if "🛑 CLOSE" in line:
            match = re.search(r'CLOSE (\w+) @ \$([\\d.]+) \((\w+)', line)
            if match:
                symbol, price, reason = match.groups()
                print(f"Found exit: {symbol} @ ${price}, reason: {reason}")

        # Find blocked entries
        if "❌" in line and "blocked @" in line:
            match = re.search(r'❌ (\w+): (\w+) blocked @ \$([\\d.]+) - (.+)', line)
            if match:
                symbol, side, price, reason = match.groups()
                blocked_entries.append({
                    "timestamp": timestamp,
                    "symbol": symbol,
                    "side": side,
                    "price": price,
                    "reason": reason
                })

        # Find CVD events
        if "[CVD_MONITORING]" in line:
            # Extract CVD data
            if "CVD from TICKS" in line:
                match = re.search(r'(\w+) Bar (\d+):.*imbalance=([-\d.]+)%.*buy=(\d+).*sell=(\d+)', line)
                if match:
                    symbol, bar, imbalance, buy_vol, sell_vol = match.groups()
                    cvd_events.append({
                        "timestamp": timestamp,
                        "symbol": symbol,
                        "bar": bar,
                        "imbalance_pct": imbalance,
                        "buy_volume": buy_vol,
                        "sell_volume": sell_vol
                    })

    print(f"\nParsing complete:")
    print(f"  Blocked entries: {len(blocked_entries)}")
    print(f"  CVD events: {len(cvd_events)}")

def generate_report():
    """Generate the comprehensive markdown report"""

    report = []
    report.append("# Trading Session Analysis - October 23, 2025\n")
    report.append("**Generated**: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
    report.append("**Session Type**: Live Paper Trading\n")
    report.append("**Log File**: `trader/logs/trader_20251023.log`\n\n")
    report.append("---\n\n")

    # Section 1: Executive Summary
    report.append("## 1. Executive Summary\n\n")
    report.append(f"- **Blocked Entries**: {len(blocked_entries)}\n")
    report.append(f"- **CVD Events Detected**: {len(cvd_events)}\n\n")

    # Section 4: Blocked Entry Analysis
    report.append("## 4. Blocked Entry Analysis\n\n")
    report.append("| Time | Symbol | Side | Price | Reason |\n")
    report.append("|------|--------|------|-------|--------|\n")
    for entry in blocked_entries[:50]:  # First 50
        report.append(f"| {entry['timestamp']} | {entry['symbol']} | {entry['side']} | ${entry['price']} | {entry['reason']} |\n")

    report.append(f"\n**Total Blocked Entries**: {len(blocked_entries)}\n\n")

    # Section 5: CVD Activity Log
    report.append("## 5. CVD Activity Log\n\n")
    report.append("### CVD Signals Detected\n\n")

    # Group by symbol
    by_symbol = defaultdict(list)
    for event in cvd_events:
        by_symbol[event['symbol']].append(event)

    for symbol, events in by_symbol.items():
        report.append(f"#### {symbol} ({len(events)} CVD signals)\n\n")
        report.append("| Time | Bar | Imbalance % | Buy Volume | Sell Volume |\n")
        report.append("|------|-----|-------------|------------|-------------|\n")
        for event in events[:20]:  # First 20 per symbol
            report.append(f"| {event['timestamp']} | {event['bar']} | {event['imbalance_pct']}% | {event['buy_volume']} | {event['sell_volume']} |\n")
        report.append("\n")

    # Write report
    with open(OUTPUT_FILE, 'w') as f:
        f.write(''.join(report))

    print(f"\nReport generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    print("Starting session analysis for October 23, 2025...")
    parse_log()
    generate_report()
    print("\nAnalysis complete!")
