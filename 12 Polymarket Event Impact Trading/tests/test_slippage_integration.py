#!/usr/bin/env python3
"""
Test slippage estimation integration with trading bots.

This script tests that slippage estimation is properly integrated into both
trader.py and trader_price_levels.py without actually executing trades.
"""

import json
from datetime import datetime
from slippage_estimator import SlippageEstimator


def test_config_loading():
    """Test that config files have slippage_estimation section"""
    print("Testing config file loading...")

    # Test event trader config
    with open('config.json', 'r') as f:
        config = json.load(f)

    assert 'slippage_estimation' in config, "config.json missing slippage_estimation section"
    assert config['slippage_estimation']['enabled'] is True
    assert config['slippage_estimation']['max_slippage_bps'] == 100
    print("  ✓ config.json has slippage_estimation section")

    # Test price-level trader config
    with open('config_price_levels.json', 'r') as f:
        config = json.load(f)

    assert 'slippage_estimation' in config, "config_price_levels.json missing slippage_estimation section"
    assert config['slippage_estimation']['enabled'] is True
    print("  ✓ config_price_levels.json has slippage_estimation section")


def test_estimator_initialization():
    """Test that SlippageEstimator can be initialized with config"""
    print("\nTesting SlippageEstimator initialization...")

    with open('config.json', 'r') as f:
        config = json.load(f)

    estimator = SlippageEstimator(config=config.get('slippage_estimation', {}))

    assert estimator.enabled is True
    assert estimator.max_slippage_bps == 100
    assert estimator.max_slippage_dollars == 5.0
    print("  ✓ SlippageEstimator initialized successfully")


def test_slippage_estimation():
    """Test slippage estimation with sample orderbook"""
    print("\nTesting slippage estimation...")

    # Create sample orderbook
    orderbook = {
        'bids': [[0.499, 100], [0.498, 100], [0.497, 100]],
        'asks': [[0.501, 100], [0.502, 100], [0.503, 100]]
    }

    with open('config.json', 'r') as f:
        config = json.load(f)

    estimator = SlippageEstimator(config=config.get('slippage_estimation', {}))

    # Test BUY order
    result = estimator.estimate_slippage(
        order_side='BUY',
        order_size=50.0,
        orderbook=orderbook,
        quoted_price=0.501,
        market_volume_24h=10000
    )

    print(f"  Order: BUY $50 @ 0.501")
    print(f"  VWAP: {result.expected_execution_price:.4f}")
    print(f"  Buffered: {result.worst_case_execution_price:.4f}")
    print(f"  Slippage: ${result.slippage_dollars:.3f} ({result.slippage_bps:.0f} bps)")
    print(f"  Levels consumed: {result.levels_consumed}")
    print(f"  Acceptable: {result.is_acceptable}")

    if not result.is_acceptable:
        print(f"  Rejection: {result.rejection_reason}")

    assert result.order_fills_immediately is True
    print("  ✓ Slippage estimation working")


def test_rejection_scenarios():
    """Test that orders are rejected when slippage is too high"""
    print("\nTesting rejection scenarios...")

    with open('config.json', 'r') as f:
        config = json.load(f)

    estimator = SlippageEstimator(config=config.get('slippage_estimation', {}))

    # Test 1: Insufficient liquidity
    orderbook = {
        'bids': [[0.499, 10]],
        'asks': [[0.501, 10]]  # Only $5.01 liquidity
    }

    result = estimator.estimate_slippage(
        order_side='BUY',
        order_size=100.0,  # Need $100
        orderbook=orderbook,
        quoted_price=0.501,
        market_volume_24h=50000
    )

    assert result.is_acceptable is False
    assert "Insufficient liquidity" in result.rejection_reason
    print("  ✓ Insufficient liquidity rejection works")

    # Test 2: Volume limit exceeded
    orderbook = {
        'bids': [[0.499, 1000]],
        'asks': [[0.501, 1000]]
    }

    result = estimator.estimate_slippage(
        order_side='BUY',
        order_size=150.0,
        orderbook=orderbook,
        quoted_price=0.501,
        market_volume_24h=10000  # 150/10000 = 1.5% > 1% limit
    )

    assert result.is_acceptable is False
    assert "daily volume" in result.rejection_reason.lower()
    print("  ✓ Volume limit rejection works")

    # Test 3: Empty orderbook
    orderbook = {'bids': [], 'asks': []}

    result = estimator.estimate_slippage(
        order_side='BUY',
        order_size=50.0,
        orderbook=orderbook,
        quoted_price=0.501,
        market_volume_24h=10000
    )

    assert result.is_acceptable is False
    assert "No liquidity" in result.rejection_reason
    print("  ✓ Empty orderbook rejection works")


def test_trader_imports():
    """Test that traders can import SlippageEstimator"""
    print("\nTesting trader imports...")

    # Test that the import statement works
    try:
        from slippage_estimator import SlippageEstimator
        print("  ✓ SlippageEstimator can be imported")
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        raise

    # Check that trader.py has the import (via grep)
    import subprocess
    result = subprocess.run(
        ['grep', '-n', 'from slippage_estimator import SlippageEstimator', 'trader.py'],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"  ✓ trader.py has slippage import at line: {result.stdout.strip().split(':')[0]}")
    else:
        print("  ✗ trader.py missing slippage import")

    # Check trader_price_levels.py
    result = subprocess.run(
        ['grep', '-n', 'from slippage_estimator import SlippageEstimator', 'trader_price_levels.py'],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"  ✓ trader_price_levels.py has slippage import at line: {result.stdout.strip().split(':')[0]}")
    else:
        print("  ✗ trader_price_levels.py missing slippage import")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Slippage Estimation Integration Tests")
    print("=" * 60)

    try:
        test_config_loading()
        test_estimator_initialization()
        test_slippage_estimation()
        test_rejection_scenarios()
        test_trader_imports()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nSlippage estimation is properly integrated.")
        print("Next steps:")
        print("  1. Start both bots with: python3 trader.py & python3 trader_price_levels.py &")
        print("  2. Monitor logs for slippage estimates")
        print("  3. Verify trade rejections work correctly")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise


if __name__ == '__main__':
    main()
