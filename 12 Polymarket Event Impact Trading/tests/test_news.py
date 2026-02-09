#!/usr/bin/env python3
"""
Test real news detection with NewsAPI
"""

import json
from event_detector import EventDetector

# Load config
with open('config.json', 'r') as f:
    config = json.load(f)

# Initialize detector with RSS feeds (works without API key)
print("Testing RSS feed news detection...")
detector = EventDetector(
    news_api_key=config.get('news_api_key') if config.get('news_api_key') != 'YOUR_NEWS_API_KEY' else None,
    rss_feeds=config.get('rss_feeds', [])
)

# Get recent events
events = detector.get_all_recent_events(lookback_hours=24)

print(f"\n✓ Found {len(events)} recent events from RSS feeds:\n")

for i, event in enumerate(events[:5], 1):
    print(f"{i}. {event.title[:70]}...")
    print(f"   Source: {event.source}")
    print(f"   Published: {event.published_time.strftime('%Y-%m-%d %I:%M %p')}")
    print(f"   Keywords: {', '.join(event.keywords[:5])}")
    print()

if len(events) == 0:
    print("⚠️  No events found. This could mean:")
    print("   - RSS feeds are slow to update")
    print("   - Network connectivity issue")
    print("   - Try adding NewsAPI key for better results")
else:
    print(f"✓ Event detection working! Found {len(events)} total events.")
