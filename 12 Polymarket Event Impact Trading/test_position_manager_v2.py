#!/usr/bin/env python3
"""Test PositionManager V2 - Enhanced position tracking for all bots."""

import sys
import os
from datetime import datetime, timezone, timedelta
import tempfile

sys.path.insert(0, 'src')

from core.position_manager_v2 import PositionManager

def test_v2_fresh_install():
    """Test V2 with fresh database."""
    print("\n" + "="*80)
    print("TEST 1: Fresh Install (V2 Schema)")
    print("="*80)

    # Create temp database
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        pm = PositionManager(db_path)

        # Test 1: Save position
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
            hours_to_expiry=24.0
        )
        print("✅ Saved position with analytics fields")

        # Test 2: Multiple positions per market
        pm.save_position(
            market_id='test_market_1',  # Same market!
            token_id='token_no',
            outcome='NO',  # Different outcome
            entry_time=datetime.now(timezone.utc),
            entry_price=0.52,
            size=30.0,
            edge=0.03,
            confidence=0.65,
            signal_reason='arbitrage'
        )
        print("✅ Saved second position on same market (YES and NO)")

        # Test 3: Load positions
        positions = pm.get_open_positions()
        assert len(positions) == 2, f"Expected 2 positions, got {len(positions)}"
        print(f"✅ Loaded {len(positions)} positions")

        # Test 4: Check individual position
        yes_pos = pm.get_position('test_market_1', 'YES')
        assert yes_pos is not None
        assert yes_pos['edge'] == 0.05
        assert yes_pos['confidence'] == 0.75
        assert yes_pos['signal_reason'] == 'momentum'
        assert yes_pos['hours_to_expiry_at_entry'] == 24.0
        print("✅ Analytics fields retrieved correctly")

        # Test 5: Update price
        pm.update_current_price('test_market_1', 'YES', 0.50)
        yes_pos = pm.get_position('test_market_1', 'YES')
        assert yes_pos['current_price'] == 0.50
        print("✅ Current price updated")

        # Test 6: Update price extremes
        pm.update_price_extremes('test_market_1', 'YES', 0.55)  # New high
        pm.update_price_extremes('test_market_1', 'YES', 0.40)  # New low
        yes_pos = pm.get_position('test_market_1', 'YES')
        assert yes_pos['highest_price_seen'] == 0.55
        assert yes_pos['lowest_price_seen'] == 0.40
        print("✅ Price extremes tracked correctly")

        # Test 7: Close position
        pm.close_position(
            market_id='test_market_1',
            outcome='YES',
            exit_price=0.52,
            exit_reason='take_profit'
        )
        yes_pos = pm.get_position('test_market_1', 'YES')
        assert yes_pos['status'] == 'closed'
        assert yes_pos['pnl'] == (0.52 - 0.45) * 50.0  # $3.50
        assert abs(yes_pos['pnl_pct'] - 15.56) < 0.1  # ~15.56%
        print(f"✅ Position closed: P&L=${yes_pos['pnl']:.2f} ({yes_pos['pnl_pct']:.2f}%)")

        # Test 8: Statistics
        stats = pm.get_statistics()
        assert stats['open_positions'] == 1  # Only NO position left
        assert stats['closed_positions'] == 1
        assert stats['wins'] == 1
        assert stats['win_rate'] == 100.0
        print(f"✅ Statistics: {stats['closed_positions']} closed, {stats['win_rate']:.1f}% win rate")

        print("\n✅ ALL V2 TESTS PASSED!")

    finally:
        os.unlink(db_path)


