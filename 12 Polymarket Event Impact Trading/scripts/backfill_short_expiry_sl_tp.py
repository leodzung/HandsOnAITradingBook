"""
Backfill missing stop-loss and take-profit for short_expiry bot positions.

This script updates existing positions that were opened before the RISK-001
constraint was enforced in trader_short_expiry.py.
"""

import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "positions_short_expiry.db"

# Default SL/TP values (from short_expiry config)
DEFAULT_SL_PCT = 15.0  # 15% stop loss
DEFAULT_TP_PCT = 50.0  # 50% take profit

def backfill_sl_tp():
    """Update positions missing SL/TP values."""
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Find positions without SL/TP
    cursor.execute("""
        SELECT id, market_id, outcome, entry_price, size, entry_time
        FROM positions
        WHERE (stop_loss_pct IS NULL OR take_profit_pct IS NULL)
        AND status = 'open'
    """)

    positions = cursor.fetchall()

    if not positions:
        print("✅ All positions have stop-loss and take-profit set")
        conn.close()
        return

    print(f"Found {len(positions)} positions missing SL/TP")
    print()

    # Update each position
    for position in positions:
        position_id, market_id, outcome, entry_price, size, entry_time = position

        print(f"Updating position {position_id}:")
        print(f"  Market: {market_id[:16]}...")
        print(f"  Outcome: {outcome}")
        print(f"  Entry: ${entry_price:.4f}")
        print(f"  Size: {size}")
        print(f"  Opened: {entry_time}")
        print(f"  Setting: SL={DEFAULT_SL_PCT}%, TP={DEFAULT_TP_PCT}%")

        cursor.execute("""
            UPDATE positions
            SET stop_loss_pct = ?, take_profit_pct = ?
            WHERE id = ?
        """, (DEFAULT_SL_PCT, DEFAULT_TP_PCT, position_id))

        print("  ✅ Updated")
        print()

    # Commit changes
    conn.commit()
    conn.close()

    print(f"✅ Backfilled {len(positions)} positions with SL/TP thresholds")
    print(f"   Stop Loss: {DEFAULT_SL_PCT}%")
    print(f"   Take Profit: {DEFAULT_TP_PCT}%")


if __name__ == "__main__":
    backfill_sl_tp()
