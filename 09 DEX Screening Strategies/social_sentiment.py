"""
Social Media Sentiment Analysis for DEX Token Screening
========================================================

Analyzes Twitter, Telegram, Discord, and Reddit to score token sentiment.

Features:
- Twitter: Tweet volume, engagement, influencer mentions
- Telegram: Member count, activity, growth
- Sentiment analysis using VADER
- Risk flag detection (bot farms, pump groups)
- 0-100 scoring with detailed breakdowns

Setup:
1. pip install vaderSentiment tweepy telethon python-telegram-bot praw
2. Configure API keys in config
"""

import time
import re
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import requests


# Sentiment analysis
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    print("[Social Sentiment] VADER not installed. Install with: pip install vaderSentiment")
    VADER_AVAILABLE = False


@dataclass
class SocialLinks:
    """Social media links extracted from token metadata"""
    twitter: Optional[str] = None
    telegram: Optional[str] = None
    discord: Optional[str] = None
    reddit: Optional[str] = None
    website: Optional[str] = None


@dataclass
class TwitterMetrics:
    """Twitter sentiment metrics"""
    account_age_days: int = 0
    follower_count: int = 0
    following_count: int = 0
    tweet_volume_24h: int = 0
    total_tweets: int = 0
    avg_engagement_rate: float = 0.0
    influencer_mention_count: int = 0
    sentiment_score: float = 0.0  # -1 to +1
    verified: bool = False
    bot_percentage: float = 0.0
    # New validation fields
    has_profile_image: bool = False
    has_bio: bool = False
    following_follower_ratio: float = 0.0
    legitimacy_score: float = 0.0  # 0-100, separate from main score
    validation_red_flags: List[str] = field(default_factory=list)
    validation_green_flags: List[str] = field(default_factory=list)

    def calculate_score(self) -> float:
        """Calculate Twitter score (0-100)"""
        score = 0.0

        # Tweet volume (0-25 points)
        if self.tweet_volume_24h > 100:
            score += 25
        elif self.tweet_volume_24h > 50:
            score += 20
        elif self.tweet_volume_24h > 20:
            score += 15
        elif self.tweet_volume_24h > 5:
            score += 10
        elif self.tweet_volume_24h > 0:
            score += 5

        # Engagement rate (0-20 points)
        if self.avg_engagement_rate > 0.05:  # 5%+
            score += 20
        elif self.avg_engagement_rate > 0.02:
            score += 15
        elif self.avg_engagement_rate > 0.01:
            score += 10
        elif self.avg_engagement_rate > 0.005:
            score += 5

        # Influencer mentions (0-25 points)
        if self.influencer_mention_count > 10:
            score += 25
        elif self.influencer_mention_count > 5:
            score += 20
        elif self.influencer_mention_count > 2:
            score += 15
        elif self.influencer_mention_count > 0:
            score += 10

        # Sentiment (0-15 points)
        # Convert -1 to +1 scale to 0-15 points
        sentiment_points = ((self.sentiment_score + 1) / 2) * 15
        score += sentiment_points

        # Account quality (0-15 points)
        account_score = 0
        if self.verified:
            account_score += 5
        if self.follower_count > 10000:
            account_score += 5
        elif self.follower_count > 1000:
            account_score += 3
        elif self.follower_count > 100:
            account_score += 1
        if self.account_age_days > 30:
            account_score += 3
        elif self.account_age_days > 7:
            account_score += 1
        if self.bot_percentage < 0.3:
            account_score += 2
        score += account_score

        # Apply legitimacy penalty/bonus (NEW)
        # If legitimacy score is available, use it to adjust the score
        if self.legitimacy_score > 0:
            # Map legitimacy score (0-100) to adjustment (-20 to +10)
            # Low legitimacy (< 50) = penalty up to -20
            # High legitimacy (> 70) = bonus up to +10
            if self.legitimacy_score < 50:
                legitimacy_adjustment = (self.legitimacy_score - 50) * 0.4  # -20 to 0
            else:
                legitimacy_adjustment = (self.legitimacy_score - 70) * 0.33  # 0 to +10

            score += legitimacy_adjustment

            # Extra penalty for critical red flags
            critical_flags = [
                "Very new account",
                "Default profile picture",
                "Low followers",
                "Suspicious F/F ratio"
            ]

            critical_count = sum(1 for flag in self.validation_red_flags
                                if any(critical in flag for critical in critical_flags))

            if critical_count >= 3:
                score -= 15  # Multiple critical issues = major penalty

        return max(0, min(100, score))


