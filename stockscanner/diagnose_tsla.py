#!/usr/bin/env python3
"""
Diagnostic script to analyze why both V1 and V2 scanners miss TSLA's $440 resistance
"""

from ib_insync import IB, Stock, util
import pandas as pd
from datetime import datetime

def analyze_v1_logic():
    """Analyze what V1 scanner sees (daily bars only)"""
    print("="*80)
    print("V1 SCANNER LOGIC ANALYSIS (Daily Bars)")
    print("="*80)

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=9001)

    contract = Stock('TSLA', 'SMART', 'USD')
    ib.qualifyContracts(contract)

    # Fetch 30 days of daily bars (what V1 uses)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime='20251016 23:59:59',
        durationStr='30 D',
        barSizeSetting='1 day',
        whatToShow='TRADES',
        useRTH=False,
        formatDate=1
    )

    df = util.df(bars)
    df['date'] = pd.to_datetime(df['date']).dt.date

    # Show last 10 days
    print("\nLast 10 Daily Bars:")
    print("-"*80)
    for idx in range(-10, 0):
        bar = df.iloc[idx]
        print(f"{bar['date']}: High ${bar['high']:.2f} | Close ${bar['close']:.2f} | Low ${bar['low']:.2f}")

    # V1 resistance calculation (lines 211-232 in scanner.py)
    print("\n" + "="*80)
    print("V1 RESISTANCE CALCULATION")
    print("="*80)

    resistance_5d_spike = df['high'].iloc[-5:].max()
    resistance_5d_close = df['close'].iloc[-5:].max()
    resistance_10d = df['high'].iloc[-10:].quantile(0.9)
    resistance_10d_close = df['close'].iloc[-10:].quantile(0.95)

    print(f"\n5-Day Spike High: ${resistance_5d_spike:.2f}")
    print(f"5-Day Closing High: ${resistance_5d_close:.2f}")
    print(f"10-Day 90th percentile (high): ${resistance_10d:.2f}")
    print(f"10-Day 95th percentile (close): ${resistance_10d_close:.2f}")

    # Check spike detection logic
    spike_detected = (resistance_5d_spike - resistance_5d_close) / resistance_5d_close > 0.01

    print(f"\nSpike Detection:")
    print(f"  Spike high - Closing high: ${resistance_5d_spike - resistance_5d_close:.2f}")
    print(f"  Percentage difference: {((resistance_5d_spike - resistance_5d_close) / resistance_5d_close * 100):.2f}%")
    print(f"  Spike detected (>1%): {'YES' if spike_detected else 'NO'}")

    if spike_detected:
        resistance = max(resistance_5d_close, resistance_10d_close)
        print(f"\n✅ SPIKE PATH: Using max(5d_close, 10d_close) = ${resistance:.2f}")
    else:
        resistance = resistance_5d_spike
        print(f"\n✅ NO SPIKE PATH: Using 5d_spike = ${resistance:.2f}")

    current_price = df.iloc[-1]['close']
    print(f"\nCurrent Price: ${current_price:.2f}")
    print(f"Distance to Resistance: {((resistance - current_price) / current_price * 100):+.2f}%")

    # Show which days contributed to the highs
    print("\n" + "="*80)
    print("DAILY HIGHS ANALYSIS (Last 10 Days)")
    print("="*80)

    last_10 = df.iloc[-10:]
    highs_above_435 = last_10[last_10['high'] >= 435.0].copy()

    for idx, bar in highs_above_435.iterrows():
        wick_size = bar['high'] - bar['close']
        wick_pct = (wick_size / bar['close']) * 100

        print(f"\n{bar['date']}")
        print(f"  High: ${bar['high']:.2f}")
        print(f"  Close: ${bar['close']:.2f}")
        print(f"  Wick: ${wick_size:.2f} ({wick_pct:.2f}%)")

        if bar['high'] >= 439.0:
            print(f"  🔥 IN $440 ZONE!")

    ib.disconnect()
    print()


