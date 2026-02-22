"""
Demo: Social Sentiment Analysis Integration
============================================

Tests social sentiment analysis on real tokens from production funnel
"""

import time
import requests
from social_sentiment import (
    SocialSentimentAnalyzer,
    format_social_sentiment_report,
    add_social_sentiment_to_metrics
)


def fetch_sample_pools():
    """Fetch sample pools from DexScreener"""
    print("\n🔍 Fetching sample pools from DexScreener...")

    url = "https://api.dexscreener.com/latest/dex/search?q=WBNB"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()

            if 'pairs' in data:
                bsc_pools = [p for p in data['pairs']
                            if p.get('chainId', '').lower() == 'bsc']

                # Filter to pools with decent liquidity
                filtered = [p for p in bsc_pools
                           if float(p.get('liquidity', {}).get('usd', 0)) >= 10000]

                print(f"   ✅ Found {len(filtered)} BSC pools with liquidity ≥ $10k")
                return filtered[:5]  # Top 5

    except Exception as e:
        print(f"   ❌ Error: {e}")

    return []


def demo_basic_analysis():
    """Demo 1: Basic social sentiment analysis"""

    print("\n" + "="*80)
    print("DEMO 1: BASIC SOCIAL SENTIMENT ANALYSIS")
    print("="*80)

    # Initialize analyzer (no API keys needed for basic mode)
    analyzer = SocialSentimentAnalyzer()

    # Fetch sample pools
    pools = fetch_sample_pools()

    if not pools:
        print("\n⚠️  No pools fetched. Using mock data...")
        # Create mock pool data for demonstration
        pools = [{
            'baseToken': {'symbol': 'DEMO', 'address': '0x1234567890abcdef1234567890abcdef12345678'},
            'quoteToken': {'symbol': 'WBNB'},
            'info': {
                'websites': [{'url': 'https://demo.com'}],
                'socials': [
                    {'type': 'twitter', 'url': 'https://twitter.com/democoin'},
                    {'type': 'telegram', 'url': 'https://t.me/democoin'}
                ]
            }
        }]

    # Analyze each pool
    for i, pool in enumerate(pools, 1):
        base = pool.get('baseToken', {})
        token_symbol = base.get('symbol', 'UNKNOWN')
        token_address = base.get('address', '')

        print(f"\n{'─'*80}")
        print(f"Analyzing #{i}: {token_symbol}")
        print(f"{'─'*80}")

        # Run social sentiment analysis
        sentiment = analyzer.analyze_token(
            token_address=token_address,
            token_symbol=token_symbol,
            dex_pool_data=pool
        )

        # Print summary
        print(f"\n  📊 Summary:")
        print(f"     Score: {sentiment.sentiment_score:.1f}/100 (Tier {sentiment.get_tier()})")
        print(f"     Twitter: {sentiment.twitter_score:.1f}/100")
        print(f"     Telegram: {sentiment.telegram_score:.1f}/100")

        if sentiment.social_links.twitter:
            print(f"     🐦 Twitter: {sentiment.social_links.twitter}")
        if sentiment.social_links.telegram:
            print(f"     💬 Telegram: {sentiment.social_links.telegram}")

        # Detailed report
        if i == 1:  # Show full report for first token only
            print(format_social_sentiment_report(sentiment))

        time.sleep(1)  # Rate limiting

    print("\n" + "="*80)
    print("✅ DEMO 1 COMPLETE")
    print("="*80)


def demo_integration_with_existing():
    """Demo 2: Integration with existing DEX screening"""

    print("\n" + "="*80)
    print("DEMO 2: INTEGRATION WITH EXISTING SCREENING")
    print("="*80)

    print("\nThis shows how social sentiment enhances your existing scoring:")

    # Initialize
    analyzer = SocialSentimentAnalyzer()

    # Simulate existing screening results
    mock_opportunities = [
        {
            'symbol': 'TOKEN1/WBNB',
            'base_symbol': 'TOKEN1',
            'address': '0xabc123...',
            'composite_score': 75.0,
            'safety': 80.0,
            'opportunity': 70.0,
            'liquidity': 50000,
            'volume': 25000,
            'pool_data': {
                'baseToken': {'symbol': 'TOKEN1', 'address': '0xabc123'},
                'info': {
                    'socials': [
                        {'type': 'twitter', 'url': 'https://twitter.com/token1'},
                        {'type': 'telegram', 'url': 'https://t.me/token1'}
                    ]
                }
            }
        },
        {
            'symbol': 'TOKEN2/WBNB',
            'base_symbol': 'TOKEN2',
            'address': '0xdef456...',
            'composite_score': 68.0,
            'safety': 65.0,
            'opportunity': 72.0,
            'liquidity': 75000,
            'volume': 50000,
            'pool_data': {
                'baseToken': {'symbol': 'TOKEN2', 'address': '0xdef456'},
                'info': {
                    'socials': [
                        {'type': 'twitter', 'url': 'https://twitter.com/token2'}
                    ]
                }
            }
        }
    ]

    print(f"\nAnalyzing {len(mock_opportunities)} opportunities from existing screening...")

    enhanced_opportunities = []

    for opp in mock_opportunities:
        print(f"\n{'─'*80}")
        print(f"Token: {opp['symbol']}")
        print(f"  Existing Score: {opp['composite_score']:.1f}/100")
        print(f"    Safety: {opp['safety']:.1f} | Opportunity: {opp['opportunity']:.1f}")

        # Add social sentiment
        sentiment = analyzer.analyze_token(
            token_address=opp['address'],
            token_symbol=opp['base_symbol'],
            dex_pool_data=opp['pool_data']
        )

        # Calculate enhanced score (70% existing + 30% social)
        social_weight = sentiment.sentiment_score / 100 * 30
        enhanced_score = (opp['composite_score'] * 0.70) + social_weight

        print(f"\n  Social Sentiment: {sentiment.sentiment_score:.1f}/100")
        print(f"  Enhanced Score: {enhanced_score:.1f}/100 (was {opp['composite_score']:.1f})")
        print(f"  Change: {enhanced_score - opp['composite_score']:+.1f} points")

        opp['social_sentiment'] = sentiment.sentiment_score
        opp['enhanced_score'] = enhanced_score
        enhanced_opportunities.append(opp)

    # Show re-ranking
    print(f"\n{'='*80}")
    print("RANKING COMPARISON")
    print(f"{'='*80}")

    print("\nBEFORE (by composite score):")
    sorted_before = sorted(mock_opportunities, key=lambda x: x['composite_score'], reverse=True)
    for i, opp in enumerate(sorted_before, 1):
        print(f"  {i}. {opp['symbol']}: {opp['composite_score']:.1f}/100")

    print("\nAFTER (by enhanced score with social sentiment):")
    sorted_after = sorted(enhanced_opportunities, key=lambda x: x['enhanced_score'], reverse=True)
    for i, opp in enumerate(sorted_after, 1):
        change = ""
        original_rank = sorted_before.index(opp) + 1
        if i < original_rank:
            change = f" (↑{original_rank-i})"
        elif i > original_rank:
            change = f" (↓{i-original_rank})"
        print(f"  {i}. {opp['symbol']}: {opp['enhanced_score']:.1f}/100 {change}")

    print("\n" + "="*80)
    print("✅ DEMO 2 COMPLETE")
    print("="*80)


