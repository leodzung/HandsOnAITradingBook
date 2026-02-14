#!/usr/bin/env python3
"""
Debug script to investigate token ID lookup issue.
"""

import sys
sys.path.insert(0, 'src')

from core.polymarket_client import PolymarketClient, MarketFilter
import json

print("="*70)
print("DEBUG: Token ID Lookup Issue")
print("="*70)

# Initialize client
client = PolymarketClient()

# Step 1: Discover a short-expiry crypto market
print("\n1. Discovering short-expiry crypto markets...")
markets = MarketFilter.discover_markets(
    client=client,
    category='crypto',
    min_hours_to_expiry=0,
    max_hours_to_expiry=24,
    min_volume=100,
    min_liquidity=50,
    max_pages=1,
    include_crypto_events=True,
    crypto_event_days_ahead=1
)

print(f"   Found {len(markets)} markets")

if not markets:
    print("   No markets found - exiting")
    sys.exit(1)

# Pick first market
market = markets[0]
print(f"\n2. Selected market: {market.get('question', 'Unknown')[:60]}")

# Get market details
condition_id = market.get('conditionId')
print(f"   Condition ID: {condition_id}")

# Check if market has clobTokenIds
clob_token_ids_str = market.get('clobTokenIds', '[]')
print(f"   clobTokenIds (raw): {clob_token_ids_str}")

try:
    clob_token_ids = json.loads(clob_token_ids_str) if isinstance(clob_token_ids_str, str) else clob_token_ids_str
    print(f"   clobTokenIds (parsed): {clob_token_ids}")
except:
    clob_token_ids = []
    print(f"   clobTokenIds: Failed to parse")

# Step 3: Try to get token IDs using get_token_ids
print(f"\n3. Trying get_token_ids('{condition_id}')...")
token_ids = client.get_token_ids(condition_id)
print(f"   Result: {token_ids}")

# Step 4: Try to get CLOB market directly
print(f"\n4. Trying get_clob_market('{condition_id}')...")
clob_market = client.get_clob_market(condition_id)
if clob_market:
    print(f"   ✓ Found CLOB market!")
    print(f"   Tokens: {clob_market.get('tokens', [])}")
else:
    print(f"   ✗ CLOB market NOT found")

# Step 5: Check if we can use clobTokenIds from Gamma API directly
print(f"\n5. Can we use clobTokenIds from Gamma API?")
if clob_token_ids and len(clob_token_ids) >= 2:
    print(f"   ✓ YES! clobTokenIds available: {clob_token_ids}")
    print(f"   We can use these directly without calling CLOB API!")

    # Test if these token IDs work for orderbook
    test_token_id = clob_token_ids[0]
    print(f"\n6. Testing orderbook with token_id: {test_token_id}")
    orderbook = client.get_orderbook(test_token_id)

    if orderbook and (orderbook.get('asks') or orderbook.get('bids')):
        print(f"   ✓ Orderbook retrieved!")
        print(f"   Asks: {len(orderbook.get('asks', []))} levels")
        print(f"   Bids: {len(orderbook.get('bids', []))} levels")
        if orderbook.get('asks'):
            print(f"   Best ask: ${orderbook['asks'][0][0]:.3f}")
        if orderbook.get('bids'):
            print(f"   Best bid: ${orderbook['bids'][0][0]:.3f}")
    else:
        print(f"   ✗ Empty orderbook")
        print(f"   Orderbook: {orderbook}")
else:
    print(f"   ✗ NO - clobTokenIds not available or insufficient")

# Step 6: Check market structure
print(f"\n7. Full market structure keys:")
print(f"   {list(market.keys())}")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)

if clob_token_ids and len(clob_token_ids) >= 2:
    print("✓ SOLUTION FOUND:")
    print(f"  Markets from Gamma API already contain 'clobTokenIds' field")
    print(f"  We should use this directly instead of calling get_token_ids()")
    print(f"  Token IDs: {clob_token_ids}")
else:
    print("✗ PROBLEM:")
    print(f"  Market doesn't have clobTokenIds")
    print(f"  Need to investigate alternative token ID lookup method")

print("="*70)
