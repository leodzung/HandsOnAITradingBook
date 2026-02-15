#!/usr/bin/env python3
"""
Centralized Market Snapshot Collector
Unified training data collection for all trading bots.

Collects market snapshots (features + predictions + outcomes) to build
ML training datasets regardless of whether trades are executed.

Created: 2026-02-15
"""

import sqlite3
import logging
import json
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

# Optional Telegram support
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from monitoring.telegram_notifier import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None

logger = logging.getLogger(__name__)


class MarketSnapshotCollector:
    """
    Centralized service for collecting market snapshots across all bots.

    Features:
    - Logs market features, predictions, and metadata
    - Tracks price evolution over time
    - Records outcomes when markets resolve
    - Provides data for ML model training/retraining
    - Works across all bot types (event, price_level, short_expiry)

    Usage:
        collector = MarketSnapshotCollector(db_path='data/market_snapshots.db')

        # Log a market snapshot
        collector.log_snapshot(
            market_id='0x123...',
            bot_type='price_level',
            features=feature_dict,
            prediction={'model_prob': 0.65, 'confidence': 0.75, 'edge': 0.15},
            market_data={'question': '...', 'expiry': '...'},
            prices={'yes': 0.50, 'no': 0.50}
        )

        # Record outcome when market resolves
        collector.record_outcome(
            snapshot_id=123,
            outcome='YES',
            resolution_price=0.95
        )

        # Fetch training data
        df = collector.get_training_data(bot_type='price_level', labeled_only=True)
    """

    def __init__(self, db_path: str = 'data/market_snapshots.db',
                 telegram: Optional[Any] = None,
                 alert_milestones: List[int] = None):
        """
        Initialize snapshot collector.

        Args:
            db_path: Path to SQLite database
            telegram: Optional TelegramNotifier for alerts
            alert_milestones: Snapshot counts to send alerts at (default: [100, 500, 1000, 5000, 10000])
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.telegram = telegram
        self.alert_milestones = alert_milestones or [100, 500, 1000, 5000, 10000]
        self._alerted_milestones = set()  # Track which milestones we've alerted on
        self._last_labeled_count = 0  # Track labeled samples for incremental alerts

        self._init_database()
        logger.info(f"MarketSnapshotCollector initialized: {self.db_path}")

        if self.telegram:
            logger.info("✓ Telegram alerts enabled for snapshot collector")

    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Market identification
                market_id TEXT NOT NULL,
                condition_id TEXT,
                token_id TEXT,
                question TEXT,

                -- Bot context
                bot_type TEXT NOT NULL,  -- 'event', 'price_level', 'short_expiry'
                snapshot_time TIMESTAMP NOT NULL,

                -- Market metadata
                asset TEXT,  -- BTC, ETH, GOLD, etc.
                strike_price REAL,  -- For price-level markets
                expiry_date TIMESTAMP,
                days_to_expiry REAL,
                market_type TEXT,  -- 'threshold', 'race', 'binary'

                -- Features (JSON serialized)
                features_json TEXT NOT NULL,

                -- Model prediction
                model_prob REAL,  -- Model's probability estimate (0-1)
                confidence REAL,  -- Model confidence
                edge REAL,  -- Calculated edge
                predicted_outcome TEXT,  -- 'YES' or 'NO'

                -- Prices at snapshot time
                yes_price REAL,
                no_price REAL,
                spread REAL,

                -- Market metrics
                volume_24h REAL,
                liquidity REAL,

                -- Trade execution (if applicable)
                position_opened INTEGER DEFAULT 0,  -- 0=no trade, 1=trade executed
                position_id INTEGER,  -- Link to positions table
                rejection_reason TEXT,  -- Why trade wasn't executed

                -- Outcome (filled when market resolves)
                outcome TEXT,  -- 'YES', 'NO', 'INVALID', 'EXPIRED'
                resolution_price REAL,
                resolution_time TIMESTAMP,
                labeled INTEGER DEFAULT 0,  -- 1 when outcome is known

                -- Indexes for fast queries
                UNIQUE(market_id, bot_type, snapshot_time)
            )
        """)

        # Price evolution table (track price changes over time)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_evolution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                check_time TIMESTAMP NOT NULL,
                yes_price REAL,
                no_price REAL,
                hours_since_snapshot REAL,

                FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(id)
            )
        """)

        # Create indexes for fast lookups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_market_id
            ON market_snapshots(market_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_type
            ON market_snapshots(bot_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_labeled
            ON market_snapshots(labeled)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_snapshot_time
            ON market_snapshots(snapshot_time)
        """)

        conn.commit()
        conn.close()
        logger.info("Database schema initialized")

    def _send_telegram(self, message: str):
        """Send Telegram notification if configured."""
        if self.telegram:
            try:
                self.telegram.send_message(message)
            except Exception as e:
                logger.warning(f"Failed to send Telegram alert: {e}")

    def _check_and_alert_milestones(self):
        """Check if we've hit any milestones and send alerts."""
        if not self.telegram:
            return

        stats = self.get_statistics()
        total = stats['total_snapshots']
        labeled = stats['labeled_snapshots']

        # Check snapshot milestones
        for milestone in self.alert_milestones:
            if total >= milestone and milestone not in self._alerted_milestones:
                self._alerted_milestones.add(milestone)
                self._notify_milestone_reached(milestone, stats)

        # Check labeled data milestones (every 50 samples)
        labeled_milestone = (labeled // 50) * 50
        if labeled_milestone > self._last_labeled_count and labeled >= 50:
            self._last_labeled_count = labeled_milestone
            self._notify_labeling_progress(labeled, stats)

        # Check training readiness (200+ labeled samples)
        if labeled >= 200 and 200 not in self._alerted_milestones:
            self._alerted_milestones.add(200)  # Use 200 as special marker
            self._notify_training_ready(labeled, stats)

    def _notify_milestone_reached(self, milestone: int, stats: Dict):
        """Send alert when snapshot milestone is reached."""
        message = (
            f"<b>📊 DATA COLLECTION MILESTONE</b>\n\n"
            f"<b>Total Snapshots:</b> {stats['total_snapshots']:,}\n"
            f"<b>Unique Markets:</b> {stats['unique_markets']:,}\n"
            f"<b>Labeled:</b> {stats['labeled_snapshots']:,} ({stats['labeling_rate']:.1f}%)\n"
            f"<b>Trades Blocked:</b> {stats['trades_blocked']:,}\n\n"
        )

        # Add bot breakdown if available
        if stats['by_bot_type']:
            message += "<b>By Bot:</b>\n"
            for bot_type, counts in stats['by_bot_type'].items():
                message += f"  • {bot_type}: {counts['total']:,} snapshots\n"

        message += f"\n<b>Status:</b> Milestone {milestone:,} reached! 🎉"

        self._send_telegram(message)
        logger.info(f"Sent milestone alert: {milestone} snapshots")

    def _notify_labeling_progress(self, labeled_count: int, stats: Dict):
        """Send alert for labeling progress."""
        unlabeled = stats['unlabeled_snapshots']
        total = stats['total_snapshots']

        message = (
            f"<b>🏷️ LABELING PROGRESS UPDATE</b>\n\n"
            f"<b>Labeled Samples:</b> {labeled_count:,}\n"
            f"<b>Unlabeled:</b> {unlabeled:,}\n"
            f"<b>Total:</b> {total:,}\n"
            f"<b>Progress:</b> {stats['labeling_rate']:.1f}%\n\n"
        )

        # Estimate to training readiness
        if labeled_count < 200:
            needed = 200 - labeled_count
            message += f"<b>Need {needed} more for training readiness</b>\n"
        else:
            message += f"<b>Status:</b> Ready for model retraining ✅\n"

        self._send_telegram(message)
        logger.info(f"Sent labeling progress alert: {labeled_count} labeled")

    def _notify_training_ready(self, labeled_count: int, stats: Dict):
        """Send alert when enough data is available for training."""
        message = (
            f"<b>🚀 TRAINING DATASET READY</b>\n\n"
            f"<b>Labeled Samples:</b> {labeled_count:,}\n"
            f"<b>Unique Markets:</b> {stats['unique_markets']:,}\n"
            f"<b>Labeling Rate:</b> {stats['labeling_rate']:.1f}%\n\n"
        )

        # Add bot breakdown
        if stats['by_bot_type']:
            message += "<b>By Bot:</b>\n"
            for bot_type, counts in stats['by_bot_type'].items():
                if counts['labeled'] > 0:
                    message += f"  • {bot_type}: {counts['labeled']:,} labeled\n"

        message += (
            f"\n<b>Next Steps:</b>\n"
            f"1. Export: python3 view_snapshots.py --export training.csv --labeled-only\n"
            f"2. Train new model with real-world data\n"
            f"3. Deploy improved model\n\n"
            f"<b>Status:</b> Minimum viable training dataset achieved! 🎓"
        )

        self._send_telegram(message)
        logger.info(f"Sent training readiness alert: {labeled_count} labeled samples")

    def _notify_outcome_recorded(self, market_id: str, outcome: str, snapshots_labeled: int):
        """Send alert when outcome is recorded for a market."""
        if not self.telegram:
            return

        # Only send individual outcome alerts for first 10 resolutions
        # After that, rely on milestone alerts
        stats = self.get_statistics()
        if stats['labeled_snapshots'] <= 10:
            message = (
                f"<b>🏁 MARKET RESOLVED</b>\n\n"
                f"<b>Market ID:</b> {market_id[:16]}...\n"
                f"<b>Outcome:</b> {outcome}\n"
                f"<b>Snapshots Labeled:</b> {snapshots_labeled}\n"
                f"<b>Total Labeled:</b> {stats['labeled_snapshots']:,}\n\n"
                f"<b>Progress:</b> {stats['labeling_rate']:.1f}% of data labeled"
            )
            self._send_telegram(message)

    def _notify_daily_summary(self, stats: Dict):
        """Send daily summary alert (call this from external scheduler)."""
        if not self.telegram:
            return

        message = (
            f"<b>📈 DAILY DATA COLLECTION SUMMARY</b>\n\n"
            f"<b>Total Snapshots:</b> {stats['total_snapshots']:,}\n"
            f"<b>Unique Markets:</b> {stats['unique_markets']:,}\n"
            f"<b>Labeled:</b> {stats['labeled_snapshots']:,} ({stats['labeling_rate']:.1f}%)\n"
            f"<b>Unlabeled:</b> {stats['unlabeled_snapshots']:,}\n"
            f"<b>Trades Executed:</b> {stats['trades_executed']:,}\n"
            f"<b>Trades Blocked:</b> {stats['trades_blocked']:,}\n\n"
        )

        # Time range
        if stats['first_snapshot'] and stats['last_snapshot']:
            message += (
                f"<b>Data Range:</b>\n"
                f"  First: {stats['first_snapshot'][:10]}\n"
                f"  Last: {stats['last_snapshot'][:10]}\n\n"
            )

        # Bot breakdown
        if stats['by_bot_type']:
            message += "<b>By Bot Type:</b>\n"
            for bot_type, counts in stats['by_bot_type'].items():
                message += (
                    f"  • {bot_type}: {counts['total']:,} total, "
                    f"{counts['labeled']:,} labeled\n"
                )

        self._send_telegram(message)

    def log_snapshot(self,
                     market_id: str,
                     bot_type: str,
                     features: Dict[str, Any],
                     prediction: Dict[str, Any],
                     market_data: Dict[str, Any],
                     prices: Dict[str, float],
                     position_opened: bool = False,
                     position_id: Optional[int] = None,
                     rejection_reason: Optional[str] = None) -> int:
        """
        Log a market snapshot.

        Args:
            market_id: Market/condition ID
            bot_type: 'event', 'price_level', or 'short_expiry'
            features: Dictionary of features (will be JSON serialized)
            prediction: Model prediction dict with keys:
                - model_prob: float (0-1)
                - confidence: float (0-1)
                - edge: float
                - predicted_outcome: 'YES' or 'NO'
            market_data: Market metadata dict with keys:
                - question: str
                - asset: str (optional)
                - strike_price: float (optional)
                - expiry_date: datetime or str
                - days_to_expiry: float
                - market_type: str (optional)
                - condition_id: str (optional)
                - token_id: str (optional)
            prices: Price dict with keys:
                - yes: float
                - no: float
                - spread: float (optional)
            position_opened: Whether a position was opened
            position_id: ID from positions table (if trade executed)
            rejection_reason: Why trade wasn't executed (if applicable)

        Returns:
            Snapshot ID (database row ID)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Parse expiry date
        expiry_date = market_data.get('expiry_date')
        if expiry_date:
            if isinstance(expiry_date, str):
                try:
                    expiry_date = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
                except:
                    expiry_date = None

        # Serialize features to JSON
        features_json = json.dumps(features)

        # Calculate spread if not provided
        spread = prices.get('spread')
        if spread is None:
            spread = prices['yes'] + prices['no'] - 1.0

        try:
            cursor.execute("""
                INSERT INTO market_snapshots (
                    market_id, condition_id, token_id, question,
                    bot_type, snapshot_time,
                    asset, strike_price, expiry_date, days_to_expiry, market_type,
                    features_json,
                    model_prob, confidence, edge, predicted_outcome,
                    yes_price, no_price, spread,
                    volume_24h, liquidity,
                    position_opened, position_id, rejection_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                market_id,
                market_data.get('condition_id'),
                market_data.get('token_id'),
                market_data.get('question', ''),
                bot_type,
                datetime.now(timezone.utc).isoformat(),
                market_data.get('asset'),
                market_data.get('strike_price'),
                expiry_date.isoformat() if expiry_date else None,
                market_data.get('days_to_expiry'),
                market_data.get('market_type'),
                features_json,
                prediction.get('model_prob'),
                prediction.get('confidence'),
                prediction.get('edge'),
                prediction.get('predicted_outcome'),
                prices['yes'],
                prices['no'],
                spread,
                features.get('volume_24h'),
                features.get('liquidity'),
                1 if position_opened else 0,
                position_id,
                rejection_reason
            ))

            snapshot_id = cursor.lastrowid
            conn.commit()

            logger.debug(f"Logged snapshot {snapshot_id}: {market_data.get('question', '')[:50]}")

            # Check for milestones and send alerts
            self._check_and_alert_milestones()

            return snapshot_id

        except sqlite3.IntegrityError as e:
            # Duplicate snapshot (same market + bot + time)
            logger.debug(f"Duplicate snapshot ignored: {e}")
            return -1
        finally:
            conn.close()

    def log_price_evolution(self, snapshot_id: int, yes_price: float, no_price: float):
        """
        Log price change for a previously recorded snapshot.

        Args:
            snapshot_id: ID from market_snapshots table
            yes_price: Current YES price
            no_price: Current NO price
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get snapshot time to calculate hours elapsed
        cursor.execute("""
            SELECT snapshot_time FROM market_snapshots WHERE id = ?
        """, (snapshot_id,))
        result = cursor.fetchone()

        if not result:
            logger.warning(f"Snapshot {snapshot_id} not found")
            conn.close()
            return

        snapshot_time = datetime.fromisoformat(result[0])
        now = datetime.now(timezone.utc)
        hours_elapsed = (now - snapshot_time).total_seconds() / 3600

        cursor.execute("""
            INSERT INTO price_evolution (
                snapshot_id, check_time, yes_price, no_price, hours_since_snapshot
            ) VALUES (?, ?, ?, ?, ?)
        """, (snapshot_id, now.isoformat(), yes_price, no_price, hours_elapsed))

        conn.commit()
        conn.close()
        logger.debug(f"Logged price evolution for snapshot {snapshot_id} (+{hours_elapsed:.1f}h)")

    def record_outcome(self, snapshot_id: Optional[int] = None,
                      market_id: Optional[str] = None,
                      bot_type: Optional[str] = None,
                      outcome: str = None,
                      resolution_price: Optional[float] = None):
        """
        Record outcome for a market snapshot.

        Can be called by snapshot_id OR by (market_id + bot_type).

        Args:
            snapshot_id: Specific snapshot ID to update
            market_id: Market ID (alternative to snapshot_id)
            bot_type: Bot type (required if using market_id)
            outcome: 'YES', 'NO', 'INVALID', or 'EXPIRED'
            resolution_price: Final resolution price (0.0 or 1.0 typically)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if snapshot_id:
            # Update specific snapshot
            cursor.execute("""
                UPDATE market_snapshots
                SET outcome = ?, resolution_price = ?,
                    resolution_time = ?, labeled = 1
                WHERE id = ?
            """, (outcome, resolution_price, datetime.now(timezone.utc).isoformat(), snapshot_id))
        elif market_id and bot_type:
            # Update all snapshots for this market/bot combination
            cursor.execute("""
                UPDATE market_snapshots
                SET outcome = ?, resolution_price = ?,
                    resolution_time = ?, labeled = 1
                WHERE market_id = ? AND bot_type = ? AND labeled = 0
            """, (outcome, resolution_price, datetime.now(timezone.utc).isoformat(),
                 market_id, bot_type))
        else:
            raise ValueError("Must provide snapshot_id OR (market_id + bot_type)")

        updated = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Recorded outcome '{outcome}' for {updated} snapshot(s)")

        # Send alert for outcome recording
        if updated > 0:
            market_identifier = market_id if market_id else f"snapshot_{snapshot_id}"
            self._notify_outcome_recorded(market_identifier, outcome, updated)

            # Check for labeling milestones
            self._check_and_alert_milestones()

    def get_training_data(self,
                         bot_type: Optional[str] = None,
                         labeled_only: bool = True,
                         min_date: Optional[datetime] = None,
                         max_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Fetch training data as a pandas DataFrame.

        Args:
            bot_type: Filter by bot type (None = all bots)
            labeled_only: Only include snapshots with known outcomes
            min_date: Minimum snapshot time
            max_date: Maximum snapshot time

        Returns:
            DataFrame with features + outcome labels
        """
        conn = sqlite3.connect(self.db_path)

        # Build query
        query = "SELECT * FROM market_snapshots WHERE 1=1"
        params = []

        if bot_type:
            query += " AND bot_type = ?"
            params.append(bot_type)

        if labeled_only:
            query += " AND labeled = 1"

        if min_date:
            query += " AND snapshot_time >= ?"
            params.append(min_date.isoformat())

        if max_date:
            query += " AND snapshot_time <= ?"
            params.append(max_date.isoformat())

        query += " ORDER BY snapshot_time ASC"

        # Load into DataFrame
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        # Deserialize features JSON
        if not df.empty and 'features_json' in df.columns:
            features_expanded = df['features_json'].apply(json.loads).apply(pd.Series)
            df = pd.concat([df.drop('features_json', axis=1), features_expanded], axis=1)

        logger.info(f"Retrieved {len(df)} training samples (bot_type={bot_type}, labeled_only={labeled_only})")
        return df

    def get_unlabeled_snapshots(self, bot_type: Optional[str] = None) -> List[Dict]:
        """
        Get all snapshots that need outcome labels.

        Useful for backfilling outcomes when markets resolve.

        Args:
            bot_type: Filter by bot type

        Returns:
            List of snapshot dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT id, market_id, condition_id, question, snapshot_time,
                   expiry_date, predicted_outcome
            FROM market_snapshots
            WHERE labeled = 0
        """
        params = []

        if bot_type:
            query += " AND bot_type = ?"
            params.append(bot_type)

        query += " ORDER BY snapshot_time ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        snapshots = [
            {
                'id': row[0],
                'market_id': row[1],
                'condition_id': row[2],
                'question': row[3],
                'snapshot_time': row[4],
                'expiry_date': row[5],
                'predicted_outcome': row[6]
            }
            for row in rows
        ]

        logger.info(f"Found {len(snapshots)} unlabeled snapshots")
        return snapshots

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with counts, coverage, and status info
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Overall stats
        cursor.execute("SELECT COUNT(*) FROM market_snapshots")
        total_snapshots = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT market_id) FROM market_snapshots")
        unique_markets = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM market_snapshots WHERE labeled = 1")
        labeled_snapshots = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM market_snapshots WHERE position_opened = 1")
        trades_executed = cursor.fetchone()[0]

        # By bot type
        cursor.execute("""
            SELECT bot_type, COUNT(*),
                   SUM(CASE WHEN labeled = 1 THEN 1 ELSE 0 END) as labeled,
                   SUM(CASE WHEN position_opened = 1 THEN 1 ELSE 0 END) as traded
            FROM market_snapshots
            GROUP BY bot_type
        """)
        by_bot = {row[0]: {'total': row[1], 'labeled': row[2], 'traded': row[3]}
                  for row in cursor.fetchall()}

        # Time range
        cursor.execute("""
            SELECT MIN(snapshot_time), MAX(snapshot_time)
            FROM market_snapshots
        """)
        time_range = cursor.fetchone()

        conn.close()

        return {
            'total_snapshots': total_snapshots,
            'unique_markets': unique_markets,
            'labeled_snapshots': labeled_snapshots,
            'unlabeled_snapshots': total_snapshots - labeled_snapshots,
            'trades_executed': trades_executed,
            'trades_blocked': total_snapshots - trades_executed,
            'by_bot_type': by_bot,
            'first_snapshot': time_range[0] if time_range[0] else None,
            'last_snapshot': time_range[1] if time_range[1] else None,
            'labeling_rate': (labeled_snapshots / total_snapshots * 100) if total_snapshots > 0 else 0
        }

    def print_statistics(self):
        """Print formatted statistics to console."""
        stats = self.get_statistics()

        print("\n" + "=" * 60)
        print("MARKET SNAPSHOT COLLECTOR - STATISTICS")
        print("=" * 60)
        print(f"Total Snapshots:     {stats['total_snapshots']:,}")
        print(f"Unique Markets:      {stats['unique_markets']:,}")
        print(f"Labeled (ready):     {stats['labeled_snapshots']:,} ({stats['labeling_rate']:.1f}%)")
        print(f"Unlabeled (pending): {stats['unlabeled_snapshots']:,}")
        print(f"Trades Executed:     {stats['trades_executed']:,}")
        print(f"Trades Blocked:      {stats['trades_blocked']:,}")

        if stats['by_bot_type']:
            print("\nBY BOT TYPE:")
            for bot_type, counts in stats['by_bot_type'].items():
                print(f"  {bot_type:15} Total: {counts['total']:4}  "
                      f"Labeled: {counts['labeled']:4}  Traded: {counts['traded']:4}")

        if stats['first_snapshot']:
            print(f"\nTime Range:")
            print(f"  First: {stats['first_snapshot']}")
            print(f"  Last:  {stats['last_snapshot']}")

        print("=" * 60 + "\n")

    def send_daily_summary(self):
        """
        Send daily summary via Telegram (public method for external scheduling).

        Usage:
            # Call from cron or scheduler
            collector = MarketSnapshotCollector(telegram=telegram_notifier)
            collector.send_daily_summary()
        """
        stats = self.get_statistics()
        self._notify_daily_summary(stats)
