"""
Validation tests for feature centralization migration.

Ensures that all three bots can still extract features correctly
after migration to centralized common_features.py.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import numpy as np
import pandas as pd

# Add src to path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from features.feature_extractor import MarketFeatureExtractor, EventFeatureExtractor
from features.price_level_features import PriceLevelFeatureExtractor, MarketMicrostructureFeatures
from features.short_expiry_features import ShortExpiryFeatureExtractor, MicrostructureFeatures


class TestEventTraderMigration:
    """Test that event trader still works after migration."""

    def test_orderbook_extraction_works(self):
        """Test event trader orderbook extraction."""
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

        features = MarketFeatureExtractor.extract_orderbook_features(orderbook)

        # Should have all expected features
        assert 'spread' in features
        assert 'spread_pct' in features
        assert 'mid_price' in features
        assert 'best_bid' in features
        assert 'best_ask' in features
        assert 'bid_depth_5' in features
        assert 'ask_depth_5' in features
        assert 'depth_imbalance' in features
        assert 'bid_ask_imbalance' in features  # Event trader specific

        # Validate values
        assert features['spread'] == pytest.approx(0.02, abs=1e-6)
        assert features['mid_price'] == pytest.approx(0.46, abs=1e-6)


class TestPriceLevelTraderMigration:
    """Test that price-level trader still works after migration."""

    def test_market_microstructure_extraction(self):
        """Test price-level trader market features."""
        market = {
            'volume24hr': 50000,
            'volume1wk': 200000,
            'liquidity': 100000
        }

        orderbook = {
            'bids': [{'price': '0.45', 'size': '1000'}],
            'asks': [{'price': '0.47', 'size': '1500'}]
        }

        features = MarketMicrostructureFeatures.extract_market_features(market, orderbook)

        # Should have all expected features
        assert 'market_price' in features
        assert 'spread' in features
        assert 'spread_pct' in features
        assert 'depth_imbalance' in features
        assert 'volume_24h' in features
        assert 'volume_7d' in features
        assert 'liquidity' in features
        assert 'volume_trend' in features

        # Validate values
        assert features['volume_24h'] == 50000
        assert features['volume_7d'] == 200000
        assert features['liquidity'] == 100000

    def test_full_feature_extraction_pipeline(self):
        """Test full price-level feature extraction pipeline."""
        # Sample parsed market
        parsed_market = {
            'asset': 'BTC',
            'strike_price': 100000.0,
            'expiry_date': datetime(2025, 12, 31, tzinfo=timezone.utc),
            'days_to_expiry': 300,
            'direction': 'ABOVE',
            'conditionId': '0xtest123',
            'token_id': '123456',
            'question': 'Will Bitcoin reach $100,000 by Dec 31, 2025?'
        }

        # Generate sample historical data
        np.random.seed(42)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        prices = 90000 + np.cumsum(np.random.randn(100) * 500)

        historical_ohlcv = pd.DataFrame({
            'date': dates,
            'open': prices * 0.99,
            'high': prices * 1.01,
            'low': prices * 0.99,
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, 100)
        })

        # Sample Polymarket data
        polymarket_data = {
            'market': {
                'volume24hr': 50000,
                'volume1wk': 200000,
                'liquidity': 100000
            },
            'orderbook': {
                'bids': [{'price': '0.45', 'size': '1000'}],
                'asks': [{'price': '0.47', 'size': '1500'}]
            }
        }

        # Extract features
        extractor = PriceLevelFeatureExtractor()

        features = extractor.extract_all_features(
            parsed_market=parsed_market,
            spot_price=89759.0,
            historical_ohlcv=historical_ohlcv,
            polymarket_data=polymarket_data
        )

        # Should have all feature categories
        assert len(features) >= 35  # Should have 40+ features

        # Check for key features
        assert 'spread' in features
        assert 'volume_24h' in features
        assert 'volatility_30d' in features
        assert 'days_to_expiry' in features


class TestShortExpiryTraderMigration:
    """Test that short-expiry trader still works after migration."""

    def test_microstructure_extraction(self):
        """Test short-expiry microstructure features."""
        market = {
            'bestBid': 0.45,
            'bestAsk': 0.47,
            'lastTradePrice': 0.46
        }

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

        features = MicrostructureFeatures.extract(market, orderbook)

        # Should have all expected features
        assert 'spread' in features
        assert 'spread_pct' in features
        assert 'mid_price' in features
        assert 'depth_imbalance' in features
        assert 'bid_concentration' in features  # Short-expiry specific
        assert 'ask_concentration' in features  # Short-expiry specific
        assert 'effective_spread' in features   # Short-expiry specific

        # Validate values
        assert features['spread'] == pytest.approx(0.02, abs=1e-6)

    def test_full_feature_extraction_pipeline(self):
        """Test full short-expiry feature extraction pipeline."""
        market = {
            'conditionId': '0xtest',
            'question': 'Will BTC hit $100k?',
            'endDate': (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat(),
            'bestBid': 0.45,
            'bestAsk': 0.47,
            'lastTradePrice': 0.46,
            'volume24hr': 50000,
            'liquidity': 100000
        }

        orderbook = {
            'bids': [{'price': '0.45', 'size': '1000'}],
            'asks': [{'price': '0.47', 'size': '1500'}]
        }

        # Extract features
        extractor = ShortExpiryFeatureExtractor()

        features_df = extractor.extract_all_features(
            market=market,
            bucket='ultra_short',
            orderbook=orderbook
        )

        # Should be a DataFrame
        assert isinstance(features_df, pd.DataFrame)
        assert len(features_df) == 1

        # Check for key features from all categories
        features = features_df.iloc[0].to_dict()

        # Orderbook features (centralized)
        assert 'spread' in features
        assert 'mid_price' in features
        assert 'depth_imbalance' in features

        # Time decay features (short-expiry specific)
        assert 'hours_to_expiry' in features
        assert 'decay_rate' in features
        assert 'urgency_score' in features

        # Microstructure features (short-expiry specific)
        assert 'bid_concentration' in features
        assert 'effective_spread' in features


class TestBackwardCompatibility:
    """Test that feature values match old implementations."""

    def test_orderbook_values_unchanged(self):
        """Ensure orderbook feature values didn't change after migration."""
        orderbook = {
            'bids': [
                {'price': '0.45', 'size': '1000'},
                {'price': '0.44', 'size': '2000'},
                {'price': '0.43', 'size': '1500'},
                {'price': '0.42', 'size': '3000'},
                {'price': '0.41', 'size': '2500'},
            ],
            'asks': [
                {'price': '0.47', 'size': '1500'},
                {'price': '0.48', 'size': '2500'},
                {'price': '0.49', 'size': '1200'},
                {'price': '0.50', 'size': '3500'},
                {'price': '0.51', 'size': '2000'},
            ]
        }

        # Event trader
        event_features = MarketFeatureExtractor.extract_orderbook_features(orderbook)

        # Price-level trader
        market = {'volume24hr': 0, 'volume1wk': 0, 'liquidity': 0}
        price_features = MarketMicrostructureFeatures.extract_market_features(market, orderbook)

        # Short-expiry trader
        market_short = {'bestBid': 0.45, 'bestAsk': 0.47, 'lastTradePrice': 0.46}
        short_features = MicrostructureFeatures.extract(market_short, orderbook)

        # All should calculate spread the same way
        assert event_features['spread'] == pytest.approx(0.02, abs=1e-6)
        assert price_features['spread'] == pytest.approx(0.02, abs=1e-6)
        assert short_features['spread'] == pytest.approx(0.02, abs=1e-6)

        # All should calculate mid_price the same way
        assert event_features['mid_price'] == pytest.approx(0.46, abs=1e-6)
        assert price_features['market_price'] == pytest.approx(0.46, abs=1e-6)  # Different name
        assert short_features['mid_price'] == pytest.approx(0.46, abs=1e-6)

        # All should calculate depth_imbalance the same way
        # bid_depth_5 = 10000, ask_depth_5 = 10700
        # imbalance = (10000 - 10700) / 20700 ≈ -0.0338
        assert event_features['depth_imbalance'] == pytest.approx(-0.0338, abs=1e-4)
        assert price_features['depth_imbalance'] == pytest.approx(-0.0338, abs=1e-4)
        assert short_features['depth_imbalance'] == pytest.approx(-0.0338, abs=1e-4)


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
