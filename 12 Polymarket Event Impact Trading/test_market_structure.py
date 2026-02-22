"""Quick test to see the actual market data structure."""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from core.polymarket_client import PolymarketClient, MarketFilter

# Initialize client
client = PolymarketClient()

# Get one market
markets = MarketFilter.discover_markets(
    client=client,
    category='crypto',
    min_hours_to_expiry=24,
    max_hours_to_expiry=72,
    min_volume=200,
    max_pages=1
)

if markets:
    print("Sample market structure:")
    print(json.dumps(markets[0], indent=2))
    print("\n\nKey fields:")
    print(f"  conditionId: {markets[0].get('conditionId')}")
    print(f"  outcomePrices: {markets[0].get('outcomePrices')}")
    print(f"  bestBid: {markets[0].get('bestBid')}")
    print(f"  bestAsk: {markets[0].get('bestAsk')}")
    print(f"  question: {markets[0].get('question', '')[:60]}")
