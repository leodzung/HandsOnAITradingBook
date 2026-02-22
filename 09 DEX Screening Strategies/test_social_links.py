"""
Test Social Link Extraction
Shows what social links DexScreener provides
"""

import requests
import json

# Fetch a sample pool from DexScreener
url = "https://api.dexscreener.com/latest/dex/search?q=WBNB"

try:
    response = requests.get(url, timeout=10)

    if response.status_code == 200:
        data = response.json()

        if 'pairs' in data and len(data['pairs']) > 0:
            # Get first BSC pool with social links
            bsc_pools = [p for p in data['pairs'] if p.get('chainId') == 'bsc']

            print("="*80)
            print("SOCIAL LINK EXTRACTION TEST")
            print("="*80)

            for pool in bsc_pools[:3]:
                base = pool.get('baseToken', {})
                quote = pool.get('quoteToken', {})

                print(f"\n{'='*80}")
                print(f"Token: {base.get('symbol')}/{quote.get('symbol')}")
                print(f"{'='*80}")

                # Extract social links
                info = pool.get('info', {})
                websites = info.get('websites', [])
                socials = info.get('socials', [])

                print(f"\n📋 Raw Info Object:")
                print(f"   Websites: {len(websites)} found")
                print(f"   Socials: {len(socials)} found")

                if websites:
                    print(f"\n🌐 Websites:")
                    for site in websites:
                        print(f"   • {site.get('url')}")

                if socials:
                    print(f"\n📱 Social Links:")
                    for social in socials:
                        social_type = social.get('type', 'unknown')
                        social_url = social.get('url', '')
                        print(f"   • {social_type}: {social_url}")

                # Build social links dict (same as in v2 script)
                social_links = {
                    'website': websites[0].get('url') if websites else None,
                    'twitter': None,
                    'telegram': None,
                    'discord': None,
                    'github': None
                }

                for social in socials:
                    social_type = social.get('type', '').lower()
                    social_url = social.get('url', '')
                    if social_type == 'twitter':
                        social_links['twitter'] = social_url
                    elif social_type == 'telegram':
                        social_links['telegram'] = social_url
                    elif social_type == 'discord':
                        social_links['discord'] = social_url
                    elif social_type == 'github':
                        social_links['github'] = social_url

                # Calculate transparency
                transparency_score = sum([
                    bool(social_links.get('github')),
                    bool(social_links.get('website')),
                    bool(social_links.get('twitter')),
                    bool(social_links.get('telegram'))
                ]) * 25

                print(f"\n✅ Extracted Social Links:")
                print(f"   Website:  {social_links['website'] or '❌ None'}")
                print(f"   Twitter:  {social_links['twitter'] or '❌ None'}")
                print(f"   Telegram: {social_links['telegram'] or '❌ None'}")
                print(f"   Discord:  {social_links['discord'] or '❌ None'}")
                print(f"   GitHub:   {social_links['github'] or '❌ None'}")

                print(f"\n📊 Transparency Score: {transparency_score}/100")

                if transparency_score >= 75:
                    print(f"   ✅ HIGH transparency (3-4 links)")
                elif transparency_score >= 50:
                    print(f"   ⚠️  MEDIUM transparency (2 links)")
                elif transparency_score >= 25:
                    print(f"   ⚠️  LOW transparency (1 link)")
                else:
                    print(f"   🚨 NO transparency (0 links) - HIGH RISK!")

                print()

        else:
            print("No pools found")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
