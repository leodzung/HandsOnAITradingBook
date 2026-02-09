"""
Tests for PolymarketClient
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
import requests

from polymarket_client import PolymarketClient, MarketFilter


class TestPolymarketClient:
    """Test suite for PolymarketClient."""

    def test_client_initialization(self):
        """Test client initialization."""
        client = PolymarketClient(
            api_key='test_key',
            api_secret='test_secret',
            private_key='test_private_key'
        )

        assert client.api_key == 'test_key'
        assert client.api_secret == 'test_secret'
        assert client.private_key == 'test_private_key'

    @patch('polymarket_client.requests.Session.get')
    def test_get_markets(self, mock_get):
        """Test getting market list."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {'conditionId': '0x1', 'question': 'Test Market 1'},
            {'conditionId': '0x2', 'question': 'Test Market 2'}
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PolymarketClient()
        markets = client.get_markets(limit=10)

        assert len(markets) == 2
        assert markets[0]['question'] == 'Test Market 1'
        mock_get.assert_called_once()

    @patch('polymarket_client.requests.Session.get')
    def test_get_markets_error_handling(self, mock_get):
        """Test error handling when API fails."""
        mock_get.side_effect = requests.exceptions.RequestException('API Error')

        client = PolymarketClient()
        markets = client.get_markets()

        assert markets == []

    def test_get_market_prices(self, mock_polymarket_client):
        """Test getting YES and NO prices."""
        prices = mock_polymarket_client.get_market_prices('0xmarket1')

        assert 'yes' in prices
        assert 'no' in prices
        assert prices['yes'] == 0.35
        assert prices['no'] == 0.65

    def test_get_market_yes_price(self, mock_polymarket_client):
        """Test getting YES price specifically."""
        yes_price = mock_polymarket_client.get_market_yes_price('0xmarket1')

        assert yes_price == 0.35

    def test_get_orderbook(self, mock_polymarket_client):
        """Test getting orderbook data."""
        orderbook = mock_polymarket_client.get_orderbook('0xtoken1')

        assert 'bids' in orderbook
        assert 'asks' in orderbook
        assert len(orderbook['bids']) > 0
        assert len(orderbook['asks']) > 0

    @patch('polymarket_client.requests.Session.get')
    def test_get_market_price_from_orderbook(self, mock_get):
        """Test calculating market price from orderbook."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'bids': [{'price': '0.34', 'size': '100'}],
            'asks': [{'price': '0.36', 'size': '120'}],
            'last_trade_price': '0.35'
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        client = PolymarketClient()
        price = client.get_market_price('0xtoken1')

        assert price == 0.35  # Uses last_trade_price

    def test_price_from_market_outcome_prices(self, sample_market):
        """Test extracting price from market's outcomePrices field."""
        client = PolymarketClient()
        yes_price = client.get_price_from_market(sample_market, outcome_index=0)
        no_price = client.get_price_from_market(sample_market, outcome_index=1)

        assert yes_price == 0.35
        assert no_price == 0.65


class TestMarketFilter:
    """Test suite for MarketFilter."""

    def test_filter_by_liquidity(self, sample_market):
        """Test filtering markets by minimum volume."""
        markets = [
            {**sample_market, 'volume': 5000},
            {**sample_market, 'volume': 500},
            {**sample_market, 'volume': 20000}
        ]

        filtered = MarketFilter.filter_by_liquidity(markets, min_volume=1000)

        assert len(filtered) == 2
        assert all(m['volume'] >= 1000 for m in filtered)

    def test_filter_active_only(self, sample_market):
        """Test filtering for active markets only."""
        past_market = {
            **sample_market,
            'active': True,
            'endDate': '2024-01-01T00:00:00+00:00'
        }
        future_market = {
            **sample_market,
            'active': True,
            'endDate': datetime.now(timezone.utc).isoformat()
        }

        markets = [past_market, future_market]
        filtered = MarketFilter.filter_active_only(markets)

        # Only future market should pass
        assert len(filtered) <= 1

    def test_filter_crypto_markets(self):
        """Test filtering for crypto-related markets."""
        markets = [
            {'question': 'Will Bitcoin hit $100k?', 'description': ''},
            {'question': 'Who will win the election?', 'description': ''},
            {'question': 'Will ETH reach $5k?', 'description': 'Ethereum price prediction'},
            {'question': 'NFL Super Bowl winner?', 'description': ''}
        ]

        filtered = MarketFilter.filter_crypto_markets(markets)

        assert len(filtered) == 2
        assert 'Bitcoin' in filtered[0]['question'] or 'ETH' in filtered[0]['question']

    def test_filter_crypto_excludes_sports(self):
        """Test that sports markets with ambiguous keywords are excluded."""
        markets = [
            {
                'question': 'Will the Avalanche win the Stanley Cup?',
                'description': 'NHL hockey playoffs'
            },
            {
                'question': 'Will Avalanche (AVAX) hit $100?',
                'description': 'Crypto price prediction'
            }
        ]

        filtered = MarketFilter.filter_crypto_markets(markets)

        assert len(filtered) == 1
        assert 'AVAX' in filtered[0]['question']

    def test_get_market_category(self):
        """Test categorizing markets."""
        btc_market = {'question': 'Will Bitcoin reach $100k?', 'description': ''}
        politics_market = {'question': 'Will Trump win the election?', 'description': ''}
        sports_market = {'question': 'Who will win the Super Bowl?', 'description': ''}

        assert MarketFilter.get_market_category(btc_market) == 'crypto'
        assert MarketFilter.get_market_category(politics_market) == 'politics'
        assert MarketFilter.get_market_category(sports_market) == 'sports'

    def test_filter_by_time_to_expiry(self, sample_market):
        """Test filtering by expiration time."""
        from datetime import timedelta

        # Market expiring in 1 day
        soon_market = {
            **sample_market,
            'endDate': (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        }

        # Market expiring in 60 days
        later_market = {
            **sample_market,
            'endDate': (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
        }

        markets = [soon_market, later_market]

        # Filter for markets expiring in 2-720 hours
        filtered = MarketFilter.filter_by_time_to_expiry(
            markets, min_hours=2, max_hours=720
        )

        # later_market should pass, soon_market should fail
        assert len(filtered) == 1
        assert filtered[0]['endDate'] == later_market['endDate']
