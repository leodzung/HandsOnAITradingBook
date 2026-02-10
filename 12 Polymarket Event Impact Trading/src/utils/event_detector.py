"""
Event Detection System
Monitors news sources and detects events that may impact Polymarket markets.

Features:
- Multi-source event detection (NewsAPI, RSS, Twitter)
- Keyword + synonym matching
- Vector embedding semantic matching (SOTA from IMDEA Polymarket arbitrage paper)
"""

import requests
import time
import logging
from typing import List, Dict, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone
import feedparser
import re
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

# Set up logging
logger = logging.getLogger(__name__)


class Event:
    """Represents a detected event."""

    def __init__(self, title: str, description: str, source: str,
                 published_time: datetime, url: str, keywords: List[str]):
        self.title = title
        self.description = description
        self.source = source
        self.published_time = published_time
        self.url = url
        self.keywords = keywords
        self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique event ID."""
        return f"{self.source}_{int(self.published_time.timestamp())}_{hash(self.title) % 10000}"

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'source': self.source,
            'published_time': self.published_time.isoformat(),
            'url': self.url,
            'keywords': self.keywords
        }

    def __repr__(self):
        return f"Event('{self.title[:50]}...', {self.published_time})"


class NewsAPIDetector:
    """Detect events using NewsAPI."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2"
        self.seen_urls: Set[str] = set()

    def get_recent_news(self, query: Optional[str] = None,
                       sources: Optional[List[str]] = None,
                       language: str = 'en',
                       lookback_hours: int = 24) -> List[Event]:
        """
        Get recent news articles.

        Args:
            query: Search query
            sources: List of news sources
            language: Language code
            lookback_hours: How far back to look

        Returns:
            List of Event objects
        """
        # NewsAPI free tier has ~24h delay on /everything endpoint
        # Enforce minimum lookback of 24 hours
        effective_lookback = max(lookback_hours, 24)

        if effective_lookback > lookback_hours:
            logger.debug(f"NewsAPI: Increased lookback from {lookback_hours}h to {effective_lookback}h (free tier limitation)")

        events = []

        # Try /everything endpoint first
        try:
            params = {
                'apiKey': self.api_key,
                'language': language,
                'sortBy': 'publishedAt',
                'from': (datetime.now() - timedelta(hours=effective_lookback)).strftime('%Y-%m-%dT%H:%M:%S'),
                'q': query if query else 'crypto OR bitcoin OR ethereum OR blockchain'
            }

            if sources:
                params['sources'] = ','.join(sources)

            response = requests.get(f"{self.base_url}/everything", params=params)
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'error':
                logger.warning(f"NewsAPI error: {data.get('message', 'Unknown error')}")
                return self._get_top_headlines(query, language)

            for article in data.get('articles', []):
                url = article.get('url', '')
                if url in self.seen_urls:
                    continue

                self.seen_urls.add(url)

                text = f"{article.get('title', '')} {article.get('description', '')}"
                keywords = self._extract_keywords(text)

                event = Event(
                    title=article.get('title', ''),
                    description=article.get('description', ''),
                    source=f"NewsAPI/{article.get('source', {}).get('name', 'Unknown')}",
                    published_time=datetime.fromisoformat(
                        article.get('publishedAt', '').replace('Z', '+00:00')
                    ),
                    url=url,
                    keywords=keywords
                )
                events.append(event)

            logger.debug(f"NewsAPI /everything: {len(events)} articles")
            return events

        except requests.exceptions.RequestException as e:
            logger.error(f"NewsAPI request error: {e}")
            return self._get_top_headlines(query, language)
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
            return []

    def _get_top_headlines(self, query: Optional[str] = None, language: str = 'en') -> List[Event]:
        """
        Fallback to top-headlines endpoint (real-time but limited).

        Args:
            query: Search query
            language: Language code

        Returns:
            List of Event objects
        """
        try:
            params = {
                'apiKey': self.api_key,
                'language': language,
                'category': 'business',
                'pageSize': 20
            }

            if query:
                params['q'] = query

            response = requests.get(f"{self.base_url}/top-headlines", params=params)
            response.raise_for_status()
            data = response.json()

            events = []
            for article in data.get('articles', []):
                url = article.get('url', '')
                if url in self.seen_urls:
                    continue

                self.seen_urls.add(url)

                text = f"{article.get('title', '')} {article.get('description', '')}"
                keywords = self._extract_keywords(text)

                event = Event(
                    title=article.get('title', ''),
                    description=article.get('description', ''),
                    source=f"NewsAPI/{article.get('source', {}).get('name', 'Unknown')}",
                    published_time=datetime.fromisoformat(
                        article.get('publishedAt', '').replace('Z', '+00:00')
                    ),
                    url=url,
                    keywords=keywords
                )
                events.append(event)

            logger.debug(f"NewsAPI /top-headlines: {len(events)} articles")
            return events

        except Exception as e:
            logger.error(f"NewsAPI top-headlines error: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simple keyword extraction (can be enhanced with NLP)
        words = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]+\b', text)
        return list(set(words))[:10]  # Top 10 unique capitalized words


