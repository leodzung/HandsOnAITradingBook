#!/usr/bin/env python3
"""
Label Unlabeled Market Snapshots

Backfills outcomes for market snapshots after markets resolve.
This creates the labeled training dataset needed for walk-forward validation.

WORKFLOW:
  1. Get unlabeled snapshots from market_snapshots.db
  2. Check if markets have resolved (via Polymarket API)
  3. Record outcomes in database
  4. Update statistics

USAGE:
  python3 scripts/label_snapshots.py --dry-run  # Preview what would be labeled
  python3 scripts/label_snapshots.py            # Actually label snapshots

Created: 2026-02-20
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import argparse
import json
import time
from datetime import datetime, timezone

from src.ml.snapshot_collector import MarketSnapshotCollector
from src.core.polymarket_client import PolymarketClient
from src.monitoring.telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SnapshotLabeler:
    """Label resolved markets in snapshot database."""

    def __init__(self,
                 snapshot_db: str = 'data/market_snapshots.db',
                 config_path: str = 'config/config_short_expiry.json'):
        """
        Initialize labeler.

        Args:
            snapshot_db: Path to market snapshots database
            config_path: Path to config (for Polymarket API)
        """
        self.snapshot_collector = MarketSnapshotCollector(db_path=snapshot_db)

        # Load config
        with open(config_path) as f:
            self.config = json.load(f)

        # Initialize Polymarket client
        self.client = PolymarketClient(config=self.config)

        # Telegram notifications (optional)
        telegram_config = self.config.get('telegram', {})
        self.telegram = TelegramNotifier(
            bot_token=telegram_config.get('bot_token', ''),
            chat_id=telegram_config.get('chat_id', ''),
            enabled=telegram_config.get('enabled', False)
        )

    def get_market_outcome(self, market_id: str) -> tuple:
        """
        Get resolved outcome for a market.

        Args:
            market_id: Market condition_id

        Returns:
            Tuple of (outcome, resolution_price) or (None, None) if not resolved
        """
        try:
            market = self.client.get_market(market_id)

            if not market:
                logger.debug(f"Market not found: {market_id[:16]}...")
                return None, None

            # Check if market is closed/resolved
            if not market.get('closed', False):
                logger.debug(f"Market still active: {market_id[:16]}...")
                return None, None

            # Get outcome from market data
            # Polymarket API typically has 'winning_outcome' or we can infer from token prices
            outcome_prices = market.get('outcomePrices', ['0.5', '0.5'])

            if outcome_prices[0] == '1' or float(outcome_prices[0]) > 0.95:
                outcome = 'YES'
                resolution_price = 1.0
            elif outcome_prices[1] == '1' or float(outcome_prices[1]) > 0.95:
                outcome = 'NO'
                resolution_price = 0.0
            else:
                # Market didn't clearly resolve
                logger.debug(f"Unclear resolution: {market_id[:16]}... prices={outcome_prices}")
                outcome = 'INVALID'
                resolution_price = 0.5

            return outcome, resolution_price

        except Exception as e:
            logger.debug(f"Error checking market {market_id[:16]}...: {e}")
            return None, None

    def label_snapshots(self, dry_run: bool = False, max_snapshots: int = None):
        """
        Label unlabeled snapshots.

        Args:
            dry_run: If True, only preview what would be labeled
            max_snapshots: Maximum snapshots to process (None = all)
        """
        logger.info("="*70)
        logger.info("SNAPSHOT LABELING")
        logger.info("="*70)

        # Get unlabeled snapshots
        unlabeled = self.snapshot_collector.get_unlabeled_snapshots(bot_type='short_expiry')

        if not unlabeled:
            logger.info("No unlabeled snapshots found!")
            return

        logger.info(f"Found {len(unlabeled)} unlabeled snapshots")

        if max_snapshots:
            unlabeled = unlabeled[:max_snapshots]
            logger.info(f"Processing first {max_snapshots} snapshots")

        # Group by market_id to avoid duplicate API calls
        markets_to_check = {}
        for snapshot in unlabeled:
            market_id = snapshot.get('market_id') or snapshot.get('condition_id')
            if market_id:
                if market_id not in markets_to_check:
                    markets_to_check[market_id] = []
                markets_to_check[market_id].append(snapshot)

        logger.info(f"Checking {len(markets_to_check)} unique markets")

        # Process markets
        labeled_count = 0
        not_resolved_count = 0
        error_count = 0

        for idx, (market_id, snapshots) in enumerate(markets_to_check.items(), 1):
            if idx % 10 == 0:
                logger.info(f"Progress: {idx}/{len(markets_to_check)} markets")

            # Get outcome
            outcome, resolution_price = self.get_market_outcome(market_id)

            if outcome is None:
                not_resolved_count += len(snapshots)
                continue

            # Label all snapshots for this market
            if dry_run:
                logger.info(f"[DRY RUN] Would label {len(snapshots)} snapshots: {market_id[:16]}... → {outcome}")
                labeled_count += len(snapshots)
            else:
                try:
                    self.snapshot_collector.record_outcome(
                        market_id=market_id,
                        bot_type='short_expiry',
                        outcome=outcome,
                        resolution_price=resolution_price
                    )
                    labeled_count += len(snapshots)
                    logger.debug(f"Labeled {len(snapshots)} snapshots: {market_id[:16]}... → {outcome}")
                except Exception as e:
                    logger.error(f"Error labeling {market_id[:16]}...: {e}")
                    error_count += len(snapshots)

            # Rate limiting
            time.sleep(0.1)

        # Summary
        logger.info("\n" + "="*70)
        logger.info("LABELING SUMMARY")
        logger.info("="*70)
        logger.info(f"Labeled: {labeled_count}")
        logger.info(f"Not resolved: {not_resolved_count}")
        logger.info(f"Errors: {error_count}")

        if dry_run:
            logger.info("\n⚠️  DRY RUN - No changes made")
            logger.info("Run without --dry-run to actually label snapshots")
        else:
            # Get updated statistics
            stats = self.snapshot_collector.get_statistics()
            logger.info(f"\nUpdated Statistics:")
            logger.info(f"  Total snapshots: {stats['total_snapshots']:,}")
            logger.info(f"  Labeled: {stats['labeled_snapshots']:,} ({stats['labeling_rate']:.1f}%)")
            logger.info(f"  Unlabeled: {stats['unlabeled_snapshots']:,}")

            if stats['labeled_snapshots'] >= 200:
                logger.info("\n✅ Sufficient data for training (200+ labeled samples)")
                logger.info("Run: python3 scripts/train_short_expiry_forward_validation.py")
            else:
                needed = 200 - stats['labeled_snapshots']
                logger.info(f"\n⏳ Need {needed} more labeled samples for training")

            # Send Telegram notification
            if self.telegram and labeled_count > 0:
                message = (
                    f"<b>🏷️ SNAPSHOT LABELING COMPLETE</b>\n\n"
                    f"<b>Newly Labeled:</b> {labeled_count}\n"
                    f"<b>Not Resolved:</b> {not_resolved_count}\n\n"
                    f"<b>Database Status:</b>\n"
                    f"  Total: {stats['total_snapshots']:,}\n"
                    f"  Labeled: {stats['labeled_snapshots']:,} ({stats['labeling_rate']:.1f}%)\n"
                    f"  Unlabeled: {stats['unlabeled_snapshots']:,}\n\n"
                )

                if stats['labeled_snapshots'] >= 200:
                    message += f"<b>Status:</b> Ready for training ✅"
                else:
                    message += f"<b>Status:</b> Need {200 - stats['labeled_snapshots']} more samples"

                self.telegram.send_message(message)


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description='Label resolved market snapshots')

    parser.add_argument('--dry-run', action='store_true',
                       help='Preview what would be labeled without making changes')

    parser.add_argument('--max-snapshots', type=int, default=None,
                       help='Maximum snapshots to process (default: all)')

    parser.add_argument('--snapshot-db', type=str, default='data/market_snapshots.db',
                       help='Path to market snapshots database')

    parser.add_argument('--config', type=str, default='config/config_short_expiry.json',
                       help='Path to config file')

    args = parser.parse_args()

    # Initialize labeler
    labeler = SnapshotLabeler(
        snapshot_db=args.snapshot_db,
        config_path=args.config
    )

    # Run labeling
    labeler.label_snapshots(
        dry_run=args.dry_run,
        max_snapshots=args.max_snapshots
    )

    logger.info("\n✅ Labeling complete!")


if __name__ == '__main__':
    main()
