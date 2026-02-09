#!/usr/bin/env python3
"""
Create Real Training Dataset
Matches real news events to Polymarket markets
"""

import json
import pandas as pd
from datetime import datetime
import re
from typing import List, Dict

def load_news() -> Dict[str, List[Dict]]:
    """Load all collected news articles"""
    news_data = {}

    topics = ['bitcoin', 'trump_election', 'federal_reserve']

    for topic in topics:
        try:
            with open(f'data/news_{topic}.json', 'r') as f:
                articles = json.load(f)
                news_data[topic] = articles
                print(f"✓ Loaded {len(articles)} {topic} articles")
        except FileNotFoundError:
            print(f"⚠️  No news file for {topic}")

    return news_data

def load_markets() -> pd.DataFrame:
    """Load collected markets"""
    try:
        df = pd.read_csv('data/high_volume_markets_20251227_191527.csv')
        print(f"✓ Loaded {len(df)} markets")
        return df
    except FileNotFoundError:
        df = pd.read_csv('data/high_volume_markets_20251227_142323.csv')
        print(f"✓ Loaded {len(df)} markets")
        return df

def extract_keywords(text: str) -> List[str]:
    """Extract keywords from text"""
    if not text:
        return []

    # Extract capitalized words and important terms
    words = re.findall(r'\b[A-Z][a-z]{2,}\b|\b[A-Z]{2,}\b', text)
    # Also get important lowercase words
    important_words = ['bitcoin', 'ethereum', 'trump', 'biden', 'election',
                      'fed', 'federal', 'reserve', 'rate', 'inflation']

    text_lower = text.lower()
    for word in important_words:
        if word in text_lower and word.title() not in words:
            words.append(word.title())

    return list(set(words))[:15]  # Top 15 unique keywords

def match_article_to_markets(article: Dict, markets_df: pd.DataFrame) -> List[str]:
    """Match a news article to relevant markets"""
    title = article.get('title', '')
    description = article.get('description', '')
    content = article.get('content', '')

    article_text = f"{title} {description} {content}".lower()
    article_keywords = set(extract_keywords(article_text))

    matched_markets = []

    for idx, market in markets_df.iterrows():
        question = str(market.get('question', '')).lower()

        # Extract market keywords
        market_keywords = set(extract_keywords(question))

        # Calculate keyword overlap
        overlap = len(article_keywords & market_keywords)

        # Match if at least 2 keywords overlap
        if overlap >= 2:
            matched_markets.append({
                'market_id': market.get('condition_id', f'market_{idx}'),
                'question': market['question'],
                'volume': market['volume'],
                'overlap': overlap
            })

    # Sort by overlap score
    matched_markets.sort(key=lambda x: x['overlap'], reverse=True)

    return matched_markets[:5]  # Top 5 matches

def create_training_samples(news_data: Dict[str, List[Dict]],
                            markets_df: pd.DataFrame) -> pd.DataFrame:
    """Create training samples from news + markets"""

    samples = []

    for topic, articles in news_data.items():
        print(f"\nProcessing {topic}...")
        matches_found = 0

        for article in articles[:50]:  # Process first 50 articles per topic
            matched_markets = match_article_to_markets(article, markets_df)

            if matched_markets:
                matches_found += 1

                # Use best match
                best_match = matched_markets[0]

                # Extract features from article
                title = article.get('title', '')
                description = article.get('description', '')

                # Simple sentiment analysis
                positive_words = ['surge', 'rise', 'gain', 'up', 'high', 'win', 'success']
                negative_words = ['fall', 'drop', 'decline', 'down', 'low', 'lose', 'fail']

                text_lower = f"{title} {description}".lower()

                pos_count = sum(1 for word in positive_words if word in text_lower)
                neg_count = sum(1 for word in negative_words if word in text_lower)

                sentiment = (pos_count - neg_count) / max(pos_count + neg_count, 1)

                # Get source credibility
                source = article.get('source', {}).get('name', '')
                credible_sources = ['Reuters', 'Bloomberg', 'WSJ', 'Financial Times',
                                  'Associated Press', 'CNBC', 'CBS News']
                credibility = 1.0 if source in credible_sources else 0.7

                # Create sample
                sample = {
                    'article_title': title[:100],
                    'source': source,
                    'published_at': article.get('publishedAt', ''),
                    'market_question': best_match['question'][:100],
                    'market_volume': best_match['volume'],
                    'topic': topic,

                    # Features
                    'sentiment_score': sentiment,
                    'sentiment_magnitude': pos_count + neg_count,
                    'source_credibility': credibility,
                    'title_length': len(title),
                    'has_description': 1 if description else 0,
                    'keyword_overlap': best_match['overlap'],

                    # NOTE: In production, you would track actual price changes
                    # For now, we'll create synthetic labels for demonstration
                    'label_note': 'SYNTHETIC - Replace with actual price movement data'
                }

                samples.append(sample)

        print(f"  ✓ Found {matches_found} article-market matches")

    df = pd.DataFrame(samples)
    return df

