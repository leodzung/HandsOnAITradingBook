#!/usr/bin/env python3
"""
Resolution Backfiller

Continuously labels unlabeled market snapshots by cross-referencing with
resolved markets from the Gamma batch API. Runs every 30 minutes as a
background service.

Two resolution paths:
  Path A (fast): Gamma batch API - fetches 100 resolved markets per call,
                 inverts lookup to find which snapshots can be labeled.
  Path B (fallback): Per-market CLOB API call for condition_ids not found
                     in Path A batch results.

Created: 2026-03-08
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_FILE = "data/backfill_state.json"
GAMMA_URL = "https://gamma-api.polymarket.com"


class ResolutionBackfiller:
    """
    Labels unlabeled market snapshots by fetching resolved markets from
    the Gamma batch API and falling back to per-market CLOB calls.
    """

    def __init__(self,
                 snapshot_db: str = "data/market_snapshots.db",
                 config_path: str = "config/config_short_expiry.json"):
        """
        Args:
            snapshot_db: Path to market_snapshots.db
            config_path: Path to config JSON (used to init PolymarketClient)
        """
        import sys
        from pathlib import Path as _Path
        sys.path.insert(0, str(_Path(__file__).parent.parent.parent))

        from src.ml.snapshot_collector import MarketSnapshotCollector
        from src.core.polymarket_client import PolymarketClient

        with open(config_path) as f:
            config = json.load(f)

        self.snapshot_collector = MarketSnapshotCollector(db_path=snapshot_db)
        self.client = PolymarketClient(config=config)
        self.snapshot_db = Path(snapshot_db)
        self.state_file = Path(STATE_FILE)

    # ------------------------------------------------------------------
    # State persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> Dict:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_state(self, state: Dict):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    # ------------------------------------------------------------------
    # Path A: Gamma batch API
    # ------------------------------------------------------------------

    def _fetch_resolved_from_gamma(self, since_date: str,
                                    target_cids: Optional[set] = None) -> Dict[str, str]:
        """
        Fetch recently-resolved markets from the Gamma batch API.

        Streams pages from the API, only retaining outcomes for condition_ids
        in `target_cids` to keep memory usage O(target_cids) rather than
        O(all Gamma markets).

        Args:
            since_date: ISO date string — only markets closed after this date.
            target_cids: Set of condition_ids we care about.  When all have been
                         found, pagination stops early.  Pass None to collect all.

        Returns:
            Dict mapping condition_id -> 'YES' | 'NO'  (INVALID markets skipped)
        """
        import requests as _requests

        outcomes: Dict[str, str] = {}
        remaining = set(target_cids) if target_cids else None
        offset = 0
        batch_size = 100

        logger.info(f"Path A: fetching resolved markets since {since_date} "
                    f"(target={len(target_cids) if target_cids else 'all'})")

        while True:
            # Early exit once we've matched every target
            if remaining is not None and len(remaining) == 0:
                logger.info("Path A: all target condition_ids matched — stopping early")
                break

            try:
                self.client._gamma_rate_limit()
                response = _requests.get(
                    f"{GAMMA_URL}/markets",
                    params={
                        "closed": "true",
                        "end_date_min": since_date,
                        "limit": batch_size,
                        "offset": offset,
                    },
                    timeout=30,
                )
                response.raise_for_status()
                markets = response.json()
            except Exception as e:
                logger.warning(f"Path A batch fetch error (offset={offset}): {e}")
                break

            if not markets:
                break

            for market in markets:
                cid = market.get("conditionId") or market.get("condition_id")
                if not cid:
                    continue

                # Skip if we don't need this condition_id
                if remaining is not None and cid not in remaining:
                    continue

                prices = market.get("outcomePrices", [])
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except Exception:
                        continue

                if not prices or len(prices) < 2:
                    continue

                try:
                    p0, p1 = float(prices[0]), float(prices[1])
                except Exception:
                    continue

                if p0 >= 0.99 and p1 <= 0.01:
                    outcomes[cid] = "YES"
                    if remaining is not None:
                        remaining.discard(cid)
                elif p1 >= 0.99 and p0 <= 0.01:
                    outcomes[cid] = "NO"
                    if remaining is not None:
                        remaining.discard(cid)
                # else: ambiguous / INVALID — skip

            logger.debug(f"  Batch offset={offset}, matched={len(outcomes)}, "
                         f"remaining={len(remaining) if remaining is not None else '?'}")
            offset += batch_size

            if len(markets) < batch_size:
                break  # Last page

        logger.info(f"Path A complete: {len(outcomes)} resolved markets matched")
        return outcomes

    # ------------------------------------------------------------------
    # Path B: per-market CLOB fallback
    # ------------------------------------------------------------------

    def _check_market_outcome_clob(self, condition_id: str) -> Optional[str]:
        """
        Check a single market via the CLOB API (same logic as SnapshotLabeler).

        Returns:
            'YES', 'NO', 'INVALID', or None (not resolved yet)
        """
        try:
            market = self.client.get_market(condition_id)
            if not market:
                return None
            if not market.get("closed", False):
                return None

            prices = market.get("outcomePrices", ["0.5", "0.5"])
            if prices[0] == "1" or float(prices[0]) > 0.95:
                return "YES"
            elif prices[1] == "1" or float(prices[1]) > 0.95:
                return "NO"
            else:
                return "INVALID"
        except Exception as e:
            logger.debug(f"Path B CLOB error for {condition_id[:16]}: {e}")
            return None

    # ------------------------------------------------------------------
    # Query unlabeled snapshots that are past expiry
    # ------------------------------------------------------------------

    def _get_expired_unlabeled_condition_ids(self) -> List[str]:
        """
        Return unique condition_ids for unlabeled snapshots whose expiry_date
        has already passed.  Filters to short_expiry bot type.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.snapshot_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT COALESCE(condition_id, market_id)
            FROM market_snapshots
            WHERE labeled = 0
              AND bot_type = 'short_expiry'
              AND expiry_date IS NOT NULL
              AND expiry_date <= ?
            """,
            (now_iso,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows if row[0]]

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run_backfill(self, lookback_days: int = 30) -> Dict:
        """
        Run one backfill pass.

        Args:
            lookback_days: How many days back to query the Gamma API for
                           resolved markets.

        Returns:
            Summary dict with counts.
        """
        logger.info("=" * 60)
        logger.info("RESOLUTION BACKFILLER - starting pass")
        logger.info("=" * 60)

        state = self._load_state()

        since_date = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
        ).strftime("%Y-%m-%d")

        # Step 1: get condition_ids of expired unlabeled snapshots
        expired_cids = set(self._get_expired_unlabeled_condition_ids())
        logger.info(f"Expired unlabeled snapshots: {len(expired_cids)} unique condition_ids")

        if not expired_cids:
            logger.info("Nothing to label — all expired snapshots already labeled.")
            state["last_backfill_time"] = datetime.now(timezone.utc).isoformat()
            self._save_state(state)
            return {"labeled": 0, "not_resolved": 0, "errors": 0}

        # Step 2: Path A — Gamma batch fetch (streaming, only collects target cids)
        gamma_outcomes = self._fetch_resolved_from_gamma(since_date, target_cids=expired_cids)

        # Step 3: Intersect
        matched_cids = expired_cids & set(gamma_outcomes.keys())
        unmatched_cids = expired_cids - matched_cids

        logger.info(
            f"Path A matched {len(matched_cids)}/{len(expired_cids)} condition_ids; "
            f"{len(unmatched_cids)} fall back to Path B"
        )

        labeled = 0
        not_resolved = 0
        errors = 0

        # Step 4: Label Path A matches
        for cid in matched_cids:
            outcome = gamma_outcomes[cid]
            resolution_price = 1.0 if outcome == "YES" else 0.0
            try:
                self.snapshot_collector.record_outcome(
                    market_id=cid,
                    bot_type="short_expiry",
                    outcome=outcome,
                    resolution_price=resolution_price,
                )
                labeled += 1
                logger.debug(f"[A] Labeled {cid[:16]}... → {outcome}")
            except Exception as e:
                logger.error(f"Error recording outcome for {cid[:16]}: {e}")
                errors += 1

        # Step 5: Path B fallback for unmatched
        for idx, cid in enumerate(sorted(unmatched_cids), 1):
            if idx % 20 == 0:
                logger.info(f"Path B progress: {idx}/{len(unmatched_cids)}")

            outcome = self._check_market_outcome_clob(cid)

            if outcome is None:
                not_resolved += 1
                continue

            if outcome == "INVALID":
                # Record as INVALID so snapshot is labeled (won't be used for training)
                resolution_price = 0.5
            elif outcome == "YES":
                resolution_price = 1.0
            else:
                resolution_price = 0.0

            try:
                self.snapshot_collector.record_outcome(
                    market_id=cid,
                    bot_type="short_expiry",
                    outcome=outcome,
                    resolution_price=resolution_price,
                )
                labeled += 1
                logger.debug(f"[B] Labeled {cid[:16]}... → {outcome}")
            except Exception as e:
                logger.error(f"Error recording outcome for {cid[:16]}: {e}")
                errors += 1

            time.sleep(0.1)  # CLOB rate limit

        # Step 6: Persist state
        state["last_backfill_time"] = datetime.now(timezone.utc).isoformat()
        state["last_labeled_count"] = labeled
        self._save_state(state)

        # Step 7: Report
        stats = self.snapshot_collector.get_statistics()
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE")
        logger.info(f"  Newly labeled:   {labeled}")
        logger.info(f"  Not resolved:    {not_resolved}")
        logger.info(f"  Errors:          {errors}")
        logger.info(f"  Total labeled:   {stats['labeled_snapshots']:,} / {stats['total_snapshots']:,} "
                    f"({stats['labeling_rate']:.1f}%)")
        logger.info("=" * 60)

        return {"labeled": labeled, "not_resolved": not_resolved, "errors": errors}
