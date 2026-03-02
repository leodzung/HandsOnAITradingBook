"""
RISK-005: Minimum expiry time at entry

Validates that bots don't enter positions too close to expiry.
"""

import pytest
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def test_short_expiry_minimum_discovery_hours():
    """Test that short-expiry bot has minimum hours in discovery config."""
    config_path = 'config/config_short_expiry.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    discovery = config['discovery']

    # Check ultra_short bucket has minimum > 0
    ultra_short_min = discovery['ultra_short_hours'][0]
    assert ultra_short_min >= 2.0, \
        f"ultra_short min hours too low: {ultra_short_min}h (should be >= 2h)"

    # Check short bucket
    short_min = discovery['short_hours'][0]
    assert short_min >= 24.0, \
        f"short min hours too low: {short_min}h (should be >= 24h)"

    # Check medium bucket
    medium_min = discovery['medium_hours'][0]
    assert medium_min >= 72.0, \
        f"medium min hours too low: {medium_min}h (should be >= 72h)"


def test_no_zero_expiry_entries():
    """Test that no positions were entered with < 2h to expiry (recent data)."""
    db_path = 'data/positions_short_expiry.db'

    if not Path(db_path).exists():
        pytest.skip("Database not found")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check recent positions (last 24h) for violations
    one_day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    cursor.execute('''
        SELECT market_id, hours_to_expiry_at_entry, entry_time
        FROM positions
        WHERE hours_to_expiry_at_entry < 2.0
        AND entry_time > ?
        ORDER BY entry_time DESC
        LIMIT 10
    ''', (one_day_ago,))

    violations = cursor.fetchall()
    conn.close()

    if violations:
        violation_details = '\n'.join([
            f"  - Market {m[:16]}... entered with {h:.2f}h at {t}"
            for m, h, t in violations
        ])
        pytest.fail(
            f"Found {len(violations)} recent positions entered with < 2h to expiry:\n"
            f"{violation_details}\n"
            f"RISK-005 violation: Bot entered too close to expiry"
        )


def test_pre_expiry_exit_reasonable():
    """Test that pre-expiry exit time leaves enough holding time."""
    config_path = 'config/config_short_expiry.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    pre_expiry_config = config['risk_management']['pre_expiry_exit_hours']
    ultra_short_min = config['discovery']['ultra_short_hours'][0]

    # Support both per-bucket dict and legacy scalar config
    if isinstance(pre_expiry_config, dict):
        pre_expiry_exit = pre_expiry_config.get('ultra_short', 1.0)
    else:
        pre_expiry_exit = pre_expiry_config

    # Minimum holding time = min_entry - pre_expiry_exit
    min_holding_time = ultra_short_min - pre_expiry_exit

    assert min_holding_time >= 2.0, \
        f"Minimum holding time too short: {min_holding_time}h " \
        f"(min_entry: {ultra_short_min}h, pre_exit: {pre_expiry_exit}h). " \
        f"Positions need >= 2h to reach take-profit."


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
