"""
Demo CEX Filter
================

Demonstrates the CEX listing filter with known tokens.
"""

from dex_utils import DEXDataFetcher, TokenMetrics, RiskAnalyzer
import time


def demo_cex_filter():
    """Demo the CEX listing functionality"""

    print("\n" + "="*80)
    print("CEX LISTING FILTER DEMONSTRATION")
    print("="*80)

    fetcher = DEXDataFetcher()

    # Test with some well-known tokens
    test_tokens = [
        {
            'name': 'USDT (Tether)',
            'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'chain': 'ethereum',
            'expected': 'CEX-listed'
        },
        {
            'name': 'UNI (Uniswap)',
            'address': '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',
            'chain': 'ethereum',
            'expected': 'CEX-listed'
        },
        {
            'name': 'PEPE (Pepe)',
            'address': '0x6982508145454Ce325dDbE47a25d4ec3d2311933',
            'chain': 'ethereum',
            'expected': 'CEX-listed'
        }
    ]

    print(f"\n📊 Testing {len(test_tokens)} tokens for CEX listings...\n")

    for i, token in enumerate(test_tokens, 1):
        print(f"\n{'='*80}")
        print(f"Token #{i}: {token['name']}")
        print(f"{'='*80}")
        print(f"Address: {token['address']}")
        print(f"Chain: {token['chain']}")
        print(f"Expected: {token['expected']}")

        # Check CEX listing
        print(f"\nChecking CEX listings...")
        cex_data = fetcher.check_cex_listing(token['address'], token['chain'])

        print(f"\nResults:")
        print(f"  Listed on CEX: {cex_data['listed_on_cex']}")
        print(f"  Major CEXs: {len(cex_data['major_exchanges'])}")

        if cex_data['major_exchanges']:
            print(f"  Exchanges: {', '.join(cex_data['major_exchanges'][:5])}")

        # Create mock metrics to show scoring impact
        metrics = TokenMetrics(
            token_address=token['address'],
            liquidity_usd=1000000,
            volume_24h=500000,
            holder_count=1000,
            top_10_concentration=30,
            honeypot_risk=0,
            contract_verified=True,
            buy_tax=0,
            sell_tax=0,
            liquidity_locked=True,
            creation_time=int(time.time()) - (48 * 3600),  # 48h ago
            price_change_1h=5,
            price_change_24h=10,
            listed_on_cex=cex_data['listed_on_cex'],
            cex_exchanges=cex_data['major_exchanges']
        )

        # Calculate scores
        safety_score = RiskAnalyzer.calculate_safety_score(metrics)
        opportunity_score = RiskAnalyzer.calculate_opportunity_score(metrics)
        composite = (safety_score * 0.6) + (opportunity_score * 0.4)

        print(f"\nScore Impact:")
        print(f"  Safety Score: {safety_score:.1f}/100")
        print(f"  Opportunity Score: {opportunity_score:.1f}/100")
        print(f"  Composite Score: {composite:.1f}/100")

        if cex_data['listed_on_cex']:
            print(f"\n  ⚠️  FILTERED OUT - Already on {len(cex_data['major_exchanges'])} major CEX(s)")
        else:
            print(f"\n  🎯 QUALIFIED - DEX-only opportunity!")

    # Show comparison
    print("\n" + "="*80)
    print("SCORING COMPARISON")
    print("="*80)

    print("\nDEX-only token (no CEX listings):")
    dex_only = TokenMetrics(
        token_address="0x0000000000000000000000000000000000000000",
        liquidity_usd=1000000,
        volume_24h=500000,
        holder_count=1000,
        top_10_concentration=30,
        honeypot_risk=0,
        contract_verified=True,
        buy_tax=0,
        sell_tax=0,
        liquidity_locked=True,
        creation_time=int(time.time()) - (48 * 3600),
        price_change_1h=5,
        price_change_24h=10,
        listed_on_cex=False,
        cex_exchanges=[]
    )

    dex_safety = RiskAnalyzer.calculate_safety_score(dex_only)
    dex_opp = RiskAnalyzer.calculate_opportunity_score(dex_only)
    dex_composite = (dex_safety * 0.6) + (dex_opp * 0.4)

    print(f"  Opportunity Score: {dex_opp:.1f}/100")
    print(f"  Composite Score: {dex_composite:.1f}/100")

    print("\nCEX-listed token (on 3 major exchanges):")
    cex_listed = TokenMetrics(
        token_address="0x0000000000000000000000000000000000000000",
        liquidity_usd=1000000,
        volume_24h=500000,
        holder_count=1000,
        top_10_concentration=30,
        honeypot_risk=0,
        contract_verified=True,
        buy_tax=0,
        sell_tax=0,
        liquidity_locked=True,
        creation_time=int(time.time()) - (48 * 3600),
        price_change_1h=5,
        price_change_24h=10,
        listed_on_cex=True,
        cex_exchanges=['binance', 'coinbase', 'kraken']
    )

    cex_safety = RiskAnalyzer.calculate_safety_score(cex_listed)
    cex_opp = RiskAnalyzer.calculate_opportunity_score(cex_listed)
    cex_composite = (cex_safety * 0.6) + (cex_opp * 0.4)

    print(f"  Opportunity Score: {cex_opp:.1f}/100")
    print(f"  Composite Score: {cex_composite:.1f}/100")

    print(f"\n📈 Score Difference:")
    print(f"  Opportunity: {dex_opp - cex_opp:+.1f} points")
    print(f"  Composite: {dex_composite - cex_composite:+.1f} points")
    print(f"\n  💡 DEX-only tokens get +30 opportunity points!")
    print(f"  ⚠️  CEX-listed tokens lose -5 points per exchange")

    print("\n" + "="*80)
    print("✅ DEMO COMPLETE")
    print("="*80)


if __name__ == "__main__":
    demo_cex_filter()
