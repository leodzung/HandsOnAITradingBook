"""
Demo: Re-ranking Top 4 Tokens with Developer Activity Analysis
================================================================

Takes the top 4 tokens from Strategy 1 and adds developer activity analysis
to create a more comprehensive ranking.

Final Score = 50% Trading Metrics + 50% Developer Activity
"""

from developer_analysis import DeveloperMetrics, DeveloperAnalyzer, format_developer_report
from dataclasses import dataclass
from typing import List


@dataclass
class RankedToken:
    """Token with combined ranking"""
    symbol: str
    trading_score: float  # From Strategy 1 composite score
    developer_score: float  # From developer activity
    final_score: float  # Combined score
    developer_metrics: DeveloperMetrics
    rank: int = 0


def create_developer_profiles():
    """Create mock developer profiles for the 4 tokens"""

    # MOONGEM - Good trading metrics, excellent developer activity
    moongem = DeveloperMetrics(
        token_address="0x0000001d6329f1c35ca4bfab3ad9b84efeedb1a6",
        token_symbol="MOONGEM",
        # GitHub Activity
        github_repo_exists=True,
        github_last_commit_days=2,
        github_total_commits=347,
        github_contributors=8,
        github_stars=156,
        github_forks=42,
        # Team & Transparency
        team_doxxed=True,
        team_size=6,
        team_experience_score=8.5,
        whitepaper_exists=True,
        whitepaper_quality=8.0,
        # Security
        contract_audited=True,
        audit_firm="CertiK",
        known_vulnerabilities=0,
        bug_bounty_program=True,
        # Social & Community
        twitter_followers=8500,
        twitter_engagement_rate=0.045,
        discord_members=2400,
        discord_active_users=320,
        telegram_members=5200,
        # Documentation
        documentation_quality=7.5,
        roadmap_exists=True,
        roadmap_milestones_completed=4,
        roadmap_milestones_total=8,
        last_update_days=3,
        # Website
        website_exists=True,
        website_quality=8.5
    )

    # SAFECOIN - Good trading metrics, moderate developer activity
    safecoin = DeveloperMetrics(
        token_address="0x0000000000000000000000001d2c4b146c0aafc8",
        token_symbol="SAFECOIN",
        # GitHub Activity
        github_repo_exists=True,
        github_last_commit_days=45,
        github_total_commits=128,
        github_contributors=3,
        github_stars=42,
        github_forks=12,
        # Team & Transparency
        team_doxxed=False,  # Anonymous team
        team_size=3,
        team_experience_score=6.0,
        whitepaper_exists=True,
        whitepaper_quality=6.5,
        # Security
        contract_audited=True,
        audit_firm="Hacken",
        known_vulnerabilities=0,
        bug_bounty_program=False,
        # Social & Community
        twitter_followers=1200,
        twitter_engagement_rate=0.028,
        discord_members=800,
        discord_active_users=60,
        telegram_members=2100,
        # Documentation
        documentation_quality=6.0,
        roadmap_exists=True,
        roadmap_milestones_completed=2,
        roadmap_milestones_total=6,
        last_update_days=30,
        # Website
        website_exists=True,
        website_quality=6.5
    )

    # LEGITGEM - Excellent trading metrics, stellar developer activity
    legitgem = DeveloperMetrics(
        token_address="0x00000000000000000000000066ddee66bffde1fb",
        token_symbol="LEGITGEM",
        # GitHub Activity - BEST
        github_repo_exists=True,
        github_last_commit_days=1,
        github_total_commits=842,
        github_contributors=15,
        github_stars=324,
        github_forks=98,
        # Team & Transparency - BEST
        team_doxxed=True,
        team_size=12,
        team_experience_score=9.5,
        whitepaper_exists=True,
        whitepaper_quality=9.5,
        # Security - BEST
        contract_audited=True,
        audit_firm="OpenZeppelin",
        known_vulnerabilities=0,
        bug_bounty_program=True,
        # Social & Community - BEST
        twitter_followers=45000,
        twitter_engagement_rate=0.062,
        discord_members=12000,
        discord_active_users=1800,
        telegram_members=28000,
        # Documentation - BEST
        documentation_quality=9.0,
        roadmap_exists=True,
        roadmap_milestones_completed=7,
        roadmap_milestones_total=10,
        last_update_days=1,
        # Website - BEST
        website_exists=True,
        website_quality=9.5
    )

    # TRENDING - Good trading metrics, poor developer activity (potential red flag)
    trending = DeveloperMetrics(
        token_address="0x000000000000000000000000142487d886bbcac2",
        token_symbol="TRENDING",
        # GitHub Activity - WORST
        github_repo_exists=False,
        github_last_commit_days=999,
        github_total_commits=0,
        github_contributors=0,
        github_stars=0,
        github_forks=0,
        # Team & Transparency - WORST
        team_doxxed=False,
        team_size=1,
        team_experience_score=3.0,
        whitepaper_exists=False,
        whitepaper_quality=0.0,
        # Security - WORST
        contract_audited=False,
        audit_firm=None,
        known_vulnerabilities=2,
        bug_bounty_program=False,
        # Social & Community - MODERATE
        twitter_followers=15000,  # Bought followers?
        twitter_engagement_rate=0.008,  # Very low engagement
        discord_members=500,
        discord_active_users=15,
        telegram_members=8000,  # Many members but low engagement
        # Documentation - WORST
        documentation_quality=2.0,
        roadmap_exists=False,
        roadmap_milestones_completed=0,
        roadmap_milestones_total=0,
        last_update_days=120,
        # Website - POOR
        website_exists=True,
        website_quality=3.0
    )

    return {
        'MOONGEM': moongem,
        'SAFECOIN': safecoin,
        'LEGITGEM': legitgem,
        'TRENDING': trending
    }


