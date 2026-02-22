"""
Live Strategy Runner
====================

Runs Strategy 1 (Pool Scanner) with REAL token data from live DEXs.
"""

import time
from datetime import datetime
from real_dex_fetcher import RealDEXFetcher
from dex_utils import RiskAnalyzer, format_token_report
from dataclasses import dataclass
from typing import List


@dataclass
class LiveOpportunity:
    """Live trading opportunity with real data"""
    pool_address: str
    token_symbol: str
    token_address: str
    pair_symbol: str
    chain: str
    dex_name: str
    liquidity_usd: float
    volume_24h: float
    price_change_1h: float
    price_change_24h: float
    age_hours: float
    safety_score: float
    opportunity_score: float
    composite_score: float
    timestamp: int
    dexscreener_url: str


class LivePoolScanner:
    """
    Strategy 1 with real data integration
    """

    def __init__(self,
                 chains: List[str] = ['ethereum', 'bsc'],
                 min_liquidity_usd: float = 20000,
                 max_pool_age_hours: int = 24,
                 min_safety_score: float = 60,
                 min_opportunity_score: float = 50):
        """Initialize live scanner"""

        self.chains = chains
        self.min_liquidity_usd = min_liquidity_usd
        self.max_pool_age_hours = max_pool_age_hours
        self.min_safety_score = min_safety_score
        self.min_opportunity_score = min_opportunity_score

        self.fetcher = RealDEXFetcher()
        self.opportunities: List[LiveOpportunity] = []
        self.scanned_pools = set()

    def calculate_safety_score(self, pool_data) -> float:
        """
        Calculate safety score from pool data

        Note: Limited by available data from free APIs
        """
        score = 50.0  # Base score (conservative)

        # Liquidity check
        liquidity = pool_data.liquidity_usd
        if liquidity >= 100000:
            score += 15
        elif liquidity >= 50000:
            score += 10
        elif liquidity >= 20000:
            score += 5

        # Volume/Liquidity ratio (healthy trading)
        if liquidity > 0:
            vol_liq_ratio = pool_data.volume_24h / liquidity
            if 0.1 <= vol_liq_ratio <= 2.0:  # Healthy range
                score += 15
            elif vol_liq_ratio > 0:
                score += 5

        # Age bonus (slightly older = more proven)
        age_hours = (time.time() - pool_data.created_timestamp) / 3600
        if 24 <= age_hours <= 72:
            score += 10
        elif 6 <= age_hours <= 24:
            score += 5

        # DEX reputation
        reputable_dexs = ['uniswap', 'pancakeswap', 'sushiswap', 'raydium']
        if any(dex in pool_data.dex_name.lower() for dex in reputable_dexs):
            score += 10

        return min(100, score)

    def calculate_opportunity_score(self, pool_data) -> float:
        """Calculate opportunity score from pool data"""
        score = 0.0

        # Price momentum
        price_change_1h = pool_data.token0.symbol  # Would be in metrics
        price_change_24h = 0  # Extract from pool_data if available

        # For now, use volume as proxy for opportunity
        if pool_data.volume_24h > pool_data.liquidity_usd:
            score += 30  # High volume = high interest

        # Liquidity (higher = better for entry/exit)
        if pool_data.liquidity_usd >= 100000:
            score += 25
        elif pool_data.liquidity_usd >= 50000:
            score += 15
        elif pool_data.liquidity_usd >= 20000:
            score += 10

        # Recency bonus
        age_hours = (time.time() - pool_data.created_timestamp) / 3600
        if age_hours <= 12:
            score += 25
        elif age_hours <= 24:
            score += 15
        elif age_hours <= 48:
            score += 10

        # DEX bonus (more liquidity on major DEXs)
        if 'uniswap' in pool_data.dex_name.lower():
            score += 10

        return min(100, score)

    def scan_and_analyze(self):
        """Run one scan cycle on all chains"""

        print(f"\n{'='*80}")
        print(f"[LIVE SCAN] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")

        all_opportunities = []

        for chain in self.chains:
            print(f"\n🔍 Scanning {chain.upper()}...")

            # Fetch new pools
            pools = self.fetcher.get_new_pools_by_age(
                chain=chain,
                max_age_hours=self.max_pool_age_hours,
                min_liquidity=self.min_liquidity_usd
            )

            if not pools:
                print(f"  No pools found on {chain}")
                continue

            print(f"\n📊 Analyzing {len(pools)} pools...")

            for pool in pools:
                # Skip if already scanned
                if pool.address in self.scanned_pools:
                    continue

                self.scanned_pools.add(pool.address)

                # Calculate scores
                safety_score = self.calculate_safety_score(pool)
                opportunity_score = self.calculate_opportunity_score(pool)
                composite_score = (safety_score * 0.6) + (opportunity_score * 0.4)

                # Age in hours
                age_hours = (time.time() - pool.created_timestamp) / 3600

                print(f"\n  {pool.token0.symbol}/{pool.token1.symbol}")
                print(f"    Safety: {safety_score:.1f} | Opportunity: {opportunity_score:.1f} | Composite: {composite_score:.1f}")

                # Check filters
                if safety_score < self.min_safety_score:
                    print(f"    ✗ REJECT: Safety score too low")
                    continue

                if opportunity_score < self.min_opportunity_score:
                    print(f"    ✗ REJECT: Opportunity score too low")
                    continue

                print(f"    ✓ ACCEPT: High-quality opportunity")

                # Create opportunity
                dexscreener_url = f"https://dexscreener.com/{chain}/{pool.address}"

                opportunity = LiveOpportunity(
                    pool_address=pool.address,
                    token_symbol=pool.token0.symbol,
                    token_address=pool.token0.address,
                    pair_symbol=f"{pool.token0.symbol}/{pool.token1.symbol}",
                    chain=chain,
                    dex_name=pool.dex_name,
                    liquidity_usd=pool.liquidity_usd,
                    volume_24h=pool.volume_24h,
                    price_change_1h=0.0,  # Would extract from API
                    price_change_24h=0.0,  # Would extract from API
                    age_hours=age_hours,
                    safety_score=safety_score,
                    opportunity_score=opportunity_score,
                    composite_score=composite_score,
                    timestamp=int(time.time()),
                    dexscreener_url=dexscreener_url
                )

                all_opportunities.append(opportunity)
                self.opportunities.append(opportunity)

        # Print summary
        if all_opportunities:
            all_opportunities.sort(key=lambda x: x.composite_score, reverse=True)

            print(f"\n{'='*80}")
            print(f"🎯 FOUND {len(all_opportunities)} OPPORTUNITIES")
            print(f"{'='*80}")

            for i, opp in enumerate(all_opportunities[:5], 1):
                print(f"\n#{i} {opp.pair_symbol} on {opp.chain.upper()}")
                print(f"   Composite Score: {opp.composite_score:.1f}/100")
                print(f"   Safety: {opp.safety_score:.1f} | Opportunity: {opp.opportunity_score:.1f}")
                print(f"   Liquidity: ${opp.liquidity_usd:,.0f}")
                print(f"   24h Volume: ${opp.volume_24h:,.0f}")
                print(f"   Age: {opp.age_hours:.1f} hours")
                print(f"   DEX: {opp.dex_name}")
                print(f"   Contract: {opp.token_address}")
                print(f"   📊 Chart: {opp.dexscreener_url}")
        else:
            print(f"\n⚠️  No opportunities found matching criteria")

        return all_opportunities

    def print_full_summary(self):
        """Print complete summary"""

        print(f"\n{'='*80}")
        print(f"LIVE STRATEGY SUMMARY")
        print(f"{'='*80}")

        if not self.opportunities:
            print("\nNo opportunities found yet")
            return

        print(f"\nTotal Opportunities: {len(self.opportunities)}")
        print(f"Total Pools Scanned: {len(self.scanned_pools)}")
        print(f"Hit Rate: {len(self.opportunities)/max(len(self.scanned_pools),1)*100:.1f}%")

        # Sort by composite score
        self.opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        print(f"\n🏆 TOP 10 OPPORTUNITIES:")
        print(f"{'='*80}")

        for i, opp in enumerate(self.opportunities[:10], 1):
            print(f"\n#{i} {opp.pair_symbol} ({opp.chain.upper()})")
            print(f"   Composite: {opp.composite_score:.1f}/100")
            print(f"   Safety: {opp.safety_score:.1f} | Opportunity: {opp.opportunity_score:.1f}")
            print(f"   Liquidity: ${opp.liquidity_usd:,.0f} | Volume: ${opp.volume_24h:,.0f}")
            print(f"   DEX: {opp.dex_name} | Age: {opp.age_hours:.1f}h")
            print(f"   Contract: {opp.token_address}")
            print(f"   📊 {opp.dexscreener_url}")


