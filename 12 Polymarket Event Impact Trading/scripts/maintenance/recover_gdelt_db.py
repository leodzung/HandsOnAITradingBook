#!/usr/bin/env python3
"""
GDELT Database Recovery Script

This script attempts to recover data from a corrupted GDELT database.
Run this when you see "database disk image is malformed" errors.

Usage:
    python3 recover_gdelt_db.py

What it does:
1. Creates a backup of the corrupted database
2. Attempts to extract all recoverable data
3. Creates a fresh database with the recovered data
4. Replaces the corrupted database with the recovered one
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def recover_database(db_path: str = 'data/gdelt_news.db'):
    """
    Recover a corrupted SQLite database.

    Args:
        db_path: Path to the corrupted database
    """
    backup_path = f"{db_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    recovered_path = f"{db_path}.recovered"

    logger.info(f"Starting recovery of {db_path}")
    logger.info(f"Creating backup at {backup_path}")

    try:
        # Create backup
        shutil.copy2(db_path, backup_path)
        logger.info(f"✓ Backup created: {backup_path}")

        # Try to recover data
        news_events_recovered = 0
        files_processed_recovered = 0

        logger.info("Opening corrupted database in recovery mode...")

        try:
            # Open corrupted database
            old_conn = sqlite3.connect(db_path, timeout=30.0)
            old_conn.execute("PRAGMA writable_schema=ON")
            old_cursor = old_conn.cursor()

            # Create new database
            logger.info(f"Creating new database at {recovered_path}...")
            new_conn = sqlite3.connect(recovered_path, timeout=30.0)
            new_cursor = new_conn.cursor()

            # Configure new database
            new_cursor.execute("PRAGMA journal_mode=WAL")
            new_cursor.execute("PRAGMA synchronous=FULL")
            new_cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")

            # Create tables
            logger.info("Creating tables...")
            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS news_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT UNIQUE,
                    title TEXT,
                    description TEXT,
                    source TEXT,
                    timestamp TEXT,
                    themes TEXT,
                    persons TEXT,
                    organizations TEXT,
                    locations TEXT,
                    tone REAL,
                    keywords TEXT,
                    gdelt_date TEXT,
                    collected_at TEXT
                )
            ''')

            new_cursor.execute('''
                CREATE TABLE IF NOT EXISTS gdelt_files_processed (
                    filename TEXT PRIMARY KEY,
                    processed_at TEXT,
                    events_found INTEGER
                )
            ''')

            # Recover news_events
            logger.info("Recovering news_events table...")
            try:
                old_cursor.execute("SELECT * FROM news_events")
                rows = old_cursor.fetchall()
                logger.info(f"Found {len(rows)} rows in news_events")

                for row in rows:
                    try:
                        new_cursor.execute('''
                            INSERT OR IGNORE INTO news_events
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', row)
                        news_events_recovered += 1
                    except Exception as e:
                        logger.debug(f"Skipping corrupted row: {e}")
                        continue

                new_conn.commit()
                logger.info(f"✓ Recovered {news_events_recovered} news events")

            except Exception as e:
                logger.warning(f"Could not recover news_events: {e}")

            # Recover gdelt_files_processed
            logger.info("Recovering gdelt_files_processed table...")
            try:
                old_cursor.execute("SELECT * FROM gdelt_files_processed")
                rows = old_cursor.fetchall()
                logger.info(f"Found {len(rows)} rows in gdelt_files_processed")

                for row in rows:
                    try:
                        new_cursor.execute('''
                            INSERT OR IGNORE INTO gdelt_files_processed
                            VALUES (?, ?, ?)
                        ''', row)
                        files_processed_recovered += 1
                    except Exception as e:
                        logger.debug(f"Skipping corrupted row: {e}")
                        continue

                new_conn.commit()
                logger.info(f"✓ Recovered {files_processed_recovered} processed file records")

            except Exception as e:
                logger.warning(f"Could not recover gdelt_files_processed: {e}")

            # Create indexes
            logger.info("Creating indexes...")
            new_cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_news_timestamp
                ON news_events(timestamp)
            ''')
            new_cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_news_source
                ON news_events(source)
            ''')
            new_conn.commit()

            # Close connections
            old_conn.close()
            new_conn.close()

            # Verify recovered database
            logger.info("Verifying recovered database...")
            verify_conn = sqlite3.connect(recovered_path)
            verify_cursor = verify_conn.cursor()
            verify_cursor.execute("PRAGMA integrity_check")
            result = verify_cursor.fetchone()
            verify_conn.close()

            if result[0] == 'ok':
                logger.info("✓ Recovered database integrity check: OK")

                # Replace corrupted database with recovered one
                logger.info(f"Replacing {db_path} with recovered database...")
                Path(db_path).unlink()
                shutil.move(recovered_path, db_path)

                logger.info("")
                logger.info("=" * 60)
                logger.info("DATABASE RECOVERY SUCCESSFUL!")
                logger.info("=" * 60)
                logger.info(f"Recovered {news_events_recovered:,} news events")
                logger.info(f"Recovered {files_processed_recovered:,} processed file records")
                logger.info(f"Backup saved at: {backup_path}")
                logger.info("")
                logger.info("You can now restart the GDELT collector:")
                logger.info("  nohup python3 gdelt_collector.py --continuous >> gdelt.out 2>&1 &")
                logger.info("")

                return True

            else:
                logger.error(f"Recovered database failed integrity check: {result}")
                return False

        except Exception as e:
            logger.error(f"Recovery failed: {e}", exc_info=True)
            if Path(recovered_path).exists():
                Path(recovered_path).unlink()
            return False

    except Exception as e:
        logger.error(f"Error during recovery: {e}", exc_info=True)
        return False

def main():
    """Main recovery routine."""
    import sys

    db_path = 'data/gdelt_news.db'

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    if not Path(db_path).exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    print("")
    print("=" * 60)
    print("GDELT DATABASE RECOVERY")
    print("=" * 60)
    print(f"Database: {db_path}")
    print("")
    print("This script will:")
    print("1. Create a backup of the corrupted database")
    print("2. Extract all recoverable data")
    print("3. Create a fresh database with the recovered data")
    print("4. Replace the corrupted database")
    print("")

    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        logger.info("Recovery cancelled")
        sys.exit(0)

    print("")
    success = recover_database(db_path)

    if not success:
        print("")
        print("=" * 60)
        print("RECOVERY FAILED")
        print("=" * 60)
        print("")
        print("The corrupted database has been backed up.")
        print("You may need to delete the database and start fresh:")
        print(f"  rm {db_path}")
        print("  python3 gdelt_collector.py --collect 30")
        print("")
        sys.exit(1)

if __name__ == "__main__":
    main()
