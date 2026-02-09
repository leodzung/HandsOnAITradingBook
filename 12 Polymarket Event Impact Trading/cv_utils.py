#!/usr/bin/env python3
"""
Cross-Validation Utilities
Helper functions for analyzing, visualizing, and assessing CV results.
"""

import json
import pandas as pd
import numpy as np
from typing import Dict, List
import logging
from pathlib import Path

from walk_forward_validator import ValidationReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def summarize_cv_results(report: ValidationReport) -> pd.DataFrame:
    """
    Convert ValidationReport to DataFrame for easy analysis.

    Args:
        report: ValidationReport from cross-validation

    Returns:
        DataFrame with metrics for each fold

    Example:
        >>> df = summarize_cv_results(report)
        >>> print(df[['fold_id', 'roc_auc', 'accuracy', 'f1']])
    """
    df = pd.DataFrame(report.fold_metrics)

    # Add aggregate statistics
    logger.info(f"\nCross-Validation Summary ({report.n_folds} folds):")
    logger.info(f"{'='*60}")

    metrics = ['roc_auc', 'accuracy', 'precision', 'recall', 'f1']
    for metric in metrics:
        if metric in df.columns:
            mean_val = df[metric].mean()
            std_val = df[metric].std()
            logger.info(f"{metric:12s}: {mean_val:.4f} ± {std_val:.4f}")

    return df


def plot_fold_performance(report: ValidationReport,
                          output_path: str = 'data/cv_fold_performance.png'):
    """
    Visualize performance metrics across folds.

    Creates a multi-panel plot showing:
    - ROC-AUC across folds
    - Accuracy across folds
    - F1 score across folds
    - Training/validation sample sizes

    Args:
        report: ValidationReport from cross-validation
        output_path: Path to save plot

    Example:
        >>> plot_fold_performance(report, 'data/model_cv_performance.png')
    """
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        sns.set_style('whitegrid')
    except ImportError:
        logger.warning("matplotlib/seaborn not available - skipping plot")
        return

    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(report.fold_metrics)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Walk-Forward Cross-Validation Performance', fontsize=16, y=0.995)

    # Plot 1: ROC-AUC across folds
    ax1 = axes[0, 0]
    fold_ids = df['fold_id']
    ax1.plot(fold_ids, df['roc_auc'], marker='o', linewidth=2, markersize=8, color='#2E86AB')
    ax1.axhline(report.mean_roc_auc, color='red', linestyle='--', linewidth=2, label='Mean')
    ax1.fill_between(fold_ids,
                      report.mean_roc_auc - report.std_roc_auc,
                      report.mean_roc_auc + report.std_roc_auc,
                      alpha=0.2, color='red', label='±1 std')
    ax1.set_xlabel('Fold', fontsize=11)
    ax1.set_ylabel('ROC-AUC', fontsize=11)
    ax1.set_title(f'ROC-AUC Across Folds (μ={report.mean_roc_auc:.3f}, σ={report.std_roc_auc:.3f})', fontsize=12)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim([max(0, df['roc_auc'].min() - 0.05), min(1, df['roc_auc'].max() + 0.05)])

    # Plot 2: Accuracy across folds
    ax2 = axes[0, 1]
    ax2.plot(fold_ids, df['accuracy'], marker='s', linewidth=2, markersize=8, color='#A23B72')
    ax2.axhline(report.mean_accuracy, color='red', linestyle='--', linewidth=2, label='Mean')
    ax2.fill_between(fold_ids,
                      report.mean_accuracy - report.std_accuracy,
                      report.mean_accuracy + report.std_accuracy,
                      alpha=0.2, color='red', label='±1 std')
    ax2.set_xlabel('Fold', fontsize=11)
    ax2.set_ylabel('Accuracy', fontsize=11)
    ax2.set_title(f'Accuracy Across Folds (μ={report.mean_accuracy:.3f}, σ={report.std_accuracy:.3f})', fontsize=12)
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([max(0, df['accuracy'].min() - 0.05), min(1, df['accuracy'].max() + 0.05)])

    # Plot 3: F1 score across folds
    ax3 = axes[1, 0]
    ax3.plot(fold_ids, df['f1'], marker='^', linewidth=2, markersize=8, color='#F18F01')
    ax3.axhline(report.mean_f1, color='red', linestyle='--', linewidth=2, label='Mean')
    ax3.fill_between(fold_ids,
                      report.mean_f1 - report.std_f1,
                      report.mean_f1 + report.std_f1,
                      alpha=0.2, color='red', label='±1 std')
    ax3.set_xlabel('Fold', fontsize=11)
    ax3.set_ylabel('F1 Score', fontsize=11)
    ax3.set_title(f'F1 Score Across Folds (μ={report.mean_f1:.3f}, σ={report.std_f1:.3f})', fontsize=12)
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim([max(0, df['f1'].min() - 0.05), min(1, df['f1'].max() + 0.05)])

    # Plot 4: Sample sizes across folds
    ax4 = axes[1, 1]
    x = np.arange(len(fold_ids))
    width = 0.35
    ax4.bar(x - width/2, df['train_samples'], width, label='Train', color='#4A90E2', alpha=0.8)
    ax4.bar(x + width/2, df['val_samples'], width, label='Validation', color='#E57373', alpha=0.8)
    ax4.set_xlabel('Fold', fontsize=11)
    ax4.set_ylabel('Sample Count', fontsize=11)
    ax4.set_title('Training/Validation Sizes (Expanding Window)', fontsize=12)
    ax4.set_xticks(x)
    ax4.set_xticklabels(fold_ids)
    ax4.legend()
    ax4.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Saved fold performance plot to {output_path}")

    plt.close()


