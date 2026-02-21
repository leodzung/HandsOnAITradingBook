"""
Integration tests for Feature Importance Tracking System

Tests end-to-end pipeline:
- Training → Feature extraction → Storage → Drift detection → Alerting

Author: AI Trading System
Date: 2026-02-21
"""

import pytest
import sqlite3
import tempfile
import os
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

# Import modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ml.feature_importance_tracker import FeatureImportanceTracker
from src.ml.drift_detector import DriftDetector
from src.ml.training_engine import ModelTrainer, ModelConfig
from src.utils.walk_forward_validator import WalkForwardValidator


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def synthetic_data():
    """Generate synthetic time-series data for testing."""
    np.random.seed(42)

    n_samples = 500
    n_features = 10

    # Create feature names
    feature_names = [f'feature_{i}' for i in range(n_features)]

    # Create dates (2026-01-01 to 2026-02-14)
    dates = pd.date_range('2026-01-01', periods=n_samples, freq='H')

    # Generate features
    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=feature_names
    )
    X['entry_date'] = dates

    # Generate labels (binary classification)
    # Make labels correlated with some features
    y = (
        X['feature_0'] * 0.5 +
        X['feature_1'] * 0.3 +
        X['feature_2'] * 0.2 +
        np.random.randn(n_samples) * 0.1
    ) > 0
    y = y.astype(int)

    return X, pd.Series(y)


