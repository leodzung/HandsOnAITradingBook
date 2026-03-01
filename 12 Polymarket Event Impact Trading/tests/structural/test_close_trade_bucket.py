"""
Structural test for ARCH-011: execute_close_trade must accept bucket parameter.

Verifies that:
1. execute_close_trade accepts a bucket parameter
2. estimate_slippage is called with bucket= in the close trade path
3. Short-expiry bot passes bucket to execute_close_trade
"""

import ast
import re
import pytest
from pathlib import Path


class TestCloseTradeAcceptsBucket:
    """Verify execute_close_trade passes bucket to slippage estimation."""

    TRADE_EXECUTOR_PATH = Path("src/core/trade_executor.py")
    SHORT_EXPIRY_BOT_PATH = Path("src/bots/trader_short_expiry.py")

    def test_execute_close_trade_has_bucket_parameter(self):
        """execute_close_trade must accept a bucket parameter."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        # Find the method definition
        assert re.search(
            r'def execute_close_trade\([^)]*bucket',
            source,
            re.DOTALL
        ), "execute_close_trade must have a 'bucket' parameter"

    def test_close_trade_passes_bucket_to_estimate_slippage(self):
        """estimate_slippage call in execute_close_trade must include bucket=."""
        source = self.TRADE_EXECUTOR_PATH.read_text()

        # Find the execute_close_trade method body
        # Look for estimate_slippage call after the method definition
        close_trade_start = source.find('def execute_close_trade')
        assert close_trade_start > 0, "execute_close_trade method not found"

        # Get the rest of the file from this method
        close_trade_body = source[close_trade_start:]

        # Check that estimate_slippage is called with bucket=
        assert re.search(
            r'estimate_slippage\([^)]*bucket\s*=\s*bucket',
            close_trade_body,
            re.DOTALL
        ), "estimate_slippage in execute_close_trade must pass bucket=bucket"

    def test_short_expiry_bot_passes_bucket_to_close_trade(self):
        """Short-expiry bot must pass bucket= to execute_close_trade."""
        if not self.SHORT_EXPIRY_BOT_PATH.exists():
            pytest.skip("Short-expiry bot not found")

        source = self.SHORT_EXPIRY_BOT_PATH.read_text()

        # Find all execute_close_trade calls
        close_calls = list(re.finditer(
            r'execute_close_trade\(',
            source
        ))

        assert len(close_calls) > 0, "Short-expiry bot should call execute_close_trade"

        # Check each call includes bucket=
        for match in close_calls:
            # Get the full call (find matching closing paren)
            start = match.start()
            paren_depth = 0
            end = start
            for i, ch in enumerate(source[start:], start):
                if ch == '(':
                    paren_depth += 1
                elif ch == ')':
                    paren_depth -= 1
                    if paren_depth == 0:
                        end = i + 1
                        break

            call_text = source[start:end]
            line_num = source[:start].count('\n') + 1

            assert 'bucket=' in call_text, (
                f"execute_close_trade call at line {line_num} must pass bucket= parameter"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
