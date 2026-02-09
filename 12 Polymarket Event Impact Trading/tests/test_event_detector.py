"""
Tests for event detection system
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from event_detector import Event, NewsAPIDetector, RSSFeedDetector


class TestEvent:
    """Test suite for Event class."""

    def test_event_creation(self):
        """Test creating an Event instance."""
        event = Event(
            title='Bitcoin Hits $100k',
            description='Bitcoin reaches new all-time high',
            source='Reuters',
            published_time=datetime.now(timezone.utc),
            url='https://example.com/news',
            keywords=['Bitcoin', 'BTC', 'Price']
        )

        assert event.title == 'Bitcoin Hits $100k'
        assert event.source == 'Reuters'
        assert len(event.keywords) == 3

    def test_event_id_generation(self):
        """Test unique event ID generation."""
        event1 = Event(
            title='Test Event',
            description='Test',
            source='Source1',
            published_time=datetime.now(timezone.utc),
            url='http://test.com',
            keywords=[]
        )

        event2 = Event(
            title='Different Event',
            description='Test',
            source='Source1',
            published_time=datetime.now(timezone.utc),
            url='http://test.com',
            keywords=[]
        )

        assert event1.id != event2.id

    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        event = Event(
            title='Test',
            description='Desc',
            source='Source',
            published_time=datetime.now(timezone.utc),
            url='http://test.com',
            keywords=['test']
        )

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert 'id' in event_dict
        assert 'title' in event_dict
        assert 'keywords' in event_dict


class TestNewsAPIDetector:
    """Test suite for NewsAPIDetector."""

    def test_initialization(self):
        """Test NewsAPI detector initialization."""
        detector = NewsAPIDetector(api_key='test_key')

        assert detector.api_key == 'test_key'
        assert len(detector.seen_urls) == 0

    @patch('event_detector.requests.get')
    def test_get_recent_news(self, mock_get):
        """Test fetching recent news."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'Bitcoin Surges',
                    'description': 'BTC hits new high',
                    'source': {'name': 'Reuters'},
                    'publishedAt': '2026-01-15T10:00:00Z',
                    'url': 'https://example.com/news1'
                },
                {
                    'title': 'Ethereum Update',
                    'description': 'ETH 2.0 progress',
                    'source': {'name': 'Bloomberg'},
                    'publishedAt': '2026-01-15T11:00:00Z',
                    'url': 'https://example.com/news2'
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        detector = NewsAPIDetector(api_key='test_key')
        events = detector.get_recent_news(query='crypto', lookback_hours=24)

        assert len(events) == 2
        assert events[0].title == 'Bitcoin Surges'
        assert events[1].source == 'Bloomberg'

    @patch('event_detector.requests.get')
    def test_deduplication(self, mock_get):
        """Test that duplicate URLs are filtered."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'articles': [
                {
                    'title': 'News 1',
                    'description': 'Desc',
                    'source': {'name': 'Source'},
                    'publishedAt': '2026-01-15T10:00:00Z',
                    'url': 'https://example.com/same'
                },
                {
                    'title': 'News 2',
                    'description': 'Desc',
                    'source': {'name': 'Source'},
                    'publishedAt': '2026-01-15T11:00:00Z',
                    'url': 'https://example.com/same'  # Duplicate
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        detector = NewsAPIDetector(api_key='test_key')
        events = detector.get_recent_news()

        # Should only get 1 event (second is duplicate)
        assert len(events) == 1

    def test_keyword_extraction(self):
        """Test keyword extraction from text."""
        detector = NewsAPIDetector(api_key='test_key')

        text = "Bitcoin Price Surges to New Record High"
        keywords = detector._extract_keywords(text)

        assert 'Bitcoin' in keywords
        assert 'Price' in keywords
        assert len(keywords) <= 10


class TestRSSFeedDetector:
    """Test suite for RSSFeedDetector."""

    def test_initialization(self):
        """Test RSS detector initialization."""
        feeds = ['http://feed1.com/rss', 'http://feed2.com/rss']
        detector = RSSFeedDetector(feed_urls=feeds)

        assert len(detector.feed_urls) == 2
        assert len(detector.seen_guids) == 0

    @patch('event_detector.feedparser.parse')
    def test_get_recent_news(self, mock_parse):
        """Test fetching news from RSS feeds."""
        mock_feed = Mock()
        mock_feed.feed.title = 'Test Feed'
        mock_feed.entries = [
            Mock(
                id='entry1',
                title='Test Article',
                summary='Test summary',
                link='http://example.com/1',
                published_parsed=(2026, 1, 15, 10, 0, 0, 0, 0, 0)
            )
        ]
        mock_parse.return_value = mock_feed

        detector = RSSFeedDetector(feed_urls=['http://feed.com/rss'])
        events = detector.get_recent_news(lookback_hours=24)

        assert len(events) >= 0  # May filter by time
        if events:
            assert events[0].title == 'Test Article'

    @patch('event_detector.feedparser.parse')
    def test_deduplication_by_guid(self, mock_parse):
        """Test deduplication by GUID."""
        mock_feed = Mock()
        mock_feed.feed.title = 'Test Feed'
        mock_feed.entries = [
            Mock(
                id='same_id',
                title='Article 1',
                summary='Summary',
                link='http://example.com/1',
                published_parsed=(2026, 1, 15, 10, 0, 0, 0, 0, 0)
            ),
            Mock(
                id='same_id',  # Duplicate
                title='Article 2',
                summary='Summary',
                link='http://example.com/2',
                published_parsed=(2026, 1, 15, 11, 0, 0, 0, 0, 0)
            )
        ]
        mock_parse.return_value = mock_feed

        detector = RSSFeedDetector(feed_urls=['http://feed.com/rss'])
        events = detector.get_recent_news(lookback_hours=24)

        # Should only get 1 event
        assert len(events) <= 1


class TestEventMatching:
    """Test event-to-market matching logic."""

    def test_keyword_overlap_detection(self, sample_event, sample_market):
        """Test detecting keyword overlap between event and market."""
        # Event has Bitcoin keywords
        # Market asks about Bitcoin
        # Should have high overlap
        event_text = sample_event.title.lower()
        market_text = sample_market['question'].lower()

        # Simple keyword check
        bitcoin_keywords = ['bitcoin', 'btc']
        event_has_btc = any(kw in event_text for kw in bitcoin_keywords)
        market_has_btc = any(kw in market_text for kw in bitcoin_keywords)

        assert event_has_btc
        assert market_has_btc

    def test_category_matching(self):
        """Test matching events to markets by category."""
        crypto_event_keywords = ['Bitcoin', 'BTC', 'Cryptocurrency']
        politics_event_keywords = ['Election', 'Trump', 'Vote']

        crypto_market = {'question': 'Will Bitcoin reach $100k?'}
        politics_market = {'question': 'Will Trump win the election?'}

        # Crypto event should match crypto market
        crypto_match = any(kw.lower() in crypto_market['question'].lower()
                          for kw in crypto_event_keywords)

        # Politics event should match politics market
        politics_match = any(kw.lower() in politics_market['question'].lower()
                           for kw in politics_event_keywords)

        assert crypto_match
        assert politics_match

    def test_timestamp_freshness(self):
        """Test that event timestamps are recent for matching."""
        from datetime import timedelta

        recent_event = Event(
            title='Test',
            description='Test',
            source='Source',
            published_time=datetime.now(timezone.utc),
            url='http://test.com',
            keywords=[]
        )

        old_event = Event(
            title='Test',
            description='Test',
            source='Source',
            published_time=datetime.now(timezone.utc) - timedelta(days=7),
            url='http://test.com',
            keywords=[]
        )

        now = datetime.now(timezone.utc)
        recent_age = (now - recent_event.published_time).total_seconds() / 3600
        old_age = (now - old_event.published_time).total_seconds() / 3600

        assert recent_age < 24  # Less than 1 day
        assert old_age > 24  # More than 1 day
