"""
RISK-004: Behavioral test for market cooldown

Tests that bots don't rapidly re-enter the same market.
"""

import pytest
import sys
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def test_no_rapid_reentry_in_recent_data():
    """Test that no markets were re-entered within cooldown period (recent data)."""
    db_path = 'data/positions_short_expiry.db'

    if not Path(db_path).exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all positions from last 48 hours, ordered by market and time
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()

    cursor.execute('''
        SELECT market_id, outcome, entry_time, exit_time
        FROM positions
        WHERE entry_time > ?
        ORDER BY market_id, entry_time
    ''', (two_days_ago,))

    positions = cursor.fetchall()
    conn.close()

    # Group by market + outcome
    market_positions = defaultdict(list)
    for market_id, outcome, entry_time, exit_time in positions:
        key = f"{market_id}_{outcome}"
        market_positions[key].append({
            'entry_time': datetime.fromisoformat(entry_time.replace('Z', '+00:00')),
            'exit_time': datetime.fromisoformat(exit_time.replace('Z', '+00:00')) if exit_time else None
        })

    # Check for rapid re-entries (< 1 hour between close and next entry)
    violations = []
    min_cooldown_hours = 0.5  # Minimum acceptable cooldown (30 min grace period)

    for key, pos_list in market_positions.items():
        if len(pos_list) < 2:
            continue

        for i in range(len(pos_list) - 1):
            current = pos_list[i]
            next_pos = pos_list[i + 1]

            if current['exit_time']:
                time_between = (next_pos['entry_time'] - current['exit_time']).total_seconds() / 3600

                if time_between < min_cooldown_hours:
                    violations.append({
                        'market': key,
                        'exit': current['exit_time'],
                        'next_entry': next_pos['entry_time'],
                        'hours_between': time_between
                    })

    if violations:
        violation_details = '\n'.join([
            f"  - Market {v['market'][:30]}...: Re-entered {v['hours_between']:.1f}h after close"
            for v in violations[:5]  # Show first 5
        ])
        pytest.fail(
            f"Found {len(violations)} rapid re-entry violations in last 48h:\n"
            f"{violation_details}\n"
            f"RISK-004 violation: Markets re-entered within cooldown period"
        )


def test_avg_trades_per_market_reasonable():
    """Test that average trades per market is reasonable (< 3)."""
    db_path = 'data/positions_short_expiry.db'

    if not Path(db_path).exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get trades per market from last 7 days
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    cursor.execute('''
        SELECT market_id, COUNT(*) as trade_count
        FROM positions
        WHERE entry_time > ?
        GROUP BY market_id
        HAVING trade_count > 3
        ORDER BY trade_count DESC
        LIMIT 10
    ''', (week_ago,))

    excessive_trading = cursor.fetchall()
    conn.close()

    if excessive_trading:
        details = '\n'.join([
            f"  - Market {m[:30]}...: {count} trades"
            for m, count in excessive_trading
        ])
        pytest.fail(
            f"Found {len(excessive_trading)} markets with >3 trades in last 7 days:\n"
            f"{details}\n"
            f"RISK-004 violation: Excessive trading in same markets (cooldown not working)"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
