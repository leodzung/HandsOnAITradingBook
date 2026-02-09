"""
Machine Learning Models for Price Movement Prediction
Implements various ML models for predicting market price changes after events.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import pickle
import json
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler


class PriceMovementPredictor:
    """Base class for price movement prediction models."""

    def __init__(self, model_type: str = 'random_forest'):
        """
        Initialize predictor.

        Args:
            model_type: Type of model ('random_forest', 'gradient_boost', 'logistic', 'svm')
        """
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_trained = False

    def _create_model(self):
        """Create model based on type."""
        if self.model_type == 'random_forest':
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42
            )
        elif self.model_type == 'gradient_boost':
            return GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
        elif self.model_type == 'logistic':
            return LogisticRegression(
                max_iter=1000,
                random_state=42
            )
        elif self.model_type == 'svm':
            return SVC(
                kernel='rbf',
                C=1.0,
                probability=True,
                random_state=42
            )
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

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

        # Keep existing simple split logic for backward compatibility
        # Store feature names
        self.feature_names = list(X.columns)

        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_val_scaled = self.scaler.transform(X_val)

        # Create and train model
        self.model = self._create_model()
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True

        # Evaluate
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_val = self.model.predict(X_val_scaled)

        metrics = {
            'train_accuracy': accuracy_score(y_train, y_pred_train),
            'val_accuracy': accuracy_score(y_val, y_pred_val),
            'train_f1': f1_score(y_train, y_pred_train, average='weighted'),
            'val_f1': f1_score(y_val, y_pred_val, average='weighted'),
        }

        # Print classification report
        print("\nValidation Classification Report:")
        print(classification_report(y_val, y_pred_val))

        return metrics

    def train_with_cv(self, X: pd.DataFrame, y: np.ndarray,
                     date_column: str = None,
                     n_folds: int = 5,
                     val_period_days: int = 30) -> Dict[str, float]:
        """
        Train with k-fold cross-validation (k >= 5).

        Performs walk-forward validation for time-series data, then trains
        final model on full dataset.

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
        from cv_utils import (
            check_production_readiness,
            plot_fold_performance,
            save_cv_summary
        )
        from walk_forward_validator import save_validation_report

        print(f"\n{'='*70}")
        print(f"TRAINING WITH {n_folds}-FOLD CROSS-VALIDATION")
        print(f"{'='*70}")

        # Store feature names
        self.feature_names = list(X.columns)
        if date_column and date_column in self.feature_names:
            # Remove date from feature names
            self.feature_names = [f for f in self.feature_names if f != date_column]

        # Create CV validator
        cv = UnifiedCrossValidator(
            n_folds=n_folds,
            val_period_days=val_period_days,
            min_samples_per_fold=50
        )

        # Define model factory (creates pipeline with scaler + model)
        def model_factory():
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            return Pipeline([
                ('scaler', StandardScaler()),
                ('classifier', self._create_model())
            ])

        # Prepare data for CV (ensure Series type for y)
        if not isinstance(y, pd.Series):
            y = pd.Series(y, index=X.index if hasattr(X, 'index') else None)

        # Run CV
        print(f"\nRunning {n_folds}-fold walk-forward validation...")
        report = cv.validate_sklearn_model(X, y, model_factory, date_column)

        # Check production readiness
        print(f"\n{'='*70}")
        print("PRODUCTION READINESS CHECK")
        print(f"{'='*70}")
        readiness = check_production_readiness(report)

        # Save results
        model_prefix = f'data/{self.model_type}'
        save_validation_report(report, f'{model_prefix}_cv_report.json')
        plot_fold_performance(report, f'{model_prefix}_cv_folds.png')
        save_cv_summary(report, readiness, f'{model_prefix}_cv_summary.json')

        # Train final model on full dataset
        print(f"\n{'='*70}")
        print("TRAINING FINAL MODEL ON FULL DATASET")
        print(f"{'='*70}")

        # Prepare features (remove date column if present)
        feature_cols = [c for c in X.columns if c != date_column]
        X_features = X[feature_cols]

        self.model = self._create_model()
        X_scaled = self.scaler.fit_transform(X_features)
        self.model.fit(X_scaled, y)
        self.is_trained = True

        print(f"\n✓ Final model trained on {len(X)} samples")

        # Log results
        print(f"\n{'='*70}")
        print("CROSS-VALIDATION SUMMARY")
        print(f"{'='*70}")
        print(f"Mean ROC-AUC:     {report.mean_roc_auc:.4f} ± {report.std_roc_auc:.4f}")
        print(f"Mean Accuracy:    {report.mean_accuracy:.4f} ± {report.std_accuracy:.4f}")
        print(f"Mean F1:          {report.mean_f1:.4f} ± {report.std_f1:.4f}")
        print(f"AUC Degradation:  {report.auc_degradation:+.4f}")
        print(f"Production Ready: {readiness['is_production_ready']}")

        if not readiness['is_production_ready']:
            print(f"\n⚠️  WARNING: Model may not be production ready")
            if readiness['issues']:
                print("Issues:")
                for issue in readiness['issues']:
                    print(f"  - {issue}")

        print(f"{'='*70}\n")

        return {
            'validation_report': report,
            'mean_roc_auc': report.mean_roc_auc,
            'std_roc_auc': report.std_roc_auc,
            'mean_accuracy': report.mean_accuracy,
            'std_accuracy': report.std_accuracy,
            'mean_f1': report.mean_f1,
            'std_f1': report.std_f1,
            'auc_degradation': report.auc_degradation,
            'production_ready': readiness['is_production_ready'],
            'readiness_assessment': readiness
        }

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict price movement.

        Args:
            X: Feature DataFrame

        Returns:
            Predictions (1, 0, or -1)
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Ensure features match training
        X = X[self.feature_names]

        # Scale and predict
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict probabilities for each class.

        Args:
            X: Feature DataFrame

        Returns:
            Probability matrix
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Ensure features match training
        X = X[self.feature_names]

        # Scale and predict
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature importance.

        Returns:
            DataFrame with feature importances
        """
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
        elif hasattr(self.model, 'coef_'):
            importances = np.abs(self.model.coef_[0])
        else:
            return pd.DataFrame()

        df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importances
        })

        return df.sort_values('importance', ascending=False)

    def save(self, filepath: str):
        """Save model to disk."""
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        data = {
            'model_type': self.model_type,
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'is_trained': self.is_trained
        }

        with open(filepath, 'wb') as f:
            pickle.dump(data, f)

    def load(self, filepath: str):
        """Load model from disk."""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        self.model_type = data['model_type']
        self.model = data['model']
        self.scaler = data['scaler']
        self.feature_names = data['feature_names']
        self.is_trained = data['is_trained']


class EnsemblePredictor:
    """Ensemble of multiple models for robust predictions."""

    def __init__(self, model_types: List[str] = None):
        """
        Initialize ensemble.

        Args:
            model_types: List of model types to ensemble
        """
        if model_types is None:
            model_types = ['random_forest', 'gradient_boost', 'logistic']

        self.models = [PriceMovementPredictor(mt) for mt in model_types]
        self.weights = None
        self.is_trained = False

    def train(self, X: pd.DataFrame, y: np.ndarray,
             validation_split: float = 0.2) -> Dict[str, float]:
        """
        Train all models in ensemble.

        Args:
            X: Feature DataFrame
            y: Labels
            validation_split: Fraction for validation

        Returns:
            Dictionary of metrics
        """
        # Split data once
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=validation_split, random_state=42
        )

        # Train each model
        val_accuracies = []
        for i, model in enumerate(self.models):
            print(f"\nTraining model {i+1}/{len(self.models)}: {model.model_type}")

            # Train on the same split
            model.feature_names = list(X_train.columns)
            X_train_scaled = model.scaler.fit_transform(X_train)
            X_val_scaled = model.scaler.transform(X_val)

            model.model = model._create_model()
            model.model.fit(X_train_scaled, y_train)
            model.is_trained = True

            # Evaluate
            y_pred_val = model.model.predict(X_val_scaled)
            acc = accuracy_score(y_val, y_pred_val)
            val_accuracies.append(acc)

            print(f"Validation accuracy: {acc:.4f}")

        # Set weights based on validation performance
        total_acc = sum(val_accuracies)
        self.weights = [acc / total_acc for acc in val_accuracies]
        self.is_trained = True

        # Ensemble predictions
        y_pred_ensemble = self.predict(X_val)
        ensemble_acc = accuracy_score(y_val, y_pred_ensemble)

        return {
            'ensemble_accuracy': ensemble_acc,
            'individual_accuracies': val_accuracies,
            'weights': self.weights
        }

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict using weighted ensemble.

        Args:
            X: Feature DataFrame

        Returns:
            Predictions
        """
        if not self.is_trained:
            raise ValueError("Ensemble not trained yet")

        # Get predictions from all models
        all_preds = []
        for model in self.models:
            preds = model.predict(X)
            all_preds.append(preds)

        all_preds = np.array(all_preds)

        # Weighted voting
        ensemble_preds = []
        for i in range(len(X)):
            votes = {}
            for j, pred in enumerate(all_preds[:, i]):
                votes[pred] = votes.get(pred, 0) + self.weights[j]

            # Get prediction with highest weighted vote
            ensemble_preds.append(max(votes.items(), key=lambda x: x[1])[0])

        return np.array(ensemble_preds)

    def predict_proba(self, X: pd.DataFrame) -> Dict[int, float]:
        """
        Predict probabilities using ensemble.

        Args:
            X: Feature DataFrame

        Returns:
            Dictionary mapping class to probability
        """
        if not self.is_trained:
            raise ValueError("Ensemble not trained yet")

        # Average probabilities from all models
        all_probs = []
        for model, weight in zip(self.models, self.weights):
            probs = model.predict_proba(X)
            all_probs.append(probs * weight)

        avg_probs = np.sum(all_probs, axis=0)

        return avg_probs


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
                          probabilities: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
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
        if not self.performance_history:
            return 0.0

        records = self.performance_history
        if lookback_hours:
            cutoff = datetime.now() - pd.Timedelta(hours=lookback_hours)
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
        with open(self.filepath, 'w') as f:
            json.dump(self.performance_history, f, indent=2)

    def load(self):
        """Load performance history from disk."""
        try:
            with open(self.filepath, 'r') as f:
                self.performance_history = json.load(f)
        except FileNotFoundError:
            self.performance_history = []
