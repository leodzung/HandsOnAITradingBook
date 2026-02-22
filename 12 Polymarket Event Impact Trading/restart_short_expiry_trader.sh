#!/bin/bash
# Restart Short-Expiry Trader with Slippage Estimation

cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"

# Kill any existing process
pkill -f trader_short_expiry.py

# Wait for cleanup
sleep 2

# Start the bot
nohup python3 src/bots/trader_short_expiry.py >> trading_short_expiry.out 2>&1 &

# Show the PID
sleep 1
PID=$(pgrep -f trader_short_expiry.py)
if [ -n "$PID" ]; then
    echo "✅ Short-Expiry Trader started (PID: $PID)"
    echo "📝 Logs: tail -f trading_short_expiry.out"
    echo "🔍 Slippage checks: grep 'Slippage' trading_short_expiry.out | tail -20"
else
    echo "❌ Failed to start trader"
    echo "Check logs: tail -20 trading_short_expiry.out"
fi
