"""
Test short-expiry trading infrastructure.

This script validates:
1. Configuration loading
2. Feature extraction
3. Signal generation
4. Position management
5. Risk management
"""

import sys
import os
import json
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.features.short_expiry_features import ShortExpiryFeatureExtractor
from src.bots.trader_short_expiry import (
    ShortExpiryRiskManager,
    ShortExpiryTrader
)
from src.core.position_manager_v2 import PositionManager


def test_config_loading():
    """Test configuration loading."""
    print("=" * 60)
    print("TEST 1: Configuration Loading")
    print("=" * 60)

    config_path = 'config/config_short_expiry.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    print(f"✓ Config loaded from {config_path}")
    print(f"  - Paper trading: {config['paper_trading']}")
    print(f"  - Initial balance: ${config['paper_trading_balance']}")
    print(f"  - Buckets: {list(config['discovery']['min_volume'].keys())}")
    print(f"  - Max positions: {config['position_limits']['max_total_positions']}")
    print(f"  - Rules enabled: arbitrage={config['rules']['arbitrage']['enabled']}, "
          f"momentum={config['rules']['momentum']['enabled']}")
    print()


def test_feature_extraction():
    """Test feature extraction."""
    print("=" * 60)
    print("TEST 2: Feature Extraction")
    print("=" * 60)

    # Create sample market data
    sample_market = {
        'conditionId': 'test_market_123',
        'question': 'Will Bitcoin price be above $60,000 by end of day?',
        'endDate': (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        'volume24hr': '5000.0',
        'liquidity': '2500.0',
        'clobRewards': {
            'lastTradePrice': '0.65',
            'bestBid': '0.63',
            'bestAsk': '0.67'
        }
    }

    extractor = ShortExpiryFeatureExtractor()

    # Extract features for each bucket
    for bucket in ['ultra_short', 'short', 'medium']:
        features = extractor.extract_all_features(sample_market, bucket)

        print(f"\nBucket: {bucket}")
        print(f"  Total features: {len(features.columns)}")
        print(f"  Sample features:")
        print(f"    - hours_to_expiry: {features['hours_to_expiry'].iloc[0]:.2f}")
        print(f"    - urgency_score: {features['urgency_score'].iloc[0]:.3f}")
        print(f"    - market_probability: {features['market_probability'].iloc[0]:.3f}")
        print(f"    - spread: {features['spread'].iloc[0]:.4f}")
        print(f"    - spread_pct: {features['spread_pct'].iloc[0]:.2f}%")
        print(f"    - mid_price: {features['mid_price'].iloc[0]:.4f}")
        print(f"    - volume_24h: {features['volume_24h'].iloc[0]:.0f}")

    print("\n✓ Feature extraction working for all buckets")
    print()


def test_position_management():
    """Test position manager."""
    print("=" * 60)
    print("TEST 3: Position Management")
    print("=" * 60)

    # Create temporary database
    db_path = 'data/test_positions.db'
    if os.path.exists(db_path):
        os.remove(db_path)

    pm = PositionManager(db_path)
    now = datetime.now(timezone.utc)

    # Test: Add position
    pm.save_position(
        market_id='test_market_1',
        token_id='token_123',
        outcome='YES',
        entry_time=now,
        entry_price=0.65,
        size=50.0,
        bucket='ultra_short',
        hours_to_expiry=12.0,
        edge=0.05,
        confidence=0.70,
        signal_reason='arbitrage',
        metadata={'bucket': 'ultra_short'}
    )
    print("✓ Position added")

    # Test: Check has_position
    assert pm.has_position('test_market_1', 'YES'), "has_position check failed"
    print("✓ has_position check working")

    # Test: Get open positions
    open_positions = pm.get_open_positions()
    assert len(open_positions) == 1, f"Expected 1 position, got {len(open_positions)}"
    print(f"✓ Retrieved {len(open_positions)} open position(s)")

    # Test: Count by bucket
    count = pm.count_positions_by_metadata('bucket', 'ultra_short')
    assert count == 1, f"Expected 1 position in ultra_short, got {count}"
    print(f"✓ Bucket count: {count}")

    # Test: Update price
    pm.update_current_price('test_market_1', 'YES', 0.75)
    print("✓ Position price updated")

    # Test: Close position
    pm.close_position('test_market_1', 'YES', 0.80, 'take_profit')
    print("✓ Position closed")

    # Verify closed
    open_positions = pm.get_open_positions()
    assert len(open_positions) == 0, "Position not closed properly"
    print("✓ Position correctly marked as closed")

    # Cleanup
    os.remove(db_path)
    print()


def test_risk_management():
    """Test risk manager."""
    print("=" * 60)
    print("TEST 4: Risk Management")
    print("=" * 60)

    # Load config
    with open('config/config_short_expiry.json', 'r') as f:
        config = json.load(f)

    rm = ShortExpiryRiskManager(config)

    # Test: Position sizing
    size = rm.calculate_position_size(edge=0.08, confidence=0.70, bucket='ultra_short')
    print(f"✓ Position size calculated: ${size:.2f}")

    # Test: Can execute
    signal = {
        'edge': 0.05,
        'confidence': 0.60,
        'action': 'BUY'
    }
    can_exec = rm.can_execute(signal, balance=500.0, bucket='ultra_short')
    print(f"✓ Can execute check: {can_exec}")

    # Test: Low edge rejection
    low_edge_signal = {
        'edge': 0.01,
        'confidence': 0.60
    }
    can_exec = rm.can_execute(low_edge_signal, balance=500.0, bucket='ultra_short')
    assert not can_exec, "Should reject low edge signal"
    print(f"✓ Low edge signal correctly rejected")

    # Test: Exit conditions
    position = {
        'entry_price': 0.50,
        'hours_to_expiry_at_entry': 10.0
    }

    # Stop-loss
    exit_reason = rm.should_exit(position, current_price=0.40, bucket='ultra_short')
    assert exit_reason == 'stop_loss', f"Expected stop_loss, got {exit_reason}"
    print(f"✓ Stop-loss triggered correctly")

    # Take-profit
    exit_reason = rm.should_exit(position, current_price=0.70, bucket='ultra_short')
    assert exit_reason == 'take_profit', f"Expected take_profit, got {exit_reason}"
    print(f"✓ Take-profit triggered correctly")

    # No exit
    exit_reason = rm.should_exit(position, current_price=0.55, bucket='ultra_short')
    assert exit_reason is None, f"Expected None, got {exit_reason}"
    print(f"✓ No premature exit")

    # Test: Circuit breaker
    rm.consecutive_losses = 0
    for i in range(4):
        rm.update_consecutive_losses(is_loss=True)
    print(f"✓ Circuit breaker: {rm.consecutive_losses} consecutive losses")

    print()


def test_signal_generation():
    """Test signal generation."""
    print("=" * 60)
    print("TEST 5: Signal Generation")
    print("=" * 60)

    # Initialize trader
    trader = ShortExpiryTrader('config/config_short_expiry.json')

    # Test 1: Arbitrage signal
    print("\nTest 5.1: Arbitrage Signal")
    sample_market = {
        'conditionId': 'test_arb',
        'question': 'Will BTC be above $60k?',
        'endDate': (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
        'volume24hr': '1000.0',
        'liquidity': '500.0',
        'clobRewards': {
            'lastTradePrice': '0.45',  # YES price
            'bestBid': '0.44',
            'bestAsk': '0.46'
        }
    }

    features = trader.feature_extractor.extract_all_features(sample_market, 'ultra_short')
    signal = trader._generate_signal(features, sample_market, 'ultra_short')

    print(f"  Market: YES=0.45, NO=0.55, Total=1.00")
    print(f"  Signal: {signal['action']} | Outcome: {signal.get('outcome', 'N/A')} | "
          f"Reason: {signal['reason']}")

    # Test 2: Momentum signal
    print("\nTest 5.2: Momentum Signal")
    sample_market['clobRewards']['lastTradePrice'] = '0.60'

    features = trader.feature_extractor.extract_all_features(sample_market, 'ultra_short')
    # Manually add momentum feature
    features['price_change_1h'] = 0.03  # 3% move

    signal = trader._generate_signal(features, sample_market, 'ultra_short')
    print(f"  Price change 1h: +3%")
    print(f"  Signal: {signal['action']} | Outcome: {signal.get('outcome', 'N/A')} | "
          f"Reason: {signal['reason']}")

    # Test 3: No signal
    print("\nTest 5.3: No Signal (normal market)")
    sample_market['clobRewards']['lastTradePrice'] = '0.50'

    features = trader.feature_extractor.extract_all_features(sample_market, 'ultra_short')
    features['price_change_1h'] = 0.005  # 0.5% move

    signal = trader._generate_signal(features, sample_market, 'ultra_short')
    print(f"  Normal market conditions")
    print(f"  Signal: {signal['action']} | Reason: {signal['reason']}")

    print("\n✓ Signal generation working")
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SHORT-EXPIRY TRADING INFRASTRUCTURE TESTS")
    print("=" * 60 + "\n")

    try:
        test_config_loading()
        test_feature_extraction()
        test_position_management()
        test_risk_management()
        test_signal_generation()

        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
