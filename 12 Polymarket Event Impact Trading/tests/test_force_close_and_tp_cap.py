"""
Tests for two critical fixes:
1. TradeExecutor force_close: skip slippage for mandatory exits (expiry, market_closed, etc.)
2. TP cap at $1.00: Polymarket prices max at 1.0, so TP targets must be capped.
"""

import sys
from pathlib import Path

# Add src/ to path so trade_executor can resolve 'from core.xxx' imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from core.trade_executor import TradeExecutor, TradeResult


# --- TradeExecutor force_close tests ---

class TestTradeExecutorForceClose:
    """TradeExecutor must skip slippage checks for mandatory exit reasons."""

    def _make_executor(self, slippage_enabled=True):
        """Create a TradeExecutor with mocked dependencies."""
        client = MagicMock()
        position_manager = MagicMock()
        config = {
            'slippage_estimation': {'enabled': slippage_enabled},
            'max_entry_price': 0.9,
        }
        executor = TradeExecutor(
            client=client,
            position_manager=position_manager,
            config=config,
            paper_trading=True,
        )
        return executor

    def test_forced_exit_reasons_defined(self):
        """FORCED_EXIT_REASONS should include all mandatory exit types."""
        expected = {'expiry_time', 'market_closed', 'pre_expiry_exit', 'expiry', 'time_exit'}
        assert expected == TradeExecutor.FORCED_EXIT_REASONS

    @pytest.mark.parametrize("exit_reason", [
        'expiry_time', 'market_closed', 'pre_expiry_exit', 'expiry', 'time_exit',
    ])
    def test_force_close_skips_slippage_for_mandatory_reasons(self, exit_reason):
        """Mandatory exit reasons must bypass slippage check even with no liquidity."""
        executor = self._make_executor(slippage_enabled=True)

        # Slippage estimator would reject (no liquidity), but should be skipped
        executor.slippage_estimator.estimate_slippage = MagicMock(
            side_effect=AssertionError("Should not be called for forced exits")
        )
        executor.client.get_orderbook = MagicMock(return_value=None)

        result = executor.execute_close_trade(
            market_id='0xtest',
            outcome='YES',
            token_id='0xtest_YES',
            exit_price=0.95,
            position_size=50.0,
            exit_reason=exit_reason,
            question='Test market?',
        )

        assert result.success, f"Force close failed for {exit_reason}: {result.reason}"

    @pytest.mark.parametrize("exit_reason", ['stop_loss', 'take_profit', 'trailing_stop'])
    def test_normal_exits_still_check_slippage(self, exit_reason):
        """Non-mandatory exits should still go through slippage validation."""
        executor = self._make_executor(slippage_enabled=True)

        # Return empty orderbook -> should fail slippage check
        executor.client.get_orderbook = MagicMock(return_value=None)

        result = executor.execute_close_trade(
            market_id='0xtest',
            outcome='YES',
            token_id='0xtest_YES',
            exit_price=0.95,
            position_size=50.0,
            exit_reason=exit_reason,
            question='Test market?',
        )

        assert not result.success, f"Expected slippage rejection for {exit_reason}"

    def test_explicit_force_close_param_skips_slippage(self):
        """Explicit force_close=True should skip slippage even for normal exit reasons."""
        executor = self._make_executor(slippage_enabled=True)
        executor.client.get_orderbook = MagicMock(return_value=None)

        result = executor.execute_close_trade(
            market_id='0xtest',
            outcome='NO',
            token_id='0xtest_NO',
            exit_price=0.5,
            position_size=30.0,
            exit_reason='stop_loss',
            force_close=True,
        )

        assert result.success

    def test_force_close_when_slippage_disabled(self):
        """If slippage is disabled, all closes should succeed regardless."""
        executor = self._make_executor(slippage_enabled=False)

        result = executor.execute_close_trade(
            market_id='0xtest',
            outcome='YES',
            token_id='0xtest_YES',
            exit_price=0.8,
            position_size=40.0,
            exit_reason='stop_loss',
        )

        assert result.success


# --- TP cap at $1.00 tests ---

