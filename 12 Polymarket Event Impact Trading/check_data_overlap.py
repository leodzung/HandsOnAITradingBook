#!/usr/bin/env python3
"""Check overlap between on-chain trades and resolved markets."""
import sqlite3

# Check alchemy trades date range
alchemy = sqlite3.connect('data/alchemy_trades.db')
alchemy_cur = alchemy.cursor()

print("=== ON-CHAIN TRADES (alchemy_trades.db) ===")
alchemy_cur.execute("SELECT COUNT(*) FROM on_chain_trades")
print(f"Total trades: {alchemy_cur.fetchone()[0]:,}")

alchemy_cur.execute("SELECT MIN(block_timestamp), MAX(block_timestamp) FROM on_chain_trades WHERE block_timestamp > '2000-01-01'")
date_range = alchemy_cur.fetchone()
print(f"Date range: {date_range[0]} to {date_range[1]}")

alchemy_cur.execute("SELECT COUNT(DISTINCT condition_id) FROM on_chain_trades WHERE condition_id IS NOT NULL")
print(f"Unique condition_ids: {alchemy_cur.fetchone()[0]:,}")

# Check resolved markets
history = sqlite3.connect('data/polymarket_history.db')
history_cur = history.cursor()

print("\n=== RESOLVED MARKETS (polymarket_history.db) ===")
history_cur.execute("SELECT COUNT(*) FROM resolved_markets")
print(f"Total resolved markets: {history_cur.fetchone()[0]:,}")

history_cur.execute("SELECT MIN(end_date), MAX(end_date) FROM resolved_markets")
date_range = history_cur.fetchone()
print(f"End date range: {date_range[0]} to {date_range[1]}")

# Check overlap
print("\n=== OVERLAP CHECK ===")
alchemy_cur.execute("SELECT condition_id FROM on_chain_trades WHERE condition_id IS NOT NULL GROUP BY condition_id")
alchemy_conditions = set(row[0] for row in alchemy_cur.fetchall())

history_cur.execute("SELECT condition_id FROM resolved_markets")
resolved_conditions = set(row[0] for row in history_cur.fetchall())

overlap = alchemy_conditions & resolved_conditions
print(f"On-chain condition_ids: {len(alchemy_conditions):,}")
print(f"Resolved condition_ids: {len(resolved_conditions):,}")
print(f"✓ OVERLAP: {len(overlap):,} markets")

if overlap:
    print(f"\n✓✓ YES! You have {len(overlap):,} markets with BOTH trades AND resolved outcomes!")
    print("This means you can create REAL labels for training!")
else:
    print("\n✗ NO OVERLAP - trades and resolved markets don't match")

alchemy.close()
history.close()
