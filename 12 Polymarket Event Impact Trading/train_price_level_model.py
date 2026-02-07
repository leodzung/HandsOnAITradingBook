#!/usr/bin/env python3
"""
Train Price-Level Prediction Model
Trains a GradientBoostingClassifier to predict if price will reach strike by expiry.
"""

import pandas as pd
import numpy as np
import pickle
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    roc_auc_score, roc_curve, accuracy_score, precision_score,
    recall_score, f1_score, confusion_matrix, classification_report,
    brier_score_loss
)
from sklearn.calibration import calibration_curve, CalibratedClassifierCV
import matplotlib.pyplot as plt

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceLevelModelTrainer:
    """Train and evaluate price-level prediction model."""

    def __init__(self, data_path: str = 'data/training_data_v2.csv',
                 model_path: str = 'data/price_level_model.pkl',
                 report_path: str = 'data/training_report.txt',
                 enable_walk_forward: bool = False,
                 wf_n_folds: int = 5,
                 wf_val_period_days: int = 30):
        """
        Initialize trainer.

        Args:
            data_path: Path to training data CSV
            model_path: Path to save trained model
            report_path: Path to save training report
            enable_walk_forward: Enable walk-forward validation
            wf_n_folds: Number of folds for walk-forward
            wf_val_period_days: Validation period length in days
        """
        self.data_path = data_path
        self.model_path = model_path
        self.report_path = report_path
        self.model = None
        self.feature_names = None
        self.metrics = {}

        # Walk-forward validation parameters
        self.enable_walk_forward = enable_walk_forward
        self.wf_n_folds = wf_n_folds
        self.wf_val_period_days = wf_val_period_days

        # Ensure output directory exists
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

    def load_data(self, keep_date: bool = False) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Load and prepare training data.

        Args:
            keep_date: If True, keep entry_date column in features (for walk-forward)

        Returns:
            Tuple of (features DataFrame, labels Series)
        """
        logger.info(f"Loading data from {self.data_path}")
        df = pd.read_csv(self.data_path)

        logger.info(f"Loaded {len(df)} samples")
        logger.info(f"Columns: {df.columns.tolist()}")

        # Metadata columns to exclude from features
        metadata_cols = ['asset', 'entry_price', 'strike_price',
                        'direction', 'days_to_expiry', 'label']

        # Conditionally exclude entry_date
        if not keep_date:
            metadata_cols.append('entry_date')

        # Extract features and labels
        feature_cols = [col for col in df.columns if col not in metadata_cols]
        X = df[feature_cols]
        y = df['label']

        if not keep_date:
            self.feature_names = feature_cols
        else:
            # Store feature names without date for model training
            self.feature_names = [c for c in feature_cols if c != 'entry_date']

        logger.info(f"Features: {len(self.feature_names)} (date column {'included' if keep_date else 'excluded'})")
        logger.info(f"Class distribution: {y.value_counts().to_dict()}")

        # Check for NaNs
        nan_count = X.isnull().sum().sum()
        if nan_count > 0:
            logger.warning(f"Found {nan_count} NaN values in features")
            X = X.fillna(0)

        return X, y

    def split_data(self, X: pd.DataFrame, y: pd.Series,
                   test_size: float = 0.15, val_size: float = 0.15,
                   random_state: int = 42) -> Dict:
        """
        Split data into train/validation/test sets.

        Args:
            X: Features
            y: Labels
            test_size: Proportion for test set
            val_size: Proportion for validation set (from remaining data)
            random_state: Random seed

        Returns:
            Dictionary with train/val/test splits
        """
        # First split: train+val vs test
        X_temp, X_test, y_temp, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )

        # Second split: train vs val
        val_size_adjusted = val_size / (1 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=val_size_adjusted,
            random_state=random_state, stratify=y_temp
        )

        logger.info(f"Split sizes:")
        logger.info(f"  Train: {len(X_train)} ({len(X_train)/len(X)*100:.1f}%)")
        logger.info(f"  Val:   {len(X_val)} ({len(X_val)/len(X)*100:.1f}%)")
        logger.info(f"  Test:  {len(X_test)} ({len(X_test)/len(X)*100:.1f}%)")

        return {
            'X_train': X_train, 'y_train': y_train,
            'X_val': X_val, 'y_val': y_val,
            'X_test': X_test, 'y_test': y_test
        }

    def train_model(self, X_train: pd.DataFrame, y_train: pd.Series):
        """
        Train GradientBoostingClassifier with calibration.

        Args:
            X_train: Training features
            y_train: Training labels

        Returns:
            Calibrated trained model
        """
        logger.info("Training GradientBoostingClassifier...")

        # Base model hyperparameters
        base_model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            min_samples_split=10,
            min_samples_leaf=5,
            subsample=0.8,
            random_state=42,
            verbose=1
        )

        # Train base model
        base_model.fit(X_train, y_train)

        logger.info("Applying probability calibration (isotonic)...")

        # Calibrate probabilities
        calibrated_model = CalibratedClassifierCV(
            estimator=base_model,
            method='isotonic',
            cv='prefit'
        )
        calibrated_model.fit(X_train, y_train)

        logger.info("Training complete")

        return calibrated_model

    def evaluate_model(self, model,
                      X: pd.DataFrame, y: pd.Series,
                      dataset_name: str = 'test') -> Dict:
        """
        Evaluate model on dataset.

        Args:
            model: Trained model
            X: Features
            y: True labels
            dataset_name: Name for logging

        Returns:
            Dictionary of metrics
        """
        logger.info(f"Evaluating on {dataset_name} set...")

        # Predictions
        y_pred = model.predict(X)
        y_prob = model.predict_proba(X)[:, 1]

        # Calculate metrics
        metrics = {
            'accuracy': accuracy_score(y, y_pred),
            'precision': precision_score(y, y_pred, zero_division=0),
            'recall': recall_score(y, y_pred, zero_division=0),
            'f1': f1_score(y, y_pred, zero_division=0),
            'roc_auc': roc_auc_score(y, y_prob),
            'brier_score': brier_score_loss(y, y_prob)
        }

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)

        logger.info(f"{dataset_name.upper()} METRICS:")
        logger.info(f"  Accuracy:  {metrics['accuracy']:.4f}")
        logger.info(f"  Precision: {metrics['precision']:.4f}")
        logger.info(f"  Recall:    {metrics['recall']:.4f}")
        logger.info(f"  F1 Score:  {metrics['f1']:.4f}")
        logger.info(f"  ROC-AUC:   {metrics['roc_auc']:.4f}")
        logger.info(f"  Brier:     {metrics['brier_score']:.4f}")
        logger.info(f"\nConfusion Matrix:")
        logger.info(f"  TN: {cm[0,0]}, FP: {cm[0,1]}")
        logger.info(f"  FN: {cm[1,0]}, TP: {cm[1,1]}")

        return metrics

    def plot_roc_curve(self, model: GradientBoostingClassifier,
                       X_test: pd.DataFrame, y_test: pd.Series):
        """Plot ROC curve."""
        y_prob = model.predict_proba(X_test)[:, 1]
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        auc = roc_auc_score(y_test, y_prob)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, label=f'ROC Curve (AUC = {auc:.3f})', linewidth=2)
        plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve - Price Level Predictor')
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig('data/roc_curve.png', dpi=100)
        logger.info("Saved ROC curve to data/roc_curve.png")
        plt.close()

    def plot_calibration_curve(self, model: GradientBoostingClassifier,
                               X_test: pd.DataFrame, y_test: pd.Series):
        """Plot calibration curve."""
        y_prob = model.predict_proba(X_test)[:, 1]
        fraction_of_positives, mean_predicted_value = calibration_curve(
            y_test, y_prob, n_bins=10, strategy='uniform'
        )

        plt.figure(figsize=(8, 6))
        plt.plot(mean_predicted_value, fraction_of_positives, 's-',
                label='Model', linewidth=2, markersize=8)
        plt.plot([0, 1], [0, 1], 'k--', label='Perfectly Calibrated')
        plt.xlabel('Mean Predicted Probability')
        plt.ylabel('Fraction of Positives')
        plt.title('Calibration Curve - Price Level Predictor')
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig('data/calibration_curve.png', dpi=100)
        logger.info("Saved calibration curve to data/calibration_curve.png")
        plt.close()

    def plot_feature_importance(self, model,
                                feature_names: list, top_n: int = 20):
        """Plot feature importance."""
        # Handle calibrated models
        if hasattr(model, 'estimator'):
            importances = model.estimator.feature_importances_
        else:
            importances = model.feature_importances_
        indices = np.argsort(importances)[::-1][:top_n]

        plt.figure(figsize=(10, 8))
        plt.barh(range(top_n), importances[indices])
        plt.yticks(range(top_n), [feature_names[i] for i in indices])
        plt.xlabel('Feature Importance')
        plt.title(f'Top {top_n} Most Important Features')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        plt.savefig('data/feature_importance.png', dpi=100)
        logger.info("Saved feature importance to data/feature_importance.png")
        plt.close()

        # Log top features
        logger.info(f"\nTop {top_n} Features:")
        for i, idx in enumerate(indices, 1):
            logger.info(f"  {i}. {feature_names[idx]}: {importances[idx]:.4f}")

    def save_model(self, model: GradientBoostingClassifier, validation_report=None):
        """Save trained model with optional validation report."""
        model_data = {
            'model': model,
            'feature_names': self.feature_names,
            'trained_at': datetime.now().isoformat(),
            'metrics': self.metrics
        }

        # Add validation report if available
        if validation_report:
            model_data['validation_report'] = validation_report

        with open(self.model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Saved model to {self.model_path}")

    def save_report(self, validation_summary=None):
        """Save training report with optional walk-forward validation summary."""
        report = []
        report.append("=" * 70)
        report.append("PRICE LEVEL MODEL TRAINING REPORT")
        report.append("=" * 70)
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"\nModel: GradientBoostingClassifier")
        report.append(f"Features: {len(self.feature_names)}")
        report.append(f"Training Data: {self.data_path}")

        # Add walk-forward validation summary if available
        if validation_summary:
            report.append("\n" + "-" * 70)
            report.append("WALK-FORWARD VALIDATION SUMMARY")
            report.append("-" * 70)
            report.append(f"  Folds:              {validation_summary['n_folds']}")
            report.append(f"  Val Period (days):  {validation_summary['val_period_days']}")
            report.append(f"  Mean ROC-AUC:       {validation_summary['mean_roc_auc']:.4f} ± {validation_summary['std_roc_auc']:.4f}")
            report.append(f"  Mean Accuracy:      {validation_summary['mean_accuracy']:.4f} ± {validation_summary['std_accuracy']:.4f}")
            report.append(f"  Mean F1:            {validation_summary['mean_f1']:.4f} ± {validation_summary['std_f1']:.4f}")
            report.append(f"  AUC Degradation:    {validation_summary['auc_degradation']:+.4f}")

        report.append("\n" + "-" * 70)
        report.append("PERFORMANCE METRICS")
        report.append("-" * 70)

        for dataset in ['train', 'val', 'test']:
            if dataset in self.metrics:
                report.append(f"\n{dataset.upper()} SET:")
                for metric, value in self.metrics[dataset].items():
                    report.append(f"  {metric:12s}: {value:.4f}")

        report.append("\n" + "-" * 70)
        report.append("FILES GENERATED")
        report.append("-" * 70)
        report.append(f"  Model:              {self.model_path}")
        if validation_summary:
            report.append(f"  Validation Report:  {self.model_path.replace('.pkl', '_validation.json')}")
        report.append(f"  ROC Curve:          data/roc_curve.png")
        report.append(f"  Calibration:        data/calibration_curve.png")
        report.append(f"  Feature Importance: data/feature_importance.png")

        report.append("\n" + "=" * 70)

        report_text = "\n".join(report)

        with open(self.report_path, 'w') as f:
            f.write(report_text)

        logger.info(f"Saved training report to {self.report_path}")
        print("\n" + report_text)

    def run_with_walk_forward(self):
        """Train with walk-forward validation."""
        from walk_forward_validator import WalkForwardValidator, save_validation_report
        from dataclasses import asdict

        logger.info("=" * 70)
        logger.info("TRAINING WITH WALK-FORWARD VALIDATION")
        logger.info("=" * 70)

        # 1. Load data (keep entry_date for temporal splitting)
        X, y = self.load_data(keep_date=True)

        # Verify entry_date column exists
        if 'entry_date' not in X.columns:
            raise ValueError("entry_date column not found in training data. "
                           "Walk-forward validation requires temporal information.")

        # 2. Create validator
        validator = WalkForwardValidator(
            n_folds=self.wf_n_folds,
            val_period_days=self.wf_val_period_days,
            gap_days=0,
            min_train_samples=500,
            min_val_samples=50
        )

        # 3. Define model factory
        def model_factory():
            base_model = GradientBoostingClassifier(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                min_samples_split=10,
                min_samples_leaf=5,
                subsample=0.8,
                random_state=42,
                verbose=0
            )
            # Return calibrated model
            calibrated = CalibratedClassifierCV(
                estimator=base_model,
                method='isotonic',
                cv=3  # Use internal CV for calibration
            )
            return calibrated

        # 4. Define evaluation function
        def eval_fn(model, X_eval, y_eval):
            # Remove entry_date for prediction
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

        # 5. Run validation
        logger.info("Running walk-forward validation...")
        report = validator.validate(X, y, model_factory, eval_fn, date_column='entry_date')

        # 6. Save validation report
        report_path = self.model_path.replace('.pkl', '_validation.json')
        save_validation_report(report, report_path)

        # 7. Train final model on full dataset
        logger.info("\n" + "=" * 70)
        logger.info("TRAINING FINAL MODEL ON FULL DATASET")
        logger.info("=" * 70)

        # Remove entry_date for final training
        feature_cols = [c for c in X.columns if c != 'entry_date']
        X_features = X[feature_cols]

        # Train base model
        logger.info("Training GradientBoostingClassifier...")
        base_model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            min_samples_split=10,
            min_samples_leaf=5,
            subsample=0.8,
            random_state=42,
            verbose=1
        )
        base_model.fit(X_features, y)

        # Apply calibration using last 20% as calibration set
        logger.info("Applying probability calibration...")
        from sklearn.model_selection import train_test_split
        X_train, X_cal, y_train, y_cal = train_test_split(
            X_features, y, test_size=0.2, random_state=42, stratify=y
        )

        # Retrain on 80%
        base_model.fit(X_train, y_train)

        # Calibrate on 20%
        calibrated_model = CalibratedClassifierCV(
            estimator=base_model,
            method='isotonic',
            cv='prefit'
        )
        calibrated_model.fit(X_cal, y_cal)

        self.model = calibrated_model

        # 8. Evaluate on full dataset (for reference)
        logger.info("\nEvaluating final model on full dataset...")
        self.metrics['full'] = self.evaluate_model(
            self.model, X_features, y, 'full'
        )

        # 9. Generate plots
        logger.info("\nGenerating visualizations...")
        self.plot_roc_curve(self.model, X_features, y)
        self.plot_calibration_curve(self.model, X_features, y)
        self.plot_feature_importance(self.model, self.feature_names, top_n=20)

        # 10. Save model with validation metadata
        logger.info("\nSaving model...")
        validation_summary = {
            'n_folds': report.n_folds,
            'val_period_days': report.val_period_days,
            'mean_roc_auc': report.mean_roc_auc,
            'std_roc_auc': report.std_roc_auc,
            'mean_accuracy': report.mean_accuracy,
            'std_accuracy': report.std_accuracy,
            'mean_f1': report.mean_f1,
            'std_f1': report.std_f1,
            'auc_degradation': report.auc_degradation
        }
        self.save_model(self.model, validation_report=validation_summary)

        # 11. Save report
        self.save_report(validation_summary=validation_summary)

        logger.info("\n" + "=" * 70)
        logger.info("TRAINING WITH WALK-FORWARD VALIDATION COMPLETE!")
        logger.info("=" * 70)

        return report

    def run(self):
        """Run complete training pipeline."""
        if self.enable_walk_forward:
            return self.run_with_walk_forward()

        # Standard training (backward compatible)
        logger.info("=" * 70)
        logger.info("STARTING PRICE LEVEL MODEL TRAINING")
        logger.info("=" * 70)

        # 1. Load data
        X, y = self.load_data(keep_date=False)

        # 2. Split data
        splits = self.split_data(X, y)

        # 3. Train model
        self.model = self.train_model(splits['X_train'], splits['y_train'])

        # 4. Evaluate on all sets
        self.metrics['train'] = self.evaluate_model(
            self.model, splits['X_train'], splits['y_train'], 'train'
        )
        self.metrics['val'] = self.evaluate_model(
            self.model, splits['X_val'], splits['y_val'], 'val'
        )
        self.metrics['test'] = self.evaluate_model(
            self.model, splits['X_test'], splits['y_test'], 'test'
        )

        # 5. Generate plots
        logger.info("\nGenerating visualizations...")
        self.plot_roc_curve(self.model, splits['X_test'], splits['y_test'])
        self.plot_calibration_curve(self.model, splits['X_test'], splits['y_test'])
        self.plot_feature_importance(self.model, self.feature_names, top_n=20)

        # 6. Save model
        self.save_model(self.model)

        # 7. Save report
        self.save_report()

        logger.info("\n" + "=" * 70)
        logger.info("TRAINING COMPLETE!")
        logger.info("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Train Price-Level Prediction Model')
    parser.add_argument('--walk-forward', action='store_true',
                       help='Enable walk-forward validation')
    parser.add_argument('--n-folds', type=int, default=5,
                       help='Number of validation folds (default: 5)')
    parser.add_argument('--val-period-days', type=int, default=30,
                       help='Validation period length in days (default: 30)')
    parser.add_argument('--data-path', type=str, default='data/training_data_v2.csv',
                       help='Path to training data CSV')
    parser.add_argument('--model-path', type=str, default='data/price_level_model.pkl',
                       help='Path to save trained model')

    args = parser.parse_args()

    trainer = PriceLevelModelTrainer(
        data_path=args.data_path,
        model_path=args.model_path,
        enable_walk_forward=args.walk_forward,
        wf_n_folds=args.n_folds,
        wf_val_period_days=args.val_period_days
    )
    trainer.run()
