# IPO Strategy - Complete Workflow

This document shows the **complete workflow** from zero to live trading.

---

## Overview

```
LOCAL MACHINE              QUANTCONNECT
┌─────────────────┐       ┌──────────────────┐
│                 │       │                  │
│ 1. s1_downloader│──────▶│ 4. data_collection│
│    .ipynb       │ S-1s  │    .ipynb        │
│                 │       │                  │
│ Download S-1    │       │ Parse & collect  │
│ filings         │       │ all other data   │
│                 │       │                  │
│ ⏱️ 1 hour       │       │ ⏱️ 2 hours       │
└─────────────────┘       └──────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │                  │
                          │ 5. research      │
                          │    .ipynb        │
                          │                  │
                          │ Train model      │
                          │                  │
                          │ ⏱️ 1 hour        │
                          └──────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │                  │
                          │ 6. main.py       │
                          │                  │
                          │ Live trading     │
                          │                  │
                          │ ⏱️ Automated     │
                          └──────────────────┘
```

---

## The Three Notebooks

### 1. `s1_downloader.ipynb` 📥
**Where:** LOCAL computer
**Purpose:** Download S-1 filings from SEC EDGAR
**Why separate:** QuantConnect blocks SEC access
**Input:** `data/ipo_calendar.csv`
**Output:** `data/s1_filings/*.html`
**Time:** ~1 hour for 100 IPOs

**Run this first, on your local machine!**

---

### 2. `data_collection.ipynb` 📊
**Where:** QuantConnect Research (or local)
**Purpose:** Collect ALL IPO data for training
**Input:** S-1 files, IPO calendar
**Output:** `data/historical_ipos.csv` (training data)
**Time:** ~2 hours for 100 IPOs

**Run this second, can use QuantConnect.**

---

### 3. `research.ipynb` 🤖
**Where:** QuantConnect Research
**Purpose:** Train ML model
**Input:** `data/historical_ipos.csv`
**Output:** Trained model in Object Store
**Time:** ~1 hour

**Run this third, trains your model.**

---

## Detailed Workflow

### Phase 1: Initial Setup (Week 1)

#### Day 1: Get IPO Calendar
```bash
# Option A: Manual
1. Visit Renaissance Capital
2. Export IPO data (2023-2024)
3. Save as data/ipo_calendar.csv

# Option B: Script
python scripts/collect_ipo_calendar.py --include-defaults
```

**Output:** `data/ipo_calendar.csv` with 50-100 IPOs

---

#### Day 2-3: Download S-1 Filings

**ON YOUR LOCAL COMPUTER:**

```bash
# 1. Install packages
pip install pandas requests beautifulsoup4 lxml tqdm jupyter

# 2. Open notebook
jupyter notebook s1_downloader.ipynb

# 3. Update configuration
YOUR_EMAIL = "your.email@example.com"  # Change this!

# 4. Run all cells
# Takes ~1 hour for 100 IPOs
```

**Output:** `data/s1_filings/*.html` (50-100 files)

**Success check:**
- ✅ 80%+ files downloaded
- ✅ Files are 100-500 KB each
- ✅ Can open in browser and see financial tables

---

#### Day 4-5: Extract Fundamentals

**IN QUANTCONNECT (or locally):**

```python
# Open data_collection.ipynb

# Step 1: Load calendar (already done)
df_calendar = pd.read_csv('data/ipo_calendar.csv')

# Step 2: SKIP - Already downloaded S-1s locally!

# Step 3: Extract fundamentals
# Option A: Manual entry (recommended)
#   - Generate template
#   - Open each S-1 in browser
#   - Enter data into CSV
#   - Takes 10-15 min per IPO

# Option B: Automated parsing (faster but less accurate)
#   - Run parsing cells
#   - Validate results
```

**Output:** `data/raw/s1_manual_fundamentals.csv`

---

### Phase 2: Complete Data Collection (Week 2)

#### Day 1: Price Performance

**IN QUANTCONNECT:**

```python
# data_collection.ipynb Step 4
df_performance = get_all_ipo_performance(df_calendar)
```

