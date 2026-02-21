#!/usr/bin/env python3
"""
Train Short-Expiry Models with Walk-Forward Validation

This script implements rigorous forward-validation (walk-forward) for the short-expiry
trading bot using the WalkForwardValidator framework.

✅ USES:
  - MarketSnapshotCollector data (labeled snapshots from market_snapshots.db)
  - WalkForwardValidator for temporal cross-validation
  - ModelTrainer (centralized training engine)

📊 WORKFLOW:
  1. Load labeled snapshots from market_snapshots.db
  2. Split data using expanding window walk-forward validation
  3. Train bucket-specific models (ultra_short, short, medium)
  4. Evaluate on out-of-sample future data
  5. Save models + validation reports

🔄 WALK-FORWARD VALIDATION:
  - Prevents lookahead bias (only train on past data)
  - Expanding window (realistic for production retraining)
  - Temporal ordering maintained
  - Example: 5 folds, 30-day validation windows

REQUIREMENTS:
  - market_snapshots.db with 200+ labeled samples
  - Snapshots must have entry_date/snapshot_time column
  - Labeled outcomes (YES/NO/INVALID)

RUN:
  python3 scripts/train_short_expiry_forward_validation.py --bucket all --n-folds 5

Created: 2026-02-20
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
import logging
import argparse
import json
from datetime import datetime, timezone
from typing import Dict, Optional

from src.ml.snapshot_collector import MarketSnapshotCollector
from src.ml.training_engine import ModelTrainer, ModelConfig
from src.utils.walk_forward_validator import WalkForwardValidator, save_validation_report
from src.monitoring.telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ShortExpiryForwardValidator:
    """Train short-expiry models with walk-forward validation."""

    def __init__(self,
                 snapshot_db: str = 'data/market_snapshots.db',
                 models_dir: str = 'data/models',
                 reports_dir: str = 'data/validation_reports',
                 telegram_config: Optional[Dict] = None):
        """
        Initialize validator.

        Args:
            snapshot_db: Path to market snapshots database
            models_dir: Directory to save trained models
            reports_dir: Directory to save validation reports
            telegram_config: Optional Telegram configuration
        """
        self.snapshot_db = Path(snapshot_db)
        self.models_dir = Path(models_dir)
        self.reports_dir = Path(reports_dir)

        # Create output directories
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.snapshot_collector = MarketSnapshotCollector(db_path=str(self.snapshot_db))

        # Telegram notifications (optional)
        self.telegram = None
        if telegram_config and telegram_config.get('enabled', False):
            self.telegram = TelegramNotifier(
                bot_token=telegram_config.get('bot_token', ''),
                chat_id=telegram_config.get('chat_id', ''),
                enabled=True
            )

    def load_training_data(self, bucket: Optional[str] = None) -> pd.DataFrame:
        """
        Load labeled snapshots for training.

        Args:
            bucket: Filter by bucket (ultra_short, short, medium) or None for all

        Returns:
            DataFrame with features + labels + metadata
        """
        logger.info("Loading training data from snapshot collector...")

        # Get all labeled snapshots for short_expiry bot
        df = self.snapshot_collector.get_training_data(
            bot_type='short_expiry',
            labeled_only=True
        )

        if df.empty:
            raise ValueError("No labeled snapshots found! Run bot to collect data first.")

        logger.info(f"Loaded {len(df)} labeled snapshots")

        # Filter by bucket if specified
        if bucket and bucket != 'all':
            df = df[df['bucket'] == bucket]
            logger.info(f"Filtered to {len(df)} samples for bucket: {bucket}")

        # Create binary label from outcome
        # YES = 1, NO = 0, INVALID/EXPIRED = drop
        df = df[df['outcome'].isin(['YES', 'NO'])].copy()
        df['label'] = (df['outcome'] == 'YES').astype(int)

        logger.info(f"Label distribution:\n{df['label'].value_counts()}")

        # Ensure we have a date column for temporal ordering
        if 'snapshot_time' in df.columns:
            df['entry_date'] = pd.to_datetime(df['snapshot_time'])
        else:
            raise ValueError("No snapshot_time column found - cannot do temporal validation")

        return df

    def prepare_features(self, df: pd.DataFrame, bucket: Optional[str] = None) -> tuple:
        """
        Prepare feature matrix and labels.

        Args:
            df: DataFrame from load_training_data()
            bucket: Bucket name (for logging)

        Returns:
            Tuple of (X, y) where X has entry_date column
        """
        # Columns to exclude from features
        exclude_cols = [
            # Labels
            'label', 'outcome', 'resolution_price', 'resolution_time', 'labeled',

            # IDs
            'id', 'market_id', 'condition_id', 'token_id', 'position_id',

            # Metadata
            'question', 'asset', 'market_type', 'bucket', 'bot_type',
            'snapshot_time', 'expiry_date',

            # Trade execution
            'position_opened', 'rejection_reason',

            # Model outputs (don't train on predictions!)
            'model_prob', 'confidence', 'edge', 'predicted_outcome',

            # Prices (avoid leakage - we predict from features, not prices)
            'yes_price', 'no_price', 'spread'
        ]

        # Get feature columns
        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Keep entry_date for temporal validation
        if 'entry_date' not in feature_cols:
            feature_cols.append('entry_date')

        X = df[feature_cols].copy()
        y = df['label'].copy()

        # Fill NaN values (tree models handle this but let's be safe)
        numeric_cols = X.select_dtypes(include=[np.number]).columns
        X[numeric_cols] = X[numeric_cols].fillna(0)

        logger.info(f"Prepared features: {len(feature_cols) - 1} (+ entry_date for temporal CV)")
        logger.info(f"Samples: {len(X)}")

        return X, y

    def train_with_forward_validation(self,
                                     bucket: str,
                                     n_folds: int = 5,
                                     val_period_days: int = 30,
                                     gap_days: int = 0) -> Dict:
        """
        Train model with walk-forward validation.

        Args:
            bucket: Bucket to train ('ultra_short', 'short', 'medium', or 'all')
            n_folds: Number of validation folds
            val_period_days: Length of each validation period
            gap_days: Embargo period between train/val

        Returns:
            Dictionary with model, metrics, and validation report
        """
        logger.info("="*70)
        logger.info(f"WALK-FORWARD VALIDATION - {bucket.upper()}")
        logger.info("="*70)

        # Load data
        df = self.load_training_data(bucket=bucket if bucket != 'all' else None)

        if len(df) < 200:
            raise ValueError(f"Insufficient data: {len(df)} samples (need 200+ for robust validation)")

        # Prepare features
        X, y = self.prepare_features(df, bucket=bucket)

        # Create model trainer
        model_config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=200,
            learning_rate=0.05,
            max_depth=4,
            min_samples_split=10,
            min_samples_leaf=5,
            subsample=0.8,
            apply_calibration=True,
            calibration_method='isotonic',
            random_state=42,
            verbose=True
        )

        trainer = ModelTrainer(config=model_config, telegram_notifier=self.telegram)

        # Create walk-forward validator
        validator = WalkForwardValidator(
            n_folds=n_folds,
            val_period_days=val_period_days,
            gap_days=gap_days,
            min_train_samples=max(100, len(df) // 20),
            min_val_samples=30
        )

        # Run validation
        logger.info(f"\nRunning {n_folds}-fold walk-forward validation...")
        validation_report = trainer.train_with_cv(
            X=X,
            y=y,
            cv_validator=validator,
            date_column='entry_date'
        )

        # Save validation report
        report_filename = f"short_expiry_{bucket}_wfv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path = self.reports_dir / report_filename
        save_validation_report(validation_report, str(report_path))
        logger.info(f"Validation report saved: {report_path}")

        # Train final model on ALL data (this is what we'll deploy)
        logger.info("\n" + "="*70)
        logger.info("TRAINING FINAL MODEL (all data)")
        logger.info("="*70)

        # Remove entry_date for final training
        X_final = X.drop(columns=['entry_date'])

        # Split into train/val for calibration
        from sklearn.model_selection import train_test_split
        X_train, X_val, y_train, y_val = train_test_split(
            X_final, y, test_size=0.2, random_state=42, stratify=y
        )

        final_model, final_metrics = trainer.train(X_train, y_train, X_val, y_val)

        # Save final model
        model_filename = f"short_expiry_{bucket}_model.pkl"
        model_path = self.models_dir / model_filename

        metadata = {
            'bucket': bucket,
            'validation_type': 'walk_forward',
            'n_folds': n_folds,
            'val_period_days': val_period_days,
            'training_samples': len(X),
            'walk_forward_metrics': {
                'mean_roc_auc': validation_report.mean_roc_auc,
                'std_roc_auc': validation_report.std_roc_auc,
                'mean_accuracy': validation_report.mean_accuracy,
                'std_accuracy': validation_report.std_accuracy,
                'auc_degradation': validation_report.auc_degradation
            },
            'data_source': 'market_snapshots_db',
            'validation_report_path': str(report_path)
        }

        trainer.save_model(final_model, final_metrics, str(model_path), metadata=metadata)

        logger.info(f"\n✅ Final model saved: {model_path}")

        # Send Telegram summary
        if self.telegram:
            self._send_training_summary(bucket, validation_report, final_metrics, len(X))

        return {
            'model': final_model,
            'metrics': final_metrics,
            'validation_report': validation_report,
            'model_path': model_path,
            'report_path': report_path
        }

    def _send_training_summary(self, bucket: str, validation_report, final_metrics: Dict, n_samples: int):
        """Send training summary via Telegram."""
        if not self.telegram:
            return

        # Get validation metrics
        val_metrics = final_metrics.get('val', final_metrics.get('train'))

        # Performance emoji
        mean_auc = validation_report.mean_roc_auc
        if mean_auc >= 0.70:
            emoji = "🟢"
            status = "Production Ready"
        elif mean_auc >= 0.60:
            emoji = "🟡"
            status = "Marginal"
        else:
            emoji = "🔴"
            status = "Needs Improvement"

        message = (
            f"<b>{emoji} FORWARD-VALIDATION COMPLETE</b>\n\n"
            f"<b>Bucket:</b> {bucket}\n"
            f"<b>Samples:</b> {n_samples:,}\n"
            f"<b>Folds:</b> {validation_report.n_folds}\n\n"
            f"<b>Walk-Forward Results:</b>\n"
            f"  ROC-AUC: {validation_report.mean_roc_auc:.3f} ± {validation_report.std_roc_auc:.3f}\n"
            f"  Accuracy: {validation_report.mean_accuracy:.3f} ± {validation_report.std_accuracy:.3f}\n"
            f"  F1 Score: {validation_report.mean_f1:.3f} ± {validation_report.std_f1:.3f}\n"
            f"  Degradation: {validation_report.auc_degradation:+.3f}\n\n"
            f"<b>Final Model (Hold-out Val):</b>\n"
            f"  Accuracy: {val_metrics.accuracy:.3f}\n"
            f"  ROC-AUC: {val_metrics.roc_auc:.3f}\n"
            f"  Brier: {val_metrics.brier_score:.3f}\n\n"
            f"<b>Status:</b> {status}\n"
            f"<b>Ready:</b> {'Yes ✅' if mean_auc >= 0.60 else 'No ❌'}"
        )

        self.telegram.send_message(message)

    def train_all_buckets(self,
                         n_folds: int = 5,
                         val_period_days: int = 30,
                         gap_days: int = 0) -> Dict[str, Dict]:
        """
        Train models for all buckets with walk-forward validation.

        Args:
            n_folds: Number of validation folds
            val_period_days: Length of each validation period
            gap_days: Embargo period between train/val

        Returns:
            Dictionary mapping bucket -> training results
        """
        logger.info("\n" + "="*70)
        logger.info("TRAINING ALL BUCKETS WITH WALK-FORWARD VALIDATION")
        logger.info("="*70 + "\n")

        buckets = ['ultra_short', 'short', 'medium']
        results = {}

        for bucket in buckets:
            try:
                result = self.train_with_forward_validation(
                    bucket=bucket,
                    n_folds=n_folds,
                    val_period_days=val_period_days,
                    gap_days=gap_days
                )
                results[bucket] = result
                logger.info(f"\n✅ {bucket} completed")

            except ValueError as e:
                logger.warning(f"\n⚠️  Skipping {bucket}: {e}")
                continue

            except Exception as e:
                logger.error(f"\n❌ Error training {bucket}: {e}", exc_info=True)
                continue

        # Summary
        logger.info("\n" + "="*70)
        logger.info("TRAINING SUMMARY")
        logger.info("="*70)

        for bucket, result in results.items():
            val_report = result['validation_report']
            logger.info(f"\n{bucket.upper()}:")
            logger.info(f"  Mean ROC-AUC: {val_report.mean_roc_auc:.3f} ± {val_report.std_roc_auc:.3f}")
            logger.info(f"  Mean Accuracy: {val_report.mean_accuracy:.3f} ± {val_report.std_accuracy:.3f}")
            logger.info(f"  Degradation: {val_report.auc_degradation:+.3f}")
            logger.info(f"  Model: {result['model_path']}")

        if not results:
            logger.warning("\n⚠️  No models trained - insufficient data")
            logger.info("Continue running trader_short_expiry.py to collect more data")

        return results


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description='Train short-expiry models with walk-forward validation')

    parser.add_argument('--bucket', type=str, default='all',
                       choices=['ultra_short', 'short', 'medium', 'all'],
                       help='Bucket to train (default: all)')

    parser.add_argument('--n-folds', type=int, default=5,
                       help='Number of validation folds (default: 5)')

    parser.add_argument('--val-period-days', type=int, default=30,
                       help='Validation period length in days (default: 30)')

    parser.add_argument('--gap-days', type=int, default=0,
                       help='Embargo period between train/val in days (default: 0)')

    parser.add_argument('--snapshot-db', type=str, default='data/market_snapshots.db',
                       help='Path to market snapshots database')

    parser.add_argument('--models-dir', type=str, default='data/models',
                       help='Directory to save trained models')

    parser.add_argument('--telegram-config', type=str, default='config/config_short_expiry.json',
                       help='Path to config with Telegram settings')

    args = parser.parse_args()

    # Load Telegram config
    telegram_config = None
    if Path(args.telegram_config).exists():
        with open(args.telegram_config) as f:
            config = json.load(f)
            telegram_config = config.get('telegram', {})

    # Initialize validator
    validator = ShortExpiryForwardValidator(
        snapshot_db=args.snapshot_db,
        models_dir=args.models_dir,
        telegram_config=telegram_config
    )

    # Check data availability
    stats = validator.snapshot_collector.get_statistics()
    logger.info("\nSnapshot Database Status:")
    logger.info(f"  Total snapshots: {stats['total_snapshots']:,}")
    logger.info(f"  Labeled: {stats['labeled_snapshots']:,}")
    logger.info(f"  Unlabeled: {stats['unlabeled_snapshots']:,}")

    if stats['labeled_snapshots'] < 200:
        logger.error(f"\n❌ Insufficient labeled data: {stats['labeled_snapshots']} (need 200+)")
        logger.info("\nCollect more data by:")
        logger.info("1. Running trader_short_expiry.py to collect snapshots")
        logger.info("2. Waiting for markets to resolve")
        logger.info("3. Running label_snapshots.py to backfill outcomes")
        return

    # Train
    if args.bucket == 'all':
        validator.train_all_buckets(
            n_folds=args.n_folds,
            val_period_days=args.val_period_days,
            gap_days=args.gap_days
        )
    else:
        validator.train_with_forward_validation(
            bucket=args.bucket,
            n_folds=args.n_folds,
            val_period_days=args.val_period_days,
            gap_days=args.gap_days
        )

    logger.info("\n✅ Training complete!")


if __name__ == '__main__':
    main()