def check_production_readiness(report: ValidationReport,
                                min_roc_auc: float = 0.70,
                                max_std_auc: float = 0.10,
                                max_degradation: float = 0.10) -> Dict:
    """
    Assess whether model meets production readiness criteria.

    Criteria:
    1. Mean ROC-AUC >= 0.70 (production ready)
    2. Std ROC-AUC < 0.10 (stable across folds)
    3. AUC degradation < 0.10 (no severe drift)

    Args:
        report: ValidationReport from cross-validation
        min_roc_auc: Minimum acceptable mean ROC-AUC
        max_std_auc: Maximum acceptable std of ROC-AUC
        max_degradation: Maximum acceptable AUC degradation

    Returns:
        Dictionary with readiness assessment

    Example:
        >>> readiness = check_production_readiness(report)
        >>> if readiness['is_production_ready']:
        ...     print("✓ Model ready for production!")
        ... else:
        ...     print("✗ Model needs improvement:")
        ...     for issue in readiness['issues']:
        ...         print(f"  - {issue}")
    """
    logger.info(f"\n{'='*70}")
    logger.info("PRODUCTION READINESS ASSESSMENT")
    logger.info(f"{'='*70}")

    issues = []
    warnings = []
    is_production_ready = True

    # Check 1: Mean ROC-AUC
    if report.mean_roc_auc >= min_roc_auc:
        logger.info(f"✓ Mean ROC-AUC: {report.mean_roc_auc:.4f} (>= {min_roc_auc})")
    elif report.mean_roc_auc >= 0.60:
        logger.warning(f"⚠ Mean ROC-AUC: {report.mean_roc_auc:.4f} (MARGINAL: 0.60-0.70)")
        warnings.append(f"Marginal performance: AUC {report.mean_roc_auc:.3f} in 0.60-0.70 range")
        is_production_ready = False
    else:
        logger.error(f"✗ Mean ROC-AUC: {report.mean_roc_auc:.4f} (< 0.60)")
        issues.append(f"Poor performance: AUC {report.mean_roc_auc:.3f} below 0.60 threshold")
        is_production_ready = False

    # Check 2: Stability (std)
    if report.std_roc_auc < max_std_auc:
        logger.info(f"✓ Std ROC-AUC: {report.std_roc_auc:.4f} (< {max_std_auc})")
    else:
        logger.warning(f"⚠ Std ROC-AUC: {report.std_roc_auc:.4f} (>= {max_std_auc})")
        issues.append(f"High instability: std {report.std_roc_auc:.3f} exceeds {max_std_auc} threshold")
        is_production_ready = False

    # Check 3: Degradation (concept drift)
    abs_degradation = abs(report.auc_degradation)
    if abs_degradation < max_degradation:
        logger.info(f"✓ AUC Degradation: {report.auc_degradation:+.4f} (|val| < {max_degradation})")
    else:
        logger.warning(f"⚠ AUC Degradation: {report.auc_degradation:+.4f} (|val| >= {max_degradation})")
        issues.append(f"Severe drift: degradation {report.auc_degradation:+.3f} exceeds {max_degradation} threshold")
        is_production_ready = False

    # Additional metrics for context
    logger.info(f"\nAdditional Metrics:")
    logger.info(f"  Mean Accuracy: {report.mean_accuracy:.4f} ± {report.std_accuracy:.4f}")
    logger.info(f"  Mean F1:       {report.mean_f1:.4f} ± {report.std_f1:.4f}")
    logger.info(f"  Folds:         {report.n_folds}")

    # Final verdict
    logger.info(f"\n{'='*70}")
    if is_production_ready:
        logger.info("✅ PRODUCTION READY")
        logger.info("Model meets all production readiness criteria.")
    else:
        logger.warning("❌ NOT PRODUCTION READY")
        logger.warning("Model requires improvement before deployment.")

        if issues:
            logger.warning("\nIssues:")
            for issue in issues:
                logger.warning(f"  - {issue}")

        if warnings:
            logger.warning("\nWarnings:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

    logger.info(f"{'='*70}\n")

    return {
        'is_production_ready': is_production_ready,
        'mean_roc_auc': report.mean_roc_auc,
        'std_roc_auc': report.std_roc_auc,
        'auc_degradation': report.auc_degradation,
        'mean_accuracy': report.mean_accuracy,
        'mean_f1': report.mean_f1,
        'issues': issues,
        'warnings': warnings,
        'criteria': {
            'min_roc_auc': min_roc_auc,
            'max_std_auc': max_std_auc,
            'max_degradation': max_degradation
        }
    }


def save_cv_summary(report: ValidationReport,
                   readiness_assessment: Dict,
                   output_path: str = 'data/cv_summary.json'):
    """
    Save comprehensive CV summary to JSON.

    Args:
        report: ValidationReport from cross-validation
        readiness_assessment: Output from check_production_readiness()
        output_path: Path to save JSON summary

    Example:
        >>> readiness = check_production_readiness(report)
        >>> save_cv_summary(report, readiness, 'data/model_cv_summary.json')
    """
    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    summary = {
        'validation_report': {
            'n_folds': report.n_folds,
            'val_period_days': report.val_period_days,
            'mean_roc_auc': float(report.mean_roc_auc),
            'std_roc_auc': float(report.std_roc_auc),
            'mean_accuracy': float(report.mean_accuracy),
            'std_accuracy': float(report.std_accuracy),
            'mean_f1': float(report.mean_f1),
            'std_f1': float(report.std_f1),
            'auc_degradation': float(report.auc_degradation),
            'created_at': report.created_at,
            'fold_metrics': report.fold_metrics
        },
        'production_readiness': readiness_assessment
    }

    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"✓ Saved CV summary to {output_path}")


