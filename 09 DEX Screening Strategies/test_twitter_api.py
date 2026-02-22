#!/usr/bin/env python3
"""
Quick test to verify Twitter API credentials
"""

import json
import requests

def test_twitter_api():
    """Test Twitter API Bearer Token"""

    print("\n" + "="*60)
    print("TWITTER API CREDENTIALS TEST")
    print("="*60)

    # Load config
    try:
        with open('twitter_config.json', 'r') as f:
            config = json.load(f)

        bearer_token = config.get('twitter_bearer_token', '')

        if not bearer_token or bearer_token == 'YOUR_BEARER_TOKEN_HERE':
            print("\n❌ ERROR: No Bearer Token configured")
            return False

        print("\n✅ Bearer Token loaded from config")
        print(f"   Token preview: {bearer_token[:20]}...{bearer_token[-10:]}")

    except FileNotFoundError:
        print("\n❌ ERROR: twitter_config.json not found")
        return False
    except Exception as e:
        print(f"\n❌ ERROR loading config: {e}")
        return False

    # Test API with a simple rate limit check (doesn't require elevated access)
    print("\n🔍 Testing API access level...")

    try:
        # First, try to check rate limit status (works with any access)
        url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
        headers = {
            'Authorization': f'Bearer {bearer_token}',
            'User-Agent': 'DEX-Token-Screener/1.0'
        }
        params = {
            'resources': 'users,search'
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            print("\n✅ BASIC API ACCESS CONFIRMED")
            data = response.json()

            # Check what endpoints are available
            resources = data.get('resources', {})
            print(f"\n📊 Available Endpoints:")

            for category, endpoints in resources.items():
                print(f"\n  {category.upper()}:")
                for endpoint, limits in endpoints.items():
                    remaining = limits.get('remaining', 0)
                    limit = limits.get('limit', 0)
                    print(f"    {endpoint}: {remaining}/{limit} remaining")

            print("\n⚠️  NOTE: Twitter has restricted free tier access")
            print("   Free tier no longer has access to v2 API endpoints")
            print("   Will use placeholder data for now")

            return True

        # If rate limit check fails, try v2 API
        print("\n🔍 Trying v2 API endpoints...")
        url = "https://api.twitter.com/2/users/by/username/Twitter"
        headers = {
            'Authorization': f'Bearer {bearer_token}',
            'User-Agent': 'DEX-Token-Screener/1.0'
        }
        params = {
            'user.fields': 'public_metrics,created_at,verified'
        }

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            user = data.get('data', {})

            print("\n✅ API CONNECTION SUCCESSFUL!")
            print("\n📊 Test Results (Twitter's Official Account):")
            print(f"   Username: @{user.get('username', 'N/A')}")
            print(f"   Name: {user.get('name', 'N/A')}")
            print(f"   Followers: {user.get('public_metrics', {}).get('followers_count', 0):,}")
            print(f"   Following: {user.get('public_metrics', {}).get('following_count', 0):,}")
            print(f"   Verified: {user.get('verified', False)}")
            print(f"   Created: {user.get('created_at', 'N/A')}")

            print("\n✅ Your Twitter API is ready to use!")
            print("   Next: Run the production screener to see real social data")

            return True

        elif response.status_code == 401:
            print("\n❌ AUTHENTICATION FAILED")
            print("   Error: Invalid Bearer Token")
            print("   Solution: Check your token in twitter_config.json")
            print("   Token should start with: AAAAAAAAAAAAAAAA...")
            return False

        elif response.status_code == 429:
            print("\n⚠️  RATE LIMIT EXCEEDED")
            print("   You've hit Twitter's rate limit")
            print("   Wait 15 minutes and try again")
            return False

        else:
            print(f"\n❌ API ERROR: Status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

    except requests.exceptions.Timeout:
        print("\n❌ TIMEOUT: Twitter API did not respond")
        print("   Check your internet connection")
        return False

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        return False

if __name__ == "__main__":
    success = test_twitter_api()

    if success:
        print("\n" + "="*60)
        print("🎉 SUCCESS! Twitter API is configured correctly")
        print("="*60)
        print("\nNext steps:")
        print("  1. Run: python3 run_with_email_alerts_v2.py")
        print("  2. Watch for real Twitter data in the console")
        print("  3. Check your email for alerts with real metrics")
        print()
    else:
        print("\n" + "="*60)
        print("❌ SETUP INCOMPLETE")
        print("="*60)
        print("\nTroubleshooting:")
        print("  1. Verify your Bearer Token is correct")
        print("  2. Check twitter_config.json formatting")
        print("  3. See TWITTER_API_SETUP_GUIDE.md for help")
        print()
