"""
Regression tests for PositionManager V2 bug fixes.

BUG 1: update_price_extremes() was returning None, callers dereferenced it
BUG 2: get_position() had no status filter, returned closed positions
BUG 3: count_positions_by_metadata() used fragile LIKE instead of json_extract()
"""

import os
import sys
import tempfile
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.position_manager_v2 import PositionManager


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def pm(db_path):
    return PositionManager(db_path)


class TestBug1UpdatePriceExtremesReturn:
    """BUG 1: update_price_extremes() must return dict, not None."""

    def test_returns_dict_with_correct_keys(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        result = pm.update_price_extremes('m1', 'YES', 0.55)
        assert isinstance(result, dict)
        assert 'highest_price_seen' in result
        assert 'lowest_price_seen' in result

    def test_returns_correct_highest(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        result = pm.update_price_extremes('m1', 'YES', 0.60)
        assert result['highest_price_seen'] == 0.60

    def test_returns_correct_lowest(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        result = pm.update_price_extremes('m1', 'YES', 0.40)
        assert result['lowest_price_seen'] == 0.40

    def test_tracks_both_extremes_across_updates(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        pm.update_price_extremes('m1', 'YES', 0.60)
        pm.update_price_extremes('m1', 'YES', 0.40)
        result = pm.update_price_extremes('m1', 'YES', 0.55)
        assert result['highest_price_seen'] == 0.60
        assert result['lowest_price_seen'] == 0.40

    def test_returns_none_for_nonexistent_position(self, pm):
        result = pm.update_price_extremes('nonexistent', 'YES', 0.50)
        assert result is None

    def test_callers_can_safely_use_get(self, pm):
        """Simulate what trader.py does: extremes.get('highest_price_seen')."""
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        extremes = pm.update_price_extremes('m1', 'YES', 0.55)
        # This is exactly what trader.py:1177 does — would crash with None
        highest = extremes.get('highest_price_seen')
        assert highest == 0.55


class TestBug2GetPositionStatusFilter:
    """BUG 2: get_position() must return OPEN position, not closed."""

    def test_returns_open_not_closed(self, pm):
        # Open and close a position
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.40, size=50.0,
        )
        pm.close_position('m1', 'YES', exit_price=0.50, exit_reason='take_profit')

        # Re-open same market/outcome
        pm.save_position(
            market_id='m1', token_id='t2', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.45, size=60.0,
        )

        pos = pm.get_position('m1', 'YES')
        assert pos is not None
        assert pos['status'].upper() == 'OPEN'
        assert pos['entry_price'] == 0.45
        assert pos['token_id'] == 't2'

    def test_returns_none_when_only_closed(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.40, size=50.0,
        )
        pm.close_position('m1', 'YES', exit_price=0.50, exit_reason='take_profit')

        pos = pm.get_position('m1', 'YES')
        assert pos is None

    def test_returns_none_when_no_position(self, pm):
        pos = pm.get_position('nonexistent', 'YES')
        assert pos is None


class TestBug3MetadataJsonExtract:
    """BUG 3: count_positions_by_metadata() must use json_extract(), not LIKE."""

    def test_basic_bucket_counting(self, pm):
        for i, bucket in enumerate(['short', 'short', 'medium']):
            pm.save_position(
                market_id=f'm{i}', token_id=f't{i}', outcome='YES',
                entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
                metadata={'bucket': bucket},
            )
        assert pm.count_positions_by_metadata('bucket', 'short') == 2
        assert pm.count_positions_by_metadata('bucket', 'medium') == 1

    def test_no_substring_false_match(self, pm):
        """'short' must NOT match 'ultra_short' via json_extract (it did with LIKE)."""
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
            metadata={'bucket': 'ultra_short'},
        )
        # With json_extract, exact match only
        assert pm.count_positions_by_metadata('bucket', 'short') == 0
        assert pm.count_positions_by_metadata('bucket', 'ultra_short') == 1

    def test_compact_json_format(self, pm):
        """Works regardless of JSON spacing (json.dumps with separators)."""
        import sqlite3
        import json

        # Manually insert with compact JSON (no spaces after colon)
        conn = sqlite3.connect(pm.db_path)
        compact_json = json.dumps({'bucket': 'short'}, separators=(',', ':'))
        conn.execute('''
            INSERT INTO positions (market_id, token_id, outcome, entry_time, entry_price, size, status, metadata)
            VALUES ('m1', 't1', 'YES', ?, 0.50, 50.0, 'OPEN', ?)
        ''', (datetime.now(timezone.utc).isoformat(), compact_json))
        conn.commit()
        conn.close()

        assert pm.count_positions_by_metadata('bucket', 'short') == 1

    def test_ignores_closed_positions(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
            metadata={'bucket': 'short'},
        )
        pm.close_position('m1', 'YES', exit_price=0.55, exit_reason='take_profit')

        assert pm.count_positions_by_metadata('bucket', 'short') == 0

    def test_no_metadata_returns_zero(self, pm):
        pm.save_position(
            market_id='m1', token_id='t1', outcome='YES',
            entry_time=datetime.now(timezone.utc), entry_price=0.50, size=50.0,
        )
        assert pm.count_positions_by_metadata('bucket', 'short') == 0
