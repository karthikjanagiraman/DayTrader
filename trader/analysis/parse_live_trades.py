#!/usr/bin/env python3
"""
Parse Live Trading Session Logs
================================

Extracts trade data from live trading session logs and formats for validation.

Usage:
    python3 parse_live_trades.py logs/live_session_20251031.log

Output:
    - analysis/live_trades_20251031.json (structured trade data)
    - Prints summary to console
"""

import re
import json
import sys
from datetime import datetime
from pathlib import Path


def parse_trade_entry(lines, idx):
    """Parse trade entry from log lines"""
    trade = {}

    # Extract symbol and side from entry line
    # Example: "🔴 SHORT SOFI @ $28.98 (10:27:21 AM ET)"
    entry_match = re.search(r'🔴 SHORT|🟢 LONG', lines[idx])
    if not entry_match:
        return None, idx

    entry_line = lines[idx]

    # Extract side
    if '🔴 SHORT' in entry_line:
        trade['side'] = 'SHORT'
    elif '🟢 LONG' in entry_line:
        trade['side'] = 'LONG'

    # Extract symbol and price
    symbol_match = re.search(r'(SHORT|LONG)\s+(\w+)\s+@\s+\$([0-9.]+)', entry_line)
    if symbol_match:
        trade['symbol'] = symbol_match.group(2)
        trade['entry_price'] = float(symbol_match.group(3))

    # Extract entry time
    time_match = re.search(r'\((\d{2}:\d{2}:\d{2})\s+(AM|PM)\s+ET\)', entry_line)
    if time_match:
        trade['entry_time'] = f"{time_match.group(1)} {time_match.group(2)} ET"

    # Look for entry details in next few lines
    for i in range(idx + 1, min(idx + 10, len(lines))):
        line = lines[i]

        # Entry Path
        if 'Entry Path:' in line:
            path_match = re.search(r'Entry Path:\s+(.+?)(?:\n|$)', line)
            if path_match:
                trade['entry_path'] = path_match.group(1).strip()

        # Shares
        if 'Shares:' in line:
            shares_match = re.search(r'Shares:\s+(\d+)', line)
            if shares_match:
                trade['shares'] = int(shares_match.group(1))

            # Room to target
            room_match = re.search(r'Room:\s+([0-9.]+)%', line)
            if room_match:
                trade['room_to_target_pct'] = float(room_match.group(1))

        # Stop and Target
        if 'Stop:' in line:
            stop_match = re.search(r'Stop:\s+\$([0-9.]+)', line)
            if stop_match:
                trade['stop_price'] = float(stop_match.group(1))

            target_match = re.search(r'Target1:\s+\$([0-9.]+)', line)
            if target_match:
                trade['target1'] = float(target_match.group(1))

        # Stop parsing after we hit next entry or exit
        if '🔴 SHORT' in line or '🟢 LONG' in line or '🛑 CLOSE' in line:
            if i > idx + 1:
                break

    return trade, idx + 1


def parse_trade_exit(lines, idx, open_trades):
    """Parse trade exit and match to open trade"""
    # Example: "🛑 CLOSE SOFI @ $29.06 (15MIN_RULE)"
    exit_line = lines[idx]

    # Extract symbol and exit price
    exit_match = re.search(r'CLOSE\s+(\w+)\s+@\s+\$([0-9.]+)\s+\((.+?)\)', exit_line)
    if not exit_match:
        return None, idx

    symbol = exit_match.group(1)
    exit_price = float(exit_match.group(2))
    exit_reason = exit_match.group(3)

    # Extract time from log timestamp
    time_match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', exit_line)
    if time_match:
        exit_time = f"{time_match.group(2)}"
    else:
        exit_time = "unknown"

    # Find matching open trade
    matched_trade = None
    for i, trade in enumerate(open_trades):
        if trade['symbol'] == symbol:
            matched_trade = open_trades.pop(i)
            break

    if not matched_trade:
        # No matching entry found - orphaned exit
        return None, idx + 1

    # Complete the trade
    matched_trade['exit_price'] = exit_price
    matched_trade['exit_reason'] = exit_reason
    matched_trade['exit_time'] = exit_time

    # Calculate P&L
    shares = matched_trade.get('shares', 0)
    entry = matched_trade.get('entry_price', 0)

    if matched_trade['side'] == 'LONG':
        pnl = (exit_price - entry) * shares
    else:  # SHORT
        pnl = (entry - exit_price) * shares

    matched_trade['pnl'] = round(pnl, 2)
    matched_trade['pnl_pct'] = round((pnl / (entry * shares)) * 100, 2) if entry > 0 else 0

    return matched_trade, idx + 1


def parse_log_file(log_file):
    """Parse entire log file and extract all trades"""
    with open(log_file, 'r') as f:
        lines = f.readlines()

    completed_trades = []
    open_trades = []

    idx = 0
    while idx < len(lines):
        line = lines[idx]

        # Check for trade entry
        if '🔴 SHORT' in line or '🟢 LONG' in line:
            trade, idx = parse_trade_entry(lines, idx)
            if trade and 'symbol' in trade:
                open_trades.append(trade)

        # Check for trade exit
        elif '🛑 CLOSE' in line:
            completed_trade, idx = parse_trade_exit(lines, idx, open_trades)
            if completed_trade:
                completed_trades.append(completed_trade)

        else:
            idx += 1

    return completed_trades, open_trades


