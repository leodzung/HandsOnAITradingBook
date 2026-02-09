"""
Tests for feature extraction
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from feature_extractor import (
    SentimentAnalyzer,
    MarketFeatureExtractor,
    EventFeatureExtractor,
    FeatureEngineering
)


class TestSentimentAnalyzer:
    """Test suite for SentimentAnalyzer."""

    def test_positive_sentiment(self):
        """Test positive sentiment detection."""
        text = "Great news! Bitcoin surges to new highs with strong growth"

        result = SentimentAnalyzer.analyze_sentiment_simple(text)

        assert result['sentiment_score'] > 0
        assert result['positive_ratio'] > result['negative_ratio']

    def test_negative_sentiment(self):
        """Test negative sentiment detection."""
        text = "Terrible crash as markets fall amid fear and concerns"

        result = SentimentAnalyzer.analyze_sentiment_simple(text)

        assert result['sentiment_score'] < 0
        assert result['negative_ratio'] > result['positive_ratio']

    def test_neutral_sentiment(self):
        """Test neutral sentiment."""
        text = "The meeting discussed various topics"

        result = SentimentAnalyzer.analyze_sentiment_simple(text)

        assert abs(result['sentiment_score']) < 0.2

    def test_sentiment_magnitude(self):
        """Test sentiment magnitude calculation."""
        strong_text = "Excellent amazing wonderful fantastic great"
        weak_text = "The price moved slightly today perhaps"

        strong_result = SentimentAnalyzer.analyze_sentiment_simple(strong_text)
        weak_result = SentimentAnalyzer.analyze_sentiment_simple(weak_text)

        assert strong_result['sentiment_magnitude'] > weak_result['sentiment_magnitude']


class TestMarketFeatureExtractor:
    """Test suite for MarketFeatureExtractor."""

    def test_extract_price_features(self, sample_historical_prices):
        """Test price feature extraction."""
        features = MarketFeatureExtractor.extract_price_features(sample_historical_prices)

        assert 'current_price' in features
        assert 'price_mean_1h' in features
        assert 'price_volatility' in features
        assert 'price_trend' in features

        # Values should be reasonable
        assert 0 <= features['current_price'] <= 1

    def test_extract_volume_features(self, sample_historical_prices):
        """Test volume feature extraction."""
        features = MarketFeatureExtractor.extract_volume_features(sample_historical_prices)

        assert 'total_volume' in features
        assert 'avg_volume' in features
        assert 'volume_std' in features

    def test_extract_orderbook_features(self, sample_orderbook):
        """Test orderbook feature extraction."""
        features = MarketFeatureExtractor.extract_orderbook_features(sample_orderbook)

        assert 'best_bid' in features
        assert 'best_ask' in features
        assert 'spread' in features
        assert 'mid_price' in features

        # Spread should be positive
        assert features['spread'] > 0
        assert features['spread'] == features['best_ask'] - features['best_bid']

    def test_orderbook_depth_features(self, sample_orderbook):
        """Test orderbook depth calculations."""
        features = MarketFeatureExtractor.extract_orderbook_features(sample_orderbook)

        assert 'bid_depth_5' in features
        assert 'ask_depth_5' in features
        assert 'depth_imbalance' in features

        # Imbalance should be between -1 and 1
        assert -1 <= features['depth_imbalance'] <= 1

    def test_empty_data_handling(self):
        """Test handling of empty data."""
        empty_df = pd.DataFrame()

        price_features = MarketFeatureExtractor.extract_price_features(empty_df)
        volume_features = MarketFeatureExtractor.extract_volume_features(empty_df)

        assert price_features == {}
        assert volume_features == {}


class TestEventFeatureExtractor:
    """Test suite for EventFeatureExtractor."""

    def test_extract_event_features(self, sample_event):
        """Test event feature extraction."""
        extractor = EventFeatureExtractor()
        features = extractor.extract_event_features(sample_event)

        assert 'sentiment_score' in features
        assert 'title_length' in features
        assert 'description_length' in features
        assert 'keyword_count' in features
        assert 'source_credibility' in features

        # Check credible source detection
        assert features['source_credibility'] == 1.0  # Reuters is credible

    def test_source_credibility_scoring(self):
        """Test source credibility scoring."""
        from event_detector import Event

        # Credible source
        credible_event = Event(
            title='Test',
            description='Test',
            source='Reuters',
            published_time=datetime.now(),
            url='http://example.com',
            keywords=[]
        )

        # Unknown source
        unknown_event = Event(
            title='Test',
            description='Test',
            source='Unknown Blog',
            published_time=datetime.now(),
            url='http://example.com',
            keywords=[]
        )

        extractor = EventFeatureExtractor()

        credible_features = extractor.extract_event_features(credible_event)
        unknown_features = extractor.extract_event_features(unknown_event)

        assert credible_features['source_credibility'] > unknown_features['source_credibility']

    def test_time_features(self, sample_event):
        """Test time-based features."""
        extractor = EventFeatureExtractor()
        features = extractor.extract_event_features(sample_event)

        assert 'minutes_since_published' in features
        assert 'hours_since_published' in features
        assert features['minutes_since_published'] >= 0


class TestFeatureEngineering:
    """Test suite for complete feature engineering pipeline."""

    def test_create_training_sample(self, sample_event, sample_market,
                                   sample_historical_prices, sample_orderbook):
        """Test creating complete feature vector."""
        fe = FeatureEngineering()

        features = fe.create_training_sample(
            event=sample_event,
            market=sample_market,
            historical_prices=sample_historical_prices,
            orderbook=sample_orderbook,
            use_transformers=False
        )

        # Check that features from all sources are present
        assert 'event_sentiment_score' in features or 'sentiment_score' in features
        assert 'market_volume' in features or 'total_volume' in features
        assert len(features) > 10  # Should have many features

    def test_feature_names_consistency(self, sample_event, sample_market,
                                      sample_historical_prices, sample_orderbook):
        """Test that feature names are consistent across calls."""
        fe = FeatureEngineering()

        features1 = fe.create_training_sample(
            sample_event, sample_market, sample_historical_prices,
            sample_orderbook, use_transformers=False
        )

        features2 = fe.create_training_sample(
            sample_event, sample_market, sample_historical_prices,
            sample_orderbook, use_transformers=False
        )

        assert set(features1.keys()) == set(features2.keys())

    def test_feature_types(self, sample_event, sample_market,
                          sample_historical_prices, sample_orderbook):
        """Test that all features are numeric."""
        fe = FeatureEngineering()

        features = fe.create_training_sample(
            sample_event, sample_market, sample_historical_prices,
            sample_orderbook, use_transformers=False
        )

        for key, value in features.items():
            assert isinstance(value, (int, float, np.integer, np.floating)), \
                f"Feature {key} has non-numeric value: {value}"

    def test_no_nan_values(self, sample_event, sample_market,
                          sample_historical_prices, sample_orderbook):
        """Test that features don't contain NaN values."""
        fe = FeatureEngineering()

        features = fe.create_training_sample(
            sample_event, sample_market, sample_historical_prices,
            sample_orderbook, use_transformers=False
        )

        for key, value in features.items():
            assert not np.isnan(value), f"Feature {key} is NaN"

    def test_feature_ranges(self, sample_event, sample_market,
                           sample_historical_prices, sample_orderbook):
        """Test that features are in reasonable ranges."""
        fe = FeatureEngineering()

        features = fe.create_training_sample(
            sample_event, sample_market, sample_historical_prices,
            sample_orderbook, use_transformers=False
        )

        # Sentiment should be -1 to 1
        if 'event_sentiment_score' in features:
            assert -1 <= features['event_sentiment_score'] <= 1

        # Binary features should be 0 or 1
        if 'has_url' in features:
            assert features['has_url'] in [0, 1]
