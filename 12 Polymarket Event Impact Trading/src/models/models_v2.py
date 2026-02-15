"""
Machine Learning Models for Price Movement Prediction (V2)
MIGRATED to use centralized training_engine.py

This is a drop-in replacement for models.py that uses the new
centralized training engine under the hood.

Migration: Phase 1 - Event Bot
Created: 2026-02-15
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
import pickle
import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.training_engine import ModelTrainer, ModelConfig, TrainingMetrics


class PriceMovementPredictor:
    """
    Price movement prediction model (V2).

    Drop-in replacement for legacy PriceMovementPredictor that uses
    the centralized training engine.

    Maintains backward compatibility with existing trader.py code.
    """

    def __init__(self, model_type: str = 'random_forest', telegram_notifier=None):
        """
        Initialize predictor.

        Args:
            model_type: Type of model ('random_forest', 'gradient_boost', 'logistic', 'svm')
            telegram_notifier: Optional TelegramNotifier for training alerts
        """
        self.model_type = model_type
        self.model = None
        self.trainer = None
        self.feature_names = []
        self.is_trained = False
        self.telegram = telegram_notifier

        # Map legacy names to new names
        model_type_map = {
            'random_forest': 'random_forest',
            'gradient_boost': 'gradient_boosting',
            'logistic': 'logistic',
            'svm': 'svm'
        }

        # Create trainer config
        mapped_model_type = model_type_map.get(model_type, model_type)

        # Legacy models.py used these hyperparameters
        if mapped_model_type == 'random_forest':
            self.config = ModelConfig(
                model_type='random_forest',
                n_estimators=100,
                rf_max_depth=10,
                rf_min_samples_split=5,
                rf_min_samples_leaf=2,
                apply_calibration=False,  # Legacy didn't use calibration
                use_scaler=True,  # Legacy used StandardScaler
                verbose=False
            )
        elif mapped_model_type == 'gradient_boosting':
            self.config = ModelConfig(
                model_type='gradient_boosting',
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                apply_calibration=False,  # Legacy didn't use calibration
                use_scaler=True,
                verbose=False
            )
        elif mapped_model_type == 'logistic':
            self.config = ModelConfig(
                model_type='logistic',
                apply_calibration=False,
                use_scaler=True,
                verbose=False
            )
        elif mapped_model_type == 'svm':
            self.config = ModelConfig(
                model_type='svm',
                apply_calibration=False,
                use_scaler=True,
                verbose=False
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

        self.trainer = ModelTrainer(self.config, telegram_notifier=self.telegram)

    def train(self, X: pd.DataFrame, y: np.ndarray,
              validation_split: float = 0.2,
              use_cv: bool = False,
              cv_n_folds: int = 5,
              date_column: str = None) -> Dict[str, float]:
        """
        Train the model with optional cross-validation.

        Args:
            X: Feature DataFrame
            y: Labels (1 for up, 0 for no change, -1 for down)
            validation_split: Fraction of data for validation (if use_cv=False)
            use_cv: Whether to use k-fold cross-validation (k >= 5)
            cv_n_folds: Number of CV folds (must be >= 5)
            date_column: Date column for temporal CV (None to inject synthetic dates)

        Returns:
            Dictionary of metrics (includes validation_report if use_cv=True)
        """
        if use_cv:
            return self.train_with_cv(X, y, date_column, cv_n_folds)

        # Simple train/val split (backward compatible with legacy)
        self.feature_names = list(X.columns)

        # Manual split for train/validation (no separate test set)
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42
        )

        # Train using centralized engine
        self.model, metrics_obj = self.trainer.train(
            X_train, y_train,
            X_val, y_val
        )

        self.is_trained = True

        # Convert metrics to legacy format for backward compatibility
        legacy_metrics = {
            'train_accuracy': metrics_obj['train'].accuracy,
            'val_accuracy': metrics_obj['val'].accuracy,
            'train_f1': metrics_obj['train'].f1,
            'val_f1': metrics_obj['val'].f1,
        }

        # Print classification report (for backward compatibility)
        print("\nValidation Metrics:")
        print(f"  Accuracy:  {metrics_obj['val'].accuracy:.4f}")
        print(f"  Precision: {metrics_obj['val'].precision:.4f}")
        print(f"  Recall:    {metrics_obj['val'].recall:.4f}")
        print(f"  F1 Score:  {metrics_obj['val'].f1:.4f}")

        return legacy_metrics

    def train_with_cv(self, X: pd.DataFrame, y: np.ndarray,
                      date_column: str = None,
                      n_folds: int = 5,
                      val_period_days: int = 30) -> Dict[str, float]:
        """
        Train with k-fold cross-validation (k >= 5).

        Args:
            X: Feature DataFrame
            y: Labels (1 for up, 0 for no change, -1 for down)
            date_column: Date column for temporal ordering (None to inject synthetic)
            n_folds: Number of folds (must be >= 5)
            val_period_days: Validation period length in days

        Returns:
            Dictionary with CV metrics and production readiness assessment
        """
        from cross_validation import UnifiedCrossValidator

        self.feature_names = list(X.columns)
        if date_column:
            self.feature_names = [f for f in self.feature_names if f != date_column]

        # Create CV validator
        cv_validator = UnifiedCrossValidator(
            n_folds=n_folds,
            val_period_days=val_period_days
        )

        # Run CV using training engine
        validation_report = self.trainer.train_with_cv(
            X, y,
            cv_validator=cv_validator,
            date_column=date_column
        )

        # Train final model on full dataset
        if date_column and date_column in X.columns:
            X_train = X.drop(columns=[date_column])
        else:
            X_train = X

        self.model, _ = self.trainer.train(X_train, y)
        self.is_trained = True

        # Convert to legacy metrics format
        legacy_metrics = {
            'cv_mean_accuracy': validation_report.mean_accuracy,
            'cv_std_accuracy': validation_report.std_accuracy,
            'cv_mean_f1': validation_report.mean_f1,
            'cv_std_f1': validation_report.std_f1,
            'cv_mean_roc_auc': validation_report.mean_roc_auc,
            'cv_std_roc_auc': validation_report.std_roc_auc,
            'production_ready': validation_report.production_ready,
            'validation_report': validation_report
        }

        return legacy_metrics

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict class labels.

        Args:
            X: Feature DataFrame

        Returns:
            Predicted labels
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Ensure features are in correct order
        X = X[self.feature_names]

        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict class probabilities.

        Args:
            X: Feature DataFrame

        Returns:
            Predicted probabilities (shape: [n_samples, n_classes])
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Ensure features are in correct order
        X = X[self.feature_names]

        return self.model.predict_proba(X)

    def save(self, filepath: str, metadata: Optional[Dict] = None):
        """
        Save model to file.

        Args:
            filepath: Path to save model
            metadata: Optional metadata
        """
        if not self.is_trained:
            raise ValueError("Cannot save untrained model")

        # Use trainer's save method
        # Create dummy metrics if not available
        dummy_metrics = {
            'train': TrainingMetrics(
                accuracy=0.0, precision=0.0, recall=0.0,
                f1=0.0, roc_auc=0.0, brier_score=0.0,
                confusion_matrix=[[0, 0], [0, 0]]
            )
        }

        self.trainer.save_model(self.model, dummy_metrics, filepath, metadata)

    def load(self, filepath: str):
        """
        Load model from file.

        Args:
            filepath: Path to model file
        """
        self.model, model_data = ModelTrainer.load_model(filepath)

        self.feature_names = model_data.get('feature_names', [])
        self.is_trained = True

        # Restore trainer's scaler if present
        if 'scaler' in model_data and model_data['scaler'] is not None:
            self.trainer.scaler = model_data['scaler']

    def get_feature_importance(self, top_n: int = 10) -> Dict[str, float]:
        """
        Get feature importance scores.

        Args:
            top_n: Number of top features to return

        Returns:
            Dictionary of {feature_name: importance}
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Get importances from model
        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
        elif hasattr(self.model, 'estimator') and hasattr(self.model.estimator, 'feature_importances_'):
            # For calibrated models
            importances = self.model.estimator.feature_importances_
        elif hasattr(self.model, 'coef_'):
            # For linear models
            importances = np.abs(self.model.coef_[0])
        else:
            raise ValueError("Model does not support feature importance")

        # Sort and return top N
        indices = np.argsort(importances)[::-1][:top_n]

        return {
            self.feature_names[i]: importances[i]
            for i in indices
        }


