# Setup Checklist

Use this checklist to track your progress setting up the E-Commerce Arbitrage System.

## Phase 1: System Installation ✅ COMPLETE

- [x] Python 3.8+ installed
- [x] Required packages installed (sqlalchemy, pandas, keepa, etc.)
- [x] Optional packages installed (playwright, telegram, etc.)
- [x] Project directories created (data/, logs/, config/)
- [x] Configuration files created (config.yaml, .env)
- [x] Main program verified working

**Status: Ready for configuration!**

---

## Phase 2: Get API Credentials ⏳ IN PROGRESS

### Amazon SP-API (Required)
- [ ] Sign up for Amazon Seller Central account
- [ ] Subscribe to Professional plan ($39.99/month)
- [ ] Register as developer (Apps & Services → Develop Apps)
- [ ] Create new app client
- [ ] Get Client ID
- [ ] Get Client Secret
- [ ] Authorize app and get Refresh Token
- [ ] Add credentials to `config/config.yaml`

**Time estimate:** 30-60 minutes (+ account approval time)

### Keepa API (Highly Recommended)
- [ ] Sign up at https://keepa.com
- [ ] Subscribe to API access (start with $19/month plan)
- [ ] Copy API key from Settings → API
- [ ] Add API key to `config/config.yaml`

**Time estimate:** 10 minutes

### Email Notifications (Recommended)
- [ ] Enable 2-Factor Authentication on email account
- [ ] Generate App Password (for Gmail: https://myaccount.google.com/apppasswords)
- [ ] Add email credentials to `config/config.yaml`
- [ ] Test email by running: `python3 main.py --report`

**Time estimate:** 15 minutes

### Retail APIs (Optional - Can add later)
- [ ] Apply for Best Buy API key
- [ ] Apply for Walmart API key
- [ ] Add keys to `config/config.yaml` when approved

**Time estimate:** Varies (approval can take days)

---

## Phase 3: Configure System Settings

### Basic Configuration
- [ ] Open `config/config.yaml` in editor
- [ ] Set minimum ROI threshold (start with 30%)
- [ ] Configure sales rank limits by category
- [ ] Set price ranges (min/max source price)
- [ ] Add excluded categories (restricted items)
- [ ] Add excluded brands (gated brands)

**File to edit:** `config/config.yaml`

### Create Watchlist (Optional but helpful)
- [ ] Add 10-20 ASINs to monitor in config
- [ ] Choose products you're familiar with
- [ ] Include variety of categories
- [ ] Include variety of price points

**Where to add:** `config/config.yaml` under `amazon.watchlist_asins`

---

## Phase 4: Test the System

### Basic Tests
- [ ] Run: `python3 main.py --show-deals`
  - Expected: System initializes without errors
- [ ] Check database created: `ls data/deals.db`
  - Expected: File exists
- [ ] View help: `python3 main.py --help`
  - Expected: Shows all available commands

### First Scan
- [ ] Run: `python3 main.py --scanner amazon`
  - Expected: Scans complete, may find 0 deals initially
- [ ] Check logs: `cat logs/arbitrage.log`
  - Expected: No error messages
- [ ] View any deals found: `python3 main.py --show-deals`

### Email Test
- [ ] Run: `python3 main.py --report`
  - Expected: Receives email digest
- [ ] Check spam folder if not received
- [ ] Verify email formatting looks good

---

## Phase 5: Initial Operation

### Manual Testing Period (Week 1)
- [ ] Run scans manually 2-3 times per day
- [ ] Review deals found
- [ ] Verify profit calculations make sense
- [ ] Check sales ranks are reasonable
- [ ] Note which categories produce best deals

### Analysis
- [ ] Install Jupyter: `pip3 install jupyter`
- [ ] Open notebook: `jupyter notebook notebooks/analysis.ipynb`
- [ ] Run all cells to see deal analytics
- [ ] Identify best-performing categories
- [ ] Note optimal price ranges

### First Purchase (Optional)
- [ ] Find a low-risk deal ($10-20 item)
- [ ] Verify on Amazon before buying
- [ ] Purchase from source
- [ ] Track actual vs estimated costs
- [ ] Update system based on learnings

---

## Phase 6: Automation Setup

### Scheduled Scans
- [ ] Decide on scan frequency (every 2-4 hours recommended)
- [ ] Set up cron job (Mac/Linux) or Task Scheduler (Windows)
- [ ] Test automated scan runs correctly
- [ ] Verify email alerts work when deals found

### Monitoring
- [ ] Set up daily digest email (8 AM recommended)
- [ ] Configure high-ROI instant alerts (50%+ ROI)
- [ ] Set up mobile notifications (optional - Telegram)
- [ ] Check logs periodically for errors

---

## Phase 7: Optimization

### After 1 Week
- [ ] Review deal quality in analysis notebook
- [ ] Adjust ROI thresholds based on results
- [ ] Refine category filters
- [ ] Update price ranges
- [ ] Add/remove from watchlist

### After 1 Month
- [ ] Track actual purchase outcomes
- [ ] Compare estimated vs actual profits
- [ ] Adjust fee calculations if needed
- [ ] Expand to additional retail sources
- [ ] Scale up if profitable

---

## Troubleshooting Checklist

### If no deals are found:
- [ ] Verify Keepa API key is working
- [ ] Check API rate limits not exceeded
- [ ] Add more items to watchlist
- [ ] Temporarily lower ROI threshold
- [ ] Verify filters aren't too restrictive

### If authentication errors:
- [ ] Double-check Amazon SP-API credentials
- [ ] Ensure refresh token is correct
- [ ] Verify no extra spaces in config file
- [ ] Check YAML syntax (use spaces, not tabs)
- [ ] Re-authorize app in Seller Central

### If emails not sending:
- [ ] Verify 2FA enabled on account
- [ ] Use App Password, not regular password
- [ ] Check SMTP server and port correct
- [ ] Verify recipient email correct
- [ ] Check spam/junk folder

---

## Current Status

**What's working:**
- ✅ System installed
- ✅ All packages ready
- ✅ Database initialized
- ✅ Main program runs

**What you need to do:**
1. Get Amazon Seller account + SP-API credentials
2. Get Keepa API key (optional but recommended)
3. Configure email notifications
4. Add credentials to `config/config.yaml`
5. Run first test scan

**Estimated time to complete:** 1-2 hours (plus account approval time)

---

## Quick Start After Setup

Once you have API credentials:

```bash
# 1. Add credentials to config
nano config/config.yaml

# 2. Test the system
python3 main.py --show-deals

# 3. Run first scan
python3 main.py --scanner amazon

# 4. View results
python3 main.py --show-deals --min-roi 30

# 5. Send test email
python3 main.py --report
```

---

## Resources

- **Detailed setup instructions:** `SETUP_GUIDE.md`
- **Quick reference:** `QUICK_REFERENCE.md`
- **Full documentation:** `README.md`
- **Fast start guide:** `QUICKSTART.md`

---

## Support Contacts

**Amazon Seller Central:**
- https://sellercentral.amazon.com/help

**Keepa Support:**
- https://keepa.com/#!discuss

**Configuration Help:**
- Check SETUP_GUIDE.md
- Verify YAML syntax at: http://www.yamllint.com/

---

**Next Step:** Open `SETUP_GUIDE.md` for detailed instructions on getting API credentials!
