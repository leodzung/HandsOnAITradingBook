#!/bin/bash
# Run health check once (suitable for cron)
# Usage: Add to crontab for periodic checks
# Example: */30 * * * * /path/to/check_bot_health.sh

cd "$(dirname "$0")/.." || exit 1

python3 -m monitoring.bot_health_monitor \
    --once \
    --db data/market_snapshots.db \
    --config config/monitoring_config.json
