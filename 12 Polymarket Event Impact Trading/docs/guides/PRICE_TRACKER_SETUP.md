# Price Tracker - Complete Setup Guide

## 🎯 What This Does

The price tracker automatically:
1. Records every event-market match you find
2. Tracks prices 1h, 6h, and 24h after the event
3. Labels outcomes as UP/DOWN/NEUTRAL based on real price movements
4. Exports labeled data for model retraining

**Result:** Real training data with actual outcomes (not synthetic labels!)

---

## ✅ Step 1: Verify Files Created

Check that these files exist:

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/12 Polymarket Event Impact Trading"

ls -lh price_tracker.py         # Main tracker
ls -lh check_outcomes.py        # Cron job script
ls -lh view_tracking_stats.py   # Stats viewer
```

All files should be there ✅

---

## ✅ Step 2: Test the Tracker

Test that the tracker works:

```bash
python3 price_tracker.py
```

**Expected output:**
```
======================================================================
PRICE TRACKER - Status Check
======================================================================

📊 Tracking Statistics:
  Total tracked:    0
  Completed:        0
  Pending:          0

======================================================================
```

If you see this, the tracker is working! ✅

---

## ✅ Step 3: Integration Already Done

I've already integrated the tracker into `trader.py`:

- ✅ Import added
- ✅ Tracker initialized in `__init__`
- ✅ Tracking call added in `process_signal`

**No action needed** - it's ready to use!

---

## ✅ Step 4: Start the Trading Bot

Start the bot to begin collecting data:

```bash
# Option A: Run in foreground (see output)
python3 trader.py

# Option B: Run in background (keeps running)
nohup python3 trader.py > trading.out 2>&1 &
```

**What happens:**
- Bot finds event-market matches
- Each match is automatically tracked
- Prices recorded at entry time
- Bot continues running every 5 minutes

**Let it run!** The longer it runs, the more data you collect.

---

## ✅ Step 5: Set Up Cron Job (Automatic Price Checking)

The cron job checks prices hourly and updates outcomes.

### Make script executable:
```bash
chmod +x check_outcomes.py
```

### Test it manually:
```bash
python3 check_outcomes.py
```

**Expected output:**
```
======================================================================
CHECKING PRICE OUTCOMES
======================================================================
Total tracked: 0
Pending: 0
Completed: 0
No pending entries to check
Check complete
```

### Set up cron job to run hourly:

```bash
# Open crontab editor
crontab -e
```

**Add this line:**
```bash
0 * * * * cd /Users/leole/workspace/HandsOnAITradingBook/12\ Polymarket\ Event\ Impact\ Trading && /usr/bin/python3 check_outcomes.py >> cron_output.log 2>&1
```

**What this does:**
- Runs every hour (at :00)
- Changes to your project directory
- Runs check_outcomes.py
- Logs output to cron_output.log

**Save and exit** (`:wq` in vim, or Ctrl+X in nano)

### Verify cron job is set:
```bash
crontab -l
```

You should see your cron entry ✅

---

## ✅ Step 6: Monitor Progress

### View statistics:
```bash
python3 view_tracking_stats.py
```

**Example output after a few hours:**
```
======================================================================
PRICE TRACKING STATISTICS
======================================================================

📊 OVERALL:
  Total tracked:       15
  Completed:           2
  Pending:             13

📋 LABEL DISTRIBUTION:
  UP (+1):       1  ( 50.0%)
  NEUTRAL (0):   0  (  0.0%)
  DOWN (-1):     1  ( 50.0%)

⏱️  RECENT ACTIVITY:
  Last 24 hours: 15 events tracked

✅ RECENTLY COMPLETED:
  1. Bitcoin Surges to $95K on Institutional Buying
     Bitcoin to reach $100K in 2025?
     $0.450 → $0.520 (+15.6%) ↗ UP

⏳ PENDING BY AGE:
  < 1h   : 5
  1-6h   : 4
  6-24h  : 4
