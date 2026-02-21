"""
Unit tests for FeatureImportanceTracker and DriftDetector

Tests:
- Database schema creation
- Feature importance storage and retrieval
- Drift metrics calculation
- Alert generation and cooldown
- Baseline strategies

Author: AI Trading System
Date: 2026-02-21
"""

import pytest
import sqlite3
import tempfile
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Import the modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.ml.feature_importance_tracker import FeatureImportanceTracker
from src.ml.drift_detector import DriftDetector


class MockModel:
    """Mock model for testing."""

    def __init__(self, feature_importances, model_type='tree'):
        if model_type == 'tree':
            self.feature_importances_ = np.array(feature_importances)
        elif model_type == 'linear':
            self.coef_ = np.array([feature_importances])

    def __class__(self):
        return type('GradientBoostingClassifier', (), {})


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def tracker(temp_db):
    """Create a FeatureImportanceTracker with temporary database."""
    return FeatureImportanceTracker(db_path=temp_db)


@pytest.fixture
def detector(temp_db):
    """Create a DriftDetector with temporary database."""
    return DriftDetector(db_path=temp_db)


class TestFeatureImportanceTracker:
    """Test FeatureImportanceTracker functionality."""

    def test_database_initialization(self, tracker):
        """Test that database tables are created correctly."""
        conn = sqlite3.connect(tracker.db_path)
        cursor = conn.cursor()

        # Check feature_importance_history table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='feature_importance_history'
        """)
        assert cursor.fetchone() is not None

        # Check drift_detection_alerts table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='drift_detection_alerts'
        """)
        assert cursor.fetchone() is not None

        # Check indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        indexes = cursor.fetchall()
        assert len(indexes) >= 3  # At least 3 indexes created

        conn.close()

    def test_store_importance_tree_model(self, tracker):
        """Test storing importance from tree-based model."""
        # Create mock model
        importances = [0.5, 0.3, 0.15, 0.05]
        feature_names = ['feature_A', 'feature_B', 'feature_C', 'feature_D']
        model = MockModel(importances, model_type='tree')

        metrics = {
            'train_roc_auc': 0.85,
            'val_roc_auc': 0.82,
            'test_roc_auc': 0.80
        }

        training_context = {'training_samples': 1000}

        # Store importance
        count = tracker.store_importance(
            bot_type='test_bot',
            model=model,
            feature_names=feature_names,
            metrics=metrics,
            training_context=training_context
        )

        assert count == 4

        # Verify data in database
        conn = sqlite3.connect(tracker.db_path)
        df = pd.read_sql_query(
            "SELECT * FROM feature_importance_history WHERE bot_type = 'test_bot'",
            conn
        )
        conn.close()

        assert len(df) == 4
        assert df['bot_type'].iloc[0] == 'test_bot'
        assert df['num_features'].iloc[0] == 4
        assert df['training_samples'].iloc[0] == 1000

        # Check normalization (sum should be 1.0)
        assert abs(df['normalized_importance'].sum() - 1.0) < 1e-6

        # Check ranking
        assert df[df['feature_name'] == 'feature_A']['importance_rank'].iloc[0] == 1
        assert df[df['feature_name'] == 'feature_B']['importance_rank'].iloc[0] == 2

    def test_store_importance_linear_model(self, tracker):
        """Test storing importance from linear model."""
        # Linear models use abs(coef_)
        coefficients = [0.8, -0.6, 0.4, -0.2]  # Mix of positive/negative
        feature_names = ['feat1', 'feat2', 'feat3', 'feat4']
        model = MockModel(coefficients, model_type='linear')

        metrics = {'train_roc_auc': 0.75, 'val_roc_auc': 0.73}
        training_context = {'training_samples': 500}

        count = tracker.store_importance(
            bot_type='linear_bot',
            model=model,
            feature_names=feature_names,
            metrics=metrics,
            training_context=training_context
        )

        assert count == 4

        # Verify absolute values are used
        conn = sqlite3.connect(tracker.db_path)
        df = pd.read_sql_query(
            "SELECT * FROM feature_importance_history WHERE bot_type = 'linear_bot' ORDER BY importance_rank",
            conn
        )
        conn.close()

        # feat1 (0.8) should be rank 1, feat2 (0.6) should be rank 2
        assert df.iloc[0]['feature_name'] == 'feat1'
        assert df.iloc[1]['feature_name'] == 'feat2'

    def test_store_fold_importance(self, tracker):
        """Test storing fold-level importance."""
        importances = [0.4, 0.3, 0.2, 0.1]
        feature_names = ['f1', 'f2', 'f3', 'f4']
        model = MockModel(importances)

        fold_context = {
            'train_start': '2026-01-01',
            'train_end': '2026-01-31',
            'val_start': '2026-02-01',
            'val_end': '2026-02-07',
            'train_samples': 800,
            'val_samples': 200
        }

        metrics = {'train_roc_auc': 0.88, 'val_roc_auc': 0.84}

        count = tracker.store_fold_importance(
            model=model,
            feature_names=feature_names,
            fold_id=0,
            fold_context=fold_context,
            metrics=metrics,
            bot_type='walk_forward'
        )

        assert count == 4

        # Verify fold context stored
        conn = sqlite3.connect(tracker.db_path)
        df = pd.read_sql_query(
            "SELECT * FROM feature_importance_history WHERE validation_fold_id = 0",
            conn
        )
        conn.close()

        assert len(df) == 4
        assert df['validation_fold_id'].iloc[0] == 0
        assert df['fold_start_date'].iloc[0] == '2026-01-01'
        assert df['fold_end_date'].iloc[0] == '2026-01-31'

    def test_get_latest_importance(self, tracker):
        """Test retrieving latest importance."""
        # Store two training runs
        for i in range(2):
            importances = [0.5 - i*0.1, 0.3, 0.2 + i*0.1]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        # Get latest
        latest = tracker.get_latest_importance('test')

        assert len(latest) == 3
        # Should have data from second run (i=1)
        assert latest.iloc[0]['importance_score'] == pytest.approx(0.4, abs=0.01)

    def test_get_importance_history(self, tracker):
        """Test retrieving historical importance."""
        # Store 5 training runs
        for i in range(5):
            importances = [0.5, 0.3, 0.2]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['X', 'Y', 'Z'],
                metrics={'val_roc_auc': 0.8 - i*0.01},
                training_context={'training_samples': 100 + i*10}
            )

        # Get last 3 runs
        history = tracker.get_importance_history('test', last_n_runs=3)

        # Should have 3 runs × 3 features = 9 rows
        assert len(history) == 9

        # Check timestamps are unique
        timestamps = history['training_timestamp'].unique()
        assert len(timestamps) == 3

    def test_get_training_timestamps(self, tracker):
        """Test retrieving training timestamps."""
        # Store 3 runs
        for i in range(3):
            model = MockModel([0.5, 0.5])
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        timestamps = tracker.get_training_timestamps('test')

        assert len(timestamps) == 3
        # Should be in descending order (most recent first)
        assert timestamps[0] > timestamps[1] > timestamps[2]


