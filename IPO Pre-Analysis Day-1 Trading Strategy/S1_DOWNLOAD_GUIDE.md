# S-1 Filing Download Guide

## Quick Start

**IMPORTANT: Run `s1_downloader.ipynb` on your LOCAL computer, NOT in QuantConnect!**

QuantConnect has network restrictions that block SEC EDGAR access. This notebook must run locally.

---

## Setup (5 minutes)

### Step 1: Install Python Packages

```bash
pip install pandas requests beautifulsoup4 lxml tqdm jupyter
```

### Step 2: Update Configuration

Open `s1_downloader.ipynb` and update these lines:

```python
YOUR_EMAIL = "your.email@example.com"  # ⚠️ CHANGE THIS!
YOUR_NAME = "Your Name or Company"      # ⚠️ CHANGE THIS!
```

**Why?** The SEC requires you to identify yourself in the User-Agent header. This is a legal requirement.

### Step 3: Prepare IPO Calendar

Create `data/ipo_calendar.csv` with at least a `ticker` column:

```csv
ticker,company,ipo_date,sector
ARM,Arm Holdings,2023-09-14,Technology
RDDT,Reddit Inc,2024-03-21,Technology
CART,Instacart,2023-09-19,Technology
```

**OR** run the notebook - it will create a sample calendar automatically!

---

## Running the Notebook

### Option A: Jupyter Notebook

```bash
# Start Jupyter
jupyter notebook

# Open s1_downloader.ipynb
# Run all cells (Cell → Run All)
```

### Option B: JupyterLab

```bash
# Start JupyterLab
jupyter lab

# Open s1_downloader.ipynb
# Run all cells
```

### Option C: VS Code

```bash
# Open folder in VS Code
code .

# Open s1_downloader.ipynb
# Click "Run All" at the top
```

---

## What It Does

The notebook will:

1. ✅ Read your IPO calendar CSV
2. ✅ Search SEC EDGAR for each ticker's S-1 filing
3. ✅ Download the S-1 HTML document
4. ✅ Save to `data/s1_filings/` folder
5. ✅ Generate download report and log

**Estimated time:**
- 10 IPOs: ~5 minutes
- 50 IPOs: ~25 minutes
- 100 IPOs: ~50 minutes

---

## Output Files

After running, you'll have:

```
data/s1_filings/
├── ARM_s1.html                    # Downloaded S-1 for ARM
├── RDDT_s1.html                   # Downloaded S-1 for Reddit
├── CART_s1.html                   # Downloaded S-1 for Instacart
├── ...
├── _download_log.csv              # Detailed log of all downloads
└── _download_summary.txt          # Summary report
```

Each S-1 file is typically:
- **Size:** 100-500 KB
- **Format:** HTML with embedded tables
- **Contains:** Full S-1 filing with financial data

---

## Success Metrics

### Good Results:
- ✅ 80%+ success rate
- ✅ Files are 100-500 KB each
- ✅ Can open HTML in browser and see financial tables
- ✅ Log shows only minor errors

### Common Issues:

**"S-1 filing not found"**
- Company may have filed F-1 (foreign issuers)
- Check if it was a SPAC merger (different filings)
- Some direct listings don't have S-1s
- Solution: Manually download or skip this IPO

**"Connection timeout"**
- SEC EDGAR may be slow
- Try increasing DELAY_BETWEEN_REQUESTS to 1.0
- Run during off-peak hours (evenings/weekends)

**"Already exists (skipped)"**
- File was downloaded in previous run
- This is normal! Notebook won't re-download

---

## Verifying Downloads

### Quick Check:
Open any downloaded S-1 file in your web browser. You should see:
- SEC header with company name and CIK
- Table of contents
- "Summary Financial Data" tables with revenue, income, etc.
- Lots of legal text

### Validation Checklist:
- [ ] Files exist in `data/s1_filings/` folder
- [ ] Each file is >50 KB (very small = probably error page)
- [ ] Can open in browser and see financial tables
- [ ] `_download_log.csv` shows success=True for most
- [ ] At least 80% success rate

---

## Manual Download (For Failed IPOs)

If some downloads failed, manually download them:

1. **Visit SEC EDGAR:**
   ```
   https://www.sec.gov/cgi-bin/browse-edgar?company=TICKER&type=S-1
   ```

