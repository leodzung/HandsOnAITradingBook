#!/bin/bash
# Update market mapper with recent resolved markets and create labels

echo "=== Step 1: Update token mappings from Gamma API ==="
echo "This will fetch all markets (including recently resolved ones)"
python3 src/utils/market_mapper.py --update

echo ""
echo "=== Step 2: Map on-chain trades to condition_ids ==="
echo "This fills in the missing condition_ids for 90% of trades"
python3 src/utils/market_mapper.py --update-trades

echo ""
echo "=== Step 3: Check coverage ==="
python3 src/utils/market_mapper.py --stats

echo ""
echo "=== Step 4: Check overlap with resolved markets ==="
python3 check_data_overlap.py

echo ""
echo "✓ If overlap > 0, you can now create REAL labels!"
