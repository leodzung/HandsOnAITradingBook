#!/usr/bin/env python3
"""
Automated Model Retraining CLI

Provides command-line interface for automated model retraining with multiple modes:
- Check triggers only (no training)
- Force retraining (bypass triggers)
- Dry run (train but don't deploy)
- Daemon mode (run periodically)

Usage Examples:
    # Check if retraining needed
    python scripts/auto_retrain.py --check

    # Force retraining immediately
    python scripts/auto_retrain.py --force

    # Dry run (train but don't deploy)
    python scripts/auto_retrain.py --dry-run

    # Daemon mode (check daily)
    python scripts/auto_retrain.py --daemon --interval 86400

Created: 2026-02-26 (Automated Model Staleness Enforcement)
"""

import sys
import time
import logging
import argparse
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from ml.auto_retrainer import AutoRetrainer

# Optional Telegram support
try:
    from monitoring.telegram_notifier import TelegramNotifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramNotifier = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_triggers_only(retrainer: AutoRetrainer):
    """Check retraining triggers without executing retraining."""
    logger.info("🔍 Checking retraining triggers...")

    should_retrain, reasons = retrainer.should_retrain()

    print("\n" + "="*70)
    print("RETRAINING TRIGGER CHECK")
    print("="*70)

    if should_retrain:
        print(f"\n🔔 RETRAINING RECOMMENDED ({len(reasons)} trigger(s))")
        for i, reason in enumerate(reasons, 1):
            print(f"  {i}. {reason}")
        print("\nRun with --force to execute retraining")
        return 1  # Exit code 1 = action needed
    else:
        print("\n✓ NO RETRAINING NEEDED")
        print("  All models are healthy and up-to-date")
        return 0


def force_retraining(retrainer: AutoRetrainer, dry_run: bool = False):
    """Force retraining regardless of triggers."""
    logger.info("🚀 Starting forced retraining...")

    if dry_run:
        logger.info("⚠️  DRY RUN MODE - Models will not be deployed")

    result = retrainer.run_full_retraining(dry_run=dry_run)

    # Print summary
    print("\n" + "="*70)
    print("RETRAINING SUMMARY")
    print("="*70)
    print(f"\nStatus: {'✅ SUCCESS' if result['success'] else '❌ FAILED'}")
    print(f"Duration: {result.get('duration_seconds', 0):.1f}s")

    if result['success']:
        print(f"\nMetrics:")
        metrics = result.get('metrics', {})
        print(f"  • AUC: {metrics.get('roc_auc', 0):.4f}")
        print(f"  • Accuracy: {metrics.get('accuracy', 0):.4f}")
        print(f"  • Precision: {metrics.get('precision', 0):.4f}")
        print(f"  • Recall: {metrics.get('recall', 0):.4f}")
        print(f"\nTraining Samples: {result.get('training_samples', 'N/A'):,}")

        if not dry_run:
            print(f"\n✅ New models deployed successfully")
            print(f"   Backups saved: {len(result.get('backup_paths', []))} files")
        else:
            print(f"\n⚠️  Dry run complete - models NOT deployed")

        return 0
    else:
        print(f"\nErrors:")
        for error in result.get('errors', []):
            print(f"  ❌ {error}")
        return 1


def daemon_mode(retrainer: AutoRetrainer, interval: int, dry_run: bool = False):
    """Run in daemon mode with periodic checking."""
    logger.info(f"🔄 Starting daemon mode (interval: {interval}s)")

    if dry_run:
        logger.info("⚠️  DRY RUN MODE - Models will not be deployed")

    try:
        while True:
            start_time = time.time()

            logger.info(f"\n{'='*70}")
            logger.info(f"⏰ Daemon check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*70}")

            # Check triggers
            should_retrain, reasons = retrainer.should_retrain()

            if should_retrain:
                logger.info(f"🔔 Retraining triggered: {', '.join(reasons)}")

                # Execute retraining
                result = retrainer.run_full_retraining(dry_run=dry_run)

                if result['success']:
                    logger.info("✅ Automated retraining completed successfully")
                else:
                    logger.error(f"❌ Automated retraining failed: {result.get('errors')}")
            else:
                logger.info("✓ No retraining needed - all models healthy")

            # Sleep until next interval
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)

            if sleep_time > 0:
                logger.info(f"💤 Sleeping for {sleep_time:.0f}s until next check")
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("\n⏹️  Stopping daemon mode")
        return 0
    except Exception as e:
        logger.error(f"❌ Daemon error: {e}", exc_info=True)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Automated model retraining system',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --check                    # Check triggers only
  %(prog)s --force                    # Force immediate retraining
  %(prog)s --dry-run                  # Train but don't deploy
  %(prog)s --daemon --interval 86400  # Run daily (86400s = 24h)
  %(prog)s --daemon --interval 3600   # Run hourly (3600s = 1h)

Retraining Triggers:
  1. Model age > 25 days
  2. Model AUC < 0.70
  3. Significant feature drift detected

Quality Gates (must pass to deploy):
  • ROC-AUC >= 0.70
  • Accuracy >= 0.60
        """
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--check', action='store_true',
                            help='Check triggers only (no retraining)')
    mode_group.add_argument('--force', action='store_true',
                            help='Force retraining (bypass triggers)')
    mode_group.add_argument('--daemon', action='store_true',
                            help='Run in daemon mode (periodic checks)')

    # Options
    parser.add_argument('--dry-run', action='store_true',
                        help='Train but do not deploy models')
    parser.add_argument('--interval', type=int, default=86400,
                        help='Daemon check interval in seconds (default: 86400 = 24h)')
    parser.add_argument('--training-data', type=str,
                        default='data/labeled_training_data.csv',
                        help='Path to training data CSV')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')

    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize Telegram (optional)
    telegram = None
    if TELEGRAM_AVAILABLE:
        try:
            telegram = TelegramNotifier()
            logger.info("✓ Telegram notifications enabled")
        except Exception as e:
            logger.warning(f"Telegram not configured: {e}")

    # Initialize retrainer
    try:
        retrainer = AutoRetrainer(
            training_data_path=args.training_data,
            telegram=telegram
        )
    except Exception as e:
        logger.error(f"❌ Failed to initialize retrainer: {e}")
        return 2

    # Execute requested mode
    try:
        if args.check:
            return check_triggers_only(retrainer)
        elif args.force:
            return force_retraining(retrainer, dry_run=args.dry_run)
        elif args.daemon:
            return daemon_mode(retrainer, args.interval, dry_run=args.dry_run)
        else:
            # Default: check triggers and retrain if needed
            should_retrain, reasons = retrainer.should_retrain()

            if should_retrain:
                logger.info(f"Retraining triggered: {', '.join(reasons)}")
                return force_retraining(retrainer, dry_run=args.dry_run)
            else:
                logger.info("No retraining needed")
                return 0

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
