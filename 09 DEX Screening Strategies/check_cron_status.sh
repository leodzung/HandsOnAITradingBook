#!/bin/bash

# Check Cron Status Script

echo "════════════════════════════════════════════════════════════════════"
echo "  DEX SCANNER CRON STATUS"
echo "════════════════════════════════════════════════════════════════════"
echo ""

# Current time
echo "⏰ CURRENT TIME:"
echo "   Local: $(date)"
echo "   UTC:   $(date -u)"
echo ""

# Cron schedule
echo "📅 CRON SCHEDULE:"
echo "   Every hour from 9AM-6PM UTC, Monday-Friday"
echo "   Cron expression: 0 9-18 * * 1-5"
echo ""

# Check if cron is installed
if crontab -l 2>/dev/null | grep -q "run_with_email_alerts.py"; then
    echo "✅ CRON JOB: INSTALLED"
    echo ""
    echo "   Your crontab entry:"
    crontab -l | grep "run_with_email_alerts.py"
else
    echo "❌ CRON JOB: NOT FOUND"
    echo "   Run: ./install_cron.sh"
    exit 1
fi

echo ""

# Check if log exists
if [ -f cron_log.txt ]; then
    echo "📝 LAST RUN:"
    echo ""

    # Get last timestamp from log
    last_run=$(grep "Scan completed successfully" cron_log.txt | tail -1 | grep -o "[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\} [0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}")

    if [ -n "$last_run" ]; then
        echo "   ✅ Last completed: $last_run UTC"
        echo ""

        # Show last few lines
        echo "   Last 5 log lines:"
        tail -5 cron_log.txt | sed 's/^/   │ /'
    else
        echo "   ⚠️  Log exists but no completed scans found"
    fi
else
    echo "📝 LAST RUN:"
    echo "   ❌ No runs yet (cron_log.txt doesn't exist)"
    echo "   This is normal if cron was just installed"
fi

echo ""

# Calculate next run
current_hour_utc=$(date -u +%H)
current_min_utc=$(date -u +%M)
current_day=$(date -u +%u)  # 1=Monday, 7=Sunday

echo "🔮 NEXT RUN:"
echo ""

# Check if today is weekday (1-5 = Mon-Fri)
if [ "$current_day" -ge 1 ] && [ "$current_day" -le 5 ]; then
    # Weekday
    if [ "$current_hour_utc" -ge 18 ]; then
        # Past 6PM UTC today, next run is tomorrow at 9AM UTC
        next_hour=9
        next_day="tomorrow"

        # Calculate hours until
        hours_until=$((24 - current_hour_utc + 9))
        mins_until=$((60 - current_min_utc))

        if [ "$current_day" -eq 5 ]; then
            # Friday after 6PM, next run is Monday
            next_day="Monday"
            hours_until=$((24 * 2 + 24 - current_hour_utc + 9))  # Weekend skip
        fi
    elif [ "$current_hour_utc" -lt 9 ]; then
        # Before 9AM UTC today, next run is today at 9AM UTC
        next_hour=9
        next_day="today"
        hours_until=$((9 - current_hour_utc))
        mins_until=$((60 - current_min_utc))
    else
        # Between 9AM-6PM UTC, next run is next hour
        next_hour=$((current_hour_utc + 1))
        next_day="today"
        hours_until=0
        mins_until=$((60 - current_min_utc))
    fi

    # Convert next run to local time
    next_hour_local=$((next_hour - 8))  # PST is UTC-8
    if [ "$next_hour_local" -lt 0 ]; then
        next_hour_local=$((next_hour_local + 24))
    fi

    echo "   ⏰ Next scheduled run:"
    echo "      UTC:   ${next_hour}:00 UTC $next_day"
    echo "      Local: ${next_hour_local}:00 PST $next_day"
    echo ""

    if [ "$hours_until" -gt 0 ]; then
        echo "   ⏳ Time until next run: ~${hours_until} hours ${mins_until} minutes"
    else
        echo "   ⏳ Time until next run: ~${mins_until} minutes"
    fi
else
    # Weekend
    echo "   ⚠️  Today is weekend - cron only runs Monday-Friday"
    echo "   ⏰ Next run: Monday at 9:00 UTC (1:00 AM PST)"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "💡 QUICK COMMANDS:"
echo "   View logs:  tail -f cron_log.txt"
echo "   Test now:   python3 run_with_email_alerts.py"
echo "   Send test:  python3 send_test_email.py"
echo ""
