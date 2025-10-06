#!/usr/bin/env python3
"""
Week backtest with new requirements implementation
Testing: Sept 23-29, 2025 (7 trading days)

Validates:
- Min R/R 2.0 filter
- 1R-based partial profits
- Volume + momentum + sustained break confirmation
- No 5-minute rule
- Slippage 0.1% + commissions $0.005/share
"""

import sys
from pathlib import Path
from datetime import date, timedelta

# Add paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'stockscanner'))

from backtest.backtester import PS60Backtester

# Test date range
start_date = date(2025, 9, 23)
end_date = date(2025, 9, 29)

print("=" * 80)
print("WEEK BACKTEST: September 23-29, 2025")
print("Testing new requirements implementation:")
print("  - Min R/R 2.0 (was 1.0)")
print("  - 1R-based partial profits (was $0.25)")
print("  - Volume + momentum + sustained break confirmation")
print("  - NO 5-minute rule")
print("  - Slippage 0.1% + commissions $0.005/share")
print("=" * 80)

all_trades = []
daily_pnls = []

current_date = start_date
while current_date <= end_date:
    scanner_file = f"backtest/monthly_results_production/scanner_{current_date.strftime('%Y%m%d')}.json"

    # Check if scanner file exists
    if not Path(scanner_file).exists():
        print(f"\n⚠️  {current_date}: Scanner file not found, skipping")
        current_date += timedelta(days=1)
        continue

    print(f"\n{'=' * 80}")
    print(f"Testing: {current_date}")
    print('=' * 80)

    try:
        backtester = PS60Backtester(
            scanner_file=scanner_file,
            test_date=current_date,
            account_size=100000
        )

        backtester.run()

        if backtester.trades:
            day_pnl = sum(t['pnl'] for t in backtester.trades)
            winners = sum(1 for t in backtester.trades if t['pnl'] > 0)
            win_rate = (winners / len(backtester.trades)) * 100

            daily_pnls.append({
                'date': current_date,
                'trades': len(backtester.trades),
                'pnl': day_pnl,
                'win_rate': win_rate
            })
            all_trades.extend(backtester.trades)

            print(f"\n{'=' * 80}")
            print(f"Day Summary: {len(backtester.trades)} trades, ${day_pnl:,.2f} P&L, {win_rate:.1f}% win rate")
            print(f"{'=' * 80}")
        else:
            print("\n❌ No trades executed")
            daily_pnls.append({
                'date': current_date,
                'trades': 0,
                'pnl': 0,
                'win_rate': 0
            })

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    current_date += timedelta(days=1)

# Print week summary
print("\n" + "=" * 80)
print("WEEK SUMMARY: September 23-29, 2025")
print("=" * 80)

if all_trades:
    total_pnl = sum(t['pnl'] for t in all_trades)
    winners = sum(1 for t in all_trades if t['pnl'] > 0)
    losers = len(all_trades) - winners
    win_rate = (winners / len(all_trades)) * 100

    avg_winner = sum(t['pnl'] for t in all_trades if t['pnl'] > 0) / winners if winners > 0 else 0
    avg_loser = sum(t['pnl'] for t in all_trades if t['pnl'] < 0) / losers if losers > 0 else 0

    print(f"Total Trades: {len(all_trades)}")
    print(f"Winners: {winners} ({win_rate:.1f}%)")
    print(f"Losers: {losers}")
    print(f"Total P&L: ${total_pnl:,.2f}")
    print(f"Avg P/L per trade: ${total_pnl / len(all_trades):,.2f}")
    print(f"Avg Winner: ${avg_winner:,.2f}")
    print(f"Avg Loser: ${avg_loser:,.2f}")

    print(f"\nDaily Breakdown:")
    print("-" * 80)
    for day in daily_pnls:
        if day['trades'] > 0:
            print(f"{day['date']}: {day['trades']:2d} trades, ${day['pnl']:8,.2f}, {day['win_rate']:5.1f}% win rate")
        else:
            print(f"{day['date']}: No trades")

    print("\n" + "=" * 80)
    print("KEY OBSERVATIONS:")
    print("=" * 80)

    # Analysis
    if len(all_trades) < 10:
        print("⚠️  Very few trades - confirmation logic may be too restrictive")
        print("   Consider reducing volume_surge_multiplier or momentum_candle_size")
    elif win_rate >= 40:
        print("✅ Win rate is good (>=40%) - confirmation logic working well")
    else:
        print("⚠️  Win rate below 40% - may need to adjust confirmation parameters")

    if total_pnl > 0:
        print("✅ Profitable week - strategy showing positive results")
    else:
        print("❌ Losing week - need to review trades and adjust parameters")

    avg_trades_per_day = len(all_trades) / len([d for d in daily_pnls if d['trades'] > 0])
    print(f"\nAvg trades per day: {avg_trades_per_day:.1f}")

    if avg_trades_per_day < 3:
        print("⚠️  Low trade count - confirmation may be filtering too aggressively")
    elif avg_trades_per_day > 15:
        print("⚠️  High trade count - may be overtrading")
    else:
        print("✅ Trade count looks reasonable")

else:
    print("❌ No trades executed during the week")
    print("⚠️  Confirmation logic is too restrictive - adjust parameters")

print("\n" + "=" * 80)
