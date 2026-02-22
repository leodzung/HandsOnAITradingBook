# Complete Setup Guide

Follow this guide step-by-step to configure your E-Commerce Arbitrage System.

## Prerequisites Completed ✓

- Python 3.9.6 installed
- All required packages installed
- Project directories created
- Configuration files created

## Next Steps

### Step 1: Get Amazon Seller Account & SP-API Credentials

**What you need:**
- Amazon Seller Central account ($39.99/month subscription)
- SP-API Developer credentials

**How to get them:**

1. **Sign up for Amazon Seller Central**
   - Go to: https://sellercentral.amazon.com
   - Click "Register now"
   - Choose "Professional" plan ($39.99/month)
   - Complete registration

2. **Register as a Developer**
   - In Seller Central, go to: Apps & Services → Develop Apps
   - Click "Add new app client"
   - Fill in:
     - App name: "Arbitrage Scanner"
     - OAuth Redirect URI: https://localhost (for testing)
     - Roles: Check all API sections you need

3. **Get your credentials**
   You'll receive:
   - Client ID (looks like: amzn1.application-oa2-client.xxxxx)
   - Client Secret (keep this secret!)

4. **Authorize your app**
   - Click "Authorize" button
   - This generates your **Refresh Token**
   - Save this token - it doesn't expire!

5. **Add credentials to config**
   ```bash
   cd "10 E-Commerce Arbitrage System"
   nano config/config.yaml
   ```

   Find the `amazon.sp_api` section and add:
   ```yaml
   amazon:
     sp_api:
       refresh_token: "YOUR_REFRESH_TOKEN_HERE"
       client_id: "amzn1.application-oa2-client.XXXXX"
       client_secret: "YOUR_CLIENT_SECRET_HERE"
       marketplace_id: "ATVPDKIKX0DER"  # US marketplace
   ```

---

### Step 2: Get Keepa API Key (Highly Recommended)

**Why you need it:**
- Tracks historical Amazon prices
- Detects price drops automatically
- Shows sales rank history
- Essential for finding good deals

**Cost:**  $19-149/month depending on usage

**How to get it:**

1. Go to: https://keepa.com
2. Create an account
3. Go to: Settings → API
4. Subscribe to API access (start with $19/month plan)
5. Copy your API key

6. Add to config:
   ```yaml
   keepa:
     api_key: "YOUR_KEEPA_API_KEY_HERE"
     rate_limit: 120  # Requests per minute (depends on your plan)
   ```

**Can I skip this?**
- Yes, but you'll have limited deal-finding capability
- You'll need to manually provide product ASINs to monitor
- No automatic price drop detection

---

### Step 3: Configure Email Notifications

**Why you need it:**
- Get alerts for high-ROI deals
- Receive daily digest of opportunities
- Monitor system status

**For Gmail users:**

1. **Enable 2-Factor Authentication**
   - Go to: https://myaccount.google.com/security
   - Enable 2-Step Verification

2. **Create App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it: "Arbitrage System"
   - Click "Generate"
   - Copy the 16-character password

3. **Add to config:**
   ```yaml
   notifications:
     email:
       enabled: true
       smtp_server: "smtp.gmail.com"
       smtp_port: 587
       sender_email: "your-email@gmail.com"
       sender_password: "YOUR_16_CHAR_APP_PASSWORD"
       recipient_emails:
         - "your-email@gmail.com"
       alert_min_roi: 50.0  # Only send alert if ROI > 50%
   ```

**For other email providers:**
- Outlook/Hotmail: smtp.office365.com, port 587
- Yahoo: smtp.mail.yahoo.com, port 587

---

### Step 4: Optional - Retail API Keys

These are optional but help find more deals:

#### Best Buy API
1. Apply for API key: https://developer.bestbuy.com/
2. Wait for approval (can take a few days)
3. Add to config:
   ```yaml
   retail:
     bestbuy:
       api_key: "YOUR_BESTBUY_API_KEY"
       enabled: true
   ```

#### Walmart API
1. Apply at: https://developer.walmart.com/
2. Requires business verification
3. Add to config:
   ```yaml
   retail:
     walmart:
       api_key: "YOUR_WALMART_API_KEY"
       enabled: true
   ```

---

### Step 5: Configure Deal Filters

Edit `config/config.yaml` to set your preferences:

```yaml
profit:
  min_roi: 30.0  # Minimum ROI percentage (30% = good starting point)
  target_profit_margin: 0.35  # Target 35% margin

filters:
  # Maximum sales rank by category (lower rank = sells faster)
  max_sales_rank:
    toys_games: 50000
    electronics: 30000
    home_kitchen: 40000
    default: 50000

  # Competition limits
  max_number_of_sellers: 10  # Avoid highly competitive products
  prefer_fba_sellers_under: 5  # Better if few FBA sellers

  # Price ranges
  min_source_price: 5.0  # Don't bother with items < $5
  max_source_price: 200.0  # Cap investment per item
  min_amazon_price: 15.0  # Minimum selling price

  # Quality filters
  min_review_count: 10  # Product should have reviews
  min_average_rating: 3.5  # Decent ratings

  # Avoid restricted categories
  excluded_categories:
    - "Grocery & Gourmet Food"  # Often restricted
    - "Health & Personal Care"  # Often restricted
    - "Beauty"  # Often gated

  # Avoid major brands (usually gated/restricted)
  excluded_brands:
    - "Apple"
    - "Nike"
    - "Sony"
```

