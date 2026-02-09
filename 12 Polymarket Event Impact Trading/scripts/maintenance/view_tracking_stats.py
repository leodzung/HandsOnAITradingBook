#!/usr/bin/env python3
"""
View Tracking Stats - Check price tracking status
"""

from price_tracker import PriceTracker
from datetime import datetime, timedelta
import sqlite3


def main():
    print("=" * 70)
    print("PRICE TRACKING STATISTICS")
    print("=" * 70)
    print()

    tracker = PriceTracker()
    stats = tracker.get_statistics()

    # Overall stats
    print("📊 OVERALL:")
    print(f"  Total tracked:       {stats['total_tracked']}")
    print(f"  Completed:           {stats['completed']}")
    print(f"  Pending:             {stats['pending']}")
    if stats['completed'] > 0:
        print(f"  Avg completion time: {stats['avg_completion_hours']:.1f} hours")
    print()

    # Label distribution
    if stats['completed'] > 0:
        print("📋 LABEL DISTRIBUTION:")
        labels = stats['labels']
        total = sum(labels.values())
        print(f"  UP (+1):     {labels['UP']:3d}  ({labels['UP']/total*100:5.1f}%)")
        print(f"  NEUTRAL (0): {labels['NEUTRAL']:3d}  ({labels['NEUTRAL']/total*100:5.1f}%)")
        print(f"  DOWN (-1):   {labels['DOWN']:3d}  ({labels['DOWN']/total*100:5.1f}%)")
        print()

    # Recent activity
    conn = sqlite3.connect(tracker.db_path)
    cursor = conn.cursor()

    # Last 24 hours
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    cursor.execute('''
        SELECT COUNT(*) FROM tracked_events
        WHERE entry_time > ?
    ''', (cutoff,))
    recent_24h = cursor.fetchone()[0]

    print(f"⏱️  RECENT ACTIVITY:")
    print(f"  Last 24 hours: {recent_24h} events tracked")
    print()

    # Recent completions
    cursor.execute('''
        SELECT event_title, market_question, entry_price, price_24h, actual_outcome
        FROM tracked_events
        WHERE completed = 1
        ORDER BY last_checked DESC
        LIMIT 5
    ''')
    recent_completed = cursor.fetchall()

    if recent_completed:
        print("✅ RECENTLY COMPLETED:")
        outcome_symbols = {1: '↗ UP', 0: '→ NEUTRAL', -1: '↘ DOWN'}
        for i, (title, market, entry, exit, outcome) in enumerate(recent_completed, 1):
            change_pct = ((exit - entry) / entry) * 100 if exit and entry else 0
            print(f"  {i}. {title[:50]}")
            print(f"     {market[:50]}")
            print(f"     ${entry:.3f} → ${exit:.3f} ({change_pct:+.1f}%) {outcome_symbols.get(outcome, '?')}")
        print()

    # Pending by age
    cursor.execute('''
        SELECT
            CASE
                WHEN (julianday('now') - julianday(entry_time)) * 24 < 1 THEN '< 1h'
                WHEN (julianday('now') - julianday(entry_time)) * 24 < 6 THEN '1-6h'
                WHEN (julianday('now') - julianday(entry_time)) * 24 < 24 THEN '6-24h'
                ELSE '> 24h'
            END as age_group,
            COUNT(*) as count
        FROM tracked_events
        WHERE completed = 0
        GROUP BY age_group
        ORDER BY age_group
    ''')
    pending_by_age = cursor.fetchall()

    if pending_by_age:
        print("⏳ PENDING BY AGE:")
        for age_group, count in pending_by_age:
            print(f"  {age_group:8s}: {count}")
        print()

    conn.close()

    # Export status
    if stats['completed'] >= 10:
        print("💾 READY TO EXPORT:")
        print(f"  {stats['completed']} labeled samples ready")
        print(f"  Run: python3 price_tracker.py")
        print(f"  Output: data/labeled_dataset.csv")
    elif stats['completed'] > 0:
        print(f"📝 NOT ENOUGH DATA YET:")
        print(f"  {stats['completed']}/10 samples completed")
        print(f"  Need {10 - stats['completed']} more for export")
    else:
        print("📝 NO COMPLETED SAMPLES YET")
        print("  Start the trading bot to begin tracking")
        print("  Run: python3 trader.py")
    print()

    print("=" * 70)


if __name__ == '__main__':
    main()
