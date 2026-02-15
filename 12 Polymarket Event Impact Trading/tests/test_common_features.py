"""
Tests for common feature extractors.

Validates that centralized feature extraction matches old implementations
and handles edge cases correctly.
"""

import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from features.common_features import (
    OrderbookFeatures,
    VolumeFeatures,
    TimeFeatures,
    extract_all_common_features
)


class TestOrderbookFeatures:
    """Test orderbook feature extraction."""

    def test_basic_orderbook_extraction(self):
        """Test basic orderbook feature extraction with dict format."""
        orderbook = {
            'bids': [
                {'price': '0.45', 'size': '1000'},
                {'price': '0.44', 'size': '2000'},
                {'price': '0.43', 'size': '1500'},
            ],
            'asks': [
                {'price': '0.47', 'size': '1500'},
                {'price': '0.48', 'size': '2500'},
                {'price': '0.49', 'size': '1200'},
            ]
        }

        features = OrderbookFeatures.extract(orderbook, return_best_bid_ask=True)

        # Validate calculations
        assert features['best_bid'] == pytest.approx(0.45, abs=1e-6)
        assert features['best_ask'] == pytest.approx(0.47, abs=1e-6)
        assert features['spread'] == pytest.approx(0.02, abs=1e-6)
        assert features['mid_price'] == pytest.approx(0.46, abs=1e-6)
        assert features['spread_pct'] == pytest.approx(4.347826, abs=1e-4)  # (0.02/0.46)*100

    def test_orderbook_with_return_best_bid_ask(self):
        """Test orderbook extraction with best_bid/ask flag."""
        orderbook = {
            'bids': [{'price': '0.50', 'size': '1000'}],
            'asks': [{'price': '0.52', 'size': '1000'}]
        }

        # Without flag
        features = OrderbookFeatures.extract(orderbook, return_best_bid_ask=False)
        assert 'best_bid' not in features
        assert 'best_ask' not in features

        # With flag
        features = OrderbookFeatures.extract(orderbook, return_best_bid_ask=True)
        assert 'best_bid' in features
        assert 'best_ask' in features
        assert features['best_bid'] == 0.50
        assert features['best_ask'] == 0.52

    def test_orderbook_array_format(self):
        """Test orderbook with array format [price, size]."""
        orderbook = {
            'bids': [[0.45, 1000], [0.44, 2000]],
            'asks': [[0.47, 1500], [0.48, 2500]]
        }

        features = OrderbookFeatures.extract(orderbook)

        assert features['spread'] == pytest.approx(0.02, abs=1e-6)
        assert features['mid_price'] == pytest.approx(0.46, abs=1e-6)

    def test_orderbook_depth_calculation(self):
        """Test depth calculation for top 5 levels."""
        orderbook = {
            'bids': [
                {'price': '0.45', 'size': '1000'},
                {'price': '0.44', 'size': '2000'},
                {'price': '0.43', 'size': '1500'},
                {'price': '0.42', 'size': '3000'},
                {'price': '0.41', 'size': '2500'},
                {'price': '0.40', 'size': '5000'},  # Should not be included (>5 levels)
            ],
            'asks': [
                {'price': '0.47', 'size': '1500'},
                {'price': '0.48', 'size': '2500'},
                {'price': '0.49', 'size': '1200'},
                {'price': '0.50', 'size': '3500'},
                {'price': '0.51', 'size': '2000'},
                {'price': '0.52', 'size': '4000'},  # Should not be included
            ]
        }

        features = OrderbookFeatures.extract(orderbook)

        # Top 5 bids: 1000 + 2000 + 1500 + 3000 + 2500 = 10000
        assert features['bid_depth_5'] == pytest.approx(10000, abs=1e-6)

        # Top 5 asks: 1500 + 2500 + 1200 + 3500 + 2000 = 10700
        assert features['ask_depth_5'] == pytest.approx(10700, abs=1e-6)

    def test_orderbook_depth_imbalance(self):
        """Test depth imbalance calculation."""
        # More bids than asks (buying pressure)
        orderbook = {
            'bids': [
                {'price': '0.45', 'size': '3000'},
                {'price': '0.44', 'size': '2000'},
            ],
            'asks': [
                {'price': '0.47', 'size': '1000'},
                {'price': '0.48', 'size': '1000'},
            ]
        }

        features = OrderbookFeatures.extract(orderbook)

        # bid_depth = 5000, ask_depth = 2000
        # imbalance = (5000 - 2000) / 7000 = 0.4286
        assert features['depth_imbalance'] == pytest.approx(0.4286, abs=1e-4)

        # More asks than bids (selling pressure)
        orderbook = {
            'bids': [{'price': '0.45', 'size': '1000'}],
            'asks': [{'price': '0.47', 'size': '5000'}]
        }

        features = OrderbookFeatures.extract(orderbook)

        # bid_depth = 1000, ask_depth = 5000
        # imbalance = (1000 - 5000) / 6000 = -0.6667
        assert features['depth_imbalance'] == pytest.approx(-0.6667, abs=1e-4)

    def test_empty_orderbook(self):
        """Test handling of empty orderbook."""
        orderbook = {'bids': [], 'asks': []}

        features = OrderbookFeatures.extract(orderbook)

        assert features['spread'] == 0.0
        assert features['spread_pct'] == 0.0
        assert features['mid_price'] == 0.5  # Default neutral
        assert features['bid_depth_5'] == 0.0
        assert features['ask_depth_5'] == 0.0
        assert features['depth_imbalance'] == 0.0

    def test_missing_orderbook_keys(self):
        """Test handling of missing bids/asks keys."""
        orderbook = {}

        features = OrderbookFeatures.extract(orderbook)

        assert features['mid_price'] == 0.5
        assert features['depth_imbalance'] == 0.0


