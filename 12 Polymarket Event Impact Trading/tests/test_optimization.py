#!/usr/bin/env python3
"""
Unit tests for parameter optimization module.

Tests objective functions, realistic backtester, and parameter optimizer.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.optimization.objective_functions import (
    calculate_metrics, composite_score, multi_fold_score,
    filter_invalid_results, format_metrics_report
)
from src.optimization.realistic_backtester import RealisticBacktester, TradeSimulation
from src.optimization.param_spaces import (
    get_param_space, get_baseline_params, params_list_to_dict,
    params_dict_to_list, validate_params, PARAM_NAMES
)


class TestObjectiveFunctions:
    """Test suite for objective_functions.py"""

    def test_calculate_metrics_basic(self):
        """Test basic metrics calculation"""
        trades = [
            {'pnl': 10, 'outcome': 'YES', 'timestamp': datetime.now()},
            {'pnl': -5, 'outcome': 'NO', 'timestamp': datetime.now()},
            {'pnl': 15, 'outcome': 'YES', 'timestamp': datetime.now()},
            {'pnl': 8, 'outcome': 'YES', 'timestamp': datetime.now()},
        ]

        metrics = calculate_metrics(trades, initial_balance=1000.0)

        assert metrics['num_trades'] == 4
        assert metrics['total_return'] == (10 - 5 + 15 + 8) / 1000.0
        assert metrics['win_rate'] == 0.75  # 3 wins out of 4
        assert metrics['avg_pnl'] == 7.0
        assert metrics['profit_factor'] > 1.0

    def test_calculate_metrics_empty(self):
        """Test metrics with empty trade list"""
        metrics = calculate_metrics([], initial_balance=1000.0)

        assert metrics['num_trades'] == 0
        assert metrics['sharpe_ratio'] == 0.0
        assert metrics['max_drawdown'] == 0.0
        assert metrics['win_rate'] == 0.0

    def test_calculate_metrics_all_wins(self):
        """Test metrics with all winning trades"""
        trades = [
            {'pnl': 10, 'outcome': 'YES', 'timestamp': datetime.now()},
            {'pnl': 15, 'outcome': 'YES', 'timestamp': datetime.now()},
            {'pnl': 8, 'outcome': 'YES', 'timestamp': datetime.now()},
        ]

        metrics = calculate_metrics(trades, initial_balance=1000.0)

        assert metrics['win_rate'] == 1.0
        assert metrics['profit_factor'] == 0.0  # No losses
        assert metrics['max_drawdown'] == 0.0

    def test_calculate_metrics_drawdown(self):
        """Test max drawdown calculation"""
        trades = [
            {'pnl': 100, 'outcome': 'YES', 'timestamp': datetime.now()},
            {'pnl': -50, 'outcome': 'NO', 'timestamp': datetime.now()},
            {'pnl': -30, 'outcome': 'NO', 'timestamp': datetime.now()},
            {'pnl': 20, 'outcome': 'YES', 'timestamp': datetime.now()},
        ]

        metrics = calculate_metrics(trades, initial_balance=1000.0)

        # Balance: 1000 -> 1100 -> 1050 -> 1020 -> 1040
        # Peak: 1100, trough: 1020
        # Drawdown: (1100 - 1020) / 1100 = 7.27%
        assert metrics['max_drawdown'] > 0.05
        assert metrics['max_drawdown'] < 0.10

    def test_composite_score_perfect(self):
        """Test composite score with excellent metrics"""
        metrics = {
            'sharpe_ratio': 2.0,
            'max_drawdown': 0.10,
            'win_rate_std': 0.02,
            'profit_factor': 2.0,
        }

        score = composite_score(metrics)

        # Should be near 1.0 with excellent metrics
        assert score > 0.8
        assert score <= 1.0

    def test_composite_score_poor(self):
        """Test composite score with poor metrics"""
        metrics = {
            'sharpe_ratio': 0.5,
            'max_drawdown': 0.30,
            'win_rate_std': 0.10,
            'profit_factor': 1.2,
        }

        score = composite_score(metrics)

        # Should be low with poor metrics
        assert score < 0.5

    def test_multi_fold_score(self):
        """Test multi-fold scoring with stability penalty"""
        fold_metrics = [
            {'sharpe_ratio': 2.0, 'max_drawdown': 0.10, 'win_rate_std': 0.02, 'profit_factor': 2.0,
             'win_rate': 0.7, 'num_trades': 50, 'total_return': 0.15, 'avg_pnl': 3.0},
            {'sharpe_ratio': 1.8, 'max_drawdown': 0.12, 'win_rate_std': 0.03, 'profit_factor': 1.9,
             'win_rate': 0.68, 'num_trades': 48, 'total_return': 0.14, 'avg_pnl': 2.9},
            {'sharpe_ratio': 2.1, 'max_drawdown': 0.09, 'win_rate_std': 0.02, 'profit_factor': 2.1,
             'win_rate': 0.72, 'num_trades': 52, 'total_return': 0.16, 'avg_pnl': 3.1},
        ]

        total_score, aggregated = multi_fold_score(fold_metrics)

        assert 0 <= total_score <= 1.0
        assert 'composite_score' in aggregated
        assert 'composite_score_std' in aggregated
        assert 'sharpe_ratio' in aggregated
        assert 'sharpe_ratio_std' in aggregated

    def test_filter_invalid_results(self):
        """Test filtering of invalid results"""
        # Valid result
        valid_metrics = {
            'num_trades': 50,
            'profit_factor': 1.8,
            'win_rate': 0.65,
            'sharpe_ratio': 1.5,
        }
        assert filter_invalid_results(valid_metrics) == True

        # Too few trades
        assert filter_invalid_results({'num_trades': 10, 'profit_factor': 2.0, 'win_rate': 0.7, 'sharpe_ratio': 1.5}) == False

        # Losing money (PF < 1)
        assert filter_invalid_results({'num_trades': 50, 'profit_factor': 0.8, 'win_rate': 0.4, 'sharpe_ratio': -0.5}) == False

        # Unrealistic win rate
        assert filter_invalid_results({'num_trades': 50, 'profit_factor': 2.0, 'win_rate': 0.98, 'sharpe_ratio': 3.0}) == False

    def test_format_metrics_report(self):
        """Test report formatting"""
        metrics = {
            'sharpe_ratio': 1.8,
            'max_drawdown': 0.15,
            'win_rate': 0.68,
            'win_rate_std': 0.03,
            'profit_factor': 2.1,
            'total_return': 0.25,
            'num_trades': 45,
            'avg_pnl': 5.56,
        }

        report = format_metrics_report(metrics)

        assert 'Sharpe Ratio' in report
        assert '1.800' in report
        assert '68.00%' in report
        assert '45' in report


class TestRealisticBacktester:
    """Test suite for realistic_backtester.py"""

    @pytest.fixture
    def sample_data(self):
        """Create sample trading data"""
        np.random.seed(42)
        n_samples = 100

        data = pd.DataFrame({
            'condition_id': [f'market_{i}' for i in range(n_samples)],
            'block_timestamp': [datetime.now() - timedelta(days=100-i) for i in range(n_samples)],
            'trade_price': np.random.uniform(0.1, 0.9, n_samples),
            'end_date': [datetime.now() - timedelta(days=100-i) + timedelta(hours=12) for i in range(n_samples)],
            'outcome': np.random.choice(['YES', 'NO'], n_samples),
            'label': np.random.choice([0.0, 1.0], n_samples),
            'volume_24h': np.random.uniform(500, 2000, n_samples),
            'spread_pct': np.random.uniform(3.0, 8.0, n_samples),
        })

        return data

    @pytest.fixture
    def sample_params(self):
        """Create sample parameters"""
        return {
            'take_profit_pct': 30,
            'stop_loss_pct': 10,
            'max_slippage_bps': 3000,
            'max_position_size': 50,
            'max_spread_pct': 10.0,
            'min_volume': 100,
            'min_confidence': 0.55,
        }

    def test_backtester_initialization(self):
        """Test backtester initialization"""
        bt = RealisticBacktester(initial_balance=1000.0, fee_pct=0.01)

        assert bt.initial_balance == 1000.0
        assert bt.current_balance == 1000.0
        assert bt.fee_pct == 0.01
        assert len(bt.trades) == 0

    def test_backtester_reset(self, sample_params, sample_data):
        """Test backtester reset"""
        bt = RealisticBacktester(initial_balance=1000.0)
        bt.backtest(sample_data.head(10), sample_params, 'ultra_short')

        assert len(bt.trades) > 0
        assert bt.current_balance != 1000.0

        bt.reset()

        assert len(bt.trades) == 0
        assert bt.current_balance == 1000.0

    def test_backtest_basic(self, sample_data, sample_params):
        """Test basic backtest execution"""
        bt = RealisticBacktester(initial_balance=1000.0)
        trades = bt.backtest(sample_data.head(20), sample_params, 'ultra_short')

        assert isinstance(trades, list)
        assert all(isinstance(t, TradeSimulation) for t in trades)

    def test_backtest_capital_constraints(self, sample_params):
        """Test that backtest respects capital constraints"""
        # Create data with high position sizes
        data = pd.DataFrame({
            'condition_id': ['market_1', 'market_2'],
            'block_timestamp': [datetime.now(), datetime.now()],
            'trade_price': [0.5, 0.5],
            'end_date': [datetime.now() + timedelta(hours=12), datetime.now() + timedelta(hours=12)],
            'outcome': ['YES', 'YES'],
            'label': [1.0, 1.0],
            'volume_24h': [1000, 1000],
            'spread_pct': [5.0, 5.0],
        })

        bt = RealisticBacktester(initial_balance=100.0)  # Small balance
        params = sample_params.copy()
        params['max_position_size'] = 200  # Larger than balance

        trades = bt.backtest(data, params, 'ultra_short')

        # Should limit position size to available balance
        executed = [t for t in trades if not t.rejected]
        if executed:
            assert all(t.position_size <= 100.0 for t in executed)

    def test_backtest_fees_and_slippage(self, sample_data, sample_params):
        """Test that fees and slippage are applied"""
        bt = RealisticBacktester(initial_balance=1000.0, fee_pct=0.01)
        trades = bt.backtest(sample_data.head(10), sample_params, 'ultra_short')

        executed = [t for t in trades if not t.rejected]

        if executed:
            # All trades should have fees
            assert all(t.entry_fee > 0 for t in executed)
            assert all(t.exit_fee > 0 for t in executed)

            # Net PnL should be less than gross PnL due to costs
            for t in executed:
                assert t.net_pnl <= t.gross_pnl

    def test_get_performance_summary(self, sample_data, sample_params):
        """Test performance summary generation"""
        bt = RealisticBacktester(initial_balance=1000.0)
        bt.backtest(sample_data.head(20), sample_params, 'ultra_short')

        summary = bt.get_performance_summary()

        assert 'total_trades' in summary
        assert 'final_balance' in summary
        assert 'total_return' in summary
        assert 'win_rate' in summary
        assert 'total_fees' in summary
        assert 'total_slippage' in summary


class TestParamSpaces:
    """Test suite for param_spaces.py"""

    def test_get_param_space(self):
        """Test parameter space retrieval"""
        space = get_param_space('ultra_short')

        assert isinstance(space, list)
        assert len(space) == len(PARAM_NAMES)

    def test_get_param_space_invalid_bucket(self):
        """Test error handling for invalid bucket"""
        with pytest.raises(ValueError):
            get_param_space('invalid_bucket')

    def test_get_baseline_params(self):
        """Test baseline parameter retrieval"""
        params = get_baseline_params('ultra_short')

        assert 'take_profit_pct' in params
        assert 'stop_loss_pct' in params
        assert 'max_slippage_bps' in params
        assert params['take_profit_pct'] == 30

    def test_params_list_to_dict(self):
        """Test list to dict conversion"""
        params_list = [30, 10, 3000, 50, 10.0, 100, 0.55]
        params_dict = params_list_to_dict(params_list)

        assert params_dict['take_profit_pct'] == 30
        assert params_dict['stop_loss_pct'] == 10
        assert params_dict['max_slippage_bps'] == 3000

    def test_params_dict_to_list(self):
        """Test dict to list conversion"""
        params_dict = {
            'take_profit_pct': 30,
            'stop_loss_pct': 10,
            'max_slippage_bps': 3000,
            'max_position_size': 50,
            'max_spread_pct': 10.0,
            'min_volume': 100,
            'min_confidence': 0.55,
        }

        params_list = params_dict_to_list(params_dict)

        assert len(params_list) == len(PARAM_NAMES)
        assert params_list[0] == 30  # take_profit_pct
        assert params_list[1] == 10  # stop_loss_pct

    def test_validate_params_valid(self):
        """Test parameter validation with valid params"""
        params = {
            'take_profit_pct': 30,
            'stop_loss_pct': 10,
            'max_slippage_bps': 3000,
            'max_position_size': 50,
            'max_spread_pct': 10.0,
            'min_volume': 100,
            'min_confidence': 0.55,
        }

        is_valid, error = validate_params(params)
        assert is_valid == True
        assert error is None

    def test_validate_params_invalid_tp_sl(self):
        """Test validation rejects TP <= SL"""
        params = {
            'take_profit_pct': 10,
            'stop_loss_pct': 15,  # SL > TP (invalid)
            'max_slippage_bps': 3000,
            'max_position_size': 50,
            'max_spread_pct': 10.0,
            'min_volume': 100,
            'min_confidence': 0.55,
        }

        is_valid, error = validate_params(params)
        assert is_valid == False
        assert 'take_profit_pct must be > stop_loss_pct' in error

    def test_validate_params_invalid_confidence(self):
        """Test validation rejects invalid confidence"""
        params = {
            'take_profit_pct': 30,
            'stop_loss_pct': 10,
            'max_slippage_bps': 3000,
            'max_position_size': 50,
            'max_spread_pct': 10.0,
            'min_volume': 100,
            'min_confidence': 1.5,  # > 1.0 (invalid)
        }

        is_valid, error = validate_params(params)
        assert is_valid == False
        assert 'min_confidence' in error


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
