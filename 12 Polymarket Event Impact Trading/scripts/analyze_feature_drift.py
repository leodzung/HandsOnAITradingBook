#!/usr/bin/env python3
"""
Feature Drift Analysis CLI Tool

Provides command-line interface for analyzing feature importance drift
across training runs.

Usage:
    # Analyze drift for specific bot
    python scripts/analyze_feature_drift.py --bot-type short_expiry

    # Compare current vs specific baseline
    python scripts/analyze_feature_drift.py --bot-type price_level --baseline 2026-02-15

    # Generate drift report
    python scripts/analyze_feature_drift.py --bot-type event --export drift_report.json

    # Plot feature importance timeline
    python scripts/analyze_feature_drift.py --bot-type short_expiry --plot

Author: AI Trading System
Date: 2026-02-21
"""

import sys
import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.feature_importance_tracker import FeatureImportanceTracker
from src.ml.drift_detector import DriftDetector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def plot_importance_timeline(history: pd.DataFrame, bot_type: str, output_file: str = None):
    """
    Plot feature importance over time.

    Args:
        history: DataFrame from get_importance_history()
        bot_type: Bot type for title
        output_file: Optional file to save plot
    """
    # Get top 10 features (by average importance)
    top_features = (
        history.groupby('feature_name')['normalized_importance']
        .mean()
        .nlargest(10)
        .index
        .tolist()
    )

    # Filter to top features
    plot_data = history[history['feature_name'].isin(top_features)]

    # Create pivot table (features × timestamps)
    pivot = plot_data.pivot(
        index='training_timestamp',
        columns='feature_name',
        values='normalized_importance'
    )

    # Plot
    fig, ax = plt.subplots(figsize=(14, 8))

    for feature in top_features:
        if feature in pivot.columns:
            ax.plot(pivot.index, pivot[feature], marker='o', label=feature, linewidth=2)

    ax.set_xlabel('Training Timestamp', fontsize=12)
    ax.set_ylabel('Normalized Importance', fontsize=12)
    ax.set_title(f'Feature Importance Timeline - {bot_type}', fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)

    # Rotate x-axis labels
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Plot saved to {output_file}")
    else:
        plt.show()

    plt.close()


