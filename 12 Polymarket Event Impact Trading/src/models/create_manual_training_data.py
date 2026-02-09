#!/usr/bin/env python3
"""
Create Manual Training Data from 10 Resolved Positions
Since we don't have tracked features, manually create reasonable training data.
"""

import pandas as pd
import numpy as np
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score


def create_manual_training_data():
    """
    Create training data from our 10 known positions.

    All 10 positions:
    - Bought YES (predicted UP)
    - Resolved NO (actual DOWN)
    - 100% loss rate
    """

    # Our 10 positions with manually assigned reasonable features
    positions = [
        {
            'market_question': 'USDT depeg in 2025?',
            'side': 'BUY',
            'entry_price': 0.4291,
            'outcome': -1,  # Resolved NO
            # Features: Negative event (depeg), but model predicted YES
            'sentiment_score': -0.5,  # Depegging is negative
            'sentiment_magnitude': 0.8,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 3,
            'market_volume': 100000.0,
        },
        {
            'market_question': 'Sundar Pichai out as Google CEO in 2025?',
            'side': 'BUY',
            'entry_price': 0.5270,
            'outcome': -1,
            # Features: CEO departure is negative/uncertain
            'sentiment_score': -0.3,
            'sentiment_magnitude': 0.7,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 4,
            'market_volume': 150000.0,
        },
        {
            'market_question': 'Tim Cook out as Apple CEO in 2025?',
            'side': 'BUY',
            'entry_price': 0.3394,
            'outcome': -1,
            'sentiment_score': -0.3,
            'sentiment_magnitude': 0.7,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 4,
            'market_volume': 120000.0,
        },
        {
            'market_question': 'Dan Clancy out as Twitch CEO in 2025?',
            'side': 'BUY',
            'entry_price': 0.3267,
            'outcome': -1,
            'sentiment_score': -0.3,
            'sentiment_magnitude': 0.6,
            'source_credibility': 0.6,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 4,
            'market_volume': 80000.0,
        },
        {
            'market_question': 'Andy Jassy out as Amazon CEO in 2025?',
            'side': 'BUY',
            'entry_price': 0.4613,
            'outcome': -1,
            'sentiment_score': -0.3,
            'sentiment_magnitude': 0.7,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 4,
            'market_volume': 130000.0,
        },
        {
            'market_question': 'Brian Armstrong out as Coinbase CEO in 2025?',
            'side': 'BUY',
            'entry_price': 0.2971,
            'outcome': -1,
            'sentiment_score': -0.3,
            'sentiment_magnitude': 0.6,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 4,
            'market_volume': 90000.0,
        },
        {
            'market_question': 'Sam Altman out as OpenAI CEO in 2025?',
            'side': 'BUY',
            'entry_price': 0.4195,
            'outcome': -1,
            'sentiment_score': -0.3,
            'sentiment_magnitude': 0.7,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 4,
            'market_volume': 110000.0,
        },
        {
            'market_question': 'Will Bitcoin dip to $70,000 by December 31, 2025?',
            'side': 'BUY',
            'entry_price': 0.3364,
            'outcome': -1,
            # Features: Price dip is negative
            'sentiment_score': -0.4,
            'sentiment_magnitude': 0.7,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 3,
            'market_volume': 200000.0,
        },
        {
            'market_question': 'Will Bitcoin dip to $50,000 by December 31, 2025?',
            'side': 'BUY',
            'entry_price': 0.2945,
            'outcome': -1,
            'sentiment_score': -0.5,
            'sentiment_magnitude': 0.8,
            'source_credibility': 0.7,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 3,
            'market_volume': 180000.0,
        },
        {
            'market_question': 'One Direction reunion in 2025?',
            'side': 'BUY',
            'entry_price': 0.3617,
            'outcome': -1,
            # Features: Reunion is positive
            'sentiment_score': 0.3,  # Positive event
            'sentiment_magnitude': 0.6,
            'source_credibility': 0.6,
            'title_length': 50,
            'has_description': 1,
            'keyword_overlap': 3,
            'market_volume': 70000.0,
        },
    ]

    df = pd.DataFrame(positions)

    # Add derived features
    df['market_volume_log'] = np.log1p(df['market_volume'])

    return df


