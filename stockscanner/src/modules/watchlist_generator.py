"""
Watchlist Generator Module
Generates output files in multiple formats (CSV, JSON, Markdown)
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import pandas as pd
from loguru import logger


class WatchlistGenerator:
    """Generate watchlist outputs in various formats"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize output generator

        Args:
            config: Configuration dictionary with output settings
        """
        self.config = config
        self.output_config = config.get('output', {})

        # Ensure output directory exists
        for path_key in ['watchlist_path', 'research_log', 'json_output']:
            path = self.output_config.get(path_key, '')
            if path:
                Path(path).parent.mkdir(parents=True, exist_ok=True)

    def generate_csv_watchlist(self, results: Dict[str, Any]) -> str:
        """
        Generate CSV watchlist file

        Args:
            results: Scan results dictionary

        Returns:
            Path to generated CSV file
        """
        csv_path = self.output_config.get('watchlist_path', './output/watchlist.csv')

        try:
            with open(csv_path, 'w', newline='') as csvfile:
                fieldnames = [
                    'Symbol', 'Direction', 'Current Price', 'Gap %', 'RVOL',
                    'Pivot High', 'Pivot Low', 'Entry', 'Stop', 'Target',
                    'R:R Ratio', 'Score', 'Rationale'
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                # Write long candidates
                for candidate in results.get('long_candidates', []):
                    writer.writerow({
                        'Symbol': candidate['symbol'],
                        'Direction': 'LONG',
                        'Current Price': f"{candidate['current_price']:.2f}",
                        'Gap %': f"{candidate['gap_pct']:.2f}",
                        'RVOL': f"{candidate['rvol']:.2f}",
                        'Pivot High': f"{candidate['pivot_high']:.2f}",
                        'Pivot Low': f"{candidate['pivot_low']:.2f}",
                        'Entry': f"{candidate['entry']:.2f}",
                        'Stop': f"{candidate['stop']:.2f}",
                        'Target': f"{candidate['target']:.2f}",
                        'R:R Ratio': f"{candidate['rr_ratio']:.2f}",
                        'Score': f"{candidate['score']:.1f}",
                        'Rationale': candidate['rationale']
                    })

                # Write short candidates
                for candidate in results.get('short_candidates', []):
                    writer.writerow({
                        'Symbol': candidate['symbol'],
                        'Direction': 'SHORT',
                        'Current Price': f"{candidate['current_price']:.2f}",
                        'Gap %': f"{candidate['gap_pct']:.2f}",
                        'RVOL': f"{candidate['rvol']:.2f}",
                        'Pivot High': f"{candidate['pivot_high']:.2f}",
                        'Pivot Low': f"{candidate['pivot_low']:.2f}",
                        'Entry': f"{candidate['entry']:.2f}",
                        'Stop': f"{candidate['stop']:.2f}",
                        'Target': f"{candidate['target']:.2f}",
                        'R:R Ratio': f"{candidate['rr_ratio']:.2f}",
                        'Score': f"{candidate['score']:.1f}",
                        'Rationale': candidate['rationale']
                    })

            logger.info(f"CSV watchlist saved to {csv_path}")
            return csv_path

        except Exception as e:
            logger.error(f"Error generating CSV: {e}")
            return ""

    def generate_json_output(self, results: Dict[str, Any]) -> str:
        """
        Generate JSON output file

        Args:
            results: Scan results dictionary

        Returns:
            Path to generated JSON file
        """
        json_path = self.output_config.get('json_output', './output/scan_results.json')

        try:
            # Convert datetime objects to strings
            output_data = {
                'scan_date': str(results.get('scan_date', '')),
                'timestamp': str(results.get('timestamp', '')),
                'market_context': {
                    'bias': results['market_context']['bias'],
                    'volatility': results['market_context']['volatility'],
                    'summary': results['market_context']['summary']
                },
                'long_candidates': results.get('long_candidates', []),
                'short_candidates': results.get('short_candidates', []),
                'statistics': {
                    'total_scanned': results.get('total_scanned', 0),
                    'long_count': len(results.get('long_candidates', [])),
                    'short_count': len(results.get('short_candidates', [])),
                    'failed_symbols': results.get('failed_symbols', [])
                }
            }

            with open(json_path, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)

            logger.info(f"JSON output saved to {json_path}")
            return json_path

        except Exception as e:
            logger.error(f"Error generating JSON: {e}")
            return ""

    def generate_markdown_research_log(self, results: Dict[str, Any]) -> str:
        """
        Generate detailed Markdown research log

        Args:
            results: Scan results dictionary

        Returns:
            Path to generated Markdown file
        """
        md_path = self.output_config.get('research_log', './output/research.md')

        try:
            with open(md_path, 'w') as f:
                # Header
                f.write("# PS60 Pre-Market Scanner Research Log\n\n")
                f.write(f"**Scan Date:** {results.get('scan_date', 'N/A')}\n")
                f.write(f"**Generated:** {results.get('timestamp', datetime.now())}\n")
                f.write(f"**Total Symbols Scanned:** {results.get('total_scanned', 0)}\n\n")

                # Market Context
                f.write("## Market Context\n\n")
                context = results.get('market_context', {})
                f.write(f"- **Bias:** {context.get('bias', 'neutral').upper()}\n")
                f.write(f"- **Volatility:** {context.get('volatility', 'normal')}\n")
                f.write(f"- **Summary:** {context.get('summary', 'No summary available')}\n\n")

                # Long Candidates
                f.write(f"## Long Candidates ({len(results.get('long_candidates', []))})\n\n")

                for i, candidate in enumerate(results.get('long_candidates', []), 1):
                    f.write(f"### {i}. {candidate['symbol']}\n\n")
                    f.write(f"- **Current Price:** ${candidate['current_price']:.2f}\n")
                    f.write(f"- **Gap:** {candidate['gap_pct']:+.2f}%\n")
                    f.write(f"- **RVOL:** {candidate['rvol']:.2f}x\n")
                    f.write(f"- **Pivot High:** ${candidate['pivot_high']:.2f} (entry trigger)\n")
                    f.write(f"- **Entry:** ${candidate['entry']:.2f}\n")
                    f.write(f"- **Stop:** ${candidate['stop']:.2f}\n")
                    f.write(f"- **Target:** ${candidate['target']:.2f}\n")
                    f.write(f"- **Risk/Reward:** {candidate['rr_ratio']:.2f}:1\n")
                    f.write(f"- **Score:** {candidate['score']:.1f}/100\n")
                    f.write(f"- **Rationale:** {candidate['rationale']}\n")

                    # Pattern details if available
                    if 'patterns' in candidate:
                        patterns = candidate['patterns']
                        if patterns.get('pattern_description'):
                            f.write(f"- **Pattern:** {patterns['pattern_description']}\n")

                    # Room analysis
                    if 'room_analysis' in candidate:
                        room = candidate['room_analysis']
                        if room.get('next_level'):
                            f.write(f"- **Next Resistance:** ${room['next_level']:.2f} ")
                            f.write(f"({room.get('obstacle', 'resistance')} - ")
                            f.write(f"{room.get('distance_pct', 0):.1f}% away)\n")

                    f.write("\n")

                # Short Candidates
                f.write(f"## Short Candidates ({len(results.get('short_candidates', []))})\n\n")

                for i, candidate in enumerate(results.get('short_candidates', []), 1):
                    f.write(f"### {i}. {candidate['symbol']}\n\n")
                    f.write(f"- **Current Price:** ${candidate['current_price']:.2f}\n")
                    f.write(f"- **Gap:** {candidate['gap_pct']:+.2f}%\n")
                    f.write(f"- **RVOL:** {candidate['rvol']:.2f}x\n")
                    f.write(f"- **Pivot Low:** ${candidate['pivot_low']:.2f} (entry trigger)\n")
                    f.write(f"- **Entry:** ${candidate['entry']:.2f}\n")
                    f.write(f"- **Stop:** ${candidate['stop']:.2f}\n")
                    f.write(f"- **Target:** ${candidate['target']:.2f}\n")
                    f.write(f"- **Risk/Reward:** {candidate['rr_ratio']:.2f}:1\n")
                    f.write(f"- **Score:** {candidate['score']:.1f}/100\n")
                    f.write(f"- **Rationale:** {candidate['rationale']}\n")

                    # Pattern details if available
                    if 'patterns' in candidate:
                        patterns = candidate['patterns']
                        if patterns.get('pattern_description'):
                            f.write(f"- **Pattern:** {patterns['pattern_description']}\n")

                    # Room analysis
                    if 'room_analysis' in candidate:
                        room = candidate['room_analysis']
                        if room.get('next_level'):
                            f.write(f"- **Next Support:** ${room['next_level']:.2f} ")
                            f.write(f"({room.get('obstacle', 'support')} - ")
                            f.write(f"{room.get('distance_pct', 0):.1f}% away)\n")

                    f.write("\n")

                # PS60 Trading Rules Reminder
                f.write("## PS60 Trading Rules Reminder\n\n")
                f.write("### Entry Rules:\n")
                f.write("- **Long:** Price breaks above pivot high with 60-min candle confirmation\n")
                f.write("- **Short:** Price breaks below pivot low with 60-min candle confirmation\n")
                f.write("- **Critical Time:** 10:00 AM for next candle confirmation\n\n")

                f.write("### Risk Management:\n")
                f.write("- Use 5-7 minute time stops if stuck at resistance\n")
                f.write("- Don't chase pivots moved >$0.16 from entry\n")
                f.write("- Consider overall market environment\n")
                f.write("- Maintain minimum 1:1 risk/reward ratio\n\n")

                # Failed Symbols
                if results.get('failed_symbols'):
                    f.write("## Failed to Process\n\n")
                    f.write(f"The following symbols could not be processed: ")
                    f.write(", ".join(results['failed_symbols']))
                    f.write("\n\n")

                # Footer
                f.write("---\n")
                f.write("*Generated by PS60 Pre-Market Scanner*\n")

            logger.info(f"Markdown research log saved to {md_path}")
            return md_path

        except Exception as e:
            logger.error(f"Error generating Markdown: {e}")
            return ""

    def generate_all_outputs(self, results: Dict[str, Any]):
        """
        Generate all configured output formats

        Args:
            results: Scan results dictionary
        """
        formats = self.output_config.get('formats', ['csv', 'json', 'markdown'])

        generated = []

        if 'csv' in formats:
            csv_path = self.generate_csv_watchlist(results)
            if csv_path:
                generated.append(csv_path)

        if 'json' in formats:
            json_path = self.generate_json_output(results)
            if json_path:
                generated.append(json_path)

        if 'markdown' in formats:
            md_path = self.generate_markdown_research_log(results)
            if md_path:
                generated.append(md_path)

        logger.info(f"Generated {len(generated)} output files")

    def create_summary_dataframe(self, results: Dict[str, Any]) -> pd.DataFrame:
        """
        Create a summary DataFrame for further analysis

        Args:
            results: Scan results dictionary

        Returns:
            DataFrame with all candidates
        """
        all_candidates = []

        # Add long candidates
        for candidate in results.get('long_candidates', []):
            candidate['direction'] = 'LONG'
            all_candidates.append(candidate)

        # Add short candidates
        for candidate in results.get('short_candidates', []):
            candidate['direction'] = 'SHORT'
            all_candidates.append(candidate)

        if all_candidates:
            df = pd.DataFrame(all_candidates)
            # Sort by score
            df = df.sort_values('score', ascending=False)
            return df

        return pd.DataFrame()  # Empty DataFrame if no candidates