#!/usr/bin/env python3
"""
Backfill metadata (question, asset) for existing open positions.

This script fetches market data from Polymarket API and updates
the metadata field for positions that are missing question/asset.
"""

import sqlite3
import json
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.polymarket_client import PolymarketClient

def infer_asset_from_question(question: str) -> str:
    """Infer asset category from market question."""
    if not question:
        return 'UNKNOWN'

    question_lower = question.lower()

    # Gold (check before crypto)
    if 'gold' in question_lower or 'gc' in question_lower or 'xau' in question_lower:
        return 'GOLD'

    # Crypto
    if 'bitcoin' in question_lower or 'btc' in question_lower:
        return 'BTC'
    elif 'ethereum' in question_lower or 'eth' in question_lower:
        return 'ETH'
    elif 'solana' in question_lower or 'sol' in question_lower:
        return 'SOL'

    # Politics
    elif any(keyword in question_lower for keyword in ['trump', 'biden', 'election', 'president', 'congress']):
        return 'POLITICS'

    # Sports
    elif any(keyword in question_lower for keyword in ['nfl', 'nba', 'sports', 'super bowl', 'world series']):
        return 'SPORTS'

    # Default to crypto for short-expiry, event for others
    return 'CRYPTO'


def backfill_database(db_path: Path, bot_type: str):
    """Backfill metadata for a single database."""

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    print(f"\n{'='*60}")
    print(f"Backfilling: {db_path.name}")
    print(f"Bot type: {bot_type}")
    print(f"{'='*60}\n")

    # Initialize Polymarket client
    client = PolymarketClient()

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find positions with missing metadata
    cursor.execute("""
        SELECT market_id, outcome, metadata, id
        FROM positions
        WHERE UPPER(status) = 'OPEN'
    """)

    positions = cursor.fetchall()

    if not positions:
        print("No open positions found")
        conn.close()
        return

    print(f"Found {len(positions)} open positions")

    updated_count = 0
    failed_count = 0

    for market_id, outcome, metadata_json, position_id in positions:
        # Parse existing metadata
        try:
            if metadata_json:
                metadata = json.loads(metadata_json)
            else:
                metadata = {}
        except:
            metadata = {}

        # Check if already has question and asset
        has_question = 'question' in metadata and metadata['question']
        has_asset = 'asset' in metadata and metadata['asset']

        if has_question and has_asset:
            print(f"  ✓ Position {market_id[:16]}... already has metadata")
            continue

        # Fetch market data from API
        print(f"  Fetching market data for {market_id[:16]}...")

        try:
            market = client.get_market(market_id)

            if not market:
                print(f"    ⚠️  Could not fetch market data")
                failed_count += 1
                continue

            # Extract question
            question = market.get('question', market.get('description', ''))

            # Infer asset
            asset = infer_asset_from_question(question)

            # Update metadata
            metadata['question'] = question
            metadata['asset'] = asset

            # Save to database
            cursor.execute("""
                UPDATE positions
                SET metadata = ?
                WHERE id = ?
            """, (json.dumps(metadata), position_id))

            print(f"    ✓ Updated: {question[:50]} | Asset: {asset}")
            updated_count += 1

        except Exception as e:
            print(f"    ❌ Error: {e}")
            failed_count += 1

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\nResults for {db_path.name}:")
    print(f"  ✓ Updated: {updated_count}")
    print(f"  ❌ Failed: {failed_count}")
    print(f"  Total: {len(positions)}")


def main():
    """Backfill all position databases."""

    databases = [
        ('data/positions.db', 'event'),
        ('data/positions_price_level.db', 'price_level'),
        ('data/positions_short_expiry.db', 'short_expiry'),
    ]

    print("=" * 60)
    print("Position Metadata Backfill")
    print("=" * 60)
    print("\nThis script will:")
    print("1. Find all open positions with missing metadata")
    print("2. Fetch market data from Polymarket API")
    print("3. Update metadata with question and asset")
    print()

    total_updated = 0

    for db_path_str, bot_type in databases:
        db_path = Path(db_path_str)
        backfill_database(db_path, bot_type)

    print("\n" + "=" * 60)
    print("Backfill complete!")
    print("=" * 60)
    print("\nRefresh the dashboard to see updated positions.")


if __name__ == '__main__':
    main()
