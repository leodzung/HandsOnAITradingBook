# NEWS & ANNOUNCEMENT SENTIMENT ANALYSIS STRATEGY
## DEX Token Screening Enhancement

---

## Executive Summary

This strategy adds **news, press releases, and project announcement sentiment analysis** to the existing DEX token screening system. It focuses on analyzing official project communications, media coverage, and development updates to score early-stage tokens before CEX listing.

**Key Differentiator:** Focus on OFFICIAL content (news articles, press releases, blogs, GitHub activity) rather than social media chatter, providing higher-quality signals with lower noise.

---

## 1. DATA SOURCES

### 1.1 Primary News Sources

#### A. Crypto News Aggregators
- **CryptoPanic API** (Free tier available)
  - Real-time crypto news aggregation
  - Coverage: 5000+ news sources
  - API Rate Limit: 20 requests/minute (free), 1000/minute (pro)
  - Cost: Free tier sufficient for testing, Pro $19/month
  - **Usage:** Search for token symbol/address mentions in news articles

- **CoinGecko News API**
  - Integrated with CoinGecko token data
  - Free tier: 50 calls/minute
  - **Usage:** Get news for specific tokens by contract address

- **NewsAPI.org**
  - General news aggregator with crypto coverage
  - 1000 requests/day (free), $449/month (business)
  - Sources: CoinDesk, CoinTelegraph, Decrypt, The Block
  - **Usage:** Keyword search for token mentions

#### B. Project-Specific Content
- **Medium API** (RSS-based, free)
  - Many crypto projects publish on Medium
  - **Usage:** Track project blog posts via RSS feeds

- **Mirror.xyz** (Web scraping)
  - Decentralized publishing platform for crypto
  - Many Web3 projects publish here
  - **Usage:** Check for project announcements

- **Project Websites** (Web scraping)
  - Direct blog/news sections
  - **Usage:** RSS feeds or periodic scraping

#### C. GitHub Activity
- **GitHub API** (Free: 5000 requests/hour authenticated)
  - Commit activity, releases, issues
  - **Usage:** Track development velocity and announcements

#### D. Audit Reports
- **CertiK, PeckShield, SlowMist** (Web scraping)
  - Security audit publications
  - **Usage:** Detect audit completion announcements

---

### 1.2 Content Discovery Flow

```
Token Discovery (DexScreener)
    ↓
Extract Metadata (symbol, address, social links)
    ↓
Search News Sources (token symbol/name)
    ↓
Fetch Project Blog (Medium/Mirror/website RSS)
    ↓
Check GitHub (repo activity, releases)
    ↓
Search Audit Platforms (audit reports)
    ↓
Aggregate All Content
    ↓
Sentiment Analysis
```

---

## 2. APIs & TOOLS

### 2.1 News Aggregation APIs

#### CryptoPanic API
```python
# Free tier: 20 req/min, 1000/month limit
# Pro tier: $19/month, 1000 req/min

import requests

def get_cryptopanic_news(token_symbol, limit=20):
    """
    Fetch news mentions from CryptoPanic
    """
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {
        'auth_token': 'YOUR_API_KEY',
        'currencies': token_symbol,
        'kind': 'news',  # news, media, blog
        'filter': 'rising',  # hot, rising, bullish, bearish
        'public': 'true'
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        return data.get('results', [])

    return []
```

#### NewsAPI.org
```python
# Free: 1000 requests/day
# Business: $449/month, 250k requests/month

def get_newsapi_articles(query, from_date):
    """
    Search news articles mentioning token
    """
    url = "https://newsapi.org/v2/everything"
    params = {
        'apiKey': 'YOUR_API_KEY',
        'q': query,
        'from': from_date,
        'language': 'en',
        'sortBy': 'publishedAt',
        'domains': 'coindesk.com,cointelegraph.com,decrypt.co,theblock.co'
    }

    response = requests.get(url, params=params)
    return response.json().get('articles', [])
```

### 2.2 GitHub API
```python
# Free: 5000 requests/hour (authenticated)
# GitHub Apps: 15,000 requests/hour

from github import Github

def get_github_activity(repo_url):
    """
    Analyze GitHub repository activity
    """
    g = Github("YOUR_GITHUB_TOKEN")

    # Extract owner/repo from URL
    # e.g., "https://github.com/owner/repo" -> "owner/repo"
    repo_path = repo_url.split('github.com/')[-1]
    repo = g.get_repo(repo_path)

    # Get recent activity
    commits = repo.get_commits(since=datetime.now() - timedelta(days=30))
    releases = repo.get_releases()

    return {
        'recent_commits': commits.totalCount,
        'last_commit_date': list(commits)[0].commit.author.date if commits.totalCount > 0 else None,
        'releases': [{'tag': r.tag_name, 'date': r.published_at, 'body': r.body}
                     for r in releases[:5]],
        'contributors': repo.get_contributors().totalCount,
        'stars': repo.stargazers_count,
        'forks': repo.forks_count
    }
```

### 2.3 Web Scraping (Medium, Mirror.xyz)
```python
import feedparser
import requests
from bs4 import BeautifulSoup

def get_medium_posts(username_or_publication):
    """
    Fetch Medium posts via RSS
    """
    feed_url = f"https://medium.com/feed/@{username_or_publication}"
    feed = feedparser.parse(feed_url)

    posts = []
    for entry in feed.entries:
        posts.append({
            'title': entry.title,
            'published': entry.published,
            'link': entry.link,
            'content': BeautifulSoup(entry.content[0].value, 'html.parser').get_text()[:5000]
        })

    return posts

def search_mirror_xyz(project_name):
    """
    Search Mirror.xyz for project posts
    Note: Requires web scraping as no official API
    """
    # Implementation would use BeautifulSoup to scrape Mirror.xyz
    pass
```

