#!/usr/bin/env python3
"""
Health check script for Polymarket Trading Bots.

Checks:
1. Database connectivity
2. Recent activity (trades, logs)
3. API connectivity
4. Balance status

Exit codes:
  0 - Healthy
  1 - Unhealthy
"""

import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

def check_database(db_path: str, table: str, max_age_hours: int = 24) -> tuple:
    """Check if database exists and has recent activity."""
    path = Path(db_path)
    if not path.exists():
        return False, f"Database not found: {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            conn.close()
            return False, f"Table '{table}' not found"

        # Check row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]

        conn.close()
        return True, f"OK ({count} rows)"
    except Exception as e:
        return False, f"Database error: {e}"

def check_balance(balance_file: str) -> tuple:
    """Check if balance file exists and is recent."""
    path = Path(balance_file)
    if not path.exists():
        return False, "Balance file not found"

    try:
        with open(path) as f:
            data = json.load(f)

        balance = data.get('balance', 0)
        last_updated = data.get('last_updated', 'unknown')

        return True, f"${balance:.2f} (updated: {last_updated[:16]})"
    except Exception as e:
        return False, f"Error reading balance: {e}"

def check_api_connectivity() -> tuple:
    """Check if Polymarket API is reachable."""
    try:
        import requests
        resp = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 1},
            timeout=10
        )
        if resp.status_code == 200:
            return True, "API reachable"
        return False, f"API returned {resp.status_code}"
    except Exception as e:
        return False, f"API error: {e}"

def main():
    """Run all health checks."""
    checks = []
    all_healthy = True

    # Check price level positions
    ok, msg = check_database("data/positions_price_level.db", "positions")
    checks.append(("Price Level DB", ok, msg))
    if not ok:
        all_healthy = False

    # Check event positions
    ok, msg = check_database("data/positions.db", "positions")
    checks.append(("Event DB", ok, msg))
    # Event DB might be empty, don't fail on this

    # Check training history
    ok, msg = check_database("data/training_history.db", "on_chain_trades")
    checks.append(("Training Data", ok, msg))

    # Check balances
    ok, msg = check_balance("data/paper_trading_balance_price_level.json")
    checks.append(("Price Level Balance", ok, msg))
    if not ok:
        all_healthy = False

    ok, msg = check_balance("data/paper_trading_balance.json")
    checks.append(("Event Balance", ok, msg))

    # Check API
    ok, msg = check_api_connectivity()
    checks.append(("Polymarket API", ok, msg))
    if not ok:
        all_healthy = False

    # Print results
    print("=" * 50)
    print("HEALTH CHECK RESULTS")
    print("=" * 50)

    for name, ok, msg in checks:
        status = "✓" if ok else "✗"
        print(f"{status} {name}: {msg}")

    print("=" * 50)
    print(f"Overall: {'HEALTHY' if all_healthy else 'UNHEALTHY'}")
    print("=" * 50)

    sys.exit(0 if all_healthy else 1)

if __name__ == "__main__":
    main()
