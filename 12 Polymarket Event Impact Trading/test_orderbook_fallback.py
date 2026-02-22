#!/usr/bin/env python3
"""
Test orderbook fallback behavior in production scenario.
"""

import sys
import time
sys.path.insert(0, 'src')

from core.polymarket_client import PolymarketClient

# Initialize client with WebSocket (like production)
client = PolymarketClient()
client.initialize_orderbook_manager(source='websocket')

# Wait a moment for WebSocket to initialize
time.sleep(2)

# Get a real market
market_id = '0x0733ad8324639e31f337a88842f4ad78cff949be61cc0a56e6acefe48a87d435'
token_ids = client.get_token_ids(market_id)
yes_token = token_ids['yes_token_id']

print(f"Testing with token: {yes_token[:40]}...\n")

# Test orderbook retrieval (simulating what the bot does)
print("1. Getting orderbook via client.get_orderbook():")
orderbook = client.get_orderbook(yes_token)
print(f"   Bids: {len(orderbook.get('bids', []))}")
print(f"   Asks: {len(orderbook.get('asks', []))}")

if not orderbook.get('bids'):
    print("\n❌ Empty orderbook! Testing fallback directly...")

    print("\n2. Testing synthetic orderbook directly:")
    synthetic = client.get_synthetic_orderbook(yes_token)
    print(f"   Bids: {len(synthetic.get('bids', []))}")
    print(f"   Asks: {len(synthetic.get('asks', []))}")

    if synthetic.get('asks'):
        print(f"   Best ask: {synthetic['asks'][0]}")

    print("\n3. Checking orderbook manager state:")
    if client._orderbook_manager:
        stats = client._orderbook_manager.get_stats()
        print(f"   Source: {stats.get('source')}")
        print(f"   Running: {stats.get('running')}")
        print(f"   Stats: {stats}")

print("\n✅ Test complete")
