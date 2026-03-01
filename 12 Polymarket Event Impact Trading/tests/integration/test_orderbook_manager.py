"""
Integration tests for ARCH-004: WebSocket orderbook with REST fallback

Validates that OrderbookManager provides unified interface for both
WebSocket (real-time) and REST (synthetic) orderbook sources.

Implementation: OrderbookManager class in src/core/orderbook_manager.py
- Primary source: WebSocket (real-time orderbook data)
- Fallback source: REST (synthetic orderbook from /price endpoint)
- Auto-fallback: If WebSocket unavailable, uses REST automatically
"""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.orderbook_manager import OrderbookManager
from src.utils.orderbook_websocket import OrderBook, OrderBookLevel


class TestOrderbookManagerExists:
    """Test that OrderbookManager exists and can be instantiated."""

    def test_orderbook_manager_class_exists(self):
        """Verify OrderbookManager class exists."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        assert manager is not None

    def test_accepts_websocket_source(self):
        """OrderbookManager should accept source='websocket'."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='websocket')
        # May fallback to rest if WebSocket not available
        assert manager.source in ['websocket', 'rest']

    def test_accepts_rest_source(self):
        """OrderbookManager should accept source='rest'."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        assert manager.source == 'rest'


class TestOrderbookManagerInterface:
    """Test OrderbookManager provides unified interface."""

    def test_has_start_method(self):
        """OrderbookManager must have start() method."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        assert hasattr(manager, 'start')
        assert callable(manager.start)

    def test_has_stop_method(self):
        """OrderbookManager must have stop() method."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        assert hasattr(manager, 'stop')
        assert callable(manager.stop)

    def test_has_register_market_method(self):
        """OrderbookManager must have register_market() method."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        assert hasattr(manager, 'register_market')
        assert callable(manager.register_market)

    def test_has_get_orderbook_method(self):
        """
        CRITICAL: OrderbookManager must have get_orderbook() method.

        This is the unified interface that abstracts WebSocket vs REST.
        """
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        assert hasattr(manager, 'get_orderbook')
        assert callable(manager.get_orderbook)

    def test_get_orderbook_signature(self):
        """get_orderbook should accept token_id parameter."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        # Should accept token_id
        orderbook = manager.get_orderbook(token_id='0xtest123')
        assert 'bids' in orderbook
        assert 'asks' in orderbook


class TestRESTMode:
    """Test REST mode (synthetic orderbook)."""

    def test_rest_mode_starts_successfully(self):
        """REST mode should start successfully (no setup needed)."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')

        result = manager.start()

        assert result is True

    def test_rest_mode_uses_synthetic_orderbook(self):
        """
        REST mode should use client.get_synthetic_orderbook().

        This validates the fallback mechanism works correctly.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000]],
            'asks': [[0.505, 5000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        orderbook = manager.get_orderbook(token_id='0xtest123')

        # Should have called get_synthetic_orderbook
        mock_client.get_synthetic_orderbook.assert_called_once_with('0xtest123')

        # Should return orderbook data
        assert orderbook['bids'] == [[0.495, 5000]]
        assert orderbook['asks'] == [[0.505, 5000]]

    def test_rest_mode_caches_orderbook(self):
        """REST mode should cache orderbook data to reduce API calls."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000]],
            'asks': [[0.505, 5000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        # First call - should hit API
        orderbook1 = manager.get_orderbook(token_id='0xtest123')

        # Second call immediately - should use cache
        orderbook2 = manager.get_orderbook(token_id='0xtest123')

        # Should only call get_synthetic_orderbook once (cached)
        assert mock_client.get_synthetic_orderbook.call_count == 1

        # Both should return same data
        assert orderbook1 == orderbook2


class TestWebSocketMode:
    """Test WebSocket mode (real-time orderbook) with mocked WebSocket."""

    def test_websocket_convert_ws_orderbook(self):
        """Test _convert_ws_orderbook converts OrderBook to dict format."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')

        ws_book = OrderBook(
            asset_id='token_123',
            condition_id='cond_456',
            bids=[
                OrderBookLevel(price=0.55, size=100),
                OrderBookLevel(price=0.54, size=200),
            ],
            asks=[
                OrderBookLevel(price=0.56, size=150),
                OrderBookLevel(price=0.57, size=250),
            ],
            last_update=datetime(2026, 1, 1, 12, 0, 0),
            last_trade_price=0.555,
        )

        result = manager._convert_ws_orderbook(ws_book)

        assert result['bids'] == [[0.55, 100], [0.54, 200]]
        assert result['asks'] == [[0.56, 150], [0.57, 250]]
        assert result['asset_id'] == 'token_123'
        assert result['last_trade_price'] == 0.555
        assert '2026-01-01' in result['timestamp']

    def test_websocket_register_market_calls_ws_client(self):
        """register_market should call add_market on the WebSocket client."""
        mock_client = Mock()

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', True):
            with patch('src.core.orderbook_manager.OrderBookWebSocket', create=True) as MockWS:
                mock_ws = MagicMock()
                mock_ws.wait_for_connection.return_value = True
                MockWS.return_value = mock_ws

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                manager.register_market('cond1', 'yes1', 'no1', 'Test Q?')

                mock_ws.add_market.assert_called_once_with('cond1', 'yes1', 'no1', 'Test Q?')

    def test_websocket_get_orderbook_returns_converted_book(self):
        """get_orderbook in websocket mode should return converted OrderBook dict."""
        mock_client = Mock()

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', True):
            with patch('src.core.orderbook_manager.OrderBookWebSocket', create=True) as MockWS:
                mock_ws = MagicMock()
                mock_ws.wait_for_connection.return_value = True

                ws_book = OrderBook(
                    asset_id='token_abc',
                    bids=[OrderBookLevel(price=0.60, size=500)],
                    asks=[OrderBookLevel(price=0.62, size=300)],
                    last_trade_price=0.61,
                )
                mock_ws.get_order_book.return_value = ws_book
                MockWS.return_value = mock_ws

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                result = manager.get_orderbook('token_abc')

                assert result['bids'] == [[0.60, 500]]
                assert result['asks'] == [[0.62, 300]]
                assert result['asset_id'] == 'token_abc'

    def test_websocket_stats_includes_ws_data(self):
        """Stats in websocket mode should include WebSocket stats."""
        mock_client = Mock()

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', True):
            with patch('src.core.orderbook_manager.OrderBookWebSocket', create=True) as MockWS:
                mock_ws = MagicMock()
                mock_ws.wait_for_connection.return_value = True
                mock_ws.stats = {'messages_received': 42, 'book_updates': 10}
                MockWS.return_value = mock_ws

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                stats = manager.get_stats()
                assert stats['source'] == 'websocket'
                assert stats['messages_received'] == 42


class TestAutoFallback:
    """
    Test automatic fallback from WebSocket to REST.

    CRITICAL: This is the core requirement of ARCH-004.
    """

    def test_fallback_when_websocket_unavailable(self):
        """
        When WebSocket not available, should auto-fallback to REST.

        This ensures reliability even without websocket-client installed.
        """
        mock_client = Mock()

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')

            # Should have fallen back to REST
            assert manager.source == 'rest'

    def test_fallback_during_get_orderbook(self):
        """
        If WebSocket fails during get_orderbook, should fallback to REST.

        This ensures continuous operation during connection issues.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000]],
            'asks': [[0.505, 5000]]
        })

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', True):
            with patch('src.utils.orderbook_websocket.OrderBookWebSocket') as MockWS:
                mock_ws_instance = MagicMock()
                MockWS.return_value = mock_ws_instance

                # WebSocket returns None (no data available)
                mock_ws_instance.get_order_book = Mock(return_value=None)

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                # Get orderbook - should fallback to REST
                orderbook = manager.get_orderbook(token_id='0xtest123')

                # Should have called REST fallback
                mock_client.get_synthetic_orderbook.assert_called_once_with('0xtest123')

                # Should return REST data
                assert orderbook['bids'] == [[0.495, 5000]]
                assert orderbook['asks'] == [[0.505, 5000]]


