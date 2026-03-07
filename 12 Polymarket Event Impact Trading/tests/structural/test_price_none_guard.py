"""
Structural tests for RISK-016: Current price must be validated non-None before exit logic.

Rationale:
    If PriceFetcher returns None for a specific outcome price, passing it to should_exit()
    or P&L arithmetic causes a TypeError crash. The position loop must guard against None
    and skip (not crash) when the price is unavailable.
"""

import re
from pathlib import Path


BOT_FILE = Path("src/bots/trader_short_expiry.py")


def _get_check_positions_source() -> str:
    content = BOT_FILE.read_text()
    match = re.search(
        r"def _check_positions\(self\).*?(?=\n    def |\Z)",
        content,
        re.DOTALL,
    )
    assert match, "_check_positions method not found in trader_short_expiry.py"
    return match.group(0)


class TestPriceNoneGuard:
    """Verify current_price is validated for None before use in exit logic."""

    def test_exit_prices_none_check_present(self):
        """RISK-016: exit_prices=None must be handled (skip position, not crash)."""
        source = _get_check_positions_source()
        # Should check if exit_prices is None
        assert "exit_prices is None" in source, (
            "_check_positions must check if exit_prices is None before using it"
        )

    def test_current_price_none_check_before_should_exit(self):
        """RISK-016: current_price must be checked for None before calling should_exit()."""
        source = _get_check_positions_source()

        # Verify None guard exists
        assert "current_price is None" in source, (
            "_check_positions must guard against None current_price "
            "before calling should_exit() or arithmetic"
        )

    def test_current_price_none_logs_warning(self):
        """RISK-016: None current_price must log a WARNING, not silently skip."""
        source = _get_check_positions_source()

        none_price_idx = source.find("current_price is None")
        assert none_price_idx >= 0, "current_price None check not found"

        block_after = source[none_price_idx:none_price_idx + 300]
        assert "warning" in block_after.lower() or "logger.warning" in block_after, (
            "When current_price is None, must log a WARNING before skipping"
        )

    def test_should_exit_called_after_price_guard(self):
        """RISK-016: should_exit() is called only after current_price is validated."""
        source = _get_check_positions_source()

        none_check_idx = source.find("current_price is None")
        # Search for the actual call (not comments/docstrings that mention the name)
        should_exit_call_idx = source.find("risk_manager.should_exit(")

        assert none_check_idx >= 0, "current_price None check not found"
        assert should_exit_call_idx >= 0, "risk_manager.should_exit() call not found"

        # The None check must come BEFORE the actual should_exit() call
        assert none_check_idx < should_exit_call_idx, (
            "current_price None check must appear before risk_manager.should_exit() call in source order"
        )

    def test_no_arithmetic_before_none_guard(self):
        """RISK-016: No arithmetic on current_price before it's validated non-None."""
        source = _get_check_positions_source()

        none_check_idx = source.find("current_price is None")
        assert none_check_idx >= 0, "current_price None check not found"

        # Get the section before the None check that mentions current_price
        before_check = source[:none_check_idx]
        current_price_uses = re.findall(r"current_price\s*[+\-\*/]", before_check)

        assert not current_price_uses, (
            f"Arithmetic on current_price found BEFORE None guard: {current_price_uses}\n"
            "Move the None check before any arithmetic."
        )
