"""
Demo: News Sentiment Analysis Integration
==========================================

Shows how to integrate news sentiment analysis with existing DEX screening strategies.

This demo:
1. Runs existing pool scanner to find tokens
2. Applies news sentiment analysis to top candidates
3. Re-ranks tokens with combined scores
4. Generates comparison report

Usage:
    python demo_news_sentiment.py

    # With API keys (for production)
    export CRYPTOPANIC_KEY="your_key"
    export NEWSAPI_KEY="your_key"
    export GITHUB_TOKEN="your_token"
    python demo_news_sentiment.py
"""

import os
from datetime import datetime
from typing import List, Dict
from dataclasses import dataclass

from news_sentiment import NewsSentimentAnalyzer, format_news_report
from dex_utils import RiskAnalyzer


# ============================================================================
# MOCK DATA (for demo when APIs not available)
# ============================================================================

MOCK_TOKENS = [
    {
        'symbol': 'BASEDOG',
        'address': '0x1234567890abcdef1234567890abcdef12345678',
        'chain': 'base',
        'base_score': 78.5,
        'safety_score': 72.0,
        'opportunity_score': 85.0,
        'liquidity_usd': 125000,
        'volume_24h': 89000,
        'social_links': {
            'github': 'https://github.com/example/basedog',
            'medium': '@basedog',
            'website': 'https://basedog.com'
        }
    },
    {
        'symbol': 'ETHGEM',
        'address': '0xabcdef1234567890abcdef1234567890abcdef12',
        'chain': 'ethereum',
        'base_score': 82.3,
        'safety_score': 88.0,
        'opportunity_score': 76.5,
        'liquidity_usd': 245000,
        'volume_24h': 156000,
        'social_links': {
            'github': 'https://github.com/example/ethgem',
            'website': 'https://ethgem.io'
        }
    },
    {
        'symbol': 'BSCMOON',
        'address': '0x567890abcdef1234567890abcdef1234567890ab',
        'chain': 'bsc',
        'base_score': 65.8,
        'safety_score': 62.0,
        'opportunity_score': 69.5,
        'liquidity_usd': 67000,
        'volume_24h': 45000,
        'social_links': {
            'website': 'https://bscmoon.finance'
        }
    },
    {
        'symbol': 'DEFI2',
        'address': '0x234567890abcdef1234567890abcdef12345678ab',
        'chain': 'ethereum',
        'base_score': 74.2,
        'safety_score': 79.0,
        'opportunity_score': 69.0,
        'liquidity_usd': 189000,
        'volume_24h': 112000,
        'social_links': {
            'github': 'https://github.com/example/defi2',
            'medium': '@defi2protocol',
            'website': 'https://defi2.org'
        }
    },
    {
        'symbol': 'REKT',
        'address': '0x890abcdef1234567890abcdef1234567890abcdef',
        'chain': 'base',
        'base_score': 45.3,
        'safety_score': 38.0,
        'opportunity_score': 52.5,
        'liquidity_usd': 34000,
        'volume_24h': 18000,
        'social_links': {}
    }
]


@dataclass
class EnhancedOpportunity:
    """Token opportunity with news sentiment"""
    symbol: str
    address: str
    chain: str

    # Original scores
    base_score: float
    safety_score: float
    opportunity_score: float

    # News sentiment
    news_score: float
    news_boost: float

    # Final score
    final_score: float

    # Metadata
    liquidity_usd: float
    volume_24h: float
    has_news_coverage: bool
    major_catalysts: List[str]


# ============================================================================
# MAIN ANALYSIS FUNCTIONS
# ============================================================================

