#!/usr/bin/env python3
"""
Verify that the short-expiry bot can collect training data.

Checks:
1. Database schema is correct
2. Feature extraction works
3. Position tracking works
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta

from src.features.short_expiry_features import ShortExpiryFeatureExtractor
from src.bots.trader_short_expiry import ShortExpiryPositionManager

def check_database_schema():
    """Verify database schema."""
    print("=" * 60)
    print("DATABASE SCHEMA CHECK")
    print("=" * 60)

    db_path = Path("data/positions_short_expiry.db")

    if not db_path.exists():
        print(f"✗ Database not found: {db_path}")
        return False

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check positions table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='positions'")
        if not cursor.fetchone():
            print("✗ Positions table not found")
            return False

        # Check columns
        cursor.execute("PRAGMA table_info(positions)")
        columns = {row[1] for row in cursor.fetchall()}

        required_cols = {'market_id', 'bucket', 'entry_price', 'entry_time',
                        'hours_to_expiry_at_entry', 'features_json'}

        missing = required_cols - columns
        if missing:
            print(f"✗ Missing columns: {missing}")
            return False

        print(f"✓ Database schema valid")
        print(f"  Columns: {len(columns)}")

        # Check existing data
        cursor.execute("SELECT COUNT(*) FROM positions")
        count = cursor.fetchone()[0]
        print(f"  Positions: {count}")

        return True

def check_feature_extraction():
    """Verify feature extraction."""
    print("\n" + "=" * 60)
    print("FEATURE EXTRACTION CHECK")
    print("=" * 60)

    # Create sample market
    now = datetime.now(timezone.utc)
    sample_market = {
        'conditionId': 'test_123',
        'question': 'Will BTC reach $100k?',
        'endDate': (now + timedelta(hours=12)).isoformat(),
        'volume24hr': 5000,
        'liquidity': 2000,
        'lastTradePrice': 0.65,
        'bestBid': 0.63,
        'bestAsk': 0.67,
        'active': True
    }

    try:
        extractor = ShortExpiryFeatureExtractor()

        for bucket in ['ultra_short', 'short', 'medium']:
            features = extractor.extract_all_features(sample_market, bucket)

            print(f"\n{bucket.upper()} Bucket:")
            print(f"  Features extracted: {len(features.columns)}")
            print(f"  Sample features: {list(features.columns)[:5]}")

        print(f"\n✓ Feature extraction working")
        return True

    except Exception as e:
        print(f"✗ Feature extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_position_tracking():
    """Verify position tracking."""
    print("\n" + "=" * 60)
    print("POSITION TRACKING CHECK")
    print("=" * 60)

    try:
        pm = ShortExpiryPositionManager(Path("data/positions_short_expiry.db"))

        # Get open positions
        positions = pm.get_open_positions()
        print(f"  Open positions: {len(positions)}")

        # Get positions by bucket
        for bucket in ['ultra_short', 'short', 'medium']:
            bucket_positions = [p for p in positions if p.get('bucket') == bucket]
            print(f"  {bucket}: {len(bucket_positions)} positions")

        print(f"\n✓ Position tracking working")
        return True

    except Exception as e:
        print(f"✗ Position tracking failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all checks."""
    print("\nSHORT-EXPIRY BOT DATA COLLECTION VERIFICATION\n")

    results = {
        'Database Schema': check_database_schema(),
        'Feature Extraction': check_feature_extraction(),
        'Position Tracking': check_position_tracking()
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {check}")

    all_passed = all(results.values())

    if all_passed:
        print("\n✅ All checks passed! Bot ready to collect training data.")
        print("\nNext steps:")
        print("1. Start bot: python src/bots/trader_short_expiry.py")
        print("2. Monitor: tail -f logs/short_expiry.out")
        print("3. After 500+ samples per bucket, train models")
    else:
        print("\n❌ Some checks failed. Fix issues before proceeding.")

    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
