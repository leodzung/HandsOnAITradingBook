# Live Trading Setup Guide

## 🚀 Quick Start - Run with Real Data

You now have 3 files ready to scan real DEX tokens:

1. **`real_dex_fetcher.py`** - Fetches live data from DexScreener API
2. **`run_live_strategy.py`** - Runs Strategy 1 with real tokens
3. **`config.json`** - Configuration file

### Step 1: Run Your First Live Scan

```bash
cd "09 DEX Screening Strategies"
python3 run_live_strategy.py
```

This will:
- ✅ Connect to DexScreener API (no auth required!)
- ✅ Fetch real pools from Ethereum and BSC
- ✅ Analyze them with Strategy 1 scoring
- ✅ Show you viable opportunities with links

---

## 📊 What You'll See

### Example Output:
```
################################################################################
# LIVE STRATEGY: REAL TOKEN SCANNER
# Fetching data from actual DEXs...
################################################################################

⚙️  Configuration:
  Chains: ethereum, bsc
  Min Liquidity: $20,000
  Max Pool Age: 48h
  Min Safety Score: 60
  Min Opportunity Score: 50

================================================================================
[LIVE SCAN] 2024-11-02 15:30:45
================================================================================

🔍 Scanning ETHEREUM...
[RealDEXFetcher] Searching for new pools on ETHEREUM...
  ✓ NEWTOKEN/WETH - $45,000 - 2.3h old
  ✓ GEMCOIN/WETH - $120,000 - 12.5h old

📊 Analyzing 8 pools...

  NEWTOKEN/WETH
    Safety: 72.5 | Opportunity: 65.3 | Composite: 69.7
    ✓ ACCEPT: High-quality opportunity

  GEMCOIN/WETH
    Safety: 55.2 | Opportunity: 48.1 | Composite: 52.5
    ✗ REJECT: Opportunity score too low

================================================================================
🎯 FOUND 1 OPPORTUNITIES
================================================================================

#1 NEWTOKEN/WETH on ETHEREUM
   Composite Score: 69.7/100
   Safety: 72.5 | Opportunity: 65.3
   Liquidity: $45,000
   24h Volume: $32,000
   Age: 2.3 hours
   DEX: uniswap_v2
   Contract: 0x1234567890abcdef...
   📊 Chart: https://dexscreener.com/ethereum/0x1234...
```

---

## ⚙️ Configuration

### Adjust Scanning Parameters

Edit `run_live_strategy.py` at the bottom:

```python
scanner = LivePoolScanner(
    chains=['ethereum', 'bsc'],      # Which chains to scan
    min_liquidity_usd=20000,         # Minimum liquidity ($)
    max_pool_age_hours=48,           # Maximum pool age (hours)
    min_safety_score=60,             # Minimum safety threshold
    min_opportunity_score=50         # Minimum opportunity threshold
)
```

### Recommended Settings by Risk Profile:

**Conservative (Safety First):**
```python
min_liquidity_usd=50000      # Higher liquidity
max_pool_age_hours=168       # 1 week old (more proven)
min_safety_score=75          # Higher safety
min_opportunity_score=60
```

**Moderate (Balanced):**
```python
min_liquidity_usd=20000
max_pool_age_hours=48
min_safety_score=65
min_opportunity_score=55
```

**Aggressive (Early Entry):**
```python
min_liquidity_usd=10000      # Lower liquidity OK
max_pool_age_hours=12        # Very new pools
min_safety_score=55          # More risk tolerance
min_opportunity_score=50
```

---

## 🔑 API Keys (Optional but Recommended)

The current setup uses **DexScreener's free API** (no auth required). For more features, add API keys to `config.json`:

### 1. Etherscan API (Contract Verification)
```
Visit: https://etherscan.io/apis
Sign up (free)
Copy API key to config.json: "etherscan": "YOUR_KEY"
```

**Benefits:**
- Verify contract source code
- Check if contract is verified
- Get transaction history
- Check token holder counts

### 2. BSCScan API (For BSC Tokens)
```
Visit: https://bscscan.com/apis
Sign up (free)
Copy API key to config.json: "bscscan": "YOUR_KEY"
```

### 3. Moralis API (Token Metadata)
```
Visit: https://moralis.io/
Sign up (free tier: 40k requests/day)
Copy API key to config.json: "moralis": "YOUR_KEY"
```

**Benefits:**
- Token holder distribution
- Wallet balances
- NFT data
- Cross-chain support

### 4. Honeypot Detection (Critical!)
```
Option 1: Honeypot.is API
  Visit: https://honeypot.is/
  Use their API: https://api.honeypot.is/v2/IsHoneypot

Option 2: GoPlus Security API (Free)
  Visit: https://gopluslabs.io/
  Sign up for free API access
```

