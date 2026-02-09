#!/bin/bash
# Setup Cron Job for Price Tracker

echo "=========================================="
echo "Setting up Price Tracker Cron Job"
echo "=========================================="
echo ""

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Project directory: $SCRIPT_DIR"
echo ""

# Make check_outcomes.py executable
chmod +x "$SCRIPT_DIR/check_outcomes.py"
echo "✓ Made check_outcomes.py executable"

# Create cron job entry
CRON_ENTRY="0 * * * * cd \"$SCRIPT_DIR\" && /usr/bin/python3 check_outcomes.py >> cron_output.log 2>&1"

echo ""
echo "Cron job entry to add:"
echo "$CRON_ENTRY"
echo ""

# Check if cron job already exists
crontab -l 2>/dev/null | grep -q "check_outcomes.py"
if [ $? -eq 0 ]; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "check_outcomes.py"
    echo ""
    read -p "Do you want to replace it? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove old entry
        crontab -l | grep -v "check_outcomes.py" | crontab -
        echo "✓ Removed old cron job"
    else
        echo "Keeping existing cron job"
        exit 0
    fi
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✓ Cron job added successfully!"
echo ""
echo "Verification:"
crontab -l | grep "check_outcomes.py"
echo ""

# Test the script
echo "=========================================="
echo "Testing check_outcomes.py..."
echo "=========================================="
cd "$SCRIPT_DIR"
python3 check_outcomes.py

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "The cron job will:"
echo "  • Run every hour (at :00)"
echo "  • Check prices for all pending events"
echo "  • Update outcomes when 24h elapsed"
echo "  • Log to: cron_output.log"
echo ""
echo "Monitor with:"
echo "  tail -f cron_output.log"
echo ""
echo "View stats:"
echo "  python3 view_tracking_stats.py"
echo ""
