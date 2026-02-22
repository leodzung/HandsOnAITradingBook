# Twitter API Setup Guide for DEX Token Screener

This guide will help you set up Twitter API access to get real social sentiment data instead of placeholder metrics.

## Why Set Up Twitter API?

**Current Status (Free Tier):**
- Follower count: Placeholder (1000)
- Tweet volume: Placeholder (5)
- Engagement rate: Placeholder
- Sentiment: Basic keyword-based

**With Twitter API (Real Data):**
- **Real follower counts** (actual numbers)
- **Actual tweet volume** (24h activity)
- **True engagement rates** (likes, retweets, replies)
- **Better sentiment analysis** (with VADER)
- **Verified badge detection**
- **Account age verification**

---

## Step-by-Step Setup

### 1. Create Twitter Developer Account

1. **Go to Twitter Developer Portal:**
   ```
   https://developer.twitter.com/en/portal/dashboard
   ```

2. **Sign in with your Twitter account**
   - Use your existing Twitter account
   - If you don't have one, create a Twitter account first

3. **Apply for Developer Access:**
   - Click "Sign up for Free Account"
   - Select **"Hobbyist"** → **"Exploring the API"**

4. **Fill out the Application:**

   **What's your name?**
   ```
   [Your actual name]
   ```

   **What country are you based in?**
   ```
   [Your country]
   ```

   **What's your use case?**
   ```
   I am building a cryptocurrency token screening tool that analyzes
   social media presence to help identify legitimate projects. The tool
   will analyze Twitter profiles, follower counts, tweet activity, and
   engagement rates to detect potential scams and verify community support
   for DEX-listed tokens before they reach centralized exchanges.
   ```

   **Will you make Twitter content available to government entities?**
   ```
   No
   ```

   **Will your product, service, or analysis make Twitter content available to government entities?**
   ```
   No
   ```

5. **Accept Terms of Service**
   - Review and accept Twitter Developer Agreement
   - Click "Submit Application"

6. **Verify Your Email**
   - Check your email inbox
   - Click the verification link from Twitter

---

### 2. Create a Project and App

1. **Once Approved (usually instant):**
   - Go to Developer Portal Dashboard
   - Click **"Create Project"**

2. **Project Details:**

   **Project Name:**
   ```
   DEX Token Screener
   ```

   **Use Case:**
   ```
   Making a bot
   ```

   **Project Description:**
   ```
   Social media sentiment analysis for cryptocurrency token screening
   ```

3. **Create an App:**

   **App Name:**
   ```
   dex-sentiment-analyzer-[your-twitter-username]
   ```
   (Must be globally unique - add your username or random numbers if taken)

   **App Environment:**
   ```
   Development
   ```

---

### 3. Get Your API Keys

