#!/usr/bin/env python3
"""
Check Outcomes - Cron job to check price movements
Run this hourly to update tracked event outcomes
"""

import sys
from price_tracker import PriceTracker
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('price_tracker.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Check outcomes for all pending tracking entries."""
    try:
        logger.info("=" * 70)
        logger.info("CHECKING PRICE OUTCOMES")
        logger.info("=" * 70)

        tracker = PriceTracker()

        # Get current stats
        stats = tracker.get_statistics()
        logger.info(f"Total tracked: {stats['total_tracked']}")
        logger.info(f"Pending: {stats['pending']}")
        logger.info(f"Completed: {stats['completed']}")

        if stats['pending'] == 0:
            logger.info("No pending entries to check")
            return 0

        # Check outcomes
        updated = tracker.check_outcomes()
        logger.info(f"Updated {updated} entries")

        # Export if we have enough completed samples
        new_stats = tracker.get_statistics()
        if new_stats['completed'] >= 10:
            logger.info("Exporting labeled dataset...")
            count = tracker.export_to_csv()
            logger.info(f"Exported {count} samples")

        logger.info("Check complete")
        return 0

    except Exception as e:
        logger.error(f"Error checking outcomes: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
