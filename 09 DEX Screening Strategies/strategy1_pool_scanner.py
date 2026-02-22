"""
Strategy 1: New Liquidity Pool Scanner
=======================================

Monitors newly created liquidity pools across multiple DEXs and chains.
Filters based on safety criteria and ranks opportunities.

Key Features:
- Real-time monitoring of new pool creations
- Multi-chain support (Ethereum, BSC, Solana)
- Safety filtering (honeypot detection, contract verification, liquidity locks)
- Opportunity scoring based on early metrics
- Alert generation for high-quality opportunities

Ideal For:
- Finding legitimate new token launches
- Avoiding rug pulls and honeypots
- Getting in early on promising projects with strong fundamentals
"""

import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from dex_utils import (
    DEXDataFetcher, TokenMetrics, RiskAnalyzer,
    format_token_report, LiquidityPool
)


@dataclass
class PoolOpportunity:
    """Scored liquidity pool opportunity"""
    pool: LiquidityPool
    metrics: TokenMetrics
    safety_score: float
    opportunity_score: float
    composite_score: float
    timestamp: int


class PoolScannerStrategy:
    """
    Strategy 1: New Liquidity Pool Scanner

    Scans for newly created pools and filters for quality opportunities
    """

    def __init__(self,
                 chains: List[str] = ['ethereum', 'bsc', 'solana'],
                 min_liquidity_usd: float = 10000,
                 max_pool_age_hours: int = 24,
                 min_safety_score: float = 60,
                 min_opportunity_score: float = 50,
                 scan_interval_seconds: int = 300,
                 exclude_cex_listed: bool = True):
        """
        Initialize the Pool Scanner Strategy

        Args:
            chains: List of chains to monitor
            min_liquidity_usd: Minimum initial liquidity
            max_pool_age_hours: Maximum pool age to consider
            min_safety_score: Minimum safety threshold (0-100)
            min_opportunity_score: Minimum opportunity threshold (0-100)
            scan_interval_seconds: Time between scans
            exclude_cex_listed: Filter out tokens already on major CEXs (default True)
        """
        self.chains = chains
        self.min_liquidity_usd = min_liquidity_usd
        self.max_pool_age_hours = max_pool_age_hours
        self.min_safety_score = min_safety_score
        self.min_opportunity_score = min_opportunity_score
        self.scan_interval = scan_interval_seconds
        self.exclude_cex_listed = exclude_cex_listed

        self.fetcher = DEXDataFetcher()
        self.opportunities: List[PoolOpportunity] = []
        self.scanned_pools = set()  # Track pools we've already analyzed
        self.cex_rejected_count = 0  # Track how many rejected due to CEX listing

    def scan_new_pools(self, chain: str) -> List[LiquidityPool]:
        """Scan for new pools on a specific chain"""
        print(f"\n[Strategy 1] Scanning new pools on {chain.upper()}...")

        pools = self.fetcher.get_new_pools(
            chain=chain,
            min_liquidity=self.min_liquidity_usd,
            max_age_hours=self.max_pool_age_hours
        )

        # Filter out already scanned pools
        new_pools = [p for p in pools if p.address not in self.scanned_pools]

        print(f"  Found {len(new_pools)} new pools (filtered {len(pools) - len(new_pools)} already scanned)")

        return new_pools

    def analyze_pool(self, pool: LiquidityPool) -> Optional[PoolOpportunity]:
        """
        Analyze a pool and determine if it's a viable opportunity

        Returns:
            PoolOpportunity if viable, None otherwise
        """
        # Get metrics for the non-stablecoin token
        # Assume token0 is the new token if token1 is WETH/WBNB/USDC/etc
        target_token = pool.token0

        metrics = self.fetcher.get_token_metrics(target_token.address, pool.chain)

        # Calculate scores
        safety_score = RiskAnalyzer.calculate_safety_score(metrics)
        opportunity_score = RiskAnalyzer.calculate_opportunity_score(metrics)

        # Composite score (weighted average: 60% safety, 40% opportunity)
        composite_score = (safety_score * 0.6) + (opportunity_score * 0.4)

        print(f"  {target_token.symbol}: Safety={safety_score:.1f}, Opp={opportunity_score:.1f}, Composite={composite_score:.1f}")

        # Check if meets minimum thresholds
        if safety_score < self.min_safety_score:
            print(f"    ✗ REJECT: Safety score too low")
            return None

        if opportunity_score < self.min_opportunity_score:
            print(f"    ✗ REJECT: Opportunity score too low")
            return None

        # Additional safety checks
        honeypot_check = self.fetcher.check_honeypot(target_token.address, pool.chain)
        if honeypot_check['is_honeypot']:
            print(f"    ✗ REJECT: Honeypot detected")
            return None

        # CEX listing check - reject if already on major exchanges
        if self.exclude_cex_listed and metrics.listed_on_cex:
            print(f"    ✗ REJECT: Already on {len(metrics.cex_exchanges)} CEX(s) - {', '.join(metrics.cex_exchanges[:2])}")
            self.cex_rejected_count += 1
            return None

        print(f"    ✓ ACCEPT: High-quality opportunity{' (DEX-ONLY 🎯)' if not metrics.listed_on_cex else ''}")

        return PoolOpportunity(
            pool=pool,
            metrics=metrics,
            safety_score=safety_score,
            opportunity_score=opportunity_score,
            composite_score=composite_score,
            timestamp=int(time.time())
        )

    def run_scan_cycle(self):
        """Run one complete scan cycle across all chains"""
        print(f"\n{'='*70}")
        print(f"[Strategy 1: Pool Scanner] Starting scan cycle at {datetime.now()}")
        print(f"{'='*70}")

        cycle_opportunities = []

        for chain in self.chains:
            new_pools = self.scan_new_pools(chain)

            for pool in new_pools:
                # Mark as scanned
                self.scanned_pools.add(pool.address)

                # Analyze the pool
                opportunity = self.analyze_pool(pool)

                if opportunity:
                    cycle_opportunities.append(opportunity)
                    self.opportunities.append(opportunity)

        # Sort opportunities by composite score
        cycle_opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        # Print top opportunities from this cycle
        if cycle_opportunities:
            print(f"\n🎯 Found {len(cycle_opportunities)} opportunities this cycle:")
            for i, opp in enumerate(cycle_opportunities[:5], 1):
                print(f"\n  #{i} {opp.pool.token0.symbol} on {opp.pool.chain.upper()}")
                print(f"     Composite Score: {opp.composite_score:.1f}/100")
                print(f"     Pool: {opp.pool.address}")
                print(f"     Liquidity: ${opp.pool.liquidity_usd:,.0f}")
        else:
            print("\n  No opportunities found this cycle")

        return cycle_opportunities

    def run(self, duration_hours: Optional[float] = None, max_cycles: Optional[int] = None):
        """
        Run the strategy continuously

        Args:
            duration_hours: Run for this many hours (None = indefinite)
            max_cycles: Maximum number of scan cycles (None = indefinite)
        """
        print(f"\n{'#'*70}")
        print(f"# STRATEGY 1: NEW LIQUIDITY POOL SCANNER")
        print(f"{'#'*70}")
        print(f"\nConfiguration:")
        print(f"  Chains: {', '.join(self.chains)}")
        print(f"  Min Liquidity: ${self.min_liquidity_usd:,.0f}")
        print(f"  Max Pool Age: {self.max_pool_age_hours}h")
        print(f"  Min Safety Score: {self.min_safety_score}")
        print(f"  Min Opportunity Score: {self.min_opportunity_score}")
        print(f"  Scan Interval: {self.scan_interval}s")
        print(f"  Exclude CEX-Listed: {'✓ Yes (DEX-only)' if self.exclude_cex_listed else '✗ No'}")
        if duration_hours:
            print(f"  Duration: {duration_hours}h")
        if max_cycles:
            print(f"  Max Cycles: {max_cycles}")

        start_time = time.time()
        cycle_count = 0

        try:
            while True:
                # Run scan cycle
                self.run_scan_cycle()
                cycle_count += 1

                # Check exit conditions
                if max_cycles and cycle_count >= max_cycles:
                    print(f"\n[Strategy 1] Reached max cycles ({max_cycles})")
                    break

                if duration_hours:
                    elapsed_hours = (time.time() - start_time) / 3600
                    if elapsed_hours >= duration_hours:
                        print(f"\n[Strategy 1] Reached duration limit ({duration_hours}h)")
                        break

                # Wait before next cycle
                print(f"\n[Strategy 1] Waiting {self.scan_interval}s until next scan...")
                time.sleep(self.scan_interval)

        except KeyboardInterrupt:
            print("\n[Strategy 1] Stopped by user")

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print strategy performance summary"""
        print(f"\n{'='*70}")
        print(f"STRATEGY 1: POOL SCANNER - SUMMARY")
        print(f"{'='*70}")

        if not self.opportunities:
            print("No opportunities found")
            return

        print(f"\nTotal Opportunities Found: {len(self.opportunities)}")
        print(f"Total Pools Scanned: {len(self.scanned_pools)}")
        print(f"Hit Rate: {len(self.opportunities)/max(len(self.scanned_pools),1)*100:.1f}%")
        if self.exclude_cex_listed:
            print(f"Rejected due to CEX listing: {self.cex_rejected_count}")

        # Sort by composite score
        self.opportunities.sort(key=lambda x: x.composite_score, reverse=True)

        print(f"\n🏆 TOP 10 OPPORTUNITIES:")
        print(f"{'='*70}")

        for i, opp in enumerate(self.opportunities[:10], 1):
            print(f"\n#{i} {opp.pool.token0.symbol} ({opp.pool.chain.upper()})")
            print(f"   Composite Score: {opp.composite_score:.1f}/100")
            print(f"   Safety: {opp.safety_score:.1f} | Opportunity: {opp.opportunity_score:.1f}")
            print(f"   Liquidity: ${opp.metrics.liquidity_usd:,.0f}")
            print(f"   24h Volume: ${opp.metrics.volume_24h:,.0f}")
            print(f"   Contract: {opp.pool.token0.address}")
            print(f"   Found: {datetime.fromtimestamp(opp.timestamp).strftime('%Y-%m-%d %H:%M:%S')}")

    def get_ranked_opportunities(self) -> List[PoolOpportunity]:
        """Get all opportunities ranked by composite score"""
        return sorted(self.opportunities, key=lambda x: x.composite_score, reverse=True)


def main():
    """Example usage of Strategy 1"""

    # Initialize strategy with CEX filtering enabled
    strategy = PoolScannerStrategy(
        chains=['ethereum', 'bsc'],
        min_liquidity_usd=20000,
        max_pool_age_hours=48,
        min_safety_score=65,
        min_opportunity_score=55,
        scan_interval_seconds=300,  # 5 minutes
        exclude_cex_listed=True  # 🎯 Filter out tokens already on major CEXs
    )

    # Run for 2 cycles (demo mode)
    strategy.run(max_cycles=2)


if __name__ == "__main__":
    main()
