"""
Feature Extraction Pipeline
Extracts features from events and market data for ML models.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from collections import Counter
import re
import warnings

# Import centralized feature extractors
from features.common_features import OrderbookFeatures, VolumeFeatures


class SentimentAnalyzer:
    """Analyze sentiment of text using various methods."""

    # Cached transformer pipelines (loaded once per process)
    _pipeline_cache: Dict[str, object] = {}

    # Simple sentiment lexicons (can be replaced with transformers)
    POSITIVE_WORDS = {
        'good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic',
        'positive', 'win', 'success', 'growth', 'gain', 'rise', 'surge',
        'bullish', 'optimistic', 'confident', 'strong', 'improve'
    }

    NEGATIVE_WORDS = {
        'bad', 'terrible', 'awful', 'horrible', 'negative', 'lose', 'loss',
        'fail', 'failure', 'decline', 'fall', 'drop', 'crash', 'bearish',
        'pessimistic', 'weak', 'concern', 'worry', 'fear', 'risk'
    }

    @classmethod
    def analyze_sentiment_simple(cls, text: str) -> Dict[str, float]:
        """
        Simple lexicon-based sentiment analysis.

        Args:
            text: Input text

        Returns:
            Dictionary with sentiment scores
        """
        text_lower = text.lower()
        words = set(re.findall(r'\b[a-z]+\b', text_lower))

        positive_count = len(words & cls.POSITIVE_WORDS)
        negative_count = len(words & cls.NEGATIVE_WORDS)
        total = positive_count + negative_count

        if total == 0:
            return {
                'sentiment_score': 0.0,
                'sentiment_magnitude': 0.0,
                'positive_ratio': 0.5,
                'negative_ratio': 0.5
            }

        score = (positive_count - negative_count) / max(total, 1)

        return {
            'sentiment_score': score,  # -1 to 1
            'sentiment_magnitude': total / len(words) if words else 0,
            'positive_ratio': positive_count / max(total, 1),
            'negative_ratio': negative_count / max(total, 1)
        }

    @classmethod
    def analyze_sentiment_transformers(cls, text: str, model_name: str = 'finbert') -> Dict[str, float]:
        """
        Transformer-based sentiment analysis (requires transformers library).

        Args:
            text: Input text
            model_name: Model to use (finbert, distilbert-sentiment, etc.)

        Returns:
            Dictionary with sentiment scores
        """
        try:
            from transformers import pipeline

            if model_name not in cls._pipeline_cache:
                if model_name == 'finbert':
                    # Use FinBERT for financial sentiment; load once and cache
                    cls._pipeline_cache[model_name] = pipeline(
                        "sentiment-analysis",
                        model="ProsusAI/finbert",
                        tokenizer="ProsusAI/finbert"
                    )
                else:
                    cls._pipeline_cache[model_name] = pipeline("sentiment-analysis")

            sentiment_pipeline = cls._pipeline_cache[model_name]
            result = sentiment_pipeline(text[:512])[0]  # Truncate to model limit

            # Map label to score
            label_map = {'positive': 1.0, 'negative': -1.0, 'neutral': 0.0}
            score = label_map.get(result['label'].lower(), 0.0)

            return {
                'sentiment_score': score,
                'sentiment_confidence': result['score'],
                'sentiment_label': result['label']
            }

        except ImportError:
            print("transformers library not installed, falling back to simple sentiment")
            return SentimentAnalyzer.analyze_sentiment_simple(text)
        except Exception as e:
            print(f"Error in transformer sentiment analysis: {e}")
            return SentimentAnalyzer.analyze_sentiment_simple(text)


class MarketFeatureExtractor:
    """Extract features from market data."""

    @staticmethod
    def extract_price_features(prices_df: pd.DataFrame) -> Dict[str, float]:
        """
        Extract price-based features from historical data.

        Args:
            prices_df: DataFrame with columns ['timestamp', 'price', 'size']

        Returns:
            Dictionary of features
        """
        if len(prices_df) == 0:
            return {}

        prices = prices_df['price'].values

        features = {
            'current_price': prices[-1] if len(prices) > 0 else 0.5,
            'price_mean_1h': np.mean(prices[-60:]) if len(prices) >= 60 else np.mean(prices),
            'price_std_1h': np.std(prices[-60:]) if len(prices) >= 60 else np.std(prices),
            'price_change_1h': prices[-1] - prices[-60] if len(prices) >= 60 else 0,
            'price_change_pct_1h': ((prices[-1] - prices[-60]) / max(prices[-60], 0.01) * 100)
                                   if len(prices) >= 60 else 0,
            'price_volatility': np.std(np.diff(prices)) if len(prices) > 1 else 0,
            'price_trend': np.polyfit(range(len(prices)), prices, 1)[0] if len(prices) > 1 else 0
        }

        # Add momentum indicators
        if len(prices) >= 10:
            features['momentum_5'] = prices[-1] - prices[-5]
            features['momentum_10'] = prices[-1] - prices[-10]

        return features

    @staticmethod
    def extract_volume_features(prices_df: pd.DataFrame) -> Dict[str, float]:
        """
        Extract volume-based features.

        Args:
            prices_df: DataFrame with columns ['timestamp', 'price', 'size']

        Returns:
            Dictionary of features
        """
        if len(prices_df) == 0 or 'size' not in prices_df.columns:
            return {}

        volumes = prices_df['size'].values

        features = {
            'total_volume': np.sum(volumes),
            'avg_volume': np.mean(volumes),
            'volume_std': np.std(volumes),
            'volume_trend': np.polyfit(range(len(volumes)), volumes, 1)[0]
                           if len(volumes) > 1 else 0
        }

        # Recent vs historical volume
        if len(volumes) >= 60:
            recent_volume = np.sum(volumes[-10:])
            historical_volume = np.sum(volumes[-60:-10])
            features['volume_ratio'] = recent_volume / max(historical_volume, 1)

        return features

    @staticmethod
    def extract_orderbook_features(orderbook: Dict) -> Dict[str, float]:
        """
        Extract features from order book.

        DEPRECATED: This method now uses the centralized OrderbookFeatures extractor
        from common_features.py. All new code should use OrderbookFeatures directly.

        Args:
            orderbook: Order book dictionary with 'bids' and 'asks'

        Returns:
            Dictionary of features
        """
        # Use centralized implementation
        features = OrderbookFeatures.extract(orderbook, return_best_bid_ask=True)
        if features is None:
            features = {}

        # Calculate bid_ask_imbalance (event trader specific)
        bids = orderbook.get('bids', []) if orderbook else []
        asks = orderbook.get('asks', []) if orderbook else []

        if bids and asks:
            best_bid_size = float(bids[0]['size']) if isinstance(bids[0], dict) else float(bids[0][1])
            best_ask_size = float(asks[0]['size']) if isinstance(asks[0], dict) else float(asks[0][1])
            features['bid_ask_imbalance'] = (best_bid_size - best_ask_size) / (best_bid_size + best_ask_size)
        else:
            features['bid_ask_imbalance'] = 0.0

        return features


class EventFeatureExtractor:
    """Extract features from events."""

    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()

    def extract_event_features(self, event, use_transformers: bool = False) -> Dict[str, float]:
        """
        Extract features from an event.

        Args:
            event: Event object
            use_transformers: Whether to use transformer models

        Returns:
            Dictionary of features
        """
        # Defensive null checks for event attributes
        title = event.title if event.title is not None else ''
        description = event.description if event.description is not None else ''
        keywords = event.keywords if event.keywords is not None else []

        text = f"{title} {description}"

        # Sentiment features
        if use_transformers:
            sentiment_features = self.sentiment_analyzer.analyze_sentiment_transformers(text)
        else:
            sentiment_features = self.sentiment_analyzer.analyze_sentiment_simple(text)

        # Text length features
        text_features = {
            'title_length': len(title),
            'description_length': len(description),
            'keyword_count': len(keywords),
            'has_url': 1 if event.url else 0
        }

        # Source credibility (simple heuristic)
        credible_sources = {
            'Reuters', 'Bloomberg', 'Associated Press', 'Wall Street Journal',
            'New York Times', 'BBC', 'CNN', 'CNBC', 'Financial Times'
        }
        text_features['source_credibility'] = 1.0 if event.source in credible_sources else 0.5

        # Time features
        now = datetime.now(timezone.utc)
        time_diff = (now - event.published_time).total_seconds()
        text_features['minutes_since_published'] = time_diff / 60
        text_features['hours_since_published'] = time_diff / 3600

        # Combine all features
        return {**sentiment_features, **text_features}


class FeatureEngineering:
    """Main feature engineering pipeline."""

    def __init__(self):
        self.market_extractor = MarketFeatureExtractor()
        self.event_extractor = EventFeatureExtractor()

    def create_training_sample(self, event, market: Dict,
                              historical_prices: pd.DataFrame,
                              orderbook: Dict,
                              use_transformers: bool = False) -> Dict[str, float]:
        """
        Create a complete feature vector for training.

        Args:
            event: Event object
            market: Market dictionary
            historical_prices: DataFrame with price history
            orderbook: Order book dictionary
            use_transformers: Whether to use transformer models

        Returns:
            Dictionary of all features
        """
        features = {}

        # Event features
        event_features = self.event_extractor.extract_event_features(
            event, use_transformers=use_transformers
        )
        features.update({f'event_{k}': v for k, v in event_features.items()})

        # Market price features
        price_features = self.market_extractor.extract_price_features(historical_prices)
        features.update({f'market_{k}': v for k, v in price_features.items()})

        # Volume features
        volume_features = self.market_extractor.extract_volume_features(historical_prices)
        features.update({f'market_{k}': v for k, v in volume_features.items()})

        # Order book features
        orderbook_features = self.market_extractor.extract_orderbook_features(orderbook)
        features.update({f'orderbook_{k}': v for k, v in orderbook_features.items()})

        # Market metadata features
        features['market_active'] = 1.0 if market.get('active', False) else 0.0
        features['market_volume'] = float(market.get('volume', 0))

        # Time to expiry
        try:
            end_date = datetime.fromisoformat(market.get('end_date_iso', '2099-01-01'))
            hours_to_expiry = (end_date - datetime.now(timezone.utc)).total_seconds() / 3600
            features['hours_to_expiry'] = hours_to_expiry
        except:
            features['hours_to_expiry'] = 10000

        return features

    def create_label(self, price_before: float, price_after: float,
                    threshold: float = 0.02) -> int:
        """
        Create label for supervised learning.

        Args:
            price_before: Price before event
            price_after: Price after event (e.g., 1 hour later)
            threshold: Minimum price change to consider significant

        Returns:
            Label: 1 (up), 0 (no change), -1 (down)
        """
        change = price_after - price_before

        if change > threshold:
            return 1  # Up
        elif change < -threshold:
            return -1  # Down
        else:
            return 0  # No significant change

    def create_regression_target(self, price_before: float, price_after: float) -> float:
        """
        Create regression target (price change).

        Args:
            price_before: Price before event
            price_after: Price after event

        Returns:
            Price change
        """
        return price_after - price_before

    def normalize_features(self, features: Dict[str, float],
                          feature_stats: Optional[Dict] = None) -> Dict[str, float]:
        """
        Normalize features using z-score or min-max.

        Args:
            features: Feature dictionary
            feature_stats: Pre-computed statistics (mean, std) for each feature

        Returns:
            Normalized features
        """
        if feature_stats is None:
            # Simple normalization for inference
            normalized = {}
            for k, v in features.items():
                if isinstance(v, (int, float)):
                    # Clip extreme values
                    normalized[k] = np.clip(v, -100, 100)
                else:
                    normalized[k] = v
            return normalized

        # Use pre-computed stats
        normalized = {}
        for k, v in features.items():
            if k in feature_stats:
                mean = feature_stats[k]['mean']
                std = feature_stats[k]['std']
                normalized[k] = (v - mean) / max(std, 0.001)
            else:
                normalized[k] = v

        return normalized


def create_feature_dataframe(feature_dicts: List[Dict[str, float]]) -> pd.DataFrame:
    """
    Convert list of feature dictionaries to DataFrame.

    Args:
        feature_dicts: List of feature dictionaries

    Returns:
        DataFrame with features
    """
    df = pd.DataFrame(feature_dicts)

    # Fill missing values
    df = df.fillna(0)

    return df


def compute_feature_importance(model, feature_names: List[str]) -> pd.DataFrame:
    """
    Compute feature importance from trained model.

    Args:
        model: Trained sklearn model
        feature_names: List of feature names

    Returns:
        DataFrame with feature importances
    """
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    elif hasattr(model, 'coef_'):
        importances = np.abs(model.coef_[0])
    else:
        return pd.DataFrame()

    df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    })

    return df.sort_values('importance', ascending=False)
