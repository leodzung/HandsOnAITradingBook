"""
Structural tests for ARCH-016: Feature extractors must return None for uncomputable markets.

Rationale:
    Returning plausible-looking default values (e.g. 24h expiry, mid=0.5) for markets
    missing end_date or empty orderbooks silently poisons ML training data.
    Callers must skip markets where extractors return None.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTimeDecayFeaturesNoneReturn:
    """TimeDecayFeatures.extract must return None when end_date is missing."""

    def test_returns_none_when_end_date_missing(self):
        """ARCH-016: TimeDecayFeatures.extract returns None if market has no end_date."""
        from features.short_expiry_features import TimeDecayFeatures

        market_no_date = {'conditionId': 'abc123', 'question': 'Will X happen?'}
        result = TimeDecayFeatures.extract(market_no_date, bucket='short')
        assert result is None, (
            "TimeDecayFeatures.extract must return None when end_date is missing, "
            f"got: {result}"
        )

    def test_returns_none_when_end_date_empty_string(self):
        """ARCH-016: TimeDecayFeatures.extract returns None if end_date is empty."""
        from features.short_expiry_features import TimeDecayFeatures

        market_empty_date = {'conditionId': 'abc123', 'endDate': '', 'end_date_iso': ''}
        result = TimeDecayFeatures.extract(market_empty_date, bucket='short')
        assert result is None, (
            "TimeDecayFeatures.extract must return None when end_date is empty string, "
            f"got: {result}"
        )

    def test_returns_dict_when_end_date_valid(self):
        """ARCH-016: TimeDecayFeatures.extract returns a dict when end_date is valid."""
        from features.short_expiry_features import TimeDecayFeatures
        from datetime import datetime, timezone, timedelta

        future = (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()
        market = {'conditionId': 'abc123', 'endDate': future}
        result = TimeDecayFeatures.extract(market, bucket='short')
        assert result is not None, "TimeDecayFeatures.extract should return features for valid end_date"
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert 'hours_to_expiry' in result


class TestOrderbookFeaturesNoneReturn:
    """OrderbookFeatures.extract must return None for empty/missing orderbook."""

    def test_returns_none_for_empty_orderbook(self):
        """ARCH-016: OrderbookFeatures.extract returns None for empty orderbook."""
        from features.common_features import OrderbookFeatures

        empty_book = {'bids': [], 'asks': []}
        result = OrderbookFeatures.extract(empty_book)
        assert result is None, (
            "OrderbookFeatures.extract must return None for empty orderbook, "
            f"got: {result}"
        )

    def test_returns_dict_for_valid_orderbook(self):
        """ARCH-016: OrderbookFeatures.extract returns dict for a valid orderbook."""
        from features.common_features import OrderbookFeatures

        valid_book = {
            'bids': [{'price': '0.45', 'size': '100'}],
            'asks': [{'price': '0.55', 'size': '100'}],
        }
        result = OrderbookFeatures.extract(valid_book)
        assert result is not None, "OrderbookFeatures.extract should return features for valid orderbook"
        assert isinstance(result, dict)


class TestCallerSkipsNoneFeatures:
    """Verify that ShortExpiryFeatureExtractor.extract_all_features skips markets with None features."""

    def test_extract_all_features_skips_missing_end_date(self):
        """ARCH-016: extract_all_features returns empty result for markets missing end_date."""
        from features.short_expiry_features import ShortExpiryFeatureExtractor

        extractor = ShortExpiryFeatureExtractor()
        market_no_date = {
            'conditionId': 'abc123',
            'question': 'Will X?',
            'bestBid': '0.4',
            'bestAsk': '0.6',
        }
        # Should return empty DataFrame (not a DataFrame with fake defaults)
        result = extractor.extract_all_features(market_no_date, bucket='short')
        assert result is not None, "extract_all_features should not crash"
        assert len(result) == 0, (
            "extract_all_features must return empty result when TimeDecayFeatures returns None "
            f"(missing end_date), got {len(result)} rows"
        )