def run_enhanced_analysis(use_mock_data=True):
    """
    Run complete analysis with news sentiment
    """
    print("\n" + "="*80)
    print("DEX TOKEN SCREENING WITH NEWS SENTIMENT ANALYSIS")
    print("="*80)

    # Initialize news analyzer
    news_analyzer = NewsSentimentAnalyzer(
        cryptopanic_key=os.getenv('CRYPTOPANIC_KEY'),
        newsapi_key=os.getenv('NEWSAPI_KEY'),
        github_token=os.getenv('GITHUB_TOKEN')
    )

    has_api_keys = any([
        os.getenv('CRYPTOPANIC_KEY'),
        os.getenv('NEWSAPI_KEY'),
        os.getenv('GITHUB_TOKEN')
    ])

    if not has_api_keys:
        print("\n⚠️  Running in DEMO MODE (no API keys detected)")
        print("Set environment variables for full functionality:")
        print("  - CRYPTOPANIC_KEY")
        print("  - NEWSAPI_KEY")
        print("  - GITHUB_TOKEN")
    else:
        print("\n✓ API keys detected - running with live data")

    # Step 1: Get base tokens (mock or real)
    if use_mock_data:
        print("\n" + "-"*80)
        print("STEP 1: Loading mock token data")
        print("-"*80)
        tokens = MOCK_TOKENS
        print(f"Loaded {len(tokens)} mock tokens")
    else:
        print("\n" + "-"*80)
        print("STEP 1: Running pool scanner")
        print("-"*80)
        # In production, would run actual pool scanner
        # from strategy1_pool_scanner import PoolScannerStrategy
        # scanner = PoolScannerStrategy(...)
        # opportunities = scanner.run(max_cycles=1)
        tokens = MOCK_TOKENS  # Fallback

    # Step 2: Analyze top candidates with news sentiment
    print("\n" + "-"*80)
    print("STEP 2: Analyzing news sentiment for top candidates")
    print("-"*80)

    enhanced_opportunities = []

    for i, token in enumerate(tokens, 1):
        print(f"\n[{i}/{len(tokens)}] Analyzing {token['symbol']}...")

        # Get news sentiment
        try:
            news_metrics = news_analyzer.analyze_token(
                token_address=token['address'],
                token_symbol=token['symbol'],
                social_links=token.get('social_links', {})
            )

            # Calculate news boost
            news_score = news_metrics.total_score
            news_boost = calculate_news_boost(news_metrics)

            # Calculate final score (weighted combination)
            base_score = token['base_score']
            final_score = calculate_final_score(base_score, news_score, news_boost)

            print(f"  Base Score: {base_score:.1f}")
            print(f"  News Score: {news_score:.1f}")
            print(f"  News Boost: {news_boost:+.1f}")
            print(f"  Final Score: {final_score:.1f}")
            print(f"  News Coverage: {news_metrics.total_news_items} articles")

            if news_metrics.major_catalysts:
                print(f"  Catalysts: {', '.join(news_metrics.major_catalysts)}")

            enhanced_opportunities.append(EnhancedOpportunity(
                symbol=token['symbol'],
                address=token['address'],
                chain=token['chain'],
                base_score=base_score,
                safety_score=token['safety_score'],
                opportunity_score=token['opportunity_score'],
                news_score=news_score,
                news_boost=news_boost,
                final_score=final_score,
                liquidity_usd=token['liquidity_usd'],
                volume_24h=token['volume_24h'],
                has_news_coverage=news_metrics.total_news_items > 0,
                major_catalysts=news_metrics.major_catalysts
            ))

        except Exception as e:
            print(f"  Error analyzing {token['symbol']}: {e}")
            # Add without news sentiment
            enhanced_opportunities.append(EnhancedOpportunity(
                symbol=token['symbol'],
                address=token['address'],
                chain=token['chain'],
                base_score=token['base_score'],
                safety_score=token['safety_score'],
                opportunity_score=token['opportunity_score'],
                news_score=0,
                news_boost=0,
                final_score=token['base_score'],
                liquidity_usd=token['liquidity_usd'],
                volume_24h=token['volume_24h'],
                has_news_coverage=False,
                major_catalysts=[]
            ))

    # Step 3: Re-rank by final score
    print("\n" + "-"*80)
    print("STEP 3: Re-ranking tokens with news sentiment")
    print("-"*80)

    enhanced_opportunities.sort(key=lambda x: x.final_score, reverse=True)

    # Step 4: Print comprehensive report
    print_comparison_report(enhanced_opportunities)

    return enhanced_opportunities


