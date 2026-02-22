#!/usr/bin/env python3
"""
Test script to verify Price Level Trader migration to TradeExecutor.

Tests:
1. Bot initializes correctly
2. TradeExecutor is initialized
3. Price filter works (rejects > $0.90)
4. Trade execution works for valid prices
"""

import sys
sys.path.insert(0, 'src')

from core.trade_executor import TradeExecutor, TradeRequest, TradeResult
from core.polymarket_client import PolymarketClient
from core.position_manager import PositionManager

def test_trade_executor_init():
    """Test TradeExecutor initialization."""
    print("=" * 70)
    print("TEST 1: TradeExecutor Initialization")
    print("=" * 70)

    config = {
        'max_entry_price': 0.90,
        'paper_trading': True,
        'slippage_estimation': {
            'enabled': False  # Disable for simple test
        }
    }

    client = PolymarketClient()
    position_manager = PositionManager(db_path='data/test_positions.db')

    executor = TradeExecutor(
        client=client,
        position_manager=position_manager,
        config=config,
        paper_trading=True
    )

    print("✅ TradeExecutor initialized successfully")
    print(f"   Max entry price: ${executor.max_entry_price:.2f}")
    print(f"   Slippage enabled: {executor.slippage_enabled}")
    print()

    return executor


def test_price_filter_rejection(executor):
    """Test that price filter rejects > $0.90."""
    print("=" * 70)
    print("TEST 2: Price Filter Rejection (price > $0.90)")
    print("=" * 70)

    request = TradeRequest(
        market_id='0xTEST123',
        token_id='TEST456',
        outcome='YES',
        entry_price=0.999,  # Too high!
        position_size=50.0,
        question='Test market - will be rejected'
    )

    result = executor.execute_trade(request)

    print(f"Request: BUY YES @ ${request.entry_price:.3f}")
    print(f"Result: {'✅ PASS' if not result.success else '❌ FAIL'}")
    print(f"   Success: {result.success}")
    print(f"   Rejection stage: {result.rejection_stage}")
    print(f"   Rejection reason: {result.rejection_reason}")

    assert not result.success, "Trade should be rejected!"
    assert result.rejection_stage == 'price', "Should fail at price stage!"
    assert '0.999' in result.rejection_reason, "Should mention price $0.999!"

    print("✅ Price filter working correctly - rejected $0.999 entry")
    print()


def test_price_filter_acceptance(executor):
    """Test that price filter accepts < $0.90."""
    print("=" * 70)
    print("TEST 3: Price Filter Acceptance (price < $0.90)")
    print("=" * 70)

    request = TradeRequest(
        market_id='0xTEST456',
        token_id='TEST789',
        outcome='YES',
        entry_price=0.45,  # Valid!
        position_size=50.0,
        question='Test market - should execute'
    )

    result = executor.execute_trade(request)

    print(f"Request: BUY YES @ ${request.entry_price:.3f}")
    print(f"Result: {'✅ PASS' if result.success else '❌ FAIL'}")
    print(f"   Success: {result.success}")
    if result.success:
        print(f"   Entry price: ${result.entry_price:.3f}")
        print(f"   Position size: ${result.position_size:.2f}")
    else:
        print(f"   Rejection stage: {result.rejection_stage}")
        print(f"   Rejection reason: {result.rejection_reason}")

    assert result.success, "Trade should execute!"
    assert result.entry_price == 0.45, "Entry price should be $0.45!"

    print("✅ Price filter working correctly - accepted $0.45 entry")
    print()


def test_borderline_case(executor):
    """Test borderline case ($0.89)."""
    print("=" * 70)
    print("TEST 4: Borderline Case (price = $0.89)")
    print("=" * 70)

    request = TradeRequest(
        market_id='0xTEST789',
        token_id='TEST101',
        outcome='NO',
        entry_price=0.89,  # Just under limit!
        position_size=25.0,
        question='Test market - borderline'
    )

    result = executor.execute_trade(request)

    print(f"Request: BUY NO @ ${request.entry_price:.3f}")
    print(f"Result: {'✅ PASS' if result.success else '❌ FAIL'}")
    print(f"   Success: {result.success}")
    print(f"   Max allowed: $0.90")
    print(f"   Actual price: $0.89")

    assert result.success, "Trade should execute (0.89 < 0.90)!"

    print("✅ Borderline case working - accepted $0.89 entry")
    print()


def test_over_limit_rejection(executor):
    """Test just over limit ($0.91)."""
    print("=" * 70)
    print("TEST 5: Over Limit Rejection (price = $0.91)")
    print("=" * 70)

    request = TradeRequest(
        market_id='0xTEST999',
        token_id='TEST202',
        outcome='YES',
        entry_price=0.91,  # Just over limit!
        position_size=75.0,
        question='Test market - over limit'
    )

    result = executor.execute_trade(request)

    print(f"Request: BUY YES @ ${request.entry_price:.3f}")
    print(f"Result: {'✅ PASS' if not result.success else '❌ FAIL'}")
    print(f"   Success: {result.success}")
    print(f"   Max allowed: $0.90")
    print(f"   Actual price: $0.91")

    assert not result.success, "Trade should be rejected (0.91 > 0.90)!"
    assert result.rejection_stage == 'price', "Should fail at price stage!"

    print("✅ Over limit rejection working - rejected $0.91 entry")
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("TRADE EXECUTOR MIGRATION TEST SUITE")
    print("=" * 70)
    print()

    try:
        # Test 1: Initialization
        executor = test_trade_executor_init()

        # Test 2: Price filter rejection (high price)
        test_price_filter_rejection(executor)

        # Test 3: Price filter acceptance (valid price)
        test_price_filter_acceptance(executor)

        # Test 4: Borderline case
        test_borderline_case(executor)

        # Test 5: Just over limit
        test_over_limit_rejection(executor)

        # Summary
        print("=" * 70)
        print("ALL TESTS PASSED! ✅")
        print("=" * 70)
        print()
        print("Price Level Trader migration successful!")
        print("  - TradeExecutor initialized correctly")
        print("  - Price filter ($0.90 limit) working")
        print("  - Trade execution working for valid prices")
        print("  - Rejection reasons clear and correct")
        print()
        print("Next step: Restart price level trader to apply changes")
        print()

    except AssertionError as e:
        print()
        print("=" * 70)
        print("TEST FAILED! ❌")
        print("=" * 70)
        print(f"Error: {e}")
        print()
        sys.exit(1)

    except Exception as e:
        print()
        print("=" * 70)
        print("ERROR! ❌")
        print("=" * 70)
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        print()
        sys.exit(1)


if __name__ == '__main__':
    main()
