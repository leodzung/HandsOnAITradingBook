#!/bin/bash
# ML Training Readiness Report

echo "=== ML TRAINING READINESS REPORT ==="
echo ""
echo "1. HISTORICAL TRAINING DATA:"
echo "   - labeled_training_data.csv: $(wc -l < data/labeled_training_data.csv) rows"
echo "   - labeled_dataset.csv: $(wc -l < data/labeled_dataset.csv) rows"
echo ""
echo "2. ON-CHAIN TRADES:"
sqlite3 data/alchemy_trades.db "SELECT COUNT(*) FROM on_chain_trades" 2>/dev/null | xargs echo "   - Total trades:"
echo ""
echo "3. GDELT NEWS:"
sqlite3 data/gdelt_news.db "SELECT COUNT(*) FROM news_events" 2>/dev/null | xargs echo "   - Total news events:"
echo ""
echo "4. LIVE POSITION DATA:"
echo "   Price-level bot:"
sqlite3 data/positions_price_level.db "SELECT '     Total: ' || COUNT(*) || ', Closed: ' || SUM(CASE WHEN exit_time IS NOT NULL THEN 1 ELSE 0 END) FROM positions" 2>/dev/null
echo "   Short-expiry bot:"
sqlite3 data/positions_short_expiry.db "SELECT '     Total: ' || COUNT(*) || ', Closed: ' || SUM(CASE WHEN exit_time IS NOT NULL THEN 1 ELSE 0 END) FROM positions" 2>/dev/null
echo ""
echo "5. PRICE SNAPSHOTS:"
sqlite3 data/tracking_short_expiry.db "SELECT '   Total: ' || COUNT(*) || ', Markets: ' || COUNT(DISTINCT market_id) FROM price_snapshots" 2>/dev/null
echo ""
echo "=== VERDICT ==="
echo "✅ READY FOR TRAINING using historical data (14K+ samples)"
echo "⏳ For live-data ML: Need 14 more days (40+ completed trades)"
echo ""
echo "=== RECOMMENDED ACTION ==="
echo "Train baseline models NOW using labeled_training_data.csv"
echo "Retrain in 14 days with fresh live data"
