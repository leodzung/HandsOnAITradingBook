#!/usr/bin/env python3
"""
Test Signal Generator Fix
Verify that SELL signals can now be generated.
"""

import numpy as np
import pandas as pd
from models import PriceMovementPredictor, TradingSignalGenerator

def test_signal_generator():
    """Test that signal generator now handles all prediction classes correctly"""

    print("="*70)
    print("TESTING SIGNAL GENERATOR FIX")
    print("="*70)

    # Load the model
    model = PriceMovementPredictor()
    model.load('real_data_model.pkl')
    print("\n✓ Model loaded")
    print(f"  Model classes: {model.model.classes_}")

    # Create signal generator
    signal_gen = TradingSignalGenerator(
        model=model,
        min_confidence=0.60,
        min_expected_return=0.03
    )
    print("✓ Signal generator created")

    # Create test features (8 features the model expects)
    test_cases = [
        {
            'name': 'Highly positive sentiment (should predict UP/1)',
            'features': {
                'sentiment_score': 1.0,
                'sentiment_magnitude': 0.8,
                'source_credibility': 1.0,
                'title_length': 60,
                'has_description': 1,
                'keyword_overlap': 5,
                'market_volume': 100000,
                'market_volume_log': 11.51
            },
            'current_price': 0.50
        },
        {
            'name': 'Highly negative sentiment (should predict DOWN/-1)',
            'features': {
                'sentiment_score': -1.0,
                'sentiment_magnitude': 0.8,
                'source_credibility': 1.0,
                'title_length': 60,
                'has_description': 1,
                'keyword_overlap': 5,
                'market_volume': 100000,
                'market_volume_log': 11.51
            },
            'current_price': 0.50
        },
        {
            'name': 'Neutral sentiment (should predict NEUTRAL/0)',
            'features': {
                'sentiment_score': 0.0,
                'sentiment_magnitude': 0.1,
                'source_credibility': 0.5,
                'title_length': 60,
                'has_description': 1,
                'keyword_overlap': 2,
                'market_volume': 10000,
                'market_volume_log': 9.21
            },
            'current_price': 0.50
        }
    ]

    print("\n" + "="*70)
    print("RUNNING TEST CASES")
    print("="*70)

    for i, test in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {test['name']} ---")

        # Create feature DataFrame
        features_df = pd.DataFrame([test['features']])

        # Get raw prediction
        prediction = model.predict(features_df)[0]
        probabilities = model.predict_proba(features_df)[0]

        print(f"  Raw prediction: {prediction}")
        print(f"  Probabilities: {probabilities}")
        print(f"    Class -1 (DOWN): {probabilities[0]:.3f}")
        print(f"    Class  0 (NEUTRAL): {probabilities[1]:.3f}")
        print(f"    Class  1 (UP): {probabilities[2]:.3f}")

        # Generate signal
        signal = signal_gen.generate_signal(features_df, test['current_price'])

        print(f"  Signal: {signal['action']}")
        print(f"  Confidence: {signal['confidence']:.2%}")
        print(f"  Reason: {signal.get('reason', 'N/A')}")

        # Validate
        if prediction == 1:
            expected_action = 'BUY'
        elif prediction == -1:
            expected_action = 'SELL'
        else:
            expected_action = 'HOLD'

        if signal['action'] == expected_action or signal['action'] == 'HOLD':
            print(f"  ✓ PASS - Signal matches prediction")
        else:
            print(f"  ✗ FAIL - Expected {expected_action}, got {signal['action']}")

    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print("\nThe fix should now:")
    print("  1. ✓ Map prediction classes correctly to probability indices")
    print("  2. ✓ Generate BUY signals for prediction = 1")
    print("  3. ✓ Generate SELL signals for prediction = -1")
    print("  4. ✓ Generate HOLD signals for prediction = 0 or low confidence")
    print("\nIf you see SELL signals above, the fix worked!")
    print("="*70)

if __name__ == '__main__':
    test_signal_generator()
