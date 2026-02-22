#!/usr/bin/env python3
"""
Build token mapping in fresh database, then transfer to alchemy_trades.db

Two-step process to work around database corruption issues:
1. Build mapping in fresh token_mapping.db
2. Transfer mapping to alchemy_trades.db and update trades
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import sqlite3
from pathlib import Path
import logging

from src.utils.market_mapper import MarketConditionMapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def build_mapping():
    """Build mapping in fresh database."""
    logger.info("="*60)
    logger.info("STEP 1: BUILD MAPPING")
    logger.info("="*60)

    fresh_db = 'data/token_mapping.db'

    # Remove existing
    if Path(fresh_db).exists():
        logger.info(f"Removing existing {fresh_db}")
        Path(fresh_db).unlink()

    # Build mapping
    mapper = MarketConditionMapper(db_path=fresh_db)
    logger.info("Fetching markets and building mapping...")
    count = mapper.build_mapping()

    stats = mapper.get_statistics()
    logger.info(f"\nMapping complete:")
    logger.info(f"  Total mappings: {stats['total_mappings']:,}")
    logger.info(f"  Unique markets: {stats['total_markets']:,}")

    return fresh_db, stats['total_mappings']


def transfer_mapping():
    """Transfer mapping to alchemy_trades.db."""
    logger.info("\n" + "="*60)
    logger.info("STEP 2: TRANSFER TO ALCHEMY_TRADES.DB")
    logger.info("="*60)

    source_db = 'data/token_mapping.db'
    target_db = 'data/alchemy_trades.db'

    logger.info(f"Transferring from {source_db} to {target_db}...")

    with sqlite3.connect(target_db) as conn:
        cursor = conn.cursor()

        # Attach source database
        cursor.execute(f"ATTACH DATABASE '{source_db}' AS mapping_db")

        # Create mapping table in target if doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_condition_map (
                token_id TEXT PRIMARY KEY,
                condition_id TEXT NOT NULL,
                outcome_index INTEGER,
                question TEXT,
                updated_at TEXT
            )
        ''')

        # Copy mappings
        cursor.execute('''
            INSERT OR REPLACE INTO token_condition_map
            SELECT * FROM mapping_db.token_condition_map
        ''')

        mappings_copied = cursor.rowcount
        logger.info(f"  Copied {mappings_copied:,} mappings")

        # Create index
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_token_condition
            ON token_condition_map(condition_id)
        ''')

        conn.commit()
        cursor.execute("DETACH DATABASE mapping_db")

    return mappings_copied


def update_trades():
    """Update trades with condition_ids."""
    logger.info("\n" + "="*60)
    logger.info("STEP 3: UPDATE TRADES")
    logger.info("="*60)

    target_db = 'data/alchemy_trades.db'

    with sqlite3.connect(target_db) as conn:
        cursor = conn.cursor()

        # Count trades to update
        cursor.execute('''
            SELECT COUNT(DISTINCT t.maker_asset_id)
            FROM on_chain_trades t
            JOIN token_condition_map m ON t.maker_asset_id = m.token_id
            WHERE t.condition_id IS NULL
        ''')
        unique_tokens = cursor.fetchone()[0]

        logger.info(f"Unique tokens to map: {unique_tokens:,}")

        # Update trades
        logger.info("Updating trades (this may take a few minutes)...")
        cursor.execute('''
            UPDATE on_chain_trades
            SET condition_id = (
                SELECT condition_id
                FROM token_condition_map
                WHERE token_condition_map.token_id = on_chain_trades.maker_asset_id
            )
            WHERE maker_asset_id IN (
                SELECT token_id FROM token_condition_map
            )
            AND condition_id IS NULL
        ''')

        updated_count = cursor.rowcount
        conn.commit()

        # Verify
        cursor.execute("SELECT COUNT(*) FROM on_chain_trades WHERE condition_id IS NOT NULL")
        total_mapped = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
        total_trades = cursor.fetchone()[0]

        coverage = 100.0 * total_mapped / total_trades if total_trades > 0 else 0

        logger.info(f"\n Update complete:")
        logger.info(f"  Trades updated: {updated_count:,}")
        logger.info(f"  Total mapped: {total_mapped:,}")
        logger.info(f"  Total trades: {total_trades:,}")
        logger.info(f"  Coverage: {coverage:.1f}%")

    return updated_count, total_mapped, total_trades


def main():
    """Run complete pipeline."""
    logger.info("TOKEN MAPPING & TRANSFER PIPELINE\n")

    # Step 1: Build mapping
    fresh_db, mapping_count = build_mapping()

    if mapping_count == 0:
        logger.error("No mappings created! Check API or market structure.")
        return 1

    # Step 2: Transfer to alchemy_trades.db
    transferred = transfer_mapping()

    # Step 3: Update trades
    updated, total_mapped, total_trades = update_trades()

    logger.info("\n" + "="*60)
    logger.info("✅ PIPELINE COMPLETE")
    logger.info("="*60)
    logger.info(f"Mappings created: {mapping_count:,}")
    logger.info(f"Trades updated: {updated:,}")
    logger.info(f"Coverage: {100.0 * total_mapped / total_trades:.1f}%")

    return 0


if __name__ == '__main__':
    sys.exit(main())
