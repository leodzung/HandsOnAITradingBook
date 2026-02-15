# Snapshot Collector Telegram Alerts - User Guide

**Date:** 2026-02-15
**Status:** ✅ Complete

---

## Overview

The Market Snapshot Collector now includes **comprehensive Telegram alerts** to keep you informed about data collection progress, labeling milestones, and training readiness.

### Why Alerts Matter

Training data collection happens in the background, and you need to know:
- ✅ When enough data is collected for model retraining
- ✅ When markets resolve and outcomes are labeled
- ✅ If data collection is progressing normally
- ✅ When milestones are reached

**With alerts**, you get real-time notifications without constantly checking `view_snapshots.py`.

---

## Alert Types

### 1. **Milestone Alerts** 📊

Sent when snapshot counts reach key milestones.

**Default milestones:** 100, 500, 1,000, 5,000, 10,000 snapshots

**Example:**
```
📊 DATA COLLECTION MILESTONE

Total Snapshots: 1,000
Unique Markets: 234
Labeled: 45 (4.5%)
Trades Blocked: 800

By Bot:
  • price_level: 1,000 snapshots

Status: Milestone 1,000 reached! 🎉
```

### 2. **Labeling Progress Alerts** 🏷️

Sent every 50 labeled samples to track model training readiness.

**Trigger:** Every 50, 100, 150, 200... labeled samples

**Example:**
```
🏷️ LABELING PROGRESS UPDATE

Labeled Samples: 150
Unlabeled: 850
Total: 1,000
Progress: 15.0%

Need 50 more for training readiness
```

### 3. **Training Ready Alert** 🚀

Sent once when 200+ labeled samples are available (minimum for model retraining).

**Trigger:** First time labeled count >= 200

**Example:**
```
🚀 TRAINING DATASET READY

Labeled Samples: 234
Unique Markets: 156
Labeling Rate: 23.4%

By Bot:
  • price_level: 234 labeled

Next Steps:
1. Export: python3 view_snapshots.py --export training.csv --labeled-only
2. Train new model with real-world data
3. Deploy improved model

Status: Minimum viable training dataset achieved! 🎓
```

### 4. **Outcome Recorded Alerts** 🏁

Sent for the first 10 market resolutions to confirm outcome labeling works.

**Trigger:** First 10 times `record_outcome()` is called

**Example:**
```
🏁 MARKET RESOLVED

Market ID: 0x1234567890abcdef...
Outcome: YES
Snapshots Labeled: 3
Total Labeled: 7

Progress: 0.7% of data labeled
```

### 5. **Daily Summary** 📈

Comprehensive daily report (requires manual scheduling).

**Example:**
```
📈 DAILY DATA COLLECTION SUMMARY

Total Snapshots: 1,234
Unique Markets: 456
Labeled: 234 (19.0%)
Unlabeled: 1,000
Trades Executed: 234
Trades Blocked: 1,000

Data Range:
  First: 2026-02-10
  Last: 2026-02-15

By Bot Type:
  • price_level: 1,234 total, 234 labeled
```

---

## Setup

### Automatic Alerts (Already Enabled)

If you have Telegram notifications enabled for the price-level bot, snapshot alerts are **automatically active**.

**Verify in config:**
```json
// config/config_price_levels.json
{
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  }
}
```

**That's it!** Alerts will be sent automatically when:
- New snapshots are logged
- Markets resolve and outcomes are recorded
- Milestones are reached

### Manual Daily Summary (Optional)

To receive daily summaries, create a cron job or scheduler:

**Option 1: Cron Job**
```bash
# Add to crontab (runs daily at 8 AM)
0 8 * * * cd /path/to/project && python3 scripts/send_daily_snapshot_summary.py
```