def calculate_news_boost(news_metrics) -> float:
    """
    Calculate news boost/penalty based on sentiment metrics

    Returns boost value: -20 to +30
    """
    boost = 0.0

    # Base news score contribution (up to +20)
    boost += (news_metrics.total_score / 100) * 20

    # Catalyst bonuses
    if 'audit' in news_metrics.major_catalysts:
        boost += 5  # Audit completion is huge

    if 'partnership' in news_metrics.major_catalysts:
        boost += 5  # Major partnership

    if 'funding' in news_metrics.major_catalysts:
        boost += 3  # Funding round

    # Negative news penalty
    if news_metrics.negative_news_count > 2:
        boost -= 10

    if news_metrics.negative_news_count > 5:
        boost -= 10  # Additional penalty

    # No news coverage penalty
    if news_metrics.total_news_items == 0:
        boost -= 5  # Lack of coverage is suspicious for "hot" tokens

    return max(-20, min(30, boost))


def calculate_final_score(base_score: float, news_score: float, news_boost: float) -> float:
    """
    Calculate final combined score

    Strategy: 70% base + 30% news influence
    """
    # Apply boost to opportunity score
    enhanced_score = base_score + news_boost

    # Weighted combination
    final = (base_score * 0.7) + (enhanced_score * 0.3)

    return min(100, max(0, final))


