#!/usr/bin/env python3
"""
Component-level integration test for parameter optimization.

Tests individual components with synthetic data to validate
they work correctly without requiring walk-forward splits.
"""

import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import optimization modules
from src.optimization.realistic_backtester import RealisticBacktester
from src.optimization.objective_functions import calculate_metrics, composite_score
from src.optimization.param_spaces import (
    get_baseline_params, validate_params, params_list_to_dict, PARAM_NAMES
)

def create_synthetic_data(n_samples=200):
    """Create synthetic trading data for testing."""
    np.random.seed(42)

    # Create dates spanning 90 days
    base_time = datetime.now() - timedelta(days=90)
    entry_times = [base_time + timedelta(hours=i*4) for i in range(n_samples)]
    exit_times = [t + timedelta(hours=np.random.randint(6, 18)) for t in entry_times]

    data = pd.DataFrame({
        'condition_id': [f'market_{i}' for i in range(n_samples)],
        'block_timestamp': entry_times,
        'trade_price': np.random.uniform(0.2, 0.8, n_samples),
        'end_date': exit_times,
        'outcome': np.random.choice(['YES', 'NO'], n_samples),
        'label': np.random.choice([0.0, 1.0], n_samples, p=[0.35, 0.65]),  # 65% win rate
        'volume_24h': np.random.uniform(500, 2000, n_samples),
        'spread_pct': np.random.uniform(3.0, 8.0, n_samples),
    })

    return data

def test_param_spaces():
    """Test parameter space functions."""
    print("\n" + "=" * 70)
    print("TEST 1: Parameter Spaces")
    print("=" * 70)

    # Test baseline params
    baseline = get_baseline_params('ultra_short')
    print(f"✓ Baseline params loaded: {len(baseline)} parameters")

    # Test validation
    is_valid, error = validate_params(baseline)
    assert is_valid, f"Baseline params should be valid: {error}"
    print(f"✓ Baseline params validated")

    # Test invalid params (TP < SL)
    invalid_params = baseline.copy()
    invalid_params['take_profit_pct'] = 5
    invalid_params['stop_loss_pct'] = 10
    is_valid, error = validate_params(invalid_params)
    assert not is_valid, "Should detect TP < SL"
    print(f"✓ Invalid params correctly rejected: {error}")

    # Test list/dict conversion
    params_list = [30, 10, 3000, 50, 10.0, 100, 0.55]
    params_dict = params_list_to_dict(params_list)
    assert params_dict['take_profit_pct'] == 30
    print(f"✓ Params list/dict conversion works")

    print("✅ Parameter spaces: ALL TESTS PASSED")
    return True

def test_objective_functions():
    """Test objective function calculations."""
    print("\n" + "=" * 70)
    print("TEST 2: Objective Functions")
    print("=" * 70)

    # Create sample trades
    trades = [
        {'pnl': 10, 'outcome': 'YES', 'timestamp': datetime.now()},
        {'pnl': -5, 'outcome': 'NO', 'timestamp': datetime.now()},
        {'pnl': 15, 'outcome': 'YES', 'timestamp': datetime.now()},
        {'pnl': 8, 'outcome': 'YES', 'timestamp': datetime.now()},
        {'pnl': -3, 'outcome': 'NO', 'timestamp': datetime.now()},
    ]

    # Calculate metrics
    metrics = calculate_metrics(trades, initial_balance=1000.0)

    assert metrics['num_trades'] == 5
    assert metrics['win_rate'] == 0.6  # 3 wins out of 5
    assert metrics['total_return'] == (10 - 5 + 15 + 8 - 3) / 1000.0
    print(f"✓ Metrics calculated: {metrics['num_trades']} trades, {metrics['win_rate']:.2%} win rate")

    # Calculate composite score
    score = composite_score(metrics)
    assert 0 <= score <= 1.0
    print(f"✓ Composite score: {score:.4f} (valid range [0, 1])")

    # Test with excellent metrics
    excellent_metrics = {
        'sharpe_ratio': 2.0,
        'max_drawdown': 0.10,
        'win_rate_std': 0.02,
        'profit_factor': 2.0,
    }
    score_excellent = composite_score(excellent_metrics)
    assert score_excellent > 0.8
    print(f"✓ Excellent metrics score: {score_excellent:.4f} (>0.8)")

    print("✅ Objective functions: ALL TESTS PASSED")
    return True

