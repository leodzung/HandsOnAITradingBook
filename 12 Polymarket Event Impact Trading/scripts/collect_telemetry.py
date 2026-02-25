#!/usr/bin/env python3
"""
Telemetry Collection Script

Periodically collects system metrics and stores them in the telemetry database.
Can be run manually, via cron, or as a daemon for continuous monitoring.

Usage:
    # One-shot collection
    python scripts/collect_telemetry.py

    # Continuous collection (every 5 minutes)
    python scripts/collect_telemetry.py --daemon --interval 300

    # With constraint validation
    python scripts/collect_telemetry.py --validate

Created: 2026-02-24 (Phase 3: Telemetry Integration)
"""

import sys
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from monitoring.telemetry import TradeTelemetry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def collect_metrics(telemetry: TradeTelemetry):
    """Collect all system metrics."""
    logger.info("📊 Collecting system metrics...")

    try:
        # Collect from all sources
        telemetry.collect_system_metrics()

        # Get latest metrics to verify
        metrics = telemetry.get_latest_metrics()
        logger.info(f"✅ Collected {len(metrics)} metrics")

        # Log summary
        for key in ['bots_silent', 'open_positions_event_trader', 'open_positions_price_level_trader']:
            if key in metrics:
                logger.info(f"  {key}: {metrics[key]}")

    except Exception as e:
        logger.error(f"❌ Error collecting metrics: {e}")
        raise


def validate_telemetry(telemetry: TradeTelemetry):
    """Run constraint validation with telemetry checks."""
    logger.info("🔍 Running constraint validation with telemetry...")

    try:
        import subprocess

        result = subprocess.run(
            ['python', 'scripts/validate_constraints.py', '--ci'],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            logger.info("✅ All constraints satisfied (including telemetry)")
        else:
            logger.warning("⚠️  Constraint violations detected")
            # Print violations
            for line in result.stdout.split('\n'):
                if 'FAILED' in line or 'Telemetry:' in line:
                    logger.warning(f"  {line}")

    except Exception as e:
        logger.error(f"❌ Error running validation: {e}")


def daemon_mode(interval: int, validate: bool):
    """Run in daemon mode with periodic collection."""
    logger.info(f"🔄 Starting telemetry collection daemon (interval: {interval}s)")

    telemetry = TradeTelemetry()

    try:
        while True:
            start_time = time.time()

            # Collect metrics
            collect_metrics(telemetry)

            # Optionally validate
            if validate:
                validate_telemetry(telemetry)

            # Sleep until next interval
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)

            if sleep_time > 0:
                logger.info(f"💤 Sleeping for {sleep_time:.0f}s until next collection")
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("⏹️  Stopping telemetry collection daemon")
    except Exception as e:
        logger.error(f"❌ Daemon error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description='Collect system telemetry metrics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # One-shot collection
  %(prog)s --daemon --interval 300   # Continuous (every 5 min)
  %(prog)s --validate                # Collect + validate constraints
  %(prog)s --daemon --validate       # Continuous with validation
        """
    )
    parser.add_argument('--daemon', action='store_true',
                        help='Run in daemon mode (continuous)')
    parser.add_argument('--interval', type=int, default=300,
                        help='Collection interval in seconds (default: 300)')
    parser.add_argument('--validate', action='store_true',
                        help='Run constraint validation after collection')

    args = parser.parse_args()

    try:
        if args.daemon:
            daemon_mode(args.interval, args.validate)
        else:
            # One-shot mode
            telemetry = TradeTelemetry()
            collect_metrics(telemetry)

            if args.validate:
                validate_telemetry(telemetry)

            logger.info("✅ Telemetry collection complete")

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
