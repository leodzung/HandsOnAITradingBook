#!/bin/bash
# Start bot health monitor in daemon mode (runs continuously)
# Checks bot health every 15 minutes and sends Telegram alerts

cd "$(dirname "$0")/.." || exit 1

echo "Starting Bot Health Monitor (daemon mode)..."
echo "Check interval: 15 minutes"
echo "Log: logs/bot_health_monitor.log"
echo ""

# Create logs directory if needed
mkdir -p logs

# Run monitor in background
nohup python3 -m monitoring.bot_health_monitor \
    --daemon \
    --interval 900 \
    --db data/market_snapshots.db \
    --config config/monitoring_config.json \
    >> logs/bot_health_monitor.log 2>&1 &

MONITOR_PID=$!
echo "Health monitor started (PID: $MONITOR_PID)"
echo "To stop: kill $MONITOR_PID"
echo "To view logs: tail -f logs/bot_health_monitor.log"
