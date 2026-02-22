# Agentic Portfolio Management System - Design Document

## Executive Summary

This system implements a **multi-agent portfolio management framework** where specialized LLM-based agents collaborate to analyze markets, coordinate trading strategies, and continuously learn from performance. The system operates in **advisory mode**, providing recommendations to human decision-makers while integrating with QuantConnect for strategy execution.

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent (Chief Investment Officer) │
│                    - Coordinates all agents                       │
│                    - Makes final portfolio recommendations        │
│                    - Manages agent communication                  │
└───────────────────────┬─────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
            ▼               ▼               ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│ Strategy Agents │ │ Research     │ │ Risk Manager    │
│                 │ │ Agent        │ │ Agent           │
│ - Momentum      │ │              │ │                 │
│ - Mean Rev.     │ │ - Backtest   │ │ - Monitor risk  │
│ - ML-Based      │ │ - Analyze    │ │ - Position size │
│ - Sentiment     │ │ - Learn      │ │ - Alerts        │
└────────┬────────┘ └──────┬───────┘ └────────┬────────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   Data & Integration Layer                    │
│                                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ QuantConnect│  │ Market Data  │  │ Performance DB   │   │
│  │ Interface   │  │ APIs         │  │ (Strategy Metrics)│   │
│  └─────────────┘  └──────────────┘  └──────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

## Agent Specifications

### 1. Orchestrator Agent (Chief Investment Officer)

**Role**: Central coordinator that synthesizes inputs from all agents and produces final portfolio recommendations.

**Responsibilities**:
- Aggregate signals from strategy agents
- Balance competing recommendations
- Apply portfolio-level constraints
- Generate human-readable investment thesis
- Track agent performance and adjust trust scores
- Communicate final recommendations to users

**LLM Capabilities**:
- Multi-agent reasoning and decision synthesis
- Natural language explanation generation
- Strategic thinking and trade-off analysis

**Inputs**:
- Strategy agent recommendations
- Risk manager constraints
- Research agent insights
- Current portfolio state

**Outputs**:
- Portfolio allocation recommendations
- Detailed investment thesis (markdown report)
- Confidence scores for each recommendation
- Expected risk/return metrics

---

### 2. Strategy Agents (Specialized Traders)

Each strategy agent specializes in a specific trading approach. Multiple agents run in parallel.

#### 2a. Momentum Strategy Agent

**Responsibilities**:
- Identify trending securities
- Generate momentum-based signals
- Monitor trend strength and duration

**Strategy Source**: Integrates with existing strategies in `06 Applied Machine Learning/`

**Outputs**:
- Long/short recommendations
- Conviction scores (0-100)
- Time horizon (short/medium/long term)
- Supporting data (momentum indicators, trend analysis)

#### 2b. Mean Reversion Strategy Agent

**Responsibilities**:
- Identify oversold/overbought conditions
- Detect statistical arbitrage opportunities
- Monitor reversion catalysts

**Outputs**:
- Trade recommendations
- Expected reversion timeline
- Statistical confidence metrics

#### 2c. ML-Based Strategy Agent

**Responsibilities**:
- Run ML models from existing strategies
- Interpret model predictions
- Assess feature importance and model confidence

**Integration**: Loads trained models from QuantConnect Object Store, queries predictions

**Outputs**:
- ML model predictions
- Feature importance explanations
- Model confidence and uncertainty estimates

#### 2d. Sentiment Analysis Agent

**Responsibilities**:
- Analyze news, social media, earnings calls
- Assess market sentiment shifts
- Detect narrative changes

**Data Sources**:
- Financial news APIs
- Social media (Twitter/Reddit)
- Earnings transcripts
- SEC filings

**Outputs**:
- Sentiment scores per security
- Key narrative themes
- Sentiment change velocity

---

### 3. Research Agent (Continuous Learner)

**Role**: Meta-analyst that studies strategy performance, discovers patterns, and proposes improvements.

**Responsibilities**:
- Analyze strategy performance metrics
- Identify regime-specific performance patterns
- Detect strategy degradation or drift
- Propose parameter adjustments
- Discover new alpha signals
- Run automated backtests

**LLM Capabilities**:
- Pattern recognition in performance data
- Hypothesis generation
- Causal reasoning about strategy failures/successes
- Natural language synthesis of findings

**Workflow**:
1. **Daily**: Analyze previous day's performance
2. **Weekly**: Deep-dive into strategy attribution
3. **Monthly**: Propose and backtest strategy improvements
4. **Continuous**: Monitor for regime changes

**Outputs**:
- Performance reports
- Improvement proposals
- Backtest results
- Research memos on market patterns

---

### 4. Risk Manager Agent

**Role**: Portfolio risk monitor and position sizing advisor.

**Responsibilities**:
- Monitor portfolio risk metrics (VaR, volatility, correlation)
- Enforce position size limits
- Detect concentration risk
- Generate risk alerts
- Recommend hedging strategies

**Inputs**:
- Current portfolio positions
- Proposed trades from strategy agents
- Market volatility data
- Correlation matrices

