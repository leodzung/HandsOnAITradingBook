"""Test why filter_crypto_markets is rejecting everything."""

import json
import sys
import os
sys.path.insert(0, '.')

from src.core.polymarket_client import PolymarketClient, MarketFilter

# Get some markets
config = json.load(open('config/config_short_expiry.json'))
client = PolymarketClient(config=config)

# Get all markets (no filtering)
all_markets = client.get_markets(
    limit=100,
    offset=0,
    active=True,
    closed=False
)

print(f"Retrieved {len(all_markets)} total markets\n")

# Show first 10 market questions
print("First 10 market questions:")
for i, m in enumerate(all_markets[:10]):
    print(f"  [{i+1}] {m.get('question', '')}")

# Test crypto filter
crypto_markets = MarketFilter.filter_crypto_markets(all_markets)

print(f"\nAfter crypto filter: {len(crypto_markets)} markets")

if len(crypto_markets) == 0:
    print("\n❌ ALL MARKETS REJECTED!")

    # Test manually on an Ethereum market
    test_market = {
        'question': 'Will the price of Ethereum be above $1,600 on February 22?',
        'description': 'This market will resolve to "Yes" if...'
    }

    result = MarketFilter.filter_crypto_markets([test_market])
    print(f"\nManual test with ETH market: {len(result)} markets")

    if len(result) == 0:
        # Check the keywords
        question = test_market['question'].lower()
        print(f"\nDEBUG:")
        print(f"  Question: {question}")
        print(f"  Contains 'ethereum': {'ethereum' in question}")
        print(f"  Contains 'eth': {'eth' in question}")

        # Check if sports exclusion is the problem
        import re
        sports_kw = MarketFilter.SPORTS_EXCLUSION_KEYWORDS
        matched_sports = [kw for kw in sports_kw if kw in question]
        print(f"  Matched sports keywords: {matched_sports}")
else:
    print("\n✅ Filter works! Sample crypto markets:")
    for i, m in enumerate(crypto_markets[:5]):
        print(f"  [{i+1}] {m.get('question', '')}")
