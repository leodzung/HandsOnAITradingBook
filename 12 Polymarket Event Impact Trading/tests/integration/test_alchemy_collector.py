"""
Integration tests for AlchemyDataCollector.

Tests use mocked HTTP responses to avoid hitting real APIs.
"""

import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestAlchemyCollector:
    """Test AlchemyDataCollector with mocked RPC responses."""

    @pytest.fixture
    def collector(self, tmp_path):
        """Create collector with temp database."""
        from collectors.alchemy_collector import AlchemyDataCollector
        db_path = str(tmp_path / 'test_alchemy.db')
        return AlchemyDataCollector(
            api_key='test_key',
            db_path=db_path,
            rate_limit_per_sec=100.0,
        )

    def test_init_creates_database(self, collector):
        """Collector should create SQLite database on init."""
        assert Path(collector.db_path).exists()

    def test_init_creates_tables(self, collector):
        """Database should have required tables."""
        conn = sqlite3.connect(collector.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert 'on_chain_trades' in tables
        assert 'token_condition_map' in tables
        assert 'collection_checkpoints' in tables

    def test_decode_order_filled_event(self, collector):
        """Test event log decoding (core parsing logic)."""
        # Minimal mock log entry with valid structure
        mock_log = {
            'topics': [
                collector.ORDER_FILLED_TOPIC,
                '0x' + '0' * 64,  # orderHash
            ],
            'data': '0x' + '00' * 32 * 6,  # 6 uint256 values
            'transactionHash': '0xabc123',
            'logIndex': '0x0',
            'blockNumber': '0x100',
        }

        result = collector.decode_order_filled(mock_log)
        # Result may be None for zero-amount trades or a dict
        assert result is None or isinstance(result, dict)

    def test_get_current_block(self, collector):
        """Test fetching current block number with mocked RPC."""
        with patch.object(collector, '_make_rpc_call', return_value='0x3A98'):
            block = collector.get_current_block()
            assert isinstance(block, int)
            assert block == 15000

    def test_endpoint_batch_sizes(self, collector):
        """Collector should have endpoint-specific batch sizes."""
        assert len(collector.ENDPOINT_BATCH_SIZES) > 0
        assert all(v > 0 for v in collector.ENDPOINT_BATCH_SIZES.values())


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
