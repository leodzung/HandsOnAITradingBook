#!/usr/bin/env python3
"""Test URL building fix for standalone vs multi-market events."""

import sys
sys.path.insert(0, 'src')

from core.polymarket_client import PolymarketClient

print("=" * 70)
print("Testing URL Builder Fix")
print("=" * 70)
print()

# Test 1: Multi-market event (using asset)
print("TEST 1: Multi-market BTC event (asset='BTC')")
url = PolymarketClient.build_market_url(asset='BTC')
print(f"  Result: {url}")
print(f"  Expected: https://polymarket.com/event/what-price-will-bitcoin-hit-before-2027")
assert 'event' in url and 'bitcoin' in url, "Should be event URL"
print("  ✅ PASS")
print()

# Test 2: Standalone market (with slug)
print("TEST 2: Standalone BTC market (market slug + asset)")
standalone_slug = 'will-bitcoin-dip-to-30000-by-december-31-2026-971-191-116-343-999'
url = PolymarketClient.build_market_url(
    market={'slug': standalone_slug},
    asset='BTC'  # Should NOT override the market slug!
)
print(f"  Result: {url}")
print(f"  Expected: https://polymarket.com/market/{standalone_slug}")
assert 'market' in url and 'dip-to-30000' in url, "Should be market URL, not event URL"
assert 'event' not in url, "Should NOT be event URL"
print("  ✅ PASS")
print()

# Test 3: Multi-market ETH event
print("TEST 3: Multi-market ETH event (asset='ETH')")
url = PolymarketClient.build_market_url(asset='ETH')
print(f"  Result: {url}")
print(f"  Expected: https://polymarket.com/event/what-price-will-ethereum-hit-before-2027")
assert 'event' in url and 'ethereum' in url, "Should be event URL"
print("  ✅ PASS")
print()

# Test 4: Standalone GOLD market (not part of multi-market event)
print("TEST 4: Standalone market with asset hint")
standalone_gold = 'will-gold-hit-6500-standalone-example'
url = PolymarketClient.build_market_url(
    market_slug=standalone_gold,
    asset='GOLD'
)
print(f"  Result: {url}")
print(f"  Expected: https://polymarket.com/market/{standalone_gold}")
assert 'market' in url, "Should be market URL"
assert 'event' not in url, "Should NOT be event URL"
print("  ✅ PASS")
print()

# Test 5: Event slug takes priority
print("TEST 5: Event slug priority (should override asset)")
url = PolymarketClient.build_market_url(
    event_slug='my-custom-event',
    asset='BTC'
)
print(f"  Result: {url}")
print(f"  Expected: https://polymarket.com/event/my-custom-event")
assert url == 'https://polymarket.com/event/my-custom-event', "Event slug should take priority"
print("  ✅ PASS")
print()

print("=" * 70)
print("ALL TESTS PASSED! ✅")
print("=" * 70)
print()
print("URL builder now correctly distinguishes:")
print("  - Multi-market events → /event/...")
print("  - Standalone markets → /market/...")
print()
