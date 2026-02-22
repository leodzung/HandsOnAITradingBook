"""Test raw API calls to understand what markets are available."""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.polymarket_client import PolymarketClient


def test_raw_markets():
    """Test raw market API calls."""
    client = PolymarketClient()
    now = datetime.now(timezone.utc)

    print("=" * 60)
    print("RAW API TEST")
    print("=" * 60)

    # Test 1: Get all active markets (no filters)
    print("\n1. All active markets (limit 10):")
    markets = client.get_markets(limit=10, active=True)
    print(f"   Found: {len(markets)} markets")
    if markets:
        m = markets[0]
        print(f"   Sample: {m.get('question', 'N/A')[:60]}")
        print(f"   End date: {m.get('endDate', 'N/A')}")
        print(f"   Volume: ${float(m.get('volume24hr', 0)):.0f}")

    # Test 2: Markets with short expiry (next 7 days)
    print(f"\n2. Markets expiring in next 7 days:")
    markets = client.get_markets(
        limit=50,
        active=True,
        end_date_min=now.isoformat(),
        end_date_max=(now + timedelta(days=7)).isoformat()
    )
    print(f"   Found: {len(markets)} markets")

    # Test 3: Add volume filter
    print(f"\n3. Markets with volume > 500:")
    markets = client.get_markets(
        limit=50,
        active=True,
        end_date_min=now.isoformat(),
        end_date_max=(now + timedelta(days=7)).isoformat(),
        volume_num_min=500
    )
    print(f"   Found: {len(markets)} markets")

    # Test 4: Check crypto markets
    print(f"\n4. Checking for crypto-related markets:")
    all_markets = client.get_markets(limit=100, active=True)
    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency']

    crypto_markets = []
    for m in all_markets:
        question = m.get('question', '').lower()
        if any(kw in question for kw in crypto_keywords):
            crypto_markets.append(m)

    print(f"   Total markets checked: {len(all_markets)}")
    print(f"   Crypto markets: {len(crypto_markets)}")

    if crypto_markets:
        print(f"\n   Sample crypto markets:")
        for i, m in enumerate(crypto_markets[:3]):
            print(f"   {i+1}. {m.get('question', 'N/A')[:60]}")
            print(f"      End: {m.get('endDate', 'N/A')}")
            print(f"      Vol: ${float(m.get('volume24hr', 0)):.0f}")

    # Test 5: Check expiry distribution
    print(f"\n5. Expiry distribution:")
    all_markets = client.get_markets(limit=100, active=True)

    buckets = {'< 24h': 0, '1-3d': 0, '3-7d': 0, '7-30d': 0, '> 30d': 0}

    for m in all_markets:
        end_date_str = m.get('endDate', m.get('end_date_iso', ''))
        if not end_date_str:
            continue

        try:
            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            hours_to_expiry = (end_date - now).total_seconds() / 3600

            if hours_to_expiry < 24:
                buckets['< 24h'] += 1
            elif hours_to_expiry < 72:
                buckets['1-3d'] += 1
            elif hours_to_expiry < 168:
                buckets['3-7d'] += 1
            elif hours_to_expiry < 720:
                buckets['7-30d'] += 1
            else:
                buckets['> 30d'] += 1
        except:
            pass

    for bucket, count in buckets.items():
        print(f"   {bucket:8s}: {count:3d} markets")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    test_raw_markets()
