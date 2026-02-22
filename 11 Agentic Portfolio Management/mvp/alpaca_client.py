"""Alpaca brokerage client for MVP"""
import os
import json
import alpaca_trade_api as tradeapi
from datetime import datetime
from models import Portfolio, Position
import config


class AlpacaClient:
    """Simple Alpaca API wrapper"""

    COST_BASIS_FILE = os.path.join(os.path.dirname(__file__), 'cost_basis.json')

    def __init__(self):
        self.api = tradeapi.REST(
            config.ALPACA_API_KEY,
            config.ALPACA_SECRET_KEY,
            config.ALPACA_BASE_URL,
            api_version='v2'
        )
        self._cost_basis_cache = None

    def _load_cost_basis(self) -> dict:
        """Load cost basis data from JSON file"""
        if self._cost_basis_cache is not None:
            return self._cost_basis_cache

        try:
            if os.path.exists(self.COST_BASIS_FILE):
                with open(self.COST_BASIS_FILE, 'r') as f:
                    data = json.load(f)
                    self._cost_basis_cache = data.get('positions', {})
                    return self._cost_basis_cache
        except Exception as e:
            print(f"Warning: Could not load cost basis: {e}")

        self._cost_basis_cache = {}
        return self._cost_basis_cache

    def get_portfolio(self) -> Portfolio:
        """Fetch current portfolio state"""
        account = self.api.get_account()
        alpaca_positions = self.api.list_positions()
        cost_basis_data = self._load_cost_basis()

        positions = []
        for pos in alpaca_positions:
            symbol = pos.symbol
            quantity = float(pos.qty)
            current_price = float(pos.current_price)
            market_value = float(pos.market_value)

            # Get original cost basis if available
            original_cost_basis = None
            original_pl = None
            original_pl_pct = None

            if symbol in cost_basis_data:
                original_cost_basis = cost_basis_data[symbol].get('original_avg_cost')
                if original_cost_basis and original_cost_basis > 0:
                    # Calculate P&L based on original Robinhood cost
                    cost_value = quantity * original_cost_basis
                    original_pl = market_value - cost_value
                    original_pl_pct = (original_pl / cost_value) * 100 if cost_value > 0 else 0

            position = Position(
                symbol=symbol,
                quantity=quantity,
                avg_entry_price=float(pos.avg_entry_price),
                current_price=current_price,
                market_value=market_value,
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_pl_pct=float(pos.unrealized_plpc) * 100,
                original_cost_basis=original_cost_basis,
                original_pl=original_pl,
                original_pl_pct=original_pl_pct
            )
            positions.append(position)

        portfolio = Portfolio(
            cash=float(account.cash),
            buying_power=float(account.buying_power),
            portfolio_value=float(account.portfolio_value),
            positions=positions,
            last_updated=datetime.now()
        )

        return portfolio

    def place_order(self, symbol: str, qty: int, side: str, order_type: str = 'market'):
        """Place an order"""
        try:
            order = self.api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,  # 'buy' or 'sell'
                type=order_type,  # 'market' or 'limit'
                time_in_force='day'
            )
            return order
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            trade = self.api.get_latest_trade(symbol)
            return float(trade.price)
        except:
            # Fallback to quote
            try:
                quote = self.api.get_latest_quote(symbol)
                return float(quote.ask_price)
            except:
                return 0.0

    def is_market_open(self) -> bool:
        """Check if market is currently open"""
        clock = self.api.get_clock()
        return clock.is_open


if __name__ == '__main__':
    # Test the client
    config.validate_config()
    client = AlpacaClient()

    print("Fetching portfolio...")
    portfolio = client.get_portfolio()

    print(f"\nCash: ${portfolio.cash:,.2f}")
    print(f"Portfolio Value: ${portfolio.portfolio_value:,.2f}")
    print(f"\nPositions:")
    for pos in portfolio.positions:
        print(f"  {pos.symbol}: {pos.quantity:.2f} shares @ ${pos.current_price:.2f}")
        print(f"    Alpaca P&L: ${pos.unrealized_pl:.2f} ({pos.unrealized_pl_pct:.2f}%)")
        if pos.original_cost_basis is not None:
            print(f"    Original Cost Basis: ${pos.original_cost_basis:.2f}")
            print(f"    P&L vs Cost Basis: ${pos.original_pl:.2f} ({pos.original_pl_pct:.2f}%)")
