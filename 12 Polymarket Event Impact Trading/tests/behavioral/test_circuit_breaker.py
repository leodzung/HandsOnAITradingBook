"""
Behavioral tests for RISK-002: Circuit breaker after 3 consecutive losses

Validates that trading pauses after 3 consecutive losing trades and
automatically resumes after cooldown period.

Implementation: RiskManager class in src/bots/trader.py
- Triggers when consecutive_losses >= circuit_breaker_losses (default 3)
- Cooldown period: circuit_breaker_cooldown_hours (default 4.0 hours)
- Auto-resume after cooldown with consecutive_losses reset to 0
"""

import pytest
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.bots.trader import RiskManager


class TestCircuitBreakerTrigger:
    """Test that circuit breaker triggers after 3 consecutive losses."""

    def test_circuit_breaker_class_exists(self):
        """Verify RiskManager class exists and can be instantiated."""
        rm = RiskManager()
        assert rm is not None

    def test_circuit_breaker_attributes_exist(self):
        """Verify circuit breaker attributes exist."""
        rm = RiskManager()

        # Check required attributes
        assert hasattr(rm, 'consecutive_losses')
        assert hasattr(rm, 'circuit_breaker_active')
        assert hasattr(rm, 'circuit_breaker_triggered_at')
        assert hasattr(rm, 'circuit_breaker_losses')
        assert hasattr(rm, 'circuit_breaker_cooldown_hours')

    def test_initial_state_no_circuit_breaker(self):
        """Verify initial state has circuit breaker inactive."""
        rm = RiskManager()

        assert rm.consecutive_losses == 0
        assert rm.circuit_breaker_active is False
        assert rm.circuit_breaker_triggered_at is None

    def test_single_loss_does_not_trigger(self):
        """Single loss should not trigger circuit breaker."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate 1 loss
        rm.remove_position('market_1', pnl=-10.0)

        assert rm.consecutive_losses == 1
        assert rm.circuit_breaker_active is False

    def test_two_losses_do_not_trigger(self):
        """Two consecutive losses should not trigger circuit breaker."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate 2 losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)

        assert rm.consecutive_losses == 2
        assert rm.circuit_breaker_active is False

    def test_three_losses_trigger_circuit_breaker(self):
        """
        CRITICAL: Three consecutive losses MUST trigger circuit breaker.

        This is the core requirement of RISK-002.
        """
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate 3 consecutive losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        # Circuit breaker should be active
        assert rm.consecutive_losses == 3
        assert rm.circuit_breaker_active is True
        assert rm.circuit_breaker_triggered_at is not None

    def test_win_resets_consecutive_losses(self):
        """Win should reset consecutive losses counter to 0."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate 2 losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        assert rm.consecutive_losses == 2

        # Simulate 1 win - should reset counter
        rm.remove_position('market_3', pnl=25.0)
        assert rm.consecutive_losses == 0
        assert rm.circuit_breaker_active is False


class TestCircuitBreakerBlocking:
    """Test that circuit breaker prevents new positions."""

    def test_can_open_position_when_no_circuit_breaker(self):
        """Should be able to open positions when circuit breaker not active."""
        rm = RiskManager()

        can_open, reason = rm.can_open_position(position_size=50.0)

        assert can_open is True
        assert reason == "OK"

    def test_cannot_open_position_when_circuit_breaker_active(self):
        """
        CRITICAL: Cannot open positions when circuit breaker is active.

        This is the enforcement mechanism for RISK-002.
        """
        rm = RiskManager(circuit_breaker_losses=3)

        # Trigger circuit breaker with 3 losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        # Should not be able to open new position
        can_open, reason = rm.can_open_position(position_size=50.0)

        assert can_open is False
        assert 'circuit breaker' in reason.lower()
        assert '3 consecutive losses' in reason.lower()

    def test_check_circuit_breaker_returns_active_status(self):
        """check_circuit_breaker should return (True, reason) when active."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Trigger circuit breaker
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        is_active, reason = rm.check_circuit_breaker()

        assert is_active is True
        assert reason != ""
        assert 'consecutive losses' in reason.lower()


class TestCircuitBreakerCooldown:
    """Test circuit breaker cooldown and auto-resume."""

    def test_circuit_breaker_has_cooldown_period(self):
        """Verify circuit breaker has configurable cooldown period."""
        rm = RiskManager(circuit_breaker_cooldown_hours=4.0)

        assert rm.circuit_breaker_cooldown_hours == 4.0

    def test_cooldown_period_configurable(self):
        """Cooldown period should be configurable."""
        rm1 = RiskManager(circuit_breaker_cooldown_hours=2.0)
        rm2 = RiskManager(circuit_breaker_cooldown_hours=8.0)

        assert rm1.circuit_breaker_cooldown_hours == 2.0
        assert rm2.circuit_breaker_cooldown_hours == 8.0

    def test_circuit_breaker_does_not_reset_immediately(self):
        """Circuit breaker should NOT reset immediately after trigger."""
        rm = RiskManager(circuit_breaker_losses=3, circuit_breaker_cooldown_hours=4.0)

        # Trigger circuit breaker
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        # Check immediately - should still be active
        is_active, reason = rm.check_circuit_breaker()

        assert is_active is True
        assert rm.circuit_breaker_active is True

    def test_circuit_breaker_auto_resets_after_cooldown(self):
        """
        CRITICAL: Circuit breaker MUST auto-reset after cooldown period.

        This ensures trading can resume automatically without manual intervention.
        """
        rm = RiskManager(circuit_breaker_losses=3, circuit_breaker_cooldown_hours=0.001)  # 3.6 seconds

        # Trigger circuit breaker
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        assert rm.circuit_breaker_active is True

        # Wait for cooldown (0.001 hours = 3.6 seconds)
        time.sleep(4)

        # Check circuit breaker - should auto-reset
        is_active, reason = rm.check_circuit_breaker()

        assert is_active is False
        assert rm.circuit_breaker_active is False
        assert rm.consecutive_losses == 0
        assert rm.circuit_breaker_triggered_at is None

    def test_consecutive_losses_reset_to_zero_after_cooldown(self):
        """After cooldown, consecutive_losses should be reset to 0."""
        rm = RiskManager(circuit_breaker_losses=3, circuit_breaker_cooldown_hours=0.001)

        # Trigger circuit breaker
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        assert rm.consecutive_losses == 3

        # Wait for cooldown
        time.sleep(4)

        # Check circuit breaker - should reset consecutive_losses
        rm.check_circuit_breaker()

        assert rm.consecutive_losses == 0

    def test_can_open_position_after_cooldown(self):
        """Should be able to open positions after cooldown period."""
        rm = RiskManager(circuit_breaker_losses=3, circuit_breaker_cooldown_hours=0.001)

        # Trigger circuit breaker
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        # Wait for cooldown
        time.sleep(4)

        # Should be able to open position now
        can_open, reason = rm.can_open_position(position_size=50.0)

        assert can_open is True
        assert reason == "OK"


