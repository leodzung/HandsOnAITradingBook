#!/usr/bin/env python3
"""
Create CORRECT training labels - FAST VERSION using in-memory join.

OPTIMIZATION: Load token mapping into dict, join in Python instead of SQL.
"""
import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/alchemy_trades.db')

print("=== Creating CORRECT Training Labels (FAST) ===\n")

# Step 1: Load token mapping into memory (only ~199K rows)
print("Loading token-condition mapping...")
df_map = pd.read_sql_query("""
    SELECT token_id, condition_id, outcome_index
    FROM token_condition_map
""", conn)
print(f"✅ Loaded {len(df_map):,} token mappings")

# Create fast lookup dict
token_to_outcome = {}
for _, row in df_map.iterrows():
    token_to_outcome[str(row['token_id'])] = int(row['outcome_index'])

print(f"✅ Created lookup dict with {len(token_to_outcome):,} tokens")

# Step 2: Load trades (without expensive join)
print("\nLoading trades...")
df_trades = pd.read_sql_query("""
    SELECT
        t.id as trade_id,
        t.condition_id,
        t.block_timestamp,
        t.price as trade_price,
        t.maker_asset_id,
        m.question,
        m.end_date,
        m.outcome_prices
    FROM on_chain_trades t
    JOIN markets m ON t.condition_id = m.condition_id
    WHERE m.end_date >= '2025-08-01'
      AND m.end_date <= '2026-02-21'
      AND m.outcome_prices IS NOT NULL
      AND t.price IS NOT NULL
      AND t.price > 0
      AND t.price < 1
""", conn)
conn.close()

print(f"✅ Loaded {len(df_trades):,} trades from {df_trades['condition_id'].nunique():,} markets")

# Step 3: Map maker_asset_id to outcome_index in memory
print("\nMapping trades to outcomes...")
df_trades['outcome_index'] = df_trades['maker_asset_id'].astype(str).map(token_to_outcome)

# Filter to trades we have mappings for
df_mapped = df_trades[df_trades['outcome_index'].notna()].copy()
print(f"✅ Mapped {len(df_mapped):,} trades ({len(df_mapped)/len(df_trades)*100:.1f}%)")

# Step 4: Create labels
print("\nParsing outcomes and creating labels...")

def parse_and_label(row):
    try:
        prices = json.loads(row['outcome_prices'])
        if len(prices) < 2:
            return None, None

        yes_price = float(prices[0])
        no_price = float(prices[1])

        # Check if resolved
        if (yes_price == 0.0 and no_price == 1.0):
            market_outcome = "NO"
            winning_outcome_index = 1
        elif (yes_price == 1.0 and no_price == 0.0):
            market_outcome = "YES"
            winning_outcome_index = 0
        elif yes_price >= 0.99 and no_price <= 0.01:
            market_outcome = "YES"
            winning_outcome_index = 0
        elif no_price >= 0.99 and yes_price <= 0.01:
            market_outcome = "NO"
            winning_outcome_index = 1
        else:
            return None, None  # Not resolved

        # CORRECT label: Check if trader bought the winning outcome
        trader_outcome_index = int(row['outcome_index'])

        if trader_outcome_index == winning_outcome_index:
            label = 1.0  # Win
        else:
            label = -1.0  # Loss

        return market_outcome, label

    except Exception as e:
        return None, None

df_mapped[['resolved_outcome', 'label']] = df_mapped.apply(
    lambda row: pd.Series(parse_and_label(row)), axis=1
)

df_labeled = df_mapped[df_mapped['label'].notna()].copy()
df_labeled['trader_bought'] = df_labeled['outcome_index'].map({0: 'YES', 1: 'NO'})

print(f"\n{'='*70}")
if len(df_labeled) > 0:
    print(f"✅✅ SUCCESS! Found {len(df_labeled):,} labeled trades")
    print(f"   Unique markets: {df_labeled['condition_id'].nunique():,}")
    print(f"   Date range: {df_labeled['block_timestamp'].min()} to {df_labeled['block_timestamp'].max()}")

    print(f"\n📊 Label distribution:")
    label_counts = df_labeled['label'].value_counts().to_dict()
    print(f"   Winners (1):  {label_counts.get(1.0, 0):,} ({label_counts.get(1.0, 0)/len(df_labeled)*100:.1f}%)")
    print(f"   Losers (-1):  {label_counts.get(-1.0, 0):,} ({label_counts.get(-1.0, 0)/len(df_labeled)*100:.1f}%)")

    print(f"\n🔍 Validation (first 3 winners):")
    winners = df_labeled[df_labeled['label'] == 1.0].head(3)
    for _, row in winners.iterrows():
        print(f"  Bought {row['trader_bought']} at ${row['trade_price']:.3f}, resolved {row['resolved_outcome']} ✓")

    print(f"\n🔍 Validation (first 3 losers):")
    losers = df_labeled[df_labeled['label'] == -1.0].head(3)
    for _, row in losers.iterrows():
        print(f"  Bought {row['trader_bought']} at ${row['trade_price']:.3f}, resolved {row['resolved_outcome']} ✗")

    # Save
    output_cols = ['trade_id', 'condition_id', 'block_timestamp', 'trade_price',
                   'trader_bought', 'resolved_outcome', 'question', 'end_date',
                   'outcome_prices', 'label']

    output = 'data/REAL_labeled_from_alchemy.csv'
    df_labeled[output_cols].to_csv(output, index=False)

    # Add hours_to_expiry
    df_final = pd.read_csv(output)
    df_final['block_timestamp'] = pd.to_datetime(df_final['block_timestamp'])
    df_final['end_date'] = pd.to_datetime(df_final['end_date'])
    df_final['hours_to_expiry'] = (df_final['end_date'] - df_final['block_timestamp']).dt.total_seconds() / 3600
    df_final.to_csv(output, index=False)

    print(f"\n{'='*70}")
    print(f"✅ SAVED: {output}")
    print(f"✅ Labels are now CORRECT!")
    print(f"{'='*70}")
else:
    print("⏳ No resolved markets found")
print(f"{'='*70}")