2. **Find S-1 Filing:**
   - Look for "S-1" or "S-1/A" (amended)
   - Choose most recent one before IPO date
   - Click "Documents" button

3. **Download Main Document:**
   - Look for largest .htm file (usually first one)
   - Right-click → "Save As"
   - Name it: `TICKER_s1.html`

4. **Save to Folder:**
   - Put in `data/s1_filings/` folder
   - File should be 100-500 KB

---

## Troubleshooting

### Error: "Please update YOUR_EMAIL"

**Problem:** You didn't change the configuration
**Solution:** Edit cell 2, update YOUR_EMAIL with your real email

---

### Error: "Input file not found"

**Problem:** No IPO calendar CSV
**Solution:**
- Create `data/ipo_calendar.csv` with ticker column
- OR just run the notebook - it creates a sample automatically

---

### Error: "Module not found"

**Problem:** Missing Python packages
**Solution:**
```bash
pip install pandas requests beautifulsoup4 lxml tqdm
```

---

### Error: "ProxyError" or "ConnectionError"

**Problem:** Network restrictions or firewall
**Solution:**
- Check if you can access https://www.sec.gov in browser
- Try disabling VPN
- Run from home network (not corporate)
- As last resort, download all S-1s manually

---

### Low Success Rate (<50%)

**Problem:** Network issues or wrong tickers
**Solution:**
- Verify tickers are correct (check on Google/Yahoo Finance)
- Increase delay: `DELAY_BETWEEN_REQUESTS = 1.0`
- Check `_download_log.csv` for specific error messages
- Some IPOs legitimately don't have S-1s (foreign issuers, SPACs)

---

## Next Steps

Once you have S-1 files downloaded:

### 1. Extract Fundamental Data

**Option A - Manual Entry (Recommended):**
- Open each S-1 in browser
- Find "Summary Financial Data" table
- Enter into CSV template
- Most accurate method
- ~10-15 min per IPO

**Option B - Automated Parsing:**
- Run `data_collection.ipynb` Step 3
- Uses regex to extract data
- Less accurate, needs validation
- ~1 min per IPO

### 2. Continue Data Collection

Go to `data_collection.ipynb`:
- ✅ Skip Step 2 (S-1 download) - you already did it!
- ▶️ Run Step 3 (fundamental extraction)
- ▶️ Run Step 4 (price performance)
- ▶️ Run Step 5 (market conditions)
- ▶️ Run Step 6 (sentiment)
- ▶️ Run Step 7 (merge & validate)

### 3. Upload to QuantConnect (Optional)

If you need S-1 files in QuantConnect:
```bash
# Zip the folder
zip -r s1_filings.zip data/s1_filings/

# Upload to QuantConnect project
# (Use their UI file upload)
```

---

## Tips for Success

1. **Test with 5 IPOs first** - Set `LIMIT = 5` in the notebook
2. **Run during off-peak hours** - SEC EDGAR is faster evenings/weekends
3. **Check log file** - Review errors to understand failures
4. **Save progress** - Downloaded files won't be re-downloaded
5. **Manual fallback** - If automation fails, manual download takes 2 min/IPO

---

## FAQ

**Q: Why can't I run this in QuantConnect?**
A: QuantConnect has a proxy that blocks SEC EDGAR access. This is a security feature.

**Q: How long will this take?**
A: ~30 seconds per IPO due to SEC rate limiting. Budget ~1 hour for 100 IPOs.

**Q: What if success rate is <80%?**
A: This is normal. Some companies use F-1 instead of S-1, or went public via SPAC. Manually download the important ones.

**Q: Can I speed it up?**
A: Not much - SEC limits to 10 requests/second. The delay is intentional.

**Q: Do I need to re-download periodically?**
A: No! S-1 filings don't change. Once downloaded, you have them forever.

**Q: What's the file format?**
A: HTML with embedded tables. Can be opened in browser or parsed with BeautifulSoup.

---

## Summary

✅ **Run locally** (not in QuantConnect)
✅ **Update email** (SEC requirement)
✅ **Check success rate** (>80% is good)
✅ **Manual fallback** (for failed downloads)
✅ **Continue to data_collection.ipynb** (Step 3+)

**Total time:** 5 min setup + 1 hour download (for 100 IPOs)

Good luck! The automated download saves hours compared to manual collection.
