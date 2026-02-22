"""
Test if we can discover markets from the Bitcoin Feb 14 event.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient, MarketFilter

def test_bitcoin_feb14_discovery():
    """Test if we can find the Bitcoin Feb 14 markets."""

    # Initialize client
    client = PolymarketClient()

    # Test 1: Check if the slug is in our generated list
    print("=" * 80)
    print("TEST 1: Checking if slug is in generated daily crypto event slugs")
    print("=" * 80)

    today = datetime.now(timezone.utc)
    print(f"Today is: {today.strftime('%Y-%m-%d')}")

    # Generate slugs for next 7 days
    daily_slugs = MarketFilter.get_daily_crypto_event_slugs(days_ahead=7)

    print(f"\nGenerated {len(daily_slugs)} daily crypto event slugs:")
    for slug in daily_slugs:
        if 'bitcoin' in slug:
            print(f"  - {slug}")

    target_slug = "bitcoin-above-on-february-14"
    if target_slug in daily_slugs:
        print(f"\n✅ Target slug '{target_slug}' IS in generated list")
    else:
        print(f"\n❌ Target slug '{target_slug}' is NOT in generated list")

    # Test 2: Try to fetch event directly
    print("\n" + "=" * 80)
    print("TEST 2: Fetching event directly from API")
    print("=" * 80)

    event = client.get_event(target_slug)

    if event:
        print(f"\n✅ Successfully fetched event: {event.get('title', 'N/A')}")
        markets = event.get('markets', [])
        print(f"Found {len(markets)} markets in event:")

        for i, market in enumerate(markets[:10], 1):  # Show first 10
            question = market.get('question', 'N/A')
            condition_id = market.get('conditionId', 'N/A')
            closed = market.get('closed', False)
            print(f"  {i}. {question}")
            print(f"     - Condition ID: {condition_id}")
            print(f"     - Closed: {closed}")

        if len(markets) > 10:
            print(f"  ... and {len(markets) - 10} more markets")
    else:
        print(f"\n❌ Could not fetch event '{target_slug}'")

    # Test 3: Try to get markets from event (with filtering)
    print("\n" + "=" * 80)
    print("TEST 3: Getting markets from event (excluding closed)")
    print("=" * 80)

    markets = client.get_markets_from_event(target_slug, exclude_closed=True)

    if markets:
        print(f"\n✅ Found {len(markets)} active markets from event")

        for i, market in enumerate(markets[:5], 1):
            question = market.get('question', 'N/A')
            end_date = market.get('endDate', market.get('endDateIso', 'N/A'))
            volume = market.get('volume', 0)
            try:
                volume_float = float(volume)
                volume_str = f"${volume_float:,.2f}"
            except:
                volume_str = str(volume)
            print(f"  {i}. {question}")
            print(f"     - End date: {end_date}")
            print(f"     - Volume: {volume_str}")
    else:
        print(f"\n❌ No active markets found from event")

    # Test 4: Test unified discover_markets method
    print("\n" + "=" * 80)
    print("TEST 4: Using unified discover_markets method")
    print("=" * 80)

    discovered_markets = MarketFilter.discover_markets(
        client=client,
        category='crypto',
        min_hours_to_expiry=0,
        max_hours_to_expiry=168,  # 7 days
        min_volume=0,
        min_liquidity=0,
        max_pages=1,
        include_crypto_events=True,
        crypto_event_days_ahead=7
    )

    # Check if any of the discovered markets are from our target event
    btc_feb14_markets = [
        m for m in discovered_markets
        if 'february 14' in m.get('question', '').lower()
        and 'bitcoin' in m.get('question', '').lower()
    ]

    print(f"\nDiscovered {len(discovered_markets)} total crypto markets")
    print(f"Found {len(btc_feb14_markets)} markets matching 'Bitcoin February 14':")

    for i, market in enumerate(btc_feb14_markets[:5], 1):
        question = market.get('question', 'N/A')
        print(f"  {i}. {question}")

    if btc_feb14_markets:
        print(f"\n✅ SUCCESS: Bitcoin Feb 14 markets ARE discoverable via discover_markets()")
    else:
        print(f"\n❌ FAILURE: Bitcoin Feb 14 markets NOT found via discover_markets()")

if __name__ == "__main__":
    test_bitcoin_feb14_discovery()
