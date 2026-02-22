"""
Diagnostic script to investigate why ultra-short bucket (0-24h) finds 0 markets.

This script mimics the short-expiry trader's market discovery flow and shows
detailed rejection reasons at each filtering stage.
"""

import json
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.polymarket_client import PolymarketClient, MarketFilter
from src.core.price_fetcher import PriceFetcher


def diagnose_ultra_short_bucket():
    """Run diagnostic on ultra-short bucket market discovery."""

    # Load config
    with open('config/config_short_expiry.json', 'r') as f:
        config = json.load(f)

    # Initialize client and price fetcher
    print("Initializing Polymarket client...")
    client = PolymarketClient(config=config)
    price_fetcher = PriceFetcher(client)

    # Ultra-short bucket config
    discovery_config = config['discovery']
    min_hours = discovery_config['ultra_short_hours'][0]
    max_hours = discovery_config['ultra_short_hours'][1]
    min_volume = discovery_config['min_volume']['ultra_short']
    min_liquidity = discovery_config['min_liquidity']['ultra_short']
    max_spread_pct = discovery_config['max_spread_pct']['ultra_short']
    min_price = discovery_config['min_price']
    max_price = discovery_config['max_price']
    crypto_only = discovery_config.get('crypto_only', True)

    print("\n" + "="*80)
    print("ULTRA-SHORT BUCKET CONFIGURATION")
    print("="*80)
    print(f"Time range:       {min_hours}-{max_hours} hours ({min_hours/24:.1f}-{max_hours/24:.1f} days)")
    print(f"Min volume:       ${min_volume:,.0f}")
    print(f"Min liquidity:    ${min_liquidity:,.0f}")
    print(f"Max spread:       {max_spread_pct}%")
    print(f"Price range:      {min_price:.2f} - {max_price:.2f}")
    print(f"Crypto only:      {crypto_only}")

    # Step 1: Discover markets
    print("\n" + "="*80)
    print("STEP 1: MARKET DISCOVERY (MarketFilter.discover_markets)")
    print("="*80)

    category = 'crypto' if crypto_only else None
    discovered_markets = MarketFilter.discover_markets(
        client=client,
        category=category,
        min_hours_to_expiry=min_hours,
        max_hours_to_expiry=max_hours,
        min_volume=min_volume,
        min_liquidity=min_liquidity,
        max_pages=3,
        include_crypto_events=True,
        crypto_event_days_ahead=1,  # Only 1 day for ultra-short
        logger=None
    )

    print(f"\n✓ Discovered {len(discovered_markets)} markets after initial filtering")

    if len(discovered_markets) == 0:
        print("\n❌ NO MARKETS FOUND in discovery phase!")
        print("\nPossible causes:")
        print("  1. API volume/liquidity filters are too strict")
        print("  2. No crypto markets expiring in 0-24h range")
        print("  3. Crypto event slugs not returning markets")

        # Test with relaxed filters
        print("\n" + "="*80)
        print("TESTING WITH RELAXED FILTERS (min_volume=0, min_liquidity=0)")
        print("="*80)

        relaxed_markets = MarketFilter.discover_markets(
            client=client,
            category=category,
            min_hours_to_expiry=min_hours,
            max_hours_to_expiry=max_hours,
            min_volume=0,  # Remove volume filter
            min_liquidity=0,  # Remove liquidity filter
            max_pages=3,
            include_crypto_events=True,
            crypto_event_days_ahead=1,
            logger=None
        )

        print(f"\n✓ Discovered {len(relaxed_markets)} markets with relaxed filters")

        if len(relaxed_markets) > 0:
            print("\n⚠️  DIAGNOSIS: Volume/liquidity filters are TOO STRICT")
            print("\nSample markets that were filtered out:")
            for i, m in enumerate(relaxed_markets[:5]):
                volume = m.get('volume', 0)
                liquidity = m.get('liquidity', 0)
                hours = _calculate_hours_to_expiry(m)
                print(f"\n  [{i+1}] {m.get('question', '')[:60]}")
                print(f"      Volume: ${volume:,.0f} | Liquidity: ${liquidity:,.0f} | "
                      f"Expiry: {hours:.1f}h")

            print(f"\n💡 RECOMMENDATION: Lower ultra_short min_volume from ${min_volume} to $0-50")
            print(f"💡 RECOMMENDATION: Lower ultra_short min_liquidity from ${min_liquidity} to $0-25")
        else:
            print("\n❌ Still no markets found!")
            print("The API is not returning ANY crypto markets in the 0-24h range.")

        return

    # Step 2: Quality filtering
    print("\n" + "="*80)
    print("STEP 2: QUALITY FILTERING (MarketFilter.filter_by_quality)")
    print("="*80)
    print(f"Checking: spread <= {max_spread_pct}%, price in [{min_price}, {max_price}]")

    # Track detailed rejections
    rejection_details = {
        'spread_too_wide': [],
        'no_market_id': [],
        'no_entry_prices': [],
        'both_prices_none': [],
        'price_out_of_range': [],
        'no_last_trade': []
    }

    for m in discovered_markets:
        # Check spread
        best_bid = m.get('bestBid', 0.45)
        best_ask = m.get('bestAsk', 0.55)

        if isinstance(best_bid, str):
            best_bid = float(best_bid)
        if isinstance(best_ask, str):
            best_ask = float(best_ask)

        spread = best_ask - best_bid
        mid_price = (best_bid + best_ask) / 2.0
        spread_pct = (spread / mid_price * 100) if mid_price > 0 else 0

        if spread_pct > max_spread_pct:
            rejection_details['spread_too_wide'].append({
                'question': m.get('question', ''),
                'spread_pct': spread_pct,
                'bid': best_bid,
                'ask': best_ask
            })
            continue

        # Get market ID
        market_id = m.get('conditionId') or m.get('condition_id')
        if not market_id:
            rejection_details['no_market_id'].append({'question': m.get('question', '')})
            continue

        # Get entry prices
        entry_prices = price_fetcher.get_entry_prices(market_id)
        if entry_prices is None:
            rejection_details['no_entry_prices'].append({
                'question': m.get('question', ''),
                'market_id': market_id[:16] + '...'
            })
            continue

        yes_price = entry_prices.yes_price
        no_price = entry_prices.no_price

        # Check both prices None
        if yes_price is None and no_price is None:
            rejection_details['both_prices_none'].append({
                'question': m.get('question', ''),
                'market_id': market_id[:16] + '...'
            })
            continue

        # Check price range
        check_price = yes_price if yes_price is not None else no_price
        if check_price < min_price or check_price > max_price:
            rejection_details['price_out_of_range'].append({
                'question': m.get('question', ''),
                'price': check_price,
                'min_price': min_price,
                'max_price': max_price
            })
            continue

        # Check last trade
        if m.get('lastTradePrice') is None:
            rejection_details['no_last_trade'].append({
                'question': m.get('question', ''),
                'market_id': market_id[:16] + '...'
            })
            continue

    # Print rejection summary
    total_rejected = sum(len(v) for v in rejection_details.values())
    total_passed = len(discovered_markets) - total_rejected

    print(f"\n📊 RESULTS:")
    print(f"   Markets passed:  {total_passed}")
    print(f"   Markets rejected: {total_rejected}")

    if total_rejected > 0:
        print(f"\n🔍 REJECTION BREAKDOWN:")
        for reason, items in rejection_details.items():
            if items:
                print(f"\n   {reason}: {len(items)}")
                # Show first 3 examples
                for i, item in enumerate(items[:3]):
                    print(f"      [{i+1}] {item.get('question', 'N/A')[:50]}")
                    if 'spread_pct' in item:
                        print(f"          Spread: {item['spread_pct']:.1f}% (max: {max_spread_pct}%)")
                    if 'price' in item:
                        print(f"          Price: {item['price']:.3f} (range: {min_price}-{max_price})")

    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if len(rejection_details['spread_too_wide']) > 0:
        avg_spread = sum(r['spread_pct'] for r in rejection_details['spread_too_wide']) / len(rejection_details['spread_too_wide'])
        print(f"\n⚠️  Spread filter is rejecting {len(rejection_details['spread_too_wide'])} markets")
        print(f"    Average rejected spread: {avg_spread:.1f}%")
        print(f"    Current max_spread_pct: {max_spread_pct}%")
        print(f"    💡 RECOMMENDATION: Increase ultra_short max_spread_pct to {avg_spread * 1.2:.0f}%")

    if len(rejection_details['price_out_of_range']) > 0:
        print(f"\n⚠️  Price range filter is rejecting {len(rejection_details['price_out_of_range'])} markets")
        rejected_prices = [r['price'] for r in rejection_details['price_out_of_range']]
        too_low = [p for p in rejected_prices if p < min_price]
        too_high = [p for p in rejected_prices if p > max_price]
        if too_low:
            print(f"    {len(too_low)} markets below {min_price} (avg: {sum(too_low)/len(too_low):.3f})")
        if too_high:
            print(f"    {len(too_high)} markets above {max_price} (avg: {sum(too_high)/len(too_high):.3f})")
        print(f"    💡 RECOMMENDATION: Relax price range to 0.02-0.98 for ultra_short")

    if len(rejection_details['no_last_trade']) > 0:
        print(f"\n⚠️  Trade activity filter is rejecting {len(rejection_details['no_last_trade'])} markets")
        print(f"    💡 RECOMMENDATION: Disable check_last_trade for ultra_short bucket")

    if total_passed == 0 and total_rejected > 0:
        print(f"\n❌ ALL {len(discovered_markets)} discovered markets were rejected by quality filters!")
        print(f"\n💡 QUICK FIX: Create separate quality filters for ultra_short bucket:")
        print(f"   - Increase max_spread_pct from {max_spread_pct}% to 15-20%")
        print(f"   - Relax price range to 0.02-0.98")
        print(f"   - Disable last trade check")
    elif total_passed > 0:
        print(f"\n✅ {total_passed} markets passed all filters and should be tradeable!")


def _calculate_hours_to_expiry(market: dict) -> float:
    """Calculate hours until market expiry."""
    try:
        end_date_str = market.get('endDate') or market.get('endDateIso')
        if not end_date_str:
            return 0.0

        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        hours = (end_date - now).total_seconds() / 3600
        return max(0, hours)
    except:
        return 0.0


if __name__ == '__main__':
    diagnose_ultra_short_bucket()
