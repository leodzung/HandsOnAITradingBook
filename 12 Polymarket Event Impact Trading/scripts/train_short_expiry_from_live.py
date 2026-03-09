#!/usr/bin/env python3
"""
Train short-expiry models from LIVE collected data.

✅ USE THIS SCRIPT when you have 100+ closed positions from trader_short_expiry.py

This script:
1. Extracts closed positions from positions_short_expiry.db
2. Parses features_json from each position
3. Uses actual entry/exit outcomes as labels
4. Trains bucket-specific models (ultra_short, short, medium)
5. Saves models to data/models/short_expiry_*.pkl

Requirements:
  - positions_short_expiry.db with 100+ closed positions
  - Features must be stored in features_json column

Check readiness:
  python3 scripts/check_data_status.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sqlite3
import pandas as pd
import numpy as np
import json
import pickle
import logging
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.calibration import CalibratedClassifierCV

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LiveDataTrainer:
    """Train models from live collected position data."""

    def __init__(self):
        self.data_dir = Path("data")
        self.models_dir = self.data_dir / "models"
        self.models_dir.mkdir(exist_ok=True)

        self.positions_db = self.data_dir / "positions_short_expiry.db"
        self.snapshots_db = self.data_dir / "market_snapshots.db"

    def load_closed_positions(self):
        """Load closed positions from database."""
        logger.info("Loading closed positions...")

        if not self.positions_db.exists():
            logger.error(f"Database not found: {self.positions_db}")
            return None

        conn = sqlite3.connect(self.positions_db)

        # Load all closed positions with features
        # Features are stored inside the 'metadata' JSON column as 'features_json' key
        query = """
            SELECT
                market_id,
                outcome,
                entry_price,
                exit_price,
                bucket,
                hours_to_expiry_at_entry,
                edge,
                confidence,
                signal_reason,
                json_extract(metadata, '$.features_json') AS features_json,
                pnl
            FROM positions
            WHERE status != 'open'
            AND exit_price IS NOT NULL
            AND metadata IS NOT NULL
            AND json_extract(metadata, '$.features_json') IS NOT NULL
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        logger.info(f"Loaded {len(df)} closed positions")

        if len(df) < 50:
            logger.warning(f"Only {len(df)} closed positions. Recommended: 100+ per bucket")

        return df

    def load_labeled_snapshots(self):
        """
        Load labeled snapshots from market_snapshots.db as additional training data.

        This is the primary training source once Phase 1/2 labeling runs:
        snapshots cover ALL evaluated markets (not just traded ones), eliminating
        the selection bias present in positions-only training.

        Returns:
            DataFrame with same columns as positions data, or None if unavailable.
        """
        logger.info("Loading labeled snapshots from market_snapshots.db...")

        if not self.snapshots_db.exists():
            logger.info(f"Snapshots DB not found: {self.snapshots_db}")
            return None

        conn = sqlite3.connect(self.snapshots_db)
        query = """
            SELECT
                market_id,
                outcome,
                yes_price AS entry_price,
                NULL AS exit_price,
                days_to_expiry,
                features_json,
                NULL AS pnl
            FROM market_snapshots
            WHERE labeled = 1
              AND bot_type = 'short_expiry'
              AND outcome IN ('YES', 'NO')
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            logger.info("No labeled snapshots found in market_snapshots.db")
            return None

        logger.info(f"Loaded {len(df)} labeled snapshots")

        # Assign bucket from days_to_expiry
        def _days_to_bucket(d):
            try:
                d = float(d)
            except (TypeError, ValueError):
                return "short"
            if d < 1:
                return "ultra_short"
            elif d <= 3:
                return "short"
            else:
                return "medium"

        df["bucket"] = df["days_to_expiry"].apply(_days_to_bucket)

        # Build a flat features + label df that matches prepare_training_data output
        training_samples = []
        for _, row in df.iterrows():
            try:
                features = json.loads(row["features_json"]) if isinstance(row["features_json"], str) else row["features_json"]
                if not isinstance(features, dict):
                    continue
            except Exception:
                continue

            # Spread-adjusted label: outcome YES → did price reach 1.0 (win)?
            spread_cost = max(self._scalar(features.get("spread_pct", 2.0), 2.0) / 100.0, 0.01)

            # For snapshots we use the resolution outcome directly as ground truth.
            # A YES resolution means the YES token paid out 1.0.
            # Label = 1 if the bot would have profited by holding to resolution
            # (assuming entry at yes_price, exit at 1.0 for YES / 0.0 for NO).
            entry_price = self._scalar(row["entry_price"], 0.5) if row["entry_price"] else 0.5
            if row["outcome"] == "YES":
                price_change = (1.0 - entry_price) / entry_price if entry_price > 0 else 0.0
                label = 1 if price_change > spread_cost else 0
            else:  # NO outcome → YES token worth 0
                price_change = (entry_price - 0.0) / entry_price if entry_price > 0 else 0.0
                label = 0  # Holding YES token to NO resolution is a loss

            flat_features = {}
            for key, value in features.items():
                if isinstance(value, (int, float)):
                    flat_features[key] = float(value)
                elif isinstance(value, dict) and len(value) == 1:
                    try:
                        flat_features[key] = float(list(value.values())[0])
                    except Exception:
                        continue
                else:
                    try:
                        flat_features[key] = float(value)
                    except Exception:
                        continue

            flat_features["label"] = label
            flat_features["bucket"] = row["bucket"]
            flat_features["market_id"] = row["market_id"]
            flat_features["actual_pnl"] = 0.0  # unknown for snapshots
            training_samples.append(flat_features)

        if not training_samples:
            logger.warning("No training samples extracted from snapshots")
            return None

        result = pd.DataFrame(training_samples)
        logger.info(f"Created {len(result)} snapshot training samples")
        logger.info(f"Snapshot samples per bucket:\n{result['bucket'].value_counts()}")
        return result

    @staticmethod
    def _scalar(value, default=0.0):
        """Extract a float scalar from a value that may be a pandas Series dict {"0": v}."""
        if isinstance(value, dict):
            try:
                return float(list(value.values())[0])
            except Exception:
                return default
        try:
            return float(value)
        except Exception:
            return default

    def prepare_training_data(self, positions_df):
        """Extract features and create labels from positions."""
        logger.info("Preparing training data...")

        training_samples = []

        for idx, row in positions_df.iterrows():
            try:
                # Parse features JSON
                features = json.loads(row['features_json']) if isinstance(row['features_json'], str) else row['features_json']

                # Spread-adjusted label: entry=ASK, exit=BID, so raw P&L is always
                # reduced by the bid-ask spread. A "win" must recover that cost.
                # Use spread_pct from features if available, else default 2% (Polymarket typical).
                spread_cost = max(self._scalar(features.get('spread_pct', 2.0), 2.0) / 100.0, 0.01)

                entry = self._scalar(row['entry_price'], 0.0)
                exit_ = self._scalar(row['exit_price'], 0.0)

                if row['outcome'] == 'YES':
                    price_change = (exit_ - entry) / entry if entry > 0 else 0.0
                    label = 1 if price_change > spread_cost else 0
                else:  # NO — win when YES price falls (entry > exit for YES token)
                    price_change = (entry - exit_) / entry if entry > 0 else 0.0
                    label = 1 if price_change > spread_cost else 0

                # Flatten features (handle nested dicts/series)
                flat_features = {}
                for key, value in features.items():
                    if isinstance(value, (pd.Series, pd.DataFrame)):
                        # Take first value if Series/DataFrame
                        flat_features[key] = float(value.iloc[0]) if len(value) > 0 else 0.0
                    elif isinstance(value, (int, float)):
                        flat_features[key] = float(value)
                    elif isinstance(value, dict):
                        # Handle pandas Series serialized as {"0": value}
                        if len(value) == 1:
                            try:
                                flat_features[key] = float(list(value.values())[0])
                            except:
                                continue
                        else:
                            continue
                    else:
                        # Try to convert to float
                        try:
                            flat_features[key] = float(value)
                        except:
                            continue

                # Add metadata
                flat_features['label'] = label
                flat_features['bucket'] = row['bucket']
                flat_features['market_id'] = row['market_id']
                flat_features['actual_pnl'] = row['pnl'] if pd.notna(row['pnl']) else 0.0

                training_samples.append(flat_features)

            except Exception as e:
                logger.debug(f"Error processing position {idx}: {e}")
                continue

        if not training_samples:
            logger.error("No training samples created!")
            return None

        training_df = pd.DataFrame(training_samples)

        logger.info(f"Created {len(training_df)} training samples")
        logger.info(f"Samples per bucket:\n{training_df['bucket'].value_counts()}")
        logger.info(f"Label distribution:\n{training_df['label'].value_counts()}")

        return training_df

    def train_model(self, training_df, bucket):
        """Train model for a specific bucket."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Training {bucket.upper()} model")
        logger.info(f"{'='*60}")

        bucket_data = training_df[training_df['bucket'] == bucket].copy()

        if len(bucket_data) < 30:
            logger.warning(f"Insufficient data for {bucket}: {len(bucket_data)} samples (need 30+)")
            return None

        # Prepare features
        exclude_cols = ['label', 'bucket', 'market_id', 'actual_pnl']
        feature_cols = [col for col in bucket_data.columns if col not in exclude_cols]

        X = bucket_data[feature_cols].fillna(0)
        y = bucket_data['label']

        logger.info(f"Features: {len(feature_cols)}")
        logger.info(f"Samples: {len(X)}")
        logger.info(f"Label distribution: {y.value_counts().to_dict()}")

        # Train with time series cross-validation
        n_splits = min(5, max(2, len(X) // 20))
        tscv = TimeSeriesSplit(n_splits=n_splits)

        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42
        )

        # Cross-validation
        cv_scores = []
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)

            acc = accuracy_score(y_val, y_pred)
            f1 = f1_score(y_val, y_pred, zero_division=0)

            cv_scores.append({'fold': fold, 'accuracy': acc, 'f1': f1})
            logger.info(f"  Fold {fold}: Acc={acc:.3f}, F1={f1:.3f}")

        avg_acc = np.mean([s['accuracy'] for s in cv_scores])
        avg_f1 = np.mean([s['f1'] for s in cv_scores])

        logger.info(f"\nCross-Validation Results:")
        logger.info(f"  Average Accuracy: {avg_acc:.3f}")
        logger.info(f"  Average F1: {avg_f1:.3f}")

        # Train final model on all data
        model.fit(X, y)

        # Calibrate probabilities
        calibrated = CalibratedClassifierCV(model, method='isotonic', cv=min(3, n_splits))
        calibrated.fit(X, y)

        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        logger.info(f"\nTop 10 Features:")
        for idx, row in feature_importance.head(10).iterrows():
            logger.info(f"  {row['feature']:30s}: {row['importance']:.4f}")

        # Save model
        model_data = {
            'model': calibrated,
            'feature_cols': feature_cols,
            'bucket': bucket,
            'metrics': {
                'accuracy': avg_acc,
                'f1': avg_f1,
                'cv_scores': cv_scores
            },
            'feature_importance': feature_importance.to_dict('records'),
            'trained_at': datetime.now().isoformat(),
            'samples': len(X),
            'training_data_source': 'live_positions+snapshots'
        }

        model_path = self.models_dir / f"short_expiry_{bucket}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"\n✅ Model saved: {model_path}")

        return model_data

    def run(self):
        """Run complete training pipeline."""
        logger.info("="*70)
        logger.info("SHORT-EXPIRY MODEL TRAINING (Live Data)")
        logger.info("="*70)

        # Load positions
        positions_df = self.load_closed_positions()
        if positions_df is None or len(positions_df) == 0:
            logger.error("No closed positions found!")
            logger.info("\nRun this script after collecting 100+ closed positions from trader_short_expiry.py")
            logger.info("Check status: python3 scripts/check_data_status.py")
            return

        # Prepare training data from positions
        training_df = self.prepare_training_data(positions_df)
        if training_df is None:
            return

        # Merge with snapshot-based training data (larger, unbiased dataset)
        snapshot_df = self.load_labeled_snapshots()
        if snapshot_df is not None and not snapshot_df.empty:
            logger.info(f"Merging {len(training_df)} position samples + {len(snapshot_df)} snapshot samples")
            training_df = pd.concat([training_df, snapshot_df], ignore_index=True)
            # Fill NaN columns introduced by schema differences between datasets
            training_df = training_df.fillna(0)
            logger.info(f"Combined training set: {len(training_df)} total samples")
            logger.info(f"Combined samples per bucket:\n{training_df['bucket'].value_counts()}")

        # Save training data
        training_csv = self.data_dir / "short_expiry_training_live.csv"
        training_df.to_csv(training_csv, index=False)
        logger.info(f"\nTraining data saved: {training_csv}")

        # Train models per bucket
        models = {}
        for bucket in ['ultra_short', 'short', 'medium']:
            if bucket in training_df['bucket'].values:
                model = self.train_model(training_df, bucket)
                if model:
                    models[bucket] = model

        # Summary
        logger.info("\n" + "="*70)
        logger.info("TRAINING COMPLETE")
        logger.info("="*70)

        if models:
            for bucket, model in models.items():
                logger.info(f"{bucket:12s}: Acc={model['metrics']['accuracy']:.3f}, "
                          f"F1={model['metrics']['f1']:.3f}, Samples={model['samples']}")
            logger.info("\n✅ Models ready for integration into trader!")
            logger.info("\nNext steps:")
            logger.info("1. Review model metrics above")
            logger.info("2. Integrate models into src/bots/trader_short_expiry.py")
            logger.info("3. Test in paper trading mode before going live")
        else:
            logger.warning("\n⚠️  No models trained - insufficient data per bucket")
            logger.info("Continue running trader_short_expiry.py to collect more data")


if __name__ == '__main__':
    trainer = LiveDataTrainer()
    trainer.run()