class TestTPCapAtOneDollar:
    """Take-profit target must be capped at $1.00 (Polymarket max price)."""

    def _make_risk_manager(self, tp_pct=50, sl_pct=15):
        """Create a ShortExpiryRiskManager with given TP/SL."""
        from src.bots.trader_short_expiry import ShortExpiryRiskManager
        config = {
            'risk_management': {
                'take_profit_pct': {'short': tp_pct, 'ultra_short': tp_pct, 'medium': tp_pct},
                'stop_loss_pct': {'short': sl_pct, 'ultra_short': sl_pct, 'medium': sl_pct},
                'pre_expiry_exit_hours': 1,
                'circuit_breaker_losses': 5,
            },
            'time_decay_tp_sl': {'enabled': False},
        }
        return ShortExpiryRiskManager(config)

    def test_tp_unreachable_when_entry_high(self):
        """Entry at $0.94 with 50% TP = target $1.41 > $1.00 -> should cap and trigger TP."""
        rm = self._make_risk_manager(tp_pct=50)
        position = {
            'entry_price': 0.94,
            'entry_time': datetime.now(timezone.utc) - timedelta(hours=10),
            'hours_to_expiry_at_entry': 48,
        }
        # Capped TP% = (1.0 - 0.94) / 0.94 * 100 = 6.38%
        # At price 1.00 -> PnL% = 6.38% -> triggers
        result = rm.should_exit(position, current_price=1.0, bucket='short')
        assert result == 'take_profit', f"Expected take_profit but got {result}"

    def test_tp_unreachable_entry_0_77(self):
        """Entry at $0.77 with 50% TP = $1.155 -> should cap at $1.00."""
        rm = self._make_risk_manager(tp_pct=50)
        position = {
            'entry_price': 0.77,
            'entry_time': datetime.now(timezone.utc) - timedelta(hours=5),
            'hours_to_expiry_at_entry': 48,
        }
        # Capped TP% = (1.0 - 0.77) / 0.77 * 100 = 29.87%
        # At price 1.0 -> PnL = 29.87% -> triggers
        result = rm.should_exit(position, current_price=1.0, bucket='short')
        assert result == 'take_profit'

    def test_tp_not_capped_when_entry_low(self):
        """Entry at $0.30 with 50% TP = $0.45 -> below $1.00, no cap needed."""
        rm = self._make_risk_manager(tp_pct=50)
        position = {
            'entry_price': 0.30,
            'entry_time': datetime.now(timezone.utc) - timedelta(hours=5),
            'hours_to_expiry_at_entry': 48,
        }
        # Normal TP at 50% -> target $0.45
        # At $0.44 -> PnL 46.7% -> should NOT trigger
        result = rm.should_exit(position, current_price=0.44, bucket='short')
        assert result is None, f"Should not trigger TP at $0.44, got {result}"

        # At $0.46 -> PnL 53.3% -> SHOULD trigger
        result = rm.should_exit(position, current_price=0.46, bucket='short')
        assert result == 'take_profit'

    def test_tp_cap_minimum_margin(self):
        """Entry at $0.999 -> capped TP% should be at least 0.5% (minimum margin)."""
        rm = self._make_risk_manager(tp_pct=50)
        position = {
            'entry_price': 0.999,
            'entry_time': datetime.now(timezone.utc) - timedelta(hours=5),
            'hours_to_expiry_at_entry': 48,
        }
        # (1.0 - 0.999) / 0.999 * 100 = 0.1% -> below minimum 0.5%
        # So TP should be 0.5% -> target $1.004 (impossible)
        # At $1.0 -> PnL = 0.1% -> should NOT trigger (0.1% < 0.5%)
        result = rm.should_exit(position, current_price=1.0, bucket='short')
        assert result is None, "0.1% gain should not trigger 0.5% min TP"

    def test_stop_loss_still_works_with_capped_tp(self):
        """SL should still work normally even when TP is capped."""
        rm = self._make_risk_manager(tp_pct=50, sl_pct=15)
        position = {
            'entry_price': 0.94,
            'entry_time': datetime.now(timezone.utc) - timedelta(hours=5),
            'hours_to_expiry_at_entry': 48,
        }
        # SL at 15% -> triggers at $0.94 * 0.85 = $0.799
        result = rm.should_exit(position, current_price=0.79, bucket='short')
        assert result == 'stop_loss'


# --- Structural tests ---

class TestTPCapStructural:
    """Verify all 3 bots implement TP cap at $1.00."""

    BOT_FILES = [
        "src/bots/trader.py",
        "src/bots/trader_price_levels.py",
        "src/bots/trader_short_expiry.py",
    ]

    def test_all_bots_have_tp_cap(self):
        """All bot files must contain TP cap at $1.00 logic."""
        missing = []
        for bot_file in self.BOT_FILES:
            path = Path(bot_file)
            if not path.exists():
                missing.append(f"{bot_file} (not found)")
                continue
            content = path.read_text()
            if 'tp_target > 1.0' not in content:
                missing.append(bot_file)

        if missing:
            pytest.fail(
                f"Bot files missing TP cap at $1.00:\n"
                + "\n".join(f"  - {f}" for f in missing)
            )


class TestForceCloseStructural:
    """Verify TradeExecutor has FORCED_EXIT_REASONS."""

    def test_forced_exit_reasons_exists(self):
        """TradeExecutor must define FORCED_EXIT_REASONS class attribute."""
        content = Path("src/core/trade_executor.py").read_text()
        assert 'FORCED_EXIT_REASONS' in content
        assert 'force_close' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
