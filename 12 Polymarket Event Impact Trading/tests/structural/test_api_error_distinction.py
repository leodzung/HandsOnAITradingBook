"""
Structural test for RISK-014: API errors must use distinct rejection_stage.

Verifies that when orderbook/market API calls fail, TradeExecutor uses
rejection_stage='api_error' instead of 'slippage'.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime, timezone


class TestApiErrorDistinction:
    """Verify API failures use 'api_error' rejection_stage."""

    TRADE_EXECUTOR_PATH = Path("src/core/trade_executor.py")

    def test_source_uses_api_error_stage(self):
        """TradeExecutor source must contain 'api_error' rejection_stage."""
        source = self.TRADE_EXECUTOR_PATH.read_text()
        assert "'api_error'" in source, (
            "TradeExecutor must use 'api_error' rejection_stage for API failures"
        )

    def test_execute_trade_api_error_on_orderbook_failure(self):
        """execute_trade must return api_error when orderbook fetch fails."""
        from src.core.trade_executor import TradeExecutor, TradeRequest

        client = Mock()
        client.get_orderbook.return_value = None  # API failure

        executor = TradeExecutor(
            client=client,
            position_manager=Mock(),
            config={'slippage_estimation': {'enabled': True}},
            paper_trading=True
        )

        request = TradeRequest(
            market_id='test', token_id='test', outcome='YES',
            entry_price=0.50, position_size=50.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'api_error', (
            f"Expected 'api_error' but got '{result.rejection_stage}'"
        )

    def test_execute_close_trade_api_error_on_orderbook_failure(self):
        """execute_close_trade must return api_error when orderbook fetch fails (non-forced exits)."""
        from src.core.trade_executor import TradeExecutor

        client = Mock()
        client.get_orderbook.return_value = None  # API failure

        executor = TradeExecutor(
            client=client,
            position_manager=Mock(),
            config={'slippage_estimation': {'enabled': True}},
            paper_trading=True
        )

        # Use a non-forced exit reason ('signal_reversal' is not in FORCED_EXIT_REASONS,
        # so slippage validation runs and the orderbook failure is caught as api_error.
        # Note: stop_loss/take_profit/expiry are in FORCED_EXIT_REASONS and intentionally
        # bypass slippage to ensure they always execute.
        result = executor.execute_close_trade(
            market_id='test', outcome='YES', token_id='test',
            exit_price=0.50, position_size=50.0,
            exit_reason='signal_reversal', question='Test'
        )

        assert not result.success
        assert result.rejection_stage == 'api_error', (
            f"Expected 'api_error' but got '{result.rejection_stage}'"
        )

    def test_slippage_rejection_still_uses_slippage_stage(self):
        """Legitimate slippage rejections must still use 'slippage' stage."""
        from src.core.trade_executor import TradeExecutor, TradeRequest

        client = Mock()
        # Return orderbook with no liquidity (legitimate rejection)
        client.get_orderbook.return_value = {
            'bids': [],
            'asks': [],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        client.get_market.return_value = {'volume_24h': 10000}

        executor = TradeExecutor(
            client=client,
            position_manager=Mock(),
            config={'slippage_estimation': {'enabled': True}},
            paper_trading=True
        )

        request = TradeRequest(
            market_id='test', token_id='test', outcome='YES',
            entry_price=0.50, position_size=50.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'slippage', (
            f"Legitimate rejection should use 'slippage', got '{result.rejection_stage}'"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
