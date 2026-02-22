"""
Improved Strategy - Trending & Top Volume Tokens
=================================================

Scans DexScreener for top volume and trending tokens on BSC.
This catches opportunities like KOGE that specific searches miss.
"""

import requests
import time
from datetime import datetime


def fetch_trending_tokens():
    """Fetch top volume/trending tokens from DexScreener"""

    print("\n" + "="*80)
    print("TRENDING TOKEN SCANNER")
    print("="*80)
    print("\nFetching trending tokens from DexScreener...")

    all_tokens = []

    # Method 1: Get top BSC pairs by liquidity/volume
    try:
        # DexScreener doesn't have a direct "trending" endpoint, so we'll search
        # for popular base tokens on BSC

        search_tokens = [
            'USDT',  # Catch all USDT pairs
            'WBNB',  # Catch all WBNB pairs
            'BUSD',  # Catch all BUSD pairs
            'USDC',  # Catch all USDC pairs
        ]

        for search_token in search_tokens:
            url = f"https://api.dexscreener.com/latest/dex/search?q={search_token}"

            print(f"\n🔍 Searching pairs with {search_token}...")

            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()

                if 'pairs' in data:
                    # Filter for BSC only
                    bsc_pairs = [p for p in data['pairs']
                                 if p.get('chainId', '').lower() == 'bsc']

                    print(f"   Found {len(bsc_pairs)} BSC pairs with {search_token}")

                    all_tokens.extend(bsc_pairs)

            # Rate limiting
            time.sleep(0.5)

        print(f"\n✅ Total pairs found: {len(all_tokens)}")

        # Deduplicate by pair address
        seen = set()
        unique_tokens = []
        for token in all_tokens:
            pair_addr = token.get('pairAddress', '')
            if pair_addr and pair_addr not in seen:
                seen.add(pair_addr)
                unique_tokens.append(token)

        print(f"✅ Unique pairs: {len(unique_tokens)}")

        # Sort by 24h volume
        unique_tokens.sort(
            key=lambda x: float(x.get('volume', {}).get('h24', 0)),
            reverse=True
        )

        # Take top 50 by volume
        top_tokens = unique_tokens[:50]

        print(f"✅ Analyzing top 50 by volume")

        return top_tokens

    except Exception as e:
        print(f"❌ Error fetching trending: {e}")
        return []


def analyze_token(pair):
    """Analyze a single token pair"""
    from run_working import (
        calculate_transparency_score,
        calculate_safety_score,
        calculate_opportunity_score
    )

    try:
        base = pair.get('baseToken', {})
        quote = pair.get('quoteToken', {})
        liq_usd = float(pair.get('liquidity', {}).get('usd', 0))
        vol_24h = float(pair.get('volume', {}).get('h24', 0))
        price_change = pair.get('priceChange', {})
        price_1h = float(price_change.get('h1', 0) or 0)
        price_24h = float(price_change.get('h24', 0) or 0)

        # Extract social links
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

        # Calculate scores
        transparency_score = calculate_transparency_score(social_links)
        safety_score = calculate_safety_score(liq_usd, vol_24h, pair.get('dexId', ''), transparency_score)
        opp_score = calculate_opportunity_score(liq_usd, vol_24h, price_24h)
        composite = (safety_score * 0.6) + (opp_score * 0.4)

        return {
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

    except Exception as e:
        print(f"   Error analyzing {pair.get('pairAddress')}: {e}")
        return None


def fetch_and_analyze_trending():
    """Main function: fetch trending and analyze"""

    # Fetch trending tokens
    trending = fetch_trending_tokens()

    if not trending:
        print("\n❌ No trending tokens found")
        return []

    # Filter by minimum liquidity
    min_liq = 5000
    filtered = [p for p in trending
                if float(p.get('liquidity', {}).get('usd', 0)) >= min_liq]

    print(f"\n✅ {len(filtered)} tokens with liquidity ≥ ${min_liq:,}")

    # Analyze each token
    print(f"\n{'='*80}")
    print("ANALYZING TOP TOKENS")
    print(f"{'='*80}\n")

    analyzed = []

    for i, pair in enumerate(filtered[:20], 1):  # Analyze top 20
        base = pair.get('baseToken', {})
        quote = pair.get('quoteToken', {})
        liq = float(pair.get('liquidity', {}).get('usd', 0))
        vol = float(pair.get('volume', {}).get('h24', 0))

        print(f"#{i} {base.get('symbol')}/{quote.get('symbol')}")
        print(f"   Liquidity: ${liq:,.0f}")
        print(f"   24h Volume: ${vol:,.0f}")

        result = analyze_token(pair)

        if result:
            print(f"   Safety: {result['safety']:.1f} | Opportunity: {result['opportunity']:.1f} | Composite: {result['composite']:.1f}")

            if result['composite'] >= 70:
                print(f"   ✅ HIGH QUALITY (≥70)")
            elif result['composite'] >= 50:
                print(f"   ⚠️  MEDIUM QUALITY (50-69)")
            else:
                print(f"   ✗ LOW QUALITY (<50)")

            analyzed.append(result)

        print()

    # Sort by composite score
    analyzed.sort(key=lambda x: x['composite'], reverse=True)

    # Print summary
    high_quality = [t for t in analyzed if t['composite'] >= 70]

    if high_quality:
        print(f"{'='*80}")
        print(f"🎯 FOUND {len(high_quality)} HIGH-QUALITY OPPORTUNITIES")
        print(f"{'='*80}\n")

        for i, token in enumerate(high_quality[:5], 1):
            print(f"🏆 #{i} {token['symbol']}")
            print(f"   Composite: {token['composite']:.1f}/100")
            print(f"   Liquidity: ${token['liquidity']:,.0f}")
            print(f"   Volume: ${token['volume']:,.0f}")
            print(f"   📊 {token['url']}")
            print()
    else:
        print(f"{'='*80}")
        print("❌ NO HIGH-QUALITY OPPORTUNITIES FOUND")
        print(f"{'='*80}\n")

        if analyzed:
            print(f"Best available: {analyzed[0]['symbol']} with {analyzed[0]['composite']:.1f}/100")

    return analyzed


if __name__ == "__main__":
    fetch_and_analyze_trending()
