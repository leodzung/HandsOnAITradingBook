"""Notification system for deal alerts."""

from typing import Dict, List, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class EmailNotifier:
    """Email notification handler."""

    def __init__(self, config: Dict):
        """Initialize email notifier.

        Args:
            config: Email configuration
        """
        self.enabled = config.get("enabled", False)
        self.smtp_server = config.get("smtp_server", "smtp.gmail.com")
        self.smtp_port = config.get("smtp_port", 587)
        self.sender_email = config.get("sender_email", "")
        self.sender_password = config.get("sender_password", "")
        self.recipient_emails = config.get("recipient_emails", [])
        self.alert_min_roi = config.get("alert_min_roi", 50.0)

    def send_deal_alert(self, deal: Dict):
        """Send alert for a high-value deal.

        Args:
            deal: Deal dictionary
        """
        if not self.enabled or not self.sender_email:
            return

        # Check if deal meets alert threshold
        if deal.get("roi_percentage", 0) < self.alert_min_roi:
            return

        try:
            subject = f"🔥 High ROI Deal Alert: {deal.get('roi_percentage', 0):.1f}% ROI"

            body = self._format_deal_email(deal)

            self._send_email(subject, body)

        except Exception as e:
            print(f"Error sending email alert: {e}")

    def send_daily_digest(self, deals: List[Dict]):
        """Send daily digest of deals.

        Args:
            deals: List of deal dictionaries
        """
        if not self.enabled or not deals:
            return

        try:
            subject = f"Daily Deal Digest - {len(deals)} Opportunities"

            body = self._format_digest_email(deals)

            self._send_email(subject, body)

        except Exception as e:
            print(f"Error sending daily digest: {e}")

    def _format_deal_email(self, deal: Dict) -> str:
        """Format single deal as HTML email.

        Args:
            deal: Deal dictionary

        Returns:
            HTML email body
        """
        return f"""
        <html>
        <body>
            <h2>High Value Deal Found!</h2>

            <h3>{deal.get('product_title', 'Unknown Product')}</h3>

            <p><strong>ASIN:</strong> {deal.get('asin', 'N/A')}</p>
            <p><strong>Source:</strong> {deal.get('source', 'N/A')}</p>

            <h4>Pricing:</h4>
            <ul>
                <li>Source Price: ${deal.get('source_price', 0):.2f}</li>
                <li>Amazon Price: ${deal.get('amazon_price', 0):.2f}</li>
                <li>Estimated Profit: ${deal.get('estimated_profit', 0):.2f}</li>
            </ul>

            <h4>Metrics:</h4>
            <ul>
                <li><strong>ROI: {deal.get('roi_percentage', 0):.1f}%</strong></li>
                <li>Profit Margin: {deal.get('profit_margin', 0):.1f}%</li>
                <li>Sales Rank: {deal.get('sales_rank', 'N/A')}</li>
                <li>Rating: {deal.get('average_rating', 0):.1f} ({deal.get('review_count', 0)} reviews)</li>
            </ul>

            <h4>Costs:</h4>
            <ul>
                <li>Referral Fee: ${deal.get('amazon_referral_fee', 0):.2f}</li>
                <li>FBA Fee: ${deal.get('amazon_fba_fee', 0):.2f}</li>
                <li>Total Fees: ${deal.get('total_fees', 0):.2f}</li>
            </ul>

            <p><a href="https://www.amazon.com/dp/{deal.get('asin', '')}">View on Amazon</a></p>

            <p><em>Alert sent at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        </body>
        </html>
        """

    def _format_digest_email(self, deals: List[Dict]) -> str:
        """Format daily digest as HTML email.

        Args:
            deals: List of deals

        Returns:
            HTML email body
        """
        # Sort deals by ROI
        sorted_deals = sorted(
            deals, key=lambda x: x.get("roi_percentage", 0), reverse=True
        )

        # Take top 20
        top_deals = sorted_deals[:20]

        deals_html = ""
        for deal in top_deals:
            deals_html += f"""
            <tr>
                <td>{deal.get('product_title', '')[:50]}</td>
                <td>{deal.get('asin', '')}</td>
                <td>${deal.get('source_price', 0):.2f}</td>
                <td>${deal.get('amazon_price', 0):.2f}</td>
                <td>${deal.get('estimated_profit', 0):.2f}</td>
                <td><strong>{deal.get('roi_percentage', 0):.1f}%</strong></td>
            </tr>
            """

        return f"""
        <html>
        <body>
            <h2>Daily Deal Digest</h2>
            <p>Found {len(deals)} deals. Top 20 by ROI shown below:</p>

            <table border="1" cellpadding="5" cellspacing="0">
                <thead>
                    <tr>
                        <th>Product</th>
                        <th>ASIN</th>
                        <th>Source Price</th>
                        <th>Amazon Price</th>
                        <th>Profit</th>
                        <th>ROI</th>
                    </tr>
                </thead>
                <tbody>
                    {deals_html}
                </tbody>
            </table>

            <p><em>Digest generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        </body>
        </html>
        """

    def _send_email(self, subject: str, body: str):
        """Send email via SMTP.

        Args:
            subject: Email subject
            body: Email body (HTML)
        """
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = self.sender_email
        message["To"] = ", ".join(self.recipient_emails)

        html_part = MIMEText(body, "html")
        message.attach(html_part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)

            print(f"Email sent successfully to {len(self.recipient_emails)} recipient(s)")

        except Exception as e:
            print(f"Error sending email: {e}")
            raise


