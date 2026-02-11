#!/usr/bin/env python3
"""
Map condition_ids to token_ids and update alchemy_trades.db

This script:
1. Loads resolved markets from polymarket_history.db
2. Queries Polymarket API to get token_ids for each condition_id
3. Builds a mapping table
4. Updates alchemy_trades.db with condition_ids

This enables using all 2M+ historical trades for model training.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
import pandas as pd
import time
from pathlib import Path
from datetime import datetime
import logging

from src.core.polymarket_client import PolymarketClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
HISTORY_DB = DATA_DIR / "polymarket_history.db"
TRADES_DB = DATA_DIR / "alchemy_trades.db"
MAPPING_DB = DATA_DIR / "token_condition_mapping.db"


class ConditionIdMapper:
    """Maps token_ids to condition_ids using Polymarket API."""

    def __init__(self):
        self.client = PolymarketClient()
        self.mapping_db = MAPPING_DB
        self._init_mapping_db()

    def _init_mapping_db(self):
        """Create mapping database."""
        with sqlite3.connect(self.mapping_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_condition_mapping (
                    token_id TEXT PRIMARY KEY,
                    condition_id TEXT NOT NULL,
                    outcome TEXT,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_condition_id
                ON token_condition_mapping(condition_id)
            """)

    def load_resolved_markets(self):
        """Load condition_ids from resolved markets."""
        logger.info("Loading resolved markets...")

        with sqlite3.connect(HISTORY_DB) as conn:
            query = "SELECT condition_id, question FROM resolved_markets WHERE condition_id IS NOT NULL"
            markets = pd.read_sql_query(query, conn)

        logger.info(f"Loaded {len(markets)} resolved markets")
        return markets

    def fetch_token_mapping(self, condition_id: str) -> list:
        """Fetch token_id mapping for a condition_id from API."""
        try:
            market = self.client.get_market(condition_id)
            if not market:
                logger.debug(f"No market data for {condition_id}")
                return []

            tokens = market.get('tokens', [])
            if not tokens:
                logger.debug(f"No tokens for {condition_id}")
                return []

            mappings = []
            for token in tokens:
                token_id = token.get('token_id')
                outcome = token.get('outcome', '')

                if token_id:
                    mappings.append({
                        'token_id': token_id,
                        'condition_id': condition_id,
                        'outcome': outcome
                    })

            return mappings

        except Exception as e:
            logger.debug(f"Error fetching tokens for {condition_id}: {e}")
            return []

    def build_mapping(self, markets_df: pd.DataFrame, rate_limit_delay: float = 0.5):
        """Build token_id → condition_id mapping."""
        logger.info(f"Building token mapping for {len(markets_df)} markets...")
        logger.info(f"Rate limit: {rate_limit_delay}s between requests")

        total_mappings = 0
        failed_count = 0

        with sqlite3.connect(self.mapping_db) as conn:
            for idx, row in markets_df.iterrows():
                if idx % 50 == 0:
                    logger.info(f"Progress: {idx}/{len(markets_df)} | Mapped: {total_mappings}")

                condition_id = row['condition_id']

                # Check if already mapped
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM token_condition_mapping WHERE condition_id = ?",
                    (condition_id,)
                )
                if cursor.fetchone()[0] > 0:
                    logger.debug(f"Already mapped: {condition_id}")
                    continue

                # Fetch from API
                mappings = self.fetch_token_mapping(condition_id)

                if mappings:
                    # Insert mappings
                    for mapping in mappings:
                        conn.execute("""
                            INSERT OR REPLACE INTO token_condition_mapping
                            (token_id, condition_id, outcome)
                            VALUES (?, ?, ?)
                        """, (mapping['token_id'], mapping['condition_id'], mapping['outcome']))

                    total_mappings += len(mappings)
                else:
                    failed_count += 1

                # Rate limiting
                time.sleep(rate_limit_delay)

            conn.commit()

        logger.info(f"\nMapping complete:")
        logger.info(f"  Total token mappings: {total_mappings}")
        logger.info(f"  Failed to fetch: {failed_count}")

        return total_mappings

    def update_trades_db(self):
        """Update alchemy_trades.db with condition_ids."""
        logger.info("\nUpdating trades database with condition_ids...")

        # Load mapping
        with sqlite3.connect(self.mapping_db) as conn:
            mapping = pd.read_sql_query(
                "SELECT token_id, condition_id FROM token_condition_mapping",
                conn
            )

        logger.info(f"Loaded {len(mapping)} token→condition mappings")

        # Create temp mapping table in trades db
        with sqlite3.connect(TRADES_DB) as conn:
            # Create temporary mapping table
            conn.execute("DROP TABLE IF EXISTS temp_token_mapping")
            mapping.to_sql('temp_token_mapping', conn, index=False)

            # Count trades to update
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM on_chain_trades t
                JOIN temp_token_mapping m ON t.maker_asset_id = m.token_id
                WHERE t.condition_id IS NULL
            """)
            count_to_update = cursor.fetchone()[0]

            logger.info(f"Trades to update: {count_to_update:,}")

            if count_to_update == 0:
                logger.info("No trades to update")
                return 0

            # Update in batches
            logger.info("Updating trades (this may take a few minutes)...")

            cursor.execute("""
                UPDATE on_chain_trades
                SET condition_id = (
                    SELECT condition_id
                    FROM temp_token_mapping
                    WHERE temp_token_mapping.token_id = on_chain_trades.maker_asset_id
                )
                WHERE maker_asset_id IN (
                    SELECT token_id FROM temp_token_mapping
                )
                AND condition_id IS NULL
            """)

            updated_count = cursor.rowcount
            conn.commit()

            # Verify
            cursor.execute("SELECT COUNT(*) FROM on_chain_trades WHERE condition_id IS NOT NULL")
            total_with_condition = cursor.fetchone()[0]

            logger.info(f"\nUpdate complete:")
            logger.info(f"  Trades updated: {updated_count:,}")
            logger.info(f"  Total with condition_id: {total_with_condition:,}")

            # Clean up
            conn.execute("DROP TABLE temp_token_mapping")

        return updated_count

    def get_statistics(self):
        """Get statistics on mapping coverage."""
        logger.info("\n" + "="*60)
        logger.info("MAPPING STATISTICS")
        logger.info("="*60)

        with sqlite3.connect(self.mapping_db) as conn:
            cursor = conn.cursor()

            # Total mappings
            cursor.execute("SELECT COUNT(*) FROM token_condition_mapping")
            total_mappings = cursor.fetchone()[0]
            logger.info(f"Total token mappings: {total_mappings:,}")

            # Unique conditions
            cursor.execute("SELECT COUNT(DISTINCT condition_id) FROM token_condition_mapping")
            unique_conditions = cursor.fetchone()[0]
            logger.info(f"Unique condition_ids: {unique_conditions:,}")

        with sqlite3.connect(TRADES_DB) as conn:
            cursor = conn.cursor()

            # Total trades
            cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
            total_trades = cursor.fetchone()[0]

            # Trades with condition_id
            cursor.execute("SELECT COUNT(*) FROM on_chain_trades WHERE condition_id IS NOT NULL")
            mapped_trades = cursor.fetchone()[0]

            # Unique markets in trades
            cursor.execute("SELECT COUNT(DISTINCT condition_id) FROM on_chain_trades WHERE condition_id IS NOT NULL")
            unique_markets = cursor.fetchone()[0]

            logger.info(f"\nTrades database:")
            logger.info(f"  Total trades: {total_trades:,}")
            logger.info(f"  Mapped trades: {mapped_trades:,} ({mapped_trades/total_trades*100:.1f}%)")
            logger.info(f"  Unique markets: {unique_markets:,}")

    def run(self, skip_api_fetch: bool = False):
        """Run complete mapping pipeline."""
        logger.info("="*60)
        logger.info("CONDITION ID MAPPER")
        logger.info("="*60)

        # Load markets
        markets = self.load_resolved_markets()

        if not skip_api_fetch:
            # Build mapping via API
            self.build_mapping(markets, rate_limit_delay=0.5)
        else:
            logger.info("Skipping API fetch (using existing mapping)")

        # Update trades database
        self.update_trades_db()

        # Show statistics
        self.get_statistics()

        logger.info("\n✅ Mapping complete!")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Map token_ids to condition_ids')
    parser.add_argument('--skip-api', action='store_true',
                       help='Skip API fetch, only update trades from existing mapping')
    parser.add_argument('--stats-only', action='store_true',
                       help='Only show statistics, don\'t update anything')

    args = parser.parse_args()

    mapper = ConditionIdMapper()

    if args.stats_only:
        mapper.get_statistics()
    else:
        mapper.run(skip_api_fetch=args.skip_api)


if __name__ == '__main__':
    main()
