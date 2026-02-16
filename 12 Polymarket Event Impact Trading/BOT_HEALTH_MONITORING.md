# Bot Health Monitoring Service

**Created**: 2026-02-15
**Status**: ✅ Operational

## Overview

Dedicated monitoring service that tracks trading bot health, data collection rates, and system anomalies. Sends Telegram alerts when issues are detected.

## Features

### 1. **Bot Liveness Checks**
- Detects silent/crashed bots (no snapshots in X minutes)
- Alerts if expected bot is missing entirely
- Configurable silence threshold (default: 30 minutes)

### 2. **Collection Rate Monitoring**
- Tracks snapshot collection rate per bot
- Alerts if rate drops >50% from baseline
- Compares current rate (last 30 min) to baseline (last 2 hours)

### 3. **Bot Asymmetry Detection**
- Identifies when one bot collects significantly more/less than others
- Alerts if ratio exceeds threshold (default: 5x difference)
- Helps identify misconfigured or underperforming bots

### 4. **Database Health Checks**
- Verifies database file exists
- Checks for corruption (integrity check)
- Monitors database size growth

### 5. **Alert Management**
- Telegram integration for real-time notifications
- Alert cooldown to prevent spam (default: 60 minutes)
- Persistent alert state (survives restarts)
- Severity levels: critical, warning, info, resolved

---

## Installation & Setup

### Quick Start

```bash
# 1. Configuration is already set up in config/monitoring_config.json
cat config/monitoring_config.json

# 2. Test the monitor (one-shot check)
python3 src/monitoring/bot_health_monitor.py --once

# 3. Start monitoring daemon (runs continuously)
./scripts/run_health_monitor_daemon.sh
```

### Running Modes

#### **Mode 1: Daemon (Recommended for Production)**
Runs continuously, checking every 15 minutes:

```bash
./scripts/run_health_monitor_daemon.sh
```

Or manually:
```bash
python3 src/monitoring/bot_health_monitor.py \
    --daemon \
    --interval 900 \
    --db data/market_snapshots.db \
    --config config/monitoring_config.json
```

**Log location**: `logs/bot_health_monitor.log`

#### **Mode 2: One-Shot (For Cron)**
Run once and exit:

```bash
./scripts/check_bot_health.sh
```

**Crontab example** (check every 30 minutes):
```bash
*/30 * * * * cd /path/to/12\ Polymarket\ Event\ Impact\ Trading && ./scripts/check_bot_health.sh >> logs/health_cron.log 2>&1
```

#### **Mode 3: Manual Check**
Run manually without Telegram alerts:

```bash
python3 src/monitoring/bot_health_monitor.py --once --no-telegram
```

---

## Configuration

**File**: `config/monitoring_config.json`

```json
{
  "expected_bots": ["event", "price_level", "short_expiry"],
  "silence_threshold_minutes": 30,
  "rate_drop_threshold": 0.5,
  "asymmetry_threshold": 5.0,
  "min_snapshots_for_rate_check": 10,
  "lookback_hours": 2,
  "alert_cooldown_minutes": 60
}
```

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `expected_bots` | `["event", "price_level", "short_expiry"]` | List of bots to monitor |
| `silence_threshold_minutes` | `30` | Alert if no snapshots in X minutes |
| `rate_drop_threshold` | `0.5` | Alert if rate drops >50% (0.5 = 50% drop) |
| `asymmetry_threshold` | `5.0` | Alert if one bot collects 5x more than another |
| `min_snapshots_for_rate_check` | `10` | Minimum baseline data needed for rate comparison |
| `lookback_hours` | `2` | Compare current rate to last X hours |
| `alert_cooldown_minutes` | `60` | Don't re-alert for same issue within X minutes |

---

## Alert Types

### 🚨 **Critical Alerts**

#### Missing Bot
```
Bot: event
Status: Never collected any snapshots

Action Required:
1. Check if bot is running
2. Verify snapshot collector integration
3. Check logs for errors
```

**Causes**:
- Bot not started
- Snapshot collector not integrated
- Import errors on startup

#### Silent Bot
```
Bot: price_level
Last Snapshot: 45 minutes ago
Threshold: 30 minutes

Possible Causes:
• Bot crashed or stopped
• No matching markets found
• API errors preventing data collection
```

**Causes**:
- Bot crashed
- Market filters too strict (no matches)
- API rate limiting or errors
- Network issues

