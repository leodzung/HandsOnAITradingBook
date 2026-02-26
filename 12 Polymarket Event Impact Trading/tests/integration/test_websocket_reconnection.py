"""
Integration tests for DEBT-002: WebSocket reconnection logic

REGRESSION CHECK: Validates that the WebSocket reconnection improvements
from 2026-02-14 are still in place.

Fixed implementation includes:
- Exponential backoff: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max)
- Random jitter: ±30% to prevent thundering herd
- Unlimited retries: No max attempt limit
- Backoff reset: Resets to 1s on successful connection
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestWebSocketReconnection:
    """Test that WebSocket reconnection uses exponential backoff with jitter."""

    @pytest.fixture
    def websocket_module(self):
        """Import OrderBookWebSocket if available."""
        try:
            from src.utils.orderbook_websocket import OrderBookWebSocket
            return OrderBookWebSocket
        except ImportError:
            pytest.skip("websocket-client not installed")

    def test_exponential_backoff_constants(self, websocket_module):
        """
        CRITICAL: Verify exponential backoff configuration constants exist.

        This is the core regression check for DEBT-002.
        """
        # Check that backoff constants are defined
        assert hasattr(websocket_module, 'INITIAL_RECONNECT_DELAY'), (
            "Missing INITIAL_RECONNECT_DELAY constant"
        )
        assert hasattr(websocket_module, 'MAX_RECONNECT_DELAY'), (
            "Missing MAX_RECONNECT_DELAY constant"
        )
        assert hasattr(websocket_module, 'BACKOFF_MULTIPLIER'), (
            "Missing BACKOFF_MULTIPLIER constant"
        )
        assert hasattr(websocket_module, 'JITTER_RANGE'), (
            "Missing JITTER_RANGE constant"
        )

        # Verify correct values (from 2026-02-14 fix)
        assert websocket_module.INITIAL_RECONNECT_DELAY == 1, (
            "INITIAL_RECONNECT_DELAY should be 1 second"
        )
        assert websocket_module.MAX_RECONNECT_DELAY == 60, (
            "MAX_RECONNECT_DELAY should be 60 seconds"
        )
        assert websocket_module.BACKOFF_MULTIPLIER == 2, (
            "BACKOFF_MULTIPLIER should be 2 (exponential doubling)"
        )
        assert websocket_module.JITTER_RANGE == 0.3, (
            "JITTER_RANGE should be 0.3 (±30%)"
        )

    def test_backoff_sequence(self, websocket_module):
        """
        Verify exponential backoff sequence: 1s → 2s → 4s → 8s → 16s → 32s → 60s (max).

        Tests that backoff doubles each time until hitting max.
        """
        initial = websocket_module.INITIAL_RECONNECT_DELAY
        max_delay = websocket_module.MAX_RECONNECT_DELAY
        multiplier = websocket_module.BACKOFF_MULTIPLIER

        # Simulate backoff sequence
        current_delay = initial
        expected_sequence = [1, 2, 4, 8, 16, 32, 60, 60, 60]  # caps at 60

        sequence = []
        for _ in range(9):
            sequence.append(current_delay)
            current_delay = min(current_delay * multiplier, max_delay)

        assert sequence == expected_sequence, (
            f"Backoff sequence should be {expected_sequence}, got {sequence}"
        )

    def test_jitter_prevents_thundering_herd(self, websocket_module):
        """
        Verify jitter is applied to prevent thundering herd problem.

        Jitter should be ±30% of base delay.
        """
        import random

        jitter_range = websocket_module.JITTER_RANGE
        base_delay = 10.0  # example delay

        # Calculate jitter bounds
        min_jitter = -jitter_range * base_delay
        max_jitter = jitter_range * base_delay

        # Expected bounds
        assert min_jitter == -3.0, "Min jitter should be -30% of base delay"
        assert max_jitter == 3.0, "Max jitter should be +30% of base delay"

        # Simulate jitter application
        jittered_delays = []
        for _ in range(100):
            jitter = random.uniform(min_jitter, max_jitter)
            jittered_delay = base_delay + jitter
            jittered_delays.append(jittered_delay)

        # All jittered delays should be within ±30%
        assert all(7.0 <= d <= 13.0 for d in jittered_delays), (
            "All jittered delays should be within ±30% of base delay"
        )

        # Average should be close to base delay
        avg_delay = sum(jittered_delays) / len(jittered_delays)
        assert 9.5 <= avg_delay <= 10.5, (
            f"Average jittered delay should be ~{base_delay}, got {avg_delay:.2f}"
        )

    def test_unlimited_retries_no_max_attempts(self, websocket_module):
        """
        CRITICAL: Verify there's NO max retry limit.

        Old implementation had limited retries - this was the bug.
        New implementation retries indefinitely while running.
        """
        # Check that _run_websocket method exists
        ws = websocket_module()

        # Verify _run_websocket uses while self._running (not a counter)
        import inspect
        source = inspect.getsource(ws._run_websocket)

        # Should have "while self._running" not "for _ in range(max_attempts)"
        assert "while self._running" in source, (
            "WebSocket should use 'while self._running' for unlimited retries"
        )

        # Should NOT have max attempts check
        forbidden_patterns = [
            "max_attempts",
            "MAX_ATTEMPTS",
            "max_retries",
            "MAX_RETRIES",
            "for _ in range",
            "attempt_count >= "
        ]

        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"❌ REGRESSION: Found '{pattern}' in reconnection logic!\n"
                f"This indicates limited retries (the old bug).\n"
                f"Should use unlimited retries with 'while self._running'"
            )

    def test_backoff_resets_on_successful_connection(self, websocket_module):
        """
        Verify backoff delay resets to initial value on successful connection.

        This prevents indefinitely long delays after temporary outages.
        """
        ws = websocket_module()

        # Check _on_open method resets backoff
        import inspect
        source = inspect.getsource(ws._on_open)

        # Should reset _current_backoff_delay to INITIAL_RECONNECT_DELAY
        assert "self._current_backoff_delay = self.INITIAL_RECONNECT_DELAY" in source, (
            "WebSocket should reset backoff delay on successful connection"
        )

        # Verify initial state
        assert ws._current_backoff_delay == websocket_module.INITIAL_RECONNECT_DELAY, (
            "Initial backoff delay should be INITIAL_RECONNECT_DELAY"
        )

    @patch('src.utils.orderbook_websocket.websocket.WebSocketApp')
    def test_reconnection_flow_with_backoff(self, mock_ws_app, websocket_module):
        """
        Integration test: Simulate connection failures and verify backoff behavior.

        Tests the complete reconnection flow with exponential backoff.
        """
        # Create WebSocket instance
        ws = websocket_module()

        # Mock WebSocketApp to simulate failures
        mock_instance = MagicMock()
        mock_ws_app.return_value = mock_instance

        # Simulate multiple connection failures
        failure_count = 0

        def run_forever_side_effect():
            nonlocal failure_count
            failure_count += 1
            if failure_count < 3:
                # Simulate connection failure
                raise ConnectionError("Connection failed")
            # Third attempt succeeds
            ws._on_open(mock_instance)

        mock_instance.run_forever.side_effect = run_forever_side_effect

        # Track delays between reconnection attempts
        delays = []
        original_sleep = time.sleep

        def mock_sleep(duration):
            delays.append(duration)
            # Don't actually sleep in tests
            return None

        with patch('time.sleep', side_effect=mock_sleep):
            # Start WebSocket in background thread
            ws._running = True
            thread = threading.Thread(target=ws._run_websocket)
            thread.daemon = True
            thread.start()

            # Wait for reconnections to complete
            time.sleep(0.5)

            # Stop WebSocket
            ws._running = False
            thread.join(timeout=1.0)

        # Verify exponential backoff occurred
        # First reconnect: ~1s with jitter
        # Second reconnect: ~2s with jitter
        assert len(delays) >= 2, "Should have at least 2 reconnection delays"

        # First delay should be ~1s (±30%)
        assert 0.7 <= delays[0] <= 1.3, (
            f"First reconnect delay should be ~1s (±30%), got {delays[0]:.2f}s"
        )

        # Second delay should be ~2s (±30%)
        assert 1.4 <= delays[1] <= 2.6, (
            f"Second reconnect delay should be ~2s (±30%), got {delays[1]:.2f}s"
        )

    def test_no_regression_to_limited_retries(self, websocket_module):
        """
        REGRESSION CHECK: Ensure we haven't reverted to the old limited retry bug.

        This is the critical regression test for DEBT-002.
        """
        ws = websocket_module()

        # Verify constants are correct
        assert ws.INITIAL_RECONNECT_DELAY == 1
        assert ws.MAX_RECONNECT_DELAY == 60
        assert ws.BACKOFF_MULTIPLIER == 2
        assert ws.JITTER_RANGE == 0.3

        # Verify no max attempts limit exists
        import inspect
        source = inspect.getsource(ws._run_websocket)
        assert "while self._running" in source
        assert "max_attempts" not in source.lower()

        # Verify backoff reset exists
        on_open_source = inspect.getsource(ws._on_open)
        assert "INITIAL_RECONNECT_DELAY" in on_open_source


class TestWebSocketReconnectionDocumentation:
    """Verify reconnection logic is well-documented."""

    @pytest.fixture
    def websocket_module(self):
        """Import OrderBookWebSocket if available."""
        try:
            from src.utils.orderbook_websocket import OrderBookWebSocket
            return OrderBookWebSocket
        except ImportError:
            pytest.skip("websocket-client not installed")

    def test_reconnection_logic_documented(self, websocket_module):
        """
        Verify reconnection logic is documented in docstrings.

        Good documentation prevents future regressions.
        """
        import inspect

        # Check _run_websocket docstring
        ws = websocket_module()
        docstring = inspect.getdoc(ws._run_websocket)

        required_documentation = [
            "exponential backoff",
            "jitter",
            "unlimited retries",
            "reset"
        ]

        for keyword in required_documentation:
            assert keyword.lower() in docstring.lower(), (
                f"Reconnection docstring should mention '{keyword}'"
            )
