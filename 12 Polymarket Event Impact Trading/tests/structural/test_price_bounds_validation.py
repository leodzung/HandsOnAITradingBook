"""
Structural test for RISK-012: TradeExecutor price validation must check both bounds.

Verifies that _validate_price checks:
1. entry_price <= 0 (lower bound)
2. entry_price >= 1.0 (upper bound for prediction markets)
3. entry_price > max_entry_price (configurable upper limit)
"""

import pytest
from pathlib import Path


class TestPriceBoundsValidation:
    """Verify _validate_price checks both lower and upper bounds."""

    TRADE_EXECUTOR_PATH = Path("src/core/trade_executor.py")

    def test_validate_price_checks_lower_bound(self):
        """_validate_price must reject entry_price <= 0."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        # Must check for price <= 0
        assert 'entry_price <= 0' in source or 'entry_price < 0' in source, (
            "_validate_price must check for entry_price <= 0"
        )

    def test_validate_price_checks_upper_bound_one(self):
        """_validate_price must reject entry_price >= 1.0."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        assert 'entry_price >= 1' in source or 'entry_price > 1' in source, (
            "_validate_price must check for entry_price >= 1.0"
        )

    def test_validate_price_checks_max_entry_price(self):
        """_validate_price must still check max_entry_price."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        assert 'max_entry_price' in source, (
            "_validate_price must check against max_entry_price config"
        )

    def test_rejects_zero_price(self):
        """Functional test: price of 0 must be rejected."""
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
            entry_price=0.0, position_size=50.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_negative_price(self):
        """Functional test: negative price must be rejected."""
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
            entry_price=-0.5, position_size=50.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_price_at_one(self):
        """Functional test: price of 1.0 must be rejected."""
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
            entry_price=1.0, position_size=50.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_price_above_one(self):
        """Functional test: price > 1.0 must be rejected."""
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
            entry_price=1.5, position_size=50.0, question='Test'
        )

        result = executor.execute_trade(request)
        assert not result.success
        assert result.rejection_stage == 'price'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
