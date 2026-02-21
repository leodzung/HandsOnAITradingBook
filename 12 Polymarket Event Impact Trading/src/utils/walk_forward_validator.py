#!/usr/bin/env python3
"""
Walk-Forward Validation for Time-Series Trading Models

Implements expanding window cross-validation to prevent lookahead bias
and provide realistic performance estimates for financial ML models.
"""

import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict, Callable, Any
from datetime import datetime, timedelta
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FoldMetrics:
    """Metrics for a single validation fold."""
    fold_id: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    train_samples: int
    val_samples: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    brier_score: float
    train_class_distribution: Dict[int, int]
    val_class_distribution: Dict[int, int]


@dataclass
class ValidationReport:
    """Aggregate results across all folds."""
    fold_metrics: List[Dict]  # List of FoldMetrics as dicts
    mean_roc_auc: float
    std_roc_auc: float
    mean_accuracy: float
    std_accuracy: float
    mean_f1: float
    std_f1: float
    auc_degradation: float  # First fold vs last fold
    created_at: str
    n_folds: int
    val_period_days: int


class WalkForwardValidator:
    """
    Expanding window time-series cross-validation.

    Prevents lookahead bias by:
    - Training only on data before validation period
    - Expanding training set over time (realistic for production)
    - Maintaining strict temporal ordering
    """

    def __init__(self, n_folds: int = 5,
                 val_period_days: int = 30,
                 gap_days: int = 0,
                 min_train_samples: int = 500,
                 min_val_samples: int = 50,
                 feature_importance_tracker: Any = None):
        """
        Initialize walk-forward validator.

        Args:
            n_folds: Number of validation folds
            val_period_days: Length of each validation period in days
            gap_days: Optional embargo period between train/val (default: 0)
            min_train_samples: Minimum samples required for training
            min_val_samples: Minimum samples required for validation
            feature_importance_tracker: Optional FeatureImportanceTracker for drift detection
        """
        self.n_folds = n_folds
        self.val_period_days = val_period_days
        self.gap_days = gap_days
        self.min_train_samples = min_train_samples
        self.min_val_samples = min_val_samples
        self.feature_importance_tracker = feature_importance_tracker

    def split(self, X: pd.DataFrame, y: pd.Series,
              date_column: str = 'entry_date') -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate train/val indices maintaining temporal order.

        Expanding window approach:
        Fold 1: Train [-----] Gap [] Val [--]
        Fold 2: Train [---------] Gap [] Val [--]
        Fold 3: Train [-------------] Gap [] Val [--]

        Args:
            X: Features DataFrame (must include date_column)
            y: Labels Series
            date_column: Name of date column for temporal ordering

        Returns:
            List of (train_indices, val_indices) tuples
        """
        if date_column not in X.columns:
            raise ValueError(f"Date column '{date_column}' not found in features")

        # Convert date column to datetime
        dates = pd.to_datetime(X[date_column])

        # Sort by date
        sorted_indices = dates.argsort()
        sorted_dates = dates.iloc[sorted_indices]

        # Determine date range
        min_date = sorted_dates.min()
        max_date = sorted_dates.max()
        total_days = (max_date - min_date).days

        logger.info(f"\n{'='*70}")
        logger.info(f"WALK-FORWARD VALIDATION SPLITS")
        logger.info(f"{'='*70}")
        logger.info(f"Date range: {min_date.date()} to {max_date.date()} ({total_days} days)")
        logger.info(f"Total samples: {len(X)}")
        logger.info(f"Folds: {self.n_folds}")
        logger.info(f"Validation period: {self.val_period_days} days")
        logger.info(f"Gap period: {self.gap_days} days")

        # Work backwards from most recent data
        # Calculate validation boundaries
        val_boundaries = []
        current_val_end = max_date

        for fold_id in range(self.n_folds):
            val_start = current_val_end - timedelta(days=self.val_period_days)

            # Check if we have enough historical data for training
            if (val_start - min_date).days < 30:  # Need at least 30 days of training
                logger.warning(f"Insufficient data for {self.n_folds} folds, reducing to {fold_id}")
                break

            val_boundaries.append({
                'val_start': val_start,
                'val_end': current_val_end,
                'fold_id': self.n_folds - fold_id  # Number from 1 to n_folds
            })

            # Move to next fold (with gap)
            current_val_end = val_start - timedelta(days=self.gap_days)

        # Reverse to get chronological order
        val_boundaries = list(reversed(val_boundaries))

        # Generate splits
        splits = []
        for boundary in val_boundaries:
            val_start = boundary['val_start']
            val_end = boundary['val_end']
            fold_id = boundary['fold_id']

            # Training: everything before validation start (minus gap)
            train_end = val_start - timedelta(days=self.gap_days)
            train_mask = sorted_dates <= train_end

            # Validation: samples in validation window
            val_mask = (sorted_dates > val_start) & (sorted_dates <= val_end)

            # Get indices
            train_indices = sorted_indices[train_mask].values
            val_indices = sorted_indices[val_mask].values

            # Validate sample sizes
            if len(train_indices) < self.min_train_samples:
                logger.warning(f"Fold {fold_id}: Training samples ({len(train_indices)}) "
                             f"below minimum ({self.min_train_samples}), skipping")
                continue

            if len(val_indices) < self.min_val_samples:
                logger.warning(f"Fold {fold_id}: Validation samples ({len(val_indices)}) "
                             f"below minimum ({self.min_val_samples}), skipping")
                continue

            # Log split info
            train_start = sorted_dates.iloc[train_indices[0]]
            train_end_actual = sorted_dates.iloc[train_indices[-1]]
            val_start_actual = sorted_dates.iloc[val_indices[0]]
            val_end_actual = sorted_dates.iloc[val_indices[-1]]

            logger.info(f"\nFold {fold_id}:")
            logger.info(f"  Train: {train_start.date()} to {train_end_actual.date()} "
                       f"({len(train_indices)} samples)")
            logger.info(f"  Val:   {val_start_actual.date()} to {val_end_actual.date()} "
                       f"({len(val_indices)} samples)")

            # Verify no overlap
            if train_end_actual >= val_start_actual:
                logger.error(f"Fold {fold_id}: Temporal overlap detected! "
                           f"Train end ({train_end_actual.date()}) >= "
                           f"Val start ({val_start_actual.date()})")
                continue

            splits.append((train_indices, val_indices))

        if not splits:
            raise ValueError("No valid splits generated. Check data size and parameters.")

        logger.info(f"\n{'-'*70}")
        logger.info(f"Generated {len(splits)} valid folds")
        logger.info(f"{'-'*70}\n")

        return splits

    def validate(self, X: pd.DataFrame, y: pd.Series,
                model_factory: Callable[[], Any],
                eval_fn: Callable[[Any, pd.DataFrame, pd.Series], Dict[str, float]],
                date_column: str = 'entry_date',
                bot_type: str = 'walk_forward') -> ValidationReport:
        """
        Run full validation across all folds.

        Args:
            X: Features DataFrame (must include date_column)
            y: Labels Series
            model_factory: Function that returns untrained model
            eval_fn: Function(model, X, y) -> Dict[str, float] returning metrics
            date_column: Name of date column for temporal ordering
            bot_type: Bot type for feature importance tracking (default: 'walk_forward')

        Returns:
            ValidationReport with aggregate metrics
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"STARTING WALK-FORWARD VALIDATION")
        logger.info(f"{'='*70}\n")

        # Generate splits
        splits = self.split(X, y, date_column)

        # Remove date column from features for training
        feature_cols = [col for col in X.columns if col != date_column]
        X_features = X[feature_cols]
        dates = X[date_column]

        # Train and evaluate each fold
        fold_metrics = []

        for fold_id, (train_idx, val_idx) in enumerate(splits, 1):
            logger.info(f"\n{'='*70}")
            logger.info(f"FOLD {fold_id}/{len(splits)}")
            logger.info(f"{'='*70}")

            # Extract train/val sets
            X_train = X_features.iloc[train_idx]
            y_train = y.iloc[train_idx]
            X_val = X_features.iloc[val_idx]
            y_val = y.iloc[val_idx]

            # Get date ranges
            train_dates = pd.to_datetime(dates.iloc[train_idx])
            val_dates = pd.to_datetime(dates.iloc[val_idx])

            train_start = train_dates.min().strftime('%Y-%m-%d')
            train_end = train_dates.max().strftime('%Y-%m-%d')
            val_start = val_dates.min().strftime('%Y-%m-%d')
            val_end = val_dates.max().strftime('%Y-%m-%d')

            # Class distributions
            train_dist = y_train.value_counts().to_dict()
            val_dist = y_val.value_counts().to_dict()

            logger.info(f"\nTrain: {train_start} to {train_end} ({len(X_train)} samples)")
            logger.info(f"  Class distribution: {train_dist}")
            logger.info(f"Val:   {val_start} to {val_end} ({len(X_val)} samples)")
            logger.info(f"  Class distribution: {val_dist}")

            # Train fresh model
            logger.info(f"\nTraining model...")
            model = model_factory()
            model.fit(X_train, y_train)

            # Evaluate
            logger.info(f"Evaluating on validation set...")
            metrics = eval_fn(model, X_val, y_val)

            # Track feature importance for drift detection (after fit, after eval)
            if self.feature_importance_tracker and hasattr(model, 'feature_importances_'):
                try:
                    feature_names = [col for col in X_train.columns if col != date_column]

                    fold_context = {
                        'train_start': train_start,
                        'train_end': train_end,
                        'val_start': val_start,
                        'val_end': val_end,
                        'train_samples': len(X_train),
                        'val_samples': len(X_val)
                    }

                    # Store fold-level importance
                    self.feature_importance_tracker.store_fold_importance(
                        model=model,
                        feature_names=feature_names,
                        fold_id=fold_id,
                        fold_context=fold_context,
                        metrics=metrics,
                        bot_type=bot_type
                    )

                    logger.debug(f"Feature importance tracked for fold {fold_id}")
                except Exception as e:
                    logger.warning(f"Failed to track feature importance for fold {fold_id}: {e}")

            # Log metrics
            logger.info(f"\nValidation Metrics:")
            for metric_name, value in metrics.items():
                logger.info(f"  {metric_name:12s}: {value:.4f}")

            # Store fold metrics
            fold_metric = FoldMetrics(
                fold_id=fold_id,
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
                train_samples=len(X_train),
                val_samples=len(X_val),
                accuracy=metrics['accuracy'],
                precision=metrics['precision'],
                recall=metrics['recall'],
                f1=metrics['f1'],
                roc_auc=metrics['roc_auc'],
                brier_score=metrics['brier_score'],
                train_class_distribution={int(k): int(v) for k, v in train_dist.items()},
                val_class_distribution={int(k): int(v) for k, v in val_dist.items()}
            )
            fold_metrics.append(fold_metric)

        # Calculate aggregate metrics
        aucs = [fm.roc_auc for fm in fold_metrics]
        accs = [fm.accuracy for fm in fold_metrics]
        f1s = [fm.f1 for fm in fold_metrics]

        mean_auc = np.mean(aucs)
        std_auc = np.std(aucs)
        mean_acc = np.mean(accs)
        std_acc = np.std(accs)
        mean_f1 = np.mean(f1s)
        std_f1 = np.std(f1s)

        # Calculate degradation (first fold vs last fold)
        auc_degradation = aucs[-1] - aucs[0] if len(aucs) >= 2 else 0.0

        # Create report
        report = ValidationReport(
            fold_metrics=[asdict(fm) for fm in fold_metrics],
            mean_roc_auc=float(mean_auc),
            std_roc_auc=float(std_auc),
            mean_accuracy=float(mean_acc),
            std_accuracy=float(std_acc),
            mean_f1=float(mean_f1),
            std_f1=float(std_f1),
            auc_degradation=float(auc_degradation),
            created_at=datetime.now().isoformat(),
            n_folds=len(fold_metrics),
            val_period_days=self.val_period_days
        )

        # Log summary
        logger.info(f"\n{'='*70}")
        logger.info(f"VALIDATION SUMMARY")
        logger.info(f"{'='*70}")
        logger.info(f"\nAggregate Metrics (across {len(fold_metrics)} folds):")
        logger.info(f"  Mean ROC-AUC:  {mean_auc:.4f} ± {std_auc:.4f}")
        logger.info(f"  Mean Accuracy: {mean_acc:.4f} ± {std_acc:.4f}")
        logger.info(f"  Mean F1:       {mean_f1:.4f} ± {std_f1:.4f}")
        logger.info(f"  AUC Degradation: {auc_degradation:+.4f} "
                   f"(Fold 1: {aucs[0]:.4f} -> Fold {len(aucs)}: {aucs[-1]:.4f})")

        # Performance assessment
        logger.info(f"\nPerformance Assessment:")
        if mean_auc >= 0.70:
            logger.info("  Status: PRODUCTION READY (AUC >= 0.70)")
        elif mean_auc >= 0.60:
            logger.info("  Status: MARGINAL - Needs improvement (AUC 0.60-0.70)")
        else:
            logger.info("  Status: NOT READY - Requires significant work (AUC < 0.60)")

        if std_auc > 0.10:
            logger.warning("  Warning: High instability (std > 0.10)")

        if abs(auc_degradation) > 0.10:
            logger.warning("  Warning: Severe concept drift detected (degradation > 0.10)")

        logger.info(f"\n{'='*70}\n")

        return report