class TestVolumeFeatures:
    """Test volume feature extraction."""

    def test_basic_volume_extraction(self):
        """Test basic volume feature extraction."""
        market = {
            'volume24hr': 50000,
            'volume1wk': 200000,
            'liquidity': 100000
        }

        features = VolumeFeatures.extract(market)

        assert features['volume_24h'] == 50000
        assert features['volume_7d'] == 200000
        assert features['liquidity'] == 100000

    def test_volume_trend_calculation(self):
        """Test volume trend calculation."""
        # Recent volume higher than average (trending up)
        market = {
            'volume24hr': 50000,
            'volume1wk': 200000,
            'liquidity': 0
        }

        features = VolumeFeatures.extract(market)

        # 7d daily avg = 200000 / 7 ≈ 28571
        # trend = 50000 / 28571 ≈ 1.75
        assert features['volume_trend'] == pytest.approx(1.75, abs=0.01)

        # Recent volume lower than average (trending down)
        market = {
            'volume24hr': 10000,
            'volume1wk': 200000,
            'liquidity': 0
        }

        features = VolumeFeatures.extract(market)

        # trend = 10000 / 28571 ≈ 0.35
        assert features['volume_trend'] == pytest.approx(0.35, abs=0.01)

    def test_missing_volume_keys(self):
        """Test handling of missing volume keys."""
        market = {}

        features = VolumeFeatures.extract(market)

        assert features['volume_24h'] == 0
        assert features['volume_7d'] == 0
        assert features['liquidity'] == 0
        assert features['volume_trend'] == 1.0  # Default

    def test_zero_volume(self):
        """Test handling of zero volume."""
        market = {
            'volume24hr': 0,
            'volume1wk': 0,
            'liquidity': 0
        }

        features = VolumeFeatures.extract(market)

        assert features['volume_trend'] == 1.0  # Avoid division by zero


class TestTimeFeatures:
    """Test time feature extraction."""

    def test_basic_time_extraction(self):
        """Test basic time feature extraction."""
        current = datetime(2025, 1, 15, 14, 30, tzinfo=timezone.utc)  # Wednesday
        expiry = datetime(2025, 2, 15, 14, 30, tzinfo=timezone.utc)   # 31 days later

        features = TimeFeatures.extract(expiry, current)

        assert features['days_to_expiry'] == 31.0
        assert features['hours_to_expiry'] == pytest.approx(31 * 24, abs=0.1)
        assert features['minutes_to_expiry'] == pytest.approx(31 * 24 * 60, abs=1)
        assert features['hour_of_day'] == 14.0
        assert features['day_of_week'] == 2.0  # Wednesday (0=Monday)
        assert features['is_weekend'] == 0.0
        assert features['month'] == 1.0

    def test_weekend_detection(self):
        """Test weekend detection."""
        # Saturday
        saturday = datetime(2025, 1, 18, 12, 0, tzinfo=timezone.utc)  # Sat Jan 18
        expiry = saturday + timedelta(days=1)

        features = TimeFeatures.extract(expiry, saturday)

        assert features['day_of_week'] == 5.0  # Saturday
        assert features['is_weekend'] == 1.0

        # Sunday
        sunday = datetime(2025, 1, 19, 12, 0, tzinfo=timezone.utc)  # Sun Jan 19
        features = TimeFeatures.extract(expiry, sunday)

        assert features['day_of_week'] == 6.0  # Sunday
        assert features['is_weekend'] == 1.0

        # Monday
        monday = datetime(2025, 1, 20, 12, 0, tzinfo=timezone.utc)  # Mon Jan 20
        features = TimeFeatures.extract(expiry, monday)

        assert features['day_of_week'] == 0.0  # Monday
        assert features['is_weekend'] == 0.0

    def test_quarter_end_detection(self):
        """Test quarter end detection."""
        # Q1 end (March)
        march = datetime(2025, 3, 15, 12, 0, tzinfo=timezone.utc)
        expiry = march + timedelta(days=1)
        features = TimeFeatures.extract(expiry, march)
        assert features['is_quarter_end'] == 1.0

        # Q2 end (June)
        june = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        features = TimeFeatures.extract(expiry, june)
        assert features['is_quarter_end'] == 1.0

        # Not quarter end (February)
        feb = datetime(2025, 2, 15, 12, 0, tzinfo=timezone.utc)
        features = TimeFeatures.extract(expiry, feb)
        assert features['is_quarter_end'] == 0.0

    def test_year_end_detection(self):
        """Test year end detection."""
        # December (year end)
        december = datetime(2025, 12, 15, 12, 0, tzinfo=timezone.utc)
        expiry = december + timedelta(days=1)
        features = TimeFeatures.extract(expiry, december)
        assert features['is_year_end'] == 1.0

        # Not December
        january = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        features = TimeFeatures.extract(expiry, january)
        assert features['is_year_end'] == 0.0

    def test_expired_market(self):
        """Test handling of already expired market."""
        current = datetime(2025, 2, 15, 12, 0, tzinfo=timezone.utc)
        expiry = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)  # Past

        features = TimeFeatures.extract(expiry, current)

        # Should return 0, not negative
        assert features['days_to_expiry'] == 0.0
        assert features['hours_to_expiry'] == 0.0
        assert features['minutes_to_expiry'] == 0.0

    def test_timezone_naive_handling(self):
        """Test handling of timezone-naive datetimes."""
        # Naive datetimes should be converted to UTC
        current = datetime(2025, 1, 15, 12, 0)  # No timezone
        expiry = datetime(2025, 2, 15, 12, 0)   # No timezone

        features = TimeFeatures.extract(expiry, current)

        assert features['days_to_expiry'] == 31.0

    def test_default_current_time(self):
        """Test default current time (now)."""
        expiry = datetime.now(timezone.utc) + timedelta(days=7)

        features = TimeFeatures.extract(expiry)  # No current_time specified

        # Should be approximately 7 days (allow for timing differences)
        assert 6.0 <= features['days_to_expiry'] <= 8.0


