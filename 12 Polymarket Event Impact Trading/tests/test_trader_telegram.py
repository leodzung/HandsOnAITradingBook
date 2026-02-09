#!/usr/bin/env python3
"""
Test Telegram notifications for traders.
Sends sample notifications to verify setup.
"""

import sys
import json
from datetime import datetime
from telegram_notifier import TelegramNotifier

def load_config():
    """Load telegram config."""
    try:
        with open("telegram_config.json", 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("❌ telegram_config.json not found!")
        print("\nCreate it first with:")
        print("  cp telegram_config.json.example telegram_config.json")
        print("  # Edit with your bot_token and chat_id")
        return None
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def test_position_opened(notifier):
    """Test position opened notification."""
    print("Testing: Position Opened...")
    notifier.notify_position_opened(
        market_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        asset="BTC",
        outcome="YES",
        entry_price=0.62,
        position_size=50.0,
        question="Will Bitcoin reach $100k by end of February?",
        edge=0.08,
        bot_name="Event Trader (TEST)"
    )
    print("✓ Sent")

def test_position_closed_profit(notifier):
    """Test position closed (profit) notification."""
    print("Testing: Position Closed (Profit)...")
    notifier.notify_position_closed(
        market_id="0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        asset="BTC",
        outcome="YES",
        entry_price=0.62,
        exit_price=0.75,
        position_size=50.0,
        pnl=6.50,
        pnl_pct=13.0,
        exit_reason="take_profit",
        question="Will Bitcoin reach $100k by end of February?",
        bot_name="Event Trader (TEST)"
    )
    print("✓ Sent")

def test_position_closed_loss(notifier):
    """Test position closed (loss) notification."""
    print("Testing: Position Closed (Loss)...")
    notifier.notify_position_closed(
        market_id="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        asset="ETH",
        outcome="NO",
        entry_price=0.45,
        exit_price=0.38,
        position_size=30.0,
        pnl=-2.10,
        pnl_pct=-7.0,
        exit_reason="stop_loss",
        question="Will Ethereum ETF be approved this month?",
        bot_name="Price Level Trader (TEST)"
    )
    print("✓ Sent")

def test_circuit_breaker(notifier):
    """Test circuit breaker notification."""
    print("Testing: Circuit Breaker...")
    notifier.notify_circuit_breaker(
        consecutive_losses=3,
        cooldown_hours=4.0,
        bot_name="Event Trader (TEST)"
    )
    print("✓ Sent")

def test_daily_summary(notifier):
    """Test daily summary notification."""
    print("Testing: Daily Summary...")
    notifier.notify_daily_summary(
        total_pnl=12.50,
        win_rate=66.7,
        trades_count=6,
        open_positions=2,
        balance=1012.50,
        bot_name="Event Trader (TEST)"
    )
    print("✓ Sent")

def test_error(notifier):
    """Test error notification."""
    print("Testing: Error Alert...")
    notifier.notify_error(
        error_message="Failed to place order: Insufficient balance",
        bot_name="Price Level Trader (TEST)"
    )
    print("✓ Sent")

def main():
    print("=== Trader Telegram Notification Test ===\n")

    # Load config
    config = load_config()
    if not config:
        sys.exit(1)

    # Create notifier
    notifier = TelegramNotifier(
        bot_token=config['bot_token'],
        chat_id=config['chat_id'],
        enabled=True
    )

    print(f"Bot Token: {config['bot_token'][:20]}...")
    print(f"Chat ID: {config['chat_id']}")
    print()

    # Test connection first
    print("Testing connection...")
    if not notifier.test_connection():
        print("❌ Connection test failed!")
        print("\nCheck:")
        print("  1. Bot token is correct")
        print("  2. Chat ID is correct")
        print("  3. You've sent /start to your bot")
        sys.exit(1)

    print("✓ Connection OK\n")

    # Offer test menu
    print("What would you like to test?\n")
    print("  1. Position Opened")
    print("  2. Position Closed (Profit)")
    print("  3. Position Closed (Loss)")
    print("  4. Circuit Breaker")
    print("  5. Daily Summary")
    print("  6. Error Alert")
    print("  7. All of the above")
    print("  0. Exit")
    print()

    choice = input("Choice (0-7): ").strip()

    tests = {
        '1': test_position_opened,
        '2': test_position_closed_profit,
        '3': test_position_closed_loss,
        '4': test_circuit_breaker,
        '5': test_daily_summary,
        '6': test_error
    }

    if choice == '0':
        print("Cancelled")
        return

    if choice == '7':
        print("\nSending all test notifications...\n")
        for test_func in tests.values():
            test_func(notifier)
            print()
        print("✓ All tests complete!")
        print("\nCheck your Telegram for 6 test messages.")
    elif choice in tests:
        print()
        tests[choice](notifier)
        print("\n✓ Test complete!")
        print("\nCheck your Telegram for the message.")
    else:
        print("Invalid choice")
        sys.exit(1)

    print("\n" + "="*50)
    print("\nYour traders are now configured to send:")
    print("  • Position opened/closed alerts")
    print("  • Circuit breaker notifications")
    print("  • Daily P&L summaries")
    print("  • Error alerts")
    print("\nNo further action needed - traders will send real alerts automatically!")

if __name__ == "__main__":
    main()
