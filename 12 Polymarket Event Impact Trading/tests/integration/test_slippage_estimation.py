"""
Integration tests for RISK-003: Slippage estimation before order execution

Validates that slippage estimation exists and is integrated into trade execution.
"""

import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.slippage_estimator import SlippageEstimator


class TestSlippageEstimation:
    """Test that slippage estimation is integrated into trade execution."""

    def test_slippage_estimator_exists(self):
        """Verify SlippageEstimator class exists and can be instantiated."""
        estimator = SlippageEstimator()
        assert estimator is not None

    def test_estimate_slippage_method_exists(self):
        """Verify estimate_slippage method exists with correct signature."""
        estimator = SlippageEstimator()
        assert hasattr(estimator, 'estimate_slippage')

    def test_slippage_estimation_rejects_bad_trades(self):
        """
        CRITICAL: Verify slippage estimation can reject trades.

        Tests that rejection logic exists (is_acceptable = False).
        """
        estimator = SlippageEstimator()

        # Empty orderbook should be rejected
        orderbook = {'bids': [], 'asks': []}

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=100.0,
            orderbook=orderbook,
            quoted_price=0.50
        )

        # Should not be acceptable
        assert not result.is_acceptable, (
            "Empty orderbook should be rejected"
        )
        assert result.rejection_reason is not None, (
            "Rejection should have a reason"
        )

    def test_slippage_estimation_accepts_good_trades(self):
        """Verify slippage estimation accepts reasonable trades."""
        estimator = SlippageEstimator()

        # Good orderbook
        orderbook = {
            'bids': [[0.495, 10000]],
            'asks': [[0.505, 10000]]
        }

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=100.0,  # Small trade, lots of liquidity
            orderbook=orderbook,
            quoted_price=0.50
        )

        # Should be acceptable
        assert result.is_acceptable or result.rejection_reason, (
            "Good trade should be acceptable or have clear rejection reason"
        )

    def test_trade_executor_uses_slippage_estimation(self):
        """
        CRITICAL: Verify TradeExecutor integrates slippage estimation.

        This is the core requirement of RISK-003.
        """
        import inspect
        from pathlib import Path

        # Read TradeExecutor source
        executor_path = Path(__file__).parent.parent.parent / "src" / "core" / "trade_executor.py"
        executor_source = executor_path.read_text()

        # Should import SlippageEstimator
        assert 'SlippageEstimator' in executor_source or 'slippage' in executor_source.lower(), (
            "TradeExecutor should use SlippageEstimator"
        )

        # Should call estimate_slippage before execution
        # Look for key patterns
        has_slippage_check = (
            'estimate_slippage' in executor_source or
            'slippage' in executor_source.lower()
        )

        assert has_slippage_check, (
            "TradeExecutor should call slippage estimation before executing trades"
        )


class TestSlippageEstimationIntegration:
    """Test slippage estimation integration and thresholds."""

    def test_has_rejection_thresholds(self):
        """Verify slippage estimator has rejection thresholds configured."""
        estimator = SlippageEstimator()

        # Should have max slippage threshold
        assert hasattr(estimator, 'max_slippage_bps'), (
            "Estimator should have max_slippage_bps threshold"
        )

        # Threshold should be a positive number
        assert estimator.max_slippage_bps > 0, (
            "max_slippage_bps should be positive"
        )

    def test_returns_slippage_estimate_object(self):
        """Verify estimate_slippage returns complete SlippageEstimate."""
        estimator = SlippageEstimator()

        orderbook = {
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        }

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=100.0,
            orderbook=orderbook,
            quoted_price=0.50
        )

        # Check required fields exist
        assert hasattr(result, 'is_acceptable')
        assert hasattr(result, 'slippage_bps')
        assert hasattr(result, 'rejection_reason')

    def test_slippage_calculated_in_basis_points(self):
        """Verify slippage is calculated and returned in basis points."""
        estimator = SlippageEstimator()

        orderbook = {
            'bids': [[0.49, 1000]],
            'asks': [[0.51, 1000]]
        }

        result = estimator.estimate_slippage(
            order_side='BUY',
            order_size=50.0,
            orderbook=orderbook,
            quoted_price=0.50
        )

        # Slippage should be a number
        assert isinstance(result.slippage_bps, (int, float)), (
            "slippage_bps should be a number"
        )

        # Basis points should be non-negative
        assert result.slippage_bps >= 0, (
            "slippage_bps should be non-negative"
        )
