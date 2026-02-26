"""
Structural tests for ARCH-001: PriceFetcher is single source of truth

These tests enforce that all price data flows through PriceFetcher.
Direct access to market['bestBid'], market['bestAsk'], etc. is FORBIDDEN.

Rationale:
    Historical bug: YES/NO price confusion caused incorrect P&L calculations.
    PriceFetcher provides correct ASK (entry) and BID (exit) prices with
    built-in safety checks.
"""

import pytest
import re
from pathlib import Path


class TestPriceFetcherConstraint:
    """Structural tests enforcing PriceFetcher usage"""

    # Files that MUST use PriceFetcher instead of direct market access
    REQUIRED_FILES = [
        "src/bots/trader.py",
        "src/bots/trader_price_levels.py",
        "src/bots/trader_short_expiry.py",
        "src/core/trade_executor.py",
    ]

    # Files that should call PriceFetcher methods (excludes TradeExecutor which receives prices)
    BOT_FILES = [
        "src/bots/trader.py",
        "src/bots/trader_price_levels.py",
        "src/bots/trader_short_expiry.py",
    ]

    # Files ALLOWED to access market prices directly
    ALLOWED_FILES = [
        "src/core/price_fetcher.py",
    ]

    # Forbidden patterns that indicate direct market price access
    FORBIDDEN_PATTERNS = [
        r"market\['bestBid'\]",
        r"market\['bestAsk'\]",
        r"market\['outcomePrices'\]",
        r"market\.get\('bestBid'\)",
        r"market\.get\('bestAsk'\)",
        r"market\.get\('outcomePrices'\)",
    ]

    def test_no_direct_market_price_access_in_bots(self):
        """Verify bots don't access market prices directly"""
        violations = []

        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

                for pattern in self.FORBIDDEN_PATTERNS:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        # Find line number
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = lines[line_num - 1].strip()

                        # Skip if it's a comment
                        if line_content.startswith('#'):
                            continue

                        violations.append({
                            'file': str(file_path),
                            'line': line_num,
                            'pattern': match.group(0),
                            'context': line_content
                        })

        if violations:
            error_msg = "Found direct market price access (should use PriceFetcher):\n"
            for v in violations:
                error_msg += f"  {v['file']}:{v['line']} - {v['pattern']}\n"
                error_msg += f"    Context: {v['context']}\n"

            pytest.fail(error_msg)

    def test_bots_import_price_fetcher(self):
        """Verify bots import PriceFetcher (excludes TradeExecutor which receives prices)"""
        missing_imports = []

        for file_path in self.BOT_FILES:  # Only check bot files, not TradeExecutor
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # Check for PriceFetcher import (accept both absolute and relative imports)
                has_import = (
                    'from src.core.price_fetcher import PriceFetcher' in content or
                    'from core.price_fetcher import PriceFetcher' in content or  # Relative import
                    'from price_fetcher import PriceFetcher' in content or
                    'import price_fetcher' in content
                )

                if not has_import:
                    missing_imports.append(str(file_path))

        if missing_imports:
            error_msg = "Bot files missing PriceFetcher import:\n"
            for file in missing_imports:
                error_msg += f"  {file}\n"

            pytest.fail(error_msg)

    def test_bots_use_get_entry_prices(self):
        """Verify bots use PriceFetcher.get_entry_prices() for entries"""
        missing_usage = []

        for file_path in self.BOT_FILES:  # Only check bot files
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # Check for get_entry_prices usage
                # Bots should call this method to get entry prices
                if 'get_entry_prices' not in content:
                    missing_usage.append(str(file_path))

        if missing_usage:
            error_msg = "Bot files should use PriceFetcher.get_entry_prices():\n"
            for file in missing_usage:
                error_msg += f"  {file}\n"

            pytest.fail(error_msg)

    def test_price_fetcher_is_only_price_source(self):
        """Verify bot files instantiate and use PriceFetcher"""
        for file_path in self.BOT_FILES:  # Only check bot files
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()

                # Bots should instantiate PriceFetcher (self.price_fetcher = PriceFetcher(...))
                assert 'PriceFetcher' in content, \
                    f"{file_path} should instantiate PriceFetcher"

                # Bots should call price fetcher methods (not access market prices directly)
                assert ('get_entry_prices' in content or 'get_exit_prices' in content), \
                    f"{file_path} should call PriceFetcher.get_entry_prices() or get_exit_prices()"

    def test_no_price_endpoint_direct_calls(self):
        """Verify no direct calls to /price or /book endpoints outside PriceFetcher"""
        violations = []

        for file_path in self.REQUIRED_FILES:
            path = Path(file_path)
            if not path.exists():
                continue

            with open(path, 'r') as f:
                content = f.read()
                lines = content.split('\n')

                # Check for direct endpoint calls
                patterns = [
                    r"\/price['\"]",
                    r"\/book['\"]",
                    r"clob_client\.get_price",
                ]

                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.MULTILINE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = lines[line_num - 1].strip()

                        if not line_content.startswith('#'):
                            violations.append({
                                'file': str(file_path),
                                'line': line_num,
                                'pattern': match.group(0),
                                'context': line_content
                            })

        if violations:
            error_msg = "Found direct price endpoint calls (should use PriceFetcher):\n"
            for v in violations:
                error_msg += f"  {v['file']}:{v['line']} - {v['pattern']}\n"

            pytest.fail(error_msg)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
