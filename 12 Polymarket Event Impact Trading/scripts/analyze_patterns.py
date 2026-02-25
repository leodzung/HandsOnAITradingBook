#!/usr/bin/env python3
"""
Pattern Analysis and Constraint Suggestion Script

Analyzes telemetry data to detect patterns and automatically suggests
new constraints. This is the core of the self-improving system.

Usage:
    # Analyze last week
    python scripts/analyze_patterns.py

    # Analyze specific time period
    python scripts/analyze_patterns.py --hours 336  # 2 weeks

    # Generate constraint suggestions
    python scripts/analyze_patterns.py --suggest

    # Export suggestions to file
    python scripts/analyze_patterns.py --suggest --output suggested_constraints.yml

Created: 2026-02-24 (Phase 4: Self-Improvement)
"""

import sys
import argparse
import logging
import json
import yaml
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from monitoring.pattern_detector import PatternDetector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_patterns(patterns):
    """Print detected patterns in human-readable format."""
    if not patterns:
        print("\n✅ No significant patterns detected - system appears healthy!")
        return

    print(f"\n📊 Detected {len(patterns)} Patterns:\n")
    print("=" * 80)

    # Group by severity
    by_severity = {}
    for pattern in patterns:
        severity = pattern.severity
        if severity not in by_severity:
            by_severity[severity] = []
        by_severity[severity].append(pattern)

    # Print in order of severity
    for severity in ['critical', 'warning', 'info']:
        if severity not in by_severity:
            continue

        severity_patterns = by_severity[severity]
        severity_icon = {'critical': '🔴', 'warning': '🟡', 'info': '🔵'}[severity]

        print(f"\n{severity_icon} {severity.upper()} ({len(severity_patterns)} patterns)\n")

        for i, pattern in enumerate(severity_patterns, 1):
            print(f"  {i}. {pattern.description}")
            print(f"     Type: {pattern.pattern_type}")
            print(f"     Frequency: {pattern.frequency}")
            if pattern.suggested_action:
                print(f"     💡 Action: {pattern.suggested_action}")
            print()


def print_suggestions(suggestions):
    """Print constraint suggestions in human-readable format."""
    if not suggestions:
        print("\n✅ No new constraints suggested - current constraints appear sufficient!")
        return

    print(f"\n💡 Generated {len(suggestions)} Constraint Suggestions:\n")
    print("=" * 80)

    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n{i}. [{suggestion.constraint_id}] {suggestion.title}")
        print(f"   Priority: {suggestion.priority.upper()}")
        print(f"   Category: {suggestion.category}")
        print(f"   Rationale: {suggestion.rationale}")

        if suggestion.telemetry:
            print(f"   Telemetry:")
            for tel in suggestion.telemetry:
                metric = tel.get('metric', 'N/A')
                threshold = tel.get('threshold', tel.get('alert_on_change', 'change-based'))
                print(f"     - {metric}: {threshold}")

        print(f"   Based on: {len(suggestion.patterns)} detected pattern(s)")


def export_suggestions_to_yaml(suggestions, output_file: str):
    """Export suggestions to YAML file suitable for adding to CONSTRAINTS.yml."""
    if not suggestions:
        logger.warning("No suggestions to export")
        return

    # Convert to dict format
    suggestions_dict = {
        'suggested_constraints': [s.to_dict() for s in suggestions],
        'generated_at': datetime.now().isoformat(),
        'total_suggestions': len(suggestions)
    }

    output_path = Path(output_file)
    with open(output_path, 'w') as f:
        yaml.dump(suggestions_dict, f, default_flow_style=False, sort_keys=False)

    logger.info(f"✅ Exported {len(suggestions)} suggestions to {output_file}")
    print(f"\n📄 Suggestions exported to: {output_file}")
    print(f"\nTo review and add to CONSTRAINTS.yml:")
    print(f"  1. Review {output_file}")
    print(f"  2. Select suggestions to adopt")
    print(f"  3. Move approved suggestions to CONSTRAINTS.yml")
    print(f"  4. Update constraint status from 'suggested' to 'enforced'")


def export_patterns_to_json(patterns, output_file: str):
    """Export patterns to JSON file for further analysis."""
    patterns_dict = {
        'patterns': [p.to_dict() for p in patterns],
        'generated_at': datetime.now().isoformat(),
        'total_patterns': len(patterns)
    }

    output_path = Path(output_file)
    with open(output_path, 'w') as f:
        json.dump(patterns_dict, f, indent=2)

    logger.info(f"✅ Exported {len(patterns)} patterns to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze telemetry patterns and suggest constraints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Analyze last week
  %(prog)s --hours 336                  # Analyze last 2 weeks
  %(prog)s --suggest                    # Generate constraint suggestions
  %(prog)s --suggest --output suggestions.yml  # Export suggestions
  %(prog)s --export-patterns patterns.json     # Export raw patterns
        """
    )
    parser.add_argument('--hours', type=int, default=168,
                        help='Hours of history to analyze (default: 168 = 1 week)')
    parser.add_argument('--suggest', action='store_true',
                        help='Generate constraint suggestions from patterns')
    parser.add_argument('--output', type=str,
                        help='Output file for constraint suggestions (YAML)')
    parser.add_argument('--export-patterns', type=str,
                        help='Export raw patterns to JSON file')
    parser.add_argument('--min-frequency', type=int, default=3,
                        help='Minimum pattern frequency to report (default: 3)')

    args = parser.parse_args()

    try:
        print(f"\n🔍 Analyzing telemetry data (last {args.hours} hours)...\n")

        detector = PatternDetector()

        # Detect patterns
        patterns = detector.detect_failure_patterns(hours=args.hours)

        # Filter by frequency
        patterns = [p for p in patterns if p.frequency >= args.min_frequency]

        # Print patterns
        print_patterns(patterns)

        # Export patterns if requested
        if args.export_patterns:
            export_patterns_to_json(patterns, args.export_patterns)

        # Generate suggestions if requested
        if args.suggest:
            print(f"\n🤖 Generating constraint suggestions...\n")
            suggestions = detector.generate_constraint_suggestions(patterns)

            print_suggestions(suggestions)

            # Export suggestions if output file specified
            if args.output:
                export_suggestions_to_yaml(suggestions, args.output)
            elif suggestions:
                print(f"\n💡 Tip: Use --output to export suggestions to a file")

        # Summary
        print("\n" + "=" * 80)
        print("\n📊 Analysis Summary:")
        print(f"  Time period: {args.hours} hours")
        print(f"  Patterns detected: {len(patterns)}")

        if args.suggest:
            suggestions_count = len(detector.generate_constraint_suggestions(patterns))
            print(f"  Suggestions generated: {suggestions_count}")

        print("\n✅ Analysis complete!")

    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