### 2.4 NLP Sentiment Models

#### Option A: FinBERT (Financial Sentiment - Recommended)
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

class FinBERTSentimentAnalyzer:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        self.model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

    def analyze(self, text):
        """
        Returns sentiment: positive, negative, neutral
        """
        inputs = self.tokenizer(text, return_tensors="pt",
                               max_length=512, truncation=True)

        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

        labels = ['positive', 'negative', 'neutral']
        scores = predictions[0].tolist()

        return {
            'label': labels[scores.index(max(scores))],
            'scores': {label: score for label, score in zip(labels, scores)}
        }
```

**Cost:** Free (open-source)
**Performance:** Runs locally, ~100ms per analysis on CPU, ~10ms on GPU

#### Option B: GPT-4o-mini (More nuanced)
```python
import openai

class GPTSentimentAnalyzer:
    def __init__(self, api_key):
        self.client = openai.OpenAI(api_key=api_key)

    def analyze_announcement(self, content, context):
        """
        Analyze announcement with context awareness
        """
        prompt = f"""Analyze this crypto project announcement for sentiment and significance.

Project Context: {context['token_symbol']}, {context['project_description']}

Announcement:
{content}

Provide JSON output:
{{
    "sentiment": "positive|neutral|negative",
    "confidence": 0-100,
    "significance": "critical|high|medium|low",
    "key_points": ["point1", "point2"],
    "concerns": ["concern1"] or [],
    "catalysts": ["partnership", "product_launch", "audit", "funding"] or []
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a crypto market analyst specializing in token fundamentals."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )

        return response.choices[0].message.content
```

**Cost:** $0.15/1M input tokens, $0.60/1M output tokens (~$0.001-0.003 per analysis)

#### Option C: Hybrid Approach (Best)
```python
class HybridSentimentAnalyzer:
    def __init__(self, openai_key=None):
        self.finbert = FinBERTSentimentAnalyzer()
        self.gpt = GPTSentimentAnalyzer(openai_key) if openai_key else None

    def analyze(self, content, use_gpt_for_important=True):
        """
        Use FinBERT for quick screening, GPT for detailed analysis
        """
        # Quick FinBERT analysis
        finbert_result = self.finbert.analyze(content)

        # If highly positive/negative and GPT available, get detailed analysis
        if use_gpt_for_important and self.gpt:
            if finbert_result['scores']['positive'] > 0.7 or finbert_result['scores']['negative'] > 0.7:
                gpt_result = self.gpt.analyze_announcement(content, context)
                return {
                    'quick_sentiment': finbert_result,
                    'detailed_analysis': gpt_result,
                    'method': 'hybrid'
                }

        return {
            'quick_sentiment': finbert_result,
            'method': 'finbert_only'
        }
```

---

## 3. SENTIMENT METRICS

### 3.1 Content Analysis Dimensions

#### A. Announcement Types & Weights
```python
ANNOUNCEMENT_TYPES = {
    'partnership': {'weight': 20, 'keywords': ['partner', 'collaboration', 'integrate']},
    'product_launch': {'weight': 25, 'keywords': ['launch', 'release', 'introduce', 'announce']},
    'audit_completion': {'weight': 30, 'keywords': ['audit', 'security review', 'certified']},
    'funding_round': {'weight': 25, 'keywords': ['raised', 'funding', 'investment', 'Series']},
    'exchange_listing': {'weight': 15, 'keywords': ['listed', 'available on', 'trading on']},
    'milestone': {'weight': 10, 'keywords': ['milestone', 'achieved', 'reached']},
    'team_expansion': {'weight': 8, 'keywords': ['hired', 'joined', 'appointed', 'CTO', 'CEO']},
    'technical_update': {'weight': 12, 'keywords': ['upgrade', 'improve', 'optimize', 'v2', 'v3']}
}
```

#### B. Media Tier Weighting
```python
MEDIA_TIERS = {
    'tier_1': {  # Major crypto publications
        'sources': ['coindesk.com', 'cointelegraph.com', 'theblock.co', 'decrypt.co'],
        'weight': 3.0
    },
    'tier_2': {  # Secondary crypto media
        'sources': ['coinjournal.net', 'cryptonews.com', 'newsbtc.com'],
        'weight': 2.0
    },
    'tier_3': {  # Project blogs, Medium
        'sources': ['medium.com', 'mirror.xyz'],
        'weight': 1.0
    }
}
```

#### C. Sentiment Polarity
- **Positive (1.0):** Partnership, funding, audit passed, product launch
- **Neutral (0.0):** Technical updates, team hiring
- **Negative (-1.0):** Security issues, delays, team departures

#### D. News Velocity
- **Frequency:** Number of announcements in last 7/30 days
- **Acceleration:** Increase in news frequency (trending)
- **Recency:** Bonus for very recent news (<24h)

#### E. GitHub Development Signals
```python
GITHUB_METRICS = {
    'commit_frequency': {
        'daily': 10,
        'weekly': 7,
        'monthly': 3,
        'inactive': -10
    },
    'release_signals': {
        'major_release': 15,
        'minor_release': 8,
        'patch': 3
    },
    'community_growth': {
        'stars_increase': 5,
        'fork_increase': 3,
        'contributor_increase': 8
    }
}
```

---

## 4. SCORING ALGORITHM

### 4.1 Component Scores

#### News Sentiment Score (0-100)
```python
def calculate_news_sentiment_score(news_items, github_activity, audit_status):
    """
    Calculate comprehensive news sentiment score

    Components:
    - 40% Weighted Sentiment (announcement types × media tier × polarity)
    - 25% News Velocity (frequency, recency, acceleration)
    - 20% GitHub Activity (commits, releases, community)
    - 15% Major Catalysts (audits, partnerships, funding)
    """

    # 1. Weighted Sentiment (40 points max)
    weighted_sentiment = 0
    total_weight = 0

    for item in news_items:
        announcement_type = classify_announcement(item['title'] + ' ' + item['content'])
        media_tier = get_media_tier(item['source'])
        sentiment = item['sentiment_score']  # -1 to 1

        type_weight = ANNOUNCEMENT_TYPES.get(announcement_type, {}).get('weight', 5)
        tier_weight = MEDIA_TIERS.get(media_tier, {}).get('weight', 1.0)

        weighted_sentiment += sentiment * type_weight * tier_weight
        total_weight += type_weight * tier_weight

    sentiment_score = (weighted_sentiment / max(total_weight, 1)) * 40
    sentiment_score = max(0, min(40, sentiment_score + 20))  # Normalize to 0-40

    # 2. News Velocity (25 points max)
    velocity_score = calculate_velocity_score(news_items)  # 0-25

    # 3. GitHub Activity (20 points max)
    github_score = calculate_github_score(github_activity)  # 0-20

    # 4. Major Catalysts (15 points max)
    catalyst_score = calculate_catalyst_score(news_items, audit_status)  # 0-15

    total_score = sentiment_score + velocity_score + github_score + catalyst_score

    return {
        'total': min(100, total_score),
        'sentiment': sentiment_score,
        'velocity': velocity_score,
        'github': github_score,
        'catalysts': catalyst_score
    }
```

#### Velocity Score Calculation
```python
def calculate_velocity_score(news_items):
    """
    Score based on news frequency and recency
    """
    now = datetime.now()

    # Count by time period
    last_24h = sum(1 for item in news_items if (now - item['published_date']).days < 1)
    last_7d = sum(1 for item in news_items if (now - item['published_date']).days < 7)
    last_30d = sum(1 for item in news_items if (now - item['published_date']).days < 30)

    score = 0

    # Recency bonus (up to 10 points)
    if last_24h > 0:
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
```

#### GitHub Score Calculation
```python
def calculate_github_score(github_activity):
    """
    Score based on development activity
    """
    if not github_activity:
        return 0

    score = 0

    # Commit frequency (up to 8 points)
    commits_30d = github_activity.get('recent_commits', 0)
    if commits_30d >= 100:
        score += 8
    elif commits_30d >= 50:
        score += 6
    elif commits_30d >= 20:
        score += 4
    elif commits_30d >= 5:
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
```

#### Catalyst Score Calculation
```python
def calculate_catalyst_score(news_items, audit_status):
    """
    Identify and score major positive catalysts
    """
    score = 0

    catalysts_found = set()

    for item in news_items:
        content_lower = (item['title'] + ' ' + item['content']).lower()

        # Audit completion (5 points)
        if any(word in content_lower for word in ['audit completed', 'security audit', 'certified by']):
            if 'audit' not in catalysts_found:
                score += 5
                catalysts_found.add('audit')

        # Major partnership (4 points)
        if any(word in content_lower for word in ['partnership with', 'collaborat', 'integrate with']):
            # Check for known tier-1 partners
            tier1_partners = ['binance', 'coinbase', 'chainlink', 'polygon', 'arbitrum']
            if any(partner in content_lower for partner in tier1_partners):
                if 'partnership' not in catalysts_found:
                    score += 4
                    catalysts_found.add('partnership')

        # Funding round (4 points)
        if any(word in content_lower for word in ['raised $', 'funding round', 'investment from']):
            if 'funding' not in catalysts_found:
                score += 4
                catalysts_found.add('funding')

        # Product launch (3 points)
        if any(word in content_lower for word in ['mainnet launch', 'beta release', 'product launch']):
            if 'product' not in catalysts_found:
                score += 3
                catalysts_found.add('product')

    return min(15, score)
```

### 4.2 Final Composite Score
```python
def calculate_final_sentiment_score(token_address, chain):
    """
    Main entry point for news sentiment scoring
    """
    # 1. Gather all data sources
    token_data = get_token_metadata(token_address, chain)
    news_items = aggregate_news(token_data['symbol'], token_data['name'])
    github_activity = get_github_activity(token_data.get('github_url')) if token_data.get('github_url') else None
    audit_status = check_audit_status(token_address, chain)

    # 2. Run sentiment analysis on all content
    for item in news_items:
        item['sentiment_score'] = analyze_sentiment(item['title'] + ' ' + item['content'])

    # 3. Calculate component scores
    scores = calculate_news_sentiment_score(news_items, github_activity, audit_status)

    # 4. Add metadata
    scores['total_news_items'] = len(news_items)
    scores['has_github'] = github_activity is not None
    scores['is_audited'] = audit_status.get('is_audited', False)
    scores['top_announcements'] = get_top_announcements(news_items)[:5]

    return scores
```

---

## 5. IMPLEMENTATION

### 5.1 Core Module Structure

```python
# news_sentiment.py

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time

@dataclass
class NewsItem:
    """Individual news article or announcement"""
    title: str
    content: str
    source: str
    url: str
    published_date: datetime
    sentiment_score: float = 0.0  # -1 to 1
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
    top_announcements: List[Dict]
    major_catalysts: List[str]
    has_github: bool
    github_commits_30d: int
    is_audited: bool
    audit_firm: Optional[str]

    # Risk factors
    negative_news_count: int
    concerns: List[str]

    # Timestamp
    analyzed_at: datetime


class NewsSentimentAnalyzer:
    """
    Main class for news sentiment analysis
    """

    def __init__(self,
                 cryptopanic_key: Optional[str] = None,
                 newsapi_key: Optional[str] = None,
                 github_token: Optional[str] = None,
                 openai_key: Optional[str] = None):

        self.cryptopanic_key = cryptopanic_key
        self.newsapi_key = newsapi_key
        self.github_token = github_token

        # Initialize sentiment analyzer
        self.sentiment_analyzer = HybridSentimentAnalyzer(openai_key)

        # Rate limiting
        self.last_api_calls = {
            'cryptopanic': 0,
            'newsapi': 0,
            'github': 0
        }

    def analyze_token(self, token_address: str, token_symbol: str,
                     social_links: Dict = None) -> NewsSentimentMetrics:
        """
        Complete sentiment analysis for a token
        """
        print(f"[NewsSentiment] Analyzing {token_symbol}...")

        # 1. Gather news from multiple sources
        news_items = self._aggregate_news(token_symbol, social_links)

        # 2. Get GitHub activity
        github_activity = None
        if social_links and social_links.get('github'):
            github_activity = self._get_github_activity(social_links['github'])

        # 3. Check audit status
        audit_status = self._check_audits(token_address, token_symbol)

        # 4. Run sentiment analysis
        for item in news_items:
            sentiment = self.sentiment_analyzer.analyze(item.content)
            item.sentiment_score = self._sentiment_to_score(sentiment)
            item.announcement_type = self._classify_announcement(item.title + ' ' + item.content)
            item.media_tier = self._get_media_tier(item.source)

        # 5. Calculate scores
        scores = calculate_news_sentiment_score(news_items, github_activity, audit_status)

        # 6. Build metrics object
        metrics = NewsSentimentMetrics(
            token_address=token_address,
            token_symbol=token_symbol,
            total_score=scores['total'],
            sentiment_score=scores['sentiment'],
            velocity_score=scores['velocity'],
            github_score=scores['github'],
            catalyst_score=scores['catalysts'],
            total_news_items=len(news_items),
            recent_news_24h=sum(1 for item in news_items if (datetime.now() - item.published_date).days < 1),
            recent_news_7d=sum(1 for item in news_items if (datetime.now() - item.published_date).days < 7),
            recent_news_30d=sum(1 for item in news_items if (datetime.now() - item.published_date).days < 30),
            top_announcements=[{
                'title': item.title,
                'date': item.published_date,
                'type': item.announcement_type,
                'sentiment': item.sentiment_score
            } for item in sorted(news_items, key=lambda x: abs(x.sentiment_score), reverse=True)[:5]],
            major_catalysts=self._extract_catalysts(news_items),
            has_github=github_activity is not None,
            github_commits_30d=github_activity.get('recent_commits', 0) if github_activity else 0,
            is_audited=audit_status.get('is_audited', False),
            audit_firm=audit_status.get('firm'),
            negative_news_count=sum(1 for item in news_items if item.sentiment_score < -0.3),
            concerns=self._extract_concerns(news_items),
            analyzed_at=datetime.now()
        )

        return metrics

    def _aggregate_news(self, token_symbol: str, social_links: Dict) -> List[NewsItem]:
        """Gather news from all sources"""
        news_items = []

        # CryptoPanic
        if self.cryptopanic_key:
            cp_news = self._fetch_cryptopanic(token_symbol)
            news_items.extend(cp_news)

        # NewsAPI
        if self.newsapi_key:
            na_news = self._fetch_newsapi(token_symbol)
            news_items.extend(na_news)

        # Medium
        if social_links and social_links.get('medium'):
            medium_posts = self._fetch_medium(social_links['medium'])
            news_items.extend(medium_posts)

        # Project website RSS
        if social_links and social_links.get('website'):
            website_news = self._fetch_website_rss(social_links['website'])
            news_items.extend(website_news)

        # Remove duplicates and sort by date
        news_items = self._deduplicate_news(news_items)
        news_items.sort(key=lambda x: x.published_date, reverse=True)

        return news_items

    def _fetch_cryptopanic(self, token_symbol: str) -> List[NewsItem]:
        """Fetch from CryptoPanic API"""
        # Rate limiting
        self._rate_limit('cryptopanic', min_interval=3)  # 20/min = 3sec

        # Implementation here...
        pass

    def _fetch_newsapi(self, token_symbol: str) -> List[NewsItem]:
        """Fetch from NewsAPI"""
        # Implementation here...
        pass

    def _rate_limit(self, api_name: str, min_interval: float):
        """Simple rate limiting"""
        last_call = self.last_api_calls.get(api_name, 0)
        elapsed = time.time() - last_call

        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

        self.last_api_calls[api_name] = time.time()
```

### 5.2 Integration with Existing System

```python
# Add to dex_utils.py

from news_sentiment import NewsSentimentAnalyzer, NewsSentimentMetrics

class RiskAnalyzer:
    # ... existing methods ...

    @staticmethod
    def calculate_opportunity_score_with_news(metrics: TokenMetrics,
                                              news_metrics: NewsSentimentMetrics) -> float:
        """
        Enhanced opportunity score incorporating news sentiment
        """
        base_score = RiskAnalyzer.calculate_opportunity_score(metrics)

        # News sentiment adds up to 30 bonus points (or penalty)
        news_bonus = (news_metrics.total_score / 100) * 30

        # Catalyst bonuses
        if 'audit' in news_metrics.major_catalysts:
            news_bonus += 5

        if 'partnership' in news_metrics.major_catalysts:
            news_bonus += 5

        # Negative news penalty
        if news_metrics.negative_news_count > 2:
            news_bonus -= 10

        final_score = base_score + news_bonus

        return min(100, max(0, final_score))
```

### 5.3 Usage Example

```python
# demo_news_sentiment.py

from news_sentiment import NewsSentimentAnalyzer
from dex_utils import DEXDataFetcher, RiskAnalyzer

# Initialize
news_analyzer = NewsSentimentAnalyzer(
    cryptopanic_key='YOUR_KEY',
    newsapi_key='YOUR_KEY',
    github_token='YOUR_TOKEN',
    openai_key='YOUR_KEY'  # Optional
)

# Analyze token
token_address = "0x1234..."
token_symbol = "NEWTOKEN"
social_links = {
    'github': 'https://github.com/project/repo',
    'medium': '@projectmedium',
    'website': 'https://project.com'
}

news_metrics = news_analyzer.analyze_token(
    token_address=token_address,
    token_symbol=token_symbol,
    social_links=social_links
)

print(f"""
NEWS SENTIMENT ANALYSIS: {token_symbol}
{'='*60}
Overall Score: {news_metrics.total_score:.1f}/100

