"""
Demo Filtering Funnel
======================

Demonstrates the filtering funnel with realistic mock data.
Shows how tokens are filtered at each step.
"""

import time
import random
from dex_utils import TokenMetrics, RiskAnalyzer


class FunnelDemo:
    """Demonstrate the filtering funnel"""

    def __init__(self):
        self.step_counts = {}
        self.rejection_reasons = {}

    def generate_mock_tokens(self, count=100):
        """Generate mock token data"""
        tokens = []

        for i in range(count):
            # Vary characteristics
            is_scam = random.random() < 0.3  # 30% scams
            is_cex_listed = random.random() < 0.4  # 40% on CEX
            is_old = random.random() < 0.35  # 35% too old
            low_liq = random.random() < 0.25  # 25% low liquidity

            age_hours = random.randint(1, 200) if not is_old else random.randint(200, 1000)
            liquidity = random.randint(10000, 500000) if not low_liq else random.randint(100, 9000)

            token = {
                'name': f"Token{i:03d}",
                'address': f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                'age_hours': age_hours,
                'liquidity_usd': liquidity,
                'volume_24h': liquidity * random.uniform(0.1, 2.0),
                'holder_count': random.randint(50, 5000),
                'top_10_concentration': random.uniform(10, 80),
                'contract_verified': not is_scam or random.random() > 0.5,
                'liquidity_locked': not is_scam or random.random() > 0.3,
                'buy_tax': random.uniform(0, 20) if is_scam else random.uniform(0, 5),
                'sell_tax': random.uniform(0, 30) if is_scam else random.uniform(0, 5),
                'honeypot_risk': random.uniform(0.5, 1.0) if is_scam else random.uniform(0, 0.3),
                'price_change_1h': random.uniform(-20, 30),
                'price_change_24h': random.uniform(-50, 100),
                'listed_on_cex': is_cex_listed,
                'cex_exchanges': random.sample(['binance', 'coinbase', 'kraken', 'kucoin'],
                                              random.randint(1, 3)) if is_cex_listed else [],
                'creation_time': int(time.time() - age_hours * 3600)
            }

            tokens.append(token)

        return tokens

    def run_funnel(self):
        """Run the complete filtering funnel"""

        print("\n" + "#"*80)
        print("# DEX SCREENING FUNNEL DEMONSTRATION")
        print("#"*80)

        # Configuration
        max_age_hours = 168
        min_liquidity = 50000
        min_safety_score = 60
        min_opportunity_score = 50
        exclude_cex = True

        print(f"\n⚙️  Configuration:")
        print(f"   Max Age: {max_age_hours}h")
        print(f"   Min Liquidity: ${min_liquidity:,}")
        print(f"   Min Safety Score: {min_safety_score}")
        print(f"   Min Opportunity Score: {min_opportunity_score}")
        print(f"   Exclude CEX-Listed: {exclude_cex}")

        # Step 1: Generate tokens
        print("\n" + "="*80)
        print("STEP 1: INITIAL TOKEN SET")
        print("="*80)

        tokens = self.generate_mock_tokens(100)
        step1_count = len(tokens)
        print(f"📊 Generated {step1_count} tokens from DEX API")

        # Step 2: Age filter
        print("\n" + "="*80)
        print(f"STEP 2: AGE FILTER (< {max_age_hours}h)")
        print("="*80)

        age_passed = [t for t in tokens if t['age_hours'] <= max_age_hours]
        age_rejected = len(tokens) - len(age_passed)

        print(f"✓ {len(age_passed)} tokens passed (age ≤ {max_age_hours}h)")
        print(f"✗ {age_rejected} tokens rejected (too old)")

        # Step 3: Liquidity filter
        print("\n" + "="*80)
        print(f"STEP 3: LIQUIDITY FILTER (≥ ${min_liquidity:,})")
        print("="*80)

        liq_passed = [t for t in age_passed if t['liquidity_usd'] >= min_liquidity]
        liq_rejected = len(age_passed) - len(liq_passed)

        print(f"✓ {len(liq_passed)} tokens passed")
        print(f"✗ {liq_rejected} tokens rejected (insufficient liquidity)")

        # Step 4: CEX filter (OPTIMIZED - moved earlier!)
        print("\n" + "="*80)
        print("STEP 4: CEX LISTING FILTER (EARLY REJECTION) 🏦")
        print("="*80)

        cex_passed = []
        cex_rejected = 0

        for token in liq_passed:
            if exclude_cex and token['listed_on_cex']:
                cex_rejected += 1
                continue
            cex_passed.append(token)

        print(f"✓ {len(cex_passed)} tokens passed (DEX-only)")
        print(f"✗ {cex_rejected} tokens rejected (on CEX)")
        print(f"\n💡 Saved computation on {cex_rejected} tokens by filtering early!")

        # Steps 5-7: Detailed analysis (only on DEX-only tokens)
        print("\n" + "="*80)
        print("STEPS 5-7: TOKEN ANALYSIS & SCORING (DEX-ONLY TOKENS)")
        print("="*80)

        safety_passed = []
        opp_passed = []
        honeypot_passed = []
        final_passed = []

        safety_rejected = 0
        opp_rejected = 0
        honeypot_rejected = 0

        for token in cex_passed:
            # Create metrics
            metrics = TokenMetrics(
                token_address=token['address'],
                liquidity_usd=token['liquidity_usd'],
                volume_24h=token['volume_24h'],
                holder_count=token['holder_count'],
                top_10_concentration=token['top_10_concentration'],
                honeypot_risk=token['honeypot_risk'],
                contract_verified=token['contract_verified'],
                buy_tax=token['buy_tax'],
                sell_tax=token['sell_tax'],
                liquidity_locked=token['liquidity_locked'],
                creation_time=token['creation_time'],
                price_change_1h=token['price_change_1h'],
                price_change_24h=token['price_change_24h'],
                listed_on_cex=token['listed_on_cex'],
                cex_exchanges=token['cex_exchanges']
            )

            # Step 5: Safety score
            safety_score = RiskAnalyzer.calculate_safety_score(metrics)
            token['safety_score'] = safety_score

            if safety_score < min_safety_score:
                safety_rejected += 1
                continue

            safety_passed.append(token)

            # Step 6: Opportunity score
            opp_score = RiskAnalyzer.calculate_opportunity_score(metrics)
            token['opportunity_score'] = opp_score

            if opp_score < min_opportunity_score:
                opp_rejected += 1
                continue

            opp_passed.append(token)

            # Step 7: Honeypot check
            if token['honeypot_risk'] > 0.7:
                honeypot_rejected += 1
                continue

            honeypot_passed.append(token)
            final_passed.append(token)

            # Calculate composite
            token['composite'] = (safety_score * 0.6) + (opp_score * 0.4)

        print(f"\n   Step 5 - Safety Filter:")
        print(f"      ✓ {len(safety_passed)} passed | ✗ {safety_rejected} rejected")

        print(f"\n   Step 6 - Opportunity Filter:")
        print(f"      ✓ {len(opp_passed)} passed | ✗ {opp_rejected} rejected")

        print(f"\n   Step 7 - Honeypot Check:")
        print(f"      ✓ {len(honeypot_passed)} passed | ✗ {honeypot_rejected} rejected")

        # Print funnel visualization
        print("\n" + "="*80)
        print("FILTERING FUNNEL VISUALIZATION")
        print("="*80)

        steps = [
            ("1. Initial Tokens", step1_count),
            ("2. Age Filter", len(age_passed)),
            ("3. Liquidity Filter", len(liq_passed)),
            ("4. 🏦 CEX Filter", len(cex_passed)),
            ("5. Safety Score", len(safety_passed)),
            ("6. Opportunity Score", len(opp_passed)),
            ("7. Honeypot Check", len(honeypot_passed)),
            ("8. ✅ QUALIFIED", len(final_passed))
        ]

        for label, count in steps:
            pct = (count / step1_count * 100) if step1_count > 0 else 0
            bar_length = int(pct / 2)
            bar = '█' * bar_length + '░' * (50 - bar_length)

            emoji = '✅' if label.startswith('8.') else '🔍'
            print(f"\n{emoji} {label:25s}")
            print(f"   {bar} {count:3d} tokens ({pct:5.1f}%)")

        # Show qualified tokens
        if final_passed:
            print("\n" + "="*80)
            print(f"🎯 QUALIFIED OPPORTUNITIES ({len(final_passed)})")
            print("="*80)

            # Sort by composite score
            qualified = sorted(final_passed, key=lambda x: x['composite'], reverse=True)

            for i, token in enumerate(qualified[:10], 1):
                dex_badge = "🎯 DEX-ONLY" if not token['listed_on_cex'] else f"CEX: {len(token['cex_exchanges'])}"

                print(f"\n#{i} {token['name']}")
                print(f"   Composite: {token['composite']:.1f}/100 (Safety: {token['safety_score']:.1f}, Opp: {token['opportunity_score']:.1f})")
                print(f"   Liquidity: ${token['liquidity_usd']:,.0f} | Volume: ${token['volume_24h']:,.0f}")
                print(f"   Age: {token['age_hours']:.0f}h | Status: {dex_badge}")
                print(f"   Address: {token['address'][:16]}...")

        # Summary stats
        print("\n" + "="*80)
        print("REJECTION BREAKDOWN")
        print("="*80)

        total_rejected = step1_count - len(final_passed)
        print(f"\n📊 Total tokens rejected: {total_rejected} / {step1_count} ({total_rejected/step1_count*100:.1f}%)")

        rejection_breakdown = [
            ("Too old", age_rejected),
            ("Low liquidity", liq_rejected),
            ("🏦 Listed on CEX (early!)", cex_rejected),
            ("Low safety score", safety_rejected),
            ("Low opportunity score", opp_rejected),
            ("Honeypot detected", honeypot_rejected)
        ]

        for reason, count in rejection_breakdown:
            if count > 0:
                pct = (count / step1_count * 100)
                print(f"   ✗ {reason:30s}: {count:3d} ({pct:5.1f}%)")

        conversion_rate = (len(final_passed) / step1_count * 100) if step1_count > 0 else 0
        print(f"\n✅ Final conversion rate: {len(final_passed)}/{step1_count} = {conversion_rate:.1f}%")

        # Show optimization benefit
        if cex_rejected > 0:
            print(f"\n⚡ OPTIMIZATION BENEFIT:")
            print(f"   By filtering CEX tokens early, we avoided analyzing {cex_rejected} tokens")
            print(f"   Time saved: ~{cex_rejected * 1.5:.0f} seconds per scan cycle!")

        print("\n" + "="*80)
        print("✅ FUNNEL DEMO COMPLETE")
        print("="*80)


if __name__ == "__main__":
    demo = FunnelDemo()
    demo.run_funnel()
