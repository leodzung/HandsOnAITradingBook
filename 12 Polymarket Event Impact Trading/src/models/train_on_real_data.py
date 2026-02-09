#!/usr/bin/env python3
"""
Train ML Model on Real Data
Uses actual article-market matches from NewsAPI and Polymarket
"""

import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

from models import PriceMovementPredictor, EnsemblePredictor
from sklearn.model_selection import cross_val_score

def load_real_dataset():
    """Load the real training dataset"""
    print("📊 Loading real training dataset...")

    df = pd.read_csv('data/real_training_dataset.csv')

    print(f"✓ Loaded {len(df)} real article-market matches")
    print(f"\nDataset info:")
    print(f"  • Topics: {df['topic'].nunique()}")
    print(f"  • Sources: {df['source'].nunique()}")
    print(f"  • Markets: {df['market_question'].nunique()}")

    return df

def create_synthetic_labels(df):
    """
    Create labels based on features (for demonstration)
    In production, these would be actual price movements
    """
    print("\n⚠️  Creating synthetic labels (for demonstration)...")
    print("In production, use actual price changes!")

    labels = []

    for idx, row in df.iterrows():
        # Use sentiment + credibility to create realistic labels
        sentiment = row['sentiment_score']
        credibility = row['source_credibility']

        # High sentiment + high credibility = likely UP
        # Low sentiment + high credibility = likely DOWN

        score = sentiment * credibility

        # Add some randomness to simulate market uncertainty
        noise = np.random.normal(0, 0.3)
        final_score = score + noise

        if final_score > 0.2:
            labels.append(1)  # UP
        elif final_score < -0.2:
            labels.append(-1)  # DOWN
        else:
            labels.append(0)  # NEUTRAL

    df['label'] = labels

    print(f"\nLabel distribution:")
    print(f"  UP (+1):     {sum(l == 1 for l in labels)}")
    print(f"  NEUTRAL (0): {sum(l == 0 for l in labels)}")
    print(f"  DOWN (-1):   {sum(l == -1 for l in labels)}")

    return df

def prepare_features(df):
    """Prepare feature matrix for training"""
    print("\n🔧 Preparing features...")

    feature_columns = [
        'sentiment_score',
        'sentiment_magnitude',
        'source_credibility',
        'title_length',
        'has_description',
        'keyword_overlap',
        'market_volume'
    ]

    # Normalize market volume (log scale)
    df['market_volume_log'] = np.log1p(df['market_volume'])
    feature_columns.append('market_volume_log')

    X = df[feature_columns]
    y = df['label']

    print(f"✓ Feature matrix: {X.shape}")
    print(f"  Features: {list(X.columns)}")

    return X, y, feature_columns

