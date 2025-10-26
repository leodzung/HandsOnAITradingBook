# IPO Data Collection Guide

This guide helps you collect historical IPO data for training the model.

## Quick Start

### Option 1: Use the Notebook (Recommended for Beginners)

1. Open `data_collection.ipynb` in QuantConnect Research
2. Follow the step-by-step workflow
3. Each section collects a specific type of data
4. Takes 4-6 hours for 100 IPOs

### Option 2: Use Python Scripts (For Automation)

```bash
# 1. Collect IPO calendar
python scripts/collect_ipo_calendar.py --include-defaults --output data/ipo_calendar.csv

# 2. Download S-1 filings
python scripts/download_s1_filings.py --input data/ipo_calendar.csv --output data/s1_filings/

# 3. Collect remaining data in notebook
# Open data_collection.ipynb and run Steps 3-7
```

## Data Collection Workflow

### Step 1: IPO Calendar (30 minutes)

**Goal:** Get list of 100-300 IPOs with basic info

**Method A - Manual (Easiest):**
1. Visit https://www.renaissancecapital.com/IPO-Center/IPO-Performance
2. Filter by year (2023-2024)
3. Export to Excel/CSV
4. Save as `data/raw/ipo_calendar_manual.csv`

**Method B - Script (Faster for bulk):**
```bash
python scripts/collect_ipo_calendar.py --include-defaults --output data/ipo_calendar.csv
```

**Required columns:**
- ticker
- company
- ipo_date
- offer_price
- sector

**Example:**
```csv
ticker,company,ipo_date,offer_price,sector
ARM,Arm Holdings,2023-09-14,51.00,Technology
RDDT,Reddit Inc,2024-03-21,34.00,Technology
```

---

### Step 2: S-1 Filings (1-2 hours)

**Goal:** Download SEC filings containing financial data

**Automated Download:**
```bash
# Update USER_AGENT in download_s1_filings.py with your email first!
python scripts/download_s1_filings.py --input data/ipo_calendar.csv --output data/s1_filings/
```

**Manual Download (if script fails):**
1. For each ticker, visit: `https://www.sec.gov/cgi-bin/browse-edgar?company=TICKER&type=S-1`
2. Find most recent S-1 or S-1/A filing
3. Click "Documents" button
4. Download HTML version
5. Save as `data/s1_filings/TICKER_s1.html`

**Success metric:** Have S-1 files for at least 80% of IPOs

---

### Step 3: Extract Fundamentals (2-3 hours)

**Goal:** Parse financial metrics from S-1 filings

**Method A - Manual Entry (Recommended for accuracy):**

1. Open `data/raw/s1_manual_entry_template.csv` (generated in notebook)
2. For each IPO:
   - Open S-1 filing
   - Find "Summary Financial Data" table (usually page 10-15)
   - Enter values for most recent fiscal year
3. Save as `data/raw/s1_manual_fundamentals.csv`

**Key metrics to extract:**
- Revenue (last 2 years → calculate growth)
- Gross profit → calc gross margin
- Operating income → calc operating margin
- Net income → is profitable?
- Cash and equivalents
- Total debt
- Employees
- Founded year

**Method B - Automated Parsing (Less accurate):**
- Use parsing code in `data_collection.ipynb` Step 3
- Requires regex pattern matching
- Needs manual validation

**Time:** ~10-15 minutes per IPO for manual entry

---

### Step 4: Price Performance (30 minutes)

**Goal:** Calculate 30-day returns (target variable)

**Method:** Run in `data_collection.ipynb` Step 4

This uses QuantConnect to get historical prices:
1. First-day closing price
2. Price 30 trading days later
3. Calculate return
4. Binary target: 1 if return > 10%, else 0

**Output:** `data/raw/ipo_performance.csv`

---

### Step 5: Market Conditions (15 minutes)

**Goal:** Capture market environment at IPO date

**Method:** Run in `data_collection.ipynb` Step 5

Collects:
- VIX level on IPO date
- SPY 30-day return (prior to IPO)
- Sector ETF 30-day return
- IPO market temperature

**Output:** `data/raw/ipo_market_conditions.csv`

---

### Step 6: Sentiment Data (1-2 hours)

**Goal:** News sentiment using FinBERT

**Method A - Manual News Collection:**
1. For each IPO, Google: "[company] IPO news"
2. Collect 5-10 headlines from month before IPO
3. Copy text into sentiment analyzer
4. Average scores

**Method B - Automated (if you have news API):**
- Use NewsAPI, AlphaSense, or similar
- Code provided in `data_collection.ipynb` Step 6
- Run through FinBERT model

**Quick Alternative:**
- Start with neutral sentiment (0.0) for all
- Train model without sentiment features
- Add sentiment later to improve model

**Output:** `data/raw/ipo_sentiment.csv`

---

### Step 7: Merge & Validate (30 minutes)

**Method:** Run in `data_collection.ipynb` Step 7

Merges all datasets:
- Calendar + Fundamentals
- + Performance (target)
- + Market Conditions
- + Sentiment

