# Brokerage Integration Guide

## Overview

This document outlines how to integrate the Agentic Portfolio Management system with real-world brokerages like Robinhood, Interactive Brokers, Alpaca, and others to fetch current portfolio data, positions, and execute trades.

## Architecture

### Brokerage Integration Layer

```
┌─────────────────────────────────────────────────────────────┐
│                   Agentic Portfolio Manager                  │
│                   (Orchestrator + Agents)                     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Portfolio Data Aggregator                       │
│              - Syncs data from all brokerages                │
│              - Normalizes portfolio format                   │
│              - Caches for performance                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│  Robinhood      │ │ Interactive  │ │ Alpaca          │
│  Adapter        │ │ Brokers      │ │ Adapter         │
│                 │ │ Adapter      │ │                 │
└────────┬────────┘ └──────┬───────┘ └────────┬────────┘
         │                 │                  │
         ▼                 ▼                  ▼
   Robinhood API      IB Gateway         Alpaca API
```

## Generic Brokerage Adapter Pattern

### Base Interface

All brokerage adapters implement a common interface:

```python
# src/integrations/brokerages/base.py
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class Position:
    """Represents a position in the portfolio"""
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal

@dataclass
class Portfolio:
    """Represents the entire portfolio"""
    account_id: str
    cash: Decimal
    buying_power: Decimal
    portfolio_value: Decimal
    positions: List[Position]
    last_updated: datetime

@dataclass
class Order:
    """Represents an order"""
    symbol: str
    quantity: Decimal
    side: str  # 'buy' or 'sell'
    order_type: str  # 'market', 'limit', 'stop'
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    time_in_force: str = 'day'  # 'day', 'gtc', 'ioc', 'fok'

@dataclass
class OrderStatus:
    """Order execution status"""
    order_id: str
    symbol: str
    status: str  # 'pending', 'filled', 'partially_filled', 'cancelled', 'rejected'
    filled_quantity: Decimal
    average_fill_price: Optional[Decimal]
    created_at: datetime
    updated_at: datetime

class BrokerageAdapter(ABC):
    """Base class for all brokerage integrations"""

    def __init__(self, credentials: dict, config: dict):
        self.credentials = credentials
        self.config = config
        self._authenticated = False

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the brokerage"""
        pass

    @abstractmethod
    async def get_portfolio(self) -> Portfolio:
        """Fetch current portfolio state"""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Fetch all current positions"""
        pass

    @abstractmethod
    async def get_cash_balance(self) -> Decimal:
        """Get available cash balance"""
        pass

    @abstractmethod
    async def get_buying_power(self) -> Decimal:
        """Get available buying power"""
        pass

    @abstractmethod
    async def place_order(self, order: Order) -> OrderStatus:
        """Place a new order"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get status of an order"""
        pass

    @abstractmethod
    async def get_order_history(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[OrderStatus]:
        """Get historical orders"""
        pass

    async def is_market_open(self) -> bool:
        """Check if market is currently open"""
        # Default implementation, can be overridden
        from datetime import time
        import pytz

        now = datetime.now(pytz.timezone('America/New_York'))
        market_open = time(9, 30)
        market_close = time(16, 0)

        # Check if weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check if during market hours
        return market_open <= now.time() <= market_close
```

## Robinhood Integration

### Option 1: robin_stocks Library (Recommended for Quick Start)

The `robin_stocks` library provides unofficial API access to Robinhood.

#### Installation

```bash
pip install robin-stocks
```

#### Implementation