#### Database Missing/Corrupted
```
Path: data/market_snapshots.db
Status: File not found
```

**Causes**:
- Database deleted
- File moved
- Disk corruption

### ⚠️ **Warning Alerts**

#### Collection Rate Drop
```
Bot: short_expiry
Baseline Rate: 25.0 snapshots/hour
Current Rate: 8.0 snapshots/hour
Drop: 68%

Possible Causes:
• Fewer markets available
• Stricter filtering criteria
• API rate limiting
• Bot performance degradation
```

**Causes**:
- Market availability decreased
- Configuration changed (stricter filters)
- Performance issues (slow processing)

### ℹ️ **Info Alerts**

#### Bot Asymmetry
```
Highest: event (523 snapshots)
Lowest: price_level (12 snapshots)
Ratio: 43.6x difference

Note: Some asymmetry is normal due to different strategies,
but extreme differences may indicate issues.
```

**Causes** (often benign):
- Different trading strategies (event bot more active)
- Different market criteria (price-level stricter)
- Time-of-day effects (short-expiry peaks near expirations)

---

## Example Output

### Healthy System
```
============================================================
BOT HEALTH MONITORING REPORT
Timestamp: 2026-02-16 02:27:25 UTC
============================================================

✅ ALL SYSTEMS HEALTHY

LIVENESS CHECK:
  ✅ OK

COLLECTION_RATE CHECK:
  ✅ OK

ASYMMETRY CHECK:
  ✅ OK

DATABASE CHECK:
  ✅ OK

============================================================
```

### System with Issues
```
============================================================
BOT HEALTH MONITORING REPORT
Timestamp: 2026-02-16 08:15:00 UTC
============================================================

⚠️  3 ISSUE(S) FOUND

LIVENESS CHECK:
  ⚠️  event: Silent for 45.2 minutes (last: 2026-02-16T07:30:00)
  ✅ price_level: OK
  ✅ short_expiry: OK

COLLECTION_RATE CHECK:
  📉 short_expiry: Collection rate dropped 68% (baseline: 25.0/hr, current: 8.0/hr)

ASYMMETRY CHECK:
  ⚖️  Bot asymmetry detected: 12.5x difference (event: 0, price_level: 234, short_expiry: 189)

DATABASE CHECK:
  ✅ OK

============================================================
```

---

## Telegram Integration

When Telegram is enabled (`config/config.json`), alerts are sent automatically:

### Alert Examples

**Bot Silent Alert**:
```
⚠️ BOT HEALTH ALERT

Bot Silent

Bot: event
Last Snapshot: 45.2 minutes ago
Threshold: 30 minutes
Total Snapshots: 1,234

Possible Causes:
• Bot crashed or stopped
• No matching markets found
• API errors preventing data collection

Action Required: Check bot logs and status
```

**Collection Rate Drop Alert**:
```
⚠️ BOT HEALTH ALERT

Collection Rate Drop

Bot: short_expiry
Baseline Rate: 25.0 snapshots/hour
Current Rate: 8.0 snapshots/hour
Drop: 68%

Possible Causes:
• Fewer markets available
• Stricter filtering criteria
• API rate limiting
• Bot performance degradation
```

### Startup Notification
When daemon starts:
```
🏥 Health Monitor Started

Check Interval: 15 minutes
Database: data/market_snapshots.db
Monitoring: event, price_level, short_expiry bots
```

---

## Troubleshooting

### Health Monitor Not Running

**Check process**:
```bash
ps aux | grep bot_health_monitor
```

**View logs**:
```bash
tail -f logs/bot_health_monitor.log
```

**Restart**:
```bash
pkill -f bot_health_monitor
./scripts/run_health_monitor_daemon.sh
```

### Not Receiving Telegram Alerts

**Check Telegram config**:
```bash
# Verify Telegram is enabled in config
cat config/config.json | grep -A 3 telegram
```

**Test Telegram manually**:
```python
from monitoring.telegram_notifier import TelegramNotifier
import json

with open('config/config.json') as f:
    config = json.load(f)
    tg = config['telegram']

notifier = TelegramNotifier(
    bot_token=tg['bot_token'],
    chat_id=tg['chat_id'],
    enabled=True
)

notifier.send_message("Test from health monitor")
```

### Alert Cooldown Too Long

If you need immediate re-alerting (e.g., during testing):

