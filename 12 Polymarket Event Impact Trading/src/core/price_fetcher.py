"""
Centralized Price Fetching Service for Polymarket Bots

Provides a single source of truth for all price operations:
- Entry prices (ask prices from CLOB)
- Exit prices (bid prices from CLOB)
- Position monitoring (bid prices from CLOB)

Uses CLOB API exclusively (not Gamma API) for accurate orderbook prices.
"""

import logging
import math
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketPrices:
    """Market prices with metadata."""
    yes_price: float
    no_price: float
    source: str  # 'CLOB_ASK' or 'CLOB_BID'
    condition_id: str

    def __post_init__(self):
        if not isinstance(self.yes_price, (int, float)):
            raise TypeError(f"yes_price must be numeric, got {type(self.yes_price).__name__}")
        if not isinstance(self.no_price, (int, float)):
            raise TypeError(f"no_price must be numeric, got {type(self.no_price).__name__}")

    def get_outcome_price(self, outcome: str) -> float:
        """Get price for specific outcome (YES or NO)."""
        if outcome is None:
            raise ValueError("outcome must be 'YES' or 'NO', got None")
        if outcome.upper() == 'YES':
            return self.yes_price
        elif outcome.upper() == 'NO':
            return self.no_price
        else:
            raise ValueError(f"Invalid outcome: {outcome}. Must be 'YES' or 'NO'")


