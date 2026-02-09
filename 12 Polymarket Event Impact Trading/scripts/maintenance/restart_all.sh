#!/bin/bash
# Safe process restart - prevents duplicates

# Function to start process only if not already running
start_if_not_running() {
    local script=$1
    local args=$2
    local logfile=$3

    if pgrep -f "$script" > /dev/null; then
        echo "⚠️  $script already running, skipping"
        return 1
    fi

    echo "Starting $script $args..."
    if [ -n "$args" ]; then
        nohup python3 "$script" $args >> "$logfile" 2>&1 &
    else
        nohup python3 "$script" >> "$logfile" 2>&1 &
    fi
    local pid=$!
    echo "✓ Started $script $args (PID: $pid)"
    return 0
}

echo "=== Starting Polymarket Processes ==="
echo ""

# Start collectors
start_if_not_running "gdelt_collector.py" "--continuous" "gdelt_collection.out"
sleep 2

start_if_not_running "alchemy_collector.py" "--continuous" "alchemy_collection.out"
sleep 2

# Start traders
start_if_not_running "trader.py" "" "trading.out"
sleep 2

start_if_not_running "trader_price_levels.py" "" "trading_price_levels.out"

echo ""
echo "=== Process Status ==="
ps aux | grep -E "(trader\.py|trader_price_levels\.py|gdelt_collector|alchemy_collector)" | grep -v grep || echo "No processes running"