class RSSFeedDetector:
    """Detect events from RSS feeds."""

    def __init__(self, feed_urls: List[str]):
        self.feed_urls = feed_urls
        self.seen_guids: Set[str] = set()

    def get_recent_news(self, lookback_hours: int = 24) -> List[Event]:
        """
        Get recent news from RSS feeds.

        Args:
            lookback_hours: How far back to look

        Returns:
            List of Event objects
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        events = []

        for feed_url in self.feed_urls:
            try:
                feed = feedparser.parse(feed_url)

                # Get feed title safely
                feed_title = 'RSS Feed'
                if hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
                    feed_title = feed.feed.title

                for entry in feed.entries:
                    # Skip if already seen
                    guid = entry.get('id', entry.get('link', ''))
                    if guid in self.seen_guids:
                        continue

                    self.seen_guids.add(guid)

                    # Parse published time (make timezone-aware)
                    published_time = datetime.now(timezone.utc)
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        # Convert struct_time to timezone-aware datetime
                        published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

                    # Skip if too old
                    if published_time < cutoff_time:
                        continue

                    # Extract keywords
                    text = f"{entry.get('title', '')} {entry.get('summary', '')}"
                    keywords = self._extract_keywords(text)

                    event = Event(
                        title=entry.get('title', ''),
                        description=entry.get('summary', ''),
                        source=feed_title,
                        published_time=published_time,
                        url=entry.get('link', ''),
                        keywords=keywords
                    )
                    events.append(event)

            except Exception as e:
                logger.error(f"Error parsing feed {feed_url}: {e}")
                continue

        return events

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        words = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]+\b', text)
        return list(set(words))[:10]


class TwitterDetector:
    """Detect events from Twitter/X (requires API access)."""

    def __init__(self, bearer_token: str):
        self.bearer_token = bearer_token
        self.base_url = "https://api.twitter.com/2"
        self.seen_tweet_ids: Set[str] = set()

    def search_recent_tweets(self, query: str, max_results: int = 100) -> List[Event]:
        """
        Search recent tweets.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of Event objects
        """
        headers = {
            'Authorization': f'Bearer {self.bearer_token}'
        }

        params = {
            'query': query,
            'max_results': max_results,
            'tweet.fields': 'created_at,public_metrics'
        }

        try:
            response = requests.get(
                f"{self.base_url}/tweets/search/recent",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            data = response.json()

            events = []
            for tweet in data.get('data', []):
                tweet_id = tweet.get('id')
                if tweet_id in self.seen_tweet_ids:
                    continue

                self.seen_tweet_ids.add(tweet_id)

                text = tweet.get('text', '')
                keywords = self._extract_keywords(text)

                event = Event(
                    title=text[:100],
                    description=text,
                    source='Twitter',
                    published_time=datetime.fromisoformat(
                        tweet.get('created_at', '').replace('Z', '+00:00')
                    ),
                    url=f"https://twitter.com/i/web/status/{tweet_id}",
                    keywords=keywords
                )
                events.append(event)

            return events

        except Exception as e:
            print(f"Error fetching tweets: {e}")
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords and hashtags from text."""
        # Extract hashtags
        hashtags = re.findall(r'#(\w+)', text)
        # Extract mentions
        mentions = re.findall(r'@(\w+)', text)
        # Extract capitalized words
        words = re.findall(r'\b[A-Z][a-z]+\b|\b[A-Z]+\b', text)

        return list(set(hashtags + mentions + words))[:10]


