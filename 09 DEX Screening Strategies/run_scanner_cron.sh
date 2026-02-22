#!/bin/bash
#
# DEX Scanner Cron Job
# Runs every 10 minutes to find DEX-only opportunities
#

# Set working directory
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies" || exit 1

# Set log file with timestamp
LOG_DIR="./logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/scanner_$(date +\%Y\%m\%d).log"

# Add timestamp to log
echo "" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "Scan started at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

# Run the production scanner
/usr/bin/python3 run_prod_funnel.py >> "$LOG_FILE" 2>&1

# Check exit status
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Scan completed successfully at $(date)" >> "$LOG_FILE"
else
    echo "❌ Scan failed with exit code $EXIT_CODE at $(date)" >> "$LOG_FILE"
fi

# Keep only last 7 days of logs
find "$LOG_DIR" -name "scanner_*.log" -mtime +7 -delete

exit $EXIT_CODE
