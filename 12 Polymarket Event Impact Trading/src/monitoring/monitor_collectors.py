#!/usr/bin/env python3
"""
Collector Health Monitor with Telegram Alerts
Monitors GDELT and Alchemy collectors and sends alerts when issues detected.

Setup:
1. Create Telegram bot: Talk to @BotFather on Telegram
2. Get your chat_id: Talk to @userinfobot on Telegram
3. Create telegram_config.json with your credentials
4. Run: python3 monitor_collectors.py --test (to test alerts)
5. Add to cron: */5 * * * * cd /path/to/project && python3 monitor_collectors.py

Alert conditions:
- Process not running
- Process using >80% CPU (stuck/infinite loop)
- Logs not updated in expected time
- Database not growing (stale data)
- Error rate too high
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    def __init__(self, config_path: str = "telegram_config.json"):
        """Initialize with config file containing bot_token and chat_id."""
        self.config_path = config_path
        self.bot_token = None
        self.chat_id = None
        self.enabled = False

        self._load_config()

    def _load_config(self):
        """Load Telegram credentials from config file."""
        if not Path(self.config_path).exists():
            print(f"⚠️  Telegram config not found: {self.config_path}")
            print("   Create it with: {'bot_token': 'YOUR_TOKEN', 'chat_id': 'YOUR_CHAT_ID'}")
            return

        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)

            self.bot_token = config.get('bot_token')
            self.chat_id = config.get('chat_id')

            if self.bot_token and self.chat_id:
                self.enabled = True
                print(f"✓ Telegram notifications enabled (chat_id: {self.chat_id})")
            else:
                print("⚠️  Telegram config incomplete (missing bot_token or chat_id)")
        except Exception as e:
            print(f"⚠️  Error loading Telegram config: {e}")

    def send_message(self, message: str, silent: bool = False) -> bool:
        """
        Send a message via Telegram.

        Args:
            message: Message text (supports Markdown)
            silent: If True, sends notification without sound

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            print(f"ℹ️  Telegram not enabled. Would send: {message}")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            'chat_id': self.chat_id,
            'text': message,
            'parse_mode': 'Markdown',
            'disable_notification': silent
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"✓ Telegram alert sent")
            return True
        except Exception as e:
            print(f"✗ Failed to send Telegram alert: {e}")
            return False