```python
# src/integrations/brokerages/robinhood.py
import robin_stocks.robinhood as rh
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
import asyncio
from .base import (
    BrokerageAdapter, Portfolio, Position, Order, OrderStatus
)

class RobinhoodAdapter(BrokerageAdapter):
    """Robinhood brokerage adapter using robin_stocks"""

    def __init__(self, credentials: dict, config: dict):
        super().__init__(credentials, config)
        self.username = credentials.get('username')
        self.password = credentials.get('password')
        self.mfa_code = credentials.get('mfa_code')  # Optional

    async def authenticate(self) -> bool:
        """Authenticate with Robinhood"""
        try:
            # robin_stocks is synchronous, run in executor
            loop = asyncio.get_event_loop()
            login = await loop.run_in_executor(
                None,
                rh.login,
                self.username,
                self.password,
                None,  # expiresIn
                None,  # scope
                False,  # by_sms
                self.mfa_code  # mfa_code
            )

            if login:
                self._authenticated = True
                return True
            return False

        except Exception as e:
            print(f"Robinhood authentication failed: {e}")
            return False

    async def get_portfolio(self) -> Portfolio:
        """Fetch current portfolio state from Robinhood"""
        if not self._authenticated:
            await self.authenticate()

        loop = asyncio.get_event_loop()

        # Get portfolio data
        profile_data = await loop.run_in_executor(
            None, rh.profiles.load_portfolio_profile
        )

        # Get positions
        positions = await self.get_positions()

        # Parse portfolio data
        portfolio = Portfolio(
            account_id=profile_data.get('account'),
            cash=Decimal(profile_data.get('withdrawable_amount', 0)),
            buying_power=Decimal(profile_data.get('excess_margin', 0)),
            portfolio_value=Decimal(profile_data.get('equity', 0)),
            positions=positions,
            last_updated=datetime.utcnow()
        )

        return portfolio

    async def get_positions(self) -> List[Position]:
        """Fetch all current positions from Robinhood"""
        if not self._authenticated:
            await self.authenticate()

        loop = asyncio.get_event_loop()

        # Get positions data
        positions_data = await loop.run_in_executor(
            None, rh.account.get_open_stock_positions
        )

        positions = []

        for pos_data in positions_data:
            # Get instrument details
            instrument = await loop.run_in_executor(
                None,
                rh.stocks.get_instrument_by_url,
                pos_data['instrument']
            )

            symbol = instrument['symbol']

            # Get current quote
            quote = await loop.run_in_executor(
                None, rh.stocks.get_latest_price, symbol
            )
            current_price = Decimal(quote[0]) if quote else Decimal(0)

            quantity = Decimal(pos_data.get('quantity', 0))
            average_cost = Decimal(pos_data.get('average_buy_price', 0))
            market_value = quantity * current_price
            unrealized_pnl = market_value - (quantity * average_cost)
            unrealized_pnl_pct = (unrealized_pnl / (quantity * average_cost) * 100) if average_cost > 0 else Decimal(0)

            position = Position(
                symbol=symbol,
                quantity=quantity,
                average_cost=average_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct
            )

            positions.append(position)

        return positions

    async def get_cash_balance(self) -> Decimal:
        """Get available cash balance"""
        portfolio = await self.get_portfolio()
        return portfolio.cash

    async def get_buying_power(self) -> Decimal:
        """Get available buying power"""
        portfolio = await self.get_portfolio()
        return portfolio.buying_power

    async def place_order(self, order: Order) -> OrderStatus:
        """Place a new order on Robinhood"""
        if not self._authenticated:
            await self.authenticate()

        loop = asyncio.get_event_loop()

        # Map order type
        order_function = {
            'market': rh.orders.order_buy_market if order.side == 'buy' else rh.orders.order_sell_market,
            'limit': rh.orders.order_buy_limit if order.side == 'buy' else rh.orders.order_sell_limit,
        }.get(order.order_type)

        if not order_function:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        # Place order
        if order.order_type == 'limit':
            result = await loop.run_in_executor(
                None,
                order_function,
                order.symbol,
                float(order.quantity),
                float(order.limit_price),
                order.time_in_force
            )
        else:
            result = await loop.run_in_executor(
                None,
                order_function,
                order.symbol,
                float(order.quantity),
                order.time_in_force
            )

        # Parse result
        order_status = OrderStatus(
            order_id=result.get('id'),
            symbol=order.symbol,
            status=self._parse_order_state(result.get('state')),
            filled_quantity=Decimal(result.get('cumulative_quantity', 0)),
            average_fill_price=Decimal(result.get('average_price', 0)) if result.get('average_price') else None,
            created_at=datetime.fromisoformat(result.get('created_at').replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(result.get('updated_at').replace('Z', '+00:00'))
        )

        return order_status

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        if not self._authenticated:
            await self.authenticate()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, rh.orders.cancel_stock_order, order_id
        )

        return result is not None

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Get status of an order"""
        if not self._authenticated:
            await self.authenticate()

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, rh.orders.get_stock_order_info, order_id
        )

        order_status = OrderStatus(
            order_id=result.get('id'),
            symbol=result.get('symbol'),
            status=self._parse_order_state(result.get('state')),
            filled_quantity=Decimal(result.get('cumulative_quantity', 0)),
            average_fill_price=Decimal(result.get('average_price', 0)) if result.get('average_price') else None,
            created_at=datetime.fromisoformat(result.get('created_at').replace('Z', '+00:00')),
            updated_at=datetime.fromisoformat(result.get('updated_at').replace('Z', '+00:00'))
        )

        return order_status

    async def get_order_history(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[OrderStatus]:
        """Get historical orders"""
        if not self._authenticated:
            await self.authenticate()

        loop = asyncio.get_event_loop()
        orders = await loop.run_in_executor(
            None, rh.orders.get_all_stock_orders
        )

        order_statuses = []
        for order in orders:
            created_at = datetime.fromisoformat(order.get('created_at').replace('Z', '+00:00'))

            if start_date <= created_at <= end_date:
                order_status = OrderStatus(
                    order_id=order.get('id'),
                    symbol=order.get('symbol'),
                    status=self._parse_order_state(order.get('state')),
                    filled_quantity=Decimal(order.get('cumulative_quantity', 0)),
                    average_fill_price=Decimal(order.get('average_price', 0)) if order.get('average_price') else None,
                    created_at=created_at,
                    updated_at=datetime.fromisoformat(order.get('updated_at').replace('Z', '+00:00'))
                )
                order_statuses.append(order_status)

        return order_statuses

    def _parse_order_state(self, state: str) -> str:
        """Map Robinhood order state to our standard states"""
        state_mapping = {
            'queued': 'pending',
            'confirmed': 'pending',
            'filled': 'filled',
            'partially_filled': 'partially_filled',
            'cancelled': 'cancelled',
            'rejected': 'rejected',
            'failed': 'rejected'
        }
        return state_mapping.get(state, 'pending')
```

