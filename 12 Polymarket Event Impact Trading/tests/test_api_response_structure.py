"""Test API response structure to understand data format."""

import sys
import os
from datetime import datetime, timezone, timedelta
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.polymarket_client import PolymarketClient


def test_response_structure():
    """Examine API response structure."""
    client = PolymarketClient()
    now = datetime.now(timezone.utc)

    print("=" * 60)
    print("API RESPONSE STRUCTURE TEST")
    print("=" * 60)

    # Get a few markets
    markets = client.get_markets(limit=5, active=True)

    print(f"\nResponse type: {type(markets)}")
    print(f"Number of markets: {len(markets)}")

    if markets:
        print(f"\n--- First market structure ---")
        m = markets[0]
        print(f"Type: {type(m)}")
        print(f"\nKeys available:")
        for key in sorted(m.keys()):
            value = m[key]
            if isinstance(value, (str, int, float, bool)):
                print(f"  {key:20s}: {value}")
            elif isinstance(value, dict):
                print(f"  {key:20s}: dict with keys {list(value.keys())[:5]}")
            elif isinstance(value, list):
                print(f"  {key:20s}: list with {len(value)} items")
            else:
                print(f"  {key:20s}: {type(value)}")

        print(f"\n--- clobRewards structure ---")
        if 'clobRewards' in m:
            rewards = m['clobRewards']
            print(f"Type: {type(rewards)}")
            if isinstance(rewards, dict):
                for key, value in rewards.items():
                    print(f"  {key:20s}: {value}")
            elif isinstance(rewards, list):
                print(f"List with {len(rewards)} items")
                if rewards:
                    print(f"First item: {rewards[0]}")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    test_response_structure()
