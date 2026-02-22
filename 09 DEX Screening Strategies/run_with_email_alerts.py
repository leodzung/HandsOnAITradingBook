#!/usr/bin/env python3
"""
Automated DEX Scanner with Email Alerts
========================================

Runs the strategy and sends email alerts when high-quality opportunities are found.
Designed to run via cron job hourly during active trading hours.
"""

import json
import smtplib
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import traceback

# Import the Moralis auto-discovery strategy
# Note: Falls back to DexScreener if Moralis API key not configured
from run_moralis_discovery import discover_and_analyze as fetch_and_analyze


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


def format_opportunities_email(opportunities, config, is_best_available=False):
    """Format opportunities as HTML email

    Args:
        opportunities: List of opportunity dicts
        config: Email configuration
        is_best_available: If True, this is "best available" not "qualified"
    """

    alert_settings = config['alert_settings']
    min_score = alert_settings['min_score_to_alert']
    max_alerts = alert_settings['max_alerts_per_run']

    # Filter high-quality opportunities
    high_quality = [o for o in opportunities if o['composite'] >= min_score]
    high_quality = high_quality[:max_alerts]  # Limit number of alerts

    # Determine what to show
    if is_best_available:
        # Show the top scorer even if below threshold
        tokens_to_show = opportunities[:1]  # Just the highest scorer
        header_bg = "#FF9800"  # Orange for "best available"
        header_title = "📊 DEX Scanner - Best Available Token"
        header_subtitle = f"No qualified opportunities found (threshold: {min_score}). Showing highest scorer:"
    else:
        tokens_to_show = high_quality
        header_bg = "#4CAF50"  # Green for qualified
        header_title = "🚨 DEX Scanner Alert"
        header_subtitle = f"Found {len(high_quality)} High-Quality Opportunities"

    if not tokens_to_show:
        return None

    # Build HTML email
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
            .low {{ color: #f44336; }}
            .metrics {{ background-color: #f5f5f5; padding: 10px; margin: 10px 0; }}
            .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; margin: 10px 0; }}
            .info {{ background-color: #d1ecf1; border-left: 4px solid #0dcaf0; padding: 10px; margin: 10px 0; }}
            .link {{ color: #2196F3; text-decoration: none; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{header_title}</h1>
            <p>{header_subtitle}</p>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
"""

    if is_best_available:
        html += f"""
        <div class="info">
            <h3>ℹ️ Market Update</h3>
            <p><strong>This is NOT a qualified opportunity.</strong> The highest scoring token found
            is below the quality threshold ({min_score}). Showing for informational purposes only.</p>
            <p>Consider waiting for better opportunities or review the scoring criteria.</p>
        </div>
"""

    for i, opp in enumerate(tokens_to_show, 1):
        if opp['composite'] >= 80:
            score_class = "high"
        elif opp['composite'] >= min_score:
            score_class = "medium"
        else:
            score_class = "low"

        html += f"""
        <div class="opportunity">
            <h2>#{i} {opp['symbol']}</h2>
            <div class="score {score_class}">
                Composite Score: {opp['composite']:.1f}/100
            </div>

            <div class="metrics">
                <p><strong>Safety Score:</strong> {opp['safety']:.1f}/100</p>
                <p><strong>Opportunity Score:</strong> {opp['opportunity']:.1f}/100</p>
                <p><strong>Transparency Score:</strong> {opp.get('transparency', 0):.1f}/100</p>
                <p><strong>Liquidity:</strong> ${opp['liquidity']:,.0f}</p>
                <p><strong>24h Volume:</strong> ${opp['volume']:,.0f}</p>
                <p><strong>Price Change:</strong> 1h: {opp['price_1h']:+.1f}%, 24h: {opp['price_24h']:+.1f}%</p>
                <p><strong>DEX:</strong> {opp['dex']}</p>
            </div>

            <p><strong>Token Address:</strong><br>
            <code>{opp['token_address']}</code></p>

            <h3>📊 Chart & Verification:</h3>
            <p>
                <a href="{opp['url']}" class="link">📊 View Chart on DexScreener</a><br>
                <a href="https://honeypot.is/?address={opp['token_address']}" class="link">🔍 Check Honeypot</a><br>
                <a href="https://bscscan.com/address/{opp['token_address']}" class="link">🔎 View on BSCScan</a>
            </p>
"""

        # Add developer activity assessment
        social_links = opp.get('social_links', {})
        base_symbol = opp.get('base_symbol', opp['symbol'].split('/')[0])
        has_github = bool(social_links.get('github'))
        has_website = bool(social_links.get('website'))
        has_twitter = bool(social_links.get('twitter'))
        has_telegram = bool(social_links.get('telegram'))

        # Calculate transparency score
        transparency_items = [has_github, has_website, has_twitter, has_telegram]
        transparency_score = sum(transparency_items)

        if transparency_score >= 3:
            transparency_level = "HIGH"
            transparency_color = "#4CAF50"
            transparency_emoji = "✅"
        elif transparency_score == 2:
            transparency_level = "MEDIUM"
            transparency_color = "#FF9800"
            transparency_emoji = "⚠️"
        else:
            transparency_level = "LOW"
            transparency_color = "#f44336"
            transparency_emoji = "🚨"

        html += f"""
            <div style="background-color: #f8f9fa; padding: 15px; margin: 15px 0; border-left: 4px solid {transparency_color};">
                <h3>{transparency_emoji} Developer Transparency: {transparency_level}</h3>
                <p><strong>Transparency Score: {transparency_score}/4</strong></p>
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
            html += """
                <div style="background-color: #d4edda; padding: 10px; margin: 10px 0; border-radius: 5px;">
                    <strong>✅ GitHub Available</strong><br>
                    <span style="font-size: 14px;">
                    Review the repository for:<br>
                    • Recent commits (last 7-30 days)<br>
                    • Multiple contributors<br>
                    • Professional documentation<br>
                    • Security measures
                    </span>
                </div>
"""

        html += """
            </div>

            <h3>🔗 Social Media & Resources:</h3>
            <p>
"""

        if social_links.get('website'):
            html += f'                <a href="{social_links["website"]}" class="link">🌐 Official Website</a><br>\n'

        if social_links.get('twitter'):
            html += f'                <a href="{social_links["twitter"]}" class="link">🐦 Twitter</a><br>\n'
        else:
            # Provide search link
            html += f'                <a href="https://twitter.com/search?q=%24{base_symbol}" class="link">🐦 Search Twitter for ${base_symbol}</a> (no official link)<br>\n'

        if social_links.get('telegram'):
            html += f'                <a href="{social_links["telegram"]}" class="link">💬 Telegram</a><br>\n'

        if social_links.get('discord'):
            html += f'                <a href="{social_links["discord"]}" class="link">💬 Discord</a><br>\n'

        if social_links.get('github'):
            html += f'                <a href="{social_links["github"]}" class="link">💻 GitHub Repository</a><br>\n'
        else:
            html += f'                <a href="https://github.com/search?q={base_symbol}&type=repositories" class="link">💻 Search GitHub for {base_symbol}</a> (no official link)<br>\n'

        # Add general search link
        html += f'                <a href="https://www.google.com/search?q=%22{base_symbol}%22+token+crypto" class="link">🔍 Google Search: {base_symbol}</a><br>\n'

        html += """
            </p>
        </div>
"""

    html += """
        <div class="warning">
            <h3>⚠️ IMPORTANT - Verify Before Buying</h3>
            <p><strong>Follow this checklist for EVERY token:</strong></p>
            <ol>
                <li>✓ <strong>Honeypot Check:</strong> Click honeypot.is link - ensure 0% sell tax</li>
                <li>✓ <strong>Contract Review:</strong> Check BSCScan - verify contract, holders, recent transactions</li>
                <li>✓ <strong>GitHub:</strong> If repo exists, check recent commits (active development is good)</li>
                <li>✓ <strong>Twitter/Social:</strong> Check followers, engagement, verify authenticity (not fake accounts)</li>
                <li>✓ <strong>Telegram/Discord:</strong> Join community, assess activity level and legitimacy</li>
                <li>✓ <strong>Team:</strong> Are developers doxxed? Anonymous teams = higher risk</li>
                <li>✓ <strong>Liquidity Lock:</strong> Check if liquidity is locked on Unicrypt or similar</li>
                <li>✓ <strong>Audit:</strong> Has contract been audited? By whom?</li>
            </ol>
            <p><strong>⚠️ Risk Warnings:</strong></p>
            <ul>
                <li>90% of early-stage tokens fail completely</li>
                <li>Start with small amounts only ($50-100 max)</li>
                <li>Never invest more than you can afford to lose</li>
                <li>This is NOT financial advice - DYOR (Do Your Own Research)</li>
            </ul>
        </div>

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            Automated alert from DEX Scanner<br>
            Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        </p>
    </body>
    </html>
"""

    return html


def main():
    """Main function to run strategy and send alerts"""

    print("\n" + "="*80)
    print(f"DEX SCANNER - AUTOMATED RUN")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    # Load config
    try:
        config = load_email_config()
        print("✅ Email configuration loaded")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    # Run strategy
    try:
        print("\n🔍 Running DEX scanner...")
        opportunities = fetch_and_analyze()
        print(f"\n✅ Scan complete. Found {len(opportunities)} opportunities")

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

        # Sort by composite score (highest first)
        opportunities.sort(key=lambda x: x['composite'], reverse=True)

        # Filter high-quality opportunities
        high_quality = [o for o in opportunities if o['composite'] >= min_score]

        if high_quality:
            # We have qualified opportunities - send regular alert
            print(f"\n📧 Found {len(high_quality)} opportunities above threshold ({min_score})")
            print("Sending email alert...")

            subject = f"Found {len(high_quality)} High-Quality Tokens!"
            html_body = format_opportunities_email(opportunities, config, is_best_available=False)

            if html_body:
                success = send_email(config, subject, html_body, is_html=True)

                if success:
                    print("✅ Alert sent successfully!")
                else:
                    print("❌ Failed to send alert")
                    sys.exit(1)
        else:
            # No qualified opportunities - send "best available"
            highest = opportunities[0]
            print(f"\n📊 No opportunities above threshold ({min_score})")
            print(f"Highest scorer: {highest['symbol']} with {highest['composite']:.1f}/100")
            print("Sending 'best available' email...")

            subject = f"Market Update - Best Available: {highest['symbol']} ({highest['composite']:.1f}/100)"
            html_body = format_opportunities_email(opportunities, config, is_best_available=True)

            if html_body:
                success = send_email(config, subject, html_body, is_html=True)

                if success:
                    print("✅ Market update email sent!")
                else:
                    print("❌ Failed to send email")
                    sys.exit(1)
    else:
        print("\nℹ️  No opportunities found this scan")
        print("No email sent.")

    # Log completion
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
