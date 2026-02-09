#!/bin/bash
# Quick GDELT status check

echo "=== GDELT COLLECTOR STATUS REPORT ==="
echo ""

echo "📁 Database Files:"
ls -lh data/gdelt*.db 2>/dev/null | awk '{print "  " $9 ": " $5}'
echo ""

echo "📝 Last Collection Log Entries:"
echo "  From gdelt_collection.log (Jan 26):"
tail -1 gdelt_collection.log 2>/dev/null | sed 's/^/    /'
echo ""
echo "  From gdelt_collection.out (Feb 1 - INTERRUPTED):"
tail -1 gdelt_collection.out 2>/dev/null | sed 's/^/    /'
echo ""

echo "🔍 Database Status:"
echo "  gdelt_news.db: CORRUPTED (1.2GB, btree errors)"
echo "  gdelt_events.db: EMPTY (0 bytes)"
echo ""

echo "📊 Estimated Data (from logs):"
echo "  Successful run (Jan 26): 2,219,519 events from 5,000 files"
echo "  Failed run (Feb 1): ~302,403 events from 540/67,437 files (CRASHED)"
echo ""

echo "💾 Recovery Options:"
echo "  1. Try SQLite recovery: sqlite3 data/gdelt_news.db '.recover' > recovered.sql"
echo "  2. Start fresh: Delete corrupted DB and recollect"
echo "  3. Use backup if available"
echo ""

echo "🔄 Process Status:"
ps aux | grep gdelt_collector | grep -v grep > /dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ GDELT collector is RUNNING"
    ps aux | grep gdelt_collector | grep -v grep | awk '{print "    PID: " $2}'
else
    echo "  ✗ GDELT collector is NOT RUNNING"
fi