```

### Check bot logs:
```bash
tail -f trader.log
```

**Look for:**
```
2025-12-28 17:00:04 - INFO - → Tracking price movement for: Fed emergency rate cut in 2025?...
```

### Check cron job logs:
```bash
tail -f cron_output.log
```

---

## ✅ Step 7: Wait for Data Collection

**How long to wait:**

| Time Running | Expected Data |
|--------------|---------------|
| 1 day | 5-15 tracked events |
| 3 days | 15-45 tracked events, 5-15 completed |
| 7 days | 50-150 tracked events, 20-50 completed |
| 14 days | 100-300 tracked events, 50-100 completed ✅ |

**Target:** 100+ completed samples for retraining

---

## ✅ Step 8: Export Labeled Data

Once you have 10+ completed samples:

```bash
python3 price_tracker.py
```

This will automatically export to: `data/labeled_dataset.csv`

**Or export manually:**
```python
from price_tracker import PriceTracker

tracker = PriceTracker()
tracker.export_to_csv('data/labeled_dataset.csv')
```

### Check the exported file:
```bash
head data/labeled_dataset.csv
wc -l data/labeled_dataset.csv  # Count rows
```

---

## ✅ Step 9: Retrain Model (After 100+ Samples)

Once you have 100+ labeled samples:

```bash
python3 train_on_real_data.py
```

**But update it to use real labels:**

```python
# In train_on_real_data.py, replace create_synthetic_labels() with:

def load_real_labels():
    """Load real labeled data from price tracker"""
    df = pd.read_csv('data/labeled_dataset.csv')

    # Use actual_outcome column (already labeled by tracker)
    print(f"Loaded {len(df)} real labeled samples")
    print(f"\nLabel distribution:")
    print(df['actual_outcome'].value_counts())

    return df
```

Then:
```bash
python3 train_on_real_data.py
```

**Expected result:**
- New model: `production_model_v2.pkl`
- Accuracy: 70%+ (vs 65% on synthetic)
- Trained on REAL price movements

---

## 🔍 How It Works

### Tracking Flow:

```
1. Bot detects event-market match
   ↓
2. Tracker records:
   - Event details (title, source, time)
   - Market details (question, ID, volume)
   - All 8 ML features
   - Current price (entry_price)
   - Timestamp (entry_time)
   ↓
3. Saved to SQLite database
   Status: PENDING
   ↓
4. Cron job runs every hour:
   ↓
5. For each pending entry, check:
   - If 1h elapsed → record price_1h
   - If 6h elapsed → record price_6h
   - If 24h elapsed → record price_24h AND label outcome
   ↓
6. Label outcome:
   - Change > +3% → UP (+1)
   - Change < -3% → DOWN (-1)
   - Change between -3% to +3% → NEUTRAL (0)
   ↓
7. Status: COMPLETED
   ↓
8. Export to CSV when 10+ completed
   ↓
9. Use for model retraining
```

---

## 📊 Database Schema

Data stored in: `data/price_tracking.db`

**Table: tracked_events**
```sql
id                     INTEGER PRIMARY KEY
tracking_id            TEXT UNIQUE          -- "market_id_event_id"
event_title            TEXT                 -- "Bitcoin Surges..."
event_source           TEXT                 -- "Bloomberg"
event_time             TIMESTAMP
market_id              TEXT
market_question        TEXT
token_id               TEXT

-- Features (8 features for ML)
sentiment_score        REAL
sentiment_magnitude    REAL
source_credibility     REAL
title_length           INTEGER
has_description        INTEGER
keyword_overlap        INTEGER
market_volume          REAL
market_volume_log      REAL

-- Prices
entry_price            REAL                 -- Price when event detected
price_1h               REAL                 -- Price 1 hour later
price_6h               REAL                 -- Price 6 hours later
price_24h              REAL                 -- Price 24 hours later

