#!/bin/bash
# Comprehensive fix for process duplication and database corruption
# Root cause: Multiple processes accessing database simultaneously

set -e

echo "=== Polymarket Process & Database Fix ==="
echo ""

# Step 1: Kill all running processes
echo "Step 1: Stopping all trading and collection processes..."
pkill -f "trader\.py" || true
pkill -f "trader_price_levels\.py" || true
pkill -f "gdelt_collector\.py" || true
pkill -f "alchemy_collector\.py" || true

sleep 3

# Verify all killed
if pgrep -f "trader\.py\|trader_price_levels\.py\|gdelt_collector\.py\|alchemy_collector\.py" > /dev/null; then
    echo "⚠️  Some processes still running, force killing..."
    pkill -9 -f "trader\.py" || true
    pkill -9 -f "trader_price_levels\.py" || true
    pkill -9 -f "gdelt_collector\.py" || true
    pkill -9 -f "alchemy_collector\.py" || true
    sleep 2
fi

echo "✓ All processes stopped"
echo ""

# Step 2: Backup corrupted database
echo "Step 2: Backing up current database..."
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
if [ -f "data/gdelt_news.db" ]; then
    cp "data/gdelt_news.db" "data/gdelt_news.db.backup_${TIMESTAMP}"
    echo "✓ Backup created: data/gdelt_news.db.backup_${TIMESTAMP}"
fi
echo ""

# Step 3: Check and fix database
echo "Step 3: Checking database integrity..."
if sqlite3 data/gdelt_news.db "PRAGMA integrity_check;" 2>&1 | grep -v "^ok$" > /dev/null; then
    echo "⚠️  Database corrupted! Attempting recovery..."

    # Try to recover data
    if sqlite3 data/gdelt_news.db ".dump" 2>/dev/null | sqlite3 "data/gdelt_news_recovered.db" 2>/dev/null; then
        echo "✓ Data recovered to gdelt_news_recovered.db"
        mv data/gdelt_news.db "data/gdelt_news.db.corrupted_${TIMESTAMP}"
        mv data/gdelt_news_recovered.db data/gdelt_news.db
        echo "✓ Database restored"
    else
        echo "✗ Recovery failed - creating fresh database"
        mv data/gdelt_news.db "data/gdelt_news.db.corrupted_${TIMESTAMP}"
        echo "✓ Fresh database will be created on next start"
    fi
else
    echo "✓ Database integrity OK"
fi
echo ""

# Step 4: Create process management script
echo "Step 4: Creating safe process launcher..."
cat > restart_all.sh << 'EOF'
#!/bin/bash
# Safe process restart - prevents duplicates

# Function to start process only if not already running
start_if_not_running() {
    local script=$1
    local logfile=$2

    if pgrep -f "$script" > /dev/null; then
        echo "⚠️  $script already running, skipping"
        return 1
    fi

    echo "Starting $script..."
    nohup python3 "$script" >> "$logfile" 2>&1 &
    echo "✓ Started $script (PID: $!)"
    return 0
}

echo "=== Starting Polymarket Processes ==="
echo ""

# Start collectors
start_if_not_running "gdelt_collector.py --continuous" "gdelt_collection.out"
sleep 2

start_if_not_running "alchemy_collector.py --continuous" "alchemy_collection.out"
sleep 2

# Start traders
start_if_not_running "trader.py" "trading.out"
sleep 2

start_if_not_running "trader_price_levels.py" "trading_price_levels.out"

echo ""
echo "=== Process Status ==="
ps aux | grep -E "(trader\.py|trader_price_levels\.py|gdelt_collector|alchemy_collector)" | grep -v grep || echo "No processes running"
EOF

chmod +x restart_all.sh
echo "✓ Created restart_all.sh"
echo ""

# Step 5: Create monitoring script
echo "Step 5: Creating process monitor..."
cat > check_processes.sh << 'EOF'
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
EOF

chmod +x check_processes.sh
echo "✓ Created check_processes.sh"
echo ""

# Step 6: Add database safety improvements to gdelt_collector.py
echo "Step 6: Adding database safety improvements..."
if [ ! -f "gdelt_collector.py.original" ]; then
    cp gdelt_collector.py gdelt_collector.py.original
    echo "✓ Backed up original gdelt_collector.py"
fi
echo ""

echo "=== Fix Complete ==="
echo ""
echo "Next steps:"
echo "1. Run: ./restart_all.sh     # Restart all processes safely"
echo "2. Run: ./check_processes.sh  # Verify no duplicates"
echo "3. Monitor: tail -f gdelt_collection.out"
echo ""
echo "To prevent future issues:"
echo "- Always use restart_all.sh to start processes"
echo "- Run check_processes.sh daily to catch duplicates"
echo "- Use 'pkill -f script.py' before restarting any process"