def plot_rank_heatmap(history: pd.DataFrame, bot_type: str, output_file: str = None):
    """
    Plot heatmap of feature rankings over time.

    Args:
        history: DataFrame from get_importance_history()
        bot_type: Bot type for title
        output_file: Optional file to save plot
    """
    # Get top 15 features
    top_features = (
        history.groupby('feature_name')['normalized_importance']
        .mean()
        .nlargest(15)
        .index
        .tolist()
    )

    # Filter to top features
    plot_data = history[history['feature_name'].isin(top_features)]

    # Create pivot table (features × timestamps)
    pivot = plot_data.pivot(
        index='feature_name',
        columns='training_timestamp',
        values='importance_rank'
    )

    # Reorder by average rank
    avg_rank = pivot.mean(axis=1).sort_values()
    pivot = pivot.loc[avg_rank.index]

    # Plot
    fig, ax = plt.subplots(figsize=(14, 10))

    sns.heatmap(
        pivot,
        cmap='RdYlGn_r',  # Red=high rank (bad), Green=low rank (good)
        annot=True,
        fmt='.0f',
        cbar_kws={'label': 'Importance Rank'},
        ax=ax
    )

    ax.set_xlabel('Training Timestamp', fontsize=12)
    ax.set_ylabel('Feature Name', fontsize=12)
    ax.set_title(f'Feature Rank Stability Heatmap - {bot_type}', fontsize=14, fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        logger.info(f"Heatmap saved to {output_file}")
    else:
        plt.show()

    plt.close()


def analyze_drift(bot_type: str, baseline_strategy: str = 'ewma', lookback_runs: int = 5):
    """
    Analyze drift for a bot and print detailed report.

    Args:
        bot_type: Bot type to analyze
        baseline_strategy: Baseline strategy ('ewma', 'latest_n', 'best_auc')
        lookback_runs: Number of runs for baseline
    """
    detector = DriftDetector()

    logger.info(f"\n{'='*70}")
    logger.info(f"FEATURE DRIFT ANALYSIS - {bot_type.upper()}")
    logger.info(f"{'='*70}")
    logger.info(f"Baseline Strategy: {baseline_strategy}")
    logger.info(f"Lookback Runs: {lookback_runs}")
    logger.info(f"{'='*70}\n")

    # Detect drift
    alerts = detector.detect_drift(bot_type, baseline_strategy, lookback_runs)

    if not alerts:
        logger.info("✅ No drift detected - feature importance is stable")
        return

    # Group alerts by severity
    critical = [a for a in alerts if a['severity'] == 'critical']
    warning = [a for a in alerts if a['severity'] == 'warning']
    info = [a for a in alerts if a['severity'] == 'info']

    # Print summary
    logger.info(f"DRIFT SUMMARY:")
    logger.info(f"  Critical: {len(critical)}")
    logger.info(f"  Warning:  {len(warning)}")
    logger.info(f"  Info:     {len(info)}")
    logger.info("")

    # Print critical alerts
    if critical:
        logger.info(f"🚨 CRITICAL ALERTS:")
        for alert in critical:
            logger.info(f"  Type: {alert['alert_type']}")
            logger.info(f"  Score: {alert['drift_score']:.3f}")
            logger.info(f"  Message: {alert['message']}")
            logger.info(f"  Affected Features: {', '.join(alert['affected_features'][:5])}")
            logger.info("")

    # Print warning alerts
    if warning:
        logger.info(f"⚠️  WARNING ALERTS:")
        for alert in warning:
            logger.info(f"  Type: {alert['alert_type']}")
            logger.info(f"  Score: {alert['drift_score']:.3f}")
            logger.info(f"  Message: {alert['message']}")
            logger.info(f"  Affected Features: {', '.join(alert['affected_features'][:5])}")
            logger.info("")

    # Print info alerts
    if info:
        logger.info(f"ℹ️  INFO ALERTS:")
        for alert in info:
            logger.info(f"  Message: {alert['message']}")
            logger.info("")


def compare_baselines(bot_type: str, timestamp1: str, timestamp2: str):
    """
    Compare feature importance between two specific timestamps.

    Args:
        bot_type: Bot type to compare
        timestamp1: First timestamp
        timestamp2: Second timestamp
    """
    tracker = FeatureImportanceTracker()

    logger.info(f"\n{'='*70}")
    logger.info(f"BASELINE COMPARISON - {bot_type.upper()}")
    logger.info(f"{'='*70}")
    logger.info(f"Timestamp 1: {timestamp1}")
    logger.info(f"Timestamp 2: {timestamp2}")
    logger.info(f"{'='*70}\n")

    # Get importance for both timestamps
    import sqlite3
    conn = sqlite3.connect(tracker.db_path)

    query = """
        SELECT feature_name, normalized_importance, importance_rank
        FROM feature_importance_history
        WHERE bot_type = ? AND training_timestamp = ?
        AND validation_fold_id IS NULL
        ORDER BY importance_rank
    """

    df1 = pd.read_sql_query(query, conn, params=(bot_type, timestamp1))
    df2 = pd.read_sql_query(query, conn, params=(bot_type, timestamp2))
    conn.close()

    if df1.empty or df2.empty:
        logger.error("One or both timestamps have no data")
        return

    # Merge on feature name
    merged = df1.merge(
        df2,
        on='feature_name',
        how='outer',
        suffixes=('_1', '_2')
    ).fillna(0)

    # Calculate changes
    merged['importance_change'] = merged['normalized_importance_2'] - merged['normalized_importance_1']
    merged['rank_change'] = merged['importance_rank_1'] - merged['importance_rank_2']  # Negative = worse rank

    # Sort by absolute importance change
    merged = merged.sort_values('importance_change', key=abs, ascending=False)

    # Print top changes
    logger.info("TOP 10 IMPORTANCE CHANGES:")
    logger.info(f"{'Feature':<30} {'Δ Importance':<15} {'Δ Rank':<10}")
    logger.info("-" * 70)

    for _, row in merged.head(10).iterrows():
        logger.info(
            f"{row['feature_name']:<30} "
            f"{row['importance_change']:>+14.4f} "
            f"{row['rank_change']:>+9.0f}"
        )


def export_report(bot_type: str, output_file: str, format: str = 'json'):
    """
    Export drift analysis report to file.

    Args:
        bot_type: Bot type to analyze
        output_file: Output file path
        format: Output format ('json' or 'csv')
    """
    detector = DriftDetector()
    tracker = FeatureImportanceTracker()

    # Get drift alerts
    alerts = detector.detect_drift(bot_type)

    # Get recent history
    history = tracker.get_importance_history(bot_type, last_n_runs=10)

    # Get latest importance
    latest = tracker.get_latest_importance(bot_type)

    report = {
        'bot_type': bot_type,
        'timestamp': datetime.now().isoformat(),
        'alerts': alerts,
        'latest_importance': latest.to_dict(orient='records') if not latest.empty else [],
        'history_summary': {
            'num_runs': len(history['training_timestamp'].unique()),
            'num_features': len(history['feature_name'].unique()),
            'date_range': {
                'start': history['training_timestamp'].min() if not history.empty else None,
                'end': history['training_timestamp'].max() if not history.empty else None
            }
        }
    }

    if format == 'json':
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report exported to {output_file}")

    elif format == 'csv':
        # Export latest importance as CSV
        if not latest.empty:
            latest.to_csv(output_file, index=False)
            logger.info(f"Latest importance exported to {output_file}")
        else:
            logger.warning("No latest importance data to export")

    else:
        logger.error(f"Unknown format: {format}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze feature importance drift for ML trading models',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --bot-type short_expiry
  %(prog)s --bot-type price_level --baseline 2026-02-15T10:30:00
  %(prog)s --bot-type event --export report.json
  %(prog)s --bot-type short_expiry --plot --output timeline.png
        """
    )

    parser.add_argument(
        '--bot-type',
        required=True,
        choices=['event', 'price_level', 'short_expiry', 'walk_forward'],
        help='Bot type to analyze'
    )

    parser.add_argument(
        '--baseline',
        help='Specific baseline timestamp to compare against (ISO format)'
    )

    parser.add_argument(
        '--baseline-strategy',
        default='ewma',
        choices=['ewma', 'latest_n', 'best_auc'],
        help='Baseline computation strategy (default: ewma)'
    )

    parser.add_argument(
        '--lookback',
        type=int,
        default=5,
        help='Number of runs to look back for baseline (default: 5)'
    )

    parser.add_argument(
        '--export',
        help='Export drift report to file (JSON or CSV)'
    )

    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate importance timeline plot'
    )

    parser.add_argument(
        '--heatmap',
        action='store_true',
        help='Generate rank stability heatmap'
    )

    parser.add_argument(
        '--output',
        help='Output file for plots (default: show in window)'
    )

    parser.add_argument(
        '--compare',
        help='Second timestamp to compare against (requires --baseline)'
    )

    args = parser.parse_args()

    try:
        # Compare two specific timestamps
        if args.compare:
            if not args.baseline:
                parser.error("--compare requires --baseline")
            compare_baselines(args.bot_type, args.baseline, args.compare)
            return

        # Export report
        if args.export:
            format = 'json' if args.export.endswith('.json') else 'csv'
            export_report(args.bot_type, args.export, format)
            return

        # Generate plots
        if args.plot or args.heatmap:
            tracker = FeatureImportanceTracker()
            history = tracker.get_importance_history(args.bot_type, last_n_runs=20)

            if history.empty:
                logger.error(f"No historical data found for {args.bot_type}")
                return

            if args.plot:
                output_file = args.output or f"{args.bot_type}_timeline.png"
                plot_importance_timeline(history, args.bot_type, output_file)

            if args.heatmap:
                output_file = args.output or f"{args.bot_type}_heatmap.png"
                plot_rank_heatmap(history, args.bot_type, output_file)

            return

        # Default: analyze drift
        analyze_drift(args.bot_type, args.baseline_strategy, args.lookback)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
