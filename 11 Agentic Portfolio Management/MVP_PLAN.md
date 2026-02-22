# MVP Implementation Plan

## Goal
Build a working proof-of-concept in **1-2 days** that demonstrates:
- LLM agents analyzing portfolio and market data
- Generating actionable trading recommendations
- Human review and approval workflow

## Scope: What's IN the MVP

### ✅ Core Features
1. **Portfolio Integration**
   - Fetch current portfolio from Alpaca (paper trading)
   - Display positions and cash balance

2. **Two Simple Agents**
   - **Momentum Agent**: Analyzes price trends, recommends buys/sells
   - **Risk Manager**: Checks position sizes, portfolio balance

3. **Basic Orchestrator**
   - Collects agent recommendations
   - Synthesizes into actionable plan
   - Generates markdown report

4. **CLI Interface**
   - View current portfolio
   - Run agent analysis
   - Approve/reject recommendations
   - Execute approved trades

5. **Simple State Management**
   - JSON files for agent history
   - No database required

### ❌ NOT in MVP (Save for Later)
- Multiple brokerages
- Research agent with backtesting
- Web dashboard
- Database/persistent storage
- Message bus/async communication
- Complex monitoring
- Authentication
- Production deployment

## MVP Architecture

```
┌─────────────────────────────────────────┐
│          CLI Interface                   │
│   - View portfolio                       │
│   - Run analysis                         │
│   - Approve trades                       │
└─────────────┬───────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────┐
│       Simple Orchestrator                │
│   - Coordinates agents                   │
│   - Generates recommendations            │
└─────────────┬───────────────────────────┘
              │
        ┌─────┴─────┐
        ▼           ▼
┌──────────────┐ ┌──────────────┐
│  Momentum    │ │  Risk        │
│  Agent       │ │  Manager     │
└──────┬───────┘ └──────┬───────┘
       │                │
       └────────┬───────┘
                ▼
      ┌──────────────────┐
      │  Alpaca Adapter  │
      │  (Paper Trading) │
      └──────────────────┘
```

## File Structure (MVP Only)

```
mvp/
├── README.md                 # Quick start guide
├── requirements.txt          # Minimal dependencies
├── .env.example             # Configuration
├── config.py                # Settings loader
├── models.py                # Data classes
├── alpaca_client.py         # Alpaca integration
├── llm_client.py            # OpenAI/Anthropic wrapper
├── agents/
│   ├── base.py              # Base agent class
│   ├── momentum.py          # Momentum strategy agent
│   └── risk_manager.py      # Risk management agent
├── orchestrator.py          # Coordinates agents
├── main.py                  # CLI entry point
└── data/                    # JSON state files
    ├── portfolio.json
    ├── recommendations.json
    └── agent_history.json
```

## Dependencies (Minimal)

```txt
# LLM
openai==1.10.0
# or anthropic==0.8.0

# Brokerage
alpaca-trade-api==3.0.0

# Data
pandas==2.1.0
yfinance==0.2.0

# Utilities
python-dotenv==1.0.0
rich==13.7.0  # For nice CLI output
```

## Implementation Steps

### Day 1: Core Infrastructure (4-6 hours)

**Step 1: Setup (30 min)**
- Create MVP directory structure
- Install dependencies
- Configure Alpaca paper trading account

**Step 2: Alpaca Integration (1 hour)**
- Simple client to fetch portfolio
- Get positions and cash balance
- Test with paper account

**Step 3: LLM Wrapper (1 hour)**
- Simple OpenAI/Anthropic client
- Structured prompt templates
- JSON response parsing

**Step 4: Base Agent Class (1 hour)**
- Simple agent framework
- System prompts
- Tool calling (market data, portfolio data)

**Step 5: Momentum Agent (1-2 hours)**
- Fetch recent price data
- Calculate momentum indicators
- Generate buy/sell recommendations
- Test with real data

### Day 2: Orchestration & Interface (4-6 hours)

**Step 6: Risk Manager Agent (1-2 hours)**
- Check position sizes
- Calculate portfolio metrics
- Flag violations