**Delete alert state file**:
```bash
rm data/bot_health_alerts.json
```

Or **adjust cooldown** in `config/monitoring_config.json`:
```json
{
  "alert_cooldown_minutes": 5  // Re-alert after 5 minutes instead of 60
}
```

### False Positives

**Bot Asymmetry** - Normal if bots have different strategies:
- Increase `asymmetry_threshold` to `10.0` or higher
- Or ignore if ratios are consistent over time

**Rate Drop** - Normal during low-activity periods:
- Increase `rate_drop_threshold` to `0.7` (70% drop required)
- Or increase `lookback_hours` to smooth out fluctuations

---

## Advanced Usage

### Custom Check Intervals

**Check every 5 minutes** (more aggressive):
```bash
python3 src/monitoring/bot_health_monitor.py --daemon --interval 300
```

**Check every hour** (less aggressive):
```bash
python3 src/monitoring/bot_health_monitor.py --daemon --interval 3600
```

### Monitor Specific Database

```bash
python3 src/monitoring/bot_health_monitor.py \
    --once \
    --db /path/to/custom_snapshots.db
```

### Run Without Telegram (Local Testing)

```bash
python3 src/monitoring/bot_health_monitor.py --once --no-telegram
```

### Custom Configuration

Create `custom_monitoring.json`:
```json
{
  "expected_bots": ["event", "short_expiry"],
  "silence_threshold_minutes": 60,
  "rate_drop_threshold": 0.3,
  "asymmetry_threshold": 10.0
}
```

Run with custom config:
```bash
python3 src/monitoring/bot_health_monitor.py \
    --once \
    --config custom_monitoring.json
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│        BotHealthMonitor                          │
│  (src/monitoring/bot_health_monitor.py)         │
└─────────────────────────────────────────────────┘
         │                           │
         │ Checks every 15 min       │ Sends alerts
         ▼                           ▼
┌──────────────────────┐    ┌──────────────────┐
│ market_snapshots.db  │    │ TelegramNotifier │
│                      │    │                  │
│ • event: 1,234       │    │ 🚨 Alerts       │
│ • price_level: 456   │    │ ⚠️  Warnings    │
│ • short_expiry: 789  │    │ ℹ️  Info        │
└──────────────────────┘    └──────────────────┘
         ▲
         │ Logs snapshots
         │
┌──────────────────────────────────────────────────┐
│  Trading Bots                                    │
│  • trader.py (event)                            │
│  • trader_price_levels.py                       │
│  • trader_short_expiry.py                       │
└──────────────────────────────────────────────────┘
```

---

## Files

```
src/monitoring/bot_health_monitor.py     # Main monitoring service
config/monitoring_config.json            # Configuration
scripts/run_health_monitor_daemon.sh     # Start daemon
scripts/check_bot_health.sh              # One-shot check (for cron)
logs/bot_health_monitor.log              # Monitor logs
data/bot_health_alerts.json              # Alert state (auto-generated)
```

---

## Integration with Existing System

The health monitor integrates seamlessly:

1. **Reads from**: `data/market_snapshots.db` (same DB used by snapshot collector)
2. **Uses**: Existing `TelegramNotifier` from `src/monitoring/`
3. **Shares config**: Uses `config/config.json` for Telegram settings
4. **Independent**: Runs separately from trading bots (won't interfere)

---

## Best Practices

### Production Deployment

1. **Run as daemon**: Use `run_health_monitor_daemon.sh`
2. **Enable Telegram**: Set `"enabled": true` in `config/config.json`
3. **Monitor logs**: `tail -f logs/bot_health_monitor.log`
4. **Set up logrotate**: Prevent log files from growing too large

### Testing Changes

1. **Test without Telegram**: Use `--no-telegram` flag
2. **One-shot mode**: Run `--once` to verify before daemon
3. **Delete alert state**: `rm data/bot_health_alerts.json` to reset cooldowns

### Alert Tuning

Start with defaults, then adjust based on your environment:
- **Too many alerts**: Increase thresholds or cooldown
- **Missing issues**: Decrease thresholds, reduce cooldown
- **False positives**: Increase `lookback_hours` or `min_snapshots_for_rate_check`

---

**Status**: ✅ Ready for production
**Last Updated**: 2026-02-15
**Next**: Start daemon and monitor for 24 hours to tune thresholds
