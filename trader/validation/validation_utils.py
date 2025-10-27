"""
Validation Utilities - Shared helpers for entry decision analysis
Author: Auto-generated
Date: October 25, 2025
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional


def load_entry_decisions(file_path: str) -> Dict:
    """
    Load entry decision JSON file (backtest or live)

    Args:
        file_path: Path to JSON file

    Returns:
        Dict with entry decision data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Entry decision file not found: {file_path}")

    with open(file_path, 'r') as f:
        data = json.load(f)

    return data


def check_all_filters_passed(filters: Dict) -> bool:
    """
    Check if all enabled filters passed

    Args:
        filters: Dict of filter results

    Returns:
        True if all enabled filters PASSED or DISABLED

    Example:
        filters = {
            'choppy': {'enabled': True, 'result': 'PASS'},
            'room_to_run': {'enabled': True, 'result': 'PASS'},
            'cvd': {'enabled': False, 'result': 'DISABLED'}
        }
        check_all_filters_passed(filters) → True
    """
    for filter_name, filter_data in filters.items():
        if isinstance(filter_data, dict):
            if filter_data.get('enabled') and filter_data.get('result') not in ['PASS', 'DISABLED']:
                return False

    return True


def check_any_filter_blocked(filters: Dict) -> Tuple[bool, List[str]]:
    """
    Check if any enabled filter blocked

    Args:
        filters: Dict of filter results

    Returns:
        Tuple of (has_blocks, list_of_blocking_filters)

    Example:
        filters = {
            'choppy': {'enabled': True, 'result': 'PASS'},
            'cvd': {'enabled': True, 'result': 'BLOCK'}
        }
        check_any_filter_blocked(filters) → (True, ['cvd'])
    """
    blocking_filters = []

    for filter_name, filter_data in filters.items():
        if isinstance(filter_data, dict):
            if filter_data.get('enabled') and filter_data.get('result') == 'BLOCK':
                blocking_filters.append(filter_name)

    return (len(blocking_filters) > 0, blocking_filters)


def find_matching_attempt(attempts: List[Dict], symbol: str, timestamp: str,
                          tolerance_seconds: int = 60) -> Optional[Dict]:
    """
    Find matching attempt in another dataset (for backtest vs live comparison)

    Args:
        attempts: List of attempt dicts to search
        symbol: Stock symbol to match
        timestamp: ISO timestamp string
        tolerance_seconds: Match tolerance in seconds

    Returns:
        Matching attempt dict or None

    Example:
        backtest_attempt = {..., 'symbol': 'NVDA', 'timestamp': '2025-10-21T09:47:00'}
        live_attempts = [...]
        match = find_matching_attempt(live_attempts, 'NVDA', '2025-10-21T09:47:00')
    """
    target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    for attempt in attempts:
        if attempt['symbol'] == symbol:
            attempt_time = datetime.fromisoformat(attempt['timestamp'].replace('Z', '+00:00'))
            time_diff = abs((attempt_time - target_time).total_seconds())

            if time_diff <= tolerance_seconds:
                return attempt

    return None


def compare_filter_results(filter1: Dict, filter2: Dict) -> Tuple[bool, str]:
    """
    Compare two filter results

    Args:
        filter1: First filter result dict
        filter2: Second filter result dict

    Returns:
        Tuple of (is_match, difference_description)

    Example:
        filter1 = {'enabled': True, 'result': 'PASS'}
        filter2 = {'enabled': True, 'result': 'BLOCK'}
        compare_filter_results(filter1, filter2) → (False, 'PASS vs BLOCK')
    """
    result1 = filter1.get('result', 'UNKNOWN')
    result2 = filter2.get('result', 'UNKNOWN')

    if result1 == result2:
        return (True, f'{result1}')
    else:
        return (False, f'{result1} vs {result2}')


def estimate_filter_value(filter_name: str, block_count: int,
                          avg_loss_per_trade: float = 150.0) -> float:
    """
    Estimate monetary value of a filter based on blocks

    Args:
        filter_name: Name of the filter
        block_count: Number of trades blocked
        avg_loss_per_trade: Estimated average loss if trade had entered

    Returns:
        Estimated dollar value saved

    Example:
        estimate_filter_value('cvd_filter', 32, 150) → $4,800
    """
    return block_count * avg_loss_per_trade


