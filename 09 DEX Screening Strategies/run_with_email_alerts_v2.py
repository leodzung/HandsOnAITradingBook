#!/usr/bin/env python3
"""
Automated DEX Scanner with Email Alerts (v2 - Production Funnel)
=================================================================

Uses the PRODUCTION FUNNEL with:
- CEX listing filter
- Volume/liquidity ratio filters
- Age and liquidity filters
- Comprehensive scoring

Runs via cron to find DEX-only opportunities.
"""

import json
import smtplib
import sys
import time
import requests
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import traceback

from dex_utils import Token, LiquidityPool, TokenMetrics, RiskAnalyzer, DEXDataFetcher
from social_sentiment import SocialSentimentAnalyzer
from team_scam_detector import TeamScamDetector


def load_twitter_config():
    """Load Twitter API configuration (optional)"""
    try:
        with open('twitter_config.json', 'r') as f:
            config = json.load(f)

        token = config.get('twitter_bearer_token', '')
        if token and token != 'YOUR_BEARER_TOKEN_HERE':
            print("✅ Twitter API credentials loaded")
            return {'twitter_bearer_token': token}
        else:
            print("⚠️  Twitter API not configured (using placeholder metrics)")
            return {}
    except FileNotFoundError:
        print("⚠️  twitter_config.json not found (using placeholder metrics)")
        return {}
    except Exception as e:
        print(f"⚠️  Error loading Twitter config: {e}")
        return {}


