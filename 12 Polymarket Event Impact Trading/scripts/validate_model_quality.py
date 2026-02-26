#!/usr/bin/env python3
"""
ML-001: Validate model quality before deployment.

Production readiness criteria:
- ROC-AUC mean ≥ 0.70
- ROC-AUC std < 0.10
- Degradation (train AUC - test AUC) < 0.10

Usage:
    python3 scripts/validate_model_quality.py --model-path data/models/candidate_model.pkl
"""

import argparse
import pickle
import sys
from pathlib import Path
import numpy as np


def validate_model_quality(model_path: Path) -> tuple[bool, dict]:
    """
    Validate model meets production quality criteria.

    Args:
        model_path: Path to pickled model file

    Returns:
        Tuple of (passes, metrics_dict)
    """
    if not model_path.exists():
        print(f"❌ Model file not found: {model_path}")
        return False, {}

    # Load model
    try:
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return False, {}

    # Extract CV results
    # Expected format: model_data contains 'cv_results' with cross-validation metrics
    if 'cv_results' not in model_data:
        print("⚠️  Model file missing 'cv_results' - cannot validate")
        print("   Model should be trained with walk-forward cross-validation")
        return False, {}

    cv_results = model_data['cv_results']

    # Extract ROC-AUC scores
    if 'test_roc_auc' in cv_results:
        test_scores = cv_results['test_roc_auc']
    elif 'roc_auc_scores' in cv_results:
        test_scores = cv_results['roc_auc_scores']
    else:
        print("⚠️  CV results missing ROC-AUC scores")
        return False, {}

    # Calculate metrics
    roc_auc_mean = np.mean(test_scores)
    roc_auc_std = np.std(test_scores)

    # Calculate degradation if train scores available
    degradation = 0.0
    if 'train_roc_auc' in cv_results:
        train_scores = cv_results['train_roc_auc']
        train_mean = np.mean(train_scores)
        degradation = train_mean - roc_auc_mean

    # Production criteria
    criteria = {
        'roc_auc_mean': roc_auc_mean,
        'roc_auc_std': roc_auc_std,
        'degradation': degradation,
        'passes_auc_mean': roc_auc_mean >= 0.70,
        'passes_auc_std': roc_auc_std < 0.10,
        'passes_degradation': degradation < 0.10,
    }

    # Overall pass
    passes = all([
        criteria['passes_auc_mean'],
        criteria['passes_auc_std'],
        criteria['passes_degradation'],
    ])

    return passes, criteria


def main():
    parser = argparse.ArgumentParser(
        description='Validate ML model quality (ML-001 constraint)'
    )
    parser.add_argument(
        '--model-path',
        type=Path,
        required=True,
        help='Path to pickled model file'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print detailed metrics'
    )

    args = parser.parse_args()

    print(f"Validating model: {args.model_path}")
    print()

    passes, metrics = validate_model_quality(args.model_path)

    if not metrics:
        print("❌ Validation failed - unable to extract metrics")
        sys.exit(1)

    # Print results
    print("📊 Model Quality Metrics:")
    print(f"   ROC-AUC Mean:    {metrics['roc_auc_mean']:.4f}  {'✅' if metrics['passes_auc_mean'] else '❌'} (≥ 0.70)")
    print(f"   ROC-AUC Std:     {metrics['roc_auc_std']:.4f}  {'✅' if metrics['passes_auc_std'] else '❌'} (< 0.10)")
    print(f"   Degradation:     {metrics['degradation']:.4f}  {'✅' if metrics['passes_degradation'] else '❌'} (< 0.10)")
    print()

    if passes:
        print("✅ Model PASSED production quality gates")
        print("   Ready for deployment")
        sys.exit(0)
    else:
        print("❌ Model FAILED production quality gates")
        print("   Needs retraining or hyperparameter tuning")
        sys.exit(1)


if __name__ == "__main__":
    main()
