#!/usr/bin/env python3
"""
Analyze actual trade performance from Alchemy on-chain data (OPTIMIZED VERSION).

Calculates real slippage, profitability, and execution metrics
from actual historical trades to calibrate backtester.

OPTIMIZATION: Uses condition_id directly from on_chain_trades table (no join needed).
"""

import sqlite3
import pandas as pd
import numpy as np
from collections import defaultdict

print("Connecting to alchemy_trades.db...")
conn = sqlite3.connect('data/alchemy_trades.db')

# Direct query without join - much faster!
# IMPORTANT: Include maker_asset_id to separate YES vs NO outcome trades
print("\nLoading trades with condition_id...")
df_trades = pd.read_sql_query("""
    SELECT
        block_timestamp,
        price,
        maker_amount_filled,
        taker_amount_filled,
        condition_id,
        maker_asset_id
    FROM on_chain_trades
    WHERE condition_id IS NOT NULL
      AND maker_asset_id IS NOT NULL
      AND price IS NOT NULL
      AND price > 0
      AND price < 1
    ORDER BY condition_id, maker_asset_id, block_timestamp
    LIMIT 500000
""", conn)

print(f"Loaded {len(df_trades):,} trades with condition IDs")

if len(df_trades) == 0:
    print("ERROR: No trades found with valid condition IDs")
    conn.close()
    exit(1)

df_trades['block_timestamp'] = pd.to_datetime(df_trades['block_timestamp'])

# Analyze by market AND outcome (to avoid mixing YES/NO prices)
print(f"\nAnalyzing trades by market and outcome...")

# Group by BOTH condition_id and maker_asset_id
market_stats = []

for (condition_id, maker_asset_id), group in df_trades.groupby(['condition_id', 'maker_asset_id']):
    if len(group) < 10:  # Need enough trades
        continue

    # Sort by time
    group = group.sort_values('block_timestamp')

    # Calculate price statistics
    prices = group['price'].values
    stats = {
        'condition_id': condition_id,
        'maker_asset_id': maker_asset_id,
        'num_trades': len(group),
        'avg_price': np.mean(prices),
        'price_std': np.std(prices),
        'price_min': np.min(prices),
        'price_max': np.max(prices),
        'price_range': np.max(prices) - np.min(prices),
        'time_span_hours': (group['block_timestamp'].max() - group['block_timestamp'].min()).total_seconds() / 3600,
    }

    # Calculate typical slippage (price changes between consecutive trades)
    if len(prices) > 1:
        price_changes = np.diff(prices)
        stats['avg_price_change'] = np.mean(np.abs(price_changes))
        stats['max_price_change'] = np.max(np.abs(price_changes))
        stats['price_volatility'] = np.std(price_changes)
        stats['median_price_change'] = np.median(np.abs(price_changes))

        # Calculate percentile-based slippage estimates
        abs_changes = np.abs(price_changes)
        stats['p50_price_change'] = np.percentile(abs_changes, 50)
        stats['p75_price_change'] = np.percentile(abs_changes, 75)
        stats['p90_price_change'] = np.percentile(abs_changes, 90)
        stats['p95_price_change'] = np.percentile(abs_changes, 95)

    market_stats.append(stats)

df_stats = pd.DataFrame(market_stats)

print(f"\nMarket-level statistics ({len(df_stats)} markets):")
print(df_stats.describe())

# Calculate aggregate slippage estimates
print(f"\nTypical slippage patterns:")
print(f"  Avg price change between trades: {df_stats['avg_price_change'].median():.4f} ({df_stats['avg_price_change'].median()*10000:.0f} bps)")
print(f"  Median price change: {df_stats['median_price_change'].median():.4f} ({df_stats['median_price_change'].median()*10000:.0f} bps)")
print(f"  P75 price change: {df_stats['p75_price_change'].median():.4f} ({df_stats['p75_price_change'].median()*10000:.0f} bps)")
print(f"  P90 price change: {df_stats['p90_price_change'].median():.4f} ({df_stats['p90_price_change'].median()*10000:.0f} bps)")
print(f"  P95 price change: {df_stats['p95_price_change'].median():.4f} ({df_stats['p95_price_change'].median()*10000:.0f} bps)")
print(f"  Max price change: {df_stats['max_price_change'].median():.4f} ({df_stats['max_price_change'].median()*10000:.0f} bps)")
print(f"  Price volatility: {df_stats['price_volatility'].median():.4f}")

# Save detailed stats
df_stats.to_csv('data/actual_trade_statistics.csv', index=False)
print(f"\n✅ Saved detailed statistics to data/actual_trade_statistics.csv")

# Show some example markets
print(f"\nExample high-volume market outcomes:")
top_markets = df_stats.nlargest(10, 'num_trades')
print(top_markets[['condition_id', 'num_trades', 'avg_price', 'price_range', 'median_price_change', 'p90_price_change']].to_string())

# Derive recommended slippage parameters
print(f"\n{'='*60}")
print("RECOMMENDED SLIPPAGE PARAMETERS FOR BACKTESTER:")
print(f"{'='*60}")

# Use P75 for base slippage (captures typical execution)
base_slippage_bps = df_stats['p75_price_change'].median() * 10000
print(f"Base slippage (entry): {base_slippage_bps:.0f} bps")

# Use P90 for exit slippage (worse execution when exiting)
exit_slippage_bps = df_stats['p90_price_change'].median() * 10000
print(f"Base slippage (exit):  {exit_slippage_bps:.0f} bps")

# Max acceptable slippage (P95 as threshold)
max_slippage_bps = df_stats['p95_price_change'].median() * 10000
print(f"Max slippage threshold: {max_slippage_bps:.0f} bps")

print(f"\nNOTE: These are empirical estimates from {len(df_trades):,} actual trades")
print(f"      across {len(df_stats)} markets. Use these to replace synthetic defaults.")

conn.close()
