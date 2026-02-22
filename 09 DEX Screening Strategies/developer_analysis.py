"""
Developer Activity Analysis Module
===================================

Analyzes developer activity and commitment for token projects.
Helps identify legitimate projects with active development vs. abandoned or scam projects.

Key Metrics:
- GitHub activity (commits, contributors, last update)
- Smart contract audit status
- Team transparency (doxxed vs anonymous)
- Social media presence and engagement
- Documentation quality
- Roadmap and delivery track record
- Community activity
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import time


@dataclass
class DeveloperMetrics:
    """Developer activity metrics for a token project"""
    token_address: str
    token_symbol: str

    # GitHub Activity
    github_repo_exists: bool
    github_last_commit_days: int  # Days since last commit
    github_total_commits: int
    github_contributors: int
    github_stars: int
    github_forks: int

    # Team & Transparency
    team_doxxed: bool  # Publicly known team members
    team_size: int
    team_experience_score: float  # 0-10 based on background
    whitepaper_exists: bool
    whitepaper_quality: float  # 0-10 rating

    # Security
    contract_audited: bool
    audit_firm: Optional[str]
    known_vulnerabilities: int
    bug_bounty_program: bool

    # Social & Community
    twitter_followers: int
    twitter_engagement_rate: float  # 0-1
    discord_members: int
    discord_active_users: int
    telegram_members: int

    # Documentation & Communication
    documentation_quality: float  # 0-10
    roadmap_exists: bool
    roadmap_milestones_completed: int
    roadmap_milestones_total: int
    last_update_days: int  # Days since last project update

    # Website & Infrastructure
    website_exists: bool
    website_quality: float  # 0-10

    # Development Activity Score (calculated)
    activity_score: float = 0.0  # 0-100


class DeveloperAnalyzer:
    """Analyzes developer activity and project health"""

    @staticmethod
    def calculate_activity_score(metrics: DeveloperMetrics) -> float:
        """
        Calculate comprehensive developer activity score (0-100)

        Weighting:
        - 30% GitHub Activity
        - 25% Team & Transparency
        - 20% Security & Audits
        - 15% Community Engagement
        - 10% Documentation
        """

        score = 0.0

        # 1. GitHub Activity (30 points max)
        github_score = 0.0

        if metrics.github_repo_exists:
            github_score += 5

            # Recent activity (up to 10 points)
            if metrics.github_last_commit_days <= 7:
                github_score += 10
            elif metrics.github_last_commit_days <= 30:
                github_score += 7
            elif metrics.github_last_commit_days <= 90:
                github_score += 4
            elif metrics.github_last_commit_days <= 180:
                github_score += 2

            # Commit volume (up to 7 points)
            if metrics.github_total_commits >= 500:
                github_score += 7
            elif metrics.github_total_commits >= 200:
                github_score += 5
            elif metrics.github_total_commits >= 50:
                github_score += 3
            elif metrics.github_total_commits >= 10:
                github_score += 1

            # Contributors (up to 5 points)
            if metrics.github_contributors >= 10:
                github_score += 5
            elif metrics.github_contributors >= 5:
                github_score += 3
            elif metrics.github_contributors >= 2:
                github_score += 2
            elif metrics.github_contributors >= 1:
                github_score += 1

            # Community interest (up to 3 points)
            if metrics.github_stars >= 100:
                github_score += 3
            elif metrics.github_stars >= 50:
                github_score += 2
            elif metrics.github_stars >= 10:
                github_score += 1

        score += min(30, github_score)

        # 2. Team & Transparency (25 points max)
        team_score = 0.0

        if metrics.team_doxxed:
            team_score += 10  # Huge trust factor

        # Team size (up to 5 points)
        if metrics.team_size >= 10:
            team_score += 5
        elif metrics.team_size >= 5:
            team_score += 3
        elif metrics.team_size >= 2:
            team_score += 2
        elif metrics.team_size >= 1:
            team_score += 1

        # Team experience (up to 5 points)
        team_score += (metrics.team_experience_score / 10) * 5

        # Whitepaper (up to 5 points)
        if metrics.whitepaper_exists:
            team_score += 2
            team_score += (metrics.whitepaper_quality / 10) * 3

        score += min(25, team_score)

        # 3. Security & Audits (20 points max)
        security_score = 0.0

        if metrics.contract_audited:
            security_score += 10

            # Reputable audit firm
            reputable_firms = ['CertiK', 'PeckShield', 'SlowMist', 'Hacken', 'OpenZeppelin']
            if metrics.audit_firm and any(firm in metrics.audit_firm for firm in reputable_firms):
                security_score += 5

        # No known vulnerabilities
        if metrics.known_vulnerabilities == 0:
            security_score += 3

        # Bug bounty program
        if metrics.bug_bounty_program:
            security_score += 2

        score += min(20, security_score)

        # 4. Community Engagement (15 points max)
        community_score = 0.0

        # Twitter presence (up to 5 points)
        if metrics.twitter_followers >= 10000:
            community_score += 3
        elif metrics.twitter_followers >= 1000:
            community_score += 2
        elif metrics.twitter_followers >= 100:
            community_score += 1

        if metrics.twitter_engagement_rate >= 0.05:
            community_score += 2
        elif metrics.twitter_engagement_rate >= 0.02:
            community_score += 1

        # Discord activity (up to 5 points)
        if metrics.discord_members >= 5000:
            community_score += 2
        elif metrics.discord_members >= 1000:
            community_score += 1

        if metrics.discord_members > 0:
            activity_ratio = metrics.discord_active_users / metrics.discord_members
            if activity_ratio >= 0.1:
                community_score += 3
            elif activity_ratio >= 0.05:
                community_score += 2
            elif activity_ratio >= 0.02:
                community_score += 1

        # Telegram (up to 5 points)
        if metrics.telegram_members >= 10000:
            community_score += 5
        elif metrics.telegram_members >= 5000:
            community_score += 3
        elif metrics.telegram_members >= 1000:
            community_score += 2
        elif metrics.telegram_members >= 100:
            community_score += 1

        score += min(15, community_score)

        # 5. Documentation (10 points max)
        docs_score = 0.0

        # Website (up to 3 points)
        if metrics.website_exists:
            docs_score += 1
            docs_score += (metrics.website_quality / 10) * 2

        # Documentation quality (up to 3 points)
        docs_score += (metrics.documentation_quality / 10) * 3

        # Roadmap (up to 4 points)
        if metrics.roadmap_exists:
            docs_score += 1
            if metrics.roadmap_milestones_total > 0:
                completion_rate = metrics.roadmap_milestones_completed / metrics.roadmap_milestones_total
                docs_score += completion_rate * 3

        score += min(10, docs_score)

        return min(100, score)

    @staticmethod
    def get_activity_rating(score: float) -> str:
        """Convert activity score to rating"""
        if score >= 80:
            return "EXCELLENT"
        elif score >= 65:
            return "GOOD"
        elif score >= 50:
            return "MODERATE"
        elif score >= 30:
            return "LOW"
        else:
            return "VERY LOW"

    @staticmethod
    def get_risk_assessment(metrics: DeveloperMetrics) -> Dict[str, str]:
        """Get risk assessment based on developer metrics"""
        risks = {}

        # Critical risks
        if not metrics.team_doxxed:
            risks['team'] = "⚠️ Anonymous team - higher rug pull risk"

        if not metrics.contract_audited:
            risks['security'] = "⚠️ No audit - potential vulnerabilities"

        if not metrics.github_repo_exists:
            risks['transparency'] = "⚠️ No GitHub - can't verify code"

        if metrics.github_last_commit_days > 180:
            risks['abandonment'] = "⚠️ Project may be abandoned (no recent commits)"

        if metrics.last_update_days > 90:
            risks['communication'] = "⚠️ No recent updates - poor communication"

        # Positive factors
        positives = {}

        if metrics.team_doxxed:
            positives['team'] = "✓ Doxxed team - lower rug pull risk"

        if metrics.contract_audited:
            positives['security'] = f"✓ Audited by {metrics.audit_firm or 'professional firm'}"

        if metrics.github_last_commit_days <= 7:
            positives['activity'] = "✓ Active development (recent commits)"

        if metrics.bug_bounty_program:
            positives['security'] = "✓ Bug bounty program active"

        return {'risks': risks, 'positives': positives}


def format_developer_report(metrics: DeveloperMetrics) -> str:
    """Format a detailed developer activity report"""

    score = DeveloperAnalyzer.calculate_activity_score(metrics)
    rating = DeveloperAnalyzer.get_activity_rating(score)
    assessment = DeveloperAnalyzer.get_risk_assessment(metrics)

    report = f"""
{'='*80}
DEVELOPER ACTIVITY REPORT: {metrics.token_symbol}
{'='*80}

