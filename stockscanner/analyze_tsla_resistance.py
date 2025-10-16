#!/usr/bin/env python3
"""
Analyze how the scanner calculated TSLA's resistance level
Traces through the exact algorithm used in scanner.py
"""

from ib_insync import *
import pandas as pd
from datetime import datetime

def analyze_tsla_resistance():
    """Fetch TSLA data and show resistance calculation step-by-step"""

    print("\n" + "="*80)
    print("TSLA RESISTANCE CALCULATION ANALYSIS (Oct 15, 2025)")
    print("="*80)

    # Connect to IBKR
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=9999)
        print("✓ Connected to IBKR\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    try:
        # Get TSLA contract
        contract = Stock('TSLA', 'SMART', 'USD')
        ib.qualifyContracts(contract)

        # Fetch 30 days of historical data (same as scanner)
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',  # Current
            durationStr='30 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False,
            formatDate=1
        )

        # Convert to DataFrame
        df = util.df(bars)

        print(f"Fetched {len(df)} days of TSLA data")
        print(f"Date range: {df.iloc[0]['date']} to {df.iloc[-1]['date']}\n")

        # Current and previous day
        today = df.iloc[-1]
        yesterday = df.iloc[-2]
        current_price = today['close']

        print("="*80)
        print("STEP 1: Current Price & Recent Data")
        print("="*80)
        print(f"Current price (today's close): ${current_price:.2f}")
        print(f"Yesterday's close: ${yesterday['close']:.2f}")
        print(f"Change: {((current_price - yesterday['close']) / yesterday['close'] * 100):+.2f}%")

        # Show last 10 days
        print("\nLast 10 days of data:")
        recent = df[['date', 'open', 'high', 'low', 'close', 'volume']].tail(10)
        for idx, row in recent.iterrows():
            print(f"  {row['date']}: High=${row['high']:.2f}, Low=${row['low']:.2f}, Close=${row['close']:.2f}")

        print("\n" + "="*80)
        print("STEP 2: Calculate Resistance Candidates (Scanner Algorithm)")
        print("="*80)

        # Near-term levels (5-day)
        resistance_5d_spike = df['high'].iloc[-5:].max()
        resistance_5d_close = df['close'].iloc[-5:].max()
        support_5d = df['low'].iloc[-5:].min()

        print(f"\n5-Day Analysis:")
        print(f"  Spike High (max of highs):    ${resistance_5d_spike:.2f}")
        print(f"  Closing High (max of closes): ${resistance_5d_close:.2f}")
        print(f"  Support (min of lows):        ${support_5d:.2f}")

        # Show which day had the spike high
        spike_day_idx = df.iloc[-5:]['high'].idxmax()
        spike_day = df.loc[spike_day_idx]
        print(f"  Spike high occurred on: {spike_day['date']}")
        print(f"    High: ${spike_day['high']:.2f}, Close: ${spike_day['close']:.2f}")
        print(f"    Wick size: ${spike_day['high'] - spike_day['close']:.2f} ({((spike_day['high'] - spike_day['close']) / spike_day['close'] * 100):.2f}%)")

        # Filter outliers using quantiles (10-day)
        resistance_10d = df['high'].iloc[-10:].quantile(0.9)
        resistance_10d_close = df['close'].iloc[-10:].quantile(0.95)
        support_10d = df['low'].iloc[-10:].quantile(0.1)

        print(f"\n10-Day Quantile Analysis (filters outliers):")
        print(f"  90th percentile of highs:  ${resistance_10d:.2f}")
        print(f"  95th percentile of closes: ${resistance_10d_close:.2f}")
        print(f"  10th percentile of lows:   ${support_10d:.2f}")

        # Moving averages
        sma_10 = df['close'].iloc[-10:].mean()
        sma_20 = df['close'].iloc[-20:].mean()

        print(f"\nMoving Averages:")
        print(f"  SMA10: ${sma_10:.2f}")
        print(f"  SMA20: ${sma_20:.2f}")

        print("\n" + "="*80)
        print("STEP 3: Smart Resistance Selection (Scanner Logic)")
        print("="*80)

        # Check if spike detected
        spike_pct = (resistance_5d_spike - resistance_5d_close) / resistance_5d_close
        print(f"\nSpike Detection:")
        print(f"  5-day spike high: ${resistance_5d_spike:.2f}")
        print(f"  5-day close high: ${resistance_5d_close:.2f}")
        print(f"  Difference: {spike_pct * 100:.2f}%")
        print(f"  Spike threshold: 1.0%")

        if spike_pct > 0.01:
            # Spike detected - use closing high or 90th percentile
            resistance = max(resistance_5d_close, resistance_10d_close)
            print(f"\n✓ SPIKE DETECTED (>{spike_pct*100:.2f}% > 1%)")
            print(f"  → Use max(5d_close_high, 10d_close_percentile)")
            print(f"  → max(${resistance_5d_close:.2f}, ${resistance_10d_close:.2f}) = ${resistance:.2f}")
        else:
            # No significant spike - use actual high
            resistance = resistance_5d_spike
            print(f"\n✗ NO SPIKE DETECTED ({spike_pct*100:.2f}% < 1%)")
            print(f"  → Use 5-day spike high: ${resistance:.2f}")

        print("\n" + "="*80)
        print("STEP 4: Smart Support Selection")
        print("="*80)

        # Support selection logic
        sma10_distance = abs(current_price - sma_10) / current_price
        support_5d_distance = abs(current_price - support_5d) / current_price

        print(f"\nSupport Candidate Evaluation:")
        print(f"  SMA10: ${sma_10:.2f} (distance: {sma10_distance*100:.2f}%)")
        print(f"  5-day low: ${support_5d:.2f} (distance: {support_5d_distance*100:.2f}%)")
        print(f"  10-day 10th percentile: ${support_10d:.2f}")

        if current_price > sma_10 and sma10_distance < 0.1:
            support = sma_10
            print(f"\n✓ Using SMA10 as support (price above SMA, within 10%)")
            print(f"  → Support = ${support:.2f}")
        elif support_5d_distance < 0.1:
            support = support_5d
            print(f"\n✓ Using 5-day low as support (within 10% of price)")
            print(f"  → Support = ${support:.2f}")
        else:
            support = support_10d
            print(f"\n✓ Using 10-day 10th percentile as support (fallback)")
            print(f"  → Support = ${support:.2f}")

        print("\n" + "="*80)
        print("STEP 5: Breakout Reasoning (Why This Level?)")
        print("="*80)

        # Count resistance touches
        touches = 0
        touch_dates = []
        for i in range(-20, 0):
            bar = df.iloc[i]
            if abs(bar['high'] - resistance) / resistance < 0.015:  # Within 1.5%
                touches += 1
                touch_dates.append(f"{bar['date']} (${bar['high']:.2f})")

        print(f"\nResistance Touch Count:")
        print(f"  Level: ${resistance:.2f}")
        print(f"  Tolerance: ±1.5%")
        print(f"  Range: ${resistance * 0.985:.2f} - ${resistance * 1.015:.2f}")
        print(f"  Touches found: {touches}")
        if touch_dates:
            print(f"  Dates:")
            for date in touch_dates[-5:]:  # Last 5 touches
                print(f"    {date}")

        # Historical significance
        high_20d = df['high'].iloc[-20:].max()
        high_10d = df['high'].iloc[-10:].max()
        high_5d = df['high'].iloc[-5:].max()
        close_5d = df['close'].iloc[-5:].max()

        print(f"\nHistorical Significance:")
        print(f"  20-day high: ${high_20d:.2f} {'✓ MATCH' if abs(resistance - high_20d) < 1 else ''}")
        print(f"  10-day high: ${high_10d:.2f} {'✓ MATCH' if abs(resistance - high_10d) < 1 else ''}")
        print(f"  5-day high:  ${high_5d:.2f} {'✓ MATCH' if abs(resistance - high_5d) < 1 else ''}")
        print(f"  5-day close: ${close_5d:.2f} {'✓ MATCH' if abs(resistance - close_5d) < 1 else ''}")

        print("\n" + "="*80)
        print("STEP 6: Final Results")
        print("="*80)

        dist_to_resistance = ((resistance - current_price) / current_price) * 100
        dist_to_support = ((current_price - support) / current_price) * 100

        print(f"\n📊 FINAL LEVELS:")
        print(f"  Current Price: ${current_price:.2f}")
        print(f"  Resistance:    ${resistance:.2f} (+{dist_to_resistance:.2f}%)")
        print(f"  Support:       ${support:.2f} (-{dist_to_support:.2f}%)")
        print(f"  Range:         ${resistance - support:.2f}")

        # Compare with scanner output
        print(f"\n📋 SCANNER OUTPUT COMPARISON:")
        print(f"  Scanner resistance: $447.37")
        print(f"  Our calculation:    ${resistance:.2f}")
        print(f"  Match: {'✓ YES' if abs(resistance - 447.37) < 0.5 else '✗ NO (difference: $' + f'{abs(resistance - 447.37):.2f})'}")

        print(f"\n  Scanner support: $400.56")
        print(f"  Our calculation: ${support:.2f}")
        print(f"  Match: {'✓ YES' if abs(support - 400.56) < 0.5 else '✗ NO (difference: $' + f'{abs(support - 400.56):.2f})'}")

        print(f"\n  Breakout reason: 'Tested 10x'")
        print(f"  Our touch count: {touches}")
        print(f"  Match: {'✓ YES' if touches == 10 else '✗ NO'}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        ib.disconnect()
        print("\n✓ Disconnected from IBKR")

if __name__ == "__main__":
    analyze_tsla_resistance()