class CollectorMonitor:
    """Monitor collector processes and database health."""

    # Expected update intervals (in seconds)
    GDELT_INTERVAL = 1 * 60  # 1 minute
    ALCHEMY_INTERVAL = 2 * 60  # 2 minutes

    # Alert thresholds
    CPU_THRESHOLD = 80.0  # Alert if CPU > 80%
    ERROR_RATE_THRESHOLD = 0.3  # Alert if >30% of recent log lines are errors

    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self.state_file = Path("data/monitor_state.json")
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load previous monitoring state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass

        return {
            'last_alert_time': {},
            'last_check_time': None,
            'last_trade_count': 0,
            'last_event_count': 0,
            'consecutive_failures': {}
        }

    def _save_state(self):
        """Save monitoring state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def _should_alert(self, alert_key: str, cooldown_minutes: int = 30) -> bool:
        """Check if enough time has passed since last alert to avoid spam."""
        last_alert = self.state['last_alert_time'].get(alert_key)

        if last_alert is None:
            return True

        last_time = datetime.fromisoformat(last_alert)
        cooldown = timedelta(minutes=cooldown_minutes)

        return datetime.now() - last_time > cooldown

    def _mark_alerted(self, alert_key: str):
        """Record that an alert was sent."""
        self.state['last_alert_time'][alert_key] = datetime.now().isoformat()
        self._save_state()

    def check_process_running(self, process_name: str) -> Tuple[bool, Optional[int], Optional[float]]:
        """
        Check if a process is running.

        Returns:
            (is_running, pid, cpu_percent)
        """
        try:
            result = subprocess.run(
                ['pgrep', '-f', process_name],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                pid = int(result.stdout.strip().split()[0])

                # Get CPU usage
                ps_result = subprocess.run(
                    ['ps', '-p', str(pid), '-o', '%cpu='],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                cpu = float(ps_result.stdout.strip()) if ps_result.returncode == 0 else 0.0

                return True, pid, cpu

            return False, None, None
        except Exception as e:
            print(f"Error checking process {process_name}: {e}")
            return False, None, None

    def check_log_updated(self, log_file: str, max_age_seconds: int) -> Tuple[bool, Optional[int]]:
        """
        Check if log file was updated recently.

        Returns:
            (is_updated, seconds_since_update)
        """
        try:
            log_path = Path(log_file)
            if not log_path.exists():
                return False, None

            mtime = log_path.stat().st_mtime
            age = time.time() - mtime

            return age < max_age_seconds, int(age)
        except Exception as e:
            print(f"Error checking log {log_file}: {e}")
            return False, None

    def check_log_errors(self, log_file: str, tail_lines: int = 50) -> Tuple[int, int]:
        """
        Check recent log for errors.

        Returns:
            (error_count, total_lines)
        """
        try:
            result = subprocess.run(
                ['tail', '-n', str(tail_lines), log_file],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return 0, 0

            lines = result.stdout.strip().split('\n')
            total = len(lines)
            errors = sum(1 for line in lines if ' - ERROR - ' in line or ' - CRITICAL - ' in line)

            return errors, total
        except Exception as e:
            print(f"Error checking log errors in {log_file}: {e}")
            return 0, 0

    def check_database_growth(self, db_path: str, table: str) -> Tuple[bool, int, int]:
        """
        Check if database is growing.

        Returns:
            (is_growing, current_count, growth)
        """
        try:
            conn = sqlite3.connect(db_path, timeout=10)
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            current_count = cursor.fetchone()[0]
            conn.close()

            # Compare with previous check
            if table == 'on_chain_trades':
                last_count = self.state.get('last_trade_count', 0)
                self.state['last_trade_count'] = current_count
            else:  # news_events
                last_count = self.state.get('last_event_count', 0)
                self.state['last_event_count'] = current_count

            self._save_state()

            growth = current_count - last_count
            is_growing = growth >= 0  # Allow zero growth (no new data is ok sometimes)

            return is_growing, current_count, growth
        except Exception as e:
            print(f"Error checking database {db_path}: {e}")
            return True, 0, 0  # Don't alert on DB check errors

    def check_gdelt_collector(self) -> List[str]:
        """Check GDELT collector health. Returns list of issues."""
        issues = []

        # Check process
        is_running, pid, cpu = self.check_process_running('gdelt_collector.py')

        if not is_running:
            issues.append("❌ GDELT collector process not running")
            self._increment_failure('gdelt_process')
        else:
            self._reset_failure('gdelt_process')

            # Check CPU
            if cpu and cpu > self.CPU_THRESHOLD:
                issues.append(f"⚠️ GDELT collector high CPU: {cpu:.1f}% (PID: {pid})")

        # Check log updated
        is_updated, age = self.check_log_updated('gdelt_collection.out', self.GDELT_INTERVAL * 2)

        if not is_updated:
            age_min = age // 60 if age else 0
            issues.append(f"⚠️ GDELT log not updated in {age_min} minutes (expected: 1 min)")
            self._increment_failure('gdelt_log')
        else:
            self._reset_failure('gdelt_log')

        # Check for errors
        error_count, total_lines = self.check_log_errors('gdelt_collection.out', tail_lines=50)
        if total_lines > 0:
            error_rate = error_count / total_lines
            if error_rate > self.ERROR_RATE_THRESHOLD:
                issues.append(f"⚠️ GDELT high error rate: {error_count}/{total_lines} ({error_rate*100:.0f}%)")

        # Check database growth
        if Path('data/gdelt_news.db').exists():
            is_growing, count, growth = self.check_database_growth('data/gdelt_news.db', 'news_events')
            if count > 0 and growth < 0:
                issues.append(f"⚠️ GDELT database shrinking: {count} events (lost {-growth})")

        return issues

    def check_alchemy_collector(self) -> List[str]:
        """Check Alchemy collector health. Returns list of issues."""
        issues = []

        # Check process
        is_running, pid, cpu = self.check_process_running('alchemy_collector.py')

        if not is_running:
            issues.append("❌ Alchemy collector process not running")
            self._increment_failure('alchemy_process')
        else:
            self._reset_failure('alchemy_process')

            # Check CPU (Alchemy can use more CPU during collection)
            if cpu and cpu > 95.0:
                issues.append(f"⚠️ Alchemy collector very high CPU: {cpu:.1f}% (PID: {pid})")

        # Check log updated (allow 2x interval since it runs every 2 min)
        is_updated, age = self.check_log_updated('alchemy_collection.out', self.ALCHEMY_INTERVAL * 2)

        if not is_updated:
            age_min = age // 60 if age else 0
            issues.append(f"⚠️ Alchemy log not updated in {age_min} minutes (expected: 2 min)")
            self._increment_failure('alchemy_log')
        else:
            self._reset_failure('alchemy_log')

        # Check for errors
        error_count, total_lines = self.check_log_errors('alchemy_collection.out', tail_lines=50)
        if total_lines > 0:
            error_rate = error_count / total_lines
            if error_rate > self.ERROR_RATE_THRESHOLD:
                issues.append(f"⚠️ Alchemy high error rate: {error_count}/{total_lines} ({error_rate*100:.0f}%)")

        # Check database growth
        if Path('data/alchemy_trades.db').exists():
            is_growing, count, growth = self.check_database_growth('data/alchemy_trades.db', 'on_chain_trades')
            if count > 0 and growth < 0:
                issues.append(f"⚠️ Alchemy database shrinking: {count} trades (lost {-growth})")

        return issues

    def _increment_failure(self, key: str):
        """Increment consecutive failure counter."""
        if key not in self.state['consecutive_failures']:
            self.state['consecutive_failures'][key] = 0
        self.state['consecutive_failures'][key] += 1
        self._save_state()

    def _reset_failure(self, key: str):
        """Reset consecutive failure counter."""
        if key in self.state['consecutive_failures']:
            self.state['consecutive_failures'][key] = 0
            self._save_state()

    def _get_failure_count(self, key: str) -> int:
        """Get consecutive failure count."""
        return self.state['consecutive_failures'].get(key, 0)

    def monitor_all(self) -> Tuple[List[str], List[str]]:
        """
        Monitor all collectors.

        Returns:
            (gdelt_issues, alchemy_issues)
        """
        print(f"=== Collector Health Check ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")

        gdelt_issues = self.check_gdelt_collector()
        alchemy_issues = self.check_alchemy_collector()

        # Print status
        if not gdelt_issues:
            print("✓ GDELT collector: OK")
        else:
            print("✗ GDELT collector issues:")
            for issue in gdelt_issues:
                print(f"  {issue}")

        if not alchemy_issues:
            print("✓ Alchemy collector: OK")
        else:
            print("✗ Alchemy collector issues:")
            for issue in alchemy_issues:
                print(f"  {issue}")

        return gdelt_issues, alchemy_issues

    def send_alerts(self, gdelt_issues: List[str], alchemy_issues: List[str]):
        """Send Telegram alerts for issues (with cooldown to avoid spam)."""

        # GDELT alerts
        for issue in gdelt_issues:
            alert_key = f"gdelt_{issue[:20]}"

            # Only alert after 2 consecutive failures (avoid transient issues)
            if "not running" in issue:
                failure_count = self._get_failure_count('gdelt_process')
                if failure_count >= 2 and self._should_alert(alert_key, cooldown_minutes=30):
                    self.notifier.send_message(
                        f"🚨 *GDELT Collector Alert*\n\n{issue}\n\n"
                        f"Consecutive failures: {failure_count}\n"
                        f"Action: Restart with `./restart_all.sh`"
                    )
                    self._mark_alerted(alert_key)

            elif "not updated" in issue:
                failure_count = self._get_failure_count('gdelt_log')
                if failure_count >= 2 and self._should_alert(alert_key, cooldown_minutes=60):
                    self.notifier.send_message(
                        f"⚠️ *GDELT Collector Warning*\n\n{issue}\n\n"
                        f"May be stuck or crashed. Check logs:\n`tail -50 gdelt_collection.out`"
                    )
                    self._mark_alerted(alert_key)

        # Alchemy alerts
        for issue in alchemy_issues:
            alert_key = f"alchemy_{issue[:20]}"

            if "not running" in issue:
                failure_count = self._get_failure_count('alchemy_process')
                if failure_count >= 2 and self._should_alert(alert_key, cooldown_minutes=30):
                    self.notifier.send_message(
                        f"🚨 *Alchemy Collector Alert*\n\n{issue}\n\n"
                        f"Consecutive failures: {failure_count}\n"
                        f"Action: Restart with `./restart_all.sh`"
                    )
                    self._mark_alerted(alert_key)

            elif "not updated" in issue:
                failure_count = self._get_failure_count('alchemy_log')
                if failure_count >= 2 and self._should_alert(alert_key, cooldown_minutes=120):
                    self.notifier.send_message(
                        f"⚠️ *Alchemy Collector Warning*\n\n{issue}\n\n"
                        f"May be stuck. Check logs:\n`tail -50 alchemy_collection.out`"
                    )
                    self._mark_alerted(alert_key)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Monitor Polymarket collectors with Telegram alerts")
    parser.add_argument('--test', action='store_true', help="Send test alert")
    parser.add_argument('--config', default='telegram_config.json', help="Telegram config file")
    args = parser.parse_args()

    # Initialize
    notifier = TelegramNotifier(config_path=args.config)

    if args.test:
        print("Sending test alert...")
        success = notifier.send_message(
            "✅ *Collector Monitor Test*\n\n"
            "Monitoring is set up correctly!\n\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        sys.exit(0 if success else 1)

    # Run monitoring
    monitor = CollectorMonitor(notifier)
    gdelt_issues, alchemy_issues = monitor.monitor_all()

    # Send alerts if issues found
    if gdelt_issues or alchemy_issues:
        monitor.send_alerts(gdelt_issues, alchemy_issues)
        print("\n⚠️  Issues detected - alerts sent")
        sys.exit(1)
    else:
        print("\n✓ All collectors healthy")
        sys.exit(0)


if __name__ == "__main__":
    main()
