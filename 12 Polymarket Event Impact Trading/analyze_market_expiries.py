"""
Analyze the expiry distribution of crypto markets to understand
why ultra-short bucket (0-24h) finds 0 markets.
"""

import json
import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.polymarket_client import PolymarketClient, MarketFilter


def analyze_crypto_market_expiries():
    """Analyze the expiry distribution of crypto markets."""

    # Load config
    with open('config/config_short_expiry.json', 'r') as f:
        config = json.load(f)

    # Initialize client
    print("Initializing Polymarket client...")
    client = PolymarketClient(config=config)

    print("\n" + "="*80)
    print("ANALYZING CRYPTO MARKET EXPIRY DISTRIBUTION")
    print("="*80)

    # Fetch crypto markets with VERY wide time range (1 hour to 30 days)
    print("\nFetching crypto markets (1h to 30 days)...")
    all_crypto_markets = MarketFilter.discover_markets(
        client=client,
        category='crypto',
        min_hours_to_expiry=1,
        max_hours_to_expiry=24 * 30,  # 30 days
        min_volume=0,
        min_liquidity=0,
        max_pages=5,
        include_crypto_events=True,
        crypto_event_days_ahead=7,
        logger=None
    )

    print(f"✓ Found {len(all_crypto_markets)} total crypto markets")

    if len(all_crypto_markets) == 0:
        print("\n❌ NO crypto markets found at all!")
        print("This suggests an issue with the crypto filtering or API.")
        return

    # Calculate expiry for each market
    expiry_data = []
    now = datetime.now(timezone.utc)

    for m in all_crypto_markets:
        try:
            end_date_str = m.get('endDate') or m.get('endDateIso')
            if not end_date_str:
                continue

            end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            hours = (end_date - now).total_seconds() / 3600
            days = hours / 24

            expiry_data.append({
                'question': m.get('question', ''),
                'hours': float(hours),
                'days': float(days),
                'volume': float(m.get('volume', 0)),
                'liquidity': float(m.get('liquidity', 0)),
                'end_date': end_date_str
            })
        except Exception as e:
            print(f"Error parsing market: {e}")
            continue

    if not expiry_data:
        print("\n❌ Could not parse expiry dates for any markets!")
        return

    # Sort by hours to expiry
    expiry_data.sort(key=lambda x: x['hours'])

    # Categorize into buckets
    buckets = {
        'ultra_short (0-24h)': [m for m in expiry_data if 0 <= m['hours'] <= 24],
        'short (24-72h)': [m for m in expiry_data if 24 < m['hours'] <= 72],
        'medium (72-168h)': [m for m in expiry_data if 72 < m['hours'] <= 168],
        'long (>168h)': [m for m in expiry_data if m['hours'] > 168]
    }

    print("\n" + "="*80)
    print("EXPIRY DISTRIBUTION BY BUCKET")
    print("="*80)

    for bucket_name, markets in buckets.items():
        print(f"\n{bucket_name}: {len(markets)} markets")

        if markets:
            avg_volume = sum(float(m['volume']) for m in markets) / len(markets)
            avg_liquidity = sum(float(m['liquidity']) for m in markets) / len(markets)
            print(f"  Avg volume:    ${avg_volume:,.0f}")
            print(f"  Avg liquidity: ${avg_liquidity:,.0f}")

            # Show first 5 markets
            print(f"\n  Sample markets:")
            for i, m in enumerate(markets[:5]):
                print(f"    [{i+1}] {m['question'][:60]}")
                print(f"        Expiry: {m['hours']:.1f}h ({m['days']:.1f}d) | "
                      f"Vol: ${m['volume']:,.0f} | Liq: ${m['liquidity']:,.0f}")

    # Find the shortest expiry market
    if expiry_data:
        shortest = expiry_data[0]
        print("\n" + "="*80)
        print("SHORTEST EXPIRY CRYPTO MARKET")
        print("="*80)
        print(f"Question: {shortest['question']}")
        print(f"Hours to expiry: {shortest['hours']:.1f}h ({shortest['days']:.2f} days)")
        print(f"End date: {shortest['end_date']}")
        print(f"Volume: ${shortest['volume']:,.0f}")
        print(f"Liquidity: ${shortest['liquidity']:,.0f}")

    # Analysis
    print("\n" + "="*80)
    print("ANALYSIS & RECOMMENDATIONS")
    print("="*80)

    ultra_short = buckets['ultra_short (0-24h)']
    if len(ultra_short) == 0:
        print("\n❌ PROBLEM IDENTIFIED: No crypto markets expire in the next 24 hours!")
        print("\nPossible reasons:")
        print("  1. Polymarket doesn't create ultra-short crypto markets")
        print("  2. Daily crypto events are structured differently than expected")
        print("  3. The crypto event slug pattern is incorrect")

        if expiry_data:
            shortest_hours = expiry_data[0]['hours']
            print(f"\n💡 The shortest expiry crypto market is {shortest_hours:.1f}h away")

            if shortest_hours > 24:
                print(f"\n💡 RECOMMENDATION #1: Adjust ultra_short bucket to {shortest_hours:.0f}-72h")
                print(f"   This would capture the actual shortest-expiry crypto markets.")

        print(f"\n💡 RECOMMENDATION #2: Remove the ultra_short bucket entirely")
        print(f"   Focus on short (24-72h) and medium (72-168h) buckets where markets exist.")

        print(f"\n💡 RECOMMENDATION #3: Use 2-bucket system:")
        print(f"   - Short: 24-72h (fast-moving crypto markets)")
        print(f"   - Medium: 72-168h (longer-term crypto trends)")

    else:
        print(f"\n✅ Found {len(ultra_short)} ultra-short markets!")
        print("The bucket configuration is correct.")

        # Check if they pass quality filters
        config_discovery = config['discovery']
        min_vol = config_discovery['min_volume']['ultra_short']
        min_liq = config_discovery['min_liquidity']['ultra_short']

        passing = [m for m in ultra_short if float(m['volume']) >= min_vol and float(m['liquidity']) >= min_liq]

        print(f"\nQuality filter check:")
        print(f"  Min volume requirement:    ${min_vol}")
        print(f"  Min liquidity requirement: ${min_liq}")
        print(f"  Markets passing filters:   {len(passing)}/{len(ultra_short)}")

        if len(passing) < len(ultra_short):
            print(f"\n💡 RECOMMENDATION: Lower volume/liquidity requirements for ultra_short")


if __name__ == '__main__':
    analyze_crypto_market_expiries()
