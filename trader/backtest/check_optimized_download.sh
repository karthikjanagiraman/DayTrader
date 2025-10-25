#!/bin/bash
# Quick progress check for OPTIMIZED tick data download

echo "========================================"
echo "OPTIMIZED TICK DATA DOWNLOAD PROGRESS"
echo "========================================"
echo ""

# Check if download process is running
if ps -p 22834 > /dev/null 2>&1; then
    echo "✅ Download RUNNING (PID 22834)"
else
    echo "⚠️  Download NOT RUNNING"
fi

echo ""
echo "📊 Progress by symbol:"

# Count files per symbol
for symbol in $(ls data/ticks/*.json 2>/dev/null | xargs -n1 basename | cut -d'_' -f1 | sort -u); do
    count=$(ls data/ticks/${symbol}_*.json 2>/dev/null | wc -l | tr -d ' ')
    pct=$(echo "scale=1; $count * 100 / 390" | bc)
    echo "  $symbol: $count / 390 min ($pct%)"
done

# Total
total=$(ls data/ticks/*.json 2>/dev/null | wc -l | tr -d ' ')
expected=3510
percent=$(echo "scale=1; $total * 100 / $expected" | bc)

echo ""
echo "📈 Total: $total / $expected files ($percent%)"
echo ""
echo "⚡ OPTIMIZATION: 92% fewer requests (3,510 vs 42,120)"
echo "========================================"