def main():
    """Run live strategy"""

    print(f"\n{'#'*80}")
    print(f"# LIVE STRATEGY: REAL TOKEN SCANNER")
    print(f"# Fetching data from actual DEXs...")
    print(f"{'#'*80}")

    scanner = LivePoolScanner(
        chains=['ethereum', 'bsc'],
        min_liquidity_usd=20000,
        max_pool_age_hours=48,
        min_safety_score=60,
        min_opportunity_score=50
    )

    print(f"\n⚙️  Configuration:")
    print(f"  Chains: {', '.join(scanner.chains)}")
    print(f"  Min Liquidity: ${scanner.min_liquidity_usd:,.0f}")
    print(f"  Max Pool Age: {scanner.max_pool_age_hours}h")
    print(f"  Min Safety Score: {scanner.min_safety_score}")
    print(f"  Min Opportunity Score: {scanner.min_opportunity_score}")

    # Run scan
    opportunities = scanner.scan_and_analyze()

    # Print summary
    scanner.print_full_summary()

    print(f"\n{'='*80}")
    print(f"SCAN COMPLETE")
    print(f"{'='*80}")

    if opportunities:
        print(f"\n💡 NEXT STEPS:")
        print(f"  1. Visit the DexScreener URLs to see charts")
        print(f"  2. Verify contracts on Etherscan/BSCScan")
        print(f"  3. Check for honeypots at honeypot.is")
        print(f"  4. Review developer activity (GitHub, social media)")
        print(f"  5. If all checks pass, consider entering position")
        print(f"\n⚠️  Remember: These are high-risk investments. Start small!")
    else:
        print(f"\n💡 No opportunities found this scan.")
        print(f"   Try adjusting filters or scanning again later.")

    print()


if __name__ == "__main__":
    main()
