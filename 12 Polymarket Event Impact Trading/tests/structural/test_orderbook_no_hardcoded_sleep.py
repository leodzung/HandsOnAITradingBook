"""
Structural tests for ARCH-012: No hardcoded sleeps for connection waiting.

Prevents regression of issue #6 (time.sleep(2) instead of wait_for_connection)
fixed in commit d6356bd.

Rules enforced:
1. _start_websocket must not contain time.sleep() calls
2. _start_websocket must use wait_for_connection() for readiness
"""

import ast
import pytest
from pathlib import Path

ORDERBOOK_MANAGER = Path("src/core/orderbook_manager.py")


class TestOrderbookNoHardcodedSleep:
    """Structural tests forbidding hardcoded sleeps in connection startup."""

    def test_no_sleep_in_start_websocket(self):
        """_start_websocket must not use time.sleep() — use wait_for_connection instead."""
        filepath = ORDERBOOK_MANAGER
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()
        tree = ast.parse(content)

        # Find _start_websocket method
        start_ws_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == '_start_websocket':
                start_ws_node = node
                break

        assert start_ws_node is not None, (
            f"_start_websocket method not found in {filepath}"
        )

        # Walk the method AST for time.sleep calls
        sleep_calls = []
        for child in ast.walk(start_ws_node):
            if isinstance(child, ast.Call):
                func = child.func
                # Match time.sleep(...)
                if (isinstance(func, ast.Attribute) and
                        func.attr == 'sleep' and
                        isinstance(func.value, ast.Name) and
                        func.value.id == 'time'):
                    sleep_calls.append(child.lineno)

        if sleep_calls:
            pytest.fail(
                f"time.sleep() found in _start_websocket at line(s) {sleep_calls}.\n"
                "Use wait_for_connection() instead of hardcoded sleeps for connection readiness."
            )

    def test_uses_wait_for_connection(self):
        """_start_websocket must use wait_for_connection for connection readiness."""
        filepath = ORDERBOOK_MANAGER
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Extract _start_websocket method source
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == '_start_websocket':
                method_source = ast.get_source_segment(content, node) or ''
                assert 'wait_for_connection' in method_source, (
                    f"_start_websocket in {filepath} must use wait_for_connection() "
                    "instead of hardcoded time.sleep() for connection readiness"
                )
                return

        pytest.fail(f"_start_websocket method not found in {filepath}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
