#!/usr/bin/env python3
"""Run backtests using existing scanner results"""

from backtester import PS60Backtester
from datetime import datetime
from pathlib import Path
import json
import pandas as pd

# Find all scanner files
scanner_dir = Path('monthly_results')
scanner_files = sorted(scanner_dir.glob('scanner_*.json'))

print(f"Found {len(scanner_files)} scanner files")

all_trades = []
daily_results = []

for scanner_file in scanner_files:
    # Extract date from filename: scanner_20250930.json
    date_str = scanner_file.stem.split('_')[1]  # '20250930'
    test_date = datetime.strptime(date_str, '%Y%m%d')

    print(f"\n{'='*80}")
    print(f"Backtesting {test_date.strftime('%Y-%m-%d')}")
    print(f"{'='*80}")

    try:
        # Run backtest
        backtester = PS60Backtester(
            scanner_results_path=str(scanner_file),
            test_date=test_date,
            account_size=100000
        )

        backtester.run()

        if backtester.trades:
            total_pnl = sum(t['pnl'] for t in backtester.trades)
            winners = [t for t in backtester.trades if t['pnl'] > 0]
            losers = [t for t in backtester.trades if t['pnl'] < 0]
            win_rate = (len(winners) / len(backtester.trades) * 100) if backtester.trades else 0

            daily_summary = {
                'date': test_date.strftime('%Y-%m-%d'),
                'trades': len(backtester.trades),
                'winners': len(winners),
                'losers': len(losers),
                'win_rate': round(win_rate, 1),
                'total_pnl': round(total_pnl, 2),
                'avg_pnl': round(total_pnl / len(backtester.trades), 2) if backtester.trades else 0
            }

            daily_results.append(daily_summary)
            all_trades.extend(backtester.trades)

            print(f"✓ {len(backtester.trades)} trades, ${total_pnl:,.2f} P&L")
        else:
            print(f"✓ No trades")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

# Generate summary
if daily_results:
    print(f"\n{'='*80}")
    print(f"MONTHLY SUMMARY: September 2025")
    print(f"{'='*80}\n")

    df = pd.DataFrame(daily_results)
    print(df.to_string(index=False))

    total_trades = df['trades'].sum()
    total_pnl = df['total_pnl'].sum()
    avg_daily_pnl = df['total_pnl'].mean()
    winning_days = len(df[df['total_pnl'] > 0])
    losing_days = len(df[df['total_pnl'] < 0])
    overall_win_rate = (df['winners'].sum() / df['trades'].sum() * 100) if total_trades > 0 else 0

    print(f"\n{'='*80}")
    print(f"OVERALL STATISTICS")
    print(f"{'='*80}")
    print(f"Trading Days: {len(daily_results)}")
    print(f"Total Trades: {total_trades}")
    print(f"Total P&L: ${total_pnl:,.2f}")
    print(f"Avg Daily P&L: ${avg_daily_pnl:,.2f}")
    print(f"Win Rate: {overall_win_rate:.1f}%")
    print(f"Winning Days: {winning_days}/{len(daily_results)} ({winning_days/len(daily_results)*100:.1f}%)")
    print(f"Losing Days: {losing_days}/{len(daily_results)}")
    print(f"Monthly Return: {(total_pnl/100000)*100:.2f}%")

    # Save results
    summary_file = scanner_dir / f'monthly_summary_202509.json'
    with open(summary_file, 'w') as f:
        json.dump({
            'month': '2025-09',
            'daily_results': daily_results,
            'summary': {
                'trading_days': len(daily_results),
                'total_trades': int(total_trades),
                'total_pnl': round(total_pnl, 2),
                'avg_daily_pnl': round(avg_daily_pnl, 2),
                'win_rate': round(overall_win_rate, 1),
                'winning_days': winning_days,
                'losing_days': losing_days,
                'monthly_return_pct': round((total_pnl/100000)*100, 2)
            }
        }, f, indent=2)
    print(f"\n✓ Summary saved to {summary_file}")

    # Save all trades
    trades_file = scanner_dir / f'all_trades_202509.json'
    with open(trades_file, 'w') as f:
        json.dump(all_trades, f, indent=2, default=str)
    print(f"✓ All trades saved to {trades_file}")
