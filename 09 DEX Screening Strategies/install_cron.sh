#!/bin/bash

# Install DEX Scanner cron job

echo "Installing DEX Scanner cron job..."
echo ""

# Get current directory
CURRENT_DIR="/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"

# Create cron job entry
CRON_JOB="0 9-18 * * 1-5 cd \"$CURRENT_DIR\" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "run_with_email_alerts.py"; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "run_with_email_alerts.py"
    echo ""
    read -p "Do you want to replace it? (y/n): " replace

    if [ "$replace" != "y" ]; then
        echo "Cancelled."
        exit 0
    fi

    # Remove old cron job
    crontab -l | grep -v "run_with_email_alerts.py" | crontab -
    echo "✅ Removed old cron job"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo ""; echo "# DEX Scanner - Hourly during peak hours"; echo "$CRON_JOB") | crontab -

echo ""
echo "✅ Cron job installed successfully!"
echo ""
echo "Schedule: Every hour from 9AM-6PM UTC, Monday-Friday"
echo "Logs: $CURRENT_DIR/cron_log.txt"
echo "Alerts to: ltd@bu.edu"
echo "From: dzung.letien@gmail.com"
echo ""
echo "Your crontab:"
echo "════════════════════════════════════════════════════════════════"
crontab -l
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Scanner will run automatically at scheduled times"
echo "  2. Check logs: tail -f cron_log.txt"
echo "  3. When opportunities found, you'll get email at ltd@bu.edu"
echo ""
