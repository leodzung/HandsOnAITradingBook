"""
Test market discovery for short-expiry trading bot.

This script tests:
1. API connectivity
2. Market discovery across 3 buckets
3. Crypto filtering
4. Quality filters (spread, price range)
"""

import sys
import os
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.bots.trader_short_expiry import ShortExpiryTrader


def test_market_discovery():
    """Test market discovery."""
    print("=" * 60)
    print("MARKET DISCOVERY TEST")
    print("=" * 60)

    # Initialize trader
    trader = ShortExpiryTrader('config/config_short_expiry.json')

    print("\nDiscovering markets across 3 buckets...")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    # Discover markets
    markets = trader.discover_markets()

    # Print results
    print(f"Results:")
    print(f"  Ultra-short (2-24h):  {len(markets['ultra_short']):3d} markets")
    print(f"  Short (1-3 days):     {len(markets['short']):3d} markets")
    print(f"  Medium (3-7 days):    {len(markets['medium']):3d} markets")
    print(f"  TOTAL:                {sum(len(m) for m in markets.values()):3d} markets")

    # Show sample markets from each bucket
    for bucket_name, bucket_markets in markets.items():
        if len(bucket_markets) > 0:
            print(f"\n--- Sample from {bucket_name.upper()} bucket ---")
            for i, market in enumerate(bucket_markets[:3]):  # Show first 3
                question = market.get('question', 'N/A')
                volume = float(market.get('volume24hr', 0))
                liquidity = float(market.get('liquidity', 0))

                # Get prices
                yes_price = market.get('lastTradePrice', 0.5)
                if isinstance(yes_price, str):
                    yes_price = float(yes_price)

                spread_pct = trader._get_spread_pct(market)

                print(f"{i+1}. {question[:60]}")
                print(f"   Price: {yes_price:.3f} | Vol: ${volume:.0f} | Liq: ${liquidity:.0f} | Spread: {spread_pct:.2f}%")
        else:
            print(f"\n--- {bucket_name.upper()} bucket: No markets found ---")

    print("\n" + "=" * 60)
    print("✓ Market discovery test complete")
    print("=" * 60)


def main():
    """Entry point."""
    try:
        test_market_discovery()
        return 0
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit(main())
