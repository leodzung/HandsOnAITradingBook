#!/usr/bin/env python3
"""
Integrate ML predictions into all trading bots.
Adds ML predictor to each bot's decision-making process.
"""

import re
from pathlib import Path

def add_ml_import(content: str) -> str:
    """Add ML predictor import."""
    # Find the imports section
    if 'from ml.ml_predictor import MLPredictor' in content:
        return content  # Already added
    
    # Add after other ml imports
    if 'from ml.' in content:
        content = content.replace(
            'from ml.snapshot_collector',
            'from ml.ml_predictor import MLPredictor, MLPredictorFactory\nfrom ml.snapshot_collector'
        )
    else:
        # Add after core imports
        content = content.replace(
            'from core.position_manager',
            'from ml.ml_predictor import MLPredictor, MLPredictorFactory\nfrom core.position_manager'
        )
    
    return content

def add_ml_to_init(content: str, class_name: str) -> str:
    """Add ML predictor initialization to __init__ method."""
    
    # Check if already added
    if 'self.ml_predictor' in content:
        return content
    
    # Find the __init__ method of the trader class
    pattern = rf'(class {class_name}:.*?def __init__\(self.*?\):.*?)(def\s+\w+)'
    
    def replacer(match):
        init_content = match.group(1)
        next_method = match.group(2)
        
        # Find a good insertion point (after config is loaded)
        if 'self.config = config' in init_content:
            ml_init = """
        # Initialize ML predictor
        bot_name = self.config.get('bot_type', 'event')  # Default to event if not specified
        self.ml_predictor = MLPredictorFactory.create_for_bot(bot_name, self.config)
        
        if self.ml_predictor.enabled:
            logger.info("✅ ML predictor initialized and enabled")
        else:
            logger.info("ML predictor disabled - using rule-based trading only")
        """
            init_content = init_content.replace(
                'self.config = config',
                'self.config = config' + ml_init
            )
        
        return init_content + next_method
    
    content = re.sub(pattern, replacer, content, flags=re.DOTALL)
    
    return content

def add_ml_to_trading_decision(content: str) -> str:
    """Add ML prediction to trading decision logic."""
    
    # This is a simplified version - we'll add a helper method
    # that bots can call before making trades
    
    if 'def _ml_should_trade' in content:
        return content  # Already added
    
    # Find the class definition and add helper method
    helper_method = '''
    def _ml_should_trade(self, market: dict, additional_context: dict = None) -> tuple[bool, str]:
        """
        Check if ML model recommends trading this market.
        
        Args:
            market: Market dictionary
            additional_context: Optional context (event info, etc.)
        
        Returns:
            Tuple of (should_trade, reason)
        """
        if not self.ml_predictor.enabled:
            return True, "ML disabled - using rules only"
        
        should_trade, reason = self.ml_predictor.should_trade(market, additional_context)
        
        if should_trade:
            confidence = self.ml_predictor.get_confidence(market, additional_context)
            logger.info(f"ML: ✅ TRADE - {reason}")
            return True, reason
        else:
            logger.info(f"ML: ❌ SKIP - {reason}")
            return False, reason
    
    def _ml_get_position_size(self, base_size: float, market: dict) -> float:
        """
        Adjust position size based on ML confidence.
        
        Args:
            base_size: Base position size
            market: Market dictionary
        
        Returns:
            Adjusted position size
        """
        if not self.ml_predictor.enabled:
            return base_size
        
        confidence = self.ml_predictor.get_confidence(market)
        multiplier = self.ml_predictor.get_position_size_multiplier(confidence)
        adjusted_size = base_size * multiplier
        
        logger.debug(f"Position size: ${base_size:.0f} × {multiplier:.2f} = ${adjusted_size:.0f}")
        
        return adjusted_size
'''
    
    # Add helper methods before the run() method
    if 'def run(self):' in content:
        content = content.replace('def run(self):', helper_method + '\n    def run(self):')
    
    return content

def integrate_bot(bot_path: str, class_name: str):
    """Integrate ML into a specific bot."""
    path = Path(bot_path)
    
    if not path.exists():
        print(f"⚠️  Bot not found: {bot_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"Integrating ML into: {path.name}")
    print(f"{'='*60}")
    
    # Read bot code
    with open(path, 'r') as f:
        content = f.read()
    
    # Make backup
    backup_path = path.with_suffix('.py.backup')
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"✅ Created backup: {backup_path}")
    
    # Apply transformations
    content = add_ml_import(content)
    print("✅ Added ML imports")
    
    content = add_ml_to_init(content, class_name)
    print("✅ Added ML initialization")
    
    content = add_ml_to_trading_decision(content)
    print("✅ Added ML helper methods")
    
    # Save modified bot
    with open(path, 'w') as f:
        f.write(content)
    print(f"✅ Saved modified bot: {path}")
    
    return True

# Integrate all bots
bots = [
    ('src/bots/trader.py', 'PolymarketTrader'),
    ('src/bots/trader_price_levels.py', 'PriceLevelTrader'),
    ('src/bots/trader_short_expiry.py', 'ShortExpiryTrader')
]

print("\n" + "="*60)
print("ML INTEGRATION - STARTING")
print("="*60)

success_count = 0
for bot_path, class_name in bots:
    if integrate_bot(bot_path, class_name):
        success_count += 1

print("\n" + "="*60)
print(f"✅ ML INTEGRATION COMPLETE: {success_count}/{len(bots)} bots updated")
print("="*60)

print("\nNext steps:")
print("1. Review the changes in each bot file")
print("2. Test the bots with: python3 src/bots/trader.py (etc.)")
print("3. Check logs for 'ML predictor initialized'")
print("4. Verify ML predictions are being made")
print("\nBackup files created with .py.backup extension")
