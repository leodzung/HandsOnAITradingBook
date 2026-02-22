#!/bin/bash
# Remove old cron job and add new one (every 10 minutes)

# Remove existing DEX Scanner cron
crontab -l 2>/dev/null | grep -v "run_with_email_alerts.py" | crontab -

# Add new cron job - every 10 minutes, 24/7
(crontab -l 2>/dev/null; echo '*/10 * * * * cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1') | crontab -

echo "✅ Cron updated to run every 10 minutes"
crontab -l
