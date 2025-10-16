#!/usr/bin/env python3
"""Test which import is causing the hang"""

print("1. Starting imports...")

print("2. Importing ib_insync...")
from ib_insync import IB, Stock
print("   ✓ ib_insync imported")

print("3. Importing datetime...")
from datetime import datetime, timedelta
print("   ✓ datetime imported")

print("4. Importing json...")
import json
print("   ✓ json imported")

print("5. Importing pandas...")
import pandas as pd
print("   ✓ pandas imported")

print("6. Importing sys and Path...")
import sys
from pathlib import Path
print("   ✓ sys and Path imported")

print("7. Importing yaml...")
import yaml
print("   ✓ yaml imported")

print("8. Importing pytz...")
import pytz
print("   ✓ pytz imported")

print("9. Importing logging...")
import logging
print("   ✓ logging imported")

print("10. Adding parent to sys.path...")
sys.path.append(str(Path(__file__).parent.parent))
print("    ✓ sys.path modified")

print("11. Importing strategy module...")
from strategy import PS60Strategy, PositionManager
print("    ✓ strategy module imported")

print("\n✅ ALL IMPORTS SUCCESSFUL!")
