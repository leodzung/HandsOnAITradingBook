"""
Working Strategy - No Age Filter
=================================

Works around API limitation by not filtering by age.
Shows actual tokens from the API with safety/opportunity scoring.
"""

import requests
import time
from datetime import datetime


def fetch_and_analyze():
    """Fetch and analyze real tokens"""

    print("\n" + "="*80)
    print("WORKING STRATEGY: REAL TOKENS (No Age Filter)")
    print("="*80)
    print("\nFetching real tokens from DexScreener...")

    url = "https://api.dexscreener.com/latest/dex/search?q=WBNB"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            print(f"❌ API error: {response.status_code}")
            return []

        data = response.json()
        if 'pairs' not in data:
            print("❌ No pairs in response")
            return []

        # Filter BSC pairs with decent liquidity
        all_pairs = data['pairs']
        bsc_pairs = [p for p in all_pairs if p.get('chainId', '').lower() == 'bsc']

        # Filter by liquidity only (no age filter due to API limitation)
        min_liq = 5000
        filtered = [p for p in bsc_pairs if float(p.get('liquidity', {}).get('usd', 0)) >= min_liq]

        print(f"\n✅ Found {len(all_pairs)} total pairs")
        print(f"✅ {len(bsc_pairs)} on BSC")
        print(f"✅ {len(filtered)} with liquidity ≥ ${min_liq:,}")

        opportunities = []
        all_analyzed = []  # Track ALL tokens analyzed, not just viable ones

        print(f"\n{'='*80}")
        print("ANALYZING TOKENS")
        print(f"{'='*80}\n")

        for i, pair in enumerate(filtered[:10], 1):  # Analyze top 10
            base = pair.get('baseToken', {})
            quote = pair.get('quoteToken', {})
            liq_usd = float(pair.get('liquidity', {}).get('usd', 0))
            vol_24h = float(pair.get('volume', {}).get('h24', 0))
            price_change = pair.get('priceChange', {})
            price_1h = float(price_change.get('h1', 0))
            price_24h = float(price_change.get('h24', 0))

            # Extract social links FIRST (needed for transparency score)
            info = pair.get('info', {})
            websites = info.get('websites', [])
            socials = info.get('socials', [])

            # Build social links dict
            social_links = {
                'website': websites[0].get('url') if websites else None,
                'twitter': None,
                'telegram': None,
                'discord': None,
                'github': None
            }

            # Parse socials list
            for social in socials:
                social_type = social.get('type', '').lower()
                social_url = social.get('url', '')
                if social_type == 'twitter':
                    social_links['twitter'] = social_url
                elif social_type == 'telegram':
                    social_links['telegram'] = social_url
                elif social_type == 'discord':
                    social_links['discord'] = social_url
                elif social_type == 'github':
                    social_links['github'] = social_url

            # Calculate transparency/developer score
            transparency_score = calculate_transparency_score(social_links)

            # Calculate scores
            safety_score = calculate_safety_score(liq_usd, vol_24h, pair.get('dexId', ''), transparency_score)
            opp_score = calculate_opportunity_score(liq_usd, vol_24h, price_24h)
            composite = (safety_score * 0.6) + (opp_score * 0.4)

            print(f"#{i} {base.get('symbol', 'UNKNOWN')}/{quote.get('symbol', 'UNKNOWN')}")
            print(f"   DEX: {pair.get('dexId', 'unknown')}")
            print(f"   Liquidity: ${liq_usd:,.2f}")
            print(f"   24h Volume: ${vol_24h:,.2f}")
            print(f"   Price Change: 1h={price_1h:+.1f}%, 24h={price_24h:+.1f}%")
            print(f"   Safety: {safety_score:.1f} | Opportunity: {opp_score:.1f} | Composite: {composite:.1f}")

            # Add to all_analyzed list
            token_data = {
                'symbol': f"{base.get('symbol')}/{quote.get('symbol')}",
                'base_symbol': base.get('symbol', 'UNKNOWN'),
                'pair_address': pair.get('pairAddress'),
                'token_address': base.get('address'),
                'liquidity': liq_usd,
                'volume': vol_24h,
                'price_1h': price_1h,
                'price_24h': price_24h,
                'safety': safety_score,
                'opportunity': opp_score,
                'composite': composite,
                'transparency': transparency_score,
                'dex': pair.get('dexId'),
                'url': f"https://dexscreener.com/bsc/{pair.get('pairAddress')}",
                'social_links': social_links
            }
            all_analyzed.append(token_data)

            # Check if viable (for display purposes)
            if safety_score >= 50 and opp_score >= 40:
                print(f"   ✅ VIABLE OPPORTUNITY")
                opportunities.append(token_data)
            else:
                print(f"   ✗ FILTERED OUT (scores too low)")

            print()

        # Print summary
        if opportunities:
            opportunities.sort(key=lambda x: x['composite'], reverse=True)

            print(f"{'='*80}")
            print(f"🎯 FOUND {len(opportunities)} VIABLE OPPORTUNITIES")
            print(f"{'='*80}\n")

            for i, opp in enumerate(opportunities[:5], 1):
                print(f"🏆 #{i} {opp['symbol']}")
                print(f"   Composite Score: {opp['composite']:.1f}/100")
                print(f"   Safety: {opp['safety']:.1f} | Opportunity: {opp['opportunity']:.1f}")
                print(f"   Liquidity: ${opp['liquidity']:,.0f}")
                print(f"   24h Volume: ${opp['volume']:,.0f}")
                print(f"   Price: 1h={opp['price_1h']:+.1f}%, 24h={opp['price_24h']:+.1f}%")
                print(f"   Token: {opp['token_address']}")
                print(f"   📊 Chart: {opp['url']}")
                print()

            print(f"{'='*80}")
            print("NEXT STEPS")
            print(f"{'='*80}\n")
            print("For the top opportunities above:")
            print("1. ✓ Click the DexScreener link to see chart")
            print("2. ✓ Visit honeypot.is and paste token address")
            print("3. ✓ Check contract on BSCScan.com")
            print("4. ✓ Review social media (Twitter, Telegram)")
            print("5. ✓ If ALL checks pass, consider SMALL test trade ($50-100)")
            print("\n⚠️  HIGH RISK - Only invest what you can afford to lose!")

        else:
            print(f"{'='*80}")
            print("❌ NO VIABLE OPPORTUNITIES")
            print(f"{'='*80}\n")
            print("All tokens were filtered out due to low scores.")
            print("Try again later or adjust thresholds.")

        # Return all analyzed tokens (sorted by composite score)
        # This allows the email script to send "best available" if no qualified opportunities
        all_analyzed.sort(key=lambda x: x['composite'], reverse=True)
        return all_analyzed

    except Exception as e:
        print(f"❌ Error: {e}")
        return []