def test_realistic_backtester():
    """Test realistic backtester."""
    print("\n" + "=" * 70)
    print("TEST 3: Realistic Backtester")
    print("=" * 70)

    # Create synthetic data
    data = create_synthetic_data(n_samples=100)
    print(f"✓ Created {len(data)} synthetic trades")

    # Get baseline params
    params = get_baseline_params('ultra_short')

    # Run backtest
    bt = RealisticBacktester(initial_balance=1000.0, fee_pct=0.01)
    trades = bt.backtest(data, params, 'ultra_short')

    print(f"✓ Backtest completed: {len(trades)} trades simulated")

    # Check trades have expected fields
    if len(trades) > 0:
        t = trades[0]
        assert hasattr(t, 'entry_price')
        assert hasattr(t, 'exit_price')
        assert hasattr(t, 'net_pnl')
        assert hasattr(t, 'entry_fee')
        assert hasattr(t, 'exit_fee')
        print(f"✓ Trade objects have correct structure")

    # Get performance summary
    summary = bt.get_performance_summary()
    print(f"✓ Performance summary generated:")
    print(f"   - Total trades: {summary.get('total_trades', 0)}")
    print(f"   - Win rate: {summary.get('win_rate', 0):.2%}")
    print(f"   - Final balance: ${summary.get('final_balance', 0):.2f}")
    print(f"   - Total fees: ${summary.get('total_fees', 0):.2f}")

    # Verify fees are charged
    if summary.get('total_trades', 0) > 0:
        assert summary['total_fees'] > 0, "Fees should be charged"
        print(f"✓ Fees correctly applied")

    # Verify net PnL accounts for fees
    executed_trades = [t for t in trades if not t.rejected]
    if executed_trades:
        for t in executed_trades[:3]:  # Check first 3
            assert t.net_pnl <= t.gross_pnl, "Net PnL should be <= gross PnL after fees"
        print(f"✓ Net PnL correctly calculated (gross - fees)")

    print("✅ Realistic backtester: ALL TESTS PASSED")
    return True

def test_end_to_end_workflow():
    """Test end-to-end workflow without optimization."""
    print("\n" + "=" * 70)
    print("TEST 4: End-to-End Workflow")
    print("=" * 70)

    # Create synthetic data
    data = create_synthetic_data(n_samples=150)

    # Test with baseline params
    baseline_params = get_baseline_params('ultra_short')
    print(f"✓ Testing with baseline params:")
    for k, v in baseline_params.items():
        print(f"   {k}: {v}")

    # Run backtest
    bt = RealisticBacktester(initial_balance=1000.0)
    trades = bt.backtest(data, baseline_params, 'ultra_short')

    # Convert to metrics format
    trades_for_metrics = [
        {'pnl': t.net_pnl, 'outcome': t.outcome, 'timestamp': t.entry_time}
        for t in trades if not t.rejected
    ]

    # Calculate metrics
    metrics = calculate_metrics(trades_for_metrics, initial_balance=1000.0)
    print(f"\n✓ Performance metrics:")
    print(f"   Trades: {metrics['num_trades']}")
    print(f"   Win rate: {metrics['win_rate']:.2%}")
    print(f"   Sharpe ratio: {metrics['sharpe_ratio']:.3f}")
    print(f"   Max drawdown: {metrics['max_drawdown']:.2%}")
    print(f"   Total return: {metrics['total_return']:.2%}")

    # Calculate composite score
    score = composite_score(metrics)
    print(f"\n✓ Composite score: {score:.4f}")

    # Test with modified params (higher TP/SL)
    modified_params = baseline_params.copy()
    modified_params['take_profit_pct'] = 50  # More aggressive
    modified_params['stop_loss_pct'] = 15

    bt2 = RealisticBacktester(initial_balance=1000.0)
    trades2 = bt2.backtest(data, modified_params, 'ultra_short')

    trades_for_metrics2 = [
        {'pnl': t.net_pnl, 'outcome': t.outcome, 'timestamp': t.entry_time}
        for t in trades2 if not t.rejected
    ]

    metrics2 = calculate_metrics(trades_for_metrics2, initial_balance=1000.0)
    score2 = composite_score(metrics2)

    print(f"\n✓ Modified params performance:")
    print(f"   Composite score: {score2:.4f} (baseline: {score:.4f})")
    print(f"   Win rate: {metrics2['win_rate']:.2%} (baseline: {metrics['win_rate']:.2%})")

    print("\n✅ End-to-end workflow: ALL TESTS PASSED")
    return True

def main():
    """Run all component tests."""
    print("=" * 70)
    print("PARAMETER OPTIMIZATION - COMPONENT TESTS")
    print("=" * 70)

    try:
        # Run all tests
        results = []

        results.append(("Parameter Spaces", test_param_spaces()))
        results.append(("Objective Functions", test_objective_functions()))
        results.append(("Realistic Backtester", test_realistic_backtester()))
        results.append(("End-to-End Workflow", test_end_to_end_workflow()))

        # Summary
        print("\n" + "=" * 70)
        print("TEST SUMMARY")
        print("=" * 70)

        all_passed = all(r[1] for r in results)

        for name, passed in results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{status}: {name}")

        print("=" * 70)

        if all_passed:
            print("\n🎉 ALL COMPONENTS WORKING CORRECTLY!")
            print("\nNext steps:")
            print("  1. Install scikit-optimize: pip install scikit-optimize")
            print("  2. Prepare data with proper date ranges for walk-forward validation")
            print("  3. Run full optimization:")
            print("     python scripts/optimize_short_expiry_params.py --bucket ultra_short --n-calls 150")
            return 0
        else:
            print("\n⚠️ SOME TESTS FAILED - Please review errors above")
            return 1

    except Exception as e:
        logger.error(f"Component tests failed: {e}", exc_info=True)
        print(f"\n❌ Test suite failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