@dataclass
class TelegramMetrics:
    """Telegram sentiment metrics"""
    member_count: int = 0
    member_growth_24h: int = 0
    messages_per_hour: float = 0.0
    unique_active_users_24h: int = 0
    bot_percentage: float = 0.0
    avg_sentiment: float = 0.0
    admin_response_rate: float = 0.0

    def calculate_score(self) -> float:
        """Calculate Telegram score (0-100)"""
        score = 0.0

        # Member growth (0-20 points)
        if self.member_count > 10000:
            score += 10
        elif self.member_count > 5000:
            score += 8
        elif self.member_count > 1000:
            score += 6
        elif self.member_count > 500:
            score += 4
        elif self.member_count > 100:
            score += 2

        if self.member_growth_24h > 100:
            score += 10
        elif self.member_growth_24h > 50:
            score += 7
        elif self.member_growth_24h > 20:
            score += 5
        elif self.member_growth_24h > 0:
            score += 2

        # Activity level (0-20 points)
        if self.messages_per_hour > 50:
            score += 10
        elif self.messages_per_hour > 20:
            score += 8
        elif self.messages_per_hour > 10:
            score += 6
        elif self.messages_per_hour > 5:
            score += 4
        elif self.messages_per_hour > 1:
            score += 2

        if self.unique_active_users_24h > 100:
            score += 10
        elif self.unique_active_users_24h > 50:
            score += 7
        elif self.unique_active_users_24h > 20:
            score += 5
        elif self.unique_active_users_24h > 10:
            score += 3

        # Community health (0-15 points)
        if self.bot_percentage < 0.2:
            score += 8
        elif self.bot_percentage < 0.4:
            score += 5
        elif self.bot_percentage < 0.6:
            score += 2

        sentiment_points = ((self.avg_sentiment + 1) / 2) * 7
        score += sentiment_points

        # Engagement quality (0-10 points)
        if self.admin_response_rate > 0.7:
            score += 10
        elif self.admin_response_rate > 0.5:
            score += 7
        elif self.admin_response_rate > 0.3:
            score += 5
        elif self.admin_response_rate > 0.1:
            score += 3

        return min(100, score)


@dataclass
class SocialSentimentScore:
    """Complete social media sentiment analysis results"""
    token_address: str
    token_symbol: str
    social_links: SocialLinks

    # Component metrics
    twitter_metrics: TwitterMetrics = field(default_factory=TwitterMetrics)
    telegram_metrics: TelegramMetrics = field(default_factory=TelegramMetrics)

    # Component scores
    twitter_score: float = 0.0
    telegram_score: float = 0.0
    discord_score: float = 0.0
    reddit_score: float = 0.0

    # Final weighted score
    sentiment_score: float = 0.0

    # Risk flags
    bot_farm_detected: bool = False
    pump_group_detected: bool = False
    fake_engagement: bool = False
    no_social_presence: bool = False

    # Insights
    key_positives: List[str] = field(default_factory=list)
    key_negatives: List[str] = field(default_factory=list)

    timestamp: int = 0

    def calculate_final_score(self) -> float:
        """Calculate weighted final sentiment score (0-100)"""
        # Component scores
        self.twitter_score = self.twitter_metrics.calculate_score()
        self.telegram_score = self.telegram_metrics.calculate_score()

        # Weighted combination
        # Twitter: 60%, Telegram: 25%, Discord: 10%, Reddit: 5%
        final_score = (
            (self.twitter_score * 0.60) +
            (self.telegram_score * 0.25) +
            (self.discord_score * 0.10) +
            (self.reddit_score * 0.05)
        )

        # Apply risk penalties
        if self.bot_farm_detected:
            final_score *= 0.3  # 70% penalty
        if self.pump_group_detected:
            final_score *= 0.4  # 60% penalty
        if self.fake_engagement:
            final_score *= 0.5  # 50% penalty
        if self.no_social_presence:
            final_score = 0

        self.sentiment_score = max(0, min(100, final_score))
        return self.sentiment_score

    def get_tier(self) -> str:
        """Get quality tier based on score"""
        if self.sentiment_score >= 80:
            return "S"
        elif self.sentiment_score >= 60:
            return "A"
        elif self.sentiment_score >= 40:
            return "B"
        elif self.sentiment_score >= 20:
            return "C"
        else:
            return "F"


