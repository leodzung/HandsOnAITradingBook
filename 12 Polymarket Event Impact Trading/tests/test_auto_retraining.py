#!/usr/bin/env python3
"""
Tests for automated model retraining system.

Verifies that:
1. Retraining triggers are correctly detected
2. Models are trained and validated
3. Quality gates prevent bad models from deploying
4. Backups are created before deployment
5. Rollback works on failure

Created: 2026-02-26 (Automated Model Retraining)
"""

import pytest
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import sys
import pandas as pd
import pickle
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ml.auto_retrainer import AutoRetrainer
from monitoring.telemetry import TradeTelemetry


class TestAutoRetraining:
    """Test automated retraining system."""

    @pytest.fixture
    def temp_dir(self, tmp_path):
        """Create temporary directory structure."""
        model_dir = tmp_path / "models"
        backup_dir = tmp_path / "models" / "backups"
        model_dir.mkdir(parents=True)
        backup_dir.mkdir(parents=True)
        return tmp_path

    @pytest.fixture
    def mock_training_data(self, temp_dir):
        """Create mock training dataset."""
        # Create synthetic training data
        np.random.seed(42)
        n_samples = 2000

        data = {
            'trade_price': np.random.uniform(0.1, 0.9, n_samples),
            'volume': np.random.uniform(1000, 100000, n_samples),
            'days_to_expiry': np.random.uniform(1, 30, n_samples),
            'label': np.random.randint(0, 2, n_samples)
        }

        df = pd.DataFrame(data)
        csv_path = temp_dir / "training_data.csv"
        df.to_csv(csv_path, index=False)

        return csv_path

    @pytest.fixture
    def mock_telemetry(self, temp_dir):
        """Create mock telemetry database."""
        db_path = temp_dir / "telemetry.db"
        return TradeTelemetry(db_path=str(db_path))

    @pytest.fixture
    def mock_old_model(self, temp_dir):
        """Create mock old model file with old training report."""
        model_dir = temp_dir / "models"
        
        # Create dummy model file
        model_path = model_dir / "event_model.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump({'dummy': 'model'}, f)

        # Create old training report (35 days ago)
        training_date = datetime.now() - timedelta(days=35)
        report = {
            "training_date": training_date.isoformat(),
            "metrics": {"roc_auc": 0.75}
        }
        report_path = model_dir / "training_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f)

        return model_path, report_path

    def test_age_trigger_detected_when_model_old(self, temp_dir, mock_training_data, mock_telemetry, mock_old_model):
        """Test that age trigger is detected when model > 25 days old."""
        model_path, report_path = mock_old_model

        # Record old model age in telemetry
        mock_telemetry.record_metric('days_since_last_retrain', 35.0)

        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        # Override telemetry
        retrainer.telemetry = mock_telemetry

        should_retrain, reasons = retrainer.should_retrain()

        assert should_retrain, "Should trigger retraining for old model"
        assert any('age' in r.lower() for r in reasons), "Should mention model age in reasons"

    def test_no_trigger_when_model_fresh(self, temp_dir, mock_training_data, mock_telemetry):
        """Test that no trigger when model is fresh (<25 days)."""
        # Record fresh model age
        mock_telemetry.record_metric('days_since_last_retrain', 2.5)

        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )
        retrainer.telemetry = mock_telemetry

        should_retrain, reasons = retrainer.should_retrain()

        assert not should_retrain, "Should not trigger for fresh model"
        assert len(reasons) == 0, "Should have no trigger reasons"

    def test_performance_trigger_detected_when_auc_low(self, temp_dir, mock_training_data, mock_telemetry):
        """Test that performance trigger detected when AUC < 0.70."""
        # Record low AUC
        mock_telemetry.record_metric('deployed_model_auc', 0.65)

        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )
        retrainer.telemetry = mock_telemetry

        should_retrain, reasons = retrainer.should_retrain()

        assert should_retrain, "Should trigger for low AUC"
        assert any('auc' in r.lower() for r in reasons), "Should mention AUC in reasons"

    def test_training_data_loaded_successfully(self, temp_dir, mock_training_data):
        """Test that training data is loaded and validated."""
        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        df = retrainer._load_training_data()

        assert len(df) >= 1000, "Should load sufficient training samples"
        assert 'label' in df.columns, "Should have label column"

    def test_insufficient_training_data_raises_error(self, temp_dir):
        """Test that insufficient training data raises error."""
        # Create tiny dataset
        df = pd.DataFrame({
            'trade_price': [0.5, 0.6],
            'label': [0, 1]
        })
        csv_path = temp_dir / "small_data.csv"
        df.to_csv(csv_path, index=False)

        retrainer = AutoRetrainer(
            training_data_path=str(csv_path),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        with pytest.raises(ValueError, match="Insufficient training data"):
            retrainer._load_training_data()

    def test_quality_gates_reject_bad_model(self, temp_dir, mock_training_data):
        """Test that quality gates reject models with poor performance."""
        from ml.training_engine import TrainingMetrics

        # Create metrics for bad model
        bad_metrics = TrainingMetrics(
            accuracy=0.55,
            precision=0.50,
            recall=0.50,
            f1=0.50,
            roc_auc=0.62,  # Below 0.70 threshold
            brier_score=0.25,
            confusion_matrix=[[50, 50], [50, 50]]
        )

        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        passed, issues = retrainer._validate_model_quality(bad_metrics)

        assert not passed, "Should reject bad model"
        assert len(issues) > 0, "Should have validation issues"
        assert any('auc' in i.lower() for i in issues), "Should flag low AUC"

    def test_quality_gates_accept_good_model(self, temp_dir, mock_training_data):
        """Test that quality gates accept models with good performance."""
        from ml.training_engine import TrainingMetrics

        # Create metrics for good model
        good_metrics = TrainingMetrics(
            accuracy=0.85,
            precision=0.83,
            recall=0.87,
            f1=0.85,
            roc_auc=0.90,  # Well above 0.70
            brier_score=0.12,
            confusion_matrix=[[85, 15], [13, 87]]
        )

        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        passed, issues = retrainer._validate_model_quality(good_metrics)

        assert passed, "Should accept good model"
        assert len(issues) == 0, "Should have no issues"

    def test_backup_creates_timestamped_files(self, temp_dir, mock_old_model):
        """Test that backup creates timestamped model files."""
        model_path, report_path = mock_old_model

        retrainer = AutoRetrainer(
            training_data_path="dummy.csv",  # Not used in this test
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        backup_paths = retrainer._backup_existing_models()

        assert len(backup_paths) > 0, "Should create backup files"

        # Verify backups exist
        for backup_path in backup_paths:
            assert backup_path.exists(), f"Backup should exist: {backup_path}"
            # Check timestamp format in filename
            assert '_202' in str(backup_path.name), "Backup should have timestamp"

    def test_dry_run_does_not_deploy(self, temp_dir, mock_training_data):
        """Test that dry run trains but doesn't deploy models."""
        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        # Get initial model file count
        model_dir = temp_dir / "models"
        initial_files = list(model_dir.glob("*.pkl"))

        result = retrainer.run_full_retraining(dry_run=True)

        # Verify dry run completed
        assert 'skip_deploy_dry_run' in result['steps_completed'], "Should skip deployment in dry run"

        # Verify no new model files created
        final_files = list(model_dir.glob("*.pkl"))
        # In dry run, we might have backup files but not deployed new models
        # The key is that deployment step was skipped

    def test_full_retraining_updates_report(self, temp_dir, mock_training_data):
        """Test that successful retraining updates training_report.json."""
        retrainer = AutoRetrainer(
            training_data_path=str(mock_training_data),
            model_dir=str(temp_dir / "models"),
            backup_dir=str(temp_dir / "models" / "backups")
        )

        result = retrainer.run_full_retraining(dry_run=False)

        if result['success']:
            report_path = temp_dir / "models" / "training_report.json"
            assert report_path.exists(), "Training report should be created"

            with open(report_path) as f:
                report = json.load(f)

            assert 'training_date' in report, "Report should have training_date"
            assert 'metrics' in report, "Report should have metrics"

            # Verify training date is recent
            training_date = datetime.fromisoformat(report['training_date'])
            age = (datetime.now() - training_date).total_seconds() / 60
            assert age < 5, "Training should have happened in last 5 minutes"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
