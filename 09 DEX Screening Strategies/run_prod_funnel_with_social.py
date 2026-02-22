"""
Production Funnel with Social Sentiment
========================================

Enhanced version of run_prod_funnel.py with social media sentiment analysis.

Adds social sentiment scoring to improve token quality filtering.
"""

import time
import requests
from datetime import datetime
from dex_utils import TokenMetrics, RiskAnalyzer, DEXDataFetcher
from social_sentiment import SocialSentimentAnalyzer, add_social_sentiment_to_metrics


def fetch_real_pools():
    """Fetch pools using multiple search strategies"""

    print("\n🔍 Fetching pools from DexScreener...")

    session = requests.Session()
    session.headers.update({'User-Agent': 'DEX-Screener/1.0'})

    all_pools = []

    strategies = [
        ('bsc', 'pancakeswap'),
        ('ethereum', 'uniswap'),
        ('bsc', 'WBNB'),
    ]

    for chain, search_term in strategies:
        try:
            url = f"https://api.dexscreener.com/latest/dex/search?q={search_term}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if 'pairs' in data:
                    pairs = data['pairs']
                    chain_pairs = [p for p in pairs if p.get('chainId', '').lower() == chain.lower()]
                    all_pools.extend(chain_pairs)

                    if len(all_pools) >= 50:
                        break

        except Exception as e:
            print(f"   Error: {e}")

        time.sleep(1.5)

    # Deduplicate
    seen = set()
    unique_pools = []
    for pool in all_pools:
        addr = pool.get('pairAddress', '')
        if addr and addr not in seen:
            seen.add(addr)
            unique_pools.append(pool)

    print(f"   ✅ Fetched {len(unique_pools)} unique pools")
    return unique_pools


