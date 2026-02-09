#!/bin/bash
# GDELT Database Recovery Script

echo "=== GDELT Database Recovery ==="
echo ""

# Stop collector
echo "1. Stopping GDELT collector..."
pkill -f "gdelt_collector.py"
sleep 2

# Run recovery
echo ""
echo "2. Running recovery script..."
python3 recover_gdelt_db.py

# Check if recovery succeeded
if [ $? -eq 0 ]; then
    echo ""
    echo "3. Restarting collector with fixed code..."
    nohup python3 gdelt_collector.py --continuous >> gdelt.out 2>&1 &
    echo ""
    echo "✓ Recovery complete! Collector restarted."
    echo ""
    echo "Monitor logs with:"
    echo "  tail -f gdelt.out"
else
    echo ""
    echo "✗ Recovery failed. See recover_gdelt_db.py output above."
fi