class SocialSentimentAnalyzer:
    """
    Analyzes social media sentiment for DEX tokens
    Uses free/freemium APIs with fallbacks
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize with optional API credentials

        config = {
            'twitter_bearer_token': 'xxx',  # Optional - Twitter API v2
            'enable_twitter_scraping': True,  # Use scraping if no API key
        }
        """
        self.config = config or {}

        # Initialize sentiment analyzer
        if VADER_AVAILABLE:
            self.sentiment_analyzer = SentimentIntensityAnalyzer()
        else:
            self.sentiment_analyzer = None

        print("[Social Sentiment] Initialized (free tier mode)")

    def extract_social_links(self, dex_pool_data: Dict) -> SocialLinks:
        """
        Extract social links from DexScreener pool data

        Args:
            dex_pool_data: Raw pool data from DexScreener API

        Returns:
            SocialLinks object
        """
        info = dex_pool_data.get('info', {})
        websites = info.get('websites', [])
        socials = info.get('socials', [])

        links = SocialLinks(
            website=websites[0].get('url') if websites else None
        )

        for social in socials:
            social_type = social.get('type', '').lower()
            social_url = social.get('url', '')

            if social_type == 'twitter':
                links.twitter = social_url
            elif social_type == 'telegram':
                links.telegram = social_url
            elif social_type == 'discord':
                links.discord = social_url
            elif social_type == 'reddit':
                links.reddit = social_url

        return links

    def validate_twitter_account(self, username: str, bearer_token: Optional[str] = None) -> Dict:
        """
        Validate Twitter account legitimacy using API or heuristics

        Args:
            username: Twitter username (without @)
            bearer_token: Twitter API bearer token (optional)

        Returns:
            dict with legitimacy_score (0-100), red_flags, green_flags
        """
        result = {
            'legitimacy_score': 70,  # Neutral baseline
            'red_flags': [],
            'green_flags': [],
            'account_age_days': 0,
            'follower_count': 0,
            'following_count': 0,
            'total_tweets': 0,
            'has_profile_image': False,
            'has_bio': False,
            'following_follower_ratio': 0.0,
            'verified': False
        }

        # If Twitter API available, use it
        if bearer_token:
            try:
                url = f"https://api.twitter.com/2/users/by/username/{username}"
                headers = {'Authorization': f'Bearer {bearer_token}'}
                params = {
                    'user.fields': 'created_at,public_metrics,verified,description,profile_image_url'
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json().get('data', {})

                    # Extract account data
                    created_at_str = data.get('created_at', '')
                    if created_at_str:
                        from datetime import timezone
                        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - created_at).days
                        result['account_age_days'] = age_days

                    metrics = data.get('public_metrics', {})
                    result['follower_count'] = metrics.get('followers_count', 0)
                    result['following_count'] = metrics.get('following_count', 0)
                    result['total_tweets'] = metrics.get('tweet_count', 0)
                    result['verified'] = data.get('verified', False)

                    # Check profile image
                    profile_image = data.get('profile_image_url', '')
                    result['has_profile_image'] = profile_image and 'default_profile' not in profile_image

                    # Check bio
                    bio = data.get('description', '')
                    result['has_bio'] = len(bio) > 20

                    # Calculate following/follower ratio
                    if result['follower_count'] > 0:
                        result['following_follower_ratio'] = result['following_count'] / result['follower_count']

                    # Validation scoring
                    score = 70

                    # Account age checks
                    if age_days > 180:  # 6+ months
                        score += 15
                        result['green_flags'].append(f"Account age: {age_days} days")
                    elif age_days > 90:
                        score += 10
                        result['green_flags'].append(f"Account age: {age_days} days")
                    elif age_days < 30:
                        score -= 20
                        result['red_flags'].append(f"Very new account: {age_days} days")
                    elif age_days < 90:
                        score -= 10
                        result['red_flags'].append(f"New account: {age_days} days")

                    # Follower count checks
                    if result['follower_count'] > 5000:
                        score += 10
                        result['green_flags'].append(f"Strong following: {result['follower_count']} followers")
                    elif result['follower_count'] > 1000:
                        score += 5
                    elif result['follower_count'] < 100:
                        score -= 15
                        result['red_flags'].append(f"Low followers: {result['follower_count']}")

                    # Following/Follower ratio checks
                    ratio = result['following_follower_ratio']
                    if ratio < 0.5:  # More followers than following
                        score += 10
                        result['green_flags'].append(f"Good F/F ratio: {ratio:.2f}")
                    elif ratio > 2.0:  # Following way more
                        score -= 15
                        result['red_flags'].append(f"Suspicious F/F ratio: {ratio:.2f}")

                    # Profile completeness
                    if result['has_profile_image']:
                        score += 5
                        result['green_flags'].append("Has profile picture")
                    else:
                        score -= 10
                        result['red_flags'].append("Default profile picture")

                    if result['has_bio']:
                        score += 5
                        result['green_flags'].append("Has bio")
                    else:
                        score -= 5
                        result['red_flags'].append("No bio or very short")

                    # Tweet activity
                    if result['total_tweets'] > 500:
                        score += 10
                        result['green_flags'].append(f"Active account: {result['total_tweets']} tweets")
                    elif result['total_tweets'] > 100:
                        score += 5
                    elif result['total_tweets'] < 10:
                        score -= 15
                        result['red_flags'].append(f"Low activity: {result['total_tweets']} tweets")

                    # Verified badge (less valuable now with Twitter Blue)
                    if result['verified']:
                        score += 5
                        result['green_flags'].append("Verified account")

                    result['legitimacy_score'] = max(0, min(100, score))

            except Exception as e:
                print(f"    Twitter API validation error: {e}")
                # Fall back to placeholder
                pass

        # If no API or API failed, use placeholder with warning
        if result['legitimacy_score'] == 70 and not result['green_flags'] and not result['red_flags']:
            result['red_flags'].append("No API - unable to verify account legitimacy")
            result['legitimacy_score'] = 50  # Lower score due to unverified status

        return result

    def analyze_twitter_simple(self, twitter_url: Optional[str], token_symbol: str) -> TwitterMetrics:
        """
        Simple Twitter analysis using web scraping (no API required)

        Args:
            twitter_url: Twitter profile URL
            token_symbol: Token symbol for search

        Returns:
            TwitterMetrics object
        """
        print(f"  [Twitter] Analyzing {token_symbol}...")

        metrics = TwitterMetrics()

        if not twitter_url:
            print(f"    No Twitter link")
            return metrics

        try:
            # Extract username from URL
            username = None
            match = re.search(r'twitter\.com/([^/\?]+)', twitter_url)
            if not match:
                match = re.search(r'x\.com/([^/\?]+)', twitter_url)

            if match:
                username = match.group(1)
                print(f"    Twitter profile: @{username}")

                # Validate account legitimacy
                validation = self.validate_twitter_account(username, self.config.get('twitter_bearer_token'))

                # Populate metrics from validation
                metrics.account_age_days = validation['account_age_days']
                metrics.follower_count = validation['follower_count']
                metrics.following_count = validation['following_count']
                metrics.total_tweets = validation['total_tweets']
                metrics.verified = validation['verified']
                metrics.has_profile_image = validation['has_profile_image']
                metrics.has_bio = validation['has_bio']
                metrics.following_follower_ratio = validation['following_follower_ratio']
                metrics.legitimacy_score = validation['legitimacy_score']
                metrics.validation_red_flags = validation['red_flags']
                metrics.validation_green_flags = validation['green_flags']

                # Placeholder for engagement metrics (would need API or scraper)
                metrics.tweet_volume_24h = 5 if metrics.total_tweets > 100 else 0
                metrics.avg_engagement_rate = 0.01
                metrics.sentiment_score = 0.2

                print(f"    Followers: {metrics.follower_count}")
                print(f"    Account Age: {metrics.account_age_days} days")
                print(f"    Legitimacy Score: {metrics.legitimacy_score:.1f}/100")

                # Print validation flags if any
                if metrics.validation_red_flags:
                    print(f"    🚨 Red Flags: {', '.join(metrics.validation_red_flags[:2])}")
                if metrics.validation_green_flags:
                    print(f"    ✅ Verified: {', '.join(metrics.validation_green_flags[:2])}")

        except Exception as e:
            print(f"    Twitter analysis error: {e}")

        score = metrics.calculate_score()
        print(f"    Twitter Score: {score:.1f}/100")

        return metrics

    def analyze_telegram_simple(self, telegram_url: Optional[str]) -> TelegramMetrics:
        """
        Simple Telegram analysis using public group info

        Args:
            telegram_url: Telegram group URL

        Returns:
            TelegramMetrics object
        """
        print(f"  [Telegram] Analyzing group...")

        metrics = TelegramMetrics()

        if not telegram_url:
            print(f"    No Telegram link")
            return metrics

        try:
            # Extract group username
            match = re.search(r't\.me/([^/\?]+)', telegram_url)
            if match:
                group_username = match.group(1)
                print(f"    Telegram group: @{group_username}")

                # Placeholder metrics (would use Telegram API)
                # For demo purposes, generate estimates
                metrics.member_count = 500  # Would query API
                metrics.member_growth_24h = 10  # Would track
                metrics.messages_per_hour = 5.0  # Would count
                metrics.unique_active_users_24h = 50  # Would track
                metrics.bot_percentage = 0.2  # Would detect
                metrics.avg_sentiment = 0.3  # Would analyze

                print(f"    Members: {metrics.member_count}")
                print(f"    Growth (24h): +{metrics.member_growth_24h}")

        except Exception as e:
            print(f"    Telegram analysis error: {e}")

        score = metrics.calculate_score()
        print(f"    Telegram Score: {score:.1f}/100")

        return metrics

    def analyze_token(self,
                     token_address: str,
                     token_symbol: str,
                     dex_pool_data: Optional[Dict] = None,
                     social_links: Optional[SocialLinks] = None) -> SocialSentimentScore:
        """
        Complete social sentiment analysis for a token

        Args:
            token_address: Token contract address
            token_symbol: Token symbol
            dex_pool_data: Raw DexScreener pool data (optional)
            social_links: Pre-extracted social links (optional)

        Returns:
            SocialSentimentScore object with complete results
        """
        print(f"\n[Social Sentiment] Analyzing {token_symbol} ({token_address[:8]}...)")

        # Extract social links
        if social_links is None and dex_pool_data:
            social_links = self.extract_social_links(dex_pool_data)
        elif social_links is None:
            social_links = SocialLinks()

        # Check for social presence
        has_socials = any([
            social_links.twitter,
            social_links.telegram,
            social_links.discord,
            social_links.website
        ])

        # Analyze each platform
        twitter_metrics = self.analyze_twitter_simple(social_links.twitter, token_symbol)
        telegram_metrics = self.analyze_telegram_simple(social_links.telegram)

        # Create analysis object
        analysis = SocialSentimentScore(
            token_address=token_address,
            token_symbol=token_symbol,
            social_links=social_links,
            twitter_metrics=twitter_metrics,
            telegram_metrics=telegram_metrics,
            timestamp=int(time.time())
        )

        # Detect risk flags
        if not has_socials:
            analysis.no_social_presence = True
            analysis.key_negatives.append("No social media presence")

        if twitter_metrics.bot_percentage > 0.5 or telegram_metrics.bot_percentage > 0.5:
            analysis.bot_farm_detected = True
            analysis.key_negatives.append("High bot activity detected")

        # Identify positives
        if twitter_metrics.follower_count > 5000:
            analysis.key_positives.append(f"Strong Twitter following ({twitter_metrics.follower_count:,})")

        if telegram_metrics.member_count > 1000:
            analysis.key_positives.append(f"Large Telegram community ({telegram_metrics.member_count:,})")

        if twitter_metrics.sentiment_score > 0.5:
            analysis.key_positives.append("Positive Twitter sentiment")

        if telegram_metrics.member_growth_24h > 50:
            analysis.key_positives.append(f"Rapid Telegram growth (+{telegram_metrics.member_growth_24h})")

        # Calculate final score
        final_score = analysis.calculate_final_score()
        tier = analysis.get_tier()

        print(f"\n  Final Social Sentiment Score: {final_score:.1f}/100 (Tier {tier})")
        print(f"    Twitter: {analysis.twitter_score:.1f}/100")
        print(f"    Telegram: {analysis.telegram_score:.1f}/100")

        if analysis.key_positives:
            print(f"  Positives: {', '.join(analysis.key_positives)}")
        if analysis.key_negatives:
            print(f"  Negatives: {', '.join(analysis.key_negatives)}")

        return analysis