**Outputs**:
- Risk-adjusted position sizes
- Risk alerts (high priority warnings)
- Hedging recommendations
- Portfolio risk report

**Risk Constraints**:
- Max position size: 10% per security
- Max sector exposure: 30%
- Max portfolio volatility: 15% annualized
- Max drawdown tolerance: -20%

---

## Communication Protocol

### Agent Message Format

All agents communicate using structured JSON messages:

```json
{
  "agent_id": "momentum_agent_001",
  "timestamp": "2025-12-11T10:30:00Z",
  "message_type": "recommendation",
  "content": {
    "symbol": "AAPL",
    "action": "buy",
    "quantity": 100,
    "conviction": 85,
    "time_horizon": "medium",
    "reasoning": "Strong uptrend with increasing volume...",
    "supporting_data": {
      "momentum_score": 0.82,
      "trend_strength": 0.91
    }
  },
  "metadata": {
    "strategy_type": "momentum",
    "confidence_interval": [75, 95]
  }
}
```

### LLM Prompt Templates

Agents use structured prompts with few-shot examples. Example for Orchestrator:

```
You are the Chief Investment Officer of a quantitative hedge fund. Your role is to
synthesize recommendations from specialized strategy agents and make final portfolio
allocation decisions.

Current Portfolio:
{current_portfolio}

Strategy Agent Recommendations:
{agent_recommendations}

Risk Constraints:
{risk_constraints}

Task: Analyze all recommendations, resolve conflicts, and produce a final portfolio
allocation with a clear investment thesis. Explain your reasoning and highlight any
disagreements between agents.

Output Format:
1. Recommended Portfolio Allocation (JSON)
2. Investment Thesis (Markdown)
3. Risk Assessment
4. Confidence Score (0-100)
```

---

## QuantConnect Integration

### Architecture

```
┌─────────────────────────────────┐
│  Agentic Orchestration Layer    │
│  (Python/FastAPI Service)        │
│                                  │
│  - Agents run independently      │
│  - Communicate via message bus   │
│  - Store state in database       │
└──────────────┬──────────────────┘
               │
               │ API Calls
               │
┌──────────────▼──────────────────┐
│  QuantConnect Integration Layer │
│                                  │
│  - QC API Client                 │
│  - Strategy Deployment           │
│  - Data Fetching                 │
│  - Object Store Interface        │
└──────────────┬──────────────────┘
               │
               │
┌──────────────▼──────────────────┐
│  QuantConnect Platform           │
│                                  │
│  - Live/Paper Trading            │
│  - Historical Data               │
│  - Strategy Execution            │
└──────────────────────────────────┘
```

### Integration Points

#### 1. Strategy Signal Extraction

Strategy agents query QuantConnect strategies for signals:

```python
# Agent queries QC strategy via API
qc_client.get_strategy_signals(strategy_id="momentum_v2")

# Returns latest signals from QC algorithm's Object Store
{
  "signals": [
    {"symbol": "AAPL", "signal": 1.0, "timestamp": "..."},
    {"symbol": "MSFT", "signal": 0.5, "timestamp": "..."}
  ]
}
```

#### 2. Backtest Execution

Research Agent can trigger backtests:

```python
# Agent requests backtest with modified parameters
qc_client.run_backtest(
    strategy="momentum_v2",
    parameters={"lookback": 60, "threshold": 0.05},
    start_date="2020-01-01",
    end_date="2024-12-31"
)
```

#### 3. Data Access

All agents can query historical data:

```python
# Fetch history via QC API
qc_client.get_history(
    symbols=["AAPL", "MSFT"],
    start="2024-01-01",
    end="2024-12-11",
    resolution="daily"
)
```

#### 4. Order Execution (Advisory Mode)

Orchestrator generates recommendations; humans approve:

```python
# Generate order recommendations
recommendations = orchestrator.generate_recommendations()

# Human reviews and approves
approved_orders = human_review_ui.review(recommendations)

# Execute approved orders via QC
for order in approved_orders:
    qc_client.place_order(order)
```

---

## Data Flow

### Daily Workflow

1. **Morning (Pre-Market)**:
   - Strategy agents fetch overnight news and data
   - Sentiment agent analyzes news sentiment
   - Research agent reviews previous day's performance

2. **Market Open**:
   - Strategy agents generate signals based on opening data
   - Risk manager assesses current portfolio risk
   - Orchestrator synthesizes signals

3. **Intraday**:
   - Continuous monitoring by risk manager
   - Real-time alerts for significant events
   - Strategy agents update signals if needed

4. **Market Close**:
   - Final signal generation from all strategy agents
   - Orchestrator produces end-of-day recommendations
   - Research agent logs performance data

5. **After-Hours**:
   - Research agent performs deep analysis
   - Backtests for strategy improvements
   - Generate daily report for human review

### Weekly Workflow

- Research agent produces comprehensive performance report
- Strategy agents are re-calibrated if needed
- Orchestrator adjusts agent trust scores based on performance

---

## Technology Stack

