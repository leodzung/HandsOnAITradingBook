"""
Orderbook Manager - Unified interface for WebSocket and REST orderbook data.

Provides a single interface that can switch between:
- WebSocket: Real-time orderbook data (accurate, complex)
- REST/Synthetic: Simulated orderbook from /price endpoint (simple, reliable)
"""

import logging
import threading
from typing import Dict, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from utils.orderbook_websocket import OrderBookWebSocket, OrderBook, WEBSOCKET_AVAILABLE
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("WebSocket not available - install websocket-client")


class OrderbookManager:
    """
    Manages orderbook data from either WebSocket or REST sources.

    Usage:
        manager = OrderbookManager(client, source='websocket')
        manager.start()

        # Get orderbook (automatically from correct source)
        orderbook = manager.get_orderbook(token_id)

        manager.stop()
    """

    def __init__(self, client, source: str = 'websocket', config: Optional[Dict] = None):
        """
        Initialize orderbook manager.

        Args:
            client: PolymarketClient instance
            source: 'websocket' for real-time, 'rest' for synthetic
            config: Optional configuration dict
        """
        self.client = client
        self.source = source.lower()
        self.config = config or {}

        # WebSocket state
        self._ws_client: Optional[OrderBookWebSocket] = None
        self._ws_running = False
        self._ws_lock = threading.Lock()  # Protects _ws_client and _ws_running
        self._token_to_condition: Dict[str, str] = {}  # token_id -> condition_id
        self._condition_to_tokens: Dict[str, Dict[str, str]] = {}  # condition_id -> {yes, no}

        # Cache for REST mode
        self._rest_cache: Dict[str, Dict] = {}  # token_id -> orderbook dict
        self._cache_ttl = self.config.get('cache_ttl_seconds', 5)
        self._cache_max_size = self.config.get('cache_max_size', 500)
        self._cache_lock = threading.Lock()

        # Validate source
        if self.source == 'websocket' and not WEBSOCKET_AVAILABLE:
            logger.warning("WebSocket not available, falling back to REST")
            self.source = 'rest'

        logger.info(f"OrderbookManager initialized: source={self.source}")

    def start(self) -> bool:
        """Start the orderbook manager."""
        if self.source == 'websocket':
            return self._start_websocket()
        else:
            logger.info("REST mode - no startup needed")
            return True

    def stop(self):
        """Stop the orderbook manager."""
        with self._ws_lock:
            if self.source == 'websocket' and self._ws_client:
                self._stop_websocket()

    def register_market(self, condition_id: str, yes_token_id: str, no_token_id: str,
                       question: str = ""):
        """
        Register a market for tracking.

        Args:
            condition_id: Market condition ID
            yes_token_id: YES token ID
            no_token_id: NO token ID
            question: Market question (for logging)
        """
        with self._cache_lock:
            self._token_to_condition[yes_token_id] = condition_id
            self._token_to_condition[no_token_id] = condition_id
            self._condition_to_tokens[condition_id] = {
                'yes': yes_token_id,
                'no': no_token_id
            }

        # Subscribe via WebSocket if running (hold ws_lock for atomic check-and-use)
        with self._ws_lock:
            if self.source == 'websocket' and self._ws_client:
                self._ws_client.add_market(condition_id, yes_token_id, no_token_id, question)
                logger.debug(f"Registered market via WebSocket: {question[:50]}")

    def get_orderbook(self, token_id: str) -> Dict:
        """
        Get orderbook for a token.

        Args:
            token_id: Token ID

        Returns:
            Dict with 'bids' and 'asks' arrays in standard format
        """
        if self.source == 'websocket':
            return self._get_websocket_orderbook(token_id)
        else:
            return self._get_rest_orderbook(token_id)

    def _start_websocket(self) -> bool:
        """Start WebSocket client."""
        try:
            ws_client = OrderBookWebSocket()
            ws_client.start()

            # Wait for connection instead of hardcoded sleep
            connected = ws_client.wait_for_connection(timeout=10)

            with self._ws_lock:
                self._ws_client = ws_client
                self._ws_running = connected

            if connected:
                logger.info("WebSocket orderbook manager started")
            else:
                logger.warning("WebSocket started but not yet connected")
            return True

        except Exception as e:
            logger.error(f"Failed to start WebSocket: {e}")
            return False

    def _stop_websocket(self):
        """Stop WebSocket client. Caller must hold _ws_lock."""
        if self._ws_client:
            self._ws_client.stop()
            self._ws_client = None
            self._ws_running = False
            logger.info("WebSocket orderbook manager stopped")

    def _get_websocket_orderbook(self, token_id: str) -> Dict:
        """Get orderbook from WebSocket."""
        with self._ws_lock:
            ws_client = self._ws_client
        if not ws_client:
            logger.warning("WebSocket not running, falling back to REST")
            return self._get_rest_orderbook(token_id)

        try:
            # Get orderbook from WebSocket cache
            ws_book = ws_client.get_order_book(token_id)

            if not ws_book:
                logger.debug(f"No WebSocket data for {token_id}, using REST")
                return self._get_rest_orderbook(token_id)

            # Convert WebSocket OrderBook to standard dict format
            return self._convert_ws_orderbook(ws_book)

        except Exception as e:
            logger.error(f"WebSocket orderbook error: {e}")
            return self._get_rest_orderbook(token_id)

    def _get_rest_orderbook(self, token_id: str) -> Dict:
        """Get synthetic orderbook from REST /price endpoint."""
        # Check cache first
        with self._cache_lock:
            if token_id in self._rest_cache:
                cached = self._rest_cache[token_id]
                age = (datetime.now() - cached['timestamp']).total_seconds()
                if age < self._cache_ttl:
                    return cached['orderbook']

        # Generate synthetic orderbook
        orderbook = self.client.get_synthetic_orderbook(token_id)

        # Cache it (with size limit to prevent unbounded growth)
        with self._cache_lock:
            self._rest_cache[token_id] = {
                'orderbook': orderbook,
                'timestamp': datetime.now()
            }
            # Evict oldest entries if cache exceeds max size
            if len(self._rest_cache) > self._cache_max_size:
                oldest_key = min(
                    self._rest_cache,
                    key=lambda k: self._rest_cache[k]['timestamp']
                )
                del self._rest_cache[oldest_key]

        return orderbook

    def _convert_ws_orderbook(self, ws_book: 'OrderBook') -> Dict:
        """
        Convert WebSocket OrderBook to standard dict format.

        Args:
            ws_book: OrderBook from WebSocket

        Returns:
            Dict with 'bids' and 'asks' in standard format
        """
        return {
            'bids': [[level.price, level.size] for level in ws_book.bids],
            'asks': [[level.price, level.size] for level in ws_book.asks],
            'asset_id': ws_book.asset_id,
            'timestamp': ws_book.last_update.isoformat(),
            'last_trade_price': ws_book.last_trade_price
        }

    def get_stats(self) -> Dict:
        """Get statistics about orderbook manager."""
        with self._ws_lock:
            ws_running = self._ws_running
            ws_client = self._ws_client

        stats = {
            'source': self.source,
            'running': ws_running if self.source == 'websocket' else True
        }

        if self.source == 'websocket' and ws_client:
            stats.update(ws_client.stats)
        else:
            with self._cache_lock:
                stats['cached_tokens'] = len(self._rest_cache)

        return stats
