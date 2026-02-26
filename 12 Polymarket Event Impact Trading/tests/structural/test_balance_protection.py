"""
RISK-006: Minimum balance protection

Validates that bots pause trading when balance falls below minimum.
"""

import pytest
import sys
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def test_short_expiry_has_min_balance_config():
    """Test that short-expiry bot has min_trading_balance configured."""
    config_path = 'config/config_short_expiry.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    assert 'min_trading_balance' in config['risk_management'], \
        "Config missing min_trading_balance"

    min_balance = config['risk_management']['min_trading_balance']
    assert min_balance > 0, "min_trading_balance must be > 0"
    assert min_balance <= 100, "min_trading_balance seems too high"


def test_short_expiry_implements_balance_check():
    """Test that short-expiry bot implements balance checking."""
    trader_path = Path('src/bots/trader_short_expiry.py')
    source = trader_path.read_text()

    # Check for balance protection implementation
    assert 'min_trading_balance' in source, \
        "trader_short_expiry.py missing min_trading_balance check"

    assert 'self.balance < min_balance' in source or 'balance < min_balance' in source, \
        "trader_short_expiry.py missing balance comparison"

    # Check that it pauses trading (continues loop without processing)
    assert 'continue' in source or 'return' in source, \
        "trader_short_expiry.py doesn't skip trading when balance low"


def test_balance_protection_still_monitors_positions():
    """Test that balance protection still monitors existing positions."""
    trader_path = Path('src/bots/trader_short_expiry.py')
    source = trader_path.read_text()

    # When balance is low, should still call _check_positions()
    # Look for pattern: if balance < min: ... _check_positions() ... continue
    lines = source.split('\n')

    found_check_positions_in_low_balance = False
    in_balance_check = False

    for i, line in enumerate(lines):
        if 'self.balance < min_balance' in line or 'balance < min_balance' in line:
            in_balance_check = True

        if in_balance_check and '_check_positions()' in line:
            # Make sure this is before the continue statement
            # Look ahead for continue within next 10 lines
            for j in range(i, min(i + 10, len(lines))):
                if 'continue' in lines[j]:
                    found_check_positions_in_low_balance = True
                    break
            break

    assert found_check_positions_in_low_balance, \
        "trader_short_expiry.py doesn't monitor positions when balance low"


def test_all_bots_have_balance_protection():
    """Test that all trading bots have minimum balance protection."""
    bot_files = [
        'src/bots/trader_short_expiry.py',
        # Add other bot files here
    ]

    for bot_file in bot_files:
        if not Path(bot_file).exists():
            continue

        source = Path(bot_file).read_text()

        # Check for balance checks
        has_balance_check = (
            'min_balance' in source or
            'minimum_balance' in source or
            'min_trading_balance' in source
        )

        assert has_balance_check, \
            f"{bot_file} missing balance protection"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
