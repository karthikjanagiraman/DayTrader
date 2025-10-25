#!/bin/bash
# Check progress of batch tick data downloads

echo "=========================================="
echo "BATCH DOWNLOAD PROGRESS"
echo "=========================================="
echo ""

# Check which downloads are complete
for date in 20251015 20251016 202510 20 20251021 20251022; do
    dir_count=$(ls -1 data/ticks/*_${date}_*.json 2>/dev/null | wc -l | tr -d ' ')
    
    if [ "$dir_count" -gt 0 ]; then
        symbol_count=$(ls -1 data/ticks/*_${date}_*.json 2>/dev/null | xargs -n1 basename | cut -d'_' -f1 | sort -u | wc -l | tr -d ' ')
        echo "✅ $date: $dir_count files ($symbol_count symbols)"
    else
        echo "⏳ $date: Not started or in progress"
    fi
done

echo ""
echo "📊 Total tick files: $(ls -1 data/ticks/*.json 2>/dev/null | wc -l | tr -d ' ')"
echo "=========================================="
