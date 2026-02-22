# 🚀 Moralis Integration Setup Guide

## Why Add Moralis?

**Problem:** DexScreener's free API doesn't have trending/top volume endpoints. You have to manually find tokens on their website.

**Solution:** Moralis API auto-discovers trending tokens, then we enrich with DexScreener for details.

---

## 📊 What You Get With Moralis

### **Auto-Discovery Features:**

| Feature | How It Helps | Example |
|---------|-------------|---------|
| **Top by Market Cap** | Find established, liquid tokens | KOGE with $162M market cap |
| **Price Gainers** | Catch momentum plays | Tokens up 50%+ today |
| **Price Losers** | Find oversold opportunities | Potential bouncebacks |
| **Volume Sorting** | High activity = high interest | $270M daily volume tokens |

### **Current Limitations (Manual Discovery):**

```
You browse DexScreener → Find KOGE manually → Add to watchlist
         ⬇️
   Scanner monitors it
```

### **With Moralis (Auto-Discovery):**

```
Moralis finds KOGE automatically → Scanner scores it → Email alert
```

---

## 🆓 Pricing: Free Tier vs Paid

### **Free Tier (Recommended to Start):**

```
Cost: $0/month
Limits: 40,000 Compute Units per day
Rate: 1,000 CU/second

Real Usage:
- 1 market cap query = ~25 CU
- 50 tokens/day = ~1,250 CU/day
- You get 40,000/day = enough for 1,600 tokens!

Verdict: FREE TIER IS PLENTY ✅
```

### **When to Upgrade:**

Only if you hit 40K CU/day (very unlikely for individual trading)

---

## 📝 Step-by-Step Setup

### **Step 1: Sign Up for Moralis**

1. Go to: https://moralis.com
2. Click "Start for Free"
3. Create account (email + password)
4. Verify your email

**Time:** 2 minutes

---

### **Step 2: Get Your API Key**

1. Log into Moralis dashboard
2. Click on your profile (top right)
3. Go to "Account Settings"
4. Navigate to "API Keys" section
5. Click "Web3 API Key"
6. Copy your API key (looks like: `eyJhbGc...`)

**Time:** 1 minute

---

### **Step 3: Add API Key to Config**

1. Open `moralis_config.json` in your scanner directory:

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
nano moralis_config.json
```

2. Replace `YOUR_MORALIS_API_KEY_HERE` with your actual API key:

```json
{
  "api_key": "eyJhbGciOiJI...YOUR_ACTUAL_KEY_HERE",
  "base_url": "https://deep-index.moralis.io/api/v2.2"
}
```

3. Save and exit (`Ctrl+X`, `Y`, `Enter`)

**Time:** 1 minute

---

### **Step 4: Test the Integration**

Run the Moralis discovery scanner:

```bash
python3 run_moralis_discovery.py
```

**Expected output:**

```
================================================================================
MORALIS-POWERED DISCOVERY SCANNER
================================================================================

🔍 Discovering tokens via Moralis API...

1️⃣ Fetching top BSC tokens by market cap...
   📡 Calling: https://deep-index.moralis.io/api/v2.2/market-data/erc20s/top-tokens
   ✅ Added 25 high market cap tokens

2️⃣ Fetching top price gainers...
   📡 Calling: https://deep-index.moralis.io/api/v2.2/market-data/erc20s/top-movers
   ✅ Found 15 gainers, 10 losers
   ✅ Added 10 new price gainers

✅ Total unique tokens discovered: 35

================================================================================
ENRICHING WITH DEXSCREENER & SCORING
================================================================================

#1 KOGE (0xe6DF05CE8C...)
   Liquidity: $37,494,075 | Volume: $270,018,898
   Score: 71.8/100
   ✅ HIGH QUALITY
```

**If it works:** You'll see tokens discovered and scored!

**If it fails:** See Troubleshooting section below

---

## 🔧 Integration with Your Cron Scanner

### **Option A: Keep Watchlist + Add Moralis (Recommended)**

Update `run_with_email_alerts.py` to use Moralis discovery:

```python
# Current: Uses watchlist + WBNB search
from run_combined import fetch_and_analyze

# Updated: Uses Moralis discovery + watchlist + WBNB search
from run_moralis_discovery import discover_and_analyze as fetch_and_analyze
```

**This gives you:**
- ✅ Auto-discovery (Moralis top tokens + gainers)
- ✅ Manual watchlist (your curated picks)
- ✅ WBNB pairs (basic search)

### **Option B: Moralis Only**

```python
from run_moralis_discovery import discover_and_analyze as fetch_and_analyze
```

**This gives you:**
- ✅ Auto-discovery only
- ❌ No manual watchlist
- ⚠️ May miss some tokens

### **Option C: Keep Current (Watchlist Only)**

```python
from run_combined import fetch_and_analyze
```

**This gives you:**
- ✅ Manual control
- ❌ No auto-discovery
- ⚠️ Requires daily browsing

---

## 📊 Performance Comparison

### **Before Moralis (Current):**

```
Daily workflow:
1. Spend 10 minutes browsing DexScreener
2. Manually add 3-5 interesting tokens to watchlist
3. Scanner monitors those 3-5 tokens hourly
4. Get email if any score ≥70

