"""
Moralis-Powered Discovery Scanner
==================================

Uses Moralis API to auto-discover trending/high-volume tokens,
then enriches with DexScreener data for social links and scoring.

Setup:
1. Sign up at moralis.com (free tier)
2. Get API key from dashboard
3. Add to moralis_config.json
"""

import requests
import json
from run_combined import analyze_pair


def load_moralis_config():
    """Load Moralis API configuration"""
    try:
        with open('moralis_config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ moralis_config.json not found!")
        print("\n📋 Create moralis_config.json with:")
        print("""
{
  "api_key": "YOUR_MORALIS_API_KEY_HERE",
  "base_url": "https://deep-index.moralis.io/api/v2.2"
}
        """)
        return None


def get_top_tokens_by_market_cap(api_key, chain="bsc", limit=50):
    """
    Get top tokens by market cap using Moralis Market Data API

    Endpoint: https://docs.moralis.com/web3-data-api/evm/reference/get-top-erc20-tokens-by-market-cap
    """

    # Real Moralis endpoint (verified from docs)
    url = "https://deep-index.moralis.io/api/v2.2/market-data/erc20s/top-tokens"

    headers = {
        "accept": "application/json",
        "X-API-Key": api_key
    }

    params = {
        "chain": chain,
        "limit": limit
    }

    try:
        print(f"   📡 Calling: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Extract tokens array from response
            tokens = data if isinstance(data, list) else data.get('tokens', [])

            # Debug: print first token structure
            if tokens and len(tokens) > 0:
                print(f"   📋 Sample token structure: {list(tokens[0].keys())}")

            return tokens

        elif response.status_code == 401:
            print(f"   ❌ Authentication failed - check your API key")
            return None
        elif response.status_code == 403:
            print(f"   ❌ Access forbidden - may need paid plan")
            return None
        else:
            print(f"   ❌ API error: {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            return None

    except Exception as e:
        print(f"   ❌ Error calling Moralis: {e}")
        return None


def get_top_price_movers(api_key, chain="bsc", limit=50):
    """
    Get top price movers (gainers and losers) using Moralis Market Data API

    Endpoint: https://docs.moralis.com/web3-data-api/evm/reference/get-top-erc20-tokens-by-price-movers
    """

    # Real Moralis endpoint for price movers
    url = "https://deep-index.moralis.io/api/v2.2/market-data/erc20s/top-movers"

    headers = {
        "accept": "application/json",
        "X-API-Key": api_key
    }

    params = {
        "chain": chain,
        "limit": limit
    }

    try:
        print(f"   📡 Calling: {url}")
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Response may contain 'gainers' and 'losers' arrays
            all_movers = []

            if isinstance(data, dict):
                gainers = data.get('gainers', [])
                losers = data.get('losers', [])

                # We want gainers (positive momentum)
                all_movers = gainers

                print(f"   ✅ Found {len(gainers)} gainers, {len(losers)} losers")

                # Debug: print first gainer structure
                if gainers and len(gainers) > 0:
                    print(f"   📋 Sample gainer structure: {list(gainers[0].keys())}")
            else:
                all_movers = data if isinstance(data, list) else []

            return all_movers

        elif response.status_code == 401:
            print(f"   ❌ Authentication failed - check your API key")
            return None
        elif response.status_code == 403:
            print(f"   ❌ Access forbidden - may need paid plan")
            return None
        else:
            print(f"   ❌ API error: {response.status_code}")
            print(f"   Response: {response.text[:300]}")
            return None

    except Exception as e:
        print(f"   ❌ Error calling Moralis: {e}")
        return None


def enrich_with_dexscreener(token_address):
    """
    Fetch detailed pair info from DexScreener for a token
    Includes social links and other metadata
    """
    url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if 'pairs' in data and len(data['pairs']) > 0:
                # Get Ethereum mainnet pairs only
                eth_pairs = [p for p in data['pairs']
                             if p.get('chainId', '').lower() == 'ethereum']

                if eth_pairs:
                    eth_pairs.sort(
                        key=lambda x: float(x.get('liquidity', {}).get('usd', 0)),
                        reverse=True
                    )
                    return eth_pairs[0]  # Return highest liquidity Ethereum pair

        return None

    except Exception as e:
        print(f"   Error fetching from DexScreener: {e}")
        return None


def discover_and_analyze():
    """
    Main function: Discover tokens with Moralis, enrich with DexScreener, score
    """

    print("\n" + "="*80)
    print("MORALIS-POWERED DISCOVERY SCANNER")
    print("="*80)

    # Load Moralis config
    config = load_moralis_config()

    if not config:
        print("\n⚠️  Moralis not configured.")
        print("   Falling back to watchlist + DexScreener search...")
        print("\n   💡 TIP: Sign up at https://moralis.com to enable auto-discovery!")

        # Fall back to the combined strategy
        from run_combined import fetch_and_analyze as fallback_fetch
        return fallback_fetch()

    api_key = config.get('api_key')

    if not api_key or api_key == "YOUR_MORALIS_API_KEY_HERE":
        print("\n⚠️  Moralis API key not set.")
        print("   Falling back to watchlist + DexScreener search...")

        # Fall back to the combined strategy
        from run_combined import fetch_and_analyze as fallback_fetch
        return fallback_fetch()

    print(f"\n🔍 Discovering tokens via Moralis API...")

    # Method 1: Get top tokens by market cap
    print("\n1️⃣ Fetching top tokens by market cap...")
    top_by_marketcap = get_top_tokens_by_market_cap(api_key, chain="eth", limit=25)

    # Method 2: Get top price movers (gainers)
    print("\n2️⃣ Fetching top price gainers...")
    price_gainers = get_top_price_movers(api_key, chain="eth", limit=25)

    # Combine results
    all_discovered = []
    seen_addresses = set()

    # Add market cap tokens
    if top_by_marketcap:
        for token in top_by_marketcap:
            addr = token.get('contract_address') or token.get('token_address') or token.get('address')
            if addr and addr not in seen_addresses:
                all_discovered.append(token)
                seen_addresses.add(addr)
        print(f"   ✅ Added {len(top_by_marketcap)} high market cap tokens")

    # Add price gainers
    if price_gainers:
        for token in price_gainers:
            addr = token.get('contract_address') or token.get('token_address') or token.get('address')
            if addr and addr not in seen_addresses:
                all_discovered.append(token)
                seen_addresses.add(addr)
        print(f"   ✅ Added {len([t for t in price_gainers if (t.get('contract_address') or t.get('token_address') or t.get('address')) not in [d.get('contract_address') or d.get('token_address') or d.get('address') for d in all_discovered[:-len(price_gainers)]]])} new price gainers")

    if not all_discovered:
        print("\n❌ No tokens discovered via Moralis")
        print("   Possible reasons:")
        print("   • API key invalid or expired")
        print("   • Rate limit exceeded")
        print("   • BSC chain not supported in free tier")
        print("\n   💡 TIP: Sign up at https://moralis.com for a free API key")
        return []

    print(f"\n✅ Total unique tokens discovered: {len(all_discovered)}")

    # Enrich with DexScreener and analyze
    print(f"\n{'='*80}")
    print("ENRICHING WITH DEXSCREENER & SCORING")
    print(f"{'='*80}\n")

    opportunities = []

    for i, token_data in enumerate(all_discovered[:20], 1):  # Analyze top 20

        # Extract token address (structure may vary)
        token_address = token_data.get('contract_address') or token_data.get('token_address') or token_data.get('address')
        token_symbol = token_data.get('token_symbol') or token_data.get('symbol', 'UNKNOWN')

        if not token_address:
            continue

        print(f"#{i} {token_symbol} ({token_address[:10]}...)")

        # Get detailed pair info from DexScreener
        pair = enrich_with_dexscreener(token_address)

        if pair:
            liq = float(pair.get('liquidity', {}).get('usd', 0))
            vol = float(pair.get('volume', {}).get('h24', 0))

            print(f"   Liquidity: ${liq:,.0f} | Volume: ${vol:,.0f}")

            # Analyze and score
            result = analyze_pair(pair)

            if result:
                print(f"   Score: {result['composite']:.1f}/100")

                if result['composite'] >= 70:
                    print(f"   ✅ HIGH QUALITY")
                    opportunities.append(result)
                elif result['composite'] >= 50:
                    print(f"   ⚠️  MEDIUM")
                    opportunities.append(result)
        else:
            print(f"   ⚠️  Not found on DexScreener")

        print()

    # Sort and display
    opportunities.sort(key=lambda x: x['composite'], reverse=True)

    print(f"{'='*80}")
    print(f"📊 RESULTS: {len(opportunities)} opportunities found")
    print(f"{'='*80}\n")

    high_quality = [o for o in opportunities if o['composite'] >= 70]

    if high_quality:
        print(f"✅ {len(high_quality)} HIGH-QUALITY:\n")

        for i, opp in enumerate(high_quality[:5], 1):
            print(f"#{i} {opp['symbol']} - {opp['composite']:.1f}/100")
            print(f"   📊 {opp['url']}")
            print()
    else:
        print("⚠️  No high-quality opportunities")

    return opportunities


def create_sample_config():
    """Create sample Moralis config file"""
    config = {
        "api_key": "YOUR_MORALIS_API_KEY_HERE",
        "base_url": "https://deep-index.moralis.io/api/v2.2",
        "instructions": [
            "1. Sign up at https://moralis.com",
            "2. Get your API key from the dashboard",
            "3. Replace YOUR_MORALIS_API_KEY_HERE with your actual key",
            "4. Free tier: 40,000 Compute Units per day"
        ]
    }

    with open('moralis_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("✅ Created moralis_config.json template")
    print("   Edit it with your API key to enable Moralis discovery")


if __name__ == "__main__":
    # Check if config exists
    try:
        with open('moralis_config.json', 'r') as f:
            pass
    except FileNotFoundError:
        print("Creating Moralis config template...")
        create_sample_config()
        print()

    discover_and_analyze()
