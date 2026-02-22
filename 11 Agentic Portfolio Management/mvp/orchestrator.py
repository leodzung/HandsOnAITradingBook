"""Orchestrator that coordinates agents and generates final recommendations"""
from datetime import datetime
from typing import List
import yfinance as yf
from models import Portfolio, AgentAnalysis, OrchestratorReport
from llm_client import LLMClient
from agents.momentum import MomentumAgent
from agents.risk_manager import RiskManagerAgent
from agents.sentiment import SentimentAgent
import config


class Orchestrator:
    """Coordinates agents and synthesizes recommendations"""

    def __init__(self, llm_client: LLMClient, enable_sentiment: bool = True):
        self.llm = llm_client
        self.momentum_agent = MomentumAgent(llm_client)
        self.risk_manager = RiskManagerAgent(llm_client)
        self.sentiment_agent = SentimentAgent(llm_client) if enable_sentiment else None

    def run_analysis(self, portfolio: Portfolio) -> OrchestratorReport:
        """Run all agents and generate final recommendations"""

        print("\n" + "=" * 60)
        print("🤖 RUNNING AGENTIC ANALYSIS")
        print("=" * 60)

        agent_analyses = []

        # Run agents
        print("\n1️⃣  Running Momentum Agent...")
        momentum_analysis = self.momentum_agent.analyze(portfolio)
        agent_analyses.append(momentum_analysis)

        print("\n2️⃣  Running Risk Manager Agent...")
        risk_analysis = self.risk_manager.analyze(portfolio)
        agent_analyses.append(risk_analysis)

        if self.sentiment_agent:
            print("\n3️⃣  Running Sentiment Agent...")
            sentiment_analysis = self.sentiment_agent.analyze(portfolio)
            agent_analyses.append(sentiment_analysis)

        # Synthesize recommendations
        step_num = 4 if self.sentiment_agent else 3
        print(f"\n{step_num}️⃣  Orchestrator synthesizing recommendations...")
        report = self._synthesize_recommendations(
            portfolio,
            agent_analyses
        )

        print("\n✅ Analysis complete!")
        return report

    def _get_top_holdings(self, portfolio: Portfolio, k: int) -> List[dict]:
        """Get top K holdings by market value"""
        if not portfolio.positions:
            return []

        # Sort positions by market value descending
        sorted_positions = sorted(
            portfolio.positions,
            key=lambda p: p.market_value,
            reverse=True
        )

        # Take top K
        top_k = sorted_positions[:k]

        # Format for report
        holdings = []
        for pos in top_k:
            pct = (pos.market_value / portfolio.portfolio_value * 100) if portfolio.portfolio_value > 0 else 0
            holdings.append({
                'symbol': pos.symbol,
                'value': pos.market_value,
                'pct': pct,
                'pl': pos.original_pl,
                'pl_pct': pos.original_pl_pct
            })

        return holdings

    def _correct_estimated_values(self, actions: List[dict]) -> List[dict]:
        """Correct estimated_value using real market prices"""
        for action in actions:
            symbol = action.get('symbol', '')
            quantity = action.get('quantity', 0)

            if symbol and quantity > 0:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1d')
                    if not hist.empty:
                        current_price = hist['Close'].iloc[-1]
                        action['estimated_value'] = round(current_price * quantity, 2)
                        action['current_price'] = round(current_price, 2)
                except Exception as e:
                    print(f"  [orchestrator] Could not get price for {symbol}: {e}")

        return actions

    def _is_valid_recommendation(self, rec: dict, portfolio: Portfolio) -> bool:
        """Validate recommendation against actual portfolio positions"""
        symbol = rec.get('symbol', '')
        action = rec.get('action', '').lower()

        # Skip placeholder symbols from examples
        if symbol.startswith('<') or symbol.startswith('['):
            return False

        # For HOLD/SELL, verify position exists and is significant
        if action in ['hold', 'sell']:
            position = next((p for p in portfolio.positions if p.symbol == symbol), None)
            if not position:
                return False  # Can't hold/sell what we don't have
            if position.market_value < config.MIN_POSITION_VALUE:
                return False  # Position too small
            position_pct = position.market_value / portfolio.portfolio_value if portfolio.portfolio_value > 0 else 0
            if position_pct < config.MIN_POSITION_PCT:
                return False  # Position too small

        return True

    def _synthesize_recommendations(
        self,
        portfolio: Portfolio,
        agent_analyses: List[AgentAnalysis]
    ) -> OrchestratorReport:
        """Use LLM to synthesize agent recommendations"""

        # Build context
        context = f"""Portfolio Status:
- Cash: ${portfolio.cash:,.2f}
- Portfolio Value: ${portfolio.portfolio_value:,.2f}
- Number of Positions: {len(portfolio.positions)}

Agent Analyses:
"""

        for analysis in agent_analyses:
            context += f"\n{analysis.agent_id.upper()}:\n"
            context += f"Summary: {analysis.summary}\n"
            context += f"Confidence: {analysis.confidence}/100\n"
            context += f"Recommendations ({len(analysis.recommendations)}):\n"

            for rec in analysis.recommendations:
                context += f"  - {rec.action.upper()} {rec.symbol}: {rec.quantity} shares "
                context += f"(Conviction: {rec.conviction}/100)\n"
                context += f"    Reasoning: {rec.reasoning}\n"

        # Get orchestrator synthesis
        system_prompt = """You are the Chief Investment Officer coordinating multiple AI agents.
Your role is to synthesize their recommendations into a coherent investment plan.

Guidelines:
1. Resolve conflicts between agents (e.g., if momentum says BUY but risk manager says SELL)
2. Prioritize risk management constraints
3. Create actionable, specific recommendations
4. Explain your reasoning clearly
5. Rate overall confidence based on agent agreement

Respond with JSON:
{
  "executive_summary": "2-3 sentence summary of overall stance and key actions",
  "recommended_actions": [
    {
      "symbol": "<SYMBOL>",
      "action": "buy",
      "quantity": 10,
      "conviction": 80,
      "reasoning": "Why this action makes sense given agent inputs",
      "estimated_value": 1800.00,
      "supporting_agents": ["momentum_agent"],
      "opposing_agents": []
    }
  ],
  "conflicts_resolved": [
    "Example: Momentum agent wanted to buy <SYMBOL> but risk manager flagged concentration"
  ],
  "risk_assessment": {
    "overall_status": "healthy",
    "key_concerns": [],
    "recommendations_compliant": true
  },
  "overall_confidence": 75
}
"""

        response = self.llm.complete_json(
            system_prompt=system_prompt,
            user_message=f"""Synthesize the following agent analyses into final portfolio recommendations.

{context}

Consider:
1. Where do agents agree vs. disagree?
2. How to resolve conflicts?
3. What actions best balance opportunity and risk?
4. Overall portfolio positioning?

Generate final recommendations in JSON format."""
        )

        # Filter out invalid recommendations (negligible positions, hallucinated symbols)
        raw_actions = response.get('recommended_actions', [])
        valid_actions = [
            rec for rec in raw_actions
            if self._is_valid_recommendation(rec, portfolio)
        ]

        # Log if any were filtered
        filtered_count = len(raw_actions) - len(valid_actions)
        if filtered_count > 0:
            print(f"  [orchestrator] Filtered {filtered_count} invalid recommendation(s)")

        # Correct estimated values using real market prices
        valid_actions = self._correct_estimated_values(valid_actions)

        # Get top K holdings
        top_holdings = self._get_top_holdings(portfolio, config.TOP_K_HOLDINGS)

        # Create report
        report = OrchestratorReport(
            timestamp=datetime.now(),
            executive_summary=response.get('executive_summary', 'No summary available'),
            recommended_actions=valid_actions,
            agent_analyses=agent_analyses,
            risk_assessment=response.get('risk_assessment', {}),
            overall_confidence=response.get('overall_confidence', 50),
            top_holdings=top_holdings
        )

        # Store conflicts for reference
        report.conflicts_resolved = response.get('conflicts_resolved', [])

        return report


if __name__ == '__main__':
    # Test the orchestrator
    import config
    from alpaca_client import AlpacaClient

    config.validate_config()

    llm = LLMClient()
    alpaca = AlpacaClient()
    orchestrator = Orchestrator(llm)

    print("Fetching portfolio...")
    portfolio = alpaca.get_portfolio()

    print("\nRunning orchestrated analysis...")
    report = orchestrator.run_analysis(portfolio)

    print("\n" + "=" * 60)
    print("FINAL RECOMMENDATIONS")
    print("=" * 60)
    print(report.to_markdown())

    # Save report
    import os
    report_path = os.path.join(config.DATA_DIR, f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    report.save_to_file(report_path)
    print(f"\n💾 Report saved to: {report_path}")