class GDELTDetector:
    """Detect events from GDELT database."""

    def __init__(self, db_path: str = 'data/gdelt_news.db'):
        """
        Initialize GDELT detector.

        Args:
            db_path: Path to GDELT SQLite database
        """
        self.db_path = db_path
        self.seen_urls: Set[str] = set()

    def get_recent_news(self, lookback_hours: int = 24,
                       min_tone: Optional[float] = None,
                       themes_filter: Optional[List[str]] = None) -> List[Event]:
        """
        Get recent news from GDELT database.

        Args:
            lookback_hours: How far back to look
            min_tone: Minimum tone value (filters out negative tone if set)
            themes_filter: List of themes to filter by (e.g., ['CRYPTO', 'BITCOIN'])

        Returns:
            List of Event objects
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Calculate cutoff time
            cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

            # Build query
            query = """
                SELECT source_url, source, timestamp, themes, keywords, tone
                FROM news_events
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT 1000
            """

            cursor.execute(query, (cutoff_time,))
            rows = cursor.fetchall()
            conn.close()

            events = []
            for row in rows:
                source_url, source, timestamp, themes, keywords, tone = row

                # Skip if already seen
                if source_url in self.seen_urls:
                    continue

                # Apply tone filter if specified
                if min_tone is not None and (tone is None or tone < min_tone):
                    continue

                # Parse themes
                theme_list = themes.split(';') if themes else []

                # Apply theme filter if specified
                if themes_filter:
                    if not any(tf.upper() in theme.upper() for tf in themes_filter for theme in theme_list):
                        continue

                # Build title from themes and keywords
                title_parts = []

                # Extract readable themes (skip technical codes)
                readable_themes = [t for t in theme_list[:5]
                                 if not t.startswith('WB_') and not t.startswith('TAX_')
                                 and not t.startswith('UNGP_') and not t.startswith('CRISISLEX_')]
                if readable_themes:
                    title_parts.extend(readable_themes[:3])

                # Add keywords
                if keywords:
                    keyword_list = keywords.split(',') if ',' in keywords else [keywords]
                    title_parts.extend([kw.strip().upper() for kw in keyword_list[:3]])

                # Fallback to source if no title parts
                if not title_parts:
                    title = f"News from {source}"
                else:
                    title = ' | '.join(title_parts)

                # Create description from themes
                description = ', '.join(readable_themes[:10]) if readable_themes else f"News article from {source}"

                # Parse timestamp
                try:
                    published_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    published_time = datetime.now(timezone.utc)

                # Extract keywords for matching
                event_keywords = []
                if keywords:
                    event_keywords.extend(keywords.split(','))
                event_keywords.extend(readable_themes[:5])
                event_keywords = [kw.strip() for kw in event_keywords if kw.strip()]

                self.seen_urls.add(source_url)

                event = Event(
                    title=title[:200],  # Limit title length
                    description=description[:500],  # Limit description length
                    source=f"GDELT/{source}",
                    published_time=published_time,
                    url=source_url,
                    keywords=event_keywords[:15]
                )
                events.append(event)

            logger.info(f"✓ GDELT: Retrieved {len(events)} events from last {lookback_hours}h")
            return events

        except sqlite3.OperationalError as e:
            logger.warning(f"GDELT database not available: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching GDELT events: {e}")
            return []


class EmbeddingMatcher:
    """
    Semantic matching using vector embeddings.

    Based on IMDEA Polymarket arbitrage paper (2025) which used embeddings
    to find semantically related markets for arbitrage detection.

    Uses sentence-transformers with e5-large-v2 model (good balance of quality/speed).
    """

    def __init__(self, model_name: str = 'intfloat/e5-large-v2',
                 cache_dir: str = 'data/embedding_cache',
                 similarity_threshold: float = 0.5):
        """
        Initialize embedding matcher.

        Args:
            model_name: HuggingFace model name for sentence-transformers
            cache_dir: Directory to cache embeddings
            similarity_threshold: Minimum cosine similarity for a match (0-1)
        """
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.similarity_threshold = similarity_threshold

        # Lazy load model (only when needed)
        self._model = None
        self._embedding_cache: Dict[str, list] = {}

        # Load cache from disk
        self._load_cache()

    def _load_model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("✓ Embedding model loaded")
            except ImportError:
                logger.warning("sentence-transformers not installed. Run: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise
        return self._model

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()

    def _load_cache(self):
        """Load embedding cache from disk."""
        cache_file = self.cache_dir / 'embeddings.json'
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    self._embedding_cache = json.load(f)
                logger.info(f"✓ Loaded {len(self._embedding_cache)} cached embeddings")
            except Exception as e:
                logger.warning(f"Could not load embedding cache: {e}")
                self._embedding_cache = {}

    def _save_cache(self):
        """Save embedding cache to disk."""
        cache_file = self.cache_dir / 'embeddings.json'
        try:
            with open(cache_file, 'w') as f:
                json.dump(self._embedding_cache, f)
        except Exception as e:
            logger.warning(f"Could not save embedding cache: {e}")

    def get_embedding(self, text: str) -> Optional[list]:
        """
        Get embedding for text, using cache if available.

        Args:
            text: Text to embed

        Returns:
            Embedding as list of floats, or None if failed
        """
        cache_key = self._get_cache_key(text)

        # Check cache
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]

        # Compute embedding
        try:
            model = self._load_model()
            # e5 models work best with "query: " or "passage: " prefix
            prefixed_text = f"query: {text}"
            embedding = model.encode(prefixed_text, normalize_embeddings=True)
            embedding_list = embedding.tolist()

            # Cache it
            self._embedding_cache[cache_key] = embedding_list

            # Periodically save cache (every 100 new embeddings)
            if len(self._embedding_cache) % 100 == 0:
                self._save_cache()

            return embedding_list
        except Exception as e:
            logger.error(f"Failed to compute embedding: {e}")
            return None

    def get_embeddings_batch(self, texts: List[str]) -> List[Optional[list]]:
        """
        Get embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            List of embeddings (or None for failures)
        """
        results = []
        texts_to_compute = []
        indices_to_compute = []

        # Check cache first
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._embedding_cache:
                results.append(self._embedding_cache[cache_key])
            else:
                results.append(None)  # Placeholder
                texts_to_compute.append(text)
                indices_to_compute.append(i)

        # Compute missing embeddings in batch
        if texts_to_compute:
            try:
                model = self._load_model()
                prefixed_texts = [f"query: {t}" for t in texts_to_compute]
                embeddings = model.encode(prefixed_texts, normalize_embeddings=True,
                                         show_progress_bar=len(texts_to_compute) > 10)

                for idx, text, emb in zip(indices_to_compute, texts_to_compute, embeddings):
                    emb_list = emb.tolist()
                    results[idx] = emb_list
                    cache_key = self._get_cache_key(text)
                    self._embedding_cache[cache_key] = emb_list

                self._save_cache()

            except Exception as e:
                logger.error(f"Failed to compute batch embeddings: {e}")

        return results

    def compute_similarity(self, emb1: list, emb2: list) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            emb1: First embedding
            emb2: Second embedding

        Returns:
            Cosine similarity (0-1 for normalized embeddings)
        """
        import numpy as np
        a = np.array(emb1)
        b = np.array(emb2)
        return float(np.dot(a, b))  # Already normalized, so dot product = cosine similarity

    def match_event_to_markets(self, event_text: str,
                               markets: List[Dict]) -> List[Tuple[str, float]]:
        """
        Match an event to markets using semantic similarity.

        Args:
            event_text: Event text (title + description)
            markets: List of market dictionaries

        Returns:
            List of (market_id, similarity_score) tuples, sorted by score descending
        """
        # Get event embedding
        event_emb = self.get_embedding(event_text)
        if event_emb is None:
            return []

        # Get market texts and embeddings
        market_texts = []
        market_ids = []
        for market in markets:
            question = market.get('question', '')
            description = market.get('description', '')[:200]  # Truncate long descriptions
            market_text = f"{question} {description}".strip()
            market_texts.append(market_text)
            market_ids.append(market.get('conditionId'))

        # Batch compute market embeddings
        market_embeddings = self.get_embeddings_batch(market_texts)

        # Compute similarities
        matches = []
        for market_id, market_emb in zip(market_ids, market_embeddings):
            if market_emb is None:
                continue
            similarity = self.compute_similarity(event_emb, market_emb)
            if similarity >= self.similarity_threshold:
                matches.append((market_id, similarity))

        # Sort by similarity descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    def is_available(self) -> bool:
        """Check if embedding model can be loaded."""
        try:
            from sentence_transformers import SentenceTransformer
            return True
        except ImportError:
            return False


