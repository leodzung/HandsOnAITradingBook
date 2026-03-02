#!/usr/bin/env python3
"""
Market Condition Mapper
Resolves token IDs to condition IDs by building a reverse lookup from Polymarket's Gamma API.
"""

import json
import sqlite3
import logging
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketConditionMapper:
    """
    Build and maintain a mapping from token_id to condition_id.

    Polymarket uses token IDs for trading but condition IDs for market identification.
    This mapper fetches all markets (active + closed) and builds a reverse lookup.
    """

    GAMMA_URL = "https://gamma-api.polymarket.com"

    def __init__(self, db_path: str = 'data/training_history.db',
                 rate_limit_per_sec: float = 1.0):
        """
        Initialize the market mapper.

        Args:
            db_path: Path to SQLite database
            rate_limit_per_sec: Maximum requests per second to Gamma API
        """
        self.db_path = db_path
        self.rate_limit_per_sec = rate_limit_per_sec
        self.min_request_interval = 1.0 / rate_limit_per_sec
        self.last_request_time = 0
        self.session = requests.Session()

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # In-memory cache for fast lookups
        self._token_cache: Dict[str, Tuple[str, int]] = {}
        self._load_cache()

    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Token-to-condition mapping
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_condition_map (
                token_id TEXT PRIMARY KEY,
                condition_id TEXT NOT NULL,
                outcome_index INTEGER,
                question TEXT,
                updated_at TEXT
            )
        ''')

        # Markets metadata cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS markets (
                condition_id TEXT PRIMARY KEY,
                question TEXT,
                description TEXT,
                category TEXT,
                end_date TEXT,
                created_at TEXT,
                closed_time TEXT,
                active INTEGER,
                resolved INTEGER,
                outcome_prices TEXT,
                volume REAL,
                liquidity REAL,
                tokens TEXT,
                updated_at TEXT
            )
        ''')

        # Index for fast lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_token_condition
            ON token_condition_map(condition_id)
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def _load_cache(self):
        """Load token mapping into memory cache."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT token_id, condition_id, outcome_index FROM token_condition_map")
        for row in cursor.fetchall():
            self._token_cache[row[0]] = (row[1], row[2])

        conn.close()
        logger.info(f"Loaded {len(self._token_cache)} token mappings into cache")

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()

    def fetch_markets_page(self, offset: int = 0, limit: int = 100,
                           closed: bool = True, active: bool = True) -> List[Dict]:
        """
        Fetch a page of markets from Gamma API.

        Args:
            offset: Pagination offset
            limit: Number of markets per page
            closed: Include closed markets
            active: Include active markets

        Returns:
            List of market dictionaries
        """
        self._rate_limit()

        params = {
            'limit': limit,
            'offset': offset
        }

        # Build filter
        if closed and not active:
            params['closed'] = 'true'
        elif active and not closed:
            params['active'] = 'true'
        # If both, don't filter (get all)

        try:
            response = self.session.get(
                f"{self.GAMMA_URL}/markets",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    def fetch_all_markets(self, include_closed: bool = True,
                          include_active: bool = True,
                          max_markets: int = 50000) -> List[Dict]:
        """
        Fetch all markets from Gamma API.

        Args:
            include_closed: Include resolved/closed markets
            include_active: Include active markets
            max_markets: Maximum number of markets to fetch

        Returns:
            List of all market dictionaries
        """
        all_markets = []
        offset = 0
        batch_size = 100

        logger.info("Fetching all markets from Gamma API...")

        while len(all_markets) < max_markets:
            markets = self.fetch_markets_page(
                offset=offset,
                limit=batch_size,
                closed=include_closed,
                active=include_active
            )

            if not markets:
                break

            all_markets.extend(markets)
            offset += batch_size

            if len(all_markets) % 500 == 0:
                logger.info(f"  Fetched {len(all_markets)} markets...")

        logger.info(f"Total markets fetched: {len(all_markets)}")
        return all_markets

    def extract_tokens_from_market(self, market: Dict) -> List[Tuple[str, int]]:
        """
        Extract token IDs from a market.

        Args:
            market: Market dictionary from API

        Returns:
            List of (token_id, outcome_index) tuples
        """
        tokens = market.get('tokens', [])
        clob_token_ids = market.get('clobTokenIds')

        results = []

        # Try tokens array first
        if tokens:
            for i, token in enumerate(tokens):
                if isinstance(token, dict):
                    token_id = token.get('token_id')
                elif isinstance(token, str):
                    token_id = token
                else:
                    continue

                if token_id:
                    results.append((token_id, i))

        # Fall back to clobTokenIds
        elif clob_token_ids:
            if isinstance(clob_token_ids, str):
                try:
                    clob_token_ids = json.loads(clob_token_ids)
                except:
                    clob_token_ids = []

            for i, token_id in enumerate(clob_token_ids):
                if token_id:
                    results.append((str(token_id), i))

        return results

    def build_mapping(self, markets: List[Dict] = None) -> int:
        """
        Build the token-to-condition mapping from markets.

        Args:
            markets: List of market dictionaries (fetches if not provided)

        Returns:
            Number of mappings created
        """
        if markets is None:
            markets = self.fetch_all_markets()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        mappings_created = 0
        now = datetime.now(timezone.utc).isoformat()

        for market in markets:
            condition_id = market.get('conditionId')
            if not condition_id:
                continue

            question = market.get('question', '')

            # Extract tokens
            tokens = self.extract_tokens_from_market(market)

            for token_id, outcome_index in tokens:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO token_condition_map
                        (token_id, condition_id, outcome_index, question, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (token_id, condition_id, outcome_index, question, now))
                    mappings_created += 1

                    # Update cache
                    self._token_cache[token_id] = (condition_id, outcome_index)

                except Exception as e:
                    logger.debug(f"Error storing mapping: {e}")

            # Store market metadata
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO markets
                    (condition_id, question, description, category, end_date,
                     created_at, closed_time, active, resolved, outcome_prices,
                     volume, liquidity, tokens, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    condition_id,
                    question,
                    market.get('description', '')[:1000],
                    market.get('category', ''),
                    market.get('endDate', ''),
                    market.get('createdAt', ''),
                    market.get('closedTime', ''),
                    1 if market.get('active') else 0,
                    1 if market.get('resolved') else 0,
                    json.dumps(market.get('outcomePrices', [])),
                    float(market.get('volume', 0) or 0),
                    float(market.get('liquidity', 0) or 0),
                    json.dumps([t[0] for t in tokens]),
                    now
                ))
            except Exception as e:
                logger.debug(f"Error storing market: {e}")

        conn.commit()
        conn.close()

        logger.info(f"Created {mappings_created} token-to-condition mappings")
        return mappings_created

    def get_condition_id(self, token_id: str) -> Optional[str]:
        """
        Get the condition_id for a token_id.

        Args:
            token_id: Token ID to look up

        Returns:
            Condition ID or None if not found
        """
        if token_id in self._token_cache:
            return self._token_cache[token_id][0]

        # Fall back to database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT condition_id FROM token_condition_map WHERE token_id = ?",
            (token_id,)
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def get_outcome_index(self, token_id: str) -> Optional[int]:
        """
        Get the outcome index (0=YES, 1=NO) for a token_id.

        Args:
            token_id: Token ID to look up

        Returns:
            Outcome index or None if not found
        """
        if token_id in self._token_cache:
            return self._token_cache[token_id][1]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT outcome_index FROM token_condition_map WHERE token_id = ?",
            (token_id,)
        )
        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def get_market(self, condition_id: str) -> Optional[Dict]:
        """Get cached market metadata."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM markets WHERE condition_id = ?",
            (condition_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        columns = [desc[0] for desc in cursor.description]
        conn.close()

        market = dict(zip(columns, row))

        # Parse JSON fields
        for field in ['outcome_prices', 'tokens']:
            if market.get(field):
                try:
                    market[field] = json.loads(market[field])
                except:
                    pass

        return market

    def get_resolved_markets(self) -> List[Dict]:
        """Get all resolved markets."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM markets
            WHERE resolved = 1 OR active = 0
            ORDER BY closed_time DESC
        """)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        markets = []
        for row in rows:
            market = dict(zip(columns, row))
            for field in ['outcome_prices', 'tokens']:
                if market.get(field):
                    try:
                        market[field] = json.loads(market[field])
                    except:
                        pass
            markets.append(market)

        return markets

    def update_trades_with_condition_ids(self) -> int:
        """
        Update on_chain_trades table with condition_ids from token mapping.

        Returns:
            Number of trades updated
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all unique token IDs from trades
        cursor.execute("""
            SELECT DISTINCT maker_asset_id FROM on_chain_trades
            WHERE condition_id IS NULL AND maker_asset_id IS NOT NULL
        """)
        token_ids = [row[0] for row in cursor.fetchall()]

        updated = 0
        for token_id in token_ids:
            condition_id = self.get_condition_id(token_id)
            if condition_id:
                cursor.execute("""
                    UPDATE on_chain_trades
                    SET condition_id = ?
                    WHERE maker_asset_id = ?
                """, (condition_id, token_id))
                updated += cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"Updated {updated} trades with condition_ids")
        return updated

    def get_statistics(self) -> Dict:
        """Get mapping statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total mappings
        cursor.execute("SELECT COUNT(*) FROM token_condition_map")
        stats["total_mappings"] = cursor.fetchone()[0]

        # Total markets
        cursor.execute("SELECT COUNT(*) FROM markets")
        stats["total_markets"] = cursor.fetchone()[0]

        # Active vs closed
        cursor.execute("SELECT active, COUNT(*) FROM markets GROUP BY active")
        for row in cursor.fetchall():
            key = "active_markets" if row[0] else "closed_markets"
            stats[key] = row[1]

        # Resolved markets
        cursor.execute("SELECT COUNT(*) FROM markets WHERE resolved = 1")
        stats["resolved_markets"] = cursor.fetchone()[0]

        # Cache size
        stats["cache_size"] = len(self._token_cache)

        conn.close()
        return stats


