#!/usr/bin/env python3
"""
Test Price-Level Trader
Runs a single trading cycle to validate integration.
"""

import logging
from trader_price_levels import PriceLevelTrader

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == '__main__':
    print("=" * 70)
    print("TESTING PRICE-LEVEL TRADER")
    print("Running single cycle...")
    print("=" * 70)

    trader = PriceLevelTrader()

    try:
        trader.trading_cycle()
        print("\n" + "=" * 70)
        print("✓ TEST COMPLETE - Bot is working!")
        print("=" * 70)
    except Exception as e:
        print("\n" + "=" * 70)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 70)
        raise