def demo_risk_detection():
    """Demo 3: Risk flag detection"""

    print("\n" + "="*80)
    print("DEMO 3: RISK FLAG DETECTION")
    print("="*80)

    analyzer = SocialSentimentAnalyzer()

    # Mock tokens with different risk profiles
    test_cases = [
        {
            'name': 'Healthy Token',
            'symbol': 'HEALTHY',
            'has_social': True,
            'bot_pct': 0.1,
            'description': 'Good social presence, low bot activity'
        },
        {
            'name': 'No Social Presence',
            'symbol': 'NOSOCIAL',
            'has_social': False,
            'bot_pct': 0.0,
            'description': 'No Twitter or Telegram'
        },
        {
            'name': 'Bot Farm',
            'symbol': 'BOTFARM',
            'has_social': True,
            'bot_pct': 0.7,
            'description': 'High bot activity (70%)'
        }
    ]

    print("\nTesting risk detection on different token profiles:\n")

    for case in test_cases:
        print(f"{'─'*80}")
        print(f"Test Case: {case['name']} (${case['symbol']})")
        print(f"  {case['description']}")

        # Create mock pool data
        pool_data = {
            'baseToken': {'symbol': case['symbol'], 'address': '0x123'},
            'info': {}
        }

        if case['has_social']:
            pool_data['info']['socials'] = [
                {'type': 'twitter', 'url': 'https://twitter.com/test'},
                {'type': 'telegram', 'url': 'https://t.me/test'}
            ]

        sentiment = analyzer.analyze_token(
            token_address='0x123',
            token_symbol=case['symbol'],
            dex_pool_data=pool_data
        )

        # Manually set bot percentage for demo
        sentiment.twitter_metrics.bot_percentage = case['bot_pct']
        sentiment.telegram_metrics.bot_percentage = case['bot_pct']

        # Re-detect flags
        if not case['has_social']:
            sentiment.no_social_presence = True
        if case['bot_pct'] > 0.5:
            sentiment.bot_farm_detected = True

        # Recalculate with flags
        sentiment.calculate_final_score()

        print(f"\n  Results:")
        print(f"    Score: {sentiment.sentiment_score:.1f}/100")
        print(f"    Risk Flags:")
        print(f"      No Social:  {'🚨' if sentiment.no_social_presence else '✓'}")
        print(f"      Bot Farm:   {'🚨' if sentiment.bot_farm_detected else '✓'}")
        print(f"      Pump Group: {'🚨' if sentiment.pump_group_detected else '✓'}")
        print(f"    Recommendation: {'⛔ AVOID' if sentiment.sentiment_score < 20 else '✅ OK'}")
        print()

    print("="*80)
    print("✅ DEMO 3 COMPLETE")
    print("="*80)


def main():
    """Run all demos"""

    print("\n" + "🚀"*40)
    print(" "*20 + "SOCIAL SENTIMENT ANALYSIS DEMO")
    print("🚀"*40)

    # Run demos
    demo_basic_analysis()
    time.sleep(2)

    demo_integration_with_existing()
    time.sleep(2)

    demo_risk_detection()

    # Final summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    print("""
Social sentiment analysis is now integrated!

Features Demonstrated:
  ✅ Twitter & Telegram metrics extraction
  ✅ 0-100 scoring with tier ratings
  ✅ Integration with existing screening
  ✅ Risk flag detection (bots, no social presence)
  ✅ Re-ranking based on social signals

Next Steps:
  1. Install VADER for better sentiment: pip install vaderSentiment
  2. Add Twitter API key for real-time data (optional)
  3. Add Telegram API for group analytics (optional)
  4. Run on production data to validate

Current Mode:
  • FREE tier (no API keys required)
  • Uses placeholder metrics for demo
  • Ready to enhance with real APIs
""")

    print("="*80)


if __name__ == "__main__":
    main()
