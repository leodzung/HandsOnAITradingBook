#!/usr/bin/env python3
"""Tests for MarketSnapshotCollector."""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ml.snapshot_collector import MarketSnapshotCollector


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    os.unlink(path)


@pytest.fixture
def collector(temp_db):
    """Create a MarketSnapshotCollector instance."""
    return MarketSnapshotCollector(db_path=temp_db)


def test_initialization(collector):
    """Test collector initializes correctly."""
    assert collector.db_path.exists()
    stats = collector.get_statistics()
    assert stats['total_snapshots'] == 0


def test_log_snapshot(collector):
    """Test logging a market snapshot."""
    snapshot_id = collector.log_snapshot(
        market_id='0x123abc',
        bot_type='price_level',
        features={
            'volatility_30d': 0.45,
            'rsi_14': 65.5,
            'spread': 0.05,
            'volume_24h': 10000
        },
        prediction={
            'model_prob': 0.65,
            'confidence': 0.75,
            'edge': 0.15,
            'predicted_outcome': 'YES'
        },
        market_data={
            'question': 'Will BTC hit $100k by Dec 31?',
            'asset': 'BTC',
            'strike_price': 100000.0,
            'expiry_date': '2026-12-31T00:00:00Z',
            'days_to_expiry': 320,
            'market_type': 'threshold',
            'condition_id': '0x123abc',
            'token_id': '0x456def'
        },
        prices={
            'yes': 0.50,
            'no': 0.50
        },
        position_opened=False,
        rejection_reason='exposure_limit'
    )

    assert snapshot_id > 0

    # Verify statistics
    stats = collector.get_statistics()
    assert stats['total_snapshots'] == 1
    assert stats['unique_markets'] == 1
    assert stats['labeled_snapshots'] == 0
    assert stats['trades_blocked'] == 1