**Validation checks:**
- Missing values < 20%
- Success rate 40-70% (balanced)
- No obvious errors (negative revenues, etc.)

**Output:** `data/historical_ipos.csv` (ready for training!)

---

## Data Quality Checklist

Before training, verify:

- [ ] At least 100 IPOs collected
- [ ] All IPOs have ticker, IPO date, offer price
- [ ] At least 80% have fundamental data
- [ ] All have 30-day return data (target)
- [ ] Market conditions filled
- [ ] Success rate between 40-70%
- [ ] No data leakage (only pre-IPO data used)

---

## Common Issues & Solutions

### Issue: Can't find S-1 filing on SEC

**Solution:**
- Company may have filed under different name
- Search by CIK number instead
- Check for S-1/A (amended) filings
- Some companies use F-1 (foreign issuers)

### Issue: S-1 financial tables are confusing

**Solution:**
- Look for "Summary Financial Data" section
- Use most recent fiscal year
- Watch for units (thousands vs. millions)
- When in doubt, check 10-K (filed after IPO)

### Issue: QuantConnect can't find ticker

**Solution:**
- Stock may have been delisted
- Check if ticker changed post-IPO
- Skip this IPO (aim for 80% success rate)

### Issue: Very low model accuracy

**Solution:**
- Need more data (target 200+ IPOs)
- Improve feature quality (manual review)
- Add more features (sentiment, deal characteristics)

---

## Time Estimates

| Task | Manual | Semi-Auto | Automated |
|------|--------|-----------|-----------|
| IPO Calendar | 30 min | 15 min | 5 min |
| S-1 Download | 2 hours | 1 hour | 30 min |
| Fundamentals | 20 hours | 10 hours | N/A* |
| Price Data | N/A | 30 min | 30 min |
| Market Data | N/A | 15 min | 15 min |
| Sentiment | 5 hours | 2 hours | 1 hour |
| Merge & Validate | 30 min | 30 min | 30 min |
| **Total (100 IPOs)** | **28 hours** | **14 hours** | **3 hours*** |

*Automated fundamental extraction needs manual validation

**Recommendation:** Start with 50 IPOs using semi-automated approach (7 hours)

---

## Data Sources

### IPO Calendars
- **Renaissance Capital** (best): https://www.renaissancecapital.com/IPO-Center
- **Nasdaq**: https://www.nasdaq.com/market-activity/ipos
- **IPOScoop**: https://www.iposcoop.com/
- **MarketWatch**: https://www.marketwatch.com/tools/ipo-calendar

### S-1 Filings
- **SEC EDGAR**: https://www.sec.gov/edgar/searchedgar/companysearch.html
- API: https://www.sec.gov/developer

### Price Data
- **QuantConnect** (in notebook)
- **Yahoo Finance** (backup)
- **Alpha Vantage** (free API)

### News / Sentiment
- **Google News** (free, manual)
- **NewsAPI** (paid, $449/mo)
- **AlphaSense** (paid, expensive)
- **Reddit/Twitter** (manual scraping)

---

## Tips for Success

1. **Start Small:** Begin with 50 IPOs from 2024, then expand
2. **Prioritize Quality:** Better to have 50 high-quality IPOs than 200 messy ones
3. **Document Everything:** Keep notes on data sources and decisions
4. **Validate Continuously:** Check for errors after each step
5. **Use Templates:** Manual entry templates in notebook save time
6. **Be Consistent:** Use same units (millions), same fiscal periods
7. **Save Progress:** Save after each step, don't lose work

---

## Next Steps After Data Collection

Once you have `data/historical_ipos.csv`:

1. **Open `research.ipynb`**
2. **Load the data**
3. **Train model** (LightGBM classifier)
4. **Validate** (target AUC > 0.70)
5. **Save model** to Object Store
6. **Start scoring** upcoming IPOs
7. **Deploy** to QuantConnect

**Timeline:** 1-2 weeks from data collection to live trading

---

## Getting Help

**Data Collection Issues:**
- Check notebook cell outputs for error messages
- Verify file paths and column names
- Test with 1-2 IPOs before running full batch

**S-1 Parsing Issues:**
- SEC filings vary greatly in structure
- Manual entry is often faster than debugging parsers
- Consider hiring VA to help with data entry ($10-15/hour)

**QuantConnect Issues:**
- Check documentation: https://www.quantconnect.com/docs/
- Forum: https://www.quantconnect.com/forum/
- Some tickers may not be available

---

## Estimated Costs

### Time
- Initial data collection: 7-20 hours
- Weekly maintenance: 2-3 hours
- Model retraining: 2 hours/quarter

### Money (Optional)
- Free tier is sufficient for 100-200 IPOs
- Optional: NewsAPI ($449/mo) for sentiment
- Optional: VA for data entry ($100-200 for 100 IPOs)
- QuantConnect: Free for backtesting, $20-80/mo for live

**Recommended:** Start completely free, add paid services only if needed

---

Good luck with data collection! Remember: quality > quantity.
It's better to have 50 well-researched IPOs than 200 with errors.
