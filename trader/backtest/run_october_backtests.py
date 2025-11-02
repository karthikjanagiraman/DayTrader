#!/usr/bin/env python3
"""
Run backtests for all October 2025 trading days and aggregate results.

Usage:
    python3 run_october_backtests.py
"""

import subprocess
import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# October 2025 trading days
OCTOBER_DATES = [
    "20251001", "20251002", "20251003", "20251006", "20251007",
    "20251008", "20251009", "20251010", "20251013", "20251014",
    "20251015", "20251016", "20251020", "20251021", "20251022",
    "20251023", "20251024", "20251027", "20251028", "20251029",
    "20251030", "20251031"
]

ACCOUNT_SIZE = 50000
BASE_DIR = Path(__file__).parent.parent.parent
SCANNER_DIR = BASE_DIR / "stockscanner" / "output"
RESULTS_DIR = Path(__file__).parent / "results"
LOGS_DIR = Path(__file__).parent / "logs"

def format_date(yyyymmdd):
    """Convert YYYYMMDD to YYYY-MM-DD"""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"

def run_backtest(date_str):
    """Run backtest for a single date"""
    scanner_file = SCANNER_DIR / f"scanner_results_{date_str}.json"
    date_formatted = format_date(date_str)

    if not scanner_file.exists():
        print(f"  ⚠️  Scanner file not found: {scanner_file}")
        return None

    print(f"\n{'='*80}")
    print(f"📊 Running backtest for {date_formatted} ({date_str})")
    print(f"{'='*80}")

    cmd = [
        "python3", "backtester.py",
        "--scanner", str(scanner_file),
        "--date", date_formatted,
        "--account-size", str(ACCOUNT_SIZE)
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per backtest
        )

        if result.returncode != 0:
            print(f"  ❌ Backtest failed with error:")
            print(result.stderr)
            return None

        # Parse results from output
        return parse_backtest_output(result.stdout, date_str)

    except subprocess.TimeoutExpired:
        print(f"  ⏱️  Backtest timed out after 5 minutes")
        return None
    except Exception as e:
        print(f"  ❌ Error running backtest: {e}")
        return None

def parse_backtest_output(output, date_str):
    """Extract key metrics from backtest output"""
    results = {
        'date': date_str,
        'total_trades': 0,
        'winners': 0,
        'losers': 0,
        'total_pnl': 0.0,
        'avg_winner': 0.0,
        'avg_loser': 0.0,
        'profit_factor': 0.0,
        'win_rate': 0.0
    }

    lines = output.split('\n')

    for line in lines:
        if 'Total trades:' in line:
            try:
                results['total_trades'] = int(line.split(':')[1].strip())
            except:
                pass
        elif 'Winners:' in line:
            try:
                parts = line.split(':')[1].strip().split('(')
                results['winners'] = int(parts[0].strip())
            except:
                pass
        elif 'Losers:' in line:
            try:
                parts = line.split(':')[1].strip().split('(')
                results['losers'] = int(parts[0].strip())
            except:
                pass
        elif 'Total P&L:' in line:
            try:
                pnl_str = line.split('$')[1].strip().split()[0].replace(',', '')
                results['total_pnl'] = float(pnl_str)
            except:
                pass
        elif 'Avg winner:' in line:
            try:
                avg_str = line.split('$')[1].strip().split()[0].replace(',', '')
                results['avg_winner'] = float(avg_str)
            except:
                pass
        elif 'Avg loser:' in line:
            try:
                avg_str = line.split('$')[1].strip().split()[0].replace(',', '')
                results['avg_loser'] = float(avg_str)
            except:
                pass
        elif 'Profit factor:' in line:
            try:
                pf_str = line.split(':')[1].strip()
                results['profit_factor'] = float(pf_str)
            except:
                pass

    # Calculate win rate
    if results['total_trades'] > 0:
        results['win_rate'] = (results['winners'] / results['total_trades']) * 100

    return results

