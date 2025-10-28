#!/usr/bin/env python3
"""
Test CVD calculator with real October 16 data
Validates that CVD would have blocked the weak entries (META, XOM, etc.)
"""

import sys
sys.path.insert(0, '/Users/karthik/projects/DayTrader')

from ib_insync import IB, Stock
from datetime import datetime
from trader.indicators.cvd_calculator import CVDCalculator


def test_oct16_weak_entries():
    """
    Test CVD on the 7 weak entries from Oct 16 that should have been blocked:
    - META: 0.3x vol, 0.0% candle
    - XOM: 0.5x vol, 0.0% candle
    - TSLA: 0.6x vol, 0.3% candle
    - CVX: 0.6x vol, 0.0% candle
    - RIVN: 1.3x vol, 0.0% candle
    - LI: 1.3x vol, 0.0% candle
    - LYFT: 0.5x vol, 0.0% candle

    Hypothesis: These all had weak/bearish CVD trends at entry
    """

    print("="*80)
    print("TESTING CVD WITH REAL OCTOBER 16, 2025 DATA")
    print("="*80)

    # Connect to IBKR
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=9001)
        print("✓ Connected to IBKR")
    except Exception as e:
        print(f"✗ Failed to connect to IBKR: {e}")
        print("Make sure TWS/Gateway is running on port 7497")
        return

    # Test symbols and their entry times (from Oct 16 logs)
    test_cases = [
        {'symbol': 'META', 'entry_time': '09:47:00', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
        {'symbol': 'XOM', 'entry_time': '09:47:30', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
        {'symbol': 'TSLA', 'entry_time': '09:48:00', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
        {'symbol': 'CVX', 'entry_time': '09:48:30', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
        {'symbol': 'RIVN', 'entry_time': '09:49:00', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
        {'symbol': 'LI', 'entry_time': '09:49:30', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
        {'symbol': 'LYFT', 'entry_time': '09:50:00', 'side': 'SHORT', 'expected_cvd': 'BEARISH or NEUTRAL'},
    ]

    results = []

    for test in test_cases:
        symbol = test['symbol']
        entry_time = test['entry_time']
        side = test['side']

        print(f"\n{'='*80}")
        print(f"Testing {symbol} {side} @ {entry_time}")
        print(f"{'='*80}")

        try:
            # Fetch 1-minute bars for the first hour of trading
            contract = Stock(symbol, 'SMART', 'USD')

            # Get bars from 9:30 AM to entry time
            bars = ib.reqHistoricalData(
                contract,
                endDateTime='20251016 ' + entry_time + ' US/Eastern',
                durationStr='1800 S',  # 30 minutes before
                barSizeSetting='1 min',
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )

            if not bars or len(bars) == 0:
                print(f"  ✗ No data available for {symbol}")
                results.append({
                    'symbol': symbol,
                    'side': side,
                    'cvd_available': False,
                    'cvd_trend': 'N/A',
                    'would_block': False,
                    'reason': 'No data'
                })
                continue

            print(f"  ✓ Fetched {len(bars)} 1-minute bars")

            # Calculate CVD at entry time
            calculator = CVDCalculator(slope_lookback=5)

            # Use last bar (at entry time)
            cvd_result = calculator.calculate_from_bars(bars, current_idx=len(bars)-1)

            print(f"  CVD Value: {cvd_result.cvd_value:,.0f}")
            print(f"  CVD Slope: {cvd_result.cvd_slope:,.0f}")
            print(f"  CVD Trend: {cvd_result.cvd_trend}")
            print(f"  Divergence: {cvd_result.divergence}")

            # Check if CVD would have blocked this entry
            would_block = False
            block_reason = None

            if side == 'SHORT':
                # SHORT needs BEARISH CVD trend
                if cvd_result.cvd_trend == 'BULLISH':
                    would_block = True
                    block_reason = f"CVD trend {cvd_result.cvd_trend} (expected BEARISH for SHORT)"
            elif side == 'LONG':
                # LONG needs BULLISH CVD trend
                if cvd_result.cvd_trend == 'BEARISH':
                    would_block = True
                    block_reason = f"CVD trend {cvd_result.cvd_trend} (expected BULLISH for LONG)"

            if would_block:
                print(f"  ✓ CVD WOULD BLOCK: {block_reason}")
            else:
                print(f"  ✗ CVD would NOT block (trend is {cvd_result.cvd_trend})")

            results.append({
                'symbol': symbol,
                'side': side,
                'cvd_available': True,
                'cvd_value': cvd_result.cvd_value,
                'cvd_slope': cvd_result.cvd_slope,
                'cvd_trend': cvd_result.cvd_trend,
                'divergence': cvd_result.divergence,
                'would_block': would_block,
                'reason': block_reason if would_block else 'CVD allowed'
            })

        except Exception as e:
            print(f"  ✗ Error testing {symbol}: {e}")
            results.append({
                'symbol': symbol,
                'side': side,
                'cvd_available': False,
                'cvd_trend': 'ERROR',
                'would_block': False,
                'reason': str(e)
            })

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    total = len(results)
    blocked = sum(1 for r in results if r['would_block'])
    allowed = total - blocked

    print(f"\nTotal weak entries tested: {total}")
    print(f"CVD would BLOCK: {blocked} ({blocked/total*100:.1f}%)")
    print(f"CVD would ALLOW: {allowed} ({allowed/total*100:.1f}%)")

    print(f"\nDetailed Results:")
    print(f"{'Symbol':<8} {'Side':<6} {'CVD Trend':<12} {'Blocked?':<10} {'Reason'}")
    print("-"*80)
    for r in results:
        blocked_str = "YES ✓" if r['would_block'] else "NO ✗"
        print(f"{r['symbol']:<8} {r['side']:<6} {r['cvd_trend']:<12} {blocked_str:<10} {r.get('reason', 'N/A')}")

    print(f"\n{'='*80}")
    print("EXPECTED OUTCOME:")
    print("If CVD blocks 50-70% of these weak entries, it's working correctly")
    print(f"{'='*80}")

    ib.disconnect()
    return results


if __name__ == '__main__':
    test_oct16_weak_entries()
