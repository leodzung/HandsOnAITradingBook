#!/usr/bin/env python3
"""
Resolution Backfiller - CLI entrypoint

Labels unlabeled market snapshots by cross-referencing with recently-resolved
markets from the Gamma batch API, with per-market CLOB fallback.

Usage:
  python scripts/run_resolution_backfiller.py                     # default 30-day lookback
  python scripts/run_resolution_backfiller.py --lookback-days 60  # longer lookback
  python scripts/run_resolution_backfiller.py --config config/config_short_expiry.json
"""

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


def _setup_logging(log_file: str = "logs/resolution_backfiller.log"):
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path),
        ],
    )


def main():
    parser = argparse.ArgumentParser(description="Label resolved market snapshots via Gamma batch API")
    parser.add_argument("--lookback-days", type=int, default=30,
                        help="Days back to query Gamma for resolved markets (default: 30)")
    parser.add_argument("--snapshot-db", type=str, default="data/market_snapshots.db",
                        help="Path to market snapshots database")
    parser.add_argument("--config", type=str, default="config/config_short_expiry.json",
                        help="Path to config file")
    args = parser.parse_args()

    _setup_logging()
    logger = logging.getLogger("run_resolution_backfiller")

    try:
        from src.collectors.resolution_backfiller import ResolutionBackfiller

        backfiller = ResolutionBackfiller(
            snapshot_db=args.snapshot_db,
            config_path=args.config,
        )

        summary = backfiller.run_backfill(lookback_days=args.lookback_days)

        logger.info(
            "Done: %d labeled, %d not resolved, %d errors",
            summary["labeled"], summary["not_resolved"], summary["errors"],
        )
        sys.exit(0)

    except Exception as e:
        logging.getLogger("run_resolution_backfiller").error(
            "Fatal error: %s", e, exc_info=True
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
