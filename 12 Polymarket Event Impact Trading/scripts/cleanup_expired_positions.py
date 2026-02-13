#!/usr/bin/env python3
"""
Cleanup script for expired short-expiry positions.

This script closes positions that should have expired based on their
entry_time and hours_to_expiry_at_entry.
"""

import sqlite3
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.polymarket_client import PolymarketClient


def calculate_expiry_time(entry_time_str: str, hours_to_expiry: float) -> datetime:
    """Calculate when a position should have expired."""
    entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
    expiry_time = entry_time + timedelta(hours=hours_to_expiry)
    return expiry_time


def close_expired_position(conn, position: dict, client: PolymarketClient, dry_run: bool = False):
    """Close an expired position."""
    market_id = position['market_id']
    outcome = position['outcome']
    entry_price = position['entry_price']
    size = position['size']
    entry_time = position['entry_time']
    hours_to_expiry = position['hours_to_expiry_at_entry']

    # Calculate expected expiry time
    expiry_time = calculate_expiry_time(entry_time, hours_to_expiry)
    now = datetime.now(timezone.utc)

    # Check if actually expired
    if now < expiry_time:
        print(f"⏱️  Position {market_id[:16]}... not yet expired (expires in {(expiry_time - now).total_seconds() / 3600:.1f}h)")
        return False

    # Try to get current market status and price
    market = client.get_market(market_id)

    if market:
        # Check if market is closed
        closed = market.get('closed', False)
        active = market.get('active', True)

        if closed or not active:
            # Market is closed - try to determine outcome
            # For now, we'll use entry price as exit price (neutral outcome)
            exit_price = entry_price
            exit_reason = 'expiry_closed'
            print(f"🔒 Market {market_id[:16]}... is closed")
        else:
            # Market still active but past expiry time - fetch current price
            prices = client.get_market_prices(market_id)
            exit_price = prices.get(outcome.lower()) or entry_price
            exit_reason = 'expiry'
            print(f"📈 Market {market_id[:16]}... still active, using current price: ${exit_price:.4f}")
    else:
        # Can't fetch market - assume expired at entry price
        exit_price = entry_price
        exit_reason = 'expiry_unknown'
        print(f"❓ Market {market_id[:16]}... not found, using entry price")

    # Calculate P&L
    pnl = (exit_price - entry_price) * (size / entry_price)
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

    # Update database
    if not dry_run:
        cursor = conn.execute("""
            UPDATE positions
            SET exit_price = ?, exit_time = ?, pnl = ?, pnl_pct = ?,
                exit_reason = ?, status = 'closed'
            WHERE market_id = ? AND outcome = ? AND status = 'open'
        """, (
            exit_price,
            now.isoformat(),
            pnl,
            pnl_pct,
            exit_reason,
            market_id,
            outcome
        ))
        conn.commit()
        print(f"✅ Closed: {outcome} @ ${entry_price:.4f} → ${exit_price:.4f} | "
              f"P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%) | {exit_reason}")
    else:
        print(f"[DRY RUN] Would close: {outcome} @ ${entry_price:.4f} → ${exit_price:.4f} | "
              f"P&L: ${pnl:+.2f} ({pnl_pct:+.1f}%)")

    return True


def main():
    """Main cleanup function."""
    import argparse

    parser = argparse.ArgumentParser(description='Cleanup expired short-expiry positions')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be closed without actually closing')
    parser.add_argument('--force', action='store_true',
                       help='Close all open positions regardless of expiry time')
    args = parser.parse_args()

    db_path = 'data/positions_short_expiry.db'

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    # Initialize client
    client = PolymarketClient()

    # Connect to database
    conn = sqlite3.connect(db_path)

    # Get open positions
    cursor = conn.execute(
        "SELECT market_id, outcome, entry_price, size, entry_time, "
        "hours_to_expiry_at_entry, bucket FROM positions WHERE status = 'open'"
    )

    columns = [desc[0] for desc in cursor.description]
    positions = [dict(zip(columns, row)) for row in cursor.fetchall()]

    if not positions:
        print("✅ No open positions to clean up")
        conn.close()
        return

    print(f"Found {len(positions)} open position(s)")
    print("=" * 80)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        print("=" * 80)

    now = datetime.now(timezone.utc)
    closed_count = 0

    for i, pos in enumerate(positions, 1):
        print(f"\n[{i}/{len(positions)}] Processing {pos['market_id'][:16]}...")

        if args.force:
            # Force close all positions
            if close_expired_position(conn, pos, client, args.dry_run):
                closed_count += 1
        else:
            # Only close expired positions
            expiry_time = calculate_expiry_time(pos['entry_time'], pos['hours_to_expiry_at_entry'])
            is_expired = now >= expiry_time

            if is_expired:
                if close_expired_position(conn, pos, client, args.dry_run):
                    closed_count += 1
            else:
                hours_remaining = (expiry_time - now).total_seconds() / 3600
                print(f"⏳ Not expired yet ({hours_remaining:.1f}h remaining)")

    conn.close()

    print("\n" + "=" * 80)
    print(f"Summary: {closed_count} position(s) closed")

    if args.dry_run:
        print("\n💡 Run without --dry-run to actually close positions")


if __name__ == '__main__':
    main()