def test_duplicate_snapshot(collector):
    """Test that multiple snapshots of same market at different times are allowed."""
    snapshot_data = {
        'market_id': '0x123abc',
        'bot_type': 'price_level',
        'features': {'volatility_30d': 0.45},
        'prediction': {'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
        'market_data': {'question': 'Test', 'days_to_expiry': 30},
        'prices': {'yes': 0.50, 'no': 0.50}
    }

    id1 = collector.log_snapshot(**snapshot_data)
    id2 = collector.log_snapshot(**snapshot_data)  # Different timestamp

    assert id1 > 0
    assert id2 > 0  # Allowed - different timestamps
    assert id1 != id2

    stats = collector.get_statistics()
    assert stats['total_snapshots'] == 2  # Both recorded
    assert stats['unique_markets'] == 1  # Same market


def test_record_outcome(collector):
    """Test recording market outcome."""
    # Log snapshot
    snapshot_id = collector.log_snapshot(
        market_id='0x123abc',
        bot_type='price_level',
        features={'volatility_30d': 0.45},
        prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
        market_data={'question': 'Test', 'days_to_expiry': 30},
        prices={'yes': 0.50, 'no': 0.50}
    )

    # Record outcome
    collector.record_outcome(
        snapshot_id=snapshot_id,
        outcome='YES',
        resolution_price=1.0
    )

    # Verify labeled
    stats = collector.get_statistics()
    assert stats['labeled_snapshots'] == 1
    assert stats['unlabeled_snapshots'] == 0


def test_record_outcome_by_market_id(collector):
    """Test recording outcome using market_id instead of snapshot_id."""
    # Log multiple snapshots for same market
    for i in range(3):
        collector.log_snapshot(
            market_id='0x123abc',
            bot_type='price_level',
            features={'volatility_30d': 0.45 + i * 0.01},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': 'Test', 'days_to_expiry': 30},
            prices={'yes': 0.50 + i * 0.01, 'no': 0.50}
        )

    # Record outcome for all snapshots of this market
    collector.record_outcome(
        market_id='0x123abc',
        bot_type='price_level',
        outcome='NO',
        resolution_price=0.0
    )

    # All 3 should be labeled
    stats = collector.get_statistics()
    assert stats['labeled_snapshots'] == 3


def test_price_evolution(collector):
    """Test logging price evolution."""
    snapshot_id = collector.log_snapshot(
        market_id='0x123abc',
        bot_type='price_level',
        features={'volatility_30d': 0.45},
        prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
        market_data={'question': 'Test', 'days_to_expiry': 30},
        prices={'yes': 0.50, 'no': 0.50}
    )

    # Log price changes
    collector.log_price_evolution(snapshot_id, yes_price=0.55, no_price=0.48)
    collector.log_price_evolution(snapshot_id, yes_price=0.60, no_price=0.45)

    # Should not raise errors (no direct way to verify count without raw SQL)
    assert True


def test_get_training_data(collector):
    """Test fetching training data as DataFrame."""
    # Log some labeled snapshots
    for i in range(5):
        snapshot_id = collector.log_snapshot(
            market_id=f'0x{i:03d}',
            bot_type='price_level',
            features={'volatility_30d': 0.40 + i * 0.05, 'rsi_14': 50 + i * 5},
            prediction={'model_prob': 0.6 + i * 0.05, 'confidence': 0.7, 'edge': 0.1, 'predicted_outcome': 'YES'},
            market_data={'question': f'Test {i}', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )
        if i < 3:  # Label first 3
            collector.record_outcome(snapshot_id, outcome='YES', resolution_price=1.0)

    # Get labeled data
    df_labeled = collector.get_training_data(labeled_only=True)
    assert len(df_labeled) == 3
    assert 'volatility_30d' in df_labeled.columns  # Features should be expanded
    assert 'outcome' in df_labeled.columns

    # Get all data
    df_all = collector.get_training_data(labeled_only=False)
    assert len(df_all) == 5


def test_get_unlabeled_snapshots(collector):
    """Test fetching unlabeled snapshots."""
    # Log some snapshots
    for i in range(3):
        collector.log_snapshot(
            market_id=f'0x{i:03d}',
            bot_type='price_level',
            features={'volatility_30d': 0.45},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': f'Test {i}', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )

    unlabeled = collector.get_unlabeled_snapshots()
    assert len(unlabeled) == 3
    assert all('market_id' in s for s in unlabeled)


def test_multiple_bot_types(collector):
    """Test handling multiple bot types."""
    # Log snapshots from different bots
    for bot_type in ['event', 'price_level', 'short_expiry']:
        collector.log_snapshot(
            market_id=f'0x_{bot_type}',
            bot_type=bot_type,
            features={'volatility_30d': 0.45},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': f'{bot_type} test', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )

    stats = collector.get_statistics()
    assert len(stats['by_bot_type']) == 3
    assert stats['by_bot_type']['event']['total'] == 1
    assert stats['by_bot_type']['price_level']['total'] == 1
    assert stats['by_bot_type']['short_expiry']['total'] == 1

    # Filter by bot type
    df_price_level = collector.get_training_data(bot_type='price_level', labeled_only=False)
    assert len(df_price_level) == 1


def test_position_tracking(collector):
    """Test tracking whether positions were opened."""
    # Snapshot with trade executed
    collector.log_snapshot(
        market_id='0x123',
        bot_type='price_level',
        features={'volatility_30d': 0.45},
        prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
        market_data={'question': 'Trade executed', 'days_to_expiry': 30},
        prices={'yes': 0.50, 'no': 0.50},
        position_opened=True,
        position_id=1001
    )

    # Snapshot with trade blocked
    collector.log_snapshot(
        market_id='0x456',
        bot_type='price_level',
        features={'volatility_30d': 0.45},
        prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
        market_data={'question': 'Trade blocked', 'days_to_expiry': 30},
        prices={'yes': 0.50, 'no': 0.50},
        position_opened=False,
        rejection_reason='exposure_limit'
    )

    stats = collector.get_statistics()
    assert stats['trades_executed'] == 1
    assert stats['trades_blocked'] == 1


def test_statistics_empty_db(collector):
    """Test statistics on empty database."""
    stats = collector.get_statistics()
    assert stats['total_snapshots'] == 0
    assert stats['unique_markets'] == 0
    assert stats['labeling_rate'] == 0
    assert stats['by_bot_type'] == {}


def test_print_statistics(collector, capsys):
    """Test statistics printing."""
    # Add some data
    collector.log_snapshot(
        market_id='0x123',
        bot_type='price_level',
        features={'volatility_30d': 0.45},
        prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
        market_data={'question': 'Test', 'days_to_expiry': 30},
        prices={'yes': 0.50, 'no': 0.50}
    )

    collector.print_statistics()
    captured = capsys.readouterr()
    assert 'MARKET SNAPSHOT COLLECTOR' in captured.out
    assert 'Total Snapshots:' in captured.out


def test_milestone_persistence_across_instances(temp_db):
    """Test that milestone alerts persist across collector instances (no duplicates)."""
    from unittest.mock import Mock

    # Mock telegram to track sent messages
    telegram1 = Mock()

    # Create collector with low milestone thresholds
    collector1 = MarketSnapshotCollector(
        db_path=temp_db,
        telegram=telegram1,
        alert_milestones=[5, 10]
    )

    # Log 5 snapshots to hit first milestone
    for i in range(5):
        collector1.log_snapshot(
            market_id=f'0x{i:03d}',
            bot_type='price_level',
            features={'volatility_30d': 0.45},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': f'Test {i}', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )

    # Should have sent milestone alert for 5
    assert telegram1.send_message.call_count == 1
    assert 'Milestone 5' in telegram1.send_message.call_args[0][0]

    # Create NEW collector instance (simulates restart)
    telegram2 = Mock()
    collector2 = MarketSnapshotCollector(
        db_path=temp_db,
        telegram=telegram2,
        alert_milestones=[5, 10]
    )

    # Log 5 more snapshots (total now 10, hitting second milestone)
    for i in range(5, 10):
        collector2.log_snapshot(
            market_id=f'0x{i:03d}',
            bot_type='price_level',
            features={'volatility_30d': 0.45},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': f'Test {i}', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )

    # Should have sent ONLY milestone 10 alert (not milestone 5 again)
    assert telegram2.send_message.call_count == 1
    assert 'Milestone 10' in telegram2.send_message.call_args[0][0]

    # Verify milestone 5 was NOT sent again
    messages = [call[0][0] for call in telegram2.send_message.call_args_list]
    assert not any('Milestone 5' in msg for msg in messages)


def test_milestone_shared_across_bot_instances(temp_db):
    """Test that multiple bot instances share milestone state (no duplicate alerts)."""
    from unittest.mock import Mock

    telegram1 = Mock()
    telegram2 = Mock()

    # Create two collector instances (simulates two bots running concurrently)
    collector1 = MarketSnapshotCollector(
        db_path=temp_db,
        telegram=telegram1,
        alert_milestones=[3]
    )
    collector2 = MarketSnapshotCollector(
        db_path=temp_db,
        telegram=telegram2,
        alert_milestones=[3]
    )

    # Collector 1 logs 3 snapshots (hits milestone)
    for i in range(3):
        collector1.log_snapshot(
            market_id=f'0x{i:03d}',
            bot_type='event',
            features={'volatility_30d': 0.45},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': f'Test {i}', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )

    # First collector should send alert
    assert telegram1.send_message.call_count == 1

    # Collector 2 logs more snapshots (total now > 3)
    for i in range(3, 5):
        collector2.log_snapshot(
            market_id=f'0x{i:03d}',
            bot_type='price_level',
            features={'volatility_30d': 0.45},
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15, 'predicted_outcome': 'YES'},
            market_data={'question': f'Test {i}', 'days_to_expiry': 30},
            prices={'yes': 0.50, 'no': 0.50}
        )

    # Second collector should NOT send milestone 3 alert (already sent by collector 1)
    # It loads the milestone state from database on init
    assert telegram2.send_message.call_count == 0
