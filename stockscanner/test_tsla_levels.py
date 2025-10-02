#!/usr/bin/env python3
"""
Test TSLA support/resistance levels
"""

from ib_insync import *
from datetime import datetime
import pandas as pd

def analyze_tsla():
    """Analyze TSLA levels to understand the issue"""

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=3333)
    print("Connected to IBKR\n")

    try:
        # Get TSLA data
        contract = Stock('TSLA', 'SMART', 'USD')
        ib.qualifyContracts(contract)

        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='30 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False
        )

        if bars:
            df = util.df(bars)
            print(f"Got {len(df)} days of data for TSLA\n")

            # Current approach (WRONG)
            support_20d_min = df['low'].iloc[-20:].min()
            resistance_20d_max = df['high'].iloc[-20:].max()

            # Better approaches
            support_5d = df['low'].iloc[-5:].min()      # Recent 5-day low
            resistance_5d = df['high'].iloc[-5:].max()   # Recent 5-day high

            # Moving average support
            sma_20 = df['close'].iloc[-20:].mean()
            sma_10 = df['close'].iloc[-10:].mean()
            sma_5 = df['close'].iloc[-5:].mean()

            # Recent consolidation
            recent_lows = df['low'].iloc[-10:]
            support_10d_mean = recent_lows.mean()  # Average of recent lows
            support_10d_median = recent_lows.median()  # Median of recent lows

            latest = df.iloc[-1]

            print("="*60)
            print("TSLA PRICE LEVELS ANALYSIS")
            print("="*60)
            print(f"Current Price: ${latest['close']:.2f}\n")

            print("CURRENT LOGIC (PROBLEMATIC):")
            print(f"  Support (20d min):  ${support_20d_min:.2f} ({((support_20d_min - latest['close'])/latest['close']*100):+.1f}% from current)")
            print(f"  Resistance (20d max): ${resistance_20d_max:.2f} ({((resistance_20d_max - latest['close'])/latest['close']*100):+.1f}% from current)\n")

            print("BETTER APPROACHES:")
            print(f"  Support (5d low):    ${support_5d:.2f} ({((support_5d - latest['close'])/latest['close']*100):+.1f}% from current)")
            print(f"  Resistance (5d high): ${resistance_5d:.2f} ({((resistance_5d - latest['close'])/latest['close']*100):+.1f}% from current)\n")

            print("MOVING AVERAGE SUPPORT:")
            print(f"  SMA 5:  ${sma_5:.2f} ({((sma_5 - latest['close'])/latest['close']*100):+.1f}% from current)")
            print(f"  SMA 10: ${sma_10:.2f} ({((sma_10 - latest['close'])/latest['close']*100):+.1f}% from current)")
            print(f"  SMA 20: ${sma_20:.2f} ({((sma_20 - latest['close'])/latest['close']*100):+.1f}% from current)\n")

            print("CONSOLIDATION SUPPORT:")
            print(f"  10d Low Mean:   ${support_10d_mean:.2f} ({((support_10d_mean - latest['close'])/latest['close']*100):+.1f}% from current)")
            print(f"  10d Low Median: ${support_10d_median:.2f} ({((support_10d_median - latest['close'])/latest['close']*100):+.1f}% from current)\n")

            # Show the actual daily data
            print("="*60)
            print("LAST 20 DAYS OF TSLA DATA:")
            print("="*60)
            display_df = df[['date', 'open', 'high', 'low', 'close', 'volume']].iloc[-20:]
            display_df['volume_M'] = (display_df['volume'] / 1e6).round(1)
            display_df = display_df.drop('volume', axis=1)
            print(display_df.to_string())

            # Find the outlier day
            min_day = df.iloc[-20:].loc[df['low'].iloc[-20:].idxmin()]
            print(f"\n⚠️  OUTLIER: Lowest day in 20d was {min_day['date']}")
            print(f"    Low: ${min_day['low']:.2f}, High: ${min_day['high']:.2f}, Close: ${min_day['close']:.2f}")

    finally:
        ib.disconnect()
        print("\nDisconnected")

if __name__ == "__main__":
    analyze_tsla()