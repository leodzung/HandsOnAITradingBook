"""CONFIG-001: Config values that may be per-bucket dicts must never be compared directly.

Prevents the class of bug where a config value stored as a dict (e.g.,
max_slippage_bps: {ultra_short: 3000, short: 2000}) gets compared directly
to a float, causing 'TypeError: > not supported between float and dict'.

All such values must go through _resolve() before numeric comparison.
"""

import ast
import os
import sys
import pytest

SRC_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'src')

# Attributes that may be per-bucket dicts and must not be compared directly
DICT_CAPABLE_ATTRS = {
    'max_slippage_bps',
    'max_slippage_dollars',
    'warn_threshold_bps',
}


def _find_raw_comparisons(filepath: str) -> list:
    """Find lines where dict-capable self.attr is used in a comparison operator."""
    violations = []
    with open(filepath) as f:
        source = f.read()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return violations

    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue

        # Check all operands in the comparison (left + comparators)
        all_operands = [node.left] + node.comparators
        for operand in all_operands:
            if isinstance(operand, ast.Attribute):
                if (operand.attr in DICT_CAPABLE_ATTRS
                        and isinstance(operand.value, ast.Attribute)
                        and operand.value.attr == 'self'
                        or (isinstance(operand.value, ast.Name)
                            and operand.value.id == 'self'
                            and operand.attr in DICT_CAPABLE_ATTRS)):
                    violations.append(
                        f"{os.path.basename(filepath)}:{node.lineno} - "
                        f"self.{operand.attr} used in direct comparison "
                        f"(must use _resolve())"
                    )

    return violations


class TestNoDictComparisons:
    """Ensure dict-capable config attrs are never compared directly."""

    def test_slippage_estimator_no_raw_dict_comparisons(self):
        """SlippageEstimator must not compare self.max_slippage_bps etc. directly."""
        filepath = os.path.join(SRC_DIR, 'core', 'slippage_estimator.py')
        violations = _find_raw_comparisons(filepath)
        assert violations == [], (
            f"Found raw comparisons of dict-capable config values "
            f"(use _resolve() instead):\n" +
            "\n".join(f"  - {v}" for v in violations)
        )

    def test_all_core_modules_no_raw_dict_comparisons(self):
        """No core module should compare dict-capable attrs directly."""
        core_dir = os.path.join(SRC_DIR, 'core')
        all_violations = []
        for filename in os.listdir(core_dir):
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(core_dir, filename)
            violations = _find_raw_comparisons(filepath)
            all_violations.extend(violations)

        assert all_violations == [], (
            f"Found raw comparisons of dict-capable config values:\n" +
            "\n".join(f"  - {v}" for v in all_violations)
        )

    def test_all_bot_modules_no_raw_dict_comparisons(self):
        """No bot module should compare dict-capable attrs directly."""
        bots_dir = os.path.join(SRC_DIR, 'bots')
        all_violations = []
        for filename in os.listdir(bots_dir):
            if not filename.endswith('.py'):
                continue
            filepath = os.path.join(bots_dir, filename)
            violations = _find_raw_comparisons(filepath)
            all_violations.extend(violations)

        assert all_violations == [], (
            f"Found raw comparisons of dict-capable config values:\n" +
            "\n".join(f"  - {v}" for v in all_violations)
        )
