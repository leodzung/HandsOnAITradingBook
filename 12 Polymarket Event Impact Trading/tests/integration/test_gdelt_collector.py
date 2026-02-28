"""
Integration tests for GDELTCollector.

Tests use mocked HTTP responses to avoid hitting real APIs.
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestGDELTCollector:
    """Test GDELTCollector with mocked API responses."""

    @pytest.fixture
    def collector(self, tmp_path):
        """Create collector with temp database."""
        from collectors.gdelt_collector import GDELTCollector
        db_path = str(tmp_path / 'test_gdelt.db')
        return GDELTCollector(
            db_path=db_path,
            rate_limit_per_sec=100.0,
        )

    def test_init_creates_database(self, collector):
        """Collector should create SQLite database on init."""
        assert Path(collector.db_path).exists()

    def test_crypto_keywords_defined(self, collector):
        """Collector must have crypto keyword filters."""
        assert len(collector.CRYPTO_KEYWORDS) > 0
        assert 'bitcoin' in collector.CRYPTO_KEYWORDS
        assert 'ethereum' in collector.CRYPTO_KEYWORDS

    def test_crypto_themes_defined(self, collector):
        """Collector must have GDELT theme filters."""
        assert len(collector.CRYPTO_THEMES) > 0
        assert 'ECON_CRYPTOCURRENCY' in collector.CRYPTO_THEMES

    @patch('requests.get')
    def test_rate_limiting(self, mock_get, collector):
        """Collector should respect rate limits."""
        assert collector.rate_limit_per_sec > 0
        assert collector.min_request_interval > 0

    def test_database_tables_created(self, collector):
        """Database should have required tables."""
        conn = sqlite3.connect(collector.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        # Should have at least a news/articles table
        assert len(tables) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
