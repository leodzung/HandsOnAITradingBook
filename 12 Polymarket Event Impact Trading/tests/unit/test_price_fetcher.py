"""
Functional unit tests for PriceFetcher and MarketPrices.

Tests use a mock client — no real API calls.

Actual API signatures (from src/core/price_fetcher.py):
- PriceFetcher.__init__(client) — client needs .get_market_prices(condition_id, side=)
- PriceFetcher.get_entry_prices(condition_id) → Optional[MarketPrices]
- PriceFetcher.get_exit_prices(condition_id) → Optional[MarketPrices]
- PriceFetcher.get_entry_and_exit_prices(condition_id) → Optional[Tuple[MarketPrices, MarketPrices]]
- PriceFetcher.calculate_spread(condition_id) → Optional[Dict]
- PriceFetcher.validate_prices(prices, max_price=0.90) → Tuple[bool, Optional[str]]
- PriceFetcher.clear_cache() → None
- MarketPrices(yes_price, no_price, source, condition_id) — dataclass
- MarketPrices.get_outcome_price(outcome) → float
"""

import math
import time
import pytest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.price_fetcher import PriceFetcher, MarketPrices


CONDITION_ID = 'abc123def456abcd'


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_market_prices.return_value = {'yes': 0.55, 'no': 0.48}
    return client


@pytest.fixture
def fetcher(mock_client):
    return PriceFetcher(mock_client)


# ── MarketPrices dataclass ──────────────────────────────────────────


class TestMarketPrices:
    def test_basic_construction(self):
        mp = MarketPrices(yes_price=0.6, no_price=0.4, source='CLOB_ASK', condition_id='x')
        assert mp.yes_price == 0.6
        assert mp.no_price == 0.4

    def test_post_init_rejects_string(self):
        with pytest.raises(TypeError, match="yes_price must be numeric"):
            MarketPrices(yes_price="bad", no_price=0.4, source='CLOB_ASK', condition_id='x')

    def test_post_init_rejects_none(self):
        with pytest.raises(TypeError, match="no_price must be numeric"):
            MarketPrices(yes_price=0.5, no_price=None, source='CLOB_ASK', condition_id='x')

    def test_get_outcome_price_yes(self):
        mp = MarketPrices(yes_price=0.6, no_price=0.4, source='CLOB_ASK', condition_id='x')
        assert mp.get_outcome_price('YES') == 0.6
        assert mp.get_outcome_price('yes') == 0.6

    def test_get_outcome_price_no(self):
        mp = MarketPrices(yes_price=0.6, no_price=0.4, source='CLOB_ASK', condition_id='x')
        assert mp.get_outcome_price('NO') == 0.4
        assert mp.get_outcome_price('No') == 0.4

    def test_get_outcome_price_invalid(self):
        mp = MarketPrices(yes_price=0.6, no_price=0.4, source='CLOB_ASK', condition_id='x')
        with pytest.raises(ValueError, match="Invalid outcome"):
            mp.get_outcome_price('MAYBE')

    def test_get_outcome_price_none(self):
        mp = MarketPrices(yes_price=0.6, no_price=0.4, source='CLOB_ASK', condition_id='x')
        with pytest.raises(ValueError, match="got None"):
            mp.get_outcome_price(None)


# ── PriceFetcher.get_entry_prices ───────────────────────────────────


