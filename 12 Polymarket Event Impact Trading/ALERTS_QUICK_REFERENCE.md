# Snapshot Collector Alerts - Quick Reference Card

**Added:** 2026-02-15 | **Status:** ✅ Ready

---

## Alert Types

| Alert | When | Example Count |
|-------|------|---------------|
| 📊 **Milestone** | 100, 500, 1K, 5K, 10K snapshots | Once per threshold |
| 🏷️ **Labeling Progress** | Every 50 labeled samples | 50, 100, 150, 200... |
| 🚀 **Training Ready** | 200+ labeled samples | Once only |
| 🏁 **Outcome Recorded** | Market resolves | First 10 only |
| 📈 **Daily Summary** | Manual/scheduled | As scheduled |

---

## What Each Alert Means

### 📊 Milestone Alert
**What it means:** Data collection is progressing normally
**What to do:** Nothing - just confirms everything works

### 🏷️ Labeling Progress
**What it means:** Markets are resolving and being labeled
**What to do:** If < 200, wait. If >= 200, see Training Ready

### 🚀 Training Ready
**What it means:** You have enough data to retrain the model!
**What to do:**
```bash
# 1. Export data
python3 view_snapshots.py --export training.csv --labeled-only

# 2. Retrain model
python3 scripts/train_price_level_model.py --data training.csv

# 3. Deploy new model
mv data/price_level_model.pkl data/price_level_model_v1_backup.pkl
mv data/price_level_model_v2.pkl data/price_level_model.pkl

# 4. Restart bot
pkill -f trader_price_levels
nohup python3 src/bots/trader_price_levels.py >> logs/trader_price_levels.log 2>&1 &
```

### 🏁 Outcome Recorded
**What it means:** Outcome labeling is working
**What to do:** Nothing - just confirms labeling works

### 📈 Daily Summary
**What it means:** Overview of collection progress
**What to do:** Review metrics, check everything looks healthy

---

## Setup Checklist

- [x] Telegram enabled in config (`telegram.enabled: true`)
- [x] Bot running (`ps aux | grep trader_price_levels`)
- [x] Snapshots being logged (`python3 view_snapshots.py`)
- [ ] Received first alert (wait for 100 snapshots)

---

## Expected Timeline

| Day | Alert | Action |
|-----|-------|--------|
| 1 | 📊 100 snapshots | ✓ Confirms logging works |
| 2-3 | 📊 500, 1000 snapshots | ✓ Data accumulating |
| 7 | 🏷️ 50 labeled | ✓ Markets resolving |
| 14 | 🏷️ 100 labeled | ✓ Halfway to training |
| 21 | 🏷️ 150 labeled | ✓ Almost ready |
| **21-30** | **🚀 200 labeled** | **→ RETRAIN MODEL** |
| 30+ | 📊 5000 snapshots | ✓ Large dataset |

---

## Customization

**Change milestone thresholds:**
```python
# In trader_price_levels.py __init__
self.snapshot_collector = MarketSnapshotCollector(
    db_path='data/market_snapshots.db',
    telegram=self.telegram,
    alert_milestones=[50, 100, 500, 1000]  # Custom
)
```

**Disable alerts:**
```python
self.snapshot_collector = MarketSnapshotCollector(
    db_path='data/market_snapshots.db',
    telegram=None  # No alerts
)
```

**Enable daily summaries:**
```bash
# crontab -e
0 8 * * * cd /path/to/project && python3 scripts/send_daily_snapshot_summary.py
```

---

## Troubleshooting

**Not receiving alerts?**
1. Check Telegram enabled: `cat config/config_price_levels.json | grep telegram`
2. Check bot running: `ps aux | grep trader_price_levels`
3. Check data logged: `python3 view_snapshots.py`

**Too many alerts?**
- Check for duplicate bot instances: `ps aux | grep trader_price_levels`
- Increase milestone thresholds (see Customization)

---

## Files Reference

| File | Purpose |
|------|---------|
| `SNAPSHOT_ALERTS_GUIDE.md` | Complete user guide |
| `SNAPSHOT_ALERTS_IMPLEMENTATION.md` | Technical details |
| `ALERTS_QUICK_REFERENCE.md` | This file |
| `scripts/send_daily_snapshot_summary.py` | Daily summary script |

---

## Quick Commands

```bash
# View statistics
python3 view_snapshots.py

# Export training data
python3 view_snapshots.py --export training.csv --labeled-only

# Send daily summary manually
python3 scripts/send_daily_snapshot_summary.py

# Check bot logs
tail -f logs/trader_price_levels.log | grep snapshot
```

---

**Questions?** See `SNAPSHOT_ALERTS_GUIDE.md` for detailed documentation.
