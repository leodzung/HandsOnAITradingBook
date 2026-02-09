#!/usr/bin/env python3
"""
GDELT Historical News Collector
Collects crypto news from the GDELT Project.

GDELT (Global Database of Events, Language, and Tone) provides free access to
global news coverage updated every 15 minutes since 2015.

MODES:
  Continuous (production):  python3 gdelt_collector.py --continuous
  Historical backfill:      python3 gdelt_collector.py --collect 30
  Single update:            python3 gdelt_collector.py --recent

For production deployment, use continuous mode with nohup:
  nohup python3 gdelt_collector.py --continuous >> gdelt.out 2>&1 &
"""

import io
import gzip
import sqlite3
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from pathlib import Path
from urllib.parse import urljoin
import time
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GDELTCollector:
    """
    Collect historical news events from GDELT Project.

    GDELT provides:
    - GKG (Global Knowledge Graph): Entity and theme extraction
    - Events: Structured event records
    - Mentions: Raw article URLs and metadata

    We use the GKG for crypto-related news filtering.
    """

    # GDELT data URLs
    GKG_MASTERLIST_URL = "http://data.gdeltproject.org/gdeltv2/masterfilelist.txt"
    GKG_LAST_UPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

    # Crypto keywords for filtering
    CRYPTO_KEYWORDS = {
        'bitcoin', 'btc', 'ethereum', 'eth', 'cryptocurrency', 'crypto',
        'blockchain', 'coinbase', 'binance', 'solana', 'dogecoin',
        'ripple', 'xrp', 'cardano', 'polygon', 'defi', 'nft',
        'satoshi', 'vitalik', 'stablecoin', 'usdt', 'usdc'
    }

    # Crypto-related GDELT themes
    CRYPTO_THEMES = {
        'ECON_CRYPTOCURRENCY', 'ECON_BITCOIN', 'TECH_BLOCKCHAIN',
        'CRISISLEX_FINANCIAL', 'ECON_STOCKMARKET'
    }

    def __init__(self, db_path: str = 'data/gdelt_news.db',
                 rate_limit_per_sec: float = 2.0):
        """
        Initialize the GDELT collector.

        Args:
            db_path: Path to SQLite database (default: separate DB to avoid conflicts)
            rate_limit_per_sec: Maximum requests per second
        """
        self.db_path = db_path
        self.rate_limit_per_sec = rate_limit_per_sec
        self.min_request_interval = 1.0 / rate_limit_per_sec
        self.last_request_time = 0
        self.session = requests.Session()
        self.is_running = False  # For continuous mode

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Prevent macOS system processes from accessing the database
        noindex_file = Path(db_path).parent / '.noindex'
        noindex_file.touch(exist_ok=True)

        # Check database integrity before initializing
        if Path(self.db_path).exists():
            if not self._check_integrity():
                logger.error("Database integrity check failed!")
                if not self._attempt_recovery():
                    logger.error("Recovery failed. Database needs manual repair.")
                    raise RuntimeError("Database corrupted and recovery failed")

        self._init_db()

    def _init_db(self):
        """Initialize database tables for news events."""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()

                # Use DELETE journal mode (more compatible with macOS than WAL)
                cursor.execute("PRAGMA journal_mode=DELETE")
                # Set busy timeout to wait up to 30 seconds for locks
                cursor.execute("PRAGMA busy_timeout=30000")
                # Set synchronous mode to FULL for maximum safety (prevents corruption)
                cursor.execute("PRAGMA synchronous=FULL")
                # Disable auto-vacuum (can cause corruption on some systems)
                cursor.execute("PRAGMA auto_vacuum=NONE")

                # News events table
                cursor.execute('''
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

                # GDELT file tracking (to avoid reprocessing)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gdelt_files_processed (
                        filename TEXT PRIMARY KEY,
                        processed_at TEXT,
                        events_found INTEGER
                    )
                ''')

                # Indexes
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_news_timestamp
                    ON news_events(timestamp)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_news_source
                    ON news_events(source)
                ''')

                conn.commit()
            logger.info(f"Database initialized: {self.db_path}")
        except sqlite3.DatabaseError as e:
            logger.error(f"Database initialization failed: {e}")
            logger.error("Database may be corrupted. Run recovery procedure.")
            raise

    def _check_integrity(self) -> bool:
        """Check database integrity."""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result and result[0] == 'ok':
                    logger.info("Database integrity check: OK")
                    return True
                else:
                    logger.error(f"Database integrity check failed: {result}")
                    return False
        except Exception as e:
            logger.error(f"Error checking database integrity: {e}")
            return False

    def _attempt_recovery(self) -> bool:
        """
        Attempt to recover corrupted database.

        Strategy:
        1. Create backup of corrupted database
        2. Try to dump readable data to SQL
        3. Create new database and restore data
        """
        from pathlib import Path
        import shutil

        backup_path = f"{self.db_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Attempting database recovery...")
        logger.info(f"Creating backup: {backup_path}")

        try:
            # Backup corrupted database
            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Backup created: {backup_path}")

            # Try to recover data by dumping and recreating
            recovered_path = f"{self.db_path}.recovered"

            try:
                # Open corrupted database in recovery mode
                with sqlite3.connect(self.db_path, timeout=30.0) as old_conn:
                    old_conn.execute("PRAGMA writable_schema=ON")

                    # Try to get recoverable data
                    cursor = old_conn.cursor()

                    # Create new database
                    with sqlite3.connect(recovered_path, timeout=30.0) as new_conn:
                        new_cursor = new_conn.cursor()

                        # Set up new database (use DELETE mode for macOS compatibility)
                        new_cursor.execute("PRAGMA journal_mode=DELETE")
                        new_cursor.execute("PRAGMA synchronous=FULL")

                        # Create tables
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

                        # Try to recover news_events
                        try:
                            cursor.execute("SELECT * FROM news_events")
                            rows = cursor.fetchall()
                            logger.info(f"Recovering {len(rows)} news events...")

                            for row in rows:
                                try:
                                    new_cursor.execute('''
                                        INSERT OR IGNORE INTO news_events
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', row)
                                except:
                                    continue

                            new_conn.commit()
                            logger.info(f"Recovered {len(rows)} news events")
                        except Exception as e:
                            logger.warning(f"Could not recover news_events: {e}")

                        # Try to recover gdelt_files_processed
                        try:
                            cursor.execute("SELECT * FROM gdelt_files_processed")
                            rows = cursor.fetchall()
                            logger.info(f"Recovering {len(rows)} processed files records...")

                            for row in rows:
                                try:
                                    new_cursor.execute('''
                                        INSERT OR IGNORE INTO gdelt_files_processed
                                        VALUES (?, ?, ?)
                                    ''', row)
                                except:
                                    continue

                            new_conn.commit()
                            logger.info(f"Recovered {len(rows)} processed files records")
                        except Exception as e:
                            logger.warning(f"Could not recover gdelt_files_processed: {e}")

                        # Create indexes
                        new_cursor.execute('''
                            CREATE INDEX IF NOT EXISTS idx_news_timestamp
                            ON news_events(timestamp)
                        ''')
                        new_cursor.execute('''
                            CREATE INDEX IF NOT EXISTS idx_news_source
                            ON news_events(source)
                        ''')
                        new_conn.commit()

                # Replace corrupted database with recovered one
                Path(self.db_path).unlink()
                shutil.move(recovered_path, self.db_path)

                logger.info("Database recovery successful!")
                return True

            except Exception as e:
                logger.error(f"Recovery failed: {e}")
                if Path(recovered_path).exists():
                    Path(recovered_path).unlink()
                return False

        except Exception as e:
            logger.error(f"Error during recovery: {e}")
            return False

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def get_gkg_file_list(self, start_date: datetime, end_date: datetime) -> List[str]:
        """
        Get list of GKG files for a date range.

        GDELT GKG files are named: YYYYMMDDHHMMSS.gkg.csv.zip
        Updated every 15 minutes.

        Args:
            start_date: Start datetime
            end_date: End datetime

        Returns:
            List of file URLs
        """
        self._rate_limit()

        try:
            response = self.session.get(self.GKG_MASTERLIST_URL, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GDELT masterlist: {e}")
            return []

        # Parse masterlist (format: size md5 url)
        files = []
        for line in response.text.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and '.gkg.csv' in parts[2]:
                url = parts[2]
                # Extract date from filename
                filename = url.split('/')[-1]
                try:
                    # Format: YYYYMMDDHHMMSS.gkg.csv.zip
                    file_date = datetime.strptime(
                        filename[:14], '%Y%m%d%H%M%S'
                    ).replace(tzinfo=timezone.utc)

                    if start_date <= file_date <= end_date:
                        files.append(url)
                except:
                    continue

        logger.info(f"Found {len(files)} GKG files in date range")
        return files

    def download_and_parse_gkg(self, url: str) -> List[Dict]:
        """
        Download and parse a GKG file.

        GKG columns include:
        - GKGRECORDID, DATE, SourceCollectionIdentifier, SourceCommonName
        - DocumentIdentifier (URL), Themes, Locations, Persons, Organizations
        - V2Tone (sentiment), V2EnhancedThemes, etc.

        Returns:
            List of crypto-related event dictionaries
        """
        self._rate_limit()

        try:
            response = self.session.get(url, timeout=120)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading {url}: {e}")
            return []

        events = []

        try:
            # Decompress and parse
            if url.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                    for name in z.namelist():
                        if name.endswith('.csv'):
                            with z.open(name) as f:
                                events.extend(self._parse_gkg_content(f.read().decode('utf-8', errors='ignore')))
            elif url.endswith('.gz'):
                content = gzip.decompress(response.content).decode('utf-8', errors='ignore')
                events.extend(self._parse_gkg_content(content))
            else:
                events.extend(self._parse_gkg_content(response.text))

        except Exception as e:
            logger.error(f"Error parsing GKG file {url}: {e}")

        return events

    def _parse_gkg_content(self, content: str) -> List[Dict]:
        """Parse GKG CSV content and filter for crypto events."""
        events = []

        # GKG is tab-separated with specific column order
        # Key columns: [1]=DATE, [3]=SourceCommonName, [4]=DocumentIdentifier,
        # [7]=Themes, [9]=Persons, [10]=Organizations, [11]=Locations, [15]=V2Tone

        for line in content.strip().split('\n'):
            try:
                cols = line.split('\t')
                if len(cols) < 16:
                    continue

                # Extract fields
                date_str = cols[1] if len(cols) > 1 else ''
                source = cols[3] if len(cols) > 3 else ''
                url = cols[4] if len(cols) > 4 else ''
                themes_str = cols[7] if len(cols) > 7 else ''
                persons = cols[9] if len(cols) > 9 else ''
                orgs = cols[10] if len(cols) > 10 else ''
                locations = cols[11] if len(cols) > 11 else ''
                tone_str = cols[15] if len(cols) > 15 else ''

                # Check if crypto-related
                themes = set(themes_str.lower().split(';')) if themes_str else set()
                text_to_check = f"{source} {url} {themes_str}".lower()

                is_crypto = (
                    any(kw in text_to_check for kw in self.CRYPTO_KEYWORDS) or
                    any(theme in themes for theme in [t.lower() for t in self.CRYPTO_THEMES])
                )

                if not is_crypto:
                    continue

                # Parse date
                try:
                    if len(date_str) >= 14:
                        timestamp = datetime.strptime(
                            date_str[:14], '%Y%m%d%H%M%S'
                        ).replace(tzinfo=timezone.utc)
                    else:
                        timestamp = datetime.strptime(
                            date_str[:8], '%Y%m%d'
                        ).replace(tzinfo=timezone.utc)
                except:
                    continue

                # Parse tone (format: tone,positive,negative,polarity,...)
                tone = 0.0
                if tone_str:
                    try:
                        tone = float(tone_str.split(',')[0])
                    except:
                        pass

                # Extract keywords found
                found_keywords = [kw for kw in self.CRYPTO_KEYWORDS if kw in text_to_check]

                events.append({
                    'source_url': url,
                    'title': '',  # GKG doesn't have titles, would need to fetch
                    'description': '',
                    'source': source,
                    'timestamp': timestamp.isoformat(),
                    'themes': themes_str,
                    'persons': persons,
                    'organizations': orgs,
                    'locations': locations,
                    'tone': tone,
                    'keywords': ','.join(found_keywords),
                    'gdelt_date': date_str[:8]
                })

            except Exception as e:
                continue

        return events

    def store_events(self, events: List[Dict]) -> int:
        """Store events in the database with batch commits for safety."""
        if not events:
            return 0

        stored = 0
        now = datetime.now(timezone.utc).isoformat()
        batch_size = 50  # Smaller batches for more frequent commits

        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()

                for i, event in enumerate(events):
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO news_events
                            (source_url, title, description, source, timestamp,
                             themes, persons, organizations, locations, tone,
                             keywords, gdelt_date, collected_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            event['source_url'],
                            event.get('title', ''),
                            event.get('description', ''),
                            event['source'],
                            event['timestamp'],
                            event.get('themes', ''),
                            event.get('persons', ''),
                            event.get('organizations', ''),
                            event.get('locations', ''),
                            event.get('tone', 0),
                            event.get('keywords', ''),
                            event.get('gdelt_date', ''),
                            now
                        ))
                        if cursor.rowcount > 0:
                            stored += 1

                        # Batch commit for crash resilience
                        if (i + 1) % batch_size == 0:
                            conn.commit()

                    except sqlite3.IntegrityError:
                        # Duplicate entry, skip
                        continue
                    except Exception as e:
                        logger.debug(f"Error storing event: {e}")
                        continue

                # Final commit for remaining events
                conn.commit()

        except sqlite3.DatabaseError as e:
            logger.error(f"Database error in store_events: {e}")
            logger.error("Database may be corrupted. Stored {} events before error.".format(stored))
            # Re-raise corruption errors so run_continuous can handle them
            error_msg = str(e).lower()
            if 'malformed' in error_msg or 'corrupted' in error_msg or 'not a database' in error_msg:
                raise
            # Don't raise for other database errors - allow partial success
        except Exception as e:
            logger.error(f"Unexpected error in store_events: {e}")

        return stored

    def mark_file_processed(self, filename: str, events_found: int):
        """Mark a GDELT file as processed."""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO gdelt_files_processed
                    (filename, processed_at, events_found)
                    VALUES (?, ?, ?)
                ''', (filename, datetime.now(timezone.utc).isoformat(), events_found))
                conn.commit()
        except sqlite3.DatabaseError as e:
            logger.error(f"Error marking file as processed: {e}")
            # Don't raise - this is not critical

    def is_file_processed(self, filename: str) -> bool:
        """Check if a GDELT file has been processed."""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM gdelt_files_processed WHERE filename = ?",
                    (filename,)
                )
                result = cursor.fetchone()
                return result is not None
        except sqlite3.DatabaseError as e:
            logger.error(f"Error checking if file processed: {e}")
            return False  # Assume not processed on error

    def collect_crypto_news(self, days_back: int = 180,
                            max_files: int = None) -> int:
        """
        Collect crypto news from GDELT for the past N days.

        Args:
            days_back: Number of days to collect
            max_files: Maximum number of GKG files to process (default: auto-calculated from days_back)

        Returns:
            Total number of events collected
        """
        # GDELT publishes 96 files/day (every 15 min). Auto-calculate limit if not specified.
        if max_files is None:
            max_files = days_back * 96 + 100  # Add buffer for safety

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)

        logger.info(f"Collecting crypto news from {start_date.date()} to {end_date.date()}")

        # Get file list
        files = self.get_gkg_file_list(start_date, end_date)

        if not files:
            logger.warning("No GDELT files found for date range")
            return 0

        # Limit files
        files = files[:max_files]
        logger.info(f"Processing {len(files)} GKG files...")

        total_events = 0
        processed = 0

        for i, url in enumerate(files):
            filename = url.split('/')[-1]

            # Skip if already processed
            if self.is_file_processed(filename):
                continue

            # Download and parse
            events = self.download_and_parse_gkg(url)

            # Store events
            stored = self.store_events(events)
            total_events += stored

            # Mark as processed
            self.mark_file_processed(filename, len(events))
            processed += 1

            if processed % 10 == 0:
                logger.info(f"  Processed {processed}/{len(files)} files, {total_events} events collected")

        logger.info(f"Collection complete: {total_events} crypto events from {processed} files")
        return total_events

    def collect_recent(self) -> int:
        """
        Collect news from the last update (15-minute interval).

        Returns:
            Number of events collected
        """
        self._rate_limit()

        try:
            response = self.session.get(self.GKG_LAST_UPDATE_URL, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching last update: {e}")
            return 0

        # Parse last update file (same format as masterlist)
        total_stored = 0
        for line in response.text.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3 and '.gkg.csv' in parts[2]:
                url = parts[2]
                filename = url.split('/')[-1]

                if self.is_file_processed(filename):
                    continue

                events = self.download_and_parse_gkg(url)
                stored = self.store_events(events)
                self.mark_file_processed(filename, len(events))

                logger.info(f"Collected {stored} events from {filename}")
                total_stored += stored

        if total_stored > 0:
            logger.info(f"Total: {total_stored} new events from latest update")

        return total_stored

    def _checkpoint_db(self):
        """Force database checkpoint to ensure data is persisted."""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                # In DELETE mode, no WAL checkpoint needed, just ensure commit
                cursor.execute("PRAGMA optimize")
                logger.debug("Database checkpoint completed")
        except Exception as e:
            logger.warning(f"Database checkpoint failed: {e}")

    def run_continuous(self, interval_seconds: int = 60):
        """
        Run collector continuously with periodic updates.

        Similar to trader.py pattern - runs indefinitely until stopped.

        Args:
            interval_seconds: Seconds between collection cycles (default: 60)
        """
        logger.info(f"Starting continuous GDELT collection (every {interval_seconds} sec)")
        logger.info("Press Ctrl+C to stop gracefully")

        self.is_running = True
        collection_count = 0

        while self.is_running:
            try:
                collection_count += 1
                logger.info(f"--- Collection cycle #{collection_count} ---")

                # Collect latest updates
                events = self.collect_recent()

                if events == 0:
                    logger.info("No new events (all files already processed)")

                # Checkpoint database every 5 cycles
                if collection_count % 5 == 0:
                    logger.info("Performing database checkpoint...")
                    self._checkpoint_db()

                # Check integrity every 20 cycles (~5 hours at 15-min intervals)
                if collection_count % 20 == 0:
                    logger.info("Performing periodic integrity check...")
                    if not self._check_integrity():
                        logger.error("Integrity check failed! Attempting recovery...")
                        if self._attempt_recovery():
                            logger.info("Recovery successful, continuing...")
                        else:
                            logger.error("Recovery failed, stopping collector")
                            self.stop()
                            break

                # Wait for next cycle
                logger.info(f"Next collection in {interval_seconds} seconds...")
                time.sleep(interval_seconds)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.stop()
            except sqlite3.DatabaseError as e:
                logger.error(f"Database error in collection cycle: {e}")
                error_msg = str(e).lower()
                if 'malformed' in error_msg or 'corrupted' in error_msg or 'not a database' in error_msg:
                    logger.error("Database corruption detected! Attempting recovery...")
                    if self._attempt_recovery():
                        logger.info("Recovery successful, continuing...")
                        time.sleep(5)  # Short delay before continuing
                    else:
                        logger.error("Recovery failed, stopping collector")
                        self.stop()
                        break
                else:
                    logger.info("Retrying in 1 minute...")
                    time.sleep(60)
            except Exception as e:
                logger.error(f"Error in collection cycle: {e}", exc_info=True)
                logger.info("Retrying in 1 minute...")
                time.sleep(60)

    def stop(self):
        """Stop the continuous collector."""
        logger.info("Stopping GDELT collector...")
        self.is_running = False
        logger.info("GDELT collector stopped")

    def get_events_for_timerange(self, start_time: datetime,
                                  end_time: datetime) -> List[Dict]:
        """Get stored events for a time range."""
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM news_events
                    WHERE timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                """, (start_time.isoformat(), end_time.isoformat()))

                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]
        except sqlite3.DatabaseError as e:
            logger.error(f"Error fetching events: {e}")
            return []

    def get_statistics(self) -> Dict:
        """Get collection statistics."""
        stats = {}
        try:
            with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                cursor = conn.cursor()

                # Total events
                cursor.execute("SELECT COUNT(*) FROM news_events")
                stats['total_events'] = cursor.fetchone()[0]

                # Date range
                cursor.execute("""
                    SELECT MIN(timestamp), MAX(timestamp)
                    FROM news_events
                """)
                result = cursor.fetchone()
                stats['earliest_event'] = result[0]
                stats['latest_event'] = result[1]

                # Files processed
                cursor.execute("SELECT COUNT(*) FROM gdelt_files_processed")
                stats['files_processed'] = cursor.fetchone()[0]

                # Events by source
                cursor.execute("""
                    SELECT source, COUNT(*) as count
                    FROM news_events
                    GROUP BY source
                    ORDER BY count DESC
                    LIMIT 10
                """)
                stats['top_sources'] = dict(cursor.fetchall())

                # Events by keyword
                cursor.execute("""
                    SELECT keywords, COUNT(*) as count
                    FROM news_events
                    WHERE keywords != ''
                    GROUP BY keywords
                    ORDER BY count DESC
                    LIMIT 10
                """)
                stats['top_keywords'] = dict(cursor.fetchall())

                # Average tone
                cursor.execute("SELECT AVG(tone) FROM news_events")
                avg_tone = cursor.fetchone()[0]
                stats['avg_tone'] = avg_tone if avg_tone is not None else 0.0

        except sqlite3.DatabaseError as e:
            logger.error(f"Error fetching statistics: {e}")
            stats['error'] = str(e)

        return stats


def main():
    """Main collection routine."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GDELT News Collector",
        epilog="Examples:\n"
               "  Backfill historical data:  python3 gdelt_collector.py --collect 30\n"
               "  Single update:             python3 gdelt_collector.py --recent\n"
               "  Continuous mode:           python3 gdelt_collector.py --continuous\n"
               "  With nohup:                nohup python3 gdelt_collector.py --continuous >> gdelt.out 2>&1 &",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--collect", type=int, metavar="DAYS",
                        help="Collect N days of historical news (one-time backfill)")
    parser.add_argument("--recent", action="store_true",
                        help="Collect most recent update (one-time)")
    parser.add_argument("--continuous", action="store_true",
                        help="Run continuously, collecting updates every 60 seconds (recommended for production)")
    parser.add_argument("--interval", type=int, default=60, metavar="SECONDS",
                        help="Seconds between updates in continuous mode (default: 60)")
    parser.add_argument("--stats", action="store_true",
                        help="Show collection statistics")
    parser.add_argument("--export", metavar="FILE",
                        help="Export events to CSV file")
    args = parser.parse_args()

    collector = GDELTCollector()

    if args.stats:
        stats = collector.get_statistics()
        print("\n=== GDELT Collection Statistics ===")
        print(f"Total events: {stats['total_events']:,}")
        print(f"Date range: {stats['earliest_event']} to {stats['latest_event']}")
        print(f"Files processed: {stats['files_processed']:,}")
        print(f"Average tone: {stats.get('avg_tone', 0):.2f}")
        print(f"\nTop sources:")
        for source, count in list(stats.get('top_sources', {}).items())[:5]:
            print(f"  {source}: {count:,}")
        print(f"\nTop keyword combinations:")
        for kw, count in list(stats.get('top_keywords', {}).items())[:5]:
            print(f"  {kw}: {count:,}")
        return

    if args.continuous:
        # Continuous mode - runs forever until stopped
        collector.run_continuous(interval_seconds=args.interval)
        return

    if args.collect:
        # One-time historical backfill
        collector.collect_crypto_news(days_back=args.collect)
        return

    if args.recent:
        # One-time recent update
        collector.collect_recent()
        return

    if args.export:
        conn = sqlite3.connect(collector.db_path)
        df = pd.read_sql_query("SELECT * FROM news_events ORDER BY timestamp", conn)
        conn.close()
        df.to_csv(args.export, index=False)
        logger.info(f"Exported {len(df)} events to {args.export}")
        return

    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()
