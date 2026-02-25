#!/usr/bin/env python3
"""
Pattern Detection System for Self-Improving Constraints

Analyzes telemetry data to detect recurring patterns, anomalies, and issues
that could benefit from new constraints or auto-remediation.

Features:
- Failure pattern detection
- Anomaly detection using statistical methods
- Correlation analysis between metrics
- Constraint suggestion generation
- Auto-remediation opportunity identification

Usage:
    from monitoring.pattern_detector import PatternDetector

    detector = PatternDetector()
    patterns = detector.detect_failure_patterns(hours=168)  # Last week
    suggestions = detector.generate_constraint_suggestions(patterns)

Created: 2026-02-24 (Phase 4: Self-Improvement)
"""

import logging
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from collections import defaultdict, Counter
import statistics
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitoring.telemetry import TradeTelemetry

logger = logging.getLogger(__name__)


class Pattern:
    """Represents a detected pattern in telemetry data."""

    def __init__(self,
                 pattern_type: str,
                 description: str,
                 frequency: int,
                 severity: str,
                 evidence: Dict[str, Any],
                 suggested_action: Optional[str] = None):
        self.pattern_type = pattern_type
        self.description = description
        self.frequency = frequency
        self.severity = severity
        self.evidence = evidence
        self.suggested_action = suggested_action
        self.detected_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'pattern_type': self.pattern_type,
            'description': self.description,
            'frequency': self.frequency,
            'severity': self.severity,
            'evidence': self.evidence,
            'suggested_action': self.suggested_action,
            'detected_at': self.detected_at.isoformat()
        }