---

## 📈 Running Continuously

### Option 1: Run in Loop

Modify `run_live_strategy.py` to add continuous scanning:

```python
def main_continuous():
    scanner = LivePoolScanner(...)

    while True:
        try:
            opportunities = scanner.scan_and_analyze()

            if opportunities:
                scanner.print_full_summary()

            # Wait 5 minutes between scans
            print("\n⏳ Waiting 5 minutes until next scan...")
            time.sleep(300)

        except KeyboardInterrupt:
            print("\n\nStopped by user")
            scanner.print_full_summary()
            break
        except Exception as e:
            print(f"\n⚠️  Error: {e}")
            time.sleep(60)  # Wait 1 minute on error

if __name__ == "__main__":
    main_continuous()
```

### Option 2: Use Cron Job (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add line to run every 10 minutes
*/10 * * * * cd /path/to/09\ DEX\ Screening\ Strategies && python3 run_live_strategy.py >> scan_log.txt 2>&1
```

### Option 3: Use Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., every 10 minutes)
4. Action: Start Program
5. Program: `python3`
6. Arguments: `run_live_strategy.py`
7. Start in: Your strategy directory

---

## 🔔 Set Up Alerts

### Discord Webhook

1. Create Discord server or use existing
2. Server Settings → Integrations → Webhooks
3. Create Webhook, copy URL
4. Add to `config.json`:
   ```json
   "notifications": {
     "discord_webhook": "https://discord.com/api/webhooks/..."
   }
   ```

### Send Alert Function

Add to `run_live_strategy.py`:

```python
import requests

def send_discord_alert(opportunity):
    webhook_url = scanner.fetcher.config.get('notifications', {}).get('discord_webhook')

    if not webhook_url:
        return

    message = {
        "content": f"🚨 **New Opportunity Found!**",
        "embeds": [{
            "title": f"{opportunity.pair_symbol} on {opportunity.chain.upper()}",
            "description": f"Composite Score: {opportunity.composite_score:.1f}/100",
            "color": 5814783,  # Green
            "fields": [
                {"name": "Safety", "value": f"{opportunity.safety_score:.1f}", "inline": True},
                {"name": "Opportunity", "value": f"{opportunity.opportunity_score:.1f}", "inline": True},
                {"name": "Liquidity", "value": f"${opportunity.liquidity_usd:,.0f}", "inline": True},
                {"name": "Volume 24h", "value": f"${opportunity.volume_24h:,.0f}", "inline": True},
                {"name": "Age", "value": f"{opportunity.age_hours:.1f}h", "inline": True},
                {"name": "Contract", "value": opportunity.token_address[:20] + "...", "inline": False},
                {"name": "Chart", "value": opportunity.dexscreener_url, "inline": False}
            ]
        }]
    }

    try:
        requests.post(webhook_url, json=message)
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")
```

Call after finding opportunity:
```python
if opportunity.composite_score >= 75:  # Only alert for high scores
    send_discord_alert(opportunity)
```

---

## 📊 Data Sources Used

### Currently Integrated (Free):
1. **DexScreener API**
   - Endpoint: `https://api.dexscreener.com/`
   - Features: Pool data, price, volume, liquidity
   - Rate Limit: ~300 requests/minute
   - No auth required ✅

### Recommended Additions:

2. **The Graph** (Advanced)
   - Endpoint: Various subgraphs per DEX
   - Uniswap: `https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2`
   - PancakeSwap: Similar
   - Features: Historical data, custom queries
   - Free tier: Good limits

3. **CoinGecko API**
   - Endpoint: `https://api.coingecko.com/api/v3/`
   - Features: Price data, market data
   - Free tier: 10-50 calls/minute

4. **Token Sniffer**
   - Website: https://tokensniffer.com/
   - Manual checks or API integration
   - Security scoring

---

## 🛡️ Safety Verification Workflow

When the scanner finds an opportunity, **ALWAYS** do these checks:

### 1. Check DexScreener Chart (Automated)
```
Click the provided DexScreener URL
Look for:
  ✓ Smooth price action (not pumpy)
  ✓ Consistent volume
  ✓ No massive spikes/dumps
```

### 2. Honeypot Check (Manual for now)
```bash
# Visit: https://honeypot.is/
# Paste token contract address
# Wait for results
```

**Red Flags:**
- ❌ "Unable to sell"
- ❌ Sell tax > 10%
- ❌ Hidden fees
- ❌ Blacklist functions

