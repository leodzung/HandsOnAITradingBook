"""Test that Event and FeatureExtractor handle None values gracefully."""

import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from utils.event_detector import Event
from features.feature_extractor import EventFeatureExtractor


def test_event_none_title():
    """Test Event with None title."""
    event = Event(
        title=None,
        description="Test description",
        source="Test",
        published_time=datetime.now(timezone.utc),
        url="https://example.com",
        keywords=["test"]
    )
    assert event.title == ''
    assert event.description == "Test description"


def test_event_none_description():
    """Test Event with None description."""
    event = Event(
        title="Test title",
        description=None,
        source="Test",
        published_time=datetime.now(timezone.utc),
        url="https://example.com",
        keywords=["test"]
    )
    assert event.title == "Test title"
    assert event.description == ''


def test_event_none_keywords():
    """Test Event with None keywords."""
    event = Event(
        title="Test title",
        description="Test description",
        source="Test",
        published_time=datetime.now(timezone.utc),
        url="https://example.com",
        keywords=None
    )
    assert event.keywords == []


def test_feature_extractor_with_none_attributes():
    """Test that FeatureExtractor handles None attributes without crashing."""
    # Create event with all None attributes
    event = Event(
        title=None,
        description=None,
        source="Test",
        published_time=datetime.now(timezone.utc),
        url=None,
        keywords=None
    )

    extractor = EventFeatureExtractor()
    features = extractor.extract_event_features(event, use_transformers=False)

    # Should not crash and should return valid features
    assert 'title_length' in features
    assert 'description_length' in features
    assert 'keyword_count' in features
    assert features['title_length'] == 0
    assert features['description_length'] == 0
    assert features['keyword_count'] == 0


def test_feature_extractor_with_valid_event():
    """Test that FeatureExtractor works normally with valid event."""
    event = Event(
        title="Bitcoin hits $70,000",
        description="Bitcoin price surges to new highs",
        source="Test",
        published_time=datetime.now(timezone.utc),
        url="https://example.com",
        keywords=["bitcoin", "crypto"]
    )

    extractor = EventFeatureExtractor()
    features = extractor.extract_event_features(event, use_transformers=False)

    assert features['title_length'] > 0
    assert features['description_length'] > 0
    assert features['keyword_count'] == 2


if __name__ == '__main__':
    print("Testing Event None handling...")
    test_event_none_title()
    test_event_none_description()
    test_event_none_keywords()
    test_feature_extractor_with_none_attributes()
    test_feature_extractor_with_valid_event()
    print("✅ All tests passed!")