**Output:** `data/raw/ipo_performance.csv`
- First-day close price
- 30-day return
- Success label (1 if >10%)

---

#### Day 2: Market Conditions

**IN QUANTCONNECT:**

```python
# data_collection.ipynb Step 5
df_market = collect_market_conditions(df_calendar)
```

**Output:** `data/raw/ipo_market_conditions.csv`
- VIX on IPO date
- SPY 30-day return
- Sector ETF return

---

#### Day 3: Sentiment Analysis

**ANYWHERE:**

```python
# data_collection.ipynb Step 6
# Option A: FinBERT analysis (advanced)
# Option B: Manual news collection
# Option C: Skip for now (use neutral 0.0)
```

**Output:** `data/raw/ipo_sentiment.csv`

---

#### Day 4: Merge & Validate

**IN QUANTCONNECT:**

```python
# data_collection.ipynb Step 7
df_final = merge_all_datasets()
df_final.to_csv('data/historical_ipos.csv')
```

**Output:** `data/historical_ipos.csv` (READY FOR TRAINING!)

**Validation:**
- ✅ At least 100 IPOs
- ✅ <20% missing values
- ✅ Success rate 40-70%
- ✅ All features present

---

### Phase 3: Model Training (Week 3)

#### Day 1-2: Train Model

**IN QUANTCONNECT:**

```python
# Open research.ipynb

# 1. Load data
df = pd.read_csv('data/historical_ipos.csv')

# 2. Train model
model = LGBMClassifier(...)
model.fit(X_train, y_train)

# 3. Validate
auc = roc_auc_score(y_test, predictions)
# Target: AUC > 0.70

# 4. Save model
qb.object_store.save_bytes('ipo_classifier_model', joblib.dumps(model))
```

**Success metrics:**
- ✅ AUC > 0.70
- ✅ Accuracy > 65%
- ✅ Precision > 70%

---

#### Day 3-5: Backtest & Deploy

**IN QUANTCONNECT:**

```python
# 1. Upload main.py, ipocalendar.py, ipoanalyzer.py

# 2. Backtest (2024)
# Verify trades execute correctly

# 3. Paper trade (1 month)
# Monitor live behavior

# 4. Go live (when confident)
# Start with 25% capital
```

---

### Phase 4: Weekly Maintenance (Ongoing)

#### Every Monday: Score New IPOs

**LOCAL OR QUANTCONNECT:**

```python
# 1. Check IPO calendar for upcoming listings
upcoming_ipos = check_ipo_calendar()

# 2. Download S-1s (local machine)
# Use s1_downloader.ipynb

# 3. Extract features
features = extract_all_features(ipo_data)

# 4. Score with model
score = model.predict_proba(features)[0][1]

# 5. Update calendar CSV
df.to_csv('data/ipo_calendar.csv')

# 6. Upload to Object Store
qb.object_store.save('ipo_calendar', csv_content)
```

**Time:** 2-3 hours per week

---

## File Organization

```
IPO Pre-Analysis Day-1 Trading Strategy/
│
├── 📓 NOTEBOOKS
│   ├── s1_downloader.ipynb        ← Run LOCAL first
│   ├── data_collection.ipynb      ← Run in QC second
│   └── research.ipynb             ← Run in QC third
│
├── 🐍 PYTHON MODULES
│   ├── main.py                    ← Trading algorithm
│   ├── ipocalendar.py             ← Custom data class
│   └── ipoanalyzer.py             ← Feature extraction
│
├── 📜 SCRIPTS (optional)
│   ├── collect_ipo_calendar.py
│   └── download_s1_filings.py
│
├── 📁 DATA
│   ├── ipo_calendar.csv           ← START HERE
│   ├── s1_filings/                ← From s1_downloader.ipynb
│   │   ├── ARM_s1.html
│   │   └── RDDT_s1.html
│   ├── raw/                       ← Intermediate files
│   │   ├── s1_manual_fundamentals.csv
│   │   ├── ipo_performance.csv
│   │   ├── ipo_market_conditions.csv
│   │   └── ipo_sentiment.csv
│   └── historical_ipos.csv        ← FINAL TRAINING DATA
│
└── 📖 DOCUMENTATION
    ├── WORKFLOW.md                ← You are here!
    ├── README.md
    ├── QUICK_START.md
    ├── IMPLEMENTATION_GUIDE.md
    ├── DATA_COLLECTION_README.md
    └── S1_DOWNLOAD_GUIDE.md
```

