# How to Buy Tokens Found by DEX Screening Strategies

## ⚠️ Important Disclaimer

**LEGITGEM and MOONGEM are demonstration tokens** used in this guide's examples. They are NOT real tokens. When you find real opportunities using the strategies, follow this guide with the actual token contract addresses.

**Critical Warnings:**
- Only invest what you can afford to lose completely
- Early-stage tokens are extremely high risk (90%+ fail)
- Always verify contract addresses on official sources
- Test with small amounts first
- Never share your seed phrase or private keys
- Be aware of impermanent loss, rug pulls, and honeypots

---

## Prerequisites

### 1. Setup a Web3 Wallet

**MetaMask (Most Popular)**
- Install: https://metamask.io/
- Create new wallet or import existing
- **CRITICAL**: Write down your 12-word seed phrase on paper (NEVER digital)
- Store seed phrase in a secure location (safe, bank deposit box)

**Alternative Wallets:**
- Trust Wallet (Mobile-friendly)
- Coinbase Wallet
- Rainbow Wallet
- Phantom (for Solana)

### 2. Fund Your Wallet

You need native blockchain tokens for gas fees:

| Blockchain | Native Token | Where to Buy |
|------------|-------------|--------------|
| Ethereum | ETH | Coinbase, Binance, Kraken |
| BSC | BNB | Binance, Coinbase |
| Solana | SOL | Coinbase, Binance, Kraken |

**How to fund:**
1. Buy ETH/BNB/SOL on a centralized exchange
2. Withdraw to your wallet address
3. **Double-check the address** before confirming
4. Start with small test amount first

### 3. Add Custom Networks (if needed)

**BSC Network Settings:**
```
Network Name: Binance Smart Chain
RPC URL: https://bsc-dataseed.binance.org/
Chain ID: 56
Symbol: BNB
Block Explorer: https://bscscan.com
```

**Other networks** usually auto-detect when you connect to a dApp.

---

## Step-by-Step: Buying a Token on a DEX

### Example: Let's say you found a real token with these details:
```
Token: EXAMPLE
Contract: 0x1234567890abcdef1234567890abcdef12345678
Chain: Ethereum
DEX: Uniswap
Liquidity: $125,000
Your Strategy Score: 92.6/100
```

---

## Method 1: Buy via DEX Website (Recommended for Beginners)

### Ethereum (Uniswap)

**Step 1: Go to Uniswap**
- Visit: https://app.uniswap.org/
- Click "Connect Wallet"
- Select MetaMask and approve connection