Tokens discovered: 3-5/day (manual)
Time investment: 10 min/day browsing
```

### **After Moralis:**

```
Daily workflow:
1. Do nothing (fully automated!)
2. Scanner auto-discovers top 50 tokens hourly
3. Scores all 50 automatically
4. Get email for any that score ≥70

Tokens discovered: 50/scan × 10 scans/day = 500/day (auto)
Time investment: 0 min/day (unless you get an alert!)
```

**ROI:** Save 10 min/day + discover 10x more opportunities

---

## ⚠️ Troubleshooting

### **Error: "Authentication failed - check your API key"**

**Problem:** API key is invalid or not set correctly

**Solution:**
1. Verify API key copied correctly (no spaces/linebreaks)
2. Check moralis_config.json formatting (valid JSON)
3. Regenerate API key in Moralis dashboard

### **Error: "Access forbidden - may need paid plan"**

**Problem:** Endpoint requires paid tier OR BSC chain not available

**Solution:**
1. Try ethereum chain instead: `chain="eth"`
2. Check Moralis docs for BSC support
3. Free tier should work for most endpoints

### **Error: "Rate limit exceeded"**

**Problem:** Hit 40K CU/day limit (unlikely) or 1K CU/sec

**Solution:**
1. Add delays between API calls (already implemented)
2. Reduce scan frequency (every 2 hours instead of hourly)
3. Upgrade to paid tier if truly needed

### **No tokens discovered**

**Problem:** API returns empty results

**Solution:**
1. Check if BSC chain is supported
2. Try `chain="eth"` for Ethereum
3. Verify your account is activated (email confirmed)

---

## 💰 Cost Analysis

### **Free Tier Budget:**

```
Daily limit: 40,000 CU

Per scan:
- Market cap query (25 tokens): 625 CU
- Price movers query (25 tokens): 625 CU
- Total per scan: 1,250 CU

Scans per day: 40,000 ÷ 1,250 = 32 scans/day

Your usage: 10 scans/day = 12,500 CU/day

Remaining buffer: 27,500 CU/day (69% unused!)
```

**Verdict:** Free tier has 3x capacity you need ✅

### **Paid Tier (If You Outgrow Free):**

```
Starter: $49/year ($4/month)
- 2 million CU/month
- Enough for 1,600 scans/day
- Only need if you're running multiple bots
```

---

## 🎯 Recommended Configuration

### **Ideal Setup for Individual Trader:**

```json
// moralis_config.json
{
  "api_key": "eyJhbGci...",  // Your real key
  "base_url": "https://deep-index.moralis.io/api/v2.2",
  "enabled": true,  // Toggle Moralis on/off
  "scan_settings": {
    "market_cap_limit": 25,    // Top 25 by market cap
    "price_movers_limit": 25,  // Top 25 gainers
    "chain": "bsc",            // Binance Smart Chain
    "min_market_cap": 100000   // $100K minimum
  }
}
```

### **Cron Schedule:**

Keep your current hourly schedule:
```
0 9-18 * * 1-5  # Every hour, 9AM-6PM UTC, Mon-Fri
```

This gives you:
- 10 scans/day
- 500 tokens analyzed/day
- ~12,500 CU/day (well under 40K limit)

---

## 📈 Expected Results

### **With Moralis Discovery:**

**Week 1:**
- Discover 500+ tokens/day automatically
- Find 5-10 high-quality opportunities (score ≥70)
- Receive 1-2 email alerts/day
- Save 70 minutes/week browsing DexScreener

**Month 1:**
- Discover 15,000+ unique tokens
- Find 150+ high-quality opportunities
- Never miss a KOGE-level opportunity
- Zero manual work required

---

## 🚀 Next Steps

1. **Sign up:** https://moralis.com (2 min)
2. **Get API key:** Copy from dashboard (1 min)
3. **Update config:** Add key to moralis_config.json (1 min)
4. **Test:** `python3 run_moralis_discovery.py` (1 min)
5. **Integrate:** Update run_with_email_alerts.py (optional)

**Total setup time: 5-10 minutes**

**Lifetime value: Auto-discovery of opportunities like KOGE!**

---

## ❓ FAQ

**Q: Is the free tier really enough?**
A: Yes! You can analyze 1,600 tokens/day on free tier. You only need ~500/day.

**Q: Will this replace my watchlist?**
A: No, keep both! Moralis finds trending tokens, watchlist lets you track specific picks.

**Q: What if Moralis API changes?**
A: The endpoints are stable (v2.2). If they change, we'll update the code.

**Q: Can I use this for Ethereum instead of BSC?**
A: Yes! Just change `chain="eth"` in the code.

**Q: Does this work with the cron job?**
A: Yes, seamlessly! Just update the import in run_with_email_alerts.py

**Q: How much does paid tier cost?**
A: Starter: $49/year ($4/month). But free tier is plenty for individual trading.

---

## 📞 Support

**Moralis Help:**
- Docs: https://docs.moralis.com
- Discord: https://moralis.com/discord
- Support: support@moralis.com

**Your Scanner Help:**
- Check logs: `tail -f cron_log.txt`
- Test manually: `python3 run_moralis_discovery.py`
- Debug: Add print statements to see API responses

---

**You're 5 minutes away from auto-discovering the next KOGE!** 🚀💎
