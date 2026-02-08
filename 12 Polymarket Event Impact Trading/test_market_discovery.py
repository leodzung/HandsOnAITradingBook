"""
Test enhanced market discovery with new parameters.
"""

from polymarket_client import PolymarketClient
from datetime import datetime, timedelta
import json

def test_market_discovery():
    """Test different parameter combinations to see how many markets we can find."""

    client = PolymarketClient()

    print("=" * 80)
    print("TESTING ENHANCED MARKET DISCOVERY")
    print("=" * 80)

    # Test 1: All active markets (baseline)
    print("\n1. All active markets (limit=1000):")
    markets_all = client.get_markets(limit=1000, active=True, closed=False)
    print(f"   Found: {len(markets_all)} markets")

    # Test 2: Active markets by category
    categories = ['crypto', 'politics', 'sports', 'pop-culture', 'business', 'science']
    print("\n2. Markets by category:")
    for cat in categories:
        markets_cat = client.get_markets(limit=1000, active=True, closed=False, category=cat)
        print(f"   {cat:15s}: {len(markets_cat):4d} markets")

    # Test 3: Markets with minimum liquidity
    print("\n3. Markets with minimum liquidity:")
    for min_liq in [100, 500, 1000, 5000, 10000]:
        markets_liq = client.get_markets(limit=1000, active=True, closed=False,
                                         liquidity_num_min=min_liq)
        print(f"   >= ${min_liq:6d}: {len(markets_liq):4d} markets")

    # Test 4: Markets with minimum volume
    print("\n4. Markets with minimum volume:")
    for min_vol in [100, 500, 1000, 5000, 10000]:
        markets_vol = client.get_markets(limit=1000, active=True, closed=False,
                                         volume_num_min=min_vol)
        print(f"   >= ${min_vol:6d}: {len(markets_vol):4d} markets")

    # Test 5: Markets ending within different timeframes
    print("\n5. Markets by end date range:")
    now = datetime.now()
    for days in [7, 14, 30, 60, 90, 180, 365]:
        end_date = now + timedelta(days=days)
        end_date_str = end_date.strftime("%Y-%m-%d")
        markets_date = client.get_markets(limit=1000, active=True, closed=False,
                                         end_date_max=end_date_str)
        print(f"   Ending within {days:3d} days: {len(markets_date):4d} markets")

    # Test 6: Markets starting after a date
    print("\n6. Markets ending after today:")
    today = datetime.now().strftime("%Y-%m-%d")
    markets_future = client.get_markets(limit=1000, active=True, closed=False,
                                       end_date_min=today)
    print(f"   Found: {len(markets_future)} markets")

    # Test 7: Combine filters - high quality markets
    print("\n7. High-quality markets (liquidity >= $1000, volume >= $1000, ending in 30 days):")
    end_30d = (now + timedelta(days=30)).strftime("%Y-%m-%d")
    markets_quality = client.get_markets(limit=1000, active=True, closed=False,
                                        liquidity_num_min=1000,
                                        volume_num_min=1000,
                                        end_date_min=today,
                                        end_date_max=end_30d)
    print(f"   Found: {len(markets_quality)} markets")

    # Show sample market details
    if markets_quality:
        print("\n" + "=" * 80)
        print("SAMPLE MARKET DETAILS (first 3 high-quality markets):")
        print("=" * 80)
        for i, market in enumerate(markets_quality[:3], 1):
            print(f"\n{i}. {market.get('question', 'N/A')}")
            print(f"   Slug: {market.get('slug', 'N/A')}")
            print(f"   Category: {market.get('category', 'N/A')}")
            print(f"   End Date: {market.get('endDate', 'N/A')}")
            print(f"   Liquidity: ${market.get('liquidityNum', 0):,.2f}")
            print(f"   Volume: ${market.get('volumeNum', 0):,.2f}")
            print(f"   Active: {market.get('active', False)}")
            print(f"   Closed: {market.get('closed', False)}")

    # Show overall statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    if markets_all:
        liquidities = [m.get('liquidityNum', 0) for m in markets_all]
        volumes = [m.get('volumeNum', 0) for m in markets_all]
        print(f"Total active markets: {len(markets_all)}")
        print(f"Avg liquidity: ${sum(liquidities)/len(liquidities):,.2f}")
        print(f"Avg volume: ${sum(volumes)/len(volumes):,.2f}")
        print(f"Max liquidity: ${max(liquidities):,.2f}")
        print(f"Max volume: ${max(volumes):,.2f}")

        # Count by category
        categories_found = {}
        for m in markets_all:
            cat = m.get('category', 'unknown')
            categories_found[cat] = categories_found.get(cat, 0) + 1

        print(f"\nMarkets by category:")
        for cat, count in sorted(categories_found.items(), key=lambda x: x[1], reverse=True):
            print(f"  {cat:20s}: {count:4d}")

if __name__ == "__main__":
    test_market_discovery()
