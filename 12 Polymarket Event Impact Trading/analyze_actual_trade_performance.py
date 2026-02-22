#!/usr/bin/env python3
"""
Analyze actual trade performance from Alchemy on-chain data.

Calculates real slippage, profitability, and execution metrics
from actual historical trades to calibrate backtester.
"""

import sqlite3
import pandas as pd
import numpy as np
from collections import defaultdict

print("Connecting to alchemy_trades.db...")
conn = sqlite3.connect('data/alchemy_trades.db')

# Check token-condition mapping
print("\nChecking token-condition mapping...")
df_map = pd.read_sql_query("""
    SELECT * FROM token_condition_map LIMIT 10
""", conn)
print("Token-condition map sample:")
print(df_map.head())

# Get trades with condition IDs
print("\nLoading trades...")
df_trades = pd.read_sql_query("""
    SELECT
        t.block_timestamp,
        t.price,
        t.maker_amount_filled,
        t.taker_amount_filled,
        t.maker_asset_id,
        m.token_id,
        m.condition_id,
        m.outcome_index
    FROM on_chain_trades t
    LEFT JOIN token_condition_map m ON CAST(t.maker_asset_id AS TEXT) = CAST(m.token_id AS TEXT)
    WHERE m.condition_id IS NOT NULL
    LIMIT 100000
""", conn)

print(f"Loaded {len(df_trades):,} trades with condition IDs")

if len(df_trades) == 0:
    print("No trades found with condition IDs. Checking mapping...")
    # Try different join
    df_trades = pd.read_sql_query("""
        SELECT
            t.*,
            m.condition_id,
            m.outcome_index
        FROM on_chain_trades t
        JOIN token_condition_map m ON CAST(t.maker_asset_id AS TEXT) = CAST(m.token_id AS TEXT)
        LIMIT 10000
    """, conn)
    print(f"Found {len(df_trades):,} with direct join")

if len(df_trades) > 0:
    df_trades['block_timestamp'] = pd.to_datetime(df_trades['block_timestamp'])

    # Analyze by market
    print(f"\nAnalyzing trades by market...")

    # Group by condition_id
    market_stats = []

    for condition_id, group in df_trades.groupby('condition_id'):
        if len(group) < 10:  # Need enough trades
            continue

        # Sort by time
        group = group.sort_values('block_timestamp')

        # Calculate price statistics
        prices = group['price'].values
        stats = {
            'condition_id': condition_id,
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

        market_stats.append(stats)

    df_stats = pd.DataFrame(market_stats)

    print(f"\nMarket-level statistics ({len(df_stats)} markets):")
    print(df_stats.describe())

    # Calculate aggregate slippage estimates
    print(f"\nTypical slippage patterns:")
    print(f"  Avg price change between trades: {df_stats['avg_price_change'].median():.4f} ({df_stats['avg_price_change'].median()*10000:.0f} bps)")
    print(f"  Max price change: {df_stats['max_price_change'].median():.4f} ({df_stats['max_price_change'].median()*10000:.0f} bps)")
    print(f"  Price volatility: {df_stats['price_volatility'].median():.4f}")

    # Save detailed stats
    df_stats.to_csv('data/actual_trade_statistics.csv', index=False)
    print(f"\n✅ Saved detailed statistics to data/actual_trade_statistics.csv")

    # Show some example markets
    print(f"\nExample high-volume markets:")
    top_markets = df_stats.nlargest(5, 'num_trades')
    print(top_markets[['condition_id', 'num_trades', 'avg_price', 'price_range', 'avg_price_change']])

else:
    print("ERROR: Could not load trades with condition IDs")
    print("Checking data structure...")

    # Check what's in the tables
    print("\nSample token_condition_map:")
    df_map = pd.read_sql_query("SELECT * FROM token_condition_map LIMIT 5", conn)
    print(df_map)

    print("\nSample on_chain_trades:")
    df_sample = pd.read_sql_query("SELECT * FROM on_chain_trades LIMIT 5", conn)
    print(df_sample)

conn.close()
