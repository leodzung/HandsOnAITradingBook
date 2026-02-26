#!/usr/bin/env python3
"""
Telemetry Dashboard - View current metrics and threshold status

Displays:
- Current metric values
- Constraint thresholds
- Alert status (OK, WARNING, CRITICAL)
- Collection statistics

Usage:
    python3 scripts/telemetry_dashboard.py
    python3 scripts/telemetry_dashboard.py --watch  # Auto-refresh every 30s
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# ANSI color codes
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


# Constraint thresholds from CONSTRAINTS.yml
THRESHOLDS = {
    'positions_without_sl_tp_event_trader': {
        'threshold': 0,
        'operator': '<=',
        'severity': 'CRITICAL',
        'constraint': 'RISK-001'
    },
    'positions_without_sl_tp_price_level_trader': {
        'threshold': 0,
        'operator': '<=',
        'severity': 'CRITICAL',
        'constraint': 'RISK-001'
    },
    'positions_without_sl_tp_short_expiry_trader': {
        'threshold': 0,
        'operator': '<=',
        'severity': 'CRITICAL',
        'constraint': 'RISK-001'
    },
    'circuit_breaker_trips': {
        'threshold': None,  # Alert on any change
        'operator': 'alert_on_change',
        'severity': 'WARNING',
        'constraint': 'RISK-002'
    },
    'websocket_fallback_rate': {
        'threshold': 0.2,
        'operator': '<=',
        'severity': 'WARNING',
        'constraint': 'ARCH-004'
    },
    'slippage_rejection_rate': {
        'threshold': 0.3,
        'operator': '<=',
        'severity': 'WARNING',
        'constraint': 'RISK-003'
    },
}


def get_latest_metrics(db_path: Path) -> Dict[str, Tuple[float, str]]:
    """Get latest value for each metric."""
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute('''
        SELECT m1.metric_name, m1.metric_value, m1.timestamp
        FROM metrics m1
        INNER JOIN (
            SELECT metric_name, MAX(timestamp) as max_ts
            FROM metrics
            GROUP BY metric_name
        ) m2 ON m1.metric_name = m2.metric_name AND m1.timestamp = m2.max_ts
        ORDER BY m1.metric_name
    ''')

    metrics = {}
    for row in cursor.fetchall():
        name, value, timestamp = row
        metrics[name] = (value, timestamp)

    conn.close()
    return metrics


def check_threshold(metric_name: str, value: float) -> Tuple[str, str]:
    """
    Check if metric violates threshold.

    Returns: (status, message)
        status: 'OK', 'WARNING', 'CRITICAL'
    """
    if metric_name not in THRESHOLDS:
        return 'OK', ''

    threshold_config = THRESHOLDS[metric_name]
    threshold = threshold_config['threshold']
    operator = threshold_config['operator']
    severity = threshold_config['severity']

    if operator == '<=':
        if value <= threshold:
            return 'OK', ''
        else:
            return severity, f'Value {value} > threshold {threshold}'
    elif operator == '>=':
        if value >= threshold:
            return 'OK', ''
        else:
            return severity, f'Value {value} < threshold {threshold}'
    elif operator == 'alert_on_change':
        # Would need to track previous value
        return 'OK', ''

    return 'OK', ''


def get_collection_stats(db_path: Path) -> Dict:
    """Get collection statistics."""
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Total records
    cursor.execute('SELECT COUNT(*) FROM metrics')
    total_records = cursor.fetchone()[0]

    # Unique metrics
    cursor.execute('SELECT COUNT(DISTINCT metric_name) FROM metrics')
    unique_metrics = cursor.fetchone()[0]

    # First and last collection
    cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM metrics')
    first_ts, last_ts = cursor.fetchone()

    # Recent collections (last hour)
    cursor.execute('''
        SELECT COUNT(*) FROM metrics
        WHERE datetime(timestamp) > datetime('now', '-1 hour')
    ''')
    recent_count = cursor.fetchone()[0]

    conn.close()

    return {
        'total_records': total_records,
        'unique_metrics': unique_metrics,
        'first_collection': first_ts,
        'last_collection': last_ts,
        'recent_count': recent_count,
    }


def display_dashboard(db_path: Path):
    """Display telemetry dashboard."""
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}📊 Polymarket Trading System - Telemetry Dashboard{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print()

    # Collection stats
    stats = get_collection_stats(db_path)
    if stats:
        print(f"{Colors.BOLD}📈 Collection Statistics:{Colors.END}")
        print(f"   Total Records:        {stats['total_records']:,}")
        print(f"   Unique Metrics:       {stats['unique_metrics']}")
        print(f"   First Collection:     {stats['first_collection']}")
        print(f"   Last Collection:      {stats['last_collection']}")
        print(f"   Records (last hour):  {stats['recent_count']}")
        print()

    # Current metrics
    metrics = get_latest_metrics(db_path)
    if not metrics:
        print(f"{Colors.RED}❌ No metrics found{Colors.END}")
        return

    print(f"{Colors.BOLD}🎯 Current Metrics & Threshold Status:{Colors.END}")
    print()

    # Group by constraint
    constraint_groups = {}
    for metric_name, (value, timestamp) in metrics.items():
        if metric_name in THRESHOLDS:
            constraint_id = THRESHOLDS[metric_name]['constraint']
        else:
            constraint_id = 'Other'

        if constraint_id not in constraint_groups:
            constraint_groups[constraint_id] = []

        constraint_groups[constraint_id].append((metric_name, value, timestamp))

    # Display by constraint
    for constraint_id in sorted(constraint_groups.keys()):
        print(f"{Colors.BOLD}[{constraint_id}]{Colors.END}")

        for metric_name, value, timestamp in constraint_groups[constraint_id]:
            status, message = check_threshold(metric_name, value)

            # Status indicator
            if status == 'OK':
                status_icon = f"{Colors.GREEN}✅{Colors.END}"
            elif status == 'WARNING':
                status_icon = f"{Colors.YELLOW}⚠️ {Colors.END}"
            else:  # CRITICAL
                status_icon = f"{Colors.RED}❌{Colors.END}"

            # Metric display
            print(f"  {status_icon} {metric_name:50s} = {value:8.1f}")

            # Show threshold info if configured
            if metric_name in THRESHOLDS:
                threshold_config = THRESHOLDS[metric_name]
                threshold = threshold_config['threshold']
                operator = threshold_config['operator']

                if threshold is not None:
                    print(f"       Threshold: {operator} {threshold}", end='')
                    if message:
                        print(f" - {Colors.RED}{message}{Colors.END}")
                    else:
                        print()

        print()

    print(f"{Colors.CYAN}Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Telemetry Dashboard - View metrics and threshold status'
    )
    parser.add_argument(
        '--watch',
        action='store_true',
        help='Auto-refresh every 30 seconds'
    )
    parser.add_argument(
        '--db',
        type=Path,
        default=Path('data/telemetry.db'),
        help='Path to telemetry database (default: data/telemetry.db)'
    )

    args = parser.parse_args()

    # Resolve relative path
    if not args.db.is_absolute():
        project_root = Path(__file__).parent.parent
        args.db = project_root / args.db

    if not args.db.exists():
        print(f"{Colors.RED}❌ Telemetry database not found: {args.db}{Colors.END}")
        print(f"\nRun collection first:")
        print(f"  python3 scripts/collect_telemetry.py")
        sys.exit(1)

    try:
        if args.watch:
            while True:
                # Clear screen
                print('\033[2J\033[H')

                display_dashboard(args.db)

                print(f"{Colors.CYAN}Refreshing in 30 seconds... (Ctrl+C to stop){Colors.END}")
                time.sleep(30)
        else:
            display_dashboard(args.db)

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Dashboard stopped{Colors.END}")
        sys.exit(0)


if __name__ == '__main__':
    main()