def compare_cv_reports(reports: Dict[str, ValidationReport],
                      output_path: str = 'data/model_comparison.png'):
    """
    Compare multiple CV reports (e.g., different models).

    Args:
        reports: Dict mapping model name to ValidationReport
        output_path: Path to save comparison plot

    Example:
        >>> reports = {
        ...     'Random Forest': rf_report,
        ...     'Gradient Boosting': gb_report,
        ...     'Logistic Regression': lr_report
        ... }
        >>> compare_cv_reports(reports)
    """
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        sns.set_style('whitegrid')
    except ImportError:
        logger.warning("matplotlib/seaborn not available - skipping comparison plot")
        return

    # Create output directory if needed
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('Model Comparison (Cross-Validation)', fontsize=16)

    model_names = list(reports.keys())
    metrics = ['mean_roc_auc', 'mean_accuracy', 'mean_f1']
    metric_labels = ['ROC-AUC', 'Accuracy', 'F1 Score']
    std_metrics = ['std_roc_auc', 'std_accuracy', 'std_f1']

    for idx, (metric, std_metric, label) in enumerate(zip(metrics, std_metrics, metric_labels)):
        ax = axes[idx]

        means = [getattr(reports[name], metric) for name in model_names]
        stds = [getattr(reports[name], std_metric) for name in model_names]

        x = np.arange(len(model_names))
        bars = ax.bar(x, means, yerr=stds, capsize=5, alpha=0.7, color='steelblue')

        # Color bars by performance
        for i, (mean, bar) in enumerate(zip(means, bars)):
            if metric == 'mean_roc_auc':
                if mean >= 0.70:
                    bar.set_color('green')
                elif mean >= 0.60:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')

        ax.set_ylabel(label, fontsize=11)
        ax.set_title(f'{label} Comparison', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(model_names, rotation=45, ha='right')
        ax.grid(True, alpha=0.3, axis='y')
        ax.set_ylim([0, 1.0])

        # Add reference line for production threshold
        if metric == 'mean_roc_auc':
            ax.axhline(0.70, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Production threshold')
            ax.axhline(0.60, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Marginal threshold')
            ax.legend(fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    logger.info(f"✓ Saved model comparison plot to {output_path}")

    plt.close()


if __name__ == '__main__':
    # Example usage
    from walk_forward_validator import load_validation_report

    logger.info("Testing CV utilities...")

    # Create a mock report for testing
    from walk_forward_validator import ValidationReport, FoldMetrics
    from dataclasses import asdict

    fold_metrics = [
        FoldMetrics(
            fold_id=i+1,
            train_start='2024-01-01',
            train_end='2024-06-01',
            val_start='2024-06-02',
            val_end='2024-07-01',
            train_samples=500 + i*100,
            val_samples=100,
            accuracy=0.65 + i*0.02,
            precision=0.67 + i*0.02,
            recall=0.63 + i*0.02,
            f1=0.65 + i*0.02,
            roc_auc=0.72 - i*0.01,
            brier_score=0.22,
            train_class_distribution={-1: 200, 0: 150, 1: 150},
            val_class_distribution={-1: 40, 0: 30, 1: 30}
        )
        for i in range(5)
    ]

    report = ValidationReport(
        fold_metrics=[asdict(fm) for fm in fold_metrics],
        mean_roc_auc=0.70,
        std_roc_auc=0.05,
        mean_accuracy=0.69,
        std_accuracy=0.04,
        mean_f1=0.69,
        std_f1=0.04,
        auc_degradation=-0.04,
        created_at='2024-01-01T12:00:00',
        n_folds=5,
        val_period_days=30
    )

    # Test summarize
    df = summarize_cv_results(report)
    logger.info(f"\nSummary DataFrame shape: {df.shape}")

    # Test plot
    plot_fold_performance(report, 'data/test_cv_performance.png')

    # Test readiness check
    readiness = check_production_readiness(report)
    logger.info(f"\nProduction ready: {readiness['is_production_ready']}")

    # Test save summary
    save_cv_summary(report, readiness, 'data/test_cv_summary.json')

    logger.info("\n✓ All CV utilities tests passed!")