1. **After Creating the App:**
   - You'll immediately see your API keys
   - **⚠️ SAVE THESE IMMEDIATELY** (you won't see them again!)

2. **Keys You'll Receive:**
   ```
   API Key:           xxxxxxxxxxxxxxxxxxxxxx
   API Key Secret:    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   Bearer Token:      xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx... (long)
   ```

3. **Which Key Do We Need?**
   - ✅ **Bearer Token** ← This is what we need!
   - ❌ API Key (not needed for this setup)
   - ❌ API Key Secret (not needed for this setup)

4. **If You Missed Them:**
   - Go to your app → **"Keys and tokens"** tab
   - Click **"Regenerate"** under Bearer Token
   - Copy the new token immediately

---

### 4. Configure Your DEX Screener

1. **Open the Configuration File:**
   ```bash
   cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
   nano twitter_config.json
   ```

   Or use any text editor to open: `twitter_config.json`

2. **Add Your Bearer Token:**

   Replace `YOUR_BEARER_TOKEN_HERE` with your actual token:

   ```json
   {
     "twitter_bearer_token": "AAAAAAAAAAAAAAAAAAAAABcdefghijklmnopqrstuvwxyz1234567890...",
     "notes": {
       "how_to_get": "Visit https://developer.twitter.com/en/portal/dashboard",
       "tier": "Free tier allows 500,000 tweets per month",
       "rate_limits": "300 requests per 15 minutes for user lookup"
     }
   }
   ```

3. **Save the File:**
   - Press `Ctrl+O` (WriteOut) then `Enter` if using nano
   - Press `Ctrl+X` (Exit) if using nano
   - Or just save normally if using a text editor

---

### 5. Test Your Setup

1. **Run a Test:**
   ```bash
   cd "/Users/leole/workspace/HandsOnAITradingBook/09 DEX Screening Strategies"
   python3 run_with_email_alerts_v2.py
   ```

2. **Look for Success Message:**
   ```
   ✅ Twitter API credentials loaded
   [Social Sentiment] Initialized (API mode)
   ```

3. **Check for Real Data:**
   ```
   [Twitter] Analyzing TOKEN...
     Followers: 15234 (real!)
     Tweets (24h): 127 (real!)
     Engagement: 3.2% (real!)
   ```

---

## Twitter API Tiers & Limits

### Free Tier (What You Get)
- **500,000 tweets/month** (plenty for screening)
- **300 requests per 15 minutes** (user lookups)
- **Tweet search** (last 7 days)
- **User profile data**
- **Follower counts**
- **Tweet metrics**

### Rate Limits for Our Use Case:
- Screening 4-10 tokens every 10 minutes = **~50-100 API calls/hour**
- Free tier limit = **1,200 calls/hour** (300 per 15 min)
- **✅ We're well within limits!**

### What We DON'T Need (Paid Features):
- ❌ Full archive search ($100+/month)
- ❌ Higher rate limits ($100+/month)
- ❌ Premium endpoints ($5,000+/month)

---

## Troubleshooting

### Problem: "403 Forbidden" Error

**Solution:**
- Check your Bearer Token is correct
- Make sure you're using a Project-level token (not standalone app)
- Regenerate your Bearer Token in the developer portal

### Problem: "Too Many Requests" Error

**Solution:**
- You hit rate limits (300 requests per 15 minutes)
- Wait 15 minutes, or
- Reduce screening frequency temporarily

### Problem: "Invalid Token" Error

**Solution:**
- Your token expired or was regenerated
- Get a new token from developer portal
- Update `twitter_config.json`

### Problem: Still Seeing Placeholder Data

**Check:**
1. Is `twitter_config.json` in the correct directory?
   ```bash
   ls -la twitter_config.json
   ```

2. Is the token properly formatted (no quotes inside the token)?
   ```json
   "twitter_bearer_token": "AAAA...",  ← Correct
   "twitter_bearer_token": "\"AAAA...\"",  ← Wrong (extra quotes)
   ```

3. Check the console output:
   ```bash
   python3 run_with_email_alerts_v2.py 2>&1 | grep -i twitter
   ```

---

## Privacy & Security

### Keep Your Token Secret!
- ✅ **DO**: Store in `twitter_config.json` (gitignored)
- ❌ **DON'T**: Commit to GitHub
- ❌ **DON'T**: Share publicly
- ❌ **DON'T**: Hardcode in scripts

### What Twitter Can See:
- Your API requests (which Twitter accounts you lookup)
- Request timestamps
- Your IP address

### What Twitter CANNOT See:
- Your trading decisions
- Your email alerts
- Which tokens you're buying

---

## Optional Enhancements

### 1. Install VADER for Better Sentiment Analysis

```bash
pip install vaderSentiment
```

This improves sentiment accuracy from keyword-based to ML-based.

### 2. Enable Tweet Content Analysis

The current setup uses profile metrics only. To analyze tweet content:

1. Install additional library:
   ```bash
   pip install tweepy
   ```

2. Update `social_sentiment.py` to use Tweepy for tweet fetching

---

## Cost Analysis

| Feature | Free Tier | Paid Tier |
|---------|-----------|-----------|
| Monthly Cost | **$0** | $100+ |
| Tweet Lookups | 500,000/month | Unlimited |
| Rate Limit | 300/15min | Higher |
| Archive Search | 7 days | Full archive |
| **Enough for us?** | **✅ YES** | Overkill |

**Recommendation:** Start with free tier. You won't need paid.

---

## Next Steps After Setup

1. ✅ Complete Twitter API setup above
2. Install VADER: `pip install vaderSentiment`
3. Run test: `python3 run_with_email_alerts_v2.py`
4. Monitor first email alert (within 10 minutes)
5. Verify real Twitter data in email

---

## Support & Resources

- **Twitter Developer Docs:** https://developer.twitter.com/en/docs
- **API Reference:** https://developer.twitter.com/en/docs/twitter-api/users/lookup/api-reference
- **Rate Limits:** https://developer.twitter.com/en/docs/twitter-api/rate-limits
- **Community Forum:** https://twittercommunity.com/

---

## Summary

**Time to Complete:** 10-15 minutes
**Cost:** $0 (free tier)
**Difficulty:** Easy
**Result:** Real Twitter data instead of placeholders

Once set up, you'll get accurate social sentiment scores based on real follower counts, engagement rates, and tweet activity!