def analyze_trades(trades):
    """Analyze trade performance"""
    if not trades:
        return None

    winners = [t for t in trades if t.get('pnl', 0) > 0]
    losers = [t for t in trades if t.get('pnl', 0) < 0]
    breakeven = [t for t in trades if t.get('pnl', 0) == 0]

    total_pnl = sum(t.get('pnl', 0) for t in trades)

    analysis = {
        'total_trades': len(trades),
        'winners': len(winners),
        'losers': len(losers),
        'breakeven': len(breakeven),
        'win_rate_pct': round(len(winners) / len(trades) * 100, 1) if trades else 0,
        'total_pnl': round(total_pnl, 2),
        'avg_winner': round(sum(t['pnl'] for t in winners) / len(winners), 2) if winners else 0,
        'avg_loser': round(sum(t['pnl'] for t in losers) / len(losers), 2) if losers else 0,
        'avg_trade': round(total_pnl / len(trades), 2) if trades else 0,
    }

    # Analyze by symbol
    symbols = {}
    for trade in trades:
        symbol = trade.get('symbol', 'UNKNOWN')
        if symbol not in symbols:
            symbols[symbol] = {'trades': 0, 'winners': 0, 'pnl': 0}

        symbols[symbol]['trades'] += 1
        if trade.get('pnl', 0) > 0:
            symbols[symbol]['winners'] += 1
        symbols[symbol]['pnl'] += trade.get('pnl', 0)

    analysis['by_symbol'] = symbols

    # Analyze by exit reason
    exit_reasons = {}
    for trade in trades:
        reason = trade.get('exit_reason', 'UNKNOWN')
        if reason not in exit_reasons:
            exit_reasons[reason] = {'count': 0, 'winners': 0, 'pnl': 0}

        exit_reasons[reason]['count'] += 1
        if trade.get('pnl', 0) > 0:
            exit_reasons[reason]['winners'] += 1
        exit_reasons[reason]['pnl'] += trade.get('pnl', 0)

    analysis['by_exit_reason'] = exit_reasons

    return analysis


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_live_trades.py <log_file>")
        print("Example: python3 parse_live_trades.py logs/live_session_20251031.log")
        sys.exit(1)

    log_file = Path(sys.argv[1])

    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        sys.exit(1)

    print(f"📖 Parsing log file: {log_file}")
    print()

    # Parse trades
    completed_trades, open_trades = parse_log_file(log_file)

    print(f"✅ Found {len(completed_trades)} completed trades")
    if open_trades:
        print(f"⚠️  Found {len(open_trades)} open trades (still in position)")
    print()

    # Analyze
    analysis = analyze_trades(completed_trades)

    if analysis:
        print("=" * 80)
        print("TRADE ANALYSIS")
        print("=" * 80)
        print(f"Total Trades: {analysis['total_trades']}")
        print(f"Winners: {analysis['winners']} ({analysis['win_rate_pct']}%)")
        print(f"Losers: {analysis['losers']}")
        print(f"Breakeven: {analysis['breakeven']}")
        print(f"Total P&L: ${analysis['total_pnl']}")
        print(f"Avg Winner: ${analysis['avg_winner']}")
        print(f"Avg Loser: ${analysis['avg_loser']}")
        print(f"Avg Trade: ${analysis['avg_trade']}")
        print()

        print("BY SYMBOL:")
        print("-" * 80)
        for symbol, data in sorted(analysis['by_symbol'].items(), key=lambda x: x[1]['pnl'], reverse=True):
            win_rate = (data['winners'] / data['trades'] * 100) if data['trades'] > 0 else 0
            print(f"  {symbol:6s} | {data['trades']:2d} trades | {data['winners']:2d} wins ({win_rate:5.1f}%) | ${data['pnl']:8.2f}")
        print()

        print("BY EXIT REASON:")
        print("-" * 80)
        for reason, data in sorted(analysis['by_exit_reason'].items(), key=lambda x: x[1]['count'], reverse=True):
            win_rate = (data['winners'] / data['count'] * 100) if data['count'] > 0 else 0
            print(f"  {reason:15s} | {data['count']:2d} trades | {data['winners']:2d} wins ({win_rate:5.1f}%) | ${data['pnl']:8.2f}")
        print()

    # Save to JSON
    date_match = re.search(r'(\d{8})', str(log_file))
    if date_match:
        date_str = date_match.group(1)
    else:
        date_str = datetime.now().strftime('%Y%m%d')

    output_dir = Path('analysis')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f'live_trades_{date_str}.json'

    output_data = {
        'date': date_str,
        'log_file': str(log_file),
        'parsed_at': datetime.now().isoformat(),
        'completed_trades': completed_trades,
        'open_trades': open_trades,
        'analysis': analysis
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"💾 Saved to: {output_file}")
    print()

    # Print sample trades
    if completed_trades:
        print("SAMPLE TRADES (first 5):")
        print("-" * 80)
        for i, trade in enumerate(completed_trades[:5], 1):
            print(f"{i}. {trade.get('symbol', 'N/A')} {trade.get('side', 'N/A')}")
            print(f"   Entry: ${trade.get('entry_price', 0):.2f} → Exit: ${trade.get('exit_price', 0):.2f}")
            print(f"   P&L: ${trade.get('pnl', 0):.2f} ({trade.get('exit_reason', 'N/A')})")
            print()


if __name__ == '__main__':
    main()
