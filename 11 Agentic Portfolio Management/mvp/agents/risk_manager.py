"""Risk management agent"""
import json
from datetime import datetime
import numpy as np
from models import Portfolio, Recommendation, AgentAnalysis
from agents.base import BaseAgent
import config


class RiskManagerAgent(BaseAgent):
    """Agent that manages portfolio risk"""

    def __init__(self, llm_client):
        super().__init__("risk_manager", llm_client)

    def get_system_prompt(self) -> str:
        return f"""You are a portfolio risk manager. Your role is to assess portfolio risk, enforce position limits, and recommend adjustments to maintain appropriate risk levels.

Risk Constraints:
- Maximum position size: {config.MAX_POSITION_SIZE_PCT * 100}% of portfolio value
- Minimum cash reserve: {config.MIN_CASH_RESERVE_PCT * 100}% of portfolio value
- Target portfolio volatility: < {config.MAX_PORTFOLIO_VOLATILITY * 100}% annualized

Analysis Guidelines:
1. Check if any positions exceed size limits
2. Verify sufficient cash reserves
3. Assess portfolio concentration risk
4. Identify any risky positions
5. Recommend rebalancing if needed

Output Format:
Respond with valid JSON containing:
{{
  "recommendations": [
    {{
      "symbol": "<SYMBOL>",
      "action": "sell",  // Typically "sell" to reduce risk, or "hold"
      "quantity": 5,
      "conviction": 90,
      "reasoning": "Position exceeds maximum size limit...",
      "supporting_data": {{
        "current_allocation_pct": 12.5,
        "max_allocation_pct": 10.0
      }}
    }}
  ],
  "summary": "Brief risk assessment...",
  "confidence": 85,
  "risk_violations": [
    "<SYMBOL> position exceeds 10% limit"
  ],
  "risk_metrics": {{
    "total_exposure": 95.0,
    "cash_reserve_pct": 5.0,
    "largest_position_pct": 12.5,
    "status": "needs_attention"  // or "healthy"
  }}
}}

Important:
- Flag any position over the limit
- Warn if cash reserves are too low
- Consider overall portfolio balance
- Prioritize risk reduction over profit maximization
"""

    def calculate_risk_metrics(self, portfolio: Portfolio) -> dict:
        """Calculate portfolio risk metrics"""
        if portfolio.portfolio_value == 0:
            return {'error': 'Portfolio value is zero'}

        cash_pct = (portfolio.cash / portfolio.portfolio_value) * 100

        positions_by_size = []
        for pos in portfolio.positions:
            allocation_pct = (pos.market_value / portfolio.portfolio_value) * 100
            positions_by_size.append({
                'symbol': pos.symbol,
                'allocation_pct': allocation_pct,
                'market_value': pos.market_value
            })

        positions_by_size.sort(key=lambda x: x['allocation_pct'], reverse=True)

        largest_position_pct = positions_by_size[0]['allocation_pct'] if positions_by_size else 0
        total_exposure = sum(p['allocation_pct'] for p in positions_by_size)

        # Check violations
        violations = []
        for pos in positions_by_size:
            if pos['allocation_pct'] > config.MAX_POSITION_SIZE_PCT * 100:
                violations.append(
                    f"{pos['symbol']} position ({pos['allocation_pct']:.1f}%) exceeds "
                    f"{config.MAX_POSITION_SIZE_PCT * 100}% limit"
                )

        if cash_pct < config.MIN_CASH_RESERVE_PCT * 100:
            violations.append(
                f"Cash reserve ({cash_pct:.1f}%) below "
                f"{config.MIN_CASH_RESERVE_PCT * 100}% minimum"
            )

        status = "needs_attention" if violations else "healthy"

        return {
            'cash_pct': round(cash_pct, 2),
            'total_exposure': round(total_exposure, 2),
            'largest_position_pct': round(largest_position_pct, 2),
            'num_positions': len(portfolio.positions),
            'violations': violations,
            'status': status,
            'positions_by_size': positions_by_size[:5]  # Top 5
        }

    def analyze(self, portfolio: Portfolio) -> AgentAnalysis:
        """Analyze portfolio risk and generate recommendations"""

        # Calculate risk metrics
        print(f"  [{self.agent_id}] Calculating risk metrics...")
        risk_metrics = self.calculate_risk_metrics(portfolio)

        # Build context for LLM
        context = self.format_portfolio_for_llm(portfolio)
        context += "\n\nRisk Analysis:\n"
        context += f"- Cash Reserve: {risk_metrics.get('cash_pct', 0):.2f}%\n"
        context += f"- Total Equity Exposure: {risk_metrics.get('total_exposure', 0):.2f}%\n"
        context += f"- Largest Position: {risk_metrics.get('largest_position_pct', 0):.2f}%\n"
        context += f"- Number of Positions: {risk_metrics.get('num_positions', 0)}\n"

        if risk_metrics.get('violations'):
            context += "\nRisk Violations Detected:\n"
            for violation in risk_metrics['violations']:
                context += f"  ⚠️  {violation}\n"
        else:
            context += "\n✅ No risk violations detected.\n"

        # Get LLM analysis
        print(f"  [{self.agent_id}] Running LLM risk assessment...")
        response = self.llm.complete_json(
            system_prompt=self.get_system_prompt(),
            user_message=f"""Analyze the following portfolio from a risk management perspective.

{context}

Assess:
1. Are any positions too large?
2. Is cash reserve adequate?
3. Is portfolio well-balanced?
4. What adjustments are needed?

Respond with JSON as specified."""
        )

        # Parse response
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

        # Add risk metrics to response
        if 'risk_metrics' not in response:
            response['risk_metrics'] = risk_metrics

        analysis = AgentAnalysis(
            agent_id=self.agent_id,
            timestamp=datetime.now(),
            recommendations=recommendations,
            summary=response.get('summary', 'Risk assessment completed'),
            confidence=response.get('confidence', 80)
        )

        # Store risk metrics for later use
        analysis.risk_metrics = response.get('risk_metrics', {})

        return analysis


if __name__ == '__main__':
    # Test the risk manager agent
    import config
    from llm_client import LLMClient
    from alpaca_client import AlpacaClient

    config.validate_config()

    llm = LLMClient()
    alpaca = AlpacaClient()
    agent = RiskManagerAgent(llm)

    print("Fetching portfolio...")
    portfolio = alpaca.get_portfolio()

    print("\nRunning risk analysis...")
    analysis = agent.analyze(portfolio)

    print(f"\n{analysis.agent_id.upper()} ANALYSIS")
    print("=" * 50)
    print(f"Summary: {analysis.summary}")
    print(f"Confidence: {analysis.confidence}/100")
    print(f"\nRisk Metrics:")
    if hasattr(analysis, 'risk_metrics'):
        for key, value in analysis.risk_metrics.items():
            if key != 'positions_by_size' and key != 'violations':
                print(f"  {key}: {value}")

    print(f"\nRecommendations ({len(analysis.recommendations)}):")
    for rec in analysis.recommendations:
        print(f"\n  {rec.action.upper()} {rec.symbol} - {rec.quantity} shares")
        print(f"  Conviction: {rec.conviction}/100")
        print(f"  Reasoning: {rec.reasoning}")