class ConfidenceFilter:
    """Filter predictions based on confidence threshold."""

    def __init__(self, min_confidence: float = 0.6):
        """
        Initialize filter.

        Args:
            min_confidence: Minimum confidence to act on prediction
        """
        self.min_confidence = min_confidence

    def filter_predictions(self, predictions: np.ndarray,
                          probabilities: np.ndarray) -> tuple:
        """
        Filter predictions by confidence.

        Args:
            predictions: Array of predictions
            probabilities: Array of probability matrices

        Returns:
            Tuple of (filtered_predictions, confidence_scores)
        """
        # Get max probability for each prediction
        max_probs = np.max(probabilities, axis=1)

        # Filter by confidence
        confident_mask = max_probs >= self.min_confidence

        filtered_predictions = predictions.copy()
        filtered_predictions[~confident_mask] = 0  # No action for low confidence

        return filtered_predictions, max_probs


class TradingSignalGenerator:
    """Generate trading signals from model predictions."""

    def __init__(self, model: PriceMovementPredictor,
                 min_confidence: float = 0.6,
                 min_expected_return: float = 0.02):
        """
        Initialize signal generator.

        Args:
            model: Trained prediction model
            min_confidence: Minimum confidence to generate signal
            min_expected_return: Minimum expected return to trade
        """
        self.model = model
        self.confidence_filter = ConfidenceFilter(min_confidence)
        self.min_expected_return = min_expected_return

    def generate_signal(self, features: pd.DataFrame,
                       current_price: float) -> Dict:
        """
        Generate trading signal.

        Args:
            features: Feature DataFrame (single row)
            current_price: Current market price

        Returns:
            Signal dictionary with action and details
        """
        # Get prediction and confidence
        prediction = self.model.predict(features)[0]
        probabilities = self.model.predict_proba(features)[0]
        confidence = np.max(probabilities)

        # Filter by confidence
        if confidence < self.confidence_filter.min_confidence:
            return {
                'action': 'HOLD',
                'reason': f'Low confidence: {confidence:.2f}',
                'confidence': confidence,
                'prediction': prediction
            }

        # Generate signal based on prediction
        # Map prediction to probability index: classes are [-1, 0, 1] -> indices [0, 1, 2]
        class_to_idx = {-1: 0, 0: 1, 1: 2}
        pred_idx = class_to_idx.get(prediction, 1)  # Default to neutral if unknown
        pred_prob = probabilities[pred_idx]

        if prediction == 1:  # Price expected to go up
            # Only buy if price is not already too high
            if current_price < 0.95:
                expected_return = pred_prob * (1 - current_price)
                if expected_return >= self.min_expected_return:
                    return {
                        'action': 'BUY',
                        'confidence': confidence,
                        'expected_return': expected_return,
                        'suggested_price': min(current_price * 1.01, 0.99),
                        'reason': f'Positive prediction with {confidence:.2%} confidence'
                    }

        elif prediction == -1:  # Price expected to go down
            # Only sell if price is not already too low
            if current_price > 0.05:
                expected_return = pred_prob * current_price
                if expected_return >= self.min_expected_return:
                    return {
                        'action': 'SELL',
                        'confidence': confidence,
                        'expected_return': expected_return,
                        'suggested_price': max(current_price * 0.99, 0.01),
                        'reason': f'Negative prediction with {confidence:.2%} confidence'
                    }

        return {
            'action': 'HOLD',
            'reason': 'No high-confidence opportunity',
            'confidence': confidence,
            'prediction': prediction
        }


