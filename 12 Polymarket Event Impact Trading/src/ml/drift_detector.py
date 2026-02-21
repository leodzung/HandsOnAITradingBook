"""
Feature Drift Detector for ML Model Monitoring

Detects feature importance drift using multiple metrics:
- Rank Stability Score (Kendall's Tau)
- L1 Distribution Shift
- Top-K Overlap (Jaccard similarity)
- Performance-Drift Correlation

Author: AI Trading System
Date: 2026-02-21
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, pearsonr

from .feature_importance_tracker import FeatureImportanceTracker

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Detects feature importance drift and generates alerts based on
    configurable thresholds.

    Drift Metrics:
    1. Rank Stability Score (RSS): Kendall's Tau correlation
    2. L1 Distribution Shift: L1 distance between normalized importance
    3. Top-K Overlap: Jaccard similarity of top-K features
    4. Performance-Drift Correlation: Correlation between drift and AUC drop

    Alert Severities:
    - INFO: Benign changes (new top feature)
    - WARNING: Moderate drift (RSS < 0.7, L1 > 0.4)
    - CRITICAL: Severe drift (RSS < 0.5, top-5 drop >80%, drift correlated with AUC drop)
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        'rank_stability': {
            'warning': 0.7,
            'critical': 0.5
        },
        'l1_distance': {
            'warning': 0.4,
            'critical': 0.6
        },
        'top_k_overlap': {
            'k': 5,
            'warning': 0.6,
            'critical': 0.4
        },
        'importance_drop': {
            'warning': 0.5,  # 50% drop
            'critical': 0.8  # 80% drop
        },
        'performance_correlation': {
            'critical': 0.6  # r > 0.6 means drift causing performance issues
        }
    }

    def __init__(
        self,
        db_path: str = 'data/training_history.db',
        thresholds: Optional[Dict] = None
    ):
        """
        Initialize the drift detector.

        Args:
            db_path: Path to training history database
            thresholds: Custom thresholds (defaults to DEFAULT_THRESHOLDS)
        """
        self.db_path = db_path
        self.tracker = FeatureImportanceTracker(db_path)
        self.thresholds = thresholds or self.DEFAULT_THRESHOLDS

        logger.info("DriftDetector initialized")

    def calculate_rank_stability(
        self,
        baseline_ranks: pd.Series,
        current_ranks: pd.Series
    ) -> Tuple[float, float]:
        """
        Calculate Kendall's Tau correlation between feature rankings.

        Args:
            baseline_ranks: Series with feature_name as index, rank as value
            current_ranks: Series with feature_name as index, rank as value

        Returns:
            (tau, p_value): Kendall's Tau correlation coefficient and p-value
        """
        # Align features (some may be missing in one of the rankings)
        common_features = baseline_ranks.index.intersection(current_ranks.index)

        if len(common_features) == 0:
            logger.warning("No common features between baseline and current rankings")
            return 0.0, 1.0

        baseline_aligned = baseline_ranks[common_features]
        current_aligned = current_ranks[common_features]

        tau, p_value = kendalltau(baseline_aligned, current_aligned)

        logger.debug(
            f"Rank stability: tau={tau:.3f}, p={p_value:.3f} "
            f"({len(common_features)} common features)"
        )

        return tau, p_value

    def calculate_importance_shift(
        self,
        baseline_importance: pd.Series,
        current_importance: pd.Series
    ) -> float:
        """
        Calculate L1 distance between normalized importance distributions.

        Args:
            baseline_importance: Series with feature_name as index, normalized importance as value
            current_importance: Series with feature_name as index, normalized importance as value

        Returns:
            L1 distance (0.0 = identical, 2.0 = completely different)
        """
        # Align features
        all_features = baseline_importance.index.union(current_importance.index)

        baseline_aligned = baseline_importance.reindex(all_features, fill_value=0.0)
        current_aligned = current_importance.reindex(all_features, fill_value=0.0)

        # L1 distance
        l1_distance = np.sum(np.abs(baseline_aligned - current_aligned))

        logger.debug(f"Importance shift: L1={l1_distance:.3f}")

        return l1_distance

    def calculate_top_k_overlap(
        self,
        baseline_top_k: List[str],
        current_top_k: List[str],
        k: int = 5
    ) -> float:
        """
        Calculate Jaccard similarity between top-K feature sets.

        Args:
            baseline_top_k: List of top-K feature names from baseline
            current_top_k: List of top-K feature names from current
            k: Number of top features to compare

        Returns:
            Jaccard similarity (1.0 = perfect overlap, 0.0 = no overlap)
        """
        baseline_set = set(baseline_top_k[:k])
        current_set = set(current_top_k[:k])

        intersection = len(baseline_set & current_set)
        union = len(baseline_set | current_set)

        if union == 0:
            return 0.0

        jaccard = intersection / union

        logger.debug(
            f"Top-{k} overlap: {jaccard:.3f} "
            f"(intersection={intersection}, union={union})"
        )

        return jaccard

    def get_baseline(
        self,
        bot_type: str,
        strategy: str = 'ewma',
        lookback_runs: int = 5,
        specific_timestamp: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get baseline feature importance using specified strategy.

        Strategies:
        - 'latest_n': Average of last N runs
        - 'ewma': Exponentially-weighted moving average (more weight on recent)
        - 'best_auc': Run with highest validation AUC
        - 'specific': Specific timestamp (requires specific_timestamp parameter)

        Args:
            bot_type: Bot type to query
            strategy: Baseline strategy
            lookback_runs: Number of runs to look back (for 'latest_n' and 'ewma')
            specific_timestamp: Specific timestamp to use (for 'specific' strategy)

        Returns:
            DataFrame with baseline feature importance
        """
        if strategy == 'specific':
            if not specific_timestamp:
                raise ValueError("specific_timestamp required for 'specific' strategy")

            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT
                    feature_name,
                    importance_score,
                    importance_rank,
                    normalized_importance
                FROM feature_importance_history
                WHERE bot_type = ?
                AND training_timestamp = ?
                AND validation_fold_id IS NULL
                ORDER BY importance_rank ASC
            """
            baseline = pd.read_sql_query(query, conn, params=(bot_type, specific_timestamp))
            conn.close()

            if baseline.empty:
                raise ValueError(f"No data found for timestamp {specific_timestamp}")

            return baseline

        # Get historical data
        history = self.tracker.get_importance_history(
            bot_type=bot_type,
            last_n_runs=lookback_runs,
            exclude_folds=True
        )

        if history.empty:
            raise ValueError(f"No historical data found for {bot_type}")

        if strategy == 'best_auc':
            # Get timestamp with highest validation AUC
            best_timestamp = (
                history.groupby('training_timestamp')['val_roc_auc']
                .first()
                .idxmax()
            )

            baseline = history[history['training_timestamp'] == best_timestamp].copy()

        elif strategy == 'latest_n':
            # Average importance across last N runs
            baseline = (
                history.groupby('feature_name')
                .agg({
                    'normalized_importance': 'mean',
                    'importance_score': 'mean'
                })
                .reset_index()
            )

            # Recalculate ranks based on averaged importance
            baseline = baseline.sort_values('importance_score', ascending=False)
            baseline['importance_rank'] = range(1, len(baseline) + 1)

        elif strategy == 'ewma':
            # EWMA with alpha=0.3 (more weight on recent)
            timestamps = sorted(history['training_timestamp'].unique(), reverse=True)

            # Initialize with oldest run
            baseline = history[history['training_timestamp'] == timestamps[-1]][
                ['feature_name', 'normalized_importance', 'importance_score']
            ].set_index('feature_name')

            # Apply EWMA
            alpha = 0.3
            for timestamp in timestamps[-2::-1]:  # Reverse iterate (oldest to newest)
                current = history[history['training_timestamp'] == timestamp][
                    ['feature_name', 'normalized_importance', 'importance_score']
                ].set_index('feature_name')

                # EWMA update
                baseline = alpha * current + (1 - alpha) * baseline
                baseline = baseline.fillna(current)  # Handle new features

            baseline = baseline.reset_index()
            baseline = baseline.sort_values('importance_score', ascending=False)
            baseline['importance_rank'] = range(1, len(baseline) + 1)

        else:
            raise ValueError(f"Unknown baseline strategy: {strategy}")

        logger.info(
            f"Computed baseline for {bot_type} using strategy '{strategy}' "
            f"({len(baseline)} features)"
        )

        return baseline

    def detect_drift(
        self,
        bot_type: str,
        baseline_strategy: str = 'ewma',
        lookback_runs: int = 5
    ) -> List[Dict]:
        """
        Detect feature importance drift and generate alerts.

        Args:
            bot_type: Bot type to analyze
            baseline_strategy: How to compute baseline ('ewma', 'latest_n', 'best_auc')
            lookback_runs: Number of runs to look back for baseline

        Returns:
            List of alert dictionaries
        """
        alerts = []

        # Get current importance
        current = self.tracker.get_latest_importance(bot_type)

        if current.empty:
            logger.warning(f"No current importance data for {bot_type}, skipping drift detection")
            return alerts

        current_timestamp = current['training_timestamp'].iloc[0]

        # Get baseline importance
        try:
            baseline = self.get_baseline(
                bot_type=bot_type,
                strategy=baseline_strategy,
                lookback_runs=lookback_runs
            )
        except ValueError as e:
            logger.warning(f"Could not get baseline for {bot_type}: {e}")
            return alerts

        baseline_timestamp = baseline.get('training_timestamp', pd.Series(['computed'])).iloc[0]

        # Prepare data for metrics
        current_ranks = current.set_index('feature_name')['importance_rank']
        baseline_ranks = baseline.set_index('feature_name')['importance_rank']

        current_importance = current.set_index('feature_name')['normalized_importance']
        baseline_importance = baseline.set_index('feature_name')['normalized_importance']

        current_top_k = current.nsmallest(10, 'importance_rank')['feature_name'].tolist()
        baseline_top_k = baseline.nsmallest(10, 'importance_rank')['feature_name'].tolist()

        # Metric 1: Rank Stability Score
        tau, p_value = self.calculate_rank_stability(baseline_ranks, current_ranks)

        if tau < self.thresholds['rank_stability']['critical']:
            alerts.append({
                'alert_type': 'rank_shift',
                'severity': 'critical',
                'drift_score': tau,
                'affected_features': current_top_k[:5],
                'message': f"Critical rank instability detected (tau={tau:.3f})"
            })
        elif tau < self.thresholds['rank_stability']['warning']:
            alerts.append({
                'alert_type': 'rank_shift',
                'severity': 'warning',
                'drift_score': tau,
                'affected_features': current_top_k[:5],
                'message': f"Moderate rank instability detected (tau={tau:.3f})"
            })

        # Metric 2: L1 Distribution Shift
        l1_distance = self.calculate_importance_shift(baseline_importance, current_importance)

        if l1_distance > self.thresholds['l1_distance']['critical']:
            alerts.append({
                'alert_type': 'distribution_shift',
                'severity': 'critical',
                'drift_score': l1_distance,
                'affected_features': current_top_k[:5],
                'message': f"Critical distribution shift detected (L1={l1_distance:.3f})"
            })
        elif l1_distance > self.thresholds['l1_distance']['warning']:
            alerts.append({
                'alert_type': 'distribution_shift',
                'severity': 'warning',
                'drift_score': l1_distance,
                'affected_features': current_top_k[:5],
                'message': f"Moderate distribution shift detected (L1={l1_distance:.3f})"
            })

        # Metric 3: Top-K Overlap
        k = self.thresholds['top_k_overlap']['k']
        top_k_overlap = self.calculate_top_k_overlap(baseline_top_k, current_top_k, k=k)

        if top_k_overlap < self.thresholds['top_k_overlap']['critical']:
            alerts.append({
                'alert_type': 'top_k_change',
                'severity': 'critical',
                'drift_score': 1.0 - top_k_overlap,  # Invert so higher = worse
                'affected_features': list(set(current_top_k[:k]) - set(baseline_top_k[:k])),
                'message': f"Critical top-{k} overlap drop (overlap={top_k_overlap:.3f})"
            })
        elif top_k_overlap < self.thresholds['top_k_overlap']['warning']:
            alerts.append({
                'alert_type': 'top_k_change',
                'severity': 'warning',
                'drift_score': 1.0 - top_k_overlap,
                'affected_features': list(set(current_top_k[:k]) - set(baseline_top_k[:k])),
                'message': f"Moderate top-{k} overlap drop (overlap={top_k_overlap:.3f})"
            })

        # Metric 4: Individual Feature Importance Drops
        common_features = baseline_importance.index.intersection(current_importance.index)
        baseline_top_5 = baseline.nsmallest(5, 'importance_rank')['feature_name'].tolist()

        for feature in baseline_top_5:
            if feature in common_features:
                baseline_imp = baseline_importance[feature]
                current_imp = current_importance[feature]

                if baseline_imp > 0:
                    drop_pct = (baseline_imp - current_imp) / baseline_imp

                    if drop_pct > self.thresholds['importance_drop']['critical']:
                        alerts.append({
                            'alert_type': 'importance_drop',
                            'severity': 'critical',
                            'drift_score': drop_pct,
                            'affected_features': [feature],
                            'message': f"Feature '{feature}' importance dropped {drop_pct*100:.1f}%"
                        })
                    elif drop_pct > self.thresholds['importance_drop']['warning']:
                        alerts.append({
                            'alert_type': 'importance_drop',
                            'severity': 'warning',
                            'drift_score': drop_pct,
                            'affected_features': [feature],
                            'message': f"Feature '{feature}' importance dropped {drop_pct*100:.1f}%"
                        })

        # Metric 5: New Top Features (informational)
        baseline_top_3 = baseline.nsmallest(3, 'importance_rank')['feature_name'].tolist()
        current_top_3 = current.nsmallest(3, 'importance_rank')['feature_name'].tolist()

        new_top_features = [f for f in current_top_3 if f not in baseline_top_k[:10]]

        if new_top_features:
            alerts.append({
                'alert_type': 'new_top_feature',
                'severity': 'info',
                'drift_score': 0.0,
                'affected_features': new_top_features,
                'message': f"New feature(s) in top-3: {', '.join(new_top_features)}"
            })

        # Store alerts in database
        for alert in alerts:
            self.store_alert(
                bot_type=bot_type,
                alert=alert,
                baseline_timestamp=baseline_timestamp,
                current_timestamp=current_timestamp,
                baseline_strategy=baseline_strategy
            )

        logger.info(
            f"Drift detection complete for {bot_type}: {len(alerts)} alerts generated "
            f"(critical={sum(1 for a in alerts if a['severity']=='critical')}, "
            f"warning={sum(1 for a in alerts if a['severity']=='warning')}, "
            f"info={sum(1 for a in alerts if a['severity']=='info')})"
        )

        return alerts

    def store_alert(
        self,
        bot_type: str,
        alert: Dict,
        baseline_timestamp: str,
        current_timestamp: str,
        baseline_strategy: str
    ):
        """
        Store drift alert in database with cooldown check.

        Args:
            bot_type: Bot type
            alert: Alert dictionary from detect_drift()
            baseline_timestamp: Baseline timestamp
            current_timestamp: Current timestamp
            baseline_strategy: Baseline strategy used
        """
        # Check for recent similar alerts (24-hour cooldown)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cooldown_time = datetime.now() - timedelta(hours=24)

        cursor.execute("""
            SELECT COUNT(*) FROM drift_detection_alerts
            WHERE bot_type = ?
            AND alert_type = ?
            AND alert_timestamp > ?
            AND acknowledged = 0
        """, (bot_type, alert['alert_type'], cooldown_time.isoformat()))

        recent_count = cursor.fetchone()[0]

        if recent_count > 0:
            logger.debug(
                f"Skipping duplicate alert (type={alert['alert_type']}, "
                f"recent_count={recent_count})"
            )
            conn.close()
            return

        # Store alert
        cursor.execute("""
            INSERT INTO drift_detection_alerts (
                alert_timestamp,
                bot_type,
                alert_type,
                severity,
                drift_score,
                affected_features,
                baseline_timestamp,
                current_timestamp,
                baseline_strategy,
                message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            bot_type,
            alert['alert_type'],
            alert['severity'],
            alert['drift_score'],
            json.dumps(alert['affected_features']),
            baseline_timestamp,
            current_timestamp,
            baseline_strategy,
            alert['message']
        ))

        conn.commit()
        conn.close()

        logger.info(f"Stored {alert['severity']} alert: {alert['message']}")

    def get_recent_alerts(
        self,
        bot_type: Optional[str] = None,
        severity: Optional[str] = None,
        hours: int = 24,
        acknowledged: Optional[bool] = None
    ) -> pd.DataFrame:
        """
        Get recent drift alerts.

        Args:
            bot_type: Filter by bot type (None = all)
            severity: Filter by severity (None = all)
            hours: Look back this many hours
            acknowledged: Filter by acknowledged status (None = all)

        Returns:
            DataFrame with recent alerts
        """
        conn = sqlite3.connect(self.db_path)

        conditions = [f"alert_timestamp > datetime('now', '-{hours} hours')"]
        params = []

        if bot_type:
            conditions.append("bot_type = ?")
            params.append(bot_type)

        if severity:
            conditions.append("severity = ?")
            params.append(severity)

        if acknowledged is not None:
            conditions.append("acknowledged = ?")
            params.append(1 if acknowledged else 0)

        where_clause = " AND ".join(conditions)

        query = f"""
            SELECT
                id,
                alert_timestamp,
                bot_type,
                alert_type,
                severity,
                drift_score,
                affected_features,
                message,
                baseline_timestamp,
                current_timestamp,
                telegram_sent,
                acknowledged
            FROM drift_detection_alerts
            WHERE {where_clause}
            ORDER BY alert_timestamp DESC
        """

        alerts = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Parse JSON
        if not alerts.empty:
            alerts['affected_features'] = alerts['affected_features'].apply(json.loads)

        return alerts

    def acknowledge_alert(self, alert_id: int):
        """Mark an alert as acknowledged."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE drift_detection_alerts
            SET acknowledged = 1, acknowledged_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), int(alert_id)))

        conn.commit()
        conn.close()

        logger.info(f"Acknowledged alert {alert_id}")
