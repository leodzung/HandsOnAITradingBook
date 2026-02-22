"""
Test if short-expiry trader can discover and would trade Bitcoin Feb 14 markets.
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.polymarket_client import PolymarketClient, MarketFilter
from core.price_fetcher import PriceFetcher

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_short_expiry_discovery():
    """Test if short-expiry trader discovers Bitcoin Feb 14 markets."""

    print("=" * 80)
    print("SHORT-EXPIRY TRADER: Bitcoin Feb 14 Market Discovery Test")
    print("=" * 80)

    # Load config
    config_path = Path(__file__).parent / "config" / "config_short_expiry.json"
    with open(config_path) as f:
        config = json.load(f)

    print(f"\nLoaded config from: {config_path}")

    # Initialize client and price fetcher
    client = PolymarketClient()
    price_fetcher = PriceFetcher(client)

    # Get discovery config
    discovery = config['discovery']

    print("\n" + "=" * 80)
    print("STEP 1: Market Discovery (All Three Buckets)")
    print("=" * 80)

    buckets = {
        'ultra_short': discovery['ultra_short_hours'],
        'short': discovery['short_hours'],
        'medium': discovery['medium_hours']
    }

    all_markets_by_bucket = {}
    btc_feb14_by_bucket = {}

    for bucket_name, hour_range in buckets.items():
        print(f"\n--- {bucket_name.upper()} Bucket: {hour_range[0]}-{hour_range[1]} hours ---")

        markets = MarketFilter.discover_markets(
            client=client,
            category=discovery.get('category_filter', 'crypto'),
            min_hours_to_expiry=hour_range[0],
            max_hours_to_expiry=hour_range[1],
            min_volume=discovery['min_volume'].get(bucket_name, 0),
            min_liquidity=discovery['min_liquidity'].get(bucket_name, 0),
            max_pages=5,
            include_crypto_events=discovery.get('crypto_only', True),
            crypto_event_days_ahead=7,
            logger=logger
        )

        all_markets_by_bucket[bucket_name] = markets

        # Filter for Bitcoin Feb 14 markets
        btc_feb14 = [
            m for m in markets
            if 'february 14' in m.get('question', '').lower()
            and 'bitcoin' in m.get('question', '').lower()
        ]

        btc_feb14_by_bucket[bucket_name] = btc_feb14

        print(f"Total markets discovered: {len(markets)}")
        print(f"Bitcoin Feb 14 markets: {len(btc_feb14)}")

        if btc_feb14:
            print(f"\nFound Bitcoin Feb 14 markets in {bucket_name.upper()} bucket:")
            for i, m in enumerate(btc_feb14[:5], 1):
                question = m.get('question', 'N/A')
                end_date = m.get('endDate', m.get('endDateIso', 'N/A'))
                volume = m.get('volume', 0)
                try:
                    volume_float = float(volume)
                    volume_str = f"${volume_float:,.0f}"
                except:
                    volume_str = str(volume)
                print(f"  {i}. {question}")
                print(f"     End: {end_date}, Volume: {volume_str}")

    # Find which bucket has the Bitcoin Feb 14 markets
    target_bucket = None
    target_markets = []
    for bucket_name, markets in btc_feb14_by_bucket.items():
        if markets:
            target_bucket = bucket_name
            target_markets = markets
            break

    if not target_bucket:
        print("\n" + "=" * 80)
        print("❌ RESULT: Bitcoin Feb 14 markets NOT found in ANY bucket")
        print("=" * 80)
        return

    print("\n" + "=" * 80)
    print(f"✅ Bitcoin Feb 14 markets found in '{target_bucket.upper()}' bucket")
    print("=" * 80)

    # STEP 2: Apply quality filters
    print("\n" + "=" * 80)
    print("STEP 2: Quality Filtering")
    print("=" * 80)

    quality_config = {
        'enabled': True,
        'min_price': discovery.get('min_price', 0.05),
        'max_price': discovery.get('max_price', 0.95),
        'max_spread_pct': discovery['max_spread_pct'].get(target_bucket, 10.0),
        'check_last_trade': True
    }

    print(f"\nQuality filter settings for {target_bucket}:")
    print(f"  - Price range: {quality_config['min_price']} - {quality_config['max_price']}")
    print(f"  - Max spread: {quality_config['max_spread_pct']}%")
    print(f"  - Check last trade: {quality_config['check_last_trade']}")

    print(f"\nApplying quality filters to {len(target_markets)} markets...")

    filtered_markets = MarketFilter.filter_by_quality(
        markets=target_markets,
        price_fetcher=price_fetcher,
        min_price=quality_config['min_price'],
        max_price=quality_config['max_price'],
        max_spread_pct=quality_config['max_spread_pct'],
        check_last_trade=quality_config['check_last_trade'],
        logger=logger
    )

    print(f"\n✅ Markets passing quality filter: {len(filtered_markets)}/{len(target_markets)}")

    if not filtered_markets:
        print("\n❌ No markets passed quality filters!")
        return

    # STEP 3: Get current prices and check trading signals
    print("\n" + "=" * 80)
    print("STEP 3: Current Prices & Potential Trading Signals")
    print("=" * 80)

    max_entry_price = config.get('max_entry_price', 0.90)
    print(f"\nMax entry price: {max_entry_price}")
    print(f"\nChecking prices for {len(filtered_markets)} markets:\n")

    tradeable_markets = []

    for i, market in enumerate(filtered_markets, 1):
        question = market.get('question', 'N/A')
        condition_id = market.get('conditionId')

        # Get current prices
        prices = price_fetcher.get_clob_prices(condition_id, side='BUY')
        yes_price = prices.get('yes_price')
        no_price = prices.get('no_price')

        print(f"{i}. {question}")
        print(f"   Condition ID: {condition_id}")
        print(f"   YES price: {yes_price}")
        print(f"   NO price: {no_price}")

        # Check if tradeable
        tradeable_yes = yes_price is not None and yes_price <= max_entry_price
        tradeable_no = no_price is not None and no_price <= max_entry_price

        if tradeable_yes or tradeable_no:
            tradeable_sides = []
            if tradeable_yes:
                tradeable_sides.append(f"YES @ {yes_price:.3f}")
            if tradeable_no:
                tradeable_sides.append(f"NO @ {no_price:.3f}")

            print(f"   ✅ TRADEABLE: {', '.join(tradeable_sides)}")
            tradeable_markets.append({
                'market': market,
                'yes_price': yes_price,
                'no_price': no_price,
                'tradeable_yes': tradeable_yes,
                'tradeable_no': tradeable_no
            })
        else:
            reasons = []
            if yes_price and yes_price > max_entry_price:
                reasons.append(f"YES too expensive ({yes_price:.3f} > {max_entry_price})")
            if no_price and no_price > max_entry_price:
                reasons.append(f"NO too expensive ({no_price:.3f} > {max_entry_price})")
            if not yes_price and not no_price:
                reasons.append("No prices available")
            print(f"   ❌ NOT TRADEABLE: {', '.join(reasons)}")

        print()

    # STEP 4: Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print(f"\n✅ Discovery: Found {len(target_markets)} Bitcoin Feb 14 markets in '{target_bucket.upper()}' bucket")
    print(f"✅ Quality filters: {len(filtered_markets)}/{len(target_markets)} markets passed")
    print(f"✅ Price check: {len(tradeable_markets)}/{len(filtered_markets)} markets are tradeable")

    if tradeable_markets:
        print(f"\n{'='*80}")
        print("🎯 TRADEABLE MARKETS (Short-Expiry Bot SHOULD Trade These)")
        print(f"{'='*80}\n")

        for i, tm in enumerate(tradeable_markets, 1):
            market = tm['market']
            question = market.get('question', 'N/A')

            sides = []
            if tm['tradeable_yes']:
                sides.append(f"YES @ {tm['yes_price']:.3f}")
            if tm['tradeable_no']:
                sides.append(f"NO @ {tm['no_price']:.3f}")

            print(f"{i}. {question}")
            print(f"   Tradeable: {', '.join(sides)}")

        print(f"\n✅ CONCLUSION: Short-expiry trader SHOULD be able to trade these markets!")
    else:
        print(f"\n❌ CONCLUSION: No tradeable markets due to price constraints (all > {max_entry_price})")

if __name__ == "__main__":
    test_short_expiry_discovery()
