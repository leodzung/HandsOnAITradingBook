#!/usr/bin/env python3
"""
Position Manager with SQLite Persistence
Ensures positions survive bot restarts.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages trading positions with SQLite persistence."""

    def __init__(self, db_path: str = 'data/positions.db'):
        """
        Initialize position manager.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._create_table()
        logger.info(f"✓ Position manager initialized (DB: {db_path})")

    def _create_table(self):
        """Create positions table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                market_id TEXT PRIMARY KEY,
                token_id TEXT,
                entry_time TEXT,
                entry_price REAL,
                side TEXT,
                size REAL,
                status TEXT DEFAULT 'OPEN',
                exit_time TEXT,
                exit_price REAL,
                pnl REAL,
                metadata TEXT,
                stop_loss_pct REAL,
                take_profit_pct REAL,
                highest_price_seen REAL,
                lowest_price_seen REAL,
                exit_reason TEXT
            )
        ''')
        conn.commit()
        conn.close()

        # Migrate existing tables to add new columns
        self._migrate_schema()

    def _migrate_schema(self):
        """Add new columns to existing tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get existing columns
        cursor.execute("PRAGMA table_info(positions)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        # New columns to add
        new_columns = [
            ('stop_loss_pct', 'REAL'),
            ('take_profit_pct', 'REAL'),
            ('highest_price_seen', 'REAL'),
            ('lowest_price_seen', 'REAL'),
            ('exit_reason', 'TEXT')
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

    def save_position(self, market_id: str, token_id: str,
                     entry_time: datetime, entry_price: float,
                     side: str, size: float, metadata: Dict = None,
                     stop_loss_pct: float = None, take_profit_pct: float = None):
        """
        Save a position to database.

        Args:
            market_id: Market ID
            token_id: Token ID
            entry_time: When position was opened
            entry_price: Entry price
            side: 'BUY' or 'SELL'
            size: Position size ($)
            metadata: Additional data (dict)
            stop_loss_pct: Stop loss percentage threshold
            take_profit_pct: Take profit percentage threshold
        """
        conn = sqlite3.connect(self.db_path)

        metadata_json = json.dumps(metadata) if metadata else None

        conn.execute('''
            INSERT OR REPLACE INTO positions
            (market_id, token_id, entry_time, entry_price, side, size, status, metadata,
             stop_loss_pct, take_profit_pct, highest_price_seen, lowest_price_seen)
            VALUES (?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?, ?)
        ''', (
            market_id,
            token_id,
            entry_time.isoformat(),
            entry_price,
            side,
            size,
            metadata_json,
            stop_loss_pct,
            take_profit_pct,
            entry_price,  # Initialize highest_price_seen with entry price
            entry_price   # Initialize lowest_price_seen with entry price
        ))

        conn.commit()
        conn.close()

        logger.info(f"✓ Saved position: {market_id} ({side} ${size:.2f} @ ${entry_price:.3f})")

    def load_positions(self) -> List[Dict]:
        """
        Load all open positions from database.

        Returns:
            List of position dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute('''
            SELECT * FROM positions WHERE status = 'OPEN'
        ''')

        positions = []
        for row in cursor:
            # Parse entry_time and ensure it's timezone-aware
            entry_time = datetime.fromisoformat(row['entry_time'])
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)

            position = {
                'market_id': row['market_id'],
                'token_id': row['token_id'],
                'entry_time': entry_time,
                'entry_price': row['entry_price'],
                'side': row['side'],
                'size': row['size'],
                'status': row['status']
            }

            # Parse metadata if exists
            if row['metadata']:
                try:
                    position['metadata'] = json.loads(row['metadata'])
                except:
                    position['metadata'] = {}

            positions.append(position)

        conn.close()

        logger.info(f"✓ Loaded {len(positions)} open positions from database")
        return positions

    def close_position(self, market_id: str, exit_time,
                      exit_price: float, pnl: float, exit_reason: str = None):
        """
        Mark a position as closed.

        Args:
            market_id: Market ID
            exit_time: When position was closed (datetime or string)
            exit_price: Exit price
            pnl: Profit/loss
            exit_reason: Why position was closed (stop_loss, take_profit, trailing_stop, time_exit, expiry, manual)
        """
        conn = sqlite3.connect(self.db_path)

        # Handle both datetime and string types for exit_time
        if hasattr(exit_time, 'isoformat'):
            exit_time_str = exit_time.isoformat()
        else:
            exit_time_str = str(exit_time)

        conn.execute('''
            UPDATE positions
            SET status = 'CLOSED',
                exit_time = ?,
                exit_price = ?,
                pnl = ?,
                exit_reason = ?
            WHERE market_id = ?
        ''', (
            exit_time_str,
            exit_price,
            pnl,
            exit_reason,
            market_id
        ))

        conn.commit()
        conn.close()

        reason_str = f" [{exit_reason}]" if exit_reason else ""
        logger.info(f"✓ Closed position: {market_id} (P&L: ${pnl:+.2f}){reason_str}")

    def get_position(self, market_id: str) -> Optional[Dict]:
        """
        Get a specific position.

        Args:
            market_id: Market ID

        Returns:
            Position dict or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute('''
            SELECT * FROM positions WHERE market_id = ?
        ''', (market_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            # Parse entry_time and ensure it's timezone-aware
            entry_time = datetime.fromisoformat(row['entry_time'])
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)

            return {
                'market_id': row['market_id'],
                'token_id': row['token_id'],
                'entry_time': entry_time,
                'entry_price': row['entry_price'],
                'side': row['side'],
                'size': row['size'],
                'status': row['status']
            }

        return None

    def get_open_positions_count(self) -> int:
        """
        Get count of open positions.

        Returns:
            Number of open positions
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('''
            SELECT COUNT(*) FROM positions WHERE status = 'OPEN'
        ''')
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def delete_position(self, market_id: str):
        """
        Delete a position from database (use sparingly).

        Args:
            market_id: Market ID
        """
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM positions WHERE market_id = ?', (market_id,))
        conn.commit()
        conn.close()

        logger.warning(f"⚠️ Deleted position: {market_id}")

    def get_all_positions(self) -> List[Dict]:
        """
        Get ALL positions (open and closed).

        Returns:
            List of all positions
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute('SELECT * FROM positions ORDER BY entry_time DESC')

        positions = []
        for row in cursor:
            # Parse entry_time and ensure it's timezone-aware
            entry_time = datetime.fromisoformat(row['entry_time'])
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=timezone.utc)

            # Parse exit_time if exists and ensure it's timezone-aware
            exit_time = None
            if row['exit_time']:
                exit_time = datetime.fromisoformat(row['exit_time'])
                if exit_time.tzinfo is None:
                    exit_time = exit_time.replace(tzinfo=timezone.utc)

            position = {
                'market_id': row['market_id'],
                'token_id': row['token_id'],
                'entry_time': entry_time,
                'entry_price': row['entry_price'],
                'side': row['side'],
                'size': row['size'],
                'status': row['status'],
                'exit_time': exit_time,
                'exit_price': row['exit_price'],
                'pnl': row['pnl']
            }
            positions.append(position)

        conn.close()
        return positions

    def get_statistics(self) -> Dict:
        """
        Get position statistics.

        Returns:
            Dictionary of stats
        """
        conn = sqlite3.connect(self.db_path)

        # Open positions
        open_count = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status = 'OPEN'"
        ).fetchone()[0]

        open_value = conn.execute(
            "SELECT SUM(size) FROM positions WHERE status = 'OPEN'"
        ).fetchone()[0] or 0

        # Closed positions
        closed_count = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status = 'CLOSED'"
        ).fetchone()[0]

        total_pnl = conn.execute(
            "SELECT SUM(pnl) FROM positions WHERE status = 'CLOSED'"
        ).fetchone()[0] or 0

        wins = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status = 'CLOSED' AND pnl > 0"
        ).fetchone()[0]

        losses = conn.execute(
            "SELECT COUNT(*) FROM positions WHERE status = 'CLOSED' AND pnl < 0"
        ).fetchone()[0]

        conn.close()

        win_rate = (wins / closed_count * 100) if closed_count > 0 else 0

        return {
            'open_positions': open_count,
            'open_value': open_value,
            'closed_positions': closed_count,
            'total_pnl': total_pnl,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate
        }

    def update_price_extremes(self, market_id: str, current_price: float) -> Dict:
        """
        Update highest/lowest price seen for trailing stop calculations.

        Args:
            market_id: Market ID
            current_price: Current market price

        Returns:
            Dict with highest_price_seen and lowest_price_seen
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get current extremes
        cursor.execute('''
            SELECT highest_price_seen, lowest_price_seen
            FROM positions WHERE market_id = ?
        ''', (market_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return {'highest_price_seen': current_price, 'lowest_price_seen': current_price}

        highest = row[0] if row[0] is not None else current_price
        lowest = row[1] if row[1] is not None else current_price

        # Update if new extremes
        new_highest = max(highest, current_price)
        new_lowest = min(lowest, current_price)

        if new_highest != highest or new_lowest != lowest:
            cursor.execute('''
                UPDATE positions
                SET highest_price_seen = ?, lowest_price_seen = ?
                WHERE market_id = ?
            ''', (new_highest, new_lowest, market_id))
            conn.commit()

        conn.close()

        return {'highest_price_seen': new_highest, 'lowest_price_seen': new_lowest}

    def get_price_extremes(self, market_id: str) -> Optional[Dict]:
        """
        Get highest/lowest price seen for a position.

        Args:
            market_id: Market ID

        Returns:
            Dict with highest_price_seen and lowest_price_seen, or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT highest_price_seen, lowest_price_seen
            FROM positions WHERE market_id = ?
        ''', (market_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'highest_price_seen': row[0],
                'lowest_price_seen': row[1]
            }
        return None

    def set_position_stops(self, market_id: str, sl_pct: float = None, tp_pct: float = None):
        """
        Set stop-loss and take-profit thresholds for a position.

        Args:
            market_id: Market ID
            sl_pct: Stop loss percentage
            tp_pct: Take profit percentage
        """
        conn = sqlite3.connect(self.db_path)

        if sl_pct is not None:
            conn.execute('''
                UPDATE positions SET stop_loss_pct = ? WHERE market_id = ?
            ''', (sl_pct, market_id))

        if tp_pct is not None:
            conn.execute('''
                UPDATE positions SET take_profit_pct = ? WHERE market_id = ?
            ''', (tp_pct, market_id))

        conn.commit()
        conn.close()

    def get_exit_reason(self, market_id: str) -> Optional[str]:
        """
        Get the exit reason for a closed position.

        Args:
            market_id: Market ID

        Returns:
            Exit reason string or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT exit_reason FROM positions WHERE market_id = ?
        ''', (market_id,))

        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None
