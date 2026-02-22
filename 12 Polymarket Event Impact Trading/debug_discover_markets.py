"""
Debug the discover_markets flow to find where markets are being lost.
"""

import json
import sys
import os
from datetime import datetime, timedelta, timezone

sys.path.insert(0, '.')

from src.core.polymarket_client import PolymarketClient, MarketFilter

# Load config
config = json.load(open('config/config_short_expiry.json'))
client = PolymarketClient(config=config)

# Calculate date range for ultra-short
min_hours = 0
max_hours = 24
now = datetime.now(timezone.utc)
end_date_min = (now + timedelta(hours=min_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
end_date_max = (now + timedelta(hours=max_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

print("="*80)
print("DEBUG: DISCOVER_MARKETS FLOW FOR ULTRA-SHORT (0-24h)")
print("="*80)

print(f"\nTime filter:")
print(f"  end_date_min: {end_date_min}")
print(f"  end_date_max: {end_date_max}")

# Step 1: Fetch from /markets endpoint
print("\n" + "="*80)
print("STEP 1: Fetch from /markets endpoint")
print("="*80)

markets_from_api = []
for page in range(3):
    offset = page * 100
    batch = client.get_markets(
        limit=100,
        offset=offset,
        active=True,
        closed=False,
        end_date_min=end_date_min,
        end_date_max=end_date_max,
        volume_num_min=100,
        liquidity_num_min=50
    )
    if not batch:
        break
    markets_from_api.extend(batch)

print(f"✓ Retrieved {len(markets_from_api)} markets from API")

if markets_from_api:
    print(f"\nSample market from API:")
    m = markets_from_api[0]
    print(f"  Question: {m.get('question', '')}")
    print(f"  End date: {m.get('endDate') or m.get('endDateIso')}")
    print(f"  Active: {m.get('active')}")
    print(f"  Closed: {m.get('closed')}")
    print(f"  Volume: ${float(m.get('volume', 0)):,.0f}")

# Step 2: Fetch from crypto events
print("\n" + "="*80)
print("STEP 2: Fetch from crypto events")
print("="*80)

event_slugs = MarketFilter.get_all_crypto_event_slugs(days_ahead=1)
print(f"Event slugs to fetch: {len(event_slugs)}")
for slug in event_slugs:
    print(f"  - {slug}")

event_markets = []
for slug in event_slugs:
    try:
        event_batch = client.get_markets_from_event(slug)
        if event_batch:
            event_markets.extend(event_batch)
            print(f"  ✓ {len(event_batch)} markets from '{slug}'")
    except Exception as e:
        print(f"  ✗ Error fetching '{slug}': {e}")

print(f"\n✓ Retrieved {len(event_markets)} markets from events")

# Deduplicate
seen_ids = {m.get('conditionId') for m in markets_from_api if m.get('conditionId')}
new_markets = [m for m in event_markets if m.get('conditionId') not in seen_ids]
all_markets = markets_from_api + new_markets

print(f"\n✓ Total after dedup: {len(all_markets)} markets")

if event_markets:
    print(f"\nSample market from events:")
    m = event_markets[0]
    print(f"  Question: {m.get('question', '')}")
    print(f"  End date: {m.get('endDate') or m.get('endDateIso')}")
    print(f"  Active: {m.get('active')}")
    print(f"  Closed: {m.get('closed')}")

# Step 3: Filter by active status
print("\n" + "="*80)
print("STEP 3: Filter by active status")
print("="*80)

active_markets = MarketFilter.filter_active_only(all_markets)
print(f"✓ {len(active_markets)} markets are active (removed {len(all_markets) - len(active_markets)})")

# Step 4: Filter by time to expiry
print("\n" + "="*80)
print("STEP 4: Filter by time to expiry")
print("="*80)

time_filtered = MarketFilter.filter_by_time_to_expiry(
    active_markets,
    min_hours=min_hours,
    max_hours=max_hours
)
print(f"✓ {len(time_filtered)} markets in {min_hours}-{max_hours}h range (removed {len(active_markets) - len(time_filtered)})")

if len(time_filtered) < len(active_markets):
    # Show why some were removed
    removed = len(active_markets) - len(time_filtered)
    print(f"\n⚠️  {removed} markets removed by time filter!")

    # Check a sample removed market
    for m in active_markets:
        if m not in time_filtered:
            end_date_str = m.get('endDate') or m.get('endDateIso')
            if end_date_str:
                try:
                    end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                    hours_to_expiry = (end_date - now).total_seconds() / 3600
                    print(f"\n  Example removed market:")
                    print(f"    Question: {m.get('question', '')[:60]}")
                    print(f"    End date: {end_date_str}")
                    print(f"    Hours to expiry: {hours_to_expiry:.1f}h")
                    print(f"    In range [{min_hours}, {max_hours}]? {min_hours <= hours_to_expiry <= max_hours}")
                    break
                except:
                    pass

# Step 5: Filter by crypto category
print("\n" + "="*80)
print("STEP 5: Filter by crypto category")
print("="*80)

crypto_markets = MarketFilter.filter_crypto_markets(time_filtered)
print(f"✓ {len(crypto_markets)} crypto markets (removed {len(time_filtered) - len(crypto_markets)})")

if len(crypto_markets) < len(time_filtered):
    print(f"\n⚠️  {len(time_filtered) - len(crypto_markets)} markets removed by crypto filter!")

    # Show sample non-crypto markets
    non_crypto = [m for m in time_filtered if m not in crypto_markets]
    print(f"\n  Sample non-crypto markets:")
    for i, m in enumerate(non_crypto[:5]):
        print(f"    [{i+1}] {m.get('question', '')[:60]}")

print("\n" + "="*80)
print("FINAL RESULT")
print("="*80)
print(f"✓ {len(crypto_markets)} ultra-short crypto markets discovered")

if len(crypto_markets) == 0:
    print("\n❌ NO MARKETS FOUND!")
    print("\nDiagnosis:")
    if len(all_markets) == 0:
        print("  - No markets fetched from API or events")
    elif len(active_markets) == 0:
        print("  - All markets filtered out by active status check")
    elif len(time_filtered) == 0:
        print("  - All markets filtered out by time-to-expiry check")
    elif len(crypto_markets) == 0:
        print("  - All markets filtered out by crypto keyword check")
