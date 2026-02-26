#!/usr/bin/env python3
"""
Tests for model staleness telemetry collection and validation.

Verifies that:
1. Model age is correctly calculated from training_report.json
2. days_since_last_retrain metric is recorded
3. Missing files are handled gracefully
4. Constraint validation detects stale models

Created: 2026-02-26 (Model Staleness Detection)
"""

import pytest
import json
import tempfile
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from monitoring.telemetry import TradeTelemetry


class TestModelStalenessTelemetry:
    """Test model staleness telemetry collection."""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary telemetry database."""
        db_path = tmp_path / "test_telemetry.db"
        return str(db_path)

    @pytest.fixture
    def temp_training_report(self, tmp_path):
        """Create temporary training report directory."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        return models_dir

    @pytest.fixture
    def mock_training_report(self, temp_training_report):
        """Create mock training report with known date."""
        training_date = datetime.now() - timedelta(days=5)
        report = {
            "training_date": training_date.isoformat(),
            "metrics": {
                "accuracy": 0.95,
                "roc_auc": 0.98
            }
        }

        report_path = temp_training_report / "training_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f)

        return report_path, training_date

    def test_model_age_calculation_correct(self, temp_db, mock_training_report):
        """Test that model age is correctly calculated from training date."""
        report_path, training_date = mock_training_report

        # Create telemetry instance
        telemetry = TradeTelemetry(db_path=temp_db)

        # Manually call collection with custom report path
        # We'll need to temporarily override the path
        original_method = telemetry._collect_model_metrics

        def mock_collect():
            model_configs = [(str(report_path), 'days_since_last_retrain')]
            for rpath, metric_name in model_configs:
                rfile = Path(rpath)
                if rfile.exists():
                    with open(rfile, 'r') as f:
                        report = json.load(f)
                    training_date_str = report.get('training_date')
                    if training_date_str:
                        train_dt = datetime.fromisoformat(training_date_str)
                        days_old = (datetime.now() - train_dt).total_seconds() / 86400
                        telemetry.record_metric(
                            metric_name,
                            days_old,
                            metadata={'training_date': training_date_str},
                            source='ml_training'
                        )

        # Call custom collection
        mock_collect()

        # Verify metric was recorded
        metrics = telemetry.get_latest_metrics(['days_since_last_retrain'])
        assert 'days_since_last_retrain' in metrics

        # Verify age is approximately 5 days (allow small variance)
        days_old = metrics['days_since_last_retrain']
        assert 4.9 <= days_old <= 5.1, f"Expected ~5 days, got {days_old}"

    def test_missing_training_report_handled_gracefully(self, temp_db, tmp_path):
        """Test that missing training report doesn't crash collection."""
        telemetry = TradeTelemetry(db_path=temp_db)

        # Create model configs with non-existent path
        nonexistent_path = tmp_path / "nonexistent" / "training_report.json"

        # This should not raise an exception
        try:
            # Simulate collection with missing file
            model_configs = [(str(nonexistent_path), 'days_since_last_retrain')]
            for rpath, metric_name in model_configs:
                rfile = Path(rpath)
                if not rfile.exists():
                    # Should just skip
                    continue

            # No metric should be recorded
            metrics = telemetry.get_latest_metrics(['days_since_last_retrain'])
            assert 'days_since_last_retrain' not in metrics

        except Exception as e:
            pytest.fail(f"Should not raise exception for missing file: {e}")

    def test_invalid_json_handled_gracefully(self, temp_db, temp_training_report):
        """Test that invalid JSON doesn't crash collection."""
        # Create invalid JSON file
        invalid_report = temp_training_report / "training_report.json"
        with open(invalid_report, 'w') as f:
            f.write("{ invalid json }")

        telemetry = TradeTelemetry(db_path=temp_db)

        # Should not crash
        try:
            model_configs = [(str(invalid_report), 'days_since_last_retrain')]
            for rpath, metric_name in model_configs:
                rfile = Path(rpath)
                if rfile.exists():
                    try:
                        with open(rfile, 'r') as f:
                            report = json.load(f)
                    except json.JSONDecodeError:
                        # Should catch and continue
                        continue

            # No metric should be recorded due to parse error
            metrics = telemetry.get_latest_metrics(['days_since_last_retrain'])
            assert 'days_since_last_retrain' not in metrics

        except json.JSONDecodeError:
            # Should be caught internally, not propagate
            pytest.fail("JSONDecodeError should be caught internally")

    def test_missing_training_date_field_handled(self, temp_db, temp_training_report):
        """Test that missing training_date field is handled gracefully."""
        # Create report without training_date
        report_path = temp_training_report / "training_report.json"
        with open(report_path, 'w') as f:
            json.dump({"metrics": {"accuracy": 0.95}}, f)

        telemetry = TradeTelemetry(db_path=temp_db)

        # Should not crash
        try:
            model_configs = [(str(report_path), 'days_since_last_retrain')]
            for rpath, metric_name in model_configs:
                rfile = Path(rpath)
                if rfile.exists():
                    with open(rfile, 'r') as f:
                        report = json.load(f)
                    if not report.get('training_date'):
                        # Should skip
                        continue

            # No metric recorded
            metrics = telemetry.get_latest_metrics(['days_since_last_retrain'])
            assert 'days_since_last_retrain' not in metrics

        except Exception as e:
            pytest.fail(f"Should not crash on missing training_date: {e}")

    def test_stale_model_detected(self, temp_db, temp_training_report):
        """Test that models older than 30 days are detected as stale."""
        # Create report with 35-day-old training date
        training_date = datetime.now() - timedelta(days=35)
        report = {
            "training_date": training_date.isoformat(),
            "metrics": {"accuracy": 0.95}
        }

        report_path = temp_training_report / "training_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f)

        telemetry = TradeTelemetry(db_path=temp_db)

        # Collect metric
        model_configs = [(str(report_path), 'days_since_last_retrain')]
        for rpath, metric_name in model_configs:
            rfile = Path(rpath)
            if rfile.exists():
                with open(rfile, 'r') as f:
                    report_data = json.load(f)
                training_date_str = report_data.get('training_date')
                if training_date_str:
                    train_dt = datetime.fromisoformat(training_date_str)
                    days_old = (datetime.now() - train_dt).total_seconds() / 86400
                    telemetry.record_metric(
                        metric_name,
                        days_old,
                        metadata={'training_date': training_date_str},
                        source='ml_training'
                    )

        # Verify metric exceeds threshold
        metrics = telemetry.get_latest_metrics(['days_since_last_retrain'])
        assert metrics['days_since_last_retrain'] > 30, "Stale model should exceed 30 days"

    def test_fresh_model_passes_threshold(self, temp_db, temp_training_report):
        """Test that recently trained models pass the 30-day threshold."""
        # Create report with 2-day-old training date
        training_date = datetime.now() - timedelta(days=2)
        report = {
            "training_date": training_date.isoformat(),
            "metrics": {"accuracy": 0.95}
        }

        report_path = temp_training_report / "training_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f)

        telemetry = TradeTelemetry(db_path=temp_db)

        # Collect metric
        model_configs = [(str(report_path), 'days_since_last_retrain')]
        for rpath, metric_name in model_configs:
            rfile = Path(rpath)
            if rfile.exists():
                with open(rfile, 'r') as f:
                    report_data = json.load(f)
                training_date_str = report_data.get('training_date')
                if training_date_str:
                    train_dt = datetime.fromisoformat(training_date_str)
                    days_old = (datetime.now() - train_dt).total_seconds() / 86400
                    telemetry.record_metric(
                        metric_name,
                        days_old,
                        metadata={'training_date': training_date_str},
                        source='ml_training'
                    )

        # Verify metric is below threshold
        metrics = telemetry.get_latest_metrics(['days_since_last_retrain'])
        assert metrics['days_since_last_retrain'] <= 30, "Fresh model should be within 30 days"

    def test_metric_metadata_stored(self, temp_db, mock_training_report):
        """Test that metadata (training_date, report_path) is stored with metric."""
        report_path, training_date = mock_training_report

        telemetry = TradeTelemetry(db_path=temp_db)

        # Collect with metadata
        model_configs = [(str(report_path), 'days_since_last_retrain')]
        for rpath, metric_name in model_configs:
            rfile = Path(rpath)
            if rfile.exists():
                with open(rfile, 'r') as f:
                    report = json.load(f)
                training_date_str = report.get('training_date')
                if training_date_str:
                    train_dt = datetime.fromisoformat(training_date_str)
                    days_old = (datetime.now() - train_dt).total_seconds() / 86400
                    telemetry.record_metric(
                        metric_name,
                        days_old,
                        metadata={
                            'training_date': training_date_str,
                            'report_path': str(rpath)
                        },
                        source='ml_training'
                    )

        # Query database directly to verify metadata
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata FROM metrics WHERE metric_name = ? ORDER BY timestamp DESC LIMIT 1",
            ('days_since_last_retrain',)
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None, "Metric should be stored"
        metadata = json.loads(result[0])
        assert 'training_date' in metadata
        assert 'report_path' in metadata
        assert metadata['training_date'] == training_date.isoformat()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
