"""Sentiment analysis agent using news and social data"""
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import yfinance as yf
from models import Portfolio, Recommendation, AgentAnalysis
from agents.base import BaseAgent
import config


class SentimentAgent(BaseAgent):
    """Agent that analyzes news sentiment to generate trading signals"""

    def __init__(self, llm_client):
        super().__init__("sentiment_agent", llm_client)
        # Universe will be derived from portfolio's top holdings
        self.max_symbols = config.TOP_K_HOLDINGS  # Analyze top K holdings
        self.max_news_per_symbol = 5  # Limit news articles per symbol

    def get_system_prompt(self) -> str:
        return """You are a sentiment analysis specialist for financial markets. Your role is to analyze news headlines and articles to gauge market sentiment and generate trading recommendations.

Analysis Guidelines:
1. Assess overall sentiment (bullish, bearish, neutral) for each stock
2. Identify significant news events that could impact stock prices
3. Distinguish between short-term noise and meaningful developments
4. Consider how news might affect the stock over different timeframes
5. Weight recent news more heavily than older news
6. Look for sentiment divergences (stock down on good news = potential opportunity)

Sentiment Scoring:
- Very Bullish: Multiple positive catalysts, strong momentum in sentiment
- Bullish: Generally positive news, favorable developments
- Neutral: Mixed news or lack of significant developments
- Bearish: Negative news, unfavorable developments
- Very Bearish: Multiple negative catalysts, serious concerns

Output Format:
Respond with valid JSON containing:
{
  "recommendations": [
    {
      "symbol": "<SYMBOL>",
      "action": "buy",  // or "sell" or "hold"
      "quantity": 10,
      "conviction": 75,  // 0-100
      "reasoning": "Recent announcements received positive reception...",
      "supporting_data": {
        "sentiment_score": 0.7,  // -1 to 1
        "sentiment_label": "bullish",
        "key_headlines": ["Company announces strong results", "..."],
        "sentiment_drivers": ["product launch", "earnings beat"]
      }
    }
  ],
  "market_sentiment_summary": "Overall market sentiment is cautiously optimistic...",
  "summary": "Brief summary of sentiment signals across the universe",
  "confidence": 70  // Overall confidence 0-100
}

Important:
- Only recommend actions when sentiment is clearly directional
- High conviction requires multiple confirming news sources
- Consider existing positions when making recommendations
- Be skeptical of single-source sentiment signals
"""

    def get_news(self, symbol: str) -> List[Dict]:
        """Fetch recent news for a symbol using yfinance"""
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news

            if not news:
                return []

            # Process and limit news articles
            processed_news = []
            for article in news[:self.max_news_per_symbol]:
                # Handle new yfinance format where data is nested under 'content'
                content = article.get('content', article)

                # Extract title
                title = content.get('title', '')

                # Extract publisher
                provider = content.get('provider', {})
                publisher = provider.get('displayName', '') if isinstance(provider, dict) else str(provider)

                # Extract link
                canonical = content.get('canonicalUrl', {})
                link = canonical.get('url', '') if isinstance(canonical, dict) else ''

                # Extract publish date
                pub_date = content.get('pubDate', '')
                if pub_date:
                    try:
                        # Parse ISO format date
                        dt = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        published = dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        published = pub_date[:16] if len(pub_date) > 16 else pub_date
                else:
                    published = 'Unknown'

                # Extract summary
                summary = content.get('summary', '') or content.get('description', '')
                summary = summary[:500] if summary else ''

                if title:  # Only add if we have a title
                    processed_news.append({
                        'title': title,
                        'publisher': publisher,
                        'link': link,
                        'published': published,
                        'type': content.get('contentType', 'news'),
                        'summary': summary
                    })

            return processed_news
        except Exception as e:
            print(f"    Warning: Could not fetch news for {symbol}: {e}")
            return []

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

    def get_news_for_universe(self, universe: List[str]) -> Dict[str, List[Dict]]:
        """Fetch news for all symbols in universe"""
        all_news = {}
        for symbol in universe:
            news = self.get_news(symbol)
            if news:
                all_news[symbol] = news
        return all_news

    def format_news_for_llm(self, news_data: Dict[str, List[Dict]]) -> str:
        """Format news data for LLM analysis"""
        if not news_data:
            return "No recent news available for analysis."

        formatted = ""
        for symbol, articles in news_data.items():
            formatted += f"\n{symbol} Recent News:\n"
            formatted += "-" * 40 + "\n"

            for i, article in enumerate(articles, 1):
                formatted += f"{i}. [{article['published']}] {article['title']}\n"
                formatted += f"   Source: {article['publisher']}\n"
                if article['summary']:
                    # Truncate summary for brevity
                    summary = article['summary'][:200] + "..." if len(article['summary']) > 200 else article['summary']
                    formatted += f"   Summary: {summary}\n"
                formatted += "\n"

        return formatted

    def analyze(self, portfolio: Portfolio) -> AgentAnalysis:
        """Analyze sentiment and generate recommendations"""

        # Get universe from portfolio's top holdings
        universe = self._get_universe_from_portfolio(portfolio)
        if not universe:
            print(f"  [{self.agent_id}] No significant positions to analyze")
            return AgentAnalysis(
                agent_id=self.agent_id,
                timestamp=datetime.now(),
                recommendations=[],
                summary="No significant positions in portfolio to analyze for sentiment.",
                confidence=0
            )

        print(f"  [{self.agent_id}] Analyzing top {len(universe)} holdings: {', '.join(universe[:5])}...")

        # Fetch news for universe
        print(f"  [{self.agent_id}] Fetching news data...")
        news_data = self.get_news_for_universe(universe)

        if not news_data:
            print(f"  [{self.agent_id}] No news data available, returning neutral analysis")
            return AgentAnalysis(
                agent_id=self.agent_id,
                timestamp=datetime.now(),
                recommendations=[],
                summary="No recent news available for sentiment analysis. Unable to generate sentiment-based recommendations.",
                confidence=20
            )

        # Build context for LLM
        context = self.format_portfolio_for_llm(portfolio)
        context += "\n\nNews Data for Sentiment Analysis:\n"
        context += self.format_news_for_llm(news_data)

        # Add current prices for context
        context += "\n\nCurrent Price Context:\n"
        for symbol in universe:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='5d')
                if not hist.empty:
                    current = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                    change_pct = ((current - prev) / prev) * 100
                    context += f"  {symbol}: ${current:.2f} ({change_pct:+.2f}% today)\n"
            except:
                pass

        # Get LLM analysis
        print(f"  [{self.agent_id}] Running LLM sentiment analysis...")
        response = self.llm.complete_json(
            system_prompt=self.get_system_prompt(),
            user_message=f"""Analyze the following news data to generate sentiment-based trading recommendations.

{context}

Consider:
1. What is the overall sentiment for each stock?
2. Are there any significant news events that warrant action?
3. Is sentiment confirming or diverging from recent price action?
4. What are the key sentiment drivers?

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

        # Build summary
        market_summary = response.get('market_sentiment_summary', '')
        agent_summary = response.get('summary', 'No summary available')
        full_summary = f"{agent_summary}"
        if market_summary:
            full_summary += f" Market overview: {market_summary}"

        analysis = AgentAnalysis(
            agent_id=self.agent_id,
            timestamp=datetime.now(),
            recommendations=recommendations,
            summary=full_summary,
            confidence=response.get('confidence', 50)
        )

        return analysis


if __name__ == '__main__':
    # Test the sentiment agent
    import config
    from llm_client import LLMClient
    from alpaca_client import AlpacaClient

    config.validate_config()

    llm = LLMClient()
    alpaca = AlpacaClient()
    agent = SentimentAgent(llm)

    print("Fetching portfolio...")
    portfolio = alpaca.get_portfolio()

    print("\nRunning sentiment analysis...")
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
        if rec.supporting_data:
            print(f"  Sentiment: {rec.supporting_data.get('sentiment_label', 'N/A')}")
            if 'key_headlines' in rec.supporting_data:
                print(f"  Key Headlines:")
                for headline in rec.supporting_data['key_headlines'][:3]:
                    print(f"    - {headline}")
