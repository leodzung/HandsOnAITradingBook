"""
News & Announcement Sentiment Analysis Module
==============================================

Analyzes official project news, announcements, and media coverage
to score early-stage DEX tokens based on sentiment and catalysts.

Focus: News articles, press releases, GitHub activity, audit reports
NOT: Social media chatter (Twitter, Telegram, Discord)

Usage:
    analyzer = NewsSentimentAnalyzer(
        cryptopanic_key='YOUR_KEY',
        newsapi_key='YOUR_KEY',
        github_token='YOUR_TOKEN'
    )

    metrics = analyzer.analyze_token(
        token_address='0x123...',
        token_symbol='TOKEN',
        social_links={'github': 'https://github.com/...'}
    )

    print(f"News Sentiment Score: {metrics.total_score}/100")
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
import time
import requests
import feedparser
from bs4 import BeautifulSoup
import json
import re


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class NewsItem:
    """Individual news article or announcement"""
    title: str
    content: str
    source: str
    url: str
    published_date: datetime
    sentiment_score: float = 0.0  # -1 to 1
    sentiment_label: str = 'neutral'  # positive, negative, neutral
    announcement_type: str = 'general'
    media_tier: str = 'tier_3'


@dataclass
class NewsSentimentMetrics:
    """News sentiment analysis results"""
    token_address: str
    token_symbol: str

    # Overall score
    total_score: float  # 0-100

    # Component scores
    sentiment_score: float  # 0-40
    velocity_score: float  # 0-25
    github_score: float  # 0-20
    catalyst_score: float  # 0-15

    # Supporting data
    total_news_items: int
    recent_news_24h: int
    recent_news_7d: int
    recent_news_30d: int

    # Key findings
    top_announcements: List[Dict] = field(default_factory=list)
    major_catalysts: List[str] = field(default_factory=list)

    # GitHub metrics
    has_github: bool = False
    github_commits_30d: int = 0
    github_last_commit_days: int = 999

    # Security
    is_audited: bool = False
    audit_firm: Optional[str] = None

    # Risk factors
    negative_news_count: int = 0
    concerns: List[str] = field(default_factory=list)

    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)


# ============================================================================
# CONFIGURATION
# ============================================================================

ANNOUNCEMENT_TYPES = {
    'partnership': {
        'weight': 20,
        'keywords': ['partner', 'collaboration', 'collaborate', 'integrate', 'integration with']
    },
    'product_launch': {
        'weight': 25,
        'keywords': ['launch', 'release', 'introducing', 'announced', 'unveil', 'mainnet']
    },
    'audit_completion': {
        'weight': 30,
        'keywords': ['audit', 'security review', 'certified', 'audited by', 'passed audit']
    },
    'funding_round': {
        'weight': 25,
        'keywords': ['raised', 'funding', 'investment', 'series a', 'series b', 'seed round']
    },
    'exchange_listing': {
        'weight': 15,
        'keywords': ['listed', 'listing on', 'available on', 'trading on', 'now on']
    },
    'milestone': {
        'weight': 10,
        'keywords': ['milestone', 'achieved', 'reached', 'surpassed', 'hit']
    },
    'team_expansion': {
        'weight': 8,
        'keywords': ['hired', 'joined', 'appointed', 'cto', 'ceo', 'cfo', 'new hire']
    },
    'technical_update': {
        'weight': 12,
        'keywords': ['upgrade', 'improved', 'optimized', 'v2', 'v3', 'version', 'update']
    }
}

MEDIA_TIERS = {
    'tier_1': {
        'sources': [
            'coindesk.com', 'cointelegraph.com', 'theblock.co', 'decrypt.co',
            'bloomberg.com', 'reuters.com', 'wsj.com'
        ],
        'weight': 3.0
    },
    'tier_2': {
        'sources': [
            'coinjournal.net', 'cryptonews.com', 'newsbtc.com', 'bitcoinist.com',
            'cryptoslate.com', 'beincrypto.com'
        ],
        'weight': 2.0
    },
    'tier_3': {
        'sources': [
            'medium.com', 'mirror.xyz', 'substack.com', 'hackernoon.com'
        ],
        'weight': 1.0
    }
}

TIER_1_PARTNERS = [
    'binance', 'coinbase', 'uniswap', 'chainlink', 'polygon', 'arbitrum',
    'optimism', 'base', 'avalanche', 'solana', 'ethereum', 'bnb chain'
]

REPUTABLE_AUDITORS = [
    'certik', 'peckshield', 'slowmist', 'hacken', 'openzeppelin',
    'trail of bits', 'consensys diligence', 'quantstamp'
]


# ============================================================================
# SENTIMENT ANALYZER (FinBERT-based)
# ============================================================================

class SimpleSentimentAnalyzer:
    """
    Simple keyword-based sentiment analyzer
    For production, replace with FinBERT or GPT-4o-mini
    """

    POSITIVE_KEYWORDS = [
        'partnership', 'launch', 'success', 'growth', 'innovative', 'revolutionary',
        'secure', 'audit', 'certified', 'raised', 'funding', 'milestone',
        'achieved', 'improved', 'optimized', 'breakthrough', 'excited'
    ]

    NEGATIVE_KEYWORDS = [
        'hack', 'exploit', 'vulnerability', 'scam', 'fraud', 'delayed',
        'postponed', 'failed', 'issue', 'bug', 'concern', 'warning',
        'investigation', 'lawsuit', 'regulatory'
    ]

    def analyze(self, text: str) -> Dict:
        """
        Analyze sentiment of text

        Returns:
            {
                'label': 'positive'|'negative'|'neutral',
                'score': -1 to 1,
                'confidence': 0 to 1
            }
        """
        text_lower = text.lower()

        positive_count = sum(1 for word in self.POSITIVE_KEYWORDS if word in text_lower)
        negative_count = sum(1 for word in self.NEGATIVE_KEYWORDS if word in text_lower)

        # Calculate score (-1 to 1)
        if positive_count + negative_count == 0:
            return {'label': 'neutral', 'score': 0.0, 'confidence': 0.3}

        score = (positive_count - negative_count) / (positive_count + negative_count)

        if score > 0.3:
            label = 'positive'
        elif score < -0.3:
            label = 'negative'
        else:
            label = 'neutral'

        confidence = min(0.9, 0.5 + abs(score) * 0.4)

        return {
            'label': label,
            'score': score,
            'confidence': confidence
        }


# ============================================================================
# NEWS DATA FETCHERS
# ============================================================================

class NewsDataFetcher:
    """Fetches news from various sources"""

    def __init__(self, cryptopanic_key=None, newsapi_key=None):
        self.cryptopanic_key = cryptopanic_key
        self.newsapi_key = newsapi_key
        self.session = requests.Session()
        self.last_api_calls = {}

    def _rate_limit(self, api_name: str, min_interval: float):
        """Simple rate limiting"""
        last_call = self.last_api_calls.get(api_name, 0)
        elapsed = time.time() - last_call

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self.last_api_calls[api_name] = time.time()

    def fetch_cryptopanic(self, token_symbol: str, limit=20) -> List[NewsItem]:
        """
        Fetch news from CryptoPanic API
        Free tier: 20 req/min
        """
        if not self.cryptopanic_key:
            return []

        self._rate_limit('cryptopanic', 3.0)  # 20/min = 3sec interval

        url = "https://cryptopanic.com/api/v1/posts/"
        params = {
            'auth_token': self.cryptopanic_key,
            'currencies': token_symbol.upper(),
            'kind': 'news',
            'filter': 'rising',
            'public': 'true'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news_items = []

                for post in data.get('results', [])[:limit]:
                    news_items.append(NewsItem(
                        title=post.get('title', ''),
                        content=post.get('title', ''),  # CryptoPanic doesn't provide full content
                        source=post.get('domain', 'cryptopanic.com'),
                        url=post.get('url', ''),
                        published_date=datetime.fromisoformat(post.get('published_at', '').replace('Z', '+00:00'))
                    ))

                return news_items

        except Exception as e:
            print(f"[CryptoPanic] Error: {e}")

        return []

    def fetch_newsapi(self, query: str, from_date: datetime, limit=20) -> List[NewsItem]:
        """
        Fetch from NewsAPI.org
        Free: 1000 requests/day
        """
        if not self.newsapi_key:
            return []

        self._rate_limit('newsapi', 1.0)

        url = "https://newsapi.org/v2/everything"
        params = {
            'apiKey': self.newsapi_key,
            'q': query,
            'from': from_date.strftime('%Y-%m-%d'),
            'language': 'en',
            'sortBy': 'publishedAt',
            'domains': 'coindesk.com,cointelegraph.com,decrypt.co,theblock.co',
            'pageSize': limit
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news_items = []

                for article in data.get('articles', []):
                    news_items.append(NewsItem(
                        title=article.get('title', ''),
                        content=article.get('description', '') + ' ' + article.get('content', ''),
                        source=article.get('source', {}).get('name', ''),
                        url=article.get('url', ''),
                        published_date=datetime.fromisoformat(article.get('publishedAt', '').replace('Z', '+00:00'))
                    ))

                return news_items

        except Exception as e:
            print(f"[NewsAPI] Error: {e}")

        return []

    def fetch_medium_rss(self, username_or_publication: str) -> List[NewsItem]:
        """
        Fetch Medium posts via RSS
        Free, no API key needed
        """
        feed_url = f"https://medium.com/feed/@{username_or_publication}"

        try:
            feed = feedparser.parse(feed_url)
            news_items = []

            for entry in feed.entries[:20]:
                # Parse published date
                published = datetime.now()
                if hasattr(entry, 'published_parsed'):
                    published = datetime(*entry.published_parsed[:6])

                # Extract text from HTML content
                content = ''
                if hasattr(entry, 'content'):
                    soup = BeautifulSoup(entry.content[0].value, 'html.parser')
                    content = soup.get_text()[:5000]

                news_items.append(NewsItem(
                    title=entry.title,
                    content=content,
                    source='medium.com',
                    url=entry.link,
                    published_date=published
                ))

            return news_items

        except Exception as e:
            print(f"[Medium RSS] Error: {e}")

        return []


class GitHubAnalyzer:
    """Analyzes GitHub repository activity"""

    def __init__(self, github_token=None):
        self.github_token = github_token
        self.session = requests.Session()
        if github_token:
            self.session.headers.update({'Authorization': f'token {github_token}'})

    def analyze_repo(self, repo_url: str) -> Optional[Dict]:
        """
        Analyze GitHub repository activity

        Returns:
            {
                'recent_commits': int,
                'last_commit_days': int,
                'releases': List[Dict],
                'contributors': int,
                'stars': int,
                'forks': int
            }
        """
        # Extract owner/repo from URL
        match = re.search(r'github\.com/([^/]+)/([^/]+)', repo_url)
        if not match:
            return None

        owner, repo = match.groups()
        repo = repo.replace('.git', '')

        try:
            # Get repository info
            repo_url = f"https://api.github.com/repos/{owner}/{repo}"
            response = self.session.get(repo_url, timeout=10)

            if response.status_code != 200:
                return None

            repo_data = response.json()

            # Get recent commits (last 30 days)
            since_date = (datetime.now() - timedelta(days=30)).isoformat()
            commits_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            commits_response = self.session.get(
                commits_url,
                params={'since': since_date, 'per_page': 100},
                timeout=10
            )

            recent_commits = 0
            last_commit_days = 999

            if commits_response.status_code == 200:
                commits = commits_response.json()
                recent_commits = len(commits)

                if commits:
                    last_commit_date = datetime.fromisoformat(
                        commits[0]['commit']['author']['date'].replace('Z', '+00:00')
                    )
                    last_commit_days = (datetime.now(last_commit_date.tzinfo) - last_commit_date).days

            # Get releases
            releases_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
            releases_response = self.session.get(releases_url, params={'per_page': 5}, timeout=10)

            releases = []
            if releases_response.status_code == 200:
                for release in releases_response.json():
                    releases.append({
                        'tag': release.get('tag_name', ''),
                        'name': release.get('name', ''),
                        'date': datetime.fromisoformat(release.get('published_at', '').replace('Z', '+00:00')),
                        'body': release.get('body', '')[:500]
                    })

            return {
                'recent_commits': recent_commits,
                'last_commit_days': last_commit_days,
                'releases': releases,
                'contributors': repo_data.get('contributors_url', '').count('/') > 0,  # Simplified
                'stars': repo_data.get('stargazers_count', 0),
                'forks': repo_data.get('forks_count', 0)
            }

        except Exception as e:
            print(f"[GitHub] Error analyzing {owner}/{repo}: {e}")

        return None


# ============================================================================
# MAIN ANALYZER
# ============================================================================

class NewsSentimentAnalyzer:
    """
    Main news sentiment analyzer
    """

    def __init__(self,
                 cryptopanic_key: Optional[str] = None,
                 newsapi_key: Optional[str] = None,
                 github_token: Optional[str] = None,
                 use_simple_sentiment: bool = True):

        self.news_fetcher = NewsDataFetcher(cryptopanic_key, newsapi_key)
        self.github_analyzer = GitHubAnalyzer(github_token)

        # Sentiment analyzer (use simple by default, can replace with FinBERT)
        self.sentiment_analyzer = SimpleSentimentAnalyzer()

    def analyze_token(self,
                     token_address: str,
                     token_symbol: str,
                     social_links: Optional[Dict] = None) -> NewsSentimentMetrics:
        """
        Complete news sentiment analysis for a token

        Args:
            token_address: Contract address
            token_symbol: Token symbol (e.g., 'ETH')
            social_links: {
                'github': 'https://github.com/...',
                'medium': '@username',
                'website': 'https://...'
            }

        Returns:
            NewsSentimentMetrics
        """
        print(f"[NewsSentiment] Analyzing {token_symbol}...")

        social_links = social_links or {}

        # 1. Aggregate news from all sources
        news_items = self._aggregate_news(token_symbol, social_links)
        print(f"  Found {len(news_items)} news items")

        # 2. Analyze GitHub activity
        github_activity = None
        if social_links.get('github'):
            github_activity = self.github_analyzer.analyze_repo(social_links['github'])
            if github_activity:
                print(f"  GitHub: {github_activity['recent_commits']} commits (30d)")

        # 3. Run sentiment analysis on all news
        for item in news_items:
            sentiment = self.sentiment_analyzer.analyze(item.title + ' ' + item.content)
            item.sentiment_score = sentiment['score']
            item.sentiment_label = sentiment['label']
            item.announcement_type = self._classify_announcement(item.title + ' ' + item.content)
            item.media_tier = self._get_media_tier(item.source)

        # 4. Check for audits
        audit_info = self._check_audit_mentions(news_items)

        # 5. Calculate scores
        scores = self._calculate_scores(news_items, github_activity, audit_info)

        # 6. Extract key insights
        top_announcements = self._get_top_announcements(news_items)
        catalysts = self._extract_catalysts(news_items, audit_info)
        concerns = self._extract_concerns(news_items)

        # 7. Build metrics
        now = datetime.now()

        metrics = NewsSentimentMetrics(
            token_address=token_address,
            token_symbol=token_symbol,
            total_score=scores['total'],
            sentiment_score=scores['sentiment'],
            velocity_score=scores['velocity'],
            github_score=scores['github'],
            catalyst_score=scores['catalyst'],
            total_news_items=len(news_items),
            recent_news_24h=sum(1 for item in news_items if (now - item.published_date).days < 1),
            recent_news_7d=sum(1 for item in news_items if (now - item.published_date).days < 7),
            recent_news_30d=sum(1 for item in news_items if (now - item.published_date).days < 30),
            top_announcements=top_announcements,
            major_catalysts=catalysts,
            has_github=github_activity is not None,
            github_commits_30d=github_activity['recent_commits'] if github_activity else 0,
            github_last_commit_days=github_activity['last_commit_days'] if github_activity else 999,
            is_audited=audit_info['is_audited'],
            audit_firm=audit_info.get('firm'),
            negative_news_count=sum(1 for item in news_items if item.sentiment_label == 'negative'),
            concerns=concerns,
            analyzed_at=datetime.now()
        )

        return metrics

    def _aggregate_news(self, token_symbol: str, social_links: Dict) -> List[NewsItem]:
        """Gather news from all available sources"""
        news_items = []

        # CryptoPanic
        cp_news = self.news_fetcher.fetch_cryptopanic(token_symbol)
        news_items.extend(cp_news)

        # NewsAPI
        from_date = datetime.now() - timedelta(days=30)
        na_news = self.news_fetcher.fetch_newsapi(token_symbol, from_date)
        news_items.extend(na_news)

        # Medium
        if social_links.get('medium'):
            medium_posts = self.news_fetcher.fetch_medium_rss(social_links['medium'])
            news_items.extend(medium_posts)

        # Deduplicate by URL
        seen_urls = set()
        unique_news = []
        for item in news_items:
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                unique_news.append(item)

        # Sort by date (newest first)
        unique_news.sort(key=lambda x: x.published_date, reverse=True)

        return unique_news

    def _classify_announcement(self, text: str) -> str:
        """Classify announcement type based on keywords"""
        text_lower = text.lower()

        scores = {}
        for ann_type, config in ANNOUNCEMENT_TYPES.items():
            score = sum(1 for keyword in config['keywords'] if keyword in text_lower)
            if score > 0:
                scores[ann_type] = score

        if not scores:
            return 'general'

        return max(scores, key=scores.get)

    def _get_media_tier(self, source: str) -> str:
        """Determine media tier based on source"""
        source_lower = source.lower()

        for tier_name, tier_config in MEDIA_TIERS.items():
            if any(domain in source_lower for domain in tier_config['sources']):
                return tier_name

        return 'tier_3'

    def _check_audit_mentions(self, news_items: List[NewsItem]) -> Dict:
        """Check for audit completion mentions"""
        for item in news_items:
            text_lower = (item.title + ' ' + item.content).lower()

            if any(word in text_lower for word in ['audit', 'audited', 'security review']):
                # Check for reputable auditors
                for auditor in REPUTABLE_AUDITORS:
                    if auditor in text_lower:
                        return {'is_audited': True, 'firm': auditor.title()}

                # Generic audit mention
                return {'is_audited': True, 'firm': 'Unknown'}

        return {'is_audited': False}

    def _calculate_scores(self, news_items: List[NewsItem],
                         github_activity: Optional[Dict],
                         audit_info: Dict) -> Dict:
        """Calculate all component scores"""

        # 1. Sentiment Score (0-40)
        sentiment_score = self._calculate_sentiment_score(news_items)

        # 2. Velocity Score (0-25)
        velocity_score = self._calculate_velocity_score(news_items)

        # 3. GitHub Score (0-20)
        github_score = self._calculate_github_score(github_activity)

        # 4. Catalyst Score (0-15)
        catalyst_score = self._calculate_catalyst_score(news_items, audit_info)

        total = sentiment_score + velocity_score + github_score + catalyst_score

        return {
            'total': min(100, total),
            'sentiment': sentiment_score,
            'velocity': velocity_score,
            'github': github_score,
            'catalyst': catalyst_score
        }

    def _calculate_sentiment_score(self, news_items: List[NewsItem]) -> float:
        """Calculate weighted sentiment score (0-40)"""
        if not news_items:
            return 0.0

        weighted_sentiment = 0
        total_weight = 0

        for item in news_items:
            type_weight = ANNOUNCEMENT_TYPES.get(item.announcement_type, {}).get('weight', 5)
            tier_weight = MEDIA_TIERS.get(item.media_tier, {}).get('weight', 1.0)

            weighted_sentiment += item.sentiment_score * type_weight * tier_weight
            total_weight += type_weight * tier_weight

        if total_weight == 0:
            return 0.0

        # Normalize to 0-40 range
        score = (weighted_sentiment / total_weight) * 40
        score = max(0, min(40, score + 20))  # Shift range from -40-40 to 0-40

        return score

    def _calculate_velocity_score(self, news_items: List[NewsItem]) -> float:
        """Calculate news velocity score (0-25)"""
        now = datetime.now()

        last_24h = sum(1 for item in news_items if (now - item.published_date).days < 1)
        last_7d = sum(1 for item in news_items if (now - item.published_date).days < 7)
        last_30d = sum(1 for item in news_items if (now - item.published_date).days < 30)

        score = 0.0

        # Recency bonus (up to 10 points)
        score += min(10, last_24h * 3)

        # Weekly frequency (up to 10 points)
        if last_7d >= 5:
            score += 10
        elif last_7d >= 3:
            score += 7
        elif last_7d >= 1:
            score += 4

        # Monthly trend (up to 5 points)
        if last_30d >= 10:
            score += 5
        elif last_30d >= 5:
            score += 3
        elif last_30d >= 2:
            score += 1

        return min(25, score)

    def _calculate_github_score(self, github_activity: Optional[Dict]) -> float:
        """Calculate GitHub activity score (0-20)"""
        if not github_activity:
            return 0.0

        score = 0.0

        # Commit frequency (up to 8 points)
        commits = github_activity.get('recent_commits', 0)
        if commits >= 100:
            score += 8
        elif commits >= 50:
            score += 6
        elif commits >= 20:
            score += 4
        elif commits >= 5:
            score += 2

        # Recent release (up to 7 points)
        releases = github_activity.get('releases', [])
        if releases:
            latest_release = releases[0]
            days_since_release = (datetime.now() - latest_release['date']).days

            if days_since_release <= 7:
                score += 7
            elif days_since_release <= 30:
                score += 5
            elif days_since_release <= 90:
                score += 3

        # Community engagement (up to 5 points)
        stars = github_activity.get('stars', 0)
        if stars >= 500:
            score += 5
        elif stars >= 100:
            score += 3
        elif stars >= 50:
            score += 2
        elif stars >= 10:
            score += 1

        return min(20, score)

    def _calculate_catalyst_score(self, news_items: List[NewsItem], audit_info: Dict) -> float:
        """Calculate major catalyst score (0-15)"""
        score = 0.0
        catalysts_found: Set[str] = set()

        # Audit completion (5 points)
        if audit_info.get('is_audited'):
            score += 5
            catalysts_found.add('audit')

        for item in news_items:
            content_lower = (item.title + ' ' + item.content).lower()

            # Major partnership (4 points)
            if 'partnership' not in catalysts_found:
                if any(word in content_lower for word in ['partnership', 'collaborate', 'integrate']):
                    if any(partner in content_lower for partner in TIER_1_PARTNERS):
                        score += 4
                        catalysts_found.add('partnership')

            # Funding round (4 points)
            if 'funding' not in catalysts_found:
                if any(word in content_lower for word in ['raised', 'funding', 'investment']):
                    score += 4
                    catalysts_found.add('funding')

            # Product launch (3 points)
            if 'product' not in catalysts_found:
                if any(word in content_lower for word in ['mainnet', 'launch', 'release']):
                    score += 3
                    catalysts_found.add('product')

        return min(15, score)

    def _get_top_announcements(self, news_items: List[NewsItem], limit=5) -> List[Dict]:
        """Get top announcements by sentiment strength"""
        sorted_items = sorted(news_items, key=lambda x: abs(x.sentiment_score), reverse=True)

        return [{
            'title': item.title,
            'date': item.published_date.strftime('%Y-%m-%d'),
            'type': item.announcement_type,
            'sentiment': item.sentiment_label,
            'sentiment_score': round(item.sentiment_score, 2),
            'source': item.source,
            'url': item.url
        } for item in sorted_items[:limit]]

    def _extract_catalysts(self, news_items: List[NewsItem], audit_info: Dict) -> List[str]:
        """Extract major catalysts found"""
        catalysts = []

        if audit_info.get('is_audited'):
            catalysts.append('audit')

        for item in news_items:
            content_lower = (item.title + ' ' + item.content).lower()

            if 'partnership' not in catalysts:
                if any(word in content_lower for word in ['partnership', 'collaborate']):
                    catalysts.append('partnership')

            if 'funding' not in catalysts:
                if any(word in content_lower for word in ['raised', 'funding']):
                    catalysts.append('funding')

            if 'product_launch' not in catalysts:
                if any(word in content_lower for word in ['mainnet', 'launch']):
                    catalysts.append('product_launch')

        return catalysts

    def _extract_concerns(self, news_items: List[NewsItem]) -> List[str]:
        """Extract concerns from negative news"""
        concerns = []

        negative_news = [item for item in news_items if item.sentiment_label == 'negative']

        for item in negative_news[:3]:  # Top 3 concerns
            concerns.append(item.title[:80])

        return concerns


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def format_news_report(metrics: NewsSentimentMetrics) -> str:
    """Format a detailed news sentiment report"""

    def rating(score):
        if score >= 80: return "EXCELLENT"
        if score >= 65: return "GOOD"
        if score >= 50: return "MODERATE"
        if score >= 30: return "LOW"
        return "VERY LOW"

    report = f"""
{'='*80}
NEWS SENTIMENT ANALYSIS: {metrics.token_symbol}
{'='*80}

