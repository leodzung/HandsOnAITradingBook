#!/usr/bin/env python3
"""Docker health check for Polymarket trading containers.

Usage:
    python scripts/docker_healthcheck.py --service event-trader

Checks that the target file exists AND was modified within max_stale_minutes,
proving the bot is alive and actively writing data.

Exit codes:
    0 = healthy (file exists and recently modified)
    1 = unhealthy (file missing or stale)
"""

import argparse
import os
import sys
import time

SERVICE_CHECKS = {
    "event-trader": {
        "path": "/app/data/positions.db",
        "max_stale_minutes": 30,
    },
    "price-level-trader": {
        "path": "/app/data/positions_price_level.db",
        "max_stale_minutes": 120,
    },
    "short-expiry-trader": {
        "path": "/app/data/positions_short_expiry.db",
        "max_stale_minutes": 30,
    },
    "arbitrage-bot": {
        "path": "/app/data/arbitrage",
        "max_stale_minutes": 10,
    },
    "gdelt-collector": {
        "path": "/app/data/gdelt_news.db",
        "max_stale_minutes": 20,
    },
    "alchemy-collector": {
        "path": "/app/data/alchemy_trades.db",
        "max_stale_minutes": 20,
    },
}


def check_health(service: str) -> bool:
    check = SERVICE_CHECKS.get(service)
    if not check:
        print(f"Unknown service: {service}")
        return False

    path = check["path"]
    max_stale = check["max_stale_minutes"]

    if not os.path.exists(path):
        print(f"UNHEALTHY: {path} does not exist")
        return False

    mtime = os.path.getmtime(path)
    age_minutes = (time.time() - mtime) / 60.0

    if age_minutes > max_stale:
        print(f"UNHEALTHY: {path} last modified {age_minutes:.1f}m ago (max {max_stale}m)")
        return False

    print(f"HEALTHY: {path} modified {age_minutes:.1f}m ago")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Docker health check")
    parser.add_argument("--service", required=True, choices=SERVICE_CHECKS.keys())
    args = parser.parse_args()

    sys.exit(0 if check_health(args.service) else 1)
