#!/usr/bin/env python3
"""
Data Status Checker

Checks what training data is available across all databases and reports
whether we're ready to train models for each bot type.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

def check_database_exists(db_path):
    """Check if database exists and is accessible."""
    if not Path(db_path).exists():
        return False, f"Not found: {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        conn.close()
        return True, "OK"
    except Exception as e:
        return False, f"Error: {e}"

def check_alchemy_trades():
    """Check alchemy trades database."""
    db_path = "data/alchemy_trades.db"
    exists, status = check_database_exists(db_path)

    if not exists:
        return {"status": "missing", "message": status}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get trade statistics
    cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
    total_trades = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT condition_id) FROM on_chain_trades")
    unique_markets = cursor.fetchone()[0]

    cursor.execute("""
        SELECT MAX(block_timestamp)
        FROM on_chain_trades
        WHERE block_timestamp IS NOT NULL
    """)
    latest_trade = cursor.fetchone()[0]

    conn.close()

    return {
        "status": "available",
        "total_trades": total_trades,
        "unique_markets": unique_markets,
        "latest_trade": latest_trade
    }

def check_token_mapping():
    """Check token mapping database."""
    db_path = "data/token_mapping.db"
    exists, status = check_database_exists(db_path)

    if not exists:
        return {"status": "missing", "message": status}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM token_condition_map")
    total_mappings = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM markets")
    total_markets = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM markets
        WHERE outcome_prices IS NOT NULL
        AND length(outcome_prices) > 2
    """)
    resolved_markets = cursor.fetchone()[0]

    conn.close()

    return {
        "status": "available",
        "total_mappings": total_mappings,
        "total_markets": total_markets,
        "resolved_markets": resolved_markets
    }

def check_linked_data():
    """Check how many markets have both trades and outcomes."""
    if not Path("data/alchemy_trades.db").exists() or not Path("data/token_mapping.db").exists():
        return {"status": "missing", "message": "Required databases not found"}

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("ATTACH DATABASE 'data/alchemy_trades.db' AS trades")
    cursor.execute("ATTACH DATABASE 'data/token_mapping.db' AS mapping")

    # Count markets with both trades and outcomes
    cursor.execute("""
        SELECT COUNT(DISTINCT t.condition_id)
        FROM trades.on_chain_trades t
        INNER JOIN mapping.markets m ON t.condition_id = m.condition_id
        WHERE m.outcome_prices LIKE '%1%'
    """)
    total_linked = cursor.fetchone()[0]

    # Check duration distribution
    cursor.execute("""
        SELECT
            CASE
                WHEN duration <= 1 THEN '0-1_days'
                WHEN duration <= 3 THEN '1-3_days'
                WHEN duration <= 7 THEN '3-7_days'
                WHEN duration <= 30 THEN '7-30_days'
                ELSE '30+_days'
            END as bucket,
            COUNT(*) as count
        FROM (
            SELECT
                (julianday(m.end_date) - julianday(m.created_at)) as duration
            FROM trades.on_chain_trades t
            INNER JOIN mapping.markets m ON t.condition_id = m.condition_id
            WHERE m.outcome_prices LIKE '%1%'
            AND m.created_at IS NOT NULL
            AND m.end_date IS NOT NULL
        )
        GROUP BY bucket
    """)

    distribution = {}
    for row in cursor.fetchall():
        distribution[row[0]] = row[1]

    conn.close()

    short_expiry_count = (
        distribution.get('0-1_days', 0) +
        distribution.get('1-3_days', 0) +
        distribution.get('3-7_days', 0)
    )

    return {
        "status": "available",
        "total_linked": total_linked,
        "short_expiry_markets": short_expiry_count,
        "distribution": distribution
    }

def check_live_positions():
    """Check live data collection progress."""
    db_path = "data/positions_short_expiry.db"
    exists, status = check_database_exists(db_path)

    if not exists:
        return {"status": "missing", "message": status}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'open'")
    open_positions = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM positions WHERE status != 'open'")
    closed_positions = cursor.fetchone()[0]

    cursor.execute("SELECT bucket, COUNT(*) FROM positions GROUP BY bucket")
    by_bucket = {}
    for row in cursor.fetchall():
        by_bucket[row[0]] = row[1]

    conn.close()

    # Estimate days until ready (need 100 closed positions)
    target = 100
    if closed_positions >= target:
        eta_message = "READY TO TRAIN!"
        days_remaining = 0
    elif closed_positions > 0:
        # Rough estimate based on current rate
        days_remaining = max(1, int((target - closed_positions) / 10))
        eta_message = f"~{days_remaining} days (assuming 10 closures/day)"
    else:
        days_remaining = 10
        eta_message = "~10 days (no closures yet)"

    return {
        "status": "collecting",
        "open_positions": open_positions,
        "closed_positions": closed_positions,
        "by_bucket": by_bucket,
        "training_ready": closed_positions >= target,
        "eta_message": eta_message,
        "days_remaining": days_remaining
    }

