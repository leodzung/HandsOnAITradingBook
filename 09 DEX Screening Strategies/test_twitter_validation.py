#!/usr/bin/env python3
"""
Test Twitter account validation features
"""

import json
from social_sentiment import SocialSentimentAnalyzer

def test_validation():
    print("\n" + "="*60)
    print("TWITTER ACCOUNT VALIDATION TEST")
    print("="*60)

    # Load Twitter config
    try:
        with open('twitter_config.json', 'r') as f:
            config = json.load(f)
        print("\n✅ Twitter API config loaded")
    except FileNotFoundError:
        print("\n⚠️  No twitter_config.json - will use placeholder validation")
        config = {}

    # Initialize analyzer
    analyzer = SocialSentimentAnalyzer(config)

    # Test with a mock Twitter URL
    test_cases = [
        {
            'url': 'https://twitter.com/CommunityofBNB',
            'symbol': 'cBNB'
        },
        {
            'url': 'https://x.com/askbrain_AI',
            'symbol': 'BRAIN'
        }
    ]

    for test in test_cases:
        print(f"\n{'─'*60}")
        print(f"Testing: {test['symbol']}")
        print(f"URL: {test['url']}")
        print(f"{'─'*60}")

        # Analyze Twitter account
        metrics = analyzer.analyze_twitter_simple(test['url'], test['symbol'])

        # Display results
        print(f"\n📊 RESULTS:")
        print(f"   Twitter Score: {metrics.calculate_score():.1f}/100")
        print(f"   Legitimacy Score: {metrics.legitimacy_score:.1f}/100")
        print(f"\n   Account Details:")
        print(f"   - Followers: {metrics.follower_count:,}")
        print(f"   - Following: {metrics.following_count:,}")
        print(f"   - Total Tweets: {metrics.total_tweets:,}")
        print(f"   - Account Age: {metrics.account_age_days} days")
        print(f"   - F/F Ratio: {metrics.following_follower_ratio:.2f}")
        print(f"   - Verified: {'✅' if metrics.verified else '❌'}")
        print(f"   - Has Profile Image: {'✅' if metrics.has_profile_image else '❌'}")
        print(f"   - Has Bio: {'✅' if metrics.has_bio else '❌'}")

        if metrics.validation_green_flags:
            print(f"\n   ✅ GREEN FLAGS:")
            for flag in metrics.validation_green_flags:
                print(f"      • {flag}")

        if metrics.validation_red_flags:
            print(f"\n   🚨 RED FLAGS:")
            for flag in metrics.validation_red_flags:
                print(f"      • {flag}")

        # Verdict
        print(f"\n   VERDICT:")
        if metrics.legitimacy_score >= 70:
            print(f"      ✅ LEGITIMATE - Account appears genuine")
        elif metrics.legitimacy_score >= 50:
            print(f"      ⚠️  QUESTIONABLE - Some concerns detected")
        else:
            print(f"      🚨 SUSPICIOUS - Likely fake or bot account")

    print(f"\n{'='*60}")
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    test_validation()
