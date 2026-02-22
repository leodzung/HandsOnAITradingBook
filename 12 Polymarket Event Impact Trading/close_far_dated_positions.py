#!/usr/bin/env python3
"""Close positions that exceed max_days_to_expiry configuration."""

import sqlite3
import json
import sys
from datetime import datetime

# Config
MAX_DAYS_TO_EXPIRY = 150
DB_PATH = 'data/positions_price_level.db'

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Find positions exceeding max days to expiry
    cursor.execute('SELECT market_id, entry_time, metadata FROM positions WHERE status = "OPEN"')

    positions_to_close = []

    for row in cursor.fetchall():
        market_id, entry_time, metadata_json = row
        metadata = json.loads(metadata_json) if metadata_json else {}
        expiry_str = metadata.get('expiry_date')
        question = metadata.get('question', 'N/A')

        print(f"DEBUG: Checking {question[:40]}")
        print(f"  entry_time: {entry_time}")
        print(f"  expiry_str: {expiry_str}")

        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str)
                entry = datetime.fromisoformat(entry_time)

                # Remove timezone for comparison
                expiry_naive = expiry.replace(tzinfo=None) if expiry.tzinfo else expiry
                entry_naive = entry.replace(tzinfo=None) if entry.tzinfo else entry

                days_to_expiry = (expiry_naive - entry_naive).days
                print(f"  days_to_expiry: {days_to_expiry}")

                if days_to_expiry > MAX_DAYS_TO_EXPIRY:
                    positions_to_close.append({
                        'market_id': market_id,
                        'question': question[:60],
                        'days_to_expiry': days_to_expiry
                    })
                    print(f"  ⚠️ EXCEEDS LIMIT")
                print()
            except Exception as e:
                print(f"  Error: {e}")
                print()

    conn.close()

    # Report findings
    if not positions_to_close:
        print("✓ No positions exceed max_days_to_expiry")
        return

    print(f"Found {len(positions_to_close)} positions exceeding {MAX_DAYS_TO_EXPIRY} days:")
    print("=" * 80)
    for pos in positions_to_close:
        print(f"Market: {pos['question']}")
        print(f"  Days at entry: {pos['days_to_expiry']}")
        print(f"  Market ID: {pos['market_id']}")
        print()

    print("=" * 80)
    print("\nThese positions were opened before the expiry filter fix (commit f12748e).")
    print("\nRecommended actions:")
    print("1. Restart trader_price_levels.py to use fixed code")
    print("2. Manually close these positions or wait for SL/TP triggers")
    print("\nTo restart trader:")
    print("  pkill -f trader_price_levels.py")
    print("  nohup python3 src/bots/trader_price_levels.py >> logs/trader_price_levels.out 2>&1 &")

if __name__ == '__main__':
    main()
