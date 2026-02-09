#!/usr/bin/env python3
"""
Label Current Positions and Retrain Model
Use our 10 resolved positions to create initial real training data.
"""

import sqlite3
import json
import pandas as pd
import numpy as np
from datetime import datetime
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score


def load_position_data():
    """Load our 10 resolved positions from database."""
    conn = sqlite3.connect('data/positions.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT market_id, entry_price, side, metadata
        FROM positions
        WHERE status = 'OPEN'
    """)

    positions = cursor.fetchall()
    conn.close()

    print(f"Loaded {len(positions)} positions from database")
    return positions


def get_tracked_events():
    """Load tracked events that contain features."""
    conn = sqlite3.connect('data/events.db')
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='tracked_events'
    """)

    if not cursor.fetchone():
        print("No tracked_events table found")
        conn.close()
        return []

    cursor.execute("""
        SELECT event_id, market_id, features_json, timestamp
        FROM tracked_events
        ORDER BY timestamp DESC
    """)

    events = cursor.fetchall()
    conn.close()

    print(f"Loaded {len(events)} tracked events")
    return events


def label_positions_with_outcomes():
    """
    Label our 10 positions with actual outcomes.
    All 10 resolved NO, so outcome = -1 (DOWN).
    """

    # Known outcomes from manual verification
    outcomes = {
        # All resolved NO
        'label': -1  # DOWN/NO
    }

    positions = load_position_data()
    events = get_tracked_events()

    # Create event lookup by market_id
    event_lookup = {}
    for event_id, market_id, features_json, timestamp in events:
        if market_id not in event_lookup:
            event_lookup[market_id] = (event_id, features_json)

    training_data = []

    for market_id, entry_price, side, metadata_json in positions:
        # Get features for this market
        if market_id not in event_lookup:
            print(f"No features found for market {market_id}")
            continue

        _, features_json = event_lookup[market_id]

        try:
            features = json.loads(features_json)

            # Create training sample
            sample = {
                'sentiment_score': features.get('event_sentiment_score', 0.0),
                'sentiment_magnitude': features.get('event_sentiment_magnitude', 0.0),
                'source_credibility': features.get('event_source_credibility', 0.5),
                'title_length': features.get('event_title_length', 0),
                'has_description': 1 if features.get('event_description_length', 0) > 0 else 0,
                'keyword_overlap': features.get('event_keyword_count', 0),
                'market_volume': features.get('market_volume', 0.0),
            }

            # Add derived features
            sample['market_volume_log'] = np.log1p(sample['market_volume'])

            # Add outcome label (all positions resolved NO)
            sample['outcome'] = -1  # DOWN/NO

            # Add metadata
            sample['market_id'] = market_id
            sample['entry_price'] = entry_price
            sample['side'] = side

            training_data.append(sample)

        except Exception as e:
            print(f"Error processing {market_id}: {e}")
            continue

    df = pd.DataFrame(training_data)
    print(f"\nCreated training dataset with {len(df)} samples")

    if len(df) > 0:
        print("\nOutcome distribution:")
        print(df['outcome'].value_counts())

        print("\nSide distribution:")
        print(df['side'].value_counts())

        print("\nSentiment score stats:")
        print(df['sentiment_score'].describe())

    return df


