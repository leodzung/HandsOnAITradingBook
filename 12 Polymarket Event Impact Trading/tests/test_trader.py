"""
Integration tests for main event trader (trader.py)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import json

from trader import PolymarketTrader, RiskManager


class TestRiskManager:
    """Test suite for RiskManager."""

    def test_initialization(self):
        """Test risk manager initialization."""
        rm = RiskManager(
            max_position_size=100,
            max_positions=10,
            max_daily_loss=500,
            circuit_breaker_losses=3
        )

        assert rm.max_position_size == 100
        assert rm.max_positions == 10
        assert rm.max_daily_loss == 500
        assert rm.consecutive_losses == 0
        assert not rm.circuit_breaker_active

    def test_can_open_position_success(self):
        """Test position opening when all checks pass."""
        rm = RiskManager(max_position_size=100, max_positions=10)

        can_open, reason = rm.can_open_position(position_size=50)

        assert can_open
        assert reason == "OK"

    def test_can_open_position_exceeds_size_limit(self):
        """Test blocking position that exceeds size limit."""
        rm = RiskManager(max_position_size=100)

        can_open, reason = rm.can_open_position(position_size=150)

        assert not can_open
        assert "Position size" in reason

    def test_can_open_position_exceeds_max_positions(self):
        """Test blocking when max positions reached."""
        rm = RiskManager(max_positions=2)
        rm.add_position('market1', 50)
        rm.add_position('market2', 50)

        can_open, reason = rm.can_open_position(position_size=50)

        assert not can_open
        assert "Max positions" in reason

    def test_can_open_position_exceeds_daily_loss(self):
        """Test blocking when daily loss limit reached."""
        rm = RiskManager(max_daily_loss=100)
        rm.daily_pnl = -150

        can_open, reason = rm.can_open_position(position_size=50)

        assert not can_open
        assert "Daily loss limit" in reason

    def test_circuit_breaker_triggers(self):
        """Test circuit breaker triggers after consecutive losses."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate 3 consecutive losses
        for i in range(3):
            rm.add_position(f'market{i}', 50)
            rm.remove_position(f'market{i}', pnl=-10)

        assert rm.circuit_breaker_active
        assert rm.consecutive_losses == 3

    def test_circuit_breaker_resets_on_win(self):
        """Test circuit breaker counter resets on win."""
        rm = RiskManager(circuit_breaker_losses=3)

        # 2 losses
        rm.add_position('market1', 50)
        rm.remove_position('market1', pnl=-10)
        rm.add_position('market2', 50)
        rm.remove_position('market2', pnl=-10)

        assert rm.consecutive_losses == 2

        # Win resets counter
        rm.add_position('market3', 50)
        rm.remove_position('market3', pnl=10)

        assert rm.consecutive_losses == 0
        assert not rm.circuit_breaker_active

    def test_get_position_size_kelly_criterion(self):
        """Test position sizing with Kelly criterion."""
        rm = RiskManager(max_position_size=100)

        # High confidence (0.9) should give larger size
        size_high = rm.get_position_size(confidence=0.9, balance=1000)

        # Low confidence (0.6) should give smaller size
        size_low = rm.get_position_size(confidence=0.6, balance=1000)

        assert size_high > size_low
        assert size_high <= rm.max_position_size

    def test_daily_counter_reset(self):
        """Test that daily counters reset at midnight."""
        from datetime import date, timedelta
        rm = RiskManager()
        rm.daily_pnl = -100
        rm.daily_reset_time = date.today() - timedelta(days=1)

        rm.reset_daily_counters()

        assert rm.daily_pnl == 0.0
        assert rm.daily_reset_time == date.today()