**Step 7: Orchestrator (2 hours)**
- Collect agent recommendations
- Resolve conflicts
- Generate markdown report

**Step 8: CLI Interface (2 hours)**
- Menu-driven interface
- View portfolio command
- Run analysis command
- Approve/execute command

**Step 9: Testing (1-2 hours)**
- End-to-end test
- Fix bugs
- Document usage

## MVP User Flow

```bash
$ python mvp/main.py

🤖 Agentic Portfolio Manager - MVP
===================================

Current Portfolio:
  Cash: $100,000.00
  Positions:
    - AAPL: 10 shares @ $180.50 ($1,805.00)
    - MSFT: 5 shares @ $420.00 ($2,100.00)
  Total Value: $103,905.00

Commands:
  1. Run Analysis
  2. View Last Recommendations
  3. Execute Approved Trades
  4. Refresh Portfolio
  5. Exit

> 1

Running agent analysis...

🔄 Momentum Agent analyzing...
🔄 Risk Manager analyzing...
🔄 Orchestrator synthesizing...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RECOMMENDATIONS - 2025-12-11 14:30
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Executive Summary
Moderate bullish stance. Momentum favors tech sector.
Risk manager suggests maintaining current allocation.

## Recommended Actions

1. BUY NVDA - 8 shares
   Conviction: 85/100
   Reasoning: Strong uptrend, positive momentum indicators
   Estimated Cost: $4,960.00

2. TRIM AAPL - Sell 3 shares
   Conviction: 60/100
   Reasoning: Take profits, rebalance portfolio
   Estimated Proceeds: $541.50

## Risk Assessment
✅ All positions within limits
✅ Portfolio volatility: 12.3% (target: <15%)
✅ Cash available: $95,094.00

Approve these recommendations? (y/n): y

✅ Recommendations approved and saved.

Execute now? (y/n): y

Executing trades...
  ✅ Bought 8 shares of NVDA @ $620.00
  ✅ Sold 3 shares of AAPL @ $180.50

Done! Portfolio updated.
```

## Success Criteria

MVP is successful if:
- ✅ Can fetch real portfolio from Alpaca
- ✅ Agents generate reasonable recommendations
- ✅ Recommendations are human-readable and actionable
- ✅ Can execute approved trades
- ✅ Takes <5 minutes to run analysis
- ✅ Code is <500 lines total

## Timeline

**Day 1 Morning** (3 hours):
- Setup + Alpaca integration + LLM wrapper

**Day 1 Afternoon** (3 hours):
- Base agent + Momentum agent

**Day 2 Morning** (3 hours):
- Risk manager + Orchestrator

**Day 2 Afternoon** (3 hours):
- CLI interface + Testing

**Total: 12-16 hours** spread over 1-2 days

## What We Learn from MVP

1. **Do LLM agents actually help?** Test if GPT-4 provides valuable insights
2. **Is the workflow intuitive?** Test human-in-the-loop approval
3. **Are recommendations actionable?** See if trades make sense
4. **What's missing?** Identify gaps for full version

## After MVP: Next Steps

Once MVP works:
1. **Evaluate**: Did it provide value? Was it useful?
2. **Decide**: Continue to full production system?
3. **Plan**: Which features to add next?
   - More agents (sentiment, mean reversion)
   - Research agent with backtesting
   - Web dashboard
   - Multiple brokerages
   - Production deployment

## Getting Started Now

```bash
# 1. Create MVP directory
cd "11 Agentic Portfolio Management"
mkdir mvp
cd mvp

# 2. Set up Alpaca paper trading
# Go to: https://alpaca.markets
# Sign up for paper trading (free)
# Get API keys

# 3. Create .env file
cat > .env << EOF
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
OPENAI_API_KEY=your_openai_key
EOF

# 4. Install dependencies
pip install openai alpaca-trade-api pandas yfinance python-dotenv rich

# 5. Run MVP (once I create it)
python main.py
```

Ready to build it? 🚀
