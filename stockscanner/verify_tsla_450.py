#!/usr/bin/env python3
"""
Verify if TSLA touched $450 in the last 20-30 days
"""

from ib_insync import *
from datetime import datetime, timedelta
import pandas as pd

def check_tsla_450():
    """Check TSLA's highs for the last 30 days"""
    print("\n" + "="*70)
    print("TSLA HISTORICAL DATA CHECK - LOOKING FOR $450+ TOUCHES")
    print("="*70)

    ib = IB()

    try:
        # Connect to IBKR with retry
        for attempt in range(3):
            try:
                ib.connect('127.0.0.1', 7497, clientId=7777+attempt)
                print(f"Connected at {datetime.now().strftime('%H:%M:%S')}\n")
                break
            except:
                if attempt == 2:
                    raise
                print(f"Connection attempt {attempt+1} failed, retrying...")
                ib = IB()  # Reset connection

        # Create TSLA contract
        contract = Stock('TSLA', 'SMART', 'USD')
        ib.qualifyContracts(contract)

        # Get 30 days of data
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='30 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False,
            formatDate=1
        )

        if bars:
            df = util.df(bars)

            # Sort by date
            df = df.sort_values('date')

            print(f"Got {len(df)} days of TSLA data\n")
            print("-"*70)
            print("LAST 20 TRADING DAYS:")
            print("-"*70)

            # Display last 20 days
            last_20 = df.iloc[-20:]

            # Format for display
            display_df = last_20[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            display_df['volume_M'] = (display_df['volume'] / 1e6).round(1)
            display_df = display_df.drop('volume', axis=1)

            # Mark days that touched $450 or higher
            display_df['Hit_450'] = display_df['high'] >= 450

            print(display_df.to_string(index=False))

            # Analysis
            print("\n" + "="*70)
            print("ANALYSIS:")
            print("="*70)

            # Find 5-day high
            last_5_high = df['high'].iloc[-5:].max()
            print(f"\n📊 5-day High: ${last_5_high:.2f}")

            # Find 10-day high
            last_10_high = df['high'].iloc[-10:].max()
            print(f"📊 10-day High: ${last_10_high:.2f}")

            # Find 20-day high
            last_20_high = df['high'].iloc[-20:].max()
            print(f"📊 20-day High: ${last_20_high:.2f}")

            # Count touches at $450
            touches_450 = 0
            touches_445_455 = 0  # Within range of 450

            for idx, row in last_20.iterrows():
                if row['high'] >= 450:
                    touches_450 += 1
                if 445 <= row['high'] <= 455:  # Within ~1% of 450
                    touches_445_455 += 1

            print(f"\n🎯 Days that reached exactly $450 or higher: {touches_450}")
            print(f"🎯 Days with high between $445-455 (±1% of $450): {touches_445_455}")

            # Find actual resistance level
            # Check what scanner would calculate
            resistance_5d = df['high'].iloc[-5:].max()
            resistance_10d_90pct = df['high'].iloc[-10:].quantile(0.9)
            resistance_20d_max = df['high'].iloc[-20:].max()

            print(f"\n📈 RESISTANCE CALCULATIONS:")
            print(f"  5-day max (used by scanner): ${resistance_5d:.2f}")
            print(f"  10-day 90th percentile: ${resistance_10d_90pct:.2f}")
            print(f"  20-day max: ${resistance_20d_max:.2f}")

            # Check how many times each level was tested
            def count_tests(level, tolerance=0.015):
                count = 0
                for idx, row in last_20.iterrows():
                    if abs(row['high'] - level) / level <= tolerance:
                        count += 1
                return count

            tests_at_resistance = count_tests(resistance_5d)
            print(f"\n✅ Times tested at ${resistance_5d:.2f} (±1.5%): {tests_at_resistance}")

            # Current price
            current = df.iloc[-1]['close']
            print(f"\n💰 Current Price: ${current:.2f}")
            print(f"📏 Distance to resistance: {((resistance_5d - current) / current * 100):.2f}%")

            # Find exact days that hit the resistance
            print(f"\n📅 DAYS THAT TESTED ${resistance_5d:.2f} (±1.5%):")
            for idx, row in last_20.iterrows():
                if abs(row['high'] - resistance_5d) / resistance_5d <= 0.015:
                    print(f"  {row['date']}: High ${row['high']:.2f}")

        else:
            print("No data received")

    except Exception as e:
        print(f"Error: {e}")

    finally:
        if ib.isConnected():
            ib.disconnect()
            print("\n✓ Disconnected")

if __name__ == "__main__":
    check_tsla_450()