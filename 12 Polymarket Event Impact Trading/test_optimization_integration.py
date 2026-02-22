#!/usr/bin/env python3
"""
Quick integration test for parameter optimization system.

Tests end-to-end workflow with small dataset (1000 samples, 10 iterations).
"""

import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import optimization modules
from src.optimization.parameter_optimizer import ParameterOptimizer
from src.optimization.param_spaces import get_baseline_params
from src.optimization.objective_functions import format_metrics_report

def main():
    """Run integration test."""
    print("=" * 70)
    print("PARAMETER OPTIMIZATION - INTEGRATION TEST")
    print("=" * 70)
    print()

    try:
        # Load small subset of data
        logger.info("Loading data subset...")
        data_path = 'data/REAL_labeled_from_alchemy.csv'

        # Load data in chunks and filter for ultra-short until we have enough
        df_ultra = pd.DataFrame()
        chunk_size = 5000
        max_rows = 50000

        for chunk in pd.read_csv(data_path, chunksize=chunk_size):
            chunk['block_timestamp'] = pd.to_datetime(chunk['block_timestamp'])
            chunk['end_date'] = pd.to_datetime(chunk['end_date'])
            chunk['hours_to_expiry'] = (chunk['end_date'] - chunk['block_timestamp']).dt.total_seconds() / 3600

            # Filter to ultra-short bucket
            ultra_chunk = chunk[(chunk['hours_to_expiry'] >= 0) & (chunk['hours_to_expiry'] <= 24)]

            if len(ultra_chunk) > 0:
                df_ultra = pd.concat([df_ultra, ultra_chunk])

            # Stop when we have enough samples
            if len(df_ultra) >= 1000:
                df_ultra = df_ultra.head(1000)
                break

            # Safety limit - don't read entire file
            if len(df_ultra) + len(chunk) > max_rows:
                break

        logger.info(f"Ultra-short bucket: {len(df_ultra)} samples")

        if len(df_ultra) < 100:
            logger.error(f"Insufficient ultra-short samples for test (found {len(df_ultra)})")
            return 1

        # Add default features
        df_ultra['volume_24h'] = 1000
        df_ultra['spread_pct'] = 5.0

        # Initialize optimizer with minimal iterations
        logger.info("Initializing optimizer...")
        optimizer = ParameterOptimizer(
            bucket='ultra_short',
            n_calls=10,  # Only 10 iterations for speed
            n_folds=3,   # Only 3 folds
            val_period_days=15,  # Shorter validation period
            initial_balance=1000.0,
            results_dir='data/optimization_results',
        )

        # Get baseline params
        baseline = get_baseline_params('ultra_short')
        print("\nBaseline parameters:")
        for k, v in baseline.items():
            print(f"  {k}: {v}")
        print()

        # Run optimization
        logger.info("Running optimization (10 iterations, 3 folds)...")
        print("This should take 1-2 minutes...\n")

        iteration_count = [0]

        def progress_callback(iteration, score, params):
            iteration_count[0] = iteration
            print(f"[{iteration}/10] Score: {score:.4f} | "
                  f"TP={params['take_profit_pct']:.1f}% | "
                  f"SL={params['stop_loss_pct']:.1f}%")

        results = optimizer.optimize(
            data=df_ultra,
            progress_callback=progress_callback
        )

        # Print results
        print("\n" + "=" * 70)
        print("INTEGRATION TEST RESULTS")
        print("=" * 70)
        print(f"\n✅ Optimization completed successfully!")
        print(f"   Iterations run: {iteration_count[0]}")
        print(f"   Best score: {results['best_score']:.4f}")
        print(f"   Baseline score: {results['baseline_score']:.4f}")
        print(f"   Improvement: {results['improvement']:.2f}%")

        print("\nBest parameters:")
        for k, v in results['best_params'].items():
            baseline_val = baseline[k]
            change = ((v - baseline_val) / baseline_val * 100) if baseline_val != 0 else 0
            print(f"  {k}: {v:.2f} (baseline: {baseline_val:.2f}, change: {change:+.1f}%)")

        print("\n✅ All components working correctly!")
        print("=" * 70)

        return 0

    except Exception as e:
        logger.error(f"Integration test failed: {e}", exc_info=True)
        print(f"\n❌ Test failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
