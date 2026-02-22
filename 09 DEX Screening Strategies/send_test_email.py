#!/usr/bin/env python3
"""
Send Test Email
===============
Simple script to test email configuration
"""

import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Load config
with open('email_config.json', 'r') as f:
    config = json.load(f)

email_settings = config['email_settings']

# Email details
from_email = email_settings['from_email']
to_email = email_settings['to_email']
password = email_settings['smtp_password']
smtp_server = email_settings['smtp_server']
smtp_port = email_settings['smtp_port']

print("="*80)
print("SENDING TEST EMAIL")
print("="*80)
print(f"\nFrom: {from_email}")
print(f"To: {to_email}")
print(f"Server: {smtp_server}:{smtp_port}")
print()

# Create message
msg = MIMEMultipart('alternative')
msg['Subject'] = f"{email_settings['subject_prefix']} TEST EMAIL - Setup Successful!"
msg['From'] = from_email
msg['To'] = to_email

# HTML body
html = f"""
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .success {{ background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin: 15px 0; }}
        .info {{ background-color: #d1ecf1; border-left: 4px solid #0dcaf0; padding: 15px; margin: 15px 0; }}
        .code {{ background-color: #f5f5f5; padding: 10px; font-family: monospace; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>✅ DEX Scanner Test Email</h1>
        <p>Your automated scanner is configured correctly!</p>
    </div>

    <div class="content">
        <div class="success">
            <h2>✅ Email Configuration Working!</h2>
            <p>If you're reading this, your DEX scanner email system is set up correctly.</p>
        </div>

        <div class="info">
            <h3>📊 Your Configuration:</h3>
            <ul>
                <li><strong>Alerts sent to:</strong> {to_email}</li>
                <li><strong>Sent from:</strong> {from_email}</li>
                <li><strong>Alert threshold:</strong> Composite score ≥ 70</li>
                <li><strong>Schedule:</strong> Every hour, 9AM-6PM UTC, Mon-Fri</li>
            </ul>
        </div>

        <h3>🔔 What Happens Next:</h3>
        <ol>
            <li>Your scanner runs automatically every hour during peak trading times</li>
            <li>When high-quality tokens are found (score ≥70), you'll get an email like this</li>
            <li>Email will include direct links to:
                <ul>
                    <li>📊 DexScreener chart</li>
                    <li>🔍 Honeypot checker</li>
                    <li>🔎 BSCScan contract viewer</li>
                </ul>
            </li>
        </ol>

        <h3>📋 Quick Commands:</h3>
        <div class="code">
# View logs<br>
tail -f cron_log.txt<br>
<br>
# Check cron status<br>
crontab -l<br>
<br>
# Test manually<br>
python3 run_with_email_alerts.py
        </div>

        <h3>⚠️ Important Reminders:</h3>
        <ul>
            <li>Always verify tokens on honeypot.is before buying</li>
            <li>Check contracts on BSCScan</li>
            <li>Start with small amounts ($50-100)</li>
            <li>90% of early tokens fail - expect losses</li>
            <li>Use stop losses and take profits systematically</li>
            <li>This is NOT financial advice</li>
        </ul>

        <div class="success">
            <h3>🎉 You're All Set!</h3>
            <p>Your automated DEX scanner is now monitoring BSC and Ethereum chains for opportunities.</p>
            <p><strong>Next alert:</strong> When opportunities are found during scheduled hours</p>
        </div>

        <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #ddd; padding-top: 15px;">
            <strong>Test Email Details:</strong><br>
            Sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}<br>
            System: DEX Scanner v1.0<br>
            Status: ✅ Active and Monitoring
        </p>
    </div>
</body>
</html>
"""

# Plain text version
text = f"""
DEX SCANNER - TEST EMAIL
========================

✅ Your email configuration is working correctly!

Configuration:
- Alerts to: {to_email}
- From: {from_email}
- Threshold: Score ≥ 70
- Schedule: Hourly, 9AM-6PM UTC, Mon-Fri

What happens next:
1. Scanner runs automatically every hour
2. When opportunities found, you get email alerts
3. Each alert includes links to verify tokens

Your scanner is now active and monitoring!

Test email sent: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
"""

msg.attach(MIMEText(text, 'plain'))
msg.attach(MIMEText(html, 'html'))

# Send email
try:
    print("Connecting to SMTP server...")
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()

    print("Authenticating...")
    server.login(from_email, password)

    print("Sending email...")
    server.send_message(msg)
    server.quit()

    print()
    print("="*80)
    print("✅ TEST EMAIL SENT SUCCESSFULLY!")
    print("="*80)
    print()
    print(f"Check your inbox at: {to_email}")
    print()
    print("📧 Email details:")
    print(f"   Subject: {msg['Subject']}")
    print(f"   From: {from_email}")
    print(f"   To: {to_email}")
    print()
    print("⏰ If you don't see it within 1-2 minutes:")
    print("   1. Check spam/junk folder")
    print("   2. Check 'Promotions' tab (Gmail)")
    print("   3. Search inbox for '[DEX Scanner]'")
    print()
    print("="*80)

except smtplib.SMTPAuthenticationError:
    print()
    print("="*80)
    print("❌ AUTHENTICATION FAILED")
    print("="*80)
    print()
    print("The email/password is incorrect.")
    print()
    print("Please check:")
    print("  1. Email address is correct")
    print("  2. App Password is correct (not regular password)")
    print("  3. 2FA is enabled on Gmail account")
    print()
    print("To fix:")
    print("  1. Go to: https://myaccount.google.com/apppasswords")
    print("  2. Generate new App Password")
    print("  3. Update email_config.json")
    print()

except Exception as e:
    print()
    print("="*80)
    print("❌ ERROR SENDING EMAIL")
    print("="*80)
    print()
    print(f"Error: {e}")
    print()
