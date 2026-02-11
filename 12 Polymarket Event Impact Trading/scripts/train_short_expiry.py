#!/usr/bin/env python3
"""
Train short-expiry models using existing historical labeling pipeline.

Reuses:
- historical_labeling_pipeline.py for data extraction
- Existing databases (alchemy_trades.db, polymarket_history.db)
- Existing feature extraction infrastructure

Adapts for:
- Short-expiry specific features (0-7 days)
- Bucket-specific models (ultra_short, short, medium)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pickle
import json
import logging
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, accuracy_score, f1_score, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV

# Import existing infrastructure
from src.utils.historical_labeling_pipeline import (
    connect_db, get_trades_with_markets, get_news_in_window,
    CRYPTO_KEYWORDS
)
from src.features.short_expiry_features import ShortExpiryFeatureExtractor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ShortExpiryTrainer:
    """Train models for short-expiry trading using historical data."""

    def __init__(self):
        self.data_dir = Path("data")
        self.models_dir = self.data_dir / "models"
        self.models_dir.mkdir(exist_ok=True)

        self.feature_extractor = ShortExpiryFeatureExtractor()

        # Use existing databases
        self.alchemy_db = self.data_dir / "alchemy_trades.db"
        self.history_db = self.data_dir / "polymarket_history.db"
        self.gdelt_db = self.data_dir / "gdelt_news.db"

    def get_short_expiry_markets(self):
        """Get resolved markets with short expiry periods."""
        logger.info("Loading short-expiry markets...")

        with sqlite3.connect(self.history_db) as conn:
            query = """
            SELECT *
            FROM resolved_markets
            WHERE resolved_outcome IS NOT NULL
            AND end_date IS NOT NULL
            AND created_at IS NOT NULL
            """
            markets = pd.read_sql_query(query, conn)

        markets['end_date'] = pd.to_datetime(markets['end_date'], format='ISO8601', errors='coerce')
        markets['created_at'] = pd.to_datetime(markets['created_at'], format='ISO8601', errors='coerce')

        # Calculate duration
        markets['duration_hours'] = (markets['end_date'] - markets['created_at']).dt.total_seconds() / 3600

        # Filter for short-expiry (0-168 hours = 0-7 days)
        short_markets = markets[markets['duration_hours'] <= 168].copy()

        # Classify into buckets
        def classify_bucket(hours):
            if hours <= 24:
                return 'ultra_short'
            elif hours <= 72:
                return 'short'
            else:
                return 'medium'

        short_markets['bucket'] = short_markets['duration_hours'].apply(classify_bucket)

        logger.info(f"Found {len(short_markets)} short-expiry markets")
        logger.info(f"Bucket distribution:\n{short_markets['bucket'].value_counts()}")

        return short_markets

    def extract_features_from_trades(self, condition_id, bucket, timestamp):
        """Extract features for a market at a given timestamp."""
        # Get trades from Alchemy database
        # Convert timestamp to string for SQLite compatibility
        timestamp_str = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)

        with sqlite3.connect(self.alchemy_db) as conn:
            query = """
            SELECT block_timestamp, price, maker_amount_filled, taker_amount_filled
            FROM on_chain_trades
            WHERE condition_id = ?
            AND block_timestamp <= ?
            ORDER BY block_timestamp
            """
            trades = pd.read_sql_query(query, conn, params=(condition_id, timestamp_str))

        if len(trades) < 5:
            if len(trades) > 0:
                logger.debug(f"Market {condition_id}: Only {len(trades)} trades (need ≥5)")
            return None

        trades['block_timestamp'] = pd.to_datetime(trades['block_timestamp'])

        # Build price history
        price_history = pd.DataFrame({
            'price': trades['price'].values,
            'timestamp': trades['block_timestamp'].values
        })

        # Build market dict
        last_price = float(trades.iloc[-1]['price'])

        market_dict = {
            'conditionId': condition_id,
            'question': '',  # Not needed for features
            'endDate': (timestamp + timedelta(hours=24)).isoformat(),
            'volume24hr': float(trades['maker_amount_filled'].sum() + trades['taker_amount_filled'].sum()),
            'liquidity': 1000,  # Placeholder
            'lastTradePrice': last_price,
            'bestBid': last_price * 0.98,
            'bestAsk': last_price * 1.02,
            'active': True
        }

        # Extract features
        try:
            features = self.feature_extractor.extract_all_features(
                market_dict,
                bucket,
                price_history=price_history
            )
            return features
        except Exception as e:
            logger.debug(f"Error extracting features: {e}")
            return None

    def build_training_data(self, markets_df, samples_per_market=5):
        """Build training dataset from historical markets."""
        logger.info("Building training dataset...")

        training_samples = []
        skipped_reasons = {'no_trades': 0, 'feature_extraction_failed': 0, 'invalid_outcome': 0}

        for idx, market in markets_df.iterrows():
            if idx % 50 == 0:
                logger.info(f"Processing {idx}/{len(markets_df)}")

            # Sample multiple points before expiry
            end_date = market['end_date']
            duration_hours = market['duration_hours']

            # Sample at different points (25%, 50%, 75%, 90%, 100% of duration)
            sample_points = [0.25, 0.5, 0.75, 0.9, 1.0]

            for pct in sample_points:
                hours_from_start = duration_hours * pct
                observation_time = market['created_at'] + timedelta(hours=hours_from_start)

                if observation_time >= end_date:
                    continue

                # Extract features at this point
                features = self.extract_features_from_trades(
                    market['condition_id'],
                    market['bucket'],
                    observation_time
                )

                if features is None:
                    skipped_reasons['no_trades'] += 1
                    continue

                # Add label (outcome)
                outcome = market['resolved_outcome']
                if outcome in ['Yes', 'YES', 'yes']:
                    label = 1
                elif outcome in ['No', 'NO', 'no']:
                    label = 0
                else:
                    skipped_reasons['invalid_outcome'] += 1
                    continue

                features['label'] = label
                features['bucket'] = market['bucket']
                features['market_id'] = market['condition_id']

                training_samples.append(features)

        logger.info(f"\nSkipped samples breakdown:")
        logger.info(f"  No trades (< 5): {skipped_reasons['no_trades']}")
        logger.info(f"  Feature extraction failed: {skipped_reasons['feature_extraction_failed']}")
        logger.info(f"  Invalid outcome: {skipped_reasons['invalid_outcome']}")

        if not training_samples:
            logger.error("No training samples generated!")
            return None

        training_df = pd.concat(training_samples, ignore_index=True)

        logger.info(f"Generated {len(training_df)} samples")
        logger.info(f"Samples per bucket:\n{training_df['bucket'].value_counts()}")

        return training_df

    def train_model(self, training_df, bucket):
        """Train model for a specific bucket."""
        logger.info(f"\nTraining {bucket} model...")

        bucket_data = training_df[training_df['bucket'] == bucket].copy()

        if len(bucket_data) < 50:
            logger.warning(f"Insufficient data for {bucket}: {len(bucket_data)} samples")
            return None

        # Prepare features
        feature_cols = [col for col in bucket_data.columns
                       if col not in ['label', 'bucket', 'market_id']]

        X = bucket_data[feature_cols].fillna(0)
        y = bucket_data['label']

        logger.info(f"Features: {len(feature_cols)}, Samples: {len(X)}")
        logger.info(f"Class distribution: {y.value_counts().to_dict()}")

        # Train with time series cross-validation
        tscv = TimeSeriesSplit(n_splits=min(5, len(X) // 20))

        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42
        )

        # Cross-validation
        cv_scores = []
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)

            acc = accuracy_score(y_val, y_pred)
            f1 = f1_score(y_val, y_pred, zero_division=0)

            cv_scores.append({'accuracy': acc, 'f1': f1})

        avg_acc = np.mean([s['accuracy'] for s in cv_scores])
        avg_f1 = np.mean([s['f1'] for s in cv_scores])

        logger.info(f"CV Results: Accuracy={avg_acc:.3f}, F1={avg_f1:.3f}")

        # Train final model
        model.fit(X, y)

        # Calibrate
        calibrated = CalibratedClassifierCV(model, method='isotonic', cv=3)
        calibrated.fit(X, y)

        # Save
        model_data = {
            'model': calibrated,
            'feature_cols': feature_cols,
            'bucket': bucket,
            'metrics': {'accuracy': avg_acc, 'f1': avg_f1},
            'trained_at': datetime.now().isoformat(),
            'samples': len(X)
        }

        model_path = self.models_dir / f"short_expiry_{bucket}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"Model saved: {model_path}")

        return model_data

    def run(self):
        """Run complete training pipeline."""
        logger.info("="*60)
        logger.info("SHORT-EXPIRY MODEL TRAINING")
        logger.info("="*60)

        # Load markets
        markets = self.get_short_expiry_markets()

        if markets is None or len(markets) == 0:
            logger.error("No markets found!")
            return

        # Build training data
        training_df = self.build_training_data(markets)

        if training_df is None:
            return

        # Save training data
        training_df.to_csv(self.data_dir / "short_expiry_training.csv", index=False)
        logger.info("Training data saved to data/short_expiry_training.csv")

        # Train models
        models = {}
        for bucket in ['ultra_short', 'short', 'medium']:
            model = self.train_model(training_df, bucket)
            if model:
                models[bucket] = model

        # Summary
        logger.info("\n" + "="*60)
        logger.info("TRAINING COMPLETE")
        logger.info("="*60)

        for bucket, model in models.items():
            logger.info(f"{bucket}: Acc={model['metrics']['accuracy']:.3f}, "
                       f"F1={model['metrics']['f1']:.3f}, Samples={model['samples']}")

        logger.info("\nModels ready for use!")


if __name__ == '__main__':
    trainer = ShortExpiryTrainer()
    trainer.run()
