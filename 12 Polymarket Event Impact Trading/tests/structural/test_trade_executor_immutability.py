"""
Structural test for ARCH-010: TradeExecutor must not mutate TradeRequest inputs.

Verifies that execute_trade() does not assign to request.entry_price or any
other TradeRequest field. Uses AST inspection to detect attribute assignments.
"""

import ast
import pytest
from pathlib import Path


class TestTradeExecutorImmutability:
    """Verify execute_trade does not mutate request fields."""

    TRADE_EXECUTOR_PATH = Path("src/core/trade_executor.py")

    def test_execute_trade_does_not_mutate_request(self):
        """execute_trade must not assign to request.* attributes."""
        source = self.TRADE_EXECUTOR_PATH.read_text()
        tree = ast.parse(source)

        violations = []

        for node in ast.walk(tree):
            # Look for assignments like: request.entry_price = ...
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (isinstance(target, ast.Attribute) and
                            isinstance(target.value, ast.Name) and
                            target.value.id == 'request'):
                        violations.append(
                            f"Line {node.lineno}: request.{target.attr} = ..."
                        )

        if violations:
            pytest.fail(
                f"execute_trade must not mutate TradeRequest (ARCH-010):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    def test_execution_price_tracked_locally(self):
        """execute_trade must use a local execution_price variable."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        assert 'execution_price = request.entry_price' in source, (
            "execute_trade should initialize execution_price from request.entry_price"
        )
        assert 'execution_price = recommended_price' in source, (
            "execute_trade should update execution_price (not request) with recommended_price"
        )

    def test_execute_position_accepts_execution_price(self):
        """_execute_position must accept execution_price parameter."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        assert 'def _execute_position(self, request: TradeRequest, execution_price: float)' in source, (
            "_execute_position must accept execution_price parameter"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