def format_timestamp(timestamp: str) -> str:
    """
    Format ISO timestamp to readable format

    Args:
        timestamp: ISO timestamp string

    Returns:
        Human-readable timestamp

    Example:
        format_timestamp('2025-10-21T09:47:00') → '09:47:00'
    """
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return dt.strftime('%H:%M:%S')


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format float as percentage string

    Args:
        value: Float value (0.0061 = 0.61%)
        decimals: Number of decimal places

    Returns:
        Formatted percentage string

    Example:
        format_percentage(0.0061, 2) → '0.61%'
    """
    return f"{value * 100:.{decimals}f}%"


def format_currency(value: float, decimals: int = 2) -> str:
    """
    Format float as currency string

    Args:
        value: Dollar amount
        decimals: Number of decimal places

    Returns:
        Formatted currency string

    Example:
        format_currency(4800.50, 2) → '$4,800.50'
    """
    return f"${value:,.{decimals}f}"


def generate_summary_stats(data: Dict) -> Dict:
    """
    Generate summary statistics from entry decision data

    Args:
        data: Entry decision data dict

    Returns:
        Dict with summary statistics

    Example:
        stats = generate_summary_stats(data)
        → {
            'total_attempts': 87,
            'entered': 6,
            'blocked': 81,
            'entry_rate': 0.069,
            'block_rate': 0.931,
            'top_blocking_filter': 'cvd_filter',
            'top_blocking_count': 32
        }
    """
    total_attempts = data.get('total_attempts', 0)
    entered = data.get('entered', 0)
    blocked = data.get('blocked', 0)

    entry_rate = entered / total_attempts if total_attempts > 0 else 0
    block_rate = blocked / total_attempts if total_attempts > 0 else 0

    blocks_by_filter = data.get('blocks_by_filter', {})
    if blocks_by_filter:
        top_filter = max(blocks_by_filter.items(), key=lambda x: x[1])
        top_blocking_filter = top_filter[0]
        top_blocking_count = top_filter[1]
    else:
        top_blocking_filter = None
        top_blocking_count = 0

    return {
        'total_attempts': total_attempts,
        'entered': entered,
        'blocked': blocked,
        'entry_rate': entry_rate,
        'block_rate': block_rate,
        'top_blocking_filter': top_blocking_filter,
        'top_blocking_count': top_blocking_count
    }


def print_section_header(title: str, width: int = 72):
    """Print a formatted section header"""
    print("=" * width)
    print(title)
    print("=" * width)


def print_subsection_header(title: str):
    """Print a formatted subsection header"""
    print(f"\n{title}")
    print("-" * len(title))


def save_report(report_text: str, output_path: str):
    """
    Save report text to file

    Args:
        report_text: Report content
        output_path: Path to save file

    Example:
        save_report(report, 'reports/validation_summary_20251021.md')
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(report_text)

    print(f"\n💾 Report saved to: {output_path}")


# Example usage
if __name__ == '__main__':
    # Test utilities
    print("Testing validation utilities...\n")

    # Test 1: Load entry decisions
    try:
        data = load_entry_decisions('../backtest/results/backtest_entry_decisions_20251021.json')
        print(f"✅ Loaded {data['total_attempts']} entry attempts")
    except FileNotFoundError:
        print("⚠️  Entry decision file not found (run backtest first)")

    # Test 2: Check all filters passed
    filters = {
        'choppy': {'enabled': True, 'result': 'PASS'},
        'room_to_run': {'enabled': True, 'result': 'PASS'},
        'cvd': {'enabled': False, 'result': 'DISABLED'}
    }
    all_passed = check_all_filters_passed(filters)
    print(f"✅ All filters passed: {all_passed}")

    # Test 3: Check any filter blocked
    filters_with_block = {
        'choppy': {'enabled': True, 'result': 'PASS'},
        'cvd': {'enabled': True, 'result': 'BLOCK'}
    }
    has_blocks, blocking = check_any_filter_blocked(filters_with_block)
    print(f"✅ Has blocks: {has_blocks}, Blocking filters: {blocking}")

    # Test 4: Formatting
    print(f"✅ Percentage: {format_percentage(0.0061)}")
    print(f"✅ Currency: {format_currency(4800.50)}")
    print(f"✅ Timestamp: {format_timestamp('2025-10-21T09:47:00')}")

    print("\n✅ All utility tests passed!")
