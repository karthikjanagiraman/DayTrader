#!/bin/bash
# Comprehensive backtest: Sep 15 - Oct 13, 2025

echo "=========================================="
echo "COMPREHENSIVE BACKTEST: Sep 15 - Oct 13"
echo "=========================================="
echo ""

DATES=(
  2025-09-15 2025-09-16 2025-09-17 2025-09-18 2025-09-19
  2025-09-22 2025-09-23 2025-09-24 2025-09-25 2025-09-26
  2025-10-01 2025-10-02 2025-10-03 2025-10-06 2025-10-07
  2025-10-08 2025-10-09 2025-10-10 2025-10-13
)

TOTAL_PNL=0
TOTAL_TRADES=0
WINNING_DAYS=0
LOSING_DAYS=0

for DATE in "${DATES[@]}"; do
  SCANNER_FILE="../../stockscanner/output/scanner_results_${DATE//-/}.json"
  
  if [ -f "$SCANNER_FILE" ]; then
    echo "Running backtest for $DATE..."
    python3 backtester.py \
      --date $DATE \
      --scanner $SCANNER_FILE \
      --account-size 100000 \
      > /tmp/backtest_${DATE}.log 2>&1
    
    # Extract P&L from log (if available)
    if grep -q "Daily P&L" /tmp/backtest_${DATE}.log; then
      DAILY_PNL=$(grep "Daily P&L" /tmp/backtest_${DATE}.log | awk '{print $NF}' | tr -d '$,')
      echo "  -> P&L: \$$DAILY_PNL"
    fi
  else
    echo "Skipping $DATE (scanner file not found)"
  fi
done

echo ""
echo "=========================================="
echo "Backtest complete! Check /tmp/backtest_*.log for details"
echo "=========================================="
