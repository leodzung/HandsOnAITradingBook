#!/usr/bin/env python3
"""
Test WebSocket orderbook integration.

Compares:
1. REST (synthetic) orderbook from /price
2. WebSocket (real) orderbook from live feed
"""

import sys
sys.path.insert(0, 'src')

import json
import time
from core.polymarket_client import PolymarketClient

print("="*70)
print("TESTING WEBSOCKET ORDERBOOK")
print("="*70)

# Test market: ETH $800
cond_id = '0x717672a48c5f2938631f6e467b9a48aedb03fa380c0198704ef5acfc91721612'
question = "Will Ethereum dip to $800 by December 31, 2026?"

# Initialize client with WebSocket config
config = {
    'orderbook_source': 'websocket',
    'orderbook': {'cache_ttl_seconds': 5}
}

client = PolymarketClient(config=config)

# Get token IDs
print(f"\nMarket: {question}")
tokens = client.get_token_ids(cond_id)
no_token = tokens.get('no_token_id')
print(f"NO Token ID: {no_token}")

# Test 1: REST mode (synthetic)
print(f"\n{'='*70}")
print("TEST 1: REST MODE (Synthetic Orderbook)")
print(f"{'='*70}")

rest_client = PolymarketClient(config={'orderbook_source': 'rest'})
rest_client.initialize_orderbook_manager('rest')
rest_book = rest_client.get_orderbook(no_token)

print(f"\nTop 3 Asks:")
for i, ask in enumerate(rest_book['asks'][:3], 1):
    print(f"  {i}. ${ask[0]:.3f} × {ask[1]:.0f} shares")

print(f"\nTop 3 Bids:")
for i, bid in enumerate(rest_book['bids'][:3], 1):
    print(f"  {i}. ${bid[0]:.3f} × {bid[1]:.0f} shares")

# Test 2: WebSocket mode (real)
print(f"\n{'='*70}")
print("TEST 2: WEBSOCKET MODE (Real Orderbook)")
print(f"{'='*70}")

ws_client = PolymarketClient(config={'orderbook_source': 'websocket'})
print("\nInitializing WebSocket...")
ws_client.initialize_orderbook_manager('websocket')

# Register the market
print(f"Registering market...")
ws_client.register_market_for_orderbook(cond_id, question)

# Wait for WebSocket to receive data
print("Waiting 5 seconds for WebSocket data...")
time.sleep(5)

# Get orderbook
ws_book = ws_client.get_orderbook(no_token)

if ws_book and 'asks' in ws_book and ws_book['asks']:
    print(f"\n✅ WebSocket orderbook received!")
    print(f"\nTop 3 Asks:")
    for i, ask in enumerate(ws_book['asks'][:3], 1):
        price = ask[0] if isinstance(ask, list) else ask['price']
        size = ask[1] if isinstance(ask, list) else ask['size']
        print(f"  {i}. ${price:.3f} × {size:.0f} shares")

    print(f"\nTop 3 Bids:")
    for i, bid in enumerate(ws_book['bids'][:3], 1):
        price = bid[0] if isinstance(bid, list) else bid['price']
        size = bid[1] if isinstance(bid, list) else bid['size']
        print(f"  {i}. ${price:.3f} × {size:.0f} shares")
else:
    print(f"\n⚠️ No WebSocket data received (may need more time or market is inactive)")
    print(f"Orderbook: {ws_book}")

# Comparison
print(f"\n{'='*70}")
print("COMPARISON")
print(f"{'='*70}")

rest_ask = rest_book['asks'][0][0] if rest_book['asks'] else None
if ws_book and ws_book.get('asks'):
    ws_ask_data = ws_book['asks'][0]
    ws_ask = ws_ask_data[0] if isinstance(ws_ask_data, list) else ws_ask_data['price']

    print(f"\nREST best ask:  ${rest_ask:.3f} (synthetic)")
    print(f"WebSocket ask:  ${ws_ask:.3f} (real)")

    if abs(rest_ask - ws_ask) < 0.05:
        print(f"✅ Prices match! (difference: ${abs(rest_ask - ws_ask):.3f})")
    else:
        print(f"⚠️ Prices differ by ${abs(rest_ask - ws_ask):.3f}")
        print(f"   WebSocket provides REAL orderbook data!")
else:
    print(f"\nREST best ask: ${rest_ask:.3f}")
    print(f"WebSocket: No data yet")

print(f"\n{'='*70}")
print("Test complete!")
print("="*70)

# Cleanup
ws_client._orderbook_manager.stop() if ws_client._orderbook_manager else None
