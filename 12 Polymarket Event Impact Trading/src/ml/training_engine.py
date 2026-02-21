#!/usr/bin/env python3
"""
Centralized ML Training Engine
Unified training, calibration, and evaluation for all trading bots.

Consolidates logic from:
- train_price_level_model.py (GBM + calibration)
- models.py (multi-model support)
- label_and_retrain.py (simple training)

Created: 2026-02-15 (Phase 1 of ML centralization)
"""

import numpy as np
import pandas as pd
import pickle
import logging
from typing import Dict, List, Tuple, Optional, Any, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
import sys

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, brier_score_loss, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV

# Optional Telegram support
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from monitoring.telegram_notifier import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for model training."""
    model_type: str = 'gradient_boosting'  # 'random_forest', 'gradient_boosting', 'logistic', 'svm'

    # GradientBoosting hyperparameters
    n_estimators: int = 200
    learning_rate: float = 0.05
    max_depth: int = 4
    min_samples_split: int = 10
    min_samples_leaf: int = 5
    subsample: float = 0.8

    # RandomForest hyperparameters (if used)
    rf_max_depth: int = 10
    rf_min_samples_split: int = 5
    rf_min_samples_leaf: int = 2

    # Calibration
    apply_calibration: bool = True
    calibration_method: str = 'isotonic'  # 'isotonic' or 'sigmoid'

    # Preprocessing
    use_scaler: bool = False  # StandardScaler (usually not needed for tree models)

    # Training
    random_state: int = 42
    verbose: bool = True


@dataclass
class TrainingMetrics:
    """Metrics from model training/evaluation."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    brier_score: float
    confusion_matrix: List[List[int]]

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)


