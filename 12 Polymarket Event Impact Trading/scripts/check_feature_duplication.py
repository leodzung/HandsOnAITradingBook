#!/usr/bin/env python3
"""
ARCH-003: Check for feature extraction code duplication.

Scans bot files for inline feature extraction patterns that should use
centralized extractors from src/features/common_features.py.

Exit code 0 = pass, 1 = violations found.
"""

import re
import sys
from pathlib import Path


# Patterns that indicate inline feature extraction (should use common_features.py)
DUPLICATION_PATTERNS = [
    # Orderbook feature duplication
    (r'orderbook\[.bids.\]\[0\]', 'Inline orderbook parsing - use OrderbookFeatures.extract()'),
    (r'orderbook\[.asks.\]\[0\]', 'Inline orderbook parsing - use OrderbookFeatures.extract()'),
    (r'bid_depth|ask_depth', 'Inline depth calculation - use OrderbookFeatures.extract()'),
    (r'sum\(.*for.*in.*bids\)', 'Inline bid aggregation - use OrderbookFeatures.extract()'),
    (r'sum\(.*for.*in.*asks\)', 'Inline ask aggregation - use OrderbookFeatures.extract()'),

    # Volume feature duplication
    (r'volume_24h\s*=.*market.*volume', 'Inline volume extraction - use VolumeFeatures.extract()'),
    (r"market\[.volume.\]", 'Inline volume access - use VolumeFeatures.extract()'),

    # Time feature duplication (calculating hours_to_expiry inline)
    (r'total_seconds\(\)\s*/\s*3600', 'Inline hours calculation - use TimeFeatures.extract()'),
]

# Files where common_features.py classes SHOULD be used
BOT_FILES = [
    'src/bots/trader.py',
    'src/bots/trader_price_levels.py',
    'src/bots/trader_short_expiry.py',
]

# Files where duplication is allowed (the common_features implementation itself)
ALLOWED_FILES = [
    'src/features/common_features.py',
    'src/features/feature_extractor.py',
]

MAX_DUPLICATE_LINES = 10


def check_duplication():
    violations = []
    duplicate_count = 0

    for bot_file in BOT_FILES:
        path = Path(bot_file)
        if not path.exists():
            continue

        lines = path.read_text().splitlines()
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('#'):
                continue

            for pattern, description in DUPLICATION_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    violations.append(f"{bot_file}:{line_num}: {description}")
                    duplicate_count += 1

    if duplicate_count > MAX_DUPLICATE_LINES:
        print(f"FAIL: {duplicate_count} duplicate feature extraction lines found (max: {MAX_DUPLICATE_LINES})")
        for v in violations:
            print(f"  - {v}")
        return False
    else:
        print(f"PASS: {duplicate_count} duplicate lines (max: {MAX_DUPLICATE_LINES})")
        return True


if __name__ == '__main__':
    success = check_duplication()
    sys.exit(0 if success else 1)
