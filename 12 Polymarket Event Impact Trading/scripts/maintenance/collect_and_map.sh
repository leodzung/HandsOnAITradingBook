#!/bin/bash
# Convenience script for collecting trades and mapping them
# Usage: ./collect_and_map.sh [--incremental|--backfill-days N]

set -e  # Exit on error

echo "================================="
echo "Collect & Map - Polymarket Trades"
echo "================================="

# Default to incremental
MODE="--incremental"

# Parse args
if [ "$1" == "--incremental" ]; then
    MODE="--incremental"
elif [ "$1" == "--backfill-days" ]; then
    if [ -z "$2" ]; then
        echo "Error: --backfill-days requires a number"
        exit 1
    fi
    MODE="--backfill-days $2"
fi

echo ""
echo "[1/2] Collecting on-chain trades..."
python3 alchemy_collector.py $MODE

if [ $? -ne 0 ]; then
    echo "Error: Trade collection failed"
    exit 1
fi

echo ""
echo "[2/2] Mapping token IDs to condition IDs..."
python3 market_mapper.py --map-all

if [ $? -ne 0 ]; then
    echo "Warning: Mapping failed, but trades were collected"
    exit 1
fi

echo ""
echo "================================="
echo "✓ Complete! Trades collected and mapped"
echo "================================="

# Show quick stats
echo ""
echo "Quick Stats:"
sqlite3 data/alchemy_trades.db "
SELECT
  'Total trades: ' || COUNT(*) ||
  ', Mapped: ' || COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) ||
  ' (' || ROUND(100.0 * COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) / COUNT(*), 1) || '%)'
FROM on_chain_trades;
"
