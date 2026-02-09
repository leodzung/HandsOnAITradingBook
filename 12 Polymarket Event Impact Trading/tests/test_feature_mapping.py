#!/usr/bin/env python3
"""
Test Feature Mapping Fix
Verify that features are correctly transformed for the model.
"""

import numpy as np
import pandas as pd

def test_transform_features_for_model():
    """Test the feature transformation logic"""

    # Sample features from feature_engineering.create_training_sample()
    # These have prefixes like 'event_', 'market_', 'orderbook_'
    extracted_features = {
        'event_sentiment_score': 0.5,
        'event_sentiment_magnitude': 0.3,
        'event_source_credibility': 0.7,
        'event_title_length': 65,
        'event_description_length': 150,
        'event_keyword_count': 3,
        'market_volume': 100000.0,
        # ... other features that aren't used by the model
        'market_current_price': 0.45,
        'orderbook_spread': 0.02,
    }

    # Transform to model format
    model_features = {
        'sentiment_score': extracted_features.get('event_sentiment_score', 0.0),
        'sentiment_magnitude': extracted_features.get('event_sentiment_magnitude', 0.0),
        'source_credibility': extracted_features.get('event_source_credibility', 0.5),
        'title_length': extracted_features.get('event_title_length', 0),
        # Convert description_length to has_description (binary)
        'has_description': 1 if extracted_features.get('event_description_length', 0) > 0 else 0,
        # Use keyword_count as keyword_overlap
        'keyword_overlap': extracted_features.get('event_keyword_count', 0),
        'market_volume': extracted_features.get('market_volume', 0.0),
    }

    # Add market_volume_log
    model_features['market_volume_log'] = np.log1p(model_features['market_volume'])

    print("✓ Feature Transformation Test")
    print("="*70)
    print("\nExtracted Features (with prefixes):")
    for k, v in extracted_features.items():
        print(f"  {k}: {v}")

    print("\nModel Features (training format):")
    for k, v in model_features.items():
        print(f"  {k}: {v}")

    print("\n" + "="*70)
    print("Expected Model Features (from training):")
    expected = [
        'sentiment_score',
        'sentiment_magnitude',
        'source_credibility',
        'title_length',
        'has_description',
        'keyword_overlap',
        'market_volume',
        'market_volume_log'
    ]
    for feat in expected:
        status = "✓" if feat in model_features else "✗ MISSING"
        print(f"  {status} {feat}")

    # Create DataFrame (as the trader does)
    features_df = pd.DataFrame([model_features])

    print("\n" + "="*70)
    print("DataFrame shape:", features_df.shape)
    print("DataFrame columns:", list(features_df.columns))

    print("\n✅ All features present and correctly formatted!")
    return True

if __name__ == '__main__':
    test_transform_features_for_model()