def save_validation_report(report: ValidationReport, output_path: str):
    """Save validation report to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(asdict(report), f, indent=2)
    logger.info(f"Saved validation report to {output_path}")


def load_validation_report(input_path: str) -> ValidationReport:
    """Load validation report from JSON file."""
    with open(input_path, 'r') as f:
        data = json.load(f)

    # Convert fold_metrics back to FoldMetrics objects
    fold_metrics = [FoldMetrics(**fm) for fm in data['fold_metrics']]
    data['fold_metrics'] = [asdict(fm) for fm in fold_metrics]

    return ValidationReport(**data)


if __name__ == '__main__':
    # Example usage with synthetic data
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, \
        roc_auc_score, brier_score_loss

    logger.info("Creating synthetic dataset...")

    # Create synthetic time-series data
    np.random.seed(42)
    n_samples = 5000
    dates = pd.date_range('2024-01-01', periods=n_samples, freq='H')

    # Features with temporal trend
    X = pd.DataFrame({
        'entry_date': dates,
        'feature1': np.random.randn(n_samples) + np.linspace(0, 2, n_samples),
        'feature2': np.random.randn(n_samples),
        'feature3': np.random.randn(n_samples) * np.linspace(1, 2, n_samples)
    })

    # Labels with temporal pattern (concept drift)
    y = ((X['feature1'] > 0.5) & (X['feature2'] > 0)).astype(int)
    # Add noise
    noise_idx = np.random.choice(n_samples, size=int(n_samples * 0.1), replace=False)
    y.iloc[noise_idx] = 1 - y.iloc[noise_idx]

    logger.info(f"Dataset: {len(X)} samples, {len(X.columns)-1} features")
    logger.info(f"Label distribution: {y.value_counts().to_dict()}")

    # Create validator
    validator = WalkForwardValidator(
        n_folds=5,
        val_period_days=30,
        gap_days=0
    )

    # Define model factory
    def model_factory():
        return GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            random_state=42
        )

    # Define evaluation function
    def eval_fn(model, X, y):
        feature_cols = [c for c in X.columns if c != 'entry_date']
        X_eval = X[feature_cols] if isinstance(X, pd.DataFrame) else X

        y_pred = model.predict(X_eval)
        y_proba = model.predict_proba(X_eval)[:, 1]

        return {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, zero_division=0),
            'recall': recall_score(y, y_pred, zero_division=0),
            'f1': f1_score(y, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y, y_proba),
            'brier_score': brier_score_loss(y, y_proba)
        }

    # Run validation
    report = validator.validate(X, y, model_factory, eval_fn, date_column='entry_date')

    # Save report
    save_validation_report(report, 'data/example_validation_report.json')

    logger.info("\nExample validation complete!")