class EventMatcher:
    """Match events to Polymarket markets."""

    # Synonym dictionary for better matching
    # Maps canonical term -> list of synonyms (all lowercase)
    SYNONYMS = {
        # Cryptocurrencies
        'bitcoin': ['btc', 'bitcoin', 'satoshi'],
        'ethereum': ['eth', 'ethereum', 'ether'],
        'solana': ['sol', 'solana'],
        'ripple': ['xrp', 'ripple'],
        'dogecoin': ['doge', 'dogecoin'],
        'cardano': ['ada', 'cardano'],

        # Financial terms
        'federal reserve': ['fed', 'federal reserve', 'fomc', 'powell', 'central bank'],
        'interest rate': ['rate', 'rates', 'interest', 'basis points', 'bps'],
        'inflation': ['cpi', 'inflation', 'prices', 'pce'],
        'stock': ['stocks', 'equity', 'equities', 'shares'],
        'market': ['markets', 'market'],

        # Crypto-specific
        'exchange': ['exchange', 'dex', 'cex', 'coinbase', 'binance', 'kraken'],
        'etf': ['etf', 'fund', 'trust', 'gbtc', 'ibit'],
        'sec': ['sec', 'securities', 'gensler', 'regulator'],
        'halving': ['halving', 'halvening', 'block reward'],
        'stablecoin': ['stablecoin', 'usdt', 'usdc', 'tether', 'dai'],

        # Price action
        'price': ['price', 'value', 'worth', 'trading'],
        'rise': ['rise', 'rising', 'surge', 'jump', 'rally', 'gain', 'increase', 'up'],
        'fall': ['fall', 'falling', 'drop', 'crash', 'decline', 'decrease', 'down', 'dip'],
        'ath': ['ath', 'all-time high', 'record', 'highest'],

        # People
        'trump': ['trump', 'donald', 'president'],
        'musk': ['musk', 'elon', 'tesla'],
        'saylor': ['saylor', 'microstrategy', 'mstr'],
    }

    def __init__(self, use_embeddings: bool = True,
                 embedding_model: str = 'intfloat/e5-large-v2',
                 embedding_threshold: float = 0.5,
                 embedding_weight: float = 0.7):
        """
        Initialize event matcher.

        Args:
            use_embeddings: Whether to use vector embeddings for matching
            embedding_model: HuggingFace model name for embeddings
            embedding_threshold: Minimum similarity for embedding match (0-1)
            embedding_weight: Weight for embedding score vs keyword score (0-1)
        """
        self.keyword_cache = defaultdict(list)
        self.use_embeddings = use_embeddings
        self.embedding_weight = embedding_weight

        # Build reverse lookup: synonym -> canonical term
        self._synonym_to_canonical = {}
        for canonical, synonyms in self.SYNONYMS.items():
            for syn in synonyms:
                self._synonym_to_canonical[syn.lower()] = canonical.lower()

        # Initialize embedding matcher if enabled
        self._embedding_matcher = None
        if use_embeddings:
            try:
                self._embedding_matcher = EmbeddingMatcher(
                    model_name=embedding_model,
                    similarity_threshold=embedding_threshold
                )
                if self._embedding_matcher.is_available():
                    logger.info(f"✓ Embedding matcher initialized (model: {embedding_model})")
                else:
                    logger.warning("Embedding model not available, falling back to keyword matching")
                    self._embedding_matcher = None
            except Exception as e:
                logger.warning(f"Could not initialize embedding matcher: {e}")
                self._embedding_matcher = None

    def _expand_keywords(self, keywords: set) -> set:
        """
        Expand keywords using synonym dictionary.

        Args:
            keywords: Set of keywords

        Returns:
            Expanded set including synonyms
        """
        expanded = set(keywords)
        for keyword in keywords:
            kw_lower = keyword.lower()
            # If keyword is a synonym, add the canonical term
            if kw_lower in self._synonym_to_canonical:
                expanded.add(self._synonym_to_canonical[kw_lower])
            # If keyword is a canonical term, add all its synonyms
            if kw_lower in self.SYNONYMS:
                expanded.update(self.SYNONYMS[kw_lower])
        return expanded

    def match_events_to_markets(self, events: List[Event],
                               markets: List[Dict],
                               min_keyword_overlap: int = 1) -> Dict[str, List[Event]]:
        """
        Match events to markets using hybrid keyword + embedding matching.

        If embeddings are enabled, uses a weighted combination of:
        - Keyword overlap score (with synonym expansion)
        - Semantic embedding similarity

        Args:
            events: List of Event objects
            markets: List of market dictionaries
            min_keyword_overlap: Minimum number of overlapping keywords (default: 1)

        Returns:
            Dictionary mapping market IDs to matching events
        """
        # Build keyword index for markets (with synonym expansion)
        market_keywords = {}
        for market in markets:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            text = f"{question} {description}"

            # Extract keywords and expand with synonyms
            keywords = set(re.findall(r'\b[a-z]{3,}\b', text))
            keywords = self._expand_keywords(keywords)
            # Use conditionId (camelCase from API)
            market_keywords[market.get('conditionId')] = keywords

        # Pre-compute embedding matches if enabled
        embedding_matches: Dict[str, Dict[str, float]] = {}  # event_id -> {market_id: score}
        if self._embedding_matcher is not None:
            logger.info(f"Computing embeddings for {len(events)} events × {len(markets)} markets...")
            for event in events:
                event_text = f"{event.title} {event.description}"
                matches = self._embedding_matcher.match_event_to_markets(event_text, markets)
                embedding_matches[event.id] = {m_id: score for m_id, score in matches}
            logger.info(f"✓ Embedding matching complete")

        # Match events to markets (hybrid scoring)
        matches = defaultdict(list)

        for event in events:
            # Expand event keywords with synonyms
            event_keywords = set([k.lower() for k in event.keywords])
            event_keywords = self._expand_keywords(event_keywords)

            for market_id, m_keywords in market_keywords.items():
                # Keyword score (Jaccard-like)
                overlap = len(event_keywords & m_keywords)
                keyword_score = overlap / max(len(m_keywords), 1)

                # Embedding score
                embedding_score = 0.0
                if event.id in embedding_matches:
                    embedding_score = embedding_matches[event.id].get(market_id, 0.0)

                # Hybrid score (weighted combination)
                if self._embedding_matcher is not None:
                    # Use weighted combination when embeddings available
                    hybrid_score = (
                        self.embedding_weight * embedding_score +
                        (1 - self.embedding_weight) * keyword_score
                    )
                    # Match if either keyword overlap OR embedding similarity is good
                    if overlap >= min_keyword_overlap or embedding_score >= self._embedding_matcher.similarity_threshold:
                        matches[market_id].append((event, hybrid_score))
                else:
                    # Fallback to keyword-only matching
                    if overlap >= min_keyword_overlap:
                        matches[market_id].append((event, keyword_score))

        # Sort matches by score and extract events
        result = {}
        for market_id, event_scores in matches.items():
            # Sort by hybrid score descending
            event_scores.sort(key=lambda x: x[1], reverse=True)
            # Extract just the events
            result[market_id] = [e for e, s in event_scores]

        # Log matching stats
        if self._embedding_matcher is not None:
            total_matches = sum(len(v) for v in result.values())
            logger.info(f"Matched {total_matches} event-market pairs (hybrid keyword+embedding)")

        return result

    def score_event_market_relevance(self, event: Event, market: Dict) -> float:
        """
        Score how relevant an event is to a market (0-1).

        Uses hybrid keyword + embedding scoring when embeddings available.

        Args:
            event: Event object
            market: Market dictionary

        Returns:
            Relevance score (0-1)
        """
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        market_text = f"{question} {description}"

        event_text = f"{event.title} {event.description}".lower()

        # Keyword-based Jaccard similarity
        market_words = set(re.findall(r'\b[a-z]{3,}\b', market_text))
        event_words = set(re.findall(r'\b[a-z]{3,}\b', event_text))

        keyword_score = 0.0
        if market_words and event_words:
            overlap = len(market_words & event_words)
            union = len(market_words | event_words)
            keyword_score = overlap / union if union > 0 else 0.0

        # Embedding-based semantic similarity
        embedding_score = 0.0
        if self._embedding_matcher is not None:
            event_emb = self._embedding_matcher.get_embedding(event_text)
            market_emb = self._embedding_matcher.get_embedding(market_text)
            if event_emb is not None and market_emb is not None:
                embedding_score = self._embedding_matcher.compute_similarity(event_emb, market_emb)

        # Hybrid score
        if self._embedding_matcher is not None:
            return self.embedding_weight * embedding_score + (1 - self.embedding_weight) * keyword_score
        else:
            return keyword_score

    # Crypto-related keywords for event filtering
    # Long keywords (7+ chars) can use simple substring matching
    CRYPTO_KEYWORDS_LONG = {
        'bitcoin', 'ethereum', 'cryptocurrency',
        'solana', 'dogecoin', 'ripple', 'cardano',
        'polygon', 'avalanche', 'chainlink',
        'uniswap', 'stablecoin', 'coinbase', 'blockchain',
        'altcoin', 'memecoin', 'halving', 'spot etf',
        'satoshi', 'nakamoto', 'vitalik', 'buterin'
    }

    # Short/ambiguous keywords need word boundary matching
    # (e.g., "eth" in "whether", "sol" in "resolution", "defi" in "deficit")
    CRYPTO_KEYWORDS_SHORT = {
        'btc', 'eth', 'sol', 'xrp', 'ada', 'matic', 'avax', 'link',
        'uni', 'nft', 'ftx', 'usdt', 'usdc', 'defi', 'aave',
        'crypto', 'binance', 'kraken', 'gensler'
    }

    def filter_crypto_events(self, events: List[Event]) -> List[Event]:
        """
        Filter events to only include crypto-related ones.

        Args:
            events: List of Event objects

        Returns:
            List of crypto-related events
        """
        filtered = []
        for event in events:
            if self.is_crypto_event(event):
                filtered.append(event)
        return filtered

    def is_crypto_event(self, event: Event) -> bool:
        """Check if an event is crypto-related."""
        text = f"{event.title} {event.description}".lower()

        # Check long keywords (simple substring match)
        if any(kw in text for kw in self.CRYPTO_KEYWORDS_LONG):
            return True

        # Check short keywords with word boundaries
        for kw in self.CRYPTO_KEYWORDS_SHORT:
            if re.search(rf'\b{kw}\b', text):
                return True

        return False


