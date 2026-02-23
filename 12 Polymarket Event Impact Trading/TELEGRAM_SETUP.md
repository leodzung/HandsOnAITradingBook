# Telegram Monitoring Setup

The monitoring system can send alerts to Telegram when collectors fail or data becomes stale.

## Quick Setup (5 minutes)

### Step 1: Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow prompts to name your bot (e.g., "Polymarket Monitor")
4. Copy the **bot token** (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Get Your Chat ID

1. Open Telegram and search for `@userinfobot`
2. Send `/start` command
3. Copy your **chat ID** (looks like `123456789` or `-123456789`)

### Step 3: Create Config File

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"

# Copy template
cp telegram_config.json.template telegram_config.json

# Edit with your credentials
nano telegram_config.json
```

**telegram_config.json:**
```json
{
  "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
  "chat_id": "123456789"
}
```

### Step 4: Test Alerts

```bash
python3 src/monitoring/monitor_collectors.py --test
```

You should receive a test message in Telegram!

## What Gets Monitored

The monitoring system checks:

✅ **Collectors Running**
- GDELT collector process alive
- Alchemy collector process alive

✅ **Data Freshness**
- GDELT: Last update < 1 hour ago
- Alchemy: Last trade < 1 hour ago

✅ **Database Health**
- Data still growing (not stuck)
- No corruption detected

✅ **System Resources**
- CPU usage < 80% (not stuck in loop)
- Disk space available

## Alert Examples

**Collector Down:**
```
🚨 GDELT Collector DOWN
Process not running
Last update: 2 hours ago
Action: Restart with:
nohup python3 src/collectors/gdelt_collector.py --continuous >> logs/gdelt.out 2>&1 &
```

**Stale Data:**
```
⚠️ Data Staleness Warning
GDELT: 3 hours since last update
Alchemy: OK (5 min ago)
```

**All OK:**
```
✅ All Collectors Healthy
GDELT: 2 min ago (7.7M events)
Alchemy: 5 min ago (9.4M trades)
```

## Running Without Telegram

The monitor works without Telegram - it just prints to console:

```bash
python3 src/monitoring/monitor_collectors.py

# Output:
ℹ️  Telegram not enabled. Would send: [Alert message]
```

## Disabling Telegram

To disable Telegram (but keep monitoring):

```bash
# Rename config to disable
mv telegram_config.json telegram_config.json.disabled

# Or delete it
rm telegram_config.json
```

## Troubleshooting

### "Telegram config not found"
- Create `telegram_config.json` using template above
- Ensure it's in the project root directory

### "Failed to send Telegram alert"
- Check bot token is correct
- Verify chat ID is correct
- Ensure bot can send messages to you (start a chat with your bot first)
- Check internet connection

### "Telegram config incomplete"
- Both `bot_token` and `chat_id` must be set
- Remove placeholder text like "YOUR_BOT_TOKEN_HERE"

## Privacy & Security

⚠️ **Important:**
- Keep `telegram_config.json` private (contains API credentials)
- Add to `.gitignore` to prevent committing to GitHub
- Never share your bot token publicly

The config file is already in `.gitignore` by default.
