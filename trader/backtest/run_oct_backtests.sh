#!/bin/bash
# Run backtests for Oct 6-9 with 7-minute rule

for date in 20251006 20251007 20251008 20251009; do
    year=${date:0:4}
    month=${date:4:2}
    day=${date:6:2}
    formatted_date="$year-$month-$day"
    
    echo "============================================="
    echo "Running backtest for $formatted_date"
    echo "============================================="
    
    python3 backtester.py \
        --date $formatted_date \
        --scanner ../../stockscanner/output/scanner_results_$date.json \
        --account-size 100000 2>&1 | grep -A100 "BACKTEST RESULTS"
    
    echo ""
    echo "Completed $formatted_date"
    echo ""
    sleep 2
done

echo "============================================="
echo "ALL BACKTESTS COMPLETED"
echo "============================================="
