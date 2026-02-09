"""
Tests for PositionManager
"""

import pytest
from datetime import datetime, timezone
from position_manager import PositionManager


class TestPositionManager:
    """Test suite for PositionManager."""

    def test_initialization(self, temp_db):
        """Test position manager initialization."""
        pm = PositionManager(db_path=temp_db)

        assert pm.db_path == temp_db
        # Check that table was created
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='positions'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_position(self, temp_db):
        """Test saving a position to database."""
        pm = PositionManager(db_path=temp_db)

        entry_time = datetime.now(timezone.utc)
        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=entry_time,
            entry_price=0.35,
            side='YES',
            size=50.0,
            metadata={'question': 'Test market?', 'edge': 0.1}
        )

        # Verify it was saved
        positions = pm.load_positions()
        assert len(positions) == 1
        assert positions[0]['market_id'] == '0xmarket123'
        assert positions[0]['entry_price'] == 0.35
        assert positions[0]['side'] == 'YES'
        assert positions[0]['size'] == 50.0

    def test_load_positions(self, temp_db):
        """Test loading positions from database."""
        pm = PositionManager(db_path=temp_db)

        # Add multiple positions
        for i in range(3):
            pm.save_position(
                market_id=f'0xmarket{i}',
                token_id=f'0xtoken{i}',
                entry_time=datetime.now(timezone.utc),
                entry_price=0.3 + i * 0.05,
                side='YES' if i % 2 == 0 else 'NO',
                size=50.0 + i * 10
            )

        positions = pm.load_positions()
        assert len(positions) == 3

    def test_close_position(self, temp_db):
        """Test closing a position."""
        pm = PositionManager(db_path=temp_db)

        # Open position
        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0
        )

        # Close position
        pm.close_position(
            market_id='0xmarket123',
            exit_time=datetime.now(timezone.utc),
            exit_price=0.45,
            pnl=10.0,
            exit_reason='take_profit'
        )

        # Verify it's closed
        open_positions = pm.load_positions()
        assert len(open_positions) == 0

        # Check closed position data
        all_positions = pm.get_all_positions()
        assert len(all_positions) == 1
        assert all_positions[0]['status'] == 'CLOSED'
        assert all_positions[0]['pnl'] == 10.0

    def test_get_position(self, temp_db):
        """Test retrieving a specific position."""
        pm = PositionManager(db_path=temp_db)

        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0
        )

        position = pm.get_position('0xmarket123')

        assert position is not None
        assert position['market_id'] == '0xmarket123'
        assert position['entry_price'] == 0.35

    def test_get_statistics(self, temp_db):
        """Test getting position statistics."""
        pm = PositionManager(db_path=temp_db)

        # Add some positions
        for i in range(3):
            pm.save_position(
                market_id=f'0xmarket{i}',
                token_id=f'0xtoken{i}',
                entry_time=datetime.now(timezone.utc),
                entry_price=0.35,
                side='YES',
                size=50.0
            )

        # Close some with wins and losses
        pm.close_position('0xmarket0', datetime.now(), 0.45, 10.0)  # Win
        pm.close_position('0xmarket1', datetime.now(), 0.30, -5.0)  # Loss

        stats = pm.get_statistics()

        assert stats['open_positions'] == 1
        assert stats['closed_positions'] == 2
        assert stats['wins'] == 1
        assert stats['losses'] == 1
        assert stats['total_pnl'] == 5.0
        assert stats['win_rate'] == 50.0

    def test_update_price_extremes(self, temp_db):
        """Test updating price extremes for trailing stop."""
        pm = PositionManager(db_path=temp_db)

        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0
        )

        # Update with higher price
        extremes = pm.update_price_extremes('0xmarket123', 0.45)
        assert extremes['highest_price_seen'] == 0.45

        # Update with lower price
        extremes = pm.update_price_extremes('0xmarket123', 0.30)
        assert extremes['lowest_price_seen'] == 0.30
        assert extremes['highest_price_seen'] == 0.45  # Still highest

    def test_delete_position(self, temp_db):
        """Test deleting a position."""
        pm = PositionManager(db_path=temp_db)

        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0
        )

        pm.delete_position('0xmarket123')

        positions = pm.load_positions()
        assert len(positions) == 0

    def test_position_persistence_across_restarts(self, temp_db):
        """Test that positions persist across manager restarts."""
        # Create first manager and save position
        pm1 = PositionManager(db_path=temp_db)
        pm1.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0
        )

        # Create new manager instance (simulating restart)
        pm2 = PositionManager(db_path=temp_db)
        positions = pm2.load_positions()

        assert len(positions) == 1
        assert positions[0]['market_id'] == '0xmarket123'

    def test_exit_reason_tracking(self, temp_db):
        """Test that exit reasons are properly recorded."""
        pm = PositionManager(db_path=temp_db)

        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0
        )

        pm.close_position(
            market_id='0xmarket123',
            exit_time=datetime.now(),
            exit_price=0.25,
            pnl=-10.0,
            exit_reason='stop_loss'
        )

        exit_reason = pm.get_exit_reason('0xmarket123')
        assert exit_reason == 'stop_loss'

    def test_metadata_storage(self, temp_db):
        """Test that position metadata is properly stored and retrieved."""
        pm = PositionManager(db_path=temp_db)

        metadata = {
            'question': 'Will BTC hit $100k?',
            'confidence': 0.7,
            'edge': 0.15,
            'asset': 'BTC'
        }

        pm.save_position(
            market_id='0xmarket123',
            token_id='0xtoken123',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.35,
            side='YES',
            size=50.0,
            metadata=metadata
        )

        positions = pm.load_positions()
        assert positions[0]['metadata'] == metadata
