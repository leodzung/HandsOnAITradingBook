#!/usr/bin/env python3
"""
Bot Health Monitor
Dedicated monitoring service for trading bot health and data collection.

Features:
- Bot liveness checks (detects silent/crashed bots)
- Snapshot collection rate monitoring
- Anomaly detection (rate drops, asymmetric collection)
- Database health monitoring
- Telegram alerts for issues
- Alert deduplication to prevent spam

Usage:
    # One-shot check (for cron)
    python3 -m monitoring.bot_health_monitor --once

    # Continuous monitoring (daemon mode)
    python3 -m monitoring.bot_health_monitor --daemon --interval 900  # Check every 15 min

Created: 2026-02-15
"""

import sqlite3
import logging
import time
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class BotHealthMonitor:
    """
    Monitors trading bot health and data collection.

    Alerts on:
    - Bot silence (no snapshots in X minutes)
    - Collection rate drops (>50% decrease)
    - Bot asymmetry (one bot collecting way more than others)
    - Missing bots (expected bot not found)
    - Database growth anomalies
    """

    def __init__(self,
                 db_path: str = 'data/market_snapshots.db',
                 telegram: Optional[TelegramNotifier] = None,
                 config: Optional[Dict] = None):
        """
        Initialize bot health monitor.

        Args:
            db_path: Path to market snapshots database
            telegram: TelegramNotifier for alerts
            config: Configuration dict with thresholds
        """
        self.db_path = Path(db_path)
        self.telegram = telegram

        # Default configuration (can be overridden)
        self.config = {
            'expected_bots': ['event', 'price_level', 'short_expiry'],
            'silence_threshold_minutes': 30,  # Alert if no snapshots in 30 min
            'rate_drop_threshold': 0.5,  # Alert if rate drops >50%
            'asymmetry_threshold': 5.0,  # Alert if one bot collects 5x more than another
            'min_snapshots_for_rate_check': 10,  # Need baseline data
            'lookback_hours': 2,  # Compare current rate to last 2 hours
            'alert_cooldown_minutes': 60,  # Don't re-alert for same issue within 1 hour
        }

        if config:
            self.config.update(config)

        # Alert tracking (prevent spam)
        self.last_alerts = {}  # {alert_type: timestamp}
        self.alert_state_file = Path('data/bot_health_alerts.json')
        self._load_alert_state()

        logger.info(f"BotHealthMonitor initialized: {self.db_path}")

    def _load_alert_state(self):
        """Load previous alert state to prevent re-alerting."""
        if self.alert_state_file.exists():
            try:
                with open(self.alert_state_file, 'r') as f:
                    data = json.load(f)
                    # Convert ISO timestamps back to datetime
                    self.last_alerts = {
                        k: datetime.fromisoformat(v)
                        for k, v in data.items()
                    }
            except Exception as e:
                logger.warning(f"Could not load alert state: {e}")

    def _save_alert_state(self):
        """Save alert state to disk."""
        try:
            self.alert_state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                k: v.isoformat()
                for k, v in self.last_alerts.items()
            }
            with open(self.alert_state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save alert state: {e}")

    def _should_alert(self, alert_key: str) -> bool:
        """Check if we should send alert (not in cooldown period)."""
        if alert_key not in self.last_alerts:
            return True

        last_alert_time = self.last_alerts[alert_key]
        cooldown = timedelta(minutes=self.config['alert_cooldown_minutes'])

        return (datetime.now(timezone.utc) - last_alert_time) > cooldown

    def _record_alert(self, alert_key: str):
        """Record that we sent an alert."""
        self.last_alerts[alert_key] = datetime.now(timezone.utc)
        self._save_alert_state()

    def _send_alert(self, alert_key: str, message: str, severity: str = 'warning'):
        """Send alert via Telegram if not in cooldown."""
        if not self.telegram:
            logger.warning(f"No Telegram configured. Alert: {message}")
            return

        if not self._should_alert(alert_key):
            logger.debug(f"Alert in cooldown: {alert_key}")
            return

        # Add severity emoji
        emoji = {
            'critical': '🚨',
            'warning': '⚠️',
            'info': 'ℹ️',
            'resolved': '✅'
        }.get(severity, '⚠️')

        formatted_message = f"{emoji} <b>BOT HEALTH ALERT</b>\n\n{message}"

        try:
            self.telegram.send_message(formatted_message)
            self._record_alert(alert_key)
            logger.info(f"Sent alert: {alert_key}")
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    def check_bot_liveness(self) -> List[str]:
        """
        Check if all expected bots have collected data recently.

        Returns:
            List of issues found (empty if all healthy)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        threshold = datetime.now(timezone.utc) - timedelta(
            minutes=self.config['silence_threshold_minutes']
        )

        # Get last snapshot time per bot
        cursor.execute("""
            SELECT bot_type, MAX(snapshot_time) as last_snapshot, COUNT(*) as total
            FROM market_snapshots
            GROUP BY bot_type
        """)

        bot_status = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        conn.close()

        issues = []

        for bot_type in self.config['expected_bots']:
            if bot_type not in bot_status:
                # Bot has never collected data
                issues.append(f"❌ {bot_type}: Never collected data (bot not running or not integrated)")
                self._send_alert(
                    f"missing_bot_{bot_type}",
                    f"<b>Bot Not Found</b>\n\n"
                    f"Bot: {bot_type}\n"
                    f"Status: Never collected any snapshots\n\n"
                    f"<b>Action Required:</b>\n"
                    f"1. Check if bot is running\n"
                    f"2. Verify snapshot collector integration\n"
                    f"3. Check logs for errors",
                    severity='critical'
                )
                continue

            last_snapshot_str, total_count = bot_status[bot_type]
            last_snapshot = datetime.fromisoformat(last_snapshot_str)

            if last_snapshot < threshold:
                # Bot is silent
                minutes_ago = (datetime.now(timezone.utc) - last_snapshot).total_seconds() / 60
                issues.append(f"⚠️  {bot_type}: Silent for {minutes_ago:.1f} minutes (last: {last_snapshot_str})")

                self._send_alert(
                    f"silent_bot_{bot_type}",
                    f"<b>Bot Silent</b>\n\n"
                    f"Bot: {bot_type}\n"
                    f"Last Snapshot: {minutes_ago:.1f} minutes ago\n"
                    f"Threshold: {self.config['silence_threshold_minutes']} minutes\n"
                    f"Total Snapshots: {total_count:,}\n\n"
                    f"<b>Possible Causes:</b>\n"
                    f"• Bot crashed or stopped\n"
                    f"• No matching markets found\n"
                    f"• API errors preventing data collection\n\n"
                    f"<b>Action Required:</b> Check bot logs and status",
                    severity='warning'
                )

        return issues

    def check_collection_rate(self) -> List[str]:
        """
        Check if snapshot collection rate has dropped significantly.

        Returns:
            List of issues found (empty if healthy)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        lookback_hours = self.config['lookback_hours']
        current_window = datetime.now(timezone.utc) - timedelta(minutes=30)
        baseline_window = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        issues = []

        for bot_type in self.config['expected_bots']:
            # Get current rate (last 30 minutes)
            cursor.execute("""
                SELECT COUNT(*) FROM market_snapshots
                WHERE bot_type = ? AND snapshot_time >= ?
            """, (bot_type, current_window.isoformat()))
            current_count = cursor.fetchone()[0]

            # Get baseline rate (full lookback period)
            cursor.execute("""
                SELECT COUNT(*) FROM market_snapshots
                WHERE bot_type = ? AND snapshot_time >= ?
            """, (bot_type, baseline_window.isoformat()))
            baseline_count = cursor.fetchone()[0]

            if baseline_count < self.config['min_snapshots_for_rate_check']:
                continue  # Not enough data for comparison

            # Calculate rates (snapshots per hour)
            current_rate = current_count * 2  # 30 min → hourly rate
            baseline_rate = baseline_count / lookback_hours

            if baseline_rate == 0:
                continue

            # Check for significant drop
            rate_ratio = current_rate / baseline_rate
            if rate_ratio < self.config['rate_drop_threshold']:
                drop_pct = (1 - rate_ratio) * 100
                issues.append(
                    f"📉 {bot_type}: Collection rate dropped {drop_pct:.0f}% "
                    f"(baseline: {baseline_rate:.1f}/hr, current: {current_rate:.1f}/hr)"
                )

                self._send_alert(
                    f"rate_drop_{bot_type}",
                    f"<b>Collection Rate Drop</b>\n\n"
                    f"Bot: {bot_type}\n"
                    f"Baseline Rate: {baseline_rate:.1f} snapshots/hour\n"
                    f"Current Rate: {current_rate:.1f} snapshots/hour\n"
                    f"Drop: {drop_pct:.0f}%\n\n"
                    f"<b>Possible Causes:</b>\n"
                    f"• Fewer markets available\n"
                    f"• Stricter filtering criteria\n"
                    f"• API rate limiting\n"
                    f"• Bot performance degradation",
                    severity='warning'
                )

        conn.close()
        return issues

    def check_bot_asymmetry(self) -> List[str]:
        """
        Check if one bot is collecting way more/less data than others.

        Returns:
            List of issues found (empty if healthy)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get snapshot counts per bot (last 24 hours)
        lookback = datetime.now(timezone.utc) - timedelta(hours=24)
        cursor.execute("""
            SELECT bot_type, COUNT(*) as count
            FROM market_snapshots
            WHERE snapshot_time >= ?
            GROUP BY bot_type
        """, (lookback.isoformat(),))

        counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        if len(counts) < 2:
            return []  # Need at least 2 bots to compare

        issues = []
        min_count = min(counts.values())
        max_count = max(counts.values())

        if min_count == 0:
            return []  # Handled by liveness check

        asymmetry_ratio = max_count / min_count

        if asymmetry_ratio > self.config['asymmetry_threshold']:
            bot_counts = ', '.join([f"{k}: {v}" for k, v in sorted(counts.items())])
            issues.append(
                f"⚖️  Bot asymmetry detected: {asymmetry_ratio:.1f}x difference ({bot_counts})"
            )

            max_bot = max(counts.items(), key=lambda x: x[1])
            min_bot = min(counts.items(), key=lambda x: x[1])

            self._send_alert(
                "bot_asymmetry",
                f"<b>Bot Collection Asymmetry</b>\n\n"
                f"Highest: {max_bot[0]} ({max_bot[1]:,} snapshots)\n"
                f"Lowest: {min_bot[0]} ({min_bot[1]:,} snapshots)\n"
                f"Ratio: {asymmetry_ratio:.1f}x difference\n\n"
                f"<b>All Bots (24h):</b>\n" +
                '\n'.join([f"  • {k}: {v:,}" for k, v in sorted(counts.items())]) +
                f"\n\n<b>Note:</b> Some asymmetry is normal due to different strategies, "
                f"but extreme differences may indicate issues.",
                severity='info'
            )

        return issues

    def check_database_health(self) -> List[str]:
        """
        Check database health metrics.

        Returns:
            List of issues found (empty if healthy)
        """
        issues = []

        # Check if database exists
        if not self.db_path.exists():
            issues.append("❌ Database file not found!")
            self._send_alert(
                "db_missing",
                f"<b>Database Missing</b>\n\n"
                f"Path: {self.db_path}\n"
                f"Status: File not found\n\n"
                f"<b>Action Required:</b> Database may have been deleted or moved.",
                severity='critical'
            )
            return issues

        # Check database size
        db_size_mb = self.db_path.stat().st_size / (1024 * 1024)

        # Warn if database is getting large (>100 MB)
        if db_size_mb > 100:
            issues.append(f"💾 Database size: {db_size_mb:.1f} MB (consider archiving old data)")

        # Check for corruption
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            conn.close()

            if result != 'ok':
                issues.append(f"⚠️  Database integrity check failed: {result}")
                self._send_alert(
                    "db_corruption",
                    f"<b>Database Integrity Issue</b>\n\n"
                    f"Check Result: {result}\n\n"
                    f"<b>Action Required:</b> Database may be corrupted. "
                    f"Consider restoring from backup.",
                    severity='critical'
                )
        except Exception as e:
            issues.append(f"❌ Database error: {e}")

        return issues

    def run_all_checks(self) -> Dict[str, List[str]]:
        """
        Run all health checks (including Alchemy collector).

        Returns:
            Dictionary of check results: {check_name: [issues]}
        """
        results = {
            'liveness': self.check_bot_liveness(),
            'collection_rate': self.check_collection_rate(),
            'asymmetry': self.check_bot_asymmetry(),
            'database': self.check_database_health()
        }

        # Add Alchemy collector checks
        alchemy_monitor = AlchemyCollectorMonitor(
            db_path='data/alchemy_trades.db',
            telegram=self.telegram,
            health_monitor=self  # Pass self for alert deduplication
        )
        alchemy_results = alchemy_monitor.run_all_checks()
        results.update(alchemy_results)

        return results

    def generate_health_report(self) -> str:
        """
        Generate human-readable health report.

        Returns:
            Formatted health report string
        """
        results = self.run_all_checks()

        report = ["=" * 60]
        report.append("BOT HEALTH MONITORING REPORT")
        report.append(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        report.append("=" * 60)

        total_issues = sum(len(issues) for issues in results.values())

        if total_issues == 0:
            report.append("\n✅ ALL SYSTEMS HEALTHY\n")
        else:
            report.append(f"\n⚠️  {total_issues} ISSUE(S) FOUND\n")

        for check_name, issues in results.items():
            report.append(f"\n{check_name.upper()} CHECK:")
            if issues:
                for issue in issues:
                    report.append(f"  {issue}")
            else:
                report.append("  ✅ OK")

        report.append("\n" + "=" * 60)

        return '\n'.join(report)

    def send_health_summary(self):
        """Send health summary via Telegram."""
        if not self.telegram:
            return

        results = self.run_all_checks()
        total_issues = sum(len(issues) for issues in results.values())

        # Only send if there are issues (or force send daily summary)
        if total_issues == 0:
            logger.info("All systems healthy, no alert needed")
            return

        message = f"<b>🏥 HEALTH CHECK SUMMARY</b>\n\n"
        message += f"Timestamp: {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n"
        message += f"Issues Found: {total_issues}\n\n"

        for check_name, issues in results.items():
            if issues:
                message += f"<b>{check_name.title()}:</b>\n"
                for issue in issues[:3]:  # Limit to 3 per category
                    message += f"  {issue}\n"
                if len(issues) > 3:
                    message += f"  ... and {len(issues) - 3} more\n"
                message += "\n"

        message += "<b>Action:</b> Check logs and bot status"

        try:
            self.telegram.send_message(message)
        except Exception as e:
            logger.error(f"Failed to send health summary: {e}")


class AlchemyCollectorMonitor:
    """
    Monitors Alchemy on-chain data collector health.

    Alerts on:
    - Collector silence (checkpoint not updated in X minutes)
    - Trade collection rate drops
    - Database health issues
    - Collection gaps (missing blocks)
    """

    def __init__(self,
                 db_path: str = 'data/alchemy_trades.db',
                 telegram: Optional[TelegramNotifier] = None,
                 health_monitor: Optional['BotHealthMonitor'] = None):
        """
        Initialize Alchemy collector monitor.

        Args:
            db_path: Path to Alchemy trades database
            telegram: TelegramNotifier for alerts
            health_monitor: BotHealthMonitor instance (for alert deduplication)
        """
        self.db_path = Path(db_path)
        self.telegram = telegram
        self.health_monitor = health_monitor

        # Default thresholds
        self.checkpoint_age_threshold_minutes = 15  # Alert if no checkpoint in 15 min
        self.trade_age_threshold_minutes = 30  # Alert if no trades in 30 min
        self.min_trades_per_hour = 1  # Minimum expected trade rate

    def _send_alert(self, alert_key: str, message: str, severity: str = 'warning'):
        """Send alert using health monitor's deduplication if available."""
        if self.health_monitor:
            self.health_monitor._send_alert(alert_key, message, severity)
        elif self.telegram:
            emoji = {'critical': '🚨', 'warning': '⚠️', 'info': 'ℹ️', 'resolved': '✅'}.get(severity, '⚠️')
            try:
                self.telegram.send_message(f"{emoji} <b>ALCHEMY COLLECTOR ALERT</b>\n\n{message}")
            except Exception as e:
                logger.error(f"Failed to send Alchemy alert: {e}")

    def check_collector_liveness(self) -> List[str]:
        """
        Check if Alchemy collector is actively updating checkpoints.

        Returns:
            List of issues found
        """
        issues = []

        if not self.db_path.exists():
            issues.append("❌ Alchemy database not found!")
            self._send_alert(
                "alchemy_db_missing",
                f"<b>Alchemy Database Missing</b>\n\n"
                f"Path: {self.db_path}\n"
                f"Status: File not found\n\n"
                f"<b>Action Required:</b>\n"
                f"• Check if Alchemy collector is running\n"
                f"• Verify database path is correct\n"
                f"• Start collector if not running",
                severity='critical'
            )
            return issues

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check checkpoint age
            cursor.execute("""
                SELECT source, last_block, last_timestamp, updated_at
                FROM collection_checkpoints
                WHERE source = 'alchemy'
            """)
            result = cursor.fetchone()

            if not result:
                issues.append("⚠️  Alchemy: No checkpoint found (collector never ran?)")
                self._send_alert(
                    "alchemy_no_checkpoint",
                    f"<b>Alchemy Collector Not Initialized</b>\n\n"
                    f"Status: No checkpoint found in database\n\n"
                    f"<b>Possible Causes:</b>\n"
                    f"• Collector has never been run\n"
                    f"• Database was reset\n"
                    f"• Wrong database path\n\n"
                    f"<b>Action Required:</b> Start Alchemy collector",
                    severity='critical'
                )
            else:
                source, last_block, last_timestamp, updated_at = result
                checkpoint_time = datetime.fromisoformat(updated_at)
                age_minutes = (datetime.now(timezone.utc) - checkpoint_time).total_seconds() / 60

                if age_minutes > self.checkpoint_age_threshold_minutes:
                    issues.append(
                        f"⚠️  Alchemy: Checkpoint stale ({age_minutes:.1f} min old, "
                        f"last block: {last_block})"
                    )
                    self._send_alert(
                        "alchemy_checkpoint_stale",
                        f"<b>Alchemy Collector Stale</b>\n\n"
                        f"Last Update: {age_minutes:.1f} minutes ago\n"
                        f"Threshold: {self.checkpoint_age_threshold_minutes} minutes\n"
                        f"Last Block: {last_block:,}\n"
                        f"Last Timestamp: {last_timestamp}\n\n"
                        f"<b>Possible Causes:</b>\n"
                        f"• Collector crashed or stopped\n"
                        f"• API errors preventing data fetch\n"
                        f"• Network connectivity issues\n"
                        f"• Rate limiting\n\n"
                        f"<b>Action Required:</b> Check alchemy.out logs and restart if needed",
                        severity='warning'
                    )

            conn.close()

        except Exception as e:
            issues.append(f"❌ Alchemy database error: {e}")
            self._send_alert(
                "alchemy_db_error",
                f"<b>Alchemy Database Error</b>\n\n"
                f"Error: {e}\n\n"
                f"<b>Action Required:</b> Check database integrity",
                severity='critical'
            )

        return issues

    def check_trade_collection_rate(self) -> List[str]:
        """
        Check if trades are being collected at expected rate.

        Returns:
            List of issues found
        """
        issues = []

        if not self.db_path.exists():
            return []  # Already handled by liveness check

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get latest trade
            cursor.execute("""
                SELECT MAX(block_timestamp) as latest_trade,
                       COUNT(*) as total_trades
                FROM on_chain_trades
            """)
            result = cursor.fetchone()

            if not result or not result[0]:
                issues.append("⚠️  Alchemy: No trades collected yet")
            else:
                latest_trade_str, total_trades = result
                latest_trade = datetime.fromisoformat(latest_trade_str)
                age_minutes = (datetime.now(timezone.utc) - latest_trade).total_seconds() / 60

                if age_minutes > self.trade_age_threshold_minutes:
                    issues.append(
                        f"⚠️  Alchemy: No new trades in {age_minutes:.1f} minutes "
                        f"(total: {total_trades:,})"
                    )
                    self._send_alert(
                        "alchemy_no_trades",
                        f"<b>Alchemy No Recent Trades</b>\n\n"
                        f"Last Trade: {age_minutes:.1f} minutes ago\n"
                        f"Threshold: {self.trade_age_threshold_minutes} minutes\n"
                        f"Total Trades Collected: {total_trades:,}\n\n"
                        f"<b>Note:</b> This may be normal during low-volume periods.\n"
                        f"Check if collector is running and checkpoint is updating.",
                        severity='info'
                    )

            # Get recent collection rate (last hour)
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            cursor.execute("""
                SELECT COUNT(*) FROM on_chain_trades
                WHERE block_timestamp >= ?
            """, (one_hour_ago.isoformat(),))
            recent_trades = cursor.fetchone()[0]

            if recent_trades < self.min_trades_per_hour:
                issues.append(
                    f"📉 Alchemy: Low trade rate ({recent_trades} trades/hour, "
                    f"expected >={self.min_trades_per_hour})"
                )

            conn.close()

        except Exception as e:
            logger.error(f"Error checking Alchemy trade rate: {e}")

        return issues

    def check_database_health(self) -> List[str]:
        """
        Check Alchemy database health metrics.

        Returns:
            List of issues found
        """
        issues = []

        if not self.db_path.exists():
            return []  # Already handled by liveness check

        # Check database size
        db_size_mb = self.db_path.stat().st_size / (1024 * 1024)
        if db_size_mb > 500:
            issues.append(
                f"💾 Alchemy DB size: {db_size_mb:.1f} MB (consider archiving old data)"
            )

        # Check for corruption
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]

            if result != 'ok':
                issues.append(f"⚠️  Alchemy DB integrity check failed: {result}")
                self._send_alert(
                    "alchemy_db_corruption",
                    f"<b>Alchemy Database Corruption</b>\n\n"
                    f"Check Result: {result}\n\n"
                    f"<b>Action Required:</b> Database may be corrupted. "
                    f"Consider restoring from backup.",
                    severity='critical'
                )

            # Get stats
            cursor.execute("SELECT COUNT(*) FROM on_chain_trades")
            total_trades = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM token_condition_map")
            mapped_tokens = cursor.fetchone()[0]

            logger.info(
                f"Alchemy DB stats: {total_trades:,} trades, "
                f"{mapped_tokens:,} mapped tokens, {db_size_mb:.1f} MB"
            )

            conn.close()

        except Exception as e:
            issues.append(f"❌ Alchemy DB error: {e}")

        return issues

    def run_all_checks(self) -> Dict[str, List[str]]:
        """
        Run all Alchemy collector health checks.

        Returns:
            Dictionary of check results
        """
        return {
            'alchemy_liveness': self.check_collector_liveness(),
            'alchemy_trade_rate': self.check_trade_collection_rate(),
            'alchemy_database': self.check_database_health()
        }