class TestPolymarketTrader:
    """Test suite for PolymarketTrader."""

    @pytest.fixture
    def trader(self, sample_config, temp_db):
        """Create trader instance for testing."""
        sample_config['model_path'] = None  # Skip model loading
        with patch('trader.PolymarketClient'):
            with patch('trader.EventDetector'):
                trader = PolymarketTrader(sample_config)
                trader.position_manager.db_path = temp_db
                return trader

    def test_trader_initialization(self, sample_config):
        """Test trader initialization."""
        with patch('trader.PolymarketClient'):
            with patch('trader.EventDetector'):
                trader = PolymarketTrader(sample_config)

                assert trader.config == sample_config
                assert trader.paper_balance == sample_config['paper_trading_balance']
                assert isinstance(trader.risk_manager, RiskManager)

    def test_execute_trade_paper_trading(self, trader, sample_market):
        """Test executing paper trade."""
        signal = {
            'action': 'BUY',
            'confidence': 0.7,
            'expected_return': 0.15
        }

        initial_balance = trader.paper_balance

        trader.execute_trade(
            market_id=sample_market['conditionId'],
            token_id='0xtoken1',
            signal=signal,
            current_price=0.35,
            outcome='YES'
        )

        # Balance should decrease
        assert trader.paper_balance < initial_balance

        # Position should be tracked
        assert sample_market['conditionId'] in trader.position_timers

    def test_close_position_profit(self, trader):
        """Test closing position with profit."""
        market_id = '0xmarket123'

        # Open position
        trader.position_timers[market_id] = {
            'entry_time': datetime.now(timezone.utc),
            'entry_price': 0.35,
            'side': 'YES',
            'size': 50.0
        }
        trader.risk_manager.add_position(market_id, 50.0)
        trader._update_paper_balance(-50, 'Open position')

        initial_balance = trader.paper_balance

        # Mock price increase
        with patch.object(trader.client, 'get_market_prices') as mock_prices:
            mock_prices.return_value = {'yes': 0.45, 'no': 0.55}

            trader.close_position(market_id, exit_reason='take_profit')

        # Balance should increase (profit)
        assert trader.paper_balance > initial_balance

        # Position should be removed
        assert market_id not in trader.position_timers

    def test_close_position_loss(self, trader):
        """Test closing position with loss."""
        market_id = '0xmarket123'

        trader.position_timers[market_id] = {
            'entry_time': datetime.now(timezone.utc),
            'entry_price': 0.35,
            'side': 'YES',
            'size': 50.0
        }
        trader.risk_manager.add_position(market_id, 50.0)
        trader._update_paper_balance(-50, 'Open position')

        initial_balance = trader.paper_balance

        # Mock price decrease
        with patch.object(trader.client, 'get_market_prices') as mock_prices:
            mock_prices.return_value = {'yes': 0.25, 'no': 0.75}

            trader.close_position(market_id, exit_reason='stop_loss')

        # Balance should be less than initial (loss)
        assert trader.paper_balance < initial_balance

    def test_manage_positions_time_exit(self, trader):
        """Test position exits after hold time."""
        from datetime import timedelta

        market_id = '0xmarket123'
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)

        trader.position_timers[market_id] = {
            'entry_time': old_time,
            'entry_price': 0.35,
            'side': 'YES',
            'size': 50.0
        }
        trader.risk_manager.add_position(market_id, 50.0)

        with patch.object(trader.client, 'get_market_prices') as mock_prices:
            mock_prices.return_value = {'yes': 0.40, 'no': 0.60}
            with patch.object(trader, 'close_position') as mock_close:
                trader.manage_positions()

                # Should call close_position for time exit
                mock_close.assert_called_once()
                call_args = mock_close.call_args
                assert call_args[1]['exit_reason'] == 'time_exit'

    def test_manage_positions_stop_loss(self, trader):
        """Test position exits on stop loss."""
        market_id = '0xmarket123'

        trader.position_timers[market_id] = {
            'entry_time': datetime.now(timezone.utc),
            'entry_price': 0.50,
            'side': 'YES',
            'size': 50.0
        }
        trader.risk_manager.add_position(market_id, 50.0)

        # Mock large price drop (>15% loss)
        with patch.object(trader.client, 'get_market_yes_price') as mock_price:
            mock_price.return_value = 0.40  # 20% drop
            with patch.object(trader, 'close_position') as mock_close:
                trader.manage_positions()

                mock_close.assert_called()
                call_args = mock_close.call_args
                assert call_args[1]['exit_reason'] == 'stop_loss'

    def test_paper_balance_persistence(self, trader, temp_json_file):
        """Test that paper balance persists to file."""
        trader.paper_balance_file = temp_json_file
        trader._update_paper_balance(-50, 'Test trade')

        # Read back
        with open(temp_json_file, 'r') as f:
            data = json.load(f)

        assert data['balance'] == trader.paper_balance

    def test_transform_features_for_model(self, trader, sample_features, sample_market):
        """Test feature transformation for model."""
        transformed = trader._transform_features_for_model(sample_features, sample_market)

        # Check all required features present
        required_features = [
            'trade_count', 'market_volume', 'price_mean', 'is_crypto',
            'news_sentiment_mean'
        ]
        for feature in required_features:
            assert feature in transformed

        # Check crypto detection
        assert transformed['is_crypto'] == 1  # Bitcoin market
