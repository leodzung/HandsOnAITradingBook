"""
Unit tests for TradeExecutor - full pipeline coverage.

Tests the complete validation pipeline:
- Price validation (both bounds)
- Position size validation
- Slippage estimation integration
- API error handling
- Request immutability
- Close trade with bucket
- Slippage-disabled path
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.core.trade_executor import TradeExecutor, TradeRequest, TradeResult
from src.core.position_manager_v2 import PositionManager


def _make_executor(slippage_enabled=True, max_entry_price=0.90):
    """Create a TradeExecutor with mocked dependencies."""
    client = Mock()
    position_manager = Mock(spec=PositionManager)
    config = {
        'max_entry_price': max_entry_price,
        'slippage_estimation': {
            'enabled': slippage_enabled,
            'max_slippage_bps': 2000,
            'max_slippage_dollars': 50.0,
        }
    }
    executor = TradeExecutor(
        client=client,
        position_manager=position_manager,
        config=config,
        paper_trading=True
    )
    return executor, client, position_manager


def _make_request(**overrides):
    """Create a TradeRequest with defaults."""
    defaults = dict(
        market_id='0xTEST',
        token_id='TOKEN123',
        outcome='YES',
        entry_price=0.50,
        position_size=50.0,
        question='Will BTC hit $100k?',
        edge=0.05,
        confidence=0.7,
        signal_reason='test',
        stop_loss_pct=15,
        take_profit_pct=50,
    )
    defaults.update(overrides)
    return TradeRequest(**defaults)


def _good_orderbook(bid=0.495, ask=0.505, size=10000):
    """Create a liquid orderbook."""
    return {
        'bids': [[bid, size]],
        'asks': [[ask, size]],
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


class TestExecuteTradeFullPipeline:
    """Test the full execute_trade validation pipeline."""

    def test_successful_trade_with_slippage(self):
        """Full pipeline: price valid, size valid, slippage acceptable."""
        executor, client, pm = _make_executor()
        client.get_orderbook.return_value = _good_orderbook()
        client.get_market.return_value = {'volume_24h': 100000}

        request = _make_request()
        result = executor.execute_trade(request)

        assert result.success
        assert result.entry_price is not None
        assert result.position_size == 50.0
        pm.save_position.assert_called_once()

    def test_successful_trade_slippage_disabled(self):
        """Pipeline with slippage disabled: skip slippage, still execute."""
        executor, client, pm = _make_executor(slippage_enabled=False)

        request = _make_request()
        result = executor.execute_trade(request)

        assert result.success
        assert result.entry_price == 0.50
        assert result.slippage_bps is None
        client.get_orderbook.assert_not_called()
        pm.save_position.assert_called_once()

    def test_rejection_stages_ordered_correctly(self):
        """Price checked before size, size before slippage."""
        executor, _, _ = _make_executor()

        # Bad price + bad size → should fail at price stage
        request = _make_request(entry_price=1.5, position_size=-10)
        result = executor.execute_trade(request)
        assert result.rejection_stage == 'price'

        # Good price + bad size → should fail at size stage
        request = _make_request(entry_price=0.50, position_size=0)
        result = executor.execute_trade(request)
        assert result.rejection_stage == 'size'


class TestPriceValidation:
    """Test _validate_price with both bounds."""

    def test_accepts_valid_price(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(entry_price=0.50))
        assert result.success

    def test_accepts_low_price(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(entry_price=0.01))
        assert result.success

    def test_accepts_price_at_max(self):
        """Price exactly at max_entry_price should be accepted."""
        executor, _, _ = _make_executor(slippage_enabled=False, max_entry_price=0.90)
        result = executor.execute_trade(_make_request(entry_price=0.90))
        assert result.success

    def test_rejects_zero_price(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(entry_price=0.0))
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_negative_price(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(entry_price=-0.5))
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_price_at_one(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(entry_price=1.0))
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_price_above_one(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(entry_price=1.5))
        assert not result.success
        assert result.rejection_stage == 'price'

    def test_rejects_price_above_max(self):
        executor, _, _ = _make_executor(slippage_enabled=False, max_entry_price=0.90)
        result = executor.execute_trade(_make_request(entry_price=0.91))
        assert not result.success
        assert result.rejection_stage == 'price'
        assert '0.91' in result.rejection_reason


class TestPositionSizeValidation:
    """Test _validate_position_size."""

    def test_rejects_zero_size(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(position_size=0.0))
        assert not result.success
        assert result.rejection_stage == 'size'

    def test_rejects_negative_size(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(position_size=-10.0))
        assert not result.success
        assert result.rejection_stage == 'size'

    def test_accepts_small_size(self):
        executor, _, _ = _make_executor(slippage_enabled=False)
        result = executor.execute_trade(_make_request(position_size=0.01))
        assert result.success


class TestRequestImmutability:
    """Test that execute_trade does not mutate TradeRequest."""

    def test_entry_price_not_mutated(self):
        """request.entry_price must remain unchanged after execute_trade."""
        executor, client, _ = _make_executor()
        client.get_orderbook.return_value = _good_orderbook()
        client.get_market.return_value = {'volume_24h': 100000}

        original_price = 0.50
        request = _make_request(entry_price=original_price)
        executor.execute_trade(request)

        assert request.entry_price == original_price, (
            f"request.entry_price was mutated from {original_price} to {request.entry_price}"
        )

    def test_result_reflects_execution_price(self):
        """TradeResult.entry_price should reflect the actual execution price."""
        executor, client, _ = _make_executor()
        client.get_orderbook.return_value = _good_orderbook()
        client.get_market.return_value = {'volume_24h': 100000}

        request = _make_request(entry_price=0.50)
        result = executor.execute_trade(request)

        assert result.success
        # entry_price in result may differ from request (slippage adjustment)
        assert result.entry_price is not None


class TestApiErrorHandling:
    """Test API error vs legitimate rejection distinction."""

    def test_orderbook_failure_returns_api_error(self):
        executor, client, _ = _make_executor()
        client.get_orderbook.return_value = None

        result = executor.execute_trade(_make_request())
        assert not result.success
        assert result.rejection_stage == 'api_error'

    def test_empty_orderbook_returns_slippage(self):
        """Empty orderbook is a legitimate rejection, not an API error."""
        executor, client, _ = _make_executor()
        client.get_orderbook.return_value = {
            'bids': [], 'asks': [],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        client.get_market.return_value = {'volume_24h': 10000}

        result = executor.execute_trade(_make_request())
        assert not result.success
        assert result.rejection_stage == 'slippage'


class TestExecuteCloseTrade:
    """Test execute_close_trade method."""

    def test_close_with_good_liquidity(self):
        """Close trade succeeds with sufficient liquidity."""
        executor, client, pm = _make_executor()
        client.get_orderbook.return_value = _good_orderbook()
        client.get_market.return_value = {'volume_24h': 100000}

        result = executor.execute_close_trade(
            market_id='0xTEST', outcome='YES', token_id='TOKEN',
            exit_price=0.55, position_size=50.0,
            exit_reason='take_profit', question='Test market'
        )

        assert result.success
        assert result.entry_price is None  # Close trades don't set entry_price
        assert result.position_size == 50.0
        pm.close_position.assert_called_once()

    def test_close_passes_bucket_to_slippage(self):
        """execute_close_trade must pass bucket to estimate_slippage."""
        executor, client, pm = _make_executor()
        client.get_orderbook.return_value = _good_orderbook()
        client.get_market.return_value = {'volume_24h': 100000}

        with patch.object(executor.slippage_estimator, 'estimate_slippage', wraps=executor.slippage_estimator.estimate_slippage) as mock_est:
            executor.execute_close_trade(
                market_id='0xTEST', outcome='YES', token_id='TOKEN',
                exit_price=0.495, position_size=50.0,
                exit_reason='stop_loss', question='Test market',
                bucket='ultra_short'
            )

            # Verify bucket was passed
            call_kwargs = mock_est.call_args
            assert call_kwargs.kwargs.get('bucket') == 'ultra_short' or \
                   (len(call_kwargs.args) > 5 and call_kwargs.args[5] == 'ultra_short'), \
                "bucket='ultra_short' must be passed to estimate_slippage"

    def test_close_api_error_on_orderbook_failure(self):
        """Close trade returns api_error when orderbook fetch fails."""
        executor, client, _ = _make_executor()
        client.get_orderbook.return_value = None

        result = executor.execute_close_trade(
            market_id='0xTEST', outcome='YES', token_id='TOKEN',
            exit_price=0.55, position_size=50.0,
            exit_reason='stop_loss', question='Test'
        )

        assert not result.success
        assert result.rejection_stage == 'api_error'

    def test_close_slippage_disabled(self):
        """Close trade succeeds with slippage disabled."""
        executor, client, pm = _make_executor(slippage_enabled=False)

        result = executor.execute_close_trade(
            market_id='0xTEST', outcome='YES', token_id='TOKEN',
            exit_price=0.55, position_size=50.0,
            exit_reason='take_profit', question='Test'
        )

        assert result.success
        assert result.slippage_bps is None
        client.get_orderbook.assert_not_called()
        pm.close_position.assert_called_once()


class TestBuildMetadata:
    """Test _build_metadata does not duplicate column fields."""

    def test_no_column_duplication(self):
        """Metadata should not contain fields already stored as columns."""
        executor, _, _ = _make_executor(slippage_enabled=False)

        request = _make_request(
            asset='BTC',
            strike_price=100000,
            expiry_date='2026-03-01',
        )

        metadata = executor._build_metadata(request)

        # These should NOT be in metadata (stored as columns)
        assert 'outcome' not in metadata
        assert 'entry_price' not in metadata
        assert 'position_size' not in metadata
        assert 'edge' not in metadata
        assert 'confidence' not in metadata
        assert 'signal_reason' not in metadata

        # These SHOULD be in metadata (not columns)
        assert metadata['question'] == 'Will BTC hit $100k?'
        assert metadata['asset'] == 'BTC'
        assert metadata['strike_price'] == 100000
        assert metadata['expiry_date'] == '2026-03-01'

    def test_merges_request_metadata(self):
        """Additional metadata from request.metadata should be merged."""
        executor, _, _ = _make_executor(slippage_enabled=False)

        request = _make_request(
            metadata={'slug': 'btc-100k', 'kelly_fraction': 0.15}
        )

        metadata = executor._build_metadata(request)
        assert metadata['slug'] == 'btc-100k'
        assert metadata['kelly_fraction'] == 0.15


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
