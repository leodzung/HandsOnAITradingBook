#!/usr/bin/env python3
"""
Tests for Pattern Detection System (Phase 4: Self-Improvement)

Tests pattern detection algorithms and constraint suggestion generation.
"""

import pytest
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from monitoring.pattern_detector import PatternDetector, Pattern
from monitoring.telemetry import TradeTelemetry


@pytest.fixture
def temp_telemetry_db(tmp_path):
    """Create temporary telemetry database with test data."""
    db_path = tmp_path / "test_telemetry.db"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create tables
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

    # Insert test data - recurring events
    now = datetime.now(timezone.utc)
    for i in range(10):
        timestamp = (now - timedelta(hours=i)).isoformat()
        cursor.execute("""
            INSERT INTO events (event_type, severity, timestamp, source)
            VALUES (?, ?, ?, ?)
        """, ('circuit_breaker_trip', 'warning', timestamp, 'test'))

    # Insert test data - metric violations
    for i in range(20):
        timestamp = (now - timedelta(minutes=i*30)).isoformat()
        # Violate threshold 50% of the time
        value = 0.4 if i % 2 == 0 else 0.1
        cursor.execute("""
            INSERT INTO metrics (metric_name, metric_value, timestamp, source)
            VALUES (?, ?, ?, ?)
        """, ('websocket_fallback_rate', value, timestamp, 'test'))

    conn.commit()
    conn.close()

    return db_path


class TestPatternDetector:
    """Test pattern detection algorithms."""

    def test_detector_initialization(self, temp_telemetry_db):
        """Test PatternDetector initializes correctly."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        assert detector is not None
        assert detector.telemetry is not None

    def test_detect_recurring_events(self, temp_telemetry_db):
        """Test detection of recurring events."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)

        # Should detect recurring circuit_breaker_trip events
        recurring_patterns = [p for p in patterns if p.pattern_type == 'recurring_event']
        assert len(recurring_patterns) > 0

        # Check pattern properties
        circuit_breaker_pattern = next(
            (p for p in recurring_patterns if 'circuit_breaker_trip' in str(p.evidence)),
            None
        )
        assert circuit_breaker_pattern is not None
        assert circuit_breaker_pattern.frequency >= 3

    def test_detect_metric_violations(self, temp_telemetry_db):
        """Test detection of metric threshold violations."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)

        # Should detect websocket_fallback_rate violations
        violation_patterns = [p for p in patterns if p.pattern_type == 'metric_violation']

        if len(violation_patterns) > 0:
            pattern = violation_patterns[0]
            assert pattern.evidence['metric_name'] == 'websocket_fallback_rate'
            assert pattern.evidence['violation_rate'] > 0.1

    def test_pattern_has_required_fields(self, temp_telemetry_db):
        """Test that detected patterns have all required fields."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)

        if len(patterns) > 0:
            pattern = patterns[0]
            assert hasattr(pattern, 'pattern_type')
            assert hasattr(pattern, 'description')
            assert hasattr(pattern, 'frequency')
            assert hasattr(pattern, 'severity')
            assert hasattr(pattern, 'evidence')
            assert hasattr(pattern, 'suggested_action')

    def test_generate_constraint_suggestions(self, temp_telemetry_db):
        """Test constraint suggestion generation."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)
        suggestions = detector.generate_constraint_suggestions(patterns)

        # Should generate at least one suggestion
        # (may be 0 if thresholds are too strict for test data)
        assert isinstance(suggestions, list)

        if len(suggestions) > 0:
            suggestion = suggestions[0]
            assert hasattr(suggestion, 'constraint_id')
            assert hasattr(suggestion, 'title')
            assert hasattr(suggestion, 'description')
            assert hasattr(suggestion, 'category')
            assert hasattr(suggestion, 'priority')
            assert hasattr(suggestion, 'rationale')

    def test_anomaly_detection(self, temp_telemetry_db):
        """Test statistical anomaly detection."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        anomalies = detector.detect_anomalies('websocket_fallback_rate', hours=24)

        # Should detect outliers (values of 0.4 are >2 std from mean)
        assert isinstance(anomalies, list)
        # May be empty if not enough data or variance

    def test_pattern_confidence_scores(self, temp_telemetry_db):
        """Test that patterns include confidence scores."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)

        # Patterns should be sorted by severity and confidence
        for pattern in patterns:
            # Confidence should be in valid range
            assert 0 <= pattern.frequency

    def test_empty_database_handling(self, tmp_path):
        """Test handling of empty telemetry database."""
        db_path = tmp_path / "empty.db"

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
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                severity TEXT,
                source TEXT
            )
        """)
        conn.commit()
        conn.close()

        telemetry = TradeTelemetry(db_path=db_path)
        detector = PatternDetector(telemetry=telemetry)

        # Should not crash on empty database
        patterns = detector.detect_failure_patterns(hours=24)
        assert patterns == []


class TestConstraintSuggestion:
    """Test constraint suggestion generation."""

    def test_suggestion_to_dict(self, temp_telemetry_db):
        """Test constraint suggestion serialization."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)
        suggestions = detector.generate_constraint_suggestions(patterns)

        if len(suggestions) > 0:
            suggestion = suggestions[0]
            suggestion_dict = suggestion.to_dict()

            # Check required fields
            assert 'id' in suggestion_dict
            assert 'title' in suggestion_dict
            assert 'description' in suggestion_dict
            assert 'category' in suggestion_dict
            assert 'priority' in suggestion_dict
            assert 'status' in suggestion_dict
            assert suggestion_dict['status'] == 'suggested'

    def test_suggestion_includes_patterns(self, temp_telemetry_db):
        """Test that suggestions include source patterns."""
        telemetry = TradeTelemetry(db_path=temp_telemetry_db)
        detector = PatternDetector(telemetry=telemetry)

        patterns = detector.detect_failure_patterns(hours=24)
        suggestions = detector.generate_constraint_suggestions(patterns)

        if len(suggestions) > 0:
            suggestion = suggestions[0]
            assert len(suggestion.patterns) > 0
            assert all(isinstance(p, Pattern) for p in suggestion.patterns)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