def main():
    """Main CLI interface."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Market Condition Mapper - Maps token IDs to condition IDs",
        epilog="Common workflow: python3 alchemy_collector.py --incremental && python3 market_mapper.py --update --update-trades"
    )
    parser.add_argument("--update", action="store_true", help="Update mappings from Gamma API")
    parser.add_argument("--lookup", help="Look up condition_id for a token_id")
    parser.add_argument("--update-trades", action="store_true", help="Update on_chain_trades with condition_ids")
    parser.add_argument("--stats", action="store_true", help="Show statistics")

    # Convenient combined flag
    parser.add_argument("--map-all", action="store_true",
                       help="Convenience: Update mappings AND update trades (combines --update --update-trades)")

    args = parser.parse_args()

    # Load config - check for db_path in config if it exists
    config_path = Path("config/config.json")
    db_path = 'data/alchemy_trades.db'  # Default to alchemy_trades.db for standalone usage

    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                # Use alchemy_trades.db if available in config
                db_path = config.get('alchemy_db_path', db_path)
        except:
            pass

    mapper = MarketConditionMapper(db_path=db_path)

    # Handle --map-all convenience flag
    if args.map_all:
        args.update = True
        args.update_trades = True

    if args.stats:
        stats = mapper.get_statistics()
        print("\n=== Market Mapper Statistics ===")
        for key, value in stats.items():
            print(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")

        # Also show trade mapping coverage if on_chain_trades table exists
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) as mapped
                FROM on_chain_trades
            """)
            result = cursor.fetchone()
            conn.close()

            if result and result[0] > 0:
                total, mapped = result
                coverage = 100.0 * mapped / total if total > 0 else 0
                print(f"\nTrade Mapping Coverage:")
                print(f"  Total trades in DB: {total:,}")
                print(f"  Mapped trades: {mapped:,}")
                print(f"  Coverage: {coverage:.1f}%")
        except:
            pass

        return

    if args.lookup:
        condition_id = mapper.get_condition_id(args.lookup)
        outcome_idx = mapper.get_outcome_index(args.lookup)
        if condition_id:
            print(f"Token ID: {args.lookup}")
            print(f"Condition ID: {condition_id}")
            print(f"Outcome Index: {outcome_idx} ({'YES' if outcome_idx == 0 else 'NO'})")
            market = mapper.get_market(condition_id)
            if market:
                print(f"Question: {market.get('question', '')[:100]}")
        else:
            print(f"Token ID {args.lookup} not found in mapping")
        return

    if args.update:
        logger.info("Updating token-to-condition mappings from Gamma API...")
        count = mapper.build_mapping()
        logger.info(f"✓ Built {count} token mappings")

    if args.update_trades:
        logger.info("Updating on_chain_trades table with condition_ids...")
        updated = mapper.update_trades_with_condition_ids()
        logger.info(f"✓ Updated {updated} trades")

        # Show coverage stats
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN condition_id IS NOT NULL THEN 1 END) as mapped
                FROM on_chain_trades
            """)
            result = cursor.fetchone()
            conn.close()

            if result and result[0] > 0:
                total, mapped = result
                coverage = 100.0 * mapped / total if total > 0 else 0
                logger.info(f"Coverage: {mapped}/{total} trades ({coverage:.1f}%)")
        except:
            pass


if __name__ == "__main__":
    main()