def aggregate_results(daily_results):
    """Aggregate daily results into monthly statistics"""
    total_trades = 0
    total_winners = 0
    total_losers = 0
    total_pnl = 0.0
    total_winner_pnl = 0.0
    total_loser_pnl = 0.0

    trading_days = len([r for r in daily_results if r is not None])

    for result in daily_results:
        if result is None:
            continue

        total_trades += result['total_trades']
        total_winners += result['winners']
        total_losers += result['losers']
        total_pnl += result['total_pnl']

        if result['winners'] > 0 and result['avg_winner'] > 0:
            total_winner_pnl += result['avg_winner'] * result['winners']
        if result['losers'] > 0 and result['avg_loser'] < 0:
            total_loser_pnl += result['avg_loser'] * result['losers']

    # Calculate aggregated metrics
    avg_winner = total_winner_pnl / total_winners if total_winners > 0 else 0
    avg_loser = total_loser_pnl / total_losers if total_losers > 0 else 0
    win_rate = (total_winners / total_trades * 100) if total_trades > 0 else 0

    gross_profit = abs(total_winner_pnl)
    gross_loss = abs(total_loser_pnl)
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

    avg_daily_pnl = total_pnl / trading_days if trading_days > 0 else 0
    monthly_return_pct = (total_pnl / ACCOUNT_SIZE) * 100

    return {
        'trading_days': trading_days,
        'total_trades': total_trades,
        'winners': total_winners,
        'losers': total_losers,
        'win_rate': win_rate,
        'total_pnl': total_pnl,
        'avg_winner': avg_winner,
        'avg_loser': avg_loser,
        'profit_factor': profit_factor,
        'avg_daily_pnl': avg_daily_pnl,
        'monthly_return_pct': monthly_return_pct,
        'account_size': ACCOUNT_SIZE
    }

def print_summary(monthly_stats, daily_results):
    """Print comprehensive summary report"""
    print("\n" + "="*80)
    print("📈 OCTOBER 2025 MONTHLY BACKTEST SUMMARY")
    print("="*80)

    print(f"\n📅 PERIOD:")
    print(f"  Trading Days: {monthly_stats['trading_days']}")
    print(f"  Account Size: ${monthly_stats['account_size']:,.0f}")

    print(f"\n📊 TRADE SUMMARY:")
    print(f"  Total Trades: {monthly_stats['total_trades']}")
    print(f"  Winners: {monthly_stats['winners']} ({monthly_stats['win_rate']:.1f}%)")
    print(f"  Losers: {monthly_stats['losers']} ({100-monthly_stats['win_rate']:.1f}%)")

    print(f"\n💰 P&L ANALYSIS:")
    print(f"  Total P&L: ${monthly_stats['total_pnl']:,.2f}")
    print(f"  Monthly Return: {monthly_stats['monthly_return_pct']:.2f}%")
    print(f"  Avg Daily P&L: ${monthly_stats['avg_daily_pnl']:,.2f}")
    print(f"  Avg Winner: ${monthly_stats['avg_winner']:,.2f}")
    print(f"  Avg Loser: ${monthly_stats['avg_loser']:,.2f}")
    print(f"  Profit Factor: {monthly_stats['profit_factor']:.2f}")

    # Daily breakdown
    print(f"\n📆 DAILY BREAKDOWN:")
    print(f"  {'Date':<12} {'Trades':>7} {'W/L':>7} {'Win%':>6} {'P&L':>12}")
    print(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*6} {'-'*12}")

    for result in daily_results:
        if result is None:
            continue

        date_formatted = format_date(result['date'])
        wl_ratio = f"{result['winners']}/{result['losers']}"

        # Color code P&L
        pnl_str = f"${result['total_pnl']:,.2f}"
        if result['total_pnl'] > 0:
            pnl_display = f"✅ {pnl_str:>10}"
        elif result['total_pnl'] < 0:
            pnl_display = f"❌ {pnl_str:>10}"
        else:
            pnl_display = f"   {pnl_str:>10}"

        print(f"  {date_formatted:<12} {result['total_trades']:>7} {wl_ratio:>7} {result['win_rate']:>5.1f}% {pnl_display}")

    print(f"\n{'='*80}")

def save_results(monthly_stats, daily_results):
    """Save results to JSON file"""
    RESULTS_DIR.mkdir(exist_ok=True)

    output_file = RESULTS_DIR / "october_2025_backtest_summary.json"

    data = {
        'summary': monthly_stats,
        'daily_results': [r for r in daily_results if r is not None],
        'generated_at': datetime.now().isoformat()
    }

    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")

def main():
    print("="*80)
    print("🚀 OCTOBER 2025 BATCH BACKTEST")
    print("="*80)
    print(f"\nAccount Size: ${ACCOUNT_SIZE:,.0f}")
    print(f"Total Days: {len(OCTOBER_DATES)}")
    print(f"Scanner Files: {SCANNER_DIR}")
    print(f"\nStarting backtests...\n")

    daily_results = []

    for i, date_str in enumerate(OCTOBER_DATES, 1):
        print(f"\n[{i}/{len(OCTOBER_DATES)}]", end=" ")
        result = run_backtest(date_str)
        daily_results.append(result)

        if result:
            print(f"  ✅ Completed: {result['total_trades']} trades, ${result['total_pnl']:,.2f} P&L")
        else:
            print(f"  ⚠️  Skipped or failed")

    # Aggregate and display results
    monthly_stats = aggregate_results(daily_results)
    print_summary(monthly_stats, daily_results)
    save_results(monthly_stats, daily_results)

    print(f"\n✨ Batch backtest completed!\n")

if __name__ == "__main__":
    main()
