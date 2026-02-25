#!/usr/bin/env python3
"""
Telemetry System for Constraint Validation

Collects and stores runtime metrics that can be validated against constraints.
Integrates with BotHealthMonitor, PositionManager, and trading bots to provide
a unified view of system health.

Features:
- Collects metrics from multiple sources
- Stores metrics in SQLite with timestamps
- Provides query interface for constraint validation
- Supports metric thresholds and alerting
- Historical metric tracking

Usage:
    from monitoring.telemetry import TradeTelemetry

    telemetry = TradeTelemetry()

    # Record metric
    telemetry.record_metric('positions_without_sl_tp', 0)

    # Query latest metrics
    metrics = telemetry.get_latest_metrics()

    # Query historical metrics
    history = telemetry.get_metric_history('circuit_breaker_trips', hours=24)

Created: 2026-02-24 (Phase 3: Telemetry Integration)
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class TradeTelemetry:
    """
    Centralized telemetry system for collecting and querying runtime metrics.

    Metrics are stored with timestamps and can be queried by constraint
    validation system to verify runtime behavior against defined thresholds.
    """

    def __init__(self, db_path: str = 'data/telemetry.db'):
        """
        Initialize telemetry system.

        Args:
            db_path: Path to SQLite database for metrics storage
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()
        logger.info(f"✓ Telemetry system initialized (DB: {db_path})")

    def _create_tables(self):
        """Create telemetry database tables."""
        conn = sqlite3.connect(self.db_path)

        # Metrics table: stores individual metric values over time
        conn.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metadata TEXT,
                source TEXT,
                UNIQUE(timestamp, metric_name)
            )
        ''')

        # Create index for fast queries
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_metrics_name_time
            ON metrics(metric_name, timestamp DESC)
        ''')

        # Events table: stores discrete events (e.g., circuit breaker trips)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                severity TEXT,
                source TEXT
            )
        ''')

        # Create index for event queries
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_events_type_time
            ON events(event_type, timestamp DESC)
        ''')

        conn.commit()
        conn.close()

    def record_metric(self,
                      metric_name: str,
                      value: float,
                      metadata: Optional[Dict] = None,
                      source: Optional[str] = None):
        """
        Record a metric value.

        Args:
            metric_name: Name of the metric (e.g., 'positions_without_sl_tp')
            value: Numeric value of the metric
            metadata: Optional metadata dict
            source: Optional source identifier (e.g., 'trader_price_levels')
        """
        conn = sqlite3.connect(self.db_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(metadata) if metadata else None

        try:
            conn.execute('''
                INSERT OR REPLACE INTO metrics
                (timestamp, metric_name, metric_value, metadata, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, metric_name, value, metadata_json, source))
            conn.commit()
            logger.debug(f"Recorded metric: {metric_name}={value}")
        except Exception as e:
            logger.error(f"Failed to record metric {metric_name}: {e}")
        finally:
            conn.close()

    def record_event(self,
                     event_type: str,
                     event_data: Optional[Dict] = None,
                     severity: str = 'info',
                     source: Optional[str] = None):
        """
        Record a discrete event.

        Args:
            event_type: Type of event (e.g., 'circuit_breaker_trip')
            event_data: Optional event data dict
            severity: Event severity (info/warning/critical)
            source: Optional source identifier
        """
        conn = sqlite3.connect(self.db_path)
        timestamp = datetime.now(timezone.utc).isoformat()
        event_json = json.dumps(event_data) if event_data else None

        try:
            conn.execute('''
                INSERT INTO events
                (timestamp, event_type, event_data, severity, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (timestamp, event_type, event_json, severity, source))
            conn.commit()
            logger.debug(f"Recorded event: {event_type} ({severity})")
        except Exception as e:
            logger.error(f"Failed to record event {event_type}: {e}")
        finally:
            conn.close()

    def get_latest_metrics(self, metric_names: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Get latest value for each metric.

        Args:
            metric_names: Optional list of specific metrics to fetch.
                         If None, fetches all metrics.

        Returns:
            Dict mapping metric_name to latest value
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if metric_names:
            # Fetch specific metrics
            placeholders = ','.join('?' * len(metric_names))
            query = f'''
                SELECT metric_name, metric_value
                FROM (
                    SELECT metric_name, metric_value,
                           ROW_NUMBER() OVER (PARTITION BY metric_name ORDER BY timestamp DESC) as rn
                    FROM metrics
                    WHERE metric_name IN ({placeholders})
                )
                WHERE rn = 1
            '''
            cursor.execute(query, metric_names)
        else:
            # Fetch all metrics
            query = '''
                SELECT metric_name, metric_value
                FROM (
                    SELECT metric_name, metric_value,
                           ROW_NUMBER() OVER (PARTITION BY metric_name ORDER BY timestamp DESC) as rn
                    FROM metrics
                )
                WHERE rn = 1
            '''
            cursor.execute(query)

        results = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        return results

    def get_metric_history(self,
                           metric_name: str,
                           hours: int = 24,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get historical values for a metric.

        Args:
            metric_name: Name of metric to query
            hours: Hours of history to fetch
            limit: Optional max number of records

        Returns:
            List of dicts with keys: timestamp, value, metadata
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        query = '''
            SELECT timestamp, metric_value, metadata
            FROM metrics
            WHERE metric_name = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        '''

        if limit:
            query += f' LIMIT {limit}'

        cursor.execute(query, (metric_name, cutoff_str))

        results = [
            {
                'timestamp': row[0],
                'value': row[1],
                'metadata': json.loads(row[2]) if row[2] else None
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def get_event_count(self,
                        event_type: str,
                        hours: Optional[int] = None,
                        severity: Optional[str] = None) -> int:
        """
        Count events of a specific type.

        Args:
            event_type: Type of event to count
            hours: Optional hours to look back (None = all time)
            severity: Optional severity filter

        Returns:
            Count of matching events
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = 'SELECT COUNT(*) FROM events WHERE event_type = ?'
        params = [event_type]

        if hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            query += ' AND timestamp >= ?'
            params.append(cutoff.isoformat())

        if severity:
            query += ' AND severity = ?'
            params.append(severity)

        cursor.execute(query, params)
        count = cursor.fetchone()[0]
        conn.close()

        return count

    def get_recent_events(self,
                          hours: int = 24,
                          event_type: Optional[str] = None,
                          severity: Optional[str] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent events.

        Args:
            hours: Hours to look back
            event_type: Optional event type filter
            severity: Optional severity filter
            limit: Max number of events to return

        Returns:
            List of event dicts
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        query = 'SELECT timestamp, event_type, event_data, severity, source FROM events WHERE timestamp >= ?'
        params = [cutoff_str]

        if event_type:
            query += ' AND event_type = ?'
            params.append(event_type)

        if severity:
            query += ' AND severity = ?'
            params.append(severity)

        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)

        results = [
            {
                'timestamp': row[0],
                'event_type': row[1],
                'event_data': json.loads(row[2]) if row[2] else None,
                'severity': row[3],
                'source': row[4]
            }
            for row in cursor.fetchall()
        ]

        conn.close()
        return results

    def check_metric_threshold(self,
                                metric_name: str,
                                threshold: float,
                                operator: str = 'lte') -> bool:
        """
        Check if latest metric value satisfies threshold.

        Args:
            metric_name: Name of metric to check
            threshold: Threshold value
            operator: Comparison operator ('lt', 'lte', 'gt', 'gte', 'eq')

        Returns:
            True if threshold satisfied, False otherwise
        """
        metrics = self.get_latest_metrics([metric_name])

        if metric_name not in metrics:
            logger.warning(f"Metric {metric_name} not found in telemetry")
            return False

        value = metrics[metric_name]

        operators = {
            'lt': lambda v, t: v < t,
            'lte': lambda v, t: v <= t,
            'gt': lambda v, t: v > t,
            'gte': lambda v, t: v >= t,
            'eq': lambda v, t: v == t
        }

        if operator not in operators:
            raise ValueError(f"Unknown operator: {operator}")

        result = operators[operator](value, threshold)

        logger.debug(f"Threshold check: {metric_name}={value} {operator} {threshold} = {result}")

        return result

    def collect_system_metrics(self):
        """
        Collect metrics from various system components.

        This method queries PositionManager, BotHealthMonitor, and other
        components to gather current metrics.
        """
        try:
            # Collect position-related metrics
            self._collect_position_metrics()

            # Collect bot health metrics
            self._collect_bot_health_metrics()

            # Collect trading metrics
            self._collect_trading_metrics()

            logger.debug("System metrics collected successfully")

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")

    def _collect_position_metrics(self):
        """Collect metrics from PositionManager."""
        try:
            from core.position_manager_v2 import PositionManager

            # Check each bot's position database
            for db_name, source in [
                ('data/positions.db', 'event_trader'),
                ('data/positions_price_level.db', 'price_level_trader'),
                ('data/positions_short_expiry.db', 'short_expiry_trader')
            ]:
                if not Path(db_name).exists():
                    continue

                pm = PositionManager(db_path=db_name)
                positions = pm.get_open_positions()

                # Count positions without SL/TP
                without_sl_tp = sum(
                    1 for p in positions
                    if p.get('stop_loss_pct') is None or p.get('take_profit_pct') is None
                )

                self.record_metric(
                    f'positions_without_sl_tp_{source}',
                    without_sl_tp,
                    metadata={'total_positions': len(positions)},
                    source=source
                )

                # Record total open positions
                self.record_metric(
                    f'open_positions_{source}',
                    len(positions),
                    source=source
                )

        except Exception as e:
            logger.error(f"Error collecting position metrics: {e}")

    def _collect_bot_health_metrics(self):
        """Collect metrics from BotHealthMonitor."""
        try:
            from monitoring.bot_health_monitor import BotHealthMonitor

            monitor = BotHealthMonitor()

            # Check for silent bots
            silent_bots = monitor.check_bot_liveness()

            self.record_metric(
                'bots_silent',
                len(silent_bots.get('silent_bots', [])),
                metadata=silent_bots,
                source='bot_health_monitor'
            )

        except Exception as e:
            logger.error(f"Error collecting bot health metrics: {e}")

    def _collect_trading_metrics(self):
        """Collect trading-specific metrics."""
        try:
            # This would collect metrics from trading bot logs/state
            # For now, we'll just record placeholder metrics

            # Example: circuit breaker status
            # Would be set by trading bots when circuit breaker trips
            pass

        except Exception as e:
            logger.error(f"Error collecting trading metrics: {e}")


# Singleton instance for global access
_telemetry_instance = None


def get_telemetry() -> TradeTelemetry:
    """Get singleton telemetry instance."""
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = TradeTelemetry()
    return _telemetry_instance


if __name__ == '__main__':
    # Example usage
    logging.basicConfig(level=logging.INFO)

    telemetry = TradeTelemetry()

    # Record some example metrics
    telemetry.record_metric('positions_without_sl_tp', 0)
    telemetry.record_metric('circuit_breaker_trips', 0)
    telemetry.record_metric('websocket_fallback_rate', 0.05)
    telemetry.record_metric('slippage_rejection_rate', 0.15)

    # Record an event
    telemetry.record_event(
        'circuit_breaker_trip',
        event_data={'reason': 'Three consecutive losses', 'bot': 'price_level'},
        severity='warning'
    )

    # Query metrics
    latest = telemetry.get_latest_metrics()
    print("Latest metrics:", latest)

    # Check threshold
    result = telemetry.check_metric_threshold('websocket_fallback_rate', 0.20, 'lte')
    print(f"WebSocket fallback rate OK: {result}")

    # Get event count
    trips = telemetry.get_event_count('circuit_breaker_trip', hours=24)
    print(f"Circuit breaker trips (24h): {trips}")
