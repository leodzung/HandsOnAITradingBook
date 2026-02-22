# MVP Setup Guide - Step by Step

Follow these steps exactly to get your MVP running.

## Prerequisites Check

- ✅ Python 3.9+ (You have: 3.9.6)
- ✅ pip installed
- ✅ Internet connection
- ⏳ Alpaca API keys (we'll get these)
- ⏳ OpenAI API key (we'll get these)

## Step 1: Get Alpaca API Keys (5 minutes)

### Option A: Already have Alpaca account?
Skip to Step 2.

### Option B: Create new Alpaca account

1. **Go to**: https://alpaca.markets
2. **Click**: "Sign Up" (top right)
3. **Fill out form**:
   - Email
   - Password
   - Accept terms
4. **Verify email** (check inbox)
5. **Enable Paper Trading**:
   - After login, you'll see "Paper Trading" option
   - This is SAFE - no real money!
   - You get $100,000 virtual cash
6. **Get API Keys**:
   - Go to: https://app.alpaca.markets/paper/dashboard/overview
   - Click "View" next to "Your API Keys"
   - Copy:
     - API Key ID (starts with PK...)
     - Secret Key (starts with...)
   - ⚠️ Keep these SECRET!

**Save these somewhere:**
```
ALPACA_API_KEY=PK...your_key_here...
ALPACA_SECRET_KEY=...your_secret_here...
```

## Step 2: Get OpenAI API Key (5 minutes)

### Option A: Already have OpenAI account?
1. Go to: https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with sk-...)

### Option B: Create new OpenAI account

1. **Go to**: https://platform.openai.com/signup
2. **Sign up** with email or Google
3. **Verify email**
4. **Add payment method**:
   - Go to: https://platform.openai.com/account/billing/overview
   - Add credit card
   - Set spending limit: $10 (recommended for testing)
5. **Create API key**:
   - Go to: https://platform.openai.com/api-keys
   - Click "Create new secret key"
   - Name it: "Agentic Portfolio Manager"
   - Copy the key (starts with sk-...)
   - ⚠️ You can only see this ONCE!

**Save this:**
```
OPENAI_API_KEY=sk-...your_key_here...
```

## Step 3: Install Dependencies (2 minutes)

Run these commands:

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/11 Agentic Portfolio Management/mvp"

# Install required packages
pip3 install -r requirements.txt
```

Expected output:
```
Successfully installed openai-1.10.0 alpaca-trade-api-3.0.0 pandas-2.1.0...
```

If you see errors, try:
```bash
# Update pip first
pip3 install --upgrade pip

# Then retry
pip3 install -r requirements.txt
```

## Step 4: Configure Environment (2 minutes)

```bash
# Create .env file from template
cd "/Users/leole/workspace/HandsOnAITradingBook/11 Agentic Portfolio Management/mvp"
cp .env.example .env

# Edit the file
nano .env
# or
open -e .env  # Opens in TextEdit on Mac
```

**Replace these lines with your actual keys:**

```env
# Replace these:
ALPACA_API_KEY=PK...paste_your_alpaca_key...
ALPACA_SECRET_KEY=...paste_your_alpaca_secret...
OPENAI_API_KEY=sk-...paste_your_openai_key...

# Leave these as-is:
ALPACA_BASE_URL=https://paper-api.alpaca.markets
OPENAI_MODEL=gpt-4-turbo-preview
```

**Save and close the file.**

## Step 5: Test Alpaca Connection (1 minute)

```bash
cd "/Users/leole/workspace/HandsOnAITradingBook/11 Agentic Portfolio Management/mvp"
python3 alpaca_client.py
```

**Expected output:**
```
Fetching portfolio...

Cash: $100,000.00
Portfolio Value: $100,000.00

Positions:
  (none yet)
```

**If you see errors:**
- "Invalid API key" → Check your .env file, make sure keys are correct
- "Module not found" → Run `pip3 install -r requirements.txt` again

## Step 6: Test OpenAI Connection (1 minute)

```bash
python3 llm_client.py
```

**Expected output:**
```
Testing LLM client...

Response: Hello World! I am an AI assistant powered by GPT-4...

Testing JSON response...
JSON Response: {
  "symbol": "AAPL",
  "recommendation": "buy",
  "conviction": 75,
  "reasoning": "Strong fundamentals..."
}
```

**If you see errors:**
- "Invalid API key" → Check your OpenAI key in .env
- "Rate limit" → Wait a minute and try again
- "Insufficient credits" → Add credits to your OpenAI account

## Step 7: Test Individual Agents (2 minutes)

```bash
# Test momentum agent
python3 -c "from agents.momentum import *; import config; config.validate_config(); print('Momentum agent loaded!')"

# Test risk manager
python3 -c "from agents.risk_manager import *; import config; config.validate_config(); print('Risk manager loaded!')"
```

**Expected:** No errors, just success messages.

## Step 8: Run the Full MVP! 🚀

```bash
python3 main.py
```

**You should see:**
```
🤖 Agentic Portfolio Manager - MVP
Powered by GPT-4 and Alpaca Markets

Current Portfolio Summary:
  💵 Cash: $100,000.00
  📊 Portfolio Value: $100,000.00
  📈 Positions: 0

━━━ Main Menu ━━━
1. 🔍 Run AI Analysis
2. 📄 View Last Report
3. ✅ Execute Approved Trades
4. 🔄 Refresh Portfolio
5. 📊 Market Status
6. 🚪 Exit

Select option [1/2/3/4/5/6]:
```

**🎉 Success! The MVP is running!**

## Step 9: Your First Analysis

1. **Press**: `1` (Run AI Analysis)
2. **Wait**: 30-60 seconds (agents are working!)
3. **Review**: Read the recommendations
4. **Decide**: Do you want to execute any trades?

## Troubleshooting

### "ModuleNotFoundError: No module named 'openai'"
```bash
pip3 install -r requirements.txt
```

### "FileNotFoundError: .env file not found"
```bash
cp .env.example .env
# Then edit .env with your keys
```

### "openai.AuthenticationError"
- Your OpenAI API key is wrong or expired
- Check: https://platform.openai.com/api-keys
- Regenerate key if needed

### "alpaca_trade_api.rest.APIError: Invalid API Key"
- Your Alpaca keys are wrong
- Check: https://app.alpaca.markets/paper/dashboard/overview
- Make sure you're using PAPER trading keys, not live

### "Market is closed" message
- Normal! Market hours: 9:30 AM - 4:00 PM ET, Mon-Fri
- You can still run analysis
- Orders will execute when market opens

### Agents take forever
- GPT-4 is thorough but slow (30-60 seconds)
- This is normal
- To speed up: Change to gpt-3.5-turbo in .env (but less accurate)

### "Insufficient credits" (OpenAI)
- Add credits: https://platform.openai.com/account/billing/overview
- $5-10 is enough for lots of testing

## Tips for First Run

1. **Start with analysis only** - Don't execute trades yet
2. **Read the reasoning** - See how agents think
3. **Check multiple times** - Run analysis at different market times
4. **Experiment** - Try executing small trades in paper trading

## What to Expect

### First Analysis (Fresh Portfolio)
- Agents will suggest building initial positions
- Usually 2-4 recommendations
- Mostly tech stocks (AAPL, MSFT, NVDA, etc.)
- Total allocation: ~$20,000-40,000

### After You Have Positions
- Risk manager will check position sizes
- Momentum agent will suggest adjustments
- Orchestrator will balance growth vs. risk

### Reports
- Saved in `data/` folder
- Named: `report_YYYYMMDD_HHMMSS.md`
- Open in any text editor

## Cost Tracking

Each analysis costs approximately:
- **Momentum Agent**: ~$0.05-0.10
- **Risk Manager**: ~$0.02-0.05
- **Orchestrator**: ~$0.05-0.10
- **Total per analysis**: ~$0.12-0.25

Running 5-10 analyses per day = ~$1-2/day

Check your usage: https://platform.openai.com/usage

## Next Steps

Once it's working:

1. **Run multiple analyses** - See how recommendations change
2. **Execute some trades** - Build a paper portfolio
3. **Check daily** - See how agents react to your positions
4. **Review reports** - Understand the reasoning
5. **Experiment** - Modify risk parameters, add symbols

## Need Help?

If you get stuck:
1. Check this guide again
2. Review error messages carefully
3. Check the main README.md
4. Verify your .env file has correct keys

---

**Ready to start? Begin with Step 1!** 🚀
