# ✅ Telegram Alerts - Complete Setup

Your entire Polymarket trading system is now sending Telegram alerts!

## What's Configured

### 1. Monitoring System ✅
**monitor_collectors.py** watches:
- GDELT collector health
- Alchemy collector health
- Process status, CPU usage, log updates
- Database growth

**Runs:** Every 5 minutes (via cron)
**Alerts:** Only when issues detected

### 2. Event Trader ✅
**trader.py** sends:
- Position opened/closed
- P&L results
- Circuit breaker
- Daily summaries
- Errors

**Runs:** Continuously
**Alerts:** Per trade event

### 3. Price Level Trader ✅
**trader_price_levels.py** sends:
- Position opened/closed
- P&L results
- Circuit breaker
- Daily summaries
- Errors

**Runs:** Continuously
**Alerts:** Per trade event

## One Bot, One Chat

Everything uses the **same Telegram bot**:
```
Bot Token: 8068515860:AAEi...
Chat ID: 6690408994
```

All alerts appear in **one Telegram conversation** - easy to monitor!

## What You'll Receive

### Monitoring Alerts (System Health)
```
🚨 GDELT Collector Alert
❌ GDELT collector process not running
Action: Restart with `./restart_all.sh`
```

```
⚠️ Alchemy Collector Warning
⚠️ Alchemy log not updated in 120 minutes
Check logs: `tail -50 alchemy_collection.out`
```

### Trading Alerts (Positions)
```
📊 NEW POSITION - Event Trader
Asset: BTC | Side: YES | Size: $50.00
Entry: $0.620 | Edge: +8.0%
Will Bitcoin reach $100k by end of February?
```

```
✅ CLOSED POSITION - Event Trader
Asset: BTC | Entry: $0.620 | Exit: $0.750
P&L: +$6.50 (+13.0%) | Reason: Take Profit
```

```
🔴 CIRCUIT BREAKER ACTIVATED - Price Level Trader
Trading paused after 3 consecutive losses.
Will resume in 4.0 hours.
```

```
📊 DAILY SUMMARY - Event Trader
Trades: 6 | Win Rate: 66.7% | P&L: +$12.50
Open Positions: 2 | Balance: $1012.50
```

## Configuration Files

### Centralized Config
**telegram_config.json** (shared by all):
```json
{
  "bot_token": "8068515860:AAEi...",
  "chat_id": "6690408994"
}
```

### Trader Configs
**config.json** (event trader):
```json
{
  ...
  "telegram": {
    "enabled": true,
    "bot_token": "8068515860:AAEi...",
    "chat_id": "6690408994"
  }
}
```

**config_price_levels.json** (price level trader):
```json
{
  ...
  "telegram": {
    "enabled": true,
    "bot_token": "8068515860:AAEi...",
    "chat_id": "6690408994"
  }
}
```

## Testing

### Test Monitoring Alerts
```bash
python3 monitor_collectors.py --test
```
Should receive: "✅ Collector Monitor Test"

### Test Trading Alerts
```bash
python3 test_trader_telegram.py
# Choose option 7 for all tests
```
Should receive 6 sample trading notifications

### Manual Check
```bash
# Check all processes
./check_processes.sh

# Check if monitoring in cron
crontab -l | grep monitor

# Check trader logs
tail -50 trading.out | grep -i telegram
```

## Alert Frequency

**Monitoring:**
- Checks every 5 minutes
- Only alerts on issues (2+ consecutive failures)
- 30-120 minute cooldown between alerts

**Trading:**
- Alerts on every position open/close
- Circuit breaker when triggered
- Daily summary at midnight
- No cooldown (each trade is unique)

## Typical Day Timeline

```
09:00 ✅ Monitoring: All collectors OK
09:15 📊 Event Trader: Opened BTC position
10:30 ✅ Event Trader: Closed position (+$3.50)
12:00 🚨 Monitoring: Alchemy collector stale logs
14:15 📊 Price Trader: Opened ETH position
15:00 ✅ Monitoring: Alchemy collector recovered
16:45 ❌ Price Trader: Closed position (-$1.20)
18:00 📊 Event Trader: Opened BTC position
23:59 📊 Event Trader: Daily summary (6 trades, +$8.30)
```