**Step 2: Import the Token**
- Click "Select token" dropdown
- Paste the contract address: `0x1234...5678`
- ⚠️ **VERIFY**: Check contract address matches official sources
- Click "Import" (you'll see a warning - normal for new tokens)

**Step 3: Set Trade Parameters**
- From: ETH (or WETH)
- To: EXAMPLE token
- Enter amount (e.g., 0.1 ETH for testing)

**Step 4: Adjust Slippage**
- Click settings icon ⚙️
- Set slippage tolerance:
  - Low volatility: 0.5% - 1%
  - Medium: 1% - 3%
  - High volatility: 3% - 5%
  - New/illiquid tokens: 5% - 12%
- ⚠️ High slippage = higher taxes or price impact

**Step 5: Review and Execute**
```
You pay: 0.1 ETH
You receive: ~X,XXX EXAMPLE (estimated)
Price impact: 0.5%
Network fee: ~$15-50 (varies by gas)
```
- Review carefully
- Click "Swap"
- Confirm in MetaMask
- **Wait for confirmation** (30 seconds - 5 minutes)

**Step 6: Verify Purchase**
- Check transaction on Etherscan: https://etherscan.io/
- Token should appear in your wallet
- If not visible: Add custom token with contract address

---

### BSC (PancakeSwap)

**Similar process:**
1. Go to: https://pancakeswap.finance/swap
2. Connect wallet (switch to BSC network)
3. Import token by contract address
4. Set slippage (BSC tokens often need 5-12%)
5. Swap BNB for token
6. Verify on BSCScan: https://bscscan.com/

---

### Solana (Raydium/Jupiter)

**Raydium:**
1. Go to: https://raydium.io/swap/
2. Connect Phantom wallet
3. Import token by mint address
4. Swap SOL for token

**Jupiter (Aggregator - usually better prices):**
1. Go to: https://jup.ag/
2. Connect wallet
3. Import token
4. Jupiter finds best route across all Solana DEXs

---

## Method 2: Buy via DEX Aggregators (Better Prices)

### 1inch (Multi-chain)
- Website: https://app.1inch.io/
- **Benefit**: Finds best price across multiple DEXs
- **Supports**: Ethereum, BSC, Polygon, Arbitrum, Optimism
- **How it works**: Splits your trade across multiple DEXs for best execution

### Matcha (0x Protocol)
- Website: https://matcha.xyz/
- Similar to 1inch
- Good for Ethereum

### Best for:** Larger trades where 0.5% better price = significant savings

---

## Method 3: Buy via Telegram Bots (Advanced - Fastest for Sniping)

**Popular Bots:**
- Maestro (@MaestroSniperBot)
- Banana Gun (@BananaGunSniper_bot)
- Unibot (@unibotsniper_bot)

**Benefits:**
- Fastest execution (can frontrun others)
- One-click buying
- Auto-slippage adjustment
- MEV protection

**Risks:**
- You give bot access to a wallet (use separate wallet!)
- Higher fees (1-2% per trade)
- Requires learning bot commands

**Setup:**
1. Create NEW wallet just for bot (never use main wallet)
2. Fund with small amount (test)
3. Open bot in Telegram
4. Set up wallet connection
5. Use commands like: `/buy 0x1234...5678 0.1` (buy with 0.1 ETH)

---

## Safety Checklist Before Buying

### 🔍 **Pre-Purchase Verification**

**1. Contract Address Verification**
```bash
✓ Check official website
✓ Verify on CoinGecko/CoinMarketCap
✓ Match with DEX pair info
✓ Cross-reference with team's Twitter/Discord
✗ NEVER trust random addresses from Telegram/Discord DMs
```

**2. Honeypot Check**
- Visit: https://honeypot.is/
- Paste contract address
- Wait for scan results
- ❌ **STOP** if honeypot detected

**3. Contract Scan**
- Visit: https://tokensniffer.com/
- Paste contract address
- Check for red flags:
  - Hidden mint functions
  - Blacklist functions
  - Proxy contracts (can be changed)
  - Excessive taxes

**4. Liquidity Check**
```
✓ Liquidity > $50,000 (for Ethereum)
✓ Liquidity > $20,000 (for BSC)
✓ Liquidity locked (check on Unicrypt/Team Finance)
✓ LP tokens burned
```

**5. Holder Analysis (Etherscan/BSCScan)**
```
⚠️ Top holder > 50% = rug pull risk
⚠️ Many wallets with exact same balance = bot distribution
⚠️ Contract still has 90%+ = team can dump
✓ Top 10 holders < 40% total = good distribution
```

---

## Trading Strategy Based on Strategy Scores

### High-Confidence Entry (Score 90+)
```
✓ Buy immediately
✓ Larger position size (2-5% of portfolio)
✓ Set stop loss at -20%
✓ Take partial profits at +50%, +100%, +200%
```

### Medium-Confidence Entry (Score 75-89)
```
✓ Buy within 1 hour of identification
✓ Moderate position (1-2% of portfolio)
✓ Set stop loss at -15%
✓ Monitor developer activity daily
```

### Low-Confidence Entry (Score 65-74)
```
⚠️ Small position only (0.5-1% of portfolio)
⚠️ Set tight stop loss at -10%
⚠️ Monitor constantly for exit signals
```

### Avoid (Score < 65)
```
❌ DO NOT BUY
❌ Too many red flags
```

---

## Exit Strategy

### Profit-Taking Ladder
```
Price +50%:  Sell 25% (recover initial investment)
Price +100%: Sell 25% (book profits)
Price +200%: Sell 25% (more profits)
Price +500%: Sell remaining (let winners run)
```

### Stop Loss
```
Developer activity drops: Consider exit
Team goes silent (30+ days): Exit immediately
Whale dump alert: Exit immediately
Trading volume dries up: Exit
```

---

## Gas Fee Optimization

### Ethereum Gas Strategies

**1. Check Gas Prices:**
- Visit: https://etherscan.io/gastracker
- Or: https://www.gasprice.io/

**Best times to trade (UTC):**
- Lowest gas: 2AM-6AM (Asian off-hours)
- Medium gas: 8AM-2PM
- Highest gas: 7PM-11PM (US/Europe peak)

**2. Set Custom Gas:**
- MetaMask → Advanced → Custom Gas
- Base fee: Check Etherscan
- Priority fee: 1-2 gwei (normal), 5+ gwei (urgent)

**3. Use Layer 2 (L2) when possible:**
- Arbitrum: Lower fees, same security
- Optimism: Lower fees
- Base: Coinbase's L2

### BSC Gas (Usually $0.20-0.50)
- Gas fees are negligible on BSC
- Set gas price: 3-5 gwei (normal)

### Solana (Usually $0.00025)
- Nearly free transactions
- No gas optimization needed

---

## Example: Complete Trade Walkthrough

**Scenario:** Strategy 1 found LEGITGEM (hypothetical real token)

```yaml
Token: LEGITGEM
Contract: 0x1234567890abcdef1234567890abcdef12345678
Chain: Ethereum
DEX: Uniswap V2
Liquidity: $180,000
Trading Score: 100/100
Developer Score: 98.3/100
Final Score: 99.2/100
```

**Step-by-Step:**

1. **Verify (5 minutes)**
   ```
   ✓ Check honeypot.is → SAFE
   ✓ Check TokenSniffer → Score 95/100
   ✓ Verify contract on Etherscan → Verified
   ✓ Check liquidity lock → Locked for 6 months
   ✓ Check holder distribution → Top 10 = 32% (good)
   ```

2. **Decision: STRONG BUY**
   ```
   Portfolio size: $10,000
   Allocation: 3% = $300
   ```

3. **Execute Trade**
   ```
   - Open Uniswap
   - Connect MetaMask
   - Import token: 0x1234...5678
   - Buy: $300 worth
   - Slippage: 1.5%
   - Gas: $25 (medium priority)
   - Confirm
   ```

4. **Set Alerts**
   ```
   - Add to DexScreener watchlist
   - Set price alerts: +50%, +100%, -20%
   - Monitor GitHub daily
   - Watch team's Twitter
   ```

5. **Take Profits**
   ```
   +50% ($450 value) → Sell 25% ($112.50)
   +100% ($600 value) → Sell 25% more
   Continue according to ladder
   ```

---

## Common Mistakes to Avoid

### ❌ **DON'T:**
1. FOMO buy without verification
2. Buy when gas is $100+ (unless time-critical)
3. Use your entire portfolio on one token
4. Ignore high slippage warnings (>10% = red flag)
5. Trust contract addresses in Telegram/Discord messages
6. Forget to take profits (greed kills gains)
7. Average down on obvious rug pulls
8. Ignore developer activity decline

### ✅ **DO:**
1. Always verify contract address
2. Test with small amount first ($50-100)
3. Set stop losses immediately
4. Take profits systematically
5. Keep detailed trade logs
6. Review mistakes monthly
7. Start small and scale up

---

## Tax Implications

### United States
- Crypto-to-crypto swaps are taxable events
- Track every transaction for IRS reporting
- Use: CoinTracker, Koinly, or TokenTax

### Track Per Trade:
```
Date: 2024-11-02
Buy: 0.1 ETH ($300) → 1,000 LEGITGEM
Sell: 500 LEGITGEM → 0.075 ETH ($450)
Gain: $150 (taxable)
```

---

## Emergency Exit Procedures

### 🚨 If You Suspect a Rug Pull:

**Immediate Actions:**
1. Open DEX (Uniswap/PancakeSwap)
2. Set slippage to 49% (maximum)
3. Swap ALL tokens for ETH/BNB immediately
4. Don't wait - exit NOW
5. Accept any loss (better than 100% loss)

**Signs of Rug Pull:**
- Liquidity suddenly drops 50%+
- Team deletes Telegram/Discord
- Wallet movements to exchanges
- Contract ownership not renounced
- Massive whale dumps

---

## Resources

### Essential Tools
- **Portfolio Tracking**: DexScreener, DeFiLlama
- **Gas Tracking**: Etherscan Gas Tracker
- **Safety**: Honeypot.is, TokenSniffer
- **Charts**: DEXTools, DEXScreener
- **Community**: Twitter Crypto CT, Discord servers

### Learning
- **Courses**: Bankless, DeFi Dad YouTube
- **Communities**: r/CryptoMoonShots (be cautious), Crypto Twitter
- **News**: The Defiant, Bankless, CoinDesk

---

## Final Reminders

1. **These tokens (LEGITGEM, MOONGEM) were demo examples** - not real
2. **When you find real opportunities:**
   - Run them through the strategies first
   - Verify everything independently
   - Start small
   - Take profits
3. **Most early tokens fail** - portfolio approach is key
4. **Never invest more than you can afford to lose completely**
5. **This is not financial advice** - you are responsible for your own trades

---

## Next Steps

Once you have real opportunities from the strategies:

1. Run `python3 demo_developer_ranking.py` with real token data
2. Get developer activity scores
3. If score > 85: Consider buying
4. If score 65-85: Small position
5. If score < 65: Avoid

**Good luck, and trade safely!** 🚀

---

*Last Updated: 2024-11-02*
*Part of: Hands-On AI Trading with Python, QuantConnect, and AWS*