def train_models(X, y):
    """Train multiple models with proper walk-forward validation"""
    print("\n" + "="*70)
    print("🤖 TRAINING MODELS ON REAL DATA")
    print("="*70)

    models = {}
    cv_results = {}

    # Determine if we have enough data for CV
    use_cv = len(X) >= 50  # Need at least 50 samples for k=5 CV

    if use_cv:
        print(f"\n✓ Dataset size: {len(X)} samples - Using walk-forward CV")
    else:
        print(f"\n⚠  Dataset size: {len(X)} samples - Using simple split (need >= 50 for CV)")

    # Model 1: Random Forest
    print("\n1. Training Random Forest...")
    rf_model = PriceMovementPredictor(model_type='random_forest')

    if use_cv:
        rf_cv_metrics = rf_model.train(X, y, use_cv=True, cv_n_folds=5)
        cv_results['random_forest'] = rf_cv_metrics

        print(f"\n   ✓ Random Forest trained with CV")
        print(f"     Mean ROC-AUC:  {rf_cv_metrics['mean_roc_auc']:.3f} ± {rf_cv_metrics['std_roc_auc']:.3f}")
        print(f"     Mean Accuracy: {rf_cv_metrics['mean_accuracy']:.3f} ± {rf_cv_metrics['std_accuracy']:.3f}")
        print(f"     Production Ready: {rf_cv_metrics['production_ready']}")
    else:
        # Fallback for small datasets
        rf_metrics = rf_model.train(X, y, validation_split=0.2)
        cv_results['random_forest'] = rf_metrics

        print(f"\n   ✓ Random Forest trained (simple split)")
        print(f"     Train accuracy: {rf_metrics['train_accuracy']:.2%}")
        print(f"     Val accuracy: {rf_metrics['val_accuracy']:.2%}")

    models['random_forest'] = rf_model

    # Model 2: Gradient Boosting (if enough samples)
    if len(X) >= 20:
        print("\n2. Training Gradient Boosting...")
        gb_model = PriceMovementPredictor(model_type='gradient_boost')

        if use_cv:
            gb_cv_metrics = gb_model.train(X, y, use_cv=True, cv_n_folds=5)
            cv_results['gradient_boost'] = gb_cv_metrics

            print(f"\n   ✓ Gradient Boosting trained with CV")
            print(f"     Mean ROC-AUC:  {gb_cv_metrics['mean_roc_auc']:.3f} ± {gb_cv_metrics['std_roc_auc']:.3f}")
            print(f"     Mean Accuracy: {gb_cv_metrics['mean_accuracy']:.3f} ± {gb_cv_metrics['std_accuracy']:.3f}")
            print(f"     Production Ready: {gb_cv_metrics['production_ready']}")
        else:
            gb_metrics = gb_model.train(X, y, validation_split=0.2)
            cv_results['gradient_boost'] = gb_metrics

            print(f"\n   ✓ Gradient Boosting trained (simple split)")
            print(f"     Train accuracy: {gb_metrics['train_accuracy']:.2%}")
            print(f"     Val accuracy: {gb_metrics['val_accuracy']:.2%}")

        models['gradient_boost'] = gb_model

    # Model 3: Logistic Regression (baseline)
    print("\n3. Training Logistic Regression (baseline)...")
    lr_model = PriceMovementPredictor(model_type='logistic')

    if use_cv:
        lr_cv_metrics = lr_model.train(X, y, use_cv=True, cv_n_folds=5)
        cv_results['logistic'] = lr_cv_metrics

        print(f"\n   ✓ Logistic Regression trained with CV")
        print(f"     Mean ROC-AUC:  {lr_cv_metrics['mean_roc_auc']:.3f} ± {lr_cv_metrics['std_roc_auc']:.3f}")
        print(f"     Mean Accuracy: {lr_cv_metrics['mean_accuracy']:.3f} ± {lr_cv_metrics['std_accuracy']:.3f}")
        print(f"     Production Ready: {lr_cv_metrics['production_ready']}")
    else:
        lr_metrics = lr_model.train(X, y, validation_split=0.2)
        cv_results['logistic'] = lr_metrics

        print(f"\n   ✓ Logistic Regression trained (simple split)")
        print(f"     Train accuracy: {lr_metrics['train_accuracy']:.2%}")
        print(f"     Val accuracy: {lr_metrics['val_accuracy']:.2%}")

    models['logistic'] = lr_model

    # Compare models if CV was used
    if use_cv and len(models) > 1:
        print("\n" + "="*70)
        print("📊 MODEL COMPARISON (Cross-Validation)")
        print("="*70)

        comparison_data = []
        for model_name in cv_results:
            if 'mean_roc_auc' in cv_results[model_name]:
                comparison_data.append({
                    'Model': model_name,
                    'Mean ROC-AUC': cv_results[model_name]['mean_roc_auc'],
                    'Std ROC-AUC': cv_results[model_name]['std_roc_auc'],
                    'Mean Accuracy': cv_results[model_name]['mean_accuracy'],
                    'Production Ready': cv_results[model_name]['production_ready']
                })

        if comparison_data:
            comparison_df = pd.DataFrame(comparison_data)
            comparison_df = comparison_df.sort_values('Mean ROC-AUC', ascending=False)

            print("\nModel Rankings:")
            for idx, row in comparison_df.iterrows():
                status = "✓" if row['Production Ready'] else "✗"
                print(f"{status} {row['Model']:20s}: ROC-AUC {row['Mean ROC-AUC']:.3f} ± {row['Std ROC-AUC']:.3f}")

            # Compare CV reports visually
            try:
                from cv_utils import compare_cv_reports
                reports = {}
                for model_name, metrics in cv_results.items():
                    if 'validation_report' in metrics:
                        reports[model_name] = metrics['validation_report']

                if reports:
                    compare_cv_reports(reports, 'data/model_comparison.png')
            except Exception as e:
                print(f"Note: Could not generate comparison plot: {e}")

    return models, cv_results