### Option 2: Official Robinhood API (When Available)

Robinhood is working on an official API. When available, implementation would be similar but using official SDK.

### Security Considerations for Robinhood

⚠️ **Important Security Notes:**

1. **MFA Required**: Robinhood requires 2FA. You'll need to handle this:
   ```python
   # Option A: Manual MFA code entry
   mfa_code = input("Enter MFA code: ")

   # Option B: Store device token (less secure)
   # Store the device_token returned after first login
   ```

2. **Token Storage**: Store authentication tokens securely:
   ```python
   # Use environment variables or encrypted storage
   import keyring

   # Store token
   keyring.set_password("agentic-pm", "robinhood_token", token)

   # Retrieve token
   token = keyring.get_password("agentic-pm", "robinhood_token")
   ```

3. **Rate Limiting**: Robinhood has rate limits. Implement caching:
   ```python
   from cachetools import TTLCache

   # Cache portfolio data for 1 minute
   portfolio_cache = TTLCache(maxsize=100, ttl=60)
   ```

## Interactive Brokers Integration

Interactive Brokers provides a professional API via the TWS/Gateway.

### Installation

```bash
pip install ib_insync
```

### Implementation

```python
# src/integrations/brokerages/interactive_brokers.py
from ib_insync import IB, Stock, MarketOrder, LimitOrder
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from .base import (
    BrokerageAdapter, Portfolio, Position, Order, OrderStatus
)

class InteractiveBrokersAdapter(BrokerageAdapter):
    """Interactive Brokers adapter using ib_insync"""

    def __init__(self, credentials: dict, config: dict):
        super().__init__(credentials, config)
        self.ib = IB()
        self.host = config.get('host', '127.0.0.1')
        self.port = config.get('port', 7497)  # 7497 for TWS, 4002 for Gateway
        self.client_id = config.get('client_id', 1)

    async def authenticate(self) -> bool:
        """Connect to IB Gateway/TWS"""
        try:
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id
            )
            self._authenticated = True
            return True
        except Exception as e:
            print(f"IB authentication failed: {e}")
            return False

    async def get_portfolio(self) -> Portfolio:
        """Fetch current portfolio from IB"""
        if not self._authenticated:
            await self.authenticate()

        # Get account values
        account_values = self.ib.accountValues()

        cash = Decimal(0)
        portfolio_value = Decimal(0)
        buying_power = Decimal(0)

        for av in account_values:
            if av.tag == 'TotalCashValue':
                cash = Decimal(av.value)
            elif av.tag == 'NetLiquidation':
                portfolio_value = Decimal(av.value)
            elif av.tag == 'BuyingPower':
                buying_power = Decimal(av.value)

        # Get positions
        positions = await self.get_positions()

        portfolio = Portfolio(
            account_id=self.ib.client.accounts[0] if self.ib.client.accounts else 'default',
            cash=cash,
            buying_power=buying_power,
            portfolio_value=portfolio_value,
            positions=positions,
            last_updated=datetime.utcnow()
        )

        return portfolio

    async def get_positions(self) -> List[Position]:
        """Fetch all positions from IB"""
        if not self._authenticated:
            await self.authenticate()

        ib_positions = self.ib.positions()
        positions = []

        for ib_pos in ib_positions:
            contract = ib_pos.contract

            # Get current market price
            ticker = self.ib.reqMktData(contract)
            await self.ib.sleep(1)  # Wait for data

            current_price = Decimal(str(ticker.last)) if ticker.last else Decimal(0)
            quantity = Decimal(str(ib_pos.position))
            average_cost = Decimal(str(ib_pos.avgCost))
            market_value = quantity * current_price
            unrealized_pnl = Decimal(str(ib_pos.unrealizedPNL))
            unrealized_pnl_pct = (unrealized_pnl / (quantity * average_cost) * 100) if average_cost > 0 else Decimal(0)

            position = Position(
                symbol=contract.symbol,
                quantity=quantity,
                average_cost=average_cost,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct
            )

            positions.append(position)

        return positions

    async def place_order(self, order: Order) -> OrderStatus:
        """Place order on IB"""
        if not self._authenticated:
            await self.authenticate()

        # Create contract
        contract = Stock(order.symbol, 'SMART', 'USD')

        # Create IB order
        if order.order_type == 'market':
            ib_order = MarketOrder(
                order.side.upper(),
                float(order.quantity)
            )
        elif order.order_type == 'limit':
            ib_order = LimitOrder(
                order.side.upper(),
                float(order.quantity),
                float(order.limit_price)
            )
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        # Place order
        trade = self.ib.placeOrder(contract, ib_order)

        # Wait for order to be submitted
        await self.ib.sleep(1)

        order_status = OrderStatus(
            order_id=str(trade.order.orderId),
            symbol=order.symbol,
            status=self._parse_ib_status(trade.orderStatus.status),
            filled_quantity=Decimal(str(trade.orderStatus.filled)),
            average_fill_price=Decimal(str(trade.orderStatus.avgFillPrice)) if trade.orderStatus.avgFillPrice else None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        return order_status

    def _parse_ib_status(self, status: str) -> str:
        """Map IB order status to our standard states"""
        status_mapping = {
            'PendingSubmit': 'pending',
            'PreSubmitted': 'pending',
            'Submitted': 'pending',
            'Filled': 'filled',
            'PartiallyFilled': 'partially_filled',
            'Cancelled': 'cancelled',
            'Inactive': 'rejected'
        }
        return status_mapping.get(status, 'pending')

    # ... implement other methods ...
```

