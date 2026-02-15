#!/usr/bin/env python3
"""
CLI tool to view market snapshot statistics and export training data.

Usage:
    python3 view_snapshots.py                    # Show statistics
    python3 view_snapshots.py --bot price_level  # Filter by bot type
    python3 view_snapshots.py --export train.csv # Export labeled data to CSV
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from ml.snapshot_collector import MarketSnapshotCollector


def main():
    parser = argparse.ArgumentParser(description='View market snapshot statistics')
    parser.add_argument('--bot', choices=['event', 'price_level', 'short_expiry'],
                       help='Filter by bot type')
    parser.add_argument('--export', type=str, metavar='FILE',
                       help='Export training data to CSV file')
    parser.add_argument('--labeled-only', action='store_true',
                       help='Only export labeled data (default: all data)')
    parser.add_argument('--db', type=str, default='data/market_snapshots.db',
                       help='Path to snapshots database (default: data/market_snapshots.db)')

    args = parser.parse_args()

    # Initialize collector
    collector = MarketSnapshotCollector(db_path=args.db)

    if args.export:
        # Export training data
        print(f"Exporting training data to {args.export}...")
        df = collector.get_training_data(
            bot_type=args.bot,
            labeled_only=args.labeled_only
        )

        if df.empty:
            print("No data to export!")
            return

        df.to_csv(args.export, index=False)
        print(f"✓ Exported {len(df)} snapshots to {args.export}")

        # Show column info
        print(f"\nColumns: {len(df.columns)}")
        print(f"Features: {[c for c in df.columns if c not in ['id', 'market_id', 'bot_type', 'snapshot_time', 'outcome', 'resolution_time']]}")

    else:
        # Show statistics
        collector.print_statistics()

        # Show unlabeled count
        unlabeled = collector.get_unlabeled_snapshots(bot_type=args.bot)
        if unlabeled:
            print(f"\nUNLABELED SNAPSHOTS: {len(unlabeled)}")
            print(f"  (These need outcomes recorded when markets resolve)")

            # Show a few examples
            print(f"\nExample unlabeled markets:")
            for snapshot in unlabeled[:5]:
                question = snapshot['question'][:60]
                expiry = snapshot.get('expiry_date', 'Unknown')
                print(f"  - {question}... (expiry: {expiry})")

            if len(unlabeled) > 5:
                print(f"  ... and {len(unlabeled) - 5} more")


if __name__ == '__main__':
    main()