def main():
    """Run developer-enhanced ranking"""

    print("\n" + "="*80)
    print("RE-RANKING TOP 4 TOKENS WITH DEVELOPER ACTIVITY ANALYSIS")
    print("="*80)
    print("\nOriginal Strategy 1 Results:")
    print("  #1 MOONGEM   - Composite: 100.0/100")
    print("  #2 SAFECOIN  - Composite: 100.0/100")
    print("  #3 LEGITGEM  - Composite: 100.0/100")
    print("  #4 TRENDING  - Composite: 100.0/100")
    print("\nAll had perfect trading scores - let's differentiate with developer activity!")
    print("="*80)

    # Get developer profiles
    dev_profiles = create_developer_profiles()

    # Original trading scores (from Strategy 1)
    trading_scores = {
        'MOONGEM': 100.0,
        'SAFECOIN': 100.0,
        'LEGITGEM': 100.0,
        'TRENDING': 100.0
    }

    # Calculate developer scores and create ranked tokens
    ranked_tokens: List[RankedToken] = []

    for symbol, metrics in dev_profiles.items():
        dev_score = DeveloperAnalyzer.calculate_activity_score(metrics)
        metrics.activity_score = dev_score

        # Combined score: 50% trading + 50% developer
        final_score = (trading_scores[symbol] * 0.5) + (dev_score * 0.5)

        ranked_token = RankedToken(
            symbol=symbol,
            trading_score=trading_scores[symbol],
            developer_score=dev_score,
            final_score=final_score,
            developer_metrics=metrics
        )
        ranked_tokens.append(ranked_token)

    # Sort by final score
    ranked_tokens.sort(key=lambda x: x.final_score, reverse=True)

    # Assign ranks
    for i, token in enumerate(ranked_tokens, 1):
        token.rank = i

    # Print summary table
    print("\n" + "="*80)
    print("FINAL RANKINGS (Trading 50% + Developer Activity 50%)")
    print("="*80)
    print(f"\n{'Rank':<6} {'Token':<12} {'Trading':<12} {'Developer':<12} {'Final':<12} {'Rating':<12}")
    print("-" * 80)

    for token in ranked_tokens:
        rating = DeveloperAnalyzer.get_activity_rating(token.developer_score)
        print(f"{token.rank:<6} {token.symbol:<12} {token.trading_score:>10.1f} {token.developer_score:>11.1f} {token.final_score:>11.1f} {rating:<12}")

    # Print detailed analysis for each token
    print("\n" + "="*80)
    print("DETAILED DEVELOPER ANALYSIS")
    print("="*80)

    for token in ranked_tokens:
        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣"}.get(token.rank, "")
        print(f"\n{rank_emoji} RANK #{token.rank}: {token.symbol}")
        print("-" * 80)
        print(f"Final Score: {token.final_score:.1f}/100")
        print(f"  • Trading Score:    {token.trading_score:.1f}/100")
        print(f"  • Developer Score:  {token.developer_score:.1f}/100")
        print(f"  • Activity Rating:  {DeveloperAnalyzer.get_activity_rating(token.developer_score)}")

        # Key highlights
        metrics = token.developer_metrics
        print(f"\nKey Highlights:")
        print(f"  • Team: {'✓ Doxxed' if metrics.team_doxxed else '✗ Anonymous'} ({metrics.team_size} members)")
        print(f"  • Audit: {'✓ ' + metrics.audit_firm if metrics.contract_audited else '✗ Not audited'}")
        print(f"  • GitHub: {'✓ Active' if metrics.github_repo_exists else '✗ No repo'} ({metrics.github_total_commits} commits)")
        print(f"  • Community: {metrics.twitter_followers + metrics.telegram_members:,} total followers")
        print(f"  • Last Update: {metrics.last_update_days} days ago")

        # Risk assessment
        assessment = DeveloperAnalyzer.get_risk_assessment(metrics)
        if assessment['risks']:
            print(f"\n⚠️  Risks:")
            for risk_msg in assessment['risks'].values():
                print(f"  • {risk_msg}")

    # Print full reports
    print("\n\n" + "#"*80)
    print("# COMPREHENSIVE DEVELOPER REPORTS")
    print("#"*80)

    for token in ranked_tokens:
        print(format_developer_report(token.developer_metrics))

    # Final recommendation
    print("\n" + "="*80)
    print("INVESTMENT RECOMMENDATION")
    print("="*80)

    winner = ranked_tokens[0]
    loser = ranked_tokens[-1]

    print(f"\n🏆 TOP PICK: {winner.symbol}")
    print(f"   Final Score: {winner.final_score:.1f}/100")
    print(f"   Why: Perfect trading metrics + {DeveloperAnalyzer.get_activity_rating(winner.developer_score)} developer activity")
    print(f"   Risk Level: LOW")
    print(f"   Recommended Action: STRONG BUY")

    print(f"\n⚠️  AVOID: {loser.symbol}")
    print(f"   Final Score: {loser.final_score:.1f}/100")
    print(f"   Why: Despite good price action, {DeveloperAnalyzer.get_activity_rating(loser.developer_score)} developer activity indicates high risk")
    print(f"   Risk Level: HIGH")
    print(f"   Recommended Action: AVOID - Potential pump & dump")

    print(f"\n💡 KEY INSIGHT:")
    print(f"   {winner.symbol} and {loser.symbol} both had perfect 100/100 trading scores,")
    print(f"   but developer analysis reveals {winner.symbol} is legitimate while {loser.symbol} may be a scam.")
    print(f"   This demonstrates why developer activity analysis is CRITICAL for early tokens!")

    print("\n" + "="*80)


if __name__ == "__main__":
    main()
