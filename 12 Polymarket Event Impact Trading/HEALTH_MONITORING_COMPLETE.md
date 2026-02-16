# Bot Health Monitoring Service - Implementation Complete

**Date**: 2026-02-15  
**Status**: ✅ Fully operational

---

## Summary

Created a dedicated monitoring service that proactively detects bot health issues and sends Telegram alerts. Addresses the gap where we had no visibility into missing or underperforming bots.

---

## What Was Built

### Core Service
**File**: `src/monitoring/bot_health_monitor.py` (600+ lines)

**Features**:
- ✅ Bot liveness checks (detects silent/crashed bots)
- ✅ Collection rate monitoring (alerts on >50% drops)
- ✅ Bot asymmetry detection (identifies imbalanced collection)
- ✅ Database health checks (corruption, size monitoring)
- ✅ Telegram integration with alert cooldowns
- ✅ Persistent alert state (survives restarts)
- ✅ Severity levels (critical, warning, info)

### Supporting Files

| File | Purpose |
|------|---------|
| `config/monitoring_config.json` | Configurable thresholds |
| `scripts/run_health_monitor_daemon.sh` | Start monitoring daemon |
| `scripts/check_bot_health.sh` | One-shot check (for cron) |
| `BOT_HEALTH_MONITORING.md` | Complete documentation (100+ lines) |
| `HEALTH_MONITORING_COMPLETE.md` | This summary |

---

## Alert Types Implemented

### 🚨 Critical Alerts
1. **Missing Bot**: Bot never collected any data
2. **Silent Bot**: No snapshots in 30+ minutes (configurable)
3. **Database Missing/Corrupted**: DB file issues

### ⚠️ Warning Alerts
1. **Collection Rate Drop**: >50% decrease from baseline
2. **Bot Performance Degradation**: Sustained low rates

### ℹ️ Info Alerts
1. **Bot Asymmetry**: One bot collecting significantly more/less than others

---

## Usage

### Quick Start

```bash
# Test the monitor
python3 src/monitoring/bot_health_monitor.py --once --no-telegram

# Start monitoring daemon (recommended for production)
./scripts/run_health_monitor_daemon.sh

# View logs
tail -f logs/bot_health_monitor.log
```

### Example Output

```
============================================================
BOT HEALTH MONITORING REPORT
Timestamp: 2026-02-16 02:27:25 UTC
============================================================

⚠️  1 ISSUE(S) FOUND

LIVENESS CHECK:
  ✅ OK

COLLECTION_RATE CHECK:
  ✅ OK

ASYMMETRY CHECK:
  ⚖️  Bot asymmetry detected: 9.5x difference
      (event: 113, price_level: 12, short_expiry: 114)

DATABASE CHECK:
  ✅ OK

============================================================
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

**All thresholds are configurable** - adjust based on your environment.

---

## Integration with Existing System

### Reads From
- `data/market_snapshots.db` - Snapshot collector database

### Uses
- `TelegramNotifier` - Existing Telegram integration
- `config/config.json` - Telegram credentials

### Independent
- Runs separately from trading bots
- Won't interfere with bot operations
- Can be stopped/started without affecting bots

---

## Running Modes

### 1. Daemon Mode (Recommended)
Runs continuously, checks every 15 minutes:
```bash
./scripts/run_health_monitor_daemon.sh
```

### 2. Cron Mode
Run periodically via crontab:
```bash
# Add to crontab (check every 30 minutes)
*/30 * * * * cd /path/to/project && ./scripts/check_bot_health.sh
```

### 3. Manual Mode
One-shot check without alerts:
```bash
python3 src/monitoring/bot_health_monitor.py --once --no-telegram
```

---

## Alert Deduplication

**Problem**: Don't spam Telegram with same alert every 15 minutes

**Solution**: Alert cooldown period (default: 60 minutes)
- Each alert type has unique key (e.g., `silent_bot_event`)
- Alerts saved to `data/bot_health_alerts.json`
- Won't re-alert for same issue within cooldown period
- State persists across restarts

---

## What Gets Monitored

### Bot Liveness
```python
# Detects:
- Bot never collected data (not running/integrated)
- Bot silent for >30 minutes (crashed/stuck)
- Expected bot missing entirely
```

### Collection Rates
```python
# Detects:
- Rate drop >50% from baseline
- Sustained low collection rates
- Sudden drops in activity

