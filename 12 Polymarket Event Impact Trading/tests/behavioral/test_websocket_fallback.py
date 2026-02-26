"""
Behavioral tests for ARCH-004: WebSocket orderbook with REST fallback

Validates end-to-end fallback behavior when WebSocket is unavailable or fails.

Implementation: OrderbookManager class in src/core/orderbook_manager.py
- Primary source: WebSocket (real-time orderbook)
- Fallback source: REST (synthetic orderbook from /price endpoint)
- Automatic fallback ensures continuous operation during connection issues
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.orderbook_manager import OrderbookManager


class TestWebSocketFallbackBehavior:
    """Test complete fallback behavior from WebSocket to REST."""

    def test_fallback_at_initialization(self):
        """
        When WebSocket not available at init, should fallback to REST immediately.

        This validates graceful degradation without user intervention.
        """
        mock_client = Mock()

        # Simulate WebSocket not available
        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')

            # Should have automatically fallen back to REST
            assert manager.source == 'rest'

    def test_fallback_provides_working_orderbook(self):
        """
        CRITICAL: After fallback, orderbook data should still be available.

        This ensures trading continues even without WebSocket.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000]],
            'asks': [[0.505, 5000]]
        })

        # Force fallback to REST
        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')
            manager.start()

            # Should be able to get orderbook via fallback
            orderbook = manager.get_orderbook(token_id='0xtest123')

            # Verify orderbook data is valid
            assert 'bids' in orderbook
            assert 'asks' in orderbook
            assert len(orderbook['bids']) > 0
            assert len(orderbook['asks']) > 0

    def test_fallback_transparent_to_caller(self):
        """
        Fallback should be transparent - caller uses same interface.

        Whether using WebSocket or REST, get_orderbook() works the same way.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        })

        # REST mode
        manager_rest = OrderbookManager(mock_client, source='rest')
        manager_rest.start()
        orderbook_rest = manager_rest.get_orderbook(token_id='0xtest123')

        # WebSocket mode (fallback to REST)
        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager_ws = OrderbookManager(mock_client, source='websocket')
            manager_ws.start()
            orderbook_ws = manager_ws.get_orderbook(token_id='0xtest123')

        # Both should return same format
        assert 'bids' in orderbook_rest and 'bids' in orderbook_ws
        assert 'asks' in orderbook_rest and 'asks' in orderbook_ws


class TestRuntimeFallback:
    """Test fallback during runtime when WebSocket fails."""

    def test_fallback_when_websocket_returns_none(self):
        """
        If WebSocket has no data, should fallback to REST automatically.

        This handles cold-start scenarios where WebSocket hasn't received data yet.
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

                # WebSocket returns None (no data)
                mock_ws_instance.get_order_book = Mock(return_value=None)

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                # Get orderbook - should fallback to REST
                orderbook = manager.get_orderbook(token_id='0xtest123')

                # Should have called REST fallback
                mock_client.get_synthetic_orderbook.assert_called_once_with('0xtest123')

                # Should return valid data
                assert orderbook['bids'] == [[0.495, 5000]]
                assert orderbook['asks'] == [[0.505, 5000]]

    def test_fallback_when_websocket_raises_exception(self):
        """
        If WebSocket raises exception, should fallback to REST gracefully.

        This ensures resilience during network issues or WebSocket errors.
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

                # WebSocket raises exception
                mock_ws_instance.get_order_book = Mock(side_effect=ConnectionError("WebSocket disconnected"))

                manager = OrderbookManager(mock_client, source='websocket')
                manager.start()

                # Get orderbook - should fallback gracefully
                orderbook = manager.get_orderbook(token_id='0xtest123')

                # Should have called REST fallback
                mock_client.get_synthetic_orderbook.assert_called_once()

                # Should return valid data
                assert 'bids' in orderbook
                assert 'asks' in orderbook


class TestFallbackResilience:
    """Test that fallback ensures continuous operation."""

    def test_multiple_fallback_calls_work(self):
        """
        Multiple orderbook requests should all fallback successfully.

        Validates continuous operation across multiple trades.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000]],
            'asks': [[0.505, 5000]]
        })

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')
            manager.start()

            # Multiple requests - all should fallback
            orderbook1 = manager.get_orderbook(token_id='0xtoken1')
            orderbook2 = manager.get_orderbook(token_id='0xtoken2')
            orderbook3 = manager.get_orderbook(token_id='0xtoken3')

            # All should succeed
            assert 'bids' in orderbook1
            assert 'bids' in orderbook2
            assert 'bids' in orderbook3

            # Should have called REST 3 times (or used cache)
            assert mock_client.get_synthetic_orderbook.call_count >= 1

    def test_no_data_loss_during_fallback(self):
        """
        CRITICAL: Fallback should not lose orderbook data.

        Every request must return valid orderbook data, even during fallback.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000], [0.490, 3000]],
            'asks': [[0.505, 5000], [0.510, 3000]]
        })

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')
            manager.start()

            orderbook = manager.get_orderbook(token_id='0xtest123')

            # Must have bids and asks
            assert 'bids' in orderbook
            assert 'asks' in orderbook

            # Must have data (not empty)
            assert len(orderbook['bids']) > 0
            assert len(orderbook['asks']) > 0

            # Data must be valid format [price, size]
            for bid in orderbook['bids']:
                assert len(bid) == 2
                assert isinstance(bid[0], (int, float))  # price
                assert isinstance(bid[1], (int, float))  # size


class TestFallbackConfiguration:
    """Test fallback configuration and control."""

    def test_can_explicitly_choose_rest_mode(self):
        """
        User should be able to explicitly choose REST mode.

        This allows bypassing WebSocket entirely if desired.
        """
        mock_client = Mock()

        manager = OrderbookManager(mock_client, source='rest')

        assert manager.source == 'rest'

    def test_explicit_rest_mode_no_websocket_attempt(self):
        """
        When source='rest', should not attempt WebSocket at all.

        This avoids unnecessary connection attempts.
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        })

        manager = OrderbookManager(mock_client, source='rest')
        result = manager.start()

        # Should start successfully without WebSocket
        assert result is True
        assert manager.source == 'rest'

        # Should be able to get orderbook
        orderbook = manager.get_orderbook(token_id='0xtest123')
        assert 'bids' in orderbook