def run_production_funnel_with_social():
    """Run the complete funnel with social sentiment analysis"""

    print("\n" + "="*80)
    print("PRODUCTION DEX SCREENING FUNNEL + SOCIAL SENTIMENT")
    print("="*80)

    # Configuration
    max_age_hours = 168
    min_liquidity = 30000
    min_volume_24h = 5000
    min_vol_liq_ratio = 0.20
    max_vol_liq_ratio = 10.0
    min_safety_score = 60
    min_opportunity_score = 50
    min_social_score = 25  # NEW: Minimum social sentiment (F tier and above)
    exclude_cex = True

    print(f"\n⚙️  Filters:")
    print(f"   Age: <{max_age_hours}h")
    print(f"   Liquidity: >${min_liquidity:,}")
    print(f"   Volume: >${min_volume_24h:,}")
    print(f"   Vol/Liq Ratio: {min_vol_liq_ratio*100:.0f}-{max_vol_liq_ratio*100:.0f}%")
    print(f"   Social Sentiment: >{min_social_score}/100 (NEW!)")
    print(f"   DEX-only: {exclude_cex}")

    # Step 1: Fetch pools
    raw_pools = fetch_real_pools()

    if len(raw_pools) == 0:
        print("\n❌ No pools fetched")
        return []

    print(f"\n📊 Starting with {len(raw_pools)} pools")

    # Steps 2-5: Basic filters (age, liquidity, volume, CEX)
    print(f"\n{'─'*80}")
    print("BASIC FILTERING")
    print(f"{'─'*80}")

    cutoff_time = time.time() - (max_age_hours * 3600)
    age_passed = [p for p in raw_pools if (p.get('pairCreatedAt', 0) / 1000) >= cutoff_time]
    print(f"   Age filter: {len(age_passed)} passed")

    liq_passed = [p for p in age_passed if float(p.get('liquidity', {}).get('usd', 0)) >= min_liquidity]
    print(f"   Liquidity filter: {len(liq_passed)} passed")

    vol_passed = []
    for pool in liq_passed:
        liq = float(pool.get('liquidity', {}).get('usd', 0))
        vol = float(pool.get('volume', {}).get('h24', 0))
        vol_liq_ratio = (vol / liq) if liq > 0 else 0

        if vol >= min_volume_24h and min_vol_liq_ratio <= vol_liq_ratio <= max_vol_liq_ratio:
            vol_passed.append(pool)

    print(f"   Volume filter: {len(vol_passed)} passed")

    # CEX filter
    fetcher = DEXDataFetcher()
    cex_passed = []

    check_limit = min(20, len(vol_passed))
    print(f"   Checking first {check_limit} pools for CEX listings...")

    for pool in vol_passed[:check_limit]:
        base = pool.get('baseToken', {})
        token_addr = base.get('address', '')
        chain = pool.get('chainId', 'ethereum')

        if not token_addr:
            continue

        cex_data = fetcher.check_cex_listing(token_addr, chain)

        if exclude_cex and cex_data['listed_on_cex']:
            continue
        else:
            cex_passed.append((pool, cex_data))

    print(f"   CEX filter: {len(cex_passed)} passed (DEX-only)")

    # NEW: Step 6 - Social Sentiment Analysis
    print(f"\n{'─'*80}")
    print("SOCIAL SENTIMENT ANALYSIS (NEW!)")
    print(f"{'─'*80}")

    social_analyzer = SocialSentimentAnalyzer()
    social_passed = []
    social_rejected = 0

    for pool, cex_data in cex_passed:
        base = pool.get('baseToken', {})
        token_symbol = base.get('symbol', 'UNKNOWN')
        token_addr = base.get('address', '')

        print(f"\n  🔍 {token_symbol}")

        # Analyze social sentiment
        social_sentiment = social_analyzer.analyze_token(
            token_address=token_addr,
            token_symbol=token_symbol,
            dex_pool_data=pool
        )

        # Filter by minimum social score
        if social_sentiment.sentiment_score < min_social_score:
            print(f"     ✗ Social sentiment too low ({social_sentiment.sentiment_score:.1f} < {min_social_score})")
            social_rejected += 1
            continue

        print(f"     ✓ Social sentiment: {social_sentiment.sentiment_score:.1f}/100 (Tier {social_sentiment.get_tier()})")
        social_passed.append((pool, cex_data, social_sentiment))

    print(f"\n   ✅ {len(social_passed)} passed social sentiment filter")
    print(f"   ✗ {social_rejected} rejected (low social presence/engagement)")

    # Steps 7-8: Safety & Opportunity Scoring
    print(f"\n{'─'*80}")
    print("SAFETY & OPPORTUNITY SCORING")
    print(f"{'─'*80}")

    qualified = []

    for pool, cex_data, social_sentiment in social_passed:
        base = pool.get('baseToken', {})
        quote = pool.get('quoteToken', {})

        price_change = pool.get('priceChange', {})
        liquidity = float(pool.get('liquidity', {}).get('usd', 0))
        volume = float(pool.get('volume', {}).get('h24', 0))
        created_at = pool.get('pairCreatedAt', int(time.time() * 1000)) / 1000

        metrics = TokenMetrics(
            token_address=base.get('address', ''),
            liquidity_usd=liquidity,
            volume_24h=volume,
            holder_count=100,
            top_10_concentration=35.0,
            honeypot_risk=0.0,
            contract_verified=False,
            buy_tax=0.0,
            sell_tax=0.0,
            liquidity_locked=False,
            creation_time=int(created_at),
            price_change_1h=float(price_change.get('h1', 0) or 0),
            price_change_24h=float(price_change.get('h24', 0) or 0),
            listed_on_cex=cex_data['listed_on_cex'],
            cex_exchanges=cex_data['major_exchanges']
        )

        # Add social sentiment to metrics
        add_social_sentiment_to_metrics(metrics, social_sentiment)

        safety_score = RiskAnalyzer.calculate_safety_score(metrics)
        opp_score = RiskAnalyzer.calculate_opportunity_score(metrics)

        if safety_score < min_safety_score or opp_score < min_opportunity_score:
            continue

        # NEW: Enhanced composite score with social sentiment
        # 50% safety, 30% opportunity, 20% social
        composite = (
            (safety_score * 0.50) +
            (opp_score * 0.30) +
            (social_sentiment.sentiment_score * 0.20)
        )

        print(f"\n  📊 {base.get('symbol')}/{quote.get('symbol')}")
        print(f"     Safety: {safety_score:.1f} | Opportunity: {opp_score:.1f} | Social: {social_sentiment.sentiment_score:.1f}")
        print(f"     Composite: {composite:.1f}/100 (enhanced with social)")

        qualified.append({
            'symbol': f"{base.get('symbol')}/{quote.get('symbol')}",
            'base_symbol': base.get('symbol'),
            'address': base.get('address'),
            'pair_address': pool.get('pairAddress'),
            'chain': pool.get('chainId'),
            'dex': pool.get('dexId'),
            'liquidity': liquidity,
            'volume': volume,
            'safety': safety_score,
            'opportunity': opp_score,
            'social_sentiment': social_sentiment.sentiment_score,  # NEW
            'social_tier': social_sentiment.get_tier(),  # NEW
            'composite': composite,
            'price_1h': metrics.price_change_1h,
            'price_24h': metrics.price_change_24h,
            'url': f"https://dexscreener.com/{pool.get('chainId')}/{pool.get('pairAddress')}",
            'social_links': {
                'twitter': social_sentiment.social_links.twitter,
                'telegram': social_sentiment.social_links.telegram,
            }
        })

    qualified.sort(key=lambda x: x['composite'], reverse=True)

    # Show results
    print(f"\n{'='*80}")
    print(f"🎯 QUALIFIED OPPORTUNITIES ({len(qualified)})")
    print(f"{'='*80}")

    if qualified:
        for i, token in enumerate(qualified, 1):
            social_badge = f"Social: {token['social_tier']} ({token['social_sentiment']:.1f})"

            print(f"\n#{i} {token['symbol']}")
            print(f"   Chain: {token['chain'].upper()} | DEX: {token['dex']}")
            print(f"   Composite: {token['composite']:.1f}/100")
            print(f"     Safety: {token['safety']:.1f} | Opportunity: {token['opportunity']:.1f} | {social_badge}")
            print(f"   Liquidity: ${token['liquidity']:,.0f} | Volume: ${token['volume']:,.0f}")
            print(f"   Price: 1h {token['price_1h']:+.1f}% | 24h {token['price_24h']:+.1f}%")

            if token['social_links']['twitter']:
                print(f"   🐦 {token['social_links']['twitter']}")
            if token['social_links']['telegram']:
                print(f"   💬 {token['social_links']['telegram']}")

            print(f"   🔗 {token['url']}")
    else:
        print("\n❌ NO QUALIFIED OPPORTUNITIES")

    # Summary
    print(f"\n{'='*80}")
    print("FILTERING SUMMARY")
    print(f"{'='*80}")

    print(f"\n  Starting pools: {len(raw_pools)}")
    print(f"  After age filter: {len(age_passed)}")
    print(f"  After liquidity filter: {len(liq_passed)}")
    print(f"  After volume filter: {len(vol_passed)}")
    print(f"  After CEX filter: {len(cex_passed)}")
    print(f"  After SOCIAL filter: {len(social_passed)} (NEW!)")
    print(f"  Final qualified: {len(qualified)}")

    conversion_rate = (len(qualified) / len(raw_pools) * 100) if len(raw_pools) > 0 else 0
    print(f"\n  Conversion rate: {len(qualified)}/{len(raw_pools)} = {conversion_rate:.1f}%")

    print(f"\n{'='*80}")
    print("✅ PRODUCTION FUNNEL WITH SOCIAL SENTIMENT COMPLETE")
    print(f"{'='*80}\n")

    return qualified


if __name__ == "__main__":
    run_production_funnel_with_social()