class ConstraintSuggestion:
    """Represents a suggested new constraint based on detected patterns."""

    def __init__(self,
                 constraint_id: str,
                 title: str,
                 description: str,
                 category: str,
                 priority: str,
                 validation: List[Dict],
                 telemetry: List[Dict],
                 rationale: str,
                 patterns: List[Pattern]):
        self.constraint_id = constraint_id
        self.title = title
        self.description = description
        self.category = category
        self.priority = priority
        self.validation = validation
        self.telemetry = telemetry
        self.rationale = rationale
        self.patterns = patterns
        self.suggested_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary suitable for CONSTRAINTS.yml."""
        return {
            'id': self.constraint_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'priority': self.priority,
            'status': 'suggested',
            'suggested_date': self.suggested_at.isoformat(),
            'validation': self.validation,
            'telemetry': self.telemetry,
            'rationale': self.rationale,
            'based_on_patterns': [p.to_dict() for p in self.patterns]
        }


class PatternDetector:
    """
    Detects patterns in telemetry data and generates actionable insights.

    This is the core of the self-improving system - it analyzes what's
    actually happening in production and suggests ways to improve constraints.
    """

    def __init__(self, telemetry: Optional[TradeTelemetry] = None):
        """
        Initialize pattern detector.

        Args:
            telemetry: TradeTelemetry instance (creates new if None)
        """
        self.telemetry = telemetry or TradeTelemetry()
        logger.info("✓ Pattern detector initialized")

    def detect_failure_patterns(self, hours: int = 168) -> List[Pattern]:
        """
        Detect recurring failure patterns in recent history.

        Args:
            hours: Hours of history to analyze (default: 168 = 1 week)

        Returns:
            List of detected patterns
        """
        patterns = []

        # Get recent events
        events = self.telemetry.get_recent_events(hours=hours, limit=10000)

        if not events:
            logger.warning("No events found in telemetry database")
            return patterns

        # Pattern 1: Recurring event types
        patterns.extend(self._detect_recurring_events(events))

        # Pattern 2: Event clustering (multiple events in short time)
        patterns.extend(self._detect_event_clusters(events))

        # Pattern 3: Event sequences (one event often followed by another)
        patterns.extend(self._detect_event_sequences(events))

        # Pattern 4: Metric threshold violations
        patterns.extend(self._detect_metric_violations(hours))

        # Pattern 5: Correlated failures
        patterns.extend(self._detect_correlated_failures(events))

        logger.info(f"Detected {len(patterns)} patterns in last {hours} hours")

        return patterns

    def _detect_recurring_events(self, events: List[Dict]) -> List[Pattern]:
        """Detect event types that occur frequently."""
        patterns = []

        # Count event types
        event_counts = Counter(e['event_type'] for e in events)

        for event_type, count in event_counts.items():
            # If event occurs more than once per day on average
            if count > len(events) / (len(set(e['timestamp'][:10] for e in events)) or 1):
                # Get sample events
                samples = [e for e in events if e['event_type'] == event_type][:5]

                pattern = Pattern(
                    pattern_type='recurring_event',
                    description=f"Event '{event_type}' occurs frequently ({count} times)",
                    frequency=count,
                    severity=self._infer_severity(samples),
                    evidence={
                        'event_type': event_type,
                        'count': count,
                        'sample_events': samples[:3]
                    },
                    suggested_action=f"Consider adding constraint to monitor '{event_type}' rate"
                )
                patterns.append(pattern)

        return patterns

    def _detect_event_clusters(self, events: List[Dict]) -> List[Pattern]:
        """Detect when events cluster in time (multiple events in short window)."""
        patterns = []

        # Group events by 5-minute windows
        windows = defaultdict(list)
        for event in events:
            # Truncate to 5-minute window
            timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            window_key = timestamp.replace(minute=(timestamp.minute // 5) * 5, second=0, microsecond=0)
            windows[window_key].append(event)

        # Find windows with many events
        for window, window_events in windows.items():
            if len(window_events) >= 5:  # 5+ events in 5 minutes
                event_types = Counter(e['event_type'] for e in window_events)

                pattern = Pattern(
                    pattern_type='event_cluster',
                    description=f"Event cluster detected: {len(window_events)} events in 5 minutes at {window}",
                    frequency=len(window_events),
                    severity='warning',
                    evidence={
                        'window_start': window.isoformat(),
                        'event_count': len(window_events),
                        'event_types': dict(event_types),
                        'sample_events': window_events[:5]
                    },
                    suggested_action="Investigate spike in activity - possible cascading failure"
                )
                patterns.append(pattern)

        return patterns

    def _detect_event_sequences(self, events: List[Dict]) -> List[Pattern]:
        """Detect when one event type is often followed by another."""
        patterns = []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e['timestamp'])

        # Look for sequences (within 1 hour)
        sequences = defaultdict(int)
        for i in range(len(sorted_events) - 1):
            event1 = sorted_events[i]
            event2 = sorted_events[i + 1]

            time1 = datetime.fromisoformat(event1['timestamp'].replace('Z', '+00:00'))
            time2 = datetime.fromisoformat(event2['timestamp'].replace('Z', '+00:00'))

            if (time2 - time1).total_seconds() < 3600:  # Within 1 hour
                sequence_key = (event1['event_type'], event2['event_type'])
                sequences[sequence_key] += 1

        # Find significant sequences (occurred 3+ times)
        for (event1_type, event2_type), count in sequences.items():
            if count >= 3:
                pattern = Pattern(
                    pattern_type='event_sequence',
                    description=f"'{event1_type}' often followed by '{event2_type}' ({count} times)",
                    frequency=count,
                    severity='info',
                    evidence={
                        'first_event': event1_type,
                        'second_event': event2_type,
                        'occurrences': count
                    },
                    suggested_action=f"Consider correlation between {event1_type} and {event2_type}"
                )
                patterns.append(pattern)

        return patterns

    def _detect_metric_violations(self, hours: int) -> List[Pattern]:
        """Detect metrics that frequently violate expected thresholds."""
        patterns = []

        # Get metric history for key metrics
        key_metrics = [
            'positions_without_sl_tp',
            'websocket_fallback_rate',
            'slippage_rejection_rate',
            'bots_silent'
        ]

        for metric_name in key_metrics:
            history = self.telemetry.get_metric_history(metric_name, hours=hours)

            if not history:
                continue

            values = [h['value'] for h in history]

            # Check for values that exceed expected thresholds
            # (These are heuristic thresholds - ideally would come from CONSTRAINTS.yml)
            thresholds = {
                'positions_without_sl_tp': 0,
                'websocket_fallback_rate': 0.20,
                'slippage_rejection_rate': 0.30,
                'bots_silent': 0
            }

            threshold = thresholds.get(metric_name)
            if threshold is not None:
                violations = [v for v in values if v > threshold]

                if violations and len(violations) / len(values) > 0.10:  # >10% violation rate
                    pattern = Pattern(
                        pattern_type='metric_violation',
                        description=f"Metric '{metric_name}' frequently exceeds threshold {threshold}",
                        frequency=len(violations),
                        severity='warning',
                        evidence={
                            'metric_name': metric_name,
                            'threshold': threshold,
                            'violation_count': len(violations),
                            'total_samples': len(values),
                            'violation_rate': len(violations) / len(values),
                            'max_value': max(values),
                            'avg_value': statistics.mean(values)
                        },
                        suggested_action=f"Tighten monitoring for '{metric_name}' or adjust threshold"
                    )
                    patterns.append(pattern)

        return patterns

    def _detect_correlated_failures(self, events: List[Dict]) -> List[Pattern]:
        """Detect when different event types tend to occur together."""
        patterns = []

        # Group events by hour
        hourly_events = defaultdict(lambda: defaultdict(int))

        for event in events:
            timestamp = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
            hourly_events[hour_key][event['event_type']] += 1

        # Find event types that co-occur
        event_types = list(set(e['event_type'] for e in events))

        for i in range(len(event_types)):
            for j in range(i + 1, len(event_types)):
                type1, type2 = event_types[i], event_types[j]

                # Count hours where both occur
                cooccurrence = sum(
                    1 for hour_events in hourly_events.values()
                    if type1 in hour_events and type2 in hour_events
                )

                total_type1 = sum(1 for hour_events in hourly_events.values() if type1 in hour_events)

                # If they co-occur >50% of the time
                if total_type1 > 0 and cooccurrence / total_type1 > 0.5 and cooccurrence >= 3:
                    pattern = Pattern(
                        pattern_type='correlated_failure',
                        description=f"'{type1}' and '{type2}' often occur together",
                        frequency=cooccurrence,
                        severity='info',
                        evidence={
                            'event_type_1': type1,
                            'event_type_2': type2,
                            'cooccurrence_count': cooccurrence,
                            'correlation_rate': cooccurrence / total_type1
                        },
                        suggested_action=f"Investigate link between {type1} and {type2}"
                    )
                    patterns.append(pattern)

        return patterns

    def _infer_severity(self, events: List[Dict]) -> str:
        """Infer severity from event samples."""
        severities = [e.get('severity', 'info') for e in events]
        severity_counts = Counter(severities)

        if 'critical' in severity_counts:
            return 'critical'
        elif 'warning' in severity_counts:
            return 'warning'
        else:
            return 'info'

    def generate_constraint_suggestions(self, patterns: List[Pattern]) -> List[ConstraintSuggestion]:
        """
        Generate constraint suggestions based on detected patterns.

        Args:
            patterns: List of detected patterns

        Returns:
            List of suggested constraints
        """
        suggestions = []

        # Group patterns by type
        patterns_by_type = defaultdict(list)
        for pattern in patterns:
            patterns_by_type[pattern.pattern_type].append(pattern)

        # Generate suggestions for recurring events
        for pattern in patterns_by_type.get('recurring_event', []):
            if pattern.frequency > 10:  # High frequency
                suggestion = self._suggest_event_rate_constraint(pattern)
                suggestions.append(suggestion)

        # Generate suggestions for metric violations
        for pattern in patterns_by_type.get('metric_violation', []):
            suggestion = self._suggest_metric_threshold_constraint(pattern)
            suggestions.append(suggestion)

        # Generate suggestions for correlated failures
        correlated = patterns_by_type.get('correlated_failure', [])
        if correlated:
            suggestion = self._suggest_correlation_constraint(correlated)
            suggestions.append(suggestion)

        logger.info(f"Generated {len(suggestions)} constraint suggestions from {len(patterns)} patterns")

        return suggestions

    def _suggest_event_rate_constraint(self, pattern: Pattern) -> ConstraintSuggestion:
        """Suggest constraint for high-frequency event."""
        event_type = pattern.evidence['event_type']

        # Generate constraint ID
        constraint_id = f"OPS-AUTO-{event_type.upper().replace('_', '-')}"

        return ConstraintSuggestion(
            constraint_id=constraint_id,
            title=f"Monitor {event_type} event rate",
            description=f"Automatically generated constraint to monitor '{event_type}' event frequency",
            category='operations',
            priority='medium',
            validation=[],  # No static validation for event rates
            telemetry=[{
                'metric': f'{event_type}_rate',
                'threshold': pattern.frequency * 0.5,  # Alert if exceeds 50% of observed rate
                'alert': 'warning',
                'description': f'Alert if {event_type} rate exceeds baseline'
            }],
            rationale=f"Detected {pattern.frequency} '{event_type}' events. High frequency suggests this should be monitored.",
            patterns=[pattern]
        )

    def _suggest_metric_threshold_constraint(self, pattern: Pattern) -> ConstraintSuggestion:
        """Suggest constraint for metric threshold violation."""
        metric_name = pattern.evidence['metric_name']
        current_threshold = pattern.evidence['threshold']
        violation_rate = pattern.evidence['violation_rate']

        constraint_id = f"METRIC-AUTO-{metric_name.upper().replace('_', '-')}"

        return ConstraintSuggestion(
            constraint_id=constraint_id,
            title=f"Tighten threshold for {metric_name}",
            description=f"Current threshold {current_threshold} violated {violation_rate:.1%} of the time",
            category='operations',
            priority='high' if violation_rate > 0.25 else 'medium',
            validation=[],
            telemetry=[{
                'metric': metric_name,
                'threshold': current_threshold * 0.8,  # Tighten by 20%
                'alert': 'warning',
                'description': f'Tightened threshold based on observed violations'
            }],
            rationale=f"Metric '{metric_name}' violated threshold {violation_rate:.1%} of the time. Consider tightening or investigating root cause.",
            patterns=[pattern]
        )

    def _suggest_correlation_constraint(self, patterns: List[Pattern]) -> ConstraintSuggestion:
        """Suggest constraint for correlated events."""
        # Use first pattern as basis
        pattern = patterns[0]
        type1 = pattern.evidence['event_type_1']
        type2 = pattern.evidence['event_type_2']

        constraint_id = f"CORR-AUTO-{type1.upper()}-{type2.upper()}"[:50]

        return ConstraintSuggestion(
            constraint_id=constraint_id,
            title=f"Monitor correlation between {type1} and {type2}",
            description=f"Events '{type1}' and '{type2}' frequently occur together",
            category='operations',
            priority='low',
            validation=[],
            telemetry=[{
                'metric': f'{type1}_and_{type2}_correlation',
                'alert_on_change': True,
                'alert': 'info',
                'description': f'Alert when {type1} and {type2} occur together'
            }],
            rationale=f"Detected correlation between '{type1}' and '{type2}'. May indicate cascading failure or common root cause.",
            patterns=patterns
        )

    def detect_anomalies(self, metric_name: str, hours: int = 168) -> List[Dict[str, Any]]:
        """
        Detect anomalies in a metric using statistical methods.

        Args:
            metric_name: Name of metric to analyze
            hours: Hours of history to analyze

        Returns:
            List of detected anomalies
        """
        history = self.telemetry.get_metric_history(metric_name, hours=hours)

        if len(history) < 10:
            logger.warning(f"Insufficient data for anomaly detection on {metric_name}")
            return []

        values = [h['value'] for h in history]
        timestamps = [h['timestamp'] for h in history]

        # Simple statistical anomaly detection
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0

        anomalies = []

        # Detect outliers (values > 2 standard deviations from mean)
        for i, (value, timestamp) in enumerate(zip(values, timestamps)):
            if stdev > 0 and abs(value - mean) > 2 * stdev:
                anomalies.append({
                    'timestamp': timestamp,
                    'value': value,
                    'mean': mean,
                    'stdev': stdev,
                    'z_score': (value - mean) / stdev,
                    'type': 'outlier'
                })

        logger.info(f"Detected {len(anomalies)} anomalies in {metric_name}")

        return anomalies


if __name__ == '__main__':
    # Example usage
    logging.basicConfig(level=logging.INFO)

    detector = PatternDetector()

    # Detect patterns
    patterns = detector.detect_failure_patterns(hours=168)

    print(f"\n📊 Detected {len(patterns)} patterns:\n")
    for pattern in patterns[:5]:  # Show first 5
        print(f"  [{pattern.severity.upper()}] {pattern.description}")
        print(f"    Frequency: {pattern.frequency}")
        print(f"    Action: {pattern.suggested_action}\n")

    # Generate suggestions
    suggestions = detector.generate_constraint_suggestions(patterns)

    print(f"\n💡 Generated {len(suggestions)} constraint suggestions:\n")
    for suggestion in suggestions:
        print(f"  [{suggestion.constraint_id}] {suggestion.title}")
        print(f"    Priority: {suggestion.priority}")
        print(f"    Rationale: {suggestion.rationale}\n")
