#!/usr/bin/env python3
"""
Real Data Collector for Polymarket Trading System
Collects real markets, events, and historical data
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time
from typing import List, Dict
import os

class PolymarketDataCollector:
    """Collect real data from Polymarket's public API"""

    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"

    def __init__(self, output_dir: str = "data"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.session = requests.Session()

    def get_active_markets(self, limit: int = 100) -> List[Dict]:
        """Fetch currently active markets"""
        print(f"Fetching active markets from Polymarket...")

        try:
            response = self.session.get(
                f"{self.GAMMA_URL}/markets",
                params={'limit': limit, 'active': 'true'},
                timeout=10
            )
            response.raise_for_status()
            markets = response.json()

            print(f"✓ Found {len(markets)} active markets")
            return markets

        except Exception as e:
            print(f"✗ Error fetching markets: {e}")
            return []

    def get_market_details(self, condition_id: str) -> Dict:
        """Get detailed info for a specific market"""
        try:
            response = self.session.get(
                f"{self.GAMMA_URL}/markets/{condition_id}",
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching market {condition_id}: {e}")
            return {}

    def save_markets_snapshot(self, markets: List[Dict], filename: str = None):
        """Save current market snapshot to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"markets_snapshot_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(markets, f, indent=2)

        print(f"✓ Saved {len(markets)} markets to {filepath}")
        return filepath

    def get_market_by_keywords(self, keywords: List[str], limit: int = 50) -> List[Dict]:
        """Search for markets matching keywords"""
        all_markets = self.get_active_markets(limit=limit)

        filtered = []
        for market in all_markets:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()

            # Check if any keyword matches
            for keyword in keywords:
                if keyword.lower() in question or keyword.lower() in description:
                    filtered.append(market)
                    break

        print(f"✓ Found {len(filtered)} markets matching keywords: {keywords}")
        return filtered

    def collect_popular_markets(self, min_volume: float = 10000) -> pd.DataFrame:
        """Collect high-volume markets suitable for trading"""
        markets = self.get_active_markets(limit=200)

        # Filter by volume
        high_volume = [
            m for m in markets
            if float(m.get('volume', 0)) >= min_volume
        ]

        # Convert to DataFrame
        df_data = []
        for market in high_volume:
            df_data.append({
                'condition_id': market.get('condition_id'),
                'question': market.get('question'),
                'category': ','.join(market.get('tags', [])),
                'volume': float(market.get('volume', 0)),
                'liquidity': float(market.get('liquidity', 0)),
                'end_date': market.get('end_date_iso'),
                'active': market.get('active'),
                'created_at': market.get('created_at')
            })

        df = pd.DataFrame(df_data)

        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self.output_dir, f"high_volume_markets_{timestamp}.csv")
        df.to_csv(filepath, index=False)

        print(f"✓ Saved {len(df)} high-volume markets to {filepath}")
        return df


class NewsDataCollector:
    """Collect real news data"""

    def __init__(self, newsapi_key: str = None, output_dir: str = "data"):
        self.api_key = newsapi_key
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def collect_news(self, query: str, days_back: int = 7) -> List[Dict]:
        """Collect news articles from NewsAPI"""
        if not self.api_key or self.api_key == "YOUR_NEWS_API_KEY":
            print("⚠️  NewsAPI key not configured")
            print("Sign up at: https://newsapi.org/register")
            return []

        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')

        url = "https://newsapi.org/v2/everything"
        params = {
            'q': query,
            'from': from_date,
            'sortBy': 'publishedAt',
            'language': 'en',
            'apiKey': self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            articles = data.get('articles', [])
            print(f"✓ Found {len(articles)} articles for '{query}'")

            return articles

        except Exception as e:
            print(f"✗ Error fetching news: {e}")
            return []

    def save_news(self, articles: List[Dict], filename: str = None):
        """Save articles to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"news_articles_{timestamp}.json"

        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, 'w') as f:
            json.dump(articles, f, indent=2)

        print(f"✓ Saved {len(articles)} articles to {filepath}")
        return filepath


def main():
    """Main data collection workflow"""
    print("="*70)
    print("REAL DATA COLLECTOR - POLYMARKET TRADING SYSTEM")
    print("="*70)

    # Initialize collectors
    poly_collector = PolymarketDataCollector()

    # 1. Collect current Polymarket markets
    print("\n📊 STEP 1: Collecting Polymarket Markets\n")

    markets = poly_collector.get_active_markets(limit=100)

    if markets:
        # Save snapshot
        poly_collector.save_markets_snapshot(markets)

        # Show sample markets
        print("\n📋 Sample Markets:")
        for i, market in enumerate(markets[:5], 1):
            print(f"\n{i}. {market.get('question', 'N/A')}")
            print(f"   Volume: ${float(market.get('volume', 0)):,.2f}")
            print(f"   Category: {', '.join(market.get('tags', []))}")
            print(f"   End Date: {market.get('end_date_iso', 'N/A')}")

        # Collect high-volume markets
        print("\n" + "="*70)
        print("\n💰 STEP 2: Filtering High-Volume Markets\n")

        df = poly_collector.collect_popular_markets(min_volume=5000)

        print(f"\nTop 5 by Volume:")
        print(df.nlargest(5, 'volume')[['question', 'volume', 'category']])

        # Search by category
        print("\n" + "="*70)
        print("\n🔍 STEP 3: Markets by Category\n")

        categories = {
            'crypto': ['bitcoin', 'ethereum', 'crypto'],
            'politics': ['trump', 'election', 'president'],
            'sports': ['nba', 'nfl', 'superbowl']
        }

        for category, keywords in categories.items():
            matches = poly_collector.get_market_by_keywords(keywords, limit=100)

            if matches:
                filename = f"markets_{category}.json"
                poly_collector.save_markets_snapshot(matches, filename)
                print(f"  • {category.title()}: {len(matches)} markets")

    # 2. News collection (if API key available)
    print("\n" + "="*70)
    print("\n📰 STEP 4: News Collection\n")

    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            newsapi_key = config.get('news_api_key')
    except:
        newsapi_key = None

    news_collector = NewsDataCollector(newsapi_key)

    if newsapi_key and newsapi_key != "YOUR_NEWS_API_KEY":
        # Collect news for popular topics
        topics = ['bitcoin', 'trump election', 'federal reserve']

        for topic in topics:
            articles = news_collector.collect_news(topic, days_back=7)
            if articles:
                news_collector.save_news(articles, f"news_{topic.replace(' ', '_')}.json")
    else:
        print("⚠️  NewsAPI key not configured")
        print("\nTo collect news data:")
        print("1. Sign up at: https://newsapi.org/register")
        print("2. Get your free API key")
        print("3. Add to config.json: \"news_api_key\": \"your-key-here\"")
        print("4. Run this script again")

    # Summary
    print("\n" + "="*70)
    print("✅ DATA COLLECTION COMPLETE")
    print("="*70)

    print("\n📁 Collected Data Files:")
    data_files = os.listdir('data')
    for f in sorted(data_files):
        filepath = os.path.join('data', f)
        size = os.path.getsize(filepath)
        print(f"  • {f} ({size:,} bytes)")

    print("\n🎯 Next Steps:")
    print("1. Review collected market data in data/ folder")
    print("2. Get NewsAPI key to collect historical events")
    print("3. Run: python3 build_training_dataset.py")
    print("4. Train model on real data")


if __name__ == '__main__':
    main()