class TestCircuitBreakerEdgeCases:
    """Test edge cases and corner cases."""

    def test_zero_pnl_resets_losses(self):
        """Break-even trade (pnl=0) should reset consecutive losses."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate 2 losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        assert rm.consecutive_losses == 2

        # Break-even trade should reset (pnl >= 0 logic)
        rm.remove_position('market_3', pnl=0.0)
        assert rm.consecutive_losses == 0

    def test_custom_threshold_configurable(self):
        """Circuit breaker threshold should be configurable."""
        rm1 = RiskManager(circuit_breaker_losses=2)
        rm2 = RiskManager(circuit_breaker_losses=5)

        assert rm1.circuit_breaker_losses == 2
        assert rm2.circuit_breaker_losses == 5

    def test_custom_threshold_2_losses_triggers(self):
        """With threshold=2, should trigger after 2 losses."""
        rm = RiskManager(circuit_breaker_losses=2)

        # Simulate 2 losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)

        assert rm.consecutive_losses == 2
        assert rm.circuit_breaker_active is True

    def test_custom_threshold_5_losses_required(self):
        """With threshold=5, should NOT trigger after 4 losses."""
        rm = RiskManager(circuit_breaker_losses=5)

        # Simulate 4 losses
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)
        rm.remove_position('market_4', pnl=-25.0)

        assert rm.consecutive_losses == 4
        assert rm.circuit_breaker_active is False

        # 5th loss should trigger
        rm.remove_position('market_5', pnl=-30.0)
        assert rm.consecutive_losses == 5
        assert rm.circuit_breaker_active is True

    def test_alternating_wins_losses_never_trigger(self):
        """Alternating wins/losses should never trigger circuit breaker."""
        rm = RiskManager(circuit_breaker_losses=3)

        # Simulate alternating pattern (10 trades)
        for i in range(10):
            if i % 2 == 0:
                rm.remove_position(f'market_{i}', pnl=-10.0)  # Loss
            else:
                rm.remove_position(f'market_{i}', pnl=15.0)   # Win

        # Should never trigger because losses are not consecutive
        assert rm.circuit_breaker_active is False
        assert rm.consecutive_losses in [0, 1]  # Either 0 (just won) or 1 (just lost)


class TestCircuitBreakerIntegration:
    """Integration tests for complete circuit breaker flow."""

    def test_complete_lifecycle_trigger_cooldown_resume(self):
        """
        Test complete lifecycle: trigger → cooldown → auto-resume → trading resumes.

        This validates the end-to-end RISK-002 requirement.
        """
        rm = RiskManager(circuit_breaker_losses=3, circuit_breaker_cooldown_hours=0.001)

        # Phase 1: Trigger circuit breaker
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)

        assert rm.circuit_breaker_active is True
        assert rm.consecutive_losses == 3

        # Phase 2: Cannot open positions during cooldown
        can_open, reason = rm.can_open_position(position_size=50.0)
        assert can_open is False

        # Phase 3: Wait for cooldown
        time.sleep(4)

        # Phase 4: Auto-resume - can open positions again
        can_open, reason = rm.can_open_position(position_size=50.0)
        assert can_open is True
        assert rm.circuit_breaker_active is False
        assert rm.consecutive_losses == 0

    def test_multiple_circuit_breaker_cycles(self):
        """Test that circuit breaker can trigger multiple times."""
        rm = RiskManager(circuit_breaker_losses=3, circuit_breaker_cooldown_hours=0.001)

        # Cycle 1: Trigger and reset
        rm.remove_position('market_1', pnl=-10.0)
        rm.remove_position('market_2', pnl=-15.0)
        rm.remove_position('market_3', pnl=-20.0)
        assert rm.circuit_breaker_active is True

        time.sleep(4)
        rm.check_circuit_breaker()  # Reset
        assert rm.circuit_breaker_active is False

        # Cycle 2: Trigger again
        rm.remove_position('market_4', pnl=-10.0)
        rm.remove_position('market_5', pnl=-15.0)
        rm.remove_position('market_6', pnl=-20.0)
        assert rm.circuit_breaker_active is True
        assert rm.consecutive_losses == 3