def print_comparison_report(opportunities: List[EnhancedOpportunity]):
    """
    Print comprehensive comparison report
    """
    print("\n" + "="*80)
    print("ENHANCED OPPORTUNITY RANKING (Base + News Sentiment)")
    print("="*80)

    # Summary statistics
    total = len(opportunities)
    with_news = sum(1 for o in opportunities if o.has_news_coverage)
    with_catalysts = sum(1 for o in opportunities if o.major_catalysts)
    avg_boost = sum(o.news_boost for o in opportunities) / max(total, 1)

    print(f"\nSUMMARY:")
    print(f"  Total Tokens:           {total}")
    print(f"  With News Coverage:     {with_news} ({with_news/total*100:.1f}%)")
    print(f"  With Major Catalysts:   {with_catalysts} ({with_catalysts/total*100:.1f}%)")
    print(f"  Avg News Boost:         {avg_boost:+.1f} points")

    print("\n" + "-"*80)
    print("TOP OPPORTUNITIES:")
    print("-"*80)

    for i, opp in enumerate(opportunities, 1):
        print(f"\n#{i} {opp.symbol} ({opp.chain.upper()})")
        print("   " + "─"*70)
        print(f"   Final Score:      {opp.final_score:.1f}/100  {'🔥' if opp.final_score >= 80 else '✓' if opp.final_score >= 70 else ''}")
        print(f"   Base Score:       {opp.base_score:.1f}/100")
        print(f"   News Score:       {opp.news_score:.1f}/100")
        print(f"   News Boost:       {opp.news_boost:+.1f} points")
        print(f"   Liquidity:        ${opp.liquidity_usd:,.0f}")
        print(f"   24h Volume:       ${opp.volume_24h:,.0f}")

        if opp.major_catalysts:
            catalysts_str = ', '.join([c.upper() for c in opp.major_catalysts])
            print(f"   Catalysts:        {catalysts_str}")

        if not opp.has_news_coverage:
            print(f"   ⚠️  No news coverage detected")

        # Risk assessment
        risk_level = "LOW" if opp.safety_score >= 75 else "MEDIUM" if opp.safety_score >= 60 else "HIGH"
        print(f"   Risk Level:       {risk_level}")

    print("\n" + "="*80)
    print("SCORE CHANGES (Before → After News Sentiment)")
    print("="*80)

    for i, opp in enumerate(opportunities, 1):
        change = opp.final_score - opp.base_score
        arrow = "⬆️" if change > 5 else "⬇️" if change < -5 else "→"
        print(f"  {i}. {opp.symbol:10s} {arrow}  {opp.base_score:.1f} → {opp.final_score:.1f}  ({change:+.1f})")

    print("\n" + "="*80)
    print("RECOMMENDATION:")
    print("="*80)

    top_3 = opportunities[:3]

    print(f"\n  🎯 TOP 3 OPPORTUNITIES:\n")
    for i, opp in enumerate(top_3, 1):
        print(f"     {i}. {opp.symbol} - Score: {opp.final_score:.1f}/100")

        if opp.major_catalysts:
            print(f"        Reason: {', '.join(opp.major_catalysts)}")
        else:
            print(f"        Reason: Strong fundamentals")

    print(f"\n  ⚠️  AVOID:\n")
    risky = [o for o in opportunities if o.safety_score < 50 or o.news_boost < -10]
    if risky:
        for opp in risky:
            reason = "Low safety score" if opp.safety_score < 50 else "Negative news"
            print(f"     • {opp.symbol} - {reason}")
    else:
        print(f"     None - all tokens meet minimum criteria")

    print("\n" + "="*80)
    print(f"Analysis completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


# ============================================================================
# DETAILED TOKEN ANALYSIS
# ============================================================================

def analyze_single_token_detailed(token_symbol: str):
    """
    Detailed analysis of a single token with full news report
    """
    print("\n" + "="*80)
    print(f"DETAILED ANALYSIS: {token_symbol}")
    print("="*80)

    # Initialize analyzer
    news_analyzer = NewsSentimentAnalyzer(
        cryptopanic_key=os.getenv('CRYPTOPANIC_KEY'),
        newsapi_key=os.getenv('NEWSAPI_KEY'),
        github_token=os.getenv('GITHUB_TOKEN')
    )

    # Find token in mock data
    token = next((t for t in MOCK_TOKENS if t['symbol'] == token_symbol), None)

    if not token:
        print(f"Token {token_symbol} not found in data")
        return

    # Run analysis
    news_metrics = news_analyzer.analyze_token(
        token_address=token['address'],
        token_symbol=token['symbol'],
        social_links=token.get('social_links', {})
    )

    # Print full report
    print(format_news_report(news_metrics))

    # Additional insights
    print("\n" + "="*80)
    print("TRADING RECOMMENDATION")
    print("="*80)

    final_score = calculate_final_score(
        token['base_score'],
        news_metrics.total_score,
        calculate_news_boost(news_metrics)
    )

    if final_score >= 80:
        recommendation = "STRONG BUY"
        reasoning = "Excellent fundamentals + positive news sentiment"
    elif final_score >= 70:
        recommendation = "BUY"
        reasoning = "Good fundamentals with supporting news"
    elif final_score >= 60:
        recommendation = "HOLD/WATCH"
        reasoning = "Moderate opportunity, monitor for improvements"
    elif final_score >= 50:
        recommendation = "CAUTION"
        reasoning = "Weak signals, high risk"
    else:
        recommendation = "AVOID"
        reasoning = "Poor fundamentals and/or negative news"

    print(f"\n  Recommendation: {recommendation}")
    print(f"  Reasoning: {reasoning}")
    print(f"  Final Score: {final_score:.1f}/100")

    if news_metrics.major_catalysts:
        print(f"\n  Positive Catalysts:")
        for catalyst in news_metrics.major_catalysts:
            print(f"    ✓ {catalyst.replace('_', ' ').title()}")

    if news_metrics.concerns:
        print(f"\n  Concerns:")
        for concern in news_metrics.concerns:
            print(f"    ⚠️ {concern}")

    print("\n" + "="*80 + "\n")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    """Main demo execution"""

    import argparse

    parser = argparse.ArgumentParser(description='News Sentiment Analysis Demo')
    parser.add_argument('--token', type=str, help='Analyze specific token in detail')
    parser.add_argument('--live', action='store_true', help='Use live data (requires API keys)')

    args = parser.parse_args()

    if args.token:
        # Single token detailed analysis
        analyze_single_token_detailed(args.token)
    else:
        # Full comparison analysis
        use_mock = not args.live
        run_enhanced_analysis(use_mock_data=use_mock)


if __name__ == "__main__":
    main()
