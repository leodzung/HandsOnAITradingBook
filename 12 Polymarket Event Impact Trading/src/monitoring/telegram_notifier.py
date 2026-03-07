"""
Telegram Notification Module
Sends trade alerts to Telegram chat.
"""

import requests
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send trading notifications via Telegram bot."""

    def __init__(self, bot_token: str, chat_id: str, enabled: bool = True):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot API token (from @BotFather)
            chat_id: Chat ID to send messages to (use @userinfobot to get yours)
            enabled: Whether notifications are enabled
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.enabled = enabled
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram.

        Args:
            message: Message text (supports HTML formatting)
            parse_mode: Parse mode (HTML or Markdown)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return True

        if not self.bot_token or not self.chat_id:
            logger.debug("Telegram not configured, skipping notification")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def notify_position_opened(self, market_id: str, asset: str, outcome: str,
                                entry_price: float, position_size: float,
                                question: str = None, edge: float = None,
                                bot_name: str = "Trading Bot"):
        """
        Send notification when a new position is opened.

        Args:
            market_id: Market condition ID
            asset: Asset symbol (BTC, ETH)
            outcome: YES or NO
            entry_price: Entry price
            position_size: Position size in $
            question: Market question
            edge: Expected edge percentage
            bot_name: Name of the trading bot
        """
        # Truncate market ID for readability
        short_id = market_id[:16] + "..."

        # Build message
        message = f"<b>NEW POSITION</b> - {bot_name}\n\n"
        message += f"<b>Asset:</b> {asset}\n"
        message += f"<b>Side:</b> {outcome}\n"
        message += f"<b>Size:</b> ${position_size:.2f}\n"
        message += f"<b>Entry:</b> ${entry_price:.3f}\n"

        if edge is not None:
            message += f"<b>Edge:</b> {edge:+.1%}\n"

        if question:
            # Truncate long questions
            q = question[:80] + "..." if len(question) > 80 else question
            message += f"\n<i>{q}</i>\n"

        message += f"\n<code>{short_id}</code>"

        self.send_message(message)

    def notify_position_closed(self, market_id: str, asset: str, outcome: str,
                                entry_price: float, exit_price: float,
                                position_size: float, pnl: float, pnl_pct: float,
                                exit_reason: str = None, question: str = None,
                                bot_name: str = "Trading Bot"):
        """
        Send notification when a position is closed.

        Args:
            market_id: Market condition ID
            asset: Asset symbol (BTC, ETH)
            outcome: YES or NO
            entry_price: Entry price
            exit_price: Exit price
            position_size: Position size in $
            pnl: Profit/loss in $
            pnl_pct: Profit/loss percentage
            exit_reason: Why position was closed (stop_loss, take_profit, etc.)
            question: Market question
            bot_name: Name of the trading bot
        """
        short_id = market_id[:16] + "..."

        # Emoji based on P&L
        emoji = "" if pnl >= 0 else ""

        # Exit reason display
        reason_map = {
            'stop_loss': 'Stop Loss',
            'take_profit': 'Take Profit',
            'trailing_stop': 'Trailing Stop',
            'expiry': 'Expiry',
            'time_exit': 'Time Exit',
            'manual': 'Manual',
            '100pct_profit': 'Max Profit'
        }
        reason_display = reason_map.get(exit_reason, exit_reason or 'N/A')

        # Build message
        message = f"<b>{emoji} CLOSED POSITION</b> - {bot_name}\n\n"
        message += f"<b>Asset:</b> {asset}\n"
        message += f"<b>Side:</b> {outcome}\n"
        message += f"<b>Entry:</b> ${entry_price:.3f}\n"
        message += f"<b>Exit:</b> ${exit_price:.3f}\n"
        message += f"<b>P&L:</b> ${pnl:+.2f} ({pnl_pct:+.1f}%)\n"
        message += f"<b>Reason:</b> {reason_display}\n"

        if question:
            q = question[:60] + "..." if len(question) > 60 else question
            message += f"\n<i>{q}</i>\n"

        message += f"\n<code>{short_id}</code>"

        self.send_message(message)

    def notify_circuit_breaker(self, consecutive_losses: int, cooldown_hours: float,
                                bot_name: str = "Trading Bot"):
        """
        Send notification when circuit breaker is triggered.

        Args:
            consecutive_losses: Number of consecutive losses
            cooldown_hours: Hours until trading resumes
            bot_name: Name of the trading bot
        """
        now = datetime.now()
        resume_time = now + timedelta(hours=cooldown_hours)
        message = f"<b>CIRCUIT BREAKER ACTIVATED</b> - {bot_name}\n\n"
        message += f"<b>Consecutive losses:</b> {consecutive_losses}\n"
        message += f"<b>Cooldown:</b> {cooldown_hours:.1f} hours\n"
        message += f"<b>Trading resumes at:</b> {resume_time.strftime('%Y-%m-%d %H:%M')} UTC\n"
        message += f"\n<i>Triggered: {now.strftime('%Y-%m-%d %H:%M')} UTC</i>"

        self.send_message(message)

    def notify_circuit_breaker_reset(self, bot_name: str = "Trading Bot"):
        """
        Send notification when circuit breaker cooldown expires and trading resumes.

        Args:
            bot_name: Name of the trading bot
        """
        message = f"<b>CIRCUIT BREAKER RESET</b> - {bot_name}\n\n"
        message += "Cooldown period elapsed. Trading has resumed.\n"
        message += f"\n<i>Reset: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC</i>"

        self.send_message(message)

    def notify_daily_summary(self, total_pnl: float, win_rate: float,
                              trades_count: int, open_positions: int,
                              balance: float, bot_name: str = "Trading Bot"):
        """
        Send daily summary notification.

        Args:
            total_pnl: Total P&L for the day
            win_rate: Win rate percentage
            trades_count: Number of trades today
            open_positions: Number of open positions
            balance: Current balance
            bot_name: Name of the trading bot
        """
        emoji = "" if total_pnl >= 0 else ""

        message = f"<b>{emoji} DAILY SUMMARY</b> - {bot_name}\n\n"
        message += f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}\n"
        message += f"<b>Trades:</b> {trades_count}\n"
        message += f"<b>Win Rate:</b> {win_rate:.1f}%\n"
        message += f"<b>P&L:</b> ${total_pnl:+.2f}\n"
        message += f"<b>Open Positions:</b> {open_positions}\n"
        message += f"<b>Balance:</b> ${balance:.2f}"

        self.send_message(message)

    def notify_error(self, error_message: str, bot_name: str = "Trading Bot"):
        """
        Send error notification.

        Args:
            error_message: Error description
            bot_name: Name of the trading bot
        """
        message = f"<b>ERROR</b> - {bot_name}\n\n"
        message += f"{error_message}\n"
        message += f"\n<i>Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"

        self.send_message(message)

    def test_connection(self) -> bool:
        """
        Test the Telegram connection by sending a test message.

        Returns:
            True if connection successful
        """
        message = f"Telegram notifier connected.\n"
        message += f"<i>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        return self.send_message(message)
