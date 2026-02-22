#!/usr/bin/env python3
"""
Update bot configs to enable ML models.
"""
import json
from pathlib import Path

configs = {
    'config/config.json': {
        'bot_name': 'event',
        'description': 'Event trader config'
    },
    'config/config_price_levels.json': {
        'bot_name': 'price_level',
        'description': 'Price-level trader config'
    },
    'config/config_short_expiry.json': {
        'bot_name': 'short_expiry',
        'description': 'Short-expiry trader config'
    }
}

for config_path, info in configs.items():
    path = Path(config_path)
    
    if not path.exists():
        print(f"⚠️  Config not found: {config_path}")
        continue
    
    # Load config
    with open(path) as f:
        config = json.load(f)
    
    # Add ML settings
    config['use_ml_model'] = True
    config['ml_model_path'] = f"data/models/{info['bot_name']}_model.pkl"
    config['ml_confidence_threshold'] = 0.60
    config['ml_position_size_scaling'] = True  # Scale position size with confidence
    
    # Save updated config
    with open(path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ Updated {config_path}")
    print(f"   ML enabled: True")
    print(f"   Model: {config['ml_model_path']}")
    print(f"   Confidence threshold: 60%")
    print()

print("="*60)
print("✅ All configs updated with ML settings")
print("="*60)
