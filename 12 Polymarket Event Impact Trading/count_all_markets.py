"""
Count total markets and analyze filtering options.
"""

from polymarket_client import PolymarketClient
from datetime import datetime, timedelta
import time

def count_all_markets():
    """Count total number of active markets."""

    client = PolymarketClient()

    print("=" * 80)
    print("COUNTING ALL ACTIVE MARKETS")
    print("=" * 80)

    offset = 0
    batch_size = 500
    total_count = 0

    start_time = time.time()

    while offset < 50000:  # Extended safety limit
        markets_batch = client.get_markets(
            limit=batch_size,
            offset=offset,
            active=True,
            closed=False
        )

        if not markets_batch:
            print(f"\nReached end at offset {offset}")
            break

        batch_count = len(markets_batch)
        total_count += batch_count

        if offset % 2500 == 0:  # Progress update every 2500
            print(f"Offset {offset:6d}: +{batch_count} markets (total: {total_count})")

        if batch_count < batch_size:
            print(f"\nReceived fewer than {batch_size} markets at offset {offset} - reached end")
            break

        offset += batch_size

    elapsed = time.time() - start_time

    print("\n" + "=" * 80)
    print(f"TOTAL ACTIVE MARKETS: {total_count:,}")
    print(f"Time elapsed: {elapsed:.1f} seconds")
    print("=" * 80)

    # Now test different filter combinations to find useful markets
    print("\n" + "=" * 80)
    print("TESTING FILTER COMBINATIONS")
    print("=" * 80)

    today = datetime.now()

    # Test 1: Markets ending in next 30 days with good liquidity
    print("\n1. Markets ending in 30 days + liquidity >= $1000:")
    end_30d = (today + timedelta(days=30)).strftime("%Y-%m-%d")
    markets_30d_liq = client.get_markets(
        limit=500,
        active=True,
        closed=False,
        end_date_min=today.strftime("%Y-%m-%d"),
        end_date_max=end_30d,
        liquidity_num_min=1000
    )
    print(f"   Found: {len(markets_30d_liq)} markets")
    if markets_30d_liq:
        avg_liq = sum(m.get('liquidityNum', 0) for m in markets_30d_liq) / len(markets_30d_liq)
        print(f"   Avg liquidity: ${avg_liq:,.2f}")

    # Test 2: High-volume markets ending this year
    print("\n2. Markets with volume >= $10,000:")
    markets_vol = client.get_markets(
        limit=500,
        active=True,
        closed=False,
        volume_num_min=10000
    )
    print(f"   Found: {len(markets_vol)} markets")
    if markets_vol:
        avg_vol = sum(m.get('volumeNum', 0) for m in markets_vol) / len(markets_vol)
        print(f"   Avg volume: ${avg_vol:,.2f}")

    # Test 3: Markets ending this week
    print("\n3. Markets ending in next 7 days:")
    end_7d = (today + timedelta(days=7)).strftime("%Y-%m-%d")
    markets_7d = client.get_markets(
        limit=500,
        active=True,
        closed=False,
        end_date_min=today.strftime("%Y-%m-%d"),
        end_date_max=end_7d
    )
    print(f"   Found: {len(markets_7d)} markets")

    # Test 4: High quality markets (good liquidity + volume + reasonable timeframe)
    print("\n4. High-quality markets (liq >= $5k, vol >= $10k, ending in 90 days):")
    end_90d = (today + timedelta(days=90)).strftime("%Y-%m-%d")
    markets_quality = client.get_markets(
        limit=500,
        active=True,
        closed=False,
        end_date_min=today.strftime("%Y-%m-%d"),
        end_date_max=end_90d,
        liquidity_num_min=5000,
        volume_num_min=10000
    )
    print(f"   Found: {len(markets_quality)} markets")

    if markets_quality:
        print("\n   Sample markets:")
        for i, m in enumerate(markets_quality[:5], 1):
            print(f"   {i}. {m.get('question', 'N/A')[:70]}")
            print(f"      Liquidity: ${m.get('liquidityNum', 0):,.0f} | "
                  f"Volume: ${m.get('volumeNum', 0):,.0f} | "
                  f"Ends: {m.get('endDateIso', 'N/A')}")

    return total_count

if __name__ == "__main__":
    total = count_all_markets()
    print(f"\n{'='*80}")
    print(f"SUMMARY: Found {total:,} active markets on Polymarket!")
    print(f"{'='*80}")
