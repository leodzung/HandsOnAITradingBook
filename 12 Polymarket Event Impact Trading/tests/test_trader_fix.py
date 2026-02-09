#!/usr/bin/env python3
"""
Test Trader Fix
Run a single trading cycle to verify the feature mismatch is fixed.
"""

import json
import logging
from trader import PolymarketTrader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_trader():
    """Test a single trading cycle"""
    print("="*70)
    print("TESTING EVENT-BASED TRADER FIX")
    print("="*70)

    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("⚠️  config.json not found, using defaults")
        config = {
            'paper_trading': True,
            'model_path': 'real_data_model.pkl',
            'min_confidence': 0.65,
            'min_expected_return': 0.03,
            'max_position_size': 100,
            'max_positions': 10,
            'max_daily_loss': 500,
            'min_market_volume': 1000,
            'min_hours_to_expiry': 2,
            'max_hours_to_expiry': 720,
            'event_lookback_hours': 1,
            'use_transformers': False
        }

    print("\n✓ Configuration loaded")
    print(f"  Paper trading: {config.get('paper_trading', True)}")
    print(f"  Model path: {config.get('model_path', 'N/A')}")

    # Initialize trader
    print("\n✓ Initializing trader...")
    trader = PolymarketTrader(config)

    print("\n✓ Running single trading cycle...")
    print("-"*70)

    try:
        trader.trading_cycle()
        print("-"*70)
        print("\n✅ TRADING CYCLE COMPLETED SUCCESSFULLY!")
        print("\nIf you see this message without errors, the fix worked!")
        return True

    except Exception as e:
        print("-"*70)
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_trader()
    exit(0 if success else 1)
