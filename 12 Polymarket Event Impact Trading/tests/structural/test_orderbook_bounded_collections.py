"""
Structural tests for ARCH-013: Bounded caches and collections in orderbook modules.

Prevents regression of issues #8, #9, #10 (unbounded memory growth)
fixed in commit d6356bd.

Rules enforced:
1. REST cache in OrderbookManager must have _cache_max_size and eviction logic
2. WebSocket _order_books must have _max_order_books size limit
3. Opportunity log in RealTimeArbitrageMonitor must use deque(maxlen=)
"""

import ast
import re
import pytest
from pathlib import Path

ORDERBOOK_MANAGER = Path("src/core/orderbook_manager.py")
ORDERBOOK_WEBSOCKET = Path("src/utils/orderbook_websocket.py")


def _get_method_source(filepath: Path, method_name: str) -> str:
    """Extract full method source using AST (handles blank lines within methods)."""
    content = filepath.read_text()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return ast.get_source_segment(content, node) or ''

    return ''


class TestOrderbookBoundedCollections:
    """Structural tests enforcing bounded collections in orderbook modules."""

    def test_rest_cache_has_max_size(self):
        """REST cache must have _cache_max_size and eviction in _get_rest_orderbook."""
        filepath = ORDERBOOK_MANAGER
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Must define _cache_max_size
        assert '_cache_max_size' in content, (
            f"{filepath} must define _cache_max_size to bound the REST orderbook cache"
        )

        # Extract full method source via AST
        method_source = _get_method_source(filepath, '_get_rest_orderbook')
        assert method_source, f"_get_rest_orderbook not found in {filepath}"

        # Must check cache size and evict
        assert '_cache_max_size' in method_source, (
            f"_get_rest_orderbook in {filepath} must check _cache_max_size to prevent "
            "unbounded cache growth"
        )

        # Must have eviction logic (del or pop)
        has_eviction = ('del ' in method_source or '.pop(' in method_source)
        assert has_eviction, (
            f"_get_rest_orderbook in {filepath} must evict old entries when cache "
            "exceeds _cache_max_size"
        )

    def test_order_books_has_max_size(self):
        """WebSocket _order_books must have _max_order_books size limit."""
        filepath = ORDERBOOK_WEBSOCKET
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Must define _max_order_books
        assert '_max_order_books' in content, (
            f"{filepath} must define _max_order_books to prevent unbounded "
            "order book storage from unsubscribed assets"
        )

        # Extract full method source via AST
        method_source = _get_method_source(filepath, '_handle_book_update')
        assert method_source, f"_handle_book_update not found in {filepath}"

        assert '_max_order_books' in method_source, (
            f"_handle_book_update in {filepath} must check _max_order_books before "
            "adding new order books to prevent unbounded growth"
        )

    def test_opportunities_uses_deque(self):
        """Opportunity log must use deque(maxlen=) for bounded storage."""
        filepath = ORDERBOOK_WEBSOCKET
        if not filepath.exists():
            pytest.skip(f"{filepath} not found")

        content = filepath.read_text()

        # Must use deque with maxlen for opportunities
        has_deque_maxlen = bool(re.search(r'deque\(maxlen=', content))
        assert has_deque_maxlen, (
            f"{filepath} must use deque(maxlen=...) for opportunity storage "
            "to prevent unbounded list growth"
        )

        # Must NOT use list slicing pattern for opportunities (e.g., self._opportunities = self._opportunities[-N:])
        list_slicing_pattern = re.compile(
            r'self\._opportunities\s*=\s*self\._opportunities\[.*:\]'
        )
        slicing_match = list_slicing_pattern.search(content)
        assert not slicing_match, (
            f"{filepath} uses list slicing for opportunities (line with: {slicing_match.group(0)}). "
            "Use deque(maxlen=) instead for O(1) bounded append."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
