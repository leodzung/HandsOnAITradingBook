"""
Orderbook Service Client

Client library for bots to connect to the centralized Orderbook Microservice.
Replaces direct WebSocket/OrderbookManager usage.

Usage:
    from services.orderbook_client import OrderbookServiceClient

    # Create client
    orderbook_client = OrderbookServiceClient()

    # Get orderbook
    orderbook = orderbook_client.get_orderbook(token_id)
"""

import logging
import requests
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OrderbookServiceClient:
    """
    Client for connecting to the Orderbook Microservice.

    Provides a simple interface for bots to fetch orderbook data
    from the centralized service instead of managing WebSocket themselves.
    """

    def __init__(self, service_url: str = "http://localhost:8765", cache_ttl_seconds: int = 5):
        """
        Initialize orderbook service client.

        Args:
            service_url: URL of the orderbook microservice
            cache_ttl_seconds: Cache TTL for local caching (optional)
        """
        self.service_url = service_url.rstrip('/')
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: Dict[str, Dict] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

        logger.info(f"OrderbookServiceClient initialized (service={service_url})")

    def get_orderbook(self, token_id: str) -> Dict:
        """
        Get orderbook for a token from the microservice.

        Args:
            token_id: Token ID

        Returns:
            Dict with 'bids' and 'asks' lists

        Example:
            >>> client = OrderbookServiceClient()
            >>> orderbook = client.get_orderbook("80986750124...")
            >>> print(orderbook['bids'][0])  # Best bid
        """
        # Check cache first
        if token_id in self._cache:
            age = datetime.now() - self._cache_timestamps[token_id]
            if age < self.cache_ttl:
                return self._cache[token_id]

        # Fetch from microservice
        try:
            response = requests.get(
                f"{self.service_url}/orderbook/{token_id}",
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                # Extract orderbook (API returns OrderbookResponse model)
                orderbook = {
                    'bids': data.get('bids', []),
                    'asks': data.get('asks', [])
                }

                # Update cache
                self._cache[token_id] = orderbook
                self._cache_timestamps[token_id] = datetime.now()

                return orderbook

            elif response.status_code == 404:
                logger.warning(f"Orderbook not available for {token_id[:16]}...")
                return {'bids': [], 'asks': []}

            else:
                logger.error(f"Orderbook service error: {response.status_code} - {response.text}")
                return {'bids': [], 'asks': []}

        except requests.exceptions.ConnectionError:
            logger.error(
                f"Cannot connect to orderbook service at {self.service_url}. "
                f"Is the service running? Start with: python3 src/services/orderbook_service.py"
            )
            return {'bids': [], 'asks': []}

        except Exception as e:
            logger.error(f"Error fetching orderbook from service: {e}")
            return {'bids': [], 'asks': []}

    def subscribe_market(self, condition_id: str, question: str = "") -> bool:
        """
        Subscribe a market for orderbook tracking.

        Args:
            condition_id: Market condition ID
            question: Optional market question

        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.service_url}/subscribe/{condition_id}",
                params={'question': question},
                timeout=5
            )

            if response.status_code == 200:
                logger.debug(f"Subscribed to market {condition_id[:16]}...")
                return True
            else:
                logger.warning(f"Failed to subscribe: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Error subscribing to market: {e}")
            return False

    def health_check(self) -> Dict:
        """
        Check service health and WebSocket status.

        Returns:
            Dict with status, websocket_connected, uptime_seconds
        """
        try:
            response = requests.get(f"{self.service_url}/health", timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                return {'status': 'error', 'error': response.text}

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'status': 'unreachable', 'error': str(e)}

    def get_stats(self) -> Dict:
        """
        Get orderbook manager statistics from service.

        Returns:
            Dict with stats (messages_received, reconnects, etc.)
        """
        try:
            response = requests.get(f"{self.service_url}/stats", timeout=5)

            if response.status_code == 200:
                return response.json()
            else:
                return {}

        except Exception as e:
            logger.error(f"Failed to fetch stats: {e}")
            return {}
