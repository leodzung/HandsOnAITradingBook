#!/usr/bin/env python3
"""
Enable Telegram notifications for traders.
Updates trader config files to use centralized telegram_config.json.
"""

import json
import sys
from pathlib import Path

def load_telegram_config():
    """Load telegram credentials from centralized config."""
    config_path = Path("telegram_config.json")

    if not config_path.exists():
        print("❌ telegram_config.json not found!")
        print("\nPlease set up Telegram first:")
        print("  1. Follow QUICK_START_TELEGRAM.md")
        print("  2. Create telegram_config.json")
        print("  3. Test with: python3 monitor_collectors.py --test")
        print("  4. Then run this script again")
        return None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        bot_token = config.get('bot_token', '')
        chat_id = config.get('chat_id', '')

        if not bot_token or not chat_id:
            print("❌ telegram_config.json is incomplete!")
            print("\nMake sure it contains both:")
            print('  "bot_token": "123456789:ABC..."')
            print('  "chat_id": "123456789"')
            return None

        print(f"✓ Loaded Telegram config (chat_id: {chat_id})")
        return {
            'bot_token': bot_token,
            'chat_id': chat_id,
            'enabled': True
        }

    except Exception as e:
        print(f"❌ Error reading telegram_config.json: {e}")
        return None

def update_config_file(config_file: str, telegram_config: dict):
    """Update a trader config file with telegram settings."""

    if not Path(config_file).exists():
        print(f"⚠️  {config_file} not found, skipping")
        return False

    try:
        # Load existing config
        with open(config_file, 'r') as f:
            config = json.load(f)

        # Update telegram section
        config['telegram'] = telegram_config

        # Write back
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✓ Updated {config_file}")
        return True

    except Exception as e:
        print(f"❌ Error updating {config_file}: {e}")
        return False

def test_notifications():
    """Test sending notifications from traders."""
    print("\n=== Testing Trader Notifications ===\n")

    try:
        from telegram_notifier import TelegramNotifier
        import json

        # Load centralized config
        with open("telegram_config.json", 'r') as f:
            config = json.load(f)

        notifier = TelegramNotifier(
            bot_token=config['bot_token'],
            chat_id=config['chat_id'],
            enabled=True
        )

        # Test connection
        print("Sending test message...")
        success = notifier.send_message(
            "<b>✅ Trader Telegram Setup Complete!</b>\n\n"
            "You will now receive alerts for:\n"
            "• New positions opened\n"
            "• Positions closed (with P&L)\n"
            "• Circuit breaker activations\n"
            "• Daily summaries\n"
            "• Critical errors\n\n"
            f"<i>Time: {notifier.notify_daily_summary.__module__}</i>",
            parse_mode="HTML"
        )

        if success:
            print("✓ Test message sent successfully!")
            return True
        else:
            print("❌ Test message failed!")
            return False

    except Exception as e:
        print(f"❌ Error testing notifications: {e}")
        return False

def main():
    print("=== Enable Telegram for Traders ===\n")

    # Load centralized telegram config
    telegram_config = load_telegram_config()
    if not telegram_config:
        sys.exit(1)

    print("\nUpdating trader configuration files...\n")

    # Update both trader configs
    updated_main = update_config_file("config.json", telegram_config)
    updated_price = update_config_file("config_price_levels.json", telegram_config)

    if not (updated_main or updated_price):
        print("\n❌ Failed to update any config files")
        sys.exit(1)

    print("\n✓ Configuration updated successfully!")

    # Offer to test
    print("\n" + "="*50)
    response = input("\nTest Telegram notifications? (y/n): ")

    if response.lower() == 'y':
        if test_notifications():
            print("\n" + "="*50)
            print("\n✅ Setup complete!")
            print("\nWhat happens now:")
            print("  • Event trader (trader.py) will send Telegram alerts")
            print("  • Price level trader (trader_price_levels.py) will send alerts")
            print("  • Same bot as monitoring system (shared config)")
            print("\nYou'll receive notifications for:")
            print("  ✓ Position opened (entry price, size, asset)")
            print("  ✓ Position closed (P&L, exit reason)")
            print("  ✓ Circuit breaker (consecutive losses)")
            print("  ✓ Daily summaries")
            print("  ✓ Critical errors")
            print("\nTo restart traders with new config:")
            print("  ./restart_all.sh")
            print("\nTo test again:")
            print("  python3 test_trader_telegram.py")
        else:
            print("\n❌ Test failed. Check your telegram_config.json")
            sys.exit(1)
    else:
        print("\n✓ Configuration saved. Restart traders to enable notifications:")
        print("  ./restart_all.sh")

if __name__ == "__main__":
    main()
