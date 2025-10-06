#!/usr/bin/env python3
"""Quick check: Did ANY stocks have successful breakouts on Sept 30?"""

import json
from pathlib import Path
from ib_insync import IB, Stock
import time

# Load scanner
scanner_file = Path(__file__).parent / "monthly_results_production" / "scanner_20250930.json"
with open(scanner_file) as f:
    scanner = json.load(f)

# Get top 5 stocks by score
top_stocks = sorted([s for s in scanner if s.get('score', 0) >= 50],
                    key=lambda x: x.get('score', 0), reverse=True)[:5]

print("Top 5 stocks from Sept 30 scanner:\n")
for s in top_stocks:
    print(f"{s['symbol']}: Score {s['score']}, R/R {s.get('risk_reward', 0):.2f}, "
          f"Resistance ${s['resistance']:.2f}")

# Connect to IBKR
print("\nConnecting to IBKR...")
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=5001)
print("✓ Connected\n")

print("="*80)
print("Checking if these stocks broke resistance and reached targets...")
print("="*80)

for stock in top_stocks:
    symbol = stock['symbol']
    resistance = stock['resistance']
    target = stock.get('target1', resistance * 1.02)

    print(f"\n{symbol}:")
    print(f"  Resistance: ${resistance:.2f}, Target: ${target:.2f}")

    contract = Stock(symbol, 'SMART', 'USD')

    try:
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='20250930 16:00:00',
            durationStr='1 D',
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        # Find breakout
        broke_resistance = False
        reached_target = False
        breakout_bar = None

        for bar in bars:
            if bar.close > resistance and not broke_resistance:
                broke_resistance = True
                breakout_bar = bar
                print(f"  ✓ Broke resistance @ {bar.date.strftime('%H:%M')}: ${bar.close:.2f}")

                # Check volume
                pre_bars = [b for b in bars if b.date < bar.date]
                if len(pre_bars) >= 20:
                    avg_vol = sum(b.volume for b in pre_bars[-20:]) / 20
                    vol_ratio = bar.volume / avg_vol
                    print(f"    Volume: {vol_ratio:.2f}x average ({'✓ PASS' if vol_ratio >= 1.3 else '✗ FAIL 1.3x'})")

                    # Check candle size
                    candle_pct = abs(bar.close - bar.open) / bar.open * 100
                    print(f"    Candle: {candle_pct:.2f}% ({'✓ PASS' if candle_pct >= 0.8 else '✗ FAIL 0.8%'})")

            # Check if reached target after breakout
            if broke_resistance and bar.high >= target and not reached_target:
                reached_target = True
                gain = ((target - breakout_bar.close) / breakout_bar.close * 100)
                print(f"  ✓ Reached target @ {bar.date.strftime('%H:%M')}: ${bar.high:.2f} (Gain: {gain:.2f}%)")

        if not broke_resistance:
            print(f"  ✗ Never broke resistance")
        elif not reached_target:
            max_price = max(b.high for b in bars if b.date >= breakout_bar.date)
            print(f"  ✗ Broke resistance but didn't reach target (max ${max_price:.2f})")

        time.sleep(0.6)  # Rate limit

    except Exception as e:
        print(f"  ✗ Error: {e}")

ib.disconnect()

print("\n" + "="*80)
print("Analysis complete")
print("="*80)