class ModelTrainer:
    """
    Centralized training engine for all trading bots.

    Features:
    - Multi-model support (RF, GBM, LogReg, SVM)
    - Automatic calibration (isotonic/sigmoid)
    - Standardized evaluation metrics
    - Model persistence with metadata
    - Train/val/test splitting

    Usage:
        config = ModelConfig(model_type='gradient_boosting', n_estimators=200)
        trainer = ModelTrainer(config)

        # Train
        model, metrics = trainer.train(X_train, y_train, X_val, y_val)

        # Evaluate
        test_metrics = trainer.evaluate(model, X_test, y_test)

        # Save
        trainer.save_model(model, metrics, 'model.pkl')
    """

    def __init__(
        self,
        config: ModelConfig = None,
        telegram_notifier: Optional[Any] = None,
        feature_importance_tracker: Optional[Any] = None
    ):
        """
        Initialize trainer.

        Args:
            config: Model configuration (uses defaults if None)
            telegram_notifier: Optional TelegramNotifier for training alerts
            feature_importance_tracker: Optional FeatureImportanceTracker for drift detection
        """
        self.config = config or ModelConfig()
        self.scaler = StandardScaler() if self.config.use_scaler else None
        self.feature_names = []
        self.telegram = telegram_notifier
        self.feature_importance_tracker = feature_importance_tracker

        if self.config.verbose:
            logger.info(f"ModelTrainer initialized: {self.config.model_type}")
            if self.telegram:
                logger.info("Telegram notifications enabled for training")
            if self.feature_importance_tracker:
                logger.info("Feature importance tracking enabled for drift detection")

    def _send_telegram(self, message: str):
        """Send Telegram notification if configured."""
        if self.telegram:
            try:
                self.telegram.send_message(message)
            except Exception as e:
                logger.warning(f"Failed to send Telegram notification: {e}")

    def _notify_training_started(self, n_samples: int, model_type: str):
        """Notify that training has started."""
        if not self.telegram:
            return

        message = (
            f"<b>🤖 ML TRAINING STARTED</b>\n\n"
            f"<b>Model:</b> {model_type}\n"
            f"<b>Samples:</b> {n_samples:,}\n"
            f"<b>Started:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        self._send_telegram(message)

    def _notify_training_completed(self, metrics: Dict[str, TrainingMetrics],
                                   duration_seconds: float):
        """Notify that training has completed with metrics."""
        if not self.telegram:
            return

        # Get validation or test metrics (prefer val if available)
        eval_metrics = metrics.get('val', metrics.get('test', metrics.get('train')))

        # Determine performance emoji
        if eval_metrics.roc_auc > 0.8 or eval_metrics.accuracy > 0.8:
            emoji = "🟢"  # Excellent
        elif eval_metrics.roc_auc > 0.7 or eval_metrics.accuracy > 0.7:
            emoji = "🟡"  # Good
        else:
            emoji = "🔴"  # Needs improvement

        message = (
            f"<b>{emoji} ML TRAINING COMPLETE</b>\n\n"
            f"<b>Duration:</b> {duration_seconds:.1f}s\n"
            f"<b>Accuracy:</b> {eval_metrics.accuracy:.1%}\n"
            f"<b>Precision:</b> {eval_metrics.precision:.1%}\n"
            f"<b>Recall:</b> {eval_metrics.recall:.1%}\n"
            f"<b>F1 Score:</b> {eval_metrics.f1:.1%}\n"
        )

        if eval_metrics.roc_auc > 0:
            message += f"<b>ROC-AUC:</b> {eval_metrics.roc_auc:.3f}\n"

        message += f"\n<b>Status:</b> Ready for use ✅"

        self._send_telegram(message)

    def _notify_training_failed(self, error: Exception):
        """Notify that training has failed."""
        if not self.telegram:
            return

        message = (
            f"<b>❌ ML TRAINING FAILED</b>\n\n"
            f"<b>Error:</b> {type(error).__name__}\n"
            f"<b>Message:</b> {str(error)[:200]}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        self._send_telegram(message)

    def _notify_poor_performance(self, metrics: TrainingMetrics, dataset: str):
        """Notify if model performance is poor."""
        if not self.telegram:
            return

        # Only alert if performance is concerning
        if metrics.accuracy < 0.6 or metrics.f1 < 0.6:
            message = (
                f"<b>⚠️ MODEL PERFORMANCE WARNING</b>\n\n"
                f"<b>Dataset:</b> {dataset}\n"
                f"<b>Accuracy:</b> {metrics.accuracy:.1%} (low!)\n"
                f"<b>F1 Score:</b> {metrics.f1:.1%}\n\n"
                f"<i>Model may need more training data or feature engineering.</i>"
            )
            self._send_telegram(message)

    def _create_base_model(self) -> Any:
        """Create base model based on config."""
        if self.config.model_type == 'random_forest':
            return RandomForestClassifier(
                n_estimators=self.config.n_estimators,
                max_depth=self.config.rf_max_depth,
                min_samples_split=self.config.rf_min_samples_split,
                min_samples_leaf=self.config.rf_min_samples_leaf,
                random_state=self.config.random_state,
                verbose=1 if self.config.verbose else 0
            )

        elif self.config.model_type == 'gradient_boosting':
            return GradientBoostingClassifier(
                n_estimators=self.config.n_estimators,
                learning_rate=self.config.learning_rate,
                max_depth=self.config.max_depth,
                min_samples_split=self.config.min_samples_split,
                min_samples_leaf=self.config.min_samples_leaf,
                subsample=self.config.subsample,
                random_state=self.config.random_state,
                verbose=1 if self.config.verbose else 0
            )

        elif self.config.model_type == 'logistic':
            return LogisticRegression(
                max_iter=1000,
                random_state=self.config.random_state,
                verbose=1 if self.config.verbose else 0
            )

        elif self.config.model_type == 'svm':
            return SVC(
                kernel='rbf',
                C=1.0,
                probability=True,
                random_state=self.config.random_state,
                verbose=self.config.verbose
            )

        else:
            raise ValueError(f"Unknown model type: {self.config.model_type}")

    def train(self, X_train: pd.DataFrame, y_train: np.ndarray,
              X_val: Optional[pd.DataFrame] = None,
              y_val: Optional[np.ndarray] = None,
              **kwargs) -> Tuple[Any, Dict[str, TrainingMetrics]]:
        """
        Train model with optional validation set.

        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            **kwargs: Additional parameters (bot_type, model_path, etc. for feature tracking)

        Returns:
            Tuple of (trained_model, metrics_dict)
            metrics_dict contains 'train' and optionally 'val' metrics
        """
        start_time = datetime.now()

        # Notify training started
        self._notify_training_started(len(X_train), self.config.model_type)

        if self.config.verbose:
            logger.info("=" * 70)
            logger.info("TRAINING MODEL")
            logger.info("=" * 70)
            logger.info(f"Model type: {self.config.model_type}")
            logger.info(f"Training samples: {len(X_train)}")
            if X_val is not None:
                logger.info(f"Validation samples: {len(X_val)}")

        try:
            # Store feature names
            self.feature_names = list(X_train.columns)

            # Apply scaling if configured
            if self.scaler:
                X_train = pd.DataFrame(
                    self.scaler.fit_transform(X_train),
                    columns=X_train.columns,
                    index=X_train.index
                )
                if X_val is not None:
                    X_val = pd.DataFrame(
                        self.scaler.transform(X_val),
                        columns=X_val.columns,
                        index=X_val.index
                    )

            # Create and train base model
            if self.config.verbose:
                logger.info(f"\nTraining {self.config.model_type}...")

            base_model = self._create_base_model()
            base_model.fit(X_train, y_train)

            # Apply calibration if configured
            if self.config.apply_calibration:
                if self.config.verbose:
                    logger.info(f"\nApplying {self.config.calibration_method} calibration...")

                model = CalibratedClassifierCV(
                    estimator=base_model,
                    method=self.config.calibration_method,
                    cv='prefit'  # Use prefit since we already trained
                )

                # For calibration, use validation set if available, else use train set
                X_cal = X_val if X_val is not None else X_train
                y_cal = y_val if y_val is not None else y_train

                model.fit(X_cal, y_cal)
            else:
                model = base_model

            if self.config.verbose:
                logger.info("\nTraining complete!")

            # Evaluate on train set
            metrics = {}
            metrics['train'] = self.evaluate(model, X_train, y_train, dataset_name='train')

            # Evaluate on validation set if provided
            if X_val is not None and y_val is not None:
                metrics['val'] = self.evaluate(model, X_val, y_val, dataset_name='val')

                # Check for poor performance
                self._notify_poor_performance(metrics['val'], 'validation')

            # Notify training completed
            duration = (datetime.now() - start_time).total_seconds()
            self._notify_training_completed(metrics, duration)

            # Track feature importance for drift detection
            if self.feature_importance_tracker and hasattr(base_model, 'feature_importances_'):
                try:
                    # Extract bot_type from kwargs (passed by training scripts)
                    bot_type = kwargs.get('bot_type', 'unified')

                    # Prepare metrics dict for tracker
                    importance_metrics = {
                        'train_roc_auc': metrics['train'].roc_auc,
                        'val_roc_auc': metrics.get('val', metrics['train']).roc_auc,
                        'test_roc_auc': metrics.get('test', metrics.get('val', metrics['train'])).roc_auc
                    }

                    # Prepare training context
                    training_context = {
                        'training_samples': len(X_train),
                        'validation_samples': len(X_val) if X_val is not None else 0,
                        'model_config': asdict(self.config)
                    }

                    # Store feature importance (use base_model before calibration)
                    self.feature_importance_tracker.store_importance(
                        bot_type=bot_type,
                        model=base_model,
                        feature_names=self.feature_names,
                        metrics=importance_metrics,
                        training_context=training_context,
                        model_path=kwargs.get('model_path')
                    )

                    if self.config.verbose:
                        logger.info(f"Feature importance tracked for {bot_type}")
                except Exception as e:
                    logger.warning(f"Failed to track feature importance: {e}")

            return model, metrics

        except Exception as e:
            # Notify training failed
            self._notify_training_failed(e)
            raise

    def evaluate(self, model: Any, X: pd.DataFrame, y: np.ndarray,
                 dataset_name: str = 'test') -> TrainingMetrics:
        """
        Evaluate model on dataset.

        Args:
            model: Trained model
            X: Features
            y: True labels
            dataset_name: Name for logging

        Returns:
            TrainingMetrics object
        """
        # Apply scaling if configured
        if self.scaler:
            X = pd.DataFrame(
                self.scaler.transform(X),
                columns=X.columns,
                index=X.index
            )

        # Predictions
        y_pred = model.predict(X)
        y_prob = model.predict_proba(X)

        # Detect if binary or multiclass
        n_classes = len(np.unique(y))
        is_binary = n_classes == 2

        # Calculate metrics
        if is_binary:
            # Binary classification metrics
            metrics = TrainingMetrics(
                accuracy=accuracy_score(y, y_pred),
                precision=precision_score(y, y_pred, zero_division=0),
                recall=recall_score(y, y_pred, zero_division=0),
                f1=f1_score(y, y_pred, zero_division=0),
                roc_auc=roc_auc_score(y, y_prob[:, 1]),
                brier_score=brier_score_loss(y, y_prob[:, 1]),
                confusion_matrix=confusion_matrix(y, y_pred).tolist()
            )
        else:
            # Multiclass metrics (use weighted average)
            metrics = TrainingMetrics(
                accuracy=accuracy_score(y, y_pred),
                precision=precision_score(y, y_pred, average='weighted', zero_division=0),
                recall=recall_score(y, y_pred, average='weighted', zero_division=0),
                f1=f1_score(y, y_pred, average='weighted', zero_division=0),
                roc_auc=0.0,  # ROC-AUC not meaningful for multiclass in simple form
                brier_score=0.0,  # Brier score not meaningful for multiclass
                confusion_matrix=confusion_matrix(y, y_pred).tolist()
            )

        # Log results
        if self.config.verbose:
            logger.info(f"\n{dataset_name.upper()} METRICS:")
            logger.info(f"  Accuracy:  {metrics.accuracy:.4f}")
            logger.info(f"  Precision: {metrics.precision:.4f}")
            logger.info(f"  Recall:    {metrics.recall:.4f}")
            logger.info(f"  F1 Score:  {metrics.f1:.4f}")
            logger.info(f"  ROC-AUC:   {metrics.roc_auc:.4f}")
            logger.info(f"  Brier:     {metrics.brier_score:.4f}")

            cm = metrics.confusion_matrix
            if len(cm) == 2:
                logger.info(f"\nConfusion Matrix:")
                logger.info(f"  TN: {cm[0][0]}, FP: {cm[0][1]}")
                logger.info(f"  FN: {cm[1][0]}, TP: {cm[1][1]}")

        return metrics

    def split_data(self, X: pd.DataFrame, y: np.ndarray,
                   test_size: float = 0.15,
                   val_size: float = 0.15,
                   stratify: bool = True) -> Dict[str, Any]:
        """
        Split data into train/val/test sets.

        Args:
            X: Features
            y: Labels
            test_size: Proportion for test set
            val_size: Proportion for validation set (from remaining data)
            stratify: Whether to stratify splits by labels

        Returns:
            Dictionary with X_train, y_train, X_val, y_val, X_test, y_test
        """
        stratify_arg = y if stratify else None

        # First split: train+val vs test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=self.config.random_state,
            stratify=stratify_arg
        )

        # Second split: train vs val
        val_size_adjusted = val_size / (1 - test_size)
        stratify_temp = y_temp if stratify else None

        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=val_size_adjusted,
            random_state=self.config.random_state,
            stratify=stratify_temp
        )

        if self.config.verbose:
            logger.info(f"\nData split:")
            logger.info(f"  Train: {len(X_train)} ({len(X_train)/len(X)*100:.1f}%)")
            logger.info(f"  Val:   {len(X_val)} ({len(X_val)/len(X)*100:.1f}%)")
            logger.info(f"  Test:  {len(X_test)} ({len(X_test)/len(X)*100:.1f}%)")

        return {
            'X_train': X_train, 'y_train': y_train,
            'X_val': X_val, 'y_val': y_val,
            'X_test': X_test, 'y_test': y_test
        }

    def save_model(self, model: Any, metrics: Dict[str, TrainingMetrics],
                   filepath: str, metadata: Optional[Dict] = None):
        """
        Save model with metadata.

        Args:
            model: Trained model
            metrics: Training/validation metrics
            filepath: Path to save model
            metadata: Additional metadata to store
        """
        # Build model data
        model_data = {
            'model': model,
            'feature_names': self.feature_names,
            'config': asdict(self.config),
            'metrics': {k: v.to_dict() for k, v in metrics.items()},
            'scaler': self.scaler,
            'trained_at': datetime.now().isoformat(),
        }

        # Add custom metadata
        if metadata:
            model_data['metadata'] = metadata

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # Save
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

        if self.config.verbose:
            logger.info(f"\n✓ Model saved to: {filepath}")

    @staticmethod
    def load_model(filepath: str) -> Tuple[Any, Dict]:
        """
        Load model and metadata.

        Args:
            filepath: Path to model file

        Returns:
            Tuple of (model, model_data_dict)
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        model = model_data['model']

        logger.info(f"✓ Model loaded from: {filepath}")
        logger.info(f"  Features: {len(model_data.get('feature_names', []))}")
        logger.info(f"  Trained: {model_data.get('trained_at', 'unknown')}")

        return model, model_data

    def train_with_cv(self, X: pd.DataFrame, y: np.ndarray,
                      cv_validator: Any = None,
                      date_column: Optional[str] = None) -> Any:
        """
        Train model with cross-validation.

        Args:
            X: Features (may include date column)
            y: Labels
            cv_validator: Cross-validation validator (e.g., UnifiedCrossValidator)
            date_column: Name of date column for temporal CV

        Returns:
            Validation report from CV
        """
        if cv_validator is None:
            raise ValueError("cv_validator required for train_with_cv()")

        # Define model factory for CV
        def model_factory():
            base_model = self._create_base_model()
            if self.config.apply_calibration:
                return CalibratedClassifierCV(
                    estimator=base_model,
                    method=self.config.calibration_method,
                    cv=3  # Internal CV for calibration
                )
            return base_model

        # Define evaluation function
        def eval_fn(model, X_eval, y_eval):
            # Remove date column if present
            if date_column and date_column in X_eval.columns:
                X_eval = X_eval.drop(columns=[date_column])

            # Apply scaling if configured
            if self.scaler:
                X_eval = pd.DataFrame(
                    self.scaler.transform(X_eval),
                    columns=X_eval.columns,
                    index=X_eval.index
                )

            y_pred = model.predict(X_eval)
            y_proba = model.predict_proba(X_eval)[:, 1]

            return {
                'accuracy': accuracy_score(y_eval, y_pred),
                'precision': precision_score(y_eval, y_pred, zero_division=0),
                'recall': recall_score(y_eval, y_pred, zero_division=0),
                'f1': f1_score(y_eval, y_pred, zero_division=0),
                'roc_auc': roc_auc_score(y_eval, y_proba),
                'brier_score': brier_score_loss(y_eval, y_proba)
            }

        # Run CV
        report = cv_validator.validate(X, y, model_factory, eval_fn, date_column=date_column)

        return report


def create_trainer_from_legacy_config(legacy_model_type: str = 'random_forest',
                                      apply_calibration: bool = False,
                                      **kwargs) -> ModelTrainer:
    """
    Create ModelTrainer from legacy model configuration.

    Helper function for migrating from old models.py interface.

    Args:
        legacy_model_type: 'random_forest', 'gradient_boost', 'logistic', 'svm'
        apply_calibration: Whether to apply calibration
        **kwargs: Additional ModelConfig parameters

    Returns:
        ModelTrainer instance
    """
    # Map legacy names to new names
    model_type_map = {
        'random_forest': 'random_forest',
        'gradient_boost': 'gradient_boosting',
        'logistic': 'logistic',
        'svm': 'svm'
    }

    model_type = model_type_map.get(legacy_model_type, legacy_model_type)

    config = ModelConfig(
        model_type=model_type,
        apply_calibration=apply_calibration,
        **kwargs
    )

    return ModelTrainer(config)