def print_report():
    """Print comprehensive data status report."""
    print("=" * 70)
    print("POLYMARKET TRADING DATA STATUS REPORT")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Check Alchemy Trades
    print("📊 ALCHEMY ON-CHAIN TRADES")
    print("-" * 70)
    alchemy = check_alchemy_trades()
    if alchemy["status"] == "available":
        print(f"  ✅ Status: Available")
        print(f"  📈 Total Trades: {alchemy['total_trades']:,}")
        print(f"  🎯 Unique Markets: {alchemy['unique_markets']:,}")
        print(f"  📅 Latest Trade: {alchemy['latest_trade']}")
    else:
        print(f"  ❌ Status: {alchemy['message']}")
    print()

    # Check Token Mapping
    print("🗺️  TOKEN-CONDITION MAPPING")
    print("-" * 70)
    mapping = check_token_mapping()
    if mapping["status"] == "available":
        print(f"  ✅ Status: Available")
        print(f"  🔗 Token Mappings: {mapping['total_mappings']:,}")
        print(f"  📊 Total Markets: {mapping['total_markets']:,}")
        print(f"  ✔️  Resolved Markets: {mapping['resolved_markets']:,}")
    else:
        print(f"  ❌ Status: {mapping['message']}")
    print()

    # Check Linked Data
    print("🔗 LINKED TRAINING DATA (Trades + Outcomes)")
    print("-" * 70)
    linked = check_linked_data()
    if linked["status"] == "available":
        print(f"  ✅ Total Markets: {linked['total_linked']:,}")
        print(f"  🎯 Short-Expiry (≤7d): {linked['short_expiry_markets']:,}")
        print(f"\n  Duration Distribution:")
        for bucket, count in sorted(linked['distribution'].items()):
            bucket_display = bucket.replace('_', ' ').title()
            marker = "✅" if count > 0 else "❌"
            print(f"    {marker} {bucket_display:15s}: {count:,}")
    else:
        print(f"  ❌ Status: {linked['message']}")
    print()

    # Check Live Positions
    print("🔴 LIVE DATA COLLECTION (Short-Expiry Bot)")
    print("-" * 70)
    positions = check_live_positions()
    if positions["status"] == "collecting":
        ready_marker = "✅" if positions['training_ready'] else "⏳"
        print(f"  {ready_marker} Training Ready: {positions['training_ready']}")
        print(f"  📂 Open Positions: {positions['open_positions']}")
        print(f"  ✔️  Closed Positions: {positions['closed_positions']}/100 (minimum)")

        if positions['by_bucket']:
            print(f"\n  By Bucket:")
            for bucket, count in positions['by_bucket'].items():
                print(f"    • {bucket:12s}: {count}")

        if not positions['training_ready']:
            print(f"\n  ⏰ ETA to Training: {positions['eta_message']}")
    else:
        print(f"  ❌ Status: {positions['message']}")
    print()

    # Summary and Recommendations
    print("=" * 70)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 70)

    short_expiry_ready = linked.get("short_expiry_markets", 0) >= 50
    live_ready = positions.get("training_ready", False)

    if live_ready:
        print("✅ READY TO TRAIN short-expiry model using live collected data!")
        print("   → Run: python3 scripts/train_short_expiry_from_live.py")
    elif short_expiry_ready:
        print("✅ Could train on historical short-expiry data")
        print("   → Run: python3 scripts/train_short_expiry.py")
    else:
        print("⏳ CONTINUE LIVE DATA COLLECTION")
        print(f"   → Current progress: {positions.get('closed_positions', 0)}/100 closed positions")
        print(f"   → Estimated time: {positions.get('eta_message', 'Unknown')}")
        print("   → Keep trader_short_expiry.py running")
        print("\n   Historical data: Not available for short-expiry markets")
        print(f"   └─ Available: {linked.get('total_linked', 0)} markets (all 90+ days duration)")
        print("   └─ Short-expiry (≤7d): 0 markets ❌")

    print("\n📝 See docs/DATA_STATUS.md for detailed information")
    print("=" * 70)

if __name__ == "__main__":
    print_report()
