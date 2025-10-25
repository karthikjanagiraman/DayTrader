#!/usr/bin/env python3
"""
Quick script to fetch and cache 1-minute bars for October 22, 2025
This solves the missing data issue for the backtest.
"""
from ib_insync import IB, Stock, util
from datetime import datetime
from pathlib import Path
import json

# Connect to IBKR
ib = IB()
ib.connect('127.0.0.1', 7497, clientId=4000)
print("✓ Connected to IBKR")

# Symbols and date
symbols = ['SMCI', 'SOFI', 'AMD', 'NVDA', 'PLTR', 'TSLA', 'HOOD', 'PATH']
date_str = '20251022'
date_obj = datetime.strptime(date_str, '%Y%m%d')

# Cache directory
cache_dir = Path('data')
cache_dir.mkdir(exist_ok=True)

print(f"\nFetching 1-minute bars for {len(symbols)} symbols on {date_obj.strftime('%Y-%m-%d')}...\n")

for i, symbol in enumerate(symbols, 1):
    print(f"[{i}/{len(symbols)}] {symbol}...")
    
    # Create contract
    contract = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(contract)
    
    # Fetch 1-minute bars
    bars = ib.reqHistoricalData(
        contract,
        endDateTime=f'{date_str} 16:00:00',
        durationStr='1 D',
        barSizeSetting='1 min',
        whatToShow='TRADES',
        useRTH=True,  # Regular trading hours only
        formatDate=1
    )
    
    if bars:
        # Convert to JSON
        bars_data = []
        for bar in bars:
            bars_data.append({
                'date': bar.date.isoformat(),
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'average': bar.average,
                'barCount': bar.barCount
            })
        
        # Save to cache file
        cache_file = cache_dir / f'{symbol}_{date_str}_1min.json'
        with open(cache_file, 'w') as f:
            json.dump(bars_data, f, indent=2)
        
        print(f"  ✓ Saved {len(bars)} bars to {cache_file.name}")
    else:
        print(f"  ⚠️  No bars returned")
    
    # Small delay to avoid rate limits
    ib.sleep(0.5)

print("\n✅ All done!")
ib.disconnect()