## Alpaca Integration

Alpaca provides a commission-free trading API perfect for algorithmic trading.

### Installation

```bash
pip install alpaca-trade-api
```

### Implementation

```python
# src/integrations/brokerages/alpaca.py
import alpaca_trade_api as tradeapi
from typing import List, Optional
from decimal import Decimal
from datetime import datetime
from .base import (
    BrokerageAdapter, Portfolio, Position, Order, OrderStatus
)

class AlpacaAdapter(BrokerageAdapter):
    """Alpaca brokerage adapter"""

    def __init__(self, credentials: dict, config: dict):
        super().__init__(credentials, config)
        self.api_key = credentials.get('api_key')
        self.secret_key = credentials.get('secret_key')
        self.base_url = config.get('base_url', 'https://paper-api.alpaca.markets')
        self.api = None

    async def authenticate(self) -> bool:
        """Initialize Alpaca API client"""
        try:
            self.api = tradeapi.REST(
                self.api_key,
                self.secret_key,
                self.base_url,
                api_version='v2'
            )
            # Test connection
            account = self.api.get_account()
            self._authenticated = True
            return True
        except Exception as e:
            print(f"Alpaca authentication failed: {e}")
            return False

    async def get_portfolio(self) -> Portfolio:
        """Fetch portfolio from Alpaca"""
        if not self._authenticated:
            await self.authenticate()

        account = self.api.get_account()
        positions = await self.get_positions()

        portfolio = Portfolio(
            account_id=account.id,
            cash=Decimal(account.cash),
            buying_power=Decimal(account.buying_power),
            portfolio_value=Decimal(account.portfolio_value),
            positions=positions,
            last_updated=datetime.utcnow()
        )

        return portfolio

    async def get_positions(self) -> List[Position]:
        """Fetch positions from Alpaca"""
        if not self._authenticated:
            await self.authenticate()

        alpaca_positions = self.api.list_positions()
        positions = []

        for pos in alpaca_positions:
            position = Position(
                symbol=pos.symbol,
                quantity=Decimal(pos.qty),
                average_cost=Decimal(pos.avg_entry_price),
                current_price=Decimal(pos.current_price),
                market_value=Decimal(pos.market_value),
                unrealized_pnl=Decimal(pos.unrealized_pl),
                unrealized_pnl_pct=Decimal(pos.unrealized_plpc) * 100
            )
            positions.append(position)

        return positions

    async def place_order(self, order: Order) -> OrderStatus:
        """Place order on Alpaca"""
        if not self._authenticated:
            await self.authenticate()

        alpaca_order = self.api.submit_order(
            symbol=order.symbol,
            qty=float(order.quantity),
            side=order.side,
            type=order.order_type,
            time_in_force=order.time_in_force,
            limit_price=float(order.limit_price) if order.limit_price else None,
            stop_price=float(order.stop_price) if order.stop_price else None
        )

        order_status = OrderStatus(
            order_id=alpaca_order.id,
            symbol=alpaca_order.symbol,
            status=self._parse_alpaca_status(alpaca_order.status),
            filled_quantity=Decimal(alpaca_order.filled_qty or 0),
            average_fill_price=Decimal(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else None,
            created_at=alpaca_order.created_at,
            updated_at=alpaca_order.updated_at or alpaca_order.created_at
        )

        return order_status

    def _parse_alpaca_status(self, status: str) -> str:
        """Map Alpaca status to our standard states"""
        status_mapping = {
            'new': 'pending',
            'accepted': 'pending',
            'pending_new': 'pending',
            'filled': 'filled',
            'partially_filled': 'partially_filled',
            'canceled': 'cancelled',
            'rejected': 'rejected',
            'expired': 'cancelled'
        }
        return status_mapping.get(status, 'pending')

    # ... implement other methods ...
```

