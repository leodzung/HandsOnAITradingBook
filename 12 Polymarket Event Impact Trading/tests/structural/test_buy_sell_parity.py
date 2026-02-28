"""
Structural test for RISK-008: Symmetric test coverage for BUY/SELL operations.

Ensures SELL test count / BUY test count >= 0.8 in slippage estimator tests.
"""

import ast
import pytest
from pathlib import Path


class TestBuySellParity:
    """Verify BUY/SELL test symmetry in slippage estimator."""

    def test_sell_to_buy_ratio_at_least_80_percent(self):
        """SELL tests / BUY tests >= 0.8."""
        test_file = Path('tests/test_slippage_estimator.py')
        assert test_file.exists(), f"Test file not found: {test_file}"

        tree = ast.parse(test_file.read_text())
        buy_tests = [
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and 'buy' in n.name.lower()
        ]
        sell_tests = [
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and 'sell' in n.name.lower()
        ]

        ratio = len(sell_tests) / max(len(buy_tests), 1)

        assert ratio >= 0.8, (
            f"BUY/SELL test parity too low: "
            f"BUY tests: {len(buy_tests)}, SELL tests: {len(sell_tests)}, "
            f"Ratio: {ratio:.2f} (need >= 0.80)"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
