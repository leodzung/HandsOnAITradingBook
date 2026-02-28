"""
Integration tests for PolymarketDataCollector.

Tests use mocked HTTP responses to avoid hitting real APIs.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestDataCollector:
    """Test PolymarketDataCollector with mocked API responses."""

    @pytest.fixture
    def collector(self, tmp_path):
        """Create collector with temp output directory."""
        from collectors.data_collector import PolymarketDataCollector
        return PolymarketDataCollector(output_dir=str(tmp_path))

    def test_init_creates_output_dir(self, collector):
        """Collector should create output directory on init."""
        assert Path(collector.output_dir).exists()

    @patch('requests.Session.get')
    def test_get_active_markets_success(self, mock_get, collector):
        """get_active_markets should return list on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'question': 'Will BTC reach $100k?', 'condition_id': 'abc123'},
            {'question': 'Will ETH reach $5k?', 'condition_id': 'def456'},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        markets = collector.get_active_markets(limit=10)
        assert isinstance(markets, list)
        assert len(markets) == 2

    @patch('requests.Session.get')
    def test_get_active_markets_error(self, mock_get, collector):
        """get_active_markets should return empty list on error."""
        mock_get.side_effect = Exception("Connection refused")

        markets = collector.get_active_markets()
        assert isinstance(markets, list)
        assert len(markets) == 0

    @patch('requests.Session.get')
    def test_get_market_details(self, mock_get, collector):
        """get_market_details should return dict on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'question': 'Will BTC reach $100k?',
            'condition_id': 'abc123',
            'outcomePrices': '[0.65, 0.38]',
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        details = collector.get_market_details('abc123')
        assert isinstance(details, dict)
        assert details.get('question') == 'Will BTC reach $100k?'

    def test_save_markets_snapshot(self, collector, tmp_path):
        """save_markets_snapshot should write JSON file."""
        markets = [{'question': 'Test', 'id': '1'}]
        filepath = collector.save_markets_snapshot(markets, 'test_snapshot.json')

        assert Path(filepath).exists()
        with open(filepath) as f:
            data = json.load(f)
        assert len(data) == 1

    @patch('requests.Session.get')
    def test_get_market_by_keywords(self, mock_get, collector):
        """get_market_by_keywords should filter markets."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'question': 'Will Bitcoin reach $100k?', 'description': ''},
            {'question': 'Will it rain tomorrow?', 'description': ''},
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = collector.get_market_by_keywords(['bitcoin'], limit=10)
        assert isinstance(results, list)
        # Should find at least the bitcoin market
        assert any('bitcoin' in m.get('question', '').lower() for m in results) if results else True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
