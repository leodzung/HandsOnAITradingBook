# Telegram Alerts Setup Guide

Get instant notifications when your collectors stop working!

## Quick Setup (5 minutes)

### Step 1: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "Polymarket Collector Monitor")
4. Choose a username (e.g., "my_polymarket_bot")
5. BotFather will give you a **bot token** like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`
6. **Save this token** - you'll need it in Step 3

### Step 2: Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Send `/start`
3. It will reply with your **chat ID** (a number like `123456789`)
4. **Save this chat ID** - you'll need it in Step 3

### Step 3: Configure Monitoring

1. Copy the example config:
   ```bash
   cp telegram_config.json.example telegram_config.json
   ```

2. Edit `telegram_config.json`:
   ```json
   {
     "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
     "chat_id": "123456789"
   }
   ```

   Replace with your actual bot token and chat ID from Steps 1 & 2.

3. Test the setup:
   ```bash
   python3 monitor_collectors.py --test
   ```

   You should receive a test message on Telegram! ✅

### Step 4: Set Up Automatic Monitoring

Run the monitoring script every 5 minutes:

```bash
# Add to crontab
python3 setup_monitoring_cron.py
```

Or manually add to cron:
```bash
crontab -e
```

Add this line:
```
*/5 * * * * cd /Users/leole/workspace/HandsOnAITradingBook/12\ Polymarket\ Event\ Impact\ Trading && python3 monitor_collectors.py >> monitoring.log 2>&1
```

### Step 5: Verify It's Working

```bash
# Check cron is running
crontab -l | grep monitor_collectors

# Watch monitoring logs
tail -f monitoring.log

# Manually run to test
python3 monitor_collectors.py
```

## What Gets Monitored

### GDELT Collector
- ✅ Process is running
- ✅ Logs updated in last 30 minutes (expected: 15 min)
- ✅ CPU usage < 80% (not stuck)
- ✅ Error rate < 30%
- ✅ Database growing (not losing data)

### Alchemy Collector
- ✅ Process is running
- ✅ Logs updated in last 2 hours (expected: 60 min)
- ✅ CPU usage < 95% (can be high during collection)
- ✅ Error rate < 30%
- ✅ Database growing (not losing data)

## Alert Examples

### Critical Alert (Process Stopped)
```
🚨 GDELT Collector Alert

❌ GDELT collector process not running

Consecutive failures: 2
Action: Restart with `./restart_all.sh`
```

### Warning Alert (Stale Logs)
```
⚠️ GDELT Collector Warning

⚠️ GDELT log not updated in 45 minutes (expected: 15 min)

May be stuck or crashed. Check logs:
`tail -50 gdelt_collection.out`
```

### High Error Rate
```
⚠️ Alchemy Collector Warning

⚠️ Alchemy high error rate: 18/50 (36%)

Check recent errors:
`tail -100 alchemy_collection.out | grep ERROR`
```

## Alert Logic

**Smart Alerting:**
- ✅ Only alerts after **2 consecutive failures** (avoids false alarms)
- ✅ **30-60 minute cooldown** between alerts (avoids spam)
- ✅ Different severity levels (🚨 critical, ⚠️ warning)
- ✅ Actionable messages with commands to run

**No alerts for:**
- Temporary network issues (1 check failure)
- Expected behavior (Alchemy CPU high during collection)
- Zero growth (ok if no new data available)

## Troubleshooting

### "Telegram config not found"
```bash
# Make sure you created the config file
ls -lh telegram_config.json

# If missing, copy from example
cp telegram_config.json.example telegram_config.json
# Then edit with your credentials
```

### "Telegram not enabled"
```bash
# Check your config has both fields
cat telegram_config.json

# Should show:
{
  "bot_token": "123456789:ABC...",  ← Must be filled
  "chat_id": "123456789"            ← Must be filled
}
```

### Not receiving alerts
```bash
# 1. Test manually
python3 monitor_collectors.py --test

# 2. Check if cron is running
crontab -l

# 3. Check monitoring logs
tail -50 monitoring.log

# 4. Verify bot token and chat_id are correct
# Resend /start to your bot on Telegram
```

### Testing Alerts

To test if alerts work, temporarily stop a collector:

```bash
# Stop GDELT collector
pkill -f gdelt_collector

# Wait 10 minutes (2 monitoring cycles)
# You should receive an alert

# Restart
./restart_all.sh
```

## Advanced Configuration

### Change Monitoring Frequency

Edit crontab:
```bash
crontab -e
```

Change `*/5` to your preferred interval:
- `*/5` = Every 5 minutes (recommended)
- `*/10` = Every 10 minutes
- `*/15` = Every 15 minutes

### Monitor Additional Things

Edit `monitor_collectors.py` and add checks to:
- `check_gdelt_collector()` - Add GDELT-specific checks
- `check_alchemy_collector()` - Add Alchemy-specific checks
- `monitor_all()` - Add new collectors

### Adjust Alert Thresholds

Edit these constants in `monitor_collectors.py`:
```python
CPU_THRESHOLD = 80.0          # Alert if CPU > 80%
ERROR_RATE_THRESHOLD = 0.3    # Alert if >30% errors
GDELT_INTERVAL = 15 * 60      # Expected update: 15 min
ALCHEMY_INTERVAL = 60 * 60    # Expected update: 60 min
```

### Multiple Chat Recipients

To send alerts to multiple people:

1. Add each person's chat_id to config:
   ```json
   {
     "bot_token": "123456789:ABC...",
     "chat_id": ["123456789", "987654321"]
   }
   ```

2. Modify `send_message()` in `monitor_collectors.py` to loop through chat_ids

### Disable Monitoring

```bash
# Remove from cron
crontab -e
# Delete the monitor_collectors line

# Or comment it out
# */5 * * * * cd /path && python3 monitor_collectors.py
```

## Security Notes

- ✅ `telegram_config.json` contains sensitive credentials - **do not commit to git**
- ✅ Already added to `.gitignore` (if not, add it)
- ✅ Bot token gives control of your bot - keep it secret
- ✅ Chat ID is less sensitive but still keep private

## Files Created

```
monitor_collectors.py           # Main monitoring script
telegram_config.json            # Your credentials (keep secret!)
telegram_config.json.example    # Template for others
TELEGRAM_SETUP.md              # This file
setup_monitoring_cron.py       # Helper to set up cron
data/monitor_state.json        # Monitoring state (auto-created)
monitoring.log                 # Monitoring logs (auto-created)
```

## Quick Reference Commands

```bash
# Test Telegram alerts
python3 monitor_collectors.py --test

# Run monitoring manually
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

## Support

If you have issues:
1. Check `monitoring.log` for errors
2. Test with `--test` flag
3. Verify bot token and chat_id
4. Make sure `requests` library is installed: `pip3 install requests`
