"""
Test CEX Filter
================

Tests the new CEX listing filter to ensure we only find DEX-only tokens.
"""

import time
from real_dex_fetcher import RealDEXFetcher
from dex_utils import RiskAnalyzer


def test_cex_filter():
    """Test the CEX listing filter"""

    print("\n" + "="*80)
    print("TESTING CEX LISTING FILTER")
    print("="*80)

    # Initialize fetcher with CEX checking enabled
    fetcher = RealDEXFetcher(check_cex=True)

    # Get some recent pools
    print("\n[Step 1] Fetching recent pools from DexScreener...")
    pools = fetcher.get_new_pools_by_age(
        chain="ethereum",
        max_age_hours=168,  # 1 week for testing
        min_liquidity=50000
    )

    if not pools:
        print("❌ No pools found. Try adjusting filters.")
        return

    print(f"\n✅ Found {len(pools)} pools")

    # Analyze first 3 pools
    print("\n[Step 2] Analyzing pools and checking CEX listings...")
    print("="*80)

    dex_only_tokens = []
    cex_listed_tokens = []

    for i, pool in enumerate(pools[:5], 1):
        print(f"\n🔍 Pool #{i}: {pool.token0.symbol}/{pool.token1.symbol}")
        print(f"   Address: {pool.address}")
        print(f"   Liquidity: ${pool.liquidity_usd:,.0f}")

        # Get token info from DexScreener
        token_info = fetcher.get_token_info(pool.token0.address, pool.chain)

        if token_info:
            # Create metrics with CEX check
            metrics = fetcher.create_token_metrics(token_info, pool.token0.address)

            # Calculate scores
            safety_score = RiskAnalyzer.calculate_safety_score(metrics)
            opportunity_score = RiskAnalyzer.calculate_opportunity_score(metrics)
            composite = (safety_score * 0.6) + (opportunity_score * 0.4)

            print(f"   Safety: {safety_score:.1f} | Opportunity: {opportunity_score:.1f} | Composite: {composite:.1f}")

            if metrics.listed_on_cex:
                print(f"   ⚠️  On {len(metrics.cex_exchanges)} CEX(s): {', '.join(metrics.cex_exchanges[:3])}")
                cex_listed_tokens.append({
                    'symbol': pool.token0.symbol,
                    'composite': composite,
                    'cex_count': len(metrics.cex_exchanges)
                })
            else:
                print(f"   🎯 DEX-ONLY - Early opportunity!")
                dex_only_tokens.append({
                    'symbol': pool.token0.symbol,
                    'composite': composite
                })

        time.sleep(1)  # Rate limiting

    # Print summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    print(f"\n📊 Tested {len(pools[:5])} tokens:")
    print(f"   🎯 DEX-Only: {len(dex_only_tokens)}")
    print(f"   ⚠️  CEX-Listed: {len(cex_listed_tokens)}")

    if dex_only_tokens:
        print(f"\n✅ DEX-ONLY OPPORTUNITIES:")
        for token in sorted(dex_only_tokens, key=lambda x: x['composite'], reverse=True):
            print(f"   • {token['symbol']} - Composite: {token['composite']:.1f}")

    if cex_listed_tokens:
        print(f"\n⚠️  CEX-LISTED TOKENS (Lower Opportunity):")
        for token in sorted(cex_listed_tokens, key=lambda x: x['composite'], reverse=True):
            print(f"   • {token['symbol']} - Composite: {token['composite']:.1f} - On {token['cex_count']} CEXs")

    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80)

    # Show the impact
    if dex_only_tokens and cex_listed_tokens:
        avg_dex = sum(t['composite'] for t in dex_only_tokens) / len(dex_only_tokens)
        avg_cex = sum(t['composite'] for t in cex_listed_tokens) / len(cex_listed_tokens)
        print(f"\n📈 IMPACT ANALYSIS:")
        print(f"   Average DEX-only score: {avg_dex:.1f}")
        print(f"   Average CEX-listed score: {avg_cex:.1f}")
        print(f"   Difference: {avg_dex - avg_cex:+.1f} points")


if __name__ == "__main__":
    test_cex_filter()
