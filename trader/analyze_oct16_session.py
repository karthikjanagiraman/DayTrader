#!/usr/bin/env python3
"""
Analyze October 16, 2025 trading session
Extract all trades with entry paths and filter details
"""

import re
import json
import csv
from datetime import datetime
from collections import defaultdict

LOG_FILE = "/Users/karthik/projects/DayTrader/trader/logs/trader_20251016.log"
OUTPUT_CSV = "/Users/karthik/projects/DayTrader/trader/trades_oct16_detailed.csv"
OUTPUT_JSON = "/Users/karthik/projects/DayTrader/trader/trades_oct16_detailed.json"
REPORT_FILE = "/Users/karthik/projects/DayTrader/trader/OCT16_SESSION_REPORT.md"

def parse_log():
    """Parse log file and extract all trades with details"""
    trades = []
    entries = {}

    with open(LOG_FILE, 'r') as f:
        for line in f:
            # Entry signals
            if '🟢 LONG' in line or '🟢 SHORT' in line:
                match = re.search(r'🟢 (LONG|SHORT) (\w+) @ \$([0-9.]+) \(([^)]+)\)', line)
                if match:
                    side, symbol, price, timestamp = match.groups()
                    entries[symbol] = {
                        'symbol': symbol,
                        'side': side,
                        'entry_price': float(price),
                        'entry_time': timestamp,
                        'exit_price': None,
                        'exit_time': None,
                        'exit_reason': None,
                        'pnl': 0.0,
                        'shares': 0,
                        'partials': [],
                        'entry_path': 'Unknown',
                        'filters_passed': []
                    }

            # Entry path details
            elif 'confirmed via' in line:
                match = re.search(r'(\w+).*confirmed via (.*?)(?:\(|$)', line)
                if match:
                    symbol = match.group(1)
                    path = match.group(2).strip()
                    if symbol in entries:
                        entries[symbol]['entry_path'] = path

            # Partials
            elif '💰 PARTIAL' in line:
                match = re.search(r'PARTIAL \d+% (\w+) @ \$([0-9.]+) \(\+\$([0-9.]+)', line)
                if match:
                    symbol, price, profit = match.groups()
                    if symbol in entries:
                        entries[symbol]['partials'].append({
                            'price': float(price),
                            'profit': float(profit)
                        })

            # Exits
            elif '🛑 CLOSE' in line:
                match = re.search(r'CLOSE (\w+) @ \$([0-9.]+) \(([^)]+)\)', line)
                if match:
                    symbol, price, reason = match.groups()
                    if symbol in entries:
                        entries[symbol]['exit_price'] = float(price)
                        entries[symbol]['exit_reason'] = reason

                        # Extract time
                        time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        if time_match:
                            entries[symbol]['exit_time'] = time_match.group(1)

    # Convert to list and calculate P&L
    for symbol, trade in entries.items():
        if trade['exit_price']:
            if trade['side'] == 'LONG':
                trade['pnl'] = trade['exit_price'] - trade['entry_price']
            else:  # SHORT
                trade['pnl'] = trade['entry_price'] - trade['exit_price']

            # Add partial profits
            for partial in trade['partials']:
                trade['pnl'] += partial['profit']

            trades.append(trade)

    return trades