def add_synthetic_data(real_df, n_synthetic=20):
    """
    Add some synthetic opposite examples to balance the dataset.
    Since all real samples are DOWN (-1), create some UP (+1) examples.
    """

    if len(real_df) == 0:
        print("No real data to augment")
        return real_df

    synthetic_data = []

    # Get average features from real data
    avg_features = real_df.drop(['outcome', 'market_id', 'entry_price', 'side'],
                                  axis=1, errors='ignore').mean()

    for i in range(n_synthetic):
        # Create synthetic UP sample with positive sentiment
        sample = {
            'sentiment_score': np.random.uniform(0.5, 1.0),  # Positive
            'sentiment_magnitude': np.random.uniform(0.7, 1.0),
            'source_credibility': np.random.uniform(0.6, 0.9),
            'title_length': int(avg_features['title_length']),
            'has_description': 1,
            'keyword_overlap': int(avg_features['keyword_overlap']),
            'market_volume': avg_features['market_volume'],
            'market_volume_log': np.log1p(avg_features['market_volume']),
            'outcome': 1  # UP
        }
        synthetic_data.append(sample)

    # Also create some NEUTRAL examples
    for i in range(n_synthetic // 2):
        sample = {
            'sentiment_score': np.random.uniform(-0.2, 0.2),  # Neutral
            'sentiment_magnitude': np.random.uniform(0.3, 0.6),
            'source_credibility': np.random.uniform(0.4, 0.7),
            'title_length': int(avg_features['title_length']),
            'has_description': 1,
            'keyword_overlap': int(avg_features['keyword_overlap']),
            'market_volume': avg_features['market_volume'],
            'market_volume_log': np.log1p(avg_features['market_volume']),
            'outcome': 0  # NEUTRAL
        }
        synthetic_data.append(sample)

    synthetic_df = pd.DataFrame(synthetic_data)
    combined_df = pd.concat([real_df, synthetic_df], ignore_index=True)

    print(f"\nAdded {len(synthetic_df)} synthetic samples")
    print(f"Combined dataset: {len(combined_df)} samples")
    print("\nCombined outcome distribution:")
    print(combined_df['outcome'].value_counts())

    return combined_df


def retrain_model(df, use_cv=True):
    """
    Retrain RandomForest model with optional cross-validation.

    ⚠️ CRITICAL: In production, always use CV (use_cv=True) to validate model
    before deployment. Training without validation is dangerous!

    Args:
        df: DataFrame with features and 'outcome' column
        use_cv: Whether to use cross-validation (default: True)

    Returns:
        Trained model if successful, None otherwise
    """
    if len(df) < 5:
        print(f"Not enough data to train ({len(df)} samples)")
        return None

    # Prepare features and labels
    feature_cols = [
        'sentiment_score', 'sentiment_magnitude', 'source_credibility',
        'title_length', 'has_description', 'keyword_overlap',
        'market_volume_log'
    ]

    X = df[feature_cols].values
    y = df['outcome'].values

    print(f"\nTraining on {len(X)} samples with {len(feature_cols)} features")
    print(f"Class distribution: {np.bincount(y + 1)}")  # Shift from -1,0,1 to 0,1,2

    # Use CV if sufficient data and requested
    if use_cv and len(df) >= 50:
        print("\n" + "="*70)
        print("⚠️  PRODUCTION TRAINING WITH CROSS-VALIDATION")
        print("="*70)
        print("Using k-fold CV to validate model before deployment...")

        from cross_validation import UnifiedCrossValidator
        from cv_utils import check_production_readiness, save_cv_summary, plot_fold_performance
        from walk_forward_validator import save_validation_report

        # Convert to DataFrame for CV
        X_df = pd.DataFrame(X, columns=feature_cols)
        y_series = pd.Series(y)

        # Define model factory
        def model_factory():
            return RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=2,
                min_samples_leaf=1,
                random_state=42,
                class_weight='balanced'
            )

        # Run CV
        cv = UnifiedCrossValidator(n_folds=5, val_period_days=30, min_samples_per_fold=10)
        report = cv.validate_sklearn_model(X_df, y_series, model_factory)

        # Check production readiness
        readiness = check_production_readiness(report)

        # Save CV results
        save_validation_report(report, 'data/retrained_model_cv_report.json')
        plot_fold_performance(report, 'data/retrained_model_cv_folds.png')
        save_cv_summary(report, readiness, 'data/retrained_model_cv_summary.json')

        print(f"\n{'='*70}")
        print("CROSS-VALIDATION RESULTS")
        print(f"{'='*70}")
        print(f"Mean ROC-AUC:     {report.mean_roc_auc:.3f} ± {report.std_roc_auc:.3f}")
        print(f"Mean Accuracy:    {report.mean_accuracy:.3f} ± {report.std_accuracy:.3f}")
        print(f"Mean F1:          {report.mean_f1:.3f} ± {report.std_f1:.3f}")
        print(f"Production Ready: {readiness['is_production_ready']}")

        # Block deployment if not production ready
        if not readiness['is_production_ready']:
            print("\n" + "="*70)
            print("⚠️  WARNING: MODEL FAILED PRODUCTION READINESS CRITERIA")
            print("="*70)
            print("\nIssues identified:")
            for issue in readiness['issues']:
                print(f"  ✗ {issue}")

            if readiness['warnings']:
                print("\nWarnings:")
                for warning in readiness['warnings']:
                    print(f"  ⚠ {warning}")

            print("\n" + "="*70)
            print("DEPLOYMENT DECISION REQUIRED")
            print("="*70)
            print("The model does not meet production quality standards.")
            print("Deploying this model may result in poor trading performance.")
            print("\nOptions:")
            print("  1. Collect more training data")
            print("  2. Improve feature engineering")
            print("  3. Try different model architectures")
            print("  4. Deploy anyway (NOT RECOMMENDED)")

            user_input = input("\nDeploy anyway? (yes/no): ").strip().lower()
            if user_input != 'yes':
                print("\n❌ Training aborted. Model NOT saved.")
                print("Collect more data or improve features before retraining.")
                return None

            print("\n⚠️  User override: Proceeding with deployment despite warnings")

    elif use_cv and len(df) < 50:
        print(f"\n⚠️  Dataset too small for CV ({len(df)} samples < 50)")
        print("Falling back to simple training (NO VALIDATION)")
        print("Collect more data for proper CV!")

    # Train final model on full dataset
    print("\n" + "="*70)
    print("TRAINING FINAL MODEL")
    print("="*70)

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        class_weight='balanced'  # Handle class imbalance
    )

    model.fit(X, y)

    # Evaluate on training data (for reference only)
    y_pred = model.predict(X)
    train_acc = accuracy_score(y, y_pred)

    print(f"\nTraining accuracy: {train_acc:.3f} (reference only)")
    print("\nClassification report (training data):")
    print(classification_report(y, y_pred, target_names=['DOWN', 'NEUTRAL', 'UP']))

    # Feature importance
    print("\nFeature importance:")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                            key=lambda x: x[1], reverse=True):
        print(f"  {feat}: {imp:.3f}")

    return model