class TestOrderbookFormat:
    """Test that orderbook format is consistent."""

    def test_orderbook_has_bids_and_asks(self):
        """Orderbook must have 'bids' and 'asks' arrays."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        orderbook = manager.get_orderbook(token_id='0xtest123')

        assert 'bids' in orderbook
        assert 'asks' in orderbook
        assert isinstance(orderbook['bids'], list)
        assert isinstance(orderbook['asks'], list)

    def test_orderbook_levels_are_price_size_pairs(self):
        """Each level should be [price, size] format."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000], [0.490, 3000]],
            'asks': [[0.505, 5000], [0.510, 3000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        orderbook = manager.get_orderbook(token_id='0xtest123')

        # Check bids format
        for level in orderbook['bids']:
            assert len(level) == 2  # [price, size]
            assert isinstance(level[0], (int, float))  # price
            assert isinstance(level[1], (int, float))  # size

        # Check asks format
        for level in orderbook['asks']:
            assert len(level) == 2
            assert isinstance(level[0], (int, float))
            assert isinstance(level[1], (int, float))


class TestOrderbookManagerLifecycle:
    """Test complete lifecycle: start → use → stop."""

    def test_lifecycle_rest_mode(self):
        """Test complete lifecycle in REST mode."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest')

        # Start
        result = manager.start()
        assert result is True

        # Use
        orderbook = manager.get_orderbook(token_id='0xtest123')
        assert 'bids' in orderbook

        # Stop (should not error)
        manager.stop()

    def test_lifecycle_websocket_mode_with_fallback(self):
        """Test lifecycle in WebSocket mode with fallback."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        })

        # WebSocket not available - will fallback to REST
        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')

            # Start (fallback to REST)
            result = manager.start()
            assert result is True
            assert manager.source == 'rest'

            # Use (via REST)
            orderbook = manager.get_orderbook(token_id='0xtest123')
            assert 'bids' in orderbook

            # Stop
            manager.stop()


class TestOrderbookManagerStats:
    """Test statistics and monitoring."""

    def test_get_stats_method_exists(self):
        """OrderbookManager should provide stats for monitoring."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')

        assert hasattr(manager, 'get_stats')
        assert callable(manager.get_stats)

    def test_stats_include_source(self):
        """Stats should include current source (websocket/rest)."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        stats = manager.get_stats()

        assert 'source' in stats
        assert stats['source'] == 'rest'

    def test_stats_include_running_status(self):
        """Stats should include running status."""
        mock_client = Mock()
        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        stats = manager.get_stats()

        assert 'running' in stats
        assert isinstance(stats['running'], bool)


class TestCacheExpiry:
    """Test cache TTL expiration (#23)."""

    def test_cache_expires_after_ttl(self):
        """Cache entries should expire after TTL, causing a fresh API call."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.50, 1000]],
            'asks': [[0.52, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest', config={'cache_ttl_seconds': 1})
        manager.start()

        # First call
        manager.get_orderbook(token_id='0xtest')
        assert mock_client.get_synthetic_orderbook.call_count == 1

        # Immediately again - should be cached
        manager.get_orderbook(token_id='0xtest')
        assert mock_client.get_synthetic_orderbook.call_count == 1

        # Manually expire the cache entry
        with manager._cache_lock:
            manager._rest_cache['0xtest']['timestamp'] = datetime.now() - timedelta(seconds=10)

        # Now should call API again
        manager.get_orderbook(token_id='0xtest')
        assert mock_client.get_synthetic_orderbook.call_count == 2

    def test_cache_max_size_evicts_oldest(self):
        """Cache should evict oldest entry when max size exceeded."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.50, 1000]],
            'asks': [[0.52, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest', config={
            'cache_ttl_seconds': 300,
            'cache_max_size': 3
        })
        manager.start()

        # Fill cache with 3 entries
        for i in range(3):
            manager.get_orderbook(token_id=f'token_{i}')

        with manager._cache_lock:
            assert len(manager._rest_cache) == 3

        # Add one more - should evict oldest
        manager.get_orderbook(token_id='token_3')

        with manager._cache_lock:
            assert len(manager._rest_cache) == 3
            assert 'token_3' in manager._rest_cache


class TestConcurrency:
    """Test thread safety of OrderbookManager (#22)."""

    def test_concurrent_get_orderbook(self):
        """Multiple threads calling get_orderbook simultaneously should not crash."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.50, 1000]],
            'asks': [[0.52, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        errors = []

        def worker(token_id):
            try:
                for _ in range(20):
                    result = manager.get_orderbook(token_id=token_id)
                    assert 'bids' in result
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f'token_{i}',)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Concurrent get_orderbook errors: {errors}"

    def test_concurrent_register_and_get(self):
        """Concurrent register_market + get_orderbook should not crash."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.50, 1000]],
            'asks': [[0.52, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        manager.start()

        errors = []

        def register_worker():
            try:
                for i in range(20):
                    manager.register_market(f'cond_{i}', f'yes_{i}', f'no_{i}', f'Q {i}?')
            except Exception as e:
                errors.append(e)

        def get_worker():
            try:
                for i in range(20):
                    manager.get_orderbook(token_id=f'yes_{i}')
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=register_worker)
        t2 = threading.Thread(target=get_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(errors) == 0, f"Concurrent register+get errors: {errors}"

    def test_concurrent_get_and_stop(self):
        """Concurrent get_orderbook + stop should not crash."""
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.50, 1000]],
            'asks': [[0.52, 1000]]
        })

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', True):
            with patch('src.core.orderbook_manager.OrderBookWebSocket', create=True) as MockWS:
                mock_ws = MagicMock()
                mock_ws.wait_for_connection.return_value = True
                mock_ws.get_order_book.return_value = None
                MockWS.return_value = mock_ws

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                errors = []

                def get_worker():
                    try:
                        for _ in range(20):
                            manager.get_orderbook(token_id='token_1')
                    except Exception as e:
                        errors.append(e)

                t1 = threading.Thread(target=get_worker)
                t1.start()

                # Stop while get_worker is running
                time.sleep(0.01)
                manager.stop()

                t1.join(timeout=10)

                assert len(errors) == 0, f"Concurrent get+stop errors: {errors}"