---

## Quick Reference

### Where to Run Each File

| File | Location | Reason |
|------|----------|--------|
| `s1_downloader.ipynb` | LOCAL | QC blocks SEC EDGAR |
| `collect_ipo_calendar.py` | LOCAL | Web scraping blocked in QC |
| `download_s1_filings.py` | LOCAL | Same as above |
| `data_collection.ipynb` | QC or LOCAL | Both work, QC easier for price data |
| `research.ipynb` | QC | Needs QuantBook |
| `main.py` | QC | Trading algorithm |

---

## Common Questions

### Q: Can I skip s1_downloader.ipynb?
**A:** Yes, but you'll need to manually download S-1s from SEC EDGAR (2 min per IPO).

### Q: Can I run everything locally?
**A:** Almost! You need QuantConnect for:
- Price/market data (Steps 4-5 in data_collection)
- Model training (research.ipynb)
- Live trading (main.py)

### Q: What's the minimum viable dataset?
**A:** 50 IPOs from 2024 with manual fundamental entry = ~7 hours work

### Q: How long until I'm live trading?
**A:**
- Fast track: 1-2 weeks (50 IPOs, basic features)
- Recommended: 3-4 weeks (100+ IPOs, all features)
- Comprehensive: 6-8 weeks (300+ IPOs, validated model)

### Q: What if I get stuck?
**A:**
1. Check the specific guide for that step
2. Review error messages in notebook outputs
3. Start with smaller sample (5-10 IPOs)
4. Manual fallback always works

---

## Success Checklist

### Week 1: Data Collection
- [ ] IPO calendar with 50+ tickers
- [ ] S-1 files downloaded (80%+ success)
- [ ] Fundamentals extracted
- [ ] Price performance calculated
- [ ] Market conditions collected
- [ ] Data merged successfully

### Week 2: Model Training
- [ ] Training data validated
- [ ] Model trained (AUC > 0.70)
- [ ] Backtest run successfully
- [ ] Model saved to Object Store

### Week 3: Deployment
- [ ] Algorithm uploaded to QC
- [ ] Parameters configured
- [ ] Paper trading started
- [ ] Monitoring set up

### Week 4+: Live Trading
- [ ] Live capital deployed
- [ ] Weekly IPO scoring workflow
- [ ] Performance tracking
- [ ] Quarterly model retraining

---

## Getting Help

**Documentation:**
- General strategy: `README.md`
- Quick start: `QUICK_START.md`
- Full implementation: `IMPLEMENTATION_GUIDE.md`
- Data collection: `DATA_COLLECTION_README.md`
- S-1 download: `S1_DOWNLOAD_GUIDE.md`
- This workflow: `WORKFLOW.md`

**File-Specific:**
- Issues with s1_downloader: See `S1_DOWNLOAD_GUIDE.md`
- Issues with data_collection: See `DATA_COLLECTION_README.md`
- Issues with model training: See `research.ipynb` notes
- Issues with trading: See `main.py` comments

**Debugging:**
- Start with small sample (5 IPOs)
- Check logs and error messages
- Verify file paths and column names
- Test each step independently

---

## Bottom Line

**To get from zero to live trading:**

1. ⏱️ **Week 1:** Collect historical data (run `s1_downloader.ipynb` locally, then `data_collection.ipynb` in QC)

2. ⏱️ **Week 2:** Train model (run `research.ipynb` in QC)

3. ⏱️ **Week 3:** Deploy & test (run `main.py` in QC)

4. ⏱️ **Week 4+:** Live trade & maintain (score new IPOs weekly)

**Total initial time:** 20-30 hours spread over 3-4 weeks

**Weekly maintenance:** 2-3 hours

Good luck! 🚀
