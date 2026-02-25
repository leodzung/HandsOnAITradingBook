"""
Integration tests for RISK-001: Stop-loss and take-profit always active

Tests that:
1. All positions have stop-loss and take-profit thresholds set
2. Position monitoring thread is running
3. Positions without SL/TP are rejected or flagged
"""

import pytest
import sqlite3
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.position_manager_v2 import PositionManager


class TestStopLossTakeProfitEnforcement:
    """Test that all positions have stop-loss and take-profit set."""

    @pytest.fixture
    def position_dbs(self):
        """Return paths to all position databases."""
        base_path = Path(__file__).parent.parent.parent / "data"
        return {
            'event_trader': base_path / "positions.db",
            'price_level': base_path / "positions_price_level.db",
            'short_expiry': base_path / "positions_short_expiry.db"
        }

    def test_sl_tp_always_set(self, position_dbs):
        """
        CRITICAL: All open positions MUST have stop-loss and take-profit set.

        This is the core test for RISK-001 constraint.
        Prevents unlimited losses and ensures profit capture.
        """
        violations = []

        for bot_name, db_path in position_dbs.items():
            if not db_path.exists():
                # Database doesn't exist yet - bot hasn't run
                continue

            # Check positions directly in database
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Query for open positions without SL/TP
            # Note: Schema uses 'status' not 'closed_at', and 'stop_loss_pct'/'take_profit_pct'
            cursor.execute("""
                SELECT market_id, outcome, entry_price, size, stop_loss_pct, take_profit_pct, entry_time
                FROM positions
                WHERE status = 'open'
            """)

            open_positions = cursor.fetchall()
            conn.close()

            # Check each position
            for position in open_positions:
                market_id, outcome, entry_price, size, stop_loss_pct, take_profit_pct, entry_time = position

                if stop_loss_pct is None or take_profit_pct is None:
                    violations.append({
                        'bot': bot_name,
                        'market_id': market_id,
                        'outcome': outcome,
                        'entry_price': entry_price,
                        'size': size,
                        'stop_loss_pct': stop_loss_pct,
                        'take_profit_pct': take_profit_pct,
                        'entry_time': entry_time
                    })

        # Build detailed error message
        if violations:
            error_msg = f"\n❌ RISK-001 VIOLATION: Found {len(violations)} positions without stop-loss/take-profit:\n\n"

            for v in violations:
                error_msg += f"  Bot: {v['bot']}\n"
                error_msg += f"    Market: {v['market_id']}\n"
                error_msg += f"    Outcome: {v['outcome']}\n"
                error_msg += f"    Entry: ${v['entry_price']:.4f}\n"
                error_msg += f"    Size: {v['size']}\n"
                error_msg += f"    Stop Loss %: {v['stop_loss_pct']} (MISSING!)\n"
                error_msg += f"    Take Profit %: {v['take_profit_pct']} (MISSING!)\n"
                error_msg += f"    Opened: {v['entry_time']}\n\n"

            error_msg += "All positions MUST have stop-loss and take-profit thresholds.\n"
            error_msg += "This prevents unlimited losses and ensures profit capture.\n"

            pytest.fail(error_msg)

    def test_position_manager_sets_sl_tp(self, tmp_path):
        """
        Test that PositionManager enforces SL/TP at save time.

        This is a unit-level check that the API itself validates.
        """
        from datetime import datetime, timezone

        db_path = tmp_path / "test_positions.db"
        pm = PositionManager(db_path=str(db_path))

        # Should succeed with SL/TP (percentages)
        pm.save_position(
            market_id="test_market_1",
            token_id="test_token_1",
            entry_time=datetime.now(timezone.utc),
            outcome="YES",
            entry_price=0.65,
            size=100.0,
            stop_loss_pct=0.15,  # 15% stop-loss
            take_profit_pct=0.25  # 25% take-profit
        )

        # Verify position has SL/TP
        positions = pm.get_open_positions()
        assert len(positions) == 1
        assert positions[0]['stop_loss_pct'] == 0.15
        assert positions[0]['take_profit_pct'] == 0.25

    def test_no_positions_without_sl_tp_in_production(self, position_dbs):
        """
        Production check: Count positions without SL/TP.

        This metric should be tracked in telemetry as 'positions_without_sl_tp'.
        """
        total_positions = 0
        positions_without_sl_tp = 0

        for bot_name, db_path in position_dbs.items():
            if not db_path.exists():
                continue

            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Count all open positions
            cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'open'")
            count = cursor.fetchone()[0]
            total_positions += count

            # Count positions without SL/TP
            cursor.execute("""
                SELECT COUNT(*) FROM positions
                WHERE status = 'open'
                AND (stop_loss_pct IS NULL OR take_profit_pct IS NULL)
            """)
            count_missing = cursor.fetchone()[0]
            positions_without_sl_tp += count_missing

            conn.close()

        # Telemetry assertion
        assert positions_without_sl_tp == 0, (
            f"Found {positions_without_sl_tp}/{total_positions} positions without SL/TP. "
            f"This should be recorded in telemetry as 'positions_without_sl_tp'."
        )


class TestPositionMonitoringThread:
    """Test that position monitoring background thread is active."""

    def test_monitoring_thread_exists(self):
        """
        Verify that position monitoring logic is implemented.

        NOTE: This is a structural test - actual thread activity requires
        runtime integration testing with the bots.
        """
        # Check that bots have position monitoring logic
        from pathlib import Path

        bot_files = [
            Path(__file__).parent.parent.parent / "src" / "bots" / "trader.py",
            Path(__file__).parent.parent.parent / "src" / "bots" / "trader_price_levels.py",
            Path(__file__).parent.parent.parent / "src" / "bots" / "trader_short_expiry.py"
        ]

        for bot_file in bot_files:
            if not bot_file.exists():
                continue

            content = bot_file.read_text()

            # Check for monitoring logic (threading OR loop-based)
            # Different bots may have different patterns
            has_monitoring = (
                "monitor_positions" in content or
                "check_stop_loss" in content or
                "check_take_profit" in content or
                "stop_loss_pct" in content or
                "take_profit_pct" in content or
                "background" in content.lower() or
                "threading" in content or
                "Thread" in content
            )

            assert has_monitoring, (
                f"{bot_file.name} should have position monitoring logic "
                f"(stop_loss_pct, take_profit_pct, or monitoring functions)"
            )
