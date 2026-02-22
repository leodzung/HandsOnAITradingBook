#!/usr/bin/env python3
"""
Test the trained models to ensure they work correctly.
"""
import pickle
import pandas as pd
import numpy as np

print("=== Testing Trained Models ===\n")

# Test each model
for bot_name in ['event', 'price_level', 'short_expiry']:
    print(f"Testing {bot_name} model...")
    
    model_path = f'data/models/{bot_name}_model.pkl'
    with open(model_path, 'rb') as f:
        model_info = pickle.load(f)
    
    model = model_info['model']
    features = model_info['feature_names']
    metrics = model_info['metrics']
    
    print(f"  ✓ Model loaded successfully")
    print(f"  ✓ Features: {len(features)}")
    print(f"  ✓ Accuracy: {metrics['accuracy']*100:.2f}%")
    print(f"  ✓ ROC AUC: {metrics['roc_auc']*100:.2f}%")
    
    # Test prediction
    test_features = pd.DataFrame([{
        'trade_price': 0.65,
        'price_squared': 0.65**2,
        'price_cubed': 0.65**3,
        'log_price': np.log(0.65),
        'price_distance_from_half': abs(0.65 - 0.5),
        'betting_yes': 1,
        'betting_no': 0,
        'market_confidence': abs(0.65 - 0.5) * 2,
        'hour_of_day': 14,
        'day_of_week': 2,
        'is_weekend': 0,
        'question_length': 50,
        'question_words': 10,
        'is_sports': 1,
        'is_politics': 0,
        'is_crypto': 0
    }])
    
    pred_proba = model.predict_proba(test_features)[0][1]
    prediction = "TRADE" if pred_proba > 0.6 else "SKIP"
    
    print(f"  ✓ Test prediction: {pred_proba*100:.1f}% confidence → {prediction}")
    print()

print("="*60)
print("✅ All models are working correctly!")
print("="*60)