OVERALL SCORE: {metrics.total_score:.1f}/100 ({rating(metrics.total_score)})

Component Breakdown:
  Sentiment:    {metrics.sentiment_score:.1f}/40
  Velocity:     {metrics.velocity_score:.1f}/25
  GitHub:       {metrics.github_score:.1f}/20
  Catalysts:    {metrics.catalyst_score:.1f}/15

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWS COVERAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  24h: {metrics.recent_news_24h} articles
  7d:  {metrics.recent_news_7d} articles
  30d: {metrics.recent_news_30d} articles
  Total: {metrics.total_news_items} articles

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GITHUB ACTIVITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Repository:      {'✓ Found' if metrics.has_github else '✗ Not found'}
  Commits (30d):   {metrics.github_commits_30d}
  Last commit:     {metrics.github_last_commit_days} days ago

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECURITY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Audited:         {'✓ YES' if metrics.is_audited else '✗ NO'}
  Audit Firm:      {metrics.audit_firm or 'N/A'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAJOR CATALYSTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  {', '.join(metrics.major_catalysts) if metrics.major_catalysts else 'None detected'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOP ANNOUNCEMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    for i, announcement in enumerate(metrics.top_announcements, 1):
        report += f"""
  {i}. {announcement['title']}
     Date: {announcement['date']} | Type: {announcement['type']}
     Sentiment: {announcement['sentiment']} ({announcement['sentiment_score']:.2f})
     Source: {announcement['source']}
"""

    if metrics.concerns:
        report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  CONCERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for concern in metrics.concerns:
            report += f"  • {concern}\n"

    report += f"\n{'='*80}\n"
    report += f"Analysis completed at: {metrics.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"{'='*80}\n"

    return report


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Demo usage
    print("News Sentiment Analyzer - Demo Mode")
    print("=" * 80)

    # Initialize analyzer (with mock data in demo mode)
    analyzer = NewsSentimentAnalyzer(
        cryptopanic_key=None,  # Add your key here
        newsapi_key=None,      # Add your key here
        github_token=None      # Add your token here
    )

    # Example analysis
    metrics = analyzer.analyze_token(
        token_address="0x1234567890abcdef",
        token_symbol="DEMO",
        social_links={
            'github': 'https://github.com/ethereum/go-ethereum',
            'medium': '@ethereum'
        }
    )

    # Print report
    print(format_news_report(metrics))

    print("\nNOTE: This is demo mode with limited functionality.")
    print("Add API keys to enable full news fetching capabilities.")
