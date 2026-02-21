#!/usr/bin/env python3
"""
Test Forward-Validation Framework

Verifies that the walk-forward validation implementation works correctly
with synthetic data before using real market snapshots.

Run: python3 tests/test_forward_validation.py
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import sqlite3
import json

from src.ml.snapshot_collector import MarketSnapshotCollector
from src.ml.training_engine import ModelTrainer, ModelConfig
from src.utils.walk_forward_validator import WalkForwardValidator


def create_synthetic_snapshots(db_path: str, n_samples: int = 500):
    """Create synthetic market snapshots for testing."""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Initialize schema
    collector = MarketSnapshotCollector(db_path=db_path)

    # Generate synthetic data with temporal pattern
    np.random.seed(42)
    base_date = datetime(2024, 1, 1)

    for i in range(n_samples):
        # Create market snapshot (spread across 60 days for temporal validation)
        snapshot_time = base_date + timedelta(hours=i * 3)  # 3-hour intervals = 62.5 days
        market_id = f"market_{i % 100}"  # Reuse markets

        # Synthetic features
        feature1 = np.random.randn() + (i / n_samples)  # Temporal trend
        feature2 = np.random.randn()
        spread = abs(np.random.randn() * 0.05)
        volume_24h = abs(np.random.randn() * 10000)

        features = {
            'market_probability': float(0.5 + np.random.randn() * 0.1),
            'spread_pct': float(spread),
            'volume_24h': float(volume_24h),
            'hours_to_expiry': float(48 - (i % 48)),
            'feature1': float(feature1),
            'feature2': float(feature2)
        }

        # Synthetic prediction
        yes_price = 0.5 + np.random.randn() * 0.1
        no_price = 1.0 - yes_price

        # Label based on features (to create learnable pattern)
        outcome = 'YES' if feature1 + feature2 > 0 else 'NO'

        # Insert snapshot
        cursor.execute("""
            INSERT INTO market_snapshots (
                market_id, bot_type, snapshot_time,
                features_json, model_prob, confidence, edge, predicted_outcome,
                yes_price, no_price, spread, volume_24h, liquidity,
                outcome, resolution_price, labeled,
                question, expiry_date, days_to_expiry
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            market_id,
            'short_expiry',
            snapshot_time.isoformat(),
            json.dumps(features),  # Properly formatted JSON
            0.5,  # model_prob
            0.7,  # confidence
            0.05,  # edge
            'YES',  # predicted_outcome
            yes_price,
            no_price,
            spread,
            volume_24h,
            1000.0,  # liquidity
            outcome,
            1.0 if outcome == 'YES' else 0.0,
            1,  # labeled
            f"Market {i}",
            (snapshot_time + timedelta(days=2)).isoformat(),
            2.0
        ))

    conn.commit()
    conn.close()

    print(f"✅ Created {n_samples} synthetic snapshots in {db_path}")


def test_forward_validation_with_synthetic_data():
    """Test walk-forward validation with synthetic data."""

    print("\n" + "="*70)
    print("TESTING FORWARD-VALIDATION FRAMEWORK")
    print("="*70)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Create synthetic snapshots
        print("\n1. Creating synthetic snapshots...")
        create_synthetic_snapshots(db_path, n_samples=500)

        # Load data
        print("\n2. Loading data from snapshot collector...")
        collector = MarketSnapshotCollector(db_path=db_path)
        df = collector.get_training_data(bot_type='short_expiry', labeled_only=True)

        assert len(df) > 0, "No data loaded!"
        print(f"   Loaded {len(df)} snapshots")

        # Prepare features
        print("\n3. Preparing features...")
        df['entry_date'] = pd.to_datetime(df['snapshot_time'])
        df['label'] = (df['outcome'] == 'YES').astype(int)

        # Get feature columns (exclude metadata)
        exclude_cols = [
            'id', 'market_id', 'condition_id', 'token_id', 'question', 'asset',
            'bot_type', 'snapshot_time', 'expiry_date', 'outcome',
            'resolution_price', 'resolution_time', 'labeled', 'position_opened',
            'rejection_reason', 'model_prob', 'confidence', 'edge', 'predicted_outcome',
            'yes_price', 'no_price', 'spread', 'label', 'market_type', 'position_id',
            'days_to_expiry', 'strike_price'
        ]

        feature_cols = [col for col in df.columns if col not in exclude_cols]

        # Create feature matrix with entry_date
        X = df[feature_cols].copy()
        X['entry_date'] = df['entry_date']
        y = df['label'].copy()

        # Fill NaN in numeric columns
        for col in X.select_dtypes(include=[np.number]).columns:
            X[col] = X[col].fillna(0)

        print(f"   Features: {len(feature_cols) - 1} (+ entry_date)")
        print(f"   Samples: {len(X)}")
        print(f"   Label distribution: {y.value_counts().to_dict()}")

        # Create validator
        print("\n4. Creating walk-forward validator...")
        # Data spans ~21 days (500 hours), so use smaller windows
        validator = WalkForwardValidator(
            n_folds=2,
            val_period_days=5,
            gap_days=0,
            min_train_samples=50,
            min_val_samples=20
        )

        # Create model trainer
        print("\n5. Creating model trainer...")
        config = ModelConfig(
            model_type='gradient_boosting',
            n_estimators=50,
            learning_rate=0.1,
            max_depth=3,
            apply_calibration=True,
            random_state=42,
            verbose=False
        )
        trainer = ModelTrainer(config=config)

        # Run validation
        print("\n6. Running walk-forward validation...")
        report = trainer.train_with_cv(
            X=X,
            y=y,
            cv_validator=validator,
            date_column='entry_date'
        )

        # Verify results
        print("\n7. Verifying results...")
        assert report.n_folds >= 1, "No folds generated!"
        assert 0 <= report.mean_roc_auc <= 1, "Invalid ROC-AUC!"
        assert len(report.fold_metrics) == report.n_folds, "Fold metrics mismatch!"

        print(f"\n✅ VALIDATION SUCCESSFUL!")
        print(f"   Folds: {report.n_folds}")
        print(f"   Mean ROC-AUC: {report.mean_roc_auc:.3f} ± {report.std_roc_auc:.3f}")
        print(f"   Mean Accuracy: {report.mean_accuracy:.3f} ± {report.std_accuracy:.3f}")
        print(f"   Mean F1: {report.mean_f1:.3f} ± {report.std_f1:.3f}")
        print(f"   AUC Degradation: {report.auc_degradation:+.3f}")

        # Check if model learned something
        if report.mean_roc_auc > 0.55:
            print(f"\n🎉 Model learned from synthetic data! (AUC > 0.55)")
        else:
            print(f"\n⚠️  Model did not learn much (AUC ≈ random)")

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"\nCleaned up temporary database: {db_path}")


if __name__ == '__main__':
    test_forward_validation_with_synthetic_data()
