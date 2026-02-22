#!/usr/bin/env python3
"""
Enrich labeled trading data with real orderbook data from snapshots.

Joins REAL_labeled_from_alchemy.csv with market_snapshots.db to get:
- Real spreads
- Real volume
- Real liquidity
- Real bid/ask prices at trade time
"""

import pandas as pd
import sqlite3
from datetime import datetime, timedelta

print("Loading labeled data...")
df_trades = pd.read_csv('data/REAL_labeled_from_alchemy.csv')
df_trades['block_timestamp'] = pd.to_datetime(df_trades['block_timestamp'])

print(f"Loaded {len(df_trades):,} labeled trades")

print("\nLoading market snapshots...")
conn = sqlite3.connect('data/market_snapshots.db')
df_snapshots = pd.read_sql_query("""
    SELECT
        condition_id,
        snapshot_time,
        yes_price,
        no_price,
        spread,
        volume_24h,
        liquidity
    FROM market_snapshots
    WHERE yes_price IS NOT NULL
      AND no_price IS NOT NULL
      AND spread IS NOT NULL
""", conn)
conn.close()

df_snapshots['snapshot_time'] = pd.to_datetime(df_snapshots['snapshot_time'])
print(f"Loaded {len(df_snapshots):,} snapshots")

# Join trades with snapshots
# For each trade, find the closest snapshot in time
print("\nMatching trades to snapshots...")

enriched_trades = []
matched_count = 0
no_match_count = 0

for idx, trade in df_trades.iterrows():
    if idx % 10000 == 0:
        print(f"  Processed {idx:,}/{len(df_trades):,} trades...")

    # Find snapshots for this market
    market_snapshots = df_snapshots[
        df_snapshots['condition_id'] == trade['condition_id']
    ]

    if len(market_snapshots) == 0:
        # No snapshots for this market - use defaults
        trade['spread_pct'] = 5.0  # Default 5%
        trade['volume_24h'] = 1000  # Default
        trade['liquidity'] = 5000  # Default
        trade['has_real_snapshot'] = False
        no_match_count += 1
    else:
        # Find closest snapshot in time
        market_snapshots['time_diff'] = abs(
            (market_snapshots['snapshot_time'] - trade['block_timestamp']).dt.total_seconds()
        )
        closest = market_snapshots.loc[market_snapshots['time_diff'].idxmin()]

        # Add real orderbook data
        trade['spread_pct'] = closest['spread'] * 100  # Convert to percentage
        trade['volume_24h'] = closest['volume_24h']
        trade['liquidity'] = closest['liquidity']
        trade['yes_price_snapshot'] = closest['yes_price']
        trade['no_price_snapshot'] = closest['no_price']
        trade['snapshot_time_diff_seconds'] = closest['time_diff']
        trade['has_real_snapshot'] = True
        matched_count += 1

    enriched_trades.append(trade)

# Create enriched dataframe
df_enriched = pd.DataFrame(enriched_trades)

print(f"\nMatching results:")
print(f"  Matched with snapshots: {matched_count:,} ({matched_count/len(df_trades)*100:.1f}%)")
print(f"  No snapshot found: {no_match_count:,} ({no_match_count/len(df_trades)*100:.1f}%)")

if matched_count > 0:
    print(f"\nSnapshot time diff stats (for matched trades):")
    matched_df = df_enriched[df_enriched['has_real_snapshot']]
    print(f"  Mean: {matched_df['snapshot_time_diff_seconds'].mean()/3600:.1f} hours")
    print(f"  Median: {matched_df['snapshot_time_diff_seconds'].median()/3600:.1f} hours")
    print(f"  Max: {matched_df['snapshot_time_diff_seconds'].max()/3600:.1f} hours")

# Save enriched data
output_path = 'data/REAL_labeled_with_orderbook.csv'
df_enriched.to_csv(output_path, index=False)
print(f"\n✅ Saved enriched data to: {output_path}")

# Show sample comparison
print("\nSample enriched data (short bucket):")
df_enriched['hours_to_expiry'] = (
    pd.to_datetime(df_enriched['end_date']) -
    df_enriched['block_timestamp']
).dt.total_seconds() / 3600

short_enriched = df_enriched[
    (df_enriched['hours_to_expiry'] > 24) &
    (df_enriched['hours_to_expiry'] <= 72) &
    (df_enriched['has_real_snapshot'])
].head()

print(short_enriched[['trade_price', 'spread_pct', 'volume_24h', 'liquidity', 'label']])
