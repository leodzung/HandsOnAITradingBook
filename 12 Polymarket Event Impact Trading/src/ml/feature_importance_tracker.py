"""
Feature Importance Tracker for Data Drift Detection

Stores feature importance scores from each training run and provides
historical analysis capabilities for detecting feature drift.

Author: AI Trading System
Date: 2026-02-21
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureImportanceTracker:
    """
    Tracks feature importance scores across training runs to enable
    drift detection and model stability analysis.

    Features:
    - Stores importance with full training context
    - Normalizes importance scores (sum=1.0)
    - Tracks ranking and cumulative importance
    - Supports both model-level and fold-level tracking
    - Provides historical queries for drift analysis
    """

    def __init__(self, db_path: str = 'data/training_history.db'):
        """
        Initialize the tracker and create database schema if needed.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_database()
        logger.info(f"FeatureImportanceTracker initialized with database: {db_path}")

    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table 1: Feature Importance History
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feature_importance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Training context
                bot_type TEXT NOT NULL,
                model_type TEXT NOT NULL,
                training_timestamp TEXT NOT NULL,

                -- Fold context (NULL for non-CV training)
                validation_fold_id INTEGER,
                fold_start_date TEXT,
                fold_end_date TEXT,

                -- Feature data
                feature_name TEXT NOT NULL,
                importance_score REAL NOT NULL,
                importance_rank INTEGER NOT NULL,

                -- Normalization (sum of all features = 1.0)
                normalized_importance REAL NOT NULL,
                cumulative_importance REAL NOT NULL,

                -- Model metadata
                model_path TEXT,
                num_features INTEGER NOT NULL,
                training_samples INTEGER NOT NULL,

                -- Performance metrics
                train_roc_auc REAL,
                val_roc_auc REAL,
                test_roc_auc REAL,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_timestamp
            ON feature_importance_history(bot_type, training_timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_feature_name
            ON feature_importance_history(feature_name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_importance_rank
            ON feature_importance_history(importance_rank)
        """)

        # Table 2: Drift Detection Alerts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drift_detection_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Alert metadata
                alert_timestamp TEXT NOT NULL,
                bot_type TEXT NOT NULL,
                alert_type TEXT NOT NULL,  -- 'rank_shift', 'importance_drop', 'new_top_feature', etc.
                severity TEXT NOT NULL,    -- 'info', 'warning', 'critical'

                -- Drift metrics
                drift_score REAL NOT NULL,
                affected_features TEXT NOT NULL,  -- JSON array of feature names

                -- Comparison context
                baseline_timestamp TEXT NOT NULL,
                current_timestamp TEXT NOT NULL,
                baseline_strategy TEXT,  -- 'ewma', 'latest_n', 'best_auc'

                -- Alert details
                message TEXT,

                -- Actions
                telegram_sent BOOLEAN DEFAULT 0,
                acknowledged BOOLEAN DEFAULT 0,
                acknowledged_at TEXT,

                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_bot_time
            ON drift_detection_alerts(bot_type, alert_timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alert_severity
            ON drift_detection_alerts(severity, acknowledged)
        """)

        conn.commit()
        conn.close()
        logger.info("Database schema initialized successfully")

    def store_importance(
        self,
        bot_type: str,
        model,
        feature_names: List[str],
        metrics: Dict[str, float],
        training_context: Dict,
        model_path: Optional[str] = None
    ):
        """
        Store feature importance from a trained model.

        Args:
            bot_type: Type of bot ('event', 'price_level', 'short_expiry')
            model: Trained model with feature_importances_ or coef_ attribute
            feature_names: List of feature names in same order as model features
            metrics: Dict with 'train_roc_auc', 'val_roc_auc', 'test_roc_auc'
            training_context: Dict with 'training_samples' and optional metadata
            model_path: Path to saved model file

        Returns:
            Number of features stored
        """
        # Extract importance scores based on model type
        if hasattr(model, 'feature_importances_'):
            # Tree-based models (GradientBoosting, RandomForest)
            importance_scores = model.feature_importances_
            model_type = type(model).__name__
        elif hasattr(model, 'coef_'):
            # Linear models (LogisticRegression)
            importance_scores = np.abs(model.coef_[0])
            model_type = type(model).__name__
        else:
            logger.warning(f"Model {type(model).__name__} has no feature_importances_ or coef_ attribute")
            return 0

        # Validate
        if len(importance_scores) != len(feature_names):
            raise ValueError(
                f"Mismatch: {len(importance_scores)} importance scores but {len(feature_names)} feature names"
            )

        # Normalize importance scores (sum = 1.0)
        total_importance = np.sum(importance_scores)
        if total_importance == 0:
            logger.warning("Total importance is zero, cannot normalize")
            normalized_scores = np.zeros_like(importance_scores)
        else:
            normalized_scores = importance_scores / total_importance

        # Create DataFrame for easier processing
        df = pd.DataFrame({
            'feature_name': feature_names,
            'importance_score': importance_scores,
            'normalized_importance': normalized_scores
        })

        # Sort by importance (descending) and assign ranks
        df = df.sort_values('importance_score', ascending=False).reset_index(drop=True)
        df['importance_rank'] = range(1, len(df) + 1)

        # Calculate cumulative importance
        df['cumulative_importance'] = df['normalized_importance'].cumsum()

        # Prepare data for insertion
        timestamp = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO feature_importance_history (
                    bot_type, model_type, training_timestamp,
                    validation_fold_id, fold_start_date, fold_end_date,
                    feature_name, importance_score, importance_rank,
                    normalized_importance, cumulative_importance,
                    model_path, num_features, training_samples,
                    train_roc_auc, val_roc_auc, test_roc_auc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot_type,
                model_type,
                timestamp,
                None, None, None,  # No fold context for model-level tracking
                row['feature_name'],
                float(row['importance_score']),
                int(row['importance_rank']),
                float(row['normalized_importance']),
                float(row['cumulative_importance']),
                model_path,
                len(feature_names),
                training_context.get('training_samples', 0),
                metrics.get('train_roc_auc'),
                metrics.get('val_roc_auc'),
                metrics.get('test_roc_auc')
            ))

        conn.commit()
        conn.close()

        logger.info(
            f"Stored importance for {len(df)} features from {bot_type} {model_type} "
            f"(timestamp: {timestamp})"
        )

        return len(df)

    def store_fold_importance(
        self,
        model,
        feature_names: List[str],
        fold_id: int,
        fold_context: Dict,
        metrics: Dict[str, float],
        bot_type: str = 'walk_forward'
    ):
        """
        Store feature importance from a walk-forward validation fold.

        Args:
            model: Trained model for this fold
            feature_names: List of feature names
            fold_id: Fold number (0-indexed)
            fold_context: Dict with train_start, train_end, val_start, val_end, train_samples, val_samples
            metrics: Dict with performance metrics
            bot_type: Bot type (defaults to 'walk_forward')

        Returns:
            Number of features stored
        """
        # Extract importance scores
        if hasattr(model, 'feature_importances_'):
            importance_scores = model.feature_importances_
            model_type = type(model).__name__
        elif hasattr(model, 'coef_'):
            importance_scores = np.abs(model.coef_[0])
            model_type = type(model).__name__
        else:
            logger.warning(f"Model {type(model).__name__} has no feature_importances_ or coef_ attribute")
            return 0

        # Validate
        if len(importance_scores) != len(feature_names):
            raise ValueError(
                f"Mismatch: {len(importance_scores)} importance scores but {len(feature_names)} feature names"
            )

        # Normalize
        total_importance = np.sum(importance_scores)
        if total_importance == 0:
            normalized_scores = np.zeros_like(importance_scores)
        else:
            normalized_scores = importance_scores / total_importance

        # Create DataFrame
        df = pd.DataFrame({
            'feature_name': feature_names,
            'importance_score': importance_scores,
            'normalized_importance': normalized_scores
        })

        # Sort and rank
        df = df.sort_values('importance_score', ascending=False).reset_index(drop=True)
        df['importance_rank'] = range(1, len(df) + 1)
        df['cumulative_importance'] = df['normalized_importance'].cumsum()

        # Prepare data
        timestamp = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO feature_importance_history (
                    bot_type, model_type, training_timestamp,
                    validation_fold_id, fold_start_date, fold_end_date,
                    feature_name, importance_score, importance_rank,
                    normalized_importance, cumulative_importance,
                    model_path, num_features, training_samples,
                    train_roc_auc, val_roc_auc, test_roc_auc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bot_type,
                model_type,
                timestamp,
                fold_id,
                fold_context.get('train_start'),
                fold_context.get('train_end'),
                row['feature_name'],
                float(row['importance_score']),
                int(row['importance_rank']),
                float(row['normalized_importance']),
                float(row['cumulative_importance']),
                None,  # No model path for fold-level tracking
                len(feature_names),
                fold_context.get('train_samples', 0),
                metrics.get('train_roc_auc'),
                metrics.get('val_roc_auc'),
                metrics.get('test_roc_auc')
            ))

        conn.commit()
        conn.close()

        logger.info(
            f"Stored importance for {len(df)} features from fold {fold_id} "
            f"(timestamp: {timestamp})"
        )

        return len(df)

    def get_importance_history(
        self,
        bot_type: str,
        last_n_runs: int = 10,
        exclude_folds: bool = True
    ) -> pd.DataFrame:
        """
        Get historical feature importance for a bot.

        Args:
            bot_type: Bot type to query
            last_n_runs: Number of recent training runs to retrieve
            exclude_folds: If True, exclude fold-level tracking (only get model-level)

        Returns:
            DataFrame with columns: training_timestamp, feature_name, importance_score,
            importance_rank, normalized_importance, train_roc_auc, val_roc_auc
        """
        conn = sqlite3.connect(self.db_path)

        # Get last N unique timestamps
        fold_filter = "AND validation_fold_id IS NULL" if exclude_folds else ""

        query = f"""
            SELECT DISTINCT training_timestamp
            FROM feature_importance_history
            WHERE bot_type = ?
            {fold_filter}
            ORDER BY training_timestamp DESC
            LIMIT ?
        """

        timestamps = pd.read_sql_query(query, conn, params=(bot_type, last_n_runs))

        if timestamps.empty:
            logger.warning(f"No importance history found for {bot_type}")
            conn.close()
            return pd.DataFrame()

        # Get all features for these timestamps
        timestamp_list = timestamps['training_timestamp'].tolist()
        placeholders = ','.join('?' * len(timestamp_list))

        query = f"""
            SELECT
                training_timestamp,
                feature_name,
                importance_score,
                importance_rank,
                normalized_importance,
                cumulative_importance,
                train_roc_auc,
                val_roc_auc,
                test_roc_auc,
                num_features,
                training_samples
            FROM feature_importance_history
            WHERE bot_type = ?
            AND training_timestamp IN ({placeholders})
            {fold_filter}
            ORDER BY training_timestamp DESC, importance_rank ASC
        """

        df = pd.read_sql_query(query, conn, params=[bot_type] + timestamp_list)
        conn.close()

        logger.info(f"Retrieved {len(df)} importance records for {bot_type} ({len(timestamp_list)} runs)")

        return df

    def get_latest_importance(self, bot_type: str, exclude_folds: bool = True) -> pd.DataFrame:
        """
        Get feature importance from the most recent training run.

        Args:
            bot_type: Bot type to query
            exclude_folds: If True, exclude fold-level tracking

        Returns:
            DataFrame with feature importance sorted by rank
        """
        conn = sqlite3.connect(self.db_path)

        fold_filter = "AND validation_fold_id IS NULL" if exclude_folds else ""

        query = f"""
            SELECT
                feature_name,
                importance_score,
                importance_rank,
                normalized_importance,
                cumulative_importance,
                training_timestamp,
                train_roc_auc,
                val_roc_auc,
                test_roc_auc
            FROM feature_importance_history
            WHERE bot_type = ?
            {fold_filter}
            AND training_timestamp = (
                SELECT MAX(training_timestamp)
                FROM feature_importance_history
                WHERE bot_type = ?
                {fold_filter}
            )
            ORDER BY importance_rank ASC
        """

        df = pd.read_sql_query(query, conn, params=(bot_type, bot_type))
        conn.close()

        if df.empty:
            logger.warning(f"No latest importance found for {bot_type}")
        else:
            logger.info(
                f"Retrieved latest importance for {bot_type}: "
                f"{len(df)} features (timestamp: {df['training_timestamp'].iloc[0]})"
            )

        return df

    def get_training_timestamps(self, bot_type: str, exclude_folds: bool = True) -> List[str]:
        """
        Get all training timestamps for a bot (for selecting baselines).

        Args:
            bot_type: Bot type to query
            exclude_folds: If True, exclude fold-level tracking

        Returns:
            List of ISO timestamp strings (most recent first)
        """
        conn = sqlite3.connect(self.db_path)

        fold_filter = "AND validation_fold_id IS NULL" if exclude_folds else ""

        query = f"""
            SELECT DISTINCT training_timestamp
            FROM feature_importance_history
            WHERE bot_type = ?
            {fold_filter}
            ORDER BY training_timestamp DESC
        """

        timestamps = pd.read_sql_query(query, conn, params=(bot_type,))
        conn.close()

        return timestamps['training_timestamp'].tolist()
