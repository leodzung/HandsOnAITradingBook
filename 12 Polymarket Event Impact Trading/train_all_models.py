#!/usr/bin/env python3
"""
Train ML models for all three trading bots using REAL labeled data.
Uses 1.23M real blockchain trades with verified outcomes.
"""

import sys
import pandas as pd
import numpy as np
import pickle
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, classification_report, confusion_matrix
)
from sklearn.calibration import CalibratedClassifierCV
import matplotlib.pyplot as plt

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class UnifiedModelTrainer:
    """Train models for event, price-level, and short-expiry bots."""
    
    def __init__(self, data_path='data/REAL_labeled_from_alchemy.csv'):
        self.data_path = data_path
        self.models_dir = Path('data/models')
        self.models_dir.mkdir(exist_ok=True)
        
        logger.info(f"Loading data from {data_path}")
        self.df = pd.read_csv(data_path)
        logger.info(f"✅ Loaded {len(self.df):,} trades from {self.df['condition_id'].nunique():,} markets")
        
        # Parse timestamp
        self.df['timestamp'] = pd.to_datetime(self.df['block_timestamp'])
        
    def engineer_features(self):
        """Engineer features for all bots."""
        logger.info("\n=== Engineering Features ===")
        
        df = self.df.copy()
        
        # Basic price features
        df['price_squared'] = df['trade_price'] ** 2
        df['price_cubed'] = df['trade_price'] ** 3
        df['log_price'] = np.log(df['trade_price'].clip(0.001, 0.999))
        df['price_distance_from_half'] = np.abs(df['trade_price'] - 0.5)
        
        # Market position (betting YES or NO)
        df['betting_yes'] = (df['trade_price'] > 0.5).astype(int)
        df['betting_no'] = (df['trade_price'] < 0.5).astype(int)
        
        # Confidence (how far from 50/50)
        df['market_confidence'] = np.abs(df['trade_price'] - 0.5) * 2
        
        # Time features (if we have timestamps)
        df['hour_of_day'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # Question length (proxy for complexity)
        df['question_length'] = df['question'].str.len()
        df['question_words'] = df['question'].str.split().str.len()
        
        # Outcome type detection
        df['is_sports'] = df['question'].str.contains(
            'win|championship|bowl|playoff|coach|mvp|athlete',
            case=False, na=False
        ).astype(int)
        
        df['is_politics'] = df['question'].str.contains(
            'election|president|mayor|vote|poll',
            case=False, na=False
        ).astype(int)
        
        df['is_crypto'] = df['question'].str.contains(
            'bitcoin|btc|ethereum|eth|crypto|blockchain|fed|interest|rate',
            case=False, na=False
        ).astype(int)
        
        logger.info(f"✅ Engineered {len([c for c in df.columns if c not in self.df.columns])} new features")
        
        return df
    
    def train_model(self, X_train, y_train, X_val, y_val, model_name):
        """Train a single GBM model."""
        logger.info(f"\nTraining {model_name}...")
        
        # Gradient Boosting Classifier
        model = GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=5,
            min_samples_split=500,
            min_samples_leaf=200,
            subsample=0.8,
            random_state=42,
            verbose=1
        )
        
        model.fit(X_train, y_train)
        
        # Calibrate probabilities
        logger.info("Calibrating probabilities...")
        calibrated_model = CalibratedClassifierCV(
            model,
            method='isotonic',
            cv='prefit'
        )
        calibrated_model.fit(X_val, y_val)
        
        return calibrated_model
    
    def evaluate_model(self, model, X_test, y_test, model_name):
        """Evaluate model performance."""
        logger.info(f"\n=== Evaluating {model_name} ===")
        
        y_pred = model.predict(X_test)
        y_proba = model.predict_proba(X_test)[:, 1]
        
        metrics = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, average='binary', pos_label=1),
            'recall': recall_score(y_test, y_pred, average='binary', pos_label=1),
            'f1': f1_score(y_test, y_pred, average='binary', pos_label=1),
            'roc_auc': roc_auc_score(y_test, y_proba)
        }
        
        logger.info(f"Accuracy:  {metrics['accuracy']:.4f}")
        logger.info(f"Precision: {metrics['precision']:.4f}")
        logger.info(f"Recall:    {metrics['recall']:.4f}")
        logger.info(f"F1 Score:  {metrics['f1']:.4f}")
        logger.info(f"ROC AUC:   {metrics['roc_auc']:.4f}")
        
        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        logger.info(f"\nConfusion Matrix:")
        logger.info(f"  TN: {cm[0,0]:,}  FP: {cm[0,1]:,}")
        logger.info(f"  FN: {cm[1,0]:,}  TP: {cm[1,1]:,}")
        
        return metrics
    
    def train_all_bots(self):
        """Train models for all three bots."""
        logger.info("\n" + "="*70)
        logger.info("TRAINING ALL BOT MODELS")
        logger.info("="*70)
        
        # Engineer features
        df = self.engineer_features()
        
        # Select features
        feature_cols = [
            'trade_price', 'price_squared', 'price_cubed', 'log_price',
            'price_distance_from_half', 'betting_yes', 'betting_no',
            'market_confidence', 'hour_of_day', 'day_of_week', 'is_weekend',
            'question_length', 'question_words',
            'is_sports', 'is_politics', 'is_crypto'
        ]
        
        X = df[feature_cols].fillna(0)
        y = (df['label'] == 1).astype(int)  # Convert to binary: 1=correct, 0=wrong
        
        logger.info(f"\nDataset summary:")
        logger.info(f"  Total samples: {len(X):,}")
        logger.info(f"  Features: {len(feature_cols)}")
        logger.info(f"  Positive class: {y.sum():,} ({y.mean()*100:.1f}%)")
        logger.info(f"  Negative class: {(~y.astype(bool)).sum():,} ({(1-y.mean())*100:.1f}%)")
        
        # Time-based split (train on older data, test on newer)
        df['timestamp'] = pd.to_datetime(df['block_timestamp'])
        df = df.sort_values('timestamp')
        
        # 70% train, 15% val, 15% test (chronological)
        n = len(df)
        train_idx = int(n * 0.70)
        val_idx = int(n * 0.85)
        
        X_train = X.iloc[:train_idx]
        y_train = y.iloc[:train_idx]
        X_val = X.iloc[train_idx:val_idx]
        y_val = y.iloc[train_idx:val_idx]
        X_test = X.iloc[val_idx:]
        y_test = y.iloc[val_idx:]
        
        logger.info(f"\nTime-based split:")
        logger.info(f"  Train: {len(X_train):,} samples")
        logger.info(f"  Val:   {len(X_val):,} samples")
        logger.info(f"  Test:  {len(X_test):,} samples")
        
        # Train unified model (can be used by all bots)
        model = self.train_model(X_train, y_train, X_val, y_val, "Unified Model")
        
        # Evaluate
        metrics = self.evaluate_model(model, X_test, y_test, "Unified Model")
        
        # Save model
        model_info = {
            'model': model,
            'feature_names': feature_cols,
            'metrics': metrics,
            'training_date': datetime.now().isoformat(),
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'data_source': 'REAL_labeled_from_alchemy.csv'
        }
        
        # Save for each bot
        for bot_name in ['event', 'price_level', 'short_expiry']:
            model_path = self.models_dir / f'{bot_name}_model.pkl'
            with open(model_path, 'wb') as f:
                pickle.dump(model_info, f)
            logger.info(f"✅ Saved {bot_name} model: {model_path}")
        
        # Save validation report
        report_path = self.models_dir / 'training_report.json'
        with open(report_path, 'w') as f:
            json.dump({
                'metrics': {k: float(v) for k, v in metrics.items()},
                'training_date': datetime.now().isoformat(),
                'samples': {
                    'train': len(X_train),
                    'val': len(X_val),
                    'test': len(X_test)
                },
                'features': feature_cols
            }, f, indent=2)
        
        logger.info(f"\n✅ Saved training report: {report_path}")
        
        logger.info("\n" + "="*70)
        logger.info("✅✅ ALL MODELS TRAINED SUCCESSFULLY!")
        logger.info("="*70)
        logger.info(f"\nModels saved in: {self.models_dir}/")
        logger.info("  - event_model.pkl")
        logger.info("  - price_level_model.pkl")
        logger.info("  - short_expiry_model.pkl")
        
        return model_info


if __name__ == '__main__':
    trainer = UnifiedModelTrainer()
    trainer.train_all_bots()
