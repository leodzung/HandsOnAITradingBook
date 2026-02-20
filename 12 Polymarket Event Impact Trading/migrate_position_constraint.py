#!/usr/bin/env python3
"""
Migrate position database to use partial unique index instead of table constraint.

This allows re-entering the same market/outcome after closing a position.

OLD: UNIQUE(market_id, outcome) - prevents any duplicates
NEW: Unique index on (market_id, outcome) WHERE status = 'OPEN' - allows re-entries
"""

import sqlite3
import os
from datetime import datetime

def migrate_database(db_path):
    """Migrate a database to use partial unique index."""

    if not os.path.exists(db_path):
        print(f"Database not found: {db_path}")
        return

    print(f"\nMigrating: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Check current schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='positions'")
    current_schema = cursor.fetchone()

    if not current_schema:
        print("  No positions table found - skipping")
        conn.close()
        return

    print(f"  Current schema has UNIQUE constraint: {'UNIQUE(market_id, outcome)' in current_schema[0]}")

    # 2. Check if partial index already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_open_positions'")
    has_index = cursor.fetchone() is not None

    if has_index:
        print("  ✓ Partial index already exists - no migration needed")
        conn.close()
        return

    # 3. Backup the table
    backup_name = f"positions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"  Creating backup: {backup_name}")
    cursor.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM positions")

    # 4. Get all column names
    cursor.execute("PRAGMA table_info(positions)")
    columns = [row[1] for row in cursor.fetchall()]
    print(f"  Found {len(columns)} columns")

    # 5. Drop old table
    print("  Dropping old table...")
    cursor.execute("DROP TABLE positions")

    # 6. Create new table without UNIQUE constraint
    print("  Creating new table...")
    cursor.execute('''
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

    # 7. Create partial unique index
    print("  Creating partial unique index...")
    cursor.execute('''
        CREATE UNIQUE INDEX idx_open_positions
        ON positions(market_id, outcome)
        WHERE UPPER(status) = 'OPEN'
    ''')

    # 8. Copy data back (using column names to handle schema differences)
    print("  Copying data from backup...")

    # Get columns from backup table
    cursor.execute(f"PRAGMA table_info({backup_name})")
    backup_columns = [row[1] for row in cursor.fetchall()]

    # Get columns from new table
    cursor.execute("PRAGMA table_info(positions)")
    new_columns = [row[1] for row in cursor.fetchall()]

    # Find common columns (excluding id which is auto-increment)
    common_columns = [col for col in backup_columns if col in new_columns and col != 'id']

    # Build INSERT statement
    cols_str = ', '.join(common_columns)
    cursor.execute(f"INSERT INTO positions ({cols_str}) SELECT {cols_str} FROM {backup_name}")

    # 9. Verify
    cursor.execute("SELECT COUNT(*) FROM positions")
    count = cursor.fetchone()[0]
    print(f"  ✓ Migrated {count} positions")

    cursor.execute("SELECT COUNT(*) FROM positions WHERE UPPER(status) = 'OPEN'")
    open_count = cursor.fetchone()[0]
    print(f"  ✓ {open_count} open positions")

    # 10. Check for duplicate open positions
    cursor.execute('''
        SELECT market_id, outcome, COUNT(*) as cnt
        FROM positions
        WHERE UPPER(status) = 'OPEN'
        GROUP BY market_id, outcome
        HAVING cnt > 1
    ''')
    duplicates = cursor.fetchall()

    if duplicates:
        print(f"  ⚠️  WARNING: Found {len(duplicates)} duplicate open positions:")
        for market_id, outcome, cnt in duplicates:
            print(f"     {market_id[:16]}... {outcome}: {cnt} open positions")
        print("  You may need to manually close duplicates")

    conn.commit()
    conn.close()

    print(f"  ✓ Migration complete!")


def main():
    """Migrate all position databases."""

    databases = [
        'data/positions.db',  # Event trader
        'data/positions_price_level.db',  # Price-level trader
        'data/positions_short_expiry.db',  # Short-expiry trader
    ]

    print("=" * 60)
    print("Position Database Migration")
    print("=" * 60)
    print("\nThis migration:")
    print("1. Removes table-level UNIQUE(market_id, outcome) constraint")
    print("2. Adds partial index: UNIQUE only for OPEN positions")
    print("3. Allows re-entering markets after closing positions")
    print()

    for db_path in databases:
        migrate_database(db_path)

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
