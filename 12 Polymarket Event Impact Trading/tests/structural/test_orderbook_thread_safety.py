"""
Structural tests for ARCH-009: Thread-safe shared state in orderbook modules.

Prevents regression of thread safety issues (#1, #2, #3, #19, #20) fixed in commit d6356bd.

Rules enforced:
1. Stats must use _inc_stat(), not direct self.stats[key] += 1
2. _inc_stat must use _stats_lock
3. _ws_client access outside __init__ must be under _ws_lock
4. OrderbookServiceClient cache must use _cache_lock
5. SharedOrderbookManager.is_initialized must read _initialized under _lock
"""

import ast
import re
import pytest
from pathlib import Path

# Orderbook module paths (relative to project root)
ORDERBOOK_WEBSOCKET = Path("src/utils/orderbook_websocket.py")
ORDERBOOK_MANAGER = Path("src/core/orderbook_manager.py")
ORDERBOOK_CLIENT = Path("src/services/orderbook_client.py")
SHARED_ORDERBOOK = Path("src/core/shared_orderbook.py")


class TestOrderbookThreadSafety:
    """Structural tests enforcing thread safety patterns in orderbook modules."""

    def test_stats_use_inc_stat_not_direct_mutation(self):
        """Stats must use _inc_stat() — direct self.stats[...] += is FORBIDDEN outside _inc_stat."""
        violations = []

        for filepath in [ORDERBOOK_WEBSOCKET]:
            if not filepath.exists():
                pytest.skip(f"{filepath} not found")

            content = filepath.read_text()
            lines = content.split('\n')

            # Pattern: self.stats[...] += (direct mutation)
            pattern = re.compile(r'self\.stats\[.*?\]\s*[+\-*/]?=')

            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue

                if pattern.search(stripped):
                    # Allow only inside _inc_stat method
                    # Walk backwards to find enclosing def
                    in_inc_stat = False
                    for j in range(i - 1, max(0, i - 20), -1):
                        prev_line = lines[j - 1].strip() if j > 0 else ''
                        if prev_line.startswith('def _inc_stat'):
                            in_inc_stat = True
                            break
                        if prev_line.startswith('def ') and not prev_line.startswith('def _inc_stat'):
                            break

                    if not in_inc_stat:
                        violations.append(f"  {filepath}:{i}: {stripped}")

        if violations:
            pytest.fail(
                "Direct self.stats[...] mutation found (must use _inc_stat()):\n"
                + '\n'.join(violations)
            )

    def test_inc_stat_uses_stats_lock(self):
        """_inc_stat method must acquire _stats_lock for thread safety."""
        filepath = ORDERBOOK_WEBSOCKET
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Find _inc_stat method body
        match = re.search(
            r'def _inc_stat\(self.*?\).*?:\n((?:[ \t]+.*\n)*)',
            content
        )
        assert match, f"_inc_stat method not found in {filepath}"

        method_body = match.group(1)
        assert '_stats_lock' in method_body, (
            f"_inc_stat in {filepath} must use _stats_lock for thread safety"
        )

    def test_ws_client_protected_by_ws_lock(self):
        """_ws_client access outside __init__ must be under _ws_lock in OrderbookManager."""
        filepath = ORDERBOOK_MANAGER
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()
        tree = ast.parse(content)

        violations = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            # Skip __init__ — initial assignment is fine
            if node.name == '__init__':
                continue

            # Check if this method accesses self._ws_client
            accesses_ws_client = False
            for child in ast.walk(node):
                if not isinstance(child, ast.Attribute):
                    continue
                if child.attr != '_ws_client':
                    continue
                # self._ws_client → Attribute(value=Name(id='self'), attr='_ws_client')
                if isinstance(child.value, ast.Name) and child.value.id == 'self':
                    accesses_ws_client = True
                    break

            if not accesses_ws_client:
                continue

            # Method accesses _ws_client — verify _ws_lock is used
            method_source = ast.get_source_segment(content, node) or ''
            if '_ws_lock' not in method_source:
                # Exception: _stop_websocket documents that caller must hold lock
                if node.name == '_stop_websocket':
                    # Check docstring mentions caller must hold lock
                    if 'caller must hold' in method_source.lower() or 'Caller must hold' in method_source:
                        continue
                violations.append(f"  {filepath}: {node.name}() (line {node.lineno})")

        if violations:
            pytest.fail(
                "Methods accessing self._ws_client without _ws_lock:\n"
                + '\n'.join(violations)
                + "\n\nAll _ws_client access outside __init__ must be under _ws_lock "
                "(or docstring must state 'Caller must hold _ws_lock')"
            )

    def test_orderbook_client_cache_has_lock(self):
        """OrderbookServiceClient must use _cache_lock to protect cache access."""
        filepath = ORDERBOOK_CLIENT
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Must define _cache_lock
        assert '_cache_lock' in content, (
            f"{filepath} must define _cache_lock for thread-safe cache access"
        )

        # Must use _cache_lock in get_orderbook (the method that reads/writes cache)
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'get_orderbook':
                method_source = ast.get_source_segment(content, node) or ''
                assert '_cache_lock' in method_source, (
                    f"get_orderbook in {filepath} must use _cache_lock when accessing cache"
                )
                return

        pytest.fail(f"get_orderbook method not found in {filepath}")

    def test_shared_orderbook_initialized_under_lock(self):
        """SharedOrderbookManager.is_initialized must read _initialized under _lock."""
        filepath = SHARED_ORDERBOOK
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Find is_initialized method
        match = re.search(
            r'def is_initialized\(cls\).*?:\n((?:[ \t]+.*\n)*)',
            content
        )
        assert match, f"is_initialized method not found in {filepath}"

        method_body = match.group(1)
        assert '_lock' in method_body, (
            f"is_initialized in {filepath} must read _initialized under _lock "
            "to prevent race conditions with get_instance()"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