class TestGetEntryPrices:
    def test_happy_path(self, fetcher, mock_client):
        result = fetcher.get_entry_prices(CONDITION_ID)
        assert result is not None
        assert result.yes_price == 0.55
        assert result.no_price == 0.48
        assert result.source == 'CLOB_ASK'
        assert result.condition_id == CONDITION_ID
        mock_client.get_market_prices.assert_called_once_with(CONDITION_ID, side='BUY')

    def test_returns_none_when_yes_missing(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': None, 'no': 0.48}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_when_no_missing(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': 0.55, 'no': None}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_for_nan(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': float('nan'), 'no': 0.48}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_for_inf(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': 0.55, 'no': float('inf')}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_for_zero_price(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': 0.0, 'no': 0.48}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_for_price_equals_one(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': 1.0, 'no': 0.48}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_for_negative_price(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': -0.1, 'no': 0.48}
        assert fetcher.get_entry_prices(CONDITION_ID) is None

    def test_returns_none_for_string_price(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': "0.55", 'no': 0.48}
        assert fetcher.get_entry_prices(CONDITION_ID) is None


# ── PriceFetcher.get_exit_prices ────────────────────────────────────


class TestGetExitPrices:
    def test_happy_path(self, fetcher, mock_client):
        result = fetcher.get_exit_prices(CONDITION_ID)
        assert result is not None
        assert result.source == 'CLOB_BID'
        mock_client.get_market_prices.assert_called_once_with(CONDITION_ID, side='SELL')

    def test_returns_none_when_prices_missing(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': None, 'no': None}
        assert fetcher.get_exit_prices(CONDITION_ID) is None

    def test_returns_none_for_nan(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': float('nan'), 'no': 0.48}
        assert fetcher.get_exit_prices(CONDITION_ID) is None


# ── PriceFetcher.get_entry_and_exit_prices ──────────────────────────


class TestGetEntryAndExitPrices:
    def test_both_succeed(self, fetcher, mock_client):
        mock_client.get_market_prices.side_effect = [
            {'yes': 0.55, 'no': 0.48},  # entry (BUY)
            {'yes': 0.53, 'no': 0.46},  # exit (SELL)
        ]
        result = fetcher.get_entry_and_exit_prices(CONDITION_ID)
        assert result is not None
        entry, exit_ = result
        assert entry.source == 'CLOB_ASK'
        assert exit_.source == 'CLOB_BID'

    def test_returns_none_when_entry_fails(self, fetcher, mock_client):
        mock_client.get_market_prices.side_effect = [
            {'yes': None, 'no': 0.48},  # entry fails
            {'yes': 0.53, 'no': 0.46},  # exit would succeed
        ]
        assert fetcher.get_entry_and_exit_prices(CONDITION_ID) is None

    def test_returns_none_when_exit_fails(self, fetcher, mock_client):
        mock_client.get_market_prices.side_effect = [
            {'yes': 0.55, 'no': 0.48},  # entry succeeds
            {'yes': None, 'no': 0.46},  # exit fails
        ]
        assert fetcher.get_entry_and_exit_prices(CONDITION_ID) is None


# ── PriceFetcher.calculate_spread ───────────────────────────────────


class TestCalculateSpread:
    def test_normal_spread(self, fetcher, mock_client):
        mock_client.get_market_prices.side_effect = [
            {'yes': 0.60, 'no': 0.50},  # entry (ASK)
            {'yes': 0.55, 'no': 0.45},  # exit (BID)
        ]
        result = fetcher.calculate_spread(CONDITION_ID)
        assert result is not None
        # YES spread = 0.60 - 0.55 = 0.05, mid = 0.575
        assert abs(result['yes_spread_pct'] - (0.05 / 0.575 * 100)) < 0.01
        assert result['yes_ask'] == 0.60
        assert result['yes_bid'] == 0.55

    def test_returns_none_when_prices_unavailable(self, fetcher, mock_client):
        mock_client.get_market_prices.return_value = {'yes': None, 'no': None}
        assert fetcher.calculate_spread(CONDITION_ID) is None


# ── PriceFetcher.validate_prices ────────────────────────────────────


class TestValidatePrices:
    def test_valid_prices(self, fetcher):
        mp = MarketPrices(yes_price=0.5, no_price=0.5, source='CLOB_ASK', condition_id='x')
        is_valid, reason = fetcher.validate_prices(mp)
        assert is_valid is True
        assert reason is None

    def test_yes_exceeds_max(self, fetcher):
        mp = MarketPrices(yes_price=0.95, no_price=0.1, source='CLOB_ASK', condition_id='x')
        is_valid, reason = fetcher.validate_prices(mp)
        assert is_valid is False
        assert 'YES price' in reason

    def test_no_exceeds_max(self, fetcher):
        mp = MarketPrices(yes_price=0.1, no_price=0.95, source='CLOB_ASK', condition_id='x')
        is_valid, reason = fetcher.validate_prices(mp)
        assert is_valid is False
        assert 'NO price' in reason

    def test_custom_max_price(self, fetcher):
        mp = MarketPrices(yes_price=0.85, no_price=0.1, source='CLOB_ASK', condition_id='x')
        is_valid, _ = fetcher.validate_prices(mp, max_price=0.80)
        assert is_valid is False

    def test_boundary_at_max(self, fetcher):
        mp = MarketPrices(yes_price=0.90, no_price=0.1, source='CLOB_ASK', condition_id='x')
        is_valid, _ = fetcher.validate_prices(mp, max_price=0.90)
        assert is_valid is True  # <= max, not < max


# ── PriceFetcher caching ───────────────────────────────────────────


class TestCaching:
    def test_cache_hit_avoids_api_call(self, fetcher, mock_client):
        # First call hits API
        fetcher.get_entry_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 1

        # Second call should use cache
        result = fetcher.get_entry_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 1  # No extra call
        assert result.yes_price == 0.55

    def test_cache_expires(self, fetcher, mock_client):
        fetcher._cache_ttl = 0.01  # 10ms TTL for test speed

        fetcher.get_entry_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 1

        time.sleep(0.02)  # Wait for cache to expire

        fetcher.get_entry_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 2

    def test_clear_cache(self, fetcher, mock_client):
        fetcher.get_entry_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 1

        fetcher.clear_cache()

        fetcher.get_entry_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 2

    def test_entry_and_exit_cached_independently(self, fetcher, mock_client):
        mock_client.get_market_prices.side_effect = [
            {'yes': 0.55, 'no': 0.48},  # entry
            {'yes': 0.53, 'no': 0.46},  # exit
        ]
        fetcher.get_entry_prices(CONDITION_ID)
        fetcher.get_exit_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 2

        # Both should be cached now
        mock_client.get_market_prices.reset_mock()
        fetcher.get_entry_prices(CONDITION_ID)
        fetcher.get_exit_prices(CONDITION_ID)
        assert mock_client.get_market_prices.call_count == 0


# ── PriceFetcher._validate_raw_price ────────────────────────────────


class TestValidateRawPrice:
    def test_valid_price(self):
        assert PriceFetcher._validate_raw_price(0.5, 'YES', CONDITION_ID) is True

    def test_nan(self):
        assert PriceFetcher._validate_raw_price(float('nan'), 'YES', CONDITION_ID) is False

    def test_inf(self):
        assert PriceFetcher._validate_raw_price(float('inf'), 'YES', CONDITION_ID) is False

    def test_negative_inf(self):
        assert PriceFetcher._validate_raw_price(float('-inf'), 'YES', CONDITION_ID) is False

    def test_zero(self):
        assert PriceFetcher._validate_raw_price(0.0, 'YES', CONDITION_ID) is False

    def test_one(self):
        assert PriceFetcher._validate_raw_price(1.0, 'YES', CONDITION_ID) is False

    def test_negative(self):
        assert PriceFetcher._validate_raw_price(-0.5, 'YES', CONDITION_ID) is False

    def test_string(self):
        assert PriceFetcher._validate_raw_price("0.5", 'YES', CONDITION_ID) is False

    def test_none(self):
        assert PriceFetcher._validate_raw_price(None, 'YES', CONDITION_ID) is False

    def test_boundary_just_above_zero(self):
        assert PriceFetcher._validate_raw_price(0.001, 'YES', CONDITION_ID) is True

    def test_boundary_just_below_one(self):
        assert PriceFetcher._validate_raw_price(0.999, 'YES', CONDITION_ID) is True
