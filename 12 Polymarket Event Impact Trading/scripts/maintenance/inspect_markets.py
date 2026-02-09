#!/usr/bin/env python3
"""
Inspect available price-level markets.
"""

from polymarket_client import PolymarketClient
from market_parser import PriceLevelMarketParser

client = PolymarketClient()
parser = PriceLevelMarketParser()

print("Fetching markets...")
markets = client.get_markets(limit=100, active=True)
print(f"Total markets: {len(markets)}\n")

price_level_markets = parser.filter_price_level_markets(markets, assets=['BTC', 'ETH'])
print(f"Price-level markets found: {len(price_level_markets)}\n")

print("=" * 80)
for i, pm in enumerate(price_level_markets, 1):
    print(f"{i}. {pm['question']}")
    print(f"   Asset: {pm['asset']}, Strike: ${pm['strike_price']:,.0f}, Direction: {pm['direction']}")
    print(f"   Days to expiry: {pm['days_to_expiry']}")
    print()