def load_email_config():
    """Load email configuration"""
    try:
        with open('email_config.json', 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("ERROR: email_config.json not found!")
        print("Please configure email settings first.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in email_config.json: {e}")
        sys.exit(1)


def load_alert_cache():
    """
    Load alert cache from file

    Returns:
        dict: Cache with token addresses and timestamps
    """
    cache_file = 'alert_cache.json'

    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cache = json.load(f)

            # Clean up old entries (older than 2 hours)
            current_time = datetime.now()
            cleaned_cache = {}

            for token_address, alert_data in cache.items():
                alert_time = datetime.fromisoformat(alert_data['timestamp'])
                age = current_time - alert_time

                # Keep entries less than 2 hours old
                if age < timedelta(hours=2):
                    cleaned_cache[token_address] = alert_data

            # Save cleaned cache back
            if len(cleaned_cache) != len(cache):
                with open(cache_file, 'w') as f:
                    json.dump(cleaned_cache, f, indent=2)

            return cleaned_cache
        else:
            return {}

    except Exception as e:
        print(f"⚠️  Error loading alert cache: {e}")
        return {}


def save_alert_cache(cache):
    """
    Save alert cache to file

    Args:
        cache: dict with token addresses and timestamps
    """
    cache_file = 'alert_cache.json'

    try:
        with open(cache_file, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"⚠️  Error saving alert cache: {e}")


def was_recently_alerted(token_address, cache, hours=1):
    """
    Check if a token was alerted on recently

    Args:
        token_address: Token contract address
        cache: Alert cache dict
        hours: Number of hours to check (default: 1)

    Returns:
        bool: True if alerted within the time window
    """
    if token_address not in cache:
        return False

    alert_data = cache[token_address]
    alert_time = datetime.fromisoformat(alert_data['timestamp'])
    current_time = datetime.now()
    age = current_time - alert_time

    return age < timedelta(hours=hours)


def add_to_alert_cache(token_address, token_symbol, score, is_best_available, cache):
    """
    Add a token to the alert cache

    Args:
        token_address: Token contract address
        token_symbol: Token symbol
        score: Composite score
        is_best_available: Whether this was a "best available" alert
        cache: Alert cache dict

    Returns:
        dict: Updated cache
    """
    cache[token_address] = {
        'symbol': token_symbol,
        'timestamp': datetime.now().isoformat(),
        'score': score,
        'is_best_available': is_best_available
    }

    return cache


def send_email(config, subject, body, is_html=False):
    """
    Send email via SMTP

    Args:
        config: Email configuration dict
        subject: Email subject
        body: Email body
        is_html: Whether body is HTML
    """
    email_settings = config['email_settings']

    from_email = email_settings['from_email']
    to_email = email_settings['to_email']
    password = email_settings['smtp_password']
    smtp_server = email_settings['smtp_server']
    smtp_port = email_settings['smtp_port']

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"{email_settings['subject_prefix']} {subject}"
    msg['From'] = from_email
    msg['To'] = to_email

    # Add body
    if is_html:
        msg.attach(MIMEText(body, 'html'))
    else:
        msg.attach(MIMEText(body, 'plain'))

    # Send email
    try:
        print(f"Sending email to {to_email}...")

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()

        print(f"✅ Email sent successfully to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        print("❌ SMTP Authentication failed!")
        print("   Check your email and app password in email_config.json")
        print("   Gmail requires an 'App Password' - see setup instructions")
        return False

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False


def fetch_real_pools():
    """Fetch pools using DexScreener API"""

    print("\n🔍 Fetching pools from DexScreener...")

    session = requests.Session()
    session.headers.update({'User-Agent': 'DEX-Screener/1.0'})

    all_pools = []

    strategies = [
        ('bsc', 'pancakeswap'),
        ('ethereum', 'uniswap'),
        ('bsc', 'WBNB'),
        ('ethereum', 'WETH'),
        ('base', 'base'),
    ]

    for chain, search_term in strategies:
        try:
            url = f"https://api.dexscreener.com/latest/dex/search?q={search_term}"
            response = session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if 'pairs' in data:
                    pairs = data['pairs']
                    chain_pairs = [p for p in pairs if p.get('chainId', '').lower() == chain.lower()]
                    all_pools.extend(chain_pairs)

                    if len(all_pools) >= 50:
                        break

        except Exception as e:
            print(f"   Error: {e}")

        time.sleep(1.5)  # Rate limiting

    # Deduplicate
    seen = set()
    unique_pools = []
    for pool in all_pools:
        addr = pool.get('pairAddress', '')
        if addr and addr not in seen:
            seen.add(addr)
            unique_pools.append(pool)

    print(f"   ✅ Fetched {len(unique_pools)} unique pools")
    return unique_pools


def run_production_funnel():
    """Run the complete funnel with real data - returns qualified opportunities"""

    print("\n" + "="*80)
    print("PRODUCTION DEX SCREENING FUNNEL")
    print("="*80)

    # Configuration
    max_age_hours = 168
    min_liquidity = 30000
    min_volume_24h = 5000
    min_vol_liq_ratio = 0.20
    max_vol_liq_ratio = 10.0
    min_safety_score = 60
    min_opportunity_score = 50
    exclude_cex = True

    print(f"\n⚙️  Filters: Age<{max_age_hours}h, Liq>${min_liquidity:,}, Vol>${min_volume_24h:,}, Vol/Liq {min_vol_liq_ratio*100:.0f}-{max_vol_liq_ratio*100:.0f}%, DEX-only")

    # Step 1: Fetch pools
    raw_pools = fetch_real_pools()

    if len(raw_pools) == 0:
        print("\n❌ No pools fetched")
        return []

    print(f"\n📊 Starting with {len(raw_pools)} pools")

    # Step 2: Age filter
    cutoff_time = time.time() - (max_age_hours * 3600)
    age_passed = [p for p in raw_pools if (p.get('pairCreatedAt', 0) / 1000) >= cutoff_time]
    print(f"   Age filter: {len(age_passed)} passed")

    # Step 3: Liquidity filter
    liq_passed = [p for p in age_passed if float(p.get('liquidity', {}).get('usd', 0)) >= min_liquidity]
    print(f"   Liquidity filter: {len(liq_passed)} passed")

    # Step 4: Volume filter
    vol_passed = []
    for pool in liq_passed:
        liq = float(pool.get('liquidity', {}).get('usd', 0))
        vol = float(pool.get('volume', {}).get('h24', 0))
        vol_liq_ratio = (vol / liq) if liq > 0 else 0

        if vol >= min_volume_24h and min_vol_liq_ratio <= vol_liq_ratio <= max_vol_liq_ratio:
            vol_passed.append(pool)

    print(f"   Volume filter: {len(vol_passed)} passed")

    # Step 5: CEX filter
    fetcher = DEXDataFetcher()
    cex_passed = []

    check_limit = min(20, len(vol_passed))
    print(f"   Checking first {check_limit} pools for CEX listings...")

    for pool in vol_passed[:check_limit]:
        base = pool.get('baseToken', {})
        token_addr = base.get('address', '')
        chain = pool.get('chainId', 'ethereum')

        if not token_addr:
            continue

        cex_data = fetcher.check_cex_listing(token_addr, chain)

        if exclude_cex and cex_data['listed_on_cex']:
            continue
        else:
            cex_passed.append((pool, cex_data))

    print(f"   CEX filter: {len(cex_passed)} passed (DEX-only)")

    # Step 6: Social Sentiment Analysis
    twitter_config = load_twitter_config()
    social_analyzer = SocialSentimentAnalyzer(config=twitter_config)
    social_passed = []

    for pool, cex_data in cex_passed:
        base = pool.get('baseToken', {})
        token_symbol = base.get('symbol', 'UNKNOWN')
        token_addr = base.get('address', '')

        # Analyze social sentiment
        social_sentiment = social_analyzer.analyze_token(
            token_address=token_addr,
            token_symbol=token_symbol,
            dex_pool_data=pool
        )

        social_passed.append((pool, cex_data, social_sentiment))

    print(f"   Social sentiment: Analyzed {len(social_passed)} tokens")

    # NEW Step 7: Team Risk Analysis
    print(f"\n{'─'*80}")
    print("TEAM RISK ANALYSIS (NEW!)")
    print(f"{'─'*80}")

    team_detector = TeamScamDetector()
    team_passed = []
    team_blocked = 0

    for pool, cex_data, social_sentiment in social_passed:
        base = pool.get('baseToken', {})
        token_symbol = base.get('symbol', 'UNKNOWN')
        token_addr = base.get('address', '')
        chain = pool.get('chainId', 'ethereum')

        print(f"\n  🔍 {token_symbol}")

        # Analyze team risk
        team_risk = team_detector.analyze_team(
            token_address=token_addr,
            chain=chain,
            pool_data=pool
        )

        # Auto-block critical risks (score < 40)
        if team_risk.team_score < 40:
            print(f"     ✗ BLOCKED - Critical team risk ({team_risk.team_score:.1f}/100)")
            print(f"       {team_risk.get_risk_description()}")
            team_blocked += 1
            continue

        print(f"     ✓ Team score: {team_risk.team_score:.1f}/100 (Risk: {team_risk.risk_level})")
        team_passed.append((pool, cex_data, social_sentiment, team_risk))

    print(f"\n   ✅ {len(team_passed)} passed team risk filter")
    print(f"   ✗ {team_blocked} blocked (critical team risks)")

    # Steps 8-9: Scoring
    qualified = []

    for pool, cex_data, social_sentiment, team_risk in team_passed:
        base = pool.get('baseToken', {})
        quote = pool.get('quoteToken', {})

        price_change = pool.get('priceChange', {})
        liquidity = float(pool.get('liquidity', {}).get('usd', 0))
        volume = float(pool.get('volume', {}).get('h24', 0))
        created_at = pool.get('pairCreatedAt', int(time.time() * 1000)) / 1000

        metrics = TokenMetrics(
            token_address=base.get('address', ''),
            liquidity_usd=liquidity,
            volume_24h=volume,
            holder_count=100,
            top_10_concentration=35.0,
            honeypot_risk=0.0,
            contract_verified=False,
            buy_tax=0.0,
            sell_tax=0.0,
            liquidity_locked=False,
            creation_time=int(created_at),
            price_change_1h=float(price_change.get('h1', 0) or 0),
            price_change_24h=float(price_change.get('h24', 0) or 0),
            listed_on_cex=cex_data['listed_on_cex'],
            cex_exchanges=cex_data['major_exchanges']
        )

        safety_score = RiskAnalyzer.calculate_safety_score(metrics)
        opp_score = RiskAnalyzer.calculate_opportunity_score(metrics)

        if safety_score < min_safety_score or opp_score < min_opportunity_score:
            continue

        # ENHANCED composite score: 40% safety + 25% opportunity + 15% social + 20% team
        composite = (
            (safety_score * 0.40) +
            (opp_score * 0.25) +
            (social_sentiment.sentiment_score * 0.15) +
            (team_risk.team_score * 0.20)
        )

        # Extract social links from pool info
        info = pool.get('info', {})
        websites = info.get('websites', [])
        socials = info.get('socials', [])

        social_links = {
            'website': websites[0].get('url') if websites else None,
            'twitter': None,
            'telegram': None,
            'discord': None,
            'github': None
        }

        # Parse socials list
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

        # Calculate transparency score
        transparency_score = sum([
            bool(social_links.get('github')),
            bool(social_links.get('website')),
            bool(social_links.get('twitter')),
            bool(social_links.get('telegram'))
        ]) * 25  # 0-100 scale

        qualified.append({
            'symbol': f"{base.get('symbol')}/{quote.get('symbol')}",
            'base_symbol': base.get('symbol'),
            'address': base.get('address'),
            'pair_address': pool.get('pairAddress'),
            'chain': pool.get('chainId'),
            'dex': pool.get('dexId'),
            'liquidity': liquidity,
            'volume': volume,
            'safety': safety_score,
            'opportunity': opp_score,
            'composite': composite,
            'social_sentiment': social_sentiment.sentiment_score,
            'social_tier': social_sentiment.get_tier(),
            'twitter_score': social_sentiment.twitter_score,
            'telegram_score': social_sentiment.telegram_score,
            'bot_farm_detected': social_sentiment.bot_farm_detected,
            'pump_group_detected': social_sentiment.pump_group_detected,
            'no_social_presence': social_sentiment.no_social_presence,
            'cex_listed': False,
            'cex_exchanges': [],
            'price_1h': metrics.price_change_1h,
            'price_24h': metrics.price_change_24h,
            'url': f"https://dexscreener.com/{pool.get('chainId')}/{pool.get('pairAddress')}",
            'token_address': base.get('address'),
            'social_links': social_links,
            'transparency': transparency_score,
            # Team risk data (NEW)
            'team_score': team_risk.team_score,
            'team_risk_level': team_risk.risk_level,
            'team_red_flags': team_risk.red_flags,
            'team_green_flags': team_risk.green_flags,
            'deployer_address': team_risk.deployer_address,
            'deployer_age_days': team_risk.deployer_age_days,
            'previous_tokens': team_risk.previous_tokens,
            'previous_rugs': team_risk.previous_rugs
        })

    qualified.sort(key=lambda x: x['composite'], reverse=True)

    print(f"\n✅ Found {len(qualified)} qualified DEX-only opportunities")

    return qualified


def format_opportunities_email(opportunities, config, is_best_available=False):
    """Format opportunities as HTML email"""

    alert_settings = config['alert_settings']
    min_score = alert_settings['min_score_to_alert']
    max_alerts = alert_settings['max_alerts_per_run']

    # Filter high-quality opportunities
    high_quality = [o for o in opportunities if o['composite'] >= min_score]
    high_quality = high_quality[:max_alerts]

    # Determine what to show
    if is_best_available:
        tokens_to_show = opportunities[:1]
        header_bg = "#FF9800"
        header_title = "📊 DEX Scanner - Best Available Token"
        header_subtitle = f"No qualified opportunities found (threshold: {min_score}). Showing highest scorer:"
    else:
        tokens_to_show = high_quality
        header_bg = "#4CAF50"
        header_title = "🚨 DEX Scanner Alert - DEX-ONLY Opportunities"
        header_subtitle = f"Found {len(high_quality)} High-Quality DEX-Only Tokens"

    if not tokens_to_show:
        return None

    # Build HTML
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; }}
            .header {{ background-color: {header_bg}; color: white; padding: 20px; }}
            .opportunity {{ border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            .score {{ font-size: 24px; font-weight: bold; }}
            .high {{ color: #4CAF50; }}
            .medium {{ color: #FF9800; }}
            .metrics {{ background-color: #f5f5f5; padding: 10px; margin: 10px 0; }}
            .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }}
            .dex-badge {{ background-color: #4CAF50; color: white; padding: 5px 10px; border-radius: 3px; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{header_title}</h1>
            <p>{header_subtitle}</p>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
"""

    for i, opp in enumerate(tokens_to_show, 1):
        score_class = "high" if opp['composite'] >= 80 else "medium"

        html += f"""
        <div class="opportunity">
            <h2>#{i} {opp['symbol']} <span class="dex-badge">🎯 DEX-ONLY</span></h2>
            <div class="score {score_class}">
                Composite Score: {opp['composite']:.1f}/100
            </div>

            <div class="metrics">
                <p><strong>Safety Score:</strong> {opp['safety']:.1f}/100</p>
                <p><strong>Opportunity Score:</strong> {opp['opportunity']:.1f}/100</p>
                <p><strong>Social Sentiment:</strong> {opp['social_sentiment']:.1f}/100 (Tier {opp['social_tier']})</p>
                <p style="margin-left: 20px; font-size: 14px;">
                    Twitter: {opp['twitter_score']:.1f}/100 |
                    Telegram: {opp['telegram_score']:.1f}/100
                </p>
                <p><strong>Team Score:</strong> {opp.get('team_score', 70):.1f}/100 (Risk: {opp.get('team_risk_level', 'UNKNOWN')})</p>
                <p><strong>Liquidity:</strong> ${opp['liquidity']:,.0f}</p>
                <p><strong>24h Volume:</strong> ${opp['volume']:,.0f}</p>
                <p><strong>Vol/Liq Ratio:</strong> {(opp['volume']/opp['liquidity']*100):.1f}%</p>
                <p><strong>Price Change:</strong> 1h: {opp['price_1h']:+.1f}%, 24h: {opp['price_24h']:+.1f}%</p>
                <p><strong>Chain:</strong> {opp['chain'].upper()}</p>
                <p><strong>DEX:</strong> {opp['dex']}</p>
            </div>

            <p><strong>Token Address:</strong><br>
            <code>{opp['token_address']}</code></p>

            <h3>📊 Chart & Verification:</h3>
            <p>
                <a href="{opp['url']}">📊 View Chart on DexScreener</a><br>
                <a href="https://honeypot.is/?address={opp['token_address']}">🔍 Check Honeypot</a><br>
            </p>
"""

        # Add social links section
        social_links = opp.get('social_links', {})
        transparency_score = opp.get('transparency', 0)
        base_symbol = opp.get('base_symbol', opp['symbol'].split('/')[0])

        has_github = bool(social_links.get('github'))
        has_website = bool(social_links.get('website'))
        has_twitter = bool(social_links.get('twitter'))
        has_telegram = bool(social_links.get('telegram'))

        # Determine transparency level
        if transparency_score >= 75:
            transparency_level = "HIGH"
            transparency_color = "#4CAF50"
            transparency_emoji = "✅"
        elif transparency_score >= 50:
            transparency_level = "MEDIUM"
            transparency_color = "#FF9800"
            transparency_emoji = "⚠️"
        else:
            transparency_level = "LOW"
            transparency_color = "#f44336"
            transparency_emoji = "🚨"

        # Add risk flags section if any detected
        has_risk_flags = (opp.get('bot_farm_detected', False) or
                         opp.get('pump_group_detected', False) or
                         opp.get('no_social_presence', False))

        if has_risk_flags:
            html += """
            <div style="background-color: #fff3cd; padding: 15px; margin: 15px 0; border-left: 4px solid #ffc107;">
                <h3>⚠️ Social Sentiment Risk Flags</h3>
                <ul style="margin: 10px 0;">
"""
            if opp.get('bot_farm_detected', False):
                html += "                    <li>🚨 <strong>Bot Farm Detected:</strong> High percentage of bot accounts in social channels</li>\n"
            if opp.get('pump_group_detected', False):
                html += "                    <li>🚨 <strong>Pump Group Detected:</strong> Coordinated messaging patterns detected</li>\n"
            if opp.get('no_social_presence', False):
                html += "                    <li>⚠️ <strong>No Social Presence:</strong> No Twitter or Telegram found</li>\n"

            html += """
                </ul>
                <p style="font-size: 14px; color: #856404;">
                    <strong>Warning:</strong> These risk flags may indicate potential scam or manipulation.
                    Exercise extreme caution and do additional research.
                </p>
            </div>
"""

        # Add team risk assessment section (NEW)
        team_score = opp.get('team_score', 70)
        team_risk_level = opp.get('team_risk_level', 'UNKNOWN')
        team_red_flags = opp.get('team_red_flags', [])
        team_green_flags = opp.get('team_green_flags', [])
        deployer_address = opp.get('deployer_address', None)
        deployer_age_days = opp.get('deployer_age_days', 0)
        previous_tokens = opp.get('previous_tokens', 0)
        previous_rugs = opp.get('previous_rugs', 0)

        # Determine team risk color and emoji
        if team_risk_level == 'CRITICAL':
            team_color = "#d32f2f"
            team_emoji = "🚨"
        elif team_risk_level == 'HIGH':
            team_color = "#f44336"
            team_emoji = "⚠️"
        elif team_risk_level == 'MEDIUM':
            team_color = "#FF9800"
            team_emoji = "⚠️"
        else:
            team_color = "#4CAF50"
            team_emoji = "✅"

        html += f"""
            <div style="background-color: #f8f9fa; padding: 15px; margin: 15px 0; border-left: 4px solid {team_color};">
                <h3>{team_emoji} Team Risk Assessment: {team_risk_level}</h3>
                <p><strong>Team Score: {team_score:.1f}/100</strong></p>
"""

        if deployer_address:
            html += f"""
                <div style="background-color: #fff; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>Deployer Info:</strong><br>
                    <span style="font-size: 14px;">
                    Address: <code>{deployer_address[:10]}...{deployer_address[-8:]}</code><br>
                    Wallet Age: {deployer_age_days} days<br>
                    Previous Tokens: {previous_tokens}
"""
            if previous_rugs > 0:
                html += f"                    <br><span style='color: #d32f2f;'><strong>⚠️ Previous Rugpulls: {previous_rugs}</strong></span>"

            html += """
                    </span>
                </div>
"""

        if team_red_flags:
            html += """
                <div style="background-color: #ffebee; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>🚨 Team Red Flags:</strong><br>
                    <ul style="margin: 5px 0; padding-left: 20px; font-size: 14px;">
"""
            for flag in team_red_flags:
                html += f"                        <li>{flag}</li>\n"

            html += """
                    </ul>
                </div>
"""

        if team_green_flags:
            html += """
                <div style="background-color: #e8f5e9; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>✅ Team Green Flags:</strong><br>
                    <ul style="margin: 5px 0; padding-left: 20px; font-size: 14px;">
"""
            for flag in team_green_flags:
                html += f"                        <li>{flag}</li>\n"

            html += """
                    </ul>
                </div>
"""

        if team_risk_level in ['CRITICAL', 'HIGH']:
            html += """
                <div style="background-color: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>⚠️ HIGH TEAM RISK WARNING</strong><br>
                    <span style="font-size: 14px; color: #856404;">
                    This token has significant team-related red flags. The deployer wallet shows
                    patterns commonly associated with scam projects. Exercise extreme caution and
                    consider avoiding this opportunity unless you can verify the team's legitimacy.
                    </span>
                </div>
"""

        html += """
            </div>
"""

        html += f"""
            <div style="background-color: #f8f9fa; padding: 15px; margin: 15px 0; border-left: 4px solid {transparency_color};">
                <h3>{transparency_emoji} Developer Transparency: {transparency_level}</h3>
                <p><strong>Transparency Score: {transparency_score}/100</strong></p>
                <ul style="margin: 10px 0;">
                    <li>{'✅' if has_github else '❌'} Official GitHub Repository</li>
                    <li>{'✅' if has_website else '❌'} Official Website</li>
                    <li>{'✅' if has_twitter else '❌'} Official Twitter</li>
                    <li>{'✅' if has_telegram else '❌'} Official Telegram</li>
                </ul>
"""

        if not has_github:
            html += """
                <div style="background-color: #fff3cd; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>🚨 HIGH RISK: No GitHub Repository</strong><br>
                    <span style="font-size: 14px;">
                    Without a GitHub repo, you cannot verify:<br>
                    • Developer activity/commit history<br>
                    • Code quality and security<br>
                    • Team size and expertise<br>
                    • Active maintenance<br>
                    <strong>This significantly increases rug pull risk!</strong>
                    </span>
                </div>
"""
        else:
            html += f"""
                <div style="background-color: #d4edda; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>✅ GitHub Available</strong><br>
                    <span style="font-size: 14px;">
                    <a href="{social_links['github']}">View Repository →</a><br>
                    Review for recent commits, multiple contributors, and security measures.
                    </span>
                </div>
"""

        html += """
            </div>

            <h3>🔗 Social Media & Resources:</h3>
            <p>
"""

        if social_links.get('website'):
            html += f'                <a href="{social_links["website"]}">🌐 Official Website</a><br>\n'

        if social_links.get('twitter'):
            html += f'                <a href="{social_links["twitter"]}">🐦 Twitter</a><br>\n'
        else:
            html += f'                <a href="https://twitter.com/search?q=%24{base_symbol}">🐦 Search Twitter for ${base_symbol}</a> (no official link)<br>\n'

        if social_links.get('telegram'):
            html += f'                <a href="{social_links["telegram"]}">💬 Telegram</a><br>\n'

        if social_links.get('discord'):
            html += f'                <a href="{social_links["discord"]}">💬 Discord</a><br>\n'

        if social_links.get('github'):
            html += f'                <a href="{social_links["github"]}">💻 GitHub Repository</a><br>\n'
        else:
            html += f'                <a href="https://github.com/search?q={base_symbol}&type=repositories">💻 Search GitHub for {base_symbol}</a> (no official link)<br>\n'

        html += f"""
                <a href="https://www.google.com/search?q=%22{base_symbol}%22+token+crypto">🔍 Google Search: {base_symbol}</a><br>
            </p>
        </div>
"""

    html += """
        <div class="warning">
            <h3>⚠️ IMPORTANT - DEX-Only Tokens Are HIGH RISK</h3>
            <p><strong>These tokens are NOT on major centralized exchanges.</strong></p>
            <p>This means:</p>
            <ul>
                <li>✅ Early opportunity (before CEX listing)</li>
                <li>⚠️ Higher rug pull risk</li>
                <li>⚠️ Lower liquidity (harder to sell large amounts)</li>
                <li>⚠️ Less vetted by exchanges</li>
            </ul>
            <p><strong>ALWAYS verify:</strong></p>
            <ol>
                <li>Check honeypot.is (ensure 0% sell tax)</li>
                <li>Review contract on explorer</li>
                <li>Check holder distribution</li>
                <li>Verify liquidity lock</li>
                <li>Start with SMALL amounts ($50-100 max)</li>
            </ol>
        </div>

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            Automated alert from DEX Scanner (Production Funnel v2)<br>
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        </p>
    </body>
    </html>
"""

    return html


def main():
    """Main function to run strategy and send alerts"""

    print("\n" + "="*80)
    print(f"DEX SCANNER - AUTOMATED RUN (Production Funnel)")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    # Load config
    try:
        config = load_email_config()
        print("✅ Email configuration loaded")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    # Run production funnel
    try:
        print("\n🔍 Running production funnel...")
        opportunities = run_production_funnel()
        print(f"\n✅ Scan complete. Found {len(opportunities)} DEX-only opportunities")

    except Exception as e:
        print(f"❌ Error running strategy: {e}")
        traceback.print_exc()

        # Send error email
        subject = "ERROR: Scanner Failed"
        body = f"""
The DEX scanner encountered an error:

{str(e)}

Traceback:
{traceback.format_exc()}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_email(config, subject, body, is_html=False)
        sys.exit(1)

    # Send alerts
    if opportunities:
        alert_settings = config['alert_settings']
        min_score = alert_settings['min_score_to_alert']

        # Sort by composite score
        opportunities.sort(key=lambda x: x['composite'], reverse=True)

        # Filter high-quality
        high_quality = [o for o in opportunities if o['composite'] >= min_score]

        # Load alert cache
        alert_cache = load_alert_cache()

        if high_quality:
            print(f"\n📧 Found {len(high_quality)} opportunities above threshold ({min_score})")
            print("Sending email alert...")

            subject = f"Found {len(high_quality)} DEX-Only Tokens!"
            html_body = format_opportunities_email(opportunities, config, is_best_available=False)

            if html_body:
                success = send_email(config, subject, html_body, is_html=True)

                if success:
                    print("✅ Alert sent successfully!")

                    # Cache all high-quality opportunities
                    for opp in high_quality[:max_alerts]:
                        alert_cache = add_to_alert_cache(
                            opp['token_address'],
                            opp['symbol'],
                            opp['composite'],
                            is_best_available=False,
                            cache=alert_cache
                        )

                    save_alert_cache(alert_cache)
                else:
                    print("❌ Failed to send alert")
                    sys.exit(1)
        else:
            highest = opportunities[0]
            print(f"\n📊 No opportunities above threshold ({min_score})")
            print(f"Highest scorer: {highest['symbol']} with {highest['composite']:.1f}/100")

            # Check if this token was recently alerted on (within 1 hour)
            token_address = highest['token_address']

            if was_recently_alerted(token_address, alert_cache, hours=1):
                last_alert = alert_cache[token_address]
                alert_time = datetime.fromisoformat(last_alert['timestamp'])
                minutes_ago = (datetime.now() - alert_time).total_seconds() / 60

                print(f"⏭️  Skipping 'best available' email - {highest['symbol']} was alerted {minutes_ago:.0f} minutes ago")
                print(f"   (Previous alert: {alert_time.strftime('%H:%M:%S')}, Score: {last_alert['score']:.1f}/100)")
                print("   Will retry next scan cycle (10 minutes)")
            else:
                print("Sending 'best available' email...")

                subject = f"Market Update - Best Available: {highest['symbol']} ({highest['composite']:.1f}/100)"
                html_body = format_opportunities_email(opportunities, config, is_best_available=True)

                if html_body:
                    success = send_email(config, subject, html_body, is_html=True)

                    if success:
                        print("✅ Market update email sent!")

                        # Cache the "best available" alert
                        alert_cache = add_to_alert_cache(
                            token_address,
                            highest['symbol'],
                            highest['composite'],
                            is_best_available=True,
                            cache=alert_cache
                        )

                        save_alert_cache(alert_cache)
                    else:
                        print("❌ Failed to send email")
                        sys.exit(1)
    else:
        print("\nℹ️  No DEX-only opportunities found this scan")
        print("No email sent.")

    print(f"\n{'='*80}")
    print(f"Scan completed successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
