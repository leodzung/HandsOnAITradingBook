#!/usr/bin/env python3
"""
Collect resolved markets from Aug 2025 - Feb 2026 for label creation.
"""
import requests
import json
import sqlite3
import time

GAMMA_URL = "https://gamma-api.polymarket.com"
DB_PATH = 'data/polymarket_history.db'

def collect_resolved_markets_by_date(start_date, end_date):
    """Collect all resolved markets in date range."""

    all_markets = []
    offset = 0
    batch_size = 100

    print(f"Collecting resolved markets from {start_date} to {end_date}...")

    while True:
        try:
            response = requests.get(
                f"{GAMMA_URL}/markets",
                params={
                    'closed': 'true',
                    'end_date_min': start_date,
                    'end_date_max': end_date,
                    'limit': batch_size,
                    'offset': offset
                },
                timeout=30
            )
            response.raise_for_status()
            markets = response.json()

            if not markets:
                break

            all_markets.extend(markets)
            print(f"  Fetched {len(all_markets)} markets...")
            offset += batch_size
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"Error: {e}")
            break

    return all_markets

def store_resolved_markets(markets):
    """Store markets in database."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    stored = 0
    resolved = 0

    for market in markets:
        # Extract outcome from outcomePrices
        prices = market.get('outcomePrices', '[]')
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except:
                continue

        if not prices or len(prices) < 2:
            continue

        try:
            p0, p1 = float(prices[0]), float(prices[1])
        except:
            continue

        # Determine resolved outcome
        if p0 >= 0.99 and p1 <= 0.01:
            resolved_outcome = 'Yes'
            resolved += 1
        elif p1 >= 0.99 and p0 <= 0.01:
            resolved_outcome = 'No'
            resolved += 1
        elif p0 == 1.0 and p1 == 0.0:
            resolved_outcome = 'Yes'
            resolved += 1
        elif p0 == 0.0 and p1 == 1.0:
            resolved_outcome = 'No'
            resolved += 1
        else:
            continue  # Not clearly resolved

        # Store in database
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO resolved_markets
                (condition_id, question, description, category, end_date,
                 resolved_outcome, outcome_prices, volume, liquidity,
                 created_at, closed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                market.get('conditionId'),
                market.get('question'),
                market.get('description', '')[:500],
                market.get('category', ''),
                market.get('endDate', ''),
                resolved_outcome,
                json.dumps(prices),
                float(market.get('volume', 0) or 0),
                float(market.get('liquidity', 0) or 0),
                market.get('createdAt', ''),
                market.get('closedTime', '')
            ))
            stored += 1
        except Exception as e:
            print(f"Error storing market: {e}")
            continue

    conn.commit()
    conn.close()

    return stored, resolved

if __name__ == '__main__':
    print("="*70)
    print("COLLECTING RECENT RESOLVED MARKETS")
    print("="*70)

    # Collect markets from Aug 2025 - Feb 2026
    markets = collect_resolved_markets_by_date('2025-08-01', '2026-02-21')
    print(f"\n✅ Fetched {len(markets)} total markets")

    # Store resolved ones
    stored, resolved = store_resolved_markets(markets)
    print(f"✅ Stored {stored} markets")
    print(f"✅ {resolved} have clear resolutions")

    # Verify
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM resolved_markets
        WHERE end_date >= '2025-08-01' AND end_date <= '2026-02-21'
    """)
    count = cursor.fetchone()[0]
    print(f"\n✅ Database now has {count} markets in training date range")

    # Show samples
    cursor.execute("""
        SELECT question, end_date, resolved_outcome
        FROM resolved_markets
        WHERE end_date >= '2025-08-01'
        ORDER BY end_date DESC
        LIMIT 10
    """)

    print(f"\n📋 Sample resolved markets:")
    for row in cursor.fetchall():
        print(f"  [{row[2]}] {row[1][:10]} - {row[0][:60]}")

    conn.close()
    print("="*70)