-- Outcome
actual_outcome         INTEGER              -- 1=UP, 0=NEUTRAL, -1=DOWN

-- Tracking metadata
completed              INTEGER DEFAULT 0    -- 0=pending, 1=done
last_checked           TIMESTAMP
created_at             TIMESTAMP
```

---

## 🛠️ Useful Commands

### View all tracked events:
```bash
sqlite3 data/price_tracking.db "SELECT event_title, market_question, entry_price, price_24h, actual_outcome FROM tracked_events LIMIT 10;"
```

### Count completed:
```bash
sqlite3 data/price_tracking.db "SELECT COUNT(*) FROM tracked_events WHERE completed = 1;"
```

### View label distribution:
```bash
sqlite3 data/price_tracking.db "SELECT actual_outcome, COUNT(*) FROM tracked_events WHERE completed = 1 GROUP BY actual_outcome;"
```

### Check pending:
```bash
sqlite3 data/price_tracking.db "SELECT COUNT(*) FROM tracked_events WHERE completed = 0;"
```

### Delete all data (reset):
```bash
rm data/price_tracking.db
python3 price_tracker.py  # Recreate database
```

---

## 🐛 Troubleshooting

### Problem: No events being tracked

**Solution:**
```bash
# Check if bot is running
ps aux | grep trader.py

# Check logs
tail -f trader.log

# Look for this line:
# "→ Tracking price movement for: ..."

# If not seeing it, check for errors in log
```

### Problem: Cron job not running

**Solution:**
```bash
# Check cron is running
pgrep cron

# Check cron logs
tail -f cron_output.log

# Test manually
python3 check_outcomes.py

# Verify cron entry
crontab -l
```

### Problem: Database locked

**Solution:**
```bash
# Stop bot
pkill -f trader.py

# Run check manually
python3 check_outcomes.py

# Restart bot
nohup python3 trader.py > trading.out 2>&1 &
```

### Problem: Not enough data

**Solution:**
- Lower `min_confidence` in config.json (0.65 → 0.55)
- Increase `event_lookback_hours` (1 → 3)
- Add more RSS feeds
- Run bot longer (need 7-14 days minimum)

---

## 📈 Expected Results

### After 1 Week:
- 30-100 tracked events
- 10-30 completed samples
- Can start analyzing patterns

### After 2 Weeks:
- 100-200 tracked events
- 50-100 completed samples ✅
- **Ready to retrain model**
- Expected accuracy improvement: 65% → 70%+

### After 1 Month:
- 200-400 tracked events
- 100-200 completed samples
- **Ready for production**
- Expected accuracy: 70-75%
- Can start live trading (if Sharpe > 1.0)

---

## ✅ Quick Start Checklist

- [ ] Files created (price_tracker.py, check_outcomes.py, etc.)
- [ ] Tested: `python3 price_tracker.py` works
- [ ] Integration verified in trader.py
- [ ] Started trading bot: `python3 trader.py` or background
- [ ] Set up cron job: `crontab -e`
- [ ] Verified cron: `crontab -l`
- [ ] Monitoring: `python3 view_tracking_stats.py`
- [ ] Check logs: `tail -f trader.log`
- [ ] Wait 7-14 days for data
- [ ] Export when 100+ samples: `python3 price_tracker.py`
- [ ] Retrain model: `python3 train_on_real_data.py`

---

## 🎯 Success Criteria

**You're ready to retrain when:**
- ✅ 100+ completed samples
- ✅ Label distribution balanced (not all UP or all DOWN)
- ✅ Data spans multiple days/weeks
- ✅ Various market types represented

**Then:**
1. Export data: `python3 price_tracker.py`
2. Retrain model: `python3 train_on_real_data.py`
3. Update config: `"model_path": "production_model_v2.pkl"`
4. Continue paper trading with new model
5. Validate improvement in accuracy

---

**The tracker is now set up and ready! Start the bot and let it collect data.** 🚀
