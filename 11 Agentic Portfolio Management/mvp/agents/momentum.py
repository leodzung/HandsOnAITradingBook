"""Momentum strategy agent"""
import json
from datetime import datetime
from models import Portfolio, Recommendation, AgentAnalysis
from agents.base import BaseAgent
import config


class MomentumAgent(BaseAgent):
    """Agent that identifies momentum opportunities"""

    def __init__(self, llm_client):
        super().__init__("momentum_agent", llm_client)
        # Universe will be derived from portfolio's top holdings
        self.max_symbols = config.TOP_K_HOLDINGS  # Analyze top K holdings

    def get_system_prompt(self) -> str:
        return """You are a momentum trading specialist. Your role is to identify securities with strong price trends and generate buy/sell recommendations.

Analysis Guidelines:
1. Look for stocks with clear uptrends or downtrends
2. Consider volume confirmation
3. Evaluate whether momentum is sustainable
4. For existing positions, decide if momentum supports holding or taking profits
5. Recommend position sizes based on conviction

Output Format:
Respond with valid JSON containing:
{
  "recommendations": [
    {
      "symbol": "<SYMBOL>",
      "action": "buy",  // or "sell" or "hold"
      "quantity": 10,
      "conviction": 85,  // 0-100
      "reasoning": "Strong uptrend with increasing volume...",
      "supporting_data": {
        "trend": "bullish",
        "volume_confirmation": true
      }
    }
  ],
  "summary": "Brief summary of market momentum...",
  "confidence": 80  // Overall confidence 0-100
}

Important:
- Only recommend buys if portfolio has sufficient cash
- Consider existing positions when making recommendations
- Be realistic about conviction scores
- Provide clear, actionable reasoning
"""

    def _get_universe_from_portfolio(self, portfolio: Portfolio) -> list:
        """Get top holdings from portfolio as the analysis universe"""
        if not portfolio.positions:
            return []

        # Sort by market value and take top K (excluding negligible positions)
        significant_positions = [
            pos for pos in portfolio.positions
            if not self.is_position_negligible(pos, portfolio.portfolio_value)
        ]
        sorted_positions = sorted(
            significant_positions,
            key=lambda p: p.market_value,
            reverse=True
        )
        return [pos.symbol for pos in sorted_positions[:self.max_symbols]]

    def analyze(self, portfolio: Portfolio) -> AgentAnalysis:
        """Analyze momentum and generate recommendations"""

        # Get universe from portfolio's top holdings
        universe = self._get_universe_from_portfolio(portfolio)
        if not universe:
            print(f"  [{self.agent_id}] No significant positions to analyze")
            return AgentAnalysis(
                agent_id=self.agent_id,
                timestamp=datetime.now(),
                recommendations=[],
                summary="No significant positions in portfolio to analyze for momentum.",
                confidence=0
            )

        print(f"  [{self.agent_id}] Analyzing top {len(universe)} holdings: {', '.join(universe[:5])}...")

        # Fetch market data for universe
        print(f"  [{self.agent_id}] Fetching market data...")
        market_data = self.get_multiple_symbols(universe, config.LOOKBACK_DAYS)

        # Build context for LLM
        context = self.format_portfolio_for_llm(portfolio)
        context += "\n\nMarket Data Analysis:\n"

        for symbol, df in market_data.items():
            if not df.empty:
                context += self.format_market_data_for_llm(symbol, df)

        # Get LLM analysis
        print(f"  [{self.agent_id}] Running LLM analysis...")
        response = self.llm.complete_json(
            system_prompt=self.get_system_prompt(),
            user_message=f"""Analyze the following portfolio and market data to generate momentum-based trading recommendations.

{context}

Consider:
1. Which stocks show strong momentum?
2. Should any existing positions be adjusted?
3. What new opportunities exist?
4. What is the overall market momentum?

Respond with JSON as specified."""
        )

        # Parse response into recommendations
        recommendations = []
        if response and 'recommendations' in response:
            for rec_data in response['recommendations']:
                rec = Recommendation(
                    symbol=rec_data.get('symbol', ''),
                    action=rec_data.get('action', 'hold'),
                    quantity=rec_data.get('quantity', 0),
                    conviction=rec_data.get('conviction', 50),
                    reasoning=rec_data.get('reasoning', ''),
                    agent_id=self.agent_id,
                    supporting_data=rec_data.get('supporting_data', {})
                )
                recommendations.append(rec)

        analysis = AgentAnalysis(
            agent_id=self.agent_id,
            timestamp=datetime.now(),
            recommendations=recommendations,
            summary=response.get('summary', 'No summary available'),
            confidence=response.get('confidence', 50)
        )

        return analysis


if __name__ == '__main__':
    # Test the momentum agent
    import config
    from llm_client import LLMClient
    from alpaca_client import AlpacaClient

    config.validate_config()

    llm = LLMClient()
    alpaca = AlpacaClient()
    agent = MomentumAgent(llm)

    print("Fetching portfolio...")
    portfolio = alpaca.get_portfolio()

    print("\nRunning momentum analysis...")
    analysis = agent.analyze(portfolio)

    print(f"\n{analysis.agent_id.upper()} ANALYSIS")
    print("=" * 50)
    print(f"Summary: {analysis.summary}")
    print(f"Confidence: {analysis.confidence}/100")
    print(f"\nRecommendations ({len(analysis.recommendations)}):")
    for rec in analysis.recommendations:
        print(f"\n  {rec.action.upper()} {rec.symbol} - {rec.quantity} shares")
        print(f"  Conviction: {rec.conviction}/100")
        print(f"  Reasoning: {rec.reasoning}")