def add_synthetic_counter_examples(real_df, n_synthetic=30):
    """
    Add synthetic examples with opposite outcomes to balance dataset.

    Since all real data is DOWN with negative sentiment → YES,
    we need to add:
    1. UP examples with positive sentiment → YES
    2. DOWN examples with negative sentiment → NO
    3. NEUTRAL examples
    """

    synthetic_data = []

    # Get average features from real data
    avg_features = real_df[['title_length', 'has_description', 'keyword_overlap',
                             'market_volume', 'source_credibility']].mean()

    # Type 1: Positive sentiment → UP outcome (what SHOULD happen)
    for i in range(n_synthetic // 3):
        sample = {
            'market_question': f'Synthetic UP {i}',
            'side': 'BUY',
            'entry_price': 0.5,
            'sentiment_score': np.random.uniform(0.5, 1.0),  # Positive
            'sentiment_magnitude': np.random.uniform(0.7, 1.0),
            'source_credibility': avg_features['source_credibility'],
            'title_length': int(avg_features['title_length']),
            'has_description': 1,
            'keyword_overlap': int(avg_features['keyword_overlap']),
            'market_volume': avg_features['market_volume'],
            'market_volume_log': np.log1p(avg_features['market_volume']),
            'outcome': 1  # UP
        }
        synthetic_data.append(sample)

    # Type 2: Negative sentiment → DOWN outcome (what happened to our positions)
    # This teaches the model that negative events → NO wins
    for i in range(n_synthetic // 3):
        sample = {
            'market_question': f'Synthetic DOWN {i}',
            'side': 'SELL',  # Would have sold
            'entry_price': 0.5,
            'sentiment_score': np.random.uniform(-1.0, -0.3),  # Negative
            'sentiment_magnitude': np.random.uniform(0.6, 0.9),
            'source_credibility': avg_features['source_credibility'],
            'title_length': int(avg_features['title_length']),
            'has_description': 1,
            'keyword_overlap': int(avg_features['keyword_overlap']),
            'market_volume': avg_features['market_volume'],
            'market_volume_log': np.log1p(avg_features['market_volume']),
            'outcome': -1  # DOWN
        }
        synthetic_data.append(sample)

    # Type 3: Neutral sentiment → NEUTRAL outcome
    for i in range(n_synthetic // 3):
        sample = {
            'market_question': f'Synthetic NEUTRAL {i}',
            'side': 'HOLD',
            'entry_price': 0.5,
            'sentiment_score': np.random.uniform(-0.2, 0.2),  # Neutral
            'sentiment_magnitude': np.random.uniform(0.3, 0.6),
            'source_credibility': avg_features['source_credibility'],
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

    print(f"\nAdded {len(synthetic_df)} synthetic counter-examples")
    print(f"Combined dataset: {len(combined_df)} samples")
    print("\nCombined outcome distribution:")
    print(combined_df['outcome'].value_counts())
    print("\nSentiment distribution by outcome:")
    print(combined_df.groupby('outcome')['sentiment_score'].describe())

    return combined_df


def retrain_model(df):
    """Retrain RandomForest on real + synthetic data."""

    feature_cols = [
        'sentiment_score', 'sentiment_magnitude', 'source_credibility',
        'title_length', 'has_description', 'keyword_overlap',
        'market_volume_log'
    ]

    X = df[feature_cols].values
    y = df['outcome'].values

    print(f"\n{'='*70}")
    print("TRAINING NEW MODEL")
    print(f"{'='*70}")
    print(f"\nDataset size: {len(X)} samples")
    print(f"Features: {len(feature_cols)}")
    print(f"Classes: DOWN (-1), NEUTRAL (0), UP (1)")
    print(f"\nClass distribution:")
    for outcome, count in zip(*np.unique(y, return_counts=True)):
        pct = (count / len(y)) * 100
        label = {-1: 'DOWN', 0: 'NEUTRAL', 1: 'UP'}[outcome]
        print(f"  {label:8s}: {count:3d} ({pct:5.1f}%)")

    # Train model
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        class_weight='balanced'
    )

    model.fit(X, y)

    # Evaluate
    y_pred = model.predict(X)
    train_acc = accuracy_score(y, y_pred)

    print(f"\n{'='*70}")
    print("TRAINING RESULTS")
    print(f"{'='*70}")
    print(f"\nTraining accuracy: {train_acc:.1%}")
    print("\nClassification report:")
    print(classification_report(y, y_pred, target_names=['DOWN', 'NEUTRAL', 'UP'],
                                zero_division=0))

    # Feature importance
    print(f"\n{'='*70}")
    print("FEATURE IMPORTANCE")
    print(f"{'='*70}\n")
    for feat, imp in sorted(zip(feature_cols, model.feature_importances_),
                            key=lambda x: x[1], reverse=True):
        print(f"  {feat:25s}: {imp:.3f} {'█' * int(imp * 50)}")

    # Test predictions on our real 10 positions
    print(f"\n{'='*70}")
    print("PREDICTIONS ON REAL POSITIONS")
    print(f"{'='*70}\n")

    real_data = df[df['market_question'].str.contains('Synthetic') == False]
    if len(real_data) > 0:
        X_real = real_data[feature_cols].values
        y_real = real_data['outcome'].values
        y_pred_real = model.predict(X_real)

        correct = np.sum(y_pred_real == y_real)
        print(f"Accuracy on 10 real positions: {correct}/10 ({correct/10:.1%})")
        print(f"\nPredictions:")
        for idx, row in real_data.iterrows():
            pred = y_pred_real[idx - real_data.index[0]]
            actual = row['outcome']
            pred_label = {-1: 'DOWN', 0: 'HOLD', 1: 'UP'}[pred]
            actual_label = {-1: 'DOWN', 0: 'HOLD', 1: 'UP'}[actual]
            match = '✓' if pred == actual else '✗'
            print(f"  {match} {row['market_question'][:45]:45s} | "
                  f"Pred: {pred_label:7s} | Actual: {actual_label:7s} | "
                  f"Sent: {row['sentiment_score']:+.2f}")

    return model


def save_model(model, filepath='retrained_model_v2.pkl'):
    """Save retrained model in expected format."""

    # Feature names used during training
    feature_names = [
        'sentiment_score', 'sentiment_magnitude', 'source_credibility',
        'title_length', 'has_description', 'keyword_overlap',
        'market_volume_log'
    ]

    # Create identity scaler (fit on dummy data, does nothing)
    # This is needed because the trader calls scaler.transform()
    scaler = StandardScaler()
    dummy_data = np.zeros((10, len(feature_names)))
    scaler.fit(dummy_data)
    # Now scaler will just subtract 0 and divide by 1 (identity transform)

    # Save in format expected by trader
    model_data = {
        'model_type': 'random_forest',
        'model': model,
        'scaler': scaler,  # Identity scaler
        'feature_names': feature_names,
        'is_trained': True
    }

    with open(filepath, 'wb') as f:
        pickle.dump(model_data, f)

    print(f"\n{'='*70}")
    print(f"✅ SAVED MODEL: {filepath}")
    print(f"{'='*70}")


def main():
    """Create manual training data and retrain model."""

    print("="*70)
    print("MANUAL TRAINING DATA CREATION & RETRAINING")
    print("="*70)
    print("\nUsing 10 resolved positions with manually assigned features")
    print("All 10 resolved NO (outcome = -1)\n")

    # Step 1: Create manual training data
    real_df = create_manual_training_data()
    print(f"\n[1] Created {len(real_df)} real training samples")

    # Save real data
    real_df.to_csv('real_position_data_manual.csv', index=False)
    print(f"✅ Saved to real_position_data_manual.csv")

    # Step 2: Add synthetic counter-examples
    print(f"\n[2] Adding synthetic counter-examples...")
    combined_df = add_synthetic_counter_examples(real_df, n_synthetic=30)

    # Save combined dataset
    combined_df.to_csv('combined_training_data_manual.csv', index=False)
    print(f"✅ Saved to combined_training_data_manual.csv")

    # Step 3: Retrain model
    print(f"\n[3] Retraining model...")
    model = retrain_model(combined_df)

    # Step 4: Save model
    save_model(model, 'retrained_model_v2.pkl')

    print("\n" + "="*70)
    print("✅ RETRAINING COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("1. Update config.json:")
    print('   "model_path": "retrained_model_v2.pkl"')
    print("\n2. Restart trader:")
    print("   kill $(cat trader.pid) && nohup python3 trader.py >> trading.out 2>&1 & echo $! > trader.pid")
    print("\n3. Monitor for SELL signals:")
    print("   tail -f trading.out | grep Signal")
    print("\n4. Expected improvement:")
    print("   - Better sentiment correlation")
    print("   - More SELL signals on negative events")
    print("   - Win rate should improve from 0% baseline")
    print("="*70)


if __name__ == '__main__':
    main()
