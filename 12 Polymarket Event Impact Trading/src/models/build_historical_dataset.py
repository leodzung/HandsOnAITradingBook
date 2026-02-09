#!/usr/bin/env python3
"""
Build Historical Training Dataset
Use resolved Polymarket markets + historical news to create real training data.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np

from polymarket_client import PolymarketClient
from event_detector import NewsAPIDetector, RSSFeedDetector, Event
from feature_extractor import FeatureEngineering


class HistoricalDatasetBuilder:
    """Build training dataset from historical resolved markets."""

    def __init__(self, news_api_key: str):
        self.client = PolymarketClient()
        self.news_detector = NewsAPIDetector(api_key=news_api_key)
        self.rss_detector = RSSFeedDetector([
            "https://feeds.bloomberg.com/markets/news.rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://www.reuters.com/rssFeed/topNews"
        ])
        self.feature_engineering = FeatureEngineering()

    def get_resolved_markets(self, limit: int = 200) -> List[Dict]:
        """
        Get resolved markets from Polymarket.

        Returns:
            List of resolved market dictionaries with outcomes
        """
        print(f"Fetching {limit} resolved markets...")
        markets = self.client.get_markets(limit=limit, closed=True, active=False)

        # Filter for markets with clear outcomes
        resolved = []
        for market in markets:
            if 'outcomePrices' in market and market['outcomePrices']:
                prices = market['outcomePrices']

                # Parse if it's a JSON string
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except:
                        continue

                # Determine winner
                if isinstance(prices, list) and len(prices) == 2:
                    yes_price = float(prices[0])
                    no_price = float(prices[1])

                    # Clear resolution: one price near 1.0, other near 0.0
                    if yes_price > 0.99:
                        market['outcome_label'] = 1  # YES/UP
                    elif no_price > 0.99:
                        market['outcome_label'] = -1  # NO/DOWN
                    else:
                        market['outcome_label'] = 0  # UNCLEAR/NEUTRAL

                    resolved.append(market)

        print(f"Found {len(resolved)} markets with clear outcomes")
        return resolved

    def get_historical_news(self, days_back: int = 30) -> List[Event]:
        """
        Get historical news events.

        Args:
            days_back: How many days of history to retrieve

        Returns:
            List of Event objects
        """
        print(f"Fetching news from last {days_back} days...")

        # NewsAPI limits free tier to 1 month
        max_days = min(days_back, 30)

        events = self.news_detector.get_recent_news(
            lookback_hours=max_days * 24
        )

        # Also try RSS feeds for more recent events
        rss_events = self.rss_detector.get_recent_news(
            lookback_hours=7 * 24  # Last week
        )

        all_events = events + rss_events
        print(f"Retrieved {len(all_events)} historical news events")

        return all_events

    def match_events_to_markets(self, events: List[Event], markets: List[Dict]) -> List[Tuple]:
        """
        Match news events to market outcomes.

        Returns:
            List of (event, market, outcome_label) tuples
        """
        print("\nMatching events to markets...")
        matches = []

        for market in markets:
            question = market.get('question', '').lower()
            market_keywords = set(question.split())

            # Try to find relevant news event
            best_match = None
            best_score = 0

            for event in events:
                # Simple keyword matching
                event_text = f"{event.title} {event.description}".lower()
                event_keywords = set(event_text.split())

                # Calculate overlap
                overlap = len(market_keywords & event_keywords)
                if overlap > best_score:
                    best_score = overlap
                    best_match = event

            # If we found a reasonable match
            if best_match and best_score >= 2:
                matches.append((best_match, market, market['outcome_label']))

        print(f"Matched {len(matches)} event-market pairs")
        return matches

    def build_training_dataset(self, matches: List[Tuple]) -> pd.DataFrame:
        """
        Build feature matrix and labels from matched pairs.

        Returns:
            DataFrame with features and outcome labels
        """
        print("\nBuilding training dataset...")

        training_data = []

        for event, market, outcome_label in matches:
            # Extract features
            try:
                # Create dummy historical prices (we don't have this)
                hist_prices = pd.DataFrame({
                    'timestamp': pd.date_range(end=datetime.now(), periods=24, freq='h'),
                    'price': [0.5] * 24,
                    'volume': [1000] * 24
                })

                # Empty orderbook
                orderbook = {'bids': [], 'asks': []}

                # Extract features with FinBERT
                features = self.feature_engineering.create_training_sample(
                    event=event,
                    market=market,
                    historical_prices=hist_prices,
                    orderbook=orderbook,
                    use_transformers=True  # Use FinBERT!
                )

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
                model_features['outcome'] = outcome_label

                training_data.append(model_features)

            except Exception as e:
                print(f"Error processing {market.get('question', 'unknown')[:50]}: {e}")
                continue

        df = pd.DataFrame(training_data)
        print(f"Created dataset with {len(df)} samples")

        # Show distribution
        if len(df) > 0:
            print(f"\nOutcome distribution:")
            print(df['outcome'].value_counts())

        return df

    def save_dataset(self, df: pd.DataFrame, filepath: str = 'historical_training_data.csv'):
        """Save dataset to CSV."""
        df.to_csv(filepath, index=False)
        print(f"\n✅ Saved dataset to {filepath}")
        print(f"   Samples: {len(df)}")
        print(f"   Features: {len(df.columns) - 1}")  # -1 for outcome column


def main():
    """Build historical training dataset."""

    print("="*70)
    print("HISTORICAL DATASET BUILDER")
    print("="*70)

    # Configuration
    news_api_key = "68502b258cb1434383fa7acce16ce420"

    # Initialize builder
    builder = HistoricalDatasetBuilder(news_api_key=news_api_key)

    # Step 1: Get resolved markets
    markets = builder.get_resolved_markets(limit=200)

    # Step 2: Get historical news
    events = builder.get_historical_news(days_back=30)

    # Step 3: Match events to markets
    matches = builder.match_events_to_markets(events, markets)

    if len(matches) == 0:
        print("\n⚠️ No matches found. Try:")
        print("  1. Increase lookback period")
        print("  2. Use better matching algorithm")
        print("  3. Fetch more markets/events")
        return

    # Step 4: Build training dataset
    df = builder.build_training_dataset(matches)

    # Step 5: Save dataset
    if len(df) > 0:
        builder.save_dataset(df, 'historical_training_data.csv')

        print("\n" + "="*70)
        print("✅ HISTORICAL DATASET COMPLETE")
        print("="*70)
        print("\nNext steps:")
        print("1. Review the dataset: historical_training_data.csv")
        print("2. Retrain model: python3 retrain_model.py")
        print("3. Test new model: python3 test_bot_restart.py")
        print("4. Deploy: Restart trader.py with new model")
    else:
        print("\n❌ No training data generated")


if __name__ == '__main__':
    main()
