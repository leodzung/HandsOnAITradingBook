#!/usr/bin/env python3
"""
Enhanced Feature Generator
Generates rich feature sets for training including:
- Market category features
- Time-based features
- Price momentum indicators
- News sentiment features from GDELT
"""

import sqlite3
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketCategoryClassifier:
    """Classify markets into categories based on question text."""

    CATEGORIES = {
        'crypto': [
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'blockchain',
            'solana', 'sol', 'dogecoin', 'doge', 'ripple', 'xrp', 'cardano',
            'polygon', 'matic', 'defi', 'nft', 'binance', 'coinbase', 'token'
        ],
        'politics': [
            'election', 'president', 'congress', 'senate', 'vote', 'poll',
            'democrat', 'republican', 'biden', 'trump', 'governor', 'mayor',
            'legislation', 'bill', 'law', 'political', 'cabinet', 'impeach'
        ],
        'sports': [
            'nfl', 'nba', 'mlb', 'nhl', 'soccer', 'football', 'basketball',
            'baseball', 'hockey', 'tennis', 'golf', 'championship', 'playoff',
            'super bowl', 'world series', 'finals', 'match', 'game', 'team'
        ],
        'economy': [
            'fed', 'interest rate', 'inflation', 'gdp', 'unemployment',
            'recession', 'stock', 'market', 'economy', 'economic', 'treasury',
            'fomc', 'jobs report', 'cpi', 'ppi', 'fed rate'
        ],
        'entertainment': [
            'oscar', 'grammy', 'emmy', 'movie', 'film', 'album', 'song',
            'tv show', 'streaming', 'netflix', 'celebrity', 'award', 'box office'
        ],
        'technology': [
            'apple', 'google', 'microsoft', 'amazon', 'meta', 'facebook',
            'ai', 'artificial intelligence', 'chatgpt', 'openai', 'tech',
            'software', 'startup', 'ipo', 'earnings'
        ],
        'weather': [
            'hurricane', 'tornado', 'earthquake', 'flood', 'weather',
            'temperature', 'storm', 'climate', 'wildfire', 'drought'
        ],
        'science': [
            'nasa', 'space', 'rocket', 'launch', 'satellite', 'mars', 'moon',
            'fda', 'vaccine', 'drug', 'clinical trial', 'scientific'
        ]
    }

    @classmethod
    def classify(cls, question: str) -> str:
        """Classify a market question into a category."""
        q_lower = question.lower()

        category_scores = {}
        for category, keywords in cls.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw in q_lower)
            if score > 0:
                category_scores[category] = score

        if category_scores:
            return max(category_scores, key=category_scores.get)
        return 'other'

    @classmethod
    def get_category_features(cls, question: str) -> Dict[str, int]:
        """Get one-hot encoded category features."""
        category = cls.classify(question)

        features = {}
        for cat in list(cls.CATEGORIES.keys()) + ['other']:
            features[f'category_{cat}'] = 1 if cat == category else 0

        return features