class TestDriftDetector:
    """Test DriftDetector functionality."""

    def test_calculate_rank_stability_perfect(self, detector):
        """Test rank stability with identical rankings."""
        baseline = pd.Series([1, 2, 3, 4, 5], index=['A', 'B', 'C', 'D', 'E'])
        current = pd.Series([1, 2, 3, 4, 5], index=['A', 'B', 'C', 'D', 'E'])

        tau, p_value = detector.calculate_rank_stability(baseline, current)

        assert tau == pytest.approx(1.0, abs=0.01)  # Perfect correlation
        assert p_value < 0.05  # Significant

    def test_calculate_rank_stability_shuffled(self, detector):
        """Test rank stability with shuffled rankings."""
        baseline = pd.Series([1, 2, 3, 4, 5], index=['A', 'B', 'C', 'D', 'E'])
        current = pd.Series([5, 4, 3, 2, 1], index=['A', 'B', 'C', 'D', 'E'])  # Reversed

        tau, p_value = detector.calculate_rank_stability(baseline, current)

        assert tau == pytest.approx(-1.0, abs=0.01)  # Perfect negative correlation

    def test_calculate_importance_shift_identical(self, detector):
        """Test L1 distance with identical distributions."""
        baseline = pd.Series([0.5, 0.3, 0.2], index=['A', 'B', 'C'])
        current = pd.Series([0.5, 0.3, 0.2], index=['A', 'B', 'C'])

        l1 = detector.calculate_importance_shift(baseline, current)

        assert l1 == pytest.approx(0.0, abs=0.01)

    def test_calculate_importance_shift_different(self, detector):
        """Test L1 distance with different distributions."""
        baseline = pd.Series([0.5, 0.3, 0.2], index=['A', 'B', 'C'])
        current = pd.Series([0.2, 0.3, 0.5], index=['A', 'B', 'C'])  # Swapped A and C

        l1 = detector.calculate_importance_shift(baseline, current)

        # |0.5-0.2| + |0.3-0.3| + |0.2-0.5| = 0.3 + 0 + 0.3 = 0.6
        assert l1 == pytest.approx(0.6, abs=0.01)

    def test_calculate_top_k_overlap_perfect(self, detector):
        """Test top-K overlap with perfect overlap."""
        baseline = ['A', 'B', 'C', 'D', 'E']
        current = ['A', 'B', 'C', 'D', 'E']

        overlap = detector.calculate_top_k_overlap(baseline, current, k=5)

        assert overlap == pytest.approx(1.0, abs=0.01)

    def test_calculate_top_k_overlap_partial(self, detector):
        """Test top-K overlap with partial overlap."""
        baseline = ['A', 'B', 'C', 'D', 'E']
        current = ['A', 'B', 'F', 'G', 'H']  # 2 out of 5 match

        overlap = detector.calculate_top_k_overlap(baseline, current, k=5)

        # Intersection = 2 (A, B), Union = 8 (A, B, C, D, E, F, G, H)
        expected = 2 / 8
        assert overlap == pytest.approx(expected, abs=0.01)

    def test_get_baseline_latest_n(self, detector, tracker):
        """Test baseline computation with 'latest_n' strategy."""
        # Store 3 runs with varying importance
        for i in range(3):
            importances = [0.5 + i*0.05, 0.3 - i*0.05, 0.2]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        # Get baseline (average of last 3 runs)
        baseline = detector.get_baseline('test', strategy='latest_n', lookback_runs=3)

        assert len(baseline) == 3
        # Check that importance is averaged
        # A: (0.5 + 0.55 + 0.6) / 3 = 0.55
        a_importance = baseline[baseline['feature_name'] == 'A']['importance_score'].iloc[0]
        assert a_importance == pytest.approx(0.55, abs=0.01)

    def test_get_baseline_best_auc(self, detector, tracker):
        """Test baseline computation with 'best_auc' strategy."""
        # Store 3 runs with different AUCs
        for i, auc in enumerate([0.75, 0.85, 0.78]):
            importances = [0.5 + i*0.1, 0.3, 0.2 - i*0.1]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C'],
                metrics={'val_roc_auc': auc},
                training_context={'training_samples': 100}
            )

        # Get baseline (run with highest AUC = i=1, AUC=0.85)
        baseline = detector.get_baseline('test', strategy='best_auc', lookback_runs=3)

        assert len(baseline) == 3
        # Should have importance from run with i=1
        a_importance = baseline[baseline['feature_name'] == 'A']['importance_score'].iloc[0]
        assert a_importance == pytest.approx(0.6, abs=0.01)

    def test_detect_drift_no_drift(self, detector, tracker):
        """Test drift detection when there's no drift."""
        # Store baseline runs (stable importance)
        for i in range(3):
            importances = [0.5, 0.3, 0.2]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        # Detect drift
        alerts = detector.detect_drift('test', baseline_strategy='latest_n', lookback_runs=2)

        # Should have no critical/warning alerts (maybe info alerts)
        critical = [a for a in alerts if a['severity'] == 'critical']
        warning = [a for a in alerts if a['severity'] == 'warning']

        assert len(critical) == 0
        assert len(warning) == 0

    def test_detect_drift_rank_shift(self, detector, tracker):
        """Test drift detection when ranks change significantly."""
        # Store baseline runs with stable ranking
        for i in range(2):
            importances = [0.5, 0.3, 0.15, 0.05]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C', 'D'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        # Store current run with shuffled ranking
        importances = [0.05, 0.15, 0.3, 0.5]  # Reversed order
        model = MockModel(importances)
        tracker.store_importance(
            bot_type='test',
            model=model,
            feature_names=['A', 'B', 'C', 'D'],
            metrics={'val_roc_auc': 0.8},
            training_context={'training_samples': 100}
        )

        # Detect drift
        alerts = detector.detect_drift('test', baseline_strategy='latest_n', lookback_runs=2)

        # Should have rank_shift alerts
        rank_alerts = [a for a in alerts if a['alert_type'] == 'rank_shift']
        assert len(rank_alerts) > 0

        # Should be critical (tau will be negative)
        critical_rank_alerts = [a for a in rank_alerts if a['severity'] == 'critical']
        assert len(critical_rank_alerts) > 0

    def test_detect_drift_importance_drop(self, detector, tracker):
        """Test drift detection when top feature importance drops."""
        # Store baseline with high importance for A
        for i in range(2):
            importances = [0.8, 0.1, 0.05, 0.05]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C', 'D'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        # Store current run with A importance dropped by 90%
        importances = [0.08, 0.5, 0.3, 0.12]  # A dropped from 0.8 to 0.08
        model = MockModel(importances)
        tracker.store_importance(
            bot_type='test',
            model=model,
            feature_names=['A', 'B', 'C', 'D'],
            metrics={'val_roc_auc': 0.8},
            training_context={'training_samples': 100}
        )

        # Detect drift
        alerts = detector.detect_drift('test', baseline_strategy='latest_n', lookback_runs=2)

        # Should have importance_drop alert for feature A
        drop_alerts = [a for a in alerts if a['alert_type'] == 'importance_drop']
        assert len(drop_alerts) > 0

        # Should mention feature A
        a_alerts = [a for a in drop_alerts if 'A' in a['affected_features']]
        assert len(a_alerts) > 0

    def test_alert_cooldown(self, detector, tracker):
        """Test that alert cooldown prevents spam."""
        # Store baseline and current with drift
        for i in range(2):
            importances = [0.5, 0.3, 0.2]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        # Store current with drift
        importances = [0.2, 0.3, 0.5]
        model = MockModel(importances)
        tracker.store_importance(
            bot_type='test',
            model=model,
            feature_names=['A', 'B', 'C'],
            metrics={'val_roc_auc': 0.8},
            training_context={'training_samples': 100}
        )

        # First drift detection
        alerts1 = detector.detect_drift('test', baseline_strategy='latest_n', lookback_runs=2)
        initial_count = len(alerts1)
        assert initial_count > 0

        # Second drift detection immediately after (should be suppressed by cooldown)
        alerts2 = detector.detect_drift('test', baseline_strategy='latest_n', lookback_runs=2)

        # Alerts should be suppressed (not stored in DB again)
        # Check database directly
        recent_alerts = detector.get_recent_alerts('test', hours=1)

        # Should only have alerts from first detection (duplicates filtered)
        unique_alert_types = recent_alerts['alert_type'].unique()
        # Each alert type should appear only once
        assert len(recent_alerts) == len(unique_alert_types)

    def test_acknowledge_alert(self, detector, tracker):
        """Test acknowledging alerts."""
        # Generate some alerts
        for i in range(2):
            importances = [0.5, 0.3, 0.2]
            model = MockModel(importances)
            tracker.store_importance(
                bot_type='test',
                model=model,
                feature_names=['A', 'B', 'C'],
                metrics={'val_roc_auc': 0.8},
                training_context={'training_samples': 100}
            )

        importances = [0.2, 0.3, 0.5]
        model = MockModel(importances)
        tracker.store_importance(
            bot_type='test',
            model=model,
            feature_names=['A', 'B', 'C'],
            metrics={'val_roc_auc': 0.8},
            training_context={'training_samples': 100}
        )

        detector.detect_drift('test', baseline_strategy='latest_n', lookback_runs=2)

        # Get unacknowledged alerts
        unack_before = detector.get_recent_alerts('test', acknowledged=False)
        assert len(unack_before) > 0

        # Acknowledge first alert
        first_alert_id = unack_before.iloc[0]['id']
        detector.acknowledge_alert(first_alert_id)

        # Check acknowledgment
        unack_after = detector.get_recent_alerts('test', acknowledged=False)
        assert len(unack_after) == len(unack_before) - 1

        ack_after = detector.get_recent_alerts('test', acknowledged=True)
        assert len(ack_after) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
