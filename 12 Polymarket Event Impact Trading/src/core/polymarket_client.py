"""
Polymarket API Client
Handles authentication, market data retrieval, and order execution.
"""

import requests
import time
import hmac
import hashlib
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
import pandas as pd


class PolymarketClient:
    """Client for interacting with Polymarket's CLOB API."""

    BASE_URL = "https://clob.polymarket.com"
    GAMMA_URL = "https://gamma-api.polymarket.com"
    WEB_URL = "https://polymarket.com"

    # Known multi-market event slugs
    EVENT_SLUGS = {
        'BTC': 'what-price-will-bitcoin-hit-before-2027',
        'ETH': 'what-price-will-ethereum-hit-before-2027',
        'GOLD': 'what-will-gold-gc-hit-by-end-of-february',
    }

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 private_key: Optional[str] = None):
        """
        Initialize Polymarket client.

        Args:
            api_key: API key for authenticated requests
            api_secret: API secret for signing requests
            private_key: Ethereum private key for order signing
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.private_key = private_key
        self.session = requests.Session()

    @classmethod
    def build_market_url(cls, market: Dict = None, event_slug: str = None,
                        market_slug: str = None, asset: str = None) -> str:
        """
        Build a Polymarket web URL for a market.

        For multi-market events (BTC/ETH/GOLD price levels), returns event-level URL.
        For standalone markets, returns individual market URL.

        Args:
            market: Market dict from API (optional, contains slug and other metadata)
            event_slug: Event slug for multi-market events (e.g., 'what-price-will-bitcoin-hit-before-2027')
            market_slug: Individual market slug for standalone markets
            asset: Asset symbol (BTC/ETH/GOLD) to look up event slug

        Returns:
            Polymarket web URL string

        Examples:
            # Using asset symbol
            >>> build_market_url(asset='BTC')
            'https://polymarket.com/event/what-price-will-bitcoin-hit-before-2027'

            # Using event slug directly
            >>> build_market_url(event_slug='my-event-slug')
            'https://polymarket.com/event/my-event-slug'

            # Using market dict
            >>> build_market_url(market={'slug': 'my-market-slug'})
            'https://polymarket.com/market/my-market-slug'
        """
        # Priority 1: Event slug (for multi-market events like BTC/ETH/GOLD)
        if event_slug:
            return f"{cls.WEB_URL}/event/{event_slug}"

        # Priority 2: Asset symbol (lookup event slug)
        if asset and asset in cls.EVENT_SLUGS:
            return f"{cls.WEB_URL}/event/{cls.EVENT_SLUGS[asset]}"

        # Priority 3: Market dict (extract slug)
        if market:
            slug = market.get('slug')
            if slug:
                return f"{cls.WEB_URL}/market/{slug}"

        # Priority 4: Direct market slug
        if market_slug:
            return f"{cls.WEB_URL}/market/{market_slug}"

        # Fallback: markets homepage
        return f"{cls.WEB_URL}/markets"

    def _get_headers(self, signature: Optional[str] = None) -> Dict:
        """Generate request headers."""
        headers = {
            'Content-Type': 'application/json',
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        if signature:
            headers['Signature'] = signature
        return headers

    def _sign_request(self, method: str, path: str, body: str = "") -> str:
        """Sign request for authenticated endpoints."""
        if not self.api_secret:
            return ""

        timestamp = str(int(time.time()))
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    @staticmethod
    def filter_closed_markets(markets: List[Dict]) -> List[Dict]:
        """
        Filter out closed/resolved markets from a list of markets.

        This is a defensive utility to prevent bots from trading on resolved markets.
        Closed markets have no CLOB orderbooks and will cause "No liquidity" errors.

        Args:
            markets: List of market dictionaries

        Returns:
            List of markets with closed=False
        """
        return [m for m in markets if not m.get('closed', False)]

    def get_markets(self, limit: int = 100, offset: int = 0,
                   active: bool = True, closed: bool = False,
                   end_date_min: Optional[str] = None,
                   end_date_max: Optional[str] = None,
                   liquidity_num_min: Optional[float] = None,
                   volume_num_min: Optional[float] = None,
                   category: Optional[str] = None,
                   tag_id: Optional[int] = None,
                   slug: Optional[str] = None) -> List[Dict]:
        """
        Get list of markets.

        Args:
            limit: Maximum number of markets to return
            offset: Offset for pagination
            active: Include active markets
            closed: Include closed markets
            end_date_min: Earliest market end date (ISO format)
            end_date_max: Latest market end date (ISO format)
            liquidity_num_min: Minimum liquidity threshold
            volume_num_min: Minimum trading volume
            category: Filter by category (e.g., 'crypto', 'politics')
            tag_id: Filter by specific tag ID
            slug: Filter by market slug

        Returns:
            List of market dictionaries
        """
        params = {
            'limit': limit,
            'offset': offset,
            'active': active,
            'closed': closed
        }

        # Add optional parameters only if provided
        if end_date_min is not None:
            params['end_date_min'] = end_date_min
        if end_date_max is not None:
            params['end_date_max'] = end_date_max
        if liquidity_num_min is not None:
            params['liquidity_num_min'] = liquidity_num_min
        if volume_num_min is not None:
            params['volume_num_min'] = volume_num_min
        if category is not None:
            params['category'] = category
        if tag_id is not None:
            params['tag_id'] = tag_id
        if slug is not None:
            params['slug'] = slug

        try:
            response = self.session.get(
                f"{self.GAMMA_URL}/markets",
                params=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            markets = response.json()

            # Defensive filtering: Even if closed=False, the API might return closed markets
            # Apply client-side filtering to ensure we never trade on resolved markets
            if not closed and markets:
                markets = self.filter_closed_markets(markets)

            return markets
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return []

    def get_event(self, slug: str) -> Optional[Dict]:
        """
        Get event details by slug (includes restricted markets).

        Args:
            slug: Event slug (e.g., 'what-price-will-ethereum-hit-before-2027')

        Returns:
            Event dictionary with markets or None
        """
        try:
            response = self.session.get(
                f"{self.GAMMA_URL}/events",
                params={'slug': slug},
                headers=self._get_headers()
            )
            response.raise_for_status()
            events = response.json()
            return events[0] if events else None
        except Exception as e:
            print(f"Error fetching event {slug}: {e}")
            return None

    def get_markets_from_event(self, slug: str, exclude_closed: bool = True) -> List[Dict]:
        """
        Get all markets from an event (includes restricted markets).

        This is useful for fetching markets that don't appear in the
        standard /markets endpoint (e.g., restricted markets).

        Args:
            slug: Event slug
            exclude_closed: If True, filter out closed/resolved markets (default: True)

        Returns:
            List of market dictionaries (excluding closed markets by default)
        """
        event = self.get_event(slug)
        if not event:
            return []

        markets = event.get('markets', [])

        # Filter out closed markets by default to prevent trading on resolved markets
        if exclude_closed:
            markets = [m for m in markets if not m.get('closed', False)]

        return markets

    def get_market(self, condition_id: str) -> Optional[Dict]:
        """
        Get details for a specific market.

        Uses CLOB API which supports /markets/{conditionId} format.
        Gamma API's /markets/{id} returns 422 for all markets.

        Args:
            condition_id: Market condition ID

        Returns:
            Market dictionary or None
        """
        try:
            # Use CLOB API (Gamma API /markets/{id} returns 422)
            response = self.session.get(
                f"{self.BASE_URL}/markets/{condition_id}",
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching market {condition_id}: {e}")
            return None

    def get_market_prices(self, condition_id: str) -> Dict[str, Optional[float]]:
        """
        Get both YES and NO prices from CLOB API.

        Args:
            condition_id: Market condition ID

        Returns:
            Dict with 'yes' and 'no' prices, e.g. {'yes': 0.3, 'no': 0.7}
        """
        result = {'yes': None, 'no': None}
        market = self.get_market(condition_id)
        if not market:
            return result

        tokens = market.get('tokens', [])
        for token in tokens:
            outcome = token.get('outcome', '').lower()
            if outcome in ('yes', 'no'):
                try:
                    price = token.get('price')
                    if price is not None:  # Don't default to 0 - that's a real price!
                        result[outcome] = float(price)
                except (ValueError, TypeError):
                    pass

        return result

    def get_market_yes_price(self, condition_id: str, event_slug: str = None) -> Optional[float]:
        """
        Get YES outcome price from CLOB API.

        Uses CLOB API's tokens array which has explicit outcome mapping,
        avoiding any ambiguity about which token is YES vs NO.

        Args:
            condition_id: Market condition ID (not token_id)
            event_slug: Unused (kept for backward compatibility)

        Returns:
            YES price (0-1) or None
        """
        prices = self.get_market_prices(condition_id)
        return prices.get('yes')

    def get_market_outcome_price(self, condition_id: str, outcome: str) -> Optional[float]:
        """
        Get price for a specific outcome (YES or NO).

        Args:
            condition_id: Market condition ID
            outcome: 'YES' or 'NO'

        Returns:
            Price for the specified outcome, or None
        """
        prices = self.get_market_prices(condition_id)
        return prices.get(outcome.lower())

    def get_clob_market(self, condition_id: str) -> Optional[Dict]:
        """
        Get market data from CLOB API (includes token-to-outcome mapping).

        Args:
            condition_id: Market condition ID

        Returns:
            Market dictionary from CLOB API or None
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/markets/{condition_id}",
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Try searching in the list
            try:
                response = self.session.get(
                    f"{self.BASE_URL}/markets",
                    params={'condition_id': condition_id},
                    headers=self._get_headers(),
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    markets = data.get('data', [])
                    for m in markets:
                        if m.get('condition_id') == condition_id:
                            return m
            except:
                pass
            return None

    def get_token_ids(self, condition_id: str) -> Dict[str, Optional[str]]:
        """
        Get token IDs with their outcomes from CLOB API.

        The CLOB /markets endpoint provides explicit token-to-outcome mapping
        in the 'tokens' array, which is the authoritative source.

        Args:
            condition_id: Market condition ID

        Returns:
            Dict with 'yes_token_id' and 'no_token_id'
        """
        result = {'yes_token_id': None, 'no_token_id': None}

        clob_market = self.get_clob_market(condition_id)
        if not clob_market:
            return result

        tokens = clob_market.get('tokens', [])
        for token in tokens:
            outcome = token.get('outcome', '').lower()
            token_id = token.get('token_id')

            if outcome == 'yes':
                result['yes_token_id'] = token_id
            elif outcome == 'no':
                result['no_token_id'] = token_id

        return result

    def identify_yes_token(self, market: Dict) -> Optional[str]:
        """
        Identify which token corresponds to the YES outcome.

        Uses CLOB API's explicit token-to-outcome mapping (preferred),
        falls back to price comparison if CLOB unavailable.

        Args:
            market: Market dictionary (from Gamma or CLOB)

        Returns:
            Token ID for YES outcome, or None if can't determine
        """
        import json as json_mod

        condition_id = market.get('conditionId') or market.get('condition_id')

        # Method 1: Use CLOB's explicit token mapping (preferred)
        if condition_id:
            token_ids = self.get_token_ids(condition_id)
            if token_ids.get('yes_token_id'):
                return token_ids['yes_token_id']

        # Method 2: Check if market already has tokens array (from CLOB)
        tokens = market.get('tokens', [])
        for token in tokens:
            if token.get('outcome', '').lower() == 'yes':
                return token.get('token_id')

        # Method 3: Fall back to price comparison (less reliable)
        clob_tokens = market.get('clobTokenIds', '[]')
        if isinstance(clob_tokens, str):
            try:
                clob_tokens = json_mod.loads(clob_tokens)
            except:
                return None

        if len(clob_tokens) != 2:
            return None

        outcome_prices = market.get('outcomePrices', '[]')
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json_mod.loads(outcome_prices)
            except:
                return None

        if len(outcome_prices) < 2:
            # Last resort: assume token[0] is YES (risky!)
            print(f"WARNING: Cannot verify YES token for {condition_id}, assuming token[0]")
            return clob_tokens[0]

        try:
            gamma_yes_price = float(outcome_prices[0])
        except (ValueError, TypeError):
            return clob_tokens[0]

        # Compare CLOB prices to Gamma to determine which is YES
        price_0 = self._get_clob_mid_price(clob_tokens[0])
        price_1 = self._get_clob_mid_price(clob_tokens[1])

        if price_0 is not None and price_1 is not None:
            if abs(price_0 - gamma_yes_price) < abs(price_1 - gamma_yes_price):
                return clob_tokens[0]
            else:
                return clob_tokens[1]

        return clob_tokens[0]  # Last resort fallback

    def _get_clob_mid_price(self, token_id: str) -> Optional[float]:
        """Get mid-price from CLOB orderbook."""
        orderbook = self.get_orderbook(token_id)

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            # Try last_trade_price as fallback
            last_trade = orderbook.get('last_trade_price')
            if last_trade:
                try:
                    return float(last_trade)
                except:
                    pass
            return None

        try:
            best_bid = float(bids[0]['price'])
            best_ask = float(asks[0]['price'])
            return (best_bid + best_ask) / 2
        except (ValueError, TypeError, KeyError):
            return None

    def get_execution_prices(self, token_id: str) -> Dict[str, Optional[float]]:
        """
        Get execution prices from CLOB orderbook.

        Args:
            token_id: Token ID to get prices for

        Returns:
            Dict with 'bid' (sell price), 'ask' (buy price), 'mid', 'spread'
        """
        orderbook = self.get_orderbook(token_id)

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        result = {'bid': None, 'ask': None, 'mid': None, 'spread': None}

        if bids:
            try:
                result['bid'] = float(bids[0]['price'])
            except:
                pass

        if asks:
            try:
                result['ask'] = float(asks[0]['price'])
            except:
                pass

        if result['bid'] and result['ask']:
            result['mid'] = (result['bid'] + result['ask']) / 2
            result['spread'] = result['ask'] - result['bid']

        return result

    def search_markets(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search markets by keyword.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching markets
        """
        markets = self.get_markets(limit=limit)

        # Filter markets by query
        query_lower = query.lower()
        filtered = [
            m for m in markets
            if query_lower in m.get('question', '').lower() or
               query_lower in m.get('description', '').lower()
        ]

        return filtered

    def get_orderbook(self, token_id: str) -> Dict:
        """
        Get order book for a specific token.

        Args:
            token_id: Token ID

        Returns:
            Order book with bids and asks
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/book",
                params={'token_id': token_id},
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching orderbook for {token_id}: {e}")
            return {'bids': [], 'asks': []}

    def get_trades(self, token_id: str, limit: int = 100) -> List[Dict]:
        """
        Get recent trades for a token.

        Args:
            token_id: Token ID
            limit: Maximum number of trades

        Returns:
            List of trade dictionaries
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/trades",
                params={'token_id': token_id, 'limit': limit},
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching trades for {token_id}: {e}")
            return []

    def get_market_price(self, token_id: str) -> Optional[float]:
        """
        Get current market price for a token.

        Priority order:
        1. last_trade_price from orderbook (most accurate)
        2. Mid-price if spread is reasonable (<20%)
        3. None if spread is too wide (unreliable)

        Args:
            token_id: Token ID

        Returns:
            Current price or None
        """
        orderbook = self.get_orderbook(token_id)

        # Try last_trade_price first (most accurate)
        last_trade = orderbook.get('last_trade_price')
        if last_trade:
            try:
                return float(last_trade)
            except (ValueError, TypeError):
                pass

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return None

        best_bid = float(bids[0]['price'])
        best_ask = float(asks[0]['price'])

        # Check spread - reject if too wide (>20%)
        spread = best_ask - best_bid
        if spread > 0.20:
            # Wide spread makes mid-price unreliable
            return None

        return (best_bid + best_ask) / 2

    def get_market_spread(self, token_id: str) -> Optional[float]:
        """
        Get bid-ask spread for a token.

        Args:
            token_id: Token ID

        Returns:
            Spread or None
        """
        orderbook = self.get_orderbook(token_id)

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return None

        best_bid = float(bids[0]['price'])
        best_ask = float(asks[0]['price'])

        return best_ask - best_bid

    def get_price_from_market(self, market: Dict, outcome_index: int = 0) -> Optional[float]:
        """
        Get price from market's outcomePrices field (most reliable).

        Args:
            market: Market dictionary from API
            outcome_index: 0 for YES, 1 for NO

        Returns:
            Price or None
        """
        import json as _json
        outcome_prices = market.get('outcomePrices', '[]')
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = _json.loads(outcome_prices)
            except _json.JSONDecodeError:
                return None

        if outcome_prices and len(outcome_prices) > outcome_index:
            try:
                return float(outcome_prices[outcome_index])
            except (ValueError, TypeError):
                return None
        return None

    def get_historical_prices(self, token_id: str,
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None,
                             interval: str = '1h') -> pd.DataFrame:
        """
        Get historical price data for a token.

        Args:
            token_id: Token ID
            start_time: Start datetime
            end_time: End datetime
            interval: Time interval (1m, 5m, 15m, 1h, 1d)

        Returns:
            DataFrame with OHLCV data
        """
        # Note: This is a placeholder. Polymarket's historical data API
        # may require different endpoints or have rate limits.
        # You may need to build your own database by storing snapshots.

        trades = self.get_trades(token_id, limit=1000)

        if not trades:
            return pd.DataFrame()

        df = pd.DataFrame(trades)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df['price'] = df['price'].astype(float)
        df['size'] = df['size'].astype(float)

        # Filter by time range
        if start_time:
            df = df[df['timestamp'] >= start_time]
        if end_time:
            df = df[df['timestamp'] <= end_time]

        return df.sort_values('timestamp')

    def place_order(self, token_id: str, side: str, price: float,
                   size: float, order_type: str = 'GTC') -> Optional[Dict]:
        """
        Place an order.

        Args:
            token_id: Token ID
            side: 'BUY' or 'SELL'
            price: Limit price
            size: Order size
            order_type: Order type (GTC, FOK, IOC)

        Returns:
            Order response or None
        """
        if not self.private_key:
            print("Private key required for order placement")
            return None

        # Note: This is a simplified placeholder.
        # Actual implementation requires:
        # 1. Creating order message
        # 2. Signing with Ethereum private key
        # 3. Submitting to CLOB

        order = {
            'token_id': token_id,
            'side': side,
            'price': str(price),
            'size': str(size),
            'type': order_type,
            'timestamp': int(time.time())
        }

        try:
            # This would need proper order signing implementation
            response = self.session.post(
                f"{self.BASE_URL}/order",
                json=order,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error placing order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            True if successful
        """
        try:
            response = self.session.delete(
                f"{self.BASE_URL}/order/{order_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error canceling order {order_id}: {e}")
            return False

    def get_positions(self) -> List[Dict]:
        """
        Get current positions.

        Returns:
            List of position dictionaries
        """
        if not self.api_key:
            print("API key required for positions")
            return []

        try:
            response = self.session.get(
                f"{self.BASE_URL}/positions",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

    def get_balance(self) -> Optional[float]:
        """
        Get account balance.

        Returns:
            Balance in USDC or None
        """
        if not self.api_key:
            print("API key required for balance")
            return None

        try:
            response = self.session.get(
                f"{self.BASE_URL}/balance",
                headers=self._get_headers()
            )
            response.raise_for_status()
            data = response.json()
            return float(data.get('balance', 0))
        except Exception as e:
            print(f"Error fetching balance: {e}")
            return None


class MarketFilter:
    """Filter markets by various criteria."""

    @staticmethod
    def filter_by_liquidity(markets: List[Dict], min_volume: float = 1000) -> List[Dict]:
        """Filter markets by minimum volume."""
        return [m for m in markets if float(m.get('volume', 0)) >= min_volume]

    @staticmethod
    def filter_by_category(markets: List[Dict], categories: List[str]) -> List[Dict]:
        """Filter markets by category tags."""
        return [
            m for m in markets
            if any(cat in m.get('tags', []) for cat in categories)
        ]

    @staticmethod
    def filter_active_only(markets: List[Dict]) -> List[Dict]:
        """Filter for active markets only."""
        now = datetime.now(timezone.utc)
        filtered = []
        for m in markets:
            if not m.get('active', False):
                continue
            try:
                end_date_str = m.get('endDate') or m.get('endDateIso', '2099-01-01')
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                if end_date > now:
                    filtered.append(m)
            except:
                continue
        return filtered

    @staticmethod
    def filter_by_time_to_expiry(markets: List[Dict],
                                 min_hours: float = 1,
                                 max_hours: float = 720) -> List[Dict]:
        """Filter markets by time until expiry."""
        now = datetime.now(timezone.utc)
        filtered = []

        for m in markets:
            try:
                # Try endDate first (has full timestamp), then fall back to endDateIso
                end_date_str = m.get('endDate') or m.get('endDateIso')
                if not end_date_str:
                    continue

                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                hours_to_expiry = (end_date - now).total_seconds() / 3600

                if min_hours <= hours_to_expiry <= max_hours:
                    filtered.append(m)
            except:
                continue

        return filtered

    # Crypto-related keywords for market filtering
    # Long keywords (7+ chars) can use simple substring matching
    CRYPTO_KEYWORDS_LONG = {
        'bitcoin', 'ethereum', 'cryptocurrency',
        'solana', 'dogecoin', 'ripple', 'cardano',
        'polygon', 'chainlink',  # Removed 'avalanche' - conflicts with hockey team
        'uniswap', 'stablecoin', 'coinbase', 'blockchain',
        'altcoin', 'memecoin', 'halving',
        'satoshi', 'nakamoto', 'vitalik', 'buterin'
    }

    # Short/ambiguous keywords need word boundary matching to avoid false positives
    # (e.g., "eth" in "whether", "sol" in "resolution", "defi" in "deficit")
    CRYPTO_KEYWORDS_SHORT = {
        'btc', 'eth', 'sol', 'xrp', 'ada', 'matic', 'avax', 'link',
        'uni', 'nft', 'ftx', 'usdt', 'usdc', 'defi', 'aave',
        'crypto', 'binance', 'gensler'  # Removed 'kraken' - conflicts with hockey team
    }

    # Ambiguous keywords that need crypto context to match
    CRYPTO_KEYWORDS_AMBIGUOUS = {
        'avalanche', 'kraken'  # Could be hockey teams or crypto
    }

    # Sports keywords that indicate NOT crypto
    SPORTS_EXCLUSION_KEYWORDS = {
        'nhl', 'nba', 'nfl', 'mlb', 'stanley cup', 'playoffs', 'division',
        'conference', 'championship', 'win the', 'beat the', 'hockey', 'basketball',
        'football', 'baseball', 'super bowl', 'world series'
    }

    @staticmethod
    def filter_crypto_markets(markets: List[Dict]) -> List[Dict]:
        """
        Filter markets related to cryptocurrency.

        Args:
            markets: List of market dictionaries

        Returns:
            List of crypto-related markets
        """
        import re
        filtered = []

        for m in markets:
            question = m.get('question', '').lower()
            description = m.get('description', '').lower()
            text = f"{question} {description}"

            # Skip if clearly sports-related
            if any(kw in text for kw in MarketFilter.SPORTS_EXCLUSION_KEYWORDS):
                continue

            # Check long keywords (simple substring match)
            if any(kw in text for kw in MarketFilter.CRYPTO_KEYWORDS_LONG):
                filtered.append(m)
                continue

            # Check short keywords with word boundaries
            matched = False
            for kw in MarketFilter.CRYPTO_KEYWORDS_SHORT:
                if re.search(rf'\b{kw}\b', text):
                    filtered.append(m)
                    matched = True
                    break

            if matched:
                continue

            # Check ambiguous keywords only if crypto context present
            crypto_context = {'price', 'token', 'coin', 'trading', 'market cap', '$'}
            has_crypto_context = any(ctx in text for ctx in crypto_context)
            if has_crypto_context:
                for kw in MarketFilter.CRYPTO_KEYWORDS_AMBIGUOUS:
                    if kw in text:
                        filtered.append(m)
                        break

        return filtered

    # Known crypto event slugs that contain price-level markets
    # These events have markets that don't appear in the standard /markets endpoint
    CRYPTO_EVENT_SLUGS_LONG_TERM = [
        'what-price-will-bitcoin-hit-before-2027',  # 32 BTC price markets
        'what-price-will-ethereum-hit-before-2027',  # 16 ETH price markets
    ]

    @staticmethod
    def get_daily_crypto_event_slugs(days_ahead: int = 7) -> List[str]:
        """
        Generate daily crypto price prediction event slugs.

        These daily events (e.g., "ethereum-above-on-february-13") contain
        restricted markets that don't appear in the standard /markets endpoint.

        Args:
            days_ahead: Number of days to generate slugs for (default: 7)

        Returns:
            List of event slugs
        """
        from datetime import datetime, timedelta, timezone

        slugs = []
        assets = ['ethereum', 'bitcoin', 'solana', 'xrp']

        for days in range(days_ahead):
            date = datetime.now(timezone.utc) + timedelta(days=days)
            month = date.strftime('%B').lower()  # 'february'
            day = date.day

            for asset in assets:
                slug = f"{asset}-above-on-{month}-{day}"
                slugs.append(slug)

        return slugs

    @staticmethod
    def get_all_crypto_event_slugs(days_ahead: int = 7) -> List[str]:
        """
        Get all crypto event slugs (both long-term and daily).

        Args:
            days_ahead: Number of days for daily events (default: 7)

        Returns:
            List of all crypto event slugs
        """
        slugs = MarketFilter.CRYPTO_EVENT_SLUGS_LONG_TERM.copy()
        slugs.extend(MarketFilter.get_daily_crypto_event_slugs(days_ahead))
        return slugs

    @staticmethod
    def get_market_category(market: Dict) -> str:
        """
        Determine the category of a market.

        Args:
            market: Market dictionary

        Returns:
            Category string: 'crypto', 'politics', 'sports', 'economics', or 'other'
        """
        import re
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        text = f"{question} {description}"

        # Check crypto first (highest priority for our use case)
        if any(kw in text for kw in MarketFilter.CRYPTO_KEYWORDS_LONG):
            return 'crypto'
        for kw in MarketFilter.CRYPTO_KEYWORDS_SHORT:
            if re.search(rf'\b{kw}\b', text):
                return 'crypto'

        # Politics keywords
        politics_kw = {'trump', 'biden', 'president', 'election', 'congress',
                       'senate', 'democrat', 'republican', 'governor', 'mayor',
                       'vote', 'ballot', 'campaign', 'political', 'white house'}
        if any(kw in text for kw in politics_kw):
            return 'politics'

        # Sports keywords
        sports_kw = {'nfl', 'nba', 'mlb', 'nhl', 'super bowl', 'championship',
                     'playoffs', 'mvp', 'quarterback', 'touchdown', 'win the',
                     'world series', 'stanley cup', 'finals', 'rookie', 'coach'}
        if any(kw in text for kw in sports_kw):
            return 'sports'

        # Economics keywords
        econ_kw = {'fed', 'inflation', 'gdp', 'interest rate', 'recession',
                   'unemployment', 'cpi', 'federal reserve', 'economy', 'tariff'}
        if any(kw in text for kw in econ_kw):
            return 'economics'

        return 'other'

    @staticmethod
    def discover_markets(client,
                        category: Optional[str] = None,
                        min_hours_to_expiry: float = 2,
                        max_hours_to_expiry: float = 8760,
                        min_volume: float = 0,
                        min_liquidity: float = 0,
                        max_pages: int = 10,
                        include_crypto_events: bool = True,
                        crypto_event_days_ahead: int = 7,
                        logger=None) -> List[Dict]:
        """
        Unified market discovery for all bots.

        This method combines:
        1. Standard API /markets endpoint with filters
        2. Event-based fetching for restricted markets (crypto daily events)
        3. Client-side category filtering

        Args:
            client: PolymarketClient instance
            category: Filter by category ('crypto', 'politics', 'sports', etc.)
            min_hours_to_expiry: Minimum hours until market expiry
            max_hours_to_expiry: Maximum hours until market expiry
            min_volume: Minimum market volume
            min_liquidity: Minimum market liquidity
            max_pages: Maximum pages to fetch from API (100 markets per page)
            include_crypto_events: Fetch markets from crypto events (recommended for crypto)
            crypto_event_days_ahead: Number of days for daily crypto events
            logger: Optional logger instance

        Returns:
            List of market dictionaries
        """
        from datetime import datetime, timedelta, timezone
        import time as time_module

        if logger:
            logger.info(f"Starting market discovery: category={category}, "
                       f"expiry={min_hours_to_expiry}-{max_hours_to_expiry}h, "
                       f"min_volume=${min_volume:,.0f}")

        # Calculate date range for API filters
        now = datetime.now(timezone.utc)
        end_date_min = (now + timedelta(hours=min_hours_to_expiry)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_date_max = (now + timedelta(hours=max_hours_to_expiry)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Step 1: Fetch from /markets endpoint with API-level filters
        markets = []
        pagination_start = time_module.time()

        for page in range(max_pages):
            offset = page * 100
            batch = client.get_markets(
                limit=100,
                offset=offset,
                active=True,
                closed=False,
                end_date_min=end_date_min,
                end_date_max=end_date_max,
                volume_num_min=min_volume if min_volume > 0 else None,
                liquidity_num_min=min_liquidity if min_liquidity > 0 else None
            )
            if not batch:
                break
            markets.extend(batch)

        pagination_duration = time_module.time() - pagination_start

        if logger:
            logger.info(f"Retrieved {len(markets)} markets from API in {pagination_duration:.2f}s "
                       f"({len(markets)/pagination_duration:.1f} markets/sec)")

        # Step 2: Fetch from crypto events (these don't appear in /markets)
        if category == 'crypto' and include_crypto_events:
            event_markets = []
            event_start = time_module.time()

            # Get all crypto event slugs
            event_slugs = MarketFilter.get_all_crypto_event_slugs(crypto_event_days_ahead)

            if logger:
                logger.info(f"Fetching markets from {len(event_slugs)} crypto events...")

            for slug in event_slugs:
                try:
                    event_batch = client.get_markets_from_event(slug)
                    if event_batch:
                        event_markets.extend(event_batch)
                        if logger:
                            logger.debug(f"  + {len(event_batch)} markets from '{slug}'")
                except Exception as e:
                    if logger:
                        logger.debug(f"Event {slug} not found or error: {e}")

            event_duration = time_module.time() - event_start

            # De-duplicate by conditionId
            seen_ids = {m.get('conditionId') for m in markets if m.get('conditionId')}
            new_markets = [m for m in event_markets if m.get('conditionId') not in seen_ids]
            markets.extend(new_markets)

            if logger:
                logger.info(f"Added {len(new_markets)} unique event-based crypto markets "
                           f"in {event_duration:.2f}s")

        # Step 3: Apply client-side filters
        # Filter by active status and expiry
        markets = MarketFilter.filter_active_only(markets)
        markets = MarketFilter.filter_by_time_to_expiry(
            markets,
            min_hours=min_hours_to_expiry,
            max_hours=max_hours_to_expiry
        )

        # Filter by category
        if category == 'crypto':
            markets = MarketFilter.filter_crypto_markets(markets)
            if logger:
                logger.info(f"Filtered to {len(markets)} crypto markets")
        elif category:
            # Filter by category using keyword matching
            markets = [m for m in markets
                      if MarketFilter.get_market_category(m) == category]
            if logger:
                logger.info(f"Filtered to {len(markets)} {category} markets")

        if logger:
            logger.info(f"Final market count: {len(markets)}")

        return markets
