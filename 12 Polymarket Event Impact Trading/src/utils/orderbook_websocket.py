#!/usr/bin/env python3
"""
Polymarket Order Book WebSocket Client

Provides real-time bid/ask data for arbitrage detection.
Uses Polymarket's CLOB WebSocket API for level 2 order book updates.

WebSocket URL: wss://ws-subscriptions-clob.polymarket.com
Channel: market (public, no auth required)

References:
- https://docs.polymarket.com/developers/CLOB/websocket/wss-overview
- https://docs.polymarket.com/developers/CLOB/websocket/market-channel
"""

import json
import time
import logging
import threading
import random
from datetime import datetime
from typing import Dict, List, Optional, Callable, Set
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("Warning: websocket-client not installed. Run: pip install websocket-client")

logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Single price level in order book."""
    price: float
    size: float


@dataclass
class OrderBook:
    """Order book state for a single token."""
    asset_id: str
    condition_id: str = ""
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    last_trade_price: Optional[float] = None

    @property
    def best_bid(self) -> Optional[float]:
        """Get best (highest) bid price."""
        if not self.bids:
            return None
        return max(level.price for level in self.bids)

    @property
    def best_ask(self) -> Optional[float]:
        """Get best (lowest) ask price."""
        if not self.asks:
            return None
        return min(level.price for level in self.asks)

    @property
    def mid_price(self) -> Optional[float]:
        """Calculate mid-price."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2

    @property
    def spread(self) -> Optional[float]:
        """Calculate bid-ask spread."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is None or ask is None:
            return None
        return ask - bid

    @property
    def spread_pct(self) -> Optional[float]:
        """Calculate spread as percentage of mid-price."""
        mid = self.mid_price
        spread = self.spread
        if mid is None or spread is None or mid == 0:
            return None
        return spread / mid

    @property
    def bid_liquidity(self) -> float:
        """Total size on bid side."""
        return sum(level.size for level in self.bids)

    @property
    def ask_liquidity(self) -> float:
        """Total size on ask side."""
        return sum(level.size for level in self.asks)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'asset_id': self.asset_id,
            'condition_id': self.condition_id,
            'best_bid': self.best_bid,
            'best_ask': self.best_ask,
            'mid_price': self.mid_price,
            'spread': self.spread,
            'spread_pct': self.spread_pct,
            'bid_liquidity': self.bid_liquidity,
            'ask_liquidity': self.ask_liquidity,
            'last_update': self.last_update.isoformat(),
            'last_trade_price': self.last_trade_price
        }


@dataclass
class ArbitrageSignal:
    """Real-time arbitrage signal from order book data."""
    timestamp: datetime
    condition_id: str
    market_question: str

    # YES token order book
    yes_asset_id: str
    yes_best_bid: float
    yes_best_ask: float

    # NO token order book
    no_asset_id: str
    no_best_bid: float
    no_best_ask: float

    # Arbitrage calculation
    # To buy both: pay YES ask + NO ask
    # Guaranteed payout: $1
    total_cost_to_buy: float = 0.0
    profit_if_buy_both: float = 0.0

    # To sell both (if holding): receive YES bid + NO bid
    total_value_if_sell: float = 0.0
    profit_if_sell_both: float = 0.0

    is_profitable: bool = False
    arb_type: str = ""  # 'buy_both' or 'sell_both'

    def __post_init__(self):
        """Calculate arbitrage opportunity."""
        # Buy both sides: pay the ask prices
        self.total_cost_to_buy = self.yes_best_ask + self.no_best_ask
        self.profit_if_buy_both = 1.0 - self.total_cost_to_buy

        # Sell both sides: receive bid prices
        self.total_value_if_sell = self.yes_best_bid + self.no_best_bid
        self.profit_if_sell_both = self.total_value_if_sell - 1.0

        # Determine if profitable
        if self.profit_if_buy_both > 0.01:  # >1% profit
            self.is_profitable = True
            self.arb_type = 'buy_both'
        elif self.profit_if_sell_both > 0.01:
            self.is_profitable = True
            self.arb_type = 'sell_both'

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'condition_id': self.condition_id,
            'question': self.market_question[:60] if self.market_question else '',
            'yes_bid': self.yes_best_bid,
            'yes_ask': self.yes_best_ask,
            'no_bid': self.no_best_bid,
            'no_ask': self.no_best_ask,
            'cost_to_buy_both': self.total_cost_to_buy,
            'profit_buy': self.profit_if_buy_both,
            'value_if_sell_both': self.total_value_if_sell,
            'profit_sell': self.profit_if_sell_both,
            'is_profitable': self.is_profitable,
            'arb_type': self.arb_type
        }


class OrderBookWebSocket:
    """
    WebSocket client for real-time Polymarket order book data.

    Usage:
        ws_client = OrderBookWebSocket()
        ws_client.subscribe(['asset_id_1', 'asset_id_2'])
        ws_client.start()

        # Get current order book
        book = ws_client.get_order_book('asset_id_1')

        # Stop when done
        ws_client.stop()
    """

    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    PING_INTERVAL = 10  # seconds

    # Exponential backoff configuration
    INITIAL_RECONNECT_DELAY = 1  # seconds - start with 1s
    MAX_RECONNECT_DELAY = 60  # seconds - cap at 60s
    BACKOFF_MULTIPLIER = 2  # exponential factor
    JITTER_RANGE = 0.3  # ±30% random jitter to prevent thundering herd

    def __init__(self, on_book_update: Optional[Callable[[OrderBook], None]] = None,
                 on_arb_signal: Optional[Callable[[ArbitrageSignal], None]] = None):
        """
        Initialize WebSocket client.

        Args:
            on_book_update: Callback when order book updates
            on_arb_signal: Callback when arbitrage opportunity detected
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("websocket-client required. Install with: pip install websocket-client")

        self.on_book_update = on_book_update
        self.on_arb_signal = on_arb_signal

        # Order book state
        self._order_books: Dict[str, OrderBook] = {}
        self._lock = threading.Lock()

        # Subscription management
        self._subscribed_assets: Set[str] = set()
        self._asset_to_condition: Dict[str, str] = {}  # asset_id -> condition_id
        self._condition_to_assets: Dict[str, List[str]] = defaultdict(list)  # condition_id -> [yes_id, no_id]
        self._condition_questions: Dict[str, str] = {}  # condition_id -> question

        # WebSocket state
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_thread: Optional[threading.Thread] = None
        self._ping_thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False
        self._reconnect_count = 0
        self._current_backoff_delay = self.INITIAL_RECONNECT_DELAY

        # Statistics
        self.stats = {
            'messages_received': 0,
            'book_updates': 0,
            'price_changes': 0,
            'arb_signals': 0,
            'errors': 0,
            'reconnects': 0
        }

    def add_market(self, condition_id: str, yes_asset_id: str, no_asset_id: str,
                   question: str = "") -> None:
        """
        Add a market to track for arbitrage.

        Args:
            condition_id: Market condition ID
            yes_asset_id: Token ID for YES outcome
            no_asset_id: Token ID for NO outcome
            question: Market question for logging
        """
        with self._lock:
            self._asset_to_condition[yes_asset_id] = condition_id
            self._asset_to_condition[no_asset_id] = condition_id
            self._condition_to_assets[condition_id] = [yes_asset_id, no_asset_id]
            self._condition_questions[condition_id] = question

            # Initialize order books
            if yes_asset_id not in self._order_books:
                self._order_books[yes_asset_id] = OrderBook(
                    asset_id=yes_asset_id,
                    condition_id=condition_id
                )
            if no_asset_id not in self._order_books:
                self._order_books[no_asset_id] = OrderBook(
                    asset_id=no_asset_id,
                    condition_id=condition_id
                )

            self._subscribed_assets.add(yes_asset_id)
            self._subscribed_assets.add(no_asset_id)

        logger.debug(f"Added market {condition_id}: YES={yes_asset_id[:16]}..., NO={no_asset_id[:16]}...")

    def subscribe(self, asset_ids: List[str]) -> None:
        """
        Subscribe to order book updates for specific assets.

        Args:
            asset_ids: List of token/asset IDs to subscribe to
        """
        with self._lock:
            for asset_id in asset_ids:
                self._subscribed_assets.add(asset_id)
                if asset_id not in self._order_books:
                    self._order_books[asset_id] = OrderBook(asset_id=asset_id)

        # If already connected, send subscription message
        if self._connected and self._ws:
            msg = json.dumps({
                "assets_ids": asset_ids,
                "operation": "subscribe"
            })
            try:
                self._ws.send(msg)
                logger.info(f"Subscribed to {len(asset_ids)} assets")
            except Exception as e:
                logger.error(f"Error subscribing: {e}")

    def unsubscribe(self, asset_ids: List[str]) -> None:
        """Unsubscribe from specific assets."""
        with self._lock:
            for asset_id in asset_ids:
                self._subscribed_assets.discard(asset_id)

        if self._connected and self._ws:
            msg = json.dumps({
                "assets_ids": asset_ids,
                "operation": "unsubscribe"
            })
            try:
                self._ws.send(msg)
            except Exception as e:
                logger.error(f"Error unsubscribing: {e}")

    def get_order_book(self, asset_id: str) -> Optional[OrderBook]:
        """Get current order book state for an asset."""
        with self._lock:
            return self._order_books.get(asset_id)

    def get_all_order_books(self) -> Dict[str, OrderBook]:
        """Get all order books."""
        with self._lock:
            return dict(self._order_books)

    def check_arbitrage(self, condition_id: str) -> Optional[ArbitrageSignal]:
        """
        Check for arbitrage opportunity on a specific market.

        Args:
            condition_id: Market condition ID

        Returns:
            ArbitrageSignal if opportunity exists, None otherwise
        """
        with self._lock:
            asset_ids = self._condition_to_assets.get(condition_id)
            if not asset_ids or len(asset_ids) != 2:
                return None

            yes_id, no_id = asset_ids
            yes_book = self._order_books.get(yes_id)
            no_book = self._order_books.get(no_id)

            if not yes_book or not no_book:
                return None

            # Need both bid and ask for both sides
            if (yes_book.best_bid is None or yes_book.best_ask is None or
                no_book.best_bid is None or no_book.best_ask is None):
                return None

            signal = ArbitrageSignal(
                timestamp=datetime.now(),
                condition_id=condition_id,
                market_question=self._condition_questions.get(condition_id, ''),
                yes_asset_id=yes_id,
                yes_best_bid=yes_book.best_bid,
                yes_best_ask=yes_book.best_ask,
                no_asset_id=no_id,
                no_best_bid=no_book.best_bid,
                no_best_ask=no_book.best_ask
            )

            return signal

    def check_all_arbitrage(self) -> List[ArbitrageSignal]:
        """Check all tracked markets for arbitrage."""
        signals = []
        with self._lock:
            condition_ids = list(self._condition_to_assets.keys())

        for condition_id in condition_ids:
            signal = self.check_arbitrage(condition_id)
            if signal and signal.is_profitable:
                signals.append(signal)
                self.stats['arb_signals'] += 1

        return signals

    def start(self) -> None:
        """Start WebSocket connection in background thread."""
        if self._running:
            logger.warning("WebSocket already running")
            return

        self._running = True
        self._ws_thread = threading.Thread(target=self._run_websocket, daemon=True)
        self._ws_thread.start()

        # Start ping thread to keep connection alive
        self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._ping_thread.start()

        logger.info("OrderBook WebSocket started")

    def stop(self) -> None:
        """Stop WebSocket connection."""
        self._running = False
        if self._ws:
            self._ws.close()
        logger.info("OrderBook WebSocket stopped")

    def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """Wait for WebSocket to connect."""
        start = time.time()
        while time.time() - start < timeout:
            if self._connected:
                return True
            time.sleep(0.1)
        return False

    def _run_websocket(self) -> None:
        """
        Run WebSocket connection loop with exponential backoff reconnection.

        Implements:
        - Exponential backoff: starts at 1s, doubles each attempt up to 60s max
        - Random jitter: ±30% randomization to prevent thundering herd
        - Unlimited retries: keeps trying as long as self._running is True
        - Backoff reset: resets delay to initial value on successful connection
        """
        while self._running:
            try:
                self._ws = websocket.WebSocketApp(
                    self.WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                self._ws.run_forever()

            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.stats['errors'] += 1

            # Only reconnect if still running (not explicitly stopped)
            if self._running:
                self._reconnect_count += 1
                self.stats['reconnects'] += 1

                # Calculate exponential backoff with jitter
                jitter = random.uniform(
                    -self.JITTER_RANGE * self._current_backoff_delay,
                    self.JITTER_RANGE * self._current_backoff_delay
                )
                delay = self._current_backoff_delay + jitter

                logger.info(
                    f"Reconnecting in {delay:.1f}s... "
                    f"(attempt #{self._reconnect_count}, "
                    f"base delay: {self._current_backoff_delay}s)"
                )

                time.sleep(delay)

                # Increase backoff delay for next attempt (exponential backoff)
                self._current_backoff_delay = min(
                    self._current_backoff_delay * self.BACKOFF_MULTIPLIER,
                    self.MAX_RECONNECT_DELAY
                )

    def _ping_loop(self) -> None:
        """Send periodic pings to keep connection alive."""
        while self._running:
            time.sleep(self.PING_INTERVAL)
            if self._connected and self._ws:
                try:
                    self._ws.send("PING")
                except:
                    pass

    def _on_open(self, ws) -> None:
        """Handle WebSocket connection opened - reset backoff on successful connection."""
        self._connected = True
        self._reconnect_count = 0

        # Reset backoff delay on successful connection
        self._current_backoff_delay = self.INITIAL_RECONNECT_DELAY

        logger.info("WebSocket connected successfully (backoff reset)")

        # Send initial subscription
        if self._subscribed_assets:
            msg = json.dumps({
                "assets_ids": list(self._subscribed_assets),
                "type": "market"
            })
            ws.send(msg)
            logger.info(f"Subscribed to {len(self._subscribed_assets)} assets")

    def _on_message(self, ws, message: str) -> None:
        """Handle incoming WebSocket message."""
        self.stats['messages_received'] += 1

        # Handle PONG
        if message == "PONG":
            return

        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        # Handle array of book updates (initial snapshot)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    self._handle_book_update(item)
            return

        # Handle single object messages
        event_type = data.get('event_type')

        if event_type == 'book':
            self._handle_book_update(data)
        elif event_type == 'last_trade_price':
            self._handle_last_trade(data)
        elif 'price_changes' in data:
            # price_changes event contains best_bid/best_ask updates
            self._handle_price_changes(data)
            self.stats['price_changes'] += 1
        elif event_type == 'price_change':
            self.stats['price_changes'] += 1
        # Ignore other event types for now

    def _handle_book_update(self, data: Dict) -> None:
        """
        Handle order book update message.

        Format from WebSocket:
        {
            "market": "0x...",
            "asset_id": "101676997...",
            "timestamp": "1769748263265",
            "hash": "035a5f834415087f...",
            "bids": [{"price": "0.001", "size": "10689.14"}, ...],
            "asks": [{"price": "0.999", "size": "100"}, ...]
        }
        """
        asset_id = data.get('asset_id')
        if not asset_id:
            return

        self.stats['book_updates'] += 1

        with self._lock:
            book = self._order_books.get(asset_id)
            if not book:
                book = OrderBook(asset_id=asset_id)
                self._order_books[asset_id] = book

            # Update condition_id from market field if available
            market_id = data.get('market')
            if market_id and not book.condition_id:
                book.condition_id = market_id
                self._asset_to_condition[asset_id] = market_id

            # Parse bids - sorted descending by price (best bid first)
            bids = data.get('bids', data.get('buys', []))
            try:
                book.bids = sorted([
                    OrderBookLevel(
                        price=float(level.get('price', 0)),
                        size=float(level.get('size', 0))
                    )
                    for level in bids if level.get('price')
                ], key=lambda x: x.price, reverse=True)
            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing bids: {e}")

            # Parse asks - sorted ascending by price (best ask first)
            asks = data.get('asks', data.get('sells', []))
            try:
                book.asks = sorted([
                    OrderBookLevel(
                        price=float(level.get('price', 0)),
                        size=float(level.get('size', 0))
                    )
                    for level in asks if level.get('price')
                ], key=lambda x: x.price)
            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing asks: {e}")

            book.last_update = datetime.now()

            # Get condition ID
            condition_id = self._asset_to_condition.get(asset_id)

        # Callback
        if self.on_book_update:
            self.on_book_update(book)

        # Check for arbitrage if we have the pair
        if condition_id:
            signal = self.check_arbitrage(condition_id)
            if signal and signal.is_profitable and self.on_arb_signal:
                self.on_arb_signal(signal)

    def _handle_last_trade(self, data: Dict) -> None:
        """Handle last trade price update."""
        asset_id = data.get('asset_id')
        price = data.get('price')

        if asset_id and price:
            with self._lock:
                book = self._order_books.get(asset_id)
                if book:
                    try:
                        book.last_trade_price = float(price)
                    except (ValueError, TypeError):
                        pass

    def _handle_price_changes(self, data: Dict) -> None:
        """
        Handle price_changes event which contains best_bid/best_ask updates.

        Format:
        {
            "market": "0x...",
            "price_changes": [
                {
                    "asset_id": "...",
                    "price": "0.862",
                    "size": "0",
                    "side": "BUY",
                    "best_bid": "0.955",
                    "best_ask": "0.972"
                },
                ...
            ]
        }
        """
        price_changes = data.get('price_changes', [])
        condition_ids_updated = set()

        for change in price_changes:
            asset_id = change.get('asset_id')
            if not asset_id:
                continue

            best_bid = change.get('best_bid')
            best_ask = change.get('best_ask')

            if not best_bid or not best_ask:
                continue

            with self._lock:
                book = self._order_books.get(asset_id)
                if not book:
                    book = OrderBook(asset_id=asset_id)
                    self._order_books[asset_id] = book

                try:
                    # Update with simplified order book (just best bid/ask)
                    book.bids = [OrderBookLevel(price=float(best_bid), size=0)]
                    book.asks = [OrderBookLevel(price=float(best_ask), size=0)]
                    book.last_update = datetime.now()

                    # Track condition for arbitrage check
                    condition_id = self._asset_to_condition.get(asset_id)
                    if condition_id:
                        condition_ids_updated.add(condition_id)

                except (ValueError, TypeError) as e:
                    logger.debug(f"Error parsing price change: {e}")

        # Check for arbitrage on updated markets
        for condition_id in condition_ids_updated:
            signal = self.check_arbitrage(condition_id)
            if signal and signal.is_profitable and self.on_arb_signal:
                self.on_arb_signal(signal)

    def _on_error(self, ws, error) -> None:
        """Handle WebSocket error."""
        logger.error(f"WebSocket error: {error}")
        self.stats['errors'] += 1

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        """Handle WebSocket connection closed."""
        self._connected = False
        logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")

    def get_stats(self) -> Dict:
        """Get connection statistics."""
        return {
            **self.stats,
            'connected': self._connected,
            'subscribed_assets': len(self._subscribed_assets),
            'tracked_markets': len(self._condition_to_assets),
            'order_books': len(self._order_books),
            'reconnect_count': self._reconnect_count,
            'current_backoff_delay': self._current_backoff_delay
        }


class RealTimeArbitrageMonitor:
    """
    High-level monitor that combines REST market discovery with WebSocket order books.

    Workflow:
    1. Fetch markets from REST API
    2. Extract token IDs for YES/NO outcomes
    3. Subscribe to WebSocket for real-time order book
    4. Detect arbitrage from bid/ask spreads
    """

    def __init__(self, min_profit_pct: float = 0.01,
                 on_opportunity: Optional[Callable[[ArbitrageSignal], None]] = None,
                 signal_cooldown_seconds: float = 30.0,
                 min_price_change_pct: float = 0.01):
        """
        Initialize monitor.

        Args:
            min_profit_pct: Minimum profit percentage to trigger callback
            on_opportunity: Callback when profitable opportunity found
            signal_cooldown_seconds: Minimum seconds between signals for same market (default 30s)
            min_price_change_pct: Minimum price change % to re-signal within cooldown (default 1%)
        """
        self.min_profit_pct = min_profit_pct
        self.on_opportunity = on_opportunity
        self.signal_cooldown_seconds = signal_cooldown_seconds
        self.min_price_change_pct = min_price_change_pct

        self.ws_client = OrderBookWebSocket(
            on_book_update=self._on_book_update,
            on_arb_signal=self._on_arb_signal
        )

        self._monitored_markets: Dict[str, Dict] = {}
        self._lock = threading.Lock()

        # Opportunity log
        self._opportunities: List[ArbitrageSignal] = []
        self._max_opportunities = 1000

        # Deduplication tracking
        self._last_signal_time: Dict[str, datetime] = {}  # condition_id -> last_signal_time
        self._last_signal_prices: Dict[str, tuple] = {}  # condition_id -> (yes_ask, no_ask, total_cost)
        self._signal_count: Dict[str, int] = defaultdict(int)  # Track how many times signaled

    def add_markets_from_api(self, markets: List[Dict]) -> int:
        """
        Add markets from Polymarket API response.

        Args:
            markets: List of market dicts from API

        Returns:
            Number of markets added
        """
        added = 0

        for market in markets:
            try:
                condition_id = market.get('conditionId')
                if not condition_id:
                    continue

                # Get token IDs
                # clobTokenIds format: "[\"yes_id\", \"no_id\"]" or list
                clob_tokens = market.get('clobTokenIds', '[]')
                if isinstance(clob_tokens, str):
                    clob_tokens = json.loads(clob_tokens)

                if len(clob_tokens) != 2:
                    continue

                yes_id, no_id = clob_tokens[0], clob_tokens[1]
                question = market.get('question', '')

                self.ws_client.add_market(condition_id, yes_id, no_id, question)

                with self._lock:
                    self._monitored_markets[condition_id] = {
                        'question': question,
                        'yes_id': yes_id,
                        'no_id': no_id,
                        'volume': float(market.get('volume', 0) or 0)
                    }

                added += 1

            except Exception as e:
                logger.debug(f"Error adding market: {e}")
                continue

        logger.info(f"Added {added} markets for real-time monitoring")
        return added

    def start(self) -> None:
        """Start WebSocket monitoring."""
        self.ws_client.start()

    def stop(self) -> None:
        """Stop WebSocket monitoring."""
        self.ws_client.stop()

    def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """Wait for WebSocket to connect."""
        return self.ws_client.wait_for_connection(timeout)

    def get_opportunities(self) -> List[ArbitrageSignal]:
        """Get logged opportunities."""
        with self._lock:
            return list(self._opportunities)

    def scan_all(self) -> List[ArbitrageSignal]:
        """Manually scan all markets for arbitrage."""
        return self.ws_client.check_all_arbitrage()

    def get_order_book_summary(self, condition_id: str) -> Optional[Dict]:
        """Get order book summary for a market."""
        with self._lock:
            market = self._monitored_markets.get(condition_id)
            if not market:
                return None

        yes_book = self.ws_client.get_order_book(market['yes_id'])
        no_book = self.ws_client.get_order_book(market['no_id'])

        if not yes_book or not no_book:
            return None

        return {
            'condition_id': condition_id,
            'question': market['question'],
            'yes': yes_book.to_dict(),
            'no': no_book.to_dict(),
            'total_cost_buy_both': (yes_book.best_ask or 0) + (no_book.best_ask or 0),
            'total_value_sell_both': (yes_book.best_bid or 0) + (no_book.best_bid or 0)
        }

    def _on_book_update(self, book: OrderBook) -> None:
        """Handle order book update."""
        pass  # Could add logging here

    def _on_arb_signal(self, signal: ArbitrageSignal) -> None:
        """Handle arbitrage signal with deduplication."""
        # Check profitability threshold
        if signal.profit_if_buy_both < self.min_profit_pct and \
           signal.profit_if_sell_both < self.min_profit_pct:
            return

        # DEDUPLICATION: Check if we recently signaled this market
        condition_id = signal.condition_id
        now = datetime.now()
        should_signal = False

        with self._lock:
            last_time = self._last_signal_time.get(condition_id)
            last_prices = self._last_signal_prices.get(condition_id)

            if last_time is None:
                # First time seeing this opportunity
                should_signal = True
                logger.debug(f"New arbitrage opportunity: {condition_id[:16]}...")
            else:
                # Check cooldown
                time_since_last = (now - last_time).total_seconds()

                if time_since_last >= self.signal_cooldown_seconds:
                    # Cooldown expired, can signal again
                    should_signal = True
                    logger.debug(f"Cooldown expired for {condition_id[:16]}... (last signal {time_since_last:.0f}s ago)")
                elif last_prices:
                    # Within cooldown, check if prices changed significantly
                    old_yes, old_no, old_total = last_prices

                    # Calculate price change percentage
                    yes_change_pct = abs(signal.yes_best_ask - old_yes) / old_yes if old_yes > 0 else 0
                    no_change_pct = abs(signal.no_best_ask - old_no) / old_no if old_no > 0 else 0
                    total_change_pct = abs(signal.total_cost_to_buy - old_total) / old_total if old_total > 0 else 0

                    max_change_pct = max(yes_change_pct, no_change_pct, total_change_pct)

                    if max_change_pct >= self.min_price_change_pct:
                        # Significant price change, signal again
                        should_signal = True
                        logger.debug(f"Significant price change for {condition_id[:16]}... ({max_change_pct:.1%})")
                    else:
                        # Skip duplicate - same prices within cooldown
                        logger.debug(f"Skipping duplicate signal for {condition_id[:16]}... (change: {max_change_pct:.2%}, cooldown: {time_since_last:.0f}s)")

            # Update tracking if we're going to signal
            if should_signal:
                self._last_signal_time[condition_id] = now
                self._last_signal_prices[condition_id] = (
                    signal.yes_best_ask,
                    signal.no_best_ask,
                    signal.total_cost_to_buy
                )
                self._signal_count[condition_id] += 1

                # Store opportunity
                self._opportunities.append(signal)
                if len(self._opportunities) > self._max_opportunities:
                    self._opportunities = self._opportunities[-self._max_opportunities:]

        # Fire callback and log (outside lock to avoid blocking)
        if should_signal:
            if self.on_opportunity:
                self.on_opportunity(signal)

            count = self._signal_count[condition_id]
            logger.info(f"ARBITRAGE OPPORTUNITY #{count}: {signal.market_question[:40]}...")
            logger.info(f"  YES: bid={signal.yes_best_bid:.3f}, ask={signal.yes_best_ask:.3f}")
            logger.info(f"  NO:  bid={signal.no_best_bid:.3f}, ask={signal.no_best_ask:.3f}")
            logger.info(f"  Buy both cost: ${signal.total_cost_to_buy:.3f} -> Profit: ${signal.profit_if_buy_both:.3f}")

    def get_stats(self) -> Dict:
        """Get monitoring statistics."""
        with self._lock:
            unique_opportunities = len(self._last_signal_time)
            total_signals = sum(self._signal_count.values())

        return {
            **self.ws_client.get_stats(),
            'monitored_markets': len(self._monitored_markets),
            'opportunities_found': len(self._opportunities),
            'unique_opportunities': unique_opportunities,
            'total_signals': total_signals,
            'avg_signals_per_opportunity': total_signals / unique_opportunities if unique_opportunities > 0 else 0
        }


# Test/demo code
if __name__ == '__main__':
    import sys
    sys.path.insert(0, '.')
    from polymarket_client import PolymarketClient

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    def on_opportunity(signal: ArbitrageSignal):
        """Callback for arbitrage opportunities."""
        print(f"\n{'='*60}")
        print(f"ARBITRAGE DETECTED!")
        print(f"Market: {signal.market_question[:50]}...")
        print(f"YES: bid=${signal.yes_best_bid:.3f}, ask=${signal.yes_best_ask:.3f}")
        print(f"NO:  bid=${signal.no_best_bid:.3f}, ask=${signal.no_best_ask:.3f}")
        print(f"Cost to buy both: ${signal.total_cost_to_buy:.3f}")
        print(f"Profit if buy both: ${signal.profit_if_buy_both:.4f} ({signal.profit_if_buy_both*100:.2f}%)")
        print(f"{'='*60}\n")

    # Fetch markets
    print("Fetching markets from API...")
    client = PolymarketClient()
    markets = client.get_markets(limit=100, active=True)
    print(f"Found {len(markets)} markets")

    # Start real-time monitor
    print("\nStarting real-time arbitrage monitor...")
    monitor = RealTimeArbitrageMonitor(
        min_profit_pct=0.005,  # 0.5% minimum
        on_opportunity=on_opportunity
    )

    added = monitor.add_markets_from_api(markets)
    print(f"Added {added} markets for monitoring")

    monitor.start()

    if not monitor.wait_for_connection(timeout=15):
        print("Failed to connect to WebSocket")
        sys.exit(1)

    print("Connected! Monitoring for arbitrage opportunities...")
    print("Press Ctrl+C to stop\n")

    try:
        # Run for a while, periodically print stats
        while True:
            time.sleep(30)
            stats = monitor.get_stats()
            print(f"\nStats: {stats['messages_received']} msgs, "
                  f"{stats['book_updates']} book updates, "
                  f"{stats['opportunities_found']} opportunities")

            # Do a manual scan
            signals = monitor.scan_all()
            if signals:
                print(f"Manual scan found {len(signals)} opportunities")
            else:
                print("No arbitrage found in current order books")

    except KeyboardInterrupt:
        print("\nStopping...")
        monitor.stop()
        print("Done")
