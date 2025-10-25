#!/bin/bash
# Batch download tick data for multiple dates (SEQUENTIAL)

DATES="2025-10-15 2025-10-16 2025-10-20 2025-10-22"
BASE_DIR="/Users/karthik/projects/DayTrader"
SCANNER_DIR="$BASE_DIR/stockscanner/output"

echo "========================================"
echo "BATCH TICK DATA DOWNLOAD (SEQUENTIAL)"
echo "========================================"
echo ""

count=0
total=$(echo $DATES | wc -w | tr -d ' ')

for date in $DATES; do
    count=$((count + 1))
    date_str=$(echo $date | tr -d '-')
    scanner_file="$SCANNER_DIR/scanner_results_${date_str}.json"
    
    echo "[$count/$total] Downloading $date..."
    echo "Scanner: $scanner_file"
    echo ""
    
    if [ ! -f "$scanner_file" ]; then
        echo "✗ Scanner file not found: $scanner_file"
        echo "Skipping..."
        echo ""
        continue
    fi
    
    python3 download_tick_data.py \
        --date $date \
        --scanner $scanner_file \
        > /tmp/download_${date_str}.log 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ $date complete!"
    else
        echo "❌ $date failed! Check /tmp/download_${date_str}.log"
    fi
    echo ""
    
    # Small delay between downloads
    sleep 2
done

echo "========================================"
echo "BATCH DOWNLOAD COMPLETE"
echo "========================================"