Component Breakdown:
  Sentiment:    {news_metrics.sentiment_score:.1f}/40
  Velocity:     {news_metrics.velocity_score:.1f}/25
  GitHub:       {news_metrics.github_score:.1f}/20
  Catalysts:    {news_metrics.catalyst_score:.1f}/15

News Coverage:
  24h: {news_metrics.recent_news_24h} articles
  7d:  {news_metrics.recent_news_7d} articles
  30d: {news_metrics.recent_news_30d} articles

Major Catalysts: {', '.join(news_metrics.major_catalysts) or 'None'}

Top Announcements:
""")

for i, announcement in enumerate(news_metrics.top_announcements, 1):
    print(f"  {i}. {announcement['title']}")
    print(f"     Type: {announcement['type']}, Sentiment: {announcement['sentiment']:.2f}")

if news_metrics.concerns:
    print(f"\nConcerns: {', '.join(news_metrics.concerns)}")
```

---

## 6. PROS & CONS

### 6.1 Advantages

#### vs. Social Media Sentiment
| Aspect | News Sentiment | Social Media Sentiment |
|--------|----------------|------------------------|
| **Signal Quality** | High - official sources | Low - prone to manipulation |
| **Noise Level** | Low - curated content | Very High - spam, bots, shilling |
| **Manipulation** | Harder to fake | Easy to fake (bot armies) |
| **Credibility** | Verified publishers | Anonymous accounts |
| **Depth** | Detailed analysis | Surface-level reactions |
| **Cost** | Moderate API costs | Lower API costs but more processing |

#### Specific Strengths
1. **Higher Signal-to-Noise Ratio**
   - Official announcements carry more weight than Twitter hype
   - Tier-1 media coverage indicates legitimacy

2. **Verifiable Events**
   - Audits, partnerships, funding are concrete
   - GitHub commits prove active development

3. **Less Gameable**
   - Harder to fake Medium articles on reputable publications
   - Requires actual development for GitHub signals

4. **Leading Indicator**
   - Major announcements often precede price moves
   - Partnership news drives subsequent social media buzz

5. **Complements Technical Analysis**
   - Provides fundamental context
   - Explains "why" behind price movements

### 6.2 Limitations

#### Disadvantages
1. **Coverage Gaps**
   - Very new tokens may have zero news coverage
   - Small projects don't get Tier-1 media attention
   - Only ~20-30% of DEX tokens have news presence

2. **Lag vs. Social Media**
   - News articles published hours/days after events
   - Social media reacts in real-time
   - May miss very early signals

3. **API Costs**
   - NewsAPI Business: $449/month for adequate volume
   - GPT-4o-mini costs add up with high volume
   - CryptoPanic Pro: $19/month

4. **False Positives**
   - Press releases can be misleading
   - Paid articles exist (project-sponsored content)
   - Not all partnerships are equal

5. **Technical Complexity**
   - Requires NLP models (FinBERT or GPT)
   - Web scraping can break with site changes
   - More moving parts = more points of failure

6. **Rate Limits**
   - NewsAPI Free: 1000 requests/day = ~40 tokens/hour
   - CryptoPanic Free: 20 requests/min = 1200/hour
   - GitHub: 5000 requests/hour (sufficient)

---

## 7. COST ANALYSIS

### 7.1 API Costs

#### Tier 1: Minimal Setup (Testing)
- **CryptoPanic Free:** $0/month (20 req/min, 1000/month total)
- **NewsAPI Free:** $0/month (1000 req/day)
- **GitHub Free:** $0/month (5000 req/hour)
- **FinBERT (local):** $0/month (open-source)
- **Total:** $0/month
- **Capacity:** ~30-40 tokens/day

#### Tier 2: Production Light
- **CryptoPanic Pro:** $19/month (1000 req/min)
- **NewsAPI Developer:** $0/month (free tier)
- **GitHub:** $0/month
- **FinBERT:** $0/month
- **GPT-4o-mini (optional):** ~$10/month (1000 tokens × $0.01)
- **Total:** $29-39/month
- **Capacity:** ~500 tokens/day

#### Tier 3: Production Heavy
- **CryptoPanic Pro:** $19/month
- **NewsAPI Business:** $449/month (250k req/month)
- **GitHub:** $0/month
- **GPT-4o-mini:** ~$50/month (5000 tokens × $0.01)
- **Total:** $518/month
- **Capacity:** ~5000 tokens/day

### 7.2 Compute Costs

#### Local FinBERT (CPU)
- **Hardware:** Any modern CPU
- **Speed:** ~100ms per article (10 articles/sec)
- **Cost:** $0 (runs on existing infrastructure)

#### Local FinBERT (GPU)
- **Hardware:** NVIDIA GPU (e.g., RTX 3060)
- **Speed:** ~10ms per article (100 articles/sec)
- **Cost:** $0.50/hour cloud GPU or one-time hardware purchase

#### GPT-4o-mini API
- **Input:** ~500 tokens per article
- **Output:** ~200 tokens per response
- **Cost per analysis:** ~$0.0015 (500 × $0.15/1M + 200 × $0.60/1M)
- **Monthly (1000 tokens):** ~$1.50

### 7.3 Cost per Token Analysis

#### Minimal Setup
- **APIs:** $0
- **NLP:** $0 (FinBERT local)
- **Total per token:** $0
- **Bottleneck:** API rate limits, not cost

#### Production Light
- **APIs:** $29/month ÷ 15,000 tokens = $0.002 per token
- **NLP:** $10/month ÷ 1,000 tokens = $0.01 per token (if using GPT)
- **Total per token:** $0.012
- **Cost for 100 tokens/day:** $36/month

#### Production Heavy
- **APIs:** $468/month ÷ 150,000 tokens = $0.003 per token
- **NLP:** $50/month ÷ 5,000 tokens = $0.01 per token
- **Total per token:** $0.013
- **Cost for 1000 tokens/day:** $390/month

### 7.4 Comparison to Alternatives

| Approach | Monthly Cost | Tokens/Day | Cost/Token |
|----------|--------------|------------|------------|
| News Sentiment (Minimal) | $0 | 30-40 | $0 |
| News Sentiment (Production) | $39 | 500 | $0.078 |
| Social Media APIs (Twitter V2) | $100 | 1000+ | $0.003 |
| Web3 Social (Lens, Farcaster) | $0 | Unlimited | $0 |
| Combined (News + Social) | $139 | 1000+ | $0.046 |

---

## 8. RATE LIMITS & THROUGHPUT

### 8.1 API Rate Limits

| API | Free Tier | Paid Tier | Cost |
|-----|-----------|-----------|------|
| **CryptoPanic** | 20 req/min<br>1000 req/month total | 1000 req/min<br>Unlimited monthly | $19/month |
| **NewsAPI** | 1000 req/day | 250k req/month | $449/month |
| **GitHub** | 5000 req/hour | 15k req/hour (App) | Free |
| **CoinGecko** | 50 calls/min | 500 calls/min | $129/month |
| **Medium RSS** | No limit | N/A | Free |
| **OpenAI (GPT-4o-mini)** | No limit | 10k req/min | Pay-per-use |

### 8.2 Practical Throughput

#### Bottleneck Analysis (Free Tier)
```
Slowest API = NewsAPI (1000 req/day = 41.6 req/hour)

Per token analysis requires:
- 1× CryptoPanic request (news search)
- 1× NewsAPI request (news search)  ← BOTTLENECK
- 1× GitHub request (if repo exists)
- 3× Article fetches (various)

Throughput = 41.6 tokens/hour = ~1000 tokens/day (if running 24/7)
```

#### With Paid Tiers
```
CryptoPanic Pro: 1000 req/min = 60,000 tokens/hour (theoretical)
NewsAPI Business: 250k req/month = ~350 req/hour avg

Practical limit: ~350 tokens/hour = 8,400 tokens/day
```

### 8.3 Optimization Strategies

#### 1. Caching
```python
# Cache news results for 6 hours
cache_ttl = 6 * 3600  # 6 hours

def get_news_cached(token_symbol):
    cache_key = f"news:{token_symbol}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)

    # Fetch fresh data
    news = fetch_news(token_symbol)
    redis_client.setex(cache_key, cache_ttl, json.dumps(news))

    return news
```
**Impact:** Reduces API calls by 80-90% for re-analyzed tokens

#### 2. Batch Processing
```python
# Process tokens in batches to optimize API usage
def analyze_batch(token_addresses, batch_size=10):
    results = []

    for i in range(0, len(token_addresses), batch_size):
        batch = token_addresses[i:i+batch_size]

        # Fetch news for entire batch (single API call if supported)
        batch_news = fetch_news_batch(batch)

        for token in batch:
            results.append(analyze_token(token, batch_news[token]))

        # Respect rate limits
        time.sleep(60 / API_RATE_LIMIT)

    return results
```
**Impact:** 2-5x throughput improvement

#### 3. Selective Deep Analysis
```python
# Use fast screening, then deep analysis for high scorers
def smart_analyze(token):
    # Quick check: Does token have ANY news?
    has_news = quick_news_check(token)  # 1 API call

    if not has_news:
        return {'score': 0, 'reason': 'No news coverage'}

    # If yes, do full analysis
    return full_news_analysis(token)  # 5-10 API calls
```
**Impact:** 70% of tokens filtered early, saving 80% of API calls

### 8.4 Realistic Production Targets

#### Configuration: Paid APIs + Caching + Batching
```
NewsAPI Business: 250k req/month = ~8,300 req/day
CryptoPanic Pro: 1000 req/min (effectively unlimited)

With optimizations:
- 30% cache hit rate
- 50% tokens have no news (quick reject)
- 20% tokens get full analysis

Effective throughput:
  8,300 req/day ÷ 1.5 avg req/token = ~5,500 tokens/day
```

#### Recommendation
```
Tier 1 (Testing): 30-40 tokens/day (free tier)
Tier 2 (Pilot): 500-1000 tokens/day ($29/month)
Tier 3 (Production): 3000-5000 tokens/day ($518/month)
```

---

## 9. INTEGRATION EXAMPLE

### 9.1 Adding to Existing Strategy Ranker

```python
# Modified strategy_ranker.py

from news_sentiment import NewsSentimentAnalyzer

class EnhancedStrategyRanker(StrategyRanker):
    def __init__(self, enable_news_sentiment=True, news_api_keys=None):
        super().__init__()

        self.enable_news_sentiment = enable_news_sentiment

        if enable_news_sentiment:
            self.news_analyzer = NewsSentimentAnalyzer(
                cryptopanic_key=news_api_keys.get('cryptopanic'),
                newsapi_key=news_api_keys.get('newsapi'),
                github_token=news_api_keys.get('github'),
                openai_key=news_api_keys.get('openai')
            )

    def analyze_opportunity_with_news(self, opportunity):
        """
        Enhance opportunity analysis with news sentiment
        """
        # Get base scores
        base_composite = opportunity.composite_score
        base_opportunity = opportunity.opportunity_score

        # Add news sentiment if enabled
        if self.enable_news_sentiment:
            news_metrics = self.news_analyzer.analyze_token(
                token_address=opportunity.token_address,
                token_symbol=opportunity.token_symbol,
                social_links=opportunity.social_links
            )

            # Adjust opportunity score based on news
            news_boost = (news_metrics.total_score / 100) * 20  # Up to +20 points

            # Bonus for major catalysts
            if 'audit' in news_metrics.major_catalysts:
                news_boost += 5
            if 'partnership' in news_metrics.major_catalysts:
                news_boost += 5

            # Penalty for negative news
            if news_metrics.negative_news_count > 2:
                news_boost -= 10

            enhanced_opportunity = base_opportunity + news_boost
            enhanced_composite = (base_composite * 0.7) + (enhanced_opportunity * 0.3)

            return {
                'original_composite': base_composite,
                'enhanced_composite': min(100, enhanced_composite),
                'news_metrics': news_metrics,
                'news_boost': news_boost
            }

        return {'original_composite': base_composite}
```

### 9.2 Complete Analysis Flow

```python
# demo_full_analysis.py

from strategy1_pool_scanner import PoolScannerStrategy
from news_sentiment import NewsSentimentAnalyzer
from dex_utils import DEXDataFetcher, RiskAnalyzer

def run_complete_analysis():
    """
    Complete token analysis with news sentiment
    """

    # Step 1: Find tokens via pool scanner
    pool_scanner = PoolScannerStrategy(
        chains=['ethereum', 'bsc', 'base'],
        min_liquidity_usd=20000,
        min_safety_score=65
    )

    pool_scanner.run(max_cycles=1)
    opportunities = pool_scanner.get_ranked_opportunities()

    print(f"Found {len(opportunities)} opportunities")

    # Step 2: Add news sentiment analysis
    news_analyzer = NewsSentimentAnalyzer(
        cryptopanic_key=os.getenv('CRYPTOPANIC_KEY'),
        newsapi_key=os.getenv('NEWSAPI_KEY'),
        github_token=os.getenv('GITHUB_TOKEN')
    )

    enhanced_opportunities = []

    for opp in opportunities[:20]:  # Top 20 only
        print(f"\nAnalyzing {opp.token_symbol}...")

        # Get news sentiment
        news_metrics = news_analyzer.analyze_token(
            token_address=opp.token_address,
            token_symbol=opp.token_symbol,
            social_links=opp.social_links
        )

        # Calculate enhanced score
        base_score = opp.composite_score
        news_score = news_metrics.total_score

        # Weighted combination: 60% base + 40% news
        final_score = (base_score * 0.6) + (news_score * 0.4)

        enhanced_opportunities.append({
            'token': opp.token_symbol,
            'address': opp.token_address,
            'base_score': base_score,
            'news_score': news_score,
            'final_score': final_score,
            'news_metrics': news_metrics,
            'opportunity': opp
        })

    # Step 3: Re-rank by final score
    enhanced_opportunities.sort(key=lambda x: x['final_score'], reverse=True)

    # Step 4: Print report
    print("\n" + "="*80)
    print("ENHANCED OPPORTUNITY RANKING (with News Sentiment)")
    print("="*80)

    for i, enh_opp in enumerate(enhanced_opportunities[:10], 1):
        nm = enh_opp['news_metrics']

        print(f"\n#{i} {enh_opp['token']} - FINAL SCORE: {enh_opp['final_score']:.1f}/100")
        print(f"   Base Score: {enh_opp['base_score']:.1f} | News Score: {enh_opp['news_score']:.1f}")
        print(f"   News: {nm.recent_news_7d} articles (7d), {nm.total_news_items} total")

        if nm.major_catalysts:
            print(f"   Catalysts: {', '.join(nm.major_catalysts)}")

        if nm.top_announcements:
            print(f"   Latest: {nm.top_announcements[0]['title'][:60]}...")

    return enhanced_opportunities

if __name__ == "__main__":
    run_complete_analysis()
```

---

## 10. CONCLUSION

### 10.1 Strategic Recommendation

**IMPLEMENT AS COMPLEMENTARY LAYER** to existing strategies, not replacement.

#### Optimal Setup
```
Tier 1 Strategy: Pool Scanner + Smart Money + Anomaly Detector
    ↓
Tier 2 Filter: News Sentiment Analysis (top 20-50 tokens)
    ↓
Final Ranking: Combined score (60% Tier 1 + 40% News)
```

#### Resource Allocation
```
Stage 1 (Testing - Month 1):
  - Use free API tiers
  - FinBERT for sentiment (local)
  - Analyze ~30 tokens/day
  - Cost: $0/month

Stage 2 (Pilot - Month 2-3):
  - CryptoPanic Pro ($19/month)
  - FinBERT + occasional GPT-4o-mini
  - Analyze ~500 tokens/day
  - Cost: $29-39/month

Stage 3 (Production - Month 4+):
  - NewsAPI Business ($449/month)
  - Hybrid FinBERT/GPT analysis
  - Analyze ~3000-5000 tokens/day
  - Cost: $500-600/month
```

### 10.2 Success Metrics

Track these KPIs to validate effectiveness:

1. **Coverage Rate:** % of DEX tokens with news coverage (expect 20-30%)
2. **Predictive Power:** Correlation between news score and 7-day returns
3. **Alpha Generation:** Returns of top-scored tokens vs. baseline
4. **False Positive Reduction:** % reduction in scam tokens vs. no news filter
5. **Cost Efficiency:** ROI (returns generated / API costs)

### 10.3 Next Steps

1. **Week 1:** Implement minimal setup with free tiers, test on 100 tokens
2. **Week 2:** Build caching and optimization layers
3. **Week 3:** Integrate with existing strategy ranker
4. **Week 4:** Backtest on historical data (if available)
5. **Month 2:** Upgrade to paid tiers, scale to 500 tokens/day
6. **Month 3:** Optimize based on performance data
7. **Month 4+:** Full production deployment

---

## APPENDIX A: Code Repository Structure

```
09 DEX Screening Strategies/
├── dex_utils.py                 # Existing
├── strategy_ranker.py           # Existing
├── strategy1_pool_scanner.py    # Existing
├── news_sentiment.py            # NEW
├── news_data_sources.py         # NEW - API wrappers
├── news_nlp.py                  # NEW - Sentiment models
├── demo_news_sentiment.py       # NEW - Demo script
├── requirements_news.txt        # NEW - Dependencies
└── config_news.yaml             # NEW - API keys config
```

## APPENDIX B: Dependencies

```txt
# requirements_news.txt

# News APIs
requests>=2.31.0
feedparser>=6.0.10
beautifulsoup4>=4.12.0

# NLP
transformers>=4.35.0
torch>=2.1.0
sentencepiece>=0.1.99

# GitHub
PyGithub>=2.1.1

# Optional (for GPT)
openai>=1.3.0

# Utilities
python-dateutil>=2.8.2
pyyaml>=6.0
redis>=5.0.0  # For caching
```

## APPENDIX C: Sample Output

```
NEWS SENTIMENT ANALYSIS: BASEDOG
================================================================================
Overall Score: 73.5/100 (GOOD)

Component Breakdown:
  Sentiment:    28.5/40  (Positive coverage)
  Velocity:     18.0/25  (High activity)
  GitHub:       15.0/20  (Active development)
  Catalysts:    12.0/15  (Major announcements)

News Coverage:
  24h: 3 articles
  7d:  12 articles
  30d: 28 articles

Major Catalysts: audit, partnership, product_launch

Top Announcements:
  1. "BASEDOG completes CertiK security audit"
     Type: audit_completion, Sentiment: 0.89

  2. "BASEDOG partners with Chainlink for price feeds"
     Type: partnership, Sentiment: 0.76

  3. "BASEDOG launches staking v2 with 15% APY"
     Type: product_launch, Sentiment: 0.68

GitHub Activity:
  Commits (30d): 47
  Last commit: 2 days ago
  Contributors: 5
  Stars: 234

Risk Assessment: LOW
  ✓ Active development (recent commits)
  ✓ Audited by CertiK
  ✓ Growing media coverage
  ⚠ Anonymous team (not doxxed)

Recommendation: STRONG BUY
  News sentiment strongly positive with multiple catalysts
  Combine with technical analysis for entry timing
================================================================================
```

---

**END OF STRATEGY DOCUMENT**
