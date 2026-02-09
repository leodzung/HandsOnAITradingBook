#!/usr/bin/env python3
"""
Quick NewsAPI Setup and Test
"""

import json
import requests
from datetime import datetime, timedelta

def update_config(api_key: str):
    """Update config.json with NewsAPI key"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)

        config['news_api_key'] = api_key

        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)

        print("✓ Updated config.json with your API key")
        return True

    except Exception as e:
        print(f"✗ Error updating config: {e}")
        return False

def test_api_key(api_key: str):
    """Test if API key works"""
    print("\nTesting API key...")

    from_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    url = "https://newsapi.org/v2/everything"
    params = {
        'q': 'bitcoin',
        'from': from_date,
        'sortBy': 'publishedAt',
        'language': 'en',
        'apiKey': api_key,
        'pageSize': 5
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get('status') == 'ok':
            articles = data.get('articles', [])
            print(f"\n✓ API key works! Found {len(articles)} recent articles\n")

            if articles:
                print("Sample articles:")
                for i, article in enumerate(articles[:3], 1):
                    print(f"\n{i}. {article['title']}")
                    print(f"   Source: {article['source']['name']}")
                    print(f"   Published: {article['publishedAt']}")

            return True
        else:
            print(f"✗ API error: {data.get('message', 'Unknown error')}")
            return False

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("✗ Invalid API key")
        elif e.response.status_code == 429:
            print("✗ Rate limit exceeded (500 requests/day limit)")
        else:
            print(f"✗ HTTP Error: {e}")
        return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("="*70)
    print("NEWSAPI SETUP")
    print("="*70)

    print("\nNewsAPI Free Tier:")
    print("  • 500 requests/day")
    print("  • 7 days historical data")
    print("  • All sources included")
    print("  • Perfect for this project!")

    print("\n" + "="*70)

    # Check if already configured
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            existing_key = config.get('news_api_key')

        if existing_key and existing_key != 'YOUR_NEWS_API_KEY':
            print("\n✓ API key already configured in config.json")
            print(f"   Key: {existing_key[:10]}...")

            test = input("\nTest existing key? (y/n): ").strip().lower()
            if test == 'y':
                if test_api_key(existing_key):
                    print("\n✓ Your NewsAPI is ready to use!")
                    print("\nNext: Run python3 data_collector.py")
                    return
            else:
                return

    except:
        pass

    # Prompt for new key
    print("\n" + "="*70)
    print("GET YOUR FREE API KEY:")
    print("="*70)

    print("\n1. Visit: https://newsapi.org/register")
    print("2. Sign up (takes 1 minute)")
    print("3. Copy your API key")
    print("4. Paste it below\n")

    api_key = input("Enter your NewsAPI key (or 'skip' to do later): ").strip()

    if api_key.lower() == 'skip':
        print("\nNo problem! You can add it to config.json manually later.")
        print("Look for: \"news_api_key\": \"YOUR_NEWS_API_KEY\"")
        return

    if not api_key or len(api_key) < 20:
        print("\n⚠️  That doesn't look like a valid API key")
        print("Keys are usually 32 characters long")
        return

    # Test the key
    if test_api_key(api_key):
        # Update config
        if update_config(api_key):
            print("\n" + "="*70)
            print("✅ SETUP COMPLETE!")
            print("="*70)

            print("\n🎯 Next Steps:")
            print("1. python3 data_collector.py  (collect news + markets)")
            print("2. python3 build_training_dataset.py  (create dataset)")
            print("3. python3 research.ipynb  (train model)")
            print("4. python3 trader.py  (start paper trading)")
    else:
        print("\n⚠️  API key test failed. Please check your key.")

if __name__ == '__main__':
    main()
