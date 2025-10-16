#!/usr/bin/env python3
"""
Tier 0 Hourly Analysis for TSLA
Checks if hourly data shows strong enough signal to override daily resistance
"""

from ib_insync import *
import pandas as pd
from datetime import datetime, date
import pytz

def analyze_tsla_hourly():
    """Analyze TSLA using Tier 0 hourly criteria"""

    print("\n" + "="*80)
    print("TSLA TIER 0 HOURLY ANALYSIS (Oct 15, 2025)")
    print("="*80)

    # Connect to IBKR
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=9998)
        print("✓ Connected to IBKR\n")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    try:
        # Get TSLA contract
        contract = Stock('TSLA', 'SMART', 'USD')
        ib.qualifyContracts(contract)

        # Get TODAY's hourly bars
        print("Fetching TODAY's hourly bars...")
        hourly_bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='1 D',
            barSizeSetting='1 hour',
            whatToShow='TRADES',
            useRTH=True,  # Regular trading hours only
            formatDate=1
        )

        # Get daily bars for comparison
        print("Fetching daily bars for baseline...")
        daily_bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='30 D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=False,
            formatDate=1
        )

        df_hourly = util.df(hourly_bars)
        df_daily = util.df(daily_bars)

        print(f"✓ Fetched {len(df_hourly)} hourly bars for TODAY")
        print(f"✓ Fetched {len(df_daily)} daily bars\n")

        # ============================================================================
        # STEP 1: Calculate Daily Resistance (Baseline)
        # ============================================================================
        print("="*80)
        print("STEP 1: Daily Resistance (Baseline)")
        print("="*80)

        current_price = df_daily.iloc[-1]['close']

        # Smart daily resistance (from scanner algorithm)
        resistance_5d_spike = df_daily['high'].iloc[-5:].max()
        resistance_5d_close = df_daily['close'].iloc[-5:].max()
        spike_pct = (resistance_5d_spike - resistance_5d_close) / resistance_5d_close

        if spike_pct > 0.01:
            resistance_10d_close = df_daily['close'].iloc[-10:].quantile(0.95)
            daily_resistance = max(resistance_5d_close, resistance_10d_close)
        else:
            daily_resistance = resistance_5d_spike

        # Count daily touches
        daily_touches = 0
        for i in range(-20, 0):
            if abs(df_daily.iloc[i]['high'] - daily_resistance) / daily_resistance < 0.015:
                daily_touches += 1

        print(f"\nDaily Resistance: ${daily_resistance:.2f}")
        print(f"Daily Touches: {daily_touches} (over last 20 days)")
        print(f"Current Price: ${current_price:.2f}")
        print(f"Distance: {((daily_resistance - current_price) / current_price * 100):.2f}%")

        # ============================================================================
        # STEP 2: Analyze TODAY's Hourly Bars
        # ============================================================================
        print("\n" + "="*80)
        print("STEP 2: TODAY's Hourly Price Action")
        print("="*80)

        print(f"\nHourly bars for {df_hourly.iloc[0]['date'].date()}:")
        print(f"{'Time':<12} {'Open':<10} {'High':<10} {'Low':<10} {'Close':<10} {'Wick %':<10}")
        print("-"*70)

        for idx, bar in df_hourly.iterrows():
            time_str = str(bar['date'].time())[:5]
            wick_size = bar['high'] - bar['close']
            wick_pct = (wick_size / bar['close']) * 100
            print(f"{time_str:<12} ${bar['open']:<9.2f} ${bar['high']:<9.2f} ${bar['low']:<9.2f} ${bar['close']:<9.2f} {wick_pct:>6.2f}%")

        # Session stats
        todays_high = df_hourly['high'].max()
        todays_low = df_hourly['low'].min()
        todays_range = todays_high - todays_low
        todays_close = df_hourly.iloc[-1]['close']
        range_pct = (todays_range / todays_close) * 100

        print(f"\nTODAY's Session Stats:")
        print(f"  High: ${todays_high:.2f}")
        print(f"  Low: ${todays_low:.2f}")
        print(f"  Range: ${todays_range:.2f} ({range_pct:.2f}%)")
        print(f"  Close: ${todays_close:.2f}")

        # ============================================================================
        # STEP 3: Check Tier 0 Activation Criteria
        # ============================================================================
        print("\n" + "="*80)
        print("STEP 3: Tier 0 Activation Criteria Check")
        print("="*80)

        tier0_activated = False
        tier0_resistance = None
        tier0_reason = ""
        tier0_confidence = ""

        # CRITERION 1: Multiple Intraday Rejections
        print("\n[Criterion 1] Multiple Intraday Rejections:")
        print("-" * 60)

        rejections = []
        for idx, bar in df_hourly.iterrows():
            wick_size = bar['high'] - bar['close']
            wick_pct = (wick_size / bar['close']) * 100

            # Rejection signature: close 0.5%+ below high
            if wick_pct >= 0.5:
                time_str = str(bar['date'].time())[:5]
                rejections.append({
                    'time': time_str,
                    'high': bar['high'],
                    'close': bar['close'],
                    'wick_pct': wick_pct
                })
                print(f"  {time_str}: High ${bar['high']:.2f}, Close ${bar['close']:.2f} (wick -{wick_pct:.2f}%) ✅ REJECTION")

        if len(rejections) >= 2:
            # Find cluster
            rejection_highs = [r['high'] for r in rejections]
            median_high = sorted(rejection_highs)[len(rejection_highs) // 2]

            cluster = [r for r in rejections if abs(r['high'] - median_high) <= 2.0]

            print(f"\n  Rejection count: {len(rejections)}")
            print(f"  Median rejection high: ${median_high:.2f}")
            print(f"  Cluster (±$2): {len(cluster)} rejections")

            if len(cluster) >= 2:
                print(f"\n  ✅ CRITERION MET: {len(cluster)} rejections clustered at ${median_high:.2f}")
                tier0_activated = True
                tier0_resistance = median_high
                tier0_reason = f"Rejected {len(cluster)}x intraday at ${median_high:.2f}"
                tier0_confidence = "HIGH"
        else:
            print(f"  ❌ Only {len(rejections)} rejection(s) found (need 2+)")

        # CRITERION 2: Fresh Intraday High
        print("\n[Criterion 2] Fresh Intraday High:")
        print("-" * 60)

        daily_vs_hourly_pct = abs(todays_high - daily_resistance) / daily_resistance * 100
        print(f"  TODAY's high: ${todays_high:.2f}")
        print(f"  Daily resistance: ${daily_resistance:.2f}")
        print(f"  Difference: {daily_vs_hourly_pct:.2f}%")

        if daily_vs_hourly_pct > 2.0:
            print(f"\n  ✅ CRITERION MET: TODAY's high is {daily_vs_hourly_pct:.2f}% different (>2%)")
            if not tier0_activated:
                tier0_activated = True
                tier0_resistance = todays_high
                tier0_reason = f"TODAY's high ${todays_high:.2f} (daily stale by {daily_vs_hourly_pct:.1f}%)"
                tier0_confidence = "MEDIUM"
        else:
            print(f"  ❌ Difference {daily_vs_hourly_pct:.2f}% is too small (<2%)")

        # CRITERION 3: SMA Confluence
        print("\n[Criterion 3] SMA Confluence at Intraday Level:")
        print("-" * 60)

        sma_10 = df_daily['close'].iloc[-10:].mean()
        sma_20 = df_daily['close'].iloc[-20:].mean()
        sma_50 = df_daily['close'].iloc[-50:].mean() if len(df_daily) >= 50 else None

        sma_levels = {
            'SMA10': sma_10,
            'SMA20': sma_20,
        }
        if sma_50:
            sma_levels['SMA50'] = sma_50

        print(f"  Moving Averages:")
        for name, value in sma_levels.items():
            print(f"    {name}: ${value:.2f}")

        print(f"\n  Checking hourly resistance (${todays_high:.2f}) for SMA alignment:")

        best_sma_match = None
        best_sma_distance = float('inf')

        for sma_name, sma_price in sma_levels.items():
            distance_pct = abs(todays_high - sma_price) / sma_price * 100
            print(f"    {sma_name}: {distance_pct:.2f}% away", end="")

            if distance_pct < 1.0:
                print(" ✅ CONFLUENCE")
                if distance_pct < best_sma_distance:
                    best_sma_distance = distance_pct
                    best_sma_match = (sma_name, sma_price)
            else:
                print()

        # Check if daily has SMA confluence
        print(f"\n  Checking daily resistance (${daily_resistance:.2f}) for SMA alignment:")
        daily_has_sma = False
        for sma_name, sma_price in sma_levels.items():
            distance_pct = abs(daily_resistance - sma_price) / sma_price * 100
            print(f"    {sma_name}: {distance_pct:.2f}% away", end="")
            if distance_pct < 2.0:
                print(" (close)")
                daily_has_sma = True
            else:
                print()

        if best_sma_match and not daily_has_sma:
            sma_name, sma_price = best_sma_match
            print(f"\n  ✅ CRITERION MET: Hourly at {sma_name} ${sma_price:.2f}, daily has no SMA confluence")
            if not tier0_activated or tier0_confidence != "HIGH":
                tier0_activated = True
                tier0_resistance = sma_price
                tier0_reason = f"Intraday at {sma_name} ${sma_price:.2f} (confluence)"
                tier0_confidence = "HIGH"
        else:
            print(f"\n  ❌ No unique SMA confluence at hourly level")

        # CRITERION 4: Tight Intraday Consolidation
        print("\n[Criterion 4] Tight Intraday Consolidation:")
        print("-" * 60)

        print(f"  TODAY's range: {range_pct:.2f}%")

        if range_pct < 2.0:
            # Count boundary touches
            boundary_touches = sum(1 for _, bar in df_hourly.iterrows()
                                 if abs(bar['high'] - todays_high) < 1.0)

            print(f"  Range is tight (<2%)")
            print(f"  Upper boundary touches: {boundary_touches}")

            if boundary_touches >= 2:
                print(f"\n  ✅ CRITERION MET: Tight range with {boundary_touches} touches at ${todays_high:.2f}")
                if not tier0_activated or tier0_confidence != "HIGH":
                    tier0_activated = True
                    tier0_resistance = todays_high
                    tier0_reason = f"Tight consolidation ({range_pct:.1f}% range), tested {boundary_touches}x"
                    tier0_confidence = "HIGH"
            else:
                print(f"  ❌ Not enough boundary touches ({boundary_touches} < 2)")
        else:
            print(f"  ❌ Range too wide ({range_pct:.2f}% >= 2%)")

        # CRITERION 5: Gap Case
        print("\n[Criterion 5] Gap Adjustment:")
        print("-" * 60)

        prev_close = df_daily.iloc[-2]['close']
        todays_open = df_hourly.iloc[0]['open']
        gap_pct = abs(todays_open - prev_close) / prev_close * 100

        print(f"  Yesterday's close: ${prev_close:.2f}")
        print(f"  TODAY's open: ${todays_open:.2f}")
        print(f"  Gap: {gap_pct:.2f}%")

        if gap_pct > 3.0:
            print(f"\n  ✅ CRITERION MET: {gap_pct:.1f}% gap (daily levels obsolete)")
            if not tier0_activated:
                tier0_activated = True
                tier0_resistance = todays_high
                tier0_reason = f"Gap {gap_pct:.1f}% (daily levels obsolete)"
                tier0_confidence = "MEDIUM"
        else:
            print(f"  ❌ Gap too small ({gap_pct:.2f}% < 3%)")

        # ============================================================================
        # STEP 4: Final Decision
        # ============================================================================
        print("\n" + "="*80)
        print("STEP 4: Final Resistance Decision")
        print("="*80)

        if tier0_activated:
            print(f"\n✅ TIER 0 OVERRIDE ACTIVATED")
            print(f"\n📊 FINAL RESISTANCE: ${tier0_resistance:.2f} (TIER_0_HOURLY)")
            print(f"   Reason: {tier0_reason}")
            print(f"   Confidence: {tier0_confidence}")
            print(f"\n   Daily resistance (reference): ${daily_resistance:.2f}")
            print(f"   Distance from current price: {((tier0_resistance - todays_close) / todays_close * 100):+.2f}%")

            # Calculate hourly touches
            hourly_touches = sum(1 for _, bar in df_hourly.iterrows()
                               if abs(bar['high'] - tier0_resistance) / tier0_resistance < 0.01)

            print(f"\n   Hourly touches: {hourly_touches}")
            print(f"   Daily touches: {daily_touches}")
        else:
            print(f"\n❌ NO TIER 0 OVERRIDE")
            print(f"\n📊 FINAL RESISTANCE: ${daily_resistance:.2f} (DAILY)")
            print(f"   Reason: Tested {daily_touches}x over 20 days")
            print(f"   Distance from current price: {((daily_resistance - todays_close) / todays_close * 100):+.2f}%")
            print(f"\n   Hourly note: No strong intraday pattern detected")
            print(f"   TODAY's high: ${todays_high:.2f} (for reference)")

        print("\n" + "="*80)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        ib.disconnect()
        print("\n✓ Disconnected from IBKR")


if __name__ == "__main__":
    analyze_tsla_hourly()
