"""
Bayesian parameter optimization with walk-forward validation.

Uses scikit-optimize for smart parameter search with temporal cross-validation
to prevent overfitting and ensure robust parameter selection.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable
from datetime import datetime
import json
from pathlib import Path

from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args

from src.optimization.param_spaces import (
    get_param_space, get_baseline_params, params_list_to_dict,
    validate_params, PARAM_NAMES
)
from src.optimization.objective_functions import (
    calculate_metrics, composite_score, multi_fold_score,
    filter_invalid_results, format_metrics_report
)
from src.optimization.realistic_backtester import RealisticBacktester
from src.utils.walk_forward_validator import WalkForwardValidator

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    Bayesian parameter optimizer with walk-forward validation.

    Uses Gaussian process optimization to efficiently search parameter space
    while validating on multiple temporal folds to prevent overfitting.
    """

    def __init__(
        self,
        bucket: str,
        n_calls: int = 150,
        n_folds: int = 5,
        val_period_days: int = 30,
        initial_balance: float = 1000.0,
        random_state: int = 42,
        results_dir: str = 'data/optimization_results',
    ):
        """
        Initialize parameter optimizer.

        Args:
            bucket: Time bucket to optimize ('ultra_short', 'short', 'medium')
            n_calls: Number of Bayesian optimization iterations
            n_folds: Number of walk-forward folds
            val_period_days: Validation period length in days
            initial_balance: Starting balance for backtesting
            random_state: Random seed for reproducibility
            results_dir: Directory to save optimization results
        """
        self.bucket = bucket
        self.n_calls = n_calls
        self.n_folds = n_folds
        self.val_period_days = val_period_days
        self.initial_balance = initial_balance
        self.random_state = random_state
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Get parameter space for this bucket
        self.param_space = get_param_space(bucket)
        self.baseline_params = get_baseline_params(bucket)

        # Initialize walk-forward validator
        self.validator = WalkForwardValidator(
            n_folds=n_folds,
            val_period_days=val_period_days,
            min_train_samples=100,
            min_val_samples=20,
        )

        # Optimization state
        self.best_params = None
        self.best_score = -np.inf
        self.optimization_history = []
        self.fold_results = []

        logger.info(f"ParameterOptimizer initialized: bucket={bucket}, "
                   f"n_calls={n_calls}, n_folds={n_folds}")

    def optimize(
        self,
        data: pd.DataFrame,
        ml_predictions: Optional[pd.Series] = None,
        ml_confidence: Optional[pd.Series] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Dict:
        """
        Run Bayesian optimization with walk-forward validation.

        Args:
            data: Trading data with features and labels
            ml_predictions: Optional ML model predictions
            ml_confidence: Optional ML confidence scores
            progress_callback: Optional callback(iteration, score, params)

        Returns:
            Dict with:
                - best_params: Optimized parameter dictionary
                - best_score: Best composite score achieved
                - baseline_score: Baseline parameter score
                - improvement: Score improvement over baseline
                - fold_results: Per-fold performance metrics
                - optimization_history: Full optimization trace
        """
        logger.info(f"Starting optimization for bucket={self.bucket}")
        logger.info(f"Dataset: {len(data)} samples")

        # Ensure data is sorted by timestamp
        if 'block_timestamp' in data.columns:
            data = data.sort_values('block_timestamp').copy()
            date_column = 'block_timestamp'
        elif 'entry_date' in data.columns:
            data = data.sort_values('entry_date').copy()
            date_column = 'entry_date'
        else:
            raise ValueError("Data must have 'block_timestamp' or 'entry_date' column")

        # Filter to bucket's time range
        data = self._filter_to_bucket(data)
        logger.info(f"Filtered to bucket {self.bucket}: {len(data)} samples")

        if len(data) < 100:
            raise ValueError(f"Insufficient data for bucket {self.bucket}: {len(data)} samples")

        # Check temporal span
        date_range = (data[date_column].max() - data[date_column].min()).days
        logger.info(f"Data temporal span: {date_range} days")

        # If insufficient temporal diversity, switch to simple validation
        if date_range < self.val_period_days * 2:
            logger.warning(f"Temporal span ({date_range} days) insufficient for walk-forward validation")
            logger.warning(f"Switching to simple train/test split (80/20)")
            self.use_simple_split = True
        else:
            self.use_simple_split = False

        # Store data for objective function
        self.data = data
        self.ml_predictions = ml_predictions
        self.ml_confidence = ml_confidence
        self.progress_callback = progress_callback

        # Define objective function for Bayesian optimization
        @use_named_args(self.param_space)
        def objective(**params_dict):
            """
            Objective function for Bayesian optimization.

            Evaluates parameter set across all walk-forward folds
            and returns negative score (minimization framework).
            """
            # Validate parameters
            is_valid, error_msg = validate_params(params_dict)
            if not is_valid:
                logger.warning(f"Invalid parameters: {error_msg}")
                return 1e6  # Large penalty for invalid params

            # Evaluate on all folds
            fold_metrics = []
            for fold_idx in range(self.n_folds):
                metrics = self._evaluate_fold(fold_idx, params_dict, date_column)
                if metrics is None:
                    # Fold failed - penalize
                    return 1e6

                # Check if results are valid
                if not filter_invalid_results(metrics):
                    logger.warning(f"Fold {fold_idx} produced invalid results")
                    return 1e6

                fold_metrics.append(metrics)

            # Calculate multi-fold score
            total_score, aggregated_metrics = multi_fold_score(fold_metrics)

            # Update best if improved
            if total_score > self.best_score:
                self.best_score = total_score
                self.best_params = params_dict.copy()
                logger.info(f"New best score: {total_score:.4f}")
                logger.info(f"Best params: {params_dict}")

            # Store history
            self.optimization_history.append({
                'iteration': len(self.optimization_history),
                'params': params_dict.copy(),
                'total_score': total_score,
                'aggregated_metrics': aggregated_metrics,
                'fold_metrics': fold_metrics,
            })

            # Progress callback
            if self.progress_callback:
                self.progress_callback(
                    len(self.optimization_history),
                    total_score,
                    params_dict
                )

            # Return negative score (Bayesian opt minimizes)
            return -total_score

        # Evaluate baseline parameters first
        logger.info("Evaluating baseline parameters...")
        baseline_score = self._evaluate_params(self.baseline_params, date_column)

        # Initialize best with baseline if optimization hasn't found anything
        if self.best_params is None:
            self.best_params = self.baseline_params.copy()
            self.best_score = baseline_score
            logger.info(f"Initialized best params with baseline: score={baseline_score:.4f}")

        # Run Bayesian optimization
        logger.info(f"Starting Bayesian optimization: {self.n_calls} iterations")
        try:
            result = gp_minimize(
                objective,
                self.param_space,
                n_calls=self.n_calls,
                random_state=self.random_state,
                n_initial_points=10,  # Random exploration first
                verbose=False,
            )
        except Exception as e:
            logger.error(f"Bayesian optimization failed: {e}", exc_info=True)
            logger.warning("Using baseline parameters as best")

        # Compile results
        results = {
            'bucket': self.bucket,
            'best_params': self.best_params,
            'best_score': self.best_score,
            'baseline_params': self.baseline_params,
            'baseline_score': baseline_score,
            'improvement': ((self.best_score - baseline_score) / baseline_score * 100) if baseline_score > 0 else 0,
            'n_calls': self.n_calls,
            'n_folds': self.n_folds,
            'optimization_history': self.optimization_history,
            'timestamp': datetime.now().isoformat(),
        }

        # Save results
        self._save_results(results)

        logger.info(f"Optimization complete!")
        logger.info(f"Best score: {self.best_score:.4f}")
        logger.info(f"Baseline score: {baseline_score:.4f}")
        logger.info(f"Improvement: {results['improvement']:.2f}%")

        return results

    def _evaluate_params(
        self,
        params_dict: Dict,
        date_column: str
    ) -> float:
        """
        Evaluate parameter set across all folds.

        Args:
            params_dict: Parameter dictionary
            date_column: Date column name

        Returns:
            Total score across folds
        """
        fold_metrics = []
        for fold_idx in range(self.n_folds):
            metrics = self._evaluate_fold(fold_idx, params_dict, date_column)
            if metrics and filter_invalid_results(metrics):
                fold_metrics.append(metrics)

        if not fold_metrics:
            logger.warning(f"No valid folds for params: {params_dict}")
            return 0.0

        # If we have at least one valid fold, compute score
        # (multi_fold_score handles single fold case)
        total_score, _ = multi_fold_score(fold_metrics)
        logger.debug(f"Evaluated params: {len(fold_metrics)} valid folds, score={total_score:.4f}")
        return total_score

    def _evaluate_fold(
        self,
        fold_idx: int,
        params_dict: Dict,
        date_column: str
    ) -> Optional[Dict]:
        """
        Evaluate parameters on a single walk-forward fold.

        Args:
            fold_idx: Fold index
            params_dict: Parameter dictionary
            date_column: Date column name

        Returns:
            Performance metrics dictionary or None if fold failed
        """
        try:
            # Use simple split if temporal diversity is insufficient
            if hasattr(self, 'use_simple_split') and self.use_simple_split:
                # Use simple 80/20 split (same for all "folds")
                split_idx = int(len(self.data) * 0.8)
                val_data = self.data.iloc[split_idx:].copy()

                if len(val_data) < 20:
                    logger.warning(f"Insufficient data for simple split ({len(val_data)} samples)")
                    return None

                logger.debug(f"Fold {fold_idx}: Using simple split, val_size={len(val_data)}")
            else:
                # Get train/val split for this fold
                # Create dummy y for split (we don't use it for backtest)
                y_dummy = pd.Series(0, index=self.data.index)

                try:
                    splits = self.validator.split(self.data, y_dummy, date_column=date_column)
                except ValueError as e:
                    logger.warning(f"Walk-forward validation failed: {e}")
                    logger.warning(f"Falling back to simple train/test split")
                    # Use simple 80/20 split
                    split_idx = int(len(self.data) * 0.8)
                    val_data = self.data.iloc[split_idx:].copy()

                    if len(val_data) < 20:
                        logger.warning(f"Insufficient data for simple split ({len(val_data)} samples)")
                        return None
                else:
                    if not splits or len(splits) == 0:
                        logger.warning(f"No splits generated, using simple train/test split")
                        split_idx = int(len(self.data) * 0.8)
                        val_data = self.data.iloc[split_idx:].copy()
                    else:
                        if fold_idx >= len(splits):
                            logger.warning(f"Fold {fold_idx} exceeds available splits ({len(splits)} folds)")
                            return None

                        train_idx, val_idx = splits[fold_idx]
                        val_data = self.data.iloc[val_idx].copy()

                    if len(val_data) < 20:
                        logger.warning(f"Fold {fold_idx}: insufficient validation data ({len(val_data)} samples)")
                        return None

            # Run backtest on validation data
            backtester = RealisticBacktester(
                initial_balance=self.initial_balance,
                fee_pct=0.01,
                min_balance_reserve=50.0,
            )

            trades = backtester.backtest(
                data=val_data,
                params=params_dict,
                bucket=self.bucket,
                ml_predictions=self.ml_predictions.iloc[val_idx] if self.ml_predictions is not None and len(splits) > 0 else None,
                ml_confidence=self.ml_confidence.iloc[val_idx] if self.ml_confidence is not None and len(splits) > 0 else None,
            )

            # Convert trades to metrics format
            trades_for_metrics = [
                {
                    'pnl': t.net_pnl,
                    'outcome': t.outcome,
                    'timestamp': t.entry_time,
                }
                for t in trades if not t.rejected
            ]

            # Calculate performance metrics
            metrics = calculate_metrics(trades_for_metrics, self.initial_balance)

            logger.debug(f"Fold {fold_idx}: {metrics['num_trades']} trades, "
                        f"Sharpe={metrics['sharpe_ratio']:.3f}, "
                        f"Win rate={metrics['win_rate']:.2%}")

            return metrics

        except Exception as e:
            logger.error(f"Error evaluating fold {fold_idx}: {e}", exc_info=True)
            return None

    def _filter_to_bucket(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Filter data to bucket's time range.

        Args:
            data: Full dataset

        Returns:
            Filtered dataset for this bucket
        """
        # Calculate hours to expiry
        if 'block_timestamp' in data.columns and 'end_date' in data.columns:
            entry_time = pd.to_datetime(data['block_timestamp'])
            end_time = pd.to_datetime(data['end_date'])
            hours_to_expiry = (end_time - entry_time).dt.total_seconds() / 3600

            # Filter by bucket
            if self.bucket == 'ultra_short':
                mask = (hours_to_expiry >= 0) & (hours_to_expiry <= 24)
            elif self.bucket == 'short':
                mask = (hours_to_expiry > 24) & (hours_to_expiry <= 72)
            elif self.bucket == 'medium':
                mask = (hours_to_expiry > 72) & (hours_to_expiry <= 168)
            else:
                raise ValueError(f"Invalid bucket: {self.bucket}")

            return data[mask].copy()
        else:
            # If time data not available, return all
            logger.warning("Cannot filter by time - missing timestamp columns")
            return data

    def _save_results(self, results: Dict):
        """
        Save optimization results to disk.

        Args:
            results: Results dictionary
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.bucket}_optimization_{timestamp}.json"
        filepath = self.results_dir / filename

        # Convert numpy types to Python types for JSON serialization
        results_serializable = self._make_serializable(results)

        with open(filepath, 'w') as f:
            json.dump(results_serializable, f, indent=2)

        logger.info(f"Results saved to {filepath}")

    def _make_serializable(self, obj):
        """Convert numpy/pandas types to JSON-serializable types."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        else:
            return obj

    def export_config(
        self,
        results: Dict,
        output_path: str,
        base_config_path: Optional[str] = None
    ):
        """
        Export optimized parameters as config file.

        Args:
            results: Optimization results
            output_path: Output config file path
            base_config_path: Optional base config to merge with
        """
        if base_config_path:
            with open(base_config_path, 'r') as f:
                config = json.load(f)
        else:
            config = {}

        # Update config with optimized parameters
        best_params = results['best_params']

        # Map to config structure
        config.setdefault('position_limits', {}).setdefault('max_position_size', {})
        config['position_limits']['max_position_size'][self.bucket] = best_params['max_position_size']

        config.setdefault('risk_management', {}).setdefault('take_profit_pct', {})
        config['risk_management']['take_profit_pct'][self.bucket] = best_params['take_profit_pct']

        config.setdefault('risk_management', {}).setdefault('stop_loss_pct', {})
        config['risk_management']['stop_loss_pct'][self.bucket] = best_params['stop_loss_pct']

        config.setdefault('slippage_estimation', {}).setdefault('max_slippage_bps', {})
        config['slippage_estimation']['max_slippage_bps'][self.bucket] = best_params['max_slippage_bps']

        config.setdefault('discovery', {}).setdefault('max_spread_pct', {})
        config['discovery']['max_spread_pct'][self.bucket] = best_params['max_spread_pct']

        config.setdefault('discovery', {}).setdefault('min_volume', {})
        config['discovery']['min_volume'][self.bucket] = best_params['min_volume']

        config.setdefault('risk_management', {})['min_confidence'] = best_params['min_confidence']

        # Save updated config
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Optimized config exported to {output_path}")
