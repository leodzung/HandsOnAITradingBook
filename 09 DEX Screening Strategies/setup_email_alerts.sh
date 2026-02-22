#!/bin/bash

# Setup script for email alerts
# This guides you through setting up automated DEX scanner with email alerts

echo "════════════════════════════════════════════════════════════════════"
echo "  DEX SCANNER - EMAIL ALERT SETUP"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "This will set up automated scanning with email alerts to ltd@bu.edu"
echo ""

# Check if email_config.json exists
if [ ! -f "email_config.json" ]; then
    echo "❌ email_config.json not found!"
    exit 1
fi

echo "Step 1: Email Configuration"
echo "────────────────────────────────────────────────────────────────────"
echo ""
echo "You need a Gmail account to send alerts."
echo ""
echo "⚠️  IMPORTANT: Gmail requires an 'App Password'"
echo "   Regular password won't work!"
echo ""
echo "To get an App Password:"
echo "  1. Go to: https://myaccount.google.com/apppasswords"
echo "  2. Select 'Mail' and 'Mac'"
echo "  3. Click 'Generate'"
echo "  4. Copy the 16-character password"
echo ""
read -p "Press Enter when you have your App Password ready..."
echo ""

# Get email details
read -p "Enter your Gmail address (e.g., yourname@gmail.com): " from_email
echo ""
read -s -p "Paste your Gmail App Password (16 characters): " app_password
echo ""
echo ""

# Update email_config.json
echo "Updating email_config.json..."

cat > email_config.json << EOF
{
  "email_settings": {
    "to_email": "ltd@bu.edu",
    "from_email": "$from_email",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_password": "$app_password",
    "subject_prefix": "[DEX Scanner]"
  },
  "alert_settings": {
    "min_score_to_alert": 70,
    "max_alerts_per_run": 5,
    "include_chart_links": true
  }
}
EOF

echo "✅ Email configuration saved"
echo ""

echo "Step 2: Test Email"
echo "────────────────────────────────────────────────────────────────────"
echo ""
echo "Testing email functionality..."
echo ""

# Make script executable
chmod +x run_with_email_alerts.py

# Test email
if python3 run_with_email_alerts.py; then
    echo ""
    echo "✅ Test completed!"
    echo ""
    read -p "Did you receive an email at ltd@bu.edu? (y/n): " received_email

    if [ "$received_email" != "y" ]; then
        echo ""
        echo "⚠️  Email not received. Please check:"
        echo "   - Spam folder at ltd@bu.edu"
        echo "   - Gmail credentials are correct"
        echo "   - App Password (not regular password)"
        echo "   - 2FA is enabled on Gmail account"
        echo ""
        echo "Run this script again after fixing the issue."
        exit 1
    fi
else
    echo ""
    echo "❌ Test failed!"
    echo "   Check the error messages above"
    echo "   Run this script again after fixing the issue"
    exit 1
fi

echo ""
echo "Step 3: Set Up Cron Job"
echo "────────────────────────────────────────────────────────────────────"
echo ""
echo "Now we'll set up automatic hourly scanning during peak hours."
echo ""
echo "Recommended schedule: Every hour from 9AM-6PM UTC (Monday-Friday)"
echo "This covers US market hours and most active trading times."
echo ""
read -p "Press Enter to open crontab editor..."
echo ""
echo "📋 Copy this line into your crontab:"
echo ""
echo "────────────────────────────────────────────────────────────────────"

# Get current directory
CURRENT_DIR=$(pwd)

echo "SCANNER_DIR=$CURRENT_DIR"
echo '0 9-18 * * 1-5 cd "$SCANNER_DIR" && /usr/bin/python3 run_with_email_alerts.py >> cron_log.txt 2>&1'
echo "────────────────────────────────────────────────────────────────────"
echo ""
echo "Instructions:"
echo "  1. The crontab editor will open in a moment"
echo "  2. Press 'i' to enter insert mode (if using vim)"
echo "  3. Paste the lines above"
echo "  4. Press Esc, then type ':wq' and press Enter"
echo "  5. Or if using nano: Paste, then Ctrl+O, Enter, Ctrl+X"
echo ""
read -p "Press Enter to open crontab editor..."

# Open crontab
crontab -e

echo ""
echo "Step 4: Verification"
echo "────────────────────────────────────────────────────────────────────"
echo ""
echo "Checking if cron job was added..."
echo ""

if crontab -l | grep -q "run_with_email_alerts.py"; then
    echo "✅ Cron job successfully added!"
    echo ""
    echo "Your crontab:"
    echo "────────────────────────────────────────────────────────────────────"
    crontab -l | grep -A 1 "DEX SCANNER\|run_with_email_alerts"
    echo "────────────────────────────────────────────────────────────────────"
else
    echo "⚠️  Cron job not detected in crontab"
    echo ""
    echo "To add manually:"
    echo "  1. Run: crontab -e"
    echo "  2. Add the line shown above"
    echo "  3. Save and exit"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo "  SETUP COMPLETE! 🎉"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Email alerts configured for: ltd@bu.edu"
echo "✅ Sending from: $from_email"
echo "✅ Schedule: Hourly from 9AM-6PM UTC, Monday-Friday"
echo ""
echo "📊 What happens next:"
echo "  • Scanner runs automatically at scheduled times"
echo "  • When opportunities found (score ≥70), you get an email"
echo "  • Logs saved to: cron_log.txt"
echo ""
echo "📋 Monitoring:"
echo "  • View logs: tail -f cron_log.txt"
echo "  • View crontab: crontab -l"
echo "  • Test manually: python3 run_with_email_alerts.py"
echo ""
echo "📖 Full documentation: See CRON_SETUP.md"
echo ""
echo "⚠️  IMPORTANT REMINDERS:"
echo "  • Always verify tokens before buying (honeypot.is, BSCScan)"
echo "  • Start with small amounts (\$50-100)"
echo "  • 90% of early tokens fail - expect losses"
echo "  • This is NOT financial advice"
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Good luck finding those gems! 💎"
echo ""