**Option 2: Python Script**
```python
# scripts/send_daily_snapshot_summary.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ml.snapshot_collector import MarketSnapshotCollector
from monitoring.telegram_notifier import TelegramNotifier
import json

# Load config
with open('config/config_price_levels.json') as f:
    config = json.load(f)

# Initialize Telegram
telegram_config = config['telegram']
telegram = TelegramNotifier(
    bot_token=telegram_config['bot_token'],
    chat_id=telegram_config['chat_id'],
    enabled=telegram_config['enabled']
)

# Send summary
collector = MarketSnapshotCollector(telegram=telegram)
collector.send_daily_summary()
print("Daily summary sent!")
```

---

## Customization

### Change Milestone Thresholds

**Default:** 100, 500, 1000, 5000, 10000

**Custom milestones:**
```python
# In trader_price_levels.py __init__
self.snapshot_collector = MarketSnapshotCollector(
    db_path='data/market_snapshots.db',
    telegram=self.telegram,
    alert_milestones=[50, 100, 250, 500, 1000, 2500]  # Custom
)
```

### Disable Specific Alerts

Alerts are triggered automatically, but you can:

**1. Disable all alerts:**
```python
# Pass telegram=None
self.snapshot_collector = MarketSnapshotCollector(
    db_path='data/market_snapshots.db',
    telegram=None  # No alerts
)
```

**2. Filter by bot type:**

Alerts include bot-specific breakdowns, so you can see which bot is generating data.

---

## Alert Frequency

