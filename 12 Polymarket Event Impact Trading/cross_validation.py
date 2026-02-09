#!/usr/bin/env python3
"""
Unified Cross-Validation Interface
Wraps WalkForwardValidator with standardized API and enforces best practices.
"""

import numpy as np
import pandas as pd
from typing import Callable, Any, Optional
from datetime import datetime, timedelta
import logging

from walk_forward_validator import WalkForwardValidator, ValidationReport
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, brier_score_loss
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UnifiedCrossValidator:
    """
    Unified cross-validation interface with enforced best practices.

    Features:
    - Enforces k >= 5 minimum folds
    - Handles datasets without date columns (injects synthetic dates)
    - Provides simple API for sklearn models
    - Returns comprehensive ValidationReport
    """

    def __init__(self, n_folds: int = 5,
                 val_period_days: int = 30,
                 gap_days: int = 0,
                 min_samples_per_fold: int = 50):
        """
        Initialize cross-validator.

        Args:
            n_folds: Number of folds (must be >= 5)
            val_period_days: Length of validation period in days
            gap_days: Embargo period between train/val
            min_samples_per_fold: Minimum samples required per fold

        Raises:
            ValueError: If n_folds < 5
        """
        if n_folds < 5:
            raise ValueError(
                f"n_folds must be >= 5 for robust validation. Got: {n_folds}\n"
                f"Rationale: With k < 5, variance in performance estimates is too high "
                f"to reliably assess production readiness."
            )

        self.n_folds = n_folds
        self.val_period_days = val_period_days
        self.gap_days = gap_days
        self.min_samples_per_fold = min_samples_per_fold

        # Calculate minimum training samples (need enough for all folds)
        self.min_train_samples = min_samples_per_fold * 2

        logger.info(f"Initialized UnifiedCrossValidator:")
        logger.info(f"  n_folds: {n_folds}")
        logger.info(f"  val_period_days: {val_period_days}")
        logger.info(f"  min_samples_per_fold: {min_samples_per_fold}")

    def _inject_synthetic_dates(self, X: pd.DataFrame) -> pd.DataFrame:
        """
        Inject synthetic dates for temporal splitting when no date column exists.

        Spreads samples evenly across time to simulate realistic temporal ordering.

        Args:
            X: Features DataFrame without date column

        Returns:
            DataFrame with 'entry_date' column added
        """
        logger.info("No date column found - injecting synthetic dates for temporal splitting")

        X = X.copy()

        # Create dates spanning the validation period requirements
        n_samples = len(X)
        # Total days needed: n_folds * val_period_days + buffer for training
        total_days = self.n_folds * self.val_period_days + 60  # 60 day buffer

        # Spread samples evenly across time - use shorter frequency to ensure enough temporal span
        # Calculate frequency to spread samples across total_days
        start_date = datetime.now() - timedelta(days=total_days)
        end_date = datetime.now()

        # Create date range spanning the full period
        dates = pd.date_range(start=start_date, end=end_date, periods=n_samples)

        X['entry_date'] = dates

        actual_span = (dates[-1] - dates[0]).days
        logger.info(f"  Generated dates from {dates[0]} to {dates[-1]}")
        logger.info(f"  Spanning {actual_span} days for {n_samples} samples")

        return X

    def validate_sklearn_model(self,
                               X: pd.DataFrame,
                               y: pd.Series,
                               model_factory: Callable[[], Any],
                               date_column: Optional[str] = None) -> ValidationReport:
        """
        Validate an sklearn-compatible model using walk-forward cross-validation.

        Args:
            X: Features DataFrame (may or may not include date column)
            y: Labels Series
            model_factory: Function that returns untrained model instance
            date_column: Name of date column (None to inject synthetic dates)

        Returns:
            ValidationReport with comprehensive metrics

        Example:
            >>> from sklearn.ensemble import RandomForestClassifier
            >>>
            >>> def model_factory():
            ...     return RandomForestClassifier(n_estimators=100, random_state=42)
            >>>
            >>> cv = UnifiedCrossValidator(n_folds=5)
            >>> report = cv.validate_sklearn_model(X, y, model_factory)
            >>> print(f"Mean ROC-AUC: {report.mean_roc_auc:.3f}")
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"UNIFIED CROSS-VALIDATION")
        logger.info(f"{'='*70}")
        logger.info(f"Dataset: {len(X)} samples, {len(X.columns)} features")
        logger.info(f"Label distribution: {y.value_counts().to_dict()}")

        # Check if date column exists, otherwise inject synthetic dates
        if date_column is None or date_column not in X.columns:
            X = self._inject_synthetic_dates(X)
            date_column = 'entry_date'

        # Verify sufficient samples
        if len(X) < self.min_train_samples:
            raise ValueError(
                f"Insufficient samples for {self.n_folds}-fold CV. "
                f"Have: {len(X)}, Need: >= {self.min_train_samples}"
            )

        # Create validator
        validator = WalkForwardValidator(
            n_folds=self.n_folds,
            val_period_days=self.val_period_days,
            gap_days=self.gap_days,
            min_train_samples=self.min_train_samples,
            min_val_samples=self.min_samples_per_fold
        )

        # Define evaluation function for multiclass classification
        def eval_fn(model, X_val, y_val):
            """Evaluate model on validation set."""
            # Remove date column if present
            feature_cols = [c for c in X_val.columns if c != date_column]
            X_eval = X_val[feature_cols] if isinstance(X_val, pd.DataFrame) else X_val

            y_pred = model.predict(X_eval)

            # Get probabilities for ROC-AUC and Brier score
            y_proba = model.predict_proba(X_eval)

            # Handle multiclass ROC-AUC (use OvR strategy)
            try:
                if len(np.unique(y_val)) > 2:
                    # Multiclass: use macro average
                    roc_auc = roc_auc_score(y_val, y_proba, multi_class='ovr', average='macro')
                else:
                    # Binary: use positive class probability
                    roc_auc = roc_auc_score(y_val, y_proba[:, 1])
            except Exception as e:
                logger.warning(f"Failed to calculate ROC-AUC: {e}")
                roc_auc = 0.5  # Random baseline

            # Brier score (average across all classes)
            try:
                # Convert to one-hot encoding
                from sklearn.preprocessing import label_binarize
                classes = np.unique(y_val)
                y_val_bin = label_binarize(y_val, classes=classes)

                # Calculate Brier score for each class
                brier_scores = []
                for i in range(len(classes)):
                    brier = brier_score_loss(y_val_bin[:, i], y_proba[:, i])
                    brier_scores.append(brier)
                brier_score = np.mean(brier_scores)
            except Exception as e:
                logger.warning(f"Failed to calculate Brier score: {e}")
                brier_score = 0.25  # Random baseline for binary

            return {
                'accuracy': accuracy_score(y_val, y_pred),
                'precision': precision_score(y_val, y_pred, average='weighted', zero_division=0),
                'recall': recall_score(y_val, y_pred, average='weighted', zero_division=0),
                'f1': f1_score(y_val, y_pred, average='weighted', zero_division=0),
                'roc_auc': roc_auc,
                'brier_score': brier_score
            }

        # Run validation
        report = validator.validate(X, y, model_factory, eval_fn, date_column)

        logger.info(f"\n{'='*70}")
        logger.info(f"VALIDATION COMPLETE")
        logger.info(f"{'='*70}")

        return report


def create_pipeline_factory(base_model_factory: Callable[[], Any],
                            use_scaler: bool = True) -> Callable[[], Any]:
    """
    Create a pipeline factory that wraps a model with preprocessing.

    Args:
        base_model_factory: Function returning untrained model
        use_scaler: Whether to include StandardScaler

    Returns:
        Function returning sklearn Pipeline

    Example:
        >>> from sklearn.ensemble import RandomForestClassifier
        >>>
        >>> def rf_factory():
        ...     return RandomForestClassifier(n_estimators=100)
        >>>
        >>> pipeline_factory = create_pipeline_factory(rf_factory, use_scaler=True)
        >>> model = pipeline_factory()  # Returns Pipeline with scaler + RF
    """
    def pipeline_factory():
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        if use_scaler:
            return Pipeline([
                ('scaler', StandardScaler()),
                ('classifier', base_model_factory())
            ])
        else:
            # No scaling (for tree-based models)
            return base_model_factory()

    return pipeline_factory


if __name__ == '__main__':
    # Example usage
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression

    logger.info("Creating synthetic dataset for testing...")

    # Synthetic data without dates
    np.random.seed(42)
    n_samples = 1000

    X = pd.DataFrame({
        'feature1': np.random.randn(n_samples),
        'feature2': np.random.randn(n_samples),
        'feature3': np.random.randn(n_samples)
    })

    # Multiclass labels: -1, 0, 1
    y = pd.Series(np.random.choice([-1, 0, 1], size=n_samples))

    logger.info(f"Dataset: {len(X)} samples, {len(X.columns)} features")
    logger.info(f"Label distribution: {y.value_counts().to_dict()}")

    # Test CV
    cv = UnifiedCrossValidator(n_folds=5, val_period_days=30)

    # Test with Random Forest
    def model_factory():
        return RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)

    report = cv.validate_sklearn_model(X, y, model_factory)

    logger.info(f"\nValidation Report:")
    logger.info(f"  Mean ROC-AUC: {report.mean_roc_auc:.4f} ± {report.std_roc_auc:.4f}")
    logger.info(f"  Mean Accuracy: {report.mean_accuracy:.4f} ± {report.std_accuracy:.4f}")
    logger.info(f"  Mean F1: {report.mean_f1:.4f} ± {report.std_f1:.4f}")
    logger.info(f"  AUC Degradation: {report.auc_degradation:+.4f}")

    logger.info("\nExample complete!")
