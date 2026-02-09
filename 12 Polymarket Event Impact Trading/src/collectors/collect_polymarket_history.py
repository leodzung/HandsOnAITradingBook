#!/usr/bin/env python3
"""
Collect Historical Polymarket Data
Gathers resolved markets with outcomes for model validation.
"""

import requests
import json
import re
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PolymarketHistoryCollector:
    """Collect and store historical Polymarket data."""

    GAMMA_URL = "https://gamma-api.polymarket.com"
    CLOB_URL = "https://clob.polymarket.com"

    def __init__(self, db_path: str = 'data/polymarket_history.db'):
        """Initialize collector."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Resolved markets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resolved_markets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT UNIQUE,
                question TEXT,
                description TEXT,
                category TEXT,
                end_date TEXT,
                resolved_outcome TEXT,
                outcome_prices TEXT,
                volume REAL,
                liquidity REAL,
                created_at TEXT,
                closed_at TEXT,
                asset TEXT,
                strike_price REAL,
                direction TEXT,
                market_type TEXT,
                collected_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Price snapshots table (for ongoing collection)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT,
                token_id TEXT,
                timestamp TEXT,
                price REAL,
                bid REAL,
                ask REAL,
                volume_24h REAL,
                UNIQUE(condition_id, timestamp)
            )
        ''')

        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT,
                token_id TEXT,
                trade_id TEXT UNIQUE,
                timestamp TEXT,
                price REAL,
                size REAL,
                side TEXT
            )
        ''')

        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")

    def collect_resolved_markets(self, max_markets: int = 2000) -> int:
        """
        Collect all resolved markets from Polymarket.

        Args:
            max_markets: Maximum number of markets to fetch

        Returns:
            Number of markets collected
        """
        logger.info("Collecting resolved markets from Polymarket API...")

        all_markets = []
        offset = 0
        batch_size = 100

        while len(all_markets) < max_markets:
            try:
                response = requests.get(
                    f"{self.GAMMA_URL}/markets",
                    params={
                        'closed': 'true',
                        'limit': batch_size,
                        'offset': offset
                    },
                    timeout=30
                )
                response.raise_for_status()
                markets = response.json()

                if not markets:
                    break

                all_markets.extend(markets)
                offset += batch_size
                logger.info(f"  Fetched {len(all_markets)} markets...")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                logger.error(f"Error fetching markets: {e}")
                break

        # Process and store markets
        stored = 0
        for market in all_markets:
            if self._process_and_store_market(market):
                stored += 1

        logger.info(f"Stored {stored} resolved markets")
        return stored

    def _process_and_store_market(self, market: Dict) -> bool:
        """Process a market and store if it has resolution."""

        # Extract outcome from outcomePrices
        prices = market.get('outcomePrices', '[]')
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except:
                return False

        if not prices or len(prices) < 2:
            return False

        try:
            p0, p1 = float(prices[0]), float(prices[1])
        except:
            return False

        # Determine resolved outcome
        if p0 >= 0.99 and p1 <= 0.01:
            resolved_outcome = 'Yes'
        elif p1 >= 0.99 and p0 <= 0.01:
            resolved_outcome = 'No'
        else:
            return False  # Not clearly resolved

        # Parse market details
        question = market.get('question', '')
        market_type, asset, strike_price, direction = self._parse_price_level_market(question)

        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO resolved_markets
                (condition_id, question, description, category, end_date,
                 resolved_outcome, outcome_prices, volume, liquidity,
                 created_at, closed_at, asset, strike_price, direction, market_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market.get('conditionId'),
                question,
                market.get('description', '')[:500],
                market.get('category', ''),
                market.get('endDate', ''),
                resolved_outcome,
                json.dumps(prices),
                float(market.get('volume', 0) or 0),
                float(market.get('liquidity', 0) or 0),
                market.get('createdAt', ''),
                market.get('closedTime', ''),
                asset,
                strike_price,
                direction,
                market_type
            ))
            conn.commit()
            return True
        except Exception as e:
            logger.debug(f"Error storing market: {e}")
            return False
        finally:
            conn.close()

    def _parse_price_level_market(self, question: str) -> Tuple[str, str, float, str]:
        """
        Parse a market question to extract price-level details.

        Returns:
            (market_type, asset, strike_price, direction)
        """
        q = question.lower()

        # Determine asset
        asset = None
        if 'bitcoin' in q or 'btc' in q:
            asset = 'BTC'
        elif 'ethereum' in q or 'eth' in q:
            asset = 'ETH'
        elif 'solana' in q or 'sol' in q:
            asset = 'SOL'

        # Extract price
        strike_price = None
        price_patterns = [
            r'\$([0-9,]+(?:\.[0-9]+)?)[k]?\b',  # $50k, $1,500
            r'([0-9,]+(?:\.[0-9]+)?)\s*(?:dollars|usd)',
            r'above\s+\$?([0-9,]+)',
            r'below\s+\$?([0-9,]+)',
            r'hit\s+\$?([0-9,]+)',
            r'reach\s+\$?([0-9,]+)',
            r'break\s+\$?([0-9,]+)',
        ]

        for pattern in price_patterns:
            match = re.search(pattern, q)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    strike_price = float(price_str)
                    # Handle 'k' suffix
                    if 'k' in q[match.end():match.end()+2]:
                        strike_price *= 1000
                    break
                except:
                    pass

        # Determine direction
        direction = None
        if 'above' in q or 'hit' in q or 'reach' in q or 'break' in q:
            direction = 'ABOVE'
        elif 'below' in q or 'dip' in q or 'drop' in q:
            direction = 'BELOW'

        # Determine market type
        if asset and strike_price:
            market_type = 'price_level'
        elif asset:
            market_type = 'crypto_other'
        else:
            market_type = 'other'

        return market_type, asset, strike_price, direction

    def collect_active_markets(self) -> int:
        """
        Collect currently active markets for ongoing tracking.

        Returns:
            Number of markets collected
        """
        logger.info("Collecting active markets...")

        try:
            response = requests.get(
                f"{self.GAMMA_URL}/markets",
                params={
                    'active': 'true',
                    'limit': 500
                },
                timeout=30
            )
            response.raise_for_status()
            markets = response.json()

            # Filter for crypto price-level markets
            crypto_markets = []
            for m in markets:
                market_type, asset, strike, direction = self._parse_price_level_market(
                    m.get('question', '')
                )
                if market_type == 'price_level':
                    m['_parsed'] = {
                        'asset': asset,
                        'strike': strike,
                        'direction': direction
                    }
                    crypto_markets.append(m)

            logger.info(f"Found {len(crypto_markets)} active crypto price-level markets")

            # Collect price snapshots
            for m in crypto_markets:
                self._collect_price_snapshot(m)

            return len(crypto_markets)

        except Exception as e:
            logger.error(f"Error collecting active markets: {e}")
            return 0

    def _collect_price_snapshot(self, market: Dict):
        """Collect current price snapshot for a market."""

        condition_id = market.get('conditionId')
        tokens = market.get('tokens', [])

        if not tokens:
            return

        # Get token ID
        token_id = None
        if isinstance(tokens[0], dict):
            token_id = tokens[0].get('token_id')
        elif isinstance(tokens[0], str):
            token_id = tokens[0]

        if not token_id:
            return

        # Get orderbook
        try:
            response = requests.get(
                f"{self.CLOB_URL}/book",
                params={'token_id': token_id},
                timeout=10
            )
            if response.status_code != 200:
                return

            book = response.json()
            bids = book.get('bids', [])
            asks = book.get('asks', [])

            if not bids or not asks:
                return

            best_bid = float(bids[0]['price'])
            best_ask = float(asks[0]['price'])
            mid_price = (best_bid + best_ask) / 2

            # Store snapshot
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR IGNORE INTO price_snapshots
                (condition_id, token_id, timestamp, price, bid, ask, volume_24h)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                condition_id,
                token_id,
                datetime.now(timezone.utc).isoformat(),
                mid_price,
                best_bid,
                best_ask,
                float(market.get('volume24hr', 0) or 0)
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.debug(f"Error collecting snapshot: {e}")

    def get_resolved_crypto_markets(self) -> List[Dict]:
        """Get all resolved crypto price-level markets from database."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM resolved_markets
            WHERE market_type = 'price_level'
            ORDER BY end_date DESC
        ''')

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        return [dict(zip(columns, row)) for row in rows]

    def get_statistics(self) -> Dict:
        """Get collection statistics."""

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Total resolved markets
        cursor.execute('SELECT COUNT(*) FROM resolved_markets')
        stats['total_resolved'] = cursor.fetchone()[0]

        # By market type
        cursor.execute('''
            SELECT market_type, COUNT(*) as count
            FROM resolved_markets
            GROUP BY market_type
        ''')
        stats['by_type'] = dict(cursor.fetchall())

        # By outcome
        cursor.execute('''
            SELECT resolved_outcome, COUNT(*) as count
            FROM resolved_markets
            WHERE market_type = 'price_level'
            GROUP BY resolved_outcome
        ''')
        stats['price_level_outcomes'] = dict(cursor.fetchall())

        # By asset
        cursor.execute('''
            SELECT asset, COUNT(*) as count
            FROM resolved_markets
            WHERE asset IS NOT NULL
            GROUP BY asset
        ''')
        stats['by_asset'] = dict(cursor.fetchall())

        # Price snapshots
        cursor.execute('SELECT COUNT(*) FROM price_snapshots')
        stats['price_snapshots'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def export_for_training(self, output_path: str = 'data/polymarket_resolved.csv'):
        """Export resolved price-level markets to CSV for training."""

        import pandas as pd

        markets = self.get_resolved_crypto_markets()

        if not markets:
            logger.warning("No resolved markets to export")
            return

        df = pd.DataFrame(markets)
        df.to_csv(output_path, index=False)
        logger.info(f"Exported {len(df)} markets to {output_path}")

        return df


def main():
    """Main collection routine."""

    logger.info("="*70)
    logger.info("POLYMARKET HISTORICAL DATA COLLECTION")
    logger.info("="*70)

    collector = PolymarketHistoryCollector()

    # Collect resolved markets
    logger.info("\n1️⃣  Collecting resolved markets...")
    resolved_count = collector.collect_resolved_markets(max_markets=2000)
    logger.info(f"   Collected {resolved_count} resolved markets")

    # Collect active markets (for ongoing tracking)
    logger.info("\n2️⃣  Collecting active markets...")
    active_count = collector.collect_active_markets()
    logger.info(f"   Collected {active_count} active crypto markets")

    # Get statistics
    logger.info("\n3️⃣  Collection Statistics:")
    stats = collector.get_statistics()
    print(f"\n   Total Resolved Markets: {stats['total_resolved']}")
    print(f"\n   By Market Type:")
    for t, c in stats.get('by_type', {}).items():
        print(f"      {t or 'unknown'}: {c}")
    print(f"\n   Price-Level Outcomes:")
    for o, c in stats.get('price_level_outcomes', {}).items():
        print(f"      {o}: {c}")
    print(f"\n   By Asset:")
    for a, c in stats.get('by_asset', {}).items():
        print(f"      {a or 'unknown'}: {c}")
    print(f"\n   Price Snapshots: {stats['price_snapshots']}")

    # Export for training
    logger.info("\n4️⃣  Exporting resolved markets...")
    df = collector.export_for_training()

    if df is not None and len(df) > 0:
        print(f"\n   Sample resolved markets:")
        for _, row in df.head(10).iterrows():
            print(f"      [{row['resolved_outcome']:3}] {row['question'][:50]}...")

    logger.info("\n" + "="*70)
    logger.info("COLLECTION COMPLETE")
    logger.info("="*70)


if __name__ == '__main__':
    main()