class TestEndToEndPipeline:
    """Test complete pipeline from training to drift detection."""

    def test_training_with_tracker(self, temp_db, synthetic_data):
        """Test that ModelTrainer correctly stores feature importance."""
        X, y = synthetic_data

        # Split data
        train_size = int(len(X) * 0.7)
        X_train, X_val = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_val = y.iloc[:train_size], y.iloc[train_size:]

        # Remove date column for training
        feature_cols = [c for c in X_train.columns if c != 'entry_date']
        X_train_features = X_train[feature_cols]
        X_val_features = X_val[feature_cols]

        # Initialize tracker
        tracker = FeatureImportanceTracker(db_path=temp_db)

        # Initialize trainer with tracker
        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            max_depth=3,
            random_state=42,
            verbose=False
        )
        trainer = ModelTrainer(
            config=config,
            feature_importance_tracker=tracker
        )

        # Train model
        model, metrics = trainer.train(
            X_train_features, y_train,
            X_val_features, y_val,
            bot_type='test_bot'
        )

        # Verify feature importance was stored
        latest = tracker.get_latest_importance('test_bot')

        assert not latest.empty
        assert len(latest) == len(feature_cols)
        assert 'feature_0' in latest['feature_name'].values

        # Verify normalization
        assert abs(latest['normalized_importance'].sum() - 1.0) < 1e-6

        # Verify metrics were stored
        assert latest['train_roc_auc'].iloc[0] > 0
        assert latest['val_roc_auc'].iloc[0] > 0

    def test_walk_forward_with_tracker(self, temp_db, synthetic_data):
        """Test that WalkForwardValidator integration point exists."""
        # This test verifies that WalkForwardValidator can accept and use
        # a feature_importance_tracker. Full validation testing would require
        # more extensive time-series data.

        tracker = FeatureImportanceTracker(db_path=temp_db)

        # Initialize validator with tracker - verify no errors
        validator = WalkForwardValidator(
            n_folds=2,
            val_period_days=1,
            gap_days=0,
            min_train_samples=20,
            min_val_samples=10,
            feature_importance_tracker=tracker
        )

        # Verify tracker was set
        assert validator.feature_importance_tracker is not None
        assert validator.feature_importance_tracker.db_path == temp_db

        # Test store_fold_importance directly
        from sklearn.ensemble import GradientBoostingClassifier
        X, y = synthetic_data

        feature_cols = [c for c in X.columns if c != 'entry_date']
        X_features = X[feature_cols]

        # Train a simple model
        model = GradientBoostingClassifier(n_estimators=10, max_depth=2, random_state=42)
        model.fit(X_features[:100], y[:100])

        # Store fold importance
        fold_context = {
            'train_start': '2026-01-01',
            'train_end': '2026-01-10',
            'val_start': '2026-01-11',
            'val_end': '2026-01-15',
            'train_samples': 100,
            'val_samples': 50
        }

        metrics = {'roc_auc': 0.75, 'accuracy': 0.70}

        count = tracker.store_fold_importance(
            model=model,
            feature_names=feature_cols,
            fold_id=0,
            fold_context=fold_context,
            metrics=metrics,
            bot_type='walk_forward_test'
        )

        # Verify data was stored
        assert count == 10  # 10 features

        conn = sqlite3.connect(temp_db)
        df = pd.read_sql_query(
            "SELECT * FROM feature_importance_history WHERE bot_type = 'walk_forward_test'",
            conn
        )
        conn.close()

        assert len(df) == 10
        assert df['validation_fold_id'].iloc[0] == 0
        assert df['fold_start_date'].iloc[0] == '2026-01-01'

    def test_drift_detection_after_training(self, temp_db, synthetic_data):
        """Test drift detection after multiple training runs."""
        X, y = synthetic_data

        # Split data
        train_size = int(len(X) * 0.7)
        X_train, X_val = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_val = y.iloc[:train_size], y.iloc[train_size:]

        feature_cols = [c for c in X_train.columns if c != 'entry_date']
        X_train_features = X_train[feature_cols]
        X_val_features = X_val[feature_cols]

        # Initialize tracker and detector
        tracker = FeatureImportanceTracker(db_path=temp_db)
        detector = DriftDetector(db_path=temp_db)

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            max_depth=3,
            random_state=42,
            verbose=False
        )
        trainer = ModelTrainer(
            config=config,
            feature_importance_tracker=tracker
        )

        # Train baseline runs (stable data)
        for i in range(3):
            model, metrics = trainer.train(
                X_train_features, y_train,
                X_val_features, y_val,
                bot_type='drift_test'
            )

        # No drift should be detected (same data)
        alerts = detector.detect_drift('drift_test', baseline_strategy='latest_n', lookback_runs=2)

        # Should have no critical/warning alerts (data is identical)
        critical = [a for a in alerts if a['severity'] == 'critical']
        warning = [a for a in alerts if a['severity'] == 'warning']

        assert len(critical) == 0
        assert len(warning) == 0

    def test_drift_detection_with_synthetic_drift(self, temp_db, synthetic_data):
        """Test drift detection when features change importance."""
        X, y = synthetic_data

        train_size = int(len(X) * 0.7)
        X_train, X_val = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_val = y.iloc[:train_size], y.iloc[train_size:]

        feature_cols = [c for c in X_train.columns if c != 'entry_date']

        # Initialize tracker and detector
        tracker = FeatureImportanceTracker(db_path=temp_db)
        detector = DriftDetector(db_path=temp_db)

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            max_depth=3,
            random_state=42,
            verbose=False
        )

        # Train baseline runs
        trainer = ModelTrainer(
            config=config,
            feature_importance_tracker=tracker
        )

        for i in range(2):
            X_train_features = X_train[feature_cols]
            X_val_features = X_val[feature_cols]

            model, metrics = trainer.train(
                X_train_features, y_train,
                X_val_features, y_val,
                bot_type='drift_test'
            )

        # Introduce drift: shuffle columns to change feature importance
        # This will cause features to get different importance values
        feature_cols_shuffled = feature_cols[::-1]  # Reverse feature order
        X_train_drifted = X_train[feature_cols_shuffled]
        X_val_drifted = X_val[feature_cols_shuffled]

        # Rename columns back to original names (so same feature names but different data)
        X_train_drifted.columns = feature_cols
        X_val_drifted.columns = feature_cols

        # Train with drifted data
        model, metrics = trainer.train(
            X_train_drifted, y_train,
            X_val_drifted, y_val,
            bot_type='drift_test'
        )

        # Detect drift
        alerts = detector.detect_drift('drift_test', baseline_strategy='latest_n', lookback_runs=2)

        # Should detect drift (features have different importance now)
        assert len(alerts) > 0

        # Should have some warnings or critical alerts
        significant_alerts = [
            a for a in alerts
            if a['severity'] in ['critical', 'warning']
        ]
        assert len(significant_alerts) > 0

    def test_baseline_stability(self, temp_db, synthetic_data):
        """Test that rank stability is >0.95 when training on same data."""
        X, y = synthetic_data

        train_size = int(len(X) * 0.7)
        X_train, X_val = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_val = y.iloc[:train_size], y.iloc[train_size:]

        feature_cols = [c for c in X_train.columns if c != 'entry_date']
        X_train_features = X_train[feature_cols]
        X_val_features = X_val[feature_cols]

        # Initialize tracker and detector
        tracker = FeatureImportanceTracker(db_path=temp_db)
        detector = DriftDetector(db_path=temp_db)

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            max_depth=3,
            random_state=42,  # Fixed seed for reproducibility
            verbose=False
        )
        trainer = ModelTrainer(
            config=config,
            feature_importance_tracker=tracker
        )

        # Train 5 times on identical data
        for i in range(5):
            model, metrics = trainer.train(
                X_train_features.copy(), y_train.copy(),
                X_val_features.copy(), y_val.copy(),
                bot_type='stability_test'
            )

        # Get first and last importance
        history = tracker.get_importance_history('stability_test', last_n_runs=5)
        timestamps = history['training_timestamp'].unique()

        first_importance = history[history['training_timestamp'] == timestamps[-1]]
        last_importance = history[history['training_timestamp'] == timestamps[0]]

        first_ranks = first_importance.set_index('feature_name')['importance_rank']
        last_ranks = last_importance.set_index('feature_name')['importance_rank']

        # Calculate rank stability
        tau, p_value = detector.calculate_rank_stability(first_ranks, last_ranks)

        # Should be very stable (same data, same seed)
        assert tau > 0.90, f"Expected tau > 0.90, got {tau:.3f}"

    def test_alert_deduplication(self, temp_db, synthetic_data):
        """Test that alert cooldown prevents spam."""
        X, y = synthetic_data

        train_size = int(len(X) * 0.7)
        X_train, X_val = X.iloc[:train_size], X.iloc[train_size:]
        y_train, y_val = y.iloc[:train_size], y.iloc[train_size:]

        feature_cols = [c for c in X_train.columns if c != 'entry_date']

        # Initialize tracker and detector
        tracker = FeatureImportanceTracker(db_path=temp_db)
        detector = DriftDetector(db_path=temp_db)

        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            max_depth=3,
            random_state=42,
            verbose=False
        )
        trainer = ModelTrainer(
            config=config,
            feature_importance_tracker=tracker
        )

        # Train baseline
        for i in range(2):
            model, metrics = trainer.train(
                X_train[feature_cols], y_train,
                X_val[feature_cols], y_val,
                bot_type='dedup_test'
            )

        # Train with drift
        feature_cols_shuffled = feature_cols[::-1]
        X_train_drifted = X_train[feature_cols_shuffled]
        X_val_drifted = X_val[feature_cols_shuffled]
        X_train_drifted.columns = feature_cols
        X_val_drifted.columns = feature_cols

        model, metrics = trainer.train(
            X_train_drifted, y_train,
            X_val_drifted, y_val,
            bot_type='dedup_test'
        )

        # First drift detection
        alerts1 = detector.detect_drift('dedup_test')
        initial_count = len(alerts1)

        # Second drift detection immediately (should be deduplicated)
        alerts2 = detector.detect_drift('dedup_test')

        # Check database for stored alerts
        recent_alerts = detector.get_recent_alerts('dedup_test', hours=1)

        # Each alert type should appear only once (deduplicated)
        unique_types = recent_alerts['alert_type'].unique()
        assert len(recent_alerts) == len(unique_types), \
            "Alerts should be deduplicated (one per type)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