## Customization

### Disable Specific Alerts

**Disable monitoring:**
```bash
crontab -e
# Comment out the monitor_collectors line
```

**Disable trader notifications:**
Edit `config.json`:
```json
"telegram": {
  "enabled": false,
  ...
}
```
Restart: `./restart_all.sh`

### Change Alert Frequency

**Monitoring interval:**
```bash
crontab -e
# Change */5 to */10 for 10-minute checks
*/10 * * * * cd /path && python3 monitor_collectors.py
```

**Trading alerts:** Cannot change (per-trade basis)

### Use Different Chat for Traders

To separate trading alerts from monitoring:

1. Create new group or chat
2. Add bot to new chat
3. Get new chat_id
4. Update `config.json`:
   ```json
   "chat_id": "NEW_CHAT_ID"
   ```
5. Restart traders

## Files Created

```
# Core Files
telegram_config.json              # Centralized bot config ✅
monitor_collectors.py             # Monitoring script ✅
test_trader_telegram.py           # Trading test script ✅

# Documentation
TELEGRAM_COMPLETE.md             # This file
QUICK_START_TELEGRAM.md          # Quick setup guide
TELEGRAM_SETUP.md                # Monitoring setup
TRADER_TELEGRAM_SETUP.md         # Trading setup
MONITORING_SUMMARY.md            # Monitoring overview

# Config Files (already existed)
config.json                      # Event trader config ✅
config_price_levels.json         # Price trader config ✅
telegram_notifier.py             # Notification module ✅
```

## Status Check

Run this to verify everything:

```bash
# 1. Test monitoring alerts
python3 monitor_collectors.py --test

# 2. Test trading alerts
python3 test_trader_telegram.py

# 3. Check all processes
./check_processes.sh

# 4. View recent activity
tail -20 monitoring.log
tail -20 trading.out | grep -i telegram
```

## Troubleshooting

### Not receiving alerts?

**Check bot is working:**
```bash
python3 monitor_collectors.py --test
```

**Check traders are running:**
```bash
./check_processes.sh
```

**Check Telegram config:**
```bash
cat telegram_config.json
# Should show bot_token and chat_id
```

**Check trader config:**
```bash
grep -A 3 '"telegram"' config.json
# Should show "enabled": true
```

### Receiving duplicate alerts?

Check for duplicate processes:
```bash
./check_processes.sh
# Should show only 1 of each process
```

If duplicates found:
```bash
./fix_processes_and_db.sh
./restart_all.sh
```

### Want to stop all alerts?

**Temporary (keep running):**
```bash
# Disable in configs
nano config.json  # Set telegram.enabled = false
./restart_all.sh

# Disable monitoring
crontab -e  # Comment out monitor line
```

**Permanent:**
```bash
# Remove telegram section from configs
# Disable monitoring cron
crontab -e
```

## Security

⚠️ **Important:**
- **telegram_config.json** contains bot credentials
- **DO NOT commit to git** (sensitive)
- Keep bot token secret
- Chat ID is less sensitive but keep private

Check `.gitignore` includes:
```
telegram_config.json
*.log
monitoring.log
```

## Quick Reference

```bash
# Test monitoring
python3 monitor_collectors.py --test

# Test trading
python3 test_trader_telegram.py

# Check status
./check_processes.sh

# Restart everything
./restart_all.sh

# View logs
tail -f monitoring.log
tail -f trading.out

# Check monitoring cron
crontab -l | grep monitor
```

## Summary

✅ **Monitoring System:** Checking collectors every 5 minutes
✅ **Event Trader:** Sending trade alerts
✅ **Price Level Trader:** Sending trade alerts
✅ **One Bot:** All alerts in one Telegram chat
✅ **Tested:** Both monitoring and trading notifications work

**You're all set!** Your system will now alert you to:
- System issues (collectors down, high CPU, errors)
- Trading activity (positions, P&L, circuit breakers)
- Daily summaries

No further action needed - just watch your Telegram for alerts! 🎉

---

**Last Updated:** 2026-02-07
**Bot:** @your_polymarket_bot
**Chat ID:** 6690408994
**Status:** ✅ **FULLY OPERATIONAL**
