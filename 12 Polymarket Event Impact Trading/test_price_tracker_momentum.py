#!/usr/bin/env python3
"""
Test script for PriceTracker momentum features.

Tests the new track_price and get_price_history methods.
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from utils.price_tracker import PriceTracker

def test_price_tracking():
    """Test price tracking and history retrieval."""
    print("\n" + "=" * 70)
    print("TESTING PRICE TRACKER MOMENTUM FEATURES")
    print("=" * 70 + "\n")

    # Use test database
    tracker = PriceTracker(db_path='data/price_tracking_test.db')

    # Test market
    test_market_id = '0xtest_market_momentum_123'

    print("1. Testing track_price()...")
    print("-" * 70)

    # Track 10 price snapshots over simulated time
    test_prices = [0.45, 0.46, 0.47, 0.48, 0.49, 0.50, 0.51, 0.52, 0.53, 0.54]

    for i, price in enumerate(test_prices):
        tracker.track_price(test_market_id, price)
        print(f"  Snapshot {i+1}/10: ${price:.2f}")
        time.sleep(0.1)  # Small delay to ensure different timestamps

    print("✓ Successfully tracked 10 price snapshots\n")

    print("2. Testing get_price_history()...")
    print("-" * 70)

    # Retrieve price history
    history = tracker.get_price_history(test_market_id, hours=24)

    if history is not None:
        print(f"✓ Retrieved {len(history)} price snapshots")
        print(f"\nPrice History:")
        print(history.to_string(index=False))
        print()

        # Verify data
        assert len(history) == 10, "Should have 10 snapshots"
        assert 'price' in history.columns, "Should have 'price' column"
        assert 'timestamp' in history.columns, "Should have 'timestamp' column"
        assert history['price'].iloc[0] == 0.45, "First price should be 0.45"
        assert history['price'].iloc[-1] == 0.54, "Last price should be 0.54"

        print("✓ All assertions passed\n")
    else:
        print("✗ Failed to retrieve price history")
        return False

    print("3. Testing momentum calculation with price history...")
    print("-" * 70)

    # Calculate some basic momentum features
    prices = history['price'].values

    price_change = prices[-1] - prices[0]
    price_change_pct = (price_change / prices[0]) * 100
    velocity = (prices[-1] - prices[-3]) / 2.0 if len(prices) >= 3 else 0

    print(f"  Initial price:     ${prices[0]:.3f}")
    print(f"  Final price:       ${prices[-1]:.3f}")
    print(f"  Price change:      ${price_change:.3f}")
    print(f"  Price change %:    {price_change_pct:+.1f}%")
    print(f"  Velocity:          {velocity:.4f}")
    print()

    print("✓ Momentum features calculated successfully\n")

    print("4. Testing cleanup_old_snapshots()...")
    print("-" * 70)

    # Test cleanup (should delete nothing since data is fresh)
    deleted = tracker.cleanup_old_snapshots(days=0)  # Delete snapshots older than 0 days
    print(f"✓ Cleanup completed: {deleted} old snapshots deleted\n")

    print("5. Testing with non-existent market...")
    print("-" * 70)

    history_empty = tracker.get_price_history('0xnonexistent', hours=24)
    if history_empty is None:
        print("✓ Correctly returns None for market with no history\n")
    else:
        print("✗ Should return None for non-existent market")
        return False

    print("=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print()

    # Clean up test database
    import os
    if os.path.exists('data/price_tracking_test.db'):
        os.remove('data/price_tracking_test.db')
        print("Test database cleaned up.\n")

    return True


if __name__ == '__main__':
    success = test_price_tracking()
    sys.exit(0 if success else 1)