def generate_report(trades):
    """Generate markdown report"""
    total_pnl = sum(t['pnl'] for t in trades)
    winners = [t for t in trades if t['pnl'] > 0]
    losers = [t for t in trades if t['pnl'] <= 0]

    # Entry path analysis
    entry_paths = defaultdict(lambda: {'count': 0, 'pnl': 0.0})
    for t in trades:
        path = t['entry_path']
        entry_paths[path]['count'] += 1
        entry_paths[path]['pnl'] += t['pnl']

    # Exit reason analysis
    exit_reasons = defaultdict(lambda: {'count': 0, 'pnl': 0.0})
    for t in trades:
        reason = t['exit_reason']
        exit_reasons[reason]['count'] += 1
        exit_reasons[reason]['pnl'] += t['pnl']

    report = f"""# October 16, 2025 Trading Session Report

## Executive Summary

**Date**: October 16, 2025 (Wednesday)
**Session Duration**: 09:49 AM - 11:44 AM ET (~2 hours)
**Total Trades**: {len(trades)}
**Realized P&L**: ${total_pnl:.2f}

**Win Rate**: {len(winners)}/{len(trades)} = {len(winners)/len(trades)*100 if trades else 0:.1f}%
**Winners**: {len(winners)} trades (Avg: ${sum(t['pnl'] for t in winners)/len(winners) if winners else 0:.2f})
**Losers**: {len(losers)} trades (Avg: ${sum(t['pnl'] for t in losers)/len(losers) if losers else 0:.2f})

## ⚠️ CRITICAL BUG IMPACT

**This session ran with the 5-SECOND BAR BUG active** (before fix was applied at 12:02 PM ET).

The bug caused PULLBACK/RETEST entries to use 5-second bar data instead of 1-minute aggregated data, resulting in:
- Meaningless volume ratios (0.3x-0.6x appearing to pass 2.0x threshold)
- Tiny candle sizes (0.0%-0.3%) bypassing 0.5% minimum
- **Weak entries that should have been blocked**

**Evidence from trader_state.json (lines 184-204)**:
```
"entry_paths": {{
  "SHORT confirmed via PULLBACK/RETEST (weak initial: 0.3x vol, 0.0% candle)": 1,
  "SHORT confirmed via PULLBACK/RETEST (weak initial: 0.5x vol, 0.0% candle)": 1,
  "SHORT confirmed via PULLBACK/RETEST (weak initial: 0.6x vol, 0.0% candle)": 1,
  ...
}}
```

**Fix Applied**: 12:02 PM ET - PULLBACK/RETEST now aggregates to 1-minute candles (ps60_entry_state_machine.py lines 226-283)

## Trade Results

### Winners ({len(winners)} trades)
"""

    for t in sorted(winners, key=lambda x: x['pnl'], reverse=True):
        partials_str = f" ({len(t['partials'])} partials)" if t['partials'] else ""
        report += f"\n- **{t['symbol']}** {t['side']}: Entry ${t['entry_price']:.2f} → Exit ${t['exit_price']:.2f} = **+${t['pnl']:.2f}**{partials_str}"
        report += f"\n  - Entry Path: {t['entry_path']}"
        report += f"\n  - Exit: {t['exit_reason']}"

    report += f"\n\n### Losers ({len(losers)} trades)\n"

    for t in sorted(losers, key=lambda x: x['pnl']):
        report += f"\n- **{t['symbol']}** {t['side']}: Entry ${t['entry_price']:.2f} → Exit ${t['exit_price']:.2f} = **${t['pnl']:.2f}**"
        report += f"\n  - Entry Path: {t['entry_path']}"
        report += f"\n  - Exit: {t['exit_reason']}"

    report += f"\n\n## Entry Path Analysis\n"

    for path, data in sorted(entry_paths.items(), key=lambda x: x[1]['pnl'], reverse=True):
        report += f"\n### {path}"
        report += f"\n- Trades: {data['count']}"
        report += f"\n- P&L: ${data['pnl']:.2f}"
        report += f"\n- Avg: ${data['pnl']/data['count']:.2f}"

    report += f"\n\n## Exit Reason Analysis\n"

    for reason, data in sorted(exit_reasons.items(), key=lambda x: x[1]['count'], reverse=True):
        report += f"\n### {reason}"
        report += f"\n- Trades: {data['count']}"
        report += f"\n- P&L: ${data['pnl']:.2f}"
        report += f"\n- Avg: ${data['pnl']/data['count']:.2f}"

    report += f"\n\n## Open Positions (Still Held)\n\n"
    report += "From trader_state.json:\n\n"

    # List open positions from state file
    try:
        with open('/Users/karthik/projects/DayTrader/trader/logs/trader_state.json') as f:
            state = json.load(f)
            positions = state.get('positions', {})

            if positions:
                for symbol, pos in positions.items():
                    report += f"- **{symbol}** {pos['side']}: Entry ${pos['entry_price']:.2f}, Shares {pos['shares']}, Stop ${pos['stop_price']:.2f}\n"
            else:
                report += "No open positions\n"
    except:
        report += "Unable to read trader_state.json\n"

    report += f"\n\n## Key Findings\n\n"
    report += f"1. **Short Session**: Only ~2 hours of trading\n"
    report += f"2. **Early Exits**: Most trades exited via 15MIN_RULE (showing no progress after 7 minutes)\n"
    report += f"3. **Bug Impact**: Unknown - need to verify entries with IBKR data post-market\n"
    report += f"4. **Fix Applied**: 12:02 PM ET - too late for this session\n"

    report += f"\n\n## Next Steps\n\n"
    report += f"1. ✅ **Fix Applied**: PULLBACK/RETEST now uses 1-minute aggregation\n"
    report += f"2. ⏳ **Verify Trades**: After market close, use verify_trade_filters.py with IBKR data\n"
    report += f"3. ⏳ **Compare Sessions**: Run backtest with fix for same date, compare results\n"
    report += f"4. ⏳ **Monitor Tomorrow**: Watch for reduced weak entries with fix in place\n"

    return report

def save_csv(trades):
    """Save trades to CSV with all details"""
    with open(OUTPUT_CSV, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'symbol', 'side', 'entry_price', 'entry_time', 'exit_price',
            'exit_time', 'exit_reason', 'pnl', 'partials_count',
            'entry_path', 'result'
        ])
        writer.writeheader()

        for t in trades:
            writer.writerow({
                'symbol': t['symbol'],
                'side': t['side'],
                'entry_price': t['entry_price'],
                'entry_time': t['entry_time'],
                'exit_price': t['exit_price'],
                'exit_time': t['exit_time'],
                'exit_reason': t['exit_reason'],
                'pnl': f"{t['pnl']:.2f}",
                'partials_count': len(t['partials']),
                'entry_path': t['entry_path'],
                'result': 'WIN' if t['pnl'] > 0 else 'LOSS'
            })

def main():
    print("Analyzing October 16, 2025 trading session...")

    trades = parse_log()
    print(f"✓ Found {len(trades)} completed trades")

    report = generate_report(trades)

    with open(REPORT_FILE, 'w') as f:
        f.write(report)
    print(f"✓ Report saved: {REPORT_FILE}")

    save_csv(trades)
    print(f"✓ CSV saved: {OUTPUT_CSV}")

    with open(OUTPUT_JSON, 'w') as f:
        json.dump(trades, f, indent=2)
    print(f"✓ JSON saved: {OUTPUT_JSON}")

    print(f"\n{report}")

if __name__ == '__main__':
    main()
