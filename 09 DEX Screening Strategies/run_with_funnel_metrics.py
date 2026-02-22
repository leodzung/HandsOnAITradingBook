"""
DEX Strategy with Funnel Metrics
=================================

Runs the DEX screening strategy and shows token counts at each filtering step.
"""

import time
from datetime import datetime
from real_dex_fetcher import RealDEXFetcher
from dex_utils import RiskAnalyzer, DEXDataFetcher


class FunnelMetrics:
    """Track filtering funnel metrics"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.step_counts = {
            '1_fetched': 0,
            '2_age_filter': 0,
            '3_liquidity_filter': 0,
            '4_safety_filter': 0,
            '5_opportunity_filter': 0,
            '6_honeypot_filter': 0,
            '7_cex_filter': 0,
            '8_final': 0
        }
        self.rejection_reasons = {
            'too_old': 0,
            'low_liquidity': 0,
            'low_safety': 0,
            'low_opportunity': 0,
            'honeypot': 0,
            'cex_listed': 0
        }

    def print_funnel(self):
        """Print the filtering funnel"""
        print("\n" + "="*80)
        print("FILTERING FUNNEL")
        print("="*80)

        total = self.step_counts['1_fetched']
        if total == 0:
            print("No tokens fetched")
            return

        steps = [
            ('1. Tokens Fetched from API', '1_fetched'),
            ('2. Age Filter (< max hours)', '2_age_filter'),
            ('3. Liquidity Filter (> min USD)', '3_liquidity_filter'),
            ('4. Safety Score Filter', '4_safety_filter'),
            ('5. Opportunity Score Filter', '5_opportunity_filter'),
            ('6. Honeypot Check', '6_honeypot_filter'),
            ('7. CEX Listing Filter', '7_cex_filter'),
            ('8. ✅ FINAL QUALIFIED', '8_final')
        ]

        for label, key in steps:
            count = self.step_counts[key]
            pct = (count / total * 100) if total > 0 else 0
            bar_length = int(pct / 2)  # 50 chars max
            bar = '█' * bar_length + '░' * (50 - bar_length)

            emoji = '✅' if key == '8_final' else '🔍'
            print(f"\n{emoji} {label}")
            print(f"   {bar} {count:3d} tokens ({pct:5.1f}%)")

        print("\n" + "="*80)
        print("REJECTION BREAKDOWN")
        print("="*80)

        for reason, count in self.rejection_reasons.items():
            if count > 0:
                pct = (count / total * 100) if total > 0 else 0
                print(f"  ✗ {reason:20s}: {count:3d} ({pct:5.1f}%)")


def run_with_metrics():
    """Run strategy with detailed funnel metrics"""

    print("\n" + "#"*80)
    print("# DEX SCREENING STRATEGY - WITH FUNNEL METRICS")
    print("#"*80)

    # Configuration
    chain = 'ethereum'
    max_age_hours = 168  # 1 week for better results
    min_liquidity = 50000
    min_safety_score = 60
    min_opportunity_score = 50
    exclude_cex = True

    print(f"\n⚙️  Configuration:")
    print(f"   Chain: {chain.upper()}")
    print(f"   Max Age: {max_age_hours}h")
    print(f"   Min Liquidity: ${min_liquidity:,}")
    print(f"   Min Safety Score: {min_safety_score}")
    print(f"   Min Opportunity Score: {min_opportunity_score}")
    print(f"   Exclude CEX-Listed: {exclude_cex}")

    metrics = FunnelMetrics()
    fetcher = RealDEXFetcher(check_cex=exclude_cex)
    dex_data_fetcher = DEXDataFetcher()

    # Step 1: Fetch pools
    print("\n" + "="*80)
    print("STEP 1: FETCHING POOLS FROM DEXSCREENER")
    print("="*80)

    raw_pools = fetcher.get_latest_pools(chain=chain, limit=50)
    metrics.step_counts['1_fetched'] = len(raw_pools)

    print(f"\n📊 Fetched {len(raw_pools)} pools from DexScreener API")

    if not raw_pools:
        print("❌ No pools found. Exiting.")
        return

    # Step 2: Age filter
    print("\n" + "="*80)
    print(f"STEP 2: FILTERING BY AGE (< {max_age_hours}h)")
    print("="*80)

    cutoff_time = time.time() - (max_age_hours * 3600)
    age_filtered = []

    for pool in raw_pools:
        created_at = pool.get('pairCreatedAt', 0) / 1000
        if created_at >= cutoff_time:
            age_filtered.append(pool)
        else:
            metrics.rejection_reasons['too_old'] += 1

    metrics.step_counts['2_age_filter'] = len(age_filtered)
    print(f"   ✓ {len(age_filtered)} pools passed age filter")
    print(f"   ✗ {metrics.rejection_reasons['too_old']} pools too old")

    # Step 3: Liquidity filter
    print("\n" + "="*80)
    print(f"STEP 3: FILTERING BY LIQUIDITY (> ${min_liquidity:,})")
    print("="*80)

    liq_filtered = []

    for pool in age_filtered:
        liq = float(pool.get('liquidity', {}).get('usd', 0))
        if liq >= min_liquidity:
            liq_filtered.append(pool)
        else:
            metrics.rejection_reasons['low_liquidity'] += 1

    metrics.step_counts['3_liquidity_filter'] = len(liq_filtered)
    print(f"   ✓ {len(liq_filtered)} pools passed liquidity filter")
    print(f"   ✗ {metrics.rejection_reasons['low_liquidity']} pools insufficient liquidity")

    if not liq_filtered:
        print("\n❌ No pools passed basic filters. Try lowering thresholds.")
        metrics.print_funnel()
        return

    # Steps 4-7: Analyze each pool
    print("\n" + "="*80)
    print("STEPS 4-7: ANALYZING TOKENS & APPLYING FILTERS")
    print("="*80)

    qualified_tokens = []

    for i, pool in enumerate(liq_filtered, 1):
        base = pool.get('baseToken', {})
        quote = pool.get('quoteToken', {})
        token_addr = base.get('address', '')

        print(f"\n🔍 [{i}/{len(liq_filtered)}] {base.get('symbol')}/{quote.get('symbol')}")
        print(f"   Address: {token_addr[:16]}...")

        # Get full token info
        token_info = fetcher.get_token_info(token_addr, chain)

        if not token_info:
            print(f"   ✗ Could not fetch token info")
            continue

        # Create metrics
        token_metrics = fetcher.create_token_metrics(token_info, token_addr)

        # Step 4: Safety score
        safety_score = RiskAnalyzer.calculate_safety_score(token_metrics)

        if safety_score < min_safety_score:
            print(f"   ✗ REJECTED: Safety score {safety_score:.1f} < {min_safety_score}")
            metrics.rejection_reasons['low_safety'] += 1
            continue

        metrics.step_counts['4_safety_filter'] += 1
        print(f"   ✓ Safety: {safety_score:.1f}/100")

        # Step 5: Opportunity score
        opportunity_score = RiskAnalyzer.calculate_opportunity_score(token_metrics)

        if opportunity_score < min_opportunity_score:
            print(f"   ✗ REJECTED: Opportunity score {opportunity_score:.1f} < {min_opportunity_score}")
            metrics.rejection_reasons['low_opportunity'] += 1
            continue

        metrics.step_counts['5_opportunity_filter'] += 1
        print(f"   ✓ Opportunity: {opportunity_score:.1f}/100")

        # Step 6: Honeypot check
        honeypot_check = dex_data_fetcher.check_honeypot(token_addr, chain)

        if honeypot_check.get('is_honeypot', False):
            print(f"   ✗ REJECTED: Honeypot detected")
            metrics.rejection_reasons['honeypot'] += 1
            continue

        metrics.step_counts['6_honeypot_filter'] += 1
        print(f"   ✓ Honeypot check passed")

        # Step 7: CEX listing check
        if exclude_cex and token_metrics.listed_on_cex:
            cex_count = len(token_metrics.cex_exchanges)
            cex_names = ', '.join(token_metrics.cex_exchanges[:2])
            print(f"   ✗ REJECTED: Listed on {cex_count} CEX(s) - {cex_names}")
            metrics.rejection_reasons['cex_listed'] += 1
            continue

        metrics.step_counts['7_cex_filter'] += 1

        if not token_metrics.listed_on_cex:
            print(f"   ✓ DEX-ONLY 🎯")
        else:
            print(f"   ✓ CEX check passed")

        # Step 8: QUALIFIED!
        metrics.step_counts['8_final'] += 1

        composite = (safety_score * 0.6) + (opportunity_score * 0.4)
        print(f"   ✅ QUALIFIED - Composite: {composite:.1f}/100")

        qualified_tokens.append({
            'symbol': f"{base.get('symbol')}/{quote.get('symbol')}",
            'base_symbol': base.get('symbol'),
            'address': token_addr,
            'liquidity': token_metrics.liquidity_usd,
            'volume': token_metrics.volume_24h,
            'safety': safety_score,
            'opportunity': opportunity_score,
            'composite': composite,
            'cex_listed': token_metrics.listed_on_cex,
            'cex_exchanges': token_metrics.cex_exchanges,
            'price_1h': token_metrics.price_change_1h,
            'price_24h': token_metrics.price_change_24h
        })

        # Rate limiting
        time.sleep(1.5)

    # Print funnel
    metrics.print_funnel()

    # Print qualified tokens
    if qualified_tokens:
        print("\n" + "="*80)
        print(f"🎯 QUALIFIED OPPORTUNITIES ({len(qualified_tokens)})")
        print("="*80)

        qualified_tokens.sort(key=lambda x: x['composite'], reverse=True)

        for i, token in enumerate(qualified_tokens, 1):
            dex_badge = "🎯 DEX-ONLY" if not token['cex_listed'] else f"CEX: {len(token['cex_exchanges'])}"

            print(f"\n#{i} {token['symbol']}")
            print(f"   Composite: {token['composite']:.1f}/100 | Safety: {token['safety']:.1f} | Opp: {token['opportunity']:.1f}")
            print(f"   Liquidity: ${token['liquidity']:,.0f} | Volume: ${token['volume']:,.0f}")
            print(f"   Price 1h: {token['price_1h']:+.1f}% | 24h: {token['price_24h']:+.1f}%")
            print(f"   Status: {dex_badge}")
            print(f"   Address: {token['address']}")
    else:
        print("\n" + "="*80)
        print("❌ NO QUALIFIED OPPORTUNITIES FOUND")
        print("="*80)
        print("\n💡 Try adjusting filters:")
        print("   • Increase max_age_hours")
        print("   • Lower min_liquidity")
        print("   • Lower min_safety_score or min_opportunity_score")

    print("\n" + "="*80)
    print("✅ ANALYSIS COMPLETE")
    print("="*80)


if __name__ == "__main__":
    run_with_metrics()
