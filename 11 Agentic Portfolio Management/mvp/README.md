# Agentic Portfolio Manager - MVP

A working proof-of-concept AI portfolio manager that uses GPT-4 powered agents to analyze your portfolio and generate trading recommendations.

## What Does It Do?

This MVP demonstrates:
- **Real Portfolio Integration**: Connects to your Alpaca paper trading account
- **AI Agents**: Two specialized agents (Momentum & Risk Manager) analyze your portfolio
- **LLM Reasoning**: GPT-4 provides human-readable explanations for every recommendation
- **Human-in-the-Loop**: You review and approve all trades before execution
- **One-Command Operation**: Simple CLI interface

## Quick Start (15 minutes)

### 1. Get API Keys

**Alpaca (Paper Trading - FREE)**:
1. Go to [https://alpaca.markets](https://alpaca.markets)
2. Sign up for a free account
3. Enable paper trading
4. Get your API keys from dashboard

**OpenAI**:
1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create an API key
3. Add some credits ($5-10 is enough for testing)

### 2. Install Dependencies

```bash
cd mvp

# Install requirements
pip install -r requirements.txt
```

### 3. Configure

```bash
# Create .env file
cp .env.example .env

# Edit with your keys
nano .env
```

Add your keys:
```env
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
OPENAI_API_KEY=sk-your-key-here
```

### 4. Run!

```bash
python main.py
```

## Usage

### Main Menu

```
🤖 Agentic Portfolio Manager - MVP

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
```

### Workflow

1. **Run AI Analysis** - Agents analyze your portfolio (takes ~30-60 seconds)
2. **Review Recommendations** - Read the AI-generated report
3. **Approve Trades** - Decide which recommendations to execute
4. **Execute** - Submit approved orders to Alpaca

## Example Output

```
🤖 RUNNING AGENTIC ANALYSIS
============================================================

1️⃣  Running Momentum Agent...
  [momentum_agent] Fetching market data...
  [momentum_agent] Running LLM analysis...

2️⃣  Running Risk Manager Agent...
  [risk_manager] Calculating risk metrics...
  [risk_manager] Running LLM risk assessment...

3️⃣  Orchestrator synthesizing recommendations...

✅ Analysis complete!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Executive Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Moderate bullish stance. Technology sector shows strong
momentum. Portfolio is well-positioned but consider
diversification into emerging opportunities.

📋 Recommended Actions:

1. BUY NVDA - 10 shares
   Conviction: 85/100
   Reasoning: Strong uptrend supported by AI boom, increasing
   volume confirms momentum, technical indicators bullish
   Estimated: $6,200.00

2. BUY MSFT - 5 shares
   Conviction: 75/100
   Reasoning: Consistent growth, cloud business strong,
   relative strength positive
   Estimated: $2,100.00

⚠️  Risk Assessment:
   Status: healthy
   Concerns: None

Confidence: 80/100
```

## Architecture

```
CLI (main.py)
    ↓
Orchestrator
    ↓
┌────────────────┬──────────────────┬──────────────────┐
↓                ↓                  ↓                  ↓
Momentum Agent   Risk Manager    Sentiment Agent   [Future Agents]
    ↓                ↓                  ↓
    └────────────────┴──────────────────┘
                     ↓
         Alpaca Client + Market Data + News
```

## What's Included

### Agents
- **Momentum Agent**: Analyzes price trends, identifies opportunities
- **Risk Manager**: Checks position sizes, enforces constraints
- **Sentiment Agent**: Analyzes news headlines to gauge market sentiment

### Infrastructure
- **Orchestrator**: Coordinates agents, resolves conflicts
- **Alpaca Client**: Fetches portfolio, executes trades
- **LLM Client**: Interfaces with GPT-4
- **CLI**: User-friendly interface

### Features
- Real-time portfolio data
- Historical market data analysis
- Multi-agent coordination
- Conflict resolution
- Risk constraint enforcement
- Human approval workflow
- Trade execution
- Report generation

## Testing Without Risk

This MVP uses **Alpaca Paper Trading** which means:
- ✅ Real market data
- ✅ Real order flow
- ✅ Real portfolio simulation
- ❌ NO real money at risk

Perfect for testing the system!

## Example Test Workflow

```bash
# 1. Start with a fresh paper account ($100,000 virtual cash)
python main.py

# 2. Run analysis
> 1

# 3. Review recommendations
# Agents will suggest trades based on current market

# 4. Execute some trades
> 3

# 5. Wait a day or a few hours

# 6. Run analysis again
> 1

# See how agents react to your new positions!
```

## Understanding the Output

### Agent Recommendations

Each agent provides:
- **Action**: buy, sell, or hold
- **Quantity**: Number of shares
- **Conviction**: 0-100 confidence score
- **Reasoning**: Human-readable explanation
- **Supporting Data**: Technical indicators, risk metrics

### Orchestrator Synthesis

The orchestrator:
- Aggregates agent recommendations
- Resolves conflicts (e.g., if agents disagree)
- Prioritizes risk management
- Generates final actionable plan

### Example Conflict Resolution

```
Momentum Agent: BUY 50 shares of AAPL (Conviction: 90)
Risk Manager: Position would exceed 10% limit

Orchestrator Decision: BUY 20 shares of AAPL (Conviction: 75)
Reasoning: Strong momentum signal but reduced quantity to
maintain risk constraints
```

## Cost Expectations

### OpenAI API Costs

- Each analysis: ~$0.10-0.30
- Daily usage: ~$1-3
- Monthly: ~$30-90

**Tips to Reduce Costs**:
- Use GPT-3.5-turbo instead of GPT-4 (10x cheaper)
- Run analysis less frequently
- Set spending limits in OpenAI dashboard

### Alpaca

- Paper trading: **FREE**
- No commissions on trades
- No account minimums

## Limitations (MVP)

This is a proof-of-concept with intentional limitations:

- ✅ ~~Only 2 agents~~ **3 agents now!** (momentum + risk + sentiment)
- ❌ Simple momentum analysis (no ML models)
- ✅ ~~No backtesting~~ **Backtesting implemented!** (see `backtest.py`)
- ❌ No database (JSON files only)
- ❌ No web dashboard
- ❌ No real-time updates
- ✅ ~~No sentiment analysis~~ **Sentiment agent implemented!** (see `agents/sentiment.py`)
- ❌ No multi-brokerage support

**For the full system**, see [../IMPLEMENTATION_ROADMAP.md](../IMPLEMENTATION_ROADMAP.md)

## Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### "Invalid API key" errors
- Check your .env file
- Verify keys are correct
- Ensure no extra spaces

### "No data for symbol" errors
- Symbol might be delisted
- Market might be closed
- Try a different symbol

### LLM takes too long
- Normal: 30-60 seconds per analysis
- GPT-4 is thorough but slow
- Use GPT-3.5-turbo for faster results

### Ollama returns empty recommendations
If using Ollama as fallback and getting empty results, the model choice matters:

| Model | Recommendation | Notes |
|-------|---------------|-------|
| `qwen2.5:14b` | **Recommended** | Good balance of speed and quality for structured JSON |
| `llama3.2:8b` | Good alternative | Faster, slightly less capable |
| `mistral:7b` | Good alternative | Fast and reliable |
| `deepseek-r1:*` | Not recommended | Reasoning models are too conservative for trading recommendations |

To change the model, edit `.env`:
```env
OLLAMA_MODEL=qwen2.5:14b
```

Then pull the model: `ollama pull qwen2.5:14b`

### Orders not executing
- Check if market is open (option 5)
- Paper trading queues orders when closed
- Check Alpaca dashboard for order status

## Next Steps

After testing the MVP:

1. **Evaluate**: Is this useful? Does it provide value?
2. **Experiment**: Try different portfolios, market conditions
3. **Learn**: Understand how agents think
4. **Decide**: Build the full production system?

### Backtesting

Run strategy backtests to evaluate historical performance:

**Momentum Strategy:**
```bash
python backtest.py --start 2024-01-01 --end 2025-01-15
```

**Sentiment Strategy:**
```bash
python backtest_sentiment.py --start 2024-01-01 --end 2025-01-15
```

**Compare Both Strategies:**
```bash
python backtest_sentiment.py --compare
```

Example comparison output (2024):
```
               Performance Comparison
┌────────────────┬──────────┬───────────┬──────────┐
│ Metric         │ Momentum │ Sentiment │  Winner  │
├────────────────┼──────────┼───────────┼──────────┤
│ Total Return % │   33.09% │    20.08% │ Momentum │
│ Alpha vs SPY   │   +8.34% │    -4.67% │ Momentum │
│ Sharpe Ratio   │     1.73 │      1.31 │ Momentum │
│ Max Drawdown   │  -14.46% │   -11.27% │ Sentiment│
│ Win Rate       │    50.0% │     44.4% │ Momentum │
│ Profit Factor  │     2.36 │      1.80 │ Momentum │
└────────────────┴──────────┴───────────┴──────────┘
Benchmark (SPY): 24.76%
```

The sentiment strategy uses historical proxies (VIX, gaps, RSI, relative strength) since actual news data isn't available for backtesting.

### Extending the MVP

Easy additions:
- **New agents**: Add sentiment, mean reversion, etc.
- **More symbols**: Expand universe beyond tech stocks
- **Better UI**: Add charts, visualizations

See [../IMPLEMENTATION_ROADMAP.md](../IMPLEMENTATION_ROADMAP.md) for the full roadmap.

## Files

- `main.py` - CLI interface
- `orchestrator.py` - Agent coordinator
- `backtest.py` - Momentum strategy backtesting
- `backtest_sentiment.py` - Sentiment strategy backtesting (with strategy comparison)
- `agents/momentum.py` - Momentum strategy agent
- `agents/risk_manager.py` - Risk management agent
- `agents/sentiment.py` - Sentiment analysis agent (news-based)
- `agents/base.py` - Base agent class
- `alpaca_client.py` - Alpaca integration (with cost basis tracking)
- `llm_client.py` - OpenAI/Gemini integration
- `models.py` - Data models
- `config.py` - Configuration
- `import_portfolio_weighted.py` - Weight-based portfolio import from Robinhood
- `cost_basis.json` - Original purchase prices for P&L tracking
- `data/` - Reports and state

## Support

Questions? Issues?
- Review [../DESIGN.md](../DESIGN.md) for architecture details
- Check [../BROKERAGE_INTEGRATION.md](../BROKERAGE_INTEGRATION.md) for integration help
- See [../QUICK_START.md](../QUICK_START.md) for guidance

## License

[Your License]

---

**Status**: ✅ MVP Complete and Ready to Test

**Built**: December 2025

**Have fun testing! 🚀**
