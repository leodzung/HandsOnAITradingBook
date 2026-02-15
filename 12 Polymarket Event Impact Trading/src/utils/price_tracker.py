#!/usr/bin/env python3
"""
Price Tracker - Track actual price movements after events
Collects real labels for retraining the ML model
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging
from pathlib import Path
import numpy as np
import pandas as pd

from core.polymarket_client import PolymarketClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PriceTracker:
    """Tracks price movements after events for ML model training."""

    def __init__(self, db_path: str = 'data/price_tracking.db'):
        """
        Initialize price tracker.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.client = PolymarketClient()
        self._init_database()

    def _get_connection(self):
        """Get SQLite connection with WAL mode and timeout for better concurrency."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_database(self):
        """Create database tables if they don't exist."""
        # Ensure data directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Table: tracked_events
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracked_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_id TEXT UNIQUE NOT NULL,
                event_title TEXT NOT NULL,
                event_description TEXT,
                event_source TEXT,
                event_time TIMESTAMP NOT NULL,
                market_id TEXT NOT NULL,
                market_question TEXT NOT NULL,
                token_id TEXT,

                -- Features (same as model input)
                sentiment_score REAL,
                sentiment_magnitude REAL,
                source_credibility REAL,
                title_length INTEGER,
                has_description INTEGER,
                keyword_overlap INTEGER,
                market_volume REAL,
                market_volume_log REAL,

                -- Prices
                entry_price REAL NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                price_1h REAL,
                price_6h REAL,
                price_24h REAL,

                -- Outcome label
                actual_outcome INTEGER,  -- 1=UP, 0=NEUTRAL, -1=DOWN

                -- Tracking status
                completed INTEGER DEFAULT 0,
                last_checked TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Index for efficient queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_completed
            ON tracked_events(completed)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_market_id
            ON tracked_events(market_id)
        ''')

        # Table: price_snapshots (for short-expiry momentum features)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Index for efficient time-based queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_price_market_time
            ON price_snapshots(market_id, timestamp)
        ''')

        conn.commit()
        conn.close()

        logger.info(f"Database initialized at {self.db_path}")

    def track_event(self,
                    event,
                    market: Dict,
                    entry_price: float,
                    features: Dict) -> str:
        """
        Start tracking an event-market pair.

        Args:
            event: Event object
            market: Market dictionary
            entry_price: Current market price
            features: Extracted features dictionary

        Returns:
            tracking_id: Unique ID for this tracking entry
        """
        tracking_id = f"{market.get('conditionId')}_{event.id}"

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get token_id for price checking (from clobTokenIds)
            # Note: clobTokenIds is a JSON string
            token_ids_str = market.get('clobTokenIds', '[]')
            token_ids = json.loads(token_ids_str) if isinstance(token_ids_str, str) else token_ids_str
            token_id = token_ids[0] if token_ids else ''

            # Extract features with correct keys (feature_extractor uses 'event_' prefix)
            sentiment_score = features.get('event_sentiment_score', features.get('sentiment_score'))
            sentiment_magnitude = features.get('event_sentiment_magnitude', features.get('sentiment_magnitude'))
            source_credibility = features.get('event_source_credibility', features.get('source_credibility'))
            title_length = features.get('event_title_length', features.get('title_length'))
            description_length = features.get('event_description_length', 0)
            has_description = 1 if description_length and description_length > 0 else 0
            keyword_overlap = features.get('event_keyword_count', features.get('keyword_overlap'))
            market_volume = features.get('market_volume', 0)
            market_volume_log = np.log1p(market_volume) if market_volume else 0

            cursor.execute('''
                INSERT OR REPLACE INTO tracked_events (
                    tracking_id, event_title, event_description, event_source,
                    event_time, market_id, market_question, token_id,
                    sentiment_score, sentiment_magnitude, source_credibility,
                    title_length, has_description, keyword_overlap,
                    market_volume, market_volume_log,
                    entry_price, entry_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                tracking_id,
                event.title,
                event.description,
                event.source,
                event.published_time.isoformat(),
                market.get('conditionId'),
                market.get('question'),
                token_id,
                sentiment_score,
                sentiment_magnitude,
                source_credibility,
                title_length,
                has_description,
                keyword_overlap,
                market_volume,
                market_volume_log,
                entry_price,
                datetime.now(timezone.utc).isoformat()
            ))

            conn.commit()
            logger.info(f"Started tracking: {tracking_id}")
            logger.info(f"  Event: {event.title[:60]}")
            logger.info(f"  Market: {market.get('question')[:60]}")
            logger.info(f"  Entry price: ${entry_price:.3f}")

        except sqlite3.IntegrityError:
            logger.warning(f"Already tracking: {tracking_id}")
        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            conn.rollback()
        finally:
            conn.close()

        return tracking_id

    def check_outcomes(self, max_age_hours: int = 168) -> int:
        """
        Check prices for pending tracking entries.

        Args:
            max_age_hours: Max age of entries to check (default: 7 days)

        Returns:
            Number of entries updated
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get pending entries
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        cursor.execute('''
            SELECT id, tracking_id, token_id, market_id, entry_price, entry_time,
                   price_1h, price_6h, price_24h
            FROM tracked_events
            WHERE completed = 0
              AND entry_time > ?
            ORDER BY entry_time ASC
        ''', (cutoff_time.isoformat(),))

        entries = cursor.fetchall()
        updated_count = 0

        logger.info(f"Checking {len(entries)} pending tracking entries...")

        for entry in entries:
            (entry_id, tracking_id, token_id, market_id, entry_price, entry_time_str,
             price_1h, price_6h, price_24h) = entry

            if not token_id:
                logger.warning(f"No token_id for {tracking_id}, skipping")
                continue

            # Parse entry time
            entry_time = datetime.fromisoformat(entry_time_str)
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)

            time_elapsed = (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600

            # Get current price - try multiple sources
            try:
                current_price = None

                # Method 1: Try to get market data and use outcomePrices (most reliable)
                if market_id:
                    try:
                        market = self.client.get_market(market_id)
                        if market:
                            current_price = self.client.get_price_from_market(market, outcome_index=0)
                    except Exception:
                        pass

                # Method 2: Fall back to Gamma API using market_id (consistent with entry)
                # NOTE: Do NOT use CLOB orderbook as fallback - token order may not match!
                if current_price is None:
                    current_price = self.client.get_market_yes_price(market_id)

                if current_price is None:
                    logger.warning(f"Could not fetch price for {tracking_id} (Gamma API unavailable)")
                    continue

                updated = False

                # Check 1 hour
                if time_elapsed >= 1 and price_1h is None:
                    cursor.execute('''
                        UPDATE tracked_events
                        SET price_1h = ?, last_checked = ?
                        WHERE id = ?
                    ''', (current_price, datetime.now(timezone.utc).isoformat(), entry_id))
                    logger.info(f"  {tracking_id}: 1h price = ${current_price:.3f}")
                    updated = True

                # Check 6 hours
                if time_elapsed >= 6 and price_6h is None:
                    cursor.execute('''
                        UPDATE tracked_events
                        SET price_6h = ?, last_checked = ?
                        WHERE id = ?
                    ''', (current_price, datetime.now(timezone.utc).isoformat(), entry_id))
                    logger.info(f"  {tracking_id}: 6h price = ${current_price:.3f}")
                    updated = True

                # Check 24 hours - FINAL
                if time_elapsed >= 24 and price_24h is None:
                    # Calculate actual outcome
                    actual_outcome = self._label_outcome(entry_price, current_price)

                    cursor.execute('''
                        UPDATE tracked_events
                        SET price_24h = ?,
                            actual_outcome = ?,
                            completed = 1,
                            last_checked = ?
                        WHERE id = ?
                    ''', (current_price, actual_outcome,
                          datetime.now(timezone.utc).isoformat(), entry_id))

                    outcome_label = {1: 'UP ↗', 0: 'NEUTRAL →', -1: 'DOWN ↘'}
                    change_pct = ((current_price - entry_price) / entry_price) * 100
                    logger.info(f"  {tracking_id}: COMPLETED")
                    logger.info(f"    Entry: ${entry_price:.3f} → Exit: ${current_price:.3f}")
                    logger.info(f"    Change: {change_pct:+.1f}%")
                    logger.info(f"    Label: {outcome_label[actual_outcome]}")
                    updated = True

                if updated:
                    updated_count += 1

            except Exception as e:
                logger.error(f"Error checking {tracking_id}: {e}")
                continue

        conn.commit()
        conn.close()

        logger.info(f"Updated {updated_count} tracking entries")
        return updated_count

    def _label_outcome(self, entry_price: float, exit_price: float) -> int:
        """
        Label outcome based on price movement.

        Args:
            entry_price: Starting price
            exit_price: Ending price

        Returns:
            1 (UP), 0 (NEUTRAL), or -1 (DOWN)
        """
        # Calculate percentage change
        change = (exit_price - entry_price) / entry_price

        # Use 3% threshold (adjust as needed)
        if change > 0.03:  # +3% or more
            return 1  # UP
        elif change < -0.03:  # -3% or more
            return -1  # DOWN
        else:
            return 0  # NEUTRAL

    def track_price(self, market_id: str, price: float):
        """
        Track a price snapshot for momentum feature calculation.

        Used by short-expiry bot to build price history for velocity/acceleration features.

        Args:
            market_id: Market condition ID
            price: Current market price (0.0 - 1.0)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO price_snapshots (market_id, price, timestamp)
                VALUES (?, ?, ?)
            ''', (market_id, price, datetime.now(timezone.utc).isoformat()))

            conn.commit()
        except Exception as e:
            logger.error(f"Error tracking price for {market_id}: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_price_history(self, market_id: str, hours: int = 24) -> Optional[pd.DataFrame]:
        """
        Retrieve price history for a market.

        Returns snapshots from the last N hours for momentum calculations.

        Args:
            market_id: Market condition ID
            hours: Hours of history to retrieve (default: 24)

        Returns:
            DataFrame with columns ['price', 'timestamp'] or None if no data
        """
        import pandas as pd

        conn = self._get_connection()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            df = pd.read_sql_query('''
                SELECT price, timestamp
                FROM price_snapshots
                WHERE market_id = ? AND timestamp > ?
                ORDER BY timestamp ASC
            ''', conn, params=(market_id, cutoff.isoformat()))

            conn.close()

            if df.empty:
                return None

            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            return df

        except Exception as e:
            logger.error(f"Error getting price history for {market_id}: {e}")
            conn.close()
            return None

    def cleanup_old_snapshots(self, days: int = 7) -> int:
        """
        Clean up old price snapshots to prevent database bloat.

        Args:
            days: Delete snapshots older than this many days (default: 7)

        Returns:
            Number of snapshots deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            cursor.execute('''
                DELETE FROM price_snapshots
                WHERE timestamp < ?
            ''', (cutoff.isoformat(),))

            deleted = cursor.rowcount
            conn.commit()

            logger.info(f"Cleaned up {deleted} old price snapshots (older than {days} days)")
            return deleted

        except Exception as e:
            logger.error(f"Error cleaning up snapshots: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def get_statistics(self) -> Dict:
        """Get tracking statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total entries
        cursor.execute('SELECT COUNT(*) FROM tracked_events')
        total = cursor.fetchone()[0]

        # Completed entries
        cursor.execute('SELECT COUNT(*) FROM tracked_events WHERE completed = 1')
        completed = cursor.fetchone()[0]

        # Pending entries
        pending = total - completed

        # Label distribution (completed only)
        cursor.execute('''
            SELECT actual_outcome, COUNT(*)
            FROM tracked_events
            WHERE completed = 1
            GROUP BY actual_outcome
        ''')
        label_dist = dict(cursor.fetchall())

        # Average time to complete
        cursor.execute('''
            SELECT AVG(
                (julianday(last_checked) - julianday(entry_time)) * 24
            )
            FROM tracked_events
            WHERE completed = 1
        ''')
        avg_hours = cursor.fetchone()[0] or 0

        conn.close()

        return {
            'total_tracked': total,
            'completed': completed,
            'pending': pending,
            'labels': {
                'UP': label_dist.get(1, 0),
                'NEUTRAL': label_dist.get(0, 0),
                'DOWN': label_dist.get(-1, 0)
            },
            'avg_completion_hours': avg_hours
        }

    def export_to_csv(self, output_path: str = 'data/labeled_dataset.csv') -> int:
        """
        Export completed tracking data to CSV for model training.

        Args:
            output_path: Path to output CSV file

        Returns:
            Number of samples exported
        """
        import pandas as pd

        conn = self._get_connection()

        # Query completed entries
        query = '''
            SELECT
                event_title,
                event_source,
                market_question,
                sentiment_score,
                sentiment_magnitude,
                source_credibility,
                title_length,
                has_description,
                keyword_overlap,
                market_volume,
                market_volume_log,
                entry_price,
                price_1h,
                price_6h,
                price_24h,
                actual_outcome,
                entry_time,
                event_time
            FROM tracked_events
            WHERE completed = 1
              AND actual_outcome IS NOT NULL
            ORDER BY entry_time DESC
        '''

        df = pd.read_sql_query(query, conn)
        conn.close()

        if len(df) == 0:
            logger.warning("No completed entries to export")
            return 0

        # Calculate additional metrics
        df['price_change_1h'] = ((df['price_1h'] - df['entry_price']) / df['entry_price']) * 100
        df['price_change_6h'] = ((df['price_6h'] - df['entry_price']) / df['entry_price']) * 100
        df['price_change_24h'] = ((df['price_24h'] - df['entry_price']) / df['entry_price']) * 100

        # Save to CSV
        df.to_csv(output_path, index=False)

        logger.info(f"Exported {len(df)} labeled samples to {output_path}")

        # Print summary
        logger.info("\nLabel distribution:")
        logger.info(f"  UP (+1):     {len(df[df['actual_outcome'] == 1])}")
        logger.info(f"  NEUTRAL (0): {len(df[df['actual_outcome'] == 0])}")
        logger.info(f"  DOWN (-1):   {len(df[df['actual_outcome'] == -1])}")

        return len(df)


def main():
    """Main function for testing."""
    print("=" * 70)
    print("PRICE TRACKER - Status Check")
    print("=" * 70)
    print()

    tracker = PriceTracker()

    # Get statistics
    stats = tracker.get_statistics()

    print("📊 Tracking Statistics:")
    print(f"  Total tracked:    {stats['total_tracked']}")
    print(f"  Completed:        {stats['completed']}")
    print(f"  Pending:          {stats['pending']}")
    print()

    if stats['completed'] > 0:
        print("📋 Label Distribution:")
        print(f"  UP (+1):     {stats['labels']['UP']}")
        print(f"  NEUTRAL (0): {stats['labels']['NEUTRAL']}")
        print(f"  DOWN (-1):   {stats['labels']['DOWN']}")
        print()
        print(f"  Avg completion time: {stats['avg_completion_hours']:.1f} hours")
        print()

        # Export if enough samples
        if stats['completed'] >= 10:
            print("💾 Exporting to CSV...")
            count = tracker.export_to_csv()
            print(f"  Exported {count} samples to data/labeled_dataset.csv")
            print()

    if stats['pending'] > 0:
        print(f"⏱️  Checking {stats['pending']} pending outcomes...")
        updated = tracker.check_outcomes()
        print(f"  Updated {updated} entries")
        print()

    print("=" * 70)


if __name__ == '__main__':
    main()
