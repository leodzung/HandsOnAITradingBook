#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect('data/alchemy_trades.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT condition_id, question, end_date, outcome_prices
    FROM markets
    WHERE outcome_prices IS NOT NULL
    LIMIT 20
""")

print("=== Sample outcome_prices ===\n")
resolved = 0
for row in cursor.fetchall():
    cid, q, end, prices_str = row
    try:
        prices = json.loads(prices_str)
        print(f"Q: {q[:50]}")
        print(f"   Prices: {prices}")
        print(f"   End: {end}")
        
        # Check if effectively resolved
        if isinstance(prices, list) and len(prices) >= 2:
            p0 = float(prices[0])
            p1 = float(prices[1])
            if (p0 in [0.0, 1.0] and p1 in [0.0, 1.0]) and (p0 + p1 == 1.0):
                resolved += 1
                print(f"   ✅ RESOLVED: {'YES' if p0 == 1.0 else 'NO'}")
        print()
    except Exception as e:
        print(f"Error: {e}\n")

print(f"Resolved markets in sample: {resolved}/20")
conn.close()
