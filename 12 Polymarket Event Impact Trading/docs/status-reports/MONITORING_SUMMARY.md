# Telegram Monitoring - Setup Complete ✅

I've set up a comprehensive monitoring system with Telegram alerts for your data collectors.

## What's Been Created

### Core Monitoring System
1. **monitor_collectors.py** - Main monitoring script
   - Checks if processes are running
   - Monitors log file updates
   - Tracks database growth
   - Detects high CPU usage
   - Calculates error rates
   - Sends Telegram alerts

2. **setup_monitoring_cron.py** - Interactive setup helper
   - Automatically configures cron job
   - Validates configuration
   - Tests alerts

3. **telegram_config.json.example** - Configuration template

### Documentation
1. **QUICK_START_TELEGRAM.md** - 2-minute setup guide
2. **TELEGRAM_SETUP.md** - Comprehensive documentation
3. **MONITORING_SUMMARY.md** - This file

## Setup Instructions (5 minutes)

### Step 1: Create Telegram Bot

1. Open Telegram, search for **@BotFather**
2. Send: `/newbot`
3. Follow prompts to create bot
4. **Copy the bot token** (like `123456789:ABCdefGHI...`)

### Step 2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Send: `/start`
3. **Copy your chat ID** (like `123456789`)

### Step 3: Configure

```bash
# Copy template
cp telegram_config.json.example telegram_config.json

# Edit with your credentials
nano telegram_config.json
```

Replace with your bot token and chat ID:
```json
{
  "bot_token": "YOUR_BOT_TOKEN_FROM_STEP_1",
  "chat_id": "YOUR_CHAT_ID_FROM_STEP_2"
}
```

### Step 4: Test

```bash
# Test that alerts work
python3 monitor_collectors.py --test
```

You should receive a test message on Telegram! ✅

### Step 5: Enable Automatic Monitoring

```bash
# Run interactive setup
python3 setup_monitoring_cron.py
```

Choose frequency (recommended: every 5 minutes) and confirm.

## Current Status

```bash
# Run this to see current status
python3 monitor_collectors.py
```

**Current output:**
```
✓ GDELT collector: OK
✓ Alchemy collector: OK
✓ All collectors healthy
```

## What Gets Monitored

### GDELT Collector
- ✅ Process running
- ✅ Logs updated (expected: every 15 min)
- ✅ CPU < 80%
- ✅ Error rate < 30%
- ✅ Database growing

### Alchemy Collector
- ✅ Process running
- ✅ Logs updated (expected: every 60 min)
- ✅ CPU < 95%
- ✅ Error rate < 30%
- ✅ Database growing

## Alert Examples

### Critical: Process Stopped
```
🚨 GDELT Collector Alert

❌ GDELT collector process not running

Consecutive failures: 2
Action: Restart with `./restart_all.sh`
```

You'll receive this if:
- Process crashes
- Process killed
- System restart

### Warning: Stale Logs
```
⚠️ Alchemy Collector Warning

⚠️ Alchemy log not updated in 120 minutes (expected: 60 min)

May be stuck. Check logs:
`tail -50 alchemy_collection.out`
```

You'll receive this if:
- Collector hung/frozen
- Database locked
- Network issues preventing collection

### High Error Rate
```
⚠️ GDELT Collector Warning

⚠️ GDELT high error rate: 18/50 (36%)

Check recent errors:
`tail -100 gdelt_collection.out | grep ERROR`
```

You'll receive this if:
- API rate limiting
- Database corruption errors
- Network connectivity issues

## Smart Features

### No False Alarms
- Only alerts after **2 consecutive failures**
- Avoids alerting on temporary glitches
- Cooldown period prevents spam

### Alert Cooldowns
- Process not running: 30 minutes between alerts
- Stale logs: 60-120 minutes between alerts
- High errors: Per-issue cooldown

### State Tracking
- Remembers previous checks in `data/monitor_state.json`
- Tracks consecutive failures
- Monitors database growth over time

## Useful Commands

```bash
# Test Telegram alerts
python3 monitor_collectors.py --test

# Run monitoring check manually
python3 monitor_collectors.py

# Check if monitoring is in cron
crontab -l | grep monitor

# View monitoring logs
tail -f monitoring.log

# Check collector status
./check_processes.sh

# Restart collectors
./restart_all.sh
```

## Files Created

```
monitor_collectors.py              # Main monitoring script
setup_monitoring_cron.py          # Cron setup helper
telegram_config.json.example      # Config template
telegram_config.json              # Your config (create this!)
QUICK_START_TELEGRAM.md          # 2-minute guide
TELEGRAM_SETUP.md                # Detailed docs
MONITORING_SUMMARY.md            # This file
data/monitor_state.json          # State (auto-created)
monitoring.log                   # Logs (auto-created)
```

## Monitoring Workflow

```
Every 5 minutes (or your chosen interval):
  ↓
Monitor checks both collectors
  ↓
All OK? → Silent (no alert)
  ↓
Issue found? → Wait for 2nd consecutive failure
  ↓
Still failing? → Check cooldown period
  ↓
Cooldown passed? → Send Telegram alert
  ↓
Log everything to monitoring.log
```

## Testing the System

### Test 1: Verify Monitoring Works
```bash
python3 monitor_collectors.py
# Should show: ✓ All collectors healthy
```

### Test 2: Verify Telegram Works
```bash
python3 monitor_collectors.py --test
# Should receive message on Telegram
```

### Test 3: Simulate Failure (Optional)
```bash
# Stop a collector
pkill -f gdelt_collector

# Wait 10 minutes (2 monitoring cycles)
# You should receive alert

# Restart
./restart_all.sh
```

## Troubleshooting

### Not receiving test message?
1. Check bot token and chat_id in telegram_config.json
2. Send /start to your bot on Telegram
3. Check for errors in terminal output

### Monitoring not running automatically?
```bash
# Check cron
crontab -l | grep monitor

# If missing, run setup again
python3 setup_monitoring_cron.py
```

### Want more frequent checks?
```bash
# Edit cron
crontab -e

# Change */5 to */3 for 3-minute intervals
*/3 * * * * cd /path && python3 monitor_collectors.py >> monitoring.log 2>&1
```

### Want to disable?
```bash
crontab -e
# Delete the monitor_collectors line
```

## Security Notes

- ⚠️ **Do not commit telegram_config.json** - it contains sensitive credentials
- ⚠️ Add to .gitignore if not already
- ⚠️ Keep bot token secret - gives control of your bot
- ⚠️ Chat ID is less sensitive but keep private

## Next Steps

1. ✅ Create Telegram bot (@BotFather)
2. ✅ Get chat ID (@userinfobot)
3. ✅ Create telegram_config.json with credentials
4. ✅ Test with: `python3 monitor_collectors.py --test`
5. ✅ Set up automatic monitoring: `python3 setup_monitoring_cron.py`
6. ✅ Verify: `crontab -l | grep monitor`

## Support

For detailed instructions, see:
- **QUICK_START_TELEGRAM.md** - Fast 2-minute setup
- **TELEGRAM_SETUP.md** - Comprehensive guide with examples

Questions? Check the monitoring logs:
```bash
tail -50 monitoring.log
```