class PriceFetcher:
    """
    Centralized price fetching service.

    Provides consistent price fetching across all bots with proper bid/ask handling.
    """

    def __init__(self, client):
        """
        Initialize price fetcher.

        Args:
            client: PolymarketClient instance
        """
        self.client = client
        self._cache = {}  # {(condition_id, side): (timestamp, MarketPrices)}
        self._cache_ttl = 5  # seconds
        logger.info("PriceFetcher initialized")

    @staticmethod
    def _validate_raw_price(price, label: str, condition_id: str) -> bool:
        """Validate a raw price value. Returns True if valid."""
        if not isinstance(price, (int, float)):
            logger.warning(f"Invalid {label} price type for {condition_id[:16]}...: {type(price)}")
            return False
        if math.isnan(price) or math.isinf(price):
            logger.warning(f"Invalid {label} price for {condition_id[:16]}...: NaN/Inf detected")
            return False
        if not (0 < price < 1):
            logger.warning(f"{label} price out of range for {condition_id[:16]}...: {price}")
            return False
        return True

    def _get_cached(self, condition_id: str, side: str) -> Optional[MarketPrices]:
        """Get cached price if still within TTL."""
        key = (condition_id, side)
        if key in self._cache:
            ts, prices = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return prices
            del self._cache[key]
        return None

    def _set_cached(self, condition_id: str, side: str, prices: MarketPrices):
        """Cache a price result with current timestamp."""
        self._cache[(condition_id, side)] = (time.time(), prices)

    def clear_cache(self):
        """Clear all cached prices."""
        self._cache.clear()

    def get_entry_prices(self, condition_id: str) -> Optional[MarketPrices]:
        """
        Get prices for ENTERING positions (ask prices - cost to buy tokens).

        Use this when:
        - Generating trading signals
        - Calculating position sizing
        - Determining entry price for new trades

        Args:
            condition_id: Market condition ID

        Returns:
            MarketPrices with ASK prices, or None if unavailable
        """
        cached = self._get_cached(condition_id, 'BUY')
        if cached is not None:
            return cached

        prices = self.client.get_market_prices(condition_id, side='BUY')

        yes_price = prices.get('yes')
        no_price = prices.get('no')

        if yes_price is None or no_price is None:
            logger.warning(
                f"Could not fetch entry prices (ASK) for {condition_id[:16]}... | "
                f"YES={yes_price}, NO={no_price}"
            )
            return None

        if not self._validate_raw_price(yes_price, 'YES ASK', condition_id):
            return None
        if not self._validate_raw_price(no_price, 'NO ASK', condition_id):
            return None

        result = MarketPrices(
            yes_price=yes_price,
            no_price=no_price,
            source='CLOB_ASK',
            condition_id=condition_id
        )
        self._set_cached(condition_id, 'BUY', result)
        return result

    def get_exit_prices(self, condition_id: str) -> Optional[MarketPrices]:
        """
        Get prices for EXITING positions (bid prices - proceeds from selling tokens).

        Use this when:
        - Monitoring position P&L
        - Checking stop-loss/take-profit triggers
        - Closing positions
        - Calculating exit value

        Args:
            condition_id: Market condition ID

        Returns:
            MarketPrices with BID prices, or None if unavailable
        """
        cached = self._get_cached(condition_id, 'SELL')
        if cached is not None:
            return cached

        prices = self.client.get_market_prices(condition_id, side='SELL')

        yes_price = prices.get('yes')
        no_price = prices.get('no')

        if yes_price is None or no_price is None:
            logger.warning(
                f"Could not fetch exit prices (BID) for {condition_id[:16]}... | "
                f"YES={yes_price}, NO={no_price}"
            )
            return None

        if not self._validate_raw_price(yes_price, 'YES BID', condition_id):
            return None
        if not self._validate_raw_price(no_price, 'NO BID', condition_id):
            return None

        result = MarketPrices(
            yes_price=yes_price,
            no_price=no_price,
            source='CLOB_BID',
            condition_id=condition_id
        )
        self._set_cached(condition_id, 'SELL', result)
        return result

    def get_entry_and_exit_prices(self, condition_id: str) -> Optional[Tuple[MarketPrices, MarketPrices]]:
        """
        Get both entry (ask) and exit (bid) prices in one call.

        Useful for:
        - Calculating spread
        - Checking arbitrage opportunities
        - Understanding market liquidity

        Args:
            condition_id: Market condition ID

        Returns:
            Tuple of (entry_prices, exit_prices), or None if either unavailable
        """
        entry_prices = self.get_entry_prices(condition_id)
        exit_prices = self.get_exit_prices(condition_id)

        if entry_prices is None or exit_prices is None:
            return None

        return (entry_prices, exit_prices)

    def calculate_spread(self, condition_id: str) -> Optional[Dict[str, float]]:
        """
        Calculate bid-ask spread for a market.

        Args:
            condition_id: Market condition ID

        Returns:
            Dict with spread info:
            - yes_spread_bps: YES spread in basis points
            - no_spread_bps: NO spread in basis points
            - yes_spread_pct: YES spread as percentage
            - no_spread_pct: NO spread as percentage
        """
        prices = self.get_entry_and_exit_prices(condition_id)
        if prices is None:
            return None

        entry_prices, exit_prices = prices

        # Spread = ASK - BID
        yes_spread = entry_prices.yes_price - exit_prices.yes_price
        no_spread = entry_prices.no_price - exit_prices.no_price

        # Prevent division by zero
        yes_mid = (entry_prices.yes_price + exit_prices.yes_price) / 2
        no_mid = (entry_prices.no_price + exit_prices.no_price) / 2

        return {
            'yes_spread_bps': (yes_spread / yes_mid * 10000) if yes_mid > 0 else 0,
            'no_spread_bps': (no_spread / no_mid * 10000) if no_mid > 0 else 0,
            'yes_spread_pct': (yes_spread / yes_mid * 100) if yes_mid > 0 else 0,
            'no_spread_pct': (no_spread / no_mid * 100) if no_mid > 0 else 0,
            'yes_ask': entry_prices.yes_price,
            'yes_bid': exit_prices.yes_price,
            'no_ask': entry_prices.no_price,
            'no_bid': exit_prices.no_price
        }

    def validate_prices(self, prices: MarketPrices, max_price: float = 0.90) -> Tuple[bool, Optional[str]]:
        """
        Validate prices are within acceptable range.

        Args:
            prices: MarketPrices to validate
            max_price: Maximum acceptable price (default 0.90)

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        # Check YES price
        if prices.yes_price > max_price:
            return (
                False,
                f"YES price ${prices.yes_price:.3f} exceeds max ${max_price:.2f}"
            )

        # Check NO price
        if prices.no_price > max_price:
            return (
                False,
                f"NO price ${prices.no_price:.3f} exceeds max ${max_price:.2f}"
            )

        # Check prices are in valid range [0, 1]
        if not (0 <= prices.yes_price <= 1) or not (0 <= prices.no_price <= 1):
            return (
                False,
                f"Prices out of range: YES=${prices.yes_price:.3f}, NO=${prices.no_price:.3f}"
            )

        return (True, None)