def save_model(model, filepath='retrained_model_v2.pkl'):
    """Save retrained model."""
    with open(filepath, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n✅ Saved retrained model to {filepath}")


def main():
    """Label positions and retrain model."""

    print("="*70)
    print("LABEL POSITIONS & RETRAIN MODEL")
    print("="*70)

    # Step 1: Label positions with outcomes
    print("\n[1] Loading and labeling positions...")
    df = label_positions_with_outcomes()

    if len(df) == 0:
        print("\n❌ No training data available")
        print("\nPossible issues:")
        print("  1. No tracked_events in database")
        print("  2. No features stored for positions")
        print("  3. Events not matched to positions")
        return

    # Save real labeled data
    df.to_csv('real_position_data.csv', index=False)
    print(f"\n✅ Saved {len(df)} real samples to real_position_data.csv")

    # Step 2: Add synthetic data to balance
    print("\n[2] Adding synthetic data for balance...")
    combined_df = add_synthetic_data(df, n_synthetic=30)

    # Save combined dataset
    combined_df.to_csv('combined_training_data.csv', index=False)
    print(f"✅ Saved combined dataset to combined_training_data.csv")

    # Step 3: Retrain model
    print("\n[3] Retraining model...")
    model = retrain_model(combined_df)

    if model:
        save_model(model, 'retrained_model_v2.pkl')

        print("\n" + "="*70)
        print("✅ RETRAINING COMPLETE")
        print("="*70)
        print("\nNext steps:")
        print("1. Test new model: update config.json to use retrained_model_v2.pkl")
        print("2. Restart bot: kill and restart trader.py")
        print("3. Monitor performance: check if SELL signals appear")
        print("4. Compare: track win rate vs old model")
    else:
        print("\n❌ Retraining failed")


if __name__ == '__main__':
    main()
