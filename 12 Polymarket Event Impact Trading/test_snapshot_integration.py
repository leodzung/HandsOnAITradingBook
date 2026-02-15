#!/usr/bin/env python3
"""
Quick integration test for Market Snapshot Collector.

Verifies that the snapshot collector is properly integrated with the price-level bot.
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ml.snapshot_collector import MarketSnapshotCollector


def test_basic_functionality():
    """Test basic snapshot collector functionality."""
    print("=" * 60)
    print("SNAPSHOT COLLECTOR INTEGRATION TEST")
    print("=" * 60)

    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db = f.name

    try:
        # Initialize collector
        print("\n1. Initializing collector...")
        collector = MarketSnapshotCollector(db_path=test_db)
        print("   ✓ Collector initialized")

        # Log a test snapshot (simulating price-level bot)
        print("\n2. Logging test snapshot...")
        snapshot_id = collector.log_snapshot(
            market_id='0xTEST123',
            bot_type='price_level',
            features={
                'volatility_30d': 0.45,
                'rsi_14': 65.5,
                'spread': 0.05,
                'volume_24h': 10000,
                'strike_distance_pct': 0.15
            },
            prediction={
                'model_prob': 0.65,
                'confidence': 0.75,
                'edge': 0.15,
                'predicted_outcome': 'YES'
            },
            market_data={
                'question': 'Will BTC hit $100k by Dec 31?',
                'asset': 'BTC',
                'strike_price': 100000.0,
                'expiry_date': (datetime.now() + timedelta(days=320)).isoformat(),
                'days_to_expiry': 320,
                'market_type': 'threshold',
                'condition_id': '0xTEST123',
                'token_id': '0xTOKEN456'
            },
            prices={
                'yes': 0.50,
                'no': 0.50
            },
            position_opened=False,
            rejection_reason='exposure_limit'
        )
        print(f"   ✓ Snapshot logged (ID: {snapshot_id})")

        # Get statistics
        print("\n3. Checking statistics...")
        stats = collector.get_statistics()
        print(f"   Total snapshots: {stats['total_snapshots']}")
        print(f"   Unique markets: {stats['unique_markets']}")
        print(f"   Trades blocked: {stats['trades_blocked']}")

        assert stats['total_snapshots'] == 1, "Should have 1 snapshot"
        assert stats['trades_blocked'] == 1, "Should have 1 blocked trade"
        print("   ✓ Statistics correct")

        # Test outcome recording
        print("\n4. Recording test outcome...")
        collector.record_outcome(
            snapshot_id=snapshot_id,
            outcome='YES',
            resolution_price=1.0
        )
        print("   ✓ Outcome recorded")

        # Verify labeling
        stats = collector.get_statistics()
        assert stats['labeled_snapshots'] == 1, "Should have 1 labeled snapshot"
        print("   ✓ Labeling verified")

        # Test data export
        print("\n5. Testing data export...")
        df = collector.get_training_data(labeled_only=True)
        assert len(df) == 1, "Should have 1 row"
        assert 'volatility_30d' in df.columns, "Features should be expanded"
        assert 'outcome' in df.columns, "Outcome should be present"
        assert df['outcome'].iloc[0] == 'YES', "Outcome should be YES"
        print(f"   ✓ Exported {len(df)} rows with {len(df.columns)} columns")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)
        print("\nSnapshot collector is working correctly!")
        print("Ready for production use with price-level bot.")

    finally:
        # Cleanup
        import os
        os.unlink(test_db)


def test_import_integration():
    """Test that price-level bot can import snapshot collector."""
    print("\n" + "=" * 60)
    print("IMPORT INTEGRATION TEST")
    print("=" * 60)

    try:
        print("\nTesting imports...")
        from ml.snapshot_collector import MarketSnapshotCollector
        print("   ✓ MarketSnapshotCollector imported")

        # Note: We can't import PriceLevelTrader without full dependencies
        # Just verify the snapshot collector module exists
        from pathlib import Path
        price_level_bot = Path(__file__).parent / 'src' / 'bots' / 'trader_price_levels.py'
        assert price_level_bot.exists(), "Price-level bot file should exist"

        # Check for integration code
        with open(price_level_bot) as f:
            content = f.read()
            assert 'MarketSnapshotCollector' in content, "Should import snapshot collector"
            assert 'snapshot_collector.log_snapshot' in content, "Should log snapshots"
            assert 'snapshot_collector.record_outcome' in content, "Should record outcomes"

        print("   ✓ Price-level bot integration verified")

        print("\n" + "=" * 60)
        print("IMPORT INTEGRATION PASSED ✅")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        raise


if __name__ == '__main__':
    test_basic_functionality()
    test_import_integration()

    print("\n" + "=" * 60)
    print("FINAL VERDICT: READY FOR PRODUCTION ✅")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Restart price-level bot to enable snapshot collection")
    print("2. Monitor: python3 view_snapshots.py")
    print("3. Check logs: tail -f logs/trader_price_levels.log")
    print("4. Wait 1 week to collect initial dataset")
    print("5. Export labeled data when markets resolve")
    print("6. Retrain model with real-world data")
