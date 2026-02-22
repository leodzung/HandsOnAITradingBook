"""
Shared Orderbook Manager Singleton

Provides a single WebSocket connection shared across all bots.
Solves the issue of multiple competing WebSocket connections.
"""

import logging
import threading
from typing import Optional, Dict
from core.orderbook_manager import OrderbookManager

logger = logging.getLogger(__name__)


class SharedOrderbookManager:
    """
    Singleton wrapper for OrderbookManager.

    Ensures only ONE WebSocket connection is created,
    shared across all bots/clients.
    """

    _instance: Optional[OrderbookManager] = None
    _lock = threading.Lock()
    _initialized = False

    @classmethod
    def get_instance(cls, client=None, source: str = 'websocket', config: Optional[Dict] = None) -> OrderbookManager:
        """
        Get or create the singleton OrderbookManager instance.

        Args:
            client: PolymarketClient (only needed for first initialization)
            source: 'websocket' or 'rest'
            config: Optional configuration dict

        Returns:
            Shared OrderbookManager instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if client is None:
                        raise ValueError("Client required for first initialization")

                    logger.info(f"Creating shared OrderbookManager (source={source})")
                    cls._instance = OrderbookManager(client, source=source, config=config)
                    cls._instance.start()
                    cls._initialized = True
                    logger.info("✓ Shared OrderbookManager created - all bots will use this connection")

        return cls._instance

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if singleton is already initialized."""
        return cls._initialized

    @classmethod
    def reset(cls):
        """Reset singleton (for testing only)."""
        with cls._lock:
            if cls._instance:
                cls._instance.stop()
            cls._instance = None
            cls._initialized = False