# Compares:
- Current rate (last 30 min)
- Baseline rate (last 2 hours)
```

### Bot Asymmetry
```python
# Detects:
- One bot collecting 5x+ more than another
- Extreme imbalances that may indicate issues

# Note: Some asymmetry is normal
- Event bot may be more active during news events
- Price-level bot may have stricter criteria
```

### Database Health
```python
# Checks:
- Database file exists
- No corruption (integrity check)
- Size monitoring (warns if >100 MB)
```

---

## Testing Results

### Test Run (2026-02-15 18:27 UTC)

```
✅ All bots alive and collecting data
✅ Collection rates normal
⚠️  Bot asymmetry detected (expected - different strategies)
✅ Database healthy

Current snapshot counts:
  event:        113 snapshots
  price_level:   12 snapshots
  short_expiry: 114 snapshots
```

**Asymmetry explanation**: Price-level bot has stricter filtering (specific strike prices), so fewer market matches. This is **expected behavior**, not a bug.

---

## Telegram Alert Examples

### Bot Silent Alert
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

### Rate Drop Alert
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

---

## Next Steps

### 1. Start the Monitor
```bash
./scripts/run_health_monitor_daemon.sh
```

### 2. Monitor for 24 Hours
- Observe normal behavior patterns
- Identify baseline collection rates
- Note any false positives

### 3. Tune Thresholds (if needed)
Edit `config/monitoring_config.json`:
- Increase `silence_threshold_minutes` if too sensitive
- Adjust `rate_drop_threshold` based on observed variance
- Increase `asymmetry_threshold` if bots have very different strategies

### 4. Set Up Logrotate (optional)
Prevent `logs/bot_health_monitor.log` from growing too large

---

## Comparison: Before vs After

### Before
- ❌ No visibility into bot health
- ❌ Manual checking required (`view_snapshots.py`)
- ❌ Issues discovered hours/days later
- ❌ No alerts when bots stop collecting data
- ❌ No detection of performance degradation

### After
- ✅ Automated health monitoring every 15 minutes
- ✅ Proactive Telegram alerts for issues
- ✅ Detects silent/crashed bots within 30 minutes
- ✅ Monitors collection rates and performance
- ✅ Database health checks
- ✅ Alert deduplication prevents spam

---

## Files Created

```
src/monitoring/bot_health_monitor.py         # Main service (600+ lines)
config/monitoring_config.json                # Configuration
scripts/run_health_monitor_daemon.sh         # Daemon launcher
scripts/check_bot_health.sh                  # Cron-friendly one-shot
BOT_HEALTH_MONITORING.md                     # Full documentation
HEALTH_MONITORING_COMPLETE.md                # This summary
data/bot_health_alerts.json                  # Alert state (auto-generated)
logs/bot_health_monitor.log                  # Monitor logs (auto-generated)
```

---

## Architecture

```
┌──────────────────────────────────────┐
│   BotHealthMonitor (Daemon)          │
│   • Checks every 15 min              │
│   • Telegram alerts                  │
│   • Alert cooldown/dedup             │
└──────────────────────────────────────┘
         │                      │
         │ Monitors             │ Sends alerts
         ▼                      ▼
┌──────────────────┐    ┌──────────────┐
│ Snapshot DB      │    │  Telegram    │
│ • event          │    │  🚨 Critical │
│ • price_level    │    │  ⚠️  Warning │
│ • short_expiry   │    │  ℹ️  Info    │
└──────────────────┘    └──────────────┘
```

---

**Implementation**: Complete ✅  
**Testing**: Passed ✅  
**Documentation**: Complete ✅  
**Ready for Production**: Yes ✅

**Recommendation**: Start the daemon and monitor for 24 hours to establish baselines, then tune thresholds if needed.
