#!/usr/bin/env python3
"""
Test snapshot collector integration across all three bots.
Verifies that all bots can log snapshots with correct bot_type.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ml.snapshot_collector import MarketSnapshotCollector

def test_bot_type_consistency():
    """Verify bot_type values match database schema."""
    collector = MarketSnapshotCollector(db_path='data/test_snapshots.db')
    
    # Expected bot types from database schema
    expected_bot_types = {'event', 'price_level', 'short_expiry'}
    
    # Test data for each bot
    test_cases = [
        {
            'bot_type': 'event',
            'market_id': 'test_market_event_001',
            'features': {'spread_pct': 0.05, 'volume_24h': 1000},
            'prediction': {'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.10, 'predicted_outcome': 'YES'},
            'market_data': {'question': 'Test event market?', 'days_to_expiry': 5},
            'prices': {'yes': 0.60, 'no': 0.45}
        },
        {
            'bot_type': 'price_level',
            'market_id': 'test_market_price_001',
            'features': {'spread_pct': 0.03, 'volume_24h': 2000},
            'prediction': {'model_prob': 0.70, 'confidence': 0.80, 'edge': 0.15, 'predicted_outcome': 'YES'},
            'market_data': {'question': 'Test price level market?', 'days_to_expiry': 10, 'strike_price': 50000},
            'prices': {'yes': 0.55, 'no': 0.50}
        },
        {
            'bot_type': 'short_expiry',
            'market_id': 'test_market_short_001',
            'features': {'spread_pct': 0.02, 'volume_24h': 5000},
            'prediction': {'model_prob': 0.60, 'confidence': 0.70, 'edge': 0.08, 'predicted_outcome': 'NO'},
            'market_data': {'question': 'Test short expiry market?', 'days_to_expiry': 0.5},
            'prices': {'yes': 0.45, 'no': 0.58}
        }
    ]
    
    print("Testing snapshot collector integration across all bots...\n")
    
    for test_case in test_cases:
        bot_type = test_case['bot_type']
        print(f"Testing {bot_type} bot...")
        
        # Verify bot_type is valid
        assert bot_type in expected_bot_types, f"Invalid bot_type: {bot_type}"
        
        # Log snapshot
        snapshot_id = collector.log_snapshot(**test_case)
        
        if snapshot_id > 0:
            print(f"  ✅ Snapshot {snapshot_id} logged successfully")
        else:
            print(f"  ⚠️  Snapshot not logged (might be duplicate)")
    
    # Verify statistics show all three bot types
    print("\n" + "="*60)
    stats = collector.get_statistics()
    print(f"Total Snapshots: {stats['total_snapshots']}")
    print(f"By Bot Type:")
    for bot_type, counts in stats['by_bot_type'].items():
        print(f"  {bot_type}: {counts['total']} total")
    
    # Verify all expected bot types are present
    actual_bot_types = set(stats['by_bot_type'].keys())
    assert actual_bot_types == expected_bot_types, \
        f"Bot type mismatch! Expected: {expected_bot_types}, Got: {actual_bot_types}"
    
    print("\n✅ All tests passed! All three bots are using consistent bot_type identifiers.")
    print("="*60)
    
    # Clean up test database
    import os
    os.remove('data/test_snapshots.db')
    print("Test database cleaned up.")

if __name__ == '__main__':
    test_bot_type_consistency()