def test_v1_to_v2_migration():
    """Test migration from V1 to V2 schema."""
    print("\n" + "="*80)
    print("TEST 2: V1 → V2 Migration")
    print("="*80)

    # Create temp database with V1 schema
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        import sqlite3

        # Create V1 schema (old format)
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

        # Insert V1 data
        conn.execute('''
            INSERT INTO positions (market_id, token_id, entry_time, entry_price, side, size, status)
            VALUES ('old_market', 'old_token', ?, 0.40, 'BUY', 100.0, 'OPEN')
        ''', (datetime.now(timezone.utc).isoformat(),))

        conn.commit()
        conn.close()
        print("✅ Created V1 database with 1 position (side='BUY')")

        # Now initialize V2 manager - should auto-migrate
        pm = PositionManager(db_path)

        # Check migration happened
        positions = pm.get_open_positions()
        print(f"DEBUG: Found {len(positions)} open positions")
        if len(positions) > 0:
            print(f"DEBUG: First position: {positions[0]}")

        # Check all positions (including closed)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM positions")
        all_pos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        print(f"DEBUG: Total positions in DB: {len(all_pos)}")
        if len(all_pos) > 0:
            print(f"DEBUG: Position status: {all_pos[0]['status']}")
            print(f"DEBUG: Position outcome: {all_pos[0]['outcome']}")

        assert len(all_pos) == 1
        assert all_pos[0]['outcome'] == 'YES'  # BUY → YES
        assert all_pos[0]['status'].upper() == 'OPEN'
        assert 'side' not in all_pos[0]  # No more 'side' field
        print("✅ V1 position migrated: BUY → YES")

        # Verify backup was created
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'positions_v1_backup%'")
        backup_table = cursor.fetchone()
        conn.close()
        assert backup_table is not None
        print(f"✅ V1 backup created: {backup_table[0]}")

        # Add new V2 position
        pm.save_position(
            market_id='new_market',
            token_id='new_token',
            outcome='NO',
            entry_time=datetime.now(timezone.utc),
            entry_price=0.60,
            size=50.0,
            edge=0.04,
            confidence=0.70
        )

        positions = pm.get_open_positions()
        assert len(positions) == 2
        print("✅ Can add new V2 positions after migration")

        print("\n✅ MIGRATION TEST PASSED!")

    finally:
        os.unlink(db_path)


def test_metadata_filtering():
    """Test filtering positions by metadata (e.g., bucket)."""
    print("\n" + "="*80)
    print("TEST 3: Metadata Filtering (Bucket Counting)")
    print("="*80)

    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    try:
        pm = PositionManager(db_path)

        # Add positions with different buckets
        for i, bucket in enumerate(['ultra_short', 'short', 'short', 'medium']):
            pm.save_position(
                market_id=f'market_{i}',
                token_id=f'token_{i}',
                outcome='YES',
                entry_time=datetime.now(timezone.utc),
                entry_price=0.50,
                size=50.0,
                metadata={'bucket': bucket, 'strategy': 'momentum'}
            )

        # Count by bucket
        ultra_short_count = pm.count_positions_by_metadata('bucket', 'ultra_short')
        short_count = pm.count_positions_by_metadata('bucket', 'short')
        medium_count = pm.count_positions_by_metadata('bucket', 'medium')

        assert ultra_short_count == 1
        assert short_count == 2
        assert medium_count == 1

        print(f"✅ Bucket counts: ultra_short={ultra_short_count}, short={short_count}, medium={medium_count}")

        print("\n✅ METADATA FILTERING TEST PASSED!")

    finally:
        os.unlink(db_path)


if __name__ == '__main__':
    print("\n🧪 Testing Enhanced PositionManager V2")
    print("="*80)

    test_v2_fresh_install()
    test_v1_to_v2_migration()
    test_metadata_filtering()

    print("\n" + "="*80)
    print("🎉 ALL TESTS PASSED! PositionManager V2 is ready for deployment")
    print("="*80)
    print("\nNext steps:")
    print("1. Backup existing position databases")
    print("2. Replace 'from core.position_manager import' with 'from core.position_manager_v2 import'")
    print("3. Update bot code to use new API (outcome instead of side)")
    print("4. Restart bots - migration will happen automatically")