---

### Step 6: Test the System

Now let's verify everything works!

**6.1 Test Configuration**
```bash
cd "10 E-Commerce Arbitrage System"
python3 main.py --show-deals
```

Expected: System initializes without errors

**6.2 Test Database**
```bash
ls -la data/
```

Expected: You should see `deals.db` file created

**6.3 Add a test watchlist (optional)**

Edit `config/config.yaml` and add some ASINs to monitor:

```yaml
amazon:
  watchlist_asins:
    - "B08N5WRWNW"  # Example ASIN
    - "B07XJ8C8F5"  # Example ASIN
```

**6.4 Run your first scan**
```bash
python3 main.py --scanner amazon
```

This will:
- Connect to Amazon API
- Check Keepa for price drops
- Scan your watchlist
- Calculate profits
- Save deals to database

---

### Step 7: View Results

**Show all deals:**
```bash
python3 main.py --show-deals
```

**Show only high-ROI deals:**
```bash
python3 main.py --show-deals --min-roi 40
```

**Send test email report:**
```bash
python3 main.py --report
```

---

## Troubleshooting

### "No deals found"

This is normal at first! Try:
1. Add more ASINs to your watchlist
2. Lower `min_roi` temporarily (try 20%)
3. Verify Keepa API key is working
4. Wait - deal finding takes time!

### "Authentication failed"

Check:
1. Amazon SP-API credentials are correct
2. Refresh token hasn't been revoked
3. No extra spaces in config file
4. YAML syntax is correct (use spaces, not tabs)

### "Email not sending"

Verify:
1. 2FA is enabled on Google account
2. Used App Password, not regular password
3. SMTP settings are correct
4. Check spam folder

### "Import errors"

Run again:
```bash
cd "10 E-Commerce Arbitrage System"
pip3 install -r requirements.txt
```

---

## Next Steps After Setup

### 1. Start with Manual Testing
- Add 10-20 products to watchlist
- Run scans manually for a week
- Observe what deals appear
- Track which ones are actually profitable

### 2. Analyze Results
```bash
jupyter notebook notebooks/analysis.ipynb
```

This will show you:
- Which categories work best
- Optimal price ranges
- ROI distribution
- Sales rank vs profitability

### 3. Set Up Automation

Create a cron job to run scans automatically:

```bash
crontab -e
```

Add these lines:
```
# Run scan every 2 hours
0 */2 * * * cd /Users/leole/workspace/HandsOnAITradingBook/10\ E-Commerce\ Arbitrage\ System && python3 main.py --scan-all

# Daily report at 8 AM
0 8 * * * cd /Users/leole/workspace/HandsOnAITradingBook/10\ E-Commerce\ Arbitrage\ System && python3 main.py --report
```

### 4. Start Small
- Buy 1-2 items to test the process
- Verify profit calculations are accurate
- Learn Amazon FBA workflow
- Scale up once comfortable

---

## Important Reminders

### Legal & Compliance
- Only sell authentic products
- Respect brand restrictions (gating)
- Don't resell without authorization
- Report all income for taxes
- Follow Amazon's seller policies

### Risk Management
- Start with low-cost items ($10-30)
- Diversify across categories
- Account for 2-5% return rate
- Monitor price changes daily
- Don't invest more than you can lose

### Best Practices
- Verify condition before purchasing
- Check expiration dates (if applicable)
- Inspect for damage before sending to FBA
- Keep receipts for authenticity
- Track actual vs estimated profits

---

## Quick Command Reference

```bash
# Run all scanners
python3 main.py --scan-all

# Run specific scanner
python3 main.py --scanner amazon
python3 main.py --scanner retail

# View deals
python3 main.py --show-deals --min-roi 35

# Send report
python3 main.py --report

# Analysis
jupyter notebook notebooks/analysis.ipynb
```

---

## Getting Help

- **Documentation**: See README.md for full details
- **Quick Start**: See QUICKSTART.md
- **Issues**: Check config file syntax first
- **API Limits**: Verify Keepa/Amazon rate limits

---

## System Status Checklist

Before going live, verify:

- [ ] Amazon Seller account active
- [ ] Amazon SP-API credentials configured
- [ ] Keepa API key configured (recommended)
- [ ] Email notifications working
- [ ] Database created successfully
- [ ] First scan completed
- [ ] Deals visible in database
- [ ] Profit calculations make sense
- [ ] Filters configured for your strategy
- [ ] Excluded restricted categories
- [ ] Test email alerts received

Once all checked, you're ready to start finding deals!

Good luck with your arbitrage business! 🚀