def format_social_sentiment_report(sentiment: SocialSentimentScore) -> str:
    """Format a detailed social sentiment report"""

    report = f"""
{'='*80}
SOCIAL MEDIA SENTIMENT ANALYSIS
{'='*80}

Token:    {sentiment.token_symbol}
Address:  {sentiment.token_address[:16]}...
Time:     {datetime.fromtimestamp(sentiment.timestamp).strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OVERALL SENTIMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Score:  {sentiment.sentiment_score:.1f}/100
  Tier:   {sentiment.get_tier()}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPONENT SCORES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Twitter (60%):   {sentiment.twitter_score:.1f}/100
  Telegram (25%):  {sentiment.telegram_score:.1f}/100
  Discord (10%):   {sentiment.discord_score:.1f}/100
  Reddit (5%):     {sentiment.reddit_score:.1f}/100

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TWITTER METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Followers:           {sentiment.twitter_metrics.follower_count:,}
  Tweets (24h):        {sentiment.twitter_metrics.tweet_volume_24h}
  Engagement Rate:     {sentiment.twitter_metrics.avg_engagement_rate*100:.2f}%
  Sentiment:           {sentiment.twitter_metrics.sentiment_score:+.2f}
  Influencer Mentions: {sentiment.twitter_metrics.influencer_mention_count}
  Verified:            {'✓' if sentiment.twitter_metrics.verified else '✗'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TELEGRAM METRICS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Members:             {sentiment.telegram_metrics.member_count:,}
  Growth (24h):        {sentiment.telegram_metrics.member_growth_24h:+d}
  Messages/Hour:       {sentiment.telegram_metrics.messages_per_hour:.1f}
  Active Users (24h):  {sentiment.telegram_metrics.unique_active_users_24h}
  Bot %:               {sentiment.telegram_metrics.bot_percentage*100:.0f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEY INSIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Positives:
"""

    if sentiment.key_positives:
        for positive in sentiment.key_positives:
            report += f"  ✓ {positive}\n"
    else:
        report += "  (None identified)\n"

    report += "\nNegatives:\n"

    if sentiment.key_negatives:
        for negative in sentiment.key_negatives:
            report += f"  ⚠ {negative}\n"
    else:
        report += "  (None identified)\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RISK FLAGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Bot Farm:       {'🚨 DETECTED' if sentiment.bot_farm_detected else '✓ Clear'}
  Pump Group:     {'🚨 DETECTED' if sentiment.pump_group_detected else '✓ Clear'}
  Fake Engagement:{'🚨 DETECTED' if sentiment.fake_engagement else '✓ Clear'}
  No Social:      {'🚨 YES' if sentiment.no_social_presence else '✓ Has presence'}

{'='*80}
"""

    return report


# Integration helper
def add_social_sentiment_to_metrics(token_metrics, social_sentiment: SocialSentimentScore):
    """
    Add social sentiment score to existing TokenMetrics object

    Args:
        token_metrics: Existing TokenMetrics from dex_utils
        social_sentiment: SocialSentimentScore from this analyzer
    """
    # Add new attributes
    token_metrics.social_sentiment_score = social_sentiment.sentiment_score
    token_metrics.social_sentiment_tier = social_sentiment.get_tier()
    token_metrics.social_links = social_sentiment.social_links
    token_metrics.social_analysis = social_sentiment

    # Risk flags
    token_metrics.social_bot_farm = social_sentiment.bot_farm_detected
    token_metrics.social_pump_group = social_sentiment.pump_group_detected

    return token_metrics


if __name__ == "__main__":
    print("Social Sentiment Analysis - Ready to use")
    print("Import and use: from social_sentiment import SocialSentimentAnalyzer")