class EventDetector:
    """Main event detection system combining multiple sources."""

    def __init__(self, news_api_key: Optional[str] = None,
                 twitter_bearer_token: Optional[str] = None,
                 rss_feeds: Optional[List[str]] = None,
                 gdelt_db_path: Optional[str] = 'data/gdelt_news.db',
                 use_embeddings: bool = True,
                 embedding_model: str = 'intfloat/e5-large-v2',
                 embedding_threshold: float = 0.5):
        """
        Initialize event detector.

        Args:
            news_api_key: NewsAPI key
            twitter_bearer_token: Twitter API bearer token
            rss_feeds: List of RSS feed URLs
            gdelt_db_path: Path to GDELT database (set to None to disable)
            use_embeddings: Whether to use vector embeddings for matching
            embedding_model: HuggingFace model name for embeddings
            embedding_threshold: Minimum similarity for embedding match (0-1)
        """
        self.detectors = []

        # Add GDELT detector first (primary source with most comprehensive data)
        if gdelt_db_path:
            self.detectors.append(GDELTDetector(gdelt_db_path))
            logger.info("✓ GDELT detector enabled")

        if news_api_key:
            self.detectors.append(NewsAPIDetector(news_api_key))
            logger.info("✓ NewsAPI detector enabled")

        if twitter_bearer_token:
            self.detectors.append(TwitterDetector(twitter_bearer_token))
            logger.info("✓ Twitter detector enabled")

        if rss_feeds:
            self.detectors.append(RSSFeedDetector(rss_feeds))
            logger.info("✓ RSS detector enabled")

        if not self.detectors:
            logger.warning("⚠ No event detectors configured!")

        self.matcher = EventMatcher(
            use_embeddings=use_embeddings,
            embedding_model=embedding_model,
            embedding_threshold=embedding_threshold
        )

    def get_all_recent_events(self, lookback_hours: int = 1,
                             query: Optional[str] = None) -> List[Event]:
        """
        Get all recent events from all sources.

        Args:
            lookback_hours: How far back to look
            query: Optional search query

        Returns:
            Combined list of events
        """
        all_events = []

        for detector in self.detectors:
            try:
                if isinstance(detector, GDELTDetector):
                    events = detector.get_recent_news(
                        lookback_hours=lookback_hours
                    )
                elif isinstance(detector, NewsAPIDetector):
                    events = detector.get_recent_news(
                        query=query,
                        lookback_hours=lookback_hours
                    )
                elif isinstance(detector, TwitterDetector) and query:
                    events = detector.search_recent_tweets(query=query)
                elif isinstance(detector, RSSFeedDetector):
                    events = detector.get_recent_news(lookback_hours=lookback_hours)
                else:
                    continue

                all_events.extend(events)
                logger.info(f"  {type(detector).__name__}: {len(events)} events")
            except Exception as e:
                logger.error(f"Error from detector {type(detector).__name__}: {e}")
                continue

        # Sort by published time
        all_events.sort(key=lambda e: e.published_time, reverse=True)

        logger.info(f"✓ Total: {len(all_events)} events from all sources")
        return all_events

    def find_relevant_events(self, markets: List[Dict],
                           lookback_hours: int = 1) -> Dict[str, List[Event]]:
        """
        Find events relevant to given markets.

        Args:
            markets: List of market dictionaries
            lookback_hours: How far back to look

        Returns:
            Dictionary mapping market IDs to relevant events
        """
        # Get all recent events
        events = self.get_all_recent_events(lookback_hours=lookback_hours)

        # Match to markets
        matches = self.matcher.match_events_to_markets(events, markets)

        return matches
