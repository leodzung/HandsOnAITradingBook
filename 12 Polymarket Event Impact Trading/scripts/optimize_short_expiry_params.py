#!/usr/bin/env python3
"""
Parameter Optimization CLI for Short-Expiry Trader

Runs Bayesian optimization to find optimal trading parameters
for each time bucket (ultra_short, short, medium) using walk-forward
validation and realistic backtesting.

Usage:
    python scripts/optimize_short_expiry_params.py --bucket ultra_short --n-calls 150
    python scripts/optimize_short_expiry_params.py --bucket short --n-calls 150 --dry-run
    python scripts/optimize_short_expiry_params.py --bucket medium --n-calls 150

Example with Telegram notifications:
    python scripts/optimize_short_expiry_params.py --bucket ultra_short --notify
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization.parameter_optimizer import ParameterOptimizer
from src.optimization.param_spaces import get_baseline_params, BASELINE_PARAMS
from src.optimization.objective_functions import format_metrics_report

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/optimization.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


def send_telegram_message(message: str, config_path: str = 'config/config_short_expiry.json'):
    """Send Telegram notification if configured."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        if config.get('telegram', {}).get('enabled', False):
            import requests
            bot_token = config['telegram']['bot_token']
            chat_id = config['telegram']['chat_id']
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.warning(f"Failed to send Telegram notification: {e}")


def load_data(data_path: str, bucket: str) -> pd.DataFrame:
    """
    Load and prepare data for optimization.

    Args:
        data_path: Path to labeled data CSV
        bucket: Time bucket name

    Returns:
        Prepared DataFrame
    """
    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)

    # Ensure required columns exist
    required_cols = ['condition_id', 'block_timestamp', 'trade_price', 'end_date', 'outcome', 'label']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")

    # Parse dates
    df['block_timestamp'] = pd.to_datetime(df['block_timestamp'])
    df['end_date'] = pd.to_datetime(df['end_date'])

    # Calculate hours to expiry
    df['hours_to_expiry'] = (df['end_date'] - df['block_timestamp']).dt.total_seconds() / 3600

    # Filter to bucket
    if bucket == 'ultra_short':
        df = df[(df['hours_to_expiry'] >= 0) & (df['hours_to_expiry'] <= 24)]
    elif bucket == 'short':
        df = df[(df['hours_to_expiry'] > 24) & (df['hours_to_expiry'] <= 72)]
    elif bucket == 'medium':
        df = df[(df['hours_to_expiry'] > 72) & (df['hours_to_expiry'] <= 168)]
    else:
        raise ValueError(f"Invalid bucket: {bucket}")

    # Add default features if not present (for basic backtesting)
    if 'volume_24h' not in df.columns:
        df['volume_24h'] = 1000  # Default volume
    if 'spread_pct' not in df.columns:
        df['spread_pct'] = 5.0  # Default 5% spread

    logger.info(f"Loaded {len(df)} samples for bucket {bucket}")
    logger.info(f"Date range: {df['block_timestamp'].min()} to {df['block_timestamp'].max()}")

    return df


