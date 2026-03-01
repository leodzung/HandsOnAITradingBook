"""
Structural tests for ARCH-014: Code quality standards in orderbook modules.

Prevents regression of issues #11, #12, #13, #17 fixed in commit d6356bd.

Rules enforced:
1. No bare except clauses (swallows errors silently)
2. No print() statements outside __main__ guard (bypasses logging)
3. Service layer must not access manager private attributes (broken encapsulation)
"""

import ast
import re
import pytest
from pathlib import Path

# All 5 orderbook module files
ORDERBOOK_FILES = [
    Path("src/utils/orderbook_websocket.py"),
    Path("src/core/orderbook_manager.py"),
    Path("src/core/shared_orderbook.py"),
    Path("src/services/orderbook_service.py"),
    Path("src/services/orderbook_client.py"),
]

ORDERBOOK_SERVICE = Path("src/services/orderbook_service.py")


class TestOrderbookCodeQuality:
    """Structural tests enforcing code quality in orderbook modules."""

    def test_no_bare_except(self):
        """No bare 'except:' clauses allowed — must specify exception type."""
        violations = []

        for filepath in ORDERBOOK_FILES:
            if not filepath.exists():
                continue

            content = filepath.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    violations.append(
                        f"  {filepath}:{node.lineno}: bare except (must specify exception type)"
                    )

        if violations:
            pytest.fail(
                "Bare except clauses found in orderbook modules:\n"
                + '\n'.join(violations)
                + "\n\nUse specific exception types (e.g., except Exception as e:) "
                "to avoid silently swallowing errors."
            )

    def test_no_print_outside_main(self):
        """No print() calls outside if __name__ == '__main__' guard."""
        violations = []

        for filepath in ORDERBOOK_FILES:
            if not filepath.exists():
                continue

            content = filepath.read_text()
            tree = ast.parse(content)

            # Find the line range of __main__ guard (if any)
            main_guard_start = None
            main_guard_end = None

            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.If):
                    # Check for: if __name__ == '__main__'
                    test = node.test
                    if (isinstance(test, ast.Compare) and
                            isinstance(test.left, ast.Name) and
                            test.left.id == '__name__'):
                        main_guard_start = node.lineno
                        main_guard_end = node.end_lineno or 99999

            # Find all print() calls
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == 'print':
                        line = node.lineno
                        # Allow if inside __main__ guard
                        if (main_guard_start is not None and
                                main_guard_start <= line <= main_guard_end):
                            continue
                        violations.append(f"  {filepath}:{line}: print() call")

        if violations:
            pytest.fail(
                "print() calls found outside __main__ guard in orderbook modules:\n"
                + '\n'.join(violations)
                + "\n\nUse logger.info/debug/warning/error instead of print()."
            )

    def test_service_no_private_attribute_access(self):
        """orderbook_service.py must not access orderbook_manager._private attributes."""
        filepath = ORDERBOOK_SERVICE
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()
        lines = content.split('\n')

        # Pattern: orderbook_manager._anything (accessing private attrs)
        pattern = re.compile(r'orderbook_manager\._\w+')
        violations = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            match = pattern.search(stripped)
            if match:
                violations.append(
                    f"  {filepath}:{i}: {match.group(0)}"
                )

        if violations:
            pytest.fail(
                "Private attribute access found in orderbook_service.py:\n"
                + '\n'.join(violations)
                + "\n\nService layer must only use public methods of OrderbookManager. "
                "Access to _private attributes breaks encapsulation."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
