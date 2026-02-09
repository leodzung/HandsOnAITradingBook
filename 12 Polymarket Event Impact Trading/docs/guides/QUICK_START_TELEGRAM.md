# Quick Start: Telegram Alerts (2 minutes)

Get notified instantly when collectors stop!

## 1. Create Telegram Bot (30 seconds)

Open Telegram and search for **@BotFather**:
```
You: /newbot
BotFather: Choose a name for your bot
You: Polymarket Monitor
BotFather: Choose a username
You: my_polymarket_monitor_bot
BotFather: Done! Your token: 123456789:ABCdefGHI...
```

**Copy the token** (looks like `123456789:ABCdefGHI...`)

## 2. Get Your Chat ID (30 seconds)

Search for **@userinfobot** on Telegram:
```
You: /start
userinfobot: Your user ID: 123456789
```

**Copy your chat ID** (the number)

## 3. Configure (30 seconds)

```bash
# Copy example config
cp telegram_config.json.example telegram_config.json

# Edit with your credentials
nano telegram_config.json
```

Paste your token and chat_id:
```json
{
  "bot_token": "123456789:ABCdefGHI...",
  "chat_id": "123456789"
}
```

Save and exit (Ctrl+X, Y, Enter)

## 4. Test (10 seconds)

```bash
python3 monitor_collectors.py --test
```

You should receive a message on Telegram! ✅

## 5. Enable Automatic Monitoring (30 seconds)

```bash
python3 setup_monitoring_cron.py
```

Follow the prompts:
- Choose frequency: **1** (every 5 minutes)
- Add to crontab: **y**

Done! You'll now get alerts if collectors stop. 🎉

## What You'll Get

### When Everything's OK
- No messages (silent monitoring)
- Check `monitoring.log` to see health checks

### When Collector Stops
```
🚨 GDELT Collector Alert

❌ GDELT collector process not running

Consecutive failures: 2
Action: Restart with `./restart_all.sh`
```

### When Collector Stuck
```
⚠️ Alchemy Collector Warning

⚠️ Alchemy log not updated in 120 minutes (expected: 60 min)

May be stuck. Check logs:
`tail -50 alchemy_collection.out`
```

## Useful Commands

```bash
# Check monitoring is running
crontab -l | grep monitor

# View monitoring logs
tail -f monitoring.log

# Run check manually
python3 monitor_collectors.py

# Test alerts
python3 monitor_collectors.py --test
```

## Troubleshooting

**Not receiving test message?**
- Check bot token and chat_id are correct
- Make sure you started a chat with your bot (send /start)
- Check error in terminal output

**Want to change frequency?**
```bash
crontab -e
# Change */5 to */10 for 10-minute intervals
```

**Want to disable?**
```bash
crontab -e
# Delete or comment out the monitor_collectors line
```

For detailed documentation, see **TELEGRAM_SETUP.md**