## Portfolio Data Aggregator

This component syncs data from all connected brokerages and provides a unified view.

```python
# src/integrations/portfolio_aggregator.py
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime
import asyncio
from .brokerages.base import BrokerageAdapter, Portfolio, Position

class PortfolioAggregator:
    """Aggregates portfolio data from multiple brokerages"""

    def __init__(self, adapters: Dict[str, BrokerageAdapter]):
        self.adapters = adapters
        self._cache = {}
        self._cache_ttl = 60  # seconds

    async def get_consolidated_portfolio(self) -> Portfolio:
        """Get consolidated portfolio across all brokerages"""

        # Fetch from all brokerages in parallel
        tasks = [
            adapter.get_portfolio()
            for adapter in self.adapters.values()
        ]
        portfolios = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate data
        total_cash = Decimal(0)
        total_buying_power = Decimal(0)
        total_portfolio_value = Decimal(0)
        all_positions = {}

        for i, portfolio in enumerate(portfolios):
            if isinstance(portfolio, Exception):
                print(f"Error fetching portfolio from adapter {i}: {portfolio}")
                continue

            total_cash += portfolio.cash
            total_buying_power += portfolio.buying_power
            total_portfolio_value += portfolio.portfolio_value

            # Aggregate positions by symbol
            for position in portfolio.positions:
                if position.symbol in all_positions:
                    # Combine positions
                    existing = all_positions[position.symbol]
                    total_qty = existing.quantity + position.quantity
                    total_cost = (existing.quantity * existing.average_cost +
                                position.quantity * position.average_cost)
                    new_avg_cost = total_cost / total_qty if total_qty > 0 else Decimal(0)

                    all_positions[position.symbol] = Position(
                        symbol=position.symbol,
                        quantity=total_qty,
                        average_cost=new_avg_cost,
                        current_price=position.current_price,
                        market_value=total_qty * position.current_price,
                        unrealized_pnl=total_qty * position.current_price - total_cost,
                        unrealized_pnl_pct=((total_qty * position.current_price - total_cost) / total_cost * 100) if total_cost > 0 else Decimal(0)
                    )
                else:
                    all_positions[position.symbol] = position

        # Create consolidated portfolio
        consolidated = Portfolio(
            account_id="consolidated",
            cash=total_cash,
            buying_power=total_buying_power,
            portfolio_value=total_portfolio_value,
            positions=list(all_positions.values()),
            last_updated=datetime.utcnow()
        )

        return consolidated

    async def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """Get all positions for a specific symbol across brokerages"""
        portfolio = await self.get_consolidated_portfolio()
        return [p for p in portfolio.positions if p.symbol == symbol]

    async def sync_to_database(self, db_session):
        """Sync portfolio data to database for historical tracking"""
        portfolio = await self.get_consolidated_portfolio()

        # Store in database
        from src.models.portfolio import PortfolioSnapshot

        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            cash=portfolio.cash,
            portfolio_value=portfolio.portfolio_value,
            positions_json=self._serialize_positions(portfolio.positions)
        )

        db_session.add(snapshot)
        await db_session.commit()

        return snapshot

    def _serialize_positions(self, positions: List[Position]) -> dict:
        """Serialize positions to JSON"""
        return {
            pos.symbol: {
                "quantity": float(pos.quantity),
                "average_cost": float(pos.average_cost),
                "current_price": float(pos.current_price),
                "market_value": float(pos.market_value),
                "unrealized_pnl": float(pos.unrealized_pnl)
            }
            for pos in positions
        }
```

