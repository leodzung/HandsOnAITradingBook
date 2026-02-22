"""
Test if we can discover the BTC 5m event.
"""
import sys
from pathlib import Path
import requests

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient, MarketFilter
from core.price_fetcher import PriceFetcher

def test_btc_5m_event():
    """Check if we can find the BTC 5m event."""

    # Extract slug from URL
    slug = "btc-updown-5m-1771027800"

    print("=" * 80)
    print(f"Testing Event: {slug}")
    print("=" * 80)

    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)

    # Test 1: Try to fetch event directly
    print("\n--- TEST 1: Fetch event directly ---")
    event = client.get_event(slug)

    if event:
        print(f"✅ Found event: {event.get('title', 'N/A')}")
        print(f"Description: {event.get('description', 'N/A')[:200]}...")

        markets = event.get('markets', [])
        print(f"\nFound {len(markets)} markets:")

        for i, market in enumerate(markets, 1):
            question = market.get('question', 'N/A')
            end_date = market.get('endDate', market.get('endDateIso', 'N/A'))
            volume = market.get('volume', 0)
            closed = market.get('closed', False)

            print(f"\n{i}. {question}")
            print(f"   End date: {end_date}")
            print(f"   Volume: ${float(volume):,.2f}" if volume else "   Volume: N/A")
            print(f"   Closed: {closed}")
    else:
        print(f"❌ Could not fetch event '{slug}'")
        return

    # Test 2: Check if discoverable via API
    print("\n" + "=" * 80)
    print("TEST 2: Check if discoverable via /markets endpoint")
    print("=" * 80)

    # Try to find by searching with very short expiry window
    discovered = MarketFilter.discover_markets(
        client=client,
        category='crypto',
        min_hours_to_expiry=0,
        max_hours_to_expiry=1,  # Very short window (< 1 hour)
        min_volume=0,
        min_liquidity=0,
        max_pages=1,
        include_crypto_events=False  # Don't use event-based discovery
    )

    # Check if any of our markets are in discovered list
    market_ids = [m.get('conditionId') for m in markets]
    found_in_api = [m for m in discovered if m.get('conditionId') in market_ids]

    print(f"\nDiscovered {len(discovered)} markets with <1h expiry")
    print(f"Found {len(found_in_api)}/{len(markets)} of our event's markets in API results")

    if found_in_api:
        print("✅ These markets ARE discoverable via /markets API")
    else:
        print("❌ These markets NOT in /markets API (might be restricted)")

    # Test 3: Check prices and liquidity
    print("\n" + "=" * 80)
    print("TEST 3: Check prices and liquidity")
    print("=" * 80)

    for i, market in enumerate(markets[:3], 1):  # Check first 3 markets
        question = market.get('question', 'N/A')
        condition_id = market.get('conditionId')

        print(f"\n{i}. {question}")
        print(f"   Condition ID: {condition_id}")

        # Get prices
        entry_prices = price_fetcher.get_entry_prices(condition_id)

        if entry_prices:
            print(f"   Entry prices (ASK): YES=${entry_prices.yes_price:.3f}, NO=${entry_prices.no_price:.3f}")

            # Check if tradeable
            max_entry = 0.90
            tradeable_yes = entry_prices.yes_price <= max_entry
            tradeable_no = entry_prices.no_price <= max_entry

            if tradeable_yes or tradeable_no:
                sides = []
                if tradeable_yes:
                    sides.append(f"YES@${entry_prices.yes_price:.3f}")
                if tradeable_no:
                    sides.append(f"NO@${entry_prices.no_price:.3f}")
                print(f"   ✅ TRADEABLE: {', '.join(sides)}")
            else:
                print(f"   ❌ NOT TRADEABLE: Both prices > ${max_entry}")
        else:
            print(f"   ❌ Could not fetch prices")

    # Test 4: Would short-expiry bot find these?
    print("\n" + "=" * 80)
    print("TEST 4: Would short-expiry bot discover these?")
    print("=" * 80)

    # Ultra-short bucket (0-24 hours)
    ultra_short = MarketFilter.discover_markets(
        client=client,
        category='crypto',
        min_hours_to_expiry=0,
        max_hours_to_expiry=24,
        min_volume=0,
        min_liquidity=0,
        max_pages=3,
        include_crypto_events=True,
        crypto_event_days_ahead=7
    )

    found_in_bot = [m for m in ultra_short if m.get('conditionId') in market_ids]

    print(f"\nUltra-short bot discovered {len(ultra_short)} total markets")
    print(f"Found {len(found_in_bot)}/{len(markets)} of our event's markets")

    if found_in_bot:
        print(f"✅ SHORT-EXPIRY BOT WOULD FIND THESE MARKETS")
    else:
        print(f"❌ SHORT-EXPIRY BOT WOULD NOT FIND THESE MARKETS")
        print(f"\nReason: These markets may be:")
        print(f"  - Too short-lived (API might not index them)")
        print(f"  - Restricted/unlisted")
        print(f"  - Need to be fetched via event slug directly")

if __name__ == "__main__":
    test_btc_5m_event()
