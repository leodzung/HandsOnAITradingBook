#!/usr/bin/env python3
"""
Tests for Walk-Forward Validator

Verifies temporal ordering, no data leakage, and expanding window behavior.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from walk_forward_validator import WalkForwardValidator, FoldMetrics, ValidationReport
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, \
    roc_auc_score, brier_score_loss


@pytest.fixture
def synthetic_timeseries_data():
    """Create synthetic time-series data for testing."""
    np.random.seed(42)
    n_samples = 5000  # More samples for better testing
    # Use hourly frequency to get enough samples per validation window
    dates = pd.date_range('2024-01-01', periods=n_samples, freq='h')

    X = pd.DataFrame({
        'entry_date': dates,
        'feature1': np.random.randn(n_samples),
        'feature2': np.random.randn(n_samples),
        'feature3': np.random.randn(n_samples)
    })

    # Labels with some signal
    y = ((X['feature1'] > 0) & (X['feature2'] > 0)).astype(int)

    return X, y


def test_split_generation(synthetic_timeseries_data):
    """Verify splits maintain temporal order and are properly sized."""
    X, y = synthetic_timeseries_data

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=30,
        min_train_samples=100,
        min_val_samples=20
    )

    splits = validator.split(X, y, date_column='entry_date')

    # Should generate 3 folds
    assert len(splits) >= 2, "Should generate at least 2 folds with sufficient data"

    # Check each split
    for train_idx, val_idx in splits:
        # Non-empty
        assert len(train_idx) > 0, "Train set should not be empty"
        assert len(val_idx) > 0, "Val set should not be empty"

        # No overlap
        overlap = set(train_idx) & set(val_idx)
        assert len(overlap) == 0, "Train and val sets should not overlap"


def test_no_temporal_leakage(synthetic_timeseries_data):
    """Ensure no future data in training set (critical for time-series)."""
    X, y = synthetic_timeseries_data

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=30
    )

    splits = validator.split(X, y, date_column='entry_date')
    dates = pd.to_datetime(X['entry_date'])

    for fold_id, (train_idx, val_idx) in enumerate(splits, 1):
        train_dates = dates.iloc[train_idx]
        val_dates = dates.iloc[val_idx]

        max_train_date = train_dates.max()
        min_val_date = val_dates.min()

        # CRITICAL: All training dates must be before validation dates
        assert max_train_date < min_val_date, \
            f"Fold {fold_id}: Temporal leakage detected! " \
            f"Max train date ({max_train_date}) >= Min val date ({min_val_date})"


def test_expanding_window(synthetic_timeseries_data):
    """Verify training set grows across folds (expanding window)."""
    X, y = synthetic_timeseries_data

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=30
    )

    splits = validator.split(X, y, date_column='entry_date')

    train_sizes = [len(train_idx) for train_idx, _ in splits]

    # Training set should grow or stay the same (expanding window)
    for i in range(1, len(train_sizes)):
        assert train_sizes[i] >= train_sizes[i-1], \
            f"Training size should grow: fold {i} ({train_sizes[i]}) < fold {i-1} ({train_sizes[i-1]})"


def test_validation_window_consistency(synthetic_timeseries_data):
    """Verify validation windows are approximately the specified length."""
    X, y = synthetic_timeseries_data

    val_period_days = 30

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=val_period_days
    )

    splits = validator.split(X, y, date_column='entry_date')
    dates = pd.to_datetime(X['entry_date'])

    for fold_id, (_, val_idx) in enumerate(splits, 1):
        val_dates = dates.iloc[val_idx]
        val_duration = (val_dates.max() - val_dates.min()).days

        # Allow some tolerance (±5 days) due to data sparsity
        assert abs(val_duration - val_period_days) <= 5, \
            f"Fold {fold_id}: Validation period ({val_duration} days) " \
            f"differs significantly from target ({val_period_days} days)"


def test_minimum_samples_enforced(synthetic_timeseries_data):
    """Verify minimum sample size constraints are respected."""
    X, y = synthetic_timeseries_data

    min_train = 500
    min_val = 100

    validator = WalkForwardValidator(
        n_folds=5,
        val_period_days=30,
        min_train_samples=min_train,
        min_val_samples=min_val
    )

    splits = validator.split(X, y, date_column='entry_date')

    for fold_id, (train_idx, val_idx) in enumerate(splits, 1):
        assert len(train_idx) >= min_train, \
            f"Fold {fold_id}: Train samples ({len(train_idx)}) below minimum ({min_train})"
        assert len(val_idx) >= min_val, \
            f"Fold {fold_id}: Val samples ({len(val_idx)}) below minimum ({min_val})"


def test_full_validation_run(synthetic_timeseries_data):
    """Test complete validation pipeline end-to-end."""
    X, y = synthetic_timeseries_data

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=30
    )

    # Model factory
    def model_factory():
        return GradientBoostingClassifier(
            n_estimators=20,
            max_depth=3,
            learning_rate=0.1,
            random_state=42
        )

    # Evaluation function
    def eval_fn(model, X_eval, y_eval):
        feature_cols = [c for c in X_eval.columns if c != 'entry_date']
        X_features = X_eval[feature_cols]

        y_pred = model.predict(X_features)
        y_proba = model.predict_proba(X_features)[:, 1]

        return {
            'accuracy': accuracy_score(y_eval, y_pred),
            'precision': precision_score(y_eval, y_pred, zero_division=0),
            'recall': recall_score(y_eval, y_pred, zero_division=0),
            'f1': f1_score(y_eval, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y_eval, y_proba),
            'brier_score': brier_score_loss(y_eval, y_proba)
        }

    # Run validation
    report = validator.validate(X, y, model_factory, eval_fn, date_column='entry_date')

    # Verify report structure
    assert isinstance(report, ValidationReport)
    assert len(report.fold_metrics) >= 2, "Should have at least 2 folds"
    assert 0 <= report.mean_roc_auc <= 1, "Mean AUC should be in [0, 1]"
    assert 0 <= report.std_roc_auc <= 1, "Std AUC should be in [0, 1]"
    assert 0 <= report.mean_accuracy <= 1, "Mean accuracy should be in [0, 1]"

    # Check fold metrics
    for fold_metric in report.fold_metrics:
        assert fold_metric['train_samples'] > 0
        assert fold_metric['val_samples'] > 0
        assert 0 <= fold_metric['roc_auc'] <= 1


def test_gap_days_enforcement(synthetic_timeseries_data):
    """Test that gap days create separation between train and val."""
    X, y = synthetic_timeseries_data

    gap_days = 7

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=30,
        gap_days=gap_days
    )

    splits = validator.split(X, y, date_column='entry_date')
    dates = pd.to_datetime(X['entry_date'])

    for fold_id, (train_idx, val_idx) in enumerate(splits, 1):
        train_dates = dates.iloc[train_idx]
        val_dates = dates.iloc[val_idx]

        max_train_date = train_dates.max()
        min_val_date = val_dates.min()

        gap = (min_val_date - max_train_date).days

        # Gap should be at least the specified days
        assert gap >= gap_days, \
            f"Fold {fold_id}: Gap ({gap} days) is less than specified ({gap_days} days)"


def test_missing_date_column_error():
    """Verify error when date column is missing."""
    X = pd.DataFrame({
        'feature1': np.random.randn(100),
        'feature2': np.random.randn(100)
    })
    y = np.random.randint(0, 2, 100)

    validator = WalkForwardValidator(n_folds=3)

    with pytest.raises(ValueError, match="Date column .* not found"):
        validator.split(X, y, date_column='entry_date')


def test_insufficient_data_warning(synthetic_timeseries_data):
    """Test that validator handles insufficient data gracefully."""
    X, y = synthetic_timeseries_data

    # Take only small subset
    X_small = X.iloc[:1500].copy()  # About 2 months of hourly data
    y_small = y.iloc[:1500].copy()

    validator = WalkForwardValidator(
        n_folds=10,  # Too many folds for data size
        val_period_days=15,  # Smaller validation period
        min_train_samples=100,
        min_val_samples=30  # Lower minimum
    )

    # Should not raise exception, but reduce folds
    splits = validator.split(X_small, y_small, date_column='entry_date')

    # Should generate fewer than 10 folds
    assert len(splits) < 10, "Should reduce folds when data is insufficient"
    assert len(splits) >= 1, "Should generate at least one fold"


def test_class_distribution_preserved(synthetic_timeseries_data):
    """Verify class distributions are reasonable across folds."""
    X, y = synthetic_timeseries_data

    validator = WalkForwardValidator(n_folds=3)

    splits = validator.split(X, y, date_column='entry_date')

    for fold_id, (train_idx, val_idx) in enumerate(splits, 1):
        y_train = y.iloc[train_idx]
        y_val = y.iloc[val_idx]

        # Both classes should be present (at least 5% each)
        train_pos_ratio = y_train.mean()
        val_pos_ratio = y_val.mean()

        assert 0.05 <= train_pos_ratio <= 0.95, \
            f"Fold {fold_id}: Train set too imbalanced ({train_pos_ratio:.2%})"
        assert 0.05 <= val_pos_ratio <= 0.95, \
            f"Fold {fold_id}: Val set too imbalanced ({val_pos_ratio:.2%})"


def test_deterministic_splits():
    """Verify splits are deterministic (same input -> same output)."""
    np.random.seed(123)
    n_samples = 3000
    # Use hourly frequency to ensure enough samples per validation window
    dates = pd.date_range('2024-01-01', periods=n_samples, freq='h')

    X = pd.DataFrame({
        'entry_date': dates,
        'feature1': np.random.randn(n_samples)
    })
    y = np.random.randint(0, 2, n_samples)

    validator = WalkForwardValidator(
        n_folds=3,
        val_period_days=15,
        min_val_samples=50
    )

    # Generate splits twice
    splits1 = validator.split(X, y, date_column='entry_date')
    splits2 = validator.split(X, y, date_column='entry_date')

    # Should be identical
    assert len(splits1) == len(splits2)
    for (train1, val1), (train2, val2) in zip(splits1, splits2):
        assert np.array_equal(train1, train2), "Train indices should be deterministic"
        assert np.array_equal(val1, val2), "Val indices should be deterministic"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
