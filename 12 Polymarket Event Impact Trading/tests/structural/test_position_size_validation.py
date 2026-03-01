"""
Structural test for RISK-013: TradeExecutor must validate position size is positive.

Verifies that execute_trade rejects position_size <= 0.
"""

import pytest
from pathlib import Path


class TestPositionSizeValidation:
    """Verify TradeExecutor validates position size."""

    TRADE_EXECUTOR_PATH = Path("src/core/trade_executor.py")

    def test_validate_position_size_method_exists(self):
        """_validate_position_size method must exist."""
        source = self.TRADE_EXECUTOR_PATH.read_text()
        assert '_validate_position_size' in source, (
            "TradeExecutor must have _validate_position_size method"
        )

    def test_execute_trade_calls_size_validation(self):
        """execute_trade must call _validate_position_size."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        # Find execute_trade method body
        et_start = source.find('def execute_trade')
        et_end = source.find('\n    def ', et_start + 1)
        et_body = source[et_start:et_end] if et_end > 0 else source[et_start:]

        assert '_validate_position_size' in et_body, (
            "execute_trade must call _validate_position_size"
        )

    def test_rejects_zero_size(self):
        """Functional test: position_size of 0 must be rejected."""
        from unittest.mock import Mock
        from src.core.trade_executor import TradeExecutor, TradeRequest

        executor = TradeExecutor(
            client=Mock(),
            position_manager=Mock(),
            config={'slippage_estimation': {'enabled': False}},
            paper_trading=True
        )

        request = TradeRequest(
            market_id='test', token_id='test', outcome='YES',
            entry_price=0.50, position_size=0.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'size'

    def test_rejects_negative_size(self):
        """Functional test: negative position_size must be rejected."""
        from unittest.mock import Mock
        from src.core.trade_executor import TradeExecutor, TradeRequest

        executor = TradeExecutor(
            client=Mock(),
            position_manager=Mock(),
            config={'slippage_estimation': {'enabled': False}},
            paper_trading=True
        )

        request = TradeRequest(
            market_id='test', token_id='test', outcome='YES',
            entry_price=0.50, position_size=-10.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'size'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
