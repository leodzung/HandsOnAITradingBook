"""
Structural tests for ARCH-015: Arbitrage checks must use BID prices (get_exit_prices),
not ASK prices (get_entry_prices).

Rationale:
    Arbitrage profit is realised by selling into the BID. Using ASK prices inflates
    the total above 1.0 and can never produce a valid arb signal.
"""

import re
from pathlib import Path


BOT_FILE = Path("src/bots/trader_short_expiry.py")


class TestArbitrageBidPrices:
    """Verify arbitrage checks use BID prices (get_exit_prices), not ASK."""

    def test_arbitrage_uses_get_exit_prices(self):
        """ARCH-015: Arbitrage rule must call get_exit_prices() for price input."""
        content = BOT_FILE.read_text()

        # Find the arbitrage block and verify it uses get_exit_prices
        arb_block_match = re.search(
            r"Rule 1.*?Arbitrage.*?(?=Rule 2|def )",
            content,
            re.DOTALL,
        )
        assert arb_block_match, "Could not find arbitrage rule block in trader_short_expiry.py"

        arb_block = arb_block_match.group(0)
        assert "get_exit_prices" in arb_block, (
            "Arbitrage block must use get_exit_prices() (BID prices) for arb total calculation"
        )

    def test_arbitrage_does_not_use_get_entry_prices(self):
        """ARCH-015: Arbitrage rule must NOT use get_entry_prices() (ASK prices)."""
        content = BOT_FILE.read_text()

        arb_block_match = re.search(
            r"Rule 1.*?Arbitrage.*?(?=Rule 2|def )",
            content,
            re.DOTALL,
        )
        assert arb_block_match, "Could not find arbitrage rule block"

        arb_block = arb_block_match.group(0)
        # get_entry_prices should NOT be used in the arbitrage block for pricing
        # (It may appear in comments but not as the price source for yes_price/no_price)
        arb_price_lines = [
            line for line in arb_block.split("\n")
            if "arb_prices" in line and "get_entry_prices" in line
        ]
        assert not arb_price_lines, (
            f"Arbitrage block must not use get_entry_prices() for arb prices:\n"
            + "\n".join(arb_price_lines)
        )

    def test_fix_comment_present(self):
        """ARCH-015: Code should document WHY exit prices are used for arbitrage."""
        content = BOT_FILE.read_text()
        # The fix comment should be near the arbitrage logic
        assert "BID" in content or "bid" in content.lower(), (
            "Code should document BID price usage for arbitrage"
        )
