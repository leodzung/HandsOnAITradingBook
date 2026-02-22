"""
Test the EXACT discovery logic used by trader_short_expiry.py to find the discrepancy.
"""

import json
import logging
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.polymarket_client import PolymarketClient, MarketFilter
from src.core.price_fetcher import PriceFetcher

# Configure logging like the trader does
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_trader_discovery():
    """Test discovery exactly as trader_short_expiry.py does it."""

    # Load config
    with open('config/config_short_expiry.json', 'r') as f:
        config = json.load(f)

    # Initialize client EXACTLY as trader does
    logger.info("Initializing client...")
    client = PolymarketClient(config=config)
    price_fetcher = PriceFetcher(client)

    # Initialize WebSocket orderbook manager (like trader does at line 263)
    logger.info("Initializing WebSocket orderbook manager...")
    client.initialize_orderbook_manager()

    # Get discovery config
    discovery_config = config['discovery']
    category = 'crypto' if discovery_config.get('crypto_only', False) else None

    print("\n" + "="*80)
    print("TESTING ULTRA-SHORT DISCOVERY (EXACTLY AS TRADER DOES)")
    print("="*80)

    # Call discover_markets EXACTLY as trader does (lines 385-396)
    try:
        ultra_short_markets = MarketFilter.discover_markets(
            client=client,
            category=category,
            min_hours_to_expiry=discovery_config['ultra_short_hours'][0],
            max_hours_to_expiry=discovery_config['ultra_short_hours'][1],
            min_volume=discovery_config['min_volume']['ultra_short'],
            min_liquidity=discovery_config['min_liquidity']['ultra_short'],
            max_pages=3,
            include_crypto_events=True,
            crypto_event_days_ahead=1,
            logger=logger  # Use logger like trader does
        )

        print(f"\n✓ Discovered {len(ultra_short_markets)} markets")

        if len(ultra_short_markets) > 0:
            print("\n✅ DISCOVERY WORKS! Sample markets:")
            for i, m in enumerate(ultra_short_markets[:5]):
                print(f"  [{i+1}] {m.get('question', '')[:60]}")
                print(f"      Volume: ${m.get('volume', 0):,.0f} | "
                      f"Liquidity: ${m.get('liquidity', 0):,.0f}")
        else:
            print("\n❌ NO MARKETS DISCOVERED!")
            print("\nThis is the exact same call the trader makes, so there must be:")
            print("  1. A timing issue (markets expired since last check)")
            print("  2. A config difference")
            print("  3. An API issue")

        # Now apply quality filtering EXACTLY as trader does (lines 397, 511-530)
        print("\n" + "="*80)
        print("APPLYING QUALITY FILTERING (EXACTLY AS TRADER DOES)")
        print("="*80)

        filtered_markets = MarketFilter.filter_by_quality(
            markets=ultra_short_markets,
            price_fetcher=price_fetcher,
            min_price=discovery_config['min_price'],
            max_price=discovery_config['max_price'],
            max_spread_pct=discovery_config['max_spread_pct']['ultra_short'],
            check_last_trade=True,
            logger=logger
        )

        print(f"\n✓ {len(filtered_markets)} markets passed quality filters")

        if len(filtered_markets) > 0:
            print("\n✅ QUALITY FILTERING WORKS! Tradeable markets:")
            for i, m in enumerate(filtered_markets[:5]):
                print(f"  [{i+1}] {m.get('question', '')[:60]}")
        else:
            print("\n❌ ALL MARKETS REJECTED BY QUALITY FILTERS!")

    except Exception as e:
        logger.error(f"Error discovering ultra_short markets: {e}", exc_info=True)
        print(f"\n❌ EXCEPTION: {e}")

    # Also test WITHOUT crypto_only to see if that's the issue
    print("\n" + "="*80)
    print("TESTING WITHOUT crypto_only FILTER")
    print("="*80)

    all_markets = MarketFilter.discover_markets(
        client=client,
        category=None,  # No category filter
        min_hours_to_expiry=discovery_config['ultra_short_hours'][0],
        max_hours_to_expiry=discovery_config['ultra_short_hours'][1],
        min_volume=discovery_config['min_volume']['ultra_short'],
        min_liquidity=discovery_config['min_liquidity']['ultra_short'],
        max_pages=3,
        include_crypto_events=True,
        crypto_event_days_ahead=1,
        logger=logger
    )

    print(f"\n✓ Discovered {len(all_markets)} markets (no category filter)")

    if len(all_markets) > len(ultra_short_markets):
        print(f"\n⚠️  Category filter removed {len(all_markets) - len(ultra_short_markets)} markets!")
        print("This suggests the crypto keyword filtering might be too strict.")


if __name__ == '__main__':
    test_trader_discovery()
