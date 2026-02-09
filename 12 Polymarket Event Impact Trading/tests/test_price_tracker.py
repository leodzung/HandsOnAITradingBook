"""
Tests for PriceTracker
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock
from price_tracker import PriceTracker


class TestPriceTracker:
    """Test suite for PriceTracker."""

    def test_initialization(self, temp_db):
        """Test price tracker initialization."""
        tracker = PriceTracker(db_path=temp_db)

        assert tracker.db_path == temp_db
        # Verify database table exists
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tracked_events'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_track_event(self, temp_db, sample_event, sample_market, sample_features):
        """Test starting to track an event."""
        tracker = PriceTracker(db_path=temp_db)

        tracking_id = tracker.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.35,
            features=sample_features
        )

        assert tracking_id is not None
        assert sample_market['conditionId'] in tracking_id

    def test_check_outcomes_updates_prices(self, temp_db, sample_event, sample_market, sample_features):
        """Test that check_outcomes updates prices at intervals."""
        tracker = PriceTracker(db_path=temp_db)

        # Track an event
        tracker.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.35,
            features=sample_features
        )

        # Mock the entry time to be 2 hours ago
        import sqlite3
        conn = sqlite3.connect(temp_db)
        entry_time_2h_ago = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        conn.execute(
            "UPDATE tracked_events SET entry_time = ?",
            (entry_time_2h_ago,)
        )
        conn.commit()
        conn.close()

        # Mock client responses
        with patch.object(tracker.client, 'get_market') as mock_get_market:
            mock_get_market.return_value = {
                **sample_market,
                'outcomePrices': '[0.40, 0.60]'
            }

            updated = tracker.check_outcomes(max_age_hours=24)

            # Should have updated 1h price
            assert updated >= 1

    def test_label_outcome_up(self, temp_db):
        """Test outcome labeling for upward movement."""
        tracker = PriceTracker(db_path=temp_db)

        outcome = tracker._label_outcome(entry_price=0.30, exit_price=0.35)
        assert outcome == 1  # UP (>3% increase)

    def test_label_outcome_down(self, temp_db):
        """Test outcome labeling for downward movement."""
        tracker = PriceTracker(db_path=temp_db)

        outcome = tracker._label_outcome(entry_price=0.35, exit_price=0.30)
        assert outcome == -1  # DOWN (>3% decrease)

    def test_label_outcome_neutral(self, temp_db):
        """Test outcome labeling for neutral movement."""
        tracker = PriceTracker(db_path=temp_db)

        outcome = tracker._label_outcome(entry_price=0.35, exit_price=0.36)
        assert outcome == 0  # NEUTRAL (<3% change)

    def test_get_statistics(self, temp_db, sample_event, sample_market, sample_features):
        """Test getting tracking statistics."""
        tracker = PriceTracker(db_path=temp_db)

        # Track some events
        for i in range(3):
            tracker.track_event(
                event=sample_event,
                market={**sample_market, 'conditionId': f'0xmarket{i}'},
                entry_price=0.35,
                features=sample_features
            )

        stats = tracker.get_statistics()

        assert stats['total_tracked'] == 3
        assert stats['completed'] == 0
        assert stats['pending'] == 3

    def test_export_to_csv(self, temp_db, sample_event, sample_market, sample_features):
        """Test exporting labeled data to CSV."""
        import tempfile
        tracker = PriceTracker(db_path=temp_db)

        # Track and complete an event
        tracking_id = tracker.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.35,
            features=sample_features
        )

        # Manually mark as completed with label
        import sqlite3
        conn = sqlite3.connect(temp_db)
        conn.execute('''
            UPDATE tracked_events
            SET completed = 1, actual_outcome = 1, price_24h = 0.40
            WHERE tracking_id = ?
        ''', (tracking_id,))
        conn.commit()
        conn.close()

        # Export
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
            csv_path = f.name

        count = tracker.export_to_csv(output_path=csv_path)

        assert count == 1
        # Verify CSV exists and has data
        import pandas as pd
        df = pd.read_csv(csv_path)
        assert len(df) == 1
        assert 'actual_outcome' in df.columns

    def test_duplicate_tracking_prevention(self, temp_db, sample_event, sample_market, sample_features):
        """Test that duplicate event-market pairs are handled correctly."""
        tracker = PriceTracker(db_path=temp_db)

        # Track same event-market twice
        tracking_id1 = tracker.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.35,
            features=sample_features
        )

        tracking_id2 = tracker.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.40,  # Different price
            features=sample_features
        )

        # Should be same tracking_id, entry replaced
        assert tracking_id1 == tracking_id2

        # Verify only one entry exists
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute('SELECT COUNT(*) FROM tracked_events')
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

    def test_feature_extraction_from_tracking(self, temp_db, sample_event, sample_market):
        """Test that features are correctly extracted and stored."""
        tracker = PriceTracker(db_path=temp_db)

        features = {
            'event_sentiment_score': 0.6,
            'event_sentiment_magnitude': 0.3,
            'event_source_credibility': 1.0,
            'event_title_length': 50,
            'event_description_length': 100,
            'event_keyword_count': 5,
            'market_volume': 25000.0
        }

        tracker.track_event(
            event=sample_event,
            market=sample_market,
            entry_price=0.35,
            features=features
        )

        # Verify features stored correctly
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute('''
            SELECT sentiment_score, market_volume, keyword_overlap
            FROM tracked_events
        ''')
        row = cursor.fetchone()
        conn.close()

        assert row[0] == 0.6  # sentiment_score
        assert row[1] == 25000.0  # market_volume
        assert row[2] == 5  # keyword_overlap
