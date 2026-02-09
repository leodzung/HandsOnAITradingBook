"""
Test pagination to discover total number of markets.
"""

from polymarket_client import PolymarketClient
from datetime import datetime, timedelta

def test_pagination():
    """Test pagination to get all available markets."""

    client = PolymarketClient()

    print("=" * 80)
    print("TESTING MARKET PAGINATION")
    print("=" * 80)

    all_markets = []
    offset = 0
    batch_size = 500  # Maximum per request

    while True:
        print(f"\nFetching batch at offset {offset}...")
        markets_batch = client.get_markets(
            limit=batch_size,
            offset=offset,
            active=True,
            closed=False
        )

        if not markets_batch:
            print(f"  No more markets (received empty response)")
            break

        print(f"  Received: {len(markets_batch)} markets")
        all_markets.extend(markets_batch)

        # If we got fewer than the batch size, we've reached the end
        if len(markets_batch) < batch_size:
            print(f"  Received fewer than {batch_size} markets - reached end")
            break

        offset += batch_size

        # Safety limit to prevent infinite loop
        if offset >= 10000:
            print(f"  Reached safety limit of 10,000 markets")
            break

    print("\n" + "=" * 80)
    print(f"TOTAL ACTIVE MARKETS FOUND: {len(all_markets)}")
    print("=" * 80)

    # Show statistics
    if all_markets:
        print(f"\nMarket statistics:")

        # Check what fields are available
        sample = all_markets[0]
        print(f"\nAvailable fields in market data:")
        for key in sorted(sample.keys())[:20]:  # Show first 20 fields
            print(f"  - {key}")

        # Count by category
        categories = {}
        for m in all_markets:
            cat = m.get('category', 'unknown') or 'none'
            categories[cat] = categories.get(cat, 0) + 1

        print(f"\nMarkets by category:")
        for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {cat:20s}: {count:5d} ({count/len(all_markets)*100:.1f}%)")

        # Liquidity distribution
        liquidities = [m.get('liquidityNum', 0) for m in all_markets if m.get('liquidityNum', 0) > 0]
        print(f"\nLiquidity statistics:")
        print(f"  Markets with liquidity > 0: {len(liquidities)}")
        if liquidities:
            print(f"  Average: ${sum(liquidities)/len(liquidities):,.2f}")
            print(f"  Median: ${sorted(liquidities)[len(liquidities)//2]:,.2f}")
            print(f"  Min: ${min(liquidities):,.2f}")
            print(f"  Max: ${max(liquidities):,.2f}")

        # Volume distribution
        volumes = [m.get('volumeNum', 0) for m in all_markets if m.get('volumeNum', 0) > 0]
        print(f"\nVolume statistics:")
        print(f"  Markets with volume > 0: {len(volumes)}")
        if volumes:
            print(f"  Average: ${sum(volumes)/len(volumes):,.2f}")
            print(f"  Median: ${sorted(volumes)[len(volumes)//2]:,.2f}")
            print(f"  Min: ${min(volumes):,.2f}")
            print(f"  Max: ${max(volumes):,.2f}")

        # End date distribution
        today = datetime.now()
        end_dates = []
        for m in all_markets:
            end_date_str = m.get('endDate')
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    days_until = (end_date - today).days
                    end_dates.append(days_until)
                except:
                    pass

        if end_dates:
            print(f"\nEnd date distribution:")
            print(f"  Markets ending in < 7 days: {sum(1 for d in end_dates if 0 <= d < 7)}")
            print(f"  Markets ending in 7-30 days: {sum(1 for d in end_dates if 7 <= d < 30)}")
            print(f"  Markets ending in 30-90 days: {sum(1 for d in end_dates if 30 <= d < 90)}")
            print(f"  Markets ending in 90-365 days: {sum(1 for d in end_dates if 90 <= d < 365)}")
            print(f"  Markets ending in 365+ days: {sum(1 for d in end_dates if d >= 365)}")
            print(f"  Markets already ended: {sum(1 for d in end_dates if d < 0)}")

if __name__ == "__main__":
    test_pagination()