### 3. Contract Verification (Etherscan/BSCScan)
```
Visit: https://etherscan.io/address/[CONTRACT]
Check:
  ✓ Contract is verified (source code visible)
  ✓ No suspicious functions (mint, blacklist)
  ✓ Ownership renounced or locked
  ✓ Liquidity locked
```

### 4. Holder Analysis
```
On Etherscan, go to "Holders" tab
Check:
  ✓ Top holder < 50% (preferably < 30%)
  ✓ At least 50+ holders
  ✓ No wallets with identical balances (bot pattern)
```

### 5. Social Verification
```
Search token name + symbol on:
  - Twitter (official account?)
  - Telegram (active community?)
  - Discord (real engagement?)
  - Website (professional?)
```

**If ALL checks pass → Consider buying**
**If ANY check fails → REJECT**

---

## 📈 Example Trade Execution

Let's say the scanner found:

```
Token: NEWGEM
Contract: 0xabc123...
Chain: Ethereum
Composite Score: 82.5/100
Safety: 85.0 | Opportunity: 78.5
Liquidity: $65,000
```

### Step-by-Step:

**1. Verify (5-10 minutes)**
```
✅ DexScreener: Good chart, steady growth
✅ Honeypot.is: SAFE
✅ Etherscan: Verified contract
✅ Holders: Top 10 = 28% (good)
✅ Twitter: 2.5k followers, active
```

**2. Decision: BUY**
```
Score: 82.5/100 (high confidence)
Position Size: 2% of portfolio = $200
```

**3. Execute on Uniswap**
```
- Connect MetaMask
- Import token: 0xabc123...
- Buy $200 worth
- Set stop loss: -20% ($160)
```

**4. Set Alerts**
```
DexScreener: Price alerts at +50%, +100%
Portfolio tracker: Add to watchlist
Calendar: Review in 24h, 72h, 7d
```

**5. Take Profits**
```
+50% ($300) → Sell 25% ($75) - Recover partial investment
+100% ($400) → Sell 25% ($100) - Take profits
+200% ($600) → Sell 25% ($150) - More profits
Let remaining ride
```

---

## ⚠️ Common Issues & Solutions

### Issue: "No pools found"
**Solutions:**
- Reduce `min_liquidity_usd` (try $5,000)
- Increase `max_pool_age_hours` (try 72h or 168h)
- Lower score thresholds
- Check different chains

### Issue: "API rate limit exceeded"
**Solutions:**
- Increase `self.min_request_interval` in `real_dex_fetcher.py`
- Add longer sleep between scans
- Use API keys for higher limits

### Issue: "All tokens rejected"
**Solutions:**
- Review rejection reasons in output
- Adjust thresholds based on what's failing
- Market may be slow - wait and scan later

### Issue: "Connection errors"
**Solutions:**
- Check internet connection
- Try different time (API maintenance?)
- Add retry logic with exponential backoff

---

## 🎯 Next Steps

### Immediate:
1. ✅ Run `python3 run_live_strategy.py`
2. ✅ Review any opportunities found
3. ✅ Adjust filters based on results
4. ✅ Set up continuous scanning

### Short-term:
1. Get API keys (Etherscan, BSCScan)
2. Implement honeypot checking
3. Set up Discord/Telegram alerts
4. Create portfolio tracking spreadsheet

### Long-term:
1. Integrate developer activity checking
2. Add Strategy 2 (Smart Money) with real data
3. Add Strategy 3 (Anomaly Detection)
4. Build dashboard for monitoring
5. Implement automated trading (very advanced!)

---

## 📚 Additional Resources

### APIs & Tools:
- DexScreener: https://dexscreener.com/
- DexTools: https://www.dextools.io/
- Honeypot.is: https://honeypot.is/
- Token Sniffer: https://tokensniffer.com/
- Etherscan: https://etherscan.io/
- BSCScan: https://bscscan.com/

### Learning:
- Uniswap Docs: https://docs.uniswap.org/
- PancakeSwap Docs: https://docs.pancakeswap.finance/
- The Graph: https://thegraph.com/docs/

### Communities:
- r/CryptoMoonShots (Reddit)
- Crypto Twitter (#CT)
- Various Discord servers (be cautious!)

---

## ⚠️ Final Warnings

1. **Start with very small amounts** ($50-100)
2. **Most early tokens fail** - expect losses
3. **Never invest more than you can afford to lose**
4. **Verify everything** - trust the data, not the hype
5. **Take profits systematically** - greed kills gains
6. **Use stop losses** - protect your capital
7. **Track all trades** - learn from mistakes
8. **This is not financial advice** - you're responsible

**Good luck, trade safely, and may your strategies find the next gem! 🚀**

---

*Last Updated: 2024-11-02*
*Part of: Hands-On AI Trading with Python, QuantConnect, and AWS*
