#!/usr/bin/env python3
"""
Quick Demo of Polymarket Trading System
Shows event detection, feature extraction, model training, and backtesting
No API keys required!
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import our modules
from event_detector import Event, EventMatcher
from feature_extractor import FeatureEngineering, SentimentAnalyzer
from models import PriceMovementPredictor, TradingSignalGenerator
from backtester import Backtester, create_sample_signals, create_sample_prices

print("="*70)
print("POLYMARKET EVENT IMPACT TRADING SYSTEM - DEMO")
print("="*70)

# ============================================================================
# STEP 1: Event Detection Demo
# ============================================================================
print("\n📰 STEP 1: Event Detection\n")
print("Simulating recent events (in production, these come from NewsAPI/RSS)...")

# Create sample events
events = [
    Event(
        title="Bitcoin surges to $75K on institutional buying",
        description="Major financial institutions announced new cryptocurrency allocations, pushing Bitcoin to all-time highs.",
        source="Bloomberg",
        published_time=datetime.now() - timedelta(minutes=30),
        url="https://example.com/bitcoin-surge",
        keywords=["Bitcoin", "cryptocurrency", "institutional", "surge", "price"]
    ),
    Event(
        title="Trump announces 2028 presidential campaign",
        description="Former President Trump officially filed paperwork for 2028 election run.",
        source="Reuters",
        published_time=datetime.now() - timedelta(minutes=15),
        url="https://example.com/trump-2028",
        keywords=["Trump", "2028", "election", "presidential", "campaign"]
    ),
    Event(
        title="Fed signals potential rate cut in Q2",
        description="Federal Reserve chairman indicated rates may be reduced if inflation continues declining.",
        source="Wall Street Journal",
        published_time=datetime.now() - timedelta(minutes=5),
        url="https://example.com/fed-rates",
        keywords=["Fed", "rates", "inflation", "economy", "cut"]
    )
]

for i, event in enumerate(events, 1):
    print(f"{i}. {event.title}")
    print(f"   Source: {event.source} | Time: {event.published_time.strftime('%I:%M %p')}")
    print(f"   Keywords: {', '.join(event.keywords[:5])}")
    print()

# ============================================================================
# STEP 2: Feature Extraction Demo
# ============================================================================
print("="*70)
print("\n🔬 STEP 2: Feature Extraction\n")

feature_eng = FeatureEngineering()

# Analyze first event
event = events[0]
print(f"Analyzing: '{event.title}'\n")

event_features = feature_eng.event_extractor.extract_event_features(event)

print("Event Features:")
for key, value in list(event_features.items())[:8]:
    if isinstance(value, float):
        print(f"  • {key}: {value:.3f}")
    else:
        print(f"  • {key}: {value}")

# ============================================================================
# STEP 3: Model Training Demo
# ============================================================================
print("\n" + "="*70)
print("\n🤖 STEP 3: Machine Learning Model Training\n")

print("Generating synthetic training data (1000 samples)...")

# Generate synthetic training data
np.random.seed(42)
n_samples = 1000

feature_names = [
    'event_sentiment_score', 'event_sentiment_magnitude', 'event_source_credibility',
    'market_current_price', 'market_price_volatility', 'market_price_trend',
    'market_total_volume', 'orderbook_spread', 'orderbook_depth_imbalance'
]

# Create features
X_train = pd.DataFrame(
    np.random.randn(n_samples, len(feature_names)),
    columns=feature_names
)

# Normalize some features
X_train['event_sentiment_score'] = np.random.uniform(-1, 1, n_samples)
X_train['event_source_credibility'] = np.random.uniform(0.3, 1.0, n_samples)
X_train['market_current_price'] = np.random.uniform(0.2, 0.8, n_samples)
X_train['orderbook_spread'] = np.random.uniform(0.01, 0.1, n_samples)

# Create labels based on sentiment (positive sentiment -> more likely up)
probs = X_train['event_sentiment_score'].apply(
    lambda x: [0.2, 0.3, 0.5] if x > 0.3 else [0.5, 0.3, 0.2] if x < -0.3 else [0.33, 0.34, 0.33]
)
y_train = np.array([np.random.choice([1, 0, -1], p=p) for p in probs])

print(f"Training data: {X_train.shape[0]} samples, {X_train.shape[1]} features")
print(f"Label distribution: {pd.Series(y_train).value_counts().to_dict()}")
print()

# Train Random Forest model
print("Training Random Forest model...")
model = PriceMovementPredictor(model_type='random_forest')
metrics = model.train(X_train, y_train, validation_split=0.2)

print(f"\n✓ Training complete!")
print(f"  Train Accuracy: {metrics['train_accuracy']:.1%}")
print(f"  Validation Accuracy: {metrics['val_accuracy']:.1%}")
print(f"  Validation F1 Score: {metrics['val_f1']:.3f}")

# Show feature importance
print("\n📊 Top 5 Most Important Features:")
importance = model.get_feature_importance()
for idx, row in importance.head(5).iterrows():
    print(f"  {idx+1}. {row['feature']}: {row['importance']:.3f}")

# ============================================================================
# STEP 4: Signal Generation Demo
# ============================================================================
print("\n" + "="*70)
print("\n💡 STEP 4: Trading Signal Generation\n")

signal_gen = TradingSignalGenerator(
    model=model,
    min_confidence=0.65,
    min_expected_return=0.03
)

# Generate signal for sample features
sample_features = X_train.iloc[[0]].copy()
current_price = 0.45

signal = signal_gen.generate_signal(sample_features, current_price)

print(f"Market Price: ${current_price:.2f}")
print(f"\nSignal Generated:")
print(f"  Action: {signal['action']}")
print(f"  Confidence: {signal.get('confidence', 0):.1%}")
print(f"  Reason: {signal['reason']}")
if 'expected_return' in signal:
    print(f"  Expected Return: {signal['expected_return']:.2%}")
if 'suggested_price' in signal:
    print(f"  Suggested Entry: ${signal['suggested_price']:.3f}")

# ============================================================================
# STEP 5: Backtesting Demo
# ============================================================================
print("\n" + "="*70)
print("\n📈 STEP 5: Backtesting Strategy\n")

print("Creating sample market data (200 trades over 30 days)...")

# Generate signals
signals_df = create_sample_signals(n_signals=200, n_markets=20)

# Generate price data
market_ids = signals_df['market_id'].unique()
start_time = signals_df['timestamp'].min()
end_time = signals_df['timestamp'].max()
price_data = create_sample_prices(market_ids, start_time, end_time)

print(f"Generated {len(signals_df)} signals across {len(market_ids)} markets")
print()

# Run backtest
print("Running backtest...")
backtester = Backtester(
    initial_capital=10000,
    position_size=100,
    hold_time_hours=24,
    max_positions=10
)

results = backtester.run_backtest(signals_df, price_data)

# Display results
print("\n" + "="*70)
print("BACKTEST RESULTS")
print("="*70)
print(f"\n💰 Performance Metrics:")
print(f"  Initial Capital: ${backtester.initial_capital:,.2f}")
print(f"  Final Equity: ${results.get('final_equity', 0):,.2f}")
print(f"  Total Return: {results.get('total_return_pct', 0):.2f}%")
print(f"  Total PnL: ${results.get('total_pnl', 0):.2f}")

print(f"\n📊 Trading Statistics:")
print(f"  Total Trades: {results.get('total_trades', 0)}")
print(f"  Winning Trades: {results.get('winning_trades', 0)}")
print(f"  Losing Trades: {results.get('losing_trades', 0)}")
print(f"  Win Rate: {results.get('win_rate', 0):.1f}%")

print(f"\n📈 Risk Metrics:")
print(f"  Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
print(f"  Max Drawdown: {results.get('max_drawdown_pct', 0):.2f}%")
print(f"  Profit Factor: {results.get('profit_factor', 0):.2f}")

print(f"\n💵 Trade Analysis:")
print(f"  Average Win: ${results.get('avg_win', 0):.2f}")
print(f"  Average Loss: ${results.get('avg_loss', 0):.2f}")

# ============================================================================
# STEP 6: Next Steps
# ============================================================================
print("\n" + "="*70)
print("✅ DEMO COMPLETE!")
print("="*70)

print("""
🎯 What You Just Saw:

1. ✓ Event detection from news sources
2. ✓ Feature extraction (sentiment, credibility, market data)
3. ✓ ML model training (Random Forest classifier)
4. ✓ Signal generation with confidence thresholds
5. ✓ Complete backtesting framework

📚 Next Steps:

1. Open research.ipynb in Jupyter to explore interactively
2. Get NewsAPI key (free) at https://newsapi.org
3. Add API key to config.json
4. Run real event detection with RSS feeds
5. Start paper trading with trader.py

💡 To Run Live Paper Trading:

   python3 trader.py

   (This will monitor real markets and events, but won't use real money)

⚠️  Before Real Trading:

   - Collect historical event + price data
   - Retrain model on real data
   - Test thoroughly in paper trading mode
   - Start with small position sizes ($10-50)

🚀 Ready to explore more? Open the research notebook!
""")

print("="*70)
