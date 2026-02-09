#!/bin/bash
# Check for duplicate or zombie processes

echo "=== Process Health Check ==="
echo ""

# Check for duplicates
for proc in "trader.py" "trader_price_levels.py" "gdelt_collector.py" "alchemy_collector.py"; do
    count=$(pgrep -f "$proc" | wc -l)
    if [ $count -gt 1 ]; then
        echo "⚠️  WARNING: $count instances of $proc running (should be 1)"
        ps aux | grep "$proc" | grep -v grep
    elif [ $count -eq 1 ]; then
        echo "✓ $proc: 1 instance running"
    else
        echo "✗ $proc: not running"
    fi
done

echo ""
echo "=== High CPU Processes ==="
ps aux | awk '$3 > 50.0 {print $3"% "$11}' | grep -E "trader|collector" || echo "None"

echo ""
echo "=== Recent Log Activity ==="
for log in trading.out trading_price_levels.out gdelt_collection.out alchemy_collection.out; do
    if [ -f "$log" ]; then
        last_line=$(tail -1 "$log" 2>/dev/null)
        echo "$log: $last_line"
    fi
done