def main():
    print("="*70)
    print("CREATING REAL TRAINING DATASET")
    print("="*70)

    # Load data
    print("\n📊 Loading collected data...")
    news_data = load_news()
    markets_df = load_markets()

    total_articles = sum(len(articles) for articles in news_data.values())
    print(f"\n✓ Total: {total_articles} articles, {len(markets_df)} markets")

    # Match and create samples
    print("\n" + "="*70)
    print("🔗 MATCHING NEWS TO MARKETS")
    print("="*70)

    df_samples = create_training_samples(news_data, markets_df)

    # Save dataset
    print("\n" + "="*70)
    print("💾 SAVING DATASET")
    print("="*70)

    filename = 'data/real_training_dataset.csv'
    df_samples.to_csv(filename, index=False)

    print(f"\n✓ Saved {len(df_samples)} samples to {filename}")

    # Show statistics
    print("\n" + "="*70)
    print("📈 DATASET STATISTICS")
    print("="*70)

    print(f"\nTotal Samples: {len(df_samples)}")
    print(f"\nSamples by Topic:")
    print(df_samples['topic'].value_counts())

    print(f"\nSentiment Distribution:")
    print(f"  Positive (>0.2): {len(df_samples[df_samples['sentiment_score'] > 0.2])}")
    print(f"  Neutral (-0.2 to 0.2): {len(df_samples[abs(df_samples['sentiment_score']) <= 0.2])}")
    print(f"  Negative (<-0.2): {len(df_samples[df_samples['sentiment_score'] < -0.2])}")

    print(f"\nTop Sources:")
    print(df_samples['source'].value_counts().head())

    # Show samples
    print("\n" + "="*70)
    print("🔍 SAMPLE DATA")
    print("="*70)

    print("\nFirst 3 matches:")
    for idx, row in df_samples.head(3).iterrows():
        print(f"\n{idx+1}. Article: {row['article_title']}")
        print(f"   Source: {row['source']}")
        print(f"   Market: {row['market_question']}")
        print(f"   Sentiment: {row['sentiment_score']:.2f}")
        print(f"   Credibility: {row['source_credibility']:.2f}")

    # Next steps
    print("\n" + "="*70)
    print("⚠️  IMPORTANT: SYNTHETIC LABELS")
    print("="*70)

    print("""
This dataset has REAL:
  ✓ News articles (from NewsAPI)
  ✓ Polymarket markets (from Polymarket API)
  ✓ Article-market matches (keyword-based)
  ✓ Sentiment features (extracted from articles)

But MISSING:
  ✗ Actual price movements after each article
  ✗ Labels (UP/DOWN/NEUTRAL)

To get real labels, you need to:
1. Record market prices when articles are published
2. Wait 1-24 hours
3. Record prices again
4. Calculate price change → Label (UP/DOWN/NEUTRAL)

For now, you can:
1. Use this dataset to understand the system
2. Start collecting prices daily
3. After 7-14 days, you'll have labeled data
4. Train production model!

Or use the synthetic dataset for learning/testing.
""")

    print("="*70)
    print("✅ DATASET CREATED!")
    print("="*70)

    print(f"\n📁 File: {filename}")
    print(f"📊 Samples: {len(df_samples)}")
    print(f"🔗 Real article-market matches!")

if __name__ == '__main__':
    main()
