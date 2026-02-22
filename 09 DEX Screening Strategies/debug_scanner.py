"""
Debug Scanner - Show What's Being Filtered
"""

import requests
import time
from datetime import datetime


def debug_api_call():
    """Debug the DexScreener API to see what we're getting"""

    print("\n" + "="*80)
    print("DEBUG: DexScreener API Response")
    print("="*80)

    # Try to get some BSC pairs
    url = "https://api.dexscreener.com/latest/dex/search?q=WBNB"

    print(f"\n📡 Calling: {url}")
    print("⏳ Waiting for response...")

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if 'pairs' in data:
                all_pairs = data['pairs']
                print(f"\n✅ API returned {len(all_pairs)} total pairs")

                # Filter for BSC
                bsc_pairs = [p for p in all_pairs if p.get('chainId', '').lower() == 'bsc']
                print(f"✅ {len(bsc_pairs)} pairs are on BSC")

                if bsc_pairs:
                    print(f"\n📊 Analyzing first 10 BSC pairs:\n")

                    for i, pair in enumerate(bsc_pairs[:10], 1):
                        base_token = pair.get('baseToken', {})
                        quote_token = pair.get('quoteToken', {})
                        liquidity = pair.get('liquidity', {})
                        volume = pair.get('volume', {})

                        # Get timestamps
                        created_at = pair.get('pairCreatedAt', 0)
                        if created_at > 0:
                            created_dt = datetime.fromtimestamp(created_at / 1000)
                            age_days = (time.time() - (created_at/1000)) / 86400
                        else:
                            created_dt = "Unknown"
                            age_days = 999

                        print(f"#{i} {base_token.get('symbol', 'UNKNOWN')}/{quote_token.get('symbol', 'UNKNOWN')}")
                        print(f"   DEX: {pair.get('dexId', 'unknown')}")
                        print(f"   Liquidity: ${liquidity.get('usd', 0):,.2f}")
                        print(f"   24h Volume: ${volume.get('h24', 0):,.2f}")
                        print(f"   Created: {created_dt}")
                        print(f"   Age: {age_days:.1f} days")
                        print(f"   Pair Address: {pair.get('pairAddress', 'N/A')[:20]}...")
                        print()

                    # Show filtering stats
                    print(f"{'='*80}")
                    print(f"FILTER ANALYSIS")
                    print(f"{'='*80}\n")

                    # Filter by liquidity
                    min_liq = 5000
                    high_liq = [p for p in bsc_pairs if float(p.get('liquidity', {}).get('usd', 0)) >= min_liq]
                    print(f"Liquidity ≥ ${min_liq:,}: {len(high_liq)}/{len(bsc_pairs)} pairs")

                    # Filter by age
                    max_age_days = 30
                    cutoff = time.time() - (max_age_days * 86400)
                    recent = []
                    for p in bsc_pairs:
                        created = p.get('pairCreatedAt', 0) / 1000
                        if created > cutoff:
                            recent.append(p)
                    print(f"Age < {max_age_days} days: {len(recent)}/{len(bsc_pairs)} pairs")

                    # Combined filters
                    combined = []
                    for p in bsc_pairs:
                        liq = float(p.get('liquidity', {}).get('usd', 0))
                        created = p.get('pairCreatedAt', 0) / 1000
                        if liq >= min_liq and created > cutoff:
                            combined.append(p)

                    print(f"Both filters: {len(combined)}/{len(bsc_pairs)} pairs")

                    if combined:
                        print(f"\n✅ POOLS THAT PASS FILTERS:\n")
                        for p in combined[:5]:
                            base = p.get('baseToken', {})
                            quote = p.get('quoteToken', {})
                            liq = p.get('liquidity', {}).get('usd', 0)
                            vol = p.get('volume', {}).get('h24', 0)
                            created = p.get('pairCreatedAt', 0) / 1000
                            age_days = (time.time() - created) / 86400

                            print(f"  {base.get('symbol')}/{quote.get('symbol')}")
                            print(f"    Liquidity: ${liq:,.0f}")
                            print(f"    Volume: ${vol:,.0f}")
                            print(f"    Age: {age_days:.1f} days")
                            print(f"    Address: {p.get('pairAddress')}")
                            print()
                    else:
                        print(f"\n⚠️  No pools pass the combined filters")
                        print(f"   Try lowering liquidity threshold or increasing max age")

                else:
                    print(f"\n⚠️  No BSC pairs found in response")

            else:
                print(f"\n⚠️  No 'pairs' key in response")
                print(f"Response keys: {data.keys()}")

        else:
            print(f"\n❌ API error: {response.status_code}")
            print(f"Response: {response.text[:200]}")

    except Exception as e:
        print(f"\n❌ Error: {e}")

    print(f"\n{'='*80}")
    print("DEBUG COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    debug_api_call()