class TelegramNotifier:
    """Telegram bot notification handler."""

    def __init__(self, config: Dict):
        """Initialize Telegram notifier.

        Args:
            config: Telegram configuration
        """
        self.enabled = config.get("enabled", False)
        self.bot_token = config.get("bot_token", "")
        self.chat_id = config.get("chat_id", "")
        self.alert_min_roi = config.get("alert_min_roi", 40.0)

    def send_deal_alert(self, deal: Dict):
        """Send Telegram alert for a deal.

        Args:
            deal: Deal dictionary
        """
        if not self.enabled or not self.bot_token:
            return

        if deal.get("roi_percentage", 0) < self.alert_min_roi:
            return

        try:
            import requests

            message = self._format_deal_message(deal)

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}

            response = requests.post(url, data=data)
            response.raise_for_status()

        except Exception as e:
            print(f"Error sending Telegram alert: {e}")

    def _format_deal_message(self, deal: Dict) -> str:
        """Format deal as Telegram message.

        Args:
            deal: Deal dictionary

        Returns:
            Formatted message
        """
        return f"""
🔥 *High ROI Deal Alert*

*{deal.get('product_title', 'Unknown')[:100]}*

💰 *ROI:* {deal.get('roi_percentage', 0):.1f}%
📊 *Profit:* ${deal.get('estimated_profit', 0):.2f}

*Pricing:*
• Source: ${deal.get('source_price', 0):.2f}
• Amazon: ${deal.get('amazon_price', 0):.2f}

*Details:*
• ASIN: `{deal.get('asin', 'N/A')}`
• Source: {deal.get('source', 'N/A')}
• Sales Rank: {deal.get('sales_rank', 'N/A')}
• Rating: {deal.get('average_rating', 0):.1f} ⭐

[View on Amazon](https://www.amazon.com/dp/{deal.get('asin', '')})
        """.strip()


class NotificationManager:
    """Manages all notification channels."""

    def __init__(self, config: Dict):
        """Initialize notification manager.

        Args:
            config: Notifications configuration
        """
        self.email = EmailNotifier(config.get("email", {}))
        self.telegram = TelegramNotifier(config.get("telegram", {}))

        # Future: Add SMS, Slack, Discord, etc.

    def send_deal_alert(self, deal: Dict):
        """Send deal alert through all enabled channels.

        Args:
            deal: Deal dictionary
        """
        self.email.send_deal_alert(deal)
        self.telegram.send_deal_alert(deal)

    def send_daily_digest(self, deals: List[Dict]):
        """Send daily digest through all enabled channels.

        Args:
            deals: List of deals
        """
        self.email.send_daily_digest(deals)

    def send_batch_alerts(self, deals: List[Dict]):
        """Send alerts for multiple high-value deals.

        Args:
            deals: List of deals
        """
        for deal in deals:
            self.send_deal_alert(deal)
