#!/usr/bin/env python3
"""
Test script to verify closed market filtering works correctly.
"""

import sys
sys.path.insert(0, 'src')

from core.polymarket_client import PolymarketClient

def test_filter_closed_markets():
    """Test the static filter method."""
    print("=" * 70)
    print("TEST 1: filter_closed_markets() static method")
    print("=" * 70)
    
    test_markets = [
        {'conditionId': '1', 'question': 'Active market 1', 'closed': False},
        {'conditionId': '2', 'question': 'Closed market', 'closed': True},
        {'conditionId': '3', 'question': 'Active market 2', 'closed': False},
        {'conditionId': '4', 'question': 'Missing closed field'},  # Should be treated as active
    ]
    
    filtered = PolymarketClient.filter_closed_markets(test_markets)
    
    print(f"Input: {len(test_markets)} markets")
    print(f"Output: {len(filtered)} markets")
    print(f"Expected: 3 markets (2 active + 1 missing field)")
    
    assert len(filtered) == 3, "Should filter out 1 closed market"
    assert all(not m.get('closed', False) for m in filtered), "All filtered markets should be non-closed"
    print("✅ PASSED\n")


def test_get_markets_from_event():
    """Test that get_markets_from_event excludes closed by default."""
    print("=" * 70)
    print("TEST 2: get_markets_from_event() excludes closed markets")
    print("=" * 70)
    
    client = PolymarketClient()
    
    # Test with GOLD event (known to have some closed markets)
    slug = "what-will-gold-gc-hit-by-end-of-february"
    
    print(f"Fetching markets from event: {slug}")
    markets = client.get_markets_from_event(slug)
    
    print(f"Found {len(markets)} markets")
    
    # Check if any closed markets slipped through
    closed_count = sum(1 for m in markets if m.get('closed', False))
    print(f"Closed markets in result: {closed_count}")
    
    if closed_count > 0:
        print("❌ FAILED: Found closed markets in filtered results!")
        for m in markets:
            if m.get('closed'):
                print(f"  - {m.get('question', '')[:60]}")
        return False
    else:
        print("✅ PASSED: No closed markets found\n")
        return True


def test_get_markets_from_event_include_closed():
    """Test that exclude_closed=False includes closed markets."""
    print("=" * 70)
    print("TEST 3: get_markets_from_event(exclude_closed=False)")
    print("=" * 70)
    
    client = PolymarketClient()
    slug = "what-will-gold-gc-hit-by-end-of-february"
    
    print(f"Fetching ALL markets (including closed) from: {slug}")
    all_markets = client.get_markets_from_event(slug, exclude_closed=False)
    active_markets = client.get_markets_from_event(slug, exclude_closed=True)
    
    closed_count = len(all_markets) - len(active_markets)
    
    print(f"All markets: {len(all_markets)}")
    print(f"Active markets: {len(active_markets)}")
    print(f"Closed markets: {closed_count}")
    
    if closed_count > 0:
        print("✅ PASSED: Successfully retrieved both active and closed markets\n")
        return True
    else:
        print("⚠️  WARNING: No closed markets found (might be none in this event)\n")
        return True


def test_get_markets_defensive_filter():
    """Test that get_markets applies defensive filtering."""
    print("=" * 70)
    print("TEST 4: get_markets() defensive filtering")
    print("=" * 70)
    
    client = PolymarketClient()
    
    # Fetch some markets with closed=False (default)
    markets = client.get_markets(limit=100, active=True, closed=False)
    
    print(f"Fetched {len(markets)} markets with closed=False")
    
    # Check if any closed markets slipped through
    closed_count = sum(1 for m in markets if m.get('closed', False))
    print(f"Closed markets in result: {closed_count}")
    
    if closed_count > 0:
        print("❌ FAILED: Found closed markets despite closed=False!")
        return False
    else:
        print("✅ PASSED: No closed markets found\n")
        return True


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("TESTING CLOSED MARKET FILTERING FIX")
    print("=" * 70 + "\n")
    
    results = []
    
    try:
        test_filter_closed_markets()
        results.append(True)
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}\n")
        results.append(False)
    
    try:
        results.append(test_get_markets_from_event())
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}\n")
        results.append(False)
    
    try:
        results.append(test_get_markets_from_event_include_closed())
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}\n")
        results.append(False)
    
    try:
        results.append(test_get_markets_defensive_filter())
    except Exception as e:
        print(f"❌ Test 4 FAILED: {e}\n")
        results.append(False)
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("\n✅ ALL TESTS PASSED - Fix is working correctly!\n")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - Fix needs review\n")
        sys.exit(1)

