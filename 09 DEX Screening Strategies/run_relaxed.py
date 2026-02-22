"""
Relaxed Strategy Runner - Find More Tokens
===========================================

Uses more permissive filters to find actual opportunities.
Good for learning and seeing the system work.
"""

import time
from datetime import datetime
from real_dex_fetcher import RealDEXFetcher
from run_live_strategy import LivePoolScanner


def main():
    """Run with relaxed filters to find actual tokens"""

    print(f"\n{'#'*80}")
    print(f"# RELAXED STRATEGY: MORE PERMISSIVE FILTERS")
    print(f"# Finding real tokens to analyze...")
    print(f"{'#'*80}")

    # More relaxed settings
    scanner = LivePoolScanner(
        chains=['bsc', 'ethereum'],  # BSC first (more activity)
        min_liquidity_usd=5000,      # Much lower (was 20000)
        max_pool_age_hours=720,      # 30 days (was 48)
        min_safety_score=50,         # Lower (was 60)
        min_opportunity_score=40     # Lower (was 50)
    )

    print(f"\n⚙️  Relaxed Configuration:")
    print(f"  Chains: {', '.join(scanner.chains)}")
    print(f"  Min Liquidity: ${scanner.min_liquidity_usd:,.0f} (relaxed)")
    print(f"  Max Pool Age: {scanner.max_pool_age_hours}h (30 days)")
    print(f"  Min Safety Score: {scanner.min_safety_score} (relaxed)")
    print(f"  Min Opportunity Score: {scanner.min_opportunity_score} (relaxed)")
    print(f"\n  ⚠️  More permissive = More results but also more risk!")
    print(f"  ⚠️  ALWAYS verify before buying!\n")

    # Run scan
    opportunities = scanner.scan_and_analyze()

    # Print summary
    scanner.print_full_summary()

    print(f"\n{'='*80}")
    print(f"SCAN COMPLETE")
    print(f"{'='*80}")

    if opportunities:
        print(f"\n📊 ANALYSIS:")
        print(f"  Found: {len(opportunities)} opportunities")
        print(f"  Scanned: {len(scanner.scanned_pools)} pools")
        print(f"  Hit Rate: {len(opportunities)/max(len(scanner.scanned_pools),1)*100:.1f}%")

        # Show score distribution
        high = sum(1 for o in opportunities if o.composite_score >= 75)
        medium = sum(1 for o in opportunities if 60 <= o.composite_score < 75)
        low = sum(1 for o in opportunities if o.composite_score < 60)

        print(f"\n  Score Distribution:")
        print(f"    High (≥75):   {high} ({high/len(opportunities)*100:.0f}%)")
        print(f"    Medium (60-74): {medium} ({medium/len(opportunities)*100:.0f}%)")
        print(f"    Low (<60):    {low} ({low/len(opportunities)*100:.0f}%)")

        print(f"\n💡 NEXT STEPS:")
        print(f"  1. Click DexScreener URLs to see charts")
        print(f"  2. For top 3 tokens, visit honeypot.is")
        print(f"  3. Check contracts on Etherscan/BSCScan")
        print(f"  4. Review social media presence")
        print(f"  5. If ALL checks pass, consider SMALL test trade")
        print(f"\n  ⚠️  Start with $50-100 maximum!")
        print(f"  ⚠️  Most tokens fail - this is very high risk!")
    else:
        print(f"\n💡 Still no opportunities found.")
        print(f"   This could mean:")
        print(f"   - Market is slow right now")
        print(f"   - Try different time of day")
        print(f"   - Try adding more chains")
        print(f"   - API may be having issues")

    print()


if __name__ == "__main__":
    main()
