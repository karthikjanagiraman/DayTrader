#!/bin/bash
# Quick progress check for overnight tick data download

echo "=================================="
echo "TICK DATA DOWNLOAD PROGRESS CHECK"
echo "=================================="
echo ""

# Check if download process is still running
if ps -p 11996 > /dev/null 2>&1; then
    echo "✅ Download process RUNNING (PID 11996)"
    ps -p 11996 -o pid,etime,rss,command | tail -1
    echo ""
else
    echo "⚠️  Download process NOT RUNNING"
    echo "   Check if it completed or crashed"
    echo ""
fi

# Count files per symbol
echo "Files downloaded per symbol:"
for symbol in $(ls backtest/data/ticks/*.json 2>/dev/null | cut -d'_' -f1 | sed 's|.*/||' | sort -u); do
    count=$(ls backtest/data/ticks/${symbol}_*.json 2>/dev/null | wc -l | tr -d ' ')
    echo "  $symbol: $count files"
done

# Total count
total=$(ls backtest/data/ticks/*.json 2>/dev/null | wc -l | tr -d ' ')
echo ""
echo "TOTAL: $total files"

# Expected: 9 symbols × 390 minutes × 12 five-sec intervals = ~42,120 files
expected=42120
percent=$((total * 100 / expected))
echo "Progress: $percent% complete ($total/$expected)"

# Estimate time remaining (rough)
if [ $total -gt 0 ]; then
    # Assume ~30 files/min download rate
    remaining=$((expected - total))
    eta_min=$((remaining / 30))
    eta_hours=$((eta_min / 60))
    eta_min_rem=$((eta_min % 60))
    echo "Estimated time remaining: ${eta_hours}h ${eta_min_rem}m"
fi

echo ""
echo "=================================="
