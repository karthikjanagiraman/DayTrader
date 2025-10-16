#!/usr/bin/env python3
"""Test backtester initialization"""

from datetime import datetime
import sys
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))

print("1. Imports complete")

print("2. Creating backtester instance...")
from backtester import PS60Backtester

print("3. Setting parameters...")
scanner_file = "../../stockscanner/output/scanner_results_20250915.json"
test_date = datetime.strptime("2025-09-15", '%Y-%m-%d')
account_size = 50000

print("4. Calling PS60Backtester() constructor...")
try:
    backtester = PS60Backtester(scanner_file, test_date, account_size)
    print("   ✓ Backtester initialized successfully!")
    print(f"   Scanner results loaded: {len(backtester.scanner_results)} stocks")
except Exception as e:
    print(f"   ✗ Error during initialization: {e}")
    import traceback
    traceback.print_exc()

print("\n✅ Test complete")