def main():
    parser = argparse.ArgumentParser(
        description='Optimize short-expiry trader parameters using Bayesian optimization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize ultra-short bucket with 150 iterations
  python scripts/optimize_short_expiry_params.py --bucket ultra_short --n-calls 150

  # Quick test run with 20 iterations
  python scripts/optimize_short_expiry_params.py --bucket ultra_short --n-calls 20 --dry-run

  # Optimize with Telegram notifications
  python scripts/optimize_short_expiry_params.py --bucket short --notify

  # Use custom data file
  python scripts/optimize_short_expiry_params.py --bucket medium --data-path data/custom_labels.csv
        """
    )

    parser.add_argument(
        '--bucket',
        type=str,
        required=True,
        choices=['ultra_short', 'short', 'medium'],
        help='Time bucket to optimize'
    )

    parser.add_argument(
        '--n-calls',
        type=int,
        default=150,
        help='Number of Bayesian optimization iterations (default: 150)'
    )

    parser.add_argument(
        '--n-folds',
        type=int,
        default=5,
        help='Number of walk-forward validation folds (default: 5)'
    )

    parser.add_argument(
        '--val-period-days',
        type=int,
        default=30,
        help='Validation period length in days (default: 30)'
    )

    parser.add_argument(
        '--data-path',
        type=str,
        default='data/REAL_labeled_from_alchemy.csv',
        help='Path to labeled data CSV (default: data/REAL_labeled_from_alchemy.csv)'
    )

    parser.add_argument(
        '--config-path',
        type=str,
        default='config/config_short_expiry.json',
        help='Path to base config file (default: config/config_short_expiry.json)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/optimization_results',
        help='Output directory for results (default: data/optimization_results)'
    )

    parser.add_argument(
        '--initial-balance',
        type=float,
        default=1000.0,
        help='Initial balance for backtesting (default: 1000.0)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test run with reduced dataset (1000 samples)'
    )

    parser.add_argument(
        '--notify',
        action='store_true',
        help='Send Telegram notifications for progress'
    )

    parser.add_argument(
        '--export-config',
        action='store_true',
        help='Export optimized parameters to config file'
    )

    args = parser.parse_args()

    # Print header
    print("=" * 70)
    print("SHORT-EXPIRY TRADER PARAMETER OPTIMIZATION")
    print("=" * 70)
    print(f"Bucket:           {args.bucket}")
    print(f"Iterations:       {args.n_calls}")
    print(f"Folds:            {args.n_folds}")
    print(f"Val period:       {args.val_period_days} days")
    print(f"Initial balance:  ${args.initial_balance}")
    print(f"Dry run:          {args.dry_run}")
    print("=" * 70)
    print()

    # Send start notification
    if args.notify:
        send_telegram_message(
            f"🔍 *Parameter Optimization Started*\n"
            f"Bucket: `{args.bucket}`\n"
            f"Iterations: {args.n_calls}\n"
            f"Folds: {args.n_folds}",
            args.config_path
        )

    try:
        # Load data
        data = load_data(args.data_path, args.bucket)

        # Dry run mode - use subset
        if args.dry_run:
            data = data.sample(n=min(1000, len(data)), random_state=42)
            logger.info(f"DRY RUN: Using {len(data)} samples")

        # Print baseline parameters
        baseline = get_baseline_params(args.bucket)
        print("\nBASELINE PARAMETERS:")
        print(json.dumps(baseline, indent=2))
        print()

        # Initialize optimizer
        optimizer = ParameterOptimizer(
            bucket=args.bucket,
            n_calls=args.n_calls,
            n_folds=args.n_folds,
            val_period_days=args.val_period_days,
            initial_balance=args.initial_balance,
            results_dir=args.output_dir,
        )

        # Progress callback
        last_notification_time = datetime.now()

        def progress_callback(iteration, score, params):
            nonlocal last_notification_time
            print(f"\n[Iteration {iteration}/{args.n_calls}] Score: {score:.4f}")
            print(f"  Params: TP={params['take_profit_pct']:.1f}%, "
                  f"SL={params['stop_loss_pct']:.1f}%, "
                  f"Slippage={params['max_slippage_bps']:.0f}bps")

            # Send periodic updates every 30 iterations or if new best
            if args.notify:
                now = datetime.now()
                if iteration % 30 == 0 or score == optimizer.best_score:
                    if (now - last_notification_time).seconds >= 300:  # At most every 5 min
                        send_telegram_message(
                            f"📊 *Optimization Progress*\n"
                            f"Bucket: `{args.bucket}`\n"
                            f"Iteration: {iteration}/{args.n_calls}\n"
                            f"Best score: {optimizer.best_score:.4f}",
                            args.config_path
                        )
                        last_notification_time = now

        # Run optimization
        logger.info("Starting optimization...")
        results = optimizer.optimize(
            data=data,
            progress_callback=progress_callback
        )

        # Print results
        print("\n" + "=" * 70)
        print("OPTIMIZATION COMPLETE")
        print("=" * 70)
        print(f"\nBest Score:       {results['best_score']:.4f}")
        print(f"Baseline Score:   {results['baseline_score']:.4f}")
        print(f"Improvement:      {results['improvement']:.2f}%")
        print(f"\nBest Parameters:")
        print(json.dumps(results['best_params'], indent=2))
        print()

        # Export config if requested
        if args.export_config:
            output_config_path = f"config/optimized/config_short_expiry_{args.bucket}_optimized.json"
            Path(output_config_path).parent.mkdir(parents=True, exist_ok=True)

            optimizer.export_config(
                results=results,
                output_path=output_config_path,
                base_config_path=args.config_path
            )
            print(f"✓ Optimized config exported to: {output_config_path}")

        # Send completion notification
        if args.notify:
            improvement_emoji = "🚀" if results['improvement'] > 15 else "✅"
            send_telegram_message(
                f"{improvement_emoji} *Optimization Complete*\n"
                f"Bucket: `{args.bucket}`\n"
                f"Best score: {results['best_score']:.4f}\n"
                f"Improvement: {results['improvement']:.2f}%\n"
                f"TP: {results['best_params']['take_profit_pct']:.1f}%\n"
                f"SL: {results['best_params']['stop_loss_pct']:.1f}%",
                args.config_path
            )

        print("\n✓ Optimization completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)

        if args.notify:
            send_telegram_message(
                f"❌ *Optimization Failed*\n"
                f"Bucket: `{args.bucket}`\n"
                f"Error: {str(e)[:200]}",
                args.config_path
            )

        print(f"\n✗ Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