### Core Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | LangGraph / CrewAI | Multi-agent orchestration |
| LLM Provider | OpenAI GPT-4 / Anthropic Claude | Agent reasoning engine |
| Message Bus | Redis / RabbitMQ | Inter-agent communication |
| Database | PostgreSQL | Performance tracking, state storage |
| API Framework | FastAPI | REST API for external interfaces |
| QuantConnect Client | Custom Python SDK | QC platform integration |
| Monitoring | Prometheus + Grafana | System health and metrics |

### Agent Implementation

Each agent is a Python class that:
- Wraps an LLM with specific system prompts
- Maintains conversation history and state
- Has access to tools (data fetchers, calculators, backtester)
- Publishes structured messages to the orchestrator

```python
class StrategyAgent:
    def __init__(self, llm, strategy_type, tools):
        self.llm = llm
        self.strategy_type = strategy_type
        self.tools = tools
        self.system_prompt = self._load_system_prompt()

    def generate_recommendation(self, market_data):
        # Use LLM to analyze data and generate recommendation
        prompt = self._build_prompt(market_data)
        response = self.llm.invoke(prompt)
        return self._parse_recommendation(response)
```

---

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
- Set up agent framework infrastructure
- Implement Orchestrator agent
- Create message bus and database schema
- Build QuantConnect API client

### Phase 2: Core Agents (Weeks 3-4)
- Implement 2-3 strategy agents (momentum, mean reversion)
- Implement Risk Manager agent
- Integration testing with QuantConnect

### Phase 3: Intelligence Layer (Weeks 5-6)
- Implement Research Agent
- Add advanced sentiment analysis
- Performance tracking and reporting

### Phase 4: Refinement (Weeks 7-8)
- UI for human review and approval
- Monitoring and alerting
- Documentation and testing
- Production deployment

---

## Example Output

### Daily Recommendation Report

```markdown
# Portfolio Recommendations - December 11, 2025

## Executive Summary
Moderate bullish stance with focus on technology and healthcare sectors.
3 agents recommend increasing equity exposure; risk manager suggests modest
position sizing due to elevated VIX.

## Recommended Actions

1. **BUY AAPL - 150 shares**
   - Conviction: 85/100
   - Supporting Agents: Momentum (90), ML-Based (80)
   - Reasoning: Strong uptrend with positive earnings revision
   - Risk-Adjusted Size: 150 shares (was 200 before risk manager adjustment)

2. **REDUCE TSLA - Sell 50 shares**
   - Conviction: 70/100
   - Supporting Agents: Mean Reversion (75), Risk Manager (80)
   - Reasoning: Overbought on multiple timeframes, reduce concentration
   - Current Position: 200 shares → Recommended: 150 shares

## Agent Disagreements

- **Momentum Agent** (bullish on TSLA) vs **Mean Reversion Agent** (bearish)
- Resolution: Risk manager sided with mean reversion due to concentration risk
- Orchestrator decision: Moderate reduction rather than full exit

## Risk Assessment

- Portfolio Volatility: 12.5% (within 15% limit)
- Max Drawdown (YTD): -8.3% (well within -20% tolerance)
- VaR (95%, 1-day): $8,500
- Sector Concentration: Tech 28%, Healthcare 22% (compliant)

## Research Insights

Recent analysis shows momentum strategies outperforming in current regime
(low vol, steady uptrend). Consider increasing allocation to momentum agent
by 10% next week.

---
Generated by Agentic Portfolio Management System
Orchestrator Agent v1.0
```

---

## Risk Management & Monitoring

### Agent Performance Tracking

Each agent has a **trust score** (0-100) based on:
- Historical recommendation accuracy
- Sharpe ratio of suggested trades
- Consistency with realized outcomes

Orchestrator weights agent recommendations by trust scores.

### System Health Monitoring

- Agent response times
- LLM API latency and costs
- Message bus throughput
- Database query performance

### Failsafes

- If agents disagree significantly, escalate to human
- If risk limits are breached, halt recommendations
- If LLM returns invalid JSON, retry with validation prompt
- Daily sanity checks on recommendations (e.g., no 100% allocation to single stock)

---

## Future Enhancements

1. **Multi-Asset Support**: Extend beyond equities to options, futures, crypto
2. **Adaptive Learning**: Agents automatically adjust their own prompts based on performance
3. **Collaborative Research**: Agents propose hypotheses and debate with each other
4. **Real-Time News Integration**: Sub-second sentiment analysis on breaking news
5. **Voice Interface**: Natural language portfolio queries via voice assistant
6. **Multi-Brokerage**: Integrate with Interactive Brokers, Alpaca, etc.

---

## Conclusion

This agentic portfolio management system combines the reasoning capabilities of LLMs
with the quantitative rigor of QuantConnect strategies. By decomposing portfolio
management into specialized agents that collaborate and learn, the system provides
sophisticated, explainable recommendations while maintaining human oversight.

The hybrid architecture allows leveraging existing QuantConnect strategies while
building a flexible orchestration layer that can expand to other platforms and
asset classes.
