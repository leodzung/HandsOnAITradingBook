#!/usr/bin/env python3
"""
Test Position Persistence
Verify positions survive bot restart.
"""

import os
import time
from datetime import datetime
from position_manager import PositionManager

def test_position_persistence():
    """Test that positions are saved and loaded correctly."""

    print("="*70)
    print("TESTING POSITION PERSISTENCE")
    print("="*70)

    # Use test database
    test_db = 'data/test_positions.db'

    # Clean up if exists
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"\n✓ Cleaned up old test database")

    # Test 1: Create positions
    print("\n--- Test 1: Creating Positions ---")
    pm1 = PositionManager(db_path=test_db)

    # Save 3 test positions
    pm1.save_position(
        market_id='market_001',
        token_id='token_001',
        entry_time=datetime.now(),
        entry_price=0.50,
        side='BUY',
        size=25.0,
        metadata={'test': True}
    )

    pm1.save_position(
        market_id='market_002',
        token_id='token_002',
        entry_time=datetime.now(),
        entry_price=0.65,
        side='SELL',
        size=30.0
    )

    pm1.save_position(
        market_id='market_003',
        token_id='token_003',
        entry_time=datetime.now(),
        entry_price=0.40,
        side='BUY',
        size=20.0
    )

    count = pm1.get_open_positions_count()
    print(f"✓ Created 3 positions, database shows: {count}")
    assert count == 3, "Should have 3 positions"

    # Test 2: Simulate restart (new instance)
    print("\n--- Test 2: Simulating Restart ---")
    print("Destroying first instance...")
    del pm1
    time.sleep(0.5)

    print("Creating new instance (simulates restart)...")
    pm2 = PositionManager(db_path=test_db)

    # Load positions
    positions = pm2.load_positions()
    print(f"✓ Loaded {len(positions)} positions after 'restart'")
    assert len(positions) == 3, "Should still have 3 positions"

    # Verify details
    print("\nLoaded positions:")
    for pos in positions:
        print(f"  - {pos['market_id']}: {pos['side']} ${pos['size']:.2f} @ ${pos['entry_price']:.3f}")

    # Test 3: Close a position
    print("\n--- Test 3: Closing Position ---")
    pm2.close_position(
        market_id='market_001',
        exit_time=datetime.now(),
        exit_price=0.55,
        pnl=1.25
    )

    open_count = pm2.get_open_positions_count()
    print(f"✓ Closed 1 position, open positions: {open_count}")
    assert open_count == 2, "Should have 2 open positions"

    # Test 4: Another restart
    print("\n--- Test 4: Another Restart ---")
    del pm2
    time.sleep(0.5)

    pm3 = PositionManager(db_path=test_db)
    positions = pm3.load_positions()
    print(f"✓ After second restart, open positions: {len(positions)}")
    assert len(positions) == 2, "Should have 2 open positions"

    # Test 5: Statistics
    print("\n--- Test 5: Statistics ---")
    stats = pm3.get_statistics()
    print(f"Open positions: {stats['open_positions']}")
    print(f"Closed positions: {stats['closed_positions']}")
    print(f"Total P&L: ${stats['total_pnl']:.2f}")
    print(f"Win rate: {stats['win_rate']:.1f}%")

    assert stats['open_positions'] == 2
    assert stats['closed_positions'] == 1
    assert stats['total_pnl'] == 1.25

    # Test 6: Get all positions
    print("\n--- Test 6: All Positions ---")
    all_positions = pm3.get_all_positions()
    print(f"Total positions (open + closed): {len(all_positions)}")
    for pos in all_positions:
        status = "OPEN" if pos['status'] == 'OPEN' else f"CLOSED (P&L: ${pos['pnl']:.2f})"
        print(f"  - {pos['market_id']}: {status}")

    assert len(all_positions) == 3

    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    print("\nPosition persistence is working correctly:")
    print("  ✓ Positions saved to database")
    print("  ✓ Positions loaded on restart")
    print("  ✓ Closed positions tracked")
    print("  ✓ Statistics calculated correctly")
    print("  ✓ Survives multiple restarts")

    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
        print(f"\n✓ Cleaned up test database")

    return True

if __name__ == '__main__':
    try:
        test_position_persistence()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
