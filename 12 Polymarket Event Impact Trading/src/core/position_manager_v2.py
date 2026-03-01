#!/usr/bin/env python3
"""
Enhanced Position Manager with SQLite Persistence (V2)

MAJOR IMPROVEMENTS:
1. Multiple positions per market (UNIQUE: market_id + outcome)
2. Prediction market terminology (outcome: YES/NO instead of side: BUY/SELL)
3. Enhanced analytics fields (edge, confidence, signal_reason, hours_to_expiry)
4. Real-time price tracking (current_price, pnl_pct)
5. Backward compatible migration from V1

This replaces both the old shared PositionManager AND ShortExpiryPositionManager.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DuplicatePositionError(Exception):
    """Raised when attempting to create a position that already exists."""
    pass


class PositionManager:
    """
    Enhanced position manager for all trading bots.

    Key Features:
    - Multiple positions per market (can hold YES and NO simultaneously)
    - Tracks edge, confidence, signal_reason for strategy analysis
    - Real-time price updates with pnl_pct calculation
    - Hours to expiry tracking for time-based exits
    - Migrates from V1 schema automatically
    """

    def __init__(self, db_path: str = 'data/positions.db'):
        """
        Initialize position manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._create_table()
        logger.info(f"✓ Position manager V2 initialized (DB: {db_path})")

    def _create_table(self):
        """Create enhanced positions table with V2 schema."""
        conn = sqlite3.connect(self.db_path)

        # OPS-005: Database integrity check at startup
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            if result and result[0] != 'ok':
                logger.error(f"Database integrity check FAILED for {self.db_path}: {result[0]}")
                raise RuntimeError(f"Database corruption detected in {self.db_path}: {result[0]}")
            logger.debug(f"Database integrity check passed for {self.db_path}")
        except sqlite3.DatabaseError as e:
            logger.error(f"Database integrity check error for {self.db_path}: {e}")
            raise

        # Check if this is a V1 database (has market_id as PRIMARY KEY)
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='positions'")
        result = cursor.fetchone()

        if result and 'market_id TEXT PRIMARY KEY' in result[0]:
            logger.info("Detected V1 schema - will migrate to V2")
            self._migrate_v1_to_v2(conn)
        else:
            # Create V2 schema from scratch
            conn.execute('''
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    token_id TEXT,
                    outcome TEXT NOT NULL,
                    entry_time TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    size REAL NOT NULL,
                    status TEXT DEFAULT 'open',

                    -- Exit fields
                    exit_time TEXT,
                    exit_price REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    exit_reason TEXT,

                    -- Analytics fields
                    edge REAL,
                    confidence REAL,
                    signal_reason TEXT,
                    hours_to_expiry_at_entry REAL,
                    bucket TEXT,

                    -- Price tracking
                    current_price REAL,
                    highest_price_seen REAL,
                    lowest_price_seen REAL,

                    -- Risk management
                    stop_loss_pct REAL,
                    take_profit_pct REAL,

                    -- Flexible metadata
                    metadata TEXT
                )
            ''')

            # Create partial unique index: only one OPEN position per (market_id, outcome)
            # This allows re-entering after closing a position
            conn.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_open_positions
                ON positions(market_id, outcome)
                WHERE UPPER(status) = 'OPEN'
            ''')

            conn.commit()

        conn.close()

        # Run migration to add any missing columns
        self._migrate_schema()

    def _migrate_v1_to_v2(self, conn):
        """
        Migrate from V1 schema (market_id PRIMARY KEY) to V2 (id + UNIQUE constraint).

        This is a destructive migration that:
        1. Backs up the old table
        2. Creates new V2 table
        3. Migrates data (side → outcome, BUY/SELL → YES/NO)
        4. Drops old table
        """
        logger.info("Starting V1 → V2 migration...")

        # 1. Backup old table
        backup_name = f"positions_v1_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        conn.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM positions")
        logger.info(f"✓ Backed up V1 table to {backup_name}")

        # 2. Drop old table
        conn.execute("DROP TABLE positions")

        # 3. Create new V2 table
        conn.execute('''
            CREATE TABLE positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                market_id TEXT NOT NULL,
                token_id TEXT,
                outcome TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                entry_price REAL NOT NULL,
                size REAL NOT NULL,
                status TEXT DEFAULT 'open',
                exit_time TEXT,
                exit_price REAL,
                pnl REAL,
                pnl_pct REAL,
                exit_reason TEXT,
                edge REAL,
                confidence REAL,
                signal_reason TEXT,
                hours_to_expiry_at_entry REAL,
                bucket TEXT,
                current_price REAL,
                highest_price_seen REAL,
                lowest_price_seen REAL,
                stop_loss_pct REAL,
                take_profit_pct REAL,
                metadata TEXT
            )
        ''')

        # Create partial unique index for open positions only
        conn.execute('''
            CREATE UNIQUE INDEX idx_open_positions
            ON positions(market_id, outcome)
            WHERE UPPER(status) = 'OPEN'
        ''')

        # 4. Migrate data (side → outcome)
        # Get columns from V1 table to handle different V1 versions
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({backup_name})")
        v1_columns = {row[1] for row in cursor.fetchall()}

        # Build SELECT statement based on available columns
        select_cols = []
        for col in ['market_id', 'token_id', 'entry_time', 'entry_price', 'size']:
            select_cols.append(col)

        # Handle side → outcome conversion
        if 'side' in v1_columns:
            select_cols.append('''CASE
                WHEN side = 'BUY' THEN 'YES'
                WHEN side = 'SELL' THEN 'NO'
                ELSE COALESCE(side, 'YES')
            END as outcome''')
        else:
            select_cols.append("'YES' as outcome")

        # Add status (uppercase)
        select_cols.append("UPPER(COALESCE(status, 'OPEN')) as status")

        # Optional columns (NULL if not exists)
        for col in ['exit_time', 'exit_price', 'pnl', 'exit_reason',
                    'highest_price_seen', 'lowest_price_seen',
                    'stop_loss_pct', 'take_profit_pct', 'metadata']:
            if col in v1_columns:
                select_cols.append(col)
            else:
                select_cols.append(f"NULL as {col}")

        # Execute migration
        conn.execute(f'''
            INSERT INTO positions (
                market_id, token_id, entry_time, entry_price, size, outcome,
                status, exit_time, exit_price, pnl, exit_reason,
                highest_price_seen, lowest_price_seen, stop_loss_pct, take_profit_pct, metadata
            )
            SELECT {", ".join(select_cols)}
            FROM {backup_name}
        ''')

        # Calculate pnl_pct for closed positions
        conn.execute('''
            UPDATE positions
            SET pnl_pct = CASE
                WHEN entry_price > 0 AND pnl IS NOT NULL
                THEN ((exit_price - entry_price) / entry_price) * 100
                ELSE NULL
            END
            WHERE status = 'CLOSED' AND exit_price IS NOT NULL
        ''')

        conn.commit()
        migrated = conn.execute("SELECT COUNT(*) FROM positions").fetchone()[0]
        logger.info(f"✓ Migrated {migrated} positions from V1 to V2")

    def _migrate_schema(self):
        """Add new columns to existing V2 tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get existing columns
        cursor.execute("PRAGMA table_info(positions)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # New columns to add (for incremental updates)
        new_columns = [
            ('edge', 'REAL'),
            ('confidence', 'REAL'),
            ('signal_reason', 'TEXT'),
            ('hours_to_expiry_at_entry', 'REAL'),
            ('bucket', 'TEXT'),
            ('current_price', 'REAL'),
            ('pnl_pct', 'REAL'),
        ]

        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE positions ADD COLUMN {col_name} {col_type}')
                    logger.info(f"Added column {col_name} to positions table")
                except sqlite3.OperationalError:
                    pass  # Column already exists

        conn.commit()
        conn.close()

    def save_position(self, market_id: str, token_id: str, outcome: str,
                     entry_time: datetime, entry_price: float, size: float,
                     edge: float = None, confidence: float = None,
                     signal_reason: str = None, hours_to_expiry: float = None,
                     bucket: str = None, metadata: Dict = None, stop_loss_pct: float = None,
                     take_profit_pct: float = None):
        """
        Save a new position to database.

        Args:
            market_id: Market condition ID
            token_id: Token ID
            outcome: 'YES' or 'NO'
            entry_time: When position was opened
            entry_price: Entry price
            size: Position size ($)
            edge: Expected edge (optional)
            confidence: Signal confidence 0-1 (optional)
            signal_reason: Strategy that generated signal (optional)
            hours_to_expiry: Hours until market expiry at entry (optional)
            bucket: Trading bucket (e.g., 'ultra_short', 'short', 'medium') (optional)
            metadata: Additional data (dict, optional)
            stop_loss_pct: Stop loss percentage (optional)
            take_profit_pct: Take profit percentage (optional)
        """
        conn = sqlite3.connect(self.db_path)

        metadata_json = json.dumps(metadata) if metadata else None

        try:
            conn.execute('''
                INSERT INTO positions
                (market_id, token_id, outcome, entry_time, entry_price, size, status,
                 edge, confidence, signal_reason, hours_to_expiry_at_entry, bucket,
                 current_price, highest_price_seen, lowest_price_seen,
                 stop_loss_pct, take_profit_pct, metadata)
                VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market_id, token_id, outcome,
                entry_time.isoformat(), entry_price, size,
                edge, confidence, signal_reason, hours_to_expiry, bucket,
                entry_price,  # Initialize current_price
                entry_price,  # Initialize highest_price_seen
                entry_price,  # Initialize lowest_price_seen
                stop_loss_pct, take_profit_pct, metadata_json
            ))
            conn.commit()
            logger.info(f"✓ Saved position: {market_id} {outcome} (${size:.2f} @ ${entry_price:.3f})")
        except sqlite3.IntegrityError as e:
            logger.error(f"Failed to save position {market_id} {outcome}: {e}")
            raise DuplicatePositionError(f"Position already exists for {market_id} {outcome}") from e
        finally:
            conn.close()

    def has_position(self, market_id: str, outcome: str = None) -> bool:
        """
        Check if we have an open position.

        Args:
            market_id: Market ID
            outcome: Specific outcome ('YES' or 'NO'), or None to check any

        Returns:
            True if position exists
        """
        conn = sqlite3.connect(self.db_path)

        if outcome:
            query = "SELECT COUNT(*) FROM positions WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'"
            params = (market_id, outcome)
        else:
            query = "SELECT COUNT(*) FROM positions WHERE market_id = ? AND UPPER(status) = 'OPEN'"
            params = (market_id,)

        cursor = conn.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()

        return count > 0

    def get_open_positions(self, outcome: str = None) -> List[Dict]:
        """
        Get all open positions.

        Args:
            outcome: Filter by outcome ('YES'/'NO'), or None for all

        Returns:
            List of position dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        if outcome:
            cursor = conn.execute(
                "SELECT * FROM positions WHERE UPPER(status) = 'OPEN' AND outcome = ?",
                (outcome,)
            )
        else:
            cursor = conn.execute("SELECT * FROM positions WHERE UPPER(status) = 'OPEN'")

        positions = []
        for row in cursor:
            position = dict(row)

            # Parse timestamps
            position['entry_time'] = datetime.fromisoformat(position['entry_time'])
            if position['entry_time'].tzinfo is None:
                position['entry_time'] = position['entry_time'].replace(tzinfo=timezone.utc)

            # Parse metadata
            if position['metadata']:
                try:
                    position['metadata'] = json.loads(position['metadata'])
                except (json.JSONDecodeError, TypeError, ValueError):
                    position['metadata'] = {}

            positions.append(position)

        conn.close()
        return positions

    def get_position(self, market_id: str, outcome: str) -> Optional[Dict]:
        """
        Get a specific position.

        Args:
            market_id: Market ID
            outcome: 'YES' or 'NO'

        Returns:
            Position dict or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT * FROM positions WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'",
            (market_id, outcome)
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            position = dict(row)
            position['entry_time'] = datetime.fromisoformat(position['entry_time'])
            if position['entry_time'].tzinfo is None:
                position['entry_time'] = position['entry_time'].replace(tzinfo=timezone.utc)

            if position['metadata']:
                try:
                    position['metadata'] = json.loads(position['metadata'])
                except (json.JSONDecodeError, TypeError, ValueError):
                    position['metadata'] = {}

            return position

        return None

    def update_current_price(self, market_id: str, outcome: str, current_price: float):
        """
        Update current price for a position.

        Args:
            market_id: Market ID
            outcome: 'YES' or 'NO'
            current_price: Current market price
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            UPDATE positions
            SET current_price = ?
            WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'
        ''', (current_price, market_id, outcome))
        conn.commit()
        conn.close()

    def update_price_extremes(self, market_id: str, outcome: str, current_price: float):
        """
        Update highest/lowest price seen for trailing stop calculations.

        Args:
            market_id: Market ID
            outcome: 'YES' or 'NO'
            current_price: Current market price
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current extremes
        cursor.execute('''
            SELECT highest_price_seen, lowest_price_seen
            FROM positions
            WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'
        ''', (market_id, outcome))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        highest, lowest = row
        new_highest = max(highest or current_price, current_price)
        new_lowest = min(lowest or current_price, current_price)

        cursor.execute('''
            UPDATE positions
            SET highest_price_seen = ?, lowest_price_seen = ?, current_price = ?
            WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'
        ''', (new_highest, new_lowest, current_price, market_id, outcome))

        conn.commit()
        conn.close()

        return {'highest_price_seen': new_highest, 'lowest_price_seen': new_lowest}

    def close_position(self, market_id: str, outcome: str, exit_price: float,
                      exit_reason: str, exit_time: datetime = None):
        """
        Mark a position as closed and calculate P&L.

        Args:
            market_id: Market ID
            outcome: 'YES' or 'NO'
            exit_price: Exit price
            exit_reason: Why closed (stop_loss, take_profit, expiry, manual, etc.)
            exit_time: When closed (defaults to now)
        """
        if exit_time is None:
            exit_time = datetime.now(timezone.utc)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get entry price and size
        cursor.execute('''
            SELECT entry_price, size
            FROM positions
            WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'
        ''', (market_id, outcome))

        row = cursor.fetchone()
        if not row:
            logger.warning(f"Position not found: {market_id} {outcome}")
            conn.close()
            return

        entry_price, size = row
        pnl = (exit_price - entry_price) * size
        pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

        # Close position
        cursor.execute('''
            UPDATE positions
            SET status = 'CLOSED',
                exit_time = ?,
                exit_price = ?,
                pnl = ?,
                pnl_pct = ?,
                exit_reason = ?
            WHERE market_id = ? AND outcome = ? AND UPPER(status) = 'OPEN'
        ''', (
            exit_time.isoformat(), exit_price, pnl, pnl_pct, exit_reason,
            market_id, outcome
        ))

        conn.commit()
        conn.close()

        logger.info(
            f"✓ Closed position: {market_id} {outcome} | "
            f"Entry: {entry_price:.4f} | Exit: {exit_price:.4f} | "
            f"P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%) | Reason: {exit_reason}"
        )

    def count_positions_by_metadata(self, key: str, value: str) -> int:
        """
        Count open positions matching a metadata key-value pair.

        Useful for bucket counting: count_positions_by_metadata('bucket', 'short')

        Args:
            key: Metadata key (e.g., 'bucket')
            value: Metadata value (e.g., 'short')

        Returns:
            Count of matching open positions
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'OPEN' AND json_extract(metadata, ?) = ?",
            (f'$.{key}', value)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_open_positions_count(self) -> int:
        """Get count of open positions."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'OPEN'")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_statistics(self) -> Dict:
        """
        Get comprehensive position statistics.

        Returns:
            Dictionary with open/closed stats, P&L, win rate, etc.
        """
        conn = sqlite3.connect(self.db_path)

        stats = {}

        # Open positions
        stats['open_positions'] = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'OPEN'"
        ).fetchone()[0]

        stats['open_value'] = conn.execute(
            "SELECT SUM(size) FROM positions WHERE UPPER(status) = 'OPEN'"
        ).fetchone()[0] or 0

        # Closed positions
        stats['closed_positions'] = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'CLOSED'"
        ).fetchone()[0]

        stats['total_pnl'] = conn.execute(
            "SELECT SUM(pnl) FROM positions WHERE UPPER(status) = 'CLOSED'"
        ).fetchone()[0] or 0

        stats['wins'] = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'CLOSED' AND pnl > 0"
        ).fetchone()[0]

        stats['losses'] = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'CLOSED' AND pnl < 0"
        ).fetchone()[0]

        stats['win_rate'] = (stats['wins'] / stats['closed_positions'] * 100) if stats['closed_positions'] > 0 else 0

        # Average P&L per trade
        if stats['closed_positions'] > 0:
            stats['avg_pnl'] = stats['total_pnl'] / stats['closed_positions']

            avg_pnl_pct = conn.execute(
                "SELECT AVG(pnl_pct) FROM positions WHERE UPPER(status) = 'CLOSED' AND pnl_pct IS NOT NULL"
            ).fetchone()[0]
            stats['avg_pnl_pct'] = avg_pnl_pct or 0
        else:
            stats['avg_pnl'] = 0
            stats['avg_pnl_pct'] = 0

        conn.close()
        return stats
