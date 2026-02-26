#!/bin/bash
#
# Setup Cron Jobs for Automated Monitoring
#
# This script sets up automated monitoring tasks:
# 1. Telemetry collection: Every 5 minutes (via daemon)
# 2. Pattern analysis: Daily at 8 AM
# 3. Auto-remediation: Every 4 hours
# 4. Constraint validation: Hourly
#
# Usage:
#   bash scripts/setup_cron.sh
#

set -e

# Get absolute path to project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "🔧 Setting up cron jobs for automated monitoring"
echo "   Project: $PROJECT_DIR"
echo

# Create cron jobs file
CRON_FILE="/tmp/polymarket_cron_$$"

# Get current crontab (if exists)
crontab -l > "$CRON_FILE" 2>/dev/null || true

# Remove existing polymarket monitoring jobs
sed -i '' '/# Polymarket Monitoring/d' "$CRON_FILE" 2>/dev/null || true
sed -i '' '/collect_telemetry.py/d' "$CRON_FILE" 2>/dev/null || true
sed -i '' '/analyze_patterns.py/d' "$CRON_FILE" 2>/dev/null || true
sed -i '' '/validate_constraints.py/d' "$CRON_FILE" 2>/dev/null || true
sed -i '' '/auto_remediation.py/d' "$CRON_FILE" 2>/dev/null || true

# Add new jobs
cat >> "$CRON_FILE" << EOF

# Polymarket Monitoring - Automated Tasks
# Generated: $(date)

# Pattern analysis: Daily at 8 AM
0 8 * * * cd "$PROJECT_DIR" && /usr/bin/python3 scripts/analyze_patterns.py --suggest --output suggestions.yml >> logs/pattern_analysis_cron.log 2>&1

# Auto-remediation: Every 4 hours (safe actions only)
0 */4 * * * cd "$PROJECT_DIR" && /usr/bin/python3 -c "from src.monitoring.auto_remediation import AutoRemediator, create_safe_remediation_actions; AutoRemediator().run_remediation(action_ids=create_safe_remediation_actions())" >> logs/auto_remediation_cron.log 2>&1

# Constraint validation: Every hour
0 * * * * cd "$PROJECT_DIR" && /usr/bin/python3 scripts/validate_constraints.py >> logs/constraint_validation_cron.log 2>&1

EOF

# Install new crontab
crontab "$CRON_FILE"

# Clean up
rm "$CRON_FILE"

echo "✅ Cron jobs installed successfully"
echo
echo "📋 Scheduled Tasks:"
echo "   • Pattern Analysis:        Daily at 8:00 AM"
echo "   • Auto-Remediation:        Every 4 hours"
echo "   • Constraint Validation:   Every hour"
echo "   • Telemetry Collection:    Every 5 minutes (daemon: PID $(pgrep -f 'collect_telemetry.py --daemon' || echo 'NOT RUNNING'))"
echo
echo "📁 Log Files:"
echo "   • logs/pattern_analysis_cron.log"
echo "   • logs/auto_remediation_cron.log"
echo "   • logs/constraint_validation_cron.log"
echo "   • logs/telemetry_daemon.log"
echo
echo "🔍 View current crontab:"
echo "   crontab -l"
echo
echo "❌ Remove cron jobs:"
echo "   crontab -l | grep -v 'Polymarket Monitoring' | grep -v 'analyze_patterns' | grep -v 'auto_remediation' | grep -v 'validate_constraints' | crontab -"
