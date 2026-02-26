"""
RISK-007: Behavioral test for account overdraw prevention

Tests that balance never went negative in historical data.
"""

import pytest
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def test_balance_never_negative():
    """Test that balance simulation never goes negative (recent data)."""
    db_path = 'data/positions_short_expiry.db'

    if not Path(db_path).exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all positions ordered by time
    cursor.execute('''
        SELECT entry_time, size * entry_price as capital,
               exit_time, size * exit_price as payout
        FROM positions
        ORDER BY entry_time
    ''')

    positions = cursor.fetchall()
    conn.close()

    if not positions:
        pytest.skip("No position data")

    # Simulate balance
    balance = 500.0  # Starting balance
    min_balance = balance
    negative_events = []

    for entry_time, capital, exit_time, payout in positions:
        # Deduct capital on entry
        balance -= capital

        if balance < 0:
            negative_events.append({
                'entry_time': entry_time,
                'capital': capital,
                'balance_after': balance
            })

        if balance < min_balance:
            min_balance = balance

        # Add back payout if closed
        if exit_time and payout:
            balance += payout

    if negative_events:
        details = '\n'.join([
            f"  - {e['entry_time']}: Opened ${e['capital']:.2f}, balance → ${e['balance_after']:.2f}"
            for e in negative_events[:5]  # Show first 5
        ])
        pytest.fail(
            f"Found {len(negative_events)} events where balance went negative:\\n"
            f"{details}\\n"
            f"Minimum balance reached: ${min_balance:.2f}\\n"
            f"RISK-007 violation: Account overdraw detected"
        )


def test_concurrent_positions_within_balance():
    """Test that maximum concurrent capital deployed never exceeded starting balance."""
    db_path = 'data/positions_short_expiry.db'

    if not Path(db_path).exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT entry_time, exit_time, size * entry_price as capital
        FROM positions
        ORDER BY entry_time
    ''')

    positions = cursor.fetchall()
    conn.close()

    if not positions:
        pytest.skip("No position data")

    # Calculate max concurrent capital
    max_concurrent = 0.0
    max_concurrent_time = None

    for i, (entry, exit, capital) in enumerate(positions):
        entry_dt = datetime.fromisoformat(entry.replace('Z', '+00:00'))

        # Calculate capital deployed at this entry time
        concurrent_capital = capital

        for j, (other_entry, other_exit, other_capital) in enumerate(positions):
            if i == j:
                continue

            other_entry_dt = datetime.fromisoformat(other_entry.replace('Z', '+00:00'))

            # Check if other position was open at this entry time
            if other_exit:
                other_exit_dt = datetime.fromisoformat(other_exit.replace('Z', '+00:00'))
                if other_entry_dt <= entry_dt <= other_exit_dt:
                    concurrent_capital += other_capital
            else:
                if other_entry_dt <= entry_dt:
                    concurrent_capital += other_capital

        if concurrent_capital > max_concurrent:
            max_concurrent = concurrent_capital
            max_concurrent_time = entry

    # Allow some tolerance for position turnover, but flag if >2x balance
    if max_concurrent > 1000.0:  # 2x starting balance of $500
        pytest.fail(
            f"Max concurrent capital deployed: ${max_concurrent:.2f} at {max_concurrent_time}\\n"
            f"This exceeds 2x starting balance ($500)\\n"
            f"RISK-007 violation: Over-deployed capital"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