class ModelPerformanceTracker:
    """Track model performance over time."""

    def __init__(self, filepath: str = 'model_performance.json'):
        self.filepath = filepath
        self.performance_history = []
        self.load()

    def record_prediction(self, prediction: int, actual: int,
                         confidence: float, market_id: str):
        """Record a prediction and its outcome."""
        import json
        from datetime import datetime

        record = {
            'timestamp': datetime.now().isoformat(),
            'prediction': int(prediction),
            'actual': int(actual),
            'confidence': float(confidence),
            'market_id': market_id,
            'correct': prediction == actual
        }

        self.performance_history.append(record)
        self.save()

    def get_accuracy(self, lookback_hours: Optional[int] = None) -> float:
        """Calculate accuracy over recent predictions."""
        from datetime import datetime, timedelta

        if not self.performance_history:
            return 0.0

        records = self.performance_history
        if lookback_hours:
            cutoff = datetime.now() - timedelta(hours=lookback_hours)
            records = [
                r for r in records
                if datetime.fromisoformat(r['timestamp']) > cutoff
            ]

        if not records:
            return 0.0

        correct = sum(1 for r in records if r['correct'])
        return correct / len(records)

    def get_statistics(self) -> Dict:
        """Get comprehensive performance statistics."""
        if not self.performance_history:
            return {}

        df = pd.DataFrame(self.performance_history)

        return {
            'total_predictions': len(df),
            'overall_accuracy': df['correct'].mean(),
            'accuracy_by_class': df.groupby('prediction')['correct'].mean().to_dict(),
            'avg_confidence': df['confidence'].mean(),
            'accuracy_last_24h': self.get_accuracy(24),
            'accuracy_last_7d': self.get_accuracy(168)
        }

    def save(self):
        """Save performance history to disk."""
        import json

        with open(self.filepath, 'w') as f:
            json.dump(self.performance_history, f, indent=2)

    def load(self):
        """Load performance history from disk."""
        import json

        try:
            with open(self.filepath, 'r') as f:
                self.performance_history = json.load(f)
        except FileNotFoundError:
            self.performance_history = []


# For backward compatibility, keep old function names
def create_model(model_type: str = 'random_forest') -> PriceMovementPredictor:
    """Create a price movement prediction model."""
    return PriceMovementPredictor(model_type)