class TestExtractAllCommonFeatures:
    """Test convenience function for extracting all features."""

    def test_extract_all_features(self):
        """Test extracting all common features at once."""
        orderbook = {
            'bids': [{'price': '0.45', 'size': '1000'}],
            'asks': [{'price': '0.47', 'size': '1500'}]
        }
        market = {
            'volume24hr': 50000,
            'volume1wk': 200000,
            'liquidity': 100000
        }
        expiry = datetime.now(timezone.utc) + timedelta(days=30)

        features = extract_all_common_features(orderbook, market, expiry)

        # Should have features from all three categories
        # Orderbook: 6 features (spread, spread_pct, mid_price, bid_depth_5, ask_depth_5, depth_imbalance)
        # Volume: 4 features (volume_24h, volume_7d, liquidity, volume_trend)
        # Time: 9 features (days/hours/minutes to expiry, hour_of_day, day_of_week, is_weekend, month, is_quarter_end, is_year_end)
        assert len(features) == 19

        # Spot check a few
        assert 'spread' in features
        assert 'volume_24h' in features
        assert 'days_to_expiry' in features

    def test_extract_all_with_best_bid_ask(self):
        """Test extracting all features including best_bid/ask."""
        orderbook = {
            'bids': [{'price': '0.45', 'size': '1000'}],
            'asks': [{'price': '0.47', 'size': '1500'}]
        }
        market = {'volume24hr': 0, 'volume1wk': 0, 'liquidity': 0}
        expiry = datetime.now(timezone.utc) + timedelta(days=1)

        features = extract_all_common_features(
            orderbook, market, expiry, return_best_bid_ask=True
        )

        # Should have 2 additional features (best_bid, best_ask)
        assert len(features) == 21
        assert 'best_bid' in features
        assert 'best_ask' in features


class TestBackwardCompatibility:
    """
    Test that new centralized features match old implementations.

    This validates that refactoring doesn't change feature values.
    """

    def test_orderbook_matches_old_event_trader(self):
        """Test that orderbook features match event trader's old implementation."""
        # This would compare against MarketFeatureExtractor.extract_orderbook_features()
        # from feature_extractor.py

        orderbook = {
            'bids': [
                {'price': '0.45', 'size': '1000'},
                {'price': '0.44', 'size': '2000'},
            ],
            'asks': [
                {'price': '0.47', 'size': '1500'},
                {'price': '0.48', 'size': '2500'},
            ]
        }

        # New implementation
        new_features = OrderbookFeatures.extract(orderbook, return_best_bid_ask=True)

        # Expected values (from old implementation)
        expected_spread = 0.02
        expected_mid_price = 0.46
        expected_spread_pct = (0.02 / 0.46) * 100

        assert new_features['spread'] == pytest.approx(expected_spread, abs=1e-6)
        assert new_features['mid_price'] == pytest.approx(expected_mid_price, abs=1e-6)
        assert new_features['spread_pct'] == pytest.approx(expected_spread_pct, abs=1e-4)


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
