#!/usr/bin/env python3
"""
Backfill stop-loss and take-profit for existing positions.

RISK-001 Compliance: All positions MUST have SL/TP set.
This script adds default SL/TP values to positions that are missing them.
"""

import sqlite3
import json
from pathlib import Path


def backfill_database(db_path: str, default_sl_pct: float, default_tp_pct: float):
    """
    Backfill stop-loss and take-profit for positions missing them.

    Args:
        db_path: Path to positions database
        default_sl_pct: Default stop-loss percentage
        default_tp_pct: Default take-profit percentage
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find open positions without SL/TP
    cursor.execute("""
        SELECT id, market_id, outcome, entry_price, size
        FROM positions
        WHERE status = 'open'
        AND (stop_loss_pct IS NULL OR take_profit_pct IS NULL)
    """)

    positions = cursor.fetchall()

    if not positions:
        print(f"✅ {db_path}: No positions need backfilling")
        conn.close()
        return

    print(f"\n📋 {db_path}: Found {len(positions)} positions without SL/TP")

    for position_id, market_id, outcome, entry_price, size in positions:
        print(f"  Position #{position_id} ({outcome}): ${entry_price:.4f}, Size: {size}")
        print(f"    Setting SL={default_sl_pct}%, TP={default_tp_pct}%")

        # Update position with default SL/TP
        cursor.execute("""
            UPDATE positions
            SET stop_loss_pct = ?, take_profit_pct = ?
            WHERE id = ?
        """, (default_sl_pct, default_tp_pct, position_id))

    conn.commit()
    conn.close()

    print(f"✅ Updated {len(positions)} positions")


if __name__ == '__main__':
    base_dir = Path(__file__).parent.parent / "data"

    # Backfill event trader positions (SL: 15%, TP: 50%)
    event_db = base_dir / "positions.db"
    if event_db.exists():
        print("\n🔧 Event Trader (positions.db)")
        backfill_database(str(event_db), default_sl_pct=15, default_tp_pct=50)

    # Backfill price-level trader positions (SL: 20%, TP: 75%)
    price_level_db = base_dir / "positions_price_level.db"
    if price_level_db.exists():
        print("\n🔧 Price-Level Trader (positions_price_level.db)")
        backfill_database(str(price_level_db), default_sl_pct=20, default_tp_pct=75)

    # Backfill short-expiry trader positions (use medium bucket defaults: SL: 20%, TP: 75%)
    short_expiry_db = base_dir / "positions_short_expiry.db"
    if short_expiry_db.exists():
        print("\n🔧 Short-Expiry Trader (positions_short_expiry.db)")
        backfill_database(str(short_expiry_db), default_sl_pct=20, default_tp_pct=75)

    print("\n✅ Backfill complete!")
    print("\nRISK-001: All positions now have stop-loss and take-profit thresholds.")
