"""Base agent class for MVP"""
from abc import ABC, abstractmethod
from typing import List
from datetime import datetime
import pandas as pd
import yfinance as yf
from models import Portfolio, Position, Recommendation, AgentAnalysis
from llm_client import LLMClient
import config


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, agent_id: str, llm_client: LLMClient):
        self.agent_id = agent_id
        self.llm = llm_client

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent"""
        pass

    @abstractmethod
    def analyze(self, portfolio: Portfolio) -> AgentAnalysis:
        """Analyze portfolio and generate recommendations"""
        pass

    def is_position_negligible(self, position: Position, portfolio_value: float) -> bool:
        """Check if a position is too small to consider for recommendations"""
        if position.market_value < config.MIN_POSITION_VALUE:
            return True
        position_pct = position.market_value / portfolio_value if portfolio_value > 0 else 0
        if position_pct < config.MIN_POSITION_PCT:
            return True
        return False

    def get_market_data(self, symbol: str, days: int = 60) -> pd.DataFrame:
        """Fetch historical market data"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")
            return hist
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def get_multiple_symbols(self, symbols: List[str], days: int = 60) -> dict:
        """Fetch data for multiple symbols"""
        data = {}
        for symbol in symbols:
            data[symbol] = self.get_market_data(symbol, days)
        return data

    def format_portfolio_for_llm(self, portfolio: Portfolio) -> str:
        """Format portfolio data for LLM context (excludes negligible positions)"""
        portfolio_str = f"""
Current Portfolio Status:
- Cash Available: ${portfolio.cash:,.2f}
- Total Portfolio Value: ${portfolio.portfolio_value:,.2f}
- Buying Power: ${portfolio.buying_power:,.2f}

Current Positions (excluding positions < ${config.MIN_POSITION_VALUE:.0f} or < {config.MIN_POSITION_PCT * 100:.1f}%):
"""
        if portfolio.positions:
            # Filter out negligible positions
            significant_positions = [
                pos for pos in portfolio.positions
                if not self.is_position_negligible(pos, portfolio.portfolio_value)
            ]

            if significant_positions:
                for pos in significant_positions:
                    portfolio_str += f"""
  {pos.symbol}:
    - Quantity: {pos.quantity} shares
    - Entry Price: ${pos.avg_entry_price:.2f}
    - Current Price: ${pos.current_price:.2f}
    - Market Value: ${pos.market_value:,.2f}
    - P&L: ${pos.unrealized_pl:,.2f} ({pos.unrealized_pl_pct:.2f}%)
"""
                # Note how many positions were filtered
                filtered_count = len(portfolio.positions) - len(significant_positions)
                if filtered_count > 0:
                    portfolio_str += f"\n  ({filtered_count} negligible positions not shown)\n"
            else:
                portfolio_str += "  No significant positions currently held.\n"
        else:
            portfolio_str += "  No positions currently held.\n"

        return portfolio_str

    def format_market_data_for_llm(self, symbol: str, df: pd.DataFrame) -> str:
        """Format market data for LLM context"""
        if df.empty:
            return f"{symbol}: No data available"

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # Calculate some basic metrics
        price_change = latest['Close'] - prev['Close']
        price_change_pct = (price_change / prev['Close']) * 100
        avg_volume = df['Volume'].mean()
        current_volume = latest['Volume']

        # Simple trend (last 20 days)
        if len(df) >= 20:
            ma20 = df['Close'].tail(20).mean()
            trend = "uptrend" if latest['Close'] > ma20 else "downtrend"
        else:
            trend = "insufficient data"

        return f"""
{symbol} Market Data:
  - Current Price: ${latest['Close']:.2f}
  - Change: ${price_change:.2f} ({price_change_pct:.2f}%)
  - Volume: {current_volume:,.0f} (Avg: {avg_volume:,.0f})
  - 20-day Trend: {trend}
  - High (period): ${df['High'].max():.2f}
  - Low (period): ${df['Low'].min():.2f}
"""