def analyze_feature_importance(model, feature_names):
    """Analyze which features matter most"""
    print("\n" + "="*70)
    print("📊 FEATURE IMPORTANCE ANALYSIS")
    print("="*70)

    importance_df = model.get_feature_importance()

    print("\nTop Features (what drives predictions):")
    for idx, row in importance_df.head(5).iterrows():
        print(f"  {idx+1}. {row['feature']}: {row['importance']:.3f}")

    return importance_df

def save_best_model(models):
    """Save the best performing model"""
    print("\n" + "="*70)
    print("💾 SAVING BEST MODEL")
    print("="*70)

    # For now, save Random Forest (most reliable with small data)
    best_model = models['random_forest']

    filename = 'real_data_model.pkl'
    best_model.save(filename)

    print(f"\n✓ Saved model to: {filename}")
    print(f"\nTo use this model for trading:")
    print(f"1. Update config.json: \"model_path\": \"{filename}\"")
    print(f"2. Run: python3 trader.py")

    return filename

def create_sample_predictions(df, model, X):
    """Show sample predictions on real data"""
    print("\n" + "="*70)
    print("🔮 SAMPLE PREDICTIONS ON REAL DATA")
    print("="*70)

    predictions = model.predict(X)
    probabilities = model.predict_proba(X)

    df['prediction'] = predictions
    df['confidence'] = probabilities.max(axis=1)

    print("\nTop 5 predictions:")
    for idx, row in df.head(5).iterrows():
        pred_label = {1: 'UP ↗', 0: 'NEUTRAL →', -1: 'DOWN ↘'}

        print(f"\n{idx+1}. Article: {row['article_title'][:60]}...")
        print(f"   Market: {row['market_question'][:60]}...")
        print(f"   Sentiment: {row['sentiment_score']:.2f}")
        print(f"   Prediction: {pred_label[row['prediction']]} ({row['confidence']:.1%} confidence)")

def main():
    print("="*70)
    print("TRAINING ML MODEL ON REAL DATA")
    print("="*70)

    # 1. Load real data
    df = load_real_dataset()

    # 2. Create labels (in production, use actual price movements)
    df = create_synthetic_labels(df)

    # 3. Prepare features
    X, y, feature_names = prepare_features(df)

    # 4. Train models
    models = train_models(X, y)

    # 5. Analyze feature importance
    analyze_feature_importance(models['random_forest'], feature_names)

    # 6. Save best model
    model_file = save_best_model(models)

    # 7. Show predictions on real data
    create_sample_predictions(df, models['random_forest'], X)

    # Summary
    print("\n" + "="*70)
    print("✅ TRAINING COMPLETE!")
    print("="*70)

    print(f"""
📊 Results Summary:
   • Trained on {len(df)} real article-market matches
   • {len(X.columns)} features extracted
   • Model saved: {model_file}

⚠️  Important Notes:
   • Labels are SYNTHETIC (based on sentiment)
   • For production: need actual price movements
   • Small dataset ({len(df)} samples) - collect more!

🎯 Next Steps:
   1. Collect more data over 7-14 days
   2. Track actual price changes after events
   3. Retrain with real labels
   4. Achieve 60-70% accuracy on real data
   5. Start paper trading!

💡 You can paper trade NOW to test the system:
   python3 trader.py
""")

    print("="*70)

if __name__ == '__main__':
    main()