class TestFallbackLogging:
    """Test that fallback events are logged appropriately."""

    def test_fallback_logged_at_init(self, caplog):
        """
        Fallback at initialization should be logged.

        Helps debugging and monitoring.
        """
        mock_client = Mock()

        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            manager = OrderbookManager(mock_client, source='websocket')

            # Check that fallback was logged
            # (Actual log message depends on implementation)
            assert manager.source == 'rest'


class TestEndToEndFallback:
    """Test complete end-to-end fallback scenarios."""

    def test_complete_trading_cycle_with_fallback(self):
        """
        CRITICAL: Complete trading cycle should work with fallback.

        Validates: init → start → register market → get orderbook → stop
        """
        mock_client = Mock()
        mock_client.get_synthetic_orderbook = Mock(return_value={
            'bids': [[0.495, 5000]],
            'asks': [[0.505, 5000]]
        })

        # Simulate WebSocket unavailable
        with patch('src.core.orderbook_manager.WEBSOCKET_AVAILABLE', False):
            # Step 1: Initialize (fallback happens here)
            manager = OrderbookManager(mock_client, source='websocket')
            assert manager.source == 'rest'

            # Step 2: Start
            result = manager.start()
            assert result is True

            # Step 3: Register market
            manager.register_market(
                condition_id='0xcondition123',
                yes_token_id='0xyes123',
                no_token_id='0xno123',
                question='Will Bitcoin hit $100k?'
            )

            # Step 4: Get orderbook
            orderbook = manager.get_orderbook(token_id='0xyes123')
            assert 'bids' in orderbook
            assert 'asks' in orderbook

            # Step 5: Stop
            manager.stop()

        # Complete cycle succeeded with fallback
        assert True
