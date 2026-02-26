"""
RISK-004: Market cooldown prevents over-trading

Validates that bots enforce cooldown before re-entering closed positions.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))


def test_short_expiry_has_cooldown_tracking():
    """Test that short-expiry bot tracks market cooldowns."""
    from bots.trader_short_expiry import ShortExpiryTrader
    import json

    # Load config
    config_path = 'config/config_short_expiry.json'
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Check cooldown config exists
    assert 'market_cooldown_hours' in config['risk_management'], \
        "Config missing market_cooldown_hours"

    cooldown_config = config['risk_management']['market_cooldown_hours']
    assert 'ultra_short' in cooldown_config
    assert 'short' in cooldown_config
    assert 'medium' in cooldown_config

    # Verify reasonable cooldown values (not 0)
    assert cooldown_config['ultra_short'] >= 0.5, "Ultra-short cooldown too low"
    assert cooldown_config['short'] >= 1.0, "Short cooldown too low"
    assert cooldown_config['medium'] >= 2.0, "Medium cooldown too low"


def test_short_expiry_implements_cooldown_check():
    """Test that short-expiry bot implements cooldown checking."""
    # Read the trader source code
    trader_path = Path('src/bots/trader_short_expiry.py')
    source = trader_path.read_text()

    # Check for cooldown implementation
    assert 'market_cooldowns' in source, \
        "trader_short_expiry.py missing market_cooldowns tracking"

    assert 'cooldown_hours' in source, \
        "trader_short_expiry.py missing cooldown_hours check"

    assert 'elapsed_hours' in source, \
        "trader_short_expiry.py missing elapsed time calculation"

    # Check cooldown is recorded on position close
    assert 'self.market_cooldowns[market_id] = datetime.now' in source, \
        "trader_short_expiry.py not recording cooldown on position close"


def test_cooldown_config_validation():
    """Test that all bots with position trading have cooldown config."""
    import json

    bot_configs = [
        'config/config_short_expiry.json',
        # Add other bot configs if they implement cooldown
    ]

    for config_path in bot_configs:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # If bot has risk_management, it should have cooldown
        if 'risk_management' in config:
            risk_mgmt = config['risk_management']

            # Short-expiry MUST have cooldown
            if 'short_expiry' in config_path:
                assert 'market_cooldown_hours' in risk_mgmt, \
                    f"{config_path} missing market_cooldown_hours"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