## Configuration

Add to `.env`:

```bash
# Robinhood Configuration
ROBINHOOD_USERNAME=your_username
ROBINHOOD_PASSWORD=your_password
ROBINHOOD_MFA_CODE=  # Leave empty if using saved device token

# Interactive Brokers Configuration
IB_HOST=127.0.0.1
IB_PORT=7497  # 7497 for TWS, 4002 for IB Gateway
IB_CLIENT_ID=1

# Alpaca Configuration
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # paper trading

# Portfolio Sync Configuration
PORTFOLIO_SYNC_INTERVAL=60  # seconds
ENABLE_PORTFOLIO_CACHE=true
PORTFOLIO_CACHE_TTL=60  # seconds
```

## Usage in the Agentic System

### Initialize Adapters

```python
# src/core/brokerage_manager.py
from src.integrations.brokerages.robinhood import RobinhoodAdapter
from src.integrations.brokerages.alpaca import AlpacaAdapter
from src.integrations.portfolio_aggregator import PortfolioAggregator

async def initialize_brokerages(config):
    """Initialize all brokerage connections"""
    adapters = {}

    # Robinhood
    if config.get('ROBINHOOD_USERNAME'):
        robinhood = RobinhoodAdapter(
            credentials={
                'username': config['ROBINHOOD_USERNAME'],
                'password': config['ROBINHOOD_PASSWORD'],
                'mfa_code': config.get('ROBINHOOD_MFA_CODE')
            },
            config={}
        )
        await robinhood.authenticate()
        adapters['robinhood'] = robinhood

    # Alpaca
    if config.get('ALPACA_API_KEY'):
        alpaca = AlpacaAdapter(
            credentials={
                'api_key': config['ALPACA_API_KEY'],
                'secret_key': config['ALPACA_SECRET_KEY']
            },
            config={
                'base_url': config.get('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
            }
        )
        await alpaca.authenticate()
        adapters['alpaca'] = alpaca

    # Create aggregator
    aggregator = PortfolioAggregator(adapters)

    return aggregator
```

### Use in Agents

