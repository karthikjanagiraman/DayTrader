#!/usr/bin/env python3
"""
Comprehensive EOD Report

Orchestrates all three analysis steps:
1. Market data validation
2. Backtest comparison
3. Live session walkthrough

Generates unified report with actionable insights.
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Import all analyzers
from market_validator import MarketDataValidator
from backtest_comparator import BacktestComparator
from session_walkthrough import SessionWalkthrough
from daily_analyzer import DailySessionAnalyzer
from trade_analyzer import TradePerformanceAnalyzer
from filter_analyzer import FilterEffectivenessAnalyzer
from scanner_analyzer import ScannerQualityAnalyzer


class EODReport:
    """
    Comprehensive End-of-Day Analysis Report

    Runs all analysis steps and generates unified insights
    """

    def __init__(self, date_str, skip_ib=False):
        """
        Initialize EOD reporter

        Args:
            date_str: Date in YYYYMMDD format
            skip_ib: Skip IBKR connection (for testing)
        """
        self.date_str = date_str
        self.skip_ib = skip_ib
        self.date = datetime.strptime(date_str, '%Y%m%d')

        # Analysis results
        self.market_validation = None
        self.backtest_comparison = None
        self.session_walkthrough = None
        self.daily_analysis = None

        # Summary insights
        self.insights = {
            'successes': [],
            'failures': [],
            'recommendations': [],
            'action_items': []
        }

    def generate_full_report(self):
        """Generate complete EOD analysis report"""
        print(f"\n{'='*80}")
        print(f"COMPREHENSIVE EOD ANALYSIS REPORT")
        print(f"Date: {self.date.strftime('%B %d, %Y')}")
        print(f"{'='*80}")

        # Step 1: Market Data Validation
        print(f"\n{'='*60}")
        print("STEP 1: MARKET DATA VALIDATION")
        print(f"{'='*60}")
        print("Validating scanner predictions against actual market movements...")

        if not self.skip_ib:
            try:
                validator = MarketDataValidator(self.date_str)
                validator.validate_all()
                self.market_validation = validator.breakout_analysis
                self._analyze_market_validation()
            except Exception as e:
                print(f"⚠️  Market validation failed: {e}")
                print("   Continuing with other analyses...")
        else:
            print("⚠️  Skipping market validation (IBKR connection disabled)")

        # Step 2: Backtest Comparison
        print(f"\n{'='*60}")
        print("STEP 2: SAME-DAY BACKTEST COMPARISON")
        print(f"{'='*60}")
        print("Running backtest with today's filters and comparing...")

        try:
            comparator = BacktestComparator(self.date_str)
            comparator.run_backtest()
            comparator.compare_with_live()
            if self.market_validation:
                comparator.market_validation = self.market_validation
                comparator.compare_with_market()
            comparator.save_comparison()
            self.backtest_comparison = comparator
            self._analyze_backtest_comparison()
        except Exception as e:
            print(f"⚠️  Backtest comparison failed: {e}")
            print("   Continuing with other analyses...")

        # Step 3: Live Session Walkthrough
        print(f"\n{'='*60}")
        print("STEP 3: LIVE SESSION WALKTHROUGH")
        print(f"{'='*60}")
        print("Analyzing chronological session events...")

        try:
            walkthrough = SessionWalkthrough(self.date_str)
            walkthrough.generate_walkthrough()
            walkthrough.save_walkthrough()
            self.session_walkthrough = walkthrough
            self._analyze_session_walkthrough()
        except Exception as e:
            print(f"⚠️  Session walkthrough failed: {e}")

        # Step 4: Standard Daily Analysis
        print(f"\n{'='*60}")
        print("STEP 4: DAILY PERFORMANCE ANALYSIS")
        print(f"{'='*60}")

        try:
            daily = DailySessionAnalyzer(self.date_str)
            daily.analyze()
            daily.save_report()
            self.daily_analysis = daily.metrics
            self._analyze_daily_performance()
        except Exception as e:
            print(f"⚠️  Daily analysis failed: {e}")

        # Generate consolidated insights
        self._generate_consolidated_insights()

        # Print executive summary
        self._print_executive_summary()

        # Save complete report
        self.save_report()

    def _analyze_market_validation(self):
        """Extract insights from market validation"""
        if not self.market_validation:
            return

        # Count true vs false breakouts
        true_breakouts = 0
        false_breakouts = 0

        for symbol, analysis in self.market_validation.items():
            true_breakouts += len(analysis.get('breakouts', []))
            false_breakouts += len(analysis.get('false_breakouts', []))

        if true_breakouts + false_breakouts > 0:
            success_rate = (true_breakouts / (true_breakouts + false_breakouts)) * 100

            if success_rate > 60:
                self.insights['successes'].append(
                    f"Scanner breakout predictions {success_rate:.0f}% accurate"
                )
            else:
                self.insights['failures'].append(
                    f"Scanner breakout accuracy only {success_rate:.0f}%"
                )
                self.insights['recommendations'].append(
                    "Review scanner pivot detection logic"
                )

    def _analyze_backtest_comparison(self):
        """Extract insights from backtest comparison"""
        if not self.backtest_comparison:
            return

        bt_trades = len(self.backtest_comparison.backtest_trades)
        live_trades = len(self.backtest_comparison.live_trades)

        # Compare trade counts
        if abs(bt_trades - live_trades) > 3:
            if bt_trades > live_trades:
                self.insights['failures'].append(
                    f"Live system took {live_trades} trades vs backtest {bt_trades}"
                )
                self.insights['recommendations'].append(
                    "Check for over-filtering or connection issues in live"
                )
            else:
                self.insights['successes'].append(
                    f"Live system more selective ({live_trades} vs {bt_trades} backtest)"
                )

        # Compare P&L
        if self.backtest_comparison.backtest_trades:
            bt_pnl = sum(t['pnl'] for t in self.backtest_comparison.backtest_trades)
        else:
            bt_pnl = 0

        if self.backtest_comparison.live_trades:
            live_pnl = sum(t['pnl'] for t in self.backtest_comparison.live_trades)
        else:
            live_pnl = 0

        if abs(bt_pnl - live_pnl) > 500:
            if live_pnl > bt_pnl:
                self.insights['successes'].append(
                    f"Live outperformed backtest by ${live_pnl - bt_pnl:.0f}"
                )
            else:
                self.insights['failures'].append(
                    f"Backtest outperformed live by ${bt_pnl - live_pnl:.0f}"
                )
                self.insights['recommendations'].append(
                    "Review execution quality and slippage"
                )

    def _analyze_session_walkthrough(self):
        """Extract insights from session walkthrough"""
        if not self.session_walkthrough:
            return

        # Analyze filter blocks
        total_blocks = sum(len(blocks) for blocks in self.session_walkthrough.filter_blocks.values())
        total_trades = len(self.session_walkthrough.trades)

        if total_blocks > total_trades * 5:
            self.insights['failures'].append(
                f"Excessive filtering: {total_blocks} blocks vs {total_trades} trades"
            )
            self.insights['action_items'].append(
                "URGENT: Review and relax filter thresholds"
            )

        # Check for position sizing issues
        position_blocks = 0
        for blocks in self.session_walkthrough.filter_blocks.values():
            for block in blocks:
                if 'Position too large' in block.get('reason', ''):
                    position_blocks += 1

        if position_blocks > 5:
            self.insights['failures'].append(
                f"{position_blocks} trades blocked by position sizing"
            )
            self.insights['action_items'].append(
                "URGENT: Implement adaptive position sizing"
            )

    def _analyze_daily_performance(self):
        """Extract insights from daily performance"""
        if not self.daily_analysis:
            return

        # Check P&L
        daily_pnl = self.daily_analysis.get('daily_pnl', 0)
        if daily_pnl > 1000:
            self.insights['successes'].append(
                f"Achieved target P&L: ${daily_pnl:.2f}"
            )
        elif daily_pnl > 0:
            self.insights['successes'].append(
                f"Profitable session: ${daily_pnl:.2f}"
            )
        else:
            self.insights['failures'].append(
                f"Losing session: ${daily_pnl:.2f}"
            )

        # Check win rate
        win_rate = self.daily_analysis.get('win_rate', 0)
        if win_rate < 30:
            self.insights['failures'].append(
                f"Low win rate: {win_rate:.1f}%"
            )
            self.insights['recommendations'].append(
                "Review entry criteria - may be too loose"
            )
        elif win_rate > 60:
            self.insights['successes'].append(
                f"High win rate: {win_rate:.1f}%"
            )

    def _generate_consolidated_insights(self):
        """Generate consolidated insights from all analyses"""
        # Check for consistent patterns
        if len(self.insights['failures']) > len(self.insights['successes']) * 2:
            self.insights['action_items'].append(
                "CRITICAL: Multiple issues detected - comprehensive review needed"
            )

        # Prioritize action items
        if self.insights['action_items']:
            self.insights['action_items'] = sorted(
                set(self.insights['action_items']),
                key=lambda x: 'URGENT' in x,
                reverse=True
            )

    def _print_executive_summary(self):
        """Print executive summary of findings"""
        print(f"\n{'='*80}")
        print("EXECUTIVE SUMMARY")
        print(f"{'='*80}")

        # Performance
        if self.daily_analysis:
            pnl = self.daily_analysis.get('daily_pnl', 0)
            trades = self.daily_analysis.get('total_trades', 0)
            win_rate = self.daily_analysis.get('win_rate', 0)

            print(f"\n📊 Performance:")
            print(f"  P&L: ${pnl:.2f}")
            print(f"  Trades: {trades}")
            print(f"  Win Rate: {win_rate:.1f}%")

        # Key Successes
        if self.insights['successes']:
            print(f"\n✅ Key Successes:")
            for success in self.insights['successes'][:3]:
                print(f"  • {success}")

        # Key Failures
        if self.insights['failures']:
            print(f"\n❌ Key Failures:")
            for failure in self.insights['failures'][:3]:
                print(f"  • {failure}")

        # Recommendations
        if self.insights['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in self.insights['recommendations'][:3]:
                print(f"  • {rec}")

        # Action Items
        if self.insights['action_items']:
            print(f"\n⚠️  ACTION ITEMS:")
            for action in self.insights['action_items']:
                print(f"  → {action}")

        # Overall Assessment
        print(f"\n📈 Overall Assessment:")
        if self.daily_analysis:
            pnl = self.daily_analysis.get('daily_pnl', 0)
            if pnl > 1500:
                print("  ✅ EXCELLENT session - strategy working well")
            elif pnl > 500:
                print("  ✓ GOOD session - minor improvements needed")
            elif pnl > 0:
                print("  → ACCEPTABLE session - room for improvement")
            else:
                print("  ⚠️  POOR session - immediate review required")

    def save_report(self):
        """Save complete EOD report"""
        report = {
            'date': self.date_str,
            'timestamp': datetime.now().isoformat(),
            'insights': self.insights,
            'daily_metrics': self.daily_analysis,
            'backtest_comparison': {
                'backtest_trades': len(self.backtest_comparison.backtest_trades) if self.backtest_comparison else 0,
                'live_trades': len(self.backtest_comparison.live_trades) if self.backtest_comparison else 0
            }
        }

        output_file = Path(f'logs/eod_report_{self.date_str}.json')
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n📄 Complete EOD report saved to: {output_file}")
        return output_file


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python eod_report.py YYYYMMDD [--skip-ib]")
        print("Example: python eod_report.py 20251007")
        print("         python eod_report.py 20251007 --skip-ib")
        sys.exit(1)

    date_str = sys.argv[1]
    skip_ib = '--skip-ib' in sys.argv

    # Validate date format
    try:
        datetime.strptime(date_str, '%Y%m%d')
    except ValueError:
        print(f"⚠️  Invalid date format: {date_str}")
        print("   Expected: YYYYMMDD")
        sys.exit(1)

    # Generate report
    reporter = EODReport(date_str, skip_ib=skip_ib)
    reporter.generate_full_report()


if __name__ == '__main__':
    main()