"""
RISK-007: Sufficient balance validation before trade

Validates that bots check balance >= position_size before opening positions.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def test_short_expiry_has_balance_check():
    """Test that short-expiry bot validates balance before opening position."""
    trader_path = Path('src/bots/trader_short_expiry.py')
    source = trader_path.read_text()

    # Check for balance validation before deducting
    assert 'if self.balance < size' in source, \
        "trader_short_expiry.py missing 'if self.balance < size' check"

    # Check that insufficient balance is handled
    assert 'Insufficient balance' in source or 'insufficient_balance' in source, \
        "trader_short_expiry.py missing insufficient balance handling"

    # Check that the trade is skipped (return statement after balance check)
    lines = source.split('\n')
    found_pattern = False

    for i, line in enumerate(lines):
        if 'if self.balance < size' in line:
            # Look for return statement within next 20 lines
            for j in range(i, min(i + 20, len(lines))):
                if 'return' in lines[j]:
                    # Check if there's a comment about skipping on this line or nearby
                    context = '\n'.join(lines[max(0, j-1):j+2])
                    if 'skip' in context.lower():
                        found_pattern = True
                        break
            break

    assert found_pattern, \
        "trader_short_expiry.py doesn't return/skip trade when balance insufficient"


def test_balance_check_before_deduction():
    """Test that balance check happens BEFORE balance -= size."""
    trader_path = Path('src/bots/trader_short_expiry.py')
    source = trader_path.read_text()

    lines = source.split('\n')

    balance_check_line = None
    balance_deduct_line = None

    for i, line in enumerate(lines):
        if 'if self.balance < size' in line and balance_check_line is None:
            balance_check_line = i
        if 'self.balance -= size' in line and balance_deduct_line is None:
            balance_deduct_line = i

    assert balance_check_line is not None, "No balance check found"
    assert balance_deduct_line is not None, "No balance deduction found"
    assert balance_check_line < balance_deduct_line, \
        f"Balance check (line {balance_check_line}) must come BEFORE deduction (line {balance_deduct_line})"


def test_telemetry_for_rejected_trades():
    """Test that rejected trades are logged for telemetry."""
    trader_path = Path('src/bots/trader_short_expiry.py')
    source = trader_path.read_text()

    # Check for telemetry recording
    assert 'record_trade_rejected' in source or 'rejected_trades' in source.lower(), \
        "trader_short_expiry.py missing telemetry for rejected trades"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
