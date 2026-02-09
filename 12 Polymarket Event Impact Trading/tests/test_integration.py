"""
End-to-end integration tests
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone
import tempfile

from trader import PolymarketTrader
from position_manager import PositionManager
from price_tracker import PriceTracker


class TestEndToEndFlow:
    """Integration tests for complete trading flow."""

    @pytest.fixture
    def integration_trader(self, sample_config, temp_db):
        """Create trader with all dependencies mocked."""
        sample_config['model_path'] = None

        with patch('trader.PolymarketClient') as mock_client_class:
            with patch('trader.EventDetector') as mock_detector_class:
                # Setup mock client
                mock_client = Mock()
                mock_client.get_markets.return_value = []
                mock_client.get_market_prices.return_value = {'yes': 0.35, 'no': 0.65}
                mock_client_class.return_value = mock_client

                # Setup mock event detector
                mock_detector = Mock()
                mock_detector.get_all_recent_events.return_value = []
                mock_detector_class.return_value = mock_detector

                trader = PolymarketTrader(sample_config)
                trader.position_manager.db_path = temp_db

                yield trader

    def test_full_trading_cycle_no_signals(self, integration_trader):
        """Test trading cycle when no signals are generated."""
        # Should complete without errors
        integration_trader.trading_cycle()

        # No positions should be opened
        assert len(integration_trader.position_timers) == 0

    def test_position_lifecycle(self, integration_trader):
        """Test complete position lifecycle: open -> monitor -> close."""
        market_id = '0xmarket123'

        # 1. Open position
        signal = {
            'action': 'BUY',
            'confidence': 0.7,
            'expected_return': 0.15
        }

        initial_balance = integration_trader.paper_balance

        integration_trader.execute_trade(
            market_id=market_id,
            token_id='0xtoken123',
            signal=signal,
            current_price=0.35,
            outcome='YES'
        )

        # Verify position opened
        assert market_id in integration_trader.position_timers
        assert integration_trader.paper_balance < initial_balance

        # 2. Monitor position
        with patch.object(integration_trader.client, 'get_market_yes_price') as mock_price:
            mock_price.return_value = 0.40  # Price increased

            # Trigger position check
            integration_trader.manage_positions()

        # Position still open (not at TP/SL)
        assert market_id in integration_trader.position_timers

        # 3. Close position
        with patch.object(integration_trader.client, 'get_market_prices') as mock_prices:
            mock_prices.return_value = {'yes': 0.45, 'no': 0.55}

            integration_trader.close_position(market_id, exit_reason='take_profit')

        # Verify position closed
        assert market_id not in integration_trader.position_timers
        # Balance should increase (profit)
        assert integration_trader.paper_balance >= initial_balance

    def test_multiple_positions_management(self, integration_trader):
        """Test managing multiple concurrent positions."""
        # Open 3 positions
        for i in range(3):
            signal = {
                'action': 'BUY',
                'confidence': 0.7,
                'expected_return': 0.15
            }

            integration_trader.execute_trade(
                market_id=f'0xmarket{i}',
                token_id=f'0xtoken{i}',
                signal=signal,
                current_price=0.35,
                outcome='YES'
            )

        # Verify all positions opened
        assert len(integration_trader.position_timers) == 3

        # Close one position
        with patch.object(integration_trader.client, 'get_market_prices') as mock_prices:
            mock_prices.return_value = {'yes': 0.45, 'no': 0.55}

            integration_trader.close_position('0xmarket0', exit_reason='manual')

        # Verify only 2 positions remain
        assert len(integration_trader.position_timers) == 2

    def test_circuit_breaker_integration(self, integration_trader):
        """Test circuit breaker across trading cycle."""
        # Create losing positions that trigger circuit breaker
        for i in range(3):
            market_id = f'0xmarket{i}'

            # Open position
            integration_trader.position_timers[market_id] = {
                'entry_time': datetime.now(timezone.utc),
                'entry_price': 0.50,
                'side': 'YES',
                'size': 50.0
            }
            integration_trader.risk_manager.add_position(market_id, 50.0)

            # Close with loss
            with patch.object(integration_trader.client, 'get_market_prices') as mock_prices:
                mock_prices.return_value = {'yes': 0.30, 'no': 0.70}

                integration_trader.close_position(market_id, exit_reason='stop_loss')

        # Circuit breaker should be active
        assert integration_trader.risk_manager.circuit_breaker_active

        # Try to open new position - should fail
        signal = {'action': 'BUY', 'confidence': 0.7}

        can_open, _ = integration_trader.risk_manager.can_open_position(50)
        assert not can_open

    def test_price_tracking_integration(self, temp_db, sample_event, sample_market):
        """Test price tracking persists across sessions."""
        # Session 1: Track event
        tracker1 = PriceTracker(db_path=temp_db)
        tracking_id = tracker1.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.35,
            features={'event_sentiment_score': 0.6}
        )

        # Session 2: Check same database
        tracker2 = PriceTracker(db_path=temp_db)
        stats = tracker2.get_statistics()

        assert stats['total_tracked'] == 1

    def test_position_persistence_across_restarts(self, integration_trader):
        """Test positions persist across bot restarts."""
        # Open position
        market_id = '0xmarket123'
        signal = {'action': 'BUY', 'confidence': 0.7, 'expected_return': 0.15}

        integration_trader.execute_trade(
            market_id=market_id,
            token_id='0xtoken123',
            signal=signal,
            current_price=0.35,
            outcome='YES'
        )

        # Create new trader instance (simulating restart)
        db_path = integration_trader.position_manager.db_path
        config = integration_trader.config

        with patch('trader.PolymarketClient'):
            with patch('trader.EventDetector'):
                new_trader = PolymarketTrader(config)
                new_trader.position_manager.db_path = db_path
                new_trader._restore_positions()

        # Position should be restored
        assert market_id in new_trader.position_timers

    def test_error_recovery(self, integration_trader):
        """Test that trader recovers from errors gracefully."""
        # Simulate API error during trading cycle
        with patch.object(integration_trader, 'get_tradeable_markets') as mock_markets:
            mock_markets.side_effect = Exception('API Error')

            # Should not crash
            try:
                integration_trader.trading_cycle()
            except Exception as e:
                pytest.fail(f"Trader should handle errors gracefully: {e}")

        # Trader should still be functional
        assert integration_trader.is_running is not None

    def test_balance_consistency(self, integration_trader):
        """Test that balance calculations remain consistent."""
        initial_balance = integration_trader.paper_balance

        # Execute multiple trades
        for i in range(5):
            market_id = f'0xmarket{i}'
            signal = {'action': 'BUY', 'confidence': 0.7, 'expected_return': 0.15}

            integration_trader.execute_trade(
                market_id=market_id,
                token_id=f'0xtoken{i}',
                signal=signal,
                current_price=0.35,
                outcome='YES'
            )

        deployed_capital = sum(pos['size'] for pos in integration_trader.position_timers.values())

        # Balance + deployed should equal initial
        assert abs((integration_trader.paper_balance + deployed_capital) - initial_balance) < 0.01