```python
# In Risk Manager Agent
async def check_portfolio_risk(self):
    """Check current portfolio risk"""

    # Get current portfolio
    portfolio = await self.portfolio_aggregator.get_consolidated_portfolio()

    # Calculate risk metrics
    risk_metrics = self.risk_calculator.calculate_all_metrics(portfolio)

    # Check constraints
    violations = self.check_risk_constraints(portfolio, risk_metrics)

    if violations:
        await self.send_risk_alert(violations)

    return risk_metrics
```

### Scheduled Portfolio Sync

```python
# In orchestrator or background worker
import asyncio

async def portfolio_sync_loop(aggregator, db_session):
    """Continuously sync portfolio data"""
    while True:
        try:
            # Sync portfolio
            snapshot = await aggregator.sync_to_database(db_session)
            print(f"Portfolio synced at {snapshot.timestamp}")

            # Wait for next sync
            await asyncio.sleep(60)  # 1 minute

        except Exception as e:
            print(f"Portfolio sync error: {e}")
            await asyncio.sleep(60)
```

## Security Best Practices

1. **Never commit credentials**:
   ```bash
   # Add to .gitignore
   .env
   *.key
   *_credentials.json
   ```

2. **Use environment variables**:
   ```python
   import os
   from dotenv import load_dotenv

   load_dotenv()
   robinhood_username = os.getenv('ROBINHOOD_USERNAME')
   ```

3. **Encrypt sensitive data**:
   ```python
   from cryptography.fernet import Fernet

   # Generate key (do once, store securely)
   key = Fernet.generate_key()
   cipher = Fernet(key)

   # Encrypt
   encrypted = cipher.encrypt(password.encode())

   # Decrypt
   decrypted = cipher.decrypt(encrypted).decode()
   ```

4. **Use secure token storage**:
   ```bash
   pip install keyring
   ```

   ```python
   import keyring

   # Store
   keyring.set_password("agentic-pm", "robinhood_token", token)

   # Retrieve
   token = keyring.get_password("agentic-pm", "robinhood_token")
   ```

5. **Implement rate limiting**:
   ```python
   from ratelimit import limits, sleep_and_retry

   @sleep_and_retry
   @limits(calls=10, period=60)  # 10 calls per minute
   async def get_portfolio(self):
       # API call here
       pass
   ```

## Testing

Create mock adapters for testing:

```python
# tests/fixtures/mock_brokerage.py
from src.integrations.brokerages.base import BrokerageAdapter, Portfolio

class MockBrokerageAdapter(BrokerageAdapter):
    """Mock adapter for testing"""

    def __init__(self, mock_data):
        super().__init__({}, {})
        self.mock_data = mock_data
        self._authenticated = True

    async def get_portfolio(self) -> Portfolio:
        return self.mock_data['portfolio']

    # ... implement other methods with mock data ...
```

## Comparison of Brokerages

| Feature | Robinhood | Interactive Brokers | Alpaca |
|---------|-----------|---------------------|--------|
| Commission-free | ✅ Yes | ❌ Small fees | ✅ Yes |
| API Complexity | 🟡 Medium | 🔴 Complex | 🟢 Simple |
| Official API | ⚠️ Unofficial | ✅ Official | ✅ Official |
| Paper Trading | ❌ No | ✅ Yes | ✅ Yes |
| Options Trading | ✅ Yes | ✅ Yes | ✅ Yes (limited) |
| Crypto | ✅ Yes | ✅ Yes | ✅ Yes |
| Best For | Retail traders | Professional traders | Algo traders |

## Recommended Approach

**For Development/Testing**: Use **Alpaca** (paper trading, official API, easy setup)

**For Production**: Support **multiple brokerages** through adapter pattern

**Starting Point**:
1. Implement Alpaca adapter first (easiest)
2. Test with paper trading
3. Add Robinhood adapter for real account access
4. Add Interactive Brokers for advanced features

## Next Steps

1. Implement base `BrokerageAdapter` class
2. Create Alpaca adapter (recommended first)
3. Add Robinhood adapter
4. Build `PortfolioAggregator`
5. Integrate with Risk Manager agent
6. Add portfolio sync to database
7. Create dashboard to display portfolio

Would you like me to implement any specific adapter or create the complete integration code?