def main():
    """Run bot health monitor (standalone or daemon mode)."""
    import argparse

    parser = argparse.ArgumentParser(description='Bot Health Monitoring Service')
    parser.add_argument('--once', action='store_true',
                       help='Run once and exit (for cron)')
    parser.add_argument('--daemon', action='store_true',
                       help='Run continuously in daemon mode')
    parser.add_argument('--interval', type=int, default=900,
                       help='Check interval in seconds (default: 900 = 15 min)')
    parser.add_argument('--db', type=str, default='data/market_snapshots.db',
                       help='Path to snapshots database')
    parser.add_argument('--config', type=str,
                       help='Path to monitoring config JSON file')
    parser.add_argument('--no-telegram', action='store_true',
                       help='Disable Telegram notifications')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/bot_health_monitor.log')
        ]
    )

    # Load config
    config = None
    if args.config and Path(args.config).exists():
        with open(args.config, 'r') as f:
            config = json.load(f)

    # Initialize Telegram
    telegram = None
    if not args.no_telegram:
        try:
            # Load from main config
            with open('config/config.json', 'r') as f:
                main_config = json.load(f)
                telegram_config = main_config.get('telegram', {})

                if telegram_config.get('enabled', False):
                    telegram = TelegramNotifier(
                        bot_token=telegram_config.get('bot_token', ''),
                        chat_id=telegram_config.get('chat_id', ''),
                        enabled=True
                    )
                    logger.info("Telegram notifications enabled")
        except Exception as e:
            logger.warning(f"Could not initialize Telegram: {e}")

    # Initialize monitor
    monitor = BotHealthMonitor(
        db_path=args.db,
        telegram=telegram,
        config=config
    )

    if args.once:
        # Run once and exit
        logger.info("Running health check (one-shot mode)...")
        report = monitor.generate_health_report()
        print(report)
        sys.exit(0)

    elif args.daemon:
        # Run continuously
        logger.info(f"Starting health monitor daemon (interval: {args.interval}s)...")

        if telegram:
            telegram.send_message(
                f"🏥 <b>Health Monitor Started</b>\n\n"
                f"Check Interval: {args.interval // 60} minutes\n"
                f"Database: {args.db}\n"
                f"Monitoring:\n"
                f"  • Trading bots (event, price_level, short_expiry)\n"
                f"  • Alchemy on-chain collector"
            )

        try:
            while True:
                logger.info("Running health checks...")
                report = monitor.generate_health_report()
                print(report)

                logger.info(f"Sleeping for {args.interval} seconds...")
                time.sleep(args.interval)

        except KeyboardInterrupt:
            logger.info("Health monitor stopped by user")
            if telegram:
                telegram.send_message("🛑 <b>Health Monitor Stopped</b>")

    else:
        # Default: run once and show report
        report = monitor.generate_health_report()
        print(report)


if __name__ == '__main__':
    main()