def calculate_transparency_score(social_links):
    """Calculate developer transparency score based on social presence"""
    score = 0

    if social_links.get('github'):
        score += 40  # GitHub is most important for dev activity
    if social_links.get('website'):
        score += 20  # Official website shows professionalism
    if social_links.get('twitter'):
        score += 20  # Twitter for community engagement
    if social_links.get('telegram'):
        score += 10  # Telegram for community
    if social_links.get('discord'):
        score += 10  # Discord for community

    return min(100, score)


def calculate_safety_score(liquidity, volume, dex_id, transparency_score):
    """Calculate safety score including developer transparency"""
    score = 20.0  # Reduced base (was 30)

    # Liquidity (max 25 points)
    if liquidity >= 50000:
        score += 25
    elif liquidity >= 20000:
        score += 15
    elif liquidity >= 10000:
        score += 10
    elif liquidity >= 5000:
        score += 5

    # Volume/Liquidity ratio (max 20 points)
    if liquidity > 0:
        ratio = volume / liquidity
        if 0.1 <= ratio <= 2.0:
            score += 20
        elif ratio > 0:
            score += 5

    # DEX reputation (max 15 points)
    reputable = ['pancakeswap', 'uniswap', 'sushiswap']
    if any(name in dex_id.lower() for name in reputable):
        score += 15

    # Developer transparency (max 20 points)
    # Scale transparency_score (0-100) to 0-20
    score += (transparency_score / 100) * 20

    return min(100, score)


def calculate_opportunity_score(liquidity, volume, price_24h):
    """Calculate opportunity score"""
    score = 20.0  # Base

    # Volume
    if volume > liquidity:
        score += 30
    elif volume > liquidity * 0.5:
        score += 20
    elif volume > 0:
        score += 10

    # Price momentum
    if price_24h > 20:
        score += 30
    elif price_24h > 10:
        score += 20
    elif price_24h > 5:
        score += 10
    elif price_24h > 0:
        score += 5

    # Liquidity (better for entry/exit)
    if liquidity >= 50000:
        score += 20
    elif liquidity >= 20000:
        score += 10

    return min(100, score)


if __name__ == "__main__":
    fetch_and_analyze()
