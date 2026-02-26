#!/usr/bin/env python3
"""
Tests for Auto-Remediation System (Phase 4: Self-Improvement)

Tests automatic remediation actions and safety checks.
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from monitoring.auto_remediation import (
    AutoRemediator,
    RemediationAction,
    create_safe_remediation_actions
)
from monitoring.telemetry import TradeTelemetry


@pytest.fixture
def temp_telemetry_db(tmp_path):
    """Create temporary telemetry database."""
    db_path = tmp_path / "test_telemetry.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            metadata TEXT,
            source TEXT,
            UNIQUE(timestamp, metric_name)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            event_data TEXT,
            severity TEXT,
            timestamp TEXT NOT NULL,
            source TEXT
        )
    """)

    conn.commit()
    conn.close()

    return db_path


class TestRemediationAction:
    """Test RemediationAction class."""

    def test_action_initialization(self):
        """Test RemediationAction initializes correctly."""
        def test_fix():
            return {'status': 'success'}

        action = RemediationAction(
            action_id='test_action',
            description='Test action',
            severity='low',
            fix_function=test_fix
        )

        assert action.action_id == 'test_action'
        assert action.description == 'Test action'
        assert action.severity == 'low'
        assert callable(action.fix_function)

    def test_action_preconditions(self):
        """Test precondition checking."""
        def test_fix():
            return {'status': 'success'}

        # Action with met precondition
        action_met = RemediationAction(
            action_id='test_action',
            description='Test action',
            severity='low',
            fix_function=test_fix,
            preconditions=[lambda: True]
        )
        assert action_met.can_remediate() is True

        # Action with unmet precondition
        action_unmet = RemediationAction(
            action_id='test_action',
            description='Test action',
            severity='low',
            fix_function=test_fix,
            preconditions=[lambda: False]
        )
        assert action_unmet.can_remediate() is False

    def test_action_execution_dry_run(self):
        """Test action execution in dry-run mode."""
        def test_fix():
            return {'status': 'success'}

        action = RemediationAction(
            action_id='test_action',
            description='Test action',
            severity='low',
            fix_function=test_fix
        )

        result = action.execute(dry_run=True)

        assert result['action_id'] == 'test_action'
        assert result['status'] == 'dry_run'
        assert 'executed_at' in result

    def test_action_execution_success(self):
        """Test successful action execution."""
        def test_fix():
            return {'cleaned': 5, 'files': []}

        action = RemediationAction(
            action_id='test_action',
            description='Test action',
            severity='low',
            fix_function=test_fix
        )

        result = action.execute(dry_run=False)

        assert result['action_id'] == 'test_action'
        assert result['status'] == 'success'
        assert result['result']['cleaned'] == 5

    def test_action_execution_failure(self):
        """Test failed action execution."""
        def test_fix():
            raise Exception("Test error")

        action = RemediationAction(
            action_id='test_action',
            description='Test action',
            severity='low',
            fix_function=test_fix
        )

        result = action.execute(dry_run=False)

        assert result['action_id'] == 'test_action'
        assert result['status'] == 'failed'
        assert 'error' in result
        assert 'Test error' in result['error']


class TestAutoRemediator:
    """Test AutoRemediator class."""

    def test_remediator_initialization(self, temp_telemetry_db):
        """Test AutoRemediator initializes correctly."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        assert remediator is not None
        assert remediator.enabled is True
        assert len(remediator.actions) > 0

    def test_remediator_disabled(self, temp_telemetry_db):
        """Test that disabled remediator does not execute actions."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry, enabled=False)

        result = remediator.run_remediation()

        assert result['status'] == 'disabled'
        assert result['actions_executed'] == []

    def test_run_remediation_dry_run(self, temp_telemetry_db):
        """Test dry-run mode."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        safe_actions = create_safe_remediation_actions()
        result = remediator.run_remediation(dry_run=True, action_ids=safe_actions)

        assert result['status'] == 'dry_run'
        assert result['total_executed'] >= 0
        assert all(a['status'] == 'dry_run' for a in result['actions_executed'])

    def test_run_safe_actions_only(self, temp_telemetry_db):
        """Test running only safe remediation actions."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        safe_actions = create_safe_remediation_actions()
        result = remediator.run_remediation(dry_run=True, action_ids=safe_actions)

        # Safe actions should include cleanup and compact
        assert any('cleanup_temp_files' == a['action_id'] for a in result['actions_executed'])
        assert any('compact_telemetry_db' == a['action_id'] for a in result['actions_executed'])

    def test_precondition_filtering(self, temp_telemetry_db):
        """Test that actions with unmet preconditions are skipped."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        # Run all actions (some should have unmet preconditions)
        result = remediator.run_remediation(dry_run=True)

        # Should have both executed and skipped actions
        assert 'actions_skipped' in result
        assert 'total_skipped' in result

    def test_result_summary(self, temp_telemetry_db):
        """Test remediation result summary."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        result = remediator.run_remediation(dry_run=True)

        # Check summary fields
        assert 'status' in result
        assert 'timestamp' in result
        assert 'actions_executed' in result
        assert 'actions_skipped' in result
        assert 'total_executed' in result
        assert 'total_skipped' in result
        assert 'successes' in result
        assert 'failures' in result

    def test_cleanup_temp_files_action(self, temp_telemetry_db, tmp_path):
        """Test cleanup temp files remediation."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        # This is a safe action, test in dry-run mode
        result = remediator.run_remediation(
            dry_run=True,
            action_ids=['cleanup_temp_files']
        )

        assert len(result['actions_executed']) == 1
        assert result['actions_executed'][0]['action_id'] == 'cleanup_temp_files'

    def test_compact_db_action(self, temp_telemetry_db):
        """Test database compaction remediation."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        remediator = AutoRemediator(telemetry=telemetry)

        # Test in dry-run mode
        result = remediator.run_remediation(
            dry_run=True,
            action_ids=['compact_telemetry_db']
        )

        assert len(result['actions_executed']) == 1
        assert result['actions_executed'][0]['action_id'] == 'compact_telemetry_db'


class TestSafeActions:
    """Test safe remediation actions list."""

    def test_safe_actions_defined(self):
        """Test that safe actions are properly defined."""
        safe_actions = create_safe_remediation_actions()

        assert isinstance(safe_actions, list)
        assert len(safe_actions) > 0
        assert all(isinstance(action_id, str) for action_id in safe_actions)

    def test_safe_actions_are_safe(self):
        """Test that safe actions do not include risky operations."""
        safe_actions = create_safe_remediation_actions()

        # Should not include actions that restart services or bots
        assert 'restart_silent_bots' not in safe_actions
        assert 'reset_websocket' not in safe_actions

        # Should include maintenance actions
        assert 'cleanup_temp_files' in safe_actions
        assert 'compact_telemetry_db' in safe_actions


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
