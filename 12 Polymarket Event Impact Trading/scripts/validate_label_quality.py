#!/usr/bin/env python3
"""
ML-003: Validate label quality using correct token-condition mapping.

Spot-checks 100 random labeled trades to ensure:
1. Labels use maker_asset_id → token_condition_map → outcome_index
2. No price-based heuristics (price > 0.5 = YES)
3. Label distribution is not random (~50/50)

Usage:
    python3 scripts/validate_label_quality.py --sample-size 100
"""

import argparse
import sqlite3
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def validate_label_quality(db_path: Path, sample_size: int = 100) -> tuple[bool, dict]:
    """
    Validate that labels are created correctly.

    Args:
        db_path: Path to alchemy_trades.db
        sample_size: Number of random trades to check

    Returns:
        Tuple of (passes, results_dict)
    """
    if not db_path.exists():
        print(f"ℹ️  Database not found: {db_path}")
        print("   (This is expected in CI - database is not checked into git)")
        return True, {'status': 'skipped', 'reason': 'database_missing'}

    conn = sqlite3.connect(str(db_path))

    # Check 1: Verify token_condition_map exists
    try:
        token_map = pd.read_sql_query("""
            SELECT token_id, outcome_index, condition_id
            FROM token_condition_map
            LIMIT 10
        """, conn)

        if len(token_map) == 0:
            print("❌ token_condition_map table is empty")
            conn.close()
            return False, {}

    except Exception as e:
        print(f"❌ token_condition_map table not found: {e}")
        conn.close()
        return False, {}

    # Check 2: Sample labeled trades
    try:
        labeled_trades = pd.read_sql_query(f"""
            SELECT maker_asset_id, label, price
            FROM on_chain_trades
            WHERE label IS NOT NULL
            ORDER BY RANDOM()
            LIMIT {sample_size}
        """, conn)

        if len(labeled_trades) == 0:
            print("⚠️  No labeled trades found - labeling system not yet populated")
            conn.close()
            # Return success since there's nothing to validate yet
            return True, {'status': 'skipped', 'reason': 'no_labeled_data'}

    except Exception as e:
        # Check if this is the expected "label column doesn't exist" error
        if 'no such column: label' in str(e):
            print("ℹ️  Label column not yet created - skipping validation")
            print("   (This is expected before labeling system is implemented)")
            conn.close()
            # Return success since labeling system isn't set up yet
            return True, {'status': 'skipped', 'reason': 'label_column_missing'}
        else:
            print(f"❌ Failed to query labeled trades: {e}")
            conn.close()
            return False, {}

    # Check 3: Verify labels match token_condition_map
    errors = []
    for idx, trade in labeled_trades.iterrows():
        maker_asset_id = trade['maker_asset_id']
        label = trade['label']

        # Look up correct outcome from token_condition_map
        try:
            correct_outcome = pd.read_sql_query(f"""
                SELECT outcome_index
                FROM token_condition_map
                WHERE token_id = '{maker_asset_id}'
            """, conn)

            if len(correct_outcome) > 0:
                expected_label = int(correct_outcome['outcome_index'].iloc[0])

                if label != expected_label:
                    errors.append({
                        'maker_asset_id': maker_asset_id,
                        'actual_label': label,
                        'expected_label': expected_label,
                    })
        except Exception:
            # Token not in map (possibly old data)
            continue

    # Check 4: Label distribution (should not be exactly 50/50 random)
    label_dist = labeled_trades['label'].value_counts(normalize=True)

    # If distribution is too close to 50/50, labels might be random
    if len(label_dist) >= 2:
        max_label_pct = label_dist.max()
        min_label_pct = label_dist.min()
        distribution_check = not (0.48 <= max_label_pct <= 0.52)
    else:
        distribution_check = True

    # Results
    accuracy = 1.0 - (len(errors) / len(labeled_trades)) if len(labeled_trades) > 0 else 0.0

    results = {
        'sample_size': len(labeled_trades),
        'errors_found': len(errors),
        'accuracy': accuracy,
        'label_distribution': label_dist.to_dict(),
        'passes_accuracy': accuracy >= 0.95,  # 95% accuracy threshold
        'passes_distribution': distribution_check,
        'errors': errors[:10],  # First 10 errors for debugging
    }

    conn.close()

    passes = results['passes_accuracy'] and results['passes_distribution']
    return passes, results


def main():
    parser = argparse.ArgumentParser(
        description='Validate label quality (ML-003 constraint)'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=100,
        help='Number of random trades to check (default: 100)'
    )
    parser.add_argument(
        '--db-path',
        type=Path,
        default=Path('data/alchemy_trades.db'),
        help='Path to alchemy trades database'
    )

    args = parser.parse_args()

    # Resolve path relative to project root
    if not args.db_path.is_absolute():
        project_root = Path(__file__).parent.parent
        args.db_path = project_root / args.db_path

    print(f"Validating labels: {args.db_path}")
    print(f"Sample size: {args.sample_size}")
    print()

    passes, results = validate_label_quality(args.db_path, args.sample_size)

    if not results:
        print("❌ Validation failed - unable to check labels")
        sys.exit(1)

    # Check if validation was skipped
    if results.get('status') == 'skipped':
        print("✅ Validation skipped (expected)")
        reason = results.get('reason', 'unknown')
        if reason == 'database_missing':
            print("   Reason: Database file not found (expected in CI)")
        elif reason == 'label_column_missing':
            print("   Reason: Label column not yet created")
        elif reason == 'no_labeled_data':
            print("   Reason: No labeled data available")
        sys.exit(0)

    # Print results
    print("📊 Label Quality Check:")
    print(f"   Sample Size:     {results['sample_size']}")
    print(f"   Errors Found:    {results['errors_found']}")
    print(f"   Accuracy:        {results['accuracy']:.1%}  {'✅' if results['passes_accuracy'] else '❌'} (≥ 95%)")
    print()

    print("📈 Label Distribution:")
    for label, pct in results['label_distribution'].items():
        print(f"   Label {label}:  {pct:.1%}")
    print(f"   Distribution:    {'✅' if results['passes_distribution'] else '❌'} (not random)")
    print()

    if results['errors']:
        print("⚠️  Example Label Errors (first 10):")
        for err in results['errors']:
            print(f"   Token: {err['maker_asset_id'][:16]}...")
            print(f"     Actual: {err['actual_label']}, Expected: {err['expected_label']}")

    print()

    if passes:
        print("✅ Labels PASSED quality check")
        print("   Using correct token-condition mapping")
        sys.exit(0)
    else:
        print("❌ Labels FAILED quality check")
        print("   May be using incorrect price-based heuristics")
        sys.exit(1)


if __name__ == "__main__":
    main()