OVERALL SCORE: {score:.1f}/100 ({rating})

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GITHUB ACTIVITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Repository Exists:     {'✓' if metrics.github_repo_exists else '✗'}
  Last Commit:           {metrics.github_last_commit_days} days ago
  Total Commits:         {metrics.github_total_commits}
  Contributors:          {metrics.github_contributors}
  Stars:                 {metrics.github_stars}
  Forks:                 {metrics.github_forks}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEAM & TRANSPARENCY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Team Doxxed:           {'✓ YES' if metrics.team_doxxed else '✗ NO (Anonymous)'}
  Team Size:             {metrics.team_size} member(s)
  Experience Score:      {metrics.team_experience_score:.1f}/10
  Whitepaper:            {'✓' if metrics.whitepaper_exists else '✗'}
  Whitepaper Quality:    {metrics.whitepaper_quality:.1f}/10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY & AUDITS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Contract Audited:      {'✓ YES' if metrics.contract_audited else '✗ NO'}
  Audit Firm:            {metrics.audit_firm or 'N/A'}
  Known Vulnerabilities: {metrics.known_vulnerabilities}
  Bug Bounty Program:    {'✓' if metrics.bug_bounty_program else '✗'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMUNITY ENGAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Twitter Followers:     {metrics.twitter_followers:,}
  Twitter Engagement:    {metrics.twitter_engagement_rate*100:.1f}%
  Discord Members:       {metrics.discord_members:,} ({metrics.discord_active_users:,} active)
  Telegram Members:      {metrics.telegram_members:,}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENTATION & ROADMAP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Website:               {'✓' if metrics.website_exists else '✗'}
  Website Quality:       {metrics.website_quality:.1f}/10
  Documentation:         {metrics.documentation_quality:.1f}/10
  Roadmap:               {'✓' if metrics.roadmap_exists else '✗'}
  Milestones:            {metrics.roadmap_milestones_completed}/{metrics.roadmap_milestones_total} completed
  Last Update:           {metrics.last_update_days} days ago

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RISK ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    if assessment['risks']:
        report += "\n⚠️  RISKS IDENTIFIED:\n"
        for risk_type, message in assessment['risks'].items():
            report += f"  • {message}\n"
    else:
        report += "\n✓ No major risks identified\n"

    if assessment['positives']:
        report += "\n✓ POSITIVE FACTORS:\n"
        for pos_type, message in assessment['positives'].items():
            report += f"  • {message}\n"

    report += f"\n{'='*80}\n"

    return report