| Alert Type | Frequency | Can Disable? |
|------------|-----------|--------------|
| Milestone | Once per milestone | Change thresholds |
| Labeling Progress | Every 50 labeled samples | No (automatic) |
| Training Ready | Once at 200 labeled | No (automatic) |
| Outcome Recorded | First 10 resolutions | No (automatic) |
| Daily Summary | Manual (cron) | Yes (don't schedule) |

### Smart Rate Limiting

- **Milestones:** Only alerted once per threshold (tracked in memory)
- **Labeling progress:** Every 50 samples (not too spammy)
- **Outcome recorded:** Only first 10 (then relies on labeling progress alerts)
- **Training ready:** Only once when threshold crossed

**Result:** You get timely updates without spam!

---

## What Alerts Tell You

### Early Days (Week 1)

**Expected alerts:**
```
📊 Milestone: 100 snapshots
📊 Milestone: 500 snapshots
📊 Milestone: 1,000 snapshots
🏁 Market resolved (first few)
```

**What this means:**
- Data collection is working ✅
- Bot is analyzing markets ✅
- Outcomes starting to be recorded ✅

### Mid-Term (Week 2-4)

**Expected alerts:**
```
🏷️ Labeling Progress: 50 labeled
🏷️ Labeling Progress: 100 labeled
🏷️ Labeling Progress: 150 labeled
🏷️ Labeling Progress: 200 labeled
🚀 TRAINING DATASET READY
```

**What this means:**
- Markets are resolving ✅
- Outcomes being labeled ✅
- **Ready to retrain model!** 🎓

### Long-Term (Month 2+)

**Expected alerts:**
```
📊 Milestone: 5,000 snapshots
🏷️ Labeling Progress: 500 labeled
📈 Daily Summary (if scheduled)
```

**What this means:**
- Large dataset accumulated ✅
- Continuous learning data ✅
- Ready for production model v2 ✅

---

## Troubleshooting

### Not Receiving Alerts

**Check 1: Telegram config**
```bash
# Verify config has Telegram enabled
cat config/config_price_levels.json | grep -A 3 telegram
```

**Check 2: Bot is running**
```bash
ps aux | grep trader_price_levels
```

**Check 3: Snapshots being logged**
```bash
python3 view_snapshots.py
# Should show Total Snapshots > 0
```

**Check 4: Telegram notifier works**
```python
# Test Telegram separately
from monitoring.telegram_notifier import TelegramNotifier

telegram = TelegramNotifier(
    bot_token="YOUR_TOKEN",
    chat_id="YOUR_CHAT_ID",
    enabled=True
)
telegram.send_message("<b>Test Alert</b>\n\nIf you see this, Telegram works!")
```

### Getting Too Many Alerts

**This shouldn't happen** due to rate limiting, but if it does:

**Option 1: Increase milestone thresholds**
```python
alert_milestones=[1000, 5000, 10000]  # Only major milestones
```

**Option 2: Disable outcome recorded alerts**

(These auto-stop after 10 resolutions anyway)

### Missing Training Ready Alert

**Possible reasons:**
1. **Not enough labeled data yet** - Check: `python3 view_snapshots.py`
2. **Alert already sent** - Only sent once at 200 labeled
3. **Bot restarted** - Milestone tracking is in-memory (resets on restart)

**Solution:**
Check statistics manually:
```bash
python3 view_snapshots.py
# If "Labeled (ready): 200+" → you're ready to train!
```

---

## Example Alert Timeline

### Day 1
```
✅ Bot started with alerts enabled
📊 Milestone: 100 snapshots (2 hours)
🏁 Market resolved: 0x123... → YES
📊 Milestone: 500 snapshots (12 hours)
```

### Day 7
```
📊 Milestone: 1,000 snapshots
🏷️ Labeling Progress: 50 labeled
🏁 Market resolved: 0x456... → NO
```

### Day 14
```
🏷️ Labeling Progress: 100 labeled
🏷️ Labeling Progress: 150 labeled
```

### Day 21
```
🏷️ Labeling Progress: 200 labeled
🚀 TRAINING DATASET READY
  → Time to export and retrain model!
```

### Day 30
```
📊 Milestone: 5,000 snapshots
🏷️ Labeling Progress: 300 labeled
📈 Daily Summary (if scheduled)
```

---

## Best Practices

### 1. Monitor Early Alerts

In the first week, watch for:
- ✅ Milestone alerts (confirms logging works)
- ✅ First outcome recorded (confirms labeling works)

**If you don't see these within 24 hours, check the bot logs.**

### 2. Act on Training Ready Alert

When you receive **🚀 TRAINING DATASET READY**:

```bash
# 1. Export data
python3 view_snapshots.py --export training_data.csv --labeled-only

# 2. Retrain model
python3 scripts/train_price_level_model.py --data training_data.csv

# 3. Deploy new model
# (backup old model first)
mv data/price_level_model.pkl data/price_level_model_v1_backup.pkl
mv data/price_level_model_v2.pkl data/price_level_model.pkl

# 4. Restart bot
pkill -f trader_price_levels
nohup python3 src/bots/trader_price_levels.py >> logs/trader_price_levels.log 2>&1 &
```

### 3. Schedule Daily Summaries

Once data collection is stable (after week 1), add daily summaries to track progress:

```bash
# crontab -e
0 8 * * * cd /path/to/project && python3 scripts/send_daily_snapshot_summary.py
```

### 4. Keep Alert History

Telegram alerts are your **data collection audit trail**. They show:
- When collection started
- Progress over time
- When milestones were hit
- When training became possible

**Don't delete old messages** - they're valuable for debugging and tracking progress.

---

## Alert Format Reference

All alerts use **HTML formatting** for readability:

```
<b>Bold headers</b>
<b>Metric:</b> Value
  • Bullet points
  - Dashes

Status: Human-readable summary
```

**Emoji key:**
- 📊 Data collection milestones
- 🏷️ Labeling progress
- 🚀 Training readiness
- 🏁 Market resolutions
- 📈 Daily summaries
- ✅ Success status
- 🎉 Celebrations
- 🎓 Training ready

---

## Summary

**Telegram alerts keep you informed about:**
1. ✅ Data collection progress (milestones)
2. ✅ Labeling progress (outcomes recorded)
3. ✅ Training readiness (200+ labeled samples)
4. ✅ Daily summaries (optional)

**Setup:** Already enabled if Telegram is configured!

**Customization:** Change milestone thresholds or schedule daily summaries.

**Best practice:** Monitor early alerts to verify everything works, then act on training ready alerts.

---

**Created:** 2026-02-15
**Status:** Production-ready ✅
