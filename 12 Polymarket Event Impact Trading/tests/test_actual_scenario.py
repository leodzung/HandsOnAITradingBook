# Test with an actual negative event matched to a market
from event_detector import Event
from feature_extractor import FeatureEngineering
from datetime import datetime
import pickle
import pandas as pd
import numpy as np

# Load model
with open('real_data_model.pkl', 'rb') as f:
    model_data = pickle.load(f)

# Real negative event from logs
event = Event(
    title="Foreigners Dump Record Indian Bonds as Weak Rupee Erodes Returns",
    description="",
    source="Bloomberg Markets",
    published_time=datetime.now(),
    url="https://example.com",
    keywords=["dump", "weak", "erodes"]
)

# Matched to this market
market = {
    'question': 'Putin out as President of Russia in 2025?',
    'current_price': 0.5,
    'volume': 1000,
    'active': True
}

# Extract features
fe = FeatureEngineering()
hist = pd.DataFrame({
    'timestamp': pd.date_range(end=datetime.now(), periods=24, freq='h'),
    'price': [0.5]*24,
    'volume': [1000]*24
})

features = fe.create_training_sample(event, market, hist, {}, use_transformers=True)

print("=== Actual Event-Market Combination ===")
print(f"Event: {event.title[:60]}")
print(f"Market: {market['question']}")
print(f"\nExtracted features:")
print(f"  Sentiment score: {features.get('event_sentiment_score', 0):+.3f}")
print(f"  Sentiment label: {features.get('event_sentiment_label', 'N/A')}")

# Transform to model format
model_features = {
    'sentiment_score': features.get('event_sentiment_score', 0.0),
    'sentiment_magnitude': features.get('event_sentiment_confidence', 0.0),
    'source_credibility': features.get('event_source_credibility', 0.5),
    'title_length': features.get('event_title_length', 0),
    'has_description': 1 if features.get('event_description_length', 0) > 0 else 0,
    'keyword_overlap': features.get('event_keyword_count', 0),
    'market_volume': features.get('market_volume', 0.0),
}
model_features['market_volume_log'] = np.log1p(model_features['market_volume'])

print(f"\nModel input features:")
for k, v in model_features.items():
    print(f"  {k}: {v}")

# Predict
df = pd.DataFrame([model_features])
scaled = model_data['scaler'].transform(df)
pred = model_data['model'].predict(scaled)[0]
prob = model_data['model'].predict_proba(scaled)[0]

print(f"\nModel output:")
print(f"  Prediction: {pred:+d}")
print(f"  Probabilities: [-1]={prob[0]:.3f}, [0]={prob[1]:.3f}, [+1]={prob[2]:.3f}")

# Signal generation
class_to_idx = {-1: 0, 0: 1, 1: 2}
pred_idx = class_to_idx.get(pred, 1)
pred_prob = prob[pred_idx]

if pred == -1:
    expected_return = pred_prob * 0.5
    action = "SELL" if expected_return >= 0.03 else "HOLD (low confidence)"
    print(f"\nSignal: {action}")
    print(f"  Expected return: {expected_return:.4f} (threshold: 0.0300)")
elif pred == 1:
    expected_return = pred_prob * (1 - 0.5)
    action = "BUY" if expected_return >= 0.03 else "HOLD (low confidence)"
    print(f"\nSignal: {action}")
    print(f"  Expected return: {expected_return:.4f} (threshold: 0.0300)")
else:
    print(f"\nSignal: HOLD (neutral prediction)")
