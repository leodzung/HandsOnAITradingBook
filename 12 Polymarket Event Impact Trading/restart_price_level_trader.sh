#!/bin/bash
# Restart Price Level Trader with Updated Slippage Config

cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"

# Kill any existing process
pkill -f trader_price_levels.py

# Wait for cleanup
sleep 2

# Start the bot
nohup python3 src/bots/trader_price_levels.py >> trading_price_levels.out 2>&1 &

# Show the PID
sleep 1
PID=$(pgrep -f trader_price_levels.py)
if [ -n "$PID" ]; then
    echo "✅ Price Level Trader started (PID: $PID)"
    echo "📝 Logs: tail -f trading_price_levels.out"
else
    echo "❌ Failed to start trader"
    echo "Check logs: tail -20 trading_price_levels.out"
fi
