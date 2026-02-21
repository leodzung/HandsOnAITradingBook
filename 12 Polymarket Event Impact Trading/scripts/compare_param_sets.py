#!/usr/bin/env python3
"""
Parameter Set Comparison Script

Compares performance of two parameter sets (e.g., current vs optimized)
on a holdout test set to validate optimization improvements.

Usage:
    python scripts/compare_param_sets.py \
        --config-a config/config_short_expiry.json \
        --config-b config/optimized/config_short_expiry_optimized.json \
        --bucket ultra_short \
        --holdout-months 2

    python scripts/compare_param_sets.py \
        --config-a config/config_short_expiry.json \
        --config-b config/optimized/config_short_expiry_optimized.json \
        --bucket short \
        --data-path data/REAL_labeled_from_alchemy.csv \
        --report-output reports/comparison_report.md
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.optimization.realistic_backtester import RealisticBacktester
from src.optimization.objective_functions import calculate_metrics, format_metrics_report
from src.optimization.param_spaces import get_baseline_params

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_params_from_config(config_path: str, bucket: str) -> dict:
    """
    Extract optimization parameters from config file.

    Args:
        config_path: Path to config JSON file
        bucket: Time bucket name

    Returns:
        Parameter dictionary
    """
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Extract parameters matching optimization structure
    params = {
        'take_profit_pct': config['risk_management']['take_profit_pct'][bucket],
        'stop_loss_pct': config['risk_management']['stop_loss_pct'][bucket],
        'max_slippage_bps': config['slippage_estimation']['max_slippage_bps'][bucket],
        'max_position_size': config['position_limits']['max_position_size'][bucket],
        'max_spread_pct': config['discovery']['max_spread_pct'][bucket],
        'min_volume': config['discovery']['min_volume'][bucket],
        'min_confidence': config['risk_management']['min_confidence'],
    }

    return params


def load_data(data_path: str, bucket: str, holdout_months: int = 2) -> tuple:
    """
    Load data and split into training (for context) and holdout test set.

    Args:
        data_path: Path to labeled data CSV
        bucket: Time bucket name
        holdout_months: Number of recent months to use for holdout test

    Returns:
        Tuple of (train_data, test_data)
    """
    logger.info(f"Loading data from {data_path}")
    df = pd.read_csv(data_path)

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

    # Add default features if not present
    if 'volume_24h' not in df.columns:
        df['volume_24h'] = 1000
    if 'spread_pct' not in df.columns:
        df['spread_pct'] = 5.0

    # Sort by date
    df = df.sort_values('block_timestamp')

    # Split into train and holdout
    cutoff_date = df['block_timestamp'].max() - timedelta(days=holdout_months * 30)
    train_data = df[df['block_timestamp'] < cutoff_date].copy()
    test_data = df[df['block_timestamp'] >= cutoff_date].copy()

    logger.info(f"Data split: {len(train_data)} training, {len(test_data)} holdout test")
    logger.info(f"Holdout period: {test_data['block_timestamp'].min()} to {test_data['block_timestamp'].max()}")

    return train_data, test_data


def run_comparison(
    params_a: dict,
    params_b: dict,
    test_data: pd.DataFrame,
    bucket: str,
    label_a: str = "Config A",
    label_b: str = "Config B",
    initial_balance: float = 1000.0
) -> dict:
    """
    Run backtest comparison between two parameter sets.

    Args:
        params_a: First parameter set
        params_b: Second parameter set
        test_data: Holdout test data
        bucket: Time bucket
        label_a: Label for first config
        label_b: Label for second config
        initial_balance: Starting balance

    Returns:
        Comparison results dictionary
    """
    logger.info(f"Running comparison: {label_a} vs {label_b}")

    # Backtest config A
    logger.info(f"Testing {label_a}...")
    backtester_a = RealisticBacktester(initial_balance=initial_balance)
    trades_a = backtester_a.backtest(test_data, params_a, bucket)
    trades_for_metrics_a = [
        {'pnl': t.net_pnl, 'outcome': t.outcome, 'timestamp': t.entry_time}
        for t in trades_a if not t.rejected
    ]
    metrics_a = calculate_metrics(trades_for_metrics_a, initial_balance)

    # Backtest config B
    logger.info(f"Testing {label_b}...")
    backtester_b = RealisticBacktester(initial_balance=initial_balance)
    trades_b = backtester_b.backtest(test_data, params_b, bucket)
    trades_for_metrics_b = [
        {'pnl': t.net_pnl, 'outcome': t.outcome, 'timestamp': t.entry_time}
        for t in trades_b if not t.rejected
    ]
    metrics_b = calculate_metrics(trades_for_metrics_b, initial_balance)

    # Calculate improvements
    improvements = {}
    for key in ['sharpe_ratio', 'max_drawdown', 'win_rate', 'profit_factor', 'total_return']:
        if key in metrics_a and key in metrics_b:
            val_a = metrics_a[key]
            val_b = metrics_b[key]

            if val_a != 0:
                if key == 'max_drawdown':  # Lower is better
                    pct_change = ((val_a - val_b) / val_a) * 100
                else:  # Higher is better
                    pct_change = ((val_b - val_a) / abs(val_a)) * 100
            else:
                pct_change = 0.0

            improvements[key] = pct_change

    return {
        'label_a': label_a,
        'label_b': label_b,
        'params_a': params_a,
        'params_b': params_b,
        'metrics_a': metrics_a,
        'metrics_b': metrics_b,
        'improvements': improvements,
        'trades_a': len(trades_for_metrics_a),
        'trades_b': len(trades_for_metrics_b),
        'rejected_a': len([t for t in trades_a if t.rejected]),
        'rejected_b': len([t for t in trades_b if t.rejected]),
    }


def generate_report(results: dict, output_path: str = None):
    """
    Generate comparison report in Markdown format.

    Args:
        results: Comparison results
        output_path: Optional file path to save report
    """
    report_lines = []

    # Header
    report_lines.append("# Parameter Comparison Report")
    report_lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"\n## Configuration Comparison")
    report_lines.append(f"\n**{results['label_a']}** vs **{results['label_b']}**")

    # Parameters
    report_lines.append("\n### Parameters")
    report_lines.append("\n| Parameter | Config A | Config B | Change |")
    report_lines.append("|-----------|----------|----------|--------|")

    for key in results['params_a'].keys():
        val_a = results['params_a'][key]
        val_b = results['params_b'][key]
        change = ((val_b - val_a) / val_a * 100) if val_a != 0 else 0
        change_str = f"{change:+.1f}%" if change != 0 else "-"

        report_lines.append(f"| {key} | {val_a} | {val_b} | {change_str} |")

    # Performance Metrics
    report_lines.append("\n### Performance Metrics")
    report_lines.append("\n| Metric | Config A | Config B | Improvement |")
    report_lines.append("|--------|----------|----------|-------------|")

    metric_display = {
        'sharpe_ratio': 'Sharpe Ratio',
        'max_drawdown': 'Max Drawdown',
        'win_rate': 'Win Rate',
        'profit_factor': 'Profit Factor',
        'total_return': 'Total Return',
        'num_trades': 'Total Trades',
    }

    for key, label in metric_display.items():
        val_a = results['metrics_a'].get(key, 0)
        val_b = results['metrics_b'].get(key, 0)
        improvement = results['improvements'].get(key, 0)

        # Format values
        if key in ['win_rate', 'total_return', 'max_drawdown']:
            val_a_str = f"{val_a:.2%}"
            val_b_str = f"{val_b:.2%}"
        elif key in ['sharpe_ratio', 'profit_factor']:
            val_a_str = f"{val_a:.3f}"
            val_b_str = f"{val_b:.3f}"
        else:
            val_a_str = f"{val_a}"
            val_b_str = f"{val_b}"

        improvement_str = f"{improvement:+.2f}%" if key != 'num_trades' else "-"

        # Add emoji for significant improvements
        if key != 'num_trades' and abs(improvement) > 10:
            if improvement > 0:
                improvement_str += " 🚀"
            else:
                improvement_str += " ⚠️"

        report_lines.append(f"| {label} | {val_a_str} | {val_b_str} | {improvement_str} |")

    # Trade Statistics
    report_lines.append("\n### Trade Statistics")
    report_lines.append(f"\n- **Config A**: {results['trades_a']} executed, {results['rejected_a']} rejected")
    report_lines.append(f"- **Config B**: {results['trades_b']} executed, {results['rejected_b']} rejected")

    # Summary
    report_lines.append("\n### Summary")

    sharpe_improvement = results['improvements'].get('sharpe_ratio', 0)
    dd_improvement = results['improvements'].get('max_drawdown', 0)

    if sharpe_improvement > 15 and dd_improvement > 10:
        verdict = "✅ **STRONG IMPROVEMENT** - Config B significantly outperforms Config A"
    elif sharpe_improvement > 5:
        verdict = "✅ **MODERATE IMPROVEMENT** - Config B shows better performance"
    elif sharpe_improvement > -5:
        verdict = "⚖️ **NEUTRAL** - Performance is similar between configs"
    else:
        verdict = "⚠️ **DEGRADATION** - Config A performs better than Config B"

    report_lines.append(f"\n{verdict}")

    # Recommendations
    report_lines.append("\n### Recommendations")

    if sharpe_improvement > 15:
        report_lines.append("\n✅ **Deploy Config B** - Strong validation on holdout data")
        report_lines.append("- Proceed with paper trading validation (2-3 weeks)")
        report_lines.append("- Monitor daily Sharpe and drawdown metrics")
        report_lines.append("- Set kill-switch if Sharpe drops >30% or drawdown >25%")
    elif sharpe_improvement > 5:
        report_lines.append("\n⚠️ **Cautious Deployment**")
        report_lines.append("- Paper trade Config B alongside Config A")
        report_lines.append("- Require 4-week validation period")
        report_lines.append("- Compare real-time performance before live deployment")
    else:
        report_lines.append("\n❌ **Do Not Deploy**")
        report_lines.append("- Optimization did not improve performance on holdout data")
        report_lines.append("- Consider: broader parameter ranges, more folds, or different objective")
        report_lines.append("- Stick with Config A for now")

    report_text = "\n".join(report_lines)

    # Print to console
    print("\n" + "=" * 70)
    print(report_text)
    print("=" * 70)

    # Save to file if requested
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(report_text)
        logger.info(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Compare two parameter sets on holdout test data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--config-a',
        type=str,
        required=True,
        help='Path to first config file (e.g., current parameters)'
    )

    parser.add_argument(
        '--config-b',
        type=str,
        required=True,
        help='Path to second config file (e.g., optimized parameters)'
    )

    parser.add_argument(
        '--bucket',
        type=str,
        required=True,
        choices=['ultra_short', 'short', 'medium'],
        help='Time bucket to compare'
    )

    parser.add_argument(
        '--data-path',
        type=str,
        default='data/REAL_labeled_from_alchemy.csv',
        help='Path to labeled data CSV'
    )

    parser.add_argument(
        '--holdout-months',
        type=int,
        default=2,
        help='Number of recent months for holdout test (default: 2)'
    )

    parser.add_argument(
        '--initial-balance',
        type=float,
        default=1000.0,
        help='Initial balance for backtesting (default: 1000.0)'
    )

    parser.add_argument(
        '--label-a',
        type=str,
        default='Current Config',
        help='Label for first config'
    )

    parser.add_argument(
        '--label-b',
        type=str,
        default='Optimized Config',
        help='Label for second config'
    )

    parser.add_argument(
        '--report-output',
        type=str,
        help='Optional path to save report (markdown format)'
    )

    args = parser.parse_args()

    try:
        # Load parameters from configs
        logger.info(f"Loading parameters from configs...")
        params_a = load_params_from_config(args.config_a, args.bucket)
        params_b = load_params_from_config(args.config_b, args.bucket)

        logger.info(f"\n{args.label_a} parameters:")
        print(json.dumps(params_a, indent=2))
        logger.info(f"\n{args.label_b} parameters:")
        print(json.dumps(params_b, indent=2))

        # Load data
        train_data, test_data = load_data(
            args.data_path,
            args.bucket,
            args.holdout_months
        )

        # Run comparison
        results = run_comparison(
            params_a=params_a,
            params_b=params_b,
            test_data=test_data,
            bucket=args.bucket,
            label_a=args.label_a,
            label_b=args.label_b,
            initial_balance=args.initial_balance
        )

        # Generate report
        generate_report(results, args.report_output)

        return 0

    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
