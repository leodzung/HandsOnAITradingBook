#!/usr/bin/env python3
"""
Build Training Dataset from Collected Data
Matches events to markets and creates labeled training data
"""

import pandas as pd
import json
import os
from datetime import datetime
from typing import List, Dict
import numpy as np

def load_markets(data_dir: str = "data") -> pd.DataFrame:
    """Load collected market data"""
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]

    if not csv_files:
        print("No CSV files found in data/ directory")
        return pd.DataFrame()

    # Load most recent high-volume markets file
    latest_file = sorted(csv_files)[-1]
    filepath = os.path.join(data_dir, latest_file)

    print(f"Loading markets from: {filepath}")
    df = pd.read_csv(filepath)

    return df

def analyze_markets(df: pd.DataFrame):
    """Analyze collected market data"""
    print("\n" + "="*70)
    print("MARKET DATA ANALYSIS")
    print("="*70)

    print(f"\nTotal Markets: {len(df)}")

    # Volume statistics
    print(f"\nVolume Statistics:")
    print(f"  Total Volume: ${df['volume'].sum():,.2f}")
    print(f"  Average Volume: ${df['volume'].mean():,.2f}")
    print(f"  Median Volume: ${df['volume'].median():,.2f}")
    print(f"  Max Volume: ${df['volume'].max():,.2f}")

    # Category breakdown
    if 'category' in df.columns and df['category'].notna().any():
        print(f"\nTop Categories:")
        categories = df['category'].value_counts().head(10)
        for cat, count in categories.items():
            print(f"  {cat}: {count} markets")

    # Market types (from questions)
    print(f"\nMarket Types (inferred from questions):")

    keywords = {
        'Election/Politics': ['election', 'president', 'trump', 'biden', 'vote'],
        'Crypto/DeFi': ['bitcoin', 'ethereum', 'btc', 'eth', 'defi', 'crypto'],
        'COVID-19': ['coronavirus', 'covid', 'vaccine', 'pandemic'],
        'Sports': ['nba', 'nfl', 'superbowl', 'world series', 'ufc'],
        'Business/IPO': ['ipo', 'publicly trading', 'stock', 'airbnb', 'coinbase'],
        'Entertainment': ['kardashian', 'drake', 'album', 'movie']
    }

    type_counts = {}
    for market_type, words in keywords.items():
        count = df['question'].str.lower().str.contains('|'.join(words), na=False).sum()
        if count > 0:
            type_counts[market_type] = count

    for mtype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {mtype}: {count} markets")

def create_example_training_samples(df: pd.DataFrame, n_samples: int = 20) -> pd.DataFrame:
    """Create example training samples with synthetic labels"""
    print("\n" + "="*70)
    print("CREATING EXAMPLE TRAINING SAMPLES")
    print("="*70)

    samples = []

    # Select diverse markets
    high_volume = df.nlargest(n_samples, 'volume')

    for idx, market in high_volume.iterrows():
        question = market['question']

        # Simulate features (in production, these would come from real events + prices)
        sample = {
            'market_id': market.get('condition_id', f'market_{idx}'),
            'market_question': question,
            'market_volume': market['volume'],

            # Event features (simulated)
            'event_sentiment': np.random.uniform(-0.5, 0.5),
            'event_credibility': np.random.uniform(0.6, 1.0),
            'event_recency_hours': np.random.uniform(0.1, 24),

            # Market features (simulated)
            'price_before_event': np.random.uniform(0.3, 0.7),
            'price_volatility': np.random.uniform(0.01, 0.1),
            'orderbook_spread': np.random.uniform(0.01, 0.05),

            # Label (simulated - in production, this would be actual price change)
            'price_after_1h': np.random.uniform(0.3, 0.7),
        }

        # Calculate label
        price_change = sample['price_after_1h'] - sample['price_before_event']

        if price_change > 0.02:
            sample['label'] = 1  # UP
        elif price_change < -0.02:
            sample['label'] = -1  # DOWN
        else:
            sample['label'] = 0  # NO CHANGE

        sample['price_change'] = price_change

        samples.append(sample)

    df_samples = pd.DataFrame(samples)

    print(f"\n✓ Created {len(df_samples)} training samples")
    print(f"\nLabel Distribution:")
    print(df_samples['label'].value_counts().to_dict())

    return df_samples

def save_training_data(df: pd.DataFrame, output_dir: str = "data"):
    """Save training dataset"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"training_dataset_{timestamp}.csv")

    df.to_csv(filepath, index=False)
    print(f"\n✓ Saved training data to: {filepath}")

    return filepath

def get_newsapi_instructions():
    """Print instructions for getting NewsAPI key"""
    print("\n" + "="*70)
    print("📰 HOW TO GET REAL NEWS DATA")
    print("="*70)

    print("""
To collect real historical news events:

1. 🌐 Go to: https://newsapi.org/register

2. 📝 Create free account:
   - Enter your email
   - Choose a password
   - Select "Individual" plan (FREE)

3. 🔑 Get your API key:
   - Check your email for confirmation
   - Login to NewsAPI
   - Copy your API key

4. ⚙️  Configure:
   - Open config.json
   - Replace "YOUR_NEWS_API_KEY" with your actual key
   - Save the file

5. ▶️  Re-run data collector:
   python3 data_collector.py

FREE Tier Limits:
  • 500 requests per day
  • 7 days of historical data
  • All news sources included

This is enough to collect:
  • ~500 events per day
  • Historical data for training
  • Real-time monitoring for paper trading

💡 Pro Tip: Collect data over multiple days to build a larger dataset!
""")

def main():
    """Main workflow"""
    print("="*70)
    print("TRAINING DATASET BUILDER")
    print("="*70)

    # 1. Load collected markets
    print("\n📊 Step 1: Loading Market Data...")
    df_markets = load_markets()

    if len(df_markets) == 0:
        print("\n⚠️  No market data found!")
        print("Run: python3 data_collector.py first")
        return

    # 2. Analyze markets
    analyze_markets(df_markets)

    # 3. Create example training samples
    df_training = create_example_training_samples(df_markets, n_samples=50)

    # 4. Save training data
    filepath = save_training_data(df_training)

    # 5. Show sample
    print("\n" + "="*70)
    print("SAMPLE TRAINING DATA")
    print("="*70)

    print("\nFirst 3 samples:")
    print(df_training[['market_question', 'event_sentiment', 'price_before_event',
                      'price_after_1h', 'price_change', 'label']].head(3).to_string())

    # 6. Show next steps
    print("\n" + "="*70)
    print("✅ DATASET CREATED")
    print("="*70)

    print(f"\n📁 File: {filepath}")
    print(f"📊 Samples: {len(df_training)}")
    print(f"📈 Features: {len(df_training.columns)}")

    print("\n⚠️  IMPORTANT: This dataset uses SIMULATED labels!")
    print("\nFor real training data, you need:")
    print("1. ✓ Real markets (DONE - we have these!)")
    print("2. ✗ Real news events (need NewsAPI key)")
    print("3. ✗ Historical price data (need to collect over time)")
    print("4. ✗ Match events to price movements (need to build)")

    # Instructions
    get_newsapi_instructions()

    print("\n" + "="*70)
    print("🎯 IMMEDIATE NEXT STEPS:")
    print("="*70)
    print("\n1. Get NewsAPI key (5 minutes)")
    print("2. Run: python3 data_collector.py")
    print("3. Collect data over 7-14 days")
    print("4. Build real training dataset")
    print("5. Train production model!")

if __name__ == '__main__':
    main()
