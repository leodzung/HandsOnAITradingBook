"""
Tests for PositionManager V2 - Enhanced position tracking for all bots.

Converted from root-level print-based tests to proper pytest.
"""

import os
import sys
import sqlite3
import tempfile
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.position_manager_v2 import PositionManager, DuplicatePositionError


@pytest.fixture
def db_path():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def pm(db_path):
    """Create a PositionManager instance with temp DB."""
    return PositionManager(db_path)


class TestV2FreshInstall:
    """Test V2 with fresh database."""

    def test_save_position_with_analytics(self, pm):
        pm.save_position(
            market_id='test_market_1',
            token_id='token_yes',
            outcome='YES',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.45,
            size=50.0,
            edge=0.05,
            confidence=0.75,
            signal_reason='momentum',
            hours_to_expiry=24.0,
        )
        positions = pm.get_open_positions()
        assert len(positions) == 1

    def test_multiple_positions_per_market(self, pm):
        pm.save_position(
            market_id='test_market_1', token_id='token_yes', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=50.0,
        )
        pm.save_position(
            market_id='test_market_1', token_id='token_no', outcome='NO',
            entry_time=datetime.now(timezone.utc), entry_price=0.52, size=30.0,
        )
        positions = pm.get_open_positions()
        assert len(positions) == 2

    def test_analytics_fields_retrieved(self, pm):
        pm.save_position(
            market_id='test_market_1', token_id='token_yes', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=50.0,
            edge=0.05, confidence=0.75, signal_reason='momentum', hours_to_expiry=24.0,
        )
        pos = pm.get_position('test_market_1', 'YES')
        assert pos['edge'] == 0.05
        assert pos['confidence'] == 0.75
        assert pos['signal_reason'] == 'momentum'
        assert pos['hours_to_expiry_at_entry'] == 24.0

    def test_update_current_price(self, pm):
        pm.save_position(
            market_id='test_market_1', token_id='token_yes', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=50.0,
        )
        pm.update_current_price('test_market_1', 'YES', 0.50)
        pos = pm.get_position('test_market_1', 'YES')
        assert pos['current_price'] == 0.50

    def test_update_price_extremes(self, pm):
        pm.save_position(
            market_id='test_market_1', token_id='token_yes', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=50.0,
        )
        pm.update_price_extremes('test_market_1', 'YES', 0.55)
        pm.update_price_extremes('test_market_1', 'YES', 0.40)
        pos = pm.get_position('test_market_1', 'YES')
        assert pos['highest_price_seen'] == 0.55
        assert pos['lowest_price_seen'] == 0.40

    def test_close_position_pnl(self, pm):
        pm.save_position(
            market_id='test_market_1', token_id='token_yes', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=50.0,
        )
        pm.close_position(
            market_id='test_market_1', outcome='YES',
            exit_price=0.52, exit_reason='take_profit',
        )
        # get_position only returns OPEN, so check via get_statistics
        stats = pm.get_statistics()
        assert stats['closed_positions'] == 1
        assert stats['wins'] == 1
        assert stats['total_pnl'] == pytest.approx((0.52 - 0.45) * 50.0, abs=0.01)

    def test_statistics(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=50.0,
        )
        pm.save_position(
            market_id='m2', token_id='t2', outcome='NO',
            entry_time=datetime.now(timezone.utc), entry_price=0.52, size=30.0,
        )
        pm.close_position('m1', 'YES', exit_price=0.52, exit_reason='take_profit')
        stats = pm.get_statistics()
        assert stats['open_positions'] == 1
        assert stats['closed_positions'] == 1
        assert stats['wins'] == 1
        assert stats['win_rate'] == 100.0


class TestV1Migration:
    """Test migration from V1 to V2 schema."""

    def test_v1_buy_becomes_yes(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE positions (
                market_id TEXT PRIMARY KEY,
                token_id TEXT,
                entry_time TEXT,
                entry_price REAL,
                side TEXT,
                size REAL,
                status TEXT DEFAULT 'OPEN'
            )
        ''')
        conn.execute('''
            INSERT INTO positions (market_id, token_id, entry_time, entry_price, side, size, status)
            VALUES ('old_market', 'old_token', ?, 0.40, 'BUY', 100.0, 'OPEN')
        ''', (datetime.now(timezone.utc).isoformat(),))
        conn.commit()
        conn.close()

        pm = PositionManager(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        all_pos = [dict(r) for r in conn.execute("SELECT * FROM positions").fetchall()]
        conn.close()

        assert len(all_pos) == 1
        assert all_pos[0]['outcome'] == 'YES'
        assert all_pos[0]['status'].upper() == 'OPEN'

    def test_v1_backup_created(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE positions (
                market_id TEXT PRIMARY KEY, token_id TEXT, entry_time TEXT,
                entry_price REAL, side TEXT, size REAL, status TEXT DEFAULT 'OPEN'
            )
        ''')
        conn.commit()
        conn.close()

        PositionManager(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'positions_v1_backup%'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_can_add_v2_positions_after_migration(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE positions (
                market_id TEXT PRIMARY KEY, token_id TEXT, entry_time TEXT,
                entry_price REAL, side TEXT, size REAL, status TEXT DEFAULT 'OPEN'
            )
        ''')
        conn.execute('''
            INSERT INTO positions VALUES ('old', 'tok', ?, 0.40, 'BUY', 100.0, 'OPEN')
        ''', (datetime.now(timezone.utc).isoformat(),))
        conn.commit()
        conn.close()

        pm = PositionManager(db_path)
        pm.save_position(
            market_id='new_market', token_id='new_token', outcome='NO',
            entry_time=datetime.now(timezone.utc), entry_price=0.60, size=50.0,
        )
        positions = pm.get_open_positions()
        assert len(positions) == 2


class TestMetadataFiltering:
    """Test filtering positions by metadata."""

    def test_count_by_bucket(self, pm):
        for i, bucket in enumerate(['ultra_short', 'short', 'short', 'medium']):
            pm.save_position(
                market_id=f'market_{i}', token_id=f'token_{i}', outcome='YES',
                entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
                metadata={'bucket': bucket, 'strategy': 'momentum'},
            )

        assert pm.count_positions_by_metadata('bucket', 'ultra_short') == 1
        assert pm.count_positions_by_metadata('bucket', 'short') == 2
        assert pm.count_positions_by_metadata('bucket', 'medium') == 1

    def test_duplicate_position_raises(self, pm):
        pm.save_position(
            market_id='dup_market', token_id='tok', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        with pytest.raises(DuplicatePositionError):
            pm.save_position(
                market_id='dup_market', token_id='tok2', outcome='YES',
                entry_time=datetime.now(timezone.utc), entry_price=0.55, size=30.0,
            )
