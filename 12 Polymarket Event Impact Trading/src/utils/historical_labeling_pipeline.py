#!/usr/bin/env python3
"""
Historical Labeling Pipeline

Converts raw on-chain trades from training_history.db into labeled training samples
by matching trades with news events and computing price movement labels.

Data sources:
- training_history.db: on_chain_trades (1.27M), news_events (2.2M), markets (50K)

Output:
- data/labeled_training_data.csv: Features + labels for model training
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = Path("data")
TRAINING_DB = DATA_DIR / "training_history.db"
OUTPUT_FILE = DATA_DIR / "labeled_training_data.csv"

# Configuration
NEWS_WINDOW_HOURS = 24  # Look for news within this window before trade
LABEL_WINDOW_HOURS = 24  # Look at price movement over this period
MIN_PRICE_CHANGE_PCT = 5  # Threshold for UP/DOWN labels (else NEUTRAL)
BATCH_SIZE = 1000  # Process trades in batches

# Crypto keywords for filtering relevant news
CRYPTO_KEYWORDS = {
    'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
    'blockchain', 'defi', 'nft', 'altcoin', 'stablecoin', 'usdc', 'usdt',
    'binance', 'coinbase', 'exchange', 'trading', 'token', 'wallet',
    'mining', 'halving', 'etf', 'sec', 'regulation', 'federal reserve',
    'inflation', 'interest rate', 'fed', 'powell', 'trump', 'gensler'
}


def connect_db() -> sqlite3.Connection:
    """Connect to training history database."""
    conn = sqlite3.connect(TRAINING_DB)
    conn.row_factory = sqlite3.Row
    return conn


def get_trades_with_markets(conn: sqlite3.Connection, limit: int = None) -> pd.DataFrame:
    """Get trades that have linked market information."""
    query = """
    SELECT
        t.id as trade_id,
        t.block_timestamp,
        t.condition_id,
        t.price as trade_price,
        t.maker_amount_filled,
        t.taker_amount_filled,
        m.question,
        m.category,
        m.volume,
        m.liquidity,
        m.end_date
    FROM on_chain_trades t
    JOIN markets m ON t.condition_id = m.condition_id
    WHERE t.condition_id IS NOT NULL
      AND t.condition_id != ''
      AND t.price > 0
      AND t.price < 1
    ORDER BY t.block_timestamp
    """
    if limit:
        query += f" LIMIT {limit}"

    return pd.read_sql_query(query, conn)


def get_news_in_window(conn: sqlite3.Connection,
                        start_time: str,
                        end_time: str) -> pd.DataFrame:
    """Get news events within a time window."""
    query = """
    SELECT
        id,
        source_url,
        source,
        timestamp,
        themes,
        tone
    FROM news_events
    WHERE timestamp BETWEEN ? AND ?
    ORDER BY timestamp
    """
    return pd.read_sql_query(query, conn, params=[start_time, end_time])


def is_crypto_relevant(themes: str) -> bool:
    """Check if news themes are crypto-relevant."""
    if not themes:
        return False
    themes_lower = themes.lower()
    return any(kw in themes_lower for kw in CRYPTO_KEYWORDS)


def extract_news_features(news_df: pd.DataFrame, market_question: str) -> Dict:
    """Extract features from news events for a market."""
    if news_df.empty:
        return {
            'news_count': 0,
            'avg_tone': 0,
            'min_tone': 0,
            'max_tone': 0,
            'tone_std': 0,
            'crypto_news_count': 0,
            'crypto_news_pct': 0
        }

    # Filter for crypto-relevant news
    crypto_mask = news_df['themes'].apply(is_crypto_relevant)
    crypto_news = news_df[crypto_mask]

    # Tone features (GDELT tone is -100 to +100)
    tones = news_df['tone'].dropna()

    return {
        'news_count': len(news_df),
        'avg_tone': tones.mean() if len(tones) > 0 else 0,
        'min_tone': tones.min() if len(tones) > 0 else 0,
        'max_tone': tones.max() if len(tones) > 0 else 0,
        'tone_std': tones.std() if len(tones) > 1 else 0,
        'crypto_news_count': len(crypto_news),
        'crypto_news_pct': len(crypto_news) / len(news_df) if len(news_df) > 0 else 0
    }


def get_future_price(conn: sqlite3.Connection,
                     condition_id: str,
                     after_time: str,
                     window_hours: int = 24) -> Optional[float]:
    """Get average price in the window after the trade."""
    end_time = (datetime.fromisoformat(after_time.replace('+00:00', '')) +
                timedelta(hours=window_hours)).isoformat() + '+00:00'

    query = """
    SELECT AVG(price) as avg_price, COUNT(*) as trade_count
    FROM on_chain_trades
    WHERE condition_id = ?
      AND block_timestamp > ?
      AND block_timestamp <= ?
      AND price > 0
      AND price < 1
    """
    result = conn.execute(query, [condition_id, after_time, end_time]).fetchone()

    if result and result['trade_count'] > 0:
        return result['avg_price']
    return None


def compute_label(entry_price: float, future_price: float) -> int:
    """
    Compute label based on price movement.

    Returns:
        1 = UP (price increased by more than threshold)
        0 = NEUTRAL (price stayed within threshold)
        -1 = DOWN (price decreased by more than threshold)
    """
    if future_price is None:
        return None

    pct_change = ((future_price - entry_price) / entry_price) * 100

    if pct_change >= MIN_PRICE_CHANGE_PCT:
        return 1  # UP
    elif pct_change <= -MIN_PRICE_CHANGE_PCT:
        return -1  # DOWN
    else:
        return 0  # NEUTRAL


def extract_market_features(row: pd.Series) -> Dict:
    """Extract features from market data."""
    # Parse end_date for days to expiry
    days_to_expiry = 0
    if row.get('end_date'):
        try:
            end_date = datetime.fromisoformat(row['end_date'].replace('Z', '+00:00'))
            trade_date = datetime.fromisoformat(row['block_timestamp'].replace('+00:00', ''))
            days_to_expiry = (end_date - trade_date).days
        except:
            pass

    return {
        'trade_price': row['trade_price'],
        'volume': row.get('volume', 0) or 0,
        'liquidity': row.get('liquidity', 0) or 0,
        'days_to_expiry': max(0, days_to_expiry),
        'trade_size': (row.get('maker_amount_filled', 0) or 0) + (row.get('taker_amount_filled', 0) or 0),
        'is_crypto': 1 if any(kw in (row.get('question', '') or '').lower() for kw in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto']) else 0
    }


def process_batch(conn: sqlite3.Connection,
                  trades_df: pd.DataFrame,
                  news_cache: Dict[str, pd.DataFrame]) -> List[Dict]:
    """Process a batch of trades and create labeled samples."""
    samples = []

    for idx, row in trades_df.iterrows():
        try:
            trade_time = row['block_timestamp']
            condition_id = row['condition_id']

            # Calculate news window
            trade_dt = datetime.fromisoformat(trade_time.replace('+00:00', ''))
            news_start = (trade_dt - timedelta(hours=NEWS_WINDOW_HOURS)).isoformat() + '+00:00'
            news_end = trade_time

            # Get news (use cache key based on hour to reduce queries)
            cache_key = news_start[:13]  # YYYY-MM-DDTHH
            if cache_key not in news_cache:
                news_cache[cache_key] = get_news_in_window(conn, news_start, news_end)
            news_df = news_cache[cache_key]

            # Extract features
            market_features = extract_market_features(row)
            news_features = extract_news_features(news_df, row.get('question', ''))

            # Get future price for label
            future_price = get_future_price(conn, condition_id, trade_time, LABEL_WINDOW_HOURS)
            label = compute_label(row['trade_price'], future_price)

            if label is not None:
                sample = {
                    'trade_id': row['trade_id'],
                    'condition_id': condition_id,
                    'timestamp': trade_time,
                    'question': row.get('question', '')[:100],
                    'category': row.get('category', ''),
                    'entry_price': row['trade_price'],
                    'future_price': future_price,
                    'label': label,
                    **market_features,
                    **news_features
                }
                samples.append(sample)

        except Exception as e:
            logger.warning(f"Error processing trade {row.get('trade_id')}: {e}")
            continue

    return samples


def run_pipeline(limit: int = None, save_every: int = 5000):
    """
    Run the full labeling pipeline.

    Args:
        limit: Max trades to process (None for all)
        save_every: Save intermediate results every N samples
    """
    logger.info("=" * 60)
    logger.info("HISTORICAL LABELING PIPELINE")
    logger.info("=" * 60)

    conn = connect_db()

    # Get trades with market info
    logger.info("Loading trades with market information...")
    trades_df = get_trades_with_markets(conn, limit)
    total_trades = len(trades_df)
    logger.info(f"Found {total_trades:,} trades with market links")

    if total_trades == 0:
        logger.error("No trades found with market links!")
        return

    # Process in batches
    all_samples = []
    news_cache = {}

    for batch_start in range(0, total_trades, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_trades)
        batch_df = trades_df.iloc[batch_start:batch_end]

        logger.info(f"Processing batch {batch_start//BATCH_SIZE + 1}: trades {batch_start+1}-{batch_end}")

        samples = process_batch(conn, batch_df, news_cache)
        all_samples.extend(samples)

        # Clear old cache entries to save memory
        if len(news_cache) > 100:
            oldest_keys = list(news_cache.keys())[:50]
            for key in oldest_keys:
                del news_cache[key]

        # Save intermediate results
        if len(all_samples) >= save_every and len(all_samples) % save_every < BATCH_SIZE:
            logger.info(f"  Saving intermediate results ({len(all_samples):,} samples)...")
            pd.DataFrame(all_samples).to_csv(OUTPUT_FILE, index=False)

    conn.close()

    # Final save
    if all_samples:
        df = pd.DataFrame(all_samples)
        df.to_csv(OUTPUT_FILE, index=False)

        # Summary statistics
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Total samples: {len(df):,}")
        logger.info(f"Label distribution:")
        label_counts = df['label'].value_counts()
        for label, count in label_counts.items():
            label_name = {1: 'UP', 0: 'NEUTRAL', -1: 'DOWN'}.get(label, 'UNKNOWN')
            logger.info(f"  {label_name}: {count:,} ({count/len(df)*100:.1f}%)")
        logger.info(f"Output saved to: {OUTPUT_FILE}")

        # Feature summary
        logger.info(f"\nFeature columns: {list(df.columns)}")
        logger.info(f"Crypto markets: {df['is_crypto'].sum():,} ({df['is_crypto'].mean()*100:.1f}%)")
        logger.info(f"Avg news count: {df['news_count'].mean():.1f}")
        logger.info(f"Avg crypto news: {df['crypto_news_count'].mean():.1f}")
    else:
        logger.warning("No samples generated!")


def quick_test(n_trades: int = 100):
    """Quick test with a small sample."""
    logger.info(f"Running quick test with {n_trades} trades...")
    run_pipeline(limit=n_trades, save_every=n_trades + 1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Historical labeling pipeline")
    parser.add_argument("--limit", type=int, help="Limit number of trades to process")
    parser.add_argument("--test", action="store_true", help="Run quick test with 100 trades")
    args = parser.parse_args()

    if args.test:
        quick_test()
    elif args.limit:
        run_pipeline(limit=args.limit)
    else:
        run_pipeline()
