#!/usr/bin/env python3
"""
Send daily snapshot collection summary via Telegram.

Usage:
    python3 scripts/send_daily_snapshot_summary.py

For automated daily reports, add to crontab:
    0 8 * * * cd /path/to/project && python3 scripts/send_daily_snapshot_summary.py
"""

import sys
import json
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from ml.snapshot_collector import MarketSnapshotCollector
from monitoring.telegram_notifier import TelegramNotifier


def main():
    """Send daily summary via Telegram."""
    # Load config
    config_path = project_root / 'config' / 'config_price_levels.json'

    try:
        with open(config_path) as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)

    # Initialize Telegram
    telegram_config = config.get('telegram', {})
    if not telegram_config.get('enabled', False):
        print("Telegram notifications are disabled in config")
        sys.exit(0)

    telegram = TelegramNotifier(
        bot_token=telegram_config.get('bot_token', ''),
        chat_id=telegram_config.get('chat_id', ''),
        enabled=True
    )

    # Initialize snapshot collector
    collector = MarketSnapshotCollector(
        db_path=project_root / 'data' / 'market_snapshots.db',
        telegram=telegram
    )

    # Send daily summary
    print("Sending daily snapshot summary...")
    collector.send_daily_summary()
    print("✓ Daily summary sent!")


if __name__ == '__main__':
    main()