class TimeFeatureExtractor:
    """Extract time-based features."""

    @staticmethod
    def extract_features(timestamp: datetime) -> Dict[str, float]:
        """
        Extract time-based features from a timestamp.

        Args:
            timestamp: datetime object

        Returns:
            Dictionary of time features
        """
        # Ensure timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        features = {
            # Cyclical encoding for hour (sine/cosine for periodicity)
            'hour_sin': np.sin(2 * np.pi * timestamp.hour / 24),
            'hour_cos': np.cos(2 * np.pi * timestamp.hour / 24),

            # Cyclical encoding for day of week
            'dow_sin': np.sin(2 * np.pi * timestamp.weekday() / 7),
            'dow_cos': np.cos(2 * np.pi * timestamp.weekday() / 7),

            # Cyclical encoding for month
            'month_sin': np.sin(2 * np.pi * timestamp.month / 12),
            'month_cos': np.cos(2 * np.pi * timestamp.month / 12),

            # Binary features
            'is_weekend': 1 if timestamp.weekday() >= 5 else 0,
            'is_us_market_hours': 1 if 14 <= timestamp.hour <= 21 else 0,  # 9am-4pm EST in UTC
            'is_asian_market_hours': 1 if 0 <= timestamp.hour <= 8 else 0,

            # Time buckets
            'hour_bucket_night': 1 if timestamp.hour < 6 else 0,       # 0-5
            'hour_bucket_morning': 1 if 6 <= timestamp.hour < 12 else 0,  # 6-11
            'hour_bucket_afternoon': 1 if 12 <= timestamp.hour < 18 else 0,  # 12-17
            'hour_bucket_evening': 1 if timestamp.hour >= 18 else 0,   # 18-23

            # Day buckets
            'is_monday': 1 if timestamp.weekday() == 0 else 0,
            'is_friday': 1 if timestamp.weekday() == 4 else 0,
        }

        return features

    @staticmethod
    def extract_expiry_features(created_at: datetime, end_date: datetime,
                                current_time: datetime = None) -> Dict[str, float]:
        """
        Extract features related to market expiry.

        Args:
            created_at: Market creation time
            end_date: Market end date
            current_time: Current time (defaults to now)

        Returns:
            Dictionary of expiry-related features
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure timezone-aware
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        total_duration = (end_date - created_at).total_seconds() / 3600  # hours
        time_elapsed = (current_time - created_at).total_seconds() / 3600
        time_remaining = (end_date - current_time).total_seconds() / 3600

        # Avoid division by zero
        total_duration = max(total_duration, 1)

        features = {
            'duration_hours': total_duration,
            'duration_days': total_duration / 24,
            'time_elapsed_hours': max(time_elapsed, 0),
            'time_remaining_hours': max(time_remaining, 0),
            'time_elapsed_pct': min(time_elapsed / total_duration, 1.0),
            'time_remaining_pct': max(1 - time_elapsed / total_duration, 0),

            # Expiry buckets
            'expiry_bucket_1d': 1 if time_remaining <= 24 else 0,
            'expiry_bucket_1w': 1 if 24 < time_remaining <= 168 else 0,
            'expiry_bucket_1m': 1 if 168 < time_remaining <= 720 else 0,
            'expiry_bucket_3m': 1 if 720 < time_remaining <= 2160 else 0,
            'expiry_bucket_long': 1 if time_remaining > 2160 else 0,

            # Duration category
            'is_short_term': 1 if total_duration <= 72 else 0,  # < 3 days
            'is_medium_term': 1 if 72 < total_duration <= 720 else 0,  # 3-30 days
            'is_long_term': 1 if total_duration > 720 else 0,  # > 30 days
        }

        return features


class PriceMomentumCalculator:
    """Calculate price momentum indicators from on-chain trade data."""

    def __init__(self, db_path: str = 'data/training_history.db'):
        self.db_path = db_path

    def get_trades_for_market(self, condition_id: str,
                               start_time: datetime = None,
                               end_time: datetime = None,
                               limit: int = 1000) -> pd.DataFrame:
        """Fetch trades for a market from the database."""
        conn = sqlite3.connect(self.db_path)

        query = """
            SELECT block_timestamp, price, maker_amount_filled as volume
            FROM on_chain_trades
            WHERE condition_id = ?
        """
        params = [condition_id]

        if start_time:
            query += " AND block_timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND block_timestamp <= ?"
            params.append(end_time.isoformat())

        query += " ORDER BY block_timestamp DESC"
        if limit:
            query += f" LIMIT {limit}"

        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if not df.empty:
            df['block_timestamp'] = pd.to_datetime(df['block_timestamp'])
            df = df.sort_values('block_timestamp')

        return df

    def calculate_momentum_features(self, trades_df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate momentum indicators from trade data.

        Args:
            trades_df: DataFrame with columns ['block_timestamp', 'price', 'volume']

        Returns:
            Dictionary of momentum features
        """
        if trades_df.empty or len(trades_df) < 2:
            return self._empty_momentum_features()

        prices = trades_df['price'].values
        volumes = trades_df['volume'].values

        features = {}

        # Current price
        features['current_price'] = prices[-1]

        # Price changes
        features['price_change_1'] = prices[-1] - prices[-2] if len(prices) >= 2 else 0
        features['price_change_5'] = prices[-1] - prices[-5] if len(prices) >= 5 else 0
        features['price_change_10'] = prices[-1] - prices[-10] if len(prices) >= 10 else 0
        features['price_change_20'] = prices[-1] - prices[-20] if len(prices) >= 20 else 0

        # Percentage changes
        if len(prices) >= 2 and prices[-2] > 0:
            features['price_pct_change_1'] = (prices[-1] - prices[-2]) / prices[-2]
        else:
            features['price_pct_change_1'] = 0

        # Moving averages
        features['sma_5'] = np.mean(prices[-5:]) if len(prices) >= 5 else prices[-1]
        features['sma_10'] = np.mean(prices[-10:]) if len(prices) >= 10 else prices[-1]
        features['sma_20'] = np.mean(prices[-20:]) if len(prices) >= 20 else prices[-1]

        # Moving average crossover signals
        features['price_above_sma5'] = 1 if prices[-1] > features['sma_5'] else 0
        features['price_above_sma10'] = 1 if prices[-1] > features['sma_10'] else 0
        features['sma5_above_sma10'] = 1 if features['sma_5'] > features['sma_10'] else 0

        # Exponential moving averages
        if len(prices) >= 10:
            ema_5 = pd.Series(prices).ewm(span=5, adjust=False).mean().iloc[-1]
            ema_10 = pd.Series(prices).ewm(span=10, adjust=False).mean().iloc[-1]
            features['ema_5'] = ema_5
            features['ema_10'] = ema_10
            features['ema_crossover'] = 1 if ema_5 > ema_10 else 0
        else:
            features['ema_5'] = prices[-1]
            features['ema_10'] = prices[-1]
            features['ema_crossover'] = 0

        # Volatility measures
        if len(prices) >= 5:
            features['volatility_5'] = np.std(prices[-5:])
            features['volatility_10'] = np.std(prices[-10:]) if len(prices) >= 10 else np.std(prices[-5:])
            features['volatility_20'] = np.std(prices[-20:]) if len(prices) >= 20 else np.std(prices)
        else:
            features['volatility_5'] = 0
            features['volatility_10'] = 0
            features['volatility_20'] = 0

        # Rate of change (ROC)
        if len(prices) >= 5 and prices[-5] > 0:
            features['roc_5'] = (prices[-1] - prices[-5]) / prices[-5] * 100
        else:
            features['roc_5'] = 0

        if len(prices) >= 10 and prices[-10] > 0:
            features['roc_10'] = (prices[-1] - prices[-10]) / prices[-10] * 100
        else:
            features['roc_10'] = 0

        # RSI (Relative Strength Index)
        if len(prices) >= 14:
            features['rsi_14'] = self._calculate_rsi(prices, 14)
        else:
            features['rsi_14'] = 50  # Neutral

        # Bollinger Band position
        if len(prices) >= 20:
            sma_20 = np.mean(prices[-20:])
            std_20 = np.std(prices[-20:])
            upper_band = sma_20 + 2 * std_20
            lower_band = sma_20 - 2 * std_20

            # Where is price relative to bands? (-1 to 1 scale)
            if upper_band != lower_band:
                features['bb_position'] = (prices[-1] - sma_20) / (upper_band - sma_20) if std_20 > 0 else 0
            else:
                features['bb_position'] = 0
            features['price_above_upper_bb'] = 1 if prices[-1] > upper_band else 0
            features['price_below_lower_bb'] = 1 if prices[-1] < lower_band else 0
        else:
            features['bb_position'] = 0
            features['price_above_upper_bb'] = 0
            features['price_below_lower_bb'] = 0

        # Volume-weighted features
        if len(volumes) > 0 and np.sum(volumes) > 0:
            features['vwap'] = np.sum(prices * volumes) / np.sum(volumes)
            features['volume_total'] = np.sum(volumes)
            features['volume_avg'] = np.mean(volumes)
            features['volume_std'] = np.std(volumes)

            # Recent volume vs historical
            if len(volumes) >= 10:
                recent_vol = np.sum(volumes[-5:])
                hist_vol = np.sum(volumes[-10:-5])
                features['volume_ratio'] = recent_vol / hist_vol if hist_vol > 0 else 1
            else:
                features['volume_ratio'] = 1
        else:
            features['vwap'] = prices[-1] if len(prices) > 0 else 0
            features['volume_total'] = 0
            features['volume_avg'] = 0
            features['volume_std'] = 0
            features['volume_ratio'] = 1

        # Trend strength
        if len(prices) >= 10:
            # Linear regression slope as trend indicator
            x = np.arange(len(prices[-10:]))
            slope, _ = np.polyfit(x, prices[-10:], 1)
            features['trend_slope'] = slope
            features['trend_direction'] = 1 if slope > 0 else (-1 if slope < 0 else 0)
        else:
            features['trend_slope'] = 0
            features['trend_direction'] = 0

        # Price extremes
        features['price_min_10'] = np.min(prices[-10:]) if len(prices) >= 10 else np.min(prices)
        features['price_max_10'] = np.max(prices[-10:]) if len(prices) >= 10 else np.max(prices)
        features['price_range_10'] = features['price_max_10'] - features['price_min_10']

        # Distance from extremes
        features['dist_from_high'] = features['price_max_10'] - prices[-1]
        features['dist_from_low'] = prices[-1] - features['price_min_10']

        return features

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period + 1:
            return 50

        deltas = np.diff(prices[-(period+1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _empty_momentum_features(self) -> Dict[str, float]:
        """Return empty momentum features when no data available."""
        return {
            'current_price': 0.5,
            'price_change_1': 0, 'price_change_5': 0, 'price_change_10': 0, 'price_change_20': 0,
            'price_pct_change_1': 0,
            'sma_5': 0.5, 'sma_10': 0.5, 'sma_20': 0.5,
            'price_above_sma5': 0, 'price_above_sma10': 0, 'sma5_above_sma10': 0,
            'ema_5': 0.5, 'ema_10': 0.5, 'ema_crossover': 0,
            'volatility_5': 0, 'volatility_10': 0, 'volatility_20': 0,
            'roc_5': 0, 'roc_10': 0,
            'rsi_14': 50,
            'bb_position': 0, 'price_above_upper_bb': 0, 'price_below_lower_bb': 0,
            'vwap': 0.5, 'volume_total': 0, 'volume_avg': 0, 'volume_std': 0, 'volume_ratio': 1,
            'trend_slope': 0, 'trend_direction': 0,
            'price_min_10': 0.5, 'price_max_10': 0.5, 'price_range_10': 0,
            'dist_from_high': 0, 'dist_from_low': 0
        }


class NewsSentimentExtractor:
    """Extract sentiment features from GDELT news data."""

    def __init__(self, db_path: str = 'data/training_history.db'):
        self.db_path = db_path

    def get_sentiment_features(self, keywords: List[str],
                                start_time: datetime,
                                end_time: datetime,
                                lookback_hours: float = 24) -> Dict[str, float]:
        """
        Get sentiment features from news events.

        Args:
            keywords: Keywords to match (e.g., ['bitcoin', 'btc'])
            start_time: Start of time window
            end_time: End of time window
            lookback_hours: Hours to look back for news

        Returns:
            Dictionary of sentiment features
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Build keyword filter
        keyword_filter = ' OR '.join([f"keywords LIKE '%{kw}%'" for kw in keywords])

        query = f"""
            SELECT tone, source, timestamp
            FROM news_events
            WHERE ({keyword_filter})
              AND timestamp >= ?
              AND timestamp <= ?
            ORDER BY timestamp DESC
        """

        try:
            cursor.execute(query, (
                (start_time - timedelta(hours=lookback_hours)).isoformat(),
                end_time.isoformat()
            ))
            rows = cursor.fetchall()
        except:
            rows = []
        finally:
            conn.close()

        if not rows:
            return self._empty_sentiment_features()

        tones = [r[0] for r in rows if r[0] is not None]

        features = {
            'news_count': len(rows),
            'news_count_log': np.log1p(len(rows)),
            'sentiment_mean': np.mean(tones) if tones else 0,
            'sentiment_std': np.std(tones) if len(tones) > 1 else 0,
            'sentiment_min': np.min(tones) if tones else 0,
            'sentiment_max': np.max(tones) if tones else 0,
            'sentiment_positive_count': sum(1 for t in tones if t > 1),
            'sentiment_negative_count': sum(1 for t in tones if t < -1),
            'sentiment_neutral_count': sum(1 for t in tones if -1 <= t <= 1),
        }

        # Sentiment ratios
        total = len(tones) if tones else 1
        features['positive_ratio'] = features['sentiment_positive_count'] / total
        features['negative_ratio'] = features['sentiment_negative_count'] / total

        # Recent vs older sentiment
        recent_tones = [r[0] for r in rows[:len(rows)//2] if r[0] is not None]
        older_tones = [r[0] for r in rows[len(rows)//2:] if r[0] is not None]

        features['sentiment_recent'] = np.mean(recent_tones) if recent_tones else 0
        features['sentiment_older'] = np.mean(older_tones) if older_tones else 0
        features['sentiment_trend'] = features['sentiment_recent'] - features['sentiment_older']

        return features

    def _empty_sentiment_features(self) -> Dict[str, float]:
        """Return empty sentiment features when no news available."""
        return {
            'news_count': 0,
            'news_count_log': 0,
            'sentiment_mean': 0,
            'sentiment_std': 0,
            'sentiment_min': 0,
            'sentiment_max': 0,
            'sentiment_positive_count': 0,
            'sentiment_negative_count': 0,
            'sentiment_neutral_count': 0,
            'positive_ratio': 0,
            'negative_ratio': 0,
            'sentiment_recent': 0,
            'sentiment_older': 0,
            'sentiment_trend': 0
        }


class EnhancedTrainingDataGenerator:
    """Generate enhanced training data with all feature types."""

    def __init__(self, db_path: str = 'data/training_history.db'):
        self.db_path = db_path
        self.momentum_calc = PriceMomentumCalculator(db_path)
        self.sentiment_extractor = NewsSentimentExtractor(db_path)

    def generate_price_level_features(self, output_path: str = 'data/training_price_level_enhanced.csv'):
        """Generate enhanced features for price-level model."""
        conn = sqlite3.connect(self.db_path)

        # Get markets with trades
        query = """
            SELECT DISTINCT m.condition_id, m.question, m.volume, m.end_date,
                   m.created_at, m.resolved, m.outcome_prices
            FROM token_condition_map tcm
            JOIN (
                SELECT DISTINCT condition_id
                FROM on_chain_trades
                WHERE condition_id IS NOT NULL
            ) t ON tcm.condition_id = t.condition_id
            LEFT JOIN markets m ON tcm.condition_id = m.condition_id
            WHERE m.question IS NOT NULL
        """

        df_markets = pd.read_sql_query(query, conn)
        conn.close()

        logger.info(f"Processing {len(df_markets)} markets for enhanced features...")

        samples = []
        for idx, row in df_markets.iterrows():
            try:
                sample = self._generate_single_sample(row)
                if sample:
                    samples.append(sample)
            except Exception as e:
                logger.debug(f"Error processing market {row['condition_id']}: {e}")

            if (idx + 1) % 100 == 0:
                logger.info(f"  Processed {idx + 1}/{len(df_markets)} markets, {len(samples)} samples")

        if samples:
            df_out = pd.DataFrame(samples)
            df_out.to_csv(output_path, index=False)
            logger.info(f"Saved {len(samples)} enhanced samples to {output_path}")

            # Show feature summary
            print(f"\n=== Enhanced Training Data Summary ===")
            print(f"Total samples: {len(df_out)}")
            print(f"Total features: {len(df_out.columns)}")
            print(f"\nLabel distribution:")
            if 'label' in df_out.columns:
                print(df_out['label'].value_counts())

        return samples

    def _generate_single_sample(self, market_row) -> Optional[Dict]:
        """Generate enhanced features for a single market."""
        condition_id = market_row['condition_id']
        question = market_row.get('question', '')

        if not question:
            return None

        # Parse market question for price-level info
        parsed = self._parse_price_level_question(question)
        if not parsed:
            return None

        features = {
            'condition_id': condition_id,
            'question': question
        }

        # Market category features
        category_features = MarketCategoryClassifier.get_category_features(question)
        features.update(category_features)

        # Parse dates
        try:
            created_at = pd.to_datetime(market_row.get('created_at'))
            end_date = pd.to_datetime(market_row.get('end_date'))
            if pd.isna(created_at) or pd.isna(end_date):
                return None

            # Ensure timezone-aware
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
        except:
            return None

        # Time features (at market creation)
        time_features = TimeFeatureExtractor.extract_features(created_at)
        features.update({f'created_{k}': v for k, v in time_features.items()})

        # Expiry features
        expiry_features = TimeFeatureExtractor.extract_expiry_features(
            created_at, end_date, created_at
        )
        features.update(expiry_features)

        # Get trades and calculate momentum
        trades_df = self.momentum_calc.get_trades_for_market(
            condition_id,
            start_time=created_at,
            end_time=min(end_date, datetime.now(timezone.utc)),
            limit=500
        )

        momentum_features = self.momentum_calc.calculate_momentum_features(trades_df)
        features.update(momentum_features)

        # News sentiment features
        keywords = self._get_keywords_for_asset(parsed['asset'])
        sentiment_features = self.sentiment_extractor.get_sentiment_features(
            keywords, created_at, end_date, lookback_hours=48
        )
        features.update({f'news_{k}': v for k, v in sentiment_features.items()})

        # Market metadata
        features['volume'] = float(market_row.get('volume') or 0)
        features['volume_log'] = np.log1p(features['volume'])

        # Price-level specific features
        features['asset'] = parsed['asset']
        features['strike'] = parsed['strike']
        features['direction'] = parsed['direction']
        features['direction_above'] = 1 if parsed['direction'] == 'ABOVE' else 0

        # Asset one-hot encoding
        for asset in ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP']:
            features[f'asset_{asset}'] = 1 if parsed['asset'] == asset else 0

        # Label (from outcome_prices - if first outcome is close to 1, it resolved YES)
        outcome_prices = market_row.get('outcome_prices', '')
        resolved = market_row.get('resolved', 0)

        if outcome_prices and resolved:
            try:
                # outcome_prices format: "0.99,0.01" means first outcome won
                prices = [float(p) for p in str(outcome_prices).split(',')]
                features['label'] = 'YES' if prices[0] > 0.5 else 'NO'
            except:
                features['label'] = 'NO'
        else:
            features['label'] = 'NO'

        return features

    def _parse_price_level_question(self, question: str) -> Optional[Dict]:
        """Parse price level market question."""
        q = question.lower()

        # Detect asset
        asset = None
        for a, patterns in [
            ('BTC', [r'\bbtc\b', r'bitcoin']),
            ('ETH', [r'\beth\b', r'ethereum']),
            ('SOL', [r'\bsol\b', r'solana']),
            ('DOGE', [r'\bdoge\b', r'dogecoin']),
            ('XRP', [r'\bxrp\b', r'ripple'])
        ]:
            if any(re.search(p, q) for p in patterns):
                asset = a
                break

        if not asset:
            return None

        # Extract strike price
        strike = None
        patterns = [
            r'\$([0-9,]+(?:\.[0-9]+)?)\s*k',
            r'\$([0-9,]+(?:\.[0-9]+)?)',
            r'([0-9,]+(?:\.[0-9]+)?)\s*(?:dollars|usd)'
        ]

        for pattern in patterns:
            match = re.search(pattern, q)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    strike = float(price_str)
                    if 'k' in q[match.end():match.end()+2].lower():
                        strike *= 1000
                    break
                except:
                    pass

        if not strike:
            return None

        # Determine direction
        direction = 'ABOVE'
        if any(w in q for w in ['below', 'under', 'drop', 'fall', 'dip']):
            direction = 'BELOW'

        return {'asset': asset, 'strike': strike, 'direction': direction}

    def _get_keywords_for_asset(self, asset: str) -> List[str]:
        """Get news keywords for an asset."""
        keyword_map = {
            'BTC': ['bitcoin', 'btc'],
            'ETH': ['ethereum', 'eth'],
            'SOL': ['solana', 'sol'],
            'DOGE': ['dogecoin', 'doge'],
            'XRP': ['ripple', 'xrp']
        }
        return keyword_map.get(asset, ['crypto'])

    def generate_event_bot_features(self, output_path: str = 'data/training_event_bot_enhanced.csv'):
        """Generate enhanced features for event-driven bot."""
        conn = sqlite3.connect(self.db_path)

        # Get markets with sufficient trade data
        query = """
            SELECT t.condition_id,
                   m.question,
                   m.volume,
                   m.end_date,
                   m.created_at,
                   m.outcome_prices,
                   m.resolved,
                   COUNT(*) as trade_count
            FROM on_chain_trades t
            LEFT JOIN markets m ON t.condition_id = m.condition_id
            WHERE t.condition_id IS NOT NULL
            GROUP BY t.condition_id
            HAVING trade_count >= 10
        """

        df_markets = pd.read_sql_query(query, conn)
        conn.close()

        logger.info(f"Processing {len(df_markets)} markets for event-bot features...")

        samples = []
        for idx, row in df_markets.iterrows():
            try:
                sample = self._generate_event_sample(row)
                if sample:
                    samples.append(sample)
            except Exception as e:
                logger.debug(f"Error processing market {row['condition_id']}: {e}")

            if (idx + 1) % 100 == 0:
                logger.info(f"  Processed {idx + 1}/{len(df_markets)} markets, {len(samples)} samples")

        if samples:
            df_out = pd.DataFrame(samples)
            df_out.to_csv(output_path, index=False)
            logger.info(f"Saved {len(samples)} enhanced event-bot samples to {output_path}")

            print(f"\n=== Event-Bot Training Data Summary ===")
            print(f"Total samples: {len(df_out)}")
            print(f"Total features: {len(df_out.columns)}")
            if 'label' in df_out.columns:
                print(f"\nLabel distribution:")
                print(df_out['label'].value_counts())

        return samples

    def _generate_event_sample(self, market_row) -> Optional[Dict]:
        """Generate event-bot sample with enhanced features."""
        condition_id = market_row['condition_id']
        question = market_row.get('question', '')

        features = {
            'condition_id': condition_id,
            'question': question
        }

        # Market category
        if question:
            category_features = MarketCategoryClassifier.get_category_features(question)
            features.update(category_features)

        # Get trade data
        trades_df = self.momentum_calc.get_trades_for_market(condition_id, limit=500)

        if trades_df.empty or len(trades_df) < 10:
            return None

        # Time features from first trade
        first_trade_time = trades_df['block_timestamp'].iloc[0]
        time_features = TimeFeatureExtractor.extract_features(first_trade_time)
        features.update(time_features)

        # Momentum features
        momentum_features = self.momentum_calc.calculate_momentum_features(trades_df)
        features.update(momentum_features)

        # News sentiment
        # Determine keywords from question
        keywords = ['crypto']
        if question:
            q_lower = question.lower()
            for kw in ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto']:
                if kw in q_lower:
                    keywords.append(kw)

        last_trade_time = trades_df['block_timestamp'].iloc[-1]
        sentiment_features = self.sentiment_extractor.get_sentiment_features(
            keywords, first_trade_time, last_trade_time, lookback_hours=24
        )
        features.update({f'news_{k}': v for k, v in sentiment_features.items()})

        # Volume
        features['market_volume'] = float(market_row.get('volume') or 0)
        features['market_volume_log'] = np.log1p(features['market_volume'])

        # Calculate label based on price movement
        price_start = trades_df['price'].iloc[0]
        price_end = trades_df['price'].iloc[-1]
        price_change = (price_end - price_start) / price_start if price_start > 0 else 0

        features['price_start'] = price_start
        features['price_end'] = price_end
        features['price_change_pct'] = price_change

        # Label: UP if price increased > 3%, DOWN if decreased > 3%, else NEUTRAL
        if price_change >= 0.03:
            features['label'] = 'UP'
        elif price_change <= -0.03:
            features['label'] = 'DOWN'
        else:
            features['label'] = 'NEUTRAL'

        # Outcome label from market resolution
        outcome_prices = market_row.get('outcome_prices', '')
        resolved = market_row.get('resolved', 0)

        if outcome_prices and resolved:
            try:
                prices = [float(p) for p in str(outcome_prices).split(',')]
                features['outcome'] = 'YES' if prices[0] > 0.5 else 'NO'
            except:
                features['outcome'] = 'UNKNOWN'
        else:
            features['outcome'] = 'UNKNOWN'

        return features


def main():
    """Main routine for enhanced feature generation."""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Feature Generator")
    parser.add_argument("--price-level", action="store_true",
                        help="Generate enhanced price-level training data")
    parser.add_argument("--event-bot", action="store_true",
                        help="Generate enhanced event-bot training data")
    parser.add_argument("--all", action="store_true",
                        help="Generate all enhanced training data")
    parser.add_argument("--output-dir", default="data",
                        help="Output directory for training files")
    args = parser.parse_args()

    generator = EnhancedTrainingDataGenerator()

    if args.all or args.price_level:
        generator.generate_price_level_features(
            f"{args.output_dir}/training_price_level_enhanced.csv"
        )

    if args.all or args.event_bot:
        generator.generate_event_bot_features(
            f"{args.output_dir}/training_event_bot_enhanced.csv"
        )

    if not (args.all or args.price_level or args.event_bot):
        parser.print_help()


if __name__ == "__main__":
    main()
