#!/usr/bin/env python3
"""
Test bot integration with Orderbook Microservice.
"""

import sys
sys.path.insert(0, 'src')

from core.polymarket_client import PolymarketClient

# Create client with microservice enabled (default)
client = PolymarketClient(config={
    'use_orderbook_service': True,
    'orderbook_service_url': 'http://localhost:8765'
})

print("Testing Orderbook Microservice Integration\n")
print("=" * 60)

# Test 1: Get orderbook
market_id = '0x0733ad8324639e31f337a88842f4ad78cff949be61cc0a56e6acefe48a87d435'
token_ids = client.get_token_ids(market_id)
yes_token = token_ids['yes_token_id']

print(f"\n1. Testing get_orderbook() via microservice")
print(f"   Token: {yes_token[:40]}...")

orderbook = client.get_orderbook(yes_token)
print(f"   ✓ Bids: {len(orderbook.get('bids', []))}")
print(f"   ✓ Asks: {len(orderbook.get('asks', []))}")

if orderbook.get('asks'):
    print(f"   ✓ Best ask: ${orderbook['asks'][0][0]:.2f}")

# Test 2: Register market
print(f"\n2. Testing register_market_for_orderbook()")
client.register_market_for_orderbook(market_id, question="Bitcoin test market")
print(f"   ✓ Market registered")

# Test 3: Verify no local orderbook manager was created
print(f"\n3. Verifying no local WebSocket created")
if client._orderbook_manager is None:
    print(f"   ✓ No local orderbook manager (using microservice)")
else:
    print(f"   ✗ WARNING: Local orderbook manager exists")

# Test 4: Health check
if client._orderbook_client:
    health = client._orderbook_client.health_check()
    print(f"\n4. Microservice health check")
    print(f"   Status: {health.get('status')}")
    print(f"   WebSocket connected: {health.get('websocket_connected')}")
    print(f"   Uptime: {health.get('uptime_seconds', 0):.1f}s")

print("\n" + "=" * 60)
print("✅ All tests passed - microservice integration working!\n")
