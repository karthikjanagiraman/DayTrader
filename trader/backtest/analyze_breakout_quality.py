#!/usr/bin/env python3
"""
Analyze specific losing trades to determine false vs real breakouts
"""

import json
from datetime import datetime

# Key losing trades from backtest output
trades = [
    {"symbol": "COIN", "side": "LONG", "entry": 392.13, "stop": 389.14, "resistance": 390.49, "entry_bar": 421, "stop_bar": 500},
    {"symbol": "TSLA", "side": "SHORT", "entry": 427.82, "stop": 430.24, "support": 429.28, "entry_bar": 865, "stop_bar": 973},
    {"symbol": "AVGO", "side": "LONG", "entry": 347.51, "stop": 346.41, "resistance": 347.10, "entry_bar": 1154, "stop_bar": 1154},
    {"symbol": "QCOM", "side": "SHORT", "entry": 163.62, "stop": 164.23, "support": 163.88, "entry_bar": 1801, "stop_bar": 1813},
]

print("=" * 100)
print("FALSE BREAKOUT ANALYSIS - OCTOBER 9, 2025")
print("=" * 100)

for trade in trades:
    symbol = trade['symbol']
    
    # Load bar data
    try:
        with open(f'data/{symbol}_20251009_5sec.json', 'r') as f:
            bars = json.load(f)
    except:
        print(f"\n{symbol}: No bar data found")
        continue
    
    print(f"\n{'=' * 100}")
    print(f"{symbol} {trade['side']}")
    print(f"{'=' * 100}")
    print(f"Scanner Pivot: ${trade.get('resistance') or trade.get('support'):.2f}")
    print(f"Entry: ${trade['entry']:.2f} (bar {trade['entry_bar']})")
    print(f"Stop: ${trade['stop']:.2f}")
    
    # Analyze bars around entry
    entry_idx = trade['entry_bar']
    
    # Look at 20 bars before entry
    print(f"\n20 BARS BEFORE ENTRY:")
    for i in range(max(0, entry_idx - 20), entry_idx):
        bar = bars[i]
        print(f"  Bar {i}: ${bar['close']:.2f} (H: ${bar['high']:.2f}, L: ${bar['low']:.2f})")
    
    # Entry bar
    entry_bar = bars[entry_idx]
    print(f"\nENTRY BAR {entry_idx}: ${entry_bar['close']:.2f} (H: ${entry_bar['high']:.2f}, L: ${entry_bar['low']:.2f})")
    
    # Look at 20 bars after entry
    print(f"\n20 BARS AFTER ENTRY (Looking for reversal):")
    for i in range(entry_idx + 1, min(len(bars), entry_idx + 21)):
        bar = bars[i]
        marker = " ← STOP HIT" if i == trade.get('stop_bar', -1) else ""
        print(f"  Bar {i}: ${bar['close']:.2f} (H: ${bar['high']:.2f}, L: ${bar['low']:.2f}){marker}")
    
    # Determine false breakout
    if trade['side'] == 'LONG':
        # Check if price went significantly above pivot before reversing
        max_after_entry = max(bars[i]['high'] for i in range(entry_idx, min(len(bars), entry_idx + 20)))
        follow_through = max_after_entry - trade['entry']
        print(f"\nMax price after entry: ${max_after_entry:.2f} (+${follow_through:.2f})")
        if follow_through < 0.50:
            print(f"❌ FALSE BREAKOUT: Price failed to follow through (only ${follow_through:.2f})")
        else:
            print(f"✓ REAL BREAKOUT: Price followed through ${follow_through:.2f}")
    else:  # SHORT
        # Check if price went significantly below pivot before reversing
        min_after_entry = min(bars[i]['low'] for i in range(entry_idx, min(len(bars), entry_idx + 20)))
        follow_through = trade['entry'] - min_after_entry
        print(f"\nMin price after entry: ${min_after_entry:.2f} (-${follow_through:.2f})")
        if follow_through < 0.50:
            print(f"❌ FALSE BREAKOUT: Price failed to follow through (only ${follow_through:.2f})")
        else:
            print(f"✓ REAL BREAKOUT: Price followed through ${follow_through:.2f}")

