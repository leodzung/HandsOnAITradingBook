#!/usr/bin/env python3
"""
Train short-expiry models from historical data.

Uses:
- Resolved markets from polymarket_history.db
- On-chain trades from alchemy_trades.db
- News events from gdelt_news.db

Creates trained models for each bucket (ultra_short, short, medium).
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pickle
import json
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV
import logging

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.features.short_expiry_features import ShortExpiryFeatureExtractor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ShortExpiryTrainingPipeline:
    """Pipeline to train models from historical data."""

    def __init__(self):
        self.data_dir = Path("data")
        self.models_dir = Path("data/models")
        self.models_dir.mkdir(exist_ok=True)

        self.feature_extractor = ShortExpiryFeatureExtractor()

        # Database connections
        self.history_db = self.data_dir / "polymarket_history.db"
        self.trades_db = self.data_dir / "alchemy_trades.db"
        self.news_db = self.data_dir / "gdelt_news.db"

    def extract_short_expiry_markets(self):
        """Extract markets that had 0-7 day expiry periods."""
        logger.info("Extracting short-expiry markets from history...")

        with sqlite3.connect(self.history_db) as conn:
            query = """
            SELECT
                condition_id,
                question,
                category,
                end_date,
                resolved_outcome,
                outcome_prices,
                volume,
                liquidity,
                created_at,
                closed_at,
                asset,
                strike_price
            FROM resolved_markets
            WHERE resolved_outcome IS NOT NULL
            """

            markets = pd.read_sql_query(query, conn)

        logger.info(f"Loaded {len(markets)} resolved markets")

        # Calculate time to expiry at various points
        markets['end_date'] = pd.to_datetime(markets['end_date'], format='ISO8601', errors='coerce')
        markets['created_at'] = pd.to_datetime(markets['created_at'], format='ISO8601', errors='coerce')
        markets['closed_at'] = pd.to_datetime(markets['closed_at'], format='ISO8601', errors='coerce')

        # Calculate total market duration
        markets['duration_days'] = (markets['end_date'] - markets['created_at']).dt.total_seconds() / 86400

        # Filter for short-expiry markets (0-30 days)
        short_expiry = markets[markets['duration_days'] <= 30].copy()

        logger.info(f"Found {len(short_expiry)} markets with ≤30 day duration")

        # Classify into buckets based on duration
        def classify_bucket(duration_days):
            if duration_days <= 1:
                return 'ultra_short'
            elif duration_days <= 3:
                return 'short'
            elif duration_days <= 7:
                return 'medium'
            else:
                return 'long'  # Will filter these out

        short_expiry['bucket'] = short_expiry['duration_days'].apply(classify_bucket)

        # Filter to only our 3 buckets
        short_expiry = short_expiry[short_expiry['bucket'].isin(['ultra_short', 'short', 'medium'])]

        logger.info(f"Bucket distribution:")
        logger.info(short_expiry['bucket'].value_counts())

        return short_expiry

    def get_trades_for_market(self, condition_id, timeframe='last_24h'):
        """Get trades for a specific market."""
        with sqlite3.connect(self.trades_db) as conn:
            query = """
            SELECT
                block_timestamp,
                maker_amount_filled as maker_amount,
                taker_amount_filled as taker_amount,
                price
            FROM on_chain_trades
            WHERE condition_id = ?
            ORDER BY block_timestamp ASC
            """

            trades = pd.read_sql_query(query, conn, params=(condition_id,))

        if len(trades) == 0:
            return None

        trades['block_timestamp'] = pd.to_datetime(trades['block_timestamp'])

        return trades

    def build_training_dataset(self, markets_df):
        """Build training dataset with features and labels."""
        logger.info("Building training dataset...")

        training_data = []

        for idx, market in markets_df.iterrows():
            if idx % 100 == 0:
                logger.info(f"Processing market {idx + 1}/{len(markets_df)}")

            # Get trades for this market
            trades = self.get_trades_for_market(market['condition_id'])

            if trades is None or len(trades) < 10:
                continue  # Skip markets with insufficient data

            # Simulate feature extraction at different time points before expiry
            # Extract features at: 24h, 12h, 6h, 3h, 1h before expiry
            end_date = market['end_date']

            for hours_before in [24, 12, 6, 3, 1]:
                observation_time = end_date - timedelta(hours=hours_before)

                # Get trades up to this point
                historical_trades = trades[trades['block_timestamp'] <= observation_time]

                if len(historical_trades) < 5:
                    continue

                # Build market dict for feature extraction
                market_dict = {
                    'conditionId': market['condition_id'],
                    'question': market['question'],
                    'endDate': market['end_date'].isoformat(),
                    'volume24hr': float(market['volume']) if pd.notna(market['volume']) else 0,
                    'liquidity': float(market['liquidity']) if pd.notna(market['liquidity']) else 0,
                    'lastTradePrice': float(historical_trades.iloc[-1]['price']) if len(historical_trades) > 0 else 0.5,
                    'bestBid': float(historical_trades.iloc[-1]['price']) * 0.98 if len(historical_trades) > 0 else 0.48,
                    'bestAsk': float(historical_trades.iloc[-1]['price']) * 1.02 if len(historical_trades) > 0 else 0.52,
                    'active': True
                }

                # Create price history
                if len(historical_trades) > 1:
                    price_history = pd.DataFrame({
                        'price': historical_trades['price'].values,
                        'timestamp': historical_trades['block_timestamp'].values
                    })
                else:
                    price_history = None

                # Extract features
                try:
                    features = self.feature_extractor.extract_all_features(
                        market_dict,
                        market['bucket'],
                        price_history=price_history
                    )

                    # Add label (outcome)
                    outcome = market['resolved_outcome']
                    if outcome == 'Yes' or outcome == 'YES':
                        label = 1  # Price went up
                    elif outcome == 'No' or outcome == 'NO':
                        label = 0  # Price went down
                    else:
                        continue  # Skip unclear outcomes

                    # Add metadata
                    features['label'] = label
                    features['bucket'] = market['bucket']
                    features['market_id'] = market['condition_id']
                    features['hours_before_expiry'] = hours_before

                    training_data.append(features)

                except Exception as e:
                    logger.debug(f"Error extracting features for {market['condition_id']}: {e}")
                    continue

        if not training_data:
            logger.error("No training data generated!")
            return None

        # Combine all feature dataframes
        training_df = pd.concat(training_data, ignore_index=True)

        logger.info(f"Generated {len(training_df)} training samples")
        logger.info(f"Samples per bucket:")
        logger.info(training_df['bucket'].value_counts())

        return training_df

    def train_bucket_model(self, training_df, bucket):
        """Train a model for a specific bucket."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Training model for {bucket} bucket")
        logger.info(f"{'='*60}")

        # Filter to bucket
        bucket_data = training_df[training_df['bucket'] == bucket].copy()

        if len(bucket_data) < 100:
            logger.warning(f"Insufficient data for {bucket}: {len(bucket_data)} samples")
            return None

        logger.info(f"Training samples: {len(bucket_data)}")

        # Separate features and labels
        feature_cols = [col for col in bucket_data.columns
                       if col not in ['label', 'bucket', 'market_id', 'hours_before_expiry']]

        X = bucket_data[feature_cols].fillna(0)
        y = bucket_data['label']

        logger.info(f"Features: {len(feature_cols)}")
        logger.info(f"Class distribution: {y.value_counts().to_dict()}")

        # Time series split for validation
        tscv = TimeSeriesSplit(n_splits=5)

        # Train model
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
            verbose=0
        )

        # Cross-validation
        cv_scores = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model.fit(X_train, y_train)

            y_pred = model.predict(X_val)
            y_pred_proba = model.predict_proba(X_val)[:, 1]

            # Calculate metrics
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

            acc = accuracy_score(y_val, y_pred)
            prec = precision_score(y_val, y_pred, zero_division=0)
            rec = recall_score(y_val, y_pred, zero_division=0)
            f1 = f1_score(y_val, y_pred, zero_division=0)

            try:
                auc = roc_auc_score(y_val, y_pred_proba)
            except:
                auc = 0.0

            cv_scores.append({
                'fold': fold,
                'accuracy': acc,
                'precision': prec,
                'recall': rec,
                'f1': f1,
                'auc': auc
            })

            logger.info(f"Fold {fold + 1}: Acc={acc:.3f}, Prec={prec:.3f}, Rec={rec:.3f}, F1={f1:.3f}, AUC={auc:.3f}")

        # Calculate average metrics
        avg_metrics = {
            'accuracy': np.mean([s['accuracy'] for s in cv_scores]),
            'precision': np.mean([s['precision'] for s in cv_scores]),
            'recall': np.mean([s['recall'] for s in cv_scores]),
            'f1': np.mean([s['f1'] for s in cv_scores]),
            'auc': np.mean([s['auc'] for s in cv_scores])
        }

        logger.info(f"\nAverage CV Metrics:")
        for metric, value in avg_metrics.items():
            logger.info(f"  {metric}: {value:.3f}")

        # Train final model on all data
        logger.info("\nTraining final model on all data...")
        model.fit(X, y)

        # Calibrate probabilities
        logger.info("Calibrating probabilities...")
        calibrated_model = CalibratedClassifierCV(model, method='isotonic', cv=3)
        calibrated_model.fit(X, y)

        # Feature importance
        logger.info("\nTop 10 Features:")
        feature_importance = pd.DataFrame({
            'feature': feature_cols,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)

        for idx, row in feature_importance.head(10).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        # Save model
        model_data = {
            'model': calibrated_model,
            'feature_cols': feature_cols,
            'bucket': bucket,
            'cv_metrics': avg_metrics,
            'feature_importance': feature_importance.to_dict('records'),
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'training_samples': len(bucket_data)
        }

        model_path = self.models_dir / f"short_expiry_{bucket}.pkl"
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"\nModel saved to: {model_path}")

        return model_data

    def run(self):
        """Run the complete training pipeline."""
        logger.info("="*60)
        logger.info("SHORT-EXPIRY MODEL TRAINING PIPELINE")
        logger.info("="*60)

        # Step 1: Extract short-expiry markets
        markets = self.extract_short_expiry_markets()

        if markets is None or len(markets) == 0:
            logger.error("No markets found!")
            return

        # Step 2: Build training dataset
        training_df = self.build_training_dataset(markets)

        if training_df is None or len(training_df) == 0:
            logger.error("No training data generated!")
            return

        # Save training data
        training_data_path = self.data_dir / "short_expiry_training_data.csv"
        training_df.to_csv(training_data_path, index=False)
        logger.info(f"\nTraining data saved to: {training_data_path}")

        # Step 3: Train models for each bucket
        models = {}

        for bucket in ['ultra_short', 'short', 'medium']:
            model_data = self.train_bucket_model(training_df, bucket)
            if model_data:
                models[bucket] = model_data

        # Step 4: Summary
        logger.info("\n" + "="*60)
        logger.info("TRAINING COMPLETE!")
        logger.info("="*60)

        summary = {
            'trained_at': datetime.now(timezone.utc).isoformat(),
            'total_markets': len(markets),
            'total_samples': len(training_df),
            'models': {}
        }

        for bucket, model_data in models.items():
            summary['models'][bucket] = {
                'samples': model_data['training_samples'],
                'metrics': model_data['cv_metrics'],
                'path': str(self.models_dir / f"short_expiry_{bucket}.pkl")
            }

            logger.info(f"\n{bucket.upper()} Model:")
            logger.info(f"  Samples: {model_data['training_samples']}")
            logger.info(f"  Accuracy: {model_data['cv_metrics']['accuracy']:.3f}")
            logger.info(f"  F1 Score: {model_data['cv_metrics']['f1']:.3f}")
            logger.info(f"  AUC: {model_data['cv_metrics']['auc']:.3f}")

        # Save summary
        summary_path = self.models_dir / "training_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\nSummary saved to: {summary_path}")
        logger.info("\nModels ready for deployment!")


if __name__ == '__main__':
    pipeline = ShortExpiryTrainingPipeline()
    pipeline.run()
