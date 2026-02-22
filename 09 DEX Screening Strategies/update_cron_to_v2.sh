#!/bin/bash
# Update cron job to use v2 (production funnel with CEX & volume filters)

echo "🔧 Updating cron job to use DEX-only production funnel..."

# Remove existing DEX Scanner cron
crontab -l 2>/dev/null | grep -v "run_with_email_alerts" | crontab -

# Add new cron job - every 10 minutes, using v2 with production funnel
(crontab -l 2>/dev/null; echo '*/10 * * * * cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies" && /usr/bin/python3 run_with_email_alerts_v2.py >> cron_log.txt 2>&1') | crontab -

echo "✅ Cron updated to run every 10 minutes with PRODUCTION FUNNEL (DEX-only)"
echo ""
echo "New cron schedule:"
crontab -l | grep "run_with_email_alerts"
echo ""
echo "📋 What changed:"
echo "   OLD: run_with_email_alerts.py → Moralis discovery (top market cap tokens like LINK)"
echo "   NEW: run_with_email_alerts_v2.py → Production funnel (DEX-only with volume filters)"
echo ""
echo "✅ You will now only get alerts for DEX-only tokens!"
