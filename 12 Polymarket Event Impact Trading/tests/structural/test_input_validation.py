"""
Structural test for RISK-010: Input validation for all external data.

Verifies that input validation tests exist in the slippage estimator test suite,
covering invalid order side, order size, and quoted price scenarios.
"""

import ast
import pytest
from pathlib import Path


class TestInputValidationCoverage:
    """Verify input validation test coverage exists."""

    def test_invalid_input_tests_exist(self):
        """Slippage estimator must have tests for invalid inputs."""
        test_file = Path('tests/test_slippage_estimator.py')
        assert test_file.exists(), f"Test file not found: {test_file}"

        tree = ast.parse(test_file.read_text())
        invalid_tests = [
            n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and 'invalid' in n.name.lower()
        ]

        assert len(invalid_tests) >= 3, (
            f"Expected at least 3 input validation tests, found {len(invalid_tests)}: "
            f"{invalid_tests}"
        )

    def test_covers_order_side_validation(self):
        """Must have test for invalid order side."""
        test_file = Path('tests/test_slippage_estimator.py')
        content = test_file.read_text()
        assert 'test_invalid_order_side' in content, (
            "Missing test_invalid_order_side in slippage estimator tests"
        )

    def test_covers_order_size_validation(self):
        """Must have test for invalid order size."""
        test_file = Path('tests/test_slippage_estimator.py')
        content = test_file.read_text()
        assert 'test_invalid_order_size' in content, (
            "Missing test_invalid_order_size in slippage estimator tests"
        )

    def test_covers_quoted_price_validation(self):
        """Must have test for invalid quoted price."""
        test_file = Path('tests/test_slippage_estimator.py')
        content = test_file.read_text()
        assert 'test_invalid_quoted_price' in content, (
            "Missing test_invalid_quoted_price in slippage estimator tests"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
