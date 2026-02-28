"""
Structural test for ARCH-008: No synthetic NO price calculation.

Bot code must NOT compute NO price as (1.0 - yes_price) or (1 - market_price).
YES and NO prices must be fetched independently from PriceFetcher.
"""

import re
import pytest
from pathlib import Path


# Patterns that indicate synthetic NO price calculation
# These match: 1.0 - <variable>, 1 - <variable> in price contexts
FORBIDDEN_PATTERNS = [
    # "no_price = 1.0 - ..." or "no_price = 1 - ..."
    (r'no_price\s*=\s*1(?:\.0)?\s*-\s*\w+', 'no_price = 1.0 - variable'),
    # "current_no_price=1.0 - ..." as keyword arg
    (r'current_no_price\s*=\s*1(?:\.0)?\s*-\s*\w+', 'current_no_price=1.0 - variable'),
    # "1.0 - market_price" or "1 - market_price"
    (r'\b1(?:\.0)?\s*-\s*market_price\b', '1.0 - market_price'),
    # "1.0 - yes_price" or "1 - yes_price"
    (r'\b1(?:\.0)?\s*-\s*yes_price\b', '1.0 - yes_price'),
]

# Lines containing these substrings are safety checks, not price synthesis
ALLOWED_CONTEXTS = [
    'no_price_estimate',   # YES/NO confusion detector
    'SAFETY',              # Safety check annotations
    'confusion detected',  # Safety error messages
]

BOT_FILES = [
    'src/bots/trader.py',
    'src/bots/trader_price_levels.py',
    'src/bots/trader_short_expiry.py',
]


class TestIndependentPrices:
    """Verify bots don't compute synthetic NO prices from YES prices."""

    def test_no_synthetic_no_price_in_bots(self):
        """Bot files must not contain patterns like no_price = 1.0 - yes_price."""
        violations = []

        for bot_file in BOT_FILES:
            path = Path(bot_file)
            if not path.exists():
                continue

            lines = path.read_text().splitlines()
            for line_num, line in enumerate(lines, 1):
                stripped = line.strip()
                # Skip comments
                if stripped.startswith('#'):
                    continue
                # Skip safe fallback patterns (explicitly documented)
                if 'Safe fallback' in line or 'ARCH-008' in line:
                    continue
                # Skip safety check contexts (anomaly detection, not price synthesis)
                if any(ctx in line for ctx in ALLOWED_CONTEXTS):
                    continue

                for pattern, description in FORBIDDEN_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(
                            f"{bot_file}:{line_num}: {description}\n"
                            f"    {stripped}"
                        )

        if violations:
            pytest.fail(
                f"ARCH-008 violation: Synthetic NO price calculation found "
                f"in {len(violations)} location(s):\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: Use price_fetcher.get_entry_prices(market_id).no_price instead"
            )

    def test_price_fetcher_used_for_no_price(self):
        """Verify PriceFetcher is imported in all bot files."""
        for bot_file in BOT_FILES:
            path = Path(bot_file)
            if not path.exists():
                continue

            content = path.read_text()
            assert 'from core.price_fetcher import PriceFetcher' in content or \
                   'from src.core.price_fetcher import PriceFetcher' in content, \
                f"{bot_file} must import PriceFetcher"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
