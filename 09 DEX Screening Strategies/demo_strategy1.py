"""
Demo for Strategy 1: Pool Scanner with Mock Data
"""

from strategy1_pool_scanner import PoolScannerStrategy, PoolOpportunity
from dex_utils import TokenMetrics, Token, LiquidityPool
import time


def create_mock_pools():
    """Create mock liquidity pools for demo"""
    pools = []

    # Mock pool data with varying quality
    pool_data = [
        ("MOONGEM", 125000, 89000, True, 2.0, 2.5, 35, 250, 8.5, 15.2),
        ("RUGPULL", 8000, 2000, False, 15.0, 25.0, 75, 45, -5.2, -12.0),
        ("SAFECOIN", 95000, 52000, True, 1.0, 1.0, 28, 420, 5.2, 12.8),
        ("SCAMTOK", 15000, 500, False, 8.0, 12.0, 82, 28, 2.1, 3.5),
        ("LEGITGEM", 180000, 125000, True, 1.5, 1.5, 32, 680, 12.5, 28.4),
        ("HONEYPOT", 25000, 1000, False, 5.0, 95.0, 88, 18, 45.2, 120.5),
        ("TRENDING", 75000, 95000, True, 2.5, 2.5, 38, 520, 18.2, 42.5),
        ("SLOWGEM", 50000, 8000, True, 3.0, 3.0, 45, 180, 1.2, 2.8),
    ]

    for symbol, liq, vol, verified, buy_tax, sell_tax, concentration, holders, price_1h, price_24h in pool_data:
        token = Token(
            address=f"0x{hash(symbol) % (10**40):040x}",
            symbol=symbol,
            name=f"{symbol} Token",
            chain="ethereum",
            decimals=18
        )

        pool = LiquidityPool(
            address=f"0x{hash(f'pool_{symbol}') % (10**40):040x}",
            token0=token,
            token1=Token("0x"+"0"*40, "WETH", "Wrapped Ether", "ethereum", 18),
            liquidity_usd=liq,
            volume_24h=vol,
            created_timestamp=int(time.time() - 3600),  # 1 hour old
            dex_name="Uniswap V2",
            chain="ethereum"
        )

        pools.append((pool, verified, buy_tax, sell_tax, concentration, holders, price_1h, price_24h))

    return pools


def main():
    """Run Strategy 1 with mock data"""

    print("\n" + "="*80)
    print("DEMO: STRATEGY 1 - NEW LIQUIDITY POOL SCANNER")
    print("="*80)
    print("\nRunning with mock pool data to demonstrate functionality...\n")

    # Initialize strategy
    strategy = PoolScannerStrategy(
        chains=['ethereum', 'bsc'],
        min_liquidity_usd=20000,
        max_pool_age_hours=48,
        min_safety_score=65,
        min_opportunity_score=55,
        scan_interval_seconds=1  # Fast for demo
    )

    # Create mock pools
    mock_pools = create_mock_pools()

    print(f"{'#'*80}")
    print(f"# Scanning {len(mock_pools)} newly created pools on Ethereum...")
    print(f"{'#'*80}\n")

    # Manually populate opportunities by analyzing each pool
    for pool, verified, buy_tax, sell_tax, concentration, holders, price_1h, price_24h in mock_pools:

        print(f"Analyzing: {pool.token0.symbol}")
        print(f"  Pool Address: {pool.address[:20]}...")
        print(f"  Liquidity: ${pool.liquidity_usd:,.0f}")
        print(f"  24h Volume: ${pool.volume_24h:,.0f}")

        # Mark as scanned
        strategy.scanned_pools.add(pool.address)

        # Create metrics
        metrics = TokenMetrics(
            token_address=pool.token0.address,
            liquidity_usd=pool.liquidity_usd,
            volume_24h=pool.volume_24h,
            holder_count=holders,
            top_10_concentration=concentration,
            honeypot_risk=0.9 if sell_tax > 50 else 0.1,
            contract_verified=verified,
            buy_tax=buy_tax,
            sell_tax=sell_tax,
            liquidity_locked=verified,  # Assume locked if verified
            creation_time=pool.created_timestamp,
            price_change_1h=price_1h,
            price_change_24h=price_24h
        )

        # Calculate safety score
        safety_score = 100.0
        if not verified:
            safety_score -= 20
        if metrics.honeypot_risk > 0.5:
            safety_score -= 30
        if buy_tax > 10 or sell_tax > 10:
            safety_score -= 15
        if concentration > 50:
            safety_score -= 20
        if not metrics.liquidity_locked:
            safety_score -= 15
        if pool.liquidity_usd < 50000:
            safety_score -= 10
        safety_score = max(0, safety_score)

        # Calculate opportunity score
        opp_score = 0.0
        if price_1h > 5:
            opp_score += 15
        if price_24h > 10:
            opp_score += 20
        if pool.volume_24h > pool.liquidity_usd * 0.5:
            opp_score += 25
        if holders > 100:
            opp_score += 10
        age_hours = (time.time() - pool.created_timestamp) / 3600
        if age_hours < 48:
            opp_score += 20
        if 20 < concentration < 40:
            opp_score += 10
        opp_score = min(100, opp_score)

        # Composite score
        composite = (safety_score * 0.6) + (opp_score * 0.4)

        print(f"  Safety Score: {safety_score:.1f}/100")
        print(f"  Opportunity Score: {opp_score:.1f}/100")
        print(f"  Composite Score: {composite:.1f}/100")

        # Check filters
        passed = True
        reject_reason = None

        if safety_score < strategy.min_safety_score:
            passed = False
            reject_reason = f"Safety score too low ({safety_score:.1f} < {strategy.min_safety_score})"
        elif opp_score < strategy.min_opportunity_score:
            passed = False
            reject_reason = f"Opportunity score too low ({opp_score:.1f} < {strategy.min_opportunity_score})"
        elif metrics.honeypot_risk > 0.7:
            passed = False
            reject_reason = "High honeypot risk detected"
        elif pool.liquidity_usd < strategy.min_liquidity_usd:
            passed = False
            reject_reason = f"Liquidity too low (${pool.liquidity_usd:,.0f} < ${strategy.min_liquidity_usd:,.0f})"

        if passed:
            print(f"  ✓ ACCEPT - High-quality opportunity")

            opportunity = PoolOpportunity(
                pool=pool,
                metrics=metrics,
                safety_score=safety_score,
                opportunity_score=opp_score,
                composite_score=composite,
                timestamp=int(time.time())
            )
            strategy.opportunities.append(opportunity)
        else:
            print(f"  ✗ REJECT - {reject_reason}")

        print()

    # Print summary
    strategy.print_summary()


if __name__ == "__main__":
    main()
