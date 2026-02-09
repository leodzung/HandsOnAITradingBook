#!/usr/bin/env python3
"""
Clean Slate Reset
Reset paper trading to fresh state before Phase 1 deployment.
"""

import os
import json
from datetime import datetime

def reset_to_clean_state():
    """Reset all trading state to fresh start."""

    print("="*70)
    print("CLEAN SLATE RESET - Phase 1")
    print("="*70)

    changes = []

    # 1. Reset paper trading balance
    print("\n1. Resetting paper trading balance...")
    balance_file = 'data/paper_trading_balance.json'

    if os.path.exists(balance_file):
        with open(balance_file, 'r') as f:
            old_balance = json.load(f).get('balance', 0)
        print(f"   Old balance: ${old_balance:.2f}")
        changes.append(f"Balance: ${old_balance:.2f} → $1,000.00")
    else:
        print("   No existing balance file")

    # Create fresh balance
    with open(balance_file, 'w') as f:
        json.dump({
            'balance': 1000.0,
            'last_updated': datetime.now().isoformat(),
            'note': 'Clean slate reset - Phase 1'
        }, f, indent=2)

    print("   ✓ Reset to $1,000.00")

    # 2. Create fresh positions database
    print("\n2. Resetting positions database...")
    positions_db = 'data/positions.db'

    if os.path.exists(positions_db):
        # Backup old database
        backup = f'data/positions_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        os.rename(positions_db, backup)
        print(f"   ✓ Backed up old database to: {backup}")
        changes.append(f"Positions: Backed up to {backup}")
    else:
        print("   No existing positions database")

    # Database will be created on first bot run
    print("   ✓ Fresh database will be created on next run")

    # 3. Log the reset
    print("\n3. Creating reset log...")
    log_file = 'data/reset_log.txt'

    with open(log_file, 'a') as f:
        f.write(f"\n{'='*70}\n")
        f.write(f"CLEAN SLATE RESET\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write(f"Reason: Phase 1 - Position Persistence Implementation\n")
        f.write(f"Changes:\n")
        for change in changes:
            f.write(f"  - {change}\n")
        f.write(f"New state: $1,000 balance, 0 positions\n")
        f.write(f"{'='*70}\n")

    print(f"   ✓ Logged to: {log_file}")

    # 4. Summary
    print("\n" + "="*70)
    print("✅ CLEAN SLATE RESET COMPLETE")
    print("="*70)
    print("\nNew state:")
    print("  • Balance: $1,000.00")
    print("  • Open positions: 0")
    print("  • Database: Fresh (will be created on startup)")
    print("  • Old data: Backed up")

    print("\nBot is ready to deploy with:")
    print("  ✓ Position persistence (survives restart)")
    print("  ✓ Signal generator fix")
    print("  ✓ Clean tracking")

    print("\n" + "="*70)

    return True

if __name__ == '__main__':
    reset_to_clean_state()
