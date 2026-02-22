"""
Combined Strategy - Watchlist + Auto-Discovery
==============================================

Monitors:
1. Watchlist tokens (manually added from DexScreener)
2. Auto-discovery via common pair searches

This hybrid approach catches both:
- High-volume tokens you manually find (like KOGE)
- New tokens in common pairs (WBNB, USDT, etc.)
"""

import json
import requests
from run_working import (
    calculate_transparency_score,
    calculate_safety_score,
    calculate_opportunity_score
)


def load_watchlist():
    """Load tokens from watchlist"""
    try:
        with open('watchlist.json', 'r') as f:
            data = json.load(f)
        return data.get('tokens', [])
    except FileNotFoundError:
        print("⚠️  No watchlist.json found")
        return []
    except json.JSONDecodeError:
        print("⚠️  Invalid watchlist.json")
        return []


def fetch_token_by_address(address):
    """Fetch token data by contract address"""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'pairs' in data and len(data['pairs']) > 0:
                # Return BSC pairs only, sorted by liquidity
                bsc_pairs = [p for p in data['pairs']
                             if p.get('chainId', '').lower() == 'bsc']

                if bsc_pairs:
                    # Return highest liquidity pair
                    bsc_pairs.sort(
                        key=lambda x: float(x.get('liquidity', {}).get('usd', 0)),
                        reverse=True
                    )
                    return bsc_pairs[0]
        return None
    except Exception as e:
        print(f"   Error fetching {address}: {e}")
        return None


def analyze_pair(pair):
    """Analyze a token pair"""
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
        print(f"   Error analyzing pair: {e}")
        return None


def fetch_and_analyze():
    """Combined scanner: watchlist + auto-discovery"""

    print("\n" + "="*80)
    print("COMBINED SCANNER: Watchlist + Auto-Discovery")
    print("="*80)

    all_opportunities = []

    # Part 1: Scan watchlist tokens
    print("\n📋 PART 1: SCANNING WATCHLIST TOKENS")
    print("="*80)

    watchlist = load_watchlist()

    if watchlist:
        print(f"Found {len(watchlist)} token(s) in watchlist")

        for entry in watchlist:
            name = entry.get('name', 'Unknown')
            address = entry.get('address')

            print(f"\n🔍 {name}")
            print(f"   Address: {address}")

            pair = fetch_token_by_address(address)

            if pair:
                base = pair.get('baseToken', {})
                quote = pair.get('quoteToken', {})
                liq = float(pair.get('liquidity', {}).get('usd', 0))
                vol = float(pair.get('volume', {}).get('h24', 0))

                print(f"   Pair: {base.get('symbol')}/{quote.get('symbol')}")
                print(f"   Liquidity: ${liq:,.0f}")
                print(f"   24h Volume: ${vol:,.0f}")

                result = analyze_pair(pair)

                if result:
                    print(f"   Safety: {result['safety']:.1f} | Opportunity: {result['opportunity']:.1f} | Composite: {result['composite']:.1f}")

                    if result['composite'] >= 70:
                        print(f"   ✅ HIGH QUALITY")
                    else:
                        print(f"   ⚠️  Below threshold")

                    all_opportunities.append(result)
            else:
                print(f"   ❌ Not found on BSC")
    else:
        print("No tokens in watchlist")
        print("\n💡 TIP: Add tokens to watchlist.json that you find on DexScreener")

    # Part 2: Auto-discovery via search
    print(f"\n\n📡 PART 2: AUTO-DISCOVERY (Common Pairs)")
    print("="*80)

    print("\n🔍 Searching WBNB pairs...")

    url = "https://api.dexscreener.com/latest/dex/search?q=WBNB"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()

            if 'pairs' in data:
                bsc_pairs = [p for p in data['pairs']
                             if p.get('chainId', '').lower() == 'bsc']

                filtered = [p for p in bsc_pairs
                            if float(p.get('liquidity', {}).get('usd', 0)) >= 5000]

                print(f"   Found {len(filtered)} BSC pairs with liquidity ≥ $5,000")

                for pair in filtered[:5]:  # Analyze top 5
                    result = analyze_pair(pair)
                    if result and result['token_address'] not in [o['token_address'] for o in all_opportunities]:
                        all_opportunities.append(result)

                        base = pair.get('baseToken', {})
                        print(f"   • {base.get('symbol')}: {result['composite']:.1f}/100")

    except Exception as e:
        print(f"   Error: {e}")

    # Sort and display results
    all_opportunities.sort(key=lambda x: x['composite'], reverse=True)

    print(f"\n\n{'='*80}")
    print(f"📊 RESULTS: {len(all_opportunities)} tokens analyzed")
    print(f"{'='*80}\n")

    high_quality = [o for o in all_opportunities if o['composite'] >= 70]

    if high_quality:
        print(f"✅ {len(high_quality)} HIGH-QUALITY OPPORTUNITIES:\n")

        for i, opp in enumerate(high_quality, 1):
            print(f"#{i} {opp['symbol']} - {opp['composite']:.1f}/100")
            print(f"   Liquidity: ${opp['liquidity']:,.0f} | Volume: ${opp['volume']:,.0f}")
            print(f"   📊 {opp['url']}")
            print()
    else:
        print("⚠️  No high-quality opportunities found")

        if all_opportunities:
            best = all_opportunities[0]
            print(f"\nBest available: {best['symbol']} - {best['composite']:.1f}/100")

    return all_opportunities


if __name__ == "__main__":
    fetch_and_analyze()
