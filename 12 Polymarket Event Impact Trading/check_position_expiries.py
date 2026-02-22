#!/usr/bin/env python3
"""Check expiry dates of open positions in price-level trader."""

import sqlite3
import json
from datetime import datetime

conn = sqlite3.connect('data/positions_price_level.db')
cursor = conn.cursor()

cursor.execute('SELECT market_id, entry_time, status, metadata FROM positions ORDER BY entry_time DESC LIMIT 30')

print('Recent positions (last 30 - showing all statuses):\n')
print('=' * 80)

violations_found = 0

for row in cursor.fetchall():
    market_id, entry_time, status, metadata_json = row
    metadata = json.loads(metadata_json) if metadata_json else {}
    expiry_str = metadata.get('expiry_date', 'N/A')
    asset = metadata.get('asset', 'UNKNOWN')
    question = metadata.get('question', 'N/A')

    if expiry_str and expiry_str != 'N/A':
        try:
            expiry = datetime.fromisoformat(expiry_str)
            entry = datetime.fromisoformat(entry_time)

            # Handle timezone-aware/naive datetime comparison
            if expiry.tzinfo is not None and entry.tzinfo is None:
                entry = entry.replace(tzinfo=expiry.tzinfo)
            elif expiry.tzinfo is None and entry.tzinfo is not None:
                expiry = expiry.replace(tzinfo=entry.tzinfo)

            # Remove timezone info for simpler comparison
            expiry_naive = expiry.replace(tzinfo=None) if expiry.tzinfo else expiry
            entry_naive = entry.replace(tzinfo=None) if entry.tzinfo else entry

            days_to_expiry_at_entry = (expiry_naive - entry_naive).days
            days_from_now = (expiry_naive - datetime.now()).days

            # Flag if expiry is too far out
            if days_to_expiry_at_entry > 150:
                flag = "⚠️ TOO FAR!"
                violations_found += 1
            else:
                flag = "✓"

            print(f'{flag} [{status}] {asset}: {question[:50]}')
            print(f'   Entry: {entry_time[:10]} | Expiry: {expiry_str[:10]}')
            print(f'   Days at entry: {days_to_expiry_at_entry} | Days remaining: {days_from_now}')
            print()
        except Exception as e:
            print(f'❌ [{status}] {asset}: {question[:50]}')
            print(f'   Expiry: {expiry_str}')
            print(f'   Error: {e}')
            print()
    else:
        print(f'? [{status}] {asset}: {question[:50]}')
        print(f'   No expiry date')
        print()

print('=' * 80)
print(f'Total violations found (>150 days): {violations_found}')

conn.close()