def analyze_v2_logic():
    """Analyze what V2 scanner sees (5-day hourly bars)"""
    print("="*80)
    print("V2 SCANNER LOGIC ANALYSIS (5-Day Hourly Bars)")
    print("="*80)

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=9002)

    contract = Stock('TSLA', 'SMART', 'USD')
    ib.qualifyContracts(contract)

    # Fetch 5 days of hourly bars (what V2 uses)
    hourly_bars = ib.reqHistoricalData(
        contract,
        endDateTime='20251016 16:00:00 US/Eastern',
        durationStr='5 D',
        barSizeSetting='1 hour',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1
    )

    df_hourly = util.df(hourly_bars)
    df_hourly['date'] = pd.to_datetime(df_hourly['date'])

    print(f"\nTotal Hourly Bars: {len(df_hourly)}")
    print(f"Date Range: {df_hourly['date'].min()} to {df_hourly['date'].max()}")

    # Group by date and show daily highs from hourly data
    df_hourly['trading_date'] = df_hourly['date'].dt.date
    daily_highs = df_hourly.groupby('trading_date')['high'].max()

    print("\nDaily Highs (from hourly bars):")
    print("-"*40)
    for date, high in daily_highs.items():
        print(f"{date}: ${high:.2f}")

    # V2 Criterion 1: Multiple Rejections (lines 136-162 in scanner_v2.py)
    print("\n" + "="*80)
    print("V2 CRITERION 1: MULTIPLE REJECTIONS")
    print("="*80)

    rejections = []
    for idx, bar in df_hourly.iterrows():
        wick_size = bar['high'] - bar['close']
        wick_pct = (wick_size / bar['close']) * 100

        # Rejection signature: close 0.5%+ below high
        if wick_pct >= 0.5:
            rejections.append(bar['high'])

    print(f"\nRejections found: {len(rejections)}")

    if len(rejections) >= 2:
        median_high = sorted(rejections)[len(rejections) // 2]
        cluster = [r for r in rejections if abs(r - median_high) <= 2.0]

        print(f"Median rejection: ${median_high:.2f}")
        print(f"Cluster (±$2): {len(cluster)} rejections")
        print(f"Cluster levels: {[f'${r:.2f}' for r in cluster]}")

        if len(cluster) >= 2:
            print(f"\n✅ CRITERION 1 ACTIVATED: ${median_high:.2f}")
        else:
            print(f"\n❌ CRITERION 1 NOT MET: Cluster too small")
    else:
        print("❌ CRITERION 1 NOT MET: Less than 2 rejections")

    # Analyze $440 zone specifically
    print("\n" + "="*80)
    print("$440 ZONE ANALYSIS (Hourly Bars)")
    print("="*80)

    zone_bars = df_hourly[(df_hourly['high'] >= 438.0) & (df_hourly['high'] <= 442.0)]

    print(f"\nBars that tested $440 zone ($438-$442): {len(zone_bars)}")

    if len(zone_bars) > 0:
        print("\nDetailed Analysis:")
        print("-"*80)

        rejections_440 = 0
        for idx, bar in zone_bars.iterrows():
            wick_size = bar['high'] - bar['close']
            wick_pct = (wick_size / bar['close']) * 100
            rejection_sig = "✅ REJECTION" if wick_pct >= 0.5 else "❌ no rejection"

            if wick_pct >= 0.5:
                rejections_440 += 1

            print(f"{bar['date']}")
            print(f"  High: ${bar['high']:.2f} | Close: ${bar['close']:.2f}")
            print(f"  Wick: ${wick_size:.2f} ({wick_pct:.2f}%) {rejection_sig}")
            print()

        print(f"Total rejections in $440 zone: {rejections_440}")

        if rejections_440 >= 2:
            print("✅ $440 zone HAD 2+ rejections - SHOULD be detected")
        else:
            print("❌ $440 zone had <2 rejections - Algorithm correctly skipped")

    ib.disconnect()
    print()


def conclusion():
    """Print diagnostic conclusion"""
    print("="*80)
    print("DIAGNOSTIC CONCLUSION")
    print("="*80)

    print("\n🔍 V1 SCANNER (Daily Bars):")
    print("   - Uses 5-day spike high or closing high")
    print("   - Misses $440 if:")
    print("     1. $440 highs occurred on older days (not in last 5)")
    print("     2. Closing high is significantly lower (spike detection)")
    print("     3. 90th percentile filters out $440 as outlier")

    print("\n🔍 V2 SCANNER (5-Day Hourly Bars):")
    print("   - Uses rejection clustering (0.5%+ wicks)")
    print("   - Misses $440 if:")
    print("     1. Less than 2 hourly bars had rejection wicks at $440")
    print("     2. Hourly closes were too close to highs (no wick)")
    print("     3. Rejection cluster centered lower (e.g., $434)")

    print("\n💡 THE GAP:")
    print("   Both scanners require REJECTION SIGNATURES (wicks/selling pressure)")
    print("   They miss resistance zones where price STALLS without rejection:")
    print("     - Multiple days hit same high level")
    print("     - But closed near highs (no wicks)")
    print("     - Supply zone exists but no dramatic rejections")

    print("\n🔧 SOLUTION:")
    print("   Add 'Multiple Highs at Same Level' criterion:")
    print("     - Count days that hit similar high level (±1%)")
    print("     - No rejection wick required")
    print("     - If 3+ days hit same zone, it's resistance")
    print("     - This catches 'soft' resistance where price can't break higher")


if __name__ == "__main__":
    try:
        analyze_v1_logic()
        analyze_v2_logic()
        conclusion()
    except KeyboardInterrupt:
        print("\n\nDiagnostic interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
