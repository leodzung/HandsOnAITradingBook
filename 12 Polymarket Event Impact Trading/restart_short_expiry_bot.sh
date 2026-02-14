#!/bin/bash
# Restart Short Expiry Bot with Price History Tracking

echo "🔍 Finding and stopping current short expiry bot..."
pkill -f "trader_short_expiry.py"
sleep 2

echo "✅ Bot stopped. Starting new instance with price tracking..."

cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"

# Start bot in background  
nohup python3 src/bots/trader_short_expiry.py >> logs/short_expiry_trader.out 2>&1 &

echo "✅ Bot restarted! PID: $!"
echo ""
echo "📊 Monitor: tail -f logs/short_expiry.log"
