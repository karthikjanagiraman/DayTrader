#!/usr/bin/env python3
"""
PS60 Analysis Tool

Unified command-line interface for all analysis modules.

Usage:
    ./analyze.py eod 20251007                # COMPREHENSIVE EOD analysis (3 steps)
    ./analyze.py daily 20251007              # Daily session analysis
    ./analyze.py trades 20251007             # Trade performance analysis
    ./analyze.py filters 20251007            # Filter effectiveness
    ./analyze.py scanner 20251007            # Scanner quality
    ./analyze.py market 20251007             # Market data validation
    ./analyze.py backtest 20251007           # Backtest comparison
    ./analyze.py walkthrough 20251007        # Session walkthrough
    ./analyze.py all 20251007                # Run all standard analyses
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'dailyanalysis'))

from dailyanalysis import (
    DailySessionAnalyzer,
    TradePerformanceAnalyzer,
    FilterEffectivenessAnalyzer,
    ScannerQualityAnalyzer,
)

# Import new analyzers
from dailyanalysis.eod_report import EODReport
from dailyanalysis.market_validator import MarketDataValidator
from dailyanalysis.backtest_comparator import BacktestComparator
from dailyanalysis.session_walkthrough import SessionWalkthrough


def print_usage():
    """Print usage information"""
    print(__doc__)
    print("\nAvailable Commands:")
    print("  eod DATE        - COMPREHENSIVE EOD analysis (recommended)")
    print("  daily DATE      - Daily session P&L and summary")
    print("  trades DATE     - Trade-level pattern analysis")
    print("  filters DATE    - Filter effectiveness analysis")
    print("  scanner DATE    - Scanner prediction quality")
    print("  market DATE     - Market data validation")
    print("  backtest DATE   - Backtest comparison")
    print("  walkthrough DATE - Session walkthrough")
    print("  all DATE        - Run all standard analyses")
    print("\nExamples:")
    print("  ./analyze.py eod 20251007        # Best for EOD review")
    print("  ./analyze.py all 20251007        # Standard analyses only")


def analyze_daily(date_str):
    """Run daily session analysis"""
    analyzer = DailySessionAnalyzer(date_str)
    analyzer.analyze()
    analyzer.save_report()


def analyze_trades(date_str):
    """Run trade performance analysis"""
    analyzer = TradePerformanceAnalyzer(date_str=date_str)
    analyzer.analyze()


def analyze_filters(date_str):
    """Run filter effectiveness analysis"""
    log_file = f"logs/trader_{date_str}.log"
    analyzer = FilterEffectivenessAnalyzer(log_file)
    analyzer.analyze()


def analyze_scanner(date_str):
    """Run scanner quality analysis"""
    # Try enhanced scoring first, fall back to standard scanner
    scanner_file = f"../scanner_validation/rescored_{date_str}.csv"
    if not Path(scanner_file).exists():
        scanner_file = f"../stockscanner/output/scanner_results_{date_str}.json"

    trades_file = f"logs/trades_{date_str}.json"

    if not Path(trades_file).exists():
        print(f"\n⚠️  No trades file found for {date_str}")
        print("   Scanner analysis requires trades to compare against")
        return

    if not Path(scanner_file).exists():
        print(f"\n⚠️  No scanner results found for {date_str}")
        print(f"   Tried: {scanner_file}")
        return

    analyzer = ScannerQualityAnalyzer(scanner_file, trades_file)
    analyzer.analyze()


def analyze_all(date_str):
    """Run all analyses"""
    print("\n" + "="*80)
    print("COMPREHENSIVE ANALYSIS SUITE")
    print("="*80)

    # 1. Daily session
    print("\n" + "="*80)
    print("1/4: DAILY SESSION ANALYSIS")
    print("="*80)
    analyze_daily(date_str)

    # 2. Trade performance
    print("\n" + "="*80)
    print("2/4: TRADE PERFORMANCE ANALYSIS")
    print("="*80)
    analyze_trades(date_str)

    # 3. Filter effectiveness
    print("\n" + "="*80)
    print("3/4: FILTER EFFECTIVENESS ANALYSIS")
    print("="*80)
    analyze_filters(date_str)

    # 4. Scanner quality
    print("\n" + "="*80)
    print("4/4: SCANNER QUALITY ANALYSIS")
    print("="*80)
    analyze_scanner(date_str)

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\n✓ Daily session report saved to: logs/analysis_{date_str}.json")


def analyze_eod(date_str, skip_ib=False):
    """Run comprehensive EOD analysis"""
    reporter = EODReport(date_str, skip_ib=skip_ib)
    reporter.generate_full_report()


def analyze_market(date_str):
    """Run market data validation"""
    validator = MarketDataValidator(date_str)
    validator.validate_all()


def analyze_backtest(date_str):
    """Run backtest comparison"""
    comparator = BacktestComparator(date_str)
    comparator.run_backtest()
    comparator.compare_with_live()
    comparator.compare_with_market()
    comparator.save_comparison()


def analyze_walkthrough(date_str):
    """Run session walkthrough"""
    walkthrough = SessionWalkthrough(date_str)
    walkthrough.generate_walkthrough()
    walkthrough.save_walkthrough()


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()
    date_str = sys.argv[2]

    # Validate date format (YYYYMMDD)
    if len(date_str) != 8 or not date_str.isdigit():
        print(f"⚠️  Invalid date format: {date_str}")
        print("   Expected: YYYYMMDD (e.g., 20251007)")
        sys.exit(1)

    # Check for optional flags
    skip_ib = '--skip-ib' in sys.argv

    # Route to appropriate analyzer
    if command == 'eod':
        analyze_eod(date_str, skip_ib=skip_ib)
    elif command == 'daily':
        analyze_daily(date_str)
    elif command == 'trades':
        analyze_trades(date_str)
    elif command == 'filters':
        analyze_filters(date_str)
    elif command == 'scanner':
        analyze_scanner(date_str)
    elif command == 'market':
        analyze_market(date_str)
    elif command == 'backtest':
        analyze_backtest(date_str)
    elif command == 'walkthrough':
        analyze_walkthrough(date_str)
    elif command == 'all':
        analyze_all(date_str)
    else:
        print(f"⚠️  Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()
