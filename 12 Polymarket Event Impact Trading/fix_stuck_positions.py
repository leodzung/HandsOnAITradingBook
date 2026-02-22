#!/usr/bin/env python3
"""
Fix stuck positions with uppercase 'OPEN' status.
These positions are from Feb 14 and aren't being properly monitored.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.polymarket_client import PolymarketClient
from core.price_fetcher import PriceFetcher
import json

def fix_stuck_positions():
    """Normalize uppercase OPEN to lowercase open."""
    db_path = 'data/positions_price_level.db'

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find stuck positions
    cursor.execute("""
        SELECT market_id, outcome, entry_price, size,
               json_extract(metadata, '$.question') as question,
               json_extract(metadata, '$.asset') as asset
        FROM positions
        WHERE status = 'OPEN'
    """)

    stuck = cursor.fetchall()

    if not stuck:
        print("✓ No stuck positions found")
        return

    print(f"Found {len(stuck)} stuck positions with uppercase 'OPEN' status\n")

    # Initialize client to check current prices
    with open('config/config_price_levels.json', 'r') as f:
        config = json.load(f)

    client = PolymarketClient(config=config)
    price_fetcher = PriceFetcher(client)

    for market_id, outcome, entry_price, size, question, asset in stuck:
        print(f"\n{asset} - {question[:60]}")
        print(f"  Position: {outcome} @ ${entry_price:.3f}, Size: ${size:.2f}")

        # Get current price
        try:
            exit_prices = price_fetcher.get_exit_prices(market_id)
            if exit_prices:
                current_price = exit_prices.get_outcome_price(outcome)
                pnl_pct = ((current_price - entry_price) / entry_price) * 100
                print(f"  Current: ${current_price:.3f} ({pnl_pct:+.1f}%)")
            else:
                print(f"  Current: Price unavailable")
                current_price = None
        except Exception as e:
            print(f"  Current: Error fetching price - {e}")
            current_price = None

    print("\n" + "="*70)
    print("OPTIONS:")
    print("  1. Normalize status to lowercase 'open' (positions will be monitored)")
    print("  2. Close all stuck positions at current prices")
    print("  3. Exit without changes")

    choice = input("\nChoice (1-3): ").strip()

    if choice == '1':
        # Normalize to lowercase
        cursor.execute("UPDATE positions SET status = 'open' WHERE status = 'OPEN'")
        conn.commit()
        count = cursor.rowcount
        print(f"\n✓ Normalized {count} positions to lowercase 'open'")
        print("  These positions will now be monitored by the bot")

    elif choice == '2':
        # Close positions
        for market_id, outcome, entry_price, size, question, asset in stuck:
            try:
                exit_prices = price_fetcher.get_exit_prices(market_id)
                if exit_prices:
                    exit_price = exit_prices.get_outcome_price(outcome)
                else:
                    exit_price = entry_price
                    print(f"  Warning: Using entry price as exit for {market_id[:20]}...")

                # Calculate P&L
                tokens = size / entry_price if entry_price > 0 else 0
                payout = tokens * exit_price
                pnl = payout - size
                pnl_pct = (pnl / size) * 100 if size > 0 else 0

                # Close position
                cursor.execute("""
                    UPDATE positions
                    SET status = 'closed',
                        exit_time = datetime('now'),
                        exit_price = ?,
                        pnl = ?,
                        pnl_pct = ?,
                        exit_reason = 'manual_cleanup'
                    WHERE market_id = ? AND outcome = ? AND status = 'OPEN'
                """, (exit_price, pnl, pnl_pct, market_id, outcome))

                print(f"  ✓ Closed {asset} {outcome}: P&L ${pnl:+.2f} ({pnl_pct:+.1f}%)")

            except Exception as e:
                print(f"  ✗ Error closing {market_id[:20]}...: {e}")

        conn.commit()
        print(f"\n✓ Closed {len(stuck)} positions")

    else:
        print("\n✓ No changes made")

    conn.close()

if __name__ == '__main__':
    fix_stuck_positions()
